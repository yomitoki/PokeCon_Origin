#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structured Step/source comparison helpers for PokeConStudio.

This module deliberately has no Tk or PokeCon runtime dependency.  It reads
Commands source with :mod:`ast`, exposes an ordered outline of controller
operations, variables, image checks, calls, and returns, and provides narrow
copy-on-write helpers for ``STATE_*_FUNCTION`` entries and one selected
function body.

The dictionary editor changes only the selected literal.  The function-body
helper keeps the existing function name, signature, decorators, STATE tables,
and all other source text.  Both paths validate a source hash so an old
comparison can never overwrite newer editor changes.
"""
from __future__ import print_function

import ast
import copy
import difflib
import hashlib
import importlib
import io
import json
import keyword
import os
import re
import sys
import tokenize

try:
    from PokeConStudio.StudioCore import (DEFAULT_OPERATION_PATTERNS,
                                         _local_top_level_base,
                                         _pokecon_command_class,
                                         _top_level_name_binding)
except ImportError:  # direct ``python PokeConStudio/PokeConStudio.py`` launch
    from StudioCore import (DEFAULT_OPERATION_PATTERNS,
                            _local_top_level_base,
                            _pokecon_command_class,
                            _top_level_name_binding)


OUTLINE_SCHEMA_VERSION = 1
STATE_TABLE_PATTERN = re.compile(r"^STATE_[A-Za-z0-9_]*_FUNCTION$")
IMAGE_CALL_NAMES = frozenset((
    "image_check", "_image_check_target", "detect_image",
    "image_check_confirmation",
))
_SOURCE_VIEW_CACHE = []


def _source_hash(source):
    return hashlib.sha256(str(source).encode("utf-8")).hexdigest()


def _literal_string(node):
    constant = getattr(ast, "Constant", None)
    if constant is not None and isinstance(node, constant):
        return node.value if isinstance(node.value, str) else None
    string = getattr(ast, "Str", None)
    if string is not None and isinstance(node, string):
        return node.s
    return None


def _qualified_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return (prefix + "." if prefix else "") + node.attr
    return ""


def _target_name(node):
    if isinstance(node, (ast.Name, ast.Attribute)):
        return _qualified_name(node)
    if isinstance(node, (ast.Tuple, ast.List)):
        result = []
        for item in node.elts:
            value = _target_name(item)
            if value:
                result.extend(value if isinstance(value, list) else [value])
        return result
    return ""


def _line_char_column(line, byte_column):
    """Translate AST's UTF-8 byte offset to a Python string column."""
    raw = line.encode("utf-8")[:max(0, int(byte_column or 0))]
    return len(raw.decode("utf-8", errors="ignore"))


def _source_view(source):
    """Return cached physical lines/offsets for one immutable source string."""
    for index, cached in enumerate(_SOURCE_VIEW_CACHE):
        if cached[0] is source:
            if index:
                _SOURCE_VIEW_CACHE.insert(0, _SOURCE_VIEW_CACHE.pop(index))
            return cached[1], cached[2]
    lines = source.splitlines(True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    _SOURCE_VIEW_CACHE.insert(0, (source, lines, offsets))
    del _SOURCE_VIEW_CACHE[3:]
    return lines, offsets


def _line_offsets(source):
    return _source_view(source)[1]


def _absolute_offset(source, line, column):
    offsets = _line_offsets(source)
    line = max(1, min(int(line), len(offsets)))
    return offsets[line - 1] + int(column)


def _node_end_line(node):
    value = int(getattr(node, "end_lineno", 0) or 0)
    if value:
        return value
    return max([int(getattr(item, "lineno", 0) or 0)
                for item in ast.walk(node)] or
               [int(getattr(node, "lineno", 1) or 1)])


def _source_segment(source, node):
    lines_with_ends, offsets = _source_view(source)
    start = int(getattr(node, "lineno", 1) or 1)
    end = _node_end_line(node)
    end_column = getattr(node, "end_col_offset", None)
    if (end_column is not None and 0 < start <= len(lines_with_ends)
            and 0 < end <= len(lines_with_ends)):
        start_line = lines_with_ends[start - 1].rstrip("\r\n")
        end_line = lines_with_ends[end - 1].rstrip("\r\n")
        begin = _line_char_column(
            start_line, getattr(node, "col_offset", 0))
        finish = _line_char_column(end_line, end_column)
        begin_offset = offsets[start - 1] + begin
        finish_offset = offsets[end - 1] + finish
        return source[begin_offset:finish_offset]
    return "\n".join(
        line.rstrip("\r\n") for line in lines_with_ends[start - 1:end])


def _expression_source(source, node):
    value = _source_segment(source, node).strip()
    if value:
        return value
    name = _qualified_name(node)
    return name or "..."


def _container_target_name(node):
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _iter_nodes_without_nested_definitions(node):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef, ast.Lambda)):
            continue
        yield child
        for descendant in _iter_nodes_without_nested_definitions(child):
            yield descendant


def _iter_statements(statements, depth=0):
    """Yield statements in lexical order with a useful visual depth."""
    for statement in statements or ():
        yield statement, depth
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
            continue
        children = []
        for field_name in ("body", "orelse", "finalbody"):
            child = getattr(statement, field_name, None)
            if isinstance(child, list):
                children.extend(child)
        if isinstance(statement, ast.Try):
            for handler in statement.handlers:
                children.extend(handler.body)
        # AST fields above may not be stored in strictly lexical order (for
        # example try/except/finally), so sort by their real source positions.
        children.sort(key=lambda item: (
            int(getattr(item, "lineno", 0) or 0),
            int(getattr(item, "col_offset", 0) or 0)))
        for child, child_depth in _iter_statements(children, depth + 1):
            yield child, child_depth


def _call_root(statement):
    """Select the expression owned by a statement, excluding child suites."""
    if isinstance(statement, (ast.If, ast.While)):
        return statement.test
    if isinstance(statement, (ast.For, ast.AsyncFor)):
        return statement.iter
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        return ast.Tuple(
            elts=[item.context_expr for item in statement.items],
            ctx=ast.Load())
    return statement


def _call_records(statement):
    result = []
    root = _call_root(statement)
    nodes = [root]
    nodes.extend(_iter_nodes_without_nested_definitions(root))
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        qualified = _qualified_name(node.func)
        tail = qualified.rsplit(".", 1)[-1]
        image_target = ""
        if tail.lower() in IMAGE_CALL_NAMES or "image_check" in tail.lower():
            if node.args:
                image_target = _literal_string(node.args[0]) or ""
            if not image_target:
                for keyword_value in node.keywords:
                    if keyword_value.arg in ("target", "picture", "name"):
                        image_target = _literal_string(keyword_value.value) or ""
                        if image_target:
                            break
        result.append({
            "name": qualified or tail,
            "tail": tail,
            "image_target": image_target,
            "line": int(getattr(node, "lineno", 0) or 0),
        })
    return sorted(result, key=lambda item: item["line"])


def _variable_names(statement):
    targets = []
    if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        nodes = (statement.targets if isinstance(statement, ast.Assign)
                 else [statement.target])
        for node in nodes:
            value = _target_name(node)
            targets.extend(value if isinstance(value, list) else [value])
    elif isinstance(statement, (ast.For, ast.AsyncFor)):
        value = _target_name(statement.target)
        targets.extend(value if isinstance(value, list) else [value])
    return [value for value in targets if value]


