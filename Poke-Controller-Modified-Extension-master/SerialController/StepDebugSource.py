#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-side helpers for saved Step-debug operation replacements."""
from __future__ import print_function

import ast
import copy
import hashlib
import inspect
import os
import re
import textwrap


def _node_end_line(node):
    end = getattr(node, "end_lineno", None)
    if end is not None:
        return int(end)
    return max(
        [int(getattr(item, "end_lineno", 0) or getattr(item, "lineno", 0) or 0)
         for item in ast.walk(node)] or [int(getattr(node, "lineno", 1))]
    )


def _segment(lines, node):
    start = max(0, int(getattr(node, "lineno", 1)) - 1)
    end = max(start + 1, _node_end_line(node))
    return textwrap.dedent("".join(lines[start:end])).strip()


def _literal_string(node):
    """Return a string AST literal across Python 3.7 through 3.14."""
    constant_type = getattr(ast, "Constant", ())
    if isinstance(node, constant_type) and isinstance(getattr(node, "value", None), str):
        return node.value
    legacy_type = getattr(ast, "Str", ())
    if isinstance(node, legacy_type) and isinstance(getattr(node, "s", None), str):
        return node.s
    return None


def _mapping_method(mapping, state):
    if not isinstance(mapping, ast.Dict):
        return ""
    for key, value in zip(mapping.keys, mapping.values):
        if _literal_string(key) != state:
            continue
        if isinstance(value, ast.Attribute):
            return value.attr
        if isinstance(value, ast.Name):
            return value.id
    return ""


def _target_name(target):
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return ""


def state_method_map(source, variable):
    """Return state value -> method for one dispatch dictionary."""
    tree = ast.parse(source)
    result = {}

    def add_mapping(mapping):
        if not isinstance(mapping, ast.Dict):
            return
        for key, value in zip(mapping.keys, mapping.values):
            state = _literal_string(key)
            if state is None:
                continue
            if isinstance(value, ast.Attribute):
                result[state] = value.attr
            elif isinstance(value, ast.Name):
                result[state] = value.id

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(_target_name(target) == variable for target in node.targets):
                add_mapping(node.value)
        elif isinstance(node, ast.AnnAssign) and _target_name(node.target) == variable:
            add_mapping(node.value)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr == "update" and node.args
              and _target_name(node.func.value) == variable):
            add_mapping(node.args[0])
    return result


def split_mixed_step_rule(rule, source, new_id):
    """Split legacy continuous-debug data whose operations span several methods."""
    original = copy.deepcopy(dict(rule or {}))
    replacements = original.get("replacements", {})
    if not isinstance(replacements, dict) or not replacements:
        return [original], False
    variable = str(original.get("variable", ""))
    original_state = str(original.get("state", ""))
    mappings = state_method_map(source, variable)
    if original_state not in mappings:
        return [original], False

    tree = ast.parse(source)
    ranges = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ranges[node.name] = (int(node.lineno), _node_end_line(node))
    method_states = {}
    for state, method in mappings.items():
        method_states.setdefault(method, []).append(state)

    grouped = {}
    for operation_id, replacement in replacements.items():
        try:
            line = int(replacement.get("line", 0))
        except (TypeError, ValueError):
            line = 0
        method = next((name for name, (start, end) in ranges.items()
                       if line and start <= line <= end), "")
        candidates = method_states.get(method, [])
        state = (original_state if original_state in candidates else
                 candidates[0] if candidates else original_state)
        grouped.setdefault(state, {})[operation_id] = copy.deepcopy(replacement)

    expected_method = mappings[original_state]
    saved_method = str(original.get("source", {}).get("method", ""))
    changed = len(grouped) > 1 or (saved_method and saved_method != expected_method)
    if not changed:
        return [original], False

    ordered_states = [original_state] + sorted(
        (state for state in grouped if state != original_state),
        key=lambda state: min(
            [int(item.get("line", 0) or 0) for item in grouped[state].values()] or [0]))
    split = []
    for index, state in enumerate(ordered_states):
        state_replacements = grouped.get(state, {})
        if not state_replacements and state != original_state:
            continue
        item = copy.deepcopy(original)
        item["state"] = state
        item["replacements"] = state_replacements
        item["source"] = dict(item.get("source", {}))
        item["source"]["method"] = mappings.get(state, item["source"].get("method", ""))
        if state != original_state:
            item["id"] = str(new_id(state, index))
            item["follow_origin_id"] = str(original.get("id", ""))
        split.append(item)
    return split, True


def resolve_state_method_name(source, variable, state, preferred=""):
    """Resolve a state-table value to its command-class method name."""
    tree = ast.parse(source)
    method_names = {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in ast.walk(tree):
        mapping = None
        target_name = ""
        if isinstance(node, ast.Assign):
            target_name = next((_target_name(target) for target in node.targets
                                if _target_name(target)), "")
            mapping = node.value
        elif isinstance(node, ast.AnnAssign):
            target_name = _target_name(node.target)
            mapping = node.value
        if target_name == variable:
            method = _mapping_method(mapping, state)
            if method:
                return method
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "update" and node.args):
            owner = node.func.value
            if isinstance(owner, ast.Attribute) and owner.attr == variable:
                method = _mapping_method(node.args[0], state)
                if method:
                    return method
    # The state dictionary is authoritative. ``preferred`` exists only for
    # legacy sources whose state table cannot be parsed; accepting it first
    # can apply a shared/mixed draft to the wrong function.
    if preferred and preferred in method_names:
        return preferred
    guessed = "_" + re.sub(r"\W+", "_", str(state)).strip("_").lower()
    if guessed in method_names:
        return guessed
    raise ValueError("Step「{}」に対応する関数をソースから特定できません。".format(state))


