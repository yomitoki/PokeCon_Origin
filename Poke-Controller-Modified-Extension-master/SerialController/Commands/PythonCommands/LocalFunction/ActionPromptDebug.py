#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare supplied action-prompt frames and retain append-only debug evidence.

This module never acquires a frame, controls a game, or imports a GUI. Callers
decide when fallback is allowed and pass the exact fresh BGR frame they accepted.
"""
from __future__ import annotations

import ast
import csv
import datetime
import hashlib
import html
import json
import math
import os
from pathlib import Path
import uuid

import cv2
import numpy as np

_STRING_NODES = tuple(getattr(ast, name) for name in ("Str", "Constant") if hasattr(ast, name))

if __package__:
    from .MaskedTemplate import masked_template_scores, validate_mask
else:
    from MaskedTemplate import masked_template_scores, validate_mask


def _check(callback):
    if callback is not None:
        callback()


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _dump(value):
    return json.dumps(_jsonable(value), ensure_ascii=False, allow_nan=False)


def _frame(frame):
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
            or frame.ndim != 3 or frame.shape[2] != 3 or not frame.size):
        raise ValueError("frame must be a nonempty, original-size uint8 BGR image")
    return frame


def _crop(image, crop):
    if not crop or not any(crop):
        return image, (0, 0)
    if len(crop) != 4:
        raise ValueError("crop must contain x1, y1, x2, y2")
    x1, y1, x2, y2 = [int(item) for item in crop]
    height, width = image.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = (width if x2 <= 0 else min(width, x2)), (height if y2 <= 0 else min(height, y2))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("crop is empty")
    return image[y1:y2, x1:x2], (x1, y1)


def _path(path, template_root):
    result = Path(os.fspath(path))
    if not result.is_absolute():
        result = Path(template_root or os.curdir) / result
    return result.resolve()


def _read(path, flags):
    data = path.read_bytes()
    result = cv2.imdecode(np.frombuffer(data, np.uint8), flags)
    if result is None:
        raise ValueError("unreadable image: " + str(path))
    return result, hashlib.sha256(data).hexdigest()


def _candidate_result(frame, candidate, index, template_root, comparison_crop):
    row = dict(_jsonable(candidate))
    row.setdefault("source_provenance", _jsonable(candidate.get("source")))
    row.update(candidate_index=index, id=str(candidate.get("id", index)),
               picture=str(candidate.get("picture", "")), score=None, matched=False,
               position=None, template_size=None, rank=None, status="error", error=None)
    try:
        threshold = float(candidate.get("threshold", .8))
        if not math.isfinite(threshold) or not -1.0 <= threshold <= 1.0:
            raise ValueError("threshold must be finite and within [-1, 1]")
        row["threshold"] = threshold
        path = _path(candidate["template_path"], template_root)
        template, digest = _read(path, cv2.IMREAD_COLOR)
        row.update(resolved_template_path=str(path), template_sha256=digest)
        mask = None
        if candidate.get("mask_path"):
            mask_path = _path(candidate["mask_path"], template_root)
            mask, mask_digest = _read(mask_path, cv2.IMREAD_GRAYSCALE)
            validate_mask(mask, template.shape)
            row.update(resolved_mask_path=str(mask_path), mask_sha256=mask_digest)
        template_crop = candidate.get("template_crop") or []
        template, _ = _crop(template, template_crop)
        if mask is not None:
            mask, _ = _crop(mask, template_crop)
        crop = candidate.get("crop") if comparison_crop is None else comparison_crop
        region, offset = _crop(frame, crop)
        row["comparison_crop"] = _jsonable(crop or [])
        row["template_size"] = [int(template.shape[1]), int(template.shape[0])]
        if region.shape[0] < template.shape[0] or region.shape[1] < template.shape[1]:
            raise ValueError("comparison region is smaller than the template")
        if candidate.get("use_gray", True):
            region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        if mask is not None:
            scores = masked_template_scores(region, template, mask)
        else:
            # OpenCV reports 1.0 for a constant template. It is not evidence.
            energy = np.asarray(template, np.float64).var(axis=(0, 1)).sum()
            if energy <= 1.e-12:
                raise ValueError("constant template has undefined normalized correlation")
            scores = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
        exclusions = candidate.get("exclude_regions") or []
        for exclusion in exclusions:
            x1, y1, x2, y2 = [int(item) for item in exclusion]
            if x2 <= x1 or y2 <= y1:
                continue
            left = max(0, x1 - offset[0] - template.shape[1] + 1)
            right = min(scores.shape[1], x2 - offset[0])
            top = max(0, y1 - offset[1] - template.shape[0] + 1)
            bottom = min(scores.shape[0], y2 - offset[1])
            if left < right and top < bottom:
                scores[top:bottom, left:right] = -2.0
        valid = np.isfinite(scores) & (scores >= -1.000001) & (scores <= 1.000001)
        if not np.any(valid):
            raise ValueError("no valid finite correlation score")
        clean = np.where(valid, scores, -2.0)
        _, score, _, position = cv2.minMaxLoc(clean)
        score = max(-1.0, min(1.0, float(score)))
        row.update(score=score, matched=score >= threshold, status="ok",
                   position=[position[0] + offset[0], position[1] + offset[1]])
    except (OSError, ValueError, TypeError, KeyError, cv2.error) as error:
        row["error"] = type(error).__name__ + ": " + str(error)
    return row


def rank_action_prompt_candidates(frame, candidates, template_root=None,
                                  comparison_crop=None, check_alive=None):
    """Rank every candidate on one supplied frame; invalid rows remain last.

    A shared comparison_crop overrides candidate crops. Same scores share the
    same competition rank; id and registration order provide stable tie ordering.
    This path performs no source scan, writes, camera access, or resizing.
    """
    _frame(frame)
    rows = []
    for index, candidate in enumerate(candidates):
        _check(check_alive)
        rows.append(_candidate_result(frame, candidate, index, template_root, comparison_crop))
    rows.sort(key=lambda row: (row["score"] is None,
                              -row["score"] if row["score"] is not None else 0,
                              row["id"], row["candidate_index"]))
    previous = None
    rank = None
    for index, row in enumerate(rows):
        if row["score"] is not None:
            if previous != row["score"]:
                rank = index + 1
            row["rank"] = rank
            previous = row["score"]
    _check(check_alive)
    return rows


def _source_evidence(source, rows, check_alive):
    result = dict(_jsonable(source))
    result.update(runtime_line=source.get("line"), disk_source_sha256=None,
                  disk_callsite=None, disk_callsite_candidates=[], source_error=None)
    for row in rows:
        row["source_usages"] = list(row.get("source_usages") or [])
    try:
        path = Path(source["source_path"]).resolve()
        data = path.read_bytes()
        text = data.decode("utf-8-sig")
        result.update(source_path=str(path), disk_source_sha256=hashlib.sha256(data).hexdigest())
        tree = ast.parse(text, filename=str(path))
        lines = text.splitlines()
        parent = {}
        for index, node in enumerate(ast.walk(tree)):
            if index % 256 == 0:
                _check(check_alive)
            for child in ast.iter_child_nodes(node):
                parent[child] = node
        def containing(node, kinds):
            while node in parent:
                node = parent[node]
                if isinstance(node, kinds):
                    return node
            return None
        def function_name(node):
            owner = containing(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            return owner.name if owner else "<module>"
        def operation(node):
            owner = containing(node, ast.Call)
            if owner is None:
                return "literal"
            return getattr(owner.func, "attr", getattr(owner.func, "id", "call"))
        ids = {}
        for row in rows:
            values = [row.get("picture"), row.get("manual_target")] + list(row.get("pictures") or [])
            for value in values:
                if value:
                    ids.setdefault(str(value), []).append(row)
        wanted = set(str(item) for item in source.get("pictures", []))
        callsites = []
        for index, node in enumerate(ast.walk(tree)):
            if index % 256 == 0:
                _check(check_alive)
            if isinstance(node, _STRING_NODES):
                value = getattr(node, "value", getattr(node, "s", None))
                if isinstance(value, str) and value in ids:
                    usage = {"source_path": str(path), "line": node.lineno, "function": function_name(node),
                             "operation": operation(node), "source_text": lines[node.lineno - 1].strip()}
                    for row in ids[value]:
                        if usage not in row["source_usages"]:
                            row["source_usages"].append(usage)
            if not isinstance(node, ast.Call):
                continue
            if source.get("function") and function_name(node) != source["function"]:
                continue
            op = getattr(node.func, "attr", getattr(node.func, "id", "call"))
            if op not in ("image_check", "ZA_story_checked_movement_action",
                          "ZA_story_wait_movement_a", "ZA_story_movement_a_check"):
                continue
            literals = {getattr(item, "value", getattr(item, "s", None))
                        for item in ast.walk(node) if isinstance(item, _STRING_NODES)
                        and isinstance(getattr(item, "value", getattr(item, "s", None)), str)}
            if wanted and not wanted.intersection(literals):
                continue
            if source.get("callsite_key") and source["callsite_key"] not in literals:
                continue
            callsites.append({"line": node.lineno, "function": function_name(node),
                              "operation": op, "pictures": sorted(wanted.intersection(literals)),
                              "source_text": lines[node.lineno - 1].strip()})
        result["disk_callsite_candidates"] = callsites
        for row in rows:
            row["source_usages"].sort(key=lambda usage: (usage.get("source_path", ""), usage.get("line", 0)))
        if len(callsites) == 1:
            resolved = dict(callsites[0])
            runtime_line = source.get("line")
            resolved["line_delta_from_runtime"] = (resolved["line"] - runtime_line
                                                   if isinstance(runtime_line, int) else None)
            result["disk_callsite"] = resolved
        result["disk_callsite_unique"] = len(callsites) == 1
        if source.get("source_text") is not None:
            result["runtime_source_text_sha256"] = hashlib.sha256(
                str(source["source_text"]).encode("utf-8")).hexdigest()
        return result, data
    except (OSError, ValueError, TypeError, KeyError, SyntaxError, UnicodeError) as error:
        result["source_error"] = type(error).__name__ + ": " + str(error)
        result["disk_callsite_unique"] = False
        return result, None


def _append(path, data):
    # One append write per event, shared safely with other PokeCon processes.
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)
    try:
        written = os.write(descriptor, data)
        if written != len(data):
            raise IOError("incomplete append: " + str(path))
    finally:
        os.close(descriptor)


def _html_report(event, rows):
    escape = lambda item: html.escape(str(item))
    source = event["source"]
    parts = ['<!doctype html><html lang="ja"><meta charset="utf-8">',
             '<title>A確認 保存画像の比較</title>',
             '<style>body{font:15px sans-serif;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:6px;vertical-align:top}img{max-width:100%;height:auto}pre{white-space:pre-wrap}</style>',
             '<h1>A確認 保存画像の比較</h1>',
             '<p>元サイズ・同一フレームを比較。無効候補は順位なし。</p>',
             '<p><a href="frame.png">保存画像</a> / <a href="ranking.csv">CSV</a> / <a href="event.json">JSON</a></p>',
             '<img src="frame.png" alt="判定に使った同一フレーム">',
             '<h2>実行箇所と保存時ソース</h2><pre>' + escape(_dump(source)) + '</pre>',
             '<table><tr><th>順位</th><th>候補</th><th>一致度 / 閾値</th><th>判定</th><th>画像・設定</th><th>ソース参照行・関数・処理</th></tr>']
    for row in rows:
        usages = '\n'.join('{}:{}: {} / {}\n{}'.format(
            usage.get("source_path", ""), usage.get("line", ""), usage.get("function", ""),
            usage.get("operation", ""), usage.get("source_text", ""))
            for usage in row["source_usages"] if isinstance(usage, dict))
        score = "—" if row["score"] is None else "{:.8f}".format(row["score"])
        settings = {key: row.get(key) for key in ("manual_target", "template_path", "template_crop", "mask_path", "crop", "comparison_crop", "position", "template_size", "source_provenance")}
        cells = [row["rank"] or "—", "{} / {} / {}".format(row["id"], row.get("text", ""), row.get("picture", "")),
                 score + " / " + str(row.get("threshold")),
                 row["error"] or ("一致" if row["matched"] else "不一致"),
                 _dump(settings), usages]
        parts.append('<tr>' + ''.join('<td><pre>' + escape(cell) + '</pre></td>' for cell in cells) + '</tr>')
    parts.append('</table></html>')
    return '\n'.join(parts)


def save_action_prompt_debug(frame, candidates, source, output_root,
                             template_root=None, comparison_crop=None,
                             fallback_detail=None, check_alive=None):
    """Save one accepted fallback and rank all word+button references.

    output_root is a stable directory supplied by the caller, never a Commands
    session directory. Existing events and index entries are never rewritten.
    Disk-source locations are explicitly separate from supplied runtime lines.
    """
    snapshot = _frame(frame).copy()
    rows = rank_action_prompt_candidates(snapshot, candidates, template_root,
                                         comparison_crop, check_alive)
    evidence, source_data = _source_evidence(source, rows, check_alive)
    _check(check_alive)
    now = datetime.datetime.now().astimezone()
    event_id = now.strftime("%Y%m%d_%H%M%S_%f_") + uuid.uuid4().hex
    root = Path(output_root).resolve()
    event_dir = root / "events" / event_id
    event_dir.mkdir(parents=True, exist_ok=False)
    ok, encoded = cv2.imencode(".png", snapshot)
    if not ok:
        raise IOError("could not encode accepted fallback frame")
    frame_data = encoded.tobytes()
    (event_dir / "frame.png").write_bytes(frame_data)
    if source_data is not None:
        (event_dir / "source_snapshot.py").write_bytes(source_data)
    event = {"schema_version": 1, "event_id": event_id, "timestamp": now.isoformat(),
             "event_dir": str(event_dir), "frame_file": "frame.png",
             "frame_shape": list(snapshot.shape), "frame_sha256": hashlib.sha256(frame_data).hexdigest(),
             "source": evidence, "fallback_detail": _jsonable(fallback_detail),
             "comparison_crop": _jsonable(comparison_crop), "ranking": rows}
    (event_dir / "event.json").write_text(_dump(event) + "\n", encoding="utf-8")
    with (event_dir / "ranking.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = ("rank", "id", "picture", "score", "threshold", "matched", "status", "error",
                  "template_path", "template_crop", "mask_path", "comparison_crop", "position",
                  "template_size", "manual_target", "source_usages", "source_provenance")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            _check(check_alive)
            writer.writerow({key: (_dump(row.get(key)) if isinstance(row.get(key), (list, dict))
                                   else row.get(key)) for key in fields})
    (event_dir / "report.html").write_text(_html_report(event, rows), encoding="utf-8")
    _check(check_alive)
    summary = {"event_id": event_id, "timestamp": event["timestamp"],
               "report": "events/" + event_id + "/report.html",
               "source": evidence, "candidate_count": len(rows)}
    _append(root / "index.jsonl", (_dump(summary) + "\n").encode("utf-8"))
    index_path = root / "index.html"
    try:
        with index_path.open("x", encoding="utf-8") as stream:
            stream.write('<!doctype html><html lang="ja"><meta charset="utf-8"><title>A確認 保存履歴</title><h1>A確認 保存履歴</h1>\n')
    except FileExistsError:
        pass
    label = "{} {} {}:{}".format(event["timestamp"], source.get("step", ""), source.get("function", ""), source.get("line", ""))
    _append(index_path, ('<p><a href="' + html.escape(summary["report"], quote=True) + '">' + html.escape(label) + '</a></p>\n').encode("utf-8"))
    return {"event_id": event_id, "event_dir": str(event_dir), "ranking": rows,
            "index_jsonl": str(root / "index.jsonl"), "source": evidence}
