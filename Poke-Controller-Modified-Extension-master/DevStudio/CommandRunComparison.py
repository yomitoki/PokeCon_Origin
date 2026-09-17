#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline comparison and safe function restore for Commands recordings."""
from __future__ import annotations

import datetime
import difflib
import hashlib
import io
import json
import os
import re
import tokenize
import uuid

try:
    import cv2
except ImportError:  # The non-image alignment/restore helpers still work.
    cv2 = None

from CommandRecordingModel import video_candidates
from SampleFunctionSync import function_records, replace_class_functions


MAX_STEP_VISITS = 5000
MAX_ALIGNMENT_ROWS = 7000
MAX_DIFF_LINES = 2000


def step_visits(events, max_visits=MAX_STEP_VISITS):
    """Collapse only consecutive equal Steps; keep every later revisit."""
    visits = []
    occurrences = {}
    previous = None
    for event in events or ():
        step = str(event.get("step_text", "") or event.get("step_path", "") or "").strip()
        if not step:
            continue
        if step == previous:
            # Prefer the event that actually owns a clean Step-start image.
            if event.get("step_frame") and visits and not visits[-1].get("step_frame"):
                visits[-1]["step_frame"] = str(event.get("step_frame", ""))
                visits[-1]["clean_frame"] = bool(event.get("clean_frame"))
            continue
        if len(visits) >= max(1, int(max_visits)):
            break
        previous = step
        occurrences[step] = occurrences.get(step, 0) + 1
        location = event.get("location", {})
        if not isinstance(location, dict):
            location = {}
        visits.append({
            "visit_index": len(visits),
            "step": step,
            "occurrence": occurrences[step],
            "event_index": int(event.get("index", len(visits) + 1) or len(visits) + 1),
            "video_time": max(0.0, float(event.get("video_time", 0.0) or 0.0)),
            "event": event,
            "location": dict(location),
            "step_frame": str(event.get("step_frame", "") or ""),
            "clean_frame": bool(event.get("clean_frame")),
        })
    return visits


def align_step_visits(baseline_visits, current_visits,
                      max_rows=MAX_ALIGNMENT_ROWS):
    """Align repeated Step visits while retaining extra recovery passes."""
    baseline = list(baseline_visits or ())[:MAX_STEP_VISITS]
    current = list(current_visits or ())[:MAX_STEP_VISITS]
    matcher = difflib.SequenceMatcher(
        None, [item["step"] for item in baseline],
        [item["step"] for item in current], autojunk=False)
    rows = []

    def append(status, left=None, right=None):
        if len(rows) >= max(1, int(max_rows)):
            return
        rows.append({
            "row_index": len(rows), "status": status,
            "baseline": left, "current": right,
        })

    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        left_items = baseline[left_start:left_end]
        right_items = current[right_start:right_end]
        if tag == "equal":
            for left, right in zip(left_items, right_items):
                append("match", left, right)
        elif tag == "delete":
            for left in left_items:
                append("baseline_only", left, None)
        elif tag == "insert":
            for right in right_items:
                append("current_only", None, right)
        else:
            paired = min(len(left_items), len(right_items))
            for index in range(paired):
                append("mismatch", left_items[index], right_items[index])
            for left in left_items[paired:]:
                append("baseline_only", left, None)
            for right in right_items[paired:]:
                append("current_only", None, right)

    first_divergence = next(
        (index for index, row in enumerate(rows) if row["status"] != "match"), None)
    matched_baseline = [
        int(row["baseline"]["visit_index"])
        for row in rows if row["status"] == "match" and row.get("baseline")]
    counts = {name: sum(1 for row in rows if row["status"] == name)
              for name in ("match", "mismatch", "baseline_only", "current_only")}
    summary = {
        "baseline_visits": len(baseline),
        "current_visits": len(current),
        "rows": len(rows),
        "truncated": len(rows) >= max(1, int(max_rows)),
        "first_divergence": first_divergence,
        "furthest_matched_baseline": max(matched_baseline) if matched_baseline else -1,
        "regressed": counts["baseline_only"] > 0,
        "not_reached": counts["baseline_only"],
        "extra_or_retry": counts["current_only"],
        "mismatch": counts["mismatch"],
        "matched": counts["match"],
    }
    return rows, summary


