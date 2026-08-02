#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data and composition helpers for the Dev Studio sample library."""
from __future__ import print_function

import ast
import json
import os


SCHEMA_VERSION = 2


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
                    members.append({"type": member["type"], "id": str(member["id"])})
            result["lists"][str(name)] = {
                "tags": [str(tag) for tag in item.get("tags", []) if str(tag).strip()],
                "members": members,
            }
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
    for member in resolve_members(data, list_name):
        metadata, body, _, _ = load_fragment(fragment_root, member["id"])
        imports.extend(metadata.get("imports", []))
        variables.extend(metadata.get("class_variables", []))
        initializer = metadata.get("initializer", "")
        if str(initializer).strip():
            initializers.append(str(initializer).rstrip())
        bodies.append(body.rstrip())
        included.append(metadata.get("name", member["id"]))
    return {
        "imports": list(dict.fromkeys(imports)),
        "class_variables": list(dict.fromkeys(variables)),
        "initializers": initializers,
        "bodies": bodies,
        "included": included,
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
            argument = node.args[0]
            if isinstance(argument, ast.Str):
                name = argument.s
            elif isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                name = argument.value
            else:
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