def _statement_source(source, statement):
    if isinstance(statement, ast.If):
        return "if " + _expression_source(source, statement.test)
    if isinstance(statement, ast.While):
        return "while " + _expression_source(source, statement.test)
    if isinstance(statement, (ast.For, ast.AsyncFor)):
        return "for {} in {}".format(
            _expression_source(source, statement.target),
            _expression_source(source, statement.iter))
    return _source_segment(source, statement).strip()


def _normalised_ast_signature(text):
    try:
        tree = ast.parse("def _outline(self):\n" + "\n".join(
            "    " + line for line in str(text or "").splitlines()))
        return ast.dump(tree, include_attributes=False)
    except (SyntaxError, ValueError, TypeError):
        return re.sub(r"\s+", " ", str(text or "")).strip()


def _statement_ast_signature(statement):
    """Stable statement identity without reparsing every source fragment."""
    try:
        return ast.dump(_call_root(statement), include_attributes=False)
    except (TypeError, ValueError):
        return _normalised_ast_signature("")


def _return_target(statement, source):
    if not isinstance(statement, ast.Return) or statement.value is None:
        return ""
    literal = _literal_string(statement.value)
    return literal if literal is not None else _expression_source(
        source, statement.value)


def _classify_statement(source, statement, depth, operation_regexes):
    calls = _call_records(statement)
    variables = _variable_names(statement)
    images = [item["image_target"] for item in calls
              if item.get("image_target")]
    image_calls = [item for item in calls
                   if (item["tail"].lower() in IMAGE_CALL_NAMES
                       or "image_check" in item["tail"].lower())]
    operation_calls = []
    for item in calls:
        if any(regex.search(item["tail"]) or regex.search(item["name"])
               for regex in operation_regexes):
            operation_calls.append(item)

    roles = []
    if variables:
        roles.append("variable")
    if operation_calls:
        roles.append("operation")
    if image_calls:
        roles.append("image_check")
    if calls:
        roles.append("call")
    if isinstance(statement, ast.Return):
        roles.append("return")

    if isinstance(statement, ast.Return):
        kind = "return"
    elif operation_calls:
        kind = "operation"
    elif image_calls:
        kind = "image_check"
    elif calls:
        kind = "call"
    elif variables:
        kind = "variable"
    else:
        return None

    text = _statement_source(source, statement)
    line = int(getattr(statement, "lineno", 1) or 1)
    end_line = _node_end_line(statement)
    call_names = [item["name"] for item in calls]
    display = text.splitlines()[0] if text else kind
    item = {
        "id": "{}:{}:{}".format(line, kind, int(depth)),
        "kind": kind,
        "roles": roles,
        "line": line,
        "end_line": end_line,
        "depth": int(depth),
        "source": text,
        "display": display,
        "calls": call_names,
        "operation_calls": [value["name"] for value in operation_calls],
        "image_targets": images,
        "variables": variables,
        "return_target": _return_target(statement, source),
    }
    if kind == "return" and item["return_target"]:
        item["signature"] = "return:" + str(item["return_target"])
    elif kind == "image_check" and images:
        item["signature"] = "image_check:" + "|".join(images)
    elif kind == "call" and call_names and not variables:
        item["signature"] = "call:" + "|".join(call_names)
    else:
        item["signature"] = kind + ":" + _statement_ast_signature(statement)
    return item


def _compile_operation_patterns(patterns):
    result = []
    for pattern in patterns or DEFAULT_OPERATION_PATTERNS:
        try:
            result.append(re.compile(str(pattern), re.IGNORECASE))
        except re.error:
            continue
    return result


def _function_outline(source, function, operation_regexes):
    items = []
    for statement, depth in _iter_statements(function.body):
        item = _classify_statement(
            source, statement, depth, operation_regexes)
        if item is not None:
            item["id"] = "{}:{}:{}:{}".format(
                function.name, item["line"], item["kind"], len(items))
            items.append(item)
    return {
        "name": function.name,
        "line": int(getattr(function, "lineno", 1) or 1),
        "end_line": _node_end_line(function),
        "items": items,
        "source": _source_segment(source, function),
    }


def _dict_token_span(source, dict_node):
    """Return character offsets and token locations of a literal dict."""
    source_lines = source.splitlines()
    ast_line = int(getattr(dict_node, "lineno", 1) or 1)
    ast_column = _line_char_column(
        source_lines[ast_line - 1] if ast_line <= len(source_lines) else "",
        getattr(dict_node, "col_offset", 0))
    end_line = int(getattr(dict_node, "end_lineno", 0) or 0)
    end_byte_column = getattr(dict_node, "end_col_offset", None)
    if (end_line and end_byte_column is not None
            and end_line <= len(source_lines)):
        end_column = _line_char_column(
            source_lines[end_line - 1], end_byte_column)
        return {
            "start": _absolute_offset(source, ast_line, ast_column),
            "end": _absolute_offset(source, end_line, end_column),
            "open_line": ast_line,
            "close_line": end_line,
            "open_column": ast_column,
            "close_column": max(0, end_column - 1),
        }
    start_position = (ast_line, ast_column)
    depth = 0
    started = False
    opening = closing = None
    reader = io.StringIO(source).readline
    for token in tokenize.generate_tokens(reader):
        if not started:
            if (token.type == tokenize.OP and token.string == "{"
                    and token.start >= start_position):
                started = True
                depth = 1
                opening = token
            continue
        if token.type != tokenize.OP:
            continue
        if token.string in "[{(":
            depth += 1
        elif token.string in "]})":
            depth -= 1
            if depth == 0:
                closing = token
                break
    if opening is None or closing is None:
        raise ValueError("STATE辞書の括弧範囲を特定できません。")
    return {
        "start": _absolute_offset(source, *opening.start),
        "end": _absolute_offset(source, *closing.end),
        "open_line": opening.start[0],
        "close_line": closing.start[0],
        "open_column": opening.start[1],
        "close_column": closing.start[1],
    }


def _table_target(assign):
    targets = assign.targets if isinstance(assign, ast.Assign) else [assign.target]
    return next((target for target in targets
                 if STATE_TABLE_PATTERN.match(_container_target_name(target))), None)


def _walk_assignments(node, class_name="", function_name=""):
    if isinstance(node, ast.ClassDef):
        class_name = node.name
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        function_name = node.name
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        yield node, class_name, function_name
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef) and class_name:
            continue
        for value in _walk_assignments(child, class_name, function_name):
            yield value


def _entry_method(value):
    qualified = _qualified_name(value)
    if not qualified:
        return ""
    return qualified.rsplit(".", 1)[-1]


def _entry_self_method(value):
    """Return a method only for the provable ``self.method`` form.

    The display/editor model keeps the tail name for other references so an
    existing STATE dictionary can be preserved verbatim.  Such references
    must never acquire a local function line, though: ``Other.step`` or a
    bare ``step`` does not prove that runtime calls ``self.step``.
    """
    if not isinstance(value, ast.Attribute):
        return ""
    owner = value.value
    if not isinstance(owner, ast.Name) or owner.id != "self":
        return ""
    return value.attr if str(value.attr or "").isidentifier() else ""