def discover_recording_folders(current_folder, limit=200):
    """Find sibling recordings without recursively scanning the workspace."""
    current = os.path.abspath(str(current_folder or ""))
    parent = os.path.dirname(current)
    result = []
    try:
        entries = list(os.scandir(parent))
    except OSError:
        return result
    for entry in entries:
        if not entry.is_dir() or os.path.normcase(entry.path) == os.path.normcase(current):
            continue
        metadata = os.path.join(entry.path, "command_monitor.json")
        if not os.path.isfile(metadata):
            continue
        try:
            modified = os.path.getmtime(metadata)
        except OSError:
            modified = 0.0
        result.append((modified, os.path.abspath(entry.path)))
    result.sort(reverse=True)
    return [path for _modified, path in result[:max(1, int(limit))]]


def _safe_recording_artifact(folder, relative):
    folder = os.path.abspath(str(folder or ""))
    relative = str(relative or "").strip()
    if not relative:
        return ""
    path = os.path.abspath(os.path.join(folder, relative))
    try:
        safe = os.path.commonpath([folder, path]) == folder
    except ValueError:
        safe = False
    return path if safe and os.path.isfile(path) else ""


def load_visit_frame(folder, visit):
    """Load a clean still, or explicitly fall back to a legacy video frame."""
    if cv2 is None:
        raise RuntimeError("OpenCVが見つからないため画面比較できません。")
    visit = visit or {}
    path = _safe_recording_artifact(folder, visit.get("step_frame", ""))
    if path:
        frame = cv2.imread(path, cv2.IMREAD_COLOR)
        if frame is not None:
            return {
                "frame": frame, "kind": "clean_step_frame", "path": path,
                "warning": "",
            }
    for _label, video in video_candidates(folder):
        capture = cv2.VideoCapture(video)
        try:
            capture.set(cv2.CAP_PROP_POS_MSEC,
                        max(0.0, float(visit.get("video_time", 0.0) or 0.0)) * 1000.0)
            ok, frame = capture.read()
        finally:
            capture.release()
        if ok and frame is not None:
            return {
                "frame": frame, "kind": "legacy_video_frame", "path": video,
                "warning": "旧録画の動画フレームです（録画設定により検知枠を含む場合があります）。",
            }
    return {
        "frame": None, "kind": "missing", "path": "",
        "warning": "Step開始画像と録画動画を読み込めません。",
    }


def compare_frames(baseline_frame, current_frame):
    if cv2 is None:
        raise RuntimeError("OpenCVが見つからないため画面比較できません。")
    if baseline_frame is None or current_frame is None:
        return {"similarity": None, "difference": None, "current_resized": current_frame}
    height, width = baseline_frame.shape[:2]
    resized = current_frame
    if current_frame.shape[:2] != (height, width):
        resized = cv2.resize(current_frame, (width, height), interpolation=cv2.INTER_AREA)
    difference = cv2.absdiff(baseline_frame, resized)
    mean = float(difference.mean())
    gray = cv2.cvtColor(difference, cv2.COLOR_BGR2GRAY)
    heatmap = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
    return {
        "similarity": max(0.0, min(1.0, 1.0 - mean / 255.0)),
        "difference": heatmap,
        "current_resized": resized,
    }


def unified_function_diff(left_path, left_function,
                          right_path, right_function, max_lines=MAX_DIFF_LINES):
    with tokenize.open(left_path) as stream:
        left_source = stream.read()
    with tokenize.open(right_path) as stream:
        right_source = stream.read()
    left = function_records(left_source, class_only=True).get(str(left_function or ""))
    right = function_records(right_source, class_only=True).get(str(right_function or ""))
    if not left or not right:
        missing = left_function if not left else right_function
        raise ValueError("比較対象の関数が見つかりません: " + str(missing or "(未記録)"))
    lines = list(difflib.unified_diff(
        left["text"].splitlines(), right["text"].splitlines(),
        fromfile=os.path.basename(left_path) + ":" + str(left_function),
        tofile=os.path.basename(right_path) + ":" + str(right_function),
        lineterm=""))
    truncated = len(lines) > max(1, int(max_lines))
    if truncated:
        lines = lines[:max(1, int(max_lines))]
        lines.append("... 差分表示を{}行で省略しました ...".format(max_lines))
    return {"text": "\n".join(lines) or "（関数内容は同一です）",
            "truncated": truncated, "different": left["normalized"] != right["normalized"]}


