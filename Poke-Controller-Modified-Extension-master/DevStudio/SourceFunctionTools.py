#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safe helpers for source-function discovery, bulk rename and sample import."""
from __future__ import print_function

import ast
import datetime
import hashlib
import io
import json
import keyword
import os
import re
import textwrap
import tokenize

from PythonSourceSafety import normalize_python_indentation


IDENTIFIER_RE = re.compile(r"^[A-Za-z_]\w*$")


def normalized_function_text(value):
    """Normalize one function for stable, function-scoped history hashes."""
    return "\n".join(
        line.rstrip() for line in
        textwrap.dedent(str(value or "")).strip().splitlines())


def function_content_hash(value):
    """Return a hash that changes only when this function body changes."""
    return hashlib.sha256(
        normalized_function_text(value).encode("utf-8")).hexdigest()


def function_sync_record(source_function, function_text, synced_at=None):
    """Build the common-ancestor record used by sample/source comparison."""
    if synced_at is None:
        synced_at = datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds")
    return {
        "source_function": str(source_function),
        "base_hash": function_content_hash(function_text),
        "synced_at": str(synced_at),
    }


def classify_function_registration(expected_text, candidates, target_name):
    """Classify function-level registrations, including multi-function files."""
    candidates = list(candidates or [])
    expected_hash = function_content_hash(expected_text)
    exact = [item for item in candidates
             if function_content_hash(item.get("text", "")) == expected_hash]
    overwrite_supported = bool(
        len(candidates) == 1 and
        candidates[0].get("metadata", {}).get("name") == str(target_name))
    if len(candidates) == 1 and exact:
        status = "登録済み"
        fragment_id = candidates[0].get("id", "")
    elif len(candidates) == 1:
        status = "処理差あり"
        fragment_id = candidates[0].get("id", "")
    elif len(candidates) > 1:
        status = "同名複数"
        fragment_id = exact[0].get("id", "") if len(exact) == 1 else ""
    else:
        status = "未登録"
        fragment_id = ""
    return {
        "status": status,
        "fragment_id": fragment_id,
        "overwrite_supported": overwrite_supported,
        "candidate_count": len(candidates),
        "exact_count": len(exact),
    }


def _node_end_line(node, lines):
    end = getattr(node, "end_lineno", None)
    if end is not None:
        return end
    for index in range(node.lineno, len(lines)):
        value = lines[index]
        stripped = value.strip()
        if stripped and not stripped.startswith("#") and \
                len(value) - len(value.lstrip(" \t")) <= node.col_offset:
            return index
    return len(lines)


def _dedent_node_text(raw, node, source_lines):
    """Remove only the function's structural indent, ignoring comments."""
    definition_line = source_lines[node.lineno - 1]
    prefix = definition_line[:node.col_offset]
    if not prefix:
        return raw
    return "".join(
        line[len(prefix):] if line.startswith(prefix) else line
        for line in raw.splitlines(True))


def source_function_records(source):
    """Return methods in the first class, or top-level functions as fallback."""
    tree = ast.parse(source)
    lines = source.splitlines(True)
    command = next((node for node in tree.body if isinstance(node, ast.ClassDef)), None)
    nodes = ([node for node in command.body
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
             if command is not None else
             [node for node in tree.body
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))])
    records = []
    for node in nodes:
        decorator_lines = [item.lineno for item in node.decorator_list]
        start = min(decorator_lines + [node.lineno]) - 1
        end = _node_end_line(node, lines)
        raw = "".join(lines[start:end])
        records.append({
            "name": node.name,
            "line": node.lineno,
            "start": start,
            "end": end,
            "text": _dedent_node_text(raw, node, lines),
            "async": isinstance(node, ast.AsyncFunctionDef),
        })
    return records


def step_function_names(source):
    """Return functions used as state-machine or generated Step handlers."""
    tree = ast.parse(source)
    command = next((node for node in tree.body if isinstance(node, ast.ClassDef)), None)
    scope = command if command is not None else tree
    names = set()

    generated_step_command = any(
        isinstance(node, (ast.Assign, ast.AnnAssign)) and any(
            isinstance(target, ast.Name) and target.id in ("STEP_LABELS", "STEP_KEYS")
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))
        for node in getattr(scope, "body", []))
    if generated_step_command:
        names.update(
            node.name for node in getattr(scope, "body", [])
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
            (node.name.startswith("_step_") or node.name.startswith("_special_")))

    for node in ast.walk(scope):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or \
                not isinstance(node.value, ast.Dict):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        is_state_dictionary = any(
            isinstance(target, ast.Attribute) and
            isinstance(target.value, ast.Name) and target.value.id == "self" and
            target.attr.startswith("STATE_") and target.attr.endswith("_FUNCTION")
            for target in targets)
        if not is_state_dictionary:
            continue
        for value in node.value.values:
            if isinstance(value, ast.Attribute) and \
                    isinstance(value.value, ast.Name) and value.value.id == "self":
                names.add(value.attr)
    return names


