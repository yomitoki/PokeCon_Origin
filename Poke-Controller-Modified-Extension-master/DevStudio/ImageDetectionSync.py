#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bidirectional comparison helpers for generated image-detection settings."""
from __future__ import print_function

import ast


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
    except (KeyError, ValueError, TypeError):
        raise ValueError("ソースにIMAGE_DETECTION_TARGETSがありません。")
    if not isinstance(targets, dict):
        raise ValueError("IMAGE_DETECTION_TARGETSの形式が正しくありません。")
    try: operators = ast.literal_eval(assignments["IMAGE_DETECTION_OPERATORS"])
    except (KeyError, ValueError, TypeError): operators = {}
    try: descriptions = ast.literal_eval(assignments["IMAGE_DETECTION_DESCRIPTIONS"])
    except (KeyError, ValueError, TypeError): descriptions = {}
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
