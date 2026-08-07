#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare and synchronize sample-fragment functions with an open command source."""
from __future__ import print_function

import ast
import os
import re
import textwrap


def _function_records(source, class_only=False):
    tree = ast.parse(source)
    lines = source.splitlines(True)
    nodes = []
    if class_only:
        command = next((node for node in tree.body if isinstance(node, ast.ClassDef)), None)
        if command is None:
            raise ValueError("ソース内にクラスがありません。")
        nodes = [node for node in command.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    else:
        nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    result = {}
    for node in nodes:
        decorator_lines = [item.lineno for item in node.decorator_list]
        start = min(decorator_lines + [node.lineno]) - 1
        end = getattr(node, "end_lineno", None)
        if end is None:
            end = len(lines)
            for index in range(node.lineno, len(lines)):
                value = lines[index]
                stripped = value.strip()
                if not stripped:
                    continue
                indentation = len(value) - len(value.lstrip(" \t"))
                if indentation <= node.col_offset:
                    end = index
                    break
        raw = "".join(lines[start:end])
        normalized = "\n".join(line.rstrip() for line in textwrap.dedent(raw).strip().splitlines())
        result[node.name] = {"name": node.name, "start": start, "end": end,
                             "text": textwrap.dedent(raw).rstrip() + "\n", "normalized": normalized}
    return result


def function_records(source, class_only=False):
    """Public read-only function catalog used by replacement pickers."""
    return _function_records(source, class_only=class_only)


def scan_folder(fragment_root, folder):
    root, folder = os.path.abspath(fragment_root), os.path.abspath(folder)
    if os.path.commonpath([root, folder]) != root:
        raise ValueError("サンプル関数ライブラリ配下のフォルダーを選択してください。")
    found = {}
    for directory, _, names in os.walk(folder):
        for filename in sorted(names):
            if not filename.endswith(".pyfrag"):
                continue
            path = os.path.join(directory, filename)
            with open(path, "r", encoding="utf-8") as stream:
                source = stream.read()
            for name, record in _function_records(source).items():
                item = dict(record); item["path"] = path
                found.setdefault(name, []).append(item)
    return found


def compare_folder(source, fragment_root, folder):
    source_functions = _function_records(source, class_only=True)
    fragment_functions = scan_folder(fragment_root, folder)
    result = []
    for name in sorted(fragment_functions, key=str.lower):
        variants = fragment_functions[name]
        if len(variants) > 1:
            status = "duplicate"
        elif name not in source_functions:
            status = "missing_source"
        elif variants[0]["normalized"] == source_functions[name]["normalized"]:
            status = "match"
        else:
            status = "different"
        result.append({"name": name, "status": status, "fragments": variants,
                       "source": source_functions.get(name)})
    return result


def update_source(source, comparisons, names):
    selected = set(names)
    records = _function_records(source, class_only=True)
    tree = ast.parse(source)
    command = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    lines = source.splitlines(True)
    replacements, additions = [], []
    for item in comparisons:
        if item["name"] not in selected or item["status"] == "duplicate":
            continue
        fragment = item["fragments"][0]["text"]
        block = textwrap.indent(fragment.rstrip(), "    ") + "\n"
        if item["name"] in records:
            record = records[item["name"]]
            replacements.append((record["start"], record["end"], block))
        else:
            additions.append(block)
    for start, end, block in sorted(replacements, reverse=True):
        lines[start:end] = [block]
    if additions:
        insertion = getattr(command, "end_lineno", len(lines))
        lines[insertion:insertion] = ["\n"] + additions
    updated = "".join(lines)
    ast.parse(updated)
    return updated


def replace_class_functions(source, function_texts):
    """Replace existing command-class methods from ``name -> function text``."""
    records = _function_records(source, class_only=True)
    lines = source.splitlines(True)
    replacements = []
    for name, function_text in function_texts.items():
        if name not in records:
            continue
        # Replacement code may be obtained from a differently named specified
        # function. Preserve the selected target method name at the call sites.
        renamed = function_text
        renamed = re.sub(
            r"(?m)^(\s*(?:async\s+)?def\s+)[A-Za-z_]\w*",
            lambda match: match.group(1) + name, renamed, count=1)
        block = textwrap.indent(textwrap.dedent(renamed).rstrip(), "    ") + "\n"
        record = records[name]
        replacements.append((record["start"], record["end"], block))
    for start, end, block in sorted(replacements, reverse=True):
        lines[start:end] = [block]
    updated = "".join(lines)
    ast.parse(updated)
    return updated


def propagate_functions(paths, function_texts):
    """Apply sample/specified functions to every existing same-name method."""
    changed = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as stream:
                source = stream.read()
            encoding = "utf-8"
        except UnicodeDecodeError:
            with open(path, "r", encoding="cp932") as stream:
                source = stream.read()
            encoding = "cp932"
        except OSError:
            continue
        try:
            records = _function_records(source, class_only=True)
        except (SyntaxError, ValueError):
            continue
        applicable = {name: text for name, text in function_texts.items() if name in records}
        if not applicable:
            continue
        updated = replace_class_functions(source, applicable)
        if updated == source:
            continue
        temporary = path + ".function-replace.tmp"
        with open(temporary, "w", encoding=encoding, newline="\n") as stream:
            stream.write(updated)
        os.replace(temporary, path)
        changed.append(path)
    return changed


def update_fragments(source, comparisons, names):
    selected = set(names)
    source_functions = _function_records(source, class_only=True)
    by_path = {}
    for item in comparisons:
        if item["name"] not in selected or item["status"] == "duplicate" or item["name"] not in source_functions:
            continue
        by_path.setdefault(item["fragments"][0]["path"], []).append(item["name"])
    changed = []
    for path, function_names in by_path.items():
        with open(path, "r", encoding="utf-8") as stream:
            fragment_source = stream.read()
        records = _function_records(fragment_source)
        lines = fragment_source.splitlines(True)
        for name in sorted(function_names, key=lambda value: records[value]["start"], reverse=True):
            record = records[name]
            lines[record["start"]:record["end"]] = [source_functions[name]["text"]]
        updated = "".join(lines)
        ast.parse(updated)
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(updated)
        os.replace(temporary, path)
        changed.append(path)
    return changed
