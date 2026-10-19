#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight, ordered Step plan for recorded-operation editing.

The original ``mappings.json`` and ``inputs.jsonl`` remain the recording
evidence.  This module stores only the editable hierarchy.  Unedited Steps
refer to an input range and are decoded on demand; a Step becomes an explicit
copy-on-write operation list only when the user edits its contents.
"""
from __future__ import print_function

import ast
import bisect
from array import array
from collections import OrderedDict
import copy
import json
import keyword
import os
import re
import threading
import uuid

from OperationSessionModel import (STICK_MODE_EXACT, atomic_json,
                                   decode_switch_input_rows,
                                   input_row_is_commands_recordable,
                                   readable_switch_operations)


PLAN_SCHEMA_VERSION = 1
PLAN_FILENAME = "step_plan.json"
PREVIEW_FILENAME = "step_plan_preview.py"
PREVIEW_MAP_FILENAME = "step_plan_preview.map.json"
PLAN_BEGIN = "# POKECON_OPERATION_STEP_PLAN:{session_id}:BEGIN"
PLAN_END = "# POKECON_OPERATION_STEP_PLAN:{session_id}:END"
NODE_KINDS = ("recorded", "operation", "call", "branch", "return",
              "comment", "ignore", "opaque")


def _new_id(prefix):
    return "{}-{}".format(prefix, uuid.uuid4().hex)


def _identifier(value, fallback):
    text = re.sub(r"\W+", "_", str(value or "").strip(),
                  flags=re.UNICODE).strip("_")
    if not text:
        text = fallback
    if text[:1].isdigit():
        text = "_" + text
    if keyword.iskeyword(text):
        text = "_" + text
    return text


def step_plan_path(session_dir):
    return os.path.join(os.path.abspath(session_dir), PLAN_FILENAME)


def preview_paths(session_dir):
    folder = os.path.join(os.path.abspath(session_dir), "source")
    return {
        "source": os.path.join(folder, PREVIEW_FILENAME),
        "map": os.path.join(folder, PREVIEW_MAP_FILENAME),
    }


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clone_state(state):
    if not isinstance(state, dict):
        return None
    return {
        "buttons": tuple(state.get("buttons", ())),
        "hat": str(state.get("hat", "CENTER") or "CENTER"),
        "left": state.get("left"),
        "right": state.get("right"),
    }


class JsonlInputIndex(object):
    """Compact byte-offset index for a potentially very large inputs.jsonl."""

    def __init__(self, path, checkpoint_lines=(), cache_ranges=2):
        self.path = os.path.abspath(path)
        self.lines = array("I")
        self.times = array("d")
        self.offsets = array("Q")
        self._states = {}
        self._range_cache = OrderedDict()
        self._cache_ranges = max(0, int(cache_ranges))
        self._lock = threading.RLock()
        self._scan(set(_int(value) for value in checkpoint_lines if _int(value) > 0))

    def _decode_chunk(self, rows, state):
        if not rows:
            return state
        _decoded, state, _malformed = decode_switch_input_rows(
            rows, stick_mode=STICK_MODE_EXACT, initial_state=state)
        return state

    def _scan(self, checkpoint_lines):
        state = None
        pending = []
        try:
            stream = open(self.path, "rb")
        except OSError:
            return
        with stream:
            while True:
                offset = stream.tell()
                raw = stream.readline()
                if not raw:
                    break
                try:
                    item = json.loads(raw.decode("utf-8-sig"))
                except (UnicodeDecodeError, ValueError):
                    continue
                if (not isinstance(item, dict) or item.get("kind") != "input"
                        or not input_row_is_commands_recordable(item)):
                    continue
                line = _int(item.get("line"))
                if line <= 0:
                    continue
                if line in checkpoint_lines:
                    state = self._decode_chunk(pending, state)
                    pending = []
                    self._states[line] = _clone_state(state)
                self.lines.append(line)
                self.times.append(_float(item.get("time")))
                self.offsets.append(offset)
                pending.append(item)
                if len(pending) >= 1024:
                    state = self._decode_chunk(pending, state)
                    pending = []
            self._decode_chunk(pending, state)
        if self.lines and int(self.lines[0]) not in self._states:
            self._states[int(self.lines[0])] = None

    def __len__(self):
        return len(self.lines)

    def _cache_put(self, key, rows):
        if self._cache_ranges <= 0:
            return
        with self._lock:
            self._range_cache[key] = rows
            self._range_cache.move_to_end(key)
            while len(self._range_cache) > self._cache_ranges:
                self._range_cache.popitem(last=False)

    def clear_cache(self):
        with self._lock:
            self._range_cache.clear()

    def fork_reader(self):
        """Return an independent reader over this immutable byte index.

        The compact line/time/offset arrays are append-only during ``_scan``
        and immutable afterwards, so a preview worker can safely share them.
        Its decoded-state checkpoints and range cache stay private, avoiding
        contention with Tree expansion/collapse in the Tk thread.
        """
        value = self.__class__.__new__(self.__class__)
        value.path = self.path
        value.lines = self.lines
        value.times = self.times
        value.offsets = self.offsets
        with self._lock:
            value._states = {
                line: _clone_state(state)
                for line, state in self._states.items()
            }
        value._range_cache = OrderedDict()
        value._cache_ranges = self._cache_ranges
        value._lock = threading.RLock()
        return value

    def read_range(self, start_line, end_line):
        start_line, end_line = _int(start_line), _int(end_line)
        if start_line > end_line:
            start_line, end_line = end_line, start_line
        key = (start_line, end_line)
        with self._lock:
            cached = self._range_cache.get(key)
            if cached is not None:
                self._range_cache.move_to_end(key)
                return [dict(item) for item in cached]
        index = bisect.bisect_left(self.lines, start_line)
        if index >= len(self.lines):
            return []
        result = []
        try:
            stream = open(self.path, "rb")
        except OSError:
            return result
        with stream:
            stream.seek(int(self.offsets[index]))
            while True:
                raw = stream.readline()
                if not raw:
                    break
                try:
                    item = json.loads(raw.decode("utf-8-sig"))
                except (UnicodeDecodeError, ValueError):
                    continue
                if (not isinstance(item, dict) or item.get("kind") != "input"
                        or not input_row_is_commands_recordable(item)):
                    continue
                line = _int(item.get("line"))
                if line > end_line:
                    break
                if line >= start_line:
                    result.append(item)
        self._cache_put(key, [dict(item) for item in result])
        return result

    def state_before(self, line):
        with self._lock:
            line = _int(line)
            if line in self._states:
                return _clone_state(self._states[line])
            candidates = [value for value in self._states if value < line]
            checkpoint = max(candidates) if candidates else (
                int(self.lines[0]) if self.lines else line)
            state = _clone_state(self._states.get(checkpoint))
            state = self._decode_chunk(
                self.read_range(checkpoint, line - 1), state)
            self._states[line] = _clone_state(state)
            return _clone_state(state)

    def time_for_line(self, line, default=0.0):
        index = bisect.bisect_left(self.lines, _int(line))
        if index < len(self.lines) and int(self.lines[index]) == _int(line):
            return float(self.times[index])
        return float(default)

    def time_before_line(self, line, default=0.0):
        index = bisect.bisect_left(self.lines, _int(line)) - 1
        if index >= 0:
            return float(self.times[index])
        return float(default)

    def first_line_in_range(self, start_line, end_line):
        start_line, end_line = _int(start_line), _int(end_line)
        if start_line > end_line:
            start_line, end_line = end_line, start_line
        index = bisect.bisect_left(self.lines, start_line)
        if index < len(self.lines) and int(self.lines[index]) <= end_line:
            return int(self.lines[index])
        return 0

    def line_at_time(self, value):
        if not self.times:
            return 0
        index = bisect.bisect_right(self.times, float(value)) - 1
        index = min(max(0, index), len(self.lines) - 1)
        return int(self.lines[index])


def _recorded_node(start_line, end_line, node_id=""):
    return {
        "id": node_id or _new_id("recorded"),
        "kind": "recorded",
        "input_start": _int(start_line),
        "input_end": _int(end_line),
        "video_start": 0.0,
        "video_end": 0.0,
    }


def _normalise_condition(value):
    value = dict(value or {})
    kind = str(value.get("kind", "image_check") or "image_check")
    if kind not in ("image_check", "expression"):
        kind = "expression"
    return {
        "kind": kind,
        "target": str(value.get("target", "") or ""),
        "source": str(value.get("source", "") or ""),
        "negate": bool(value.get("negate", False)),
    }


def normalise_node(value):
    source = dict(value or {})
    kind = str(source.get("kind", "operation") or "operation")
    if kind not in NODE_KINDS:
        kind = "opaque"
    result = {
        "id": str(source.get("id") or _new_id(kind)),
        "kind": kind,
        "input_start": max(0, _int(source.get("input_start"))),
        "input_end": max(0, _int(source.get("input_end"))),
        "video_start": max(0.0, _float(source.get("video_start"))),
        "video_end": max(0.0, _float(source.get("video_end"))),
    }
    if result["input_end"] and result["input_start"] > result["input_end"]:
        result["input_start"], result["input_end"] = \
            result["input_end"], result["input_start"]
    if kind in ("operation", "opaque"):
        result["source"] = str(source.get("source", "") or "")
    elif kind == "call":
        result["name"] = str(source.get("name", "") or "")
        result["source"] = str(source.get("source", "") or "")
        result["recorded_timing"] = bool(source.get("recorded_timing", False))
    elif kind == "return":
        result["target"] = str(source.get("target", "") or "")
    elif kind in ("comment", "ignore"):
        result["text"] = str(source.get("text", "") or "")
    elif kind == "branch":
        branches = []
        for branch in source.get("branches", []) or []:
            if not isinstance(branch, dict):
                continue
            condition = branch.get("condition")
            branches.append({
                "id": str(branch.get("id") or _new_id("branch-arm")),
                "condition": (_normalise_condition(condition)
                              if condition is not None else None),
                "items": [normalise_node(item)
                          for item in branch.get("items", []) or []
                          if isinstance(item, dict)],
            })
        if not branches:
            branches = [{
                "id": _new_id("branch-arm"),
                "condition": _normalise_condition({"kind": "image_check"}),
                "items": [],
            }, {
                "id": _new_id("branch-arm"),
                "condition": None,
                "items": [],
            }]
        result["branches"] = branches
    return result


def normalise_step(value):
    source = dict(value or {})
    start = max(0, _int(source.get("input_start", source.get("start_line", 0))))
    end = max(0, _int(source.get("input_end", source.get("end_line", start))))
    if end and start > end:
        start, end = end, start
    name = str(source.get("name", source.get("step_name", "")) or "")
    return {
        "id": str(source.get("id") or _new_id("step")),
        "kind": "step",
        "name": name,
        "method": _identifier(source.get("method", name), "RECORDED_STEP"),
        "label": str(source.get("label", source.get("notes", "")) or ""),
        "next_step": str(source.get("next_step", "") or ""),
        "input_start": start,
        "input_end": end,
        "video_start": max(0.0, _float(source.get("video_start"))),
        "video_end": max(0.0, _float(source.get("video_end"))),
        "materialized": bool(source.get("materialized", False)),
        "auto_next": bool(source.get("auto_next", True)),
        "items": [normalise_node(item) for item in source.get("items", []) or []
                  if isinstance(item, dict)],
    }


def normalise_plan(value):
    source = dict(value or {})
    generation = source.get("generation", {})
    if not isinstance(generation, dict):
        generation = {}
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "session_id": str(source.get("session_id", "") or ""),
        "revision": max(0, _int(source.get("revision"))),
        "source_path": str(source.get("source_path", "") or ""),
        "generation": {
            "target": str(generation.get("target", "switch") or "switch"),
            "stick_mode": str(generation.get("stick_mode", STICK_MODE_EXACT)
                              or STICK_MODE_EXACT),
        },
        "steps": [normalise_step(item) for item in source.get("steps", []) or []
                  if isinstance(item, dict)],
    }


def migrate_mappings(session, mappings):
    """Create an in-memory plan without changing the evidence mappings file."""
    mappings = [dict(item) for item in mappings or [] if isinstance(item, dict)]
    steps = []
    for mapping in sorted(
            (item for item in mappings if item.get("kind") == "step"),
            key=lambda item: (_int(item.get("start_line")),
                              _int(item.get("end_line")))):
        start, end = _int(mapping.get("start_line")), _int(mapping.get("end_line"))
        items = []
        cursor = start
        children = sorted((item for item in mappings
                           if item.get("kind") in ("function", "ignore")
                           and _int(item.get("start_line")) >= start
                           and _int(item.get("end_line")) <= end),
                          key=lambda item: (_int(item.get("start_line")),
                                            _int(item.get("end_line"))))
        for child in children:
            child_start = _int(child.get("start_line"))
            child_end = _int(child.get("end_line"))
            if child_start < cursor:
                continue
            if cursor < child_start:
                items.append(_recorded_node(cursor, child_start - 1))
            if child.get("kind") == "function":
                items.append(normalise_node({
                    "id": child.get("id"), "kind": "call",
                    "name": child.get("function_name", ""),
                    "input_start": child_start, "input_end": child_end,
                    "recorded_timing": True,
                }))
            else:
                items.append(normalise_node({
                    "id": child.get("id"), "kind": "ignore",
                    "text": child.get("notes", ""),
                    "input_start": child_start, "input_end": child_end,
                }))
            cursor = child_end + 1
        if cursor <= end:
            items.append(_recorded_node(cursor, end))
        steps.append(normalise_step({
            "id": mapping.get("id"),
            "name": mapping.get("step_name", ""),
            "label": mapping.get("notes", ""),
            "next_step": mapping.get("next_step", ""),
            "input_start": start, "input_end": end,
            "items": items,
        }))
    return normalise_plan({
        "session_id": (session or {}).get("session_id", ""),
        "source_path": (session or {}).get("final_source", ""),
        "generation": {
            "target": ((session or {}).get("generation", {}) or {}).get(
                "input_target", "switch"),
            "stick_mode": ((session or {}).get("generation", {}) or {}).get(
                "stick_angle_mode", STICK_MODE_EXACT),
        },
        "steps": steps,
    })


def _raw_plan_structure_errors(value):
    """Reject malformed containers before normalization can empty them."""
    errors = []
    if "generation" in value and not isinstance(value.get("generation"), dict):
        errors.append("generation はJSONオブジェクトである必要があります。")

    def require_list(container, key, path):
        if key not in container:
            return []
        child = container.get(key)
        if not isinstance(child, list):
            errors.append("{} は配列である必要があります。".format(path))
            return []
        return child

    def check_items(container, path):
        items = require_list(container, "items", path + ".items")
        for item_index, node in enumerate(items):
            node_path = "{}.items[{}]".format(path, item_index)
            if not isinstance(node, dict):
                errors.append("{} はJSONオブジェクトである必要があります。".format(
                    node_path))
                continue
            if str(node.get("kind", "")) != "branch":
                continue
            branches = require_list(
                node, "branches", node_path + ".branches")
            for branch_index, branch in enumerate(branches):
                branch_path = "{}.branches[{}]".format(
                    node_path, branch_index)
                if not isinstance(branch, dict):
                    errors.append(
                        "{} はJSONオブジェクトである必要があります。".format(
                            branch_path))
                    continue
                if ("condition" in branch
                        and branch.get("condition") is not None
                        and not isinstance(branch.get("condition"), dict)):
                    errors.append(
                        "{}.condition はJSONオブジェクトまたはnullである必要があります。".format(
                            branch_path))
                check_items(branch, branch_path)

    steps = require_list(value, "steps", "steps")
    for step_index, step in enumerate(steps):
        step_path = "steps[{}]".format(step_index)
        if not isinstance(step, dict):
            errors.append("{} はJSONオブジェクトである必要があります。".format(
                step_path))
            continue
        check_items(step, step_path)
    return errors


def load_step_plan(session_dir, session=None, mappings=None):
    path = step_plan_path(session_dir)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as stream:
                value = json.load(stream)
        except (OSError, ValueError) as error:
            raise ValueError("step_plan.jsonを読み込めません: {}".format(error))
        if not isinstance(value, dict):
            raise ValueError("step_plan.jsonのルートはJSONオブジェクトである必要があります。")
        structure_errors = _raw_plan_structure_errors(value)
        if structure_errors:
            raise ValueError(
                "step_plan.jsonの階層構造が不正です:\n" +
                "\n".join(structure_errors))
        schema_version = _int(
            value.get("schema_version", PLAN_SCHEMA_VERSION),
            PLAN_SCHEMA_VERSION)
        if schema_version != PLAN_SCHEMA_VERSION:
            raise ValueError(
                "未対応のstep_plan.json schema_versionです: {}".format(
                    schema_version))
        expected_session = str((session or {}).get("session_id", "") or "")
        actual_session = str(value.get("session_id", "") or "")
        if expected_session and actual_session \
                and expected_session != actual_session:
            raise ValueError(
                "step_plan.jsonのsession_idが現在の記録と一致しません。")
        plan = normalise_plan(value)
        validation = validate_plan(plan)
        if validation["errors"]:
            raise ValueError(
                "step_plan.jsonが不正です:\n" +
                "\n".join(validation["errors"]))
        return plan, True
    return migrate_mappings(session or {}, mappings or []), False


def save_step_plan(session_dir, plan, input_index=None):
    if not isinstance(plan, dict):
        raise ValueError("Step計画のルートはJSONオブジェクトである必要があります。")
    structure_errors = _raw_plan_structure_errors(plan)
    if structure_errors:
        raise ValueError("\n".join(structure_errors))
    value = normalise_plan(plan)
    validation = validate_plan(value, input_index=input_index)
    if validation["errors"]:
        raise ValueError("\n".join(validation["errors"]))
    value["revision"] = _int(value.get("revision")) + 1
    atomic_json(step_plan_path(session_dir), value)
    return value


def hydrate_plan_times(plan, input_index):
    for step in plan.get("steps", []):
        start, end = step.get("input_start", 0), step.get("input_end", 0)
        step["video_start"] = input_index.time_for_line(start, step.get("video_start", 0.0))
        step["video_end"] = input_index.time_for_line(end, step.get("video_end", 0.0))
        for node, _parent, _index in walk_nodes(step.get("items", [])):
            start, end = node.get("input_start", 0), node.get("input_end", 0)
            if start:
                node["video_start"] = input_index.time_for_line(
                    start, node.get("video_start", 0.0))
            if end:
                node["video_end"] = input_index.time_for_line(
                    end, node.get("video_end", 0.0))
    return plan


def find_step(plan, step_id):
    return next((step for step in plan.get("steps", [])
                 if step.get("id") == step_id), None)


def walk_nodes(items):
    for index, node in enumerate(items or []):
        yield node, items, index
        if node.get("kind") == "branch":
            for branch in node.get("branches", []):
                for value in walk_nodes(branch.get("items", [])):
                    yield value


def find_node(step, node_id):
    return next(((node, parent, index)
                 for node, parent, index in walk_nodes(step.get("items", []))
                 if node.get("id") == node_id), (None, None, -1))


def find_branch_arm(step, arm_id):
    for node, _parent, _index in walk_nodes(step.get("items", [])):
        if node.get("kind") != "branch":
            continue
        for branch in node.get("branches", []):
            if branch.get("id") == arm_id:
                return branch
    return None


def materialize_step(step, input_index):
    """Copy recorded ranges into editable operations only for this Step."""
    if step.get("materialized") and not any(
            node.get("kind") == "recorded" for node, _parent, _index
            in walk_nodes(step.get("items", []))):
        return step

    def expand(items):
        expanded = []
        for node in items:
            if node.get("kind") == "recorded":
                start, end = node.get("input_start", 0), node.get("input_end", 0)
                rows = input_index.read_range(start, end)
                operations = readable_switch_operations(
                    rows, stick_mode=STICK_MODE_EXACT,
                    initial_state=input_index.state_before(start),
                    origin_time=input_index.time_before_line(start, 0.0))
                for operation in operations:
                    expanded.append(normalise_node({
                        "kind": "operation", "source": operation.get("code", ""),
                        "input_start": operation.get("start_line", start),
                        "input_end": operation.get("end_line", end),
                        "video_start": operation.get("time", 0.0),
                        "video_end": operation.get("time", 0.0),
                    }))
            elif node.get("kind") == "branch":
                copied = copy.deepcopy(node)
                for branch in copied.get("branches", []):
                    branch["items"] = expand(branch.get("items", []))
                expanded.append(copied)
            else:
                expanded.append(copy.deepcopy(node))
        return expanded

    step["items"] = expand(step.get("items", []))
    step["materialized"] = True
    return step


def new_step(name, next_step="", label=""):
    return normalise_step({
        "id": _new_id("step"), "name": name, "next_step": next_step,
        "label": label, "materialized": True, "items": [],
    })


def move_step(plan, step_id, amount):
    steps = plan.get("steps", [])
    index = next((index for index, step in enumerate(steps)
                  if step.get("id") == step_id), -1)
    target = index + int(amount)
    if index < 0 or target < 0 or target >= len(steps):
        return False
    steps[index], steps[target] = steps[target], steps[index]
    return True


def rename_step_references(plan, old_name, new_name):
    """Update explicit transitions that point at a renamed Step."""
    changed = 0
    old_name, new_name = str(old_name or ""), str(new_name or "")
    if not old_name or old_name == new_name:
        return changed
    for step in plan.get("steps", []):
        if step.get("next_step") == old_name:
            step["next_step"] = new_name
            changed += 1
        for node, _parent, _index in walk_nodes(step.get("items", [])):
            if node.get("kind") == "return" and node.get("target") == old_name:
                node["target"] = new_name
                changed += 1
    return changed


def split_step(plan, step_id, split_line, new_name, split_node_id=""):
    steps = plan.get("steps", [])
    index = next((index for index, step in enumerate(steps)
                  if step.get("id") == step_id), -1)
    if index < 0:
        raise ValueError("Stepが見つかりません。")
    step = steps[index]
    new_name = str(new_name or "").strip()
    if not new_name:
        raise ValueError("分割後のStep名を指定してください。")
    if any(item.get("name") == new_name for item in steps):
        raise ValueError("同じStep名が既にあります。")
    new_method = _identifier(new_name, "RECORDED_STEP")
    if any(_identifier(item.get("method", item.get("name")), "RECORDED_STEP")
           == new_method for item in steps):
        raise ValueError("同じ出力メソッド名になるStepが既にあります。")
    if not step.get("auto_next", True):
        raise ValueError("自動の次Stepが無効なStepは先に遷移を整理してください。")
    split_line = _int(split_line)
    first_items, second_items = [], []
    if split_node_id:
        split_index = next((item_index for item_index, node in enumerate(
            step.get("items", [])) if node.get("id") == split_node_id), -1)
        if split_index < 0:
            raise ValueError("分割位置の操作がStep直下に見つかりません。")
        split_node = step.get("items", [])[split_index]
        if split_node.get("kind") != "operation":
            raise ValueError("Step直下の操作を分割位置に指定してください。")
        split_line = _int(split_node.get("input_start", split_line))
        if split_line <= 0:
            raise ValueError("記録行を持たない追加操作ではStepを分割できません。")
        first_items = list(step.get("items", [])[:split_index])
        second_items = list(step.get("items", [])[split_index:])
    else:
        if not (step.get("input_start", 0) < split_line <= step.get("input_end", 0)):
            raise ValueError("Step範囲内の分割行を指定してください。")
        for node in step.get("items", []):
            start, end = node.get("input_start", 0), node.get("input_end", 0)
            if node.get("kind") == "recorded" and start < split_line <= end:
                first_items.append(_recorded_node(
                    start, split_line - 1, node.get("id")))
                second_items.append(_recorded_node(split_line, end))
            elif start and start >= split_line:
                second_items.append(node)
            elif end and end < split_line:
                first_items.append(node)
            elif start and end and start < split_line <= end:
                raise ValueError("操作・関数・条件の途中ではStepを分割できません。")
            else:
                # Unanchored custom nodes stay with the first half.
                first_items.append(node)
    old_next = step.get("next_step", "")
    old_end = step.get("input_end", 0)
    step["input_end"] = split_line - 1
    step["video_end"] = 0.0
    step["next_step"] = str(new_name)
    step["items"] = first_items
    created = normalise_step({
        "name": new_name, "next_step": old_next,
        "label": "{}（分割）".format(step.get("label", "")).strip(),
        "input_start": split_line, "input_end": old_end,
        "materialized": step.get("materialized", False),
        "items": second_items,
    })
    steps.insert(index + 1, created)
    return created


def new_operation(source, anchor=None):
    anchor = anchor or {}
    return normalise_node({
        "kind": "operation", "source": source,
        "input_start": anchor.get("input_start", 0),
        "input_end": anchor.get("input_end", 0),
        "video_start": anchor.get("video_start", 0.0),
        "video_end": anchor.get("video_end", 0.0),
    })


def new_call(name, anchor=None, source=""):
    anchor = anchor or {}
    return normalise_node({
        "kind": "call", "name": name, "source": source,
        "input_start": anchor.get("input_start", 0),
        "input_end": anchor.get("input_end", 0),
        "video_start": anchor.get("video_start", 0.0),
        "video_end": anchor.get("video_end", 0.0),
    })


def new_return(target, anchor=None):
    anchor = anchor or {}
    return normalise_node({
        "kind": "return", "target": target,
        "input_start": anchor.get("input_start", 0),
        "input_end": anchor.get("input_end", 0),
        "video_start": anchor.get("video_start", 0.0),
        "video_end": anchor.get("video_end", 0.0),
    })


def new_branch(condition_kind="image_check", value="", negate=False,
               wrapped_item=None, anchor=None):
    anchor = anchor or wrapped_item or {}
    condition = {"kind": condition_kind, "negate": bool(negate)}
    if condition_kind == "image_check":
        condition["target"] = value
    else:
        condition["source"] = value
    return normalise_node({
        "kind": "branch",
        "input_start": anchor.get("input_start", 0),
        "input_end": anchor.get("input_end", 0),
        "video_start": anchor.get("video_start", 0.0),
        "video_end": anchor.get("video_end", 0.0),
        "branches": [{
            "condition": condition,
            "items": [copy.deepcopy(wrapped_item)] if wrapped_item else [],
        }, {"condition": None, "items": []}],
    })


def insert_node(step, node, parent_node_id="", branch_arm_id="", index=None):
    if branch_arm_id:
        arm = find_branch_arm(step, branch_arm_id)
        if arm is None:
            raise ValueError("分岐先が見つかりません。")
        target = arm.setdefault("items", [])
    elif parent_node_id:
        parent, _items, _index = find_node(step, parent_node_id)
        if not parent or parent.get("kind") != "branch":
            raise ValueError("条件分岐を選択してください。")
        target = parent["branches"][0].setdefault("items", [])
    else:
        target = step.setdefault("items", [])
    value = normalise_node(node)
    if index is None:
        target.append(value)
    else:
        target.insert(max(0, min(int(index), len(target))), value)
    return value


def remove_node(step, node_id):
    node, parent, index = find_node(step, node_id)
    if node is None:
        return False
    del parent[index]
    return True


def move_node(step, node_id, amount):
    node, parent, index = find_node(step, node_id)
    target = index + int(amount)
    if node is None or target < 0 or target >= len(parent):
        return False
    parent[index], parent[target] = parent[target], parent[index]
    return True


def _condition_source(condition):
    condition = _normalise_condition(condition)
    if condition["kind"] == "image_check":
        source = "self.image_check({!r})".format(condition.get("target", ""))
    else:
        source = condition.get("source", "") or "False"
    if condition.get("negate"):
        return "not ({})".format(source)
    return source


def _validate_statement(source):
    try:
        ast.parse("def _validate(self):\n" + "\n".join(
            "    " + line for line in str(source or "").splitlines()))
        return ""
    except (SyntaxError, ValueError) as error:
        return str(error)


def _parsed_operation_source(source):
    try:
        return ast.parse("def _validate(self):\n" + "\n".join(
            "    " + line for line in str(source or "").splitlines()))
    except (SyntaxError, ValueError):
        return None


def _contains_direct_serial_reference(source):
    tree = _parsed_operation_source(source)
    if tree is None:
        return False
    for node in ast.walk(tree):
        if ((isinstance(node, ast.Attribute) and node.attr == "direct_serial")
                or (isinstance(node, ast.Name) and node.id == "direct_serial")):
            return True
        literal = _ast_string_value(node)
        if isinstance(literal, str) and literal == "direct_serial":
            return True
    return False


_RAW_HEX_PATTERN = re.compile(
    r"(?<![0-9A-Za-z_])0x_?[0-9a-f](?:_?[0-9a-f])*(?![0-9A-Za-z_])",
    re.IGNORECASE)


def _ast_string_value(node):
    constant_type = getattr(ast, "Constant", None)
    if constant_type is not None and isinstance(node, constant_type):
        return node.value if isinstance(node.value, str) else None
    string_type = getattr(ast, "Str", None)
    if string_type is not None and isinstance(node, string_type):
        return node.s
    return None


def _contains_raw_hex(source):
    source = str(source or "")
    if _RAW_HEX_PATTERN.search(source):
        return True
    tree = _parsed_operation_source(source)
    if tree is None:
        return False
    for node in ast.walk(tree):
        literal = _ast_string_value(node)
        if isinstance(literal, str) and _RAW_HEX_PATTERN.search(literal):
            return True
    return False


def validate_plan(plan, input_index=None):
    errors, warnings = [], []
    if not isinstance(plan, dict):
        return {
            "errors": ["Step計画のルートはJSONオブジェクトである必要があります。"],
            "warnings": [],
        }
    structure_errors = _raw_plan_structure_errors(plan)
    if structure_errors:
        return {"errors": structure_errors, "warnings": []}
    names = []
    methods = []
    ids = set()
    for step in plan.get("steps", []):
        name = str(step.get("name", "") or "")
        method = _identifier(step.get("method", name), "RECORDED_STEP")
        if step.get("id") in ids:
            errors.append("IDが重複しています: {}".format(step.get("id")))
        ids.add(step.get("id"))
        if not name:
            errors.append("Step名が空です。")
        if name in names:
            errors.append("Step名が重複しています: {}".format(name))
        names.append(name)
        if method in methods:
            errors.append("出力メソッド名が重複しています: {}".format(method))
        methods.append(method)
        for node, _parent, _index in walk_nodes(step.get("items", [])):
            if node.get("id") in ids:
                errors.append("IDが重複しています: {}".format(node.get("id")))
            ids.add(node.get("id"))
            kind = node.get("kind")
            if kind == "recorded":
                if node.get("input_start", 0) <= 0 or node.get("input_end", 0) <= 0:
                    errors.append("{}: 記録範囲が不正です。".format(name))
                elif input_index is not None:
                    left = bisect.bisect_left(
                        input_index.lines, _int(node.get("input_start")))
                    if (left >= len(input_index.lines)
                            or int(input_index.lines[left])
                            > _int(node.get("input_end"))):
                        errors.append(
                            "{}: 記録範囲に入力がありません: #{}-#{}".format(
                                name, node.get("input_start"),
                                node.get("input_end")))
            elif kind in ("operation", "opaque"):
                problem = _validate_statement(node.get("source", ""))
                if problem:
                    errors.append("{}: 操作ソースが不正です: {}".format(name, problem))
                if (_contains_direct_serial_reference(node.get("source", "")) \
                        or _contains_raw_hex(node.get("source", ""))):
                    errors.append("{}: 生パケットではなく可読操作を指定してください。".format(name))
            elif kind == "call":
                call_name = str(node.get("name", "") or "")
                if not call_name.isidentifier() or keyword.iskeyword(call_name):
                    errors.append("{}: 関数名が不正です: {}".format(
                        name, call_name))
                if node.get("source"):
                    errors.append(
                        "{}: 関数呼出しは関数名のみ指定してください。".format(name))
            elif kind == "branch":
                branches = node.get("branches", [])
                if not branches:
                    errors.append("{}: 条件分岐が空です。".format(name))
                    continue
                else_seen = False
                for branch_index, branch in enumerate(branches):
                    arm_id = branch.get("id")
                    if arm_id in ids:
                        errors.append("IDが重複しています: {}".format(arm_id))
                    ids.add(arm_id)
                    condition = branch.get("condition")
                    if condition is None:
                        if branch_index == 0:
                            errors.append("{}: 条件分岐の先頭に条件がありません。".format(name))
                        if else_seen or branch_index != len(branches) - 1:
                            errors.append("{}: elseは最後に1つだけ指定できます。".format(name))
                        else_seen = True
                        continue
                    if else_seen:
                        errors.append("{}: elseの後には条件を追加できません。".format(name))
                    condition = _normalise_condition(condition)
                    if condition["kind"] == "image_check" and not condition["target"]:
                        errors.append("{}: image_check名が空です。".format(name))
                    if condition["kind"] == "expression":
                        condition_source = condition.get("source", "")
                        try:
                            ast.parse(condition_source, mode="eval")
                        except (SyntaxError, ValueError) as error:
                            errors.append("{}: 条件式が不正です: {}".format(name, error))
                        if (_contains_direct_serial_reference(condition_source)
                                or _contains_raw_hex(condition_source)):
                            errors.append(
                                "{}: 条件式に生パケットは指定できません。".format(name))
    known = set(names)
    for step in plan.get("steps", []):
        target = step.get("next_step", "")
        if target and target not in known and not str(target).endswith("_END"):
            warnings.append("{} の次Step {} は一覧にありません。".format(
                step.get("name", ""), target))
    return {"errors": errors, "warnings": warnings}


def render_plan(plan, input_index=None):
    """Render a preview and a per-line map; never changes the final source."""
    validation = validate_plan(plan, input_index=input_index)
    if validation["errors"]:
        raise ValueError("\n".join(validation["errors"]))
    session_id = str(plan.get("session_id", "operation") or "operation")
    lines = [PLAN_BEGIN.format(session_id=session_id),
             "# 軽量Step編集から生成した確認用ソースです。",
             "# 元のmappings.json / inputs.jsonlと最終ソースは変更していません。", ""]
    source_map = []

    def append(text, node=None, step=None):
        for value in str(text).splitlines() or [""]:
            lines.append(value)
            source_map.append({
                "line": len(lines),
                "step_id": (step or {}).get("id", ""),
                "node_id": (node or {}).get("id", ""),
                "input_start": (node or step or {}).get("input_start", 0),
                "input_end": (node or step or {}).get("input_end", 0),
                "video_time": (node or step or {}).get("video_start", 0.0),
            })

    def render_items(items, indent, step):
        emitted = False
        for node in items or []:
            kind = node.get("kind")
            if kind == "recorded":
                if input_index is None:
                    append(indent + "pass  # 記録入力は索引未読込", node, step)
                else:
                    start, end = node.get("input_start", 0), node.get("input_end", 0)
                    operations = readable_switch_operations(
                        input_index.read_range(start, end),
                        stick_mode=STICK_MODE_EXACT,
                        initial_state=input_index.state_before(start),
                        origin_time=input_index.time_before_line(start, 0.0))
                    for operation in operations:
                        mapped = dict(node)
                        mapped["input_start"] = operation.get("start_line", start)
                        mapped["input_end"] = operation.get("end_line", end)
                        mapped["video_start"] = operation.get("time", 0.0)
                        append(indent + operation.get("code", "pass"), mapped, step)
                emitted = True
            elif kind in ("operation", "opaque"):
                source = node.get("source", "") or "pass"
                for source_line in source.splitlines():
                    append(indent + source_line, node, step)
                emitted = True
            elif kind == "call":
                if (node.get("recorded_timing") and input_index is not None
                        and node.get("input_start", 0)):
                    call_line = input_index.first_line_in_range(
                        node.get("input_start"), node.get("input_end"))
                    if call_line:
                        call_start = input_index.time_for_line(call_line, 0.0)
                        call_origin = input_index.time_before_line(call_line, 0.0)
                        gap = max(0.0, call_start - call_origin)
                        if gap:
                            append(indent + "self.wait({})".format(
                                ("{:.6f}".format(gap).rstrip("0").rstrip(".")
                                 or "0.0")), node, step)
                source = "self.{}()".format(
                    _identifier(node.get("name"), "recorded_function"))
                append(indent + source, node, step)
                emitted = True
            elif kind == "return":
                append(indent + "return {!r}".format(node.get("target", "")), node, step)
                emitted = True
            elif kind in ("comment", "ignore"):
                prefix = "反映不要: " if kind == "ignore" else ""
                comment_lines = str(node.get("text", "") or "").splitlines() or [""]
                for comment_line in comment_lines:
                    append(indent + "# " + prefix + comment_line, node, step)
                # Comments do not form a Python suite by themselves.  Keep
                # ``emitted`` false so an otherwise empty function/branch
                # also receives an indented ``pass``.
            elif kind == "branch":
                branches = node.get("branches", [])
                for branch_index, branch in enumerate(branches):
                    condition = branch.get("condition")
                    if branch_index == 0:
                        header = "if {}:".format(_condition_source(condition))
                    elif condition is None:
                        header = "else:"
                    else:
                        header = "elif {}:".format(_condition_source(condition))
                    append(indent + header, node, step)
                    if not render_items(branch.get("items", []), indent + "    ", step):
                        append(indent + "    pass", node, step)
                emitted = True
        return emitted

    for step in plan.get("steps", []):
        append("def {}(self):".format(
            _identifier(step.get("method", step.get("name")), "RECORDED_STEP")),
            step=step)
        label = step.get("label", "")
        if label:
            for label_line in str(label).splitlines() or [""]:
                append("    # " + label_line, step=step)
        emitted = render_items(step.get("items", []), "    ", step)
        if step.get("auto_next", True) and step.get("next_step", ""):
            append("    return {!r}".format(step.get("next_step")), step=step)
            emitted = True
        if not emitted:
            append("    pass", step=step)
        append("", step=step)
    append(PLAN_END.format(session_id=session_id))
    append("")
    source = "\n".join(lines)
    ast.parse(source)
    return source, source_map, validation["warnings"]


def save_preview(session_dir, plan, input_index=None):
    source, source_map, warnings = render_plan(plan, input_index=input_index)
    paths = preview_paths(session_dir)
    os.makedirs(os.path.dirname(paths["source"]), exist_ok=True)
    temporary = paths["source"] + ".tmp-" + uuid.uuid4().hex
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(source)
    os.replace(temporary, paths["source"])
    atomic_json(paths["map"], {
        "schema_version": 1,
        "session_id": plan.get("session_id", ""),
        "source": paths["source"],
        "lines": source_map,
        "warnings": warnings,
    })
    return paths, warnings