def build_rename_map(names, find_text="", replace_text="", prefix="", suffix="",
                     whole_name=False):
    """Build and validate a deterministic old-name -> new-name preview."""
    result = {}
    for name in names:
        changed = str(name)
        if find_text and whole_name:
            if changed == str(find_text):
                changed = str(replace_text)
        elif find_text:
            changed = changed.replace(str(find_text), str(replace_text))
        changed = str(prefix) + changed + str(suffix)
        if not IDENTIFIER_RE.match(changed) or keyword.iskeyword(changed):
            raise ValueError("Python関数名として使用できません: {}".format(changed))
        result[str(name)] = changed
    duplicates = sorted(name for name in set(result.values())
                        if list(result.values()).count(name) > 1)
    if duplicates:
        raise ValueError("変更後の関数名が重複しています: " + ", ".join(duplicates))
    return result


def _rename_positions(source, mapping, require_definitions=True):
    tree = ast.parse(source)
    records = source_function_records(source)
    available = {item["name"] for item in records}
    missing = sorted(set(mapping) - available)
    if missing and require_definitions:
        raise ValueError("ソースに関数がありません: " + ", ".join(missing))
    untouched = available - set(mapping)
    defined_values = {value for name, value in mapping.items() if name in available}
    collisions = sorted(defined_values & untouched)
    if collisions:
        raise ValueError("既存の関数名と重複します: " + ", ".join(collisions))
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("変更後の関数名が重複しています。")
    for name in mapping.values():
        if not IDENTIFIER_RE.match(name) or keyword.iskeyword(name):
            raise ValueError("Python関数名として使用できません: {}".format(name))

    name_positions = {
        (node.lineno, node.col_offset): node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in mapping
    }
    definition_lines = {item["line"]: item["name"] for item in records
                        if item["name"] in mapping}
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    replacements = []
    previous = None
    for token in tokens:
        if token.type == tokenize.NAME and token.string in mapping:
            rename = False
            if definition_lines.get(token.start[0]) == token.string and \
                    previous is not None and previous.string == "def":
                rename = True
            elif previous is not None and previous.string == ".":
                rename = True
            elif (token.start[0], token.start[1]) in name_positions:
                rename = True
            if rename:
                replacements.append((token.start, token.end, mapping[token.string]))
        if token.type not in (tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE,
                              tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT):
            previous = token
    return replacements


