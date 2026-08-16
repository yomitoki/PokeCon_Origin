#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare and synchronize sample-fragment functions with an open command source."""
from __future__ import print_function

import ast
import datetime
import difflib
import json
import os
import re
import textwrap

from SourceFunctionTools import (function_content_hash, function_sync_record,
                                 rename_source_functions)
from PythonSourceSafety import normalize_python_indentation


def _changed_character_spans(left, right):
    left_spans, right_spans = [], []
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        if left_end > left_start:
            left_spans.append((left_start, left_end))
        if right_end > right_start:
            right_spans.append((right_start, right_end))
    return left_spans, right_spans


def side_by_side_diff_rows(left_text, right_text):
    """Return aligned WinMerge-style rows with character-level differences."""
    left_lines = str(left_text or "").splitlines()
    right_lines = str(right_text or "").splitlines()
    rows = []
    left_number = right_number = 1

    def append(left="", right="", kind="equal", left_exists=True,
               right_exists=True):
        nonlocal left_number, right_number
        left_spans, right_spans = ([], [])
        if kind != "equal":
            left_spans, right_spans = _changed_character_spans(left, right)
        rows.append({
            "left": left, "right": right, "kind": kind,
            "left_line": left_number if left_exists else None,
            "right_line": right_number if right_exists else None,
            "left_spans": left_spans, "right_spans": right_spans,
        })
        if left_exists:
            left_number += 1
        if right_exists:
            right_number += 1

    matcher = difflib.SequenceMatcher(
        None, left_lines, right_lines, autojunk=False)
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            for left, right in zip(
                    left_lines[left_start:left_end],
                    right_lines[right_start:right_end]):
                append(left, right)
        elif tag == "delete":
            for left in left_lines[left_start:left_end]:
                append(left=left, kind="delete", right_exists=False)
        elif tag == "insert":
            for right in right_lines[right_start:right_end]:
                append(right=right, kind="insert", left_exists=False)
        else:
            left_block = left_lines[left_start:left_end]
            right_block = right_lines[right_start:right_end]
            count = max(len(left_block), len(right_block))
            for index in range(count):
                left_exists = index < len(left_block)
                right_exists = index < len(right_block)
                append(
                    left_block[index] if left_exists else "",
                    right_block[index] if right_exists else "",
                    "replace" if left_exists and right_exists else
                    ("delete" if left_exists else "insert"),
                    left_exists, right_exists)
    return rows


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
                if not stripped or stripped.startswith("#"):
                    continue
                indentation = len(value) - len(value.lstrip(" \t"))
                if indentation <= node.col_offset:
                    end = index
                    break
        raw = "".join(lines[start:end])
        # Older ZA sources contain comment-only lines indented less than the
        # surrounding method.  textwrap.dedent() treats those comments as the
        # minimum indent and can leave the extracted ``def`` indented.  Strip
        # the method's actual structural prefix instead.
        definition_line = lines[node.lineno - 1]
        prefix = definition_line[:node.col_offset]
        extracted = "".join(
            line[len(prefix):] if prefix and line.startswith(prefix) else line
            for line in raw.splitlines(True))
        normalized = "\n".join(
            line.rstrip() for line in extracted.strip().splitlines())
        result[node.name] = {"name": node.name, "start": start, "end": end,
                             "text": extracted.rstrip() + "\n",
                             "normalized": normalized}
    return result


def function_records(source, class_only=False):
    """Public read-only function catalog used by replacement pickers."""
    return _function_records(source, class_only=class_only)


def replace_fragment_function_text(fragment_source, function_name,
                                   replacement_text):
    """Replace one top-level sample function and validate the whole fragment."""
    records = _function_records(fragment_source, class_only=False)
    if function_name not in records:
        raise ValueError("サンプル関数が見つかりません: " + str(function_name))
    replacement_text = normalize_python_indentation(replacement_text)
    replacement_records = _function_records(
        str(replacement_text), class_only=False)
    if list(replacement_records) != [function_name]:
        raise ValueError(
            "編集欄には同じ名前の関数を1つだけ残してください: " +
            str(function_name))
    record = records[function_name]
    lines = fragment_source.splitlines(True)
    replacement = str(replacement_text).rstrip() + "\n"
    lines[record["start"]:record["end"]] = [replacement]
    updated = normalize_python_indentation("".join(lines))
    ast.parse(updated)
    return updated


