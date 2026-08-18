#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static checks for image_check names used by an open Python source."""
from __future__ import print_function

import ast
import pprint
import re
import textwrap


LIBRARY_IMPORT_BEGIN = "# POKECON_IMAGE_CHECK_LIBRARY_IMPORTS_BEGIN"
LIBRARY_IMPORT_END = "# POKECON_IMAGE_CHECK_LIBRARY_IMPORTS_END"


def _literal_string(node):
    constant_type = getattr(ast, "Constant", ())
    if isinstance(node, constant_type) and isinstance(getattr(node, "value", None), str):
        return node.value
    legacy_type = getattr(ast, "Str", ())
    if isinstance(node, legacy_type) and isinstance(getattr(node, "s", None), str):
        return node.s
    return None


def _container_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _string_keys(node):
    """Return statically visible string keys without evaluating user code."""
    if isinstance(node, ast.Dict):
        return {_literal_string(key) for key in node.keys if _literal_string(key) is not None}
    # Allow TARGETS = dict(NAME=...), which is occasionally convenient in samples.
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
        return {keyword.arg for keyword in node.keywords if keyword.arg}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _string_keys(node.left) | _string_keys(node.right)
    return set()


def _subscript_key(node):
    if not isinstance(node, ast.Subscript):
        return None
    value = node.slice
    # Python 3.8 and earlier wrap slices in ast.Index.
    index_type = getattr(ast, "Index", ())
    if isinstance(value, index_type):
        value = value.value
    return _literal_string(value)


def _is_image_check_call(node):
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id == "image_check"
    return isinstance(node.func, ast.Attribute) and node.func.attr == "image_check"


def _source_expression(source, node):
    getter = getattr(ast, "get_source_segment", None)
    if getter is not None:
        value = getter(source, node)
        if value:
            return value
    # DevStudio still supports Python versions whose AST has no end_lineno.
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _source_expression(source, node.value) + "." + node.attr
    return "<{}>".format(node.__class__.__name__)


def _contains_name(node, name):
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def _literal_strings(node):
    value = _literal_string(node)
    if value is not None:
        return {value}
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values = {_literal_string(item) for item in node.elts}
        return {item for item in values if item is not None}
    return set()


def _exception_names(tree):
    """Find literal names explicitly handled by image_check_exception methods."""
    result = set()
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                or function.name != "image_check_exception":
            continue
        parameters = [argument.arg for argument in function.args.args if argument.arg != "self"]
        target_parameter = "targetimage" if "targetimage" in parameters else (parameters[0] if parameters else "")
        if not target_parameter:
            continue
        for comparison in (node for node in ast.walk(function) if isinstance(node, ast.Compare)):
            if not _contains_name(comparison, target_parameter):
                continue
            operands = [comparison.left] + list(comparison.comparators)
            for index, operand in enumerate(operands):
                if not _contains_name(operand, target_parameter):
                    continue
                for other_index, other in enumerate(operands):
                    if index != other_index:
                        result.update(_literal_strings(other))
    return result


def _exception_rule_names(test, target_parameter):
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 \
            or len(test.comparators) != 1:
        return []
    left, operator, right = test.left, test.ops[0], test.comparators[0]
    if isinstance(left, ast.Name) and left.id == target_parameter:
        if isinstance(operator, ast.Eq):
            value = _literal_string(right)
            return [value] if value is not None else []
        if isinstance(operator, ast.In):
            return [value for value in (
                _literal_string(item)
                for item in getattr(right, "elts", ())) if value is not None]
    if isinstance(right, ast.Name) and right.id == target_parameter \
            and isinstance(operator, ast.Eq):
        value = _literal_string(left)
        return [value] if value is not None else []
    return []


def _exception_function(tree):
    return next((node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == "image_check_exception"), None)


def image_check_exception_rules(source):
    """Return directly editable literal exception branches in source order."""
    tree = ast.parse(source)
    function = _exception_function(tree)
    if function is None:
        return []
    parameters = [argument.arg for argument in function.args.args
                  if argument.arg != "self"]
    target = "targetimage" if "targetimage" in parameters \
        else (parameters[0] if parameters else "")
    rules = []
    for branch in function.body:
        if not isinstance(branch, ast.If) or len(branch.body) != 1 \
                or not isinstance(branch.body[0], ast.Return) \
                or branch.body[0].value is None:
            continue
        names = _exception_rule_names(branch.test, target)
        if not names:
            continue
        expression = _source_expression(source, branch.body[0].value)
        for name in names:
            rules.append({
                "name": name,
                "expression": expression,
                "line": int(getattr(branch, "lineno", 1)),
                "names": list(names),
                "node": branch,
            })
    return rules


