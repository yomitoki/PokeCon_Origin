#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare and safely reflect sample-list functions back to origin Commands."""
from __future__ import print_function

import ast
import datetime
import json
import os
import shutil
import textwrap

from SampleFunctionSync import function_records, update_source
from SampleLibrary import load_fragment, normalize_library, resolve_members
from SourceFunctionTools import rename_source_functions


def _read_source(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as stream:
            return stream.read(), "utf-8-sig"
    except UnicodeDecodeError:
        with open(path, "r", encoding="cp932") as stream:
            return stream.read(), "cp932"


def _normalized(value):
    tree = ast.parse(textwrap.dedent(str(value)))
    function = next((node for node in tree.body
                     if isinstance(node, (ast.FunctionDef,
                                          ast.AsyncFunctionDef))), None)
    if function is None:
        raise ValueError("サンプル関数コードではありません。")
    return ast.dump(function, annotate_fields=True, include_attributes=False)


def _resolve_origin_path(path, fragment_root):
    value = str(path or "").strip()
    if not value:
        return ""
    if os.path.isabs(value):
        return os.path.abspath(value)
    candidates = [os.path.abspath(value)]
    current = os.path.abspath(fragment_root)
    while True:
        candidates.append(os.path.abspath(os.path.join(current, value)))
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return next((candidate for candidate in candidates
                 if os.path.isfile(candidate)), candidates[0])


def _fragment_function(body, name):
    records = function_records(body, class_only=False)
    if name not in records:
        raise ValueError("サンプル内に指定関数がありません: " + str(name))
    return records[name]["text"]


def compare_sample_list_origins(fragment_root, data, list_name):
    """Return one comparison row per function-scoped origin binding."""
    normalized_data = normalize_library(data)
    list_origin_path = normalized_data["lists"].get(
        list_name, {}).get("origin_path", "")
    rows = []
    for index, member in enumerate(resolve_members(normalized_data, list_name)):
        function_name = str(member.get("function", "")).strip()
        if not function_name:
            continue
        metadata, body, _metadata_path, body_path = load_fragment(
            fragment_root, member["id"])
        fragment_records = function_records(body, class_only=False)
        sample_text = _fragment_function(body, function_name)
        origin = metadata.get("source", {})
        origin_path = _resolve_origin_path(
            member.get("origin_path") or list_origin_path or
            origin.get("path", ""),
            fragment_root)
        metadata_function = str(origin.get("function", ""))
        origin_function = str(member.get("origin_function") or (
            metadata_function if metadata_function and
            (len(fragment_records) == 1 or
             str(metadata.get("name", "")) == function_name)
            else function_name))
        comparison_text = sample_text
        if function_name != origin_function:
            comparison_text = rename_source_functions(
                comparison_text, {function_name: origin_function},
                require_definitions=False)
        key = "{}|{}|{}|{}".format(
            os.path.normcase(origin_path), origin_function,
            member["id"], index)
        row = {
            "key": key, "sample_name": function_name,
            "sample_id": member["id"], "sample_path": body_path,
            "sample_text": sample_text, "comparison_text": comparison_text,
            "origin_path": origin_path, "origin_function": origin_function,
            "source_text": "", "status": "missing_origin",
        }
        if origin_path and os.path.isfile(origin_path):
            try:
                source, _encoding = _read_source(origin_path)
                records = function_records(source, class_only=True)
                row["source_text"] = (
                    records[origin_function]["text"]
                    if origin_function in records else "")
                row["status"] = (
                    "missing_source" if origin_function not in records else
                    ("match" if _normalized(row["source_text"]) ==
                     _normalized(comparison_text) else "different"))
            except (OSError, SyntaxError, ValueError) as error:
                row["status"] = "invalid_origin"
                row["error"] = str(error)
        rows.append(row)

    bindings = {}
    for row in rows:
        if not row["origin_path"]:
            continue
        binding = (os.path.normcase(row["origin_path"]),
                   row["origin_function"])
        bindings.setdefault(binding, []).append(row)
    for variants in bindings.values():
        if len(variants) < 2:
            continue
        bodies = {_normalized(row["comparison_text"]) for row in variants}
        if len(bodies) > 1:
            for row in variants:
                row["status"] = "binding_conflict"
        else:
            for row in variants[1:]:
                row["status"] = "duplicate_binding"
    return rows


def _create_backup(paths, backup_root, list_name):
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    directory = os.path.abspath(os.path.join(backup_root, stamp))
    os.makedirs(directory, exist_ok=False)
    entries = []
    for index, path in enumerate(sorted(paths, key=str.casefold), 1):
        backup = os.path.join(
            directory, "{:04d}_{}.bak".format(index, os.path.basename(path)))
        shutil.copy2(path, backup)
        entries.append({"path": path, "backup": backup})
    manifest = {
        "created": stamp, "sample_list": str(list_name), "files": entries}
    manifest_path = os.path.join(directory, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    manifest["manifest_path"] = manifest_path
    return manifest


def apply_sample_list_to_origins(comparisons, selected_keys, backup_root,
                                 list_name=""):
    """Reflect selected whole functions to origin files with atomic rollback."""
    selected = set(selected_keys)
    rows = [row for row in comparisons if row["key"] in selected]
    blocked = [row for row in rows if row["status"] in (
        "missing_origin", "invalid_origin", "binding_conflict")]
    if blocked:
        raise ValueError(
            "登録元へ反映できない関数があります: " + ", ".join(
                row["origin_function"] for row in blocked))
    applicable = [row for row in rows if row["status"] in (
        "different", "missing_source")]
    by_path = {}
    seen = set()
    for row in applicable:
        binding = (os.path.normcase(row["origin_path"]),
                   row["origin_function"])
        if binding in seen:
            continue
        seen.add(binding)
        by_path.setdefault(row["origin_path"], []).append(row)
    if not by_path:
        return {"changed": [], "functions": 0, "backup": None}

    planned, encodings, originals = {}, {}, {}
    for path, path_rows in by_path.items():
        source, encoding = _read_source(path)
        synthetic = []
        for row in path_rows:
            synthetic.append({
                "name": row["origin_function"], "status": row["status"],
                "fragments": [{
                    "comparison_text": row["comparison_text"],
                    "text": row["comparison_text"]}],
            })
        updated = update_source(
            source, synthetic,
            [row["origin_function"] for row in path_rows])
        ast.parse(updated)
        planned[path] = updated
        encodings[path] = encoding
        originals[path] = source

    backup = _create_backup(planned, backup_root, list_name)
    replaced = []
    try:
        for path, updated in planned.items():
            temporary = path + ".sample-origin-sync.tmp"
            with open(temporary, "w", encoding=encodings[path],
                      newline="\n") as stream:
                stream.write(updated)
            os.replace(temporary, path)
            replaced.append(path)
    except Exception:
        for path in replaced:
            temporary = path + ".sample-origin-sync-rollback.tmp"
            with open(temporary, "w", encoding=encodings[path],
                      newline="\n") as stream:
                stream.write(originals[path])
            os.replace(temporary, path)
        raise
    return {
        "changed": sorted(planned, key=str.casefold),
        "functions": sum(len(rows) for rows in by_path.values()),
        "backup": backup,
    }


def restore_origin_sync_backup(manifest_path):
    """Restore every Commands source recorded by an origin-sync backup."""
    with open(manifest_path, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    planned, originals = {}, {}
    for entry in manifest.get("files", []):
        path = os.path.abspath(entry["path"])
        with open(entry["backup"], "rb") as stream:
            planned[path] = stream.read()
        with open(path, "rb") as stream:
            originals[path] = stream.read()
    replaced = []
    try:
        for path, content in planned.items():
            temporary = path + ".sample-origin-sync-restore.tmp"
            with open(temporary, "wb") as stream:
                stream.write(content)
            os.replace(temporary, path)
            replaced.append(path)
    except Exception:
        for path in replaced:
            temporary = path + ".sample-origin-sync-restore-rollback.tmp"
            with open(temporary, "wb") as stream:
                stream.write(originals[path])
            os.replace(temporary, path)
        raise
    return manifest
