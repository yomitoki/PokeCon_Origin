#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backend for turning recorded controller rows into editable Commands code."""
from __future__ import print_function

import difflib
import ast
import json
import math
import os
import re
import textwrap
import uuid


MAPPING_KINDS = ("step", "function", "raw", "ignore")
GENERATION_TARGET_SWITCH = "switch"
GENERATION_TARGET_PORTABLE = "switch_steam_ps4"
GENERATION_TARGETS = (GENERATION_TARGET_SWITCH, GENERATION_TARGET_PORTABLE)
STICK_MODE_EXACT = "exact"
STICK_MODE_EIGHT_WAY = "eight_way"
STICK_MODES = (STICK_MODE_EXACT, STICK_MODE_EIGHT_WAY)
BEGIN_MARKER = "# POKECON_OPERATION_SESSION:{session_id}:BEGIN"
END_MARKER = "# POKECON_OPERATION_SESSION:{session_id}:END"


def input_row_is_commands_recordable(item):
    """Exclude keyboard-origin rows, including rows from older sessions."""
    source = str((item or {}).get("source", "") or "").strip().lower()
    return "keyboard" not in source


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
        return value
    except (OSError, ValueError):
        return default


def atomic_json(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = path + ".tmp-" + uuid.uuid4().hex
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def load_session(session_dir):
    path = os.path.join(os.path.abspath(session_dir), "session.json")
    value = load_json(path, None)
    if not isinstance(value, dict):
        raise ValueError("session.jsonを読み込めません。")
    return value


def load_inputs(session_dir):
    result = []
    path = os.path.join(os.path.abspath(session_dir), "inputs.jsonl")
    try:
        with open(path, "r", encoding="utf-8") as stream:
            for text in stream:
                try:
                    item = json.loads(text)
                except ValueError:
                    continue
                if (isinstance(item, dict) and item.get("kind") == "input"
                        and input_row_is_commands_recordable(item)):
                    result.append(item)
    except OSError:
        pass
    return sorted(result, key=lambda item: int(item.get("line", 0)))


def operation_video_sources(session):
    """Return playable combined or per-segment videos with timeline origins."""
    if not isinstance(session, dict):
        return []
    result = []
    outputs = session.get("outputs", {})
    if isinstance(outputs, dict):
        for label, key in (("1280x720 元映像", "clean_video"),
                           ("操作情報付き映像", "input_overlay_video")):
            path = str(outputs.get(key, "") or "")
            if path and os.path.isfile(path):
                result.append({"label": label, "path": os.path.abspath(path),
                               "timeline_start": 0.0,
                               "duration": float(session.get("active_duration", 0.0) or 0.0)})
    if result:
        return result
    for index, segment in enumerate(session.get("segments", []) or [], 1):
        if not isinstance(segment, dict):
            continue
        folder = os.path.abspath(str(segment.get("recorder_dir", "") or ""))
        candidates = (os.path.join(folder, "recording.avi"),
                      os.path.join(folder, "recording.mp4"),
                      str(segment.get("media_hint", "") or ""))
        path = next((os.path.abspath(item) for item in candidates
                     if item and os.path.isfile(item)), "")
        if path:
            number = int(segment.get("number", index) or index)
            result.append({
                "label": "未結合 区間{}".format(number),
                "path": path,
                "timeline_start": float(segment.get("timeline_start", 0.0) or 0.0),
                "duration": float(segment.get("duration", 0.0) or 0.0),
            })
    return result


def mappings_path(session_dir):
    return os.path.join(os.path.abspath(session_dir), "mappings.json")


def normalize_mapping(item):
    result = dict(item or {})
    result["id"] = str(result.get("id") or uuid.uuid4().hex)
    try:
        result["start_line"] = max(1, int(result.get("start_line", 1)))
        result["end_line"] = max(result["start_line"], int(result.get("end_line", result["start_line"])))
    except (TypeError, ValueError):
        result["start_line"], result["end_line"] = 1, 1
    result["kind"] = str(result.get("kind", "raw"))
    if result["kind"] not in MAPPING_KINDS:
        result["kind"] = "raw"
    for key in ("step_name", "next_step", "function_name", "call_from_step", "notes"):
        result[key] = str(result.get(key, ""))
    return result


def load_mappings(session_dir):
    value = load_json(mappings_path(session_dir), {"schema_version": 1, "mappings": []})
    rows = value.get("mappings", []) if isinstance(value, dict) else []
    return sorted([normalize_mapping(item) for item in rows if isinstance(item, dict)],
                  key=lambda item: (item["start_line"], item["end_line"]))


def save_mappings(session_dir, mappings):
    rows = sorted([normalize_mapping(item) for item in mappings],
                  key=lambda item: (item["start_line"], item["end_line"]))
    atomic_json(mappings_path(session_dir), {"schema_version": 1, "mappings": rows})
    return rows


def covered_lines(mappings, include_ignored=True):
    result = set()
    for mapping in mappings:
        if include_ignored or mapping.get("kind") != "ignore":
            result.update(range(int(mapping["start_line"]), int(mapping["end_line"]) + 1))
    return result


def pending_lines(inputs, mappings):
    covered = covered_lines(mappings, include_ignored=True)
    return [int(item.get("line", 0)) for item in inputs
            if int(item.get("line", 0)) not in covered]


def pending_neighbor(inputs, mappings, current_line=0, forward=True):
    rows = pending_lines(inputs, mappings)
    if not rows:
        return None
    if forward:
        return next((line for line in rows if line > int(current_line or 0)), rows[0])
    return next((line for line in reversed(rows) if line < int(current_line or 0)), rows[-1])


def compact_line_ranges(lines):
    """Format thousands of pending rows without creating one enormous line."""
    values = sorted(set(int(value) for value in lines))
    if not values:
        return ""
    ranges = []
    start = previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append((start, previous))
        start = previous = value
    ranges.append((start, previous))
    return ", ".join(
        "#{:04d}".format(start) if start == end else
        "#{:04d}-#{:04d}".format(start, end)
        for start, end in ranges)


def _identifier(value, fallback):
    text = re.sub(r"\W+", "_", str(value or "").strip(), flags=re.UNICODE).strip("_")
    if not text:
        text = fallback
    if text[:1].isdigit():
        text = "_" + text
    return text


def rows_for_mapping(inputs, mapping):
    start, end = int(mapping["start_line"]), int(mapping["end_line"])
    return [item for item in inputs if start <= int(item.get("line", 0)) <= end]


def normalize_stick_mode(value):
    value = str(value or STICK_MODE_EXACT).strip().lower()
    return value if value in STICK_MODES else STICK_MODE_EXACT


def _quantized_stick_xy(stick):
    """Round only the angle to 45 degrees while retaining recorded magnitude."""
    if not isinstance(stick, dict) or stick.get("angle") is None:
        return None
    try:
        angle = float(stick["angle"]) % 360.0
        magnitude = max(0.0, min(1.0, float(stick.get("magnitude", 0.0))))
    except (TypeError, ValueError):
        return None
    angle = (math.floor((angle + 22.5) / 45.0) * 45.0) % 360.0
    try:
        radius = min(127.0, math.hypot(
            float(stick["x"]) - 128.0, 128.0 - float(stick["y"])))
    except (KeyError, TypeError, ValueError):
        radius = 127.0 * magnitude
    radians = math.radians(angle)
    x = max(0, min(255, int(round(128.0 + math.cos(radians) * radius))))
    y = max(0, min(255, int(round(128.0 - math.sin(radians) * radius))))
    return x, y


def quantize_serial_stick_message(row):
    """Return a packet with its present stick angles quantized to eight ways."""
    message = str((row or {}).get("message", ""))
    parts = message.split()
    if len(parts) < 2:
        return message
    try:
        bits = int(parts[0], 16)
    except (TypeError, ValueError):
        return message
    position = 2
    for flag, key in ((0x2, "left_stick"), (0x1, "right_stick")):
        if not bits & flag:
            continue
        if position + 1 >= len(parts):
            return message
        value = _quantized_stick_xy((row or {}).get(key))
        if value is not None:
            parts[position] = "{:02x}".format(value[0])
            parts[position + 1] = "{:02x}".format(value[1])
        position += 2
    return " ".join(parts)


def direct_serial_lines(rows, indent="        ", stick_mode=STICK_MODE_EXACT):
    if not rows:
        return [indent + "pass  # 入力なし"]
    stick_mode = normalize_stick_mode(stick_mode)
    messages = [
        quantize_serial_stick_message(item)
        if stick_mode == STICK_MODE_EIGHT_WAY else str(item.get("message", ""))
        for item in rows
    ]
    waits = [0.0]
    for index in range(1, len(rows)):
        waits.append(max(0.0, float(rows[index].get("time", 0.0)) -
                         float(rows[index - 1].get("time", 0.0))))
    return [indent + "self.direct_serial(",
            indent + "    {!r},".format(messages),
            indent + "    {!r},".format([round(value, 6) for value in waits]),
            indent + ")"]


def normalize_generation_target(value):
    value = str(value or GENERATION_TARGET_SWITCH).strip().lower()
    return value if value in GENERATION_TARGETS else GENERATION_TARGET_SWITCH


def _stick_direction_name(prefix, stick):
    if not isinstance(stick, dict) or stick.get("angle") is None:
        return ""
    try:
        angle = float(stick["angle"]) % 360.0
        magnitude = float(stick.get("magnitude", 0.0))
    except (TypeError, ValueError):
        return ""
    if magnitude < 0.05:
        return ""
    directions = (
        "right", "up_right", "up", "up_left",
        "left", "down_left", "down", "down_right",
    )
    return "{}_{}".format(prefix, directions[int((angle + 22.5) // 45.0) % 8])


def _exact_stick_name(prefix, stick):
    if not isinstance(stick, dict) or stick.get("angle") is None:
        return ""
    try:
        angle = float(stick["angle"]) % 360.0
        magnitude = max(0.0, min(1.0, float(stick.get("magnitude", 0.0))))
    except (TypeError, ValueError):
        return ""
    if magnitude < 0.05:
        return ""
    return "{}@{:.2f}/{:.4f}".format(prefix, angle, magnitude)


def semantic_controls(row, stick_mode=STICK_MODE_EIGHT_WAY):
    """Return platform-neutral names understood by game_input_state()."""
    result = []
    for button in row.get("buttons", []) if isinstance(row, dict) else []:
        name = str(button or "").strip().upper()
        if name and name not in result:
            result.append(name)
    hat_names = {
        "UP": "Lbutton_up", "UP_RIGHT": "Lbutton_up_right",
        "RIGHT": "Lbutton_right", "DOWN_RIGHT": "Lbutton_down_right",
        "DOWN": "Lbutton_down", "DOWN_LEFT": "Lbutton_down_left",
        "LEFT": "Lbutton_left", "UP_LEFT": "Lbutton_up_left",
    }
    hat = hat_names.get(str(row.get("hat", "CENTER")).upper()) \
        if isinstance(row, dict) else None
    if hat and hat not in result:
        result.append(hat)
    for prefix, key in (("Lstick", "left_stick"), ("Rstick", "right_stick")):
        if normalize_stick_mode(stick_mode) == STICK_MODE_EXACT:
            name = _exact_stick_name(prefix, row.get(key)) \
                if isinstance(row, dict) else ""
        else:
            name = _stick_direction_name(prefix, row.get(key)) \
                if isinstance(row, dict) else ""
        if name and name not in result:
            result.append(name)
    return result


def portable_input_lines(rows, indent="        ", stick_mode=STICK_MODE_EXACT):
    """Generate semantic input states reusable by Switch, Steam and PS4."""
    if not rows:
        return [indent + "pass  # 入力なし"]
    result = []
    for index, row in enumerate(rows):
        current = float(row.get("time", 0.0))
        if index + 1 < len(rows):
            duration = max(0.0, float(rows[index + 1].get("time", current)) - current)
        else:
            duration = 0.1 if semantic_controls(row, stick_mode) else 0.0
        controls = semantic_controls(row, stick_mode)
        if controls:
            result.append(indent + "self.game_input_state(")
            result.append(indent + "    {!r}, duration={}, wait=0.0,".format(
                controls, round(duration, 6)))
            result.append(indent + ")")
        elif duration:
            result.append(indent + "self.wait({})".format(round(duration, 6)))
    return result or [indent + "pass  # 入力なし"]


def generated_input_lines(rows, target, indent="        ",
                          stick_mode=STICK_MODE_EXACT):
    if normalize_generation_target(target) == GENERATION_TARGET_PORTABLE:
        return portable_input_lines(rows, indent, stick_mode=stick_mode)
    return direct_serial_lines(rows, indent, stick_mode=stick_mode)


def _step_body_lines(inputs, step_mapping, nested_mappings,
                     generation_target=GENERATION_TARGET_SWITCH,
                     stick_mode=STICK_MODE_EXACT):
    """Keep nested functions in order and omit intentionally ignored ranges."""
    start = int(step_mapping["start_line"])
    end = int(step_mapping["end_line"])
    children = sorted(
        (item for item in nested_mappings
         if int(item["start_line"]) >= start and int(item["end_line"]) <= end),
        key=lambda item: (int(item["start_line"]), int(item["end_line"])))
    result = []
    cursor = start
    previous_time = None

    def wait_before(rows):
        if previous_time is None or not rows:
            return
        gap = max(0.0, float(rows[0].get("time", 0.0)) - previous_time)
        if gap:
            value = "{:.6f}".format(gap).rstrip("0").rstrip(".")
            result.append("    self.wait({})".format(value))

    for child in children:
        child_start, child_end = int(child["start_line"]), int(child["end_line"])
        if child_start < cursor:
            continue
        direct = [row for row in inputs
                  if cursor <= int(row.get("line", 0)) < child_start]
        if direct:
            wait_before(direct)
            result.extend(generated_input_lines(
                direct, generation_target, "    ", stick_mode=stick_mode))
            previous_time = float(direct[-1].get("time", 0.0))
        child_rows = [row for row in inputs
                      if child_start <= int(row.get("line", 0)) <= child_end]
        if child.get("kind") == "function":
            wait_before(child_rows)
            result.append("    self.{}()".format(
                _identifier(child.get("function_name"), "recorded_function")))
        else:
            result.append("    # 反映不要: 入力 #{:04d}-#{:04d} {}".format(
                child_start, child_end, child.get("notes", "")).rstrip())
        if child_rows:
            previous_time = float(child_rows[-1].get("time", 0.0))
        cursor = child_end + 1
    direct = [row for row in inputs if cursor <= int(row.get("line", 0)) <= end]
    if direct:
        wait_before(direct)
        result.extend(generated_input_lines(
            direct, generation_target, "    ", stick_mode=stick_mode))
    return result or ["    pass  # 入力なし"]


def generate_intermediate(session, inputs, mappings,
                          generation_target=GENERATION_TARGET_SWITCH,
                          stick_mode=STICK_MODE_EXACT):
    inputs = [item for item in inputs if input_row_is_commands_recordable(item)]
    generation_target = normalize_generation_target(generation_target)
    stick_mode = normalize_stick_mode(stick_mode)
    session_id = str(session.get("session_id", "operation"))
    lines = [BEGIN_MARKER.format(session_id=session_id),
             "# DevStudio 操作記録から生成。mappings.jsonと映像が根拠です。",
             "# 未割当行は意図的にTODOとして残し、勝手に最終ソースへ反映しません。"]
    if generation_target == GENERATION_TARGET_PORTABLE:
        lines.extend([
            "# 入力対象: Switch＋Steam/PS4流用。Steam_Switch_Game_Inputサンプル関数を使用します。",
            "# キーはgame_input_profilesまたはset_game_input_mapping()で後から変更できます。",
            "# 画像検知は共通論理名をgame_image_check()へ渡します。初期状態は全機種共通で、",
            "# game_image_profiles / set_game_image_mapping()により機種別へ後から差し替えられます。",
        ])
    else:
        lines.append("# 入力対象: Switchのみ。")
    if stick_mode == STICK_MODE_EXACT:
        lines.append(
            "# スティック角度: 記録角度と倒し量を保持（PCキー流用時のみ最寄り8方向）。")
    else:
        lines.append(
            "# スティック角度: 倒し量を保持し、角度を最寄りの45度単位へ変換。")
    lines.append("")
    calls_by_step = {}
    for mapping in mappings:
        if mapping.get("kind") != "function" or not mapping.get("call_from_step"):
            continue
        step_name = _identifier(mapping.get("call_from_step"), "")
        function_name = _identifier(mapping.get("function_name"), "recorded_function")
        if step_name:
            calls_by_step.setdefault(step_name, []).append(function_name)
    emitted_steps = set()
    emitted_functions = set()
    for mapping in sorted(mappings, key=lambda item: (item["start_line"], item["end_line"])):
        rows = rows_for_mapping(inputs, mapping)
        kind = mapping.get("kind")
        range_text = "入力 #{:04d}-#{:04d}".format(mapping["start_line"], mapping["end_line"])
        if kind == "ignore":
            nested_in_step = any(
                item.get("kind") == "step"
                and int(item["start_line"]) <= int(mapping["start_line"])
                and int(item["end_line"]) >= int(mapping["end_line"])
                for item in mappings)
            if not nested_in_step:
                lines.extend(["# 反映不要: {} {}".format(
                    range_text, mapping.get("notes", "")).rstrip(), ""])
            continue
        if kind == "function":
            name = _identifier(mapping.get("function_name"), "recorded_function")
            emitted_functions.add(name)
            lines.extend(["def {}(self):".format(name), "    # " + range_text])
            lines.extend(generated_input_lines(
                rows, generation_target, "    ", stick_mode=stick_mode))
            lines.append("")
            continue
        if kind == "step":
            name = _identifier(mapping.get("step_name"), "RECORDED_STEP")
            emitted_steps.add(name)
            lines.extend(["def {}(self):".format(name), "    # " + range_text])
            nested = [item for item in mappings
                      if ((item.get("kind") == "function"
                           and _identifier(item.get("call_from_step"), "") == name)
                          or item.get("kind") == "ignore")]
            lines.extend(_step_body_lines(
                inputs, mapping, nested, generation_target=generation_target,
                stick_mode=stick_mode))
            next_step = str(mapping.get("next_step", "")).strip()
            if next_step:
                lines.append("    return {!r}".format(next_step))
            lines.append("")
            continue
        raw_name = "recorded_input_{:04d}_{:04d}".format(
            mapping["start_line"], mapping["end_line"])
        lines.extend(["def {}(self):".format(raw_name), "    # 直接処理: " + range_text])
        lines.extend(generated_input_lines(
            rows, generation_target, "    ", stick_mode=stick_mode))
        lines.append("")
    # A function may have been assigned before the Step mapping.  Make these
    # relationships visible even if the user has not regenerated the Step yet.
    for step_name, function_names in sorted(calls_by_step.items()):
        if step_name not in emitted_steps:
            lines.append("# TODO: {} から {} を呼び出す".format(
                step_name, ", ".join("self.{}()".format(name) for name in function_names)))
    pending = pending_lines(inputs, mappings)
    if pending:
        lines.extend(["", "# TODO 未割当入力: " + compact_line_ranges(pending)])
    lines.extend([END_MARKER.format(session_id=session_id), ""])
    return "\n".join(lines)


def source_class_names(source):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, TypeError):
        return []
    return [node.name for node in tree.body if isinstance(node, ast.ClassDef)]


def _indented_generated(generated, indent):
    return "\n".join((indent + line) if line else "" for line in generated.rstrip().splitlines()) + "\n"


def _insert_into_class(original, generated, class_name):
    tree = ast.parse(original)
    classes = [node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == class_name]
    if not classes:
        raise ValueError("指定したクラスが最終ファイルにありません: " + str(class_name))
    target = classes[0]
    following = [node.lineno for node in tree.body if node.lineno > target.lineno]
    insert_line = min(following) - 1 if following else len(original.splitlines())
    lines = original.splitlines(True)
    class_line = lines[target.lineno - 1]
    class_indent = class_line[:len(class_line) - len(class_line.lstrip())] + "    "
    block = "\n" + _indented_generated(generated, class_indent)
    if insert_line >= len(lines):
        separator = "" if not original or original.endswith("\n") else "\n"
        return original + separator + block.lstrip("\n")
    lines.insert(insert_line, block)
    return "".join(lines)


def _function_records(source, class_name=None):
    tree = ast.parse(source)
    lines = source.splitlines(True)
    if class_name is None:
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    else:
        command = next((node for node in tree.body
                        if isinstance(node, ast.ClassDef) and node.name == class_name), None)
        if command is None:
            raise ValueError("指定したクラスが最終ファイルにありません: " + str(class_name))
        nodes = [node for node in command.body if isinstance(node, ast.FunctionDef)]
    records = {}
    for node in nodes:
        starts = [node.lineno] + [decorator.lineno for decorator in node.decorator_list]
        start = min(starts) - 1
        end = getattr(node, "end_lineno", None)
        if end is None:
            end = len(lines)
            for index in range(node.lineno, len(lines)):
                value = lines[index]
                if not value.strip():
                    continue
                indentation = len(value) - len(value.lstrip(" \t"))
                if indentation <= node.col_offset:
                    end = index
                    break
        records[node.name] = {
            "start": start, "end": int(end),
            "text": textwrap.dedent("".join(lines[start:int(end)])).rstrip() + "\n",
        }
    return records


def _without_generated_region(source, session_id):
    begin = BEGIN_MARKER.format(session_id=session_id)
    end = END_MARKER.format(session_id=session_id)
    start = source.find(begin)
    if start < 0:
        return source
    finish = source.find(end, start)
    if finish < 0:
        raise ValueError("最終ファイル内の操作セッション終了マーカーがありません。")
    line_start = source.rfind("\n", 0, start) + 1
    line_end = source.find("\n", finish + len(end))
    line_end = len(source) if line_end < 0 else line_end + 1
    return source[:line_start] + source[line_end:]


def _remove_functions(generated, names):
    records = _function_records(generated)
    lines = generated.splitlines(True)
    ranges = [(record["start"], record["end"])
              for name, record in records.items() if name in names]
    for start, end in sorted(ranges, reverse=True):
        lines[start:end] = []
    return "".join(lines)


def _merge_generated_into_class(original, generated, session_id, class_name):
    # A prior session block contains only methods that were new at that time.
    # Remove it first so deleted/renamed mappings do not remain as stale code.
    base = _without_generated_region(original, session_id)
    generated_records = _function_records(generated)
    source_records = _function_records(base, class_name=class_name)
    matched = set(generated_records).intersection(source_records)
    lines = base.splitlines(True)
    tree = ast.parse(base)
    command = next(node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == class_name)
    class_line = lines[command.lineno - 1]
    indent = class_line[:len(class_line) - len(class_line.lstrip())] + "    "
    for name in sorted(matched, key=lambda value: source_records[value]["start"], reverse=True):
        source_record = source_records[name]
        block = textwrap.indent(generated_records[name]["text"].rstrip(), indent) + "\n"
        lines[source_record["start"]:source_record["end"]] = [block]
    updated = "".join(lines)
    remaining = _remove_functions(generated, matched)
    updated = _insert_into_class(updated, remaining, class_name)
    ast.parse(updated)
    return updated


def replace_generated_region(original, generated, session_id, class_name=None):
    if class_name:
        return _merge_generated_into_class(
            original, generated, session_id, class_name)
    begin = BEGIN_MARKER.format(session_id=session_id)
    end = END_MARKER.format(session_id=session_id)
    start = original.find(begin)
    if start >= 0:
        finish = original.find(end, start)
        if finish < 0:
            raise ValueError("最終ファイル内の操作セッション終了マーカーがありません。")
        finish += len(end)
        line_start = original.rfind("\n", 0, start) + 1
        indent = original[line_start:start]
        rendered = _indented_generated(generated, indent).rstrip("\n")
        suffix = "\n" if original[finish:finish + 1] == "\n" else ""
        return original[:line_start] + rendered + suffix + original[finish + len(suffix):]
    separator = "" if not original or original.endswith("\n\n") else ("\n" if original.endswith("\n") else "\n\n")
    return original + separator + generated


def unified_diff(original, updated, from_name="最終ファイル（現在）", to_name="中間反映後"):
    return "".join(difflib.unified_diff(
        original.splitlines(True), updated.splitlines(True),
        fromfile=from_name, tofile=to_name))
