"""Low-cost command-variable trigger evaluation shared by recording and recovery.

The evaluator stores only small scalar snapshots and is intended to run at
4-10 Hz.  It never touches Tk, camera frames, or image matching.
"""
from __future__ import annotations

import ast
import re
import time


def discover_state_values(source, variable_name):
    """Extract selectable state-table keys from Python source text."""
    target = str(variable_name or "").strip().upper()
    wanted_names = {target}
    if target in ("STEP", "CURRENT_STEP"):
        wanted_names.update(("STEP_LABELS", "STEPS"))
    found = set()
    tree = ast.parse(str(source))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        assigned = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = set()
        for item in assigned:
            if isinstance(item, ast.Name):
                names.add(item.id.upper())
            elif isinstance(item, ast.Attribute):
                names.add(item.attr.upper())
        if names.intersection(wanted_names) and isinstance(node.value, ast.Dict):
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    found.add(key.value)
    if not found:
        story = re.fullmatch(r"STATE_(\d+)_STORY_FUNCTION", target)
        prefix = story.group(1) + "_STORY_" if story else ""
        for match in re.finditer(r"['\"]([A-Z0-9_]{4,})['\"]", str(source)):
            value = match.group(1)
            if (not prefix or value.startswith(prefix)) and ("STORY" in value or "STEP" in value):
                found.add(value)
    return sorted(found, key=str.casefold)


def resolve_command_value(command, requested_name):
    """Return ``(found, value, actual_attribute)`` with common state aliases."""
    if command is None:
        return False, None, ""
    name = str(requested_name or "").strip()
    candidates = [name]
    upper = name.upper()
    if upper == "STATE_MAIN_FUNCTION":
        candidates.extend(("main_current_state", "za_infi_main_current_state"))
    story = re.fullmatch(r"STATE_(\d+)_STORY_FUNCTION", upper)
    if story:
        candidates.append("_{}_story_current_state".format(story.group(1)))
    common = re.fullmatch(r"STATE_COMMON_(.+)_FUNCTION", upper)
    if common:
        candidates.append("common_{}_current_state".format(common.group(1).lower()))
    if upper in ("STEP", "CURRENT_STEP"):
        candidates.extend(("current_step", "step", "step_name"))
    for candidate in candidates:
        if candidate and hasattr(command, candidate):
            try:
                return True, getattr(command, candidate), candidate
            except Exception:
                return False, None, candidate
    return False, None, name


def command_scope_matches(rule, command_name):
    scope = str(rule.get("command", "") or "").strip()
    return not scope or scope in ("すべて", "All commands", "*") or scope == str(command_name or "")


class StableRuleEvaluator:
    def __init__(self):
        self.states = {}

    def reset(self):
        self.states.clear()

    def clear_rule(self, rule_id):
        self.states.pop(str(rule_id), None)

    def evaluate(self, rule, command, command_name="", now=None):
        """Return a compact result dict for one value-stable/unchanged rule."""
        now = time.monotonic() if now is None else float(now)
        rule_id = str(rule.get("id", id(rule)))
        state = self.states.setdefault(rule_id, {})
        if not command_scope_matches(rule, command_name):
            state.clear()
            return {"triggered": False, "found": False, "value": None, "elapsed": 0.0}
        found, value, actual_name = resolve_command_value(command, rule.get("variable", ""))
        if not found:
            state.clear()
            return {"triggered": False, "found": False, "value": None,
                    "actual_name": actual_name, "elapsed": 0.0}
        value_text = str(value)
        seconds = max(0.0, float(rule.get("seconds", 0.0) or 0.0))
        kind = rule.get("kind", "value_stable")
        if kind == "unchanged":
            if state.get("value") != value_text:
                state["value"] = value_text
                state["since"] = now
            elapsed = max(0.0, now - state.get("since", now))
            triggered = elapsed >= seconds
        else:
            expected = str(rule.get("value", ""))
            if value_text != expected:
                state.clear()
                elapsed, triggered = 0.0, False
            else:
                state.setdefault("since", now)
                state["value"] = value_text
                elapsed = max(0.0, now - state["since"])
                triggered = elapsed >= seconds
        return {"triggered": triggered, "found": True, "value": value,
                "actual_name": actual_name, "elapsed": elapsed}

    def evaluate_any(self, rules, command, command_name="", now=None):
        results = []
        for rule in rules:
            result = self.evaluate(rule, command, command_name, now=now)
            results.append((rule, result))
            if result["triggered"]:
                return rule, result, results
        return None, None, results