def _table_fingerprint(table):
    rows = [(entry.get("name", ""), entry.get("value_source", ""))
            for entry in table.get("entries", [])]
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_state_tables(source, tree, functions):
    tables = []
    occurrences = {}
    lines = source.splitlines(True)
    for assign, class_name, function_name in _walk_assignments(tree):
        target = _table_target(assign)
        value = getattr(assign, "value", None)
        if target is None or not isinstance(value, ast.Dict):
            continue
        name = _container_target_name(target)
        occurrence = occurrences.get((class_name, function_name, name), 0)
        occurrences[(class_name, function_name, name)] = occurrence + 1
        table_id = "{}:{}:{}:{}".format(
            class_name or "<module>", function_name or "<body>", name,
            occurrence)
        span = _dict_token_span(source, value)
        entries = []
        problems = []
        previous_line = span["open_line"]
        seen_names = set()
        for index, (key_node, value_node) in enumerate(zip(value.keys, value.values)):
            key = _literal_string(key_node)
            method = _entry_method(value_node)
            self_method = _entry_self_method(value_node)
            key_line = int(getattr(key_node, "lineno", 0) or 0)
            value_line = int(getattr(value_node, "lineno", 0) or 0)
            if key is None:
                problems.append("文字列でないStepキーがあります。")
                key = "<unsupported-{}>".format(index + 1)
            if key in seen_names:
                problems.append("Step名が重複しています: {}".format(key))
            seen_names.add(key)
            if not method:
                problems.append("{} の関数参照が単純名ではありません。".format(key))
            if key_line != value_line:
                problems.append("{} は複数行のため構成編集できません。".format(key))
            # Supported STATE values are plain Name/Attribute references.
            # Rebuild that reference from the AST instead of depending on
            # end_lineno/end_col_offset, which are absent on Python 3.7.
            value_source = _qualified_name(value_node) \
                or _expression_source(source, value_node)
            leading = lines[previous_line:key_line - 1] \
                if key_line > previous_line + 1 else []
            line_text = lines[key_line - 1].rstrip("\r\n") \
                if 0 < key_line <= len(lines) else ""
            trailing_comment = ""
            if "#" in line_text:
                trailing_comment = "#" + line_text.split("#", 1)[1]
            entry_id = hashlib.sha1(
                (table_id + "\0" + str(key)).encode("utf-8")).hexdigest()
            # Only ``self.method`` is a proven reference to the selected
            # command class.  Keep external/alias references visible and
            # structurally preservable, but never offer body replacement for
            # a same-named local method.
            function = functions.get(self_method, {}) if self_method else {}
            entries.append({
                "id": "state-" + entry_id,
                "name": str(key),
                "method": method,
                "self_method": self_method,
                "locked_method": method,
                "value_source": value_source,
                "line": key_line,
                "leading_lines": list(leading),
                "trailing_comment": trailing_comment,
                "function_line": int(function.get("line", 0) or 0),
                "function_end_line": int(function.get("end_line", 0) or 0),
                "items": copy.deepcopy(function.get("items", [])),
            })
            previous_line = key_line
        tail_lines = lines[previous_line:span["close_line"] - 1] \
            if span["close_line"] > previous_line + 1 else []
        assignment_line = int(getattr(assign, "lineno", 1) or 1)
        assignment_text = lines[assignment_line - 1] \
            if 0 < assignment_line <= len(lines) else ""
        base_indent = assignment_text[:len(assignment_text) -
                                      len(assignment_text.lstrip(" \t"))]
        table = {
            "id": table_id,
            "name": name,
            "class_name": class_name,
            "function_name": function_name,
            "occurrence": occurrence,
            "assignment_line": assignment_line,
            "dict_start": span["start"],
            "dict_end": span["end"],
            "base_indent": base_indent,
            "item_indent": base_indent + "    ",
            "tail_lines": list(tail_lines),
            "editable": not problems,
            "edit_problem": "\n".join(dict.fromkeys(problems)),
            "entries": entries,
        }
        table["fingerprint"] = _table_fingerprint(table)
        tables.append(table)
    return tables


def _external_base_symbol(tree, owner, base):
    """Return a stable opaque identity for one non-local base expression."""
    if isinstance(base, ast.Name):
        # Repeated uses of the same bare name share an identity only while its
        # module binding remains unchanged between class statements.
        return ("external-name", base.id,
                _top_level_name_binding(tree, owner, base.id))
    # Calls, subscriptions, and even qualified attributes can evaluate to a
    # different class on every occurrence.  Source text alone cannot prove
    # identity, so include the AST occurrence position instead of merging two
    # same-looking expressions into a fictitious common ancestor.
    return (
        "external-expression",
        int(getattr(base, "lineno", 0) or 0),
        int(getattr(base, "col_offset", 0) or 0),
        ast.dump(base, include_attributes=False),
    )


def _command_mro_symbols(tree, command_class):
    """Return a projected C3 MRO containing local and opaque base symbols.

    Importing a Commands module just to inspect inheritance would execute
    user code, so external bases remain deliberately opaque.  Keeping their
    position is nevertheless essential: in ``class Demo(External, Local)``,
    ``External`` may provide a method before ``Local`` and a local rewrite is
    therefore not provably safe.
    """
    if command_class is None:
        return []
    memo = {}
    visiting = set()

    def merge(sequences, class_name):
        sequences = [list(sequence) for sequence in sequences if sequence]
        result = []
        while sequences:
            candidate = None
            for sequence in sequences:
                head = sequence[0]
                if not any(head in other[1:] for other in sequences):
                    candidate = head
                    break
            if candidate is None:
                raise ValueError(
                    "ソース内クラス {} のMROを解決できません。".format(
                        class_name))
            result.append(candidate)
            next_sequences = []
            for sequence in sequences:
                if sequence and sequence[0] == candidate:
                    sequence.pop(0)
                if sequence:
                    next_sequences.append(sequence)
            sequences = next_sequences
        return result

    def linearize(node):
        if node in memo:
            return list(memo[node])
        if node in visiting:
            raise ValueError(
                "ソース内クラス {} の継承が循環しています。".format(
                    node.name))
        visiting.add(node)
        bases = []
        for base in node.bases:
            # A qualified expression such as ``external.Base`` cannot refer
            # to a top-level ``class Base`` in this source file.  A bare name
            # resolves only to the binding that existed before this class;
            # later same-named definitions cannot be its runtime base.
            local_base = _local_top_level_base(tree, node, base)
            bases.append(local_base if local_base is not None
                         else _external_base_symbol(tree, node, base))
        sequences = [
            linearize(base) if isinstance(base, ast.ClassDef) else [base]
            for base in bases
        ]
        sequences.append(list(bases))
        result = [node] + merge(sequences, node.name)
        visiting.remove(node)
        memo[node] = tuple(result)
        return list(result)

    return linearize(command_class)