def _exception_branch_text(indent, names, expression, newline="\n"):
    lines = []
    for name in names:
        lines.append("{}if targetimage == {!r}:{}".format(
            indent, str(name), newline))
        lines.append("{}    return {}{}".format(indent, expression, newline))
    return "".join(lines)


def _replace_source_lines(source, start_line, end_line, replacement):
    lines = source.splitlines(True)
    lines[start_line - 1:end_line] = [replacement]
    return "".join(lines)


def upsert_image_check_exception(source, new_name, expression,
                                 old_name=None):
    """Add or change one simple image_check_exception return branch."""
    new_name = str(new_name or "").strip()
    expression = str(expression or "").strip()
    old_name = str(old_name or "").strip() or None
    if not new_name or "\n" in new_name or "\r" in new_name:
        raise ValueError("例外の画像検知名を1行で入力してください。")
    if not expression:
        raise ValueError("例外判定の戻り値式を入力してください。")
    ast.parse(expression, mode="eval")
    rules = image_check_exception_rules(source)
    existing = {rule["name"] for rule in rules}
    if new_name in existing and new_name != old_name:
        raise ValueError("同じ例外判定名が既にあります: " + new_name)
    newline = "\r\n" if "\r\n" in source else "\n"
    if old_name:
        rule = next((item for item in rules if item["name"] == old_name), None)
        if rule is None:
            raise ValueError("変更元の例外判定がありません: " + old_name)
        node = rule["node"]
        source_line = source.splitlines()[node.lineno - 1]
        indent = source_line[:len(source_line) - len(source_line.lstrip())]
        names = [name for name in rule["names"] if name != old_name]
        names.append(new_name)
        replacement = _exception_branch_text(indent, names, expression, newline)
        # Keep the original expression for aliases that shared the old branch.
        if len(rule["names"]) > 1:
            replacement = _exception_branch_text(
                indent, [name for name in rule["names"] if name != old_name],
                rule["expression"], newline)
            replacement += _exception_branch_text(
                indent, [new_name], expression, newline)
        updated = _replace_source_lines(
            source, node.lineno, getattr(node, "end_lineno", node.lineno),
            replacement)
    else:
        tree = ast.parse(source)
        function = _exception_function(tree)
        if function is None:
            raise ValueError("image_check_exception()がソースにありません。")
        function_lines = source.splitlines(True)
        body_indent = " " * (int(function.col_offset) + 4)
        marker_line = next((index for index in range(
            function.lineno, getattr(function, "end_lineno", function.lineno))
            if "POKECON_IMAGE_CHECK_EXCEPTION_USER_BEGIN" in
            function_lines[index]), None)
        if marker_line is None:
            final_return = next((item for item in reversed(function.body)
                                 if isinstance(item, ast.Return)), None)
            insert_line = (final_return.lineno - 1) if final_return else \
                getattr(function, "end_lineno", function.lineno) - 1
        else:
            insert_line = marker_line
        function_lines[insert_line:insert_line] = [
            _exception_branch_text(body_indent, [new_name], expression, newline)]
        updated = "".join(function_lines)
    compile(updated, "<image_check_exception>", "exec")
    return updated


def delete_image_check_exception(source, name):
    """Delete one editable exception branch while keeping shared aliases."""
    name = str(name or "").strip()
    rules = image_check_exception_rules(source)
    rule = next((item for item in rules if item["name"] == name), None)
    if rule is None:
        raise ValueError("削除する例外判定がありません: " + name)
    node = rule["node"]
    source_line = source.splitlines()[node.lineno - 1]
    indent = source_line[:len(source_line) - len(source_line.lstrip())]
    newline = "\r\n" if "\r\n" in source else "\n"
    remaining = [item for item in rule["names"] if item != name]
    replacement = _exception_branch_text(
        indent, remaining, rule["expression"], newline) if remaining else ""
    updated = _replace_source_lines(
        source, node.lineno, getattr(node, "end_lineno", node.lineno),
        replacement)
    compile(updated, "<image_check_exception>", "exec")
    return updated


def _all_literal_nodes(node, value):
    return [child for child in ast.walk(node)
            if _literal_string(child) == value]


def _replace_literal_nodes(source, nodes, replacement):
    lines = source.splitlines(True)
    starts, offset = [], 0
    for line in lines:
        starts.append(offset)
        offset += len(line)

    def character_column(line, byte_column):
        raw = line.encode("utf-8")
        return len(raw[:byte_column].decode("utf-8"))

    spans = set()
    for node in nodes:
        if not hasattr(node, "end_lineno") or node.end_lineno is None:
            raise ValueError("このPythonでは安全な名称変更位置を取得できません。")
        start_line, end_line = node.lineno - 1, node.end_lineno - 1
        start = starts[start_line] + character_column(
            lines[start_line], node.col_offset)
        end = starts[end_line] + character_column(
            lines[end_line], node.end_col_offset)
        spans.add((start, end))
    updated = source
    for start, end in sorted(spans, reverse=True):
        updated = updated[:start] + repr(str(replacement)) + updated[end:]
    return updated


