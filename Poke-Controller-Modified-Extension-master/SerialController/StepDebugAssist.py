#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safe helpers for the interactive state-function debugger.

The production command source is never edited here.  A state method is read,
split into user-selectable operations, and individual snippets are executed
against the already initialized command instance.
"""
from __future__ import print_function

import ast
import hashlib
import inspect
import textwrap
import builtins


def _segment(source_lines, node):
    start = max(0, int(getattr(node, "lineno", 1)) - 1)
    end = int(getattr(node, "end_lineno", start + 1) or (start + 1))
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
                if isinstance(node.value, ast.Str):
                    next_states.append(node.value.s)
                elif isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    next_states.append(node.value.value)
                continue
            if isinstance(node, ast.If):
                condition = _condition_text(lines, node.test)
                visit(node.body, contexts + (("IF " + condition),))
                if node.orelse:
                    visit(node.orelse, contexts + (("ELSE " + condition),))
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
                    and isinstance(getattr(node, "value", None), (ast.Str, ast.Constant))
                    and isinstance(getattr(node.value, "s", getattr(node.value, "value", None)), str)):
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