def _resolved_function_nodes(mro_symbols):
    """Map methods whose effective local implementation is provable.

    Once an opaque external base appears in MRO order, it may implement any
    method declared by a later local base.  Those later declarations remain
    visible as source, but are intentionally ineligible for automatic body
    replacement.  A direct command override appears before every base and is
    therefore still safe.
    """
    result = {}
    blocked = set()
    external_seen = False
    for class_node in mro_symbols:
        if not isinstance(class_node, ast.ClassDef):
            external_seen = True
            continue
        for node in getattr(class_node, "body", ()):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name in result or node.name in blocked:
                continue
            if external_seen:
                blocked.add(node.name)
            else:
                result[node.name] = (class_node, node)
    return result


def _command_class_chain(tree, command_class):
    """Return local classes in reverse Python C3/MRO order.

    Callers build dictionaries by visiting this list from left to right, so
    the effective runtime implementation must be visited last.  A depth-first
    base walk happens to work for single inheritance, but gives the *right*
    base precedence for ``class Command(Left, Right)``.  Python lookup gives
    ``Left`` precedence.  Computing C3 first and then reversing its local
    portion preserves both that rule and diamond inheritance.

    External bases are retained while calculating the projected MRO, then
    removed only from this display/traversal view.  Their positions are used
    separately to decide whether an inherited local function is safe.
    """
    return list(reversed([
        item for item in _command_mro_symbols(tree, command_class)
        if isinstance(item, ast.ClassDef)
    ]))