def _read_source_bytes(path):
    with open(path, "rb") as stream:
        raw = stream.read()
    encoding, _lines = tokenize.detect_encoding(io.BytesIO(raw).readline)
    source = raw.decode(encoding)
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return raw, source, encoding, newline


def prepare_function_restore(baseline_source_path, target_source_path,
                             function_name):
    """Build and validate a whole-function restore plan without writing."""
    baseline_path = os.path.abspath(str(baseline_source_path or ""))
    target_path = os.path.abspath(str(target_source_path or ""))
    function_name = str(function_name or "").strip()
    if not os.path.isfile(baseline_path):
        raise ValueError("基準録画のソーススナップショットが見つかりません。")
    if not os.path.isfile(target_path) or not target_path.lower().endswith(".py"):
        raise ValueError("復元先の実ソース.pyが見つかりません。")
    if not function_name:
        raise ValueError("復元する関数を選択してください。")
    _baseline_raw, baseline_source, _baseline_encoding, _baseline_newline = \
        _read_source_bytes(baseline_path)
    target_raw, target_source, encoding, newline = _read_source_bytes(target_path)
    baseline_record = function_records(baseline_source, class_only=True).get(function_name)
    target_record = function_records(target_source, class_only=True).get(function_name)
    if baseline_record is None or target_record is None:
        raise ValueError("両方のソースに同じ関数がありません: " + function_name)
    updated = replace_class_functions(
        target_source, {function_name: baseline_record["text"]})
    # Preserve the live source's newline and encoding after AST validation.
    compile(updated, target_path, "exec")
    normalized = updated.replace("\r\n", "\n").replace("\r", "\n")
    if newline != "\n":
        normalized = normalized.replace("\n", newline)
    updated_raw = normalized.encode(encoding)
    diff_lines = list(difflib.unified_diff(
        target_record["text"].splitlines(), baseline_record["text"].splitlines(),
        fromfile="現在の実ソース:" + function_name,
        tofile="基準録画:" + function_name, lineterm=""))
    return {
        "baseline_source_path": baseline_path,
        "target_source_path": target_path,
        "function_name": function_name,
        "target_before_hash": hashlib.sha256(target_raw).hexdigest(),
        "target_before_raw": target_raw,
        "updated_raw": updated_raw,
        "different": target_raw != updated_raw,
        "diff": "\n".join(diff_lines[:MAX_DIFF_LINES]) or "（関数内容は同一です）",
        "diff_truncated": len(diff_lines) > MAX_DIFF_LINES,
    }


def apply_function_restore(plan, timestamp=None):
    """Atomically apply a prepared plan after making a recoverable backup."""
    target = os.path.abspath(str((plan or {}).get("target_source_path", "")))
    if not os.path.isfile(target):
        raise ValueError("復元先の実ソースが見つかりません。")
    with open(target, "rb") as stream:
        current_raw = stream.read()
    if hashlib.sha256(current_raw).hexdigest() != plan.get("target_before_hash"):
        raise RuntimeError("確認後に実ソースが変更されたため、復元を中止しました。再比較してください。")
    if not plan.get("different"):
        return {"changed": False, "target": target, "backup": "", "manifest": ""}
    when = timestamp or datetime.datetime.now()
    stamp = when.strftime("%Y%m%d_%H%M%S_%f")
    function = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(plan.get("function_name", "function")))
    backup_dir = os.path.join(os.path.dirname(target), ".pokecon-command-backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup = os.path.join(backup_dir, "{}_{}.py.bak".format(stamp, function))
    manifest = backup + ".json"
    with open(backup, "wb") as stream:
        stream.write(current_raw)
    manifest_data = {
        "created_at": when.isoformat(timespec="seconds"),
        "target": target,
        "backup": backup,
        "baseline_source": plan.get("baseline_source_path", ""),
        "function": plan.get("function_name", ""),
        "before_sha256": plan.get("target_before_hash", ""),
        "after_sha256": hashlib.sha256(plan["updated_raw"]).hexdigest(),
    }
    with open(manifest, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest_data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    temporary = target + ".command-restore.tmp-" + uuid.uuid4().hex
    try:
        with open(temporary, "wb") as stream:
            stream.write(plan["updated_raw"])
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise
    return {"changed": True, "target": target,
            "backup": backup, "manifest": manifest}