def extract_named_method_info(source, method_name):
    """Return operation records compatible with StepDebugAssist IDs."""
    tree = ast.parse(source)
    function = None
    for class_node in [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]:
        function = next((node for node in class_node.body
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and node.name == method_name), None)
        if function is not None:
            break
    if function is None:
        function = next((node for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and node.name == method_name), None)
    if function is None:
        raise ValueError("関数「{}」がソースにありません。".format(method_name))
    lines = source.splitlines(True)
    operations, next_states, duplicate_ids = [], [], {}

    def add_operation(node, contexts):
        code = _segment(lines, node)
        if not code:
            return
        digest = hashlib.sha1(" ".join(code.split()).encode("utf-8")).hexdigest()[:12]
        duplicate_ids[digest] = duplicate_ids.get(digest, 0) + 1
        operation_id = "{}-{}".format(digest, duplicate_ids[digest])
        first = code.splitlines()[0].strip()
        if len(first) > 92:
            first = first[:89] + "..."
        operations.append({
            "id": operation_id,
            "line": int(getattr(node, "lineno", 1)),
            "end_line": _node_end_line(node),
            "code": code,
            "summary": first,
            "context": " / ".join(contexts),
        })

    def condition_text(node):
        return (_segment(lines, node).splitlines()[0] if lines else "").rstrip(":").strip()

    def visit(statements, contexts=()):
        for node in statements:
            if isinstance(node, ast.Return):
                value = _literal_string(node.value)
                if value is not None:
                    next_states.append(value)
                continue
            if isinstance(node, ast.If):
                condition = condition_text(node.test)
                count = len(operations)
                visit(node.body, contexts + (("IF " + condition),))
                if node.orelse:
                    visit(node.orelse, contexts + (("ELSE " + condition),))
                if len(operations) == count:
                    add_operation(node, contexts)
                continue
            if isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.Try,
                                 ast.With, ast.AsyncWith)):
                add_operation(node, contexts)
                continue
            if isinstance(node, (ast.Pass, ast.Import, ast.ImportFrom,
                                 ast.Global, ast.Nonlocal)):
                continue
            if (isinstance(node, ast.Expr)
                    and _literal_string(getattr(node, "value", None)) is not None):
                continue
            add_operation(node, contexts)

    visit(function.body)
    return {
        "name": method_name,
        "line": function.lineno,
        "end_line": _node_end_line(function),
        "operations": operations,
        "next_states": list(dict.fromkeys(next_states)),
    }


def extract_state_method_info(source, variable, state, preferred=""):
    method_name = resolve_state_method_name(source, variable, state, preferred=preferred)
    return extract_named_method_info(source, method_name)


def apply_operation_replacements(source, info, replacement_codes):
    """Apply operation-id -> code replacements and return validated source."""
    lines = source.splitlines(True)
    operations = {item["id"]: item for item in info.get("operations", [])}
    edits = []
    for operation_id, code in replacement_codes.items():
        operation = operations.get(operation_id)
        if operation is None:
            raise ValueError("置換元の処理が現在のソースにありません: " + str(operation_id))
        value = textwrap.dedent(str(code or "")).strip()
        if not value:
            raise ValueError("反映する置換コードが空です。")
        start = int(operation["line"]) - 1
        end = int(operation["end_line"])
        original_line = lines[start] if 0 <= start < len(lines) else ""
        indentation = original_line[:len(original_line) - len(original_line.lstrip(" \t"))]
        block = "\n".join(indentation + line if line else ""
                          for line in value.splitlines()) + "\n"
        edits.append((start, end, block))
    for start, end, block in sorted(edits, reverse=True):
        lines[start:end] = [block]
    updated = "".join(lines)
    ast.parse(updated)
    return updated


def build_runtime_replacement_function(method, replacement_codes):
    """Compile a whole state method with operation replacements in memory.

    The returned function is unbound.  Callers bind it to the fresh Commands
    instance and place it in the state dispatch dictionary.  No source file is
    written, so this is suitable for a production-speed trial before applying
    the reviewed diff.
    """
    function = getattr(method, "__func__", method)
    method_name = getattr(function, "__name__", "")
    if not method_name:
        raise ValueError("置換する関数名を取得できません。")
    try:
        source = textwrap.dedent(inspect.getsource(function))
    except (OSError, TypeError) as error:
        raise ValueError("置換する関数のソースを取得できません: {}".format(error))
    info = extract_named_method_info(source, method_name)
    updated = apply_operation_replacements(source, info, replacement_codes)
    namespace = dict(getattr(function, "__globals__", {}))
    exec(compile(updated, "<runtime-function-replacement>", "exec"), namespace, namespace)
    replacement = namespace.get(method_name)
    if not callable(replacement):
        raise ValueError("置換後の関数を生成できませんでした: " + method_name)
    return replacement


def find_sample_function_files(fragment_root, method_name):
    """Return .pyfrag files containing the selected method."""
    found = []
    if not os.path.isdir(fragment_root):
        return found
    for directory, _, filenames in os.walk(fragment_root):
        for filename in sorted(filenames):
            if not filename.endswith(".pyfrag"):
                continue
            path = os.path.join(directory, filename)
            try:
                with open(path, "r", encoding="utf-8") as stream:
                    source = stream.read()
                extract_named_method_info(source, method_name)
            except (OSError, SyntaxError, ValueError):
                continue
            found.append(path)
    return found