def _parse_source_outline(source, source_path="", operation_patterns=None,
                          include_items=True, tree=None):
    # Replacement validation already has a parsed tree for both the old and
    # new source.  Reusing it avoids reparsing multi-megabyte Commands files
    # several times for a single interactive apply.
    if tree is None:
        tree = ast.parse(source)
    command_class = _pokecon_command_class(tree)
    mro_symbols = _command_mro_symbols(tree, command_class)
    class_nodes = list(reversed([
        item for item in mro_symbols if isinstance(item, ast.ClassDef)
    ]))
    if not class_nodes:
        class_nodes = [tree]
    regexes = _compile_operation_patterns(operation_patterns)
    functions = {}
    if command_class is None:
        function_nodes = [
            (node.name, node) for node in getattr(tree, "body", ())
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    else:
        function_nodes = [
            (name, value[1]) for name, value in
            _resolved_function_nodes(mro_symbols).items()
        ]
    for name, node in function_nodes:
        if include_items:
            functions[name] = _function_outline(source, node, regexes)
        else:
            functions[name] = {
                "name": name,
                "line": int(getattr(node, "lineno", 1) or 1),
                "end_line": _node_end_line(node),
                "items": [],
                "source": "",
            }
    tables = []
    for class_node in class_nodes:
        tables.extend(_parse_state_tables(source, class_node, functions))
    return {
        "schema_version": OUTLINE_SCHEMA_VERSION,
        "source_path": os.path.abspath(source_path) if source_path else "",
        "file_name": os.path.basename(source_path) if source_path else "",
        "source_hash": _source_hash(source),
        "command_class": getattr(command_class, "name", ""),
        "class_chain": [getattr(node, "name", "")
                        for node in class_nodes
                        if isinstance(node, ast.ClassDef)],
        "functions": functions,
        "tables": tables,
    }


def parse_source_outline(source, source_path="", operation_patterns=None):
    """Parse Commands source without importing or executing it."""
    return _parse_source_outline(
        source, source_path=source_path,
        operation_patterns=operation_patterns, include_items=True)


def _select_table(outline, table_id=""):
    tables = outline.get("tables", [])
    if table_id:
        table = next((item for item in tables
                      if item.get("id") == table_id
                      or item.get("name") == table_id), None)
        if table is None:
            raise ValueError("STATE辞書が見つかりません: {}".format(table_id))
        return table
    if len(tables) != 1:
        raise ValueError("編集するSTATE辞書を選択してください。")
    return tables[0]


def create_state_table_draft(outline, table_id=""):
    """Create a copy-on-write ordering draft for one STATE dictionary."""
    table = _select_table(outline, table_id)
    if not table.get("editable", False):
        raise ValueError(table.get("edit_problem") or
                         "このSTATE辞書は構成編集できません。")
    entries = []
    for entry in table.get("entries", []):
        entries.append({
            "id": entry.get("id", ""),
            "name": entry.get("name", ""),
            "locked_name": entry.get("name", ""),
            "method": entry.get("method", ""),
            "locked_method": entry.get("locked_method", ""),
            "value_source": entry.get("value_source", ""),
            "leading_lines": list(entry.get("leading_lines", [])),
            "trailing_comment": entry.get("trailing_comment", ""),
            "is_new": False,
        })
    return {
        "schema_version": OUTLINE_SCHEMA_VERSION,
        "source_hash": outline.get("source_hash", ""),
        "table_id": table.get("id", ""),
        "table_name": table.get("name", ""),
        "table_fingerprint": table.get("fingerprint", ""),
        "available_methods": sorted(outline.get("functions", {})),
        "tail_lines": list(table.get("tail_lines", [])),
        "entries": entries,
    }


def _draft_entry_index(draft, entry_id_or_name):
    return next((index for index, entry in enumerate(draft.get("entries", []))
                 if entry.get("id") == entry_id_or_name
                 or entry.get("name") == entry_id_or_name), -1)


def add_state_step(draft, step_name, method_name, index=None):
    step_name = str(step_name or "").strip()
    method_name = str(method_name or "").strip()
    if not step_name:
        raise ValueError("Step名を指定してください。")
    if any(entry.get("name") == step_name for entry in draft.get("entries", [])):
        raise ValueError("Step名が重複しています: {}".format(step_name))
    if not method_name.isidentifier() or keyword.iskeyword(method_name):
        raise ValueError("関数名が不正です: {}".format(method_name))
    if method_name not in set(draft.get("available_methods", [])):
        raise ValueError(
            "追加する関数はソース側で定義してください: {}".format(method_name))
    entry_id = "new-" + hashlib.sha1(
        (draft.get("table_id", "") + "\0" + step_name).encode("utf-8")
    ).hexdigest()
    entry = {
        "id": entry_id,
        "name": step_name,
        "locked_name": "",
        "method": method_name,
        "locked_method": "",
        "value_source": "self." + method_name,
        "leading_lines": [],
        "trailing_comment": "",
        "is_new": True,
    }
    entries = draft.setdefault("entries", [])
    if index is None:
        entries.append(entry)
    else:
        entries.insert(max(0, min(int(index), len(entries))), entry)
    return entry


def delete_state_step(draft, entry_id_or_name):
    index = _draft_entry_index(draft, entry_id_or_name)
    if index < 0:
        return False
    del draft["entries"][index]
    return True


def move_state_step(draft, entry_id_or_name, amount):
    index = _draft_entry_index(draft, entry_id_or_name)
    target = index + int(amount)
    entries = draft.get("entries", [])
    if index < 0 or target < 0 or target >= len(entries):
        return False
    entries[index], entries[target] = entries[target], entries[index]
    return True


def validate_state_table_draft(source, draft):
    errors = []
    try:
        outline = _parse_source_outline(source, include_items=False)
    except (SyntaxError, ValueError) as error:
        return {"errors": ["ソースを解析できません: {}".format(error)],
                "warnings": []}
    if draft.get("schema_version") != OUTLINE_SCHEMA_VERSION:
        errors.append("未対応の構成draftです。")
    if outline.get("source_hash") != draft.get("source_hash"):
        errors.append("ソースが構成draft作成後に変更されています。再読込してください。")
    try:
        table = _select_table(outline, draft.get("table_id", ""))
    except ValueError as error:
        errors.append(str(error))
        table = None
    if table is not None:
        if table.get("fingerprint") != draft.get("table_fingerprint"):
            errors.append("STATE辞書が構成draft作成後に変更されています。")
        if not table.get("editable", False):
            errors.append(table.get("edit_problem") or
                          "このSTATE辞書は構成編集できません。")

    known_methods = set(outline.get("functions", {}))
    source_by_id = {}
    source_by_name = {}
    if table is not None:
        source_by_id = {entry.get("id", ""): entry
                        for entry in table.get("entries", [])}
        source_by_name = {entry.get("name", ""): entry
                          for entry in table.get("entries", [])}
    names = set()
    ids = set()
    for entry in draft.get("entries", []):
        name = str(entry.get("name", "") or "")
        method = str(entry.get("method", "") or "")
        entry_id = str(entry.get("id", "") or "")
        if not name:
            errors.append("Step名が空です。")
        elif name in names:
            errors.append("Step名が重複しています: {}".format(name))
        names.add(name)
        if not entry_id or entry_id in ids:
            errors.append("Step IDが重複または空です: {}".format(entry_id))
        ids.add(entry_id)
        if not method.isidentifier() or keyword.iskeyword(method):
            errors.append("関数名が不正です: {}".format(method))
        locked = str(entry.get("locked_method", "") or "")
        if locked and locked != method:
            errors.append(
                "既存Stepの関数名はソース側で変更してください: {}".format(name))
        original = source_by_id.get(entry_id)
        same_named_original = source_by_name.get(name)
        preserved_reference = bool(
            original is not None and locked == method and
            str(entry.get("value_source", "") or "") ==
            str(original.get("value_source", "") or ""))
        # Existing external/alias/ambiguous references are allowed to move or
        # be deleted without becoming valid body-replacement targets.  Only a
        # newly added/remapped entry must resolve to a proven local method.
        if (method.isidentifier() and not keyword.iskeyword(method) and
                method not in known_methods and not preserved_reference):
            errors.append("ソース側に関数がありません: {}".format(method))
        if original is not None:
            if name != original.get("name"):
                errors.append(
                    "既存Step名は追加・削除では変更できません: {}".format(name))
            if method != original.get("method"):
                errors.append(
                    "既存Stepの関数名はソース側で変更してください: {}".format(name))
            if (str(entry.get("value_source", "") or "") !=
                    str(original.get("value_source", "") or "")):
                errors.append(
                    "既存Stepの関数参照はソース側で変更してください: {}".format(
                        name))
        elif same_named_original is not None:
            errors.append(
                "既存Stepを別の関数へ再追加できません: {}".format(name))
    return {"errors": list(dict.fromkeys(errors)), "warnings": []}


def _render_state_dict(table, draft, newline):
    opening = "{" + newline
    output = [opening]
    item_indent = table.get("item_indent", "    ")
    for entry in draft.get("entries", []):
        for leading in entry.get("leading_lines", []):
            if leading.endswith(("\n", "\r")):
                output.append(leading)
            else:
                output.append(leading + newline)
        value_source = (entry.get("value_source", "")
                        if entry.get("locked_method") else
                        "self." + entry.get("method", ""))
        line = "{}{}: {},".format(
            item_indent,
            json.dumps(entry.get("name", ""), ensure_ascii=False),
            value_source)
        comment = str(entry.get("trailing_comment", "") or "")
        if comment:
            line += "  " + comment
        output.append(line + newline)
    for trailing in draft.get("tail_lines", []):
        if trailing.endswith(("\n", "\r")):
            output.append(trailing)
        else:
            output.append(trailing + newline)
    output.append(table.get("base_indent", "") + "}")
    return "".join(output)


def apply_state_table_draft(source, draft):
    """Apply a validated STATE dictionary draft to source text only."""
    validation = validate_state_table_draft(source, draft)
    if validation["errors"]:
        raise ValueError("\n".join(validation["errors"]))
    outline = _parse_source_outline(source, include_items=False)
    table = _select_table(outline, draft.get("table_id", ""))
    newline = "\r\n" if "\r\n" in source else "\n"
    replacement = _render_state_dict(table, draft, newline)
    updated = (source[:int(table["dict_start"])] + replacement +
               source[int(table["dict_end"]):])
    ast.parse(updated)
    # Re-read the result and make sure the actual order/key/function mapping is
    # exactly the narrow change requested by the draft.
    result_outline = _parse_source_outline(updated, include_items=False)
    result_table = _select_table(result_outline, draft.get("table_id", ""))
    expected = [(entry.get("name"), entry.get("method"))
                for entry in draft.get("entries", [])]
    actual = [(entry.get("name"), entry.get("method"))
              for entry in result_table.get("entries", [])]
    if actual != expected:
        raise ValueError("STATE辞書の適用結果を検証できませんでした。")
    return updated


def _plan_needs_input_index(nodes):
    """Return whether rendering needs immutable input timing/evidence."""
    for node in nodes or ():
        if node.get("kind") == "recorded":
            return True
        if (node.get("kind") == "call" and node.get("recorded_timing")
                and int(node.get("input_start", 0) or 0) > 0):
            return True
        if node.get("kind") != "branch":
            continue
        for branch in node.get("branches", ()):
            if _plan_needs_input_index(branch.get("items", ())):
                return True
    return False


def render_recording_step_body(step, input_index=None, known_step_names=None):
    """Render one editable operation Step as an unindented Python suite.

    ``recorded`` nodes must be expanded with the operation editor's compact
    input index.  Silently replacing them with the preview renderer's ``pass``
    placeholder would lose controller operations, so this helper rejects that
    case explicitly.
    """
    if not isinstance(step, dict):
        raise ValueError("反映する操作記録Stepがありません。")
    if _plan_needs_input_index(step.get("items", ())) and input_index is None:
        raise ValueError(
            "記録入力の索引がまだ読み込まれていません。"
            "操作記録Step編集の読込完了後にやり直してください。")
    _session_model, plan_model = _load_operation_plan_modules()
    plan = {
        "schema_version": getattr(plan_model, "PLAN_SCHEMA_VERSION", 1),
        "session_id": "source-body-replacement",
        "source_path": "",
        "steps": [copy.deepcopy(step)],
    }
    preview, _source_map, warnings = plan_model.render_plan(
        plan, input_index=input_index)
    next_step = str(step.get("next_step", "") or "")
    isolated_next_warning = "{} の次Step {} は一覧にありません。".format(
        step.get("name", ""), next_step)
    known = set(str(name) for name in (known_step_names or ()) if name)
    if next_step.endswith("_END") or next_step in known:
        warnings = [warning for warning in warnings
                    if warning != isolated_next_warning]
    preview_tree = ast.parse(preview)
    function = next((node for node in preview_tree.body
                     if isinstance(node, (ast.FunctionDef,
                                          ast.AsyncFunctionDef))), None)
    if function is None:
        raise ValueError("操作記録Stepから関数本体を生成できませんでした。")
    marker = plan_model.PLAN_END.format(session_id=plan["session_id"])
    preview_lines = preview.splitlines()
    try:
        marker_index = preview_lines.index(marker)
    except ValueError:
        raise ValueError("操作記録Stepの生成範囲を確認できませんでした。")
    # ``function.lineno`` is one-based and therefore also the zero-based index
    # of the first physical line after the generated ``def`` line.
    body_lines = preview_lines[int(function.lineno):marker_index]
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    relative = []
    for line in body_lines:
        if not line.strip():
            relative.append("")
        elif line.startswith("    "):
            relative.append(line[4:])
        else:
            raise ValueError("生成した関数本体のインデントを確認できませんでした。")
    if not relative:
        relative = ["pass"]
    # Parse the suite independently before it is allowed near a live editor.
    ast.parse("def _recorded_step(self):\n" + "\n".join(
        "    " + line if line else "" for line in relative) + "\n")
    return "\n".join(relative), list(warnings or ())


def _function_candidates(source, method_name, tree=None):
    if tree is None:
        tree = ast.parse(source)
    command_class = _pokecon_command_class(tree)
    if command_class is None:
        result = [
            (tree, node) for node in getattr(tree, "body", ())
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == method_name)
        ]
    else:
        resolved = _resolved_function_nodes(
            _command_mro_symbols(tree, command_class))
        result = [resolved[method_name]] if method_name in resolved else []
    return tree, result


