"""Discover and apply start/end/debug/recovery options for Python Commands."""
from __future__ import annotations

import ast
import copy
import inspect
import re

from CommandStartOverride import apply_command_start_override


STATE_SUFFIX = "_FUNCTION"
DEBUG_ATTRIBUTE_NAMES = {
    "DEBUG", "debug", "TESTADDCODE", "testcode", "fastread"}
RECOVERY_METHOD_NAMES = (
    "delete_save_for_user", "delete_save_data_for_user",
    "delete_save_data", "delete_save", "on_save_delete_retry")


def preserve_location_selection(current, visible, fallback=""):
    """Keep an already selected run location when filters hide it.

    Start and end share the search controls. Selecting a start in one chapter
    and then filtering another chapter for the end must not clear the start.
    """
    current = str(current or "")
    if current:
        return current
    visible = list(visible or [])
    return visible[0] if visible else str(fallback or "")


def _literal(node, default=None):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return default


def _assigned_name(statement):
    targets = (statement.targets if isinstance(statement, ast.Assign)
               else [statement.target] if isinstance(statement, ast.AnnAssign)
               else [])
    for target in targets:
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute) and \
                isinstance(target.value, ast.Name) and target.value.id == "self":
            return target.attr
    return ""


def _class_literal(command, name, default=None):
    for statement in command.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)) and \
                _assigned_name(statement) == name:
            return _literal(statement.value, default)
    return default


def _description_map(command):
    result = {}
    for name in ("COMMAND_STEP_DESCRIPTIONS", "STEP_DESCRIPTIONS",
                 "RUN_LOCATION_DESCRIPTIONS"):
        value = _class_literal(command, name, {})
        if isinstance(value, dict):
            result.update({str(key): str(description)
                           for key, description in value.items()})
    return result


def _state_locations(command, descriptions):
    methods = {node.name: node for node in command.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    result = []
    for statement in ast.walk(command):
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)) or \
                not isinstance(statement.value, ast.Dict):
            continue
        name = _assigned_name(statement)
        if not (name.startswith("STATE_") and name.endswith(STATE_SUFFIX)):
            continue
        for order, (key, value) in enumerate(zip(
                statement.value.keys, statement.value.values)):
            state = _literal(key)
            if not isinstance(state, str):
                continue
            handler = (value.attr if isinstance(value, ast.Attribute) and
                       isinstance(value.value, ast.Name) and
                       value.value.id == "self" else "")
            description = descriptions.get(state, "")
            if not description and handler in methods:
                description = ast.get_docstring(methods[handler]) or ""
            result.append({
                "id": "state:{}:{}".format(name, state),
                "kind": "state", "mode": "state", "variable": name,
                "value": state, "label": state,
                "description": description,
                "group": name, "order": order,
            })
    return result


def _step_locations(command, descriptions):
    labels = _class_literal(command, "STEP_LABELS", [])
    keys = _class_literal(command, "STEP_KEYS", [])
    if not isinstance(labels, (list, tuple)):
        return []
    result = []
    for index, label in enumerate(labels):
        key = (keys[index] if isinstance(keys, (list, tuple)) and
               index < len(keys) and keys[index] not in (None, "") else index)
        display = str(label)
        result.append({
            "id": "step:{}".format(index), "kind": "step",
            "mode": "attribute", "variable": "step", "value": index,
            "label": display,
            "description": descriptions.get(str(key),
                                                descriptions.get(display, "")),
            "group": "STEP_LABELS", "order": index,
        })
    return result


def _numbered_route_locations(command):
    result = []
    for statement in ast.walk(command):
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)) or \
                _assigned_name(statement) not in (
                    "cb_restart_flag", "COMMAND_ROUTE_LOCATIONS"):
            continue
        values = _literal(statement.value, [])
        if not isinstance(values, (list, tuple)):
            continue
        for order, raw in enumerate(values):
            text = str(raw)
            match = re.match(r"\s*(\d+)\s*[:：]\s*(.*)", text)
            number = int(match.group(1)) if match else order
            description = match.group(2).strip() if match else text.strip()
            result.append({
                "id": "route:{}".format(number), "kind": "route",
                "mode": "attribute", "variable": "restart_flag",
                "end_variable": "stop_flag", "value": number,
                "dialog_value": text, "label": "{}: {}".format(
                    number, description), "description": description,
                "group": "番号付きルート", "order": order,
                "dialog_start_index": 0, "dialog_end_index": 1,
            })
        if result:
            break
    return result


