#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded offline analysis helpers for PokeCon Commands development.

The functions in this module never import or execute a Commands class.  They
operate on source text, retained monitor events, and sampled video frames so
DevStudio analysis cannot send controller input or stall the live PokeCon.
"""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import math
import os
import re
import time

from ImageCheckReferenceAudit import audit_image_check_references


SCHEMA_VERSION = 1
MAX_PROFILE_SAMPLES = 2000
MAX_PROFILE_MATCH_OPERATIONS = 12000
STATE_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
LIFECYCLE_METHODS = {
    "do_safe", "end", "finish", "force_stop", "sendStopRequest", "start",
}


def _call_name(node):
    function = getattr(node, "func", None)
    if isinstance(function, ast.Attribute):
        return str(function.attr)
    if isinstance(function, ast.Name):
        return str(function.id)
    return ""


def _assignment_name(node):
    if isinstance(node, ast.Attribute):
        return str(node.attr)
    if isinstance(node, ast.Name):
        return str(node.id)
    return ""


def _state_function_name(node):
    if isinstance(node, ast.Attribute):
        return str(node.attr)
    if isinstance(node, ast.Name):
        return str(node.id)
    if isinstance(node, ast.Lambda):
        return "<lambda>"
    return ""


def _iter_statement_lists(node):
    for field in ("body", "orelse", "finalbody"):
        value = getattr(node, field, None)
        if isinstance(value, list):
            yield value
    handlers = getattr(node, "handlers", None)
    if isinstance(handlers, list):
        for handler in handlers:
            if isinstance(getattr(handler, "body", None), list):
                yield handler.body


def _unreachable_lines(function):
    lines = []

    def visit_statements(statements):
        terminal = None
        for statement in statements:
            if terminal is not None:
                lines.append((int(getattr(statement, "lineno", 0) or 0), terminal))
                terminal = None
            if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                terminal = type(statement).__name__
            for nested in _iter_statement_lists(statement):
                visit_statements(nested)

    visit_statements(function.body)
    return lines


def _constant_string(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return ""


def analyze_command_source(source, source_path=""):
    """Return state transitions, image references, and bounded quality issues."""
    source = str(source or "")
    result = {
        "source_path": os.path.abspath(source_path) if source_path else "",
        "source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "syntax_error": "",
        "states": [],
        "transitions": [],
        "issues": [],
        "image_checks": [],
        "image_reference_audit": {},
        "functions": [],
    }
    try:
        module = ast.parse(source, filename=source_path or "<command>")
    except SyntaxError as error:
        result["syntax_error"] = "{}:{}: {}".format(
            int(error.lineno or 0), int(error.offset or 0), error.msg)
        result["issues"].append({
            "severity": "ERROR", "code": "syntax_error",
            "message": result["syntax_error"], "line": int(error.lineno or 0),
            "function": "",
        })
        return result

    image_checks = []
    for call in (node for node in ast.walk(module) if isinstance(node, ast.Call)):
        if _call_name(call) == "image_check" and call.args:
            name = _constant_string(call.args[0])
            if name and name not in image_checks:
                image_checks.append(name)
    result["image_checks"] = image_checks
    result["image_reference_audit"] = audit_image_check_references(source)

    states = []
    transitions = []
    issues = []
    all_known_states = set()
    mapping_first_states = set()
    state_key_counts = collections.Counter()
    function_nodes = {}

    classes = [node for node in module.body if isinstance(node, ast.ClassDef)]
    for command_class in classes:
        class_functions = {
            node.name: node for node in command_class.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        function_nodes.update(class_functions)
        for node in ast.walk(command_class):
            target = value = None
            if isinstance(node, ast.Assign) and node.targets:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign):
                target, value = node.target, node.value
            mapping = _assignment_name(target)
            if not (mapping.startswith("STATE_") and mapping.endswith("_FUNCTION")
                    and isinstance(value, ast.Dict)):
                continue
            first_in_mapping = True
            for key_node, function_node in zip(value.keys, value.values):
                state = _constant_string(key_node)
                function = _state_function_name(function_node)
                if not state:
                    continue
                state_key_counts[(mapping, state)] += 1
                all_known_states.add(state)
                if first_in_mapping:
                    mapping_first_states.add(state)
                    first_in_mapping = False
                states.append({
                    "class": command_class.name,
                    "mapping": mapping,
                    "state": state,
                    "function": function,
                    "line": int(getattr(key_node, "lineno", 0) or 0),
                })

        for name, function in class_functions.items():
            result["functions"].append({
                "class": command_class.name, "name": name,
                "line": int(getattr(function, "lineno", 0) or 0),
            })
            for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
                called = _call_name(call)
                if called in LIFECYCLE_METHODS:
                    issues.append({
                        "severity": "INFO", "code": "command_lifecycle_call",
                        "message": "Commands終了・開始ライフサイクル関数 {}() を呼び出します。".format(called),
                        "line": int(getattr(call, "lineno", 0) or 0),
                        "function": name,
                    })
            for loop in (node for node in ast.walk(function) if isinstance(node, ast.While)):
                is_infinite = isinstance(loop.test, ast.Constant) and loop.test.value is True
                has_alive_check = any(
                    isinstance(child, ast.Call) and _call_name(child) == "checkIfAlive"
                    for child in ast.walk(loop))
                if is_infinite and not has_alive_check:
                    issues.append({
                        "severity": "WARNING", "code": "loop_without_alive_check",
                        "message": "while True 内に checkIfAlive() がありません。Stopを受け付けない可能性があります。",
                        "line": int(getattr(loop, "lineno", 0) or 0),
                        "function": name,
                    })
            for line, terminal in _unreachable_lines(function):
                issues.append({
                    "severity": "WARNING", "code": "unreachable_statement",
                    "message": "{} の直後に到達不能な処理があります。".format(terminal),
                    "line": line, "function": name,
                })

    function_names = set(function_nodes)
    function_states = collections.defaultdict(list)
    for state in states:
        function_states[state["function"]].append(state)
        if not state["function"] or state["function"] == "<lambda>":
            issues.append({
                "severity": "WARNING", "code": "non_method_state_target",
                "message": "{} の {} は通常メソッドを参照していません。".format(
                    state["mapping"], state["state"]),
                "line": state["line"], "function": state["function"],
            })
        elif state["function"] not in function_names:
            issues.append({
                "severity": "ERROR", "code": "missing_state_method",
                "message": "{} の {} が未定義関数 {} を参照しています。".format(
                    state["mapping"], state["state"], state["function"]),
                "line": state["line"], "function": state["function"],
            })

    for (mapping, state), count in state_key_counts.items():
        if count > 1:
            line = next(item["line"] for item in states
                        if item["mapping"] == mapping and item["state"] == state)
            issues.append({
                "severity": "ERROR", "code": "duplicate_state",
                "message": "{} 内で {} が{}回定義されています。".format(mapping, state, count),
                "line": line, "function": "",
            })

    incoming = collections.Counter()
    for function_name, sources in function_states.items():
        function = function_nodes.get(function_name)
        if function is None:
            continue
        for return_node in (node for node in ast.walk(function)
                            if isinstance(node, ast.Return)):
            destination = _constant_string(return_node.value)
            if not destination:
                continue
            known = destination in all_known_states
            if not known and not STATE_NAME_PATTERN.fullmatch(destination):
                continue
            for source_state in sources:
                row = {
                    "mapping": source_state["mapping"],
                    "from_state": source_state["state"],
                    "from_function": function_name,
                    "to_state": destination,
                    "known": known,
                    "line": int(getattr(return_node, "lineno", 0) or 0),
                }
                transitions.append(row)
                if known:
                    incoming[destination] += 1
            if not known:
                issues.append({
                    "severity": "WARNING", "code": "unknown_return_state",
                    "message": "return先 {} はSTATE辞書に登録されていません。".format(destination),
                    "line": int(getattr(return_node, "lineno", 0) or 0),
                    "function": function_name,
                })

    for state in states:
        name = state["state"]
        initial = (name in mapping_first_states or name.endswith("_START")
                   or name.endswith("_INIT"))
        state["incoming"] = int(incoming.get(name, 0))
        if not initial and state["incoming"] == 0:
            issues.append({
                "severity": "INFO", "code": "no_static_incoming_transition",
                "message": "{} への直接文字列returnを確認できません。変数returnなら問題ありません。".format(name),
                "line": state["line"], "function": state["function"],
            })

    severity_order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    result["states"] = states
    result["transitions"] = transitions
    result["issues"] = sorted(
        issues, key=lambda item: (
            severity_order.get(item["severity"], 9), int(item.get("line", 0))))
    return result


def detect_repeated_step_cycles(sequence, minimum_cycles=3, min_period=2,
                                max_period=8):
    """Return bounded repeated suffix cycles from a distinct Step sequence."""
    values = [str(value) for value in sequence if str(value)]
    results = []
    for end in range(1, len(values) + 1):
        for period in range(min_period, max_period + 1):
            size = period * minimum_cycles
            if end < size:
                continue
            block = values[end - period:end]
            if len(set(block)) < 2:
                continue
            if all(values[end - size + offset:end - size + offset + period] == block
                   for offset in range(0, size, period)):
                results.append({
                    "start_index": end - size, "end_index": end - 1,
                    "period": period, "cycles": minimum_cycles,
                    "steps": list(block),
                })
                break
    # Keep only the first occurrence for an identical end/period pair and cap
    # pathological recordings without losing the earliest evidence.
    return results[:200]


def analyze_recording_events(events, max_history=50000):
    """Summarize runtime Step edges and state/watch variable changes."""
    events = [event for event in (events or []) if isinstance(event, dict)]
    edge_counts = collections.Counter()
    edge_first = {}
    edge_last = {}
    distinct_steps = []
    previous_step = ""
    history = []
    last_values = {}
    truncated = False

    for event in events:
        step = str(event.get("step_text", "") or event.get("step_path", "") or "")
        try:
            video_time = max(0.0, float(event.get("video_time", 0.0) or 0.0))
        except (TypeError, ValueError):
            video_time = 0.0
        if step and step != previous_step:
            if previous_step:
                edge = (previous_step, step)
                edge_counts[edge] += 1
                edge_first.setdefault(edge, video_time)
                edge_last[edge] = video_time
            distinct_steps.append(step)
            previous_step = step

        values = {}
        states = event.get("states", {})
        if isinstance(states, dict):
            values.update({str(name): value for name, value in states.items()})
        watched = event.get("watch_values", {})
        if isinstance(watched, dict):
            values.update({str(name): value for name, value in watched.items()})
        for name, value in values.items():
            rendered = str(value)
            if last_values.get(name, object()) == rendered:
                continue
            if len(history) < max(1, int(max_history)):
                history.append({
                    "time": video_time, "name": name,
                    "before": last_values.get(name, "<未記録>"),
                    "after": rendered, "step": step,
                })
            else:
                truncated = True
            last_values[name] = rendered

    transitions = [{
        "from_step": edge[0], "to_step": edge[1], "count": count,
        "first_time": edge_first[edge], "last_time": edge_last[edge],
    } for edge, count in edge_counts.items()]
    transitions.sort(key=lambda item: (item["first_time"], item["from_step"], item["to_step"]))
    return {
        "event_count": len(events),
        "distinct_step_count": len(set(distinct_steps)),
        "step_sequence": distinct_steps,
        "transitions": transitions,
        "variable_history": history,
        "history_truncated": truncated,
        "loops": detect_repeated_step_cycles(distinct_steps),
    }


def build_regression_case(metadata, events, source_analysis, source_text="",
                          source_path=""):
    """Create a portable, deterministic regression fixture dictionary."""
    runtime = analyze_recording_events(events)
    source_analysis = source_analysis if isinstance(source_analysis, dict) else {}
    return {
        "schema": "pokecon_command_regression",
        "schema_version": SCHEMA_VERSION,
        "created_from": os.path.abspath(str(metadata.get("session_dir", "") or ""))
        if isinstance(metadata, dict) else "",
        "command": str(metadata.get("command", "") or "")
        if isinstance(metadata, dict) else "",
        "source": {
            "path": os.path.abspath(source_path) if source_path else "",
            "sha256": hashlib.sha256(str(source_text or "").encode("utf-8")).hexdigest(),
            "state_names": [item["state"] for item in source_analysis.get("states", [])],
            "function_names": [item["name"] for item in source_analysis.get("functions", [])],
            "image_checks": list(source_analysis.get("image_checks", [])),
        },
        "runtime": {
            "step_sequence": runtime["step_sequence"][:5000],
            "transitions": runtime["transitions"][:5000],
            "loops": runtime["loops"],
            "variable_history": runtime["variable_history"][:10000],
        },
    }


def render_regression_unittest(case_path):
    """Render a standalone unittest that audits the fixture's current source."""
    case_path = os.path.abspath(str(case_path))
    return '''#!/usr/bin/env python3
# Generated by PokeCon DevStudio.  This test never starts Commands or sends input.
import ast
import json
import os
import unittest

CASE_PATH = {case_path!r}


class RecordedCommandRegressionTest(unittest.TestCase):
    def setUp(self):
        with open(CASE_PATH, "r", encoding="utf-8") as stream:
            self.case = json.load(stream)

    def test_recorded_steps_and_source_symbols_still_exist(self):
        source_path = self.case["source"]["path"]
        self.assertTrue(os.path.isfile(source_path), source_path)
        with open(source_path, "r", encoding="utf-8") as stream:
            tree = ast.parse(stream.read(), filename=source_path)
        functions = {{
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }}
        missing = sorted(set(self.case["source"]["function_names"]) - functions)
        self.assertEqual(missing, [], "録画時の関数が現在ソースから消えています")
        self.assertGreater(len(self.case["runtime"]["step_sequence"]), 0)


if __name__ == "__main__":
    unittest.main()
'''.format(case_path=case_path)


