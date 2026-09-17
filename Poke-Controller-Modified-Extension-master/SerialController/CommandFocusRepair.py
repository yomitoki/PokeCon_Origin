#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure helpers for target-function focused Commands repair recordings."""
from __future__ import annotations

import re


_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")


def normalize_focus_function_name(value):
    """Accept ``self.func(...)`` or a dotted name and return ``func`` only."""
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^[\-\u2022]+\s*", "", text)
    text = text.split("#", 1)[0].strip()
    text = re.sub(r"\s*\(.*$", "", text).strip()
    text = text.rstrip(".:;,").strip()
    if "." in text:
        text = text.rsplit(".", 1)[-1].strip()
    return text if _IDENTIFIER.fullmatch(text) else ""


def parse_focus_function_targets(value):
    """Parse a newline/comma/semicolon separated target list, preserving order."""
    if isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = re.split(r"[,;\n\r]+", str(value or ""))
    result = []
    seen = set()
    for item in raw:
        name = normalize_focus_function_name(item)
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def location_function_names(location):
    """Return innermost-to-outermost functions represented by one stack sample."""
    if not isinstance(location, dict):
        return []
    result = []
    seen = set()
    frames = [location]
    frames.extend(item for item in location.get("stack", [])
                  if isinstance(item, dict))
    for frame in frames:
        name = normalize_focus_function_name(frame.get("function", ""))
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def matching_focus_functions(location, targets):
    """Return active targets in stack order (innermost target first)."""
    wanted = set(parse_focus_function_targets(targets))
    return [name for name in location_function_names(location) if name in wanted]


def matching_focus_function(location, targets):
    matches = matching_focus_functions(location, targets)
    return matches[0] if matches else ""


def focus_segment_id(function_name, occurrence, start_time):
    return "{}-{:04d}-{:.3f}".format(
        normalize_focus_function_name(function_name) or "function",
        max(1, int(occurrence)), max(0.0, float(start_time or 0.0)))


def build_focus_segments(events, targets, duration=0.0):
    """Build independent, possibly overlapping intervals for every target."""
    targets = parse_focus_function_targets(targets)
    if not targets:
        return []
    ordered = sorted(
        [event for event in (events or []) if isinstance(event, dict)],
        key=lambda item: (
            float(item.get("video_time", 0.0) or 0.0),
            int(item.get("index", 0) or 0)))
    try:
        recording_end = max(0.0, float(duration or 0.0))
    except (TypeError, ValueError):
        recording_end = 0.0
    if ordered:
        recording_end = max(
            recording_end,
            max(float(item.get("video_time", 0.0) or 0.0)
                for item in ordered))

    occurrences = {name: 0 for name in targets}
    segments = []
    active = {}

    def close_active(name, end_time):
        segment = active.pop(name, None)
        if segment is None:
            return
        segment["end_time"] = max(
            float(segment["start_time"]), float(end_time or 0.0))
        segment["duration"] = max(
            0.0, segment["end_time"] - segment["start_time"])
        segment["step_paths"] = list(segment.pop("_step_paths"))
        segment["event_count"] = len(segment["event_indices"])
        segments.append(segment)

    def open_active(name, now):
        if name in active:
            return active[name]
        occurrences[name] += 1
        active[name] = {
            "id": focus_segment_id(name, occurrences[name], now),
            "function": name,
            "occurrence": occurrences[name],
            "start_time": now,
            "end_time": now,
            "duration": 0.0,
            "event_indices": [],
            "events": [],
            "_step_paths": [],
            "source_file": "",
            "source_snapshot": "",
        }
        return active[name]

    def append_event(name, event, now):
        segment = open_active(name, now)
        segment["end_time"] = now
        segment["event_indices"].append(int(event.get("index", 0) or 0))
        segment["events"].append(event)
        step = str(event.get("step_text", "")
                   or event.get("step_path", "") or "").strip()
        if step and step not in segment["_step_paths"]:
            segment["_step_paths"].append(step)
        location = event.get("location", {})
        if not isinstance(location, dict):
            return
        frames = [location]
        frames.extend(frame for frame in location.get("stack", [])
                      if isinstance(frame, dict))
        target_frame = next(
            (frame for frame in frames
             if normalize_focus_function_name(frame.get("function", "")) == name),
            location)
        if not segment["source_file"]:
            segment["source_file"] = str(target_frame.get("file", "") or "")
        if not segment["source_snapshot"]:
            segment["source_snapshot"] = str(
                target_frame.get("snapshot", "") or "")

    for event in ordered:
        now = max(0.0, float(event.get("video_time", 0.0) or 0.0))
        location = event.get("location", {})
        sampled_functions = location_function_names(location)
        annotated = normalize_focus_function_name(
            event.get("focus_function", ""))
        is_exact = bool(event.get("focus_trace"))
        if is_exact and annotated in targets:
            append_event(annotated, event, now)
            if (str(event.get("focus_trace_phase", "") or "") == "return"
                    and int(event.get("focus_trace_depth", 1) or 1) <= 1):
                close_active(annotated, now)
            continue

        matched = matching_focus_functions(location, targets)
        for name in parse_focus_function_targets(
                event.get("focus_target_stack", [])):
            if name in targets and name not in matched:
                matched.append(name)
        if annotated in targets and annotated not in matched:
            matched.insert(0, annotated)
        if not sampled_functions and not matched:
            if event.get("event") == "loop_processing_skipped":
                for name in list(active):
                    close_active(name, now)
            else:
                for name in list(active):
                    append_event(name, event, now)
            continue
        # A real stack sample proves which targets are active at this instant.
        for name in list(active):
            if name not in matched:
                close_active(name, now)
        for name in matched:
            append_event(name, event, now)
    for name in list(active):
        close_active(name, recording_end)
    target_order = {name: index for index, name in enumerate(targets)}
    return sorted(segments, key=lambda item: (
        float(item.get("start_time", 0.0) or 0.0),
        target_order.get(item.get("function", ""), len(target_order)),
        int(item.get("occurrence", 0) or 0)))