def rename_image_check_references(source, old_name, new_name,
                                  include_definitions=False):
    """Rename literal image_check callers and optional generated definitions."""
    old_name = str(old_name or "").strip()
    new_name = str(new_name or "").strip()
    if not old_name or not new_name:
        raise ValueError("変更前と変更後の画像検知名を入力してください。")
    if old_name == new_name:
        return source, 0
    tree = ast.parse(source)
    nodes = []
    for call in (node for node in ast.walk(tree) if _is_image_check_call(node)):
        if call.args and _literal_string(call.args[0]) == old_name:
            nodes.append(call.args[0])
    if include_definitions:
        containers = {
            "IMAGE_DETECTION_TARGETS", "IMAGE_DETECTION_OPERATORS",
            "IMAGE_DETECTION_DESCRIPTIONS", "IMAGE_DETECTION_SETS",
            "IMAGE_DETECTION_LISTS",
        }
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(_container_name(target) in containers for target in targets):
                    nodes.extend(_all_literal_nodes(node.value, old_name))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ("update", "setdefault"):
                container = _container_name(node.func.value)
                nested = isinstance(node.func.value, ast.Call) and \
                    isinstance(node.func.value.func, ast.Attribute) and \
                    _container_name(node.func.value.func.value) in containers
                if container in containers or nested:
                    for argument in node.args:
                        nodes.extend(_all_literal_nodes(argument, old_name))
    updated = _replace_literal_nodes(source, nodes, new_name) if nodes else source
    compile(updated, "<image_check_rename>", "exec")
    return updated, len({(node.lineno, node.col_offset) for node in nodes})