def _explicit_locations(command):
    value = _class_literal(command, "COMMAND_RUN_LOCATIONS", [])
    if not isinstance(value, (list, tuple)):
        return []
    result = []
    for order, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row.setdefault("id", str(row.get("value", order)))
        row.setdefault("label", str(row.get("value", row["id"])))
        row.setdefault("description", "")
        row.setdefault("mode", "state" if row.get("variable", "").startswith(
            "STATE_") else "attribute")
        row.setdefault("kind", "explicit")
        row.setdefault("group", "Commands定義")
        row.setdefault("order", order)
        result.append(row)
    return result


def _debug_options(command):
    explicit = _class_literal(command, "COMMAND_DEBUG_OPTIONS", [])
    if isinstance(explicit, (list, tuple)) and explicit:
        result = []
        for item in explicit:
            if isinstance(item, str):
                item = {"attribute": item, "label": item}
            if not isinstance(item, dict) or not item.get("attribute"):
                continue
            row = dict(item)
            row.setdefault("id", row["attribute"])
            row.setdefault("label", row["attribute"])
            row.setdefault("description", "")
            row.setdefault("default", False)
            result.append(row)
        return result
    found = {}
    for statement in ast.walk(command):
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        name = _assigned_name(statement)
        if name not in DEBUG_ATTRIBUTE_NAMES:
            continue
        default = _literal(statement.value, False)
        found[name] = {
            "id": name, "attribute": name, "label": name,
            "description": "Commands内で検出したデバッグ設定",
            "default": bool(default),
        }
    return [found[name] for name in sorted(found, key=str.casefold)]


