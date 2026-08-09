#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safe helpers for the interactive state-function debugger.

The production command source is never edited here.  A state method is read,
split into user-selectable operations, and individual snippets are executed
against the already initialized command instance.
"""
from __future__ import print_function

import ast
import copy
import hashlib
import inspect
import textwrap
import builtins


DELETE_OPERATION_CODE = "pass  # PokeCon Stepデバッグ: 処理削除"


def _literal_string(node):
    """Return a string AST literal across Python 3.7 through 3.14."""
    constant_type = getattr(ast, "Constant", ())
    if isinstance(node, constant_type) and isinstance(getattr(node, "value", None), str):
        return node.value
    legacy_type = getattr(ast, "Str", ())
    if isinstance(node, legacy_type) and isinstance(getattr(node, "s", None), str):
        return node.s
    return None


def recommended_next_state(current_state, return_candidates, mapping_states):
    """Choose the forward Step without hiding legitimate loop/backtrack choices.

    When source analysis cannot find a literal ``return``, the UI falls back to
    all keys in the state mapping.  Picking the first different key in that list
    sends execution to an old Step.  Prefer the key immediately following the
    current Step, then fall back to the first explicit non-current return.
    """
    current = str(current_state or "")
    candidates = list(dict.fromkeys(
        str(value) for value in (return_candidates or []) if str(value)))
    states = list(dict.fromkeys(
        str(value) for value in (mapping_states or []) if str(value)))

    try:
        following = states[states.index(current) + 1]
    except (ValueError, IndexError):
        following = ""

    # A literal return list is authoritative.  Use the declared next mapping
    # only when that function can actually return it.
    if following and (not candidates or following in candidates):
        return following
    return next((value for value in candidates if value != current),
                current if current in candidates else (candidates[0] if candidates else ""))


def replacement_is_enabled(replacement):
    """Return whether a saved draft replacement should be used for a trial."""
    return bool(replacement) and bool(replacement.get("enabled", True))


def derive_follow_step_rule(template, command_name, variable, state, rule_id):
    """Create an independent saved rule when continuous debug enters a new Step."""
    derived = copy.deepcopy(dict(template or {}))
    derived.update({
        "id": str(rule_id),
        "enabled": True,
        "command": str(command_name or template.get("command", "")),
        "variable": str(variable),
        "state": str(state),
        "replacements": {},
        "source": {},
        "follow_origin_id": str(template.get("id", "")),
    })
    return derived


def _segment(source_lines, node):
    start = max(0, int(getattr(node, "lineno", 1)) - 1)
    end = getattr(node, "end_lineno", None)
    if end is None:
        # Python versions before AST end-position support only expose the
        # starting line.  Recover the final line from descendant nodes so a
        # compound statement is not truncated to just ``if ...:``.
        end = max(
            [int(getattr(item, "end_lineno", 0) or getattr(item, "lineno", 0) or 0)
             for item in ast.walk(node)]
            or [start + 1]
        )
    end = max(start + 1, int(end))
    return textwrap.dedent("".join(source_lines[start:end])).strip()


def _condition_text(source_lines, node):
    value = _segment(source_lines, node).splitlines()[0] if source_lines else ""
    return value.rstrip(":").strip()


def extract_step_method(method):
    """Return source operations and literal next-state candidates for a method."""
    source, first_line = inspect.getsourcelines(method)
    dedented = textwrap.dedent("".join(source))
    tree = ast.parse(dedented)
    function = next((node for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
    if function is None:
        raise ValueError("関数の処理を取得できません。")
    lines = dedented.splitlines(True)
    operations = []
    next_states = []
    duplicate_ids = {}

    def add_operation(node, contexts):
        code = _segment(lines, node)
        if not code:
            return
        normalized = " ".join(code.split())
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
        duplicate_ids[digest] = duplicate_ids.get(digest, 0) + 1
        operation_id = "{}-{}".format(digest, duplicate_ids[digest])
        relative_line = int(getattr(node, "lineno", 1))
        absolute_line = first_line + relative_line - 1
        first = code.splitlines()[0].strip()
        if len(first) > 92:
            first = first[:89] + "..."
        loaded_names = {item.id for item in ast.walk(node)
                        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
                        and item.id not in ("self", "True", "False", "None")}
        known_names = set(getattr(method, "__globals__", {})) | set(dir(builtins))
        local_names = sorted(loaded_names - known_names)
        operations.append({
            "id": operation_id,
            "line": absolute_line,
            "code": code,
            "summary": first,
            "context": " / ".join(contexts),
            "uses_names": local_names,
        })

    def visit(statements, contexts=()):
        for node in statements:
            if isinstance(node, ast.Return):
                returned_state = _literal_string(node.value)
                if returned_state is not None:
                    next_states.append(returned_state)
                continue
            if isinstance(node, ast.If):
                condition = _condition_text(lines, node.test)
                operation_count = len(operations)
                visit(node.body, contexts + (("IF " + condition),))
                if node.orelse:
                    visit(node.orelse, contexts + (("ELSE " + condition),))
                # A state function may consist only of a condition and return
                # statements (for example, an image/marker check that selects
                # the next state).  Return nodes are intentionally not listed
                # as controller actions, but hiding the whole condition leaves
                # the Step debug table blank.  Keep that condition as one
                # executable operation when it produced no child operations.
                if len(operations) == operation_count:
                    add_operation(node, contexts)
                continue
            # Keep loops/try/with blocks intact.  Flattening these would change
            # their repetition, exception, or resource-management semantics.
            if isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.Try,
                                 ast.With, ast.AsyncWith)):
                add_operation(node, contexts)
                continue
            if isinstance(node, (ast.Pass, ast.Import, ast.ImportFrom,
                                 ast.Global, ast.Nonlocal)):
                continue
            # A function docstring is explanatory text, not an action.
            if (isinstance(node, ast.Expr)
                    and _literal_string(getattr(node, "value", None)) is not None):
                continue
            add_operation(node, contexts)

    visit(function.body)
    return {
        "name": getattr(method, "__name__", function.name),
        "file": inspect.getsourcefile(method) or "",
        "first_line": first_line,
        "operations": operations,
        "next_states": list(dict.fromkeys(next_states)),
        "source": dedented,
    }


def validate_operation_code(code):
    value = textwrap.dedent(str(code or "")).strip()
    if not value:
        raise ValueError("実行する処理が空です。")
    wrapped = "def __step_debug_validate(self):\n" + textwrap.indent(value, "    ") + "\n"
    compile(wrapped, "<step-debug-replacement>", "exec")
    return value


def execute_operation(command, method, code):
    """Execute one operation without changing the command source file."""
    value = validate_operation_code(code)
    namespace = dict(getattr(method, "__globals__", {}))
    wrapped = "def __step_debug_operation(self):\n" + textwrap.indent(value, "    ") + "\n"
    exec(compile(wrapped, "<step-debug-operation>", "exec"), namespace, namespace)
    return namespace["__step_debug_operation"](command)