def _function_token_span(source, function):
    """Return ``(colon_end, suite_end_offset, suite_end_line, inline)``.

    Tokenization starts at the definition's physical line and stops at its
    matching DEDENT.  This keeps parsing a large Commands file linear in the
    total size of its function bodies instead of rescanning the whole prefix
    for every function.
    """
    definition_line = int(getattr(function, "lineno", 1) or 1)
    physical_lines, offsets = _source_view(source)
    definition_text = (
        physical_lines[definition_line - 1].rstrip("\r\n")
        if 0 < definition_line <= len(physical_lines) else "")
    definition_column = _line_char_column(
        definition_text, getattr(function, "col_offset", 0))

    next_line = [definition_line - 1]

    def reader():
        index = next_line[0]
        if index >= len(physical_lines):
            return ""
        next_line[0] += 1
        return physical_lines[index]

    started = False
    header_depth = 0
    colon_relative = None
    colon_end = None
    header_newline = False
    suite_depth = 0
    inline_suite = False
    last_suite_line = 0
    try:
        for token in tokenize.generate_tokens(reader):
            if colon_relative is None:
                if not started:
                    if token.end <= (1, definition_column):
                        continue
                    started = True
                if token.type != tokenize.OP:
                    continue
                if token.string in "([{":
                    header_depth += 1
                elif token.string in ")]}":
                    header_depth = max(0, header_depth - 1)
                elif token.string == ":" and header_depth == 0:
                    colon_relative = token.end
                    colon_end = (
                        definition_line + int(token.end[0]) - 1,
                        int(token.end[1]))
                    last_suite_line = int(colon_end[0])
                continue

            if token.end <= colon_relative:
                continue

            if inline_suite:
                if token.type == tokenize.NEWLINE:
                    end_line = max(
                        last_suite_line,
                        definition_line + int(token.end[0]) - 1)
                    return (colon_end,
                            offsets[min(end_line, len(offsets) - 1)],
                            end_line, True)
                if token.type not in (tokenize.NL, tokenize.ENDMARKER):
                    last_suite_line = max(
                        last_suite_line,
                        definition_line + int(token.end[0]) - 1)
                continue

            if suite_depth == 0:
                if token.type == tokenize.NEWLINE:
                    header_newline = True
                    continue
                if token.type in (tokenize.NL, tokenize.COMMENT):
                    continue
                if token.type == tokenize.INDENT and header_newline:
                    suite_depth = 1
                    continue
                if token.type == tokenize.ENDMARKER:
                    break
                if not header_newline:
                    inline_suite = True
                    last_suite_line = max(
                        last_suite_line,
                        definition_line + int(token.end[0]) - 1)
                    continue
                # A valid parsed function must eventually enter its suite.
                continue

            if token.type == tokenize.INDENT:
                suite_depth += 1
                continue
            if token.type == tokenize.DEDENT:
                suite_depth -= 1
                if suite_depth == 0:
                    if last_suite_line <= int(colon_end[0]):
                        raise ValueError(
                            "反映先関数の本体範囲を確認できませんでした。")
                    return (colon_end,
                            offsets[min(last_suite_line,
                                        len(offsets) - 1)],
                            last_suite_line, False)
                continue
            if token.type == tokenize.COMMENT:
                if int(token.start[1]) > definition_column:
                    last_suite_line = max(
                        last_suite_line,
                        definition_line + int(token.end[0]) - 1)
                continue
            if token.type not in (tokenize.NL, tokenize.NEWLINE,
                                  tokenize.ENDMARKER):
                last_suite_line = max(
                    last_suite_line,
                    definition_line + int(token.end[0]) - 1)
    except (tokenize.TokenError, IndentationError) as error:
        raise ValueError(
            "反映先関数の本体範囲を確認できませんでした: {}".format(error))
    raise ValueError("反映先関数の本体範囲を確認できませんでした。")


def _function_header_colon(source, function):
    """Locate the suite colon, including multiline signatures on Python 3.7."""
    return _function_token_span(source, function)[0]


def _function_suite_end(source, function):
    """Return the exact end offset/line of a function suite.

    Python 3.7 AST nodes have no ``end_lineno``.  Taking the greatest child
    ``lineno`` is unsafe because closing parentheses of a final multiline
    statement have no AST node of their own.  Token indentation identifies
    the complete suite on every supported Python version.  The final
    substantive token line is used instead of the matching DEDENT line so
    blank lines and class-level comments before the next member are retained.
    Indented trailing comments remain part of the replaced function body.
    """
    _colon_end, end, end_line, _inline = \
        _function_token_span(source, function)
    return end, end_line


def _function_source_segment(source, function, suite_end=None):
    """Return one complete function without consuming following comments."""
    lines_with_ends, offsets = _source_view(source)
    start_line = int(getattr(function, "lineno", 1) or 1)
    line = (lines_with_ends[start_line - 1].rstrip("\r\n")
            if 0 < start_line <= len(lines_with_ends) else "")
    start_column = _line_char_column(
        line, getattr(function, "col_offset", 0))
    start = offsets[start_line - 1] + start_column
    if suite_end is None:
        suite_end, _end_line = _function_suite_end(source, function)
    end = int(suite_end)
    return source[start:end].rstrip("\r\n")


def _state_mappings(outline):
    """Stable STATE identity used to prove body replacement stayed narrow."""
    return [(
        table.get("id", ""),
        tuple((entry.get("name", ""), entry.get("method", ""),
               entry.get("value_source", ""))
              for entry in table.get("entries", ())),
    ) for table in outline.get("tables", ())]