def remove_fragment_function_text(fragment_source, function_name):
    """Remove one top-level function while preserving the rest of a fragment."""
    records = _function_records(fragment_source, class_only=False)
    if function_name not in records:
        raise ValueError("サンプル関数が見つかりません: " + str(function_name))
    record = records[function_name]
    lines = fragment_source.splitlines(True)
    del lines[record["start"]:record["end"]]
    updated = "".join(lines)
    ast.parse(updated)
    return updated


def reflect_fragment_function_text(source_function_text, source_function_name,
                                   target_fragment_source,
                                   target_function_name):
    """Replace a target sample function with one source sample function.

    This is a directional whole-function replacement, not a line merge.  The
    target function name is kept so existing references in its fragment remain
    valid.
    """
    replacement = str(source_function_text)
    if source_function_name != target_function_name:
        replacement = rename_source_functions(
            replacement,
            {str(source_function_name): str(target_function_name)},
            require_definitions=True)
    return replace_fragment_function_text(
        target_fragment_source, target_function_name, replacement)


def merge_fragment_function_text(source_function_text, source_function_name,
                                 target_fragment_source,
                                 target_function_name):
    """Backward-compatible alias for directional sample reflection."""
    return reflect_fragment_function_text(
        source_function_text, source_function_name,
        target_fragment_source, target_function_name)


def fragment_function_stats(fragment_source, function_name):
    """Return function count and executable references to one sample method."""
    records = _function_records(fragment_source, class_only=False)
    tree = ast.parse(fragment_source)
    references = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == function_name:
            references += 1
        elif isinstance(node, ast.Name) and node.id == function_name:
            # Function definition names are strings on FunctionDef and are not
            # represented as ast.Name, so these are executable references.
            references += 1
    return {
        "function_count": len(records),
        "reference_count": references,
    }


def resolve_fragment_folder(fragment_root, folder):
    """Resolve a requested comparison folder without scanning outside samples.

    Selecting the project root is a common way to ask for every registered
    sample.  Treat any ancestor of the fragment library as the library root,
    while still rejecting an unrelated directory.
    """
    root = os.path.abspath(fragment_root)
    requested = os.path.abspath(folder or root)
    try:
        common = os.path.commonpath([root, requested])
    except ValueError:
        common = ""
    if common == root:
        return requested
    if common == requested:
        return root
    raise ValueError("サンプル関数ライブラリ配下のフォルダーを選択してください。")


def source_paths_equivalent(saved_path, current_path):
    """Match a recorded origin after a workspace/drive relocation."""
    saved = str(saved_path or "").strip()
    current = str(current_path or "").strip()
    if not saved or not current:
        return False
    if os.path.normcase(os.path.abspath(saved)) == \
            os.path.normcase(os.path.abspath(current)):
        return True

    def portable_suffix(value):
        normalized = value.replace("\\", "/").strip().casefold()
        marker = "serialcontroller/"
        index = normalized.rfind(marker)
        return normalized[index:] if index >= 0 else ""

    saved_suffix = portable_suffix(saved)
    current_suffix = portable_suffix(current)
    return bool(saved_suffix) and saved_suffix == current_suffix


def function_update_status(source_text, sample_text, base_hash="",
                           source_unsaved=False):
    """Classify changes against the last function-scoped synchronization."""
    source_hash = (function_content_hash(source_text)
                   if source_text is not None else "")
    sample_hash = (function_content_hash(sample_text)
                   if sample_text is not None else "")
    base_hash = str(base_hash or "")
    if not source_hash:
        status = "source_missing"
    elif source_hash == sample_hash:
        status = "synchronized"
    elif not base_hash:
        status = "unknown_history"
    elif source_hash == base_hash and sample_hash != base_hash:
        status = "sample_newer"
    elif sample_hash == base_hash and source_hash != base_hash:
        status = "source_newer"
    else:
        status = "both_changed"
    return {
        "status": status,
        "base_hash": base_hash,
        "source_hash": source_hash,
        "sample_hash": sample_hash,
        "source_unsaved": bool(source_unsaved),
    }


