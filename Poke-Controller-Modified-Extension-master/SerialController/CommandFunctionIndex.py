#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a compact caller index for selected common Commands functions."""
from __future__ import annotations

import json
import os
import re
import uuid


INDEX_FILE_NAME = "common_function_index.json"
BATTLE_RENDA_GROUP = {
    "id": "battle_renda_three_functions",
    "name": "バトル連打 共通3関数",
    "functions": [
        "ZA_story_Template_battle_before_renda_route",
        "ZA_story_Template_battle_function_renda_route",
        "ZA_story_Template_battle_after_renda_route",
    ],
}


def normalize_function_groups(groups):
    """Return JSON-safe groups with normalized, de-duplicated function names."""
    result = []
    for position, raw in enumerate(groups or ()): 
        if not isinstance(raw, dict):
            continue
        functions = []
        for value in raw.get("functions", ()): 
            name = str(value or "").strip()
            if name.startswith("self."):
                name = name[5:]
            name = name.split("(", 1)[0].strip().rstrip(".")
            if "." in name:
                name = name.rsplit(".", 1)[-1]
            if name and name not in functions:
                functions.append(name)
        if not functions:
            continue
        group_id = str(raw.get("id", "") or "").strip()
        if not group_id:
            group_id = "function_group_{}".format(position + 1)
        result.append({
            "id": group_id,
            "name": str(raw.get("name", "") or group_id),
            "functions": functions,
        })
    return result


def group_targets(groups):
    result = []
    for group in normalize_function_groups(groups):
        for name in group["functions"]:
            if name not in result:
                result.append(name)
    return result


def enabled_common_function_groups(battle_renda_enabled=False):
    return [dict(BATTLE_RENDA_GROUP)] if battle_renda_enabled else []


def _video_time(event):
    for key in ("video_time", "chunk_time", "command_time"):
        try:
            value = event.get(key)
            if value not in (None, ""):
                return max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return 0.0


def _caller_frames(event, target):
    location = event.get("location", {})
    if not isinstance(location, dict):
        return []
    frames = []
    for frame in location.get("stack", ()): 
        if not isinstance(frame, dict):
            continue
        name = str(frame.get("function", "") or "")
        if name == target and not frames:
            continue
        item = {
            key: frame.get(key) for key in
            ("file", "function", "line", "source", "snapshot")
            if frame.get(key) not in (None, "")
        }
        if item and item.get("function") != target:
            frames.append(item)
    return frames


def _step_owner(frames):
    """Prefer the outer Step-style method, while retaining arbitrary callers."""
    if not frames:
        return ""
    for frame in frames:
        name = str(frame.get("function", "") or "")
        if re.match(r"^_[0-9].+", name):
            return name
    return str(frames[0].get("function", "") or "")