def prepare_recording_step_replacement(source, step, method_name,
                                       expected_source_hash="",
                                       expected_function_line=0,
                                       input_index=None,
                                       known_step_names=None):
    """Build a verified replacement of one existing function body's suite.

    The returned text is intended for the PokeConStudio *editor buffer*.
    This function performs no file I/O and does not modify ``step_plan.json``
    or immutable recording evidence.
    """
    source = str(source or "")
    method_name = str(method_name or "").strip()
    if not source.strip():
        raise ValueError("現在ソースが空です。")
    if not method_name.isidentifier() or keyword.iskeyword(method_name):
        raise ValueError("反映先の関数名が不正です: {}".format(method_name))
    if expected_source_hash and _source_hash(source) != expected_source_hash:
        raise ValueError(
            "比較後にソースが変更されています。3列を再読込してください。")

    _tree, candidates = _function_candidates(source, method_name)
    expected_line = int(expected_function_line or 0)
    if expected_line:
        candidates = [value for value in candidates
                      if int(getattr(value[1], "lineno", 0) or 0)
                      == expected_line]
    if not candidates:
        suffix = "（比較時の行{}）".format(expected_line) if expected_line else ""
        raise ValueError(
            "反映先関数 {}() が見つかりません{}。3列を再読込してください。".format(
                method_name, suffix))
    if len(candidates) != 1:
        raise ValueError(
            "同名関数 {}() が複数あります。3列の対応関数を特定できません。".format(
                method_name))
    _owner, function = candidates[0]
    body_source, warnings = render_recording_step_body(
        step, input_index=input_index,
        known_step_names=known_step_names)

    (colon_line, colon_column), end, _function_end_line, inline_suite = \
        _function_token_span(source, function)
    if inline_suite:
        start = _absolute_offset(source, colon_line, colon_column)
    else:
        # Preserve everything on the definition line after the suite colon,
        # especially an explanatory/type comment.  For a block suite the
        # replaceable body begins on the following physical line.
        _physical_lines, line_offsets = _source_view(source)
        start = line_offsets[min(colon_line, len(line_offsets) - 1)]
    if end <= start:
        raise ValueError("反映先関数の本体範囲を確認できませんでした。")

    source_lines = source.splitlines()
    definition_line = source_lines[int(function.lineno) - 1]
    definition_indent = definition_line[
        :len(definition_line) - len(definition_line.lstrip(" \t"))]
    body_indent = definition_indent + "    "
    if function.body:
        first_line = int(getattr(function.body[0], "lineno", 0) or 0)
        if 0 < first_line <= len(source_lines):
            text = source_lines[first_line - 1]
            existing_indent = text[:len(text) - len(text.lstrip(" \t"))]
            if existing_indent.startswith(definition_indent) \
                    and len(existing_indent) > len(definition_indent):
                body_indent = existing_indent

    newline = "\r\n" if "\r\n" in source else "\n"
    rendered_lines = [body_indent + line if line else ""
                      for line in body_source.split("\n")]
    replacement = newline.join(rendered_lines) + newline
    if inline_suite:
        replacement = newline + replacement
    updated = source[:start] + replacement + source[end:]
    updated_tree = ast.parse(updated)

    before_outline = _parse_source_outline(
        source, include_items=False, tree=_tree)
    after_outline = _parse_source_outline(
        updated, include_items=False, tree=updated_tree)
    if _state_mappings(before_outline) != _state_mappings(after_outline):
        raise ValueError("関数本体以外のSTATE辞書が変わるため反映を中止しました。")
    _updated_tree, updated_candidates = _function_candidates(
        updated, method_name, tree=updated_tree)
    updated_target = next((node for _class_node, node in updated_candidates
                           if int(getattr(node, "lineno", 0) or 0)
                           == int(getattr(function, "lineno", 0) or 0)), None)
    if updated_target is None:
        raise ValueError("反映後の関数を確認できませんでした。")

    return {
        "source": updated,
        "method": method_name,
        "function_line": int(getattr(function, "lineno", 0) or 0),
        "step_id": str(step.get("id", "") or ""),
        "step_name": str(step.get("name", "") or ""),
        "old_function_source": _function_source_segment(
            source, function, suite_end=end),
        "new_function_source": _function_source_segment(
            updated, updated_target),
        "warnings": warnings,
    }


def _load_operation_plan_modules():
    devstudio = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "DevStudio")
    added = False
    if devstudio not in sys.path:
        sys.path.insert(0, devstudio)
        added = True
    try:
        session_model = importlib.import_module("OperationSessionModel")
        plan_model = importlib.import_module("OperationStepPlan")
    finally:
        if added:
            try:
                sys.path.remove(devstudio)
            except ValueError:
                pass
    return session_model, plan_model


def load_recording_plan_bundle(session_dir, build_input_index=True):
    """Load an operation Step plan and, when requested, its compact index.

    The comparison view needs only Step/range metadata.  Its embedded operation
    editor builds the index used for on-demand input expansion, so callers can
    pass ``build_input_index=False`` to avoid scanning a large ``inputs.jsonl``
    twice.
    """
    session_model, plan_model = _load_operation_plan_modules()
    session_dir = os.path.abspath(session_dir)
    session = session_model.load_session(session_dir)
    mappings = session_model.load_mappings(session_dir)
    plan, existed = plan_model.load_step_plan(
        session_dir, session=session, mappings=mappings)
    input_path = os.path.join(session_dir, "inputs.jsonl")
    input_index = None
    if build_input_index and os.path.isfile(input_path):
        checkpoints = [step.get("input_start", 0)
                       for step in plan.get("steps", [])]
        input_index = plan_model.JsonlInputIndex(
            input_path, checkpoint_lines=checkpoints)
        plan_model.hydrate_plan_times(plan, input_index)
    return {
        "session_dir": session_dir,
        "session": session,
        "mappings": mappings,
        "plan": plan,
        "input_index": input_index,
        "plan_existed": bool(existed),
    }


def _outline_items_from_code(code, regexes):
    wrapper = "def _recorded(self):\n" + "\n".join(
        "    " + line for line in str(code or "pass").splitlines())
    try:
        function = ast.parse(wrapper).body[0]
    except (SyntaxError, ValueError):
        return [{
            "id": "recorded:opaque",
            "kind": "operation",
            "roles": ["operation"],
            "line": 0,
            "end_line": 0,
            "depth": 0,
            "source": str(code or ""),
            "display": str(code or "").splitlines()[0] if code else "",
            "calls": [], "operation_calls": [], "image_targets": [],
            "variables": [], "return_target": "",
            "signature": "operation:" + re.sub(
                r"\s+", " ", str(code or "")).strip(),
        }]
    result = []
    for statement, depth in _iter_statements(function.body):
        item = _classify_statement(wrapper, statement, depth, regexes)
        if item is not None:
            # Wrapper adds one source line; recorded line numbers come from
            # the node metadata instead and are filled by the caller.
            item["line"] = max(0, item["line"] - 1)
            item["end_line"] = max(0, item["end_line"] - 1)
            result.append(item)
    return result