def format_function_update_status(update):
    """Return an honest function-scoped update label for the comparison UI."""
    update = update or {}
    status = update.get("status", "unknown_history")
    if status == "source_newer":
        return ("未保存ソース関数が新しい（同期後にソース側のみ変更）"
                if update.get("source_unsaved") else
                "ソース関数が新しい（同期後にソース側のみ変更）")
    if status == "sample_newer":
        return "サンプル関数が新しい（同期後にサンプル側のみ変更）"
    if status == "synchronized":
        return "同期済み（関数内容が同じ）"
    if status == "both_changed":
        return "判定不能（同期後に両方変更）"
    if status == "source_missing":
        return "ソース関数が未登録"
    if status == "mixed":
        return "判定混在（重複サンプルを個別確認）"
    return "判定不能（関数単位の同期履歴なし）"


def scan_folder(fragment_root, folder):
    root = os.path.abspath(fragment_root)
    folder = resolve_fragment_folder(root, folder)
    metadata_by_fragment = {}
    metadata_path_by_fragment = {}
    for directory, _, names in os.walk(folder):
        for filename in names:
            if not filename.endswith(".pokesample.json"):
                continue
            metadata_path = os.path.join(directory, filename)
            try:
                with open(metadata_path, "r", encoding="utf-8") as stream:
                    metadata = json.load(stream)
                body_path = os.path.abspath(os.path.join(
                    directory, str(metadata.get("fragment", ""))))
                metadata_by_fragment[body_path] = metadata
                metadata_path_by_fragment[body_path] = metadata_path
            except (OSError, ValueError, TypeError):
                continue
    found = {}
    for directory, _, names in os.walk(folder):
        for filename in sorted(names):
            if not filename.endswith(".pyfrag"):
                continue
            path = os.path.join(directory, filename)
            with open(path, "r", encoding="utf-8") as stream:
                source = stream.read()
            records = _function_records(source)
            metadata = metadata_by_fragment.get(os.path.abspath(path), {})
            origin = metadata.get("source", {}) if isinstance(metadata, dict) else {}
            function_sync = (metadata.get("function_sync", {})
                             if isinstance(metadata, dict) else {})
            for name, record in records.items():
                source_name = name
                if isinstance(origin, dict) and origin.get("function") and \
                        (len(records) == 1 or str(metadata.get("name", "")) == name):
                    source_name = str(origin["function"])
                comparison_text = record["text"]
                if source_name != name:
                    comparison_text = rename_source_functions(
                        comparison_text, {name: source_name},
                        require_definitions=False)
                item = dict(record)
                item.update({
                    "path": path,
                    "sample_name": name,
                    "source_name": source_name,
                    "source_path": str(origin.get("path", ""))
                    if isinstance(origin, dict) else "",
                    "metadata_path": metadata_path_by_fragment.get(
                        os.path.abspath(path), ""),
                    "function_sync": dict(function_sync.get(name, {}))
                    if isinstance(function_sync, dict) and
                    isinstance(function_sync.get(name), dict) else {},
                    "comparison_text": comparison_text,
                    "comparison_normalized": "\n".join(
                        line.rstrip() for line in
                        textwrap.dedent(comparison_text).strip().splitlines()),
                })
                found.setdefault(source_name, []).append(item)
    return found


