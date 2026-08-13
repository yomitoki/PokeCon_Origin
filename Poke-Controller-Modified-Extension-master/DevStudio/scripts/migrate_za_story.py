#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-time, repeatable migration of ZA_story to DevStudio image profiles."""
from __future__ import print_function

import ast
import io
import os
import sys
import tokenize


DEV_STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(DEV_STUDIO)
if DEV_STUDIO not in sys.path:
    sys.path.insert(0, DEV_STUDIO)

from ImageDetectionLibrary import generate_image_check, load_library, save_library


SOURCE_PATH = os.path.join(ROOT, "SerialController", "Commands", "PythonCommands", "ZA", "ZA_story", "ZA_story.py")
PROFILE_PATH = os.path.join(ROOT, "SerialController", "Template", "image_detection_profiles.json")
TAG = "Pokemon_ZA"
PREFIX = "POKEMON_ZA_"
SPECIAL_NAMES = {
    "TRUE_RETURN": "POKEMON_ZA_TRUE_RETURN",
    "FALSE_RETURN": "POKEMON_ZA_FALSE_RETURN",
    "Filed_Hard_Check_0": "POKEMON_ZA_FILED_HARD_CHECK_0",
    "Filed_Hard_Check_1": "POKEMON_ZA_FILED_HARD_CHECK_1",
    "no_battle_filed_check_Hard_Check": "POKEMON_ZA_NO_BATTLE_FIELD_HARD_CHECK",
    "ZONE12": "POKEMON_ZA_ZONE12",
}


def literal_string(node):
    constant_type = getattr(ast, "Constant", ())
    if isinstance(node, constant_type) and isinstance(getattr(node, "value", None), str):
        return node.value
    legacy_type = getattr(ast, "Str", ())
    if isinstance(node, legacy_type) and isinstance(getattr(node, "s", None), str):
        return node.s
    return None


def image_check_node(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "image_check":
            return node
    raise RuntimeError("image_check was not found")


def branch_names(test):
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq):
        values = [test.left] + list(test.comparators)
        return [text for text in (literal_string(value) for value in values) if text is not None]
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
        output = []
        for value in test.values:
            output.extend(branch_names(value))
        return output
    return []


def direct_branches(function):
    for top_level in function.body:
        first = top_level if isinstance(top_level, ast.If) and branch_names(top_level.test) else None
        while first is not None:
            yield first
            first = first.orelse[0] if len(first.orelse) == 1 and isinstance(first.orelse[0], ast.If) else None


def literal_keyword(call, name, default):
    value = next((keyword.value for keyword in call.keywords if keyword.arg == name), None)
    if value is None:
        return default
    try:
        return ast.literal_eval(value)
    except (ValueError, TypeError):
        return default


def collect_profiles(source):
    tree = ast.parse(source)
    function = image_check_node(tree)
    profiles = {}
    for branch in direct_branches(function):
        names = branch_names(branch.test)
        calls = [node for statement in branch.body for node in ast.walk(statement) if isinstance(node, ast.Call) and
                 ((isinstance(node.func, ast.Attribute) and node.func.attr.startswith("isContainTemplateUltra")) or
                  (isinstance(node.func, ast.Name) and node.func.id.startswith("isContainTemplateUltra")))]
        if not calls:
            continue
        call = calls[0]
        template_path = str(literal_keyword(call, "template_path", "")).replace("\\", "/")
        template_path = "Template/" + template_path.lstrip("/")
        variant = {
            "template_path": template_path,
            "threshold": float(literal_keyword(call, "threshold", 0.8)),
            "use_gray": bool(literal_keyword(call, "use_gray", True)),
            "show_value": bool(literal_keyword(call, "show_value", False)),
            "show_position": bool(literal_keyword(call, "show_position", True)),
            "show_only_true_rect": bool(literal_keyword(call, "show_only_true_rect", False)),
            "ms": int(literal_keyword(call, "ms", 2000)),
            "crop": list(literal_keyword(call, "crop", [])),
        }
        for old_name in names:
            if old_name not in SPECIAL_NAMES:
                profiles.setdefault(old_name, []).append(variant)
    return function, profiles


def rename_exact_string_literals(source, mapping):
    tokens = []
    reader = io.StringIO(source).readline
    for token in tokenize.generate_tokens(reader):
        if token.type == tokenize.STRING:
            try:
                value = ast.literal_eval(token.string)
            except (ValueError, SyntaxError):
                value = None
            if isinstance(value, str) and value in mapping:
                quote = '"' if token.string.startswith('"') else "'"
                escaped = mapping[value].replace("\\", "\\\\").replace(quote, "\\" + quote)
                token = tokenize.TokenInfo(token.type, quote + escaped + quote, token.start, token.end, token.line)
        tokens.append(token)
    return tokenize.untokenize(tokens)


