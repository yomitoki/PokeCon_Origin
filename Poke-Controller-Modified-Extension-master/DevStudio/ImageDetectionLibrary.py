#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persistent image-detection profiles, nested lists and source generation."""
from __future__ import print_function

import json
import os
import pprint


SCHEMA_VERSION = 1


def empty_library():
    return {"schema_version": SCHEMA_VERSION, "targets": {}, "lists": {}}


def load_library(path):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, ValueError):
        return empty_library()
    result = empty_library()
    if not isinstance(value, dict):
        return result
    for name, item in value.get("targets", {}).items():
        if not isinstance(item, dict):
            continue
        result["targets"][str(name)] = {
            "description": str(item.get("description", "")),
            "operator": str(item.get("operator", "OR")).strip().upper()
            if str(item.get("operator", "OR")).strip().upper() in ("AND", "OR") else "OR",
            "tags": [str(tag) for tag in item.get("tags", []) if str(tag).strip()],
            "variants": [dict(variant) for variant in item.get("variants", []) if isinstance(variant, dict)],
        }
    for name, item in value.get("lists", {}).items():
        if not isinstance(item, dict):
            continue
        members = []
        for member in item.get("members", []):
            if isinstance(member, dict) and member.get("type") in ("target", "list") and member.get("id"):
                members.append({"type": member["type"], "id": str(member["id"])})
        result["lists"][str(name)] = {
            "description": str(item.get("description", "")),
            "members": members,
        }
    return result


def save_library(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def folder_tags(template_root, image_path):
    try:
        relative = os.path.relpath(os.path.dirname(os.path.abspath(image_path)), os.path.abspath(template_root))
        if relative.startswith(".."):
            return []
        return [part for part in relative.replace("\\", "/").split("/") if part and part != "."]
    except ValueError:
        return []


def resolve_list(data, list_name):
    output = []

    def visit(name, stack):
        if name in stack:
            raise ValueError("画像検知リストが循環しています: " + " -> ".join(stack + [name]))
        if name not in data["lists"]:
            raise ValueError("画像検知リストがありません: " + name)
        for member in data["lists"][name]["members"]:
            if member["type"] == "list":
                visit(member["id"], stack + [name])
            elif member["id"] not in output:
                output.append(member["id"])

    visit(list_name, [])
    return output


def selected_targets(data, name, selection_type="list"):
    names = resolve_list(data, name) if selection_type == "list" else [name]
    return {target_name: data["targets"][target_name]["variants"] for target_name in names if target_name in data["targets"]}


def generate_image_check(data, name, selection_type="list"):
    targets = selected_targets(data, name, selection_type)
    operators = {target_name: data["targets"].get(target_name, {}).get("operator", "OR") for target_name in targets}
    descriptions = {
        "targets": {target_name: str(data["targets"].get(target_name, {}).get("description", "")) for target_name in targets},
    }
    lines = [
        "# POKECON_IMAGE_CHECK_BEGIN",
        "# Generated image detection selection: {}:{}".format(selection_type, name),
        "IMAGE_DETECTION_TARGETS = " + pprint.pformat(targets, width=120),
        "IMAGE_DETECTION_OPERATORS = " + pprint.pformat(operators, width=120),
        "IMAGE_DETECTION_DESCRIPTIONS = " + pprint.pformat(descriptions, width=120),
        "",
        "def _image_check_target(self, targetimage):",
        "    variants = self.IMAGE_DETECTION_TARGETS.get(str(targetimage), [])",
        "    if not hasattr(self, '_image_similarity_history'):",
        "        self._image_similarity_history = SimilarityHistory()",
        "    results = []",
        "    for settings in variants:",
        "        detect_settings = dict(settings)",
        "        output_panel = getattr(self, 'IMAGE_DETECTION_OUTPUT_PANEL', None)",
        "        show_value = bool(detect_settings.get('show_value', False) or getattr(self, 'show_value_bool', False))",
        "        if output_panel and show_value:",
        "            detect_settings['show_value'] = False",
        "        result = detect_image(self, name=targetimage, history=self._image_similarity_history, **detect_settings)",
        "        self.last_image_detection = result",
        "        if output_panel and show_value:",
        "            self.show_output(output_panel, text=(\"{} ZNCC value: {:.6f} / threshold: {:.6f} {}\".format(",
        "                targetimage, result['score'], result['threshold'], 'MATCH' if result['matched'] else 'NO MATCH')))",
        "        results.append(bool(result['matched']))",
        "    if not results:",
        "        return False",
        "    operator = self.IMAGE_DETECTION_OPERATORS.get(str(targetimage), 'OR')",
        "    return all(results) if operator == 'AND' else any(results)",
        "",
        "def image_check(self, targetimage, nocheckflag=1):",
        "    # nocheckflag=0 is the test-output skip used by existing commands.",
        "    if nocheckflag == 0:",
        "        return False",
        "    if str(targetimage) in self.IMAGE_DETECTION_TARGETS:",
        "        return bool(self._image_check_target(str(targetimage)))",
        "    return bool(self.image_check_exception(targetimage))",
        "# POKECON_IMAGE_CHECK_GENERATED_END",
        "",
        "# POKECON_IMAGE_CHECK_USER_BEGIN",
        "def image_check_exception(self, targetimage):",
        "    # 未登録名や標準パターンで一致しない場合の例外判定をここへ追加します。",
        "    # この領域は画像検知設定を再反映しても保持されます。",
        "    return False",
        "# POKECON_IMAGE_CHECK_USER_END",
        "# POKECON_IMAGE_CHECK_END",
    ]
    return "\n".join(lines) + "\n"