def build_common_function_index(events, groups, duration=0.0):
    """Pair target call/return events and expose their runtime callers."""
    events = [dict(event) for event in (events or ())
              if isinstance(event, dict)]
    groups = normalize_function_groups(groups)
    target_group = {
        function: group for group in groups for function in group["functions"]
    }
    active = {}
    occurrences = []
    counters = {}

    def close(key, end_time, return_event=None):
        occurrence = active.pop(key, None)
        if occurrence is None:
            return
        occurrence["end_seconds"] = max(
            occurrence["start_seconds"], float(end_time))
        occurrence["duration_seconds"] = round(
            occurrence["end_seconds"] - occurrence["start_seconds"], 6)
        if isinstance(return_event, dict):
            occurrence["return_line"] = dict(
                return_event.get("location", {}) or {}).get("line")
        occurrences.append(occurrence)

    for event in events:
        if not event.get("focus_trace"):
            continue
        target = str(event.get("focus_function", "") or "")
        group = target_group.get(target)
        if group is None:
            continue
        phase = str(event.get("focus_trace_phase", "") or "")
        depth = max(1, int(event.get("focus_trace_depth", 1) or 1))
        key = (target, depth)
        now = _video_time(event)
        if phase == "call":
            if key in active:
                close(key, now)
            counters[target] = counters.get(target, 0) + 1
            callers = _caller_frames(event, target)
            location = dict(event.get("location", {}) or {})
            active[key] = {
                "id": "{}-{:04d}".format(target, counters[target]),
                "group_id": group["id"],
                "group_name": group["name"],
                "target_function": target,
                "occurrence": counters[target],
                "direct_caller": str(
                    callers[0].get("function", "") if callers else ""),
                "step_owner": _step_owner(callers),
                "caller_stack": callers,
                "step_path": str(event.get("step_path", "") or ""),
                "start_seconds": now,
                "source": {
                    key: location.get(key) for key in
                    ("file", "function", "line", "source", "snapshot")
                    if location.get(key) not in (None, "")
                },
                "step_frame": str(event.get("step_frame", "") or ""),
            }
        elif phase == "return":
            close(key, now, event)

    final_time = max(0.0, float(duration or 0.0))
    for key in list(active):
        start = active[key]["start_seconds"]
        close(key, max(start, final_time))
    occurrences.sort(key=lambda item: (
        float(item["start_seconds"]), item["target_function"],
        int(item["occurrence"])))
    for occurrence in occurrences:
        start = float(occurrence["start_seconds"])
        end = float(occurrence["end_seconds"])
        event_indexes = []
        evidence = []
        frames = []
        for position, event in enumerate(events, start=1):
            when = _video_time(event)
            if when < start or when > end:
                continue
            event_indexes.append(position)
            step_frame = str(event.get("step_frame", "") or "")
            if step_frame and step_frame not in frames:
                frames.append(step_frame)
            event_name = str(event.get("event", "") or "")
            if event_name in ("state", "focus_line"):
                continue
            item = {
                "event_index": position,
                "video_time": when,
                "event": event_name,
                "step_path": str(event.get("step_path", "") or ""),
            }
            for key, value in event.items():
                if (key in item or key in (
                        "location", "states", "focus_trace", "focus_function",
                        "focus_trace_phase", "focus_trace_sequence",
                        "focus_trace_depth", "time", "chunk_time",
                        "command_time", "video_time", "step_path", "event")):
                    continue
                if isinstance(value, (str, int, float, bool, type(None), list, dict)):
                    item[key] = value
            if len(evidence) < 100:
                evidence.append(item)
        occurrence["timeline_event_range"] = {
            "first": event_indexes[0] if event_indexes else None,
            "last": event_indexes[-1] if event_indexes else None,
        }
        occurrence["representative_frames"] = frames[:12]
        occurrence["evidence_events"] = evidence
    callers = {}
    for occurrence in occurrences:
        caller = occurrence.get("step_owner") or occurrence.get("direct_caller") or "(unknown)"
        callers.setdefault(caller, []).append(occurrence["id"])
    return {
        "version": 1,
        "groups": groups,
        "occurrence_count": len(occurrences),
        "callers": callers,
        "occurrences": occurrences,
        "artifacts": {
            "timeline": "steps.jsonl",
            "output_log": "commands.log",
            "step_frames": "step_frames/",
            "source_snapshots": "source_snapshots/",
            "youtube_mapping": "youtube_remote.json",
        },
    }


def load_timeline_events(folder):
    path = os.path.join(os.path.abspath(folder), "steps.jsonl")
    result = []
    try:
        stream = open(path, "r", encoding="utf-8")
    except OSError:
        return result
    with stream:
        for line in stream:
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                result.append(value)
    return result


def write_common_function_index(folder, groups, duration=0.0):
    folder = os.path.abspath(folder)
    payload = build_common_function_index(
        load_timeline_events(folder), groups, duration=duration)
    path = os.path.join(folder, INDEX_FILE_NAME)
    temporary = "{}.{}.tmp".format(path, uuid.uuid4().hex)
    os.makedirs(folder, exist_ok=True)
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass
    return payload