def register_profiles(profiles):
    library = load_library(PROFILE_PATH)
    folder_members = {}
    all_members = []
    for old_name, variants in sorted(profiles.items()):
        name = PREFIX + old_name
        library["targets"][name] = {
            "description": "Pokemon ZA image detection migrated from ZA_story: " + old_name,
            "operator": "OR",
            "tags": [TAG],
            "variants": variants,
        }
        member = {"type": "target", "id": name}
        all_members.append(member)
        folder = os.path.dirname(variants[0]["template_path"]).replace("Template/ZA_Story/", "").replace("Template/ZA_Story", "ROOT")
        folder_members.setdefault(folder or "ROOT", []).append(member)
    child_members = []
    for folder, members in sorted(folder_members.items()):
        safe = "".join(character if character.isalnum() else "_" for character in folder.upper()).strip("_") or "ROOT"
        set_name = "POKEMON_ZA_FOLDER_" + safe
        library["lists"][set_name] = {
            "description": "Pokemon ZA image detections under " + folder,
            "members": members,
        }
        child_members.append({"type": "list", "id": set_name})
    library["lists"]["POKEMON_ZA_ALL"] = {
        "description": "All registered Pokemon ZA image detections grouped by template folder.",
        "members": child_members,
    }
    save_library(PROFILE_PATH, library)
    return library


def replace_image_check(source, library):
    tree = ast.parse(source)
    function = image_check_node(tree)
    generated = generate_image_check(library, "POKEMON_ZA_ALL", "list")
    exception = '''def image_check_exception(self, targetimage):
    """Handle Pokemon ZA checks that do not use a template image."""
    if targetimage in ("POKEMON_ZA_TRUE_RETURN", "TRUE_RETURN", "RETURN_TRUE", "RETURN TRUE"):
        return True
    if targetimage in ("POKEMON_ZA_FALSE_RETURN", "FALSE_RETURN", "RETURN_FALSE", "RETURN FALSE"):
        return False
    if targetimage == "POKEMON_ZA_FILED_HARD_CHECK_0":
        return bool(self.story_Template_Field_HardGaurd())
    if targetimage == "POKEMON_ZA_FILED_HARD_CHECK_1":
        return bool(self.story_Template_Field_HardGaurd(mode=1))
    if targetimage == "POKEMON_ZA_NO_BATTLE_FIELD_HARD_CHECK":
        return bool(self.no_battle_filed_check_HardGaurd())
    if targetimage == "POKEMON_ZA_ZONE12":
        return True
    # POKECON_IMAGE_CHECK_EXCEPTION_USER_BEGIN
    # Add command-specific non-image checks here.
    # POKECON_IMAGE_CHECK_EXCEPTION_USER_END
    return False'''
    start = generated.index("def image_check_exception")
    end = generated.index("# POKECON_IMAGE_CHECK_USER_END", start)
    generated = generated[:start] + exception + "\n" + generated[end:]
    indented = "\n".join(("    " + line) if line else "" for line in generated.rstrip().splitlines()) + "\n"
    lines = source.splitlines(True)
    start_offset = sum(len(line) for line in lines[:function.lineno - 1])
    next_method = source.find("\n    def ", start_offset + 1)
    end_offset = len(source) if next_method < 0 else next_method + 1
    return source[:start_offset] + indented + source[end_offset:]


def add_import(source):
    statement = "from LocalFunction.ImageDetection import SimilarityHistory, detect_image\n"
    if statement.strip() in source:
        return source
    marker = "from Commands.PythonCommandBase import ImageProcPythonCommand\n"
    return source.replace(marker, marker + statement, 1)


def remove_class_methods(source, method_names):
    """Remove obsolete methods by AST start line and the following method boundary."""
    tree = ast.parse(source)
    lines = source.splitlines(True)
    targets = []
    for class_node in [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]:
        methods = [node for node in class_node.body if isinstance(node, ast.FunctionDef)]
        for index, method in enumerate(methods):
            if method.name not in method_names:
                continue
            start = method.lineno - 1
            end = methods[index + 1].lineno - 1 if index + 1 < len(methods) else len(lines)
            targets.append((start, end))
    for start, end in sorted(targets, reverse=True):
        del lines[start:end]
    return "".join(lines), len(targets)


def cleanup_obsolete_code(source):
    source, removed = remove_class_methods(
        source, {"_legacy_Benchi", "isContainTemplateUltra", "isContainTemplateUltra_get_max_val"})
    dead_start = source.find("        # Kept unreachable only for compatibility with old source comparisons.")
    if dead_start >= 0:
        dead_end = source.find("    ######################################################\n    # Command", dead_start)
        if dead_end >= 0:
            source = source[:dead_start] + source[dead_end:]
            removed += 1
    return source, removed


def main():
    with open(SOURCE_PATH, "r", encoding="utf-8-sig", newline="") as stream:
        source = stream.read().replace("\r\n", "\n")
    if "# POKECON_IMAGE_CHECK_BEGIN" not in source:
        function, profiles = collect_profiles(source)
        if len(profiles) < 200:
            raise RuntimeError("Expected at least 200 image profiles, found {}".format(len(profiles)))
        mapping = {name: PREFIX + name for name in profiles}
        mapping.update(SPECIAL_NAMES)
        source = rename_exact_string_literals(source, mapping)
        library = register_profiles(profiles)
        source = replace_image_check(source, library)
        source = add_import(source)
        print("Migrated {} image targets and {} special checks".format(len(profiles), len(SPECIAL_NAMES)))
    source, removed = cleanup_obsolete_code(source)
    with open(SOURCE_PATH, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(source)
    print("Removed {} obsolete ZA_story block(s)".format(removed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
