#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only links between an operation recording and an editable source.

Recording evidence, the editable Step plan and the Commands source are three
different documents.  A matching Step name is a link, not proof that edits in
one of them have been applied to another.  This module never imports or runs
the inspected Commands and never changes any of those documents.
"""
from __future__ import print_function

import ast
import hashlib
import io
import json
import math
import os
import tokenize


MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024


def _literal(node, default=None):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return default


def _assignment_names(node):
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return [target.id if isinstance(target, ast.Name) else
            target.attr if isinstance(target, ast.Attribute) and
            isinstance(target.value, ast.Name) and target.value.id == "self" else ""
            for target in targets]


def _end_line(node):
    return max([getattr(child, "end_lineno", None) or
                getattr(child, "lineno", node.lineno)
                for child in ast.walk(node)] or [node.lineno])


def _source_manifest(document):
    """Use generated line/timing links only for exactly this source content."""
    path = document.get("path", "")
    manifest_path = os.path.join(os.path.dirname(path), "vision_source_bindings.json")
    result = {"path": manifest_path, "status": "未登録", "steps": {}}
    if not path or not os.path.isfile(manifest_path):
        return result
    try:
        if os.path.getsize(manifest_path) > MAX_MANIFEST_BYTES:
            raise ValueError("対応manifestが8 MiBを超えています。")
        with open(manifest_path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("対応manifestの形式が未対応です。")
        expected_hash = str(value.get("source_sha256", ""))
        actual_hash = document.get("sha256", "")
        if document.get("hash_kind") == "editor_buffer_utf8":
            saved = inspect_source_document(path, include_manifest=False)
            if saved.get("source") != document.get("source"):
                raise ValueError("未保存の編集があるため生成済みmanifestの行・区間を使用しません。")
            actual_hash = saved.get("sha256", "")
        if not expected_hash or expected_hash != actual_hash:
            raise ValueError("ソースSHA256不一致のため生成済みmanifestの行・区間を使用しません。")
        declared_path = str(value.get("source_path", "") or "").replace("/", os.sep)
        parent, project_root = os.path.dirname(path), ""
        for _index in range(24):
            candidate = os.path.abspath(os.path.join(parent, declared_path))
            if declared_path and os.path.normcase(candidate) == os.path.normcase(path):
                project_root = parent
                break
            previous, parent = parent, os.path.dirname(parent)
            if parent == previous:
                break
        if not project_root:
            raise ValueError("manifestのsource_pathと編集対象が一致しません。")
        steps = value.get("steps", [])
        if not isinstance(steps, list) or any(not isinstance(item, dict) for item in steps):
            raise ValueError("manifestのStep一覧が不正です。")
        by_state = {}
        for step in steps:
            state = str(step.get("state", ""))
            if not state or state in by_state:
                raise ValueError("manifestのStep名が空または重複しています。")
            for field in ("source_line", "end_line", "input_start_line",
                          "input_end_line", "action_count"):
                if type(step.get(field)) is not int or step[field] < 0:
                    raise ValueError("manifestの行番号・処理数が不正です。")
            for field in ("emitted_input_start_line", "emitted_input_end_line",
                          "carry_in_input_line"):
                if field == "carry_in_input_line" and step.get(field) is None:
                    continue
                if field in step and (type(step[field]) is not int or step[field] < 0):
                    raise ValueError("manifestの発行入力・持越し入力行が不正です。")
            times = [float(step.get(field)) for field in ("source_start", "source_end")]
            if (not all(math.isfinite(item) and item >= 0 for item in times) or
                    times[0] > times[1] or step["source_line"] > step["end_line"] or
                    step["input_start_line"] > step["input_end_line"]):
                raise ValueError("manifestの時刻・入力区間が不正です。")
            # Operation order is displayed from the actual AST source, not
            # from this generated copy. Do not retain thousands of action
            # dictionaries in the lightweight editor's one-source cache.
            by_state[state] = {key: item for key, item in step.items()
                               if key != "actions"}
        result.update({"status": "ソースSHA256一致", "steps": by_state,
                       "session_id": str(value.get("source_session_id", "")),
                       "recording_session": os.path.abspath(os.path.join(
                           project_root, str(value.get("recording_session", "")).replace("/", os.sep))),
                       "source_sha256": expected_hash})
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as error:
        result["status"] = "未採用: " + str(error)
    return result


def inspect_source_document(path, source_text=None, include_manifest=True):
    """Describe static Step links and function ranges without executing code.

    Byte SHA256 identifies a saved file; an optional editor buffer gets an
    explicitly labelled UTF-8 buffer SHA256 instead.  Syntax errors and
    ambiguous mappings are reported rather than guessing a function.
    """
    path = os.path.abspath(path) if path else ""
    result = {"path": path, "sha256": "", "hash_kind": "file_bytes",
              "source": "", "functions": {}, "step_links": {},
              "session_ids": [], "errors": [], "class_bases": {},
              "opaque_state_owners": []}
    try:
        if source_text is None:
            if not path or not os.path.isfile(path):
                raise OSError("編集対象ソースが存在しません。")
            if os.path.getsize(path) > MAX_SOURCE_BYTES:
                raise ValueError("ソースが16 MiBを超えるため対応解析を行いません。")
            with open(path, "rb") as stream:
                raw = stream.read(MAX_SOURCE_BYTES + 1)
            if len(raw) > MAX_SOURCE_BYTES:
                raise ValueError("ソースが16 MiBを超えるため対応解析を行いません。")
            result["sha256"] = hashlib.sha256(raw).hexdigest()
            # Hash and parse the same immutable byte snapshot even if an
            # external generator replaces the source during inspection.
            encoding, _lines = tokenize.detect_encoding(io.BytesIO(raw).readline)
            with io.TextIOWrapper(io.BytesIO(raw), encoding=encoding) as stream:
                source_text = stream.read()
        else:
            source_text = str(source_text)
            raw = source_text.encode("utf-8")
            if len(raw) > MAX_SOURCE_BYTES:
                raise ValueError("編集バッファが16 MiBを超えるため対応解析を行いません。")
            result["sha256"] = hashlib.sha256(raw).hexdigest()
            result["hash_kind"] = "editor_buffer_utf8"
        result["source"] = source_text
        tree = ast.parse(source_text, filename=path or "<editor buffer>")
    except (OSError, ValueError, SyntaxError, UnicodeError) as error:
        result["errors"].append(str(error))
        return result

    lines = source_text.splitlines()
    scopes = [("", tree)] + [(node.name, node) for node in tree.body
                             if isinstance(node, ast.ClassDef)]
    for owner, scope in scopes:
        if isinstance(scope, ast.ClassDef):
            result["class_bases"][owner] = [base.id for base in scope.bases
                                            if isinstance(base, ast.Name)]
        for node in scope.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start, end = node.lineno, _end_line(node)
                qualified = owner + "." + node.name if owner else node.name
                result["functions"].setdefault(node.name, []).append({
                    "owner": owner, "name": node.name, "qualified": qualified,
                    "line": start, "end_line": end,
                    "source": "\n".join(lines[start - 1:end]),
                    "opaque_story_wrapper": any(
                        isinstance(child, ast.Call) and
                        isinstance(child.func, ast.Attribute) and
                        child.func.attr == "run_image_story_step"
                        for child in ast.walk(node)),
                })
            # State dictionaries can be class constants or assigned in init.
            nodes = ast.walk(node) if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)) else [node]
            for assignment in nodes:
                if not isinstance(assignment, (ast.Assign, ast.AnnAssign)):
                    continue
                names = _assignment_names(assignment)
                if "SOURCE_SESSION_ID" in names:
                    value = _literal(assignment.value)
                    if isinstance(value, str) and value not in result["session_ids"]:
                        result["session_ids"].append(value)
                if not any(name.startswith("STATE_") and name.endswith("_FUNCTION")
                           for name in names):
                    continue
                if not isinstance(assignment.value, ast.Dict):
                    if owner not in result["opaque_state_owners"]:
                        result["opaque_state_owners"].append(owner)
                    continue
                for key, value in zip(assignment.value.keys,
                                      assignment.value.values):
                    step_name = _literal(key)
                    if (not isinstance(step_name, str) or
                            not isinstance(value, ast.Attribute) or
                            not isinstance(value.value, ast.Name) or
                            value.value.id != "self"):
                        continue
                    result["step_links"].setdefault(step_name, []).append({
                        "owner": owner, "method": value.attr,
                        "table_line": assignment.lineno,
                    })
    if include_manifest:
        result["manifest"] = _source_manifest(result)
    return result


def _absolute_source_path(value, session_dir):
    value = str(value or "").strip()
    if not value:
        return ""
    if os.path.isabs(value):
        return os.path.abspath(value)
    return os.path.abspath(os.path.join(session_dir, value))


def operation_step_binding(session_dir, session, plan, step, document):
    """Return an honest source/recording link for one selected Step."""
    session_dir = os.path.abspath(session_dir) if session_dir else ""
    step, session, plan = step or {}, session or {}, plan or {}
    name = str(step.get("name", step.get("step_name", "")) or "")
    recorded_id = str(session.get("session_id", "") or "")
    declared = list(document.get("session_ids", []))
    session_status = ("一致" if declared == [recorded_id] and recorded_id
                      else "不一致" if declared else "未宣言")
    warnings = list(document.get("errors", []))
    if session_status == "不一致":
        warnings.append("SOURCE_SESSION_IDが開いている録画と一致しません。")
    elif session_status == "未宣言":
        warnings.append("SOURCE_SESSION_ID未宣言のため、同じ録画由来とは確認できません。")

    links = list(document.get("step_links", {}).get(name, []))
    # Never choose the first of duplicated state registrations silently.
    unique_links = {(item["owner"], item["method"]) for item in links}
    function, link_kind = None, "未確認"
    if any(owner in document.get("opaque_state_owners", [])
           for owner, _method in unique_links):
        warnings.append("同じクラスの状態テーブルに動的な代入があり、静的対応を断定しません。")
        unique_links = set()
        # Keep a dynamic table from falling through to the plan-name guess.
        links = [{}]
    if len(unique_links) == 1:
        owner, method = next(iter(unique_links))
        candidates = document.get("functions", {}).get(method, [])
        owned = [item for item in candidates if item["owner"] == owner]
        # Do not mistake an unrelated class's same-named function for this
        # class's implementation. Only a simple, unambiguous local base chain
        # is resolved here; dynamic/multiple inheritance stays unconfirmed.
        visited = set()
        while not owned and owner and owner not in visited:
            visited.add(owner)
            bases = document.get("class_bases", {}).get(owner, [])
            owner = bases[0] if len(bases) == 1 else ""
            owned = [item for item in candidates if item["owner"] == owner] if owner else []
        candidates = owned
        if len(candidates) == 1:
            function, link_kind = candidates[0], "状態テーブル"
        elif candidates:
            warnings.append("同名の関数が複数あり、対応関数を特定できません。")
    elif len(unique_links) > 1:
        warnings.append("同じStepに複数の状態テーブル対応があるため、自動選択しません。")
    elif not links:
        # A plan method is only a declared candidate, not a verified Step link.
        method = str(step.get("method", step.get("function_name", "")) or "")
        candidates = document.get("functions", {}).get(method, [])
        if method and len(candidates) == 1:
            function, link_kind = candidates[0], "計画の関数名候補（状態テーブル未確認）"
    if name and function is None:
        warnings.append("選択Stepと編集対象ソースの関数対応を確認できません。")
    if function and function.get("opaque_story_wrapper"):
        warnings.append("この関数はrun_image_story_stepへの委譲です。操作順の実体は外部plan/runtimeにあります。")

    manifest = document.get("manifest", {})
    current_step = manifest.get("steps", {}).get(name)
    if current_step:
        if (manifest.get("session_id") != recorded_id or
                os.path.normcase(manifest.get("recording_session", "")) !=
                os.path.normcase(session_dir)):
            warnings.append("manifestの録画sessionが開いている証跡と異なるため、現Step区間を採用しません。")
            current_step = None
        elif (not function or current_step.get("method") != function.get("name") or
              current_step.get("source_line") != function.get("line") or
              current_step.get("end_line") != function.get("end_line")):
            warnings.append("manifestの関数名・行と現在ASTが異なるため、現Step区間を採用しません。")
            current_step = None
    return {
        "source": document, "source_session_status": session_status,
        "session_id": recorded_id, "session_dir": session_dir,
        "recording_session_path": os.path.join(session_dir, "session.json") if session_dir else "",
        "recording_inputs_path": os.path.join(session_dir, "inputs.jsonl") if session_dir else "",
        "recording_mappings_path": os.path.join(session_dir, "mappings.json") if session_dir else "",
        "session_final_source": _absolute_source_path(session.get("final_source"), session_dir),
        "plan_path": os.path.join(session_dir, "step_plan.json") if session_dir else "",
        "preview_path": os.path.join(session_dir, "source", "step_plan_preview.py") if session_dir else "",
        "plan_revision": plan.get("revision", 0), "step_name": name,
        "input_start": step.get("input_start", step.get("start_line", 0)),
        "input_end": step.get("input_end", step.get("end_line", 0)),
        "video_start": step.get("video_start", 0.0),
        "video_end": step.get("video_end", 0.0),
        "recording_time_known": "video_start" in step and "video_end" in step,
        "function": function, "link_kind": link_kind, "warnings": warnings,
        "current_step": current_step,
    }


def binding_summary(binding):
    function = binding.get("function") or {}
    location = "{} : L{}".format(function.get("qualified"), function.get("line")) \
        if function else "関数対応未確認"
    return "{} → {} / 録画ID{}（Step境界は別確認） / 計画編集はソースへ自動反映されません".format(
        binding.get("step_name") or "Step未選択", location,
        binding.get("source_session_status", "未宣言"))


def binding_details(binding):
    source, function = binding.get("source", {}), binding.get("function") or {}
    rows = [
        "【編集対象Commands（現在のファイル／録画snapshotではありません）】",
        source.get("path", "") or "未指定",
        "SHA256（{}）: {}".format(source.get("hash_kind", ""), source.get("sha256", "") or "未取得"),
        "ソースSOURCE_SESSION_ID: {}".format(", ".join(source.get("session_ids", [])) or "未宣言"),
        "選択Step: {} / 対応方式: {}".format(binding.get("step_name", ""), binding.get("link_kind", "")),
        "関数: {} / L{}–L{}".format(function.get("qualified", "未確認"),
                                     function.get("line", "?"), function.get("end_line", "?")),
        "", "【元の操作記録（証跡・書き換えません）】",
        "Session ID: {} / ソースの宣言と{}".format(binding.get("session_id", ""), binding.get("source_session_status", "")),
        binding.get("recording_session_path", ""),
        binding.get("recording_inputs_path", ""),
        binding.get("recording_mappings_path", ""),
        "記録プラン側の入力行（現CommandsのStep境界とは限りません）: #{}–#{} / 記録時刻: {}".format(
            binding.get("input_start", 0), binding.get("input_end", 0),
            "{:.6f}–{:.6f}秒".format(
                float(binding.get("video_start", 0.0) or 0.0),
                float(binding.get("video_end", 0.0) or 0.0))
            if binding.get("recording_time_known") else "未取得（入力行を参照）"),
        "session.final_source（登録済み反映先。現在ソースと同一内容の保証なし）: " +
        (binding.get("session_final_source", "") or "未登録"),
        "", "【編集計画・確認用出力（Commandsソースとは別）】",
        "計画: {} / revision {}".format(binding.get("plan_path", ""), binding.get("plan_revision", 0)),
        "確認用出力: " + binding.get("preview_path", ""),
        "Step計画の保存・確認用出力では、編集対象Commandsは変更されません。",
        "録画と同じID／同じStep名でも、計画の変更がソースへ反映済みとは判定しません。",
    ]
    current_step = binding.get("current_step")
    rows += ["", "【現在Commandsの画像Step区間（生成manifest・ソースSHA256照合済みだけ採用）】",
             "manifest: " + source.get("manifest", {}).get("path", "未登録"),
             "状態: " + source.get("manifest", {}).get("status", "未登録")]
    if current_step:
        rows += ["元入力行（開始時の継続保持を含む）: #{}–#{} / 元動画: {:.6f}–{:.6f}秒 / {}処理".format(
            current_step.get("input_start_line", 0), current_step.get("input_end_line", 0),
            float(current_step.get("source_start", 0.0)), float(current_step.get("source_end", 0.0)),
            current_step.get("action_count", 0)),
            "開始画像: " + str(current_step.get("entry_image", "")),
            "終了画像: " + str(current_step.get("exit_image", ""))]
        if "emitted_input_start_line" in current_step:
            rows += ["本Step内で発行された元入力行: #{}–#{} / 開始前からの継続保持入力行: {}".format(
                current_step.get("emitted_input_start_line", 0),
                current_step.get("emitted_input_end_line", 0),
                "#{}".format(current_step["carry_in_input_line"])
                if current_step.get("carry_in_input_line") else "なし")]
    else:
        rows += ["現Commandsの正確な入力／動画区間は未確認。上の記録プラン範囲を代用しません。"]
    if binding.get("warnings"):
        rows += ["", "【確認事項】"] + ["・" + item for item in binding["warnings"]]
    rows += ["", "【編集対象ソース内の処理順（現在ファイル・読み取り専用）】"]
    if function:
        rows += ["{:6d}  {}".format(function["line"] + offset, line)
                 for offset, line in enumerate(function["source"].splitlines())]
    else:
        rows += ["対応関数を確認できないため、処理順は表示しません。"]
    return "\n".join(rows)


def recording_session_for_source(project_root, document):
    """Find a unique local recording by its explicit source Session ID only."""
    ids = document.get("session_ids", [])
    if len(ids) != 1:
        return ""
    session_id = ids[0]
    if (not session_id or session_id in (".", "..") or
            any(value in session_id for value in ("/", "\\", ":"))):
        return ""
    recording_root = os.path.join(project_root, "SerialController", "CommandsRecording")
    try:
        groups = os.listdir(recording_root)
    except OSError:
        return ""
    candidates = [os.path.join(recording_root, group, session_id)
                  for group in groups if os.path.isfile(os.path.join(
                      recording_root, group, session_id, "session.json"))]
    return os.path.abspath(candidates[0]) if len(candidates) == 1 else ""


class OperationSourceBindingReader(object):
    """One-file stat-aware cache; selection does not repeatedly parse a source."""

    def __init__(self):
        self._key, self._document = None, None

    def read(self, path, force=False):
        path = os.path.abspath(path) if path else ""
        try:
            value = os.stat(path)
            key = (path, value.st_mtime_ns, value.st_size)
        except OSError:
            key = (path, None, None)
        if force or key != self._key or self._document is None:
            self._document = inspect_source_document(path)
            self._key = key
        return self._document