def load_image_library(path):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, ValueError):
        return {"targets": {}, "lists": {}}
    return value if isinstance(value, dict) else {"targets": {}, "lists": {}}


def _template_path(template_root, portable):
    path = str(portable or "").strip()
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.abspath(path)
    return os.path.abspath(os.path.join(os.path.dirname(template_root), path))


def profile_recorded_video(video_path, library, template_root, target_names,
                           sample_interval=0.5, max_samples=600,
                           cancel_event=None, progress=None):
    """Replay registered template checks against evenly sampled video frames."""
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCVが必要です。") from error
    video_path = os.path.abspath(str(video_path or ""))
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise ValueError("動画を開けません: " + video_path)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    duration = frame_count / max(1.0, fps)
    interval = max(0.05, float(sample_interval))
    count = min(MAX_PROFILE_SAMPLES, max(1, int(max_samples)),
                max(1, int(math.floor(duration / interval)) + 1))
    targets = library.get("targets", {}) if isinstance(library, dict) else {}
    names = [str(name) for name in target_names if str(name) in targets]
    prepared = {}
    missing = []
    for name in names:
        item = targets.get(name, {})
        variants = []
        for variant in item.get("variants", []):
            if not isinstance(variant, dict):
                continue
            path = _template_path(template_root, variant.get("template_path", ""))
            template = cv2.imread(path, cv2.IMREAD_COLOR) if path else None
            if template is None:
                missing.append("{}: {}".format(name, path or "<画像なし>"))
                continue
            variants.append((dict(variant), template))
        prepared[name] = {
            "operator": str(item.get("operator", "OR") or "OR").upper(),
            "variants": variants,
        }
    operation_factor = sum(
        max(1, len(item["variants"])) for item in prepared.values())
    operation_cap = max(1, MAX_PROFILE_MATCH_OPERATIONS // max(1, operation_factor))
    work_capped = count > operation_cap
    count = min(count, operation_cap)

    aggregates = {name: {
        "name": name, "samples": 0, "matches": 0,
        "minimum": 1.0, "maximum": -1.0, "score_sum": 0.0,
        "elapsed_ms": 0.0, "changes": [], "last_match": None,
    } for name in names}
    timeline = []
    started = time.monotonic()
    try:
        for index in range(count):
            if cancel_event is not None and cancel_event.is_set():
                break
            video_time = min(duration, index * interval)
            capture.set(cv2.CAP_PROP_POS_MSEC, video_time * 1000.0)
            ok, frame = capture.read()
            if not ok:
                continue
            frame_height, frame_width = frame.shape[:2]
            row = {"time": video_time, "targets": {}}
            for name in names:
                if cancel_event is not None and cancel_event.is_set():
                    break
                target_started = time.perf_counter()
                item = prepared[name]
                variant_results = []
                for variant, template in item["variants"]:
                    if cancel_event is not None and cancel_event.is_set():
                        break
                    crop = variant.get("crop", [0, 0, 0, 0])
                    try:
                        x1, y1, x2, y2 = [int(value) for value in crop]
                    except (TypeError, ValueError):
                        x1, y1, x2, y2 = 0, 0, 0, 0
                    if not any((x1, y1, x2, y2)):
                        x1, y1, x2, y2 = 0, 0, frame_width, frame_height
                    else:
                        x1, y1 = max(0, x1), max(0, y1)
                        x2 = frame_width if x2 <= 0 else min(frame_width, x2)
                        y2 = frame_height if y2 <= 0 else min(frame_height, y2)
                    region = frame[y1:y2, x1:x2]
                    scaled = template
                    use_gray = bool(variant.get("use_gray", True))
                    if use_gray and region.size:
                        region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                        scaled = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
                    if (region.size == 0 or region.shape[0] < scaled.shape[0]
                            or region.shape[1] < scaled.shape[1]):
                        score = -1.0
                    else:
                        result = cv2.matchTemplate(
                            region, scaled, cv2.TM_CCOEFF_NORMED)
                        exclusions = variant.get("exclude_regions", [])
                        if isinstance(exclusions, list) and exclusions:
                            result = result.copy()
                            result_height, result_width = result.shape[:2]
                            template_height, template_width = scaled.shape[:2]
                            for exclusion in exclusions:
                                try:
                                    ex1, ey1, ex2, ey2 = [int(value) for value in exclusion]
                                except (TypeError, ValueError):
                                    continue
                                if ex2 <= ex1 or ey2 <= ey1:
                                    continue
                                left = max(0, ex1 - x1 - template_width + 1)
                                right = min(result_width, ex2 - x1)
                                top = max(0, ey1 - y1 - template_height + 1)
                                bottom = min(result_height, ey2 - y1)
                                if left < right and top < bottom:
                                    result[top:bottom, left:right] = -2.0
                        _minimum, score, _min_pos, _max_pos = cv2.minMaxLoc(result)
                    threshold = float(variant.get("threshold", 0.8) or 0.8)
                    variant_results.append((float(score), float(threshold)))
                operator = item["operator"]
                scores = [value[0] for value in variant_results]
                if operator == "AND":
                    score = min(scores) if scores else -1.0
                    matched = bool(variant_results) and all(
                        value >= threshold for value, threshold in variant_results)
                else:
                    score = max(scores) if scores else -1.0
                    matched = any(value >= threshold
                                  for value, threshold in variant_results)
                elapsed_ms = (time.perf_counter() - target_started) * 1000.0
                aggregate = aggregates[name]
                aggregate["samples"] += 1
                aggregate["matches"] += int(matched)
                aggregate["minimum"] = min(aggregate["minimum"], score)
                aggregate["maximum"] = max(aggregate["maximum"], score)
                aggregate["score_sum"] += score
                aggregate["elapsed_ms"] += elapsed_ms
                if aggregate["last_match"] is None or aggregate["last_match"] != matched:
                    aggregate["changes"].append({"time": video_time, "matched": matched, "score": score})
                aggregate["last_match"] = matched
                row["targets"][name] = {"score": score, "matched": matched}
            timeline.append(row)
            if cancel_event is not None and cancel_event.is_set():
                break
            if callable(progress) and (index % 10 == 0 or index + 1 == count):
                progress(index + 1, count)
    finally:
        capture.release()

    summaries = []
    for name in names:
        item = aggregates[name]
        samples = max(1, item["samples"])
        summaries.append({
            "name": name, "samples": item["samples"], "matches": item["matches"],
            "match_rate": item["matches"] / float(samples),
            "minimum": item["minimum"] if item["samples"] else -1.0,
            "maximum": item["maximum"] if item["samples"] else -1.0,
            "average": item["score_sum"] / float(samples),
            "average_ms": item["elapsed_ms"] / float(samples),
            "changes": item["changes"],
        })
    return {
        "video": video_path, "duration": duration, "fps": fps,
        "requested_samples": count, "processed_samples": len(timeline),
        "work_capped": work_capped,
        "max_match_operations": MAX_PROFILE_MATCH_OPERATIONS,
        "cancelled": bool(cancel_event is not None and cancel_event.is_set()),
        "elapsed": max(0.0, time.monotonic() - started),
        "missing_templates": missing,
        "targets": summaries, "timeline": timeline,
    }
