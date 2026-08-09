#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate namespaced Pokemon ZA samples from reusable ZA_story methods."""
from __future__ import print_function

import ast
import json
import os
import re


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE_PATH = os.path.join(ROOT, "SerialController", "Commands", "PythonCommands", "ZA", "ZA_story", "ZA_story.py")
FRAGMENT_ROOT = os.path.join(ROOT, "SerialController", "DevTemplates", "Fragments")
ZA_ROOT = os.path.join(FRAGMENT_ROOT, "Pokemon_ZA")
LIST_PATH = os.path.join(FRAGMENT_ROOT, "sample_lists.json")
TAG = "Pokemon_ZA"


def literal_string(node):
    constant_type = getattr(ast, "Constant", ())
    if isinstance(node, constant_type) and isinstance(getattr(node, "value", None), str):
        return node.value
    legacy_type = getattr(ast, "Str", ())
    if isinstance(node, legacy_type) and isinstance(getattr(node, "s", None), str):
        return node.s
    return None


GROUP_PATTERNS = [
    ("ZA_MovementAndEvent", [
        r"sendCommand", r"etc_sendCommand", r"zone_check", r"MOVE_.*", r"ROTOM_GLIDE", r"ZL_ACTION", r"renda_button",
        r"mega_evolution_.*", r"story_Template_.*", r"no_battle_filed_check_HardGaurd",
        r"get_pokemon", r"ball_change", r"EventSkip_plus", r"markerdir",
    ]),
    ("ZA_CommonPokemonManagement", [r"common_.*"]),
    ("ZA_CommonNavigation", [r"Common_.*"]),
    ("ZA_BattleAndRoyale", [r"load_json_with_comments", r"save_sleeps", r"load_zones", r"load_sleeps",
                              r"battle_.*", r"bench_.*", r"quasar_.*", r"za_infi_.*", r"Benchi",
                              r"goto_quasar.*", r"ZA_battle_infi_main", r"DebugLog"]),
]


def method_end(methods, index, total_lines):
    return max(getattr(node, "lineno", methods[index].lineno) for node in ast.walk(methods[index]))


def namespaced(name):
    return name if name.startswith("ZA_") else "ZA_" + name


def replace_method_names(text, mapping):
    for old_name in sorted(mapping, key=len, reverse=True):
        new_name = mapping[old_name]
        text = re.sub(r"(?m)^(\s*def\s+)" + re.escape(old_name) + r"\b", r"\1" + new_name, text)
        text = re.sub(r"\bself\." + re.escape(old_name) + r"\b", "self." + new_name, text)
    return text


def state_initializers(initializer, group_methods, mapping):
    blocks = []
    current_state_names = set()
    for node in initializer.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        targets = [target.attr for target in node.targets if isinstance(target, ast.Attribute) and
                   isinstance(target.value, ast.Name) and target.value.id == "self" and
                   target.attr.startswith("STATE_") and target.attr.endswith("_FUNCTION")]
        if not targets:
            continue
        members = []
        for key, value in zip(node.value.keys, node.value.values):
            state_name = literal_string(key)
            if state_name is not None and isinstance(value, ast.Attribute) and value.attr in group_methods:
                members.append((state_name, mapping[value.attr]))
        if not members:
            continue
        dictionary_name = "ZA_" + targets[0]
        lines = ["self.{} = {{".format(dictionary_name)]
        lines.extend("    {!r}: self.{},".format(key, method) for key, method in members)
        lines.append("}")
        blocks.append("\n".join(lines))
        base = targets[0][len("STATE_"):-len("_FUNCTION")].lower()
        current_state_names.add(base + "_current_state")
    simple_values = {}
    for node in initializer.body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                simple_values[target.attr] = value
    referenced = set()
    for method in group_methods.values() if isinstance(group_methods, dict) else []:
        for node in ast.walk(method):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
                referenced.add(node.attr)
    for attribute in sorted(referenced | current_state_names):
        if attribute in simple_values:
            blocks.append("self.ZA_{} = {!r}".format(attribute, simple_values[attribute]))
    return "\n".join(blocks)


def rewrite_instance_attributes(text, simple_attributes, state_attributes=None):
    for attribute in sorted(simple_attributes, key=len, reverse=True):
        text = re.sub(r"\bself\." + re.escape(attribute) + r"\b", "self.ZA_" + attribute, text)
    for attribute in sorted(state_attributes or [], key=len, reverse=True):
        text = re.sub(r"\bself\." + re.escape(attribute) + r"\b", "self.ZA_" + attribute, text)
    return text