def _linked_function_sync_metadata_updates(fragment_path, entries):
    """Build metadata writes for function baselines linked to one fragment."""
    updates = {}
    directory = os.path.dirname(os.path.abspath(fragment_path))
    for filename in os.listdir(directory):
        if not filename.endswith(".pokesample.json"):
            continue
        metadata_path = os.path.join(directory, filename)
        try:
            with open(metadata_path, "r", encoding="utf-8") as stream:
                metadata = json.load(stream)
            linked_body = os.path.abspath(os.path.join(
                directory, str(metadata.get("fragment", ""))))
        except (OSError, ValueError, TypeError):
            continue
        if linked_body != os.path.abspath(fragment_path):
            continue
        history = dict(metadata.get("function_sync", {}))
        for sample_name, source_name, canonical_text in entries:
            history[str(sample_name)] = function_sync_record(
                source_name, canonical_text)
        metadata["function_sync"] = history
        updates[metadata_path] = (
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8")
    return updates


def _apply_atomic_updates(planned_updates, temporary_suffix):
    originals = {}
    for path in planned_updates:
        with open(path, "rb") as stream:
            originals[path] = stream.read()
    replaced = []
    try:
        for path, content in planned_updates.items():
            temporary = path + temporary_suffix
            with open(temporary, "wb") as stream:
                stream.write(content)
            os.replace(temporary, path)
            replaced.append(path)
    except Exception:
        for path in replaced:
            temporary = path + temporary_suffix + ".rollback"
            with open(temporary, "wb") as stream:
                stream.write(originals[path])
            os.replace(temporary, path)
        raise


def source_paths_for_folder(fragment_root, folder):
    """Return existing origin source paths recorded by samples in a folder."""
    paths = set()
    for variants in scan_folder(fragment_root, folder).values():
        for item in variants:
            path = str(item.get("source_path", "")).strip()
            if path and os.path.isfile(path):
                paths.add(os.path.abspath(path))
    return sorted(paths, key=str.casefold)


def _is_namespace_prefix_rename(sample_name, source_name):
    """Allow safe namespace prefixes such as ``ZA_``, not semantic names."""
    suffix = "_" + str(source_name)
    if not str(sample_name).endswith(suffix):
        return False
    prefix = str(sample_name)[:-len(suffix)]
    return bool(prefix) and prefix.upper() == prefix and bool(
        re.match(r"^[A-Z][A-Z0-9_]*$", prefix))


def comparison_source_text(selected_path, editor_path="", editor_source="",
                           editor_dirty=False):
    """Return comparison text from an unsaved editor or the current disk.

    An unsaved editor remains authoritative for function-reflection previews.
    A clean editor may be stale after another tool updates the file, so a
    re-check reads the selected source from disk in that case.
    """
    selected_abs = os.path.abspath(str(selected_path))
    editor_abs = os.path.abspath(str(editor_path)) if editor_path else ""
    same_file = bool(editor_abs) and (
        os.path.normcase(selected_abs) == os.path.normcase(editor_abs))
    if same_file and editor_dirty:
        return str(editor_source), "editor"
    with open(selected_abs, "r", encoding="utf-8-sig") as stream:
        return stream.read(), "disk"


def save_reflected_source(source_path, source):
    """Validate and atomically persist a sample-reflected Python source."""
    requested_path = str(source_path or "").strip()
    if not requested_path:
        raise ValueError("反映先ソースの保存先が指定されていません。")
    path = os.path.abspath(requested_path)
    source = str(source)
    ast.parse(source, filename=path)
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        raise OSError("反映先ソースのフォルダーがありません: " + parent)

    original = None
    if os.path.isfile(path):
        with open(path, "rb") as stream:
            original = stream.read()
    temporary = path + ".sample-source-save.tmp"
    replaced = False
    try:
        with open(temporary, "w", encoding="utf-8", newline="") as stream:
            stream.write(source)
        os.replace(temporary, path)
        replaced = True
        with open(path, "r", encoding="utf-8-sig", newline="") as stream:
            saved = stream.read()
        if saved != source:
            raise OSError("反映先ソースの保存後検証に失敗しました: " + path)
    except Exception:
        try:
            if replaced:
                if original is None:
                    os.remove(path)
                else:
                    rollback = path + ".sample-source-rollback.tmp"
                    with open(rollback, "wb") as stream:
                        stream.write(original)
                    os.replace(rollback, path)
            elif os.path.isfile(temporary):
                os.remove(temporary)
        except OSError:
            pass
        raise
    return path


def compare_folder(source, fragment_root, folder, source_path="",
                   source_unsaved=False):
    source_functions = _function_records(source, class_only=True)
    fragment_functions = scan_folder(fragment_root, folder)
    result = []
    for recorded_name in sorted(fragment_functions, key=str.lower):
        variants = fragment_functions[recorded_name]
        if source_path:
            variants = [
                item for item in variants
                if not item.get("source_path") or
                source_paths_equivalent(
                    item.get("source_path"), source_path)]
            if not variants:
                continue
        name = recorded_name
        if name not in source_functions:
            sample_name = variants[0].get("sample_name", recorded_name)
            suffix_matches = [
                source_name for source_name in source_functions
                if sample_name == source_name or
                _is_namespace_prefix_rename(sample_name, source_name)]
            if len(suffix_matches) == 1:
                name = suffix_matches[0]
        adjusted_variants = []
        for variant in variants:
            adjusted = dict(variant)
            sample_name = adjusted.get("sample_name", recorded_name)
            comparison_text = adjusted.get("text", "")
            if sample_name != name:
                comparison_text = rename_source_functions(
                    comparison_text, {sample_name: name},
                    require_definitions=False)
            adjusted["source_name"] = name
            adjusted["comparison_text"] = comparison_text
            adjusted["comparison_normalized"] = "\n".join(
                line.rstrip() for line in
                textwrap.dedent(comparison_text).strip().splitlines())
            adjusted_variants.append(adjusted)
        variants = adjusted_variants
        duplicate_kind = ""
        if len(variants) > 1:
            status = "duplicate"
            duplicate_kind = (
                "same" if len({item["comparison_normalized"]
                               for item in variants}) == 1
                else "different")
        elif name not in source_functions:
            status = "missing_source"
        elif variants[0]["comparison_normalized"] == source_functions[name]["normalized"]:
            status = ("name_different"
                      if variants[0].get("sample_name", name) != name
                      else "match")
        else:
            status = "different"
        function_updates = [
            function_update_status(
                source_functions[name]["normalized"]
                if name in source_functions else None,
                item.get("comparison_normalized", ""),
                item.get("function_sync", {}).get("base_hash", ""),
                source_unsaved=source_unsaved)
            for item in variants]
        update_statuses = {item["status"] for item in function_updates}
        function_update = (function_updates[0] if len(update_statuses) == 1
                           else {"status": "mixed",
                                 "source_unsaved": bool(source_unsaved)})
        result.append({"name": name,
                       "sample_name": variants[0].get("sample_name", name),
                       "source_path": variants[0].get("source_path", ""),
                       "status": status,
                       "duplicate_kind": duplicate_kind,
                       "function_update": function_update,
                       "function_update_label":
                       format_function_update_status(function_update),
                       "fragments": variants,
                       "source": source_functions.get(name)})
    return result


def merge_sample_names_with_source_bodies(source, comparisons, names):
    """Use sample names and source bodies, updating both sides consistently.

    The source definition and all executable references are renamed through
    Python tokens.  The corresponding sample body then receives that renamed
    source implementation, and its origin metadata follows the new name.
    """
    selected = set(names)
    items = [
        item for item in comparisons
        if item.get("name") in selected and item.get("source") and
        len(item.get("fragments", [])) == 1]
    mapping = {
        item["name"]: item["fragments"][0].get("sample_name", item["name"])
        for item in items
        if item["fragments"][0].get("sample_name", item["name"]) != item["name"]}
    if not items:
        return source, [], {}
    updated_source = rename_source_functions(source, mapping)
    source_functions = _function_records(updated_source, class_only=True)
    by_path = {}
    for item in items:
        by_path.setdefault(item["fragments"][0]["path"], []).append(item)
    planned_updates = {}
    for path, path_items in by_path.items():
        with open(path, "r", encoding="utf-8") as stream:
            fragment_source = stream.read()
        records = _function_records(fragment_source)
        lines = fragment_source.splitlines(True)
        path_items = sorted(
            path_items,
            key=lambda item: records[item["fragments"][0]["sample_name"]]["start"],
            reverse=True)
        for item in path_items:
            sample_name = item["fragments"][0]["sample_name"]
            record = records[sample_name]
            lines[record["start"]:record["end"]] = [
                source_functions[sample_name]["text"]]
        updated_fragment = "".join(lines)
        ast.parse(updated_fragment)
        planned_updates[path] = updated_fragment.encode("utf-8")

        # Preserve the origin path but move the tracked function name to the
        # now-canonical sample name.  A later edit/compare must not revive the
        # old source name.
        directory = os.path.dirname(path)
        for filename in os.listdir(directory):
            if not filename.endswith(".pokesample.json"):
                continue
            metadata_path = os.path.join(directory, filename)
            try:
                with open(metadata_path, "r", encoding="utf-8") as stream:
                    metadata = json.load(stream)
                linked_body = os.path.abspath(os.path.join(
                    directory, str(metadata.get("fragment", ""))))
            except (OSError, ValueError, TypeError):
                continue
            if linked_body != os.path.abspath(path):
                continue
            sample_names = {
                item["fragments"][0]["sample_name"] for item in path_items}
            if str(metadata.get("name", "")) in sample_names or \
                    len(sample_names) == 1:
                sample_name = (str(metadata.get("name", ""))
                               if str(metadata.get("name", "")) in sample_names
                               else next(iter(sample_names)))
                origin = dict(metadata.get("source", {}))
                origin["function"] = sample_name
                metadata["source"] = origin
            history = dict(metadata.get("function_sync", {}))
            for item in path_items:
                sample_name = item["fragments"][0]["sample_name"]
                history[sample_name] = function_sync_record(
                    sample_name, source_functions[sample_name]["text"])
            metadata["function_sync"] = history
            metadata_text = json.dumps(
                metadata, ensure_ascii=False, indent=2) + "\n"
            planned_updates[metadata_path] = metadata_text.encode("utf-8")

    # Validate everything before touching any target.  If a filesystem error
    # occurs after one replace, restore every target from its in-memory copy.
    _apply_atomic_updates(planned_updates, ".sample-sync.tmp")
    changed = sorted(
        path for path in planned_updates if path.lower().endswith(".pyfrag"))
    return updated_source, changed, mapping


def create_sample_sync_backup(source_path, source_text, comparisons, names,
                              backup_root, extra_paths=(),
                              source_will_be_saved=False):
    """Persist a restorable snapshot before a batch sample synchronization."""
    selected = set(names)
    paths = {
        os.path.abspath(path) for path in (extra_paths or ())
        if path and os.path.isfile(path)}
    for item in comparisons:
        if item.get("name") not in selected:
            continue
        for fragment in item.get("fragments", []):
            path = os.path.abspath(fragment.get("path", ""))
            if not path or not os.path.isfile(path):
                continue
            paths.add(path)
            directory = os.path.dirname(path)
            for filename in os.listdir(directory):
                if not filename.endswith(".pokesample.json"):
                    continue
                metadata_path = os.path.join(directory, filename)
                try:
                    with open(metadata_path, "r", encoding="utf-8") as stream:
                        metadata = json.load(stream)
                    linked = os.path.abspath(os.path.join(
                        directory, str(metadata.get("fragment", ""))))
                except (OSError, ValueError, TypeError):
                    continue
                if linked == path:
                    paths.add(os.path.abspath(metadata_path))
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    directory = os.path.abspath(os.path.join(backup_root, stamp))
    os.makedirs(directory, exist_ok=False)
    source_backup = os.path.join(directory, "source_before.py.bak")
    with open(source_backup, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(str(source_text))
    entries = []
    for index, path in enumerate(sorted(paths, key=str.casefold), 1):
        backup = os.path.join(
            directory, "{:04d}_{}.bak".format(index, os.path.basename(path)))
        with open(path, "rb") as source_stream:
            content = source_stream.read()
        with open(backup, "wb") as backup_stream:
            backup_stream.write(content)
        entries.append({"path": path, "backup": backup})
    manifest = {
        "created": stamp,
        "source_path": os.path.abspath(source_path) if source_path else "",
        "source_was_saved": bool(source_will_be_saved and source_path),
        "source_backup": source_backup,
        "files": entries,
        "names": sorted(selected, key=str.casefold),
    }
    manifest_path = os.path.join(directory, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    manifest["manifest_path"] = manifest_path
    return manifest


def latest_sample_sync_backup(backup_root):
    if not os.path.isdir(backup_root):
        return ""
    candidates = []
    for name in os.listdir(backup_root):
        path = os.path.join(backup_root, name, "manifest.json")
        if os.path.isfile(path):
            candidates.append(path)
    return max(candidates, key=os.path.getmtime) if candidates else ""


def restore_sample_sync_backup(manifest_path):
    """Restore sample files and return the source snapshot for editor review."""
    with open(manifest_path, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    with open(manifest["source_backup"], "r", encoding="utf-8") as stream:
        source_text = stream.read()
    originals = {}
    restored_contents = {}
    for entry in manifest.get("files", []):
        path, backup = entry["path"], entry["backup"]
        if os.path.isfile(path):
            with open(path, "rb") as stream:
                originals[path] = stream.read()
        else:
            originals[path] = None
        with open(backup, "rb") as stream:
            restored_contents[path] = stream.read()
    replaced = []
    try:
        for path, content in restored_contents.items():
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temporary = path + ".sample-sync-restore.tmp"
            with open(temporary, "wb") as stream:
                stream.write(content)
            os.replace(temporary, path)
            replaced.append(path)
    except Exception:
        # Restore the files changed in this restore attempt before surfacing
        # the error; a failed rollback must not leave another partial state.
        for path in replaced:
            if originals[path] is None:
                try:
                    os.remove(path)
                except OSError:
                    pass
            else:
                temporary = path + ".sample-sync-restore-rollback.tmp"
                with open(temporary, "wb") as stream:
                    stream.write(originals[path])
                os.replace(temporary, path)
        raise
    return source_text, str(manifest.get("source_path", "")), manifest


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
        fragment = item["fragments"][0].get(
            "comparison_text", item["fragments"][0]["text"])
        fragment = normalize_python_indentation(fragment)
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
    updated = normalize_python_indentation("".join(lines))
    ast.parse(updated)
    return updated


def mark_comparisons_synchronized(source, comparisons, names):
    """Record a new common function baseline after source was safely saved."""
    selected = set(names)
    source_functions = _function_records(source, class_only=True)
    by_path = {}
    for item in comparisons:
        if item.get("name") not in selected or \
                item.get("name") not in source_functions or \
                len(item.get("fragments", [])) != 1:
            continue
        fragment = item["fragments"][0]
        by_path.setdefault(fragment["path"], []).append((
            fragment.get("sample_name", item["name"]), item["name"],
            source_functions[item["name"]]["text"]))
    planned_updates = {}
    for path, entries in by_path.items():
        planned_updates.update(
            _linked_function_sync_metadata_updates(path, entries))
    if planned_updates:
        _apply_atomic_updates(planned_updates, ".function-sync.tmp")
    return sorted(planned_updates, key=str.casefold)


def replace_class_functions(source, function_texts):
    """Replace existing command-class methods from ``name -> function text``."""
    records = _function_records(source, class_only=True)
    lines = source.splitlines(True)
    replacements = []
    for name, function_text in function_texts.items():
        if name not in records:
            continue
        function_text = normalize_python_indentation(function_text)
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
        by_path.setdefault(item["fragments"][0]["path"], []).append(item)
    planned_updates = {}
    changed = []
    for path, items in by_path.items():
        with open(path, "r", encoding="utf-8") as stream:
            fragment_source = stream.read()
        records = _function_records(fragment_source)
        lines = fragment_source.splitlines(True)
        items = sorted(
            items,
            key=lambda value: records[value["fragments"][0].get(
                "sample_name", value["name"])]["start"],
            reverse=True)
        for item in items:
            source_name = item["name"]
            sample_name = item["fragments"][0].get("sample_name", source_name)
            record = records[sample_name]
            replacement = normalize_python_indentation(
                source_functions[source_name]["text"])
            if source_name != sample_name:
                replacement = rename_source_functions(
                    replacement, {source_name: sample_name},
                    require_definitions=False)
            lines[record["start"]:record["end"]] = [replacement]
        updated = normalize_python_indentation("".join(lines))
        ast.parse(updated)
        planned_updates[path] = updated.encode("utf-8")
        entries = []
        for item in items:
            source_name = item["name"]
            sample_name = item["fragments"][0].get(
                "sample_name", source_name)
            entries.append((sample_name, source_name,
                            source_functions[source_name]["text"]))
        planned_updates.update(
            _linked_function_sync_metadata_updates(path, entries))
        changed.append(path)
    if planned_updates:
        _apply_atomic_updates(planned_updates, ".sample-update.tmp")
    return changed