def discover_command_run_options(source, class_name=""):
    """Read selectable run locations and debug/recovery capabilities."""
    tree = ast.parse(source)
    class_nodes = {node.name: node for node in tree.body
                   if isinstance(node, ast.ClassDef)}
    command = next((node for node in tree.body
                    if isinstance(node, ast.ClassDef)
                    and (not class_name or node.name == class_name)), None)
    if command is None:
        raise ValueError("Commandsクラスがありません。")
    chain = []
    visiting = set()

    def add_bases(node):
        if node.name in visiting:
            return
        visiting.add(node.name)
        for base in node.bases:
            base_name = base.id if isinstance(base, ast.Name) else ""
            if base_name in class_nodes:
                add_bases(class_nodes[base_name])
        chain.append(node)

    add_bases(command)
    descriptions = {}
    for node in chain:
        descriptions.update(_description_map(node))
    locations = []
    for node in reversed(chain):
        locations.extend(_explicit_locations(node))
    if not locations:
        for node in chain:
            locations.extend(_step_locations(node, descriptions))
            locations.extend(_numbered_route_locations(node))
            locations.extend(_state_locations(node, descriptions))
    seen, unique = set(), []
    for row in locations:
        key = (row.get("mode"), row.get("variable"), row.get("value"))
        if key in seen:
            continue
        seen.add(key); unique.append(row)
    methods = {item.name for node in chain for item in node.body
               if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
    recovery = {}
    for node in chain:
        value = _class_literal(node, "COMMAND_SAVE_RECOVERY", {})
        if isinstance(value, dict):
            recovery.update(value)
    recovery_method = str(recovery.get("method", ""))
    if not recovery_method:
        recovery_method = next((name for name in RECOVERY_METHOD_NAMES
                                if name in methods), "")
    recovery.update({
        "method": recovery_method,
        "available": bool(recovery_method),
        "user_attribute": str(recovery.get(
            "user_attribute", "save_delete_user_number")),
        "max_retries": max(1, int(recovery.get("max_retries", 1) or 1)),
    })
    debug_by_attribute = {}
    for node in chain:
        for row in _debug_options(node):
            debug_by_attribute[str(row.get(
                "attribute", row.get("id", "")))] = row
    enabled = any(bool(_class_literal(
        node, "COMMAND_RUN_SETTINGS", False)) for node in chain)
    return {
        "class_name": command.name, "locations": unique,
        "enabled": enabled,
        "debug_options": list(debug_by_attribute.values()),
        "save_recovery": recovery,
    }


def apply_command_run_options(command, config):
    """Apply one saved run profile to a fresh Commands instance."""
    config = copy.deepcopy(config or {})
    assignments = []
    start = config.get("start") or {}
    if start:
        mode = start.get("mode", "state")
        if mode == "state":
            assignments.extend(apply_command_start_override(
                command, start.get("variable", ""), start.get("value", "")))
        else:
            variable = str(start.get("variable", ""))
            if variable:
                setattr(command, variable, start.get("value"))
                assignments.append({
                    "variable": variable, "attribute": variable,
                    "value": start.get("value"), "uses_init": False})
    end = config.get("end") or {}
    if end and end.get("mode") == "attribute":
        variable = str(end.get("end_variable") or end.get("variable", ""))
        if variable:
            setattr(command, variable, end.get("value"))
            assignments.append({
                "variable": variable, "attribute": variable,
                "value": end.get("value"), "uses_init": False})
    _install_end_hook(command, end)
    for attribute, enabled in (config.get("debug") or {}).items():
        setattr(command, str(attribute), bool(enabled))
        assignments.append({
            "variable": str(attribute), "attribute": str(attribute),
            "value": bool(enabled), "uses_init": False})
    user_number = max(0, int(config.get("save_delete_user_number", 0) or 0))
    setattr(command, "save_delete_user_number", user_number)
    command._command_run_profile = config
    command._command_failure_recovery_attempts = 0
    return assignments


def _install_end_hook(command, end):
    """Stop immediately after a state/Step handler completes successfully.

    Polling remains useful for progress display, but can miss a short Step.
    Wrapping the selected handler makes the end boundary inclusive without
    changing the Commands source file.
    """
    if not isinstance(end, dict) or not end:
        return False
    target = None
    replace = None
    kind = str(end.get("kind", ""))
    if end.get("mode") == "state":
        table = getattr(command, str(end.get("variable", "")), None)
        value = end.get("value")
        if isinstance(table, dict) and callable(table.get(value)):
            target = table[value]
            replace = lambda wrapper: table.__setitem__(value, wrapper)
    elif kind == "step":
        try:
            method_name = "_step_{}".format(int(end.get("value")))
        except (TypeError, ValueError):
            method_name = ""
        candidate = getattr(command, method_name, None) if method_name else None
        if callable(candidate):
            target = candidate
            replace = lambda wrapper: setattr(command, method_name, wrapper)
    if target is None or replace is None:
        return False

    def stop_after_selected_handler(*args, **kwargs):
        result = target(*args, **kwargs)
        command.sendStopRequest()
        return result

    stop_after_selected_handler.__name__ = getattr(
        target, "__name__", "command_end_location")
    stop_after_selected_handler.__doc__ = getattr(target, "__doc__", None)
    replace(stop_after_selected_handler)
    command._command_end_hook_installed = True
    return True


def apply_profile_to_dialogue_result(command, dialogue_list, result):
    """Reflect numbered start/end/debug selections into a legacy dialog result."""
    profile = getattr(command, "_command_run_profile", None)
    if not isinstance(profile, dict) or not isinstance(result, list):
        return result
    updated = list(result)
    for kind in ("start", "end"):
        location = profile.get(kind) or {}
        if not location or location.get("mode") != "attribute":
            continue
        index = location.get(
            "dialog_start_index" if kind == "start" else "dialog_end_index")
        if isinstance(index, int) and 0 <= index < len(updated):
            updated[index] = location.get("dialog_value", location.get("value"))
    debug = profile.get("debug") or {}
    for index, row in enumerate(dialogue_list or []):
        if index >= len(updated) or not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        label = str(row[1]).strip()
        for attribute, enabled in debug.items():
            if label.casefold() == str(attribute).casefold():
                updated[index] = bool(enabled)
    return updated


def perform_failure_save_recovery(command, error):
    """Delete save through an explicit Commands hook and allow one retry."""
    profile = getattr(command, "_command_run_profile", None)
    if not isinstance(profile, dict) or not profile.get("retry_on_failure"):
        return False
    attempts = int(getattr(command, "_command_failure_recovery_attempts", 0) or 0)
    max_retries = max(1, int(profile.get("max_retries", 1) or 1))
    if attempts >= max_retries:
        return False
    method_name = str(profile.get("recovery_method", ""))
    method = getattr(command, method_name, None) if method_name else None
    if not callable(method):
        print("[SAVE RECOVERY] セーブ削除関数がないため再実行しません。")
        return False
    user_number = max(0, int(profile.get("save_delete_user_number", 0) or 0))
    command._command_failure_recovery_attempts = attempts + 1
    print("[SAVE RECOVERY] 失敗を検出。ユーザー{}のセーブ削除後に再実行します ({}/{})".format(
        user_number, attempts + 1, max_retries))
    try:
        parameters = inspect.signature(method).parameters
        if parameters:
            method(user_number)
        else:
            method()
        prepare = getattr(command, "prepare_command_retry", None)
        if callable(prepare):
            prepare(error, attempts + 1)
    except Exception as recovery_error:
        print("[SAVE RECOVERY] セーブ削除／再試行準備に失敗: {}".format(
            recovery_error))
        return False
    return True
