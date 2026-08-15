#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portable image detection and similarity-monitoring helpers.

This module deliberately does not patch PokeCon's original image APIs.  A
generated command imports this file, so copying ``LocalFunction`` together with
that command is sufficient when moving it to another PokeCon installation.
"""
from __future__ import annotations

from collections import deque
import os
import time

import cv2
import numpy as np


class SimilarityHistory:
    """Bounded time series with summary/gap data for logging and graphing."""

    def __init__(self, max_samples=3600):
        self.samples = deque(maxlen=max(1, int(max_samples)))

    def add(self, name, score, threshold, matched, timestamp=None):
        row = {
            "time": float(time.time() if timestamp is None else timestamp),
            "name": str(name),
            "score": float(score),
            "threshold": float(threshold),
            "matched": bool(matched),
        }
        self.samples.append(row)
        return row

    def values(self, name=None):
        return [dict(row) for row in self.samples if name is None or row["name"] == name]

    def summary(self, name=None, gap_seconds=1.0):
        rows = self.values(name)
        scores = [row["score"] for row in rows]
        gaps = []
        for previous, current in zip(rows, rows[1:]):
            interval = current["time"] - previous["time"]
            if interval >= float(gap_seconds):
                gaps.append({"start": previous["time"], "end": current["time"], "seconds": interval})
        return {
            "count": len(scores),
            "average": sum(scores) / len(scores) if scores else None,
            "minimum": min(scores) if scores else None,
            "maximum": max(scores) if scores else None,
            "gaps": gaps,
        }


def _command_frame(command):
    camera = getattr(command, "camera", None)
    if camera is None:
        raise RuntimeError("画像検知にはPokeConのCameraが必要です。")
    if hasattr(camera, "readFreshFrame"):
        # A momentary DirectShow/Windows scheduling gap is not an input loss.
        # Wait outside Tk for capture to resume, while still refusing the
        # cached final image if the device has genuinely stopped.
        frame = camera.readFreshFrame(timeout=0.75)
    elif hasattr(camera, "readFrame"):
        frame = camera.readFrame()
    else:
        # Compatibility for copied LocalFunction modules used with an older
        # Camera implementation.  Current PokeCon always uses readFrame(),
        # which rejects the cached final frame after input has stalled.
        frame = getattr(camera, "image_bgr", None)
    if frame is None:
        raise RuntimeError("Cameraの新しい映像を取得できません（入力停止または切替中）。")
    return frame


def _crop_region(frame, crop):
    if not crop or len(crop) != 4 or not any(int(value) for value in crop):
        return frame, (0, 0)
    x1, y1, x2, y2 = [int(value) for value in crop]
    height, width = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2 = width if x2 <= 0 else min(width, x2)
    y2 = height if y2 <= 0 else min(height, y2)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("cropは[x1, y1, x2, y2]で指定してください。")
    return frame[y1:y2, x1:x2], (x1, y1)


def detect_image(
        command,
        name,
        template_path,
        threshold=0.8,
        use_gray=True,
        show_value=False,
        show_position=True,
        show_only_true_rect=False,
        ms=2000,
        crop=None,
        match_color="blue",
        no_match_color="red",
        history=None):
    """Return match details while remaining independent of PokeCon base APIs."""
    frame = _command_frame(command)
    resolved_template_path = str(template_path)
    if not os.path.isabs(resolved_template_path):
        serial_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        resolved_template_path = os.path.join(serial_root, resolved_template_path)
    template = cv2.imread(resolved_template_path, cv2.IMREAD_COLOR)
    if template is None:
        raise FileNotFoundError("テンプレート画像を読み込めません: " + str(template_path))
    region, offset = _crop_region(frame, crop or [])
    source_match = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if use_gray else region
    template_match = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if use_gray else template
    if source_match.shape[0] < template_match.shape[0] or source_match.shape[1] < template_match.shape[1]:
        raise ValueError("検知範囲がテンプレート画像より小さいです: " + str(name))
    result = cv2.matchTemplate(source_match, template_match, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    matched = float(score) >= float(threshold)
    absolute_location = (location[0] + offset[0], location[1] + offset[1])
    if show_value:
        print("{} ZNCC value: {:.6f} / threshold: {:.6f}".format(name, score, threshold))
    if history is not None:
        history.add(name, score, threshold, matched)
    if show_position and hasattr(command, "displayRectangle") and (matched or not show_only_true_rect):
        color = [str(match_color), "orange"] if matched else [str(no_match_color), "orange"]
        command.displayRectangle(
            absolute_location,
            int(template.shape[1]),
            int(template.shape[0]),
            str(time.perf_counter()),
            ms,
            color=color,
            crop=[],
        )
    elif show_position and getattr(command, "gui", None) is not None and (matched or not show_only_true_rect):
        outline = str(match_color) if matched else str(no_match_color)
        command.gui.ImgRect(
            absolute_location[0],
            absolute_location[1],
            absolute_location[0] + int(template.shape[1]) + 1,
            absolute_location[1] + int(template.shape[0]) + 1,
            outline=outline,
            tag=str(time.perf_counter()),
            ms=int(ms),
        )
    detail = {
        "name": str(name),
        "matched": matched,
        "score": float(score),
        "threshold": float(threshold),
        "position": absolute_location,
        "template_size": (int(template.shape[1]), int(template.shape[0])),
        "show_value": bool(show_value),
        "timestamp": time.time(),
    }
    event_callback = getattr(command, "image_detection_event", None)
    if callable(event_callback):
        try:
            event_callback(detail)
        except Exception:
            # Detection itself must never fail because an optional recorder
            # consumer has already closed or is unavailable.
            pass
    return detail


def format_similarity_summary(history, name=None, gap_seconds=1.0):
    """Return a compact average/range/gap line suitable for the PokeCon log."""
    summary = history.summary(name=name, gap_seconds=gap_seconds)
    if not summary["count"]:
        return "{}: no similarity samples".format(name or "all")
    return ("{}: count={} average={:.4f} min={:.4f} max={:.4f} gaps={}".format(
        name or "all", summary["count"], summary["average"], summary["minimum"],
        summary["maximum"], len(summary["gaps"])))


def log_similarity_summary(history, name=None, gap_seconds=1.0):
    """Print and return the current continuous-monitoring summary."""
    text = format_similarity_summary(history, name=name, gap_seconds=gap_seconds)
    print(text)
    return text


def render_similarity_graph(samples, width=640, height=180, name=None):
    """Render a score/threshold graph as a BGR frame for preview or recording."""
    rows = [row for row in samples if name is None or row.get("name") == name]
    canvas = np.zeros((max(80, int(height)), max(160, int(width)), 3), dtype=np.uint8)
    canvas[:] = (28, 28, 28)
    left, top, right, bottom = 45, 15, canvas.shape[1] - 12, canvas.shape[0] - 25
    cv2.rectangle(canvas, (left, top), (right, bottom), (90, 90, 90), 1)
    cv2.putText(canvas, "1.0", (5, top + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (210, 210, 210), 1)
    cv2.putText(canvas, "0.0", (5, bottom + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (210, 210, 210), 1)
    if rows:
        visible = rows[-max(2, right - left):]
        points, thresholds = [], []
        denominator = max(1, len(visible) - 1)
        for index, row in enumerate(visible):
            x = left + int((right - left) * index / denominator)
            points.append((x, bottom - int((bottom - top) * max(0.0, min(1.0, float(row["score"]))))))
            thresholds.append((x, bottom - int((bottom - top) * max(0.0, min(1.0, float(row["threshold"]))))))
        if len(points) > 1:
            cv2.polylines(canvas, [np.array(points, dtype=np.int32)], False, (60, 220, 80), 1)
            cv2.polylines(canvas, [np.array(thresholds, dtype=np.int32)], False, (60, 120, 240), 1)
        cv2.putText(canvas, "score {:.3f}".format(float(visible[-1]["score"])), (left, canvas.shape[0] - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 220, 80), 1)
    return canvas


def compose_monitor_frame(video_frame, graph_frame, log_lines=None, output_width=None):
    """Combine camera video, similarity graph and log text into one recording frame."""
    video = video_frame.copy()
    width = int(output_width or video.shape[1])
    if video.shape[1] != width:
        video = cv2.resize(video, (width, int(video.shape[0] * width / video.shape[1])))
    graph = graph_frame
    if graph.shape[1] != width:
        graph = cv2.resize(graph, (width, int(graph.shape[0] * width / graph.shape[1])))
    log_lines = list(log_lines or [])
    log_height = max(28, 20 + 18 * len(log_lines))
    log_panel = np.zeros((log_height, width, 3), dtype=np.uint8)
    log_panel[:] = (18, 18, 18)
    for index, line in enumerate(log_lines):
        cv2.putText(log_panel, str(line), (8, 20 + 18 * index), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (220, 220, 220), 1, cv2.LINE_AA)
    return np.vstack((video, graph, log_panel))
