#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Model helpers for comparing a Commands recording with executed source."""
from __future__ import print_function

import ast
import datetime
import json
import os
import tokenize


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
        return value
    except (OSError, ValueError):
        return default


def load_command_recording(folder):
    folder = os.path.abspath(str(folder or ""))
    metadata = _load_json(os.path.join(folder, "command_monitor.json"), None)
    if not isinstance(metadata, dict):
        raise ValueError("command_monitor.jsonを読み込めません。")
    metadata["session_dir"] = folder
    return metadata


def _state_text(event):
    value = str(event.get("step_path", "") or "").strip()
    if value:
        return value
    states = event.get("states", {})
    if isinstance(states, dict):
        return " > ".join(str(item) for item in states.values() if item not in (None, ""))
    return ""


def load_command_timeline(folder):
    folder = os.path.abspath(str(folder or ""))
    path = os.path.join(folder, "steps.jsonl")
    metadata = _load_json(os.path.join(folder, "command_monitor.json"), {})
    try:
        video_duration = max(0.0, float(metadata.get("duration", 0.0) or 0.0)) \
            if isinstance(metadata, dict) else 0.0
    except (TypeError, ValueError):
        video_duration = 0.0
    rows = []
    first_wall = None
    try:
        stream = open(path, "r", encoding="utf-8")
    except OSError:
        return rows
    with stream:
        for text in stream:
            try:
                item = json.loads(text)
            except ValueError:
                continue
            if not isinstance(item, dict):
                continue
            wall = None
            try:
                wall = datetime.datetime.fromisoformat(str(item.get("time", "")))
                first_wall = first_wall or wall
            except (TypeError, ValueError):
                pass
            video_time = item.get("video_time")
            if video_time in (None, ""):
                video_time = item.get("chunk_time")
            if video_time in (None, ""):
                video_time = item.get("command_time")
            if video_time in (None, "") and wall is not None and first_wall is not None:
                video_time = (wall - first_wall).total_seconds()
            try:
                video_time = max(0.0, float(video_time or 0.0))
            except (TypeError, ValueError):
                video_time = 0.0
            if video_duration and video_time > video_duration + 0.25:
                # The retained clip can start midway through the Commands run.
                # Do not show path events that belong before/after that video.
                continue
            if video_duration:
                video_time = min(video_time, video_duration)
            location = item.get("location", {})
            if not isinstance(location, dict):
                location = {}
            item = dict(item)
            item.update({
                "index": len(rows) + 1,
                "video_time": video_time,
                "step_text": _state_text(item),
                "location": dict(location),
            })
            rows.append(item)
    # The writer preserves order.  A stable sort also repairs a legacy merge
    # in which chunk events were concatenated with equal timestamps.
    return sorted(rows, key=lambda item: (float(item["video_time"]), int(item["index"])))


def event_search_text(event):
    location = event.get("location", {}) if isinstance(event, dict) else {}
    stack = location.get("stack", []) if isinstance(location, dict) else []
    stack_text = " ".join(
        "{} {} {} {}".format(
            frame.get("function", ""), frame.get("file", ""),
            frame.get("line", ""), frame.get("source", ""))
        for frame in stack if isinstance(frame, dict))
    return " ".join((
        str(event.get("index", "")), str(event.get("event", "")),
        str(event.get("step_text", "")), str(event.get("stop_variable", "")),
        str(event.get("stop_state", "")), str(event.get("controller_input", "")),
        str(location.get("function", "")), str(location.get("file", "")),
        str(location.get("line", "")), str(location.get("source", "")), stack_text,
    )).lower()


def observed_source_lines(events, source_file):
    """Return every source line observed for one file in a trace timeline."""
    source_file = str(source_file or "").strip()
    if not source_file:
        return set()
    wanted = os.path.normcase(os.path.abspath(source_file))
    lines = set()
    for event in events or ():
        location = event.get("location", {}) if isinstance(event, dict) else {}
        if not isinstance(location, dict):
            continue
        locations = [location]
        locations.extend(
            frame for frame in location.get("stack", [])
            if isinstance(frame, dict))
        for frame in locations:
            path = str(frame.get("file", "") or "")
            try:
                matches = os.path.normcase(os.path.abspath(path)) == wanted
            except (OSError, ValueError):
                matches = False
            if not matches:
                continue
            try:
                line = int(frame.get("line", 0) or 0)
            except (TypeError, ValueError):
                line = 0
            if line > 0:
                lines.add(line)
    return lines


def filtered_timeline(events, query="", stops_only=False):
    query = str(query or "").strip().lower()
    result = []
    for event in events:
        if stops_only and event.get("event") != "step_debug_stop":
            continue
        if query and query not in event_search_text(event):
            continue
        result.append(event)
    return result


def timeline_page(events, page=0, page_size=500):
    page_size = max(50, int(page_size))
    page_count = max(1, (len(events) + page_size - 1) // page_size)
    page = min(max(0, int(page)), page_count - 1)
    start = page * page_size
    return events[start:start + page_size], page, page_count


def video_candidates(folder):
    folder = os.path.abspath(str(folder or ""))
    result = []
    for label, filename in (("結合済みMP4", "recording.mp4"),
                            ("録画AVI", "recording.avi")):
        path = os.path.join(folder, filename)
        if os.path.isfile(path):
            result.append((label, path))
    return result


def resolve_event_source(folder, metadata, event):
    location = dict(event.get("location", {}) or {})
    snapshot = str(location.get("snapshot", "") or "")
    if snapshot:
        path = os.path.abspath(os.path.join(folder, snapshot))
        try:
            if os.path.commonpath([os.path.abspath(folder), path]) == os.path.abspath(folder) \
                    and os.path.isfile(path):
                return path, location
        except ValueError:
            pass
    original = str(location.get("file", "") or "")
    if original and os.path.isfile(original):
        return os.path.abspath(original), location
    source = metadata.get("source", {}) if isinstance(metadata, dict) else {}
    if isinstance(source, dict):
        snapshot = str(source.get("snapshot", "") or "")
        if snapshot:
            path = os.path.abspath(os.path.join(folder, snapshot))
            if os.path.isfile(path):
                return path, dict(source)
        original = str(source.get("file", "") or "")
        if original and os.path.isfile(original):
            return os.path.abspath(original), dict(source)
    return "", location


def _read_source(path):
    with tokenize.open(path) as stream:
        return stream.read()


def source_function_block(path, function_name="", line=0, context=25):
    """Return the most relevant function block and its absolute line range."""
    source = _read_source(path)
    lines = source.splitlines(True)
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        tree = None
    line = max(0, int(line or 0))
    candidates = []
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            end = max([
                int(getattr(item, "end_lineno", 0)
                    or getattr(item, "lineno", 0) or 0)
                for item in ast.walk(node)
            ] or [int(node.lineno)])
            score = 0
            if function_name and node.name == function_name:
                score += 4
            if line and int(node.lineno) <= line <= end:
                score += 8
            if score:
                candidates.append((score, -(end - int(node.lineno)), node, end))
    if candidates:
        _score, _length, node, end = max(candidates, key=lambda item: (item[0], item[1]))
        start = min([int(node.lineno)] +
                    [int(item.lineno) for item in getattr(node, "decorator_list", [])])
    else:
        center = min(max(1, line or 1), max(1, len(lines)))
        start = max(1, center - int(context))
        end = min(len(lines), center + int(context))
    return {
        "path": os.path.abspath(path),
        "start_line": start,
        "end_line": end,
        "highlight_line": line,
        "text": "".join(lines[start - 1:end]),
    }