def _registered_names(tree):
    targets, sets = set(), set()
    container_sets = {
        "IMAGE_DETECTION_TARGETS": targets,
        "IMAGE_DETECTION_SETS": sets,
        "IMAGE_DETECTION_LISTS": sets,
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            assignment_targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            for target in assignment_targets:
                name = _container_name(target)
                if name in container_sets:
                    container_sets[name].update(_string_keys(value))
                    continue
                if isinstance(target, ast.Subscript):
                    name = _container_name(target.value)
                    key = _subscript_key(target)
                    if name in container_sets and key is not None:
                        container_sets[name].add(key)
        elif isinstance(node, ast.AugAssign):
            name = _container_name(node.target)
            if name in container_sets:
                container_sets[name].update(_string_keys(node.value))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "update":
            name = _container_name(node.func.value)
            if name in container_sets and node.args:
                container_sets[name].update(_string_keys(node.args[0]))
    return targets, sets


def audit_image_check_references(source):
    """Compare literal image_check references with runtime registrations.

    Dynamic arguments are returned separately because a static check cannot know
    their runtime values.  The function parses source only and never imports or
    executes the command being inspected.
    """
    tree = ast.parse(source)
    target_names, set_names = _registered_names(tree)
    exception_names = _exception_names(tree)
    resolved_names = target_names | set_names | exception_names

    literal_lines = {}
    dynamic = []
    for call in (node for node in ast.walk(tree) if _is_image_check_call(node)):
        argument = call.args[0] if call.args else None
        name = _literal_string(argument) if argument is not None else None
        if name is None:
            expression = _source_expression(source, argument) if argument is not None else "<引数なし>"
            dynamic.append({
                "line": int(getattr(call, "lineno", 1)),
                "column": int(getattr(call, "col_offset", 0)),
                "expression": expression or "<動的指定>",
            })
            continue
        literal_lines.setdefault(name, []).append(int(getattr(call, "lineno", 1)))

    references = []
    for name, lines in literal_lines.items():
        if name in target_names:
            resolved_by = "画像検知"
        elif name in set_names:
            resolved_by = "検知セット"
        elif name in exception_names:
            resolved_by = "例外判定"
        else:
            resolved_by = "未登録"
        references.append({
            "name": name,
            "lines": sorted(lines),
            "line": min(lines),
            "count": len(lines),
            "status": "ok" if name in resolved_names else "missing",
            "resolved_by": resolved_by,
        })
    references.sort(key=lambda item: (item["status"] != "missing", item["name"].lower()))
    dynamic.sort(key=lambda item: (item["line"], item["column"]))
    return {
        "references": references,
        "missing": [item for item in references if item["status"] == "missing"],
        "dynamic": dynamic,
        "target_names": sorted(target_names, key=str.lower),
        "set_names": sorted(set_names, key=str.lower),
        "exception_names": sorted(exception_names, key=str.lower),
    }


def _library_import_match(source):
    pattern = re.compile(
        r"(?ms)^(?P<indent>[ \t]*)" + re.escape(LIBRARY_IMPORT_BEGIN) +
        r"\n.*?^\1" + re.escape(LIBRARY_IMPORT_END) + r"[ \t]*$")
    return pattern.search(source)


def _managed_import_targets(source):
    match = _library_import_match(source)
    if not match:
        return {}, {}, {}
    try:
        tree = ast.parse(textwrap.dedent(match.group(0)))
    except SyntaxError:
        return {}, {}, {}
    targets, operators, descriptions = {}, {}, {}
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "update" or not call.args:
            continue
        try:
            values = ast.literal_eval(call.args[0])
        except (ValueError, TypeError, SyntaxError):
            continue
        if not isinstance(values, dict):
            continue
        container = _container_name(call.func.value)
        if container == "IMAGE_DETECTION_TARGETS":
            targets.update(values)
        elif container == "IMAGE_DETECTION_OPERATORS":
            operators.update(values)
        elif isinstance(call.func.value, ast.Call):
            base = call.func.value.func
            if isinstance(base, ast.Attribute) and base.attr == "setdefault" \
                    and _container_name(base.value) == "IMAGE_DETECTION_DESCRIPTIONS":
                descriptions.update(values)
    return targets, operators, descriptions


def _format_library_import_block(indent, targets, operators, descriptions):
    body = [
        LIBRARY_IMPORT_BEGIN,
        "# DevStudioの登録済み画像検知から追加。再生成時も保持されます。",
        "IMAGE_DETECTION_TARGETS.update(" + pprint.pformat(targets, width=100) + ")",
        # Older generated command sources do not define OPERATORS.  A class
        # body NameError here prevents Commands reload and leaves PokeCon
        # running the previous cached module, so update optional dictionaries
        # only when that generation supports them.
        "if 'IMAGE_DETECTION_OPERATORS' in locals():",
        "    IMAGE_DETECTION_OPERATORS.update(" + pprint.pformat(operators, width=100) + ")",
        "if 'IMAGE_DETECTION_DESCRIPTIONS' in locals():",
        "    IMAGE_DETECTION_DESCRIPTIONS.setdefault('targets', {}).update(" +
        pprint.pformat(descriptions, width=100) + ")",
        LIBRARY_IMPORT_END,
    ]
    return textwrap.indent("\n".join(body), indent)


def _insert_library_import_block(source, block):
    existing = _library_import_match(source)
    if existing:
        return source[:existing.start()] + block + source[existing.end():]
    method = re.search(r"(?m)^(?P<indent>[ \t]*)def _image_check_target\s*\(", source)
    if not method:
        raise ValueError("ソースに生成済みの _image_check_target がありません。先に画像検知をソースへ反映してください。")
    return source[:method.start()] + block + "\n\n" + source[method.start():]


def merge_library_targets_into_source(source, library, names):
    """Add selected library targets without rebuilding existing registrations."""
    targets, operators, descriptions = _managed_import_targets(source)
    added = []
    library_targets = library.get("targets", {}) if isinstance(library, dict) else {}
    for name in names:
        item = library_targets.get(str(name))
        if not isinstance(item, dict) or not item.get("variants"):
            continue
        variants = []
        for variant in item.get("variants", []):
            if not isinstance(variant, dict):
                continue
            clean = dict(variant)
            # Older generated image_check implementations pass settings as-is.
            clean.pop("health_ignored_warnings", None)
            variants.append(clean)
        if not variants:
            continue
        name = str(name)
        targets[name] = variants
        operators[name] = str(item.get("operator", "OR")).upper()
        descriptions[name] = str(item.get("description", ""))
        added.append(name)
    if not added:
        raise ValueError("選択した検知名にはソースへ反映できる登録設定がありません。")

    existing = _library_import_match(source)
    if existing:
        indent = existing.group("indent")
    else:
        method = re.search(r"(?m)^(?P<indent>[ \t]*)def _image_check_target\s*\(", source)
        if not method:
            raise ValueError("ソースに生成済みの _image_check_target がありません。先に画像検知をソースへ反映してください。")
        indent = method.group("indent")
    block = _format_library_import_block(indent, targets, operators, descriptions)
    return _insert_library_import_block(source, block), sorted(set(added), key=str.lower)


def preserve_library_import_block(generated_code, previous_source):
    """Carry DevStudio-added targets through a later full image-code rebuild."""
    match = _library_import_match(previous_source)
    if not match:
        return generated_code
    block = textwrap.dedent(match.group(0))
    return _insert_library_import_block(generated_code, block)
