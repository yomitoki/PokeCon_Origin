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


def rename_target(data, old_name, new_name):
    """Rename a registered target and every list member that refers to it."""
    old_name = str(old_name or "").strip()
    new_name = str(new_name or "").strip()
    if not old_name or old_name not in data.get("targets", {}):
        raise ValueError("変更元の画像検知がありません: " + old_name)
    if not new_name:
        raise ValueError("変更後の画像検知名を入力してください。")
    if new_name != old_name and new_name in data.get("targets", {}):
        raise ValueError("変更後の画像検知名は既に登録されています: " + new_name)
    if new_name == old_name:
        return data
    targets = data["targets"]
    renamed = {}
    for name, item in targets.items():
        renamed[new_name if name == old_name else name] = item
    data["targets"] = renamed
    for item in data.get("lists", {}).values():
        for member in item.get("members", []):
            if member.get("type") == "target" and member.get("id") == old_name:
                member["id"] = new_name
    return data


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


def normalized_excluded_folders(value):
    """Return portable, case-insensitive folder prefixes from a UI value."""
    if value is None:
        return ()
    if isinstance(value, str):
        values = value.replace(";", ",").replace("\r", "\n").replace("\n", ",").split(",")
    else:
        try:
            values = list(value)
        except TypeError:
            values = [value]
    output = []
    for item in values:
        folder = str(item or "").strip().replace("\\", "/")
        while folder.startswith("./"):
            folder = folder[2:]
        folder = folder.strip("/").casefold()
        if folder and folder not in output:
            output.append(folder)
    return tuple(output)


def template_path_is_excluded(template_path, excluded_folders):
    """Return whether a template path belongs to an excluded folder."""
    path = str(template_path or "").strip().replace("\\", "/").strip("/").casefold()
    for folder in normalized_excluded_folders(excluded_folders):
        if path == folder or path.startswith(folder + "/"):
            return True
    return False


def image_preview_size(width, height, max_width=480, max_height=220,
                       max_upscale=4.0):
    """Fit an image into the preview area while keeping its aspect ratio."""
    width, height = int(width), int(height)
    max_width, max_height = int(max_width), int(max_height)
    if width <= 0 or height <= 0 or max_width <= 0 or max_height <= 0:
        raise ValueError("Image and preview dimensions must be positive")
    scale = min(float(max_width) / width, float(max_height) / height,
                max(1.0, float(max_upscale)))
    return max(1, int(round(width * scale))), max(1, int(round(height * scale)))


def filter_image_library_variants(data, query="", grayscale="all",
                                  excluded_folders=None):
    """Return ``(target name, variant index)`` rows matching the workspace filters."""
    needle = str(query or "").strip().casefold()
    gray_value = str(grayscale if grayscale is not None else "all").strip().casefold()
    if grayscale is True or gray_value in ("on", "true", "1", "gray", "grayscale", "グレースケール"):
        expected_gray = True
    elif grayscale is False or gray_value in ("off", "false", "0", "color", "カラー"):
        expected_gray = False
    else:
        expected_gray = None

    results = []
    targets = data.get("targets", {}) if isinstance(data, dict) else {}
    for name in sorted(targets, key=str.casefold):
        target = targets.get(name, {})
        if not isinstance(target, dict):
            continue
        variants = target.get("variants", [])
        searchable = [str(name), str(target.get("description", ""))]
        searchable.extend(str(tag) for tag in target.get("tags", []))
        searchable.extend(
            str(variant.get("template_path", ""))
            for variant in variants if isinstance(variant, dict))
        if needle and needle not in " ".join(searchable).casefold():
            continue
        for index, variant in enumerate(variants):
            if not isinstance(variant, dict):
                continue
            if template_path_is_excluded(
                    variant.get("template_path", ""), excluded_folders):
                continue
            # Runtime image detection treats an omitted use_gray as enabled.
            if expected_gray is not None and bool(variant.get("use_gray", True)) != expected_gray:
                continue
            results.append((str(name), index))
    return results


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
        "        detect_settings.pop('health_ignored_warnings', None)",
        "        output_panel = getattr(self, 'IMAGE_DETECTION_OUTPUT_PANEL', None)",
        "        show_value = bool(detect_settings.get('show_value', False) or getattr(self, 'show_value_bool', False))",
        "        if output_panel and show_value:",
        "            detect_settings['show_value'] = False",
        "        try:",
        "            result = detect_image(",
        "                self, name=targetimage,",
        "                history=self._image_similarity_history,",
        "                **detect_settings)",
        "        except RuntimeError as error:",
        "            if \"Cameraの新しい映像を取得できません\" not in str(error):",
        "                raise",
        "            if not getattr(self, '_camera_frame_unavailable_logged', False):",
        "                message = \"Cameraの新しい映像がないため画像検知を待機します。\"",
        "                print(message)",
        "                logger = getattr(self, '_logger', None)",
        "                if logger is not None:",
        "                    logger.warning(message)",
        "                self._camera_frame_unavailable_logged = True",
        "            return False",
        "        if getattr(self, '_camera_frame_unavailable_logged', False):",
        "            logger = getattr(self, '_logger', None)",
        "            if logger is not None:",
        "                logger.info(\"Cameraの映像入力が復帰しました。画像検知を再開します。\")",
        "            self._camera_frame_unavailable_logged = False",
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
        "        matched = bool(self._image_check_target(str(targetimage)))",
        "    else:",
        "        matched = bool(self.image_check_exception(targetimage))",
        "    if matched:",
        "        confirmation = getattr(self, 'image_check_confirmation', None)",
        "        if callable(confirmation):",
        "            return bool(confirmation(targetimage, first_match=True))",
        "    return matched",
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
