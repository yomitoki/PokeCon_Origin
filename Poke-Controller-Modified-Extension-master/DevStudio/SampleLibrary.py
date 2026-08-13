#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data and composition helpers for the Dev Studio sample library."""
from __future__ import print_function

import ast
import json
import os


SCHEMA_VERSION = 2


def _node_end_line(node, lines):
    end = getattr(node, "end_lineno", None)
    if end is not None:
        return end
    compound_nodes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                      ast.If, ast.For, ast.While, ast.Try, ast.With)
    if not isinstance(node, compound_nodes):
        balance = 0
        for index in range(node.lineno - 1, len(lines)):
            value = lines[index]
            balance += sum(value.count(mark) for mark in "([{")
            balance -= sum(value.count(mark) for mark in ")]}")
            if balance <= 0 and not value.rstrip().endswith("\\"):
                return index + 1
        return len(lines)
    header_end = node.lineno - 1
    balance = 0
    for index in range(node.lineno - 1, len(lines)):
        value = lines[index]
        balance += sum(value.count(mark) for mark in "([{")
        balance -= sum(value.count(mark) for mark in ")]}")
        if balance <= 0 and value.rstrip().endswith(":"):
            header_end = index
            break
    for index in range(header_end + 1, len(lines)):
        value = lines[index]
        stripped = value.strip()
        if stripped and not stripped.startswith("#") and \
                len(value) - len(value.lstrip(" \t")) <= node.col_offset:
            return index
    return len(lines)


def _literal_string(node):
    """Return a string AST literal across Python 3.7 through 3.14."""
    constant_type = getattr(ast, "Constant", ())
    if isinstance(node, constant_type) and isinstance(getattr(node, "value", None), str):
        return node.value
    legacy_type = getattr(ast, "Str", ())
    if isinstance(node, legacy_type) and isinstance(getattr(node, "s", None), str):
        return node.s
    return None


def empty_library():
    return {"schema_version": SCHEMA_VERSION, "lists": {}}


def normalize_library(value):
    """Return schema v2 data, migrating the original name -> [path] mapping."""
    if not isinstance(value, dict):
        return empty_library()
    if value.get("schema_version") == SCHEMA_VERSION and isinstance(value.get("lists"), dict):
        result = empty_library()
        for name, item in value["lists"].items():
            if not isinstance(item, dict):
                item = {"members": item if isinstance(item, list) else []}
            members = []
            for member in item.get("members", []):
                if isinstance(member, str):
                    member = {"type": "fragment", "id": member}
                if isinstance(member, dict) and member.get("type") in ("fragment", "list") and member.get("id"):
                    normalized_member = {
                        "type": member["type"], "id": str(member["id"])}
                    if member["type"] == "fragment" and member.get("function"):
                        normalized_member["function"] = str(member["function"])
                    if member["type"] == "fragment" and member.get("origin_path"):
                        normalized_member["origin_path"] = str(member["origin_path"])
                    if member["type"] == "fragment" and member.get("origin_function"):
                        normalized_member["origin_function"] = str(
                            member["origin_function"])
                    members.append(normalized_member)
            result["lists"][str(name)] = {
                "tags": [str(tag) for tag in item.get("tags", []) if str(tag).strip()],
                "members": members,
            }
            if item.get("origin_path"):
                result["lists"][str(name)]["origin_path"] = str(
                    item["origin_path"])
        return result
    result = empty_library()
    for name, members in value.items():
        if isinstance(members, list):
            result["lists"][str(name)] = {
                "tags": [],
                "members": [{"type": "fragment", "id": str(member)} for member in members],
            }
    return result


def load_library(path):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            return normalize_library(json.load(stream))
    except (OSError, ValueError):
        return empty_library()


def save_library(path, data):
    data = normalize_library(data)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def catalog(fragment_root):
    result = []
    if not os.path.isdir(fragment_root):
        return result
    for directory, dirs, names in os.walk(fragment_root):
        dirs[:] = sorted(dirs)
        for name in sorted(names):
            if not name.endswith(".pokesample.json"):
                continue
            path = os.path.join(directory, name)
            try:
                with open(path, "r", encoding="utf-8") as stream:
                    item = json.load(stream)
                if not isinstance(item, dict):
                    continue
                item["id"] = os.path.relpath(path, fragment_root).replace("\\", "/")
                item["folder"] = os.path.relpath(directory, fragment_root).replace("\\", "/")
                result.append(item)
            except (OSError, ValueError):
                continue
    return result


def resolve_members(data, list_name):
    """Flatten nested lists, preserving order and rejecting cycles."""
    data = normalize_library(data)
    lists = data["lists"]
    output = []

    def visit(name, stack):
        if name in stack:
            raise ValueError("Sample-list cycle: " + " -> ".join(stack + [name]))
        if name not in lists:
            raise ValueError("Unknown sample list: " + name)
        for member in lists[name]["members"]:
            if member["type"] == "list":
                visit(member["id"], stack + [name])
            elif member not in output:
                output.append(member)

    visit(list_name, [])
    return output