def main():
    with open(SOURCE_PATH, "r", encoding="utf-8") as stream:
        source = stream.read()
    lines = source.splitlines(True)
    tree = ast.parse(source)
    command = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ZA_story_Base")
    initializer = next(node for node in command.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    methods = [node for node in command.body if isinstance(node, ast.FunctionDef)]
    by_name = {node.name: node for node in methods}
    assigned = {}
    for group_name, patterns in GROUP_PATTERNS:
        selected = []
        for method in methods:
            if any(re.fullmatch(pattern, method.name) for pattern in patterns):
                if method.name in assigned:
                    raise RuntimeError("Method assigned twice: " + method.name)
                assigned[method.name] = group_name
                selected.append(method.name)
        if not selected:
            raise RuntimeError("Empty ZA sample group: " + group_name)
    mapping = {name: namespaced(name) for name in assigned}
    simple_attributes = set()
    state_attributes = set()
    for node in initializer.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self" and target.attr.startswith("STATE_"):
                    state_attributes.add(target.attr)
            try:
                ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                    if not target.attr.startswith("STATE_"):
                        simple_attributes.add(target.attr)
    generated = []
    for group_name, _ in GROUP_PATTERNS:
        selected_nodes = [node for node in methods if assigned.get(node.name) == group_name]
        bodies = []
        for node in selected_nodes:
            index = methods.index(node)
            segment = "".join(lines[node.lineno - 1:method_end(methods, index, len(lines))])
            segment = "\n".join(line[4:] if line.startswith("    ") else line for line in segment.splitlines())
            bodies.append(segment.rstrip())
        body = replace_method_names("\n\n".join(bodies) + "\n", mapping)
        body = rewrite_instance_attributes(body, simple_attributes, state_attributes)
        ast.parse(body)
        group_method_nodes = {node.name: node for node in selected_nodes}
        initializer_text = state_initializers(initializer, group_method_nodes, mapping)
        initializer_text = replace_method_names(initializer_text, mapping)
        initializer_text = rewrite_instance_attributes(initializer_text, simple_attributes, state_attributes)
        directory = os.path.join(ZA_ROOT, group_name)
        os.makedirs(directory, exist_ok=True)
        fragment_name = group_name + ".pyfrag"
        with open(os.path.join(directory, fragment_name), "w", encoding="utf-8", newline="\n") as stream:
            stream.write(body)
        metadata = {
            "schema_version": 1,
            "name": group_name,
            "tags": [TAG],
            "imports": ["import enum", "import json", "import os", "import time"],
            "class_variables": [],
            "initializer": initializer_text,
            "fragment": fragment_name,
        }
        with open(os.path.join(directory, group_name + ".pokesample.json"), "w", encoding="utf-8", newline="\n") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        generated.append((group_name, len(selected_nodes)))
    with open(LIST_PATH, "r", encoding="utf-8") as stream:
        library = json.load(stream)
    lists = library.setdefault("lists", {})
    fragment_id = lambda name: "Pokemon_ZA/{0}/{0}.pokesample.json".format(name)
    lists["Pokemon_ZA_MovementAndEvent"] = {"tags": [TAG], "members": [{"type": "fragment", "id": fragment_id("ZA_MovementAndEvent")}]}
    lists["Pokemon_ZA_Common"] = {"tags": [TAG], "members": [
        {"type": "list", "id": "Pokemon_ZA_MovementAndEvent"},
        {"type": "fragment", "id": fragment_id("ZA_CommonPokemonManagement")},
        {"type": "fragment", "id": fragment_id("ZA_CommonNavigation")},
    ]}
    lists["Pokemon_ZA_BattleAndRoyale"] = {"tags": [TAG], "members": [
        {"type": "list", "id": "Pokemon_ZA_Common"},
        {"type": "fragment", "id": fragment_id("ZA_BattleAndRoyale")},
    ]}
    lists["Pokemon_ZA_AllReusable"] = {"tags": [TAG], "members": [
        {"type": "list", "id": "Pokemon_ZA_BattleAndRoyale"},
        {"type": "fragment", "id": "Pokemon_ZA/ZA_state_machine_step/ZA_state_machine_step.pokesample.json"},
        {"type": "fragment", "id": "Pokemon_ZA/ZA_image_check_helpers/ZA_image_check_helpers.pokesample.json"},
        {"type": "fragment", "id": "Pokemon_ZA/ZA_switch_input/ZA_switch_input.pokesample.json"},
        {"type": "fragment", "id": "Pokemon_ZA/ZA_common_flow/ZA_common_flow.pokesample.json"},
    ]}
    temporary = LIST_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(library, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, LIST_PATH)
    print("Generated " + ", ".join("{}={}".format(name, count) for name, count in generated))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
