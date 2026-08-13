"""Helpers for monitoring DevStudio image-detection registrations.

The GUI owns scheduling and history display.  This module keeps library
loading, searching and OpenCV matching independent from Tk so they can be
tested without opening PokeCon.
"""
from __future__ import annotations

import json
import math
import os
import time


def empty_library():
    return {"schema_version": 1, "targets": {}, "lists": {}}


def load_detection_library(path):
    """Load the DevStudio library, returning an empty library on bad input."""
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, ValueError, TypeError):
        return empty_library()
    if not isinstance(value, dict) or not isinstance(value.get("targets"), dict):
        return empty_library()
    value.setdefault("lists", {})
    return value


def filter_target_names(library, query=""):
    """Return target names matching name, description, tag, or image path."""
    needle = str(query or "").strip().casefold()
    results = []
    for name, target in library.get("targets", {}).items():
        if not isinstance(target, dict):
            continue
        variants = [item for item in target.get("variants", []) if isinstance(item, dict)]
        if not variants:
            continue
        searchable = [str(name), str(target.get("description", ""))]
        searchable.extend(str(tag) for tag in target.get("tags", []))
        searchable.extend(str(item.get("template_path", "")) for item in variants)
        if not needle or needle in " ".join(searchable).casefold():
            results.append(str(name))
    return sorted(results, key=str.casefold)


def show_value_entry_key(detail):
    """Keep different detection names/patterns as independent output rows."""
    return (str(detail.get("name", "image detection")), str(detail.get("variant") or ""))


def update_show_value_entries(entries, detail, now=None, limit=24):
    """Insert the newest detection result while keeping the cache bounded."""
    current = time.time() if now is None else float(now)
    value = dict(detail)
    value["display_timestamp"] = current
    key = show_value_entry_key(value)
    # Reinsert updated items at the end, so the displayed order follows the
    # latest actual output rather than alphabetical order.
    entries.pop(key, None)
    entries[key] = value
    while len(entries) > max(1, int(limit)):
        del entries[next(iter(entries))]
    return key


def prune_show_value_entries(entries, timeout_seconds, now=None):
    """Remove names which have not produced another result within the timeout."""
    current = time.time() if now is None else float(now)
    cutoff = current - max(0.1, float(timeout_seconds))
    stale = [key for key, value in entries.items()
             if float(value.get("display_timestamp", 0.0)) < cutoff]
    for key in stale:
        del entries[key]
    return stale


def format_show_value_entries(entries, tag="ShowValue"):
    """Render each currently active image detection as a separate block."""
    blocks = []
    for detail in entries.values():
        try:
            score = float(detail.get("score"))
            threshold = float(detail.get("threshold", 0.0))
        except (TypeError, ValueError):
            continue
        position = detail.get("position") or ("-", "-")
        variant = detail.get("variant")
        variant_text = " / パターン{}".format(variant) if variant else ""
        blocks.append(("[{}] {}{}\n"
                       "一致度: {:.6f} / 閾値: {:.6f} / {}\n"
                       "検出位置: {},{} / 取得元: {}").format(
                           str(tag or "ShowValue"),
                           detail.get("name", "image detection"), variant_text,
                           score, threshold,
                           "一致" if detail.get("matched") else "不一致",
                           position[0], position[1],
                           detail.get("source", "Commands")))
    return "\n\n".join(blocks)


def resolve_template_path(serial_root, template_path):
    path = str(template_path or "").replace("/", os.sep)
    return path if os.path.isabs(path) else os.path.join(serial_root, path)


def padded_search_crop(roi, margin, frame_shape):
    """Convert x,y,w,h into a clamped [x1,y1,x2,y2] search crop.

    Area Capture stores the selected template as x,y,w,h, while registered
    image detections use x1,y1,x2,y2.  The configured Arrow move amount is a
    tolerance around the exact template position in every direction.
    """
    if not isinstance(roi, (list, tuple)) or len(roi) != 4:
        raise ValueError("ROI must be x,y,width,height")
    if not isinstance(frame_shape, (list, tuple)) or len(frame_shape) < 2:
        raise ValueError("Frame shape must contain height and width")
    try:
        x, y, width, height = [int(value) for value in roi]
        padding = max(0, int(margin))
        frame_height, frame_width = int(frame_shape[0]), int(frame_shape[1])
    except (TypeError, ValueError):
        raise ValueError("ROI, margin, and frame shape must be integers")
    if width <= 0 or height <= 0 or frame_width <= 0 or frame_height <= 0:
        raise ValueError("ROI and frame dimensions must be positive")
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(frame_width, x + width + padding)
    y2 = min(frame_height, y + height + padding)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("ROI is outside the camera image")
    return [x1, y1, x2, y2]


def crop_search_region(frame, crop):
    """Copy the configured [x1,y1,x2,y2] search region and return its offset."""
    if frame is None or getattr(frame, "size", 0) == 0:
        raise ValueError("映像を取得できません。")
    height, width = frame.shape[:2]
    if not isinstance(crop, (list, tuple)) or len(crop) != 4:
        return frame.copy(), (0, 0)
    try:
        x1, y1, x2, y2 = [int(value) for value in crop]
    except (TypeError, ValueError):
        raise ValueError("検知範囲は [x1, y1, x2, y2] で指定してください。")
    if not any((x1, y1, x2, y2)):
        return frame.copy(), (0, 0)
    x1, y1 = max(0, min(width, x1)), max(0, min(height, y1))
    x2 = width if x2 <= 0 else max(0, min(width, x2))
    y2 = height if y2 <= 0 else max(0, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("登録された検知範囲が現在映像の外です。")
    return frame[y1:y2, x1:x2].copy(), (x1, y1)


def match_variant(source, template, variant, offset=(0, 0)):
    """Match one registered variant against an already copied search region."""
    # Keep library/search helpers usable by maintenance scripts that do not
    # install the optional OpenCV runtime used by the desktop application.
    import cv2

    if template is None or getattr(template, "size", 0) == 0:
        raise ValueError("登録画像を読み込めません。")
    use_gray = bool(variant.get("use_gray", True))
    search = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY) if use_gray else source
    target = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if use_gray else template
    if search.shape[0] < target.shape[0] or search.shape[1] < target.shape[1]:
        raise ValueError("検知範囲が登録画像より小さいです。")
    response = cv2.matchTemplate(search, target, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(response)
    if not math.isfinite(score):
        raise ValueError("類似度を計算できません。登録画像を確認してください。")
    threshold = float(variant.get("threshold", 0.8))
    absolute = (int(offset[0]) + int(location[0]), int(offset[1]) + int(location[1]))
    return {
        "score": float(score),
        "threshold": threshold,
        "matched": float(score) >= threshold,
        "position": absolute,
        "template_size": (int(template.shape[1]), int(template.shape[0])),
    }