def load_fragment(fragment_root, fragment_id):
    root = os.path.abspath(fragment_root)
    metadata_path = os.path.abspath(os.path.join(root, fragment_id))
    if os.path.commonpath([root, metadata_path]) != root:
        raise ValueError("Fragment path is outside the library")
    with open(metadata_path, "r", encoding="utf-8") as stream:
        metadata = json.load(stream)
    body_path = os.path.abspath(os.path.join(os.path.dirname(metadata_path), metadata["fragment"]))
    if os.path.commonpath([root, body_path]) != root:
        raise ValueError("Fragment body is outside the library")
    with open(body_path, "r", encoding="utf-8") as stream:
        body = stream.read()
    return metadata, body, metadata_path, body_path


def compose_preview(fragment_root, data, list_name):
    imports, variables, initializers, bodies, included = [], [], [], [], []
    external_variables = []
    members = resolve_members(data, list_name)
    dependency_support = False
    for member in members:
        if member.get("function"):
            continue
        metadata, _body, _, _ = load_fragment(fragment_root, member["id"])
        if metadata.get("dependency_group"):
            dependency_support = True
            break
    for member in members:
        metadata, body, _, _ = load_fragment(fragment_root, member["id"])
        external_variables.extend(metadata.get("external_class_variables", []))
        external_variables.extend(
            metadata.get("dependency_group", {}).get(
                "external_class_variables", []))
        function_name = str(member.get("function", "")).strip()
        # A dependency-group support fragment contains the exact imports and
        # initialization for the whole group.  Function-scoped references then
        # contribute only their selected function body; importing their parent
        # fragment metadata would reintroduce unrelated state and duplicates.
        body_only = bool(function_name and dependency_support)
        if not body_only:
            imports.extend(metadata.get("imports", []))
            variables.extend(metadata.get("class_variables", []))
            initializer = metadata.get("initializer", "")
            if str(initializer).strip():
                initializers.append(str(initializer).rstrip())
        if function_name:
            tree = ast.parse(body)
            node = next((value for value in tree.body
                         if isinstance(value, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                         value.name == function_name), None)
            if node is None:
                raise ValueError(
                    "サンプル内に指定関数がありません: {} / {}".format(
                        member["id"], function_name))
            lines = body.splitlines(True)
            selected_body = "".join(
                lines[node.lineno - 1:_node_end_line(node, lines)])
            bodies.append(selected_body.rstrip())
            included.append(function_name)
        elif body.strip() and not body.lstrip().startswith("# Support settings"):
            bodies.append(body.rstrip())
            included.append(metadata.get("name", member["id"]))
    return {
        "imports": list(dict.fromkeys(imports)),
        "class_variables": list(dict.fromkeys(variables)),
        "initializers": initializers,
        "bodies": bodies,
        "included": included,
        "external_class_variables": list(dict.fromkeys(external_variables)),
        "image_targets": image_targets_from_bodies(bodies),
    }


def image_targets_from_bodies(bodies):
    """Return literal image_check target names used by sample functions."""
    targets = []
    for body in bodies:
        try:
            tree = ast.parse(body)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            function = node.func
            is_image_check = ((isinstance(function, ast.Attribute) and function.attr == "image_check") or
                              (isinstance(function, ast.Name) and function.id == "image_check"))
            if not is_image_check:
                continue
            name = _literal_string(node.args[0])
            if name is None:
                continue
            if name not in targets:
                targets.append(name)
    return targets


def detect_conflicts(source, preview):
    conflicts = []
    for line in preview["imports"]:
        if line and line not in source:
            conflicts.append("import will be added: " + line)
    for line in preview["class_variables"]:
        name = line.split("=", 1)[0].strip()
        if name and any(existing.strip().startswith(name + " =") or existing.strip().startswith(name + "=") for existing in source.splitlines()):
            conflicts.append("class variable already exists: " + name)
    for name in preview["included"]:
        marker = "@pokedev-fragment: " + name
        if marker in source:
            conflicts.append("fragment already present: " + name)
    return conflicts


def merge_preview(source, preview, list_name):
    """Merge imports, class variables and bodies after review by the caller."""
    lines = source.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (lines[insert_at].startswith("#!") or
                                      "coding" in lines[insert_at] or
                                      lines[insert_at].strip().startswith("#") or
                                      not lines[insert_at].strip()):
        insert_at += 1
    missing_imports = [line for line in preview["imports"] if line not in lines]
    if missing_imports:
        lines[insert_at:insert_at] = missing_imports + [""]
    class_index = next((index for index, line in enumerate(lines) if line.startswith("class ")), None)
    if class_index is not None:
        variable_lines = []
        for value in preview["class_variables"]:
            name = value.split("=", 1)[0].strip()
            exists = any(line.strip().startswith(name + " =") or line.strip().startswith(name + "=") for line in lines)
            if not exists:
                variable_lines.append("    " + value)
        if variable_lines:
            lines[class_index + 1:class_index + 1] = variable_lines + [""]
    block = ["", "# POKECON_SAMPLE_LIST_BEGIN " + list_name]
    for body in preview["bodies"]:
        block.extend(body.rstrip().splitlines())
        block.append("")
    block.append("# POKECON_SAMPLE_LIST_END " + list_name)
    lines.extend(block)
    return "\n".join(lines).rstrip() + "\n"
