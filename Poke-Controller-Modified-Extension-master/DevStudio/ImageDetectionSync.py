#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bidirectional comparison helpers for generated image-detection settings."""
from __future__ import print_function

import ast


def _literal_dict(node, default=None):
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return {} if default is None else default
    return value if isinstance(value, dict) else ({} if default is None else default)


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _apply_literal_updates(tree, targets, operators, descriptions):
    """Apply generated/managed ``dict.update`` blocks without executing source."""
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "update" and node.args
    ]
    calls.sort(key=lambda node: (
        int(getattr(node, "lineno", 1)),
        int(getattr(node, "col_offset", 0))))
    for call in calls:
        values = _literal_dict(call.args[0])
        if not values:
            continue
        owner = call.func.value
        container = _name(owner)
        if container == "IMAGE_DETECTION_TARGETS":
            targets.update(values)
        elif container == "IMAGE_DETECTION_OPERATORS":
            operators.update(values)
        elif container == "IMAGE_DETECTION_DESCRIPTIONS":
            descriptions.update(values)
        elif isinstance(owner, ast.Call) \
                and isinstance(owner.func, ast.Attribute) \
                and owner.func.attr == "setdefault" \
                and _name(owner.func.value) == "IMAGE_DETECTION_DESCRIPTIONS" \
                and owner.args:
            try:
                section = ast.literal_eval(owner.args[0])
            except (ValueError, TypeError, SyntaxError):
                continue
            if section == "targets":
                descriptions.setdefault("targets", {}).update(values)


def parse_source_settings(source):
    tree = ast.parse(source)
    assignments = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            name = getattr(target, "id", "")
            if name.startswith("IMAGE_DETECTION_"):
                assignments[name] = node.value
    try:
        targets = ast.literal_eval(assignments["IMAGE_DETECTION_TARGETS"])
    except (KeyError, ValueError, TypeError, SyntaxError):
        raise ValueError("ソースにIMAGE_DETECTION_TARGETSがありません。")
    if not isinstance(targets, dict):
        raise ValueError("IMAGE_DETECTION_TARGETSの形式が正しくありません。")
    operators = _literal_dict(
        assignments.get("IMAGE_DETECTION_OPERATORS"), {})
    descriptions = _literal_dict(
        assignments.get("IMAGE_DETECTION_DESCRIPTIONS"), {})
    _apply_literal_updates(
        tree, targets, operators, descriptions)
    result = {}
    for name, variants in targets.items():
        if not isinstance(variants, list):
            continue
        result[str(name)] = {
            "description": str(descriptions.get("targets", {}).get(str(name), "")),
            "operator": str(operators.get(str(name), "OR")).upper(),
            "variants": [dict(item) for item in variants if isinstance(item, dict)],
        }
    return result


def compare_settings(source_settings, library):
    result = []
    source_names, library_names = set(source_settings), set(library.get("targets", {}))
    for name in sorted(source_names | library_names, key=str.lower):
        source_item, library_item = source_settings.get(name), library.get("targets", {}).get(name)
        if source_item is None:
            status = "library_only"
        elif library_item is None:
            status = "source_only"
        else:
            comparable_library = {
                "description": str(library_item.get("description", "")),
                "operator": str(library_item.get("operator", "OR")).upper(),
                "variants": library_item.get("variants", []),
            }
            status = "match" if source_item == comparable_library else "different"
        result.append({"name": name, "status": status, "source": source_item, "library": library_item})
    return result


def update_library_from_source(library, source_settings, names):
    updated = set(names)
    for name in updated:
        if name not in source_settings:
            continue
        old = library["targets"].get(name, {})
        source_item = source_settings[name]
        library["targets"][name] = {
            "description": source_item["description"],
            "operator": source_item["operator"],
            "tags": list(old.get("tags", [])),
            "variants": [dict(item) for item in source_item["variants"]],
        }
    return library