def rename_source_functions(source, mapping, require_definitions=True):
    """Rename selected definitions and executable references without touching text."""
    mapping = {str(old): str(new) for old, new in mapping.items() if str(old) != str(new)}
    if not mapping:
        return source
    replacements = _rename_positions(
        source, mapping, require_definitions=require_definitions)
    lines = source.splitlines(True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def absolute(position):
        row, column = position
        return offsets[row - 1] + column

    updated = source
    for start, end, value in sorted(
            ((absolute(start), absolute(end), value) for start, end, value in replacements),
            reverse=True):
        updated = updated[:start] + value + updated[end:]
    ast.parse(updated)
    return updated


def source_imports(source):
    tree = ast.parse(source)
    lines = source.splitlines(True)
    values = []
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        end = getattr(node, "end_lineno", None)
        if end is None:
            end = node.lineno
            balance = 0
            while end <= len(lines):
                line = lines[end - 1]
                balance += sum(line.count(mark) for mark in "([{")
                balance -= sum(line.count(mark) for mark in ")]}")
                if balance <= 0 and not line.rstrip().endswith("\\"):
                    break
                end += 1
        value = "".join(lines[node.lineno - 1:end]).strip()
        if value and value not in values:
            values.append(value)
    return values


def register_source_functions(source, names, fragment_root, folder="SourceImports",
                              rename_map=None, tags=None, overwrite=False,
                              source_path=""):
    """Create one editable sample fragment per selected source function."""
    records = {item["name"]: item for item in source_function_records(source)}
    selected = [str(name) for name in names]
    missing = sorted(set(selected) - set(records))
    if missing:
        raise ValueError("ソースに関数がありません: " + ", ".join(missing))
    rename_map = dict(rename_map or {})
    final_names = build_rename_map([rename_map.get(name, name) for name in selected])
    final_names = {old: final_names[rename_map.get(old, old)] for old in selected}
    if len(set(final_names.values())) != len(final_names):
        raise ValueError("登録後の関数名が重複しています。")

    root = os.path.abspath(fragment_root)
    relative_folder = str(folder or "SourceImports").replace("\\", "/").strip("/")
    if any(part in ("", ".", "..") for part in relative_folder.split("/")):
        raise ValueError("保存先にはサンプルライブラリ内のフォルダー名を指定してください。")
    target_root = os.path.abspath(os.path.join(root, *relative_folder.split("/")))
    if os.path.commonpath([root, target_root]) != root:
        raise ValueError("保存先がサンプルライブラリ外です。")

    existing_by_name = {}
    if os.path.isdir(root):
        for directory, _, filenames in os.walk(root):
            for filename in filenames:
                if not filename.endswith(".pokesample.json"):
                    continue
                metadata_path = os.path.join(directory, filename)
                try:
                    with open(metadata_path, "r", encoding="utf-8") as stream:
                        metadata = json.load(stream)
                    existing_by_name.setdefault(str(metadata.get("name", "")), []).append(
                        (metadata, metadata_path))
                except (OSError, ValueError):
                    continue

    planned = []
    for old_name in selected:
        final_name = final_names[old_name]
        existing = existing_by_name.get(final_name, [])
        if len(existing) > 1:
            raise ValueError("同名サンプルが複数あります: {}".format(final_name))
        if existing:
            existing_metadata, metadata_path = existing[0]
            sample_dir = os.path.dirname(metadata_path)
            body_path = os.path.join(
                sample_dir, existing_metadata.get("fragment", final_name + ".pyfrag"))
        else:
            existing_metadata = {}
            sample_dir = os.path.join(target_root, final_name)
            metadata_path = os.path.join(sample_dir, final_name + ".pokesample.json")
            body_path = os.path.join(sample_dir, final_name + ".pyfrag")
        if not overwrite and (existing or os.path.exists(metadata_path) or os.path.exists(body_path)):
            raise FileExistsError("登録済みです: {}".format(final_name))
        planned.append((old_name, final_name, sample_dir, metadata_path, body_path,
                        existing_metadata))

    imports = source_imports(source)
    saved_tags = list(dict.fromkeys(str(tag).strip() for tag in (tags or []) if str(tag).strip()))
    created = []
    for old_name, final_name, sample_dir, metadata_path, body_path, existing_metadata in planned:
        body = normalize_python_indentation(records[old_name]["text"])
        # The extracted block has no competing functions, so this safely also
        # updates recursive self.old_name() references inside the sample.
        if any(old != new for old, new in final_names.items()):
            body = rename_source_functions(
                body, final_names, require_definitions=False)
        metadata = dict(existing_metadata)
        function_sync = dict(metadata.get("function_sync", {}))
        function_sync[final_name] = function_sync_record(
            old_name, records[old_name]["text"])
        metadata.update({
            "schema_version": 1,
            "name": final_name,
            "tags": list(dict.fromkeys(list(metadata.get("tags", [])) + saved_tags)),
            "imports": list(dict.fromkeys(list(metadata.get("imports", [])) + imports)),
            "class_variables": list(metadata.get("class_variables", [])),
            "fragment": os.path.basename(body_path),
            "source": {"path": str(source_path or ""), "function": old_name},
            "function_sync": function_sync,
        })
        os.makedirs(sample_dir, exist_ok=True)
        temporary_metadata = metadata_path + ".tmp"
        temporary_body = body_path + ".tmp"
        with open(temporary_metadata, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        with open(temporary_body, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(body.rstrip() + "\n")
        os.replace(temporary_metadata, metadata_path)
        os.replace(temporary_body, body_path)
        created.append({
            "old_name": old_name,
            "name": final_name,
            "id": os.path.relpath(metadata_path, root).replace("\\", "/"),
            "metadata_path": metadata_path,
            "body_path": body_path,
        })
    return created
