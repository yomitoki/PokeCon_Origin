#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a reviewable screen-transition sample from operation video.

The generated code is intentionally separate from the normal intermediate
source.  Video-derived regions are only heuristics and must remain easy to
review or replace before they are copied into a real Command.
"""
from __future__ import print_function

import os
import re

from OperationSessionModel import atomic_json, rows_for_mapping
from OperationDebugCommand import debug_output_paths


VISION_SCHEMA_VERSION = 1
VISION_METADATA_NAME = "vision_sample.json"
VISION_SOURCE_NAME = "vision_sample.py"


def _identifier(value, fallback):
    text = re.sub(r"\W+", "_", str(value or "").strip(), flags=re.UNICODE).strip("_")
    if not text:
        text = fallback
    if text[:1].isdigit():
        text = "_" + text
    return text


def vision_output_paths(session_dir):
    paths = debug_output_paths(session_dir)
    return {
        "image_dir": paths["templates"],
        "metadata": os.path.join(paths["vision"], VISION_METADATA_NAME),
        "source": os.path.join(paths["vision"], VISION_SOURCE_NAME),
        "support_log": os.path.join(paths["logs"], "vision_support.jsonl"),
    }


def _read_frame(capture, cv2, seconds):
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(seconds)) * 1000.0)
    ok, frame = capture.read()
    return frame if ok else None


def _candidate_regions(width, height):
    """Return overlapping, fixed-position regions suitable for UI screens."""
    region_width = max(96, int(round(width * 0.24)))
    region_height = max(72, int(round(height * 0.20)))
    region_width = min(region_width, width)
    region_height = min(region_height, height)
    x_values = sorted(set(int(round(value * (width - region_width) / 4.0))
                          for value in range(5)))
    y_values = sorted(set(int(round(value * (height - region_height) / 4.0))
                          for value in range(5)))
    return [(x, y, x + region_width, y + region_height)
            for y in y_values for x in x_values]


def _region_score(cv2, baseline, target, later, roi):
    x1, y1, x2, y2 = roi
    target_region = target[y1:y2, x1:x2]
    baseline_region = baseline[y1:y2, x1:x2]
    later_region = later[y1:y2, x1:x2]
    if not target_region.size or target_region.shape != baseline_region.shape \
            or target_region.shape != later_region.shape:
        return None
    target_gray = cv2.cvtColor(target_region, cv2.COLOR_BGR2GRAY)
    baseline_gray = cv2.cvtColor(baseline_region, cv2.COLOR_BGR2GRAY)
    later_gray = cv2.cvtColor(later_region, cv2.COLOR_BGR2GRAY)
    changed = float(cv2.mean(cv2.absdiff(target_gray, baseline_gray))[0])
    motion = float(cv2.mean(cv2.absdiff(target_gray, later_gray))[0])
    texture = float(cv2.Laplacian(target_gray, cv2.CV_64F).var())
    changed_score = min(1.0, changed / 40.0)
    stable_score = max(0.0, 1.0 - motion / 25.0)
    texture_score = min(1.0, texture / 500.0)
    score = 0.45 * changed_score + 0.35 * stable_score + 0.20 * texture_score
    return {
        "score": score,
        "changed": changed,
        "motion": motion,
        "texture": texture,
    }


def _write_png(cv2, path, image):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise OSError("候補画像をPNGへ変換できません: " + path)
    encoded.tofile(path)


def analyse_operation_video(session_dir, session, inputs, mappings, video_path,
                            video_sync_offset=0.0):
    """Extract one stable/distinctive candidate region near each Step end."""
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("動画判断サンプルにはOpenCVが必要です。") from error

    video_path = os.path.abspath(video_path)
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise RuntimeError("動画を開けません: " + video_path)
    paths = vision_output_paths(session_dir)
    os.makedirs(paths["image_dir"], exist_ok=True)
    candidates = []
    try:
        for sequence, mapping in enumerate(
                (item for item in mappings if item.get("kind") == "step"), 1):
            rows = rows_for_mapping(inputs, mapping)
            if not rows:
                continue
            start_time = float(rows[0].get("time", 0.0)) + float(video_sync_offset)
            end_time = float(rows[-1].get("time", 0.0)) + float(video_sync_offset)
            # A short delay after the final input usually captures the screen
            # which represents successful completion of the current Step.
            target_time = max(0.0, end_time + 0.40)
            baseline_time = max(0.0, min(start_time, target_time - 0.65))
            later_time = target_time + 0.20
            baseline = _read_frame(capture, cv2, baseline_time)
            target = _read_frame(capture, cv2, target_time)
            later = _read_frame(capture, cv2, later_time)
            if baseline is None or target is None or later is None:
                continue
            if baseline.shape[:2] != target.shape[:2] or later.shape[:2] != target.shape[:2]:
                continue
            height, width = target.shape[:2]
            scored = []
            for roi in _candidate_regions(width, height):
                details = _region_score(cv2, baseline, target, later, roi)
                if details is not None:
                    scored.append((details["score"], roi, details))
            if not scored:
                continue
            _score, roi, details = max(scored, key=lambda item: item[0])
            step_name = _identifier(mapping.get("step_name"), "STEP_{:02d}".format(sequence))
            logical_name = "AUTO_{}_COMPLETE".format(step_name.upper())
            image_name = "{:02d}_{}.png".format(sequence, logical_name.lower())
            image_path = os.path.join(paths["image_dir"], image_name)
            x1, y1, x2, y2 = roi
            _write_png(cv2, image_path, target[y1:y2, x1:x2])
            confidence = max(0.0, min(1.0, float(details["score"])))
            candidates.append({
                "sequence": sequence,
                "step_name": step_name,
                "next_step": str(mapping.get("next_step", "")).strip(),
                "logical_name": logical_name,
                "video_time": round(target_time, 3),
                "baseline_time": round(baseline_time, 3),
                "roi": [int(x1), int(y1), int(x2), int(y2)],
                "frame_size": [int(width), int(height)],
                "template_path": os.path.abspath(image_path),
                "platform_templates": {
                    "switch": os.path.abspath(image_path),
                    "steam": os.path.abspath(image_path),
                    "ps4": os.path.abspath(image_path),
                },
                "threshold": 0.82,
                "confidence": round(confidence, 4),
                "signals": {
                    "changed": round(details["changed"], 3),
                    "motion": round(details["motion"], 3),
                    "texture": round(details["texture"], 3),
                },
                "review_required": True,
                "reason": "Step終端後の、変化が大きく直後の動きが少ない領域を自動選択",
            })
    finally:
        capture.release()

    metadata = {
        "schema_version": VISION_SCHEMA_VERSION,
        "session_id": str(session.get("session_id", "operation")),
        "video_path": video_path,
        "video_sync_offset": float(video_sync_offset),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "notes": [
            "候補は自動推定です。画像、範囲、閾値を実機映像で確認してください。",
            "機種別画像は初期状態では共通です。platform_templatesを後から個別変更できます。",
        ],
    }
    atomic_json(paths["metadata"], metadata)
    return metadata


def generate_vision_sample(session_dir, session, metadata, support_timeout=300.0):
    """Generate standalone, pasteable transition checks plus support logging."""
    paths = vision_output_paths(session_dir)
    candidates = metadata.get("candidates", []) if isinstance(metadata, dict) else []
    support_log = paths["support_log"]
    session_id = str(session.get("session_id", "operation"))
    lines = [
        "# POKECON_OPERATION_VISION_SAMPLE:{}:BEGIN".format(session_id),
        "# 動画と操作記録から作った疑似サンプルです。通常の中間コードとは別表示・別管理です。",
        "# 自動抽出した画像・範囲・閾値は候補です。実機で確認してから利用してください。",
        "# 同じクラスに通常の中間コードを置くと、対応Stepを実行してから完了画面を判定します。",
        "# 指定画面が出れば次Stepへ進み、出なければサポート待ちへ入り、その利用をJSONLへ記録します。",
        "",
        "def _operation_sample_detect(self, template_path, crop, threshold=0.82):",
        "    try:",
        "        return bool(self.isContainTemplate(",
        "            template_path, threshold=threshold, use_gray=True,",
        "            show_value=True, show_position=True, crop_fmt=1, crop=crop,",
        "        ))",
        "    except Exception as error:",
        "        print('[動画判断サンプル] 画像判定失敗:', error)",
        "        return False",
        "",
        "def _operation_sample_support_memo(self, log_path, event, step_name, next_step, image_name, note):",
        "    import datetime",
        "    import json",
        "    import os",
        "    folder = os.path.dirname(os.path.abspath(log_path))",
        "    os.makedirs(folder, exist_ok=True)",
        "    record = {",
        "        'time': datetime.datetime.now().astimezone().isoformat(),",
        "        'event': event, 'support_used': True, 'step': step_name,",
        "        'next_step': next_step, 'image': image_name, 'memo': note,",
        "    }",
        "    with open(log_path, 'a', encoding='utf-8') as stream:",
        "        stream.write(json.dumps(record, ensure_ascii=False) + '\\n')",
        "",
        "def _operation_sample_wait_for_support(self, step_name, next_step, image_name,",
        "                                       template_path, crop, threshold, log_path,",
        "                                       timeout=300.0, interval=1.0):",
        "    import time",
        "    note = '自動画像判定で次Stepへ進めなかったためサポートを要求'",
        "    self._operation_sample_support_memo(",
        "        log_path, 'support_requested', step_name, next_step, image_name, note)",
        "    print('[動画判断サンプル] サポート待ち:', step_name, '->', next_step)",
        "    callback = getattr(self, 'operation_support_callback', None)",
        "    if callable(callback):",
        "        callback(step_name=step_name, next_step=next_step, image_name=image_name)",
        "    deadline = time.monotonic() + max(0.0, float(timeout))",
        "    while time.monotonic() < deadline:",
        "        if self._operation_sample_detect(template_path, crop, threshold):",
        "            self._operation_sample_support_memo(",
        "                log_path, 'support_completed', step_name, next_step, image_name,",
        "                'サポート後に指定画面を検知して通過')",
        "            return next_step or None",
        "        self.wait(max(0.05, float(interval)))",
        "    self._operation_sample_support_memo(",
        "        log_path, 'support_timeout', step_name, next_step, image_name,",
        "        'サポート待ち時間内に指定画面を検知できず同じStepを維持')",
        "    return step_name",
        "",
    ]
    if not candidates:
        lines.extend([
            "# 判定候補を生成できませんでした。動画、Step割当、同期位置を確認して再生成してください。",
            "",
        ])
    for candidate in candidates:
        step_name = _identifier(candidate.get("step_name"), "RECORDED_STEP")
        method_name = "VISION_SAMPLE_{}".format(step_name)
        next_step = str(candidate.get("next_step", "")).strip()
        shared_path = os.path.abspath(str(candidate.get("template_path", "")))
        platform_templates = candidate.get("platform_templates", {})
        if not isinstance(platform_templates, dict):
            platform_templates = {}
        platform_templates = {
            platform: os.path.abspath(str(platform_templates.get(platform) or shared_path))
            for platform in ("switch", "steam", "ps4")
        }
        lines.extend([
            "def {}(self):".format(method_name),
            "    # 候補時刻: {:.3f}秒 / 自動信頼度: {:.2f} / 要レビュー".format(
                float(candidate.get("video_time", 0.0)),
                float(candidate.get("confidence", 0.0))),
            "    image_name = {!r}".format(str(candidate.get("logical_name", ""))),
            "    platform_templates = {!r}".format(platform_templates),
            "    platform = str(getattr(self, 'game_input_target', 'switch')).lower()",
            "    template_path = platform_templates.get(platform, platform_templates['switch'])",
            "    crop = {!r}".format([int(value) for value in candidate.get("roi", [])]),
            "    threshold = {!r}".format(float(candidate.get("threshold", 0.82))),
            "    if self._operation_sample_detect(template_path, crop, threshold):",
            "        return {!r} or None".format(next_step),
            "    recorded_step = getattr(self, {!r}, None)".format(step_name),
            "    if callable(recorded_step):",
            "        recorded_step()",
            "        self.wait(0.4)",
            "    if self._operation_sample_detect(template_path, crop, threshold):",
            "        return {!r} or None".format(next_step),
            "    return self._operation_sample_wait_for_support(",
            "        {!r}, {!r}, image_name, template_path, crop, threshold,".format(
                step_name, next_step),
            "        {!r}, timeout={!r},".format(support_log, float(support_timeout)),
            "    )",
            "",
        ])
    lines.extend([
        "# POKECON_OPERATION_VISION_SAMPLE:{}:END".format(session_id),
        "",
    ])
    return "\n".join(lines)