def recording_plan_outline(plan, input_index=None, operation_patterns=None):
    """Convert an OperationStepPlan plan into source-comparable Steps."""
    regexes = _compile_operation_patterns(operation_patterns)
    readable_switch_operations = None
    if input_index is not None:
        session_model, _plan_model = _load_operation_plan_modules()
        readable_switch_operations = session_model.readable_switch_operations
        stick_mode = session_model.STICK_MODE_EXACT
    else:
        stick_mode = "exact"

    steps = []

    def append_code(items, code, node, depth):
        values = _outline_items_from_code(code, regexes)
        for value in values:
            value["depth"] = int(value.get("depth", 0)) + depth
            value["input_start"] = int(node.get("input_start", 0) or 0)
            value["input_end"] = int(node.get("input_end", 0) or 0)
            value["video_start"] = float(node.get("video_start", 0.0) or 0.0)
            value["video_end"] = float(node.get("video_end", 0.0) or 0.0)
            value["id"] = "{}:{}".format(node.get("id", "node"), len(items))
            items.append(value)

    def walk_plan_nodes(nodes, items, depth=0):
        for node in nodes or []:
            kind = node.get("kind")
            if kind == "recorded":
                if readable_switch_operations is None:
                    items.append({
                        "id": node.get("id", ""),
                        "kind": "recorded_range",
                        "roles": ["operation"],
                        "line": 0, "end_line": 0, "depth": depth,
                        "source": "記録 #{}-#{}".format(
                            node.get("input_start", 0), node.get("input_end", 0)),
                        "display": "記録入力 #{}-#{}".format(
                            node.get("input_start", 0), node.get("input_end", 0)),
                        "calls": [], "operation_calls": [],
                        "image_targets": [], "variables": [],
                        "return_target": "",
                        "signature": "recorded_range:{}:{}".format(
                            node.get("input_start", 0), node.get("input_end", 0)),
                        "input_start": node.get("input_start", 0),
                        "input_end": node.get("input_end", 0),
                        "video_start": node.get("video_start", 0.0),
                        "video_end": node.get("video_end", 0.0),
                    })
                else:
                    start = int(node.get("input_start", 0) or 0)
                    end = int(node.get("input_end", 0) or 0)
                    operations = readable_switch_operations(
                        input_index.read_range(start, end),
                        stick_mode=stick_mode,
                        initial_state=input_index.state_before(start),
                        origin_time=input_index.time_before_line(start, 0.0))
                    for operation in operations:
                        mapped = dict(node)
                        mapped["input_start"] = operation.get("start_line", start)
                        mapped["input_end"] = operation.get("end_line", end)
                        mapped["video_start"] = operation.get("time", 0.0)
                        append_code(items, operation.get("code", ""), mapped, depth)
            elif kind in ("operation", "opaque"):
                append_code(items, node.get("source", ""), node, depth)
            elif kind == "call":
                append_code(items, "self.{}()".format(
                    node.get("name", "recorded_function")), node, depth)
            elif kind == "return":
                append_code(items, "return {!r}".format(
                    node.get("target", "")), node, depth)
            elif kind == "branch":
                for branch_index, branch in enumerate(node.get("branches", [])):
                    condition = branch.get("condition")
                    if condition is not None:
                        if condition.get("kind") == "image_check":
                            expression = "self.image_check({!r})".format(
                                condition.get("target", ""))
                        else:
                            expression = condition.get("source", "") or "False"
                        if condition.get("negate"):
                            expression = "not ({})".format(expression)
                        prefix = "if" if branch_index == 0 else "elif"
                        append_code(items, "{} {}:\n    pass".format(
                            prefix, expression), node, depth)
                    walk_plan_nodes(branch.get("items", []), items, depth + 1)

    for step in plan.get("steps", []) or []:
        items = []
        walk_plan_nodes(step.get("items", []), items)
        if step.get("auto_next", True) and step.get("next_step"):
            append_code(items, "return {!r}".format(step.get("next_step")),
                        step, 0)
        steps.append({
            "id": step.get("id", ""),
            "name": step.get("name", ""),
            "method": step.get("method", ""),
            "label": step.get("label", ""),
            "input_start": step.get("input_start", 0),
            "input_end": step.get("input_end", 0),
            "video_start": step.get("video_start", 0.0),
            "video_end": step.get("video_end", 0.0),
            "items": items,
        })
    return {
        "schema_version": OUTLINE_SCHEMA_VERSION,
        "session_id": plan.get("session_id", ""),
        "source_path": plan.get("source_path", ""),
        "file_name": os.path.basename(plan.get("source_path", "")),
        "steps": steps,
    }


def _comparable_signatures(items):
    return [item.get("signature", "") for item in items
            if item.get("kind") not in ("comment", "ignore")]


def compare_recording_to_source(recording_outline, source_outline,
                                table_id=""):
    """Align recorded Steps with one source STATE table and summarize diffs."""
    table = _select_table(source_outline, table_id)
    source_by_name = {entry.get("name", ""): entry
                      for entry in table.get("entries", [])}
    source_by_method = {}
    for entry in table.get("entries", []):
        source_by_method.setdefault(entry.get("method", ""), []).append(entry)

    rows = []
    used_source_ids = set()
    summary = {"same": 0, "changed": 0, "recording_only": 0,
               "source_only": 0, "unresolved": 0}
    for recorded in recording_outline.get("steps", []):
        source_step = source_by_name.get(recorded.get("name", ""))
        match_kind = "name"
        if source_step is None and recorded.get("method"):
            candidates = source_by_method.get(recorded.get("method"), [])
            if len(candidates) == 1:
                source_step = candidates[0]
                match_kind = "method"
        if source_step is None:
            status = "recording_only"
            summary[status] += 1
            rows.append({"status": status, "match": "", "recording": recorded,
                         "source": None, "changes": []})
            continue
        used_source_ids.add(source_step.get("id"))
        recorded_signatures = _comparable_signatures(recorded.get("items", []))
        source_signatures = _comparable_signatures(source_step.get("items", []))
        unresolved = any(value.startswith("recorded_range:")
                         for value in recorded_signatures)
        matcher = difflib.SequenceMatcher(
            None, recorded_signatures, source_signatures, autojunk=False)
        changes = [{
            "tag": tag,
            "recording_start": i1,
            "recording_end": i2,
            "source_start": j1,
            "source_end": j2,
        } for tag, i1, i2, j1, j2 in matcher.get_opcodes()
                   if tag != "equal"]
        if unresolved:
            status = "unresolved"
        elif not changes:
            status = "same"
        else:
            status = "changed"
        summary[status] += 1
        rows.append({
            "status": status,
            "match": match_kind,
            "recording": recorded,
            "source": source_step,
            "changes": changes,
        })
    for source_step in table.get("entries", []):
        if source_step.get("id") in used_source_ids:
            continue
        summary["source_only"] += 1
        rows.append({"status": "source_only", "match": "",
                     "recording": None, "source": source_step, "changes": []})
    return {
        "table_id": table.get("id", ""),
        "table_name": table.get("name", ""),
        "rows": rows,
        "summary": summary,
    }


__all__ = [
    "OUTLINE_SCHEMA_VERSION",
    "add_state_step",
    "apply_state_table_draft",
    "compare_recording_to_source",
    "create_state_table_draft",
    "delete_state_step",
    "load_recording_plan_bundle",
    "move_state_step",
    "parse_source_outline",
    "prepare_recording_step_replacement",
    "recording_plan_outline",
    "render_recording_step_body",
    "validate_state_table_draft",
]
