"""Helpers for monitoring DevStudio image-detection registrations.

The GUI owns scheduling and history display.  This module keeps library
loading, searching and OpenCV matching independent from Tk so they can be
tested without opening PokeCon.
"""
from __future__ import annotations

import json
import math
import os


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


def resolve_template_path(serial_root, template_path):
    path = str(template_path or "").replace("/", os.sep)
    return path if os.path.isabs(path) else os.path.join(serial_root, path)


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
