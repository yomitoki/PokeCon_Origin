"""Apply a configured command start state through existing init variables."""

from __future__ import annotations

import inspect

from AutomationTriggers import resolve_command_value


def _method_source(function):
    try:
        return inspect.getsource(function)
    except (OSError, TypeError):
        return ""


def _find_parent_state(command, child_variable, child_current):
    """Return (mapping name, mapping key, current attribute) for a child loop."""
    for variable, mapping in vars(command).items():
        if variable == child_variable or not isinstance(mapping, dict):
            continue
        if not (str(variable).startswith("STATE_") and str(variable).endswith("_FUNCTION")):
            continue
        found, _value, current = resolve_command_value(command, variable)
        if not found or not current:
            continue
        for state, function in mapping.items():
            if not callable(function):
                continue
            source = _method_source(function)
            if child_variable in source and (not child_current or child_current in source):
                return str(variable), str(state), str(current)
    return None


def apply_command_start_override(command, variable, state):
    """Set one state and any parent init state; return applied assignments.

    Existing ``*_current_state_init`` attributes are preferred. Commands that
    do not provide an init attribute fall back to changing the fresh command
    instance's current-state attribute only; source files are never edited.
    """
    if command is None:
        raise ValueError("Commandsが生成されていません。")
    variable = str(variable or "").strip()
    state = str(state or "").strip()
    mapping = getattr(command, variable, None)
    if not isinstance(mapping, dict):
        raise ValueError("状態変数「{}」がCommandsにありません。".format(variable))
    if state not in mapping:
        raise ValueError("Step「{}」が{}にありません。".format(state, variable))

    found, _value, current = resolve_command_value(command, variable)
    if not found or not current:
        raise ValueError("{}の現在Step変数を特定できません。".format(variable))

    assignments = []
    visited = set()
    current_variable, current_state, current_attr = variable, state, current
    while current_variable not in visited:
        visited.add(current_variable)
        init_attr = current_attr + "_init"
        target_attr = init_attr if hasattr(command, init_attr) else current_attr
        setattr(command, target_attr, current_state)
        assignments.append({
            "variable": current_variable,
            "attribute": target_attr,
            "value": current_state,
            "uses_init": target_attr == init_attr,
        })
        parent = _find_parent_state(command, current_variable, current_attr)
        if parent is None:
            break
        current_variable, current_state, current_attr = parent
    return assignments
