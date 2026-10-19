#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recording/source comparison and Step-structure editor for PokeConStudio.

The window deliberately separates three kinds of data:

* Operation-session evidence (``inputs.jsonl`` / ``mappings.json``) is read
  only.  The embedded lightweight editor writes its copy-on-write
  ``step_plan.json`` just as it does when launched on its own.
* Commands-monitor evidence (``steps.jsonl`` / ``command_monitor.json``) is
  read only by this window.  The existing Commands recording workspace is
  embedded for video/source inspection.
* The current PokeConStudio editor buffer is obtained and updated only through
  callbacks.  A STATE draft changes one ``STATE_*_FUNCTION`` dictionary.  A
  separately confirmed operation-Step replacement changes only the matched
  function body while preserving its name and signature.  Neither path writes
  the source file.

The three-way comparison aligns operation-plan and Commands visits by Step
name plus occurrence number.  Wall-clock/video timestamps are intentionally
not used for alignment.
"""
from __future__ import print_function

import copy
import difflib
import importlib
import os
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from PokeConStudio.StepModel import (
        add_state_step,
        apply_state_table_draft,
        compare_recording_to_source,
        create_state_table_draft,
        delete_state_step,
        load_recording_plan_bundle,
        move_state_step,
        parse_source_outline,
        prepare_recording_step_replacement,
        recording_plan_outline,
    )
except ImportError:
    # Direct ``python PokeConStudio/PokeConStudio.py`` launch.
    from StepModel import (  # noqa: E402
        add_state_step,
        apply_state_table_draft,
        compare_recording_to_source,
        create_state_table_draft,
        delete_state_step,
        load_recording_plan_bundle,
        move_state_step,
        parse_source_outline,
        prepare_recording_step_replacement,
        recording_plan_outline,
    )


_KIND_LABELS = {
    "operation": "操作",
    "variable": "変数",
    "image_check": "image_check",
    "call": "関数呼出",
    "return": "return",
    "recorded_range": "操作記録",
}

_STATUS_LABELS = {
    "same": "一致",
    "changed": "内容差分",
    "recording_only": "操作記録のみ",
    "source_only": "ソースのみ",
    "unresolved": "操作記録（詳細はStep編集）",
}


def _display_basename(path):
    value = str(path or "").rstrip("/\\")
    if not value:
        return "未選択"
    return os.path.basename(value) or value


def _one_line(value, limit=180):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) > limit:
        return text[:max(1, limit - 1)] + "…"
    return text


def _normal_name(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _source_entry_for_visit(source_entries, operation=None, command=None):
    """Resolve one visit without silently collapsing distinct STATE keys.

    STATE keys are case-sensitive Python strings.  A normalized-name lookup is
    useful for display alignment, but it is not safe as the first choice for a
    source edit: ``Step`` and ``step`` may intentionally call different
    methods.  Prefer the exact visit name, then the operation plan's exact
    method, and use the normalized name only when it identifies one entry.
    """
    entries = list(source_entries or ())
    operation = operation or {}
    command = command or {}
    visit_name = str(operation.get("name", "") or
                     command.get("name", "") or "")
    if visit_name:
        exact = [entry for entry in entries
                 if str(entry.get("name", "") or "") == visit_name]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            return None

    operation_step = operation.get("step") or {}
    method = str(operation_step.get("method", "") or "")
    if method:
        by_method = [entry for entry in entries
                     if str(entry.get("method", "") or "") == method]
        if len(by_method) == 1:
            return by_method[0]

    normalized_name = _normal_name(visit_name)
    if normalized_name:
        normalized = [entry for entry in entries
                      if _normal_name(entry.get("name", "")) ==
                      normalized_name]
        if len(normalized) == 1:
            return normalized[0]
    return None


def _state_method_references(source_outline, method):
    """Return every STATE table/Step reference to an exact method name."""
    method = str(method or "")
    references = []
    if not method:
        return references
    for table in (source_outline or {}).get("tables", ()):
        table_name = str(table.get("name", "") or
                         table.get("id", "") or "STATE")
        for entry in table.get("entries", ()):
            if (str(entry.get("method", "") or "") != method
                    or str(entry.get("self_method", "") or "") != method):
                continue
            references.append({
                "table": table_name,
                "step": str(entry.get("name", "") or "(名称なし)"),
            })
    return references


def _shared_method_note(source_outline, method):
    """Describe the complete cross-table impact of replacing a method."""
    references = _state_method_references(source_outline, method)
    if len(references) <= 1:
        return ""
    grouped = []
    by_table = {}
    for reference in references:
        table_name = reference["table"]
        if table_name not in by_table:
            by_table[table_name] = []
            grouped.append(table_name)
        by_table[table_name].append(reference["step"])
    affected = " / ".join(
        "{}: {}".format(table_name, ", ".join(by_table[table_name]))
        for table_name in grouped)
    return (
        "この関数は全STATE辞書の {} Stepから共有されています: {}"
        .format(len(references), affected))


def _source_value(value):
    """Normalize the documented provider mapping, with small legacy fallbacks."""
    if isinstance(value, dict):
        source = value.get("source", value.get("text", ""))
        path = value.get("path", value.get("source_path", ""))
        return str(source or ""), str(path or "")
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        first, second = str(value[0] or ""), str(value[1] or "")
        # Accept both (source, path) and the common (path, source) convenience.
        if ("\n" not in first and "\r" not in first
                and (first.lower().endswith(".py") or os.path.isfile(first))):
            return second, first
        return first, second
    return str(value or ""), ""


def _load_devstudio_classes(project_root):
    devstudio = os.path.join(os.path.abspath(project_root), "DevStudio")
    if devstudio not in sys.path:
        # The existing DevStudio modules intentionally import their siblings as
        # top-level modules.  Keep this path for their later lazy imports too.
        sys.path.insert(0, devstudio)
    operation_module = importlib.import_module("LightweightOperationStudio")
    command_module = importlib.import_module("CommandRecordingStudio")
    command_model = importlib.import_module("CommandRecordingModel")
    return (operation_module.LightweightOperationStudio,
            command_module.CommandRecordingWorkspace,
            command_model)


def _step_parts(step_text):
    text = str(step_text or "").strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"\s*>\s*", text)
            if part.strip()]


def _known_name_map(known_names):
    canonical = {}
    for name in known_names or ():
        if name:
            canonical.setdefault(_normal_name(name), str(name))
    return canonical


def _command_step_name(event, known_names, canonical=None):
    """Resolve one recorded Step without hiding an unknown leaf Step.

    ``step_path`` is a state hierarchy.  Its leaf is therefore the actual Step
    visit even when the current operation plan/source does not know that name.
    Falling back to a known ancestor would incorrectly turn ``A > RECOVERY``
    into another visit to ``A`` and conceal the extra recovery Step.
    """
    canonical = canonical if canonical is not None else \
        _known_name_map(known_names)
    path = str(event.get("step_path", "") or
               event.get("step_text", "") or "").strip()
    parts = _step_parts(path)
    if parts:
        leaf = parts[-1]
        return canonical.get(_normal_name(leaf), leaf), path or leaf
    states = event.get("states", {})
    if isinstance(states, dict):
        for value in reversed(list(states.values())):
            match = canonical.get(_normal_name(value))
            if match:
                return match, path or str(value)
    stop_state = str(event.get("stop_state", "") or "").strip()
    match = canonical.get(_normal_name(stop_state))
    if match:
        return match, path or stop_state
    fallback = parts[-1] if parts else stop_state
    return fallback, path or fallback


def _command_location(event):
    """Return compact, display-only execution evidence for one timeline row."""
    location = event.get("location", {}) if isinstance(event, dict) else {}
    if not isinstance(location, dict):
        return None
    file_path = str(location.get("file", "") or "")
    function = str(location.get("function", "") or "")
    source = _one_line(location.get("source", ""), limit=220)
    try:
        line = max(0, int(location.get("line", 0) or 0))
    except (TypeError, ValueError):
        line = 0
    if not (file_path or function or line or source):
        return None
    normalized_file = ""
    if file_path:
        try:
            normalized_file = os.path.normcase(os.path.abspath(file_path))
        except (OSError, ValueError):
            normalized_file = os.path.normcase(file_path)
    return {
        "file": file_path,
        "normalized_file": normalized_file,
        "function": function,
        "line": line,
        "source": source,
        "count": 1,
        "key": (normalized_file, function, line, source),
    }


def _command_visits(events, known_names=None):
    """Collapse consecutive events but preserve every later Step revisit."""
    visits = []
    previous_name = ""
    canonical = _known_name_map(known_names)
    for event in events or ():
        name, path = _command_step_name(
            event, known_names or (), canonical=canonical)
        if not name:
            continue
        normal = _normal_name(name)
        location = _command_location(event)
        if normal == previous_name:
            visits[-1]["event_count"] += 1
            if location is not None:
                rows = visits[-1]["command_rows"]
                if rows and rows[-1].get("key") == location.get("key"):
                    rows[-1]["count"] += 1
                else:
                    rows.append(location)
            continue
        visits.append({
            "name": name,
            "path": path,
            "event_count": 1,
            "command_rows": [location] if location is not None else [],
        })
        previous_name = normal
    return _number_visits(visits)


def _operation_visits(recording_outline):
    visits = []
    for step in recording_outline.get("steps", []) if recording_outline else ():
        visits.append({
            "name": str(step.get("name", "") or step.get("label", "") or ""),
            "step": step,
        })
    return _number_visits(visits)


def _number_visits(visits):
    counts = {}
    result = []
    for value in visits:
        item = dict(value)
        normal = _normal_name(item.get("name", ""))
        counts[normal] = counts.get(normal, 0) + 1
        item["visit"] = counts[normal]
        item["key"] = (normal, counts[normal])
        result.append(item)
    return result


def _align_visits(operation_visits, command_visits):
    """Return ordered operation/Commands pairs without consulting timestamps."""
    left = [item.get("key") for item in operation_visits]
    right = [item.get("key") for item in command_visits]
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    rows = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            rows.extend((operation_visits[index],
                         command_visits[j1 + index - i1])
                        for index in range(i1, i2))
            continue
        left_values = operation_visits[i1:i2]
        right_values = command_visits[j1:j2]
        for index in range(max(len(left_values), len(right_values))):
            rows.append((left_values[index] if index < len(left_values) else None,
                         right_values[index] if index < len(right_values) else None))
    return rows


def _visit_label(visit):
    if not visit:
        return ""
    name = str(visit.get("name", "") or "")
    occurrence = int(visit.get("visit", 1) or 1)
    return "{}{}".format(name, "  [再訪{}]".format(occurrence)
                         if occurrence > 1 else "")


def _item_signature(item):
    return str(item.get("signature", "") or "")


def _align_items(recorded_items, source_items):
    left = [_item_signature(item) for item in recorded_items]
    right = [_item_signature(item) for item in source_items]
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    rows = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            rows.extend((recorded_items[index],
                         source_items[j1 + index - i1], "same")
                        for index in range(i1, i2))
            continue
        left_values = recorded_items[i1:i2]
        right_values = source_items[j1:j2]
        for index in range(max(len(left_values), len(right_values))):
            rows.append((left_values[index] if index < len(left_values) else None,
                         right_values[index] if index < len(right_values) else None,
                         "changed"))
    return rows


def _item_text(item):
    if not item:
        return ""
    kind = item.get("kind", "")
    label = _KIND_LABELS.get(kind, kind or "処理")
    if kind == "image_check" and item.get("image_targets"):
        detail = ", ".join(_display_basename(value)
                           for value in item.get("image_targets", []))
    elif kind == "variable" and item.get("variables"):
        detail = ", ".join(item.get("variables", []))
    elif kind == "return" and item.get("return_target"):
        detail = "→ " + str(item.get("return_target"))
    elif kind in ("operation", "call") and item.get("calls"):
        detail = ", ".join(str(value).rsplit(".", 1)[-1]
                           for value in item.get("calls", []))
    else:
        detail = item.get("display", item.get("source", ""))
    return "[{}] {}".format(label, _one_line(detail))


def _command_row_text(row):
    if not row:
        return ""
    place = "{}()".format(row.get("function", "")) \
        if row.get("function") else "実行行"
    if row.get("line"):
        place += ":{}".format(row.get("line"))
    file_name = _display_basename(row.get("file", "")) \
        if row.get("file") else ""
    if file_name:
        place = file_name + " / " + place
    source = _one_line(row.get("source", ""), limit=150)
    text = "{}  {}".format(place, source).strip()
    count = int(row.get("count", 1) or 1)
    if count > 1:
        text += "  ×{}".format(count)
    return text


def _assign_command_rows(command_rows, source_items, source_path=""):
    """Attach sampled execution rows to the narrowest current-source item."""
    normalized_source = ""
    if source_path:
        try:
            normalized_source = os.path.normcase(os.path.abspath(source_path))
        except (OSError, ValueError):
            normalized_source = os.path.normcase(source_path)
    assigned = [[] for _item in source_items]
    unmatched = []
    for row in command_rows or ():
        if (normalized_source
                and row.get("normalized_file") != normalized_source):
            continue
        line = int(row.get("line", 0) or 0)
        candidates = []
        for index, item in enumerate(source_items):
            start = int(item.get("line", 0) or 0)
            end = int(item.get("end_line", 0) or start)
            if line and start <= line <= max(start, end):
                candidates.append((
                    0 if line == start else 1,
                    max(0, end - start), start, index))
        if not candidates:
            unmatched.append(row)
            continue
        _exact, _span, _line, index = min(
            candidates, key=lambda value: value[:3])
        assigned[index].append(row)
    return assigned, unmatched


class _NewStateStepDialog(tk.Toplevel):
    """Small modal that can reference only an already-defined function."""

    def __init__(self, parent, methods):
        tk.Toplevel.__init__(self, parent)
        self.result = None
        self.methods = list(methods or ())
        self.step_name = tk.StringVar()
        self.method_name = tk.StringVar(value=self.methods[0]
                                        if self.methods else "")
        self.title("STATE Stepを追加")
        self.transient(parent)
        self.resizable(True, False)

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="Step名").grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(body, textvariable=self.step_name, width=48)
        entry.grid(row=0, column=1, sticky="ew", padx=(7, 0))
        ttk.Label(body, text="既存関数").grid(
            row=1, column=0, sticky="w", pady=(7, 0))
        combo = ttk.Combobox(
            body, textvariable=self.method_name, values=self.methods, width=45)
        combo.grid(row=1, column=1, sticky="ew", padx=(7, 0), pady=(7, 0))
        ttk.Label(
            body,
            text="関数名の変更や関数内部の修正は、ソースエディタで行います。",
            foreground="#5a5a5a").grid(
                row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        buttons = ttk.Frame(body)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="キャンセル", command=self.destroy).pack(
            side="right")
        ttk.Button(buttons, text="追加", command=self._accept).pack(
            side="right", padx=(0, 5))
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
        entry.focus_set()

    def _accept(self):
        name = self.step_name.get().strip()
        method = self.method_name.get().strip()
        if not name:
            messagebox.showerror("Step追加", "Step名を入力してください。", parent=self)
            return
        if method not in self.methods:
            messagebox.showerror(
                "Step追加", "ソース側で定義済みの関数を選択してください。",
                parent=self)
            return
        self.result = (name, method)
        self.destroy()


class _FunctionReplacementDialog(tk.Toplevel):
    """Show the exact old/new function before touching the editor buffer."""

    def __init__(self, parent, replacement, note=""):
        tk.Toplevel.__init__(self, parent)
        self.result = False
        method = replacement.get("method", "")
        step_name = replacement.get("step_name", "")
        self.title("操作記録Stepから関数本体を反映")
        self.transient(parent)
        self.geometry("1180x720")
        self.minsize(760, 440)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        ttk.Label(
            self,
            text=("操作記録 {} の処理で {}() の本体だけを置き換えます。"
                  "関数名・引数・decorator・STATE辞書は保持します。".format(
                      step_name or "(名称なし)", method)),
            foreground="#174a7e", justify="left", wraplength=1120).pack(
                fill="x", padx=10, pady=(10, 5))
        if note:
            ttk.Label(self, text=note, foreground="#8a5200",
                      justify="left", wraplength=1120).pack(
                          fill="x", padx=10, pady=(0, 5))

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10, pady=5)
        for title, value in (
                ("現在ソース", replacement.get("old_function_source", "")),
                ("反映後", replacement.get("new_function_source", ""))):
            frame = ttk.Frame(panes)
            panes.add(frame, weight=1)
            frame.rowconfigure(1, weight=1)
            frame.columnconfigure(0, weight=1)
            ttk.Label(frame, text=title).grid(row=0, column=0, sticky="w")
            text_widget = tk.Text(
                frame, wrap="none", undo=False, font=("Consolas", 10))
            vertical = ttk.Scrollbar(
                frame, orient="vertical", command=text_widget.yview)
            horizontal = ttk.Scrollbar(
                frame, orient="horizontal", command=text_widget.xview)
            text_widget.configure(yscrollcommand=vertical.set,
                                  xscrollcommand=horizontal.set)
            text_widget.grid(row=1, column=0, sticky="nsew")
            vertical.grid(row=1, column=1, sticky="ns")
            horizontal.grid(row=2, column=0, sticky="ew")
            text_widget.insert("1.0", value)
            text_widget.configure(state="disabled")

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=(2, 10))
        ttk.Label(
            buttons,
            text="反映後も未保存です。録画証跡とstep_plan.jsonは変更しません。",
            foreground="#5a5a5a").pack(side="left")
        ttk.Button(buttons, text="キャンセル", command=self.destroy).pack(
            side="right")
        ttk.Button(
            buttons, text="現在のエディタへ反映", command=self._accept).pack(
                side="right", padx=(0, 5))
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()

    def _accept(self):
        self.result = True
        self.destroy()


class RecordingComparisonWindow(tk.Toplevel):
    """Three-way recording comparison and narrow STATE dictionary editor.

    ``source_provider`` must return ``{"source": text, "path": path}``.
    ``apply_source_callback`` is called as ``callback(updated_text, path)`` and
    must update the PokeConStudio editor buffer synchronously.  It should not
    save the file implicitly.  ``open_source_callback`` is optional and is
    called as ``callback(path, line)``.  ``paths_changed_callback`` is optional
    and is called as ``callback(operation_session, command_recording)``.
    Recording-frame registration uses ``image_folders_provider()`` and
    ``register_image_check_callback(row, source_path)`` when supplied.
    """

    def __init__(self, master, project_root, source_provider,
                 apply_source_callback, open_source_callback=None,
                 paths_changed_callback=None, initial_operation_session="",
                 initial_command_recording="", image_folders_provider=None,
                 register_image_check_callback=None):
        tk.Toplevel.__init__(self, master)
        self.project_root = os.path.abspath(project_root)
        self.source_provider = source_provider
        self.apply_source_callback = apply_source_callback
        self.open_source_callback = open_source_callback
        self.paths_changed_callback = paths_changed_callback
        self.image_folders_provider = image_folders_provider
        self.register_image_check_callback = register_image_check_callback
        self.operation_session = os.path.abspath(initial_operation_session) \
            if initial_operation_session else ""
        self.command_recording = os.path.abspath(initial_command_recording) \
            if initial_command_recording else ""
        self.source_text = ""
        self.source_path = ""
        self.source_outline = None
        self.recording_bundle = None
        self.recording_outline = None
        self.command_metadata = {}
        self.operation_visits = []
        self.command_visits = []
        self.aligned_visits = []
        self.state_draft = None
        self.table_labels = {}
        self.current_table_id = ""
        self.comparison_result = None
        self.tree_meta = {}
        self._state_draft_dirty = False
        self._load_generation = 0
        self._comparison_generation = 0
        self._comparison_loading = False
        self._closing = False
        self._details_ready = False
        self._path_refresh_job = None
        self._operation_trace = None
        self._command_trace = None
        self._worker_results = queue.Queue()
        self._load_lock = threading.Lock()
        self._load_thread = None
        self._load_request = None
        self._comparison_lock = threading.Lock()
        self._comparison_thread = None
        self._comparison_request = None
        self._result_poll_after = None

        self.title("記録比較・Step編集 - PokeConStudio")
        self.geometry("1580x920")
        self.minsize(1050, 660)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self._result_poll_after = self.after(50, self._drain_worker_results)
        self.after_idle(self.refresh_comparison)

    @staticmethod
    def _latest_worker_loop(owner, lock, request_attribute,
                            thread_attribute):
        """Run at most one job, then only the latest queued replacement."""
        while True:
            with lock:
                job = getattr(owner, request_attribute)
                setattr(owner, request_attribute, None)
                if job is None:
                    setattr(owner, thread_attribute, None)
                    return
            try:
                job()
            except BaseException as error:
                owner._worker_results.put(("worker_error", str(error)))

    def _submit_latest_worker(self, kind, job):
        if kind == "load":
            lock = self._load_lock
            request_attribute = "_load_request"
            thread_attribute = "_load_thread"
            thread_name = "PokeConStudioRecordingCompare"
        else:
            lock = self._comparison_lock
            request_attribute = "_comparison_request"
            thread_attribute = "_comparison_thread"
            thread_name = "PokeConStudioStepContentCompare"
        with lock:
            setattr(self, request_attribute, job)
            thread = getattr(self, thread_attribute)
            if thread is not None:
                return
            thread = threading.Thread(
                target=self._latest_worker_loop,
                args=(self, lock, request_attribute, thread_attribute),
                name=thread_name, daemon=True)
            setattr(self, thread_attribute, thread)
            thread.start()

    def _drain_worker_results(self):
        """Apply worker results only from Tk's owning thread."""
        self._result_poll_after = None
        if self._closing:
            return
        try:
            for _index in range(20):
                item = self._worker_results.get_nowait()
                if item[0] == "refresh":
                    self._finish_refresh(*item[1])
                elif item[0] == "comparison":
                    self._finish_table_comparison(*item[1])
                elif item[0] == "worker_error":
                    self._comparison_loading = False
                    self._update_replace_button()
                    self.status.set("記録比較workerエラー: " + item[1])
        except queue.Empty:
            pass
        if not self._closing:
            try:
                delay = 10 if not self._worker_results.empty() else 50
                self._result_poll_after = self.after(
                    delay, self._drain_worker_results)
            except tk.TclError:
                self._result_poll_after = None

    def _build(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.compare_tab = ttk.Frame(self.notebook)
        self.operation_tab = ttk.Frame(self.notebook)
        self.command_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.compare_tab, text="3列比較・ソース構成")
        self.notebook.add(self.operation_tab, text="操作記録Step編集")
        self.notebook.add(self.command_tab, text="Commands録画詳細")
        self._build_compare_tab()
        self._build_detail_tabs()

    def _build_compare_tab(self):
        self.operation_name = tk.StringVar(
            value=_display_basename(self.operation_session))
        self.command_name = tk.StringVar(
            value=_display_basename(self.command_recording))
        self.source_name = tk.StringVar(value="未選択")
        self.table_choice = tk.StringVar()
        self.summary = tk.StringVar(
            value="操作記録・Commands録画・現在ソースを選択してください。")
        self.status = tk.StringVar(
            value="時刻ではなく、Step名と再訪順で比較します。")

        guide = ttk.Label(
            self.compare_tab,
            text=("操作記録とCommands録画は、Step名＋同名Stepの再訪順で比較します。"
                  "録画時刻同士は比較しません。展開したCommands実行行はsteps.jsonlの"
                  "サンプリング証跡であり、全コントローラー操作の記録を保証しません。"
                  "選択Stepは、操作記録Step編集の現在内容から対応するソース関数本体へ"
                  "差分確認後に反映できます。関数名・引数はソース側で修正してください。"),
            foreground="#174a7e", justify="left", wraplength=1480)
        guide.pack(fill="x", padx=9, pady=(8, 4))

        selectors = ttk.Frame(self.compare_tab)
        selectors.pack(fill="x", padx=9, pady=(0, 4))
        for column in range(6):
            selectors.columnconfigure(column, weight=1 if column in (1, 3, 5)
                                      else 0)
        ttk.Label(selectors, text="操作記録:").grid(row=0, column=0, sticky="w")
        ttk.Label(selectors, textvariable=self.operation_name, relief="sunken",
                  padding=(5, 2), anchor="w").grid(
                      row=0, column=1, sticky="ew", padx=(4, 10))
        ttk.Button(selectors, text="選択…", command=self.choose_operation_session).grid(
            row=0, column=2, padx=(0, 12))
        ttk.Label(selectors, text="Commands録画:").grid(
            row=0, column=3, sticky="e")
        ttk.Label(selectors, textvariable=self.command_name, relief="sunken",
                  padding=(5, 2), anchor="w").grid(
                      row=0, column=4, sticky="ew", padx=4)
        ttk.Button(selectors, text="選択…", command=self.choose_command_recording).grid(
            row=0, column=5, sticky="w")

        source_row = ttk.Frame(self.compare_tab)
        source_row.pack(fill="x", padx=9, pady=(0, 4))
        ttk.Label(source_row, text="現在ソース:").pack(side="left")
        ttk.Label(source_row, textvariable=self.source_name, relief="sunken",
                  padding=(5, 2), width=28, anchor="w").pack(
                      side="left", padx=4)
        ttk.Label(source_row, text="STATE辞書:").pack(side="left", padx=(9, 0))
        self.table_combo = ttk.Combobox(
            source_row, textvariable=self.table_choice, state="readonly", width=45)
        self.table_combo.pack(side="left", padx=4)
        self.table_combo.bind("<<ComboboxSelected>>", self._table_selected)
        ttk.Button(source_row, text="3列を再読込（未保存Step含む）",
                   command=self._request_refresh_comparison).pack(
                       side="left", padx=(8, 0))
        ttk.Label(source_row, textvariable=self.summary, anchor="w").pack(
            side="left", fill="x", expand=True, padx=10)

        actions = ttk.Frame(self.compare_tab)
        actions.pack(fill="x", padx=9, pady=(0, 4))
        self.add_button = ttk.Button(actions, text="＋Step",
                                     command=self.add_state_step)
        self.delete_button = ttk.Button(actions, text="Step削除",
                                        command=self.delete_state_step)
        self.up_button = ttk.Button(actions, text="↑ 上へ",
                                    command=lambda: self.move_state_step(-1))
        self.down_button = ttk.Button(actions, text="↓ 下へ",
                                      command=lambda: self.move_state_step(1))
        for button in (self.add_button, self.delete_button,
                       self.up_button, self.down_button):
            button.pack(side="left", padx=(0, 3))
        ttk.Separator(actions, orient="vertical").pack(
            side="left", fill="y", padx=7)
        self.apply_button = ttk.Button(
            actions, text="STATE辞書を現在のエディタへ反映",
            command=self.apply_state_draft)
        self.apply_button.pack(side="left", padx=(0, 3))
        self.reset_button = ttk.Button(
            actions, text="構成編集を戻す", command=self.reset_state_draft)
        self.reset_button.pack(side="left")
        ttk.Separator(actions, orient="vertical").pack(
            side="left", fill="y", padx=7)
        self.replace_body_button = ttk.Button(
            actions, text="選択Stepの処理をソース関数へ反映…",
            command=self.replace_selected_function_body, state="disabled")
        self.replace_body_button.pack(side="left")
        ttk.Button(actions, text="選択箇所をソースで開く",
                   command=self.open_selected_source).pack(side="right")

        holder = ttk.Frame(self.compare_tab)
        holder.pack(fill="both", expand=True, padx=9, pady=(0, 4))
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        self.compare_tree = ttk.Treeview(
            holder, columns=("commands", "source"), show="tree headings",
            selectmode="browse")
        self.compare_tree.heading("#0", text="① 操作記録 / step_plan")
        self.compare_tree.heading("commands", text="② Commands録画 / Step再訪")
        self.compare_tree.heading("source", text="③ 現在ソース / STATE構成・処理")
        self.compare_tree.column("#0", width=440, minwidth=220, stretch=True)
        self.compare_tree.column("commands", width=400, minwidth=200, stretch=True)
        self.compare_tree.column("source", width=570, minwidth=260, stretch=True)
        sy = ttk.Scrollbar(holder, orient="vertical", command=self.compare_tree.yview)
        sx = ttk.Scrollbar(holder, orient="horizontal", command=self.compare_tree.xview)
        self.compare_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.compare_tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        self.compare_tree.bind("<<TreeviewSelect>>", self._tree_selected)
        self.compare_tree.bind("<<TreeviewOpen>>", self._tree_opened)
        self.compare_tree.bind("<Double-1>", lambda _event: self.open_selected_source())
        for tag, background in (
                ("same", "#e9f6e9"), ("changed", "#fff1b8"),
                ("missing", "#ffd9d5"), ("source_only", "#dcecff"),
                ("draft", "#ece7fa"), ("detail", "#f6f6f6")):
            self.compare_tree.tag_configure(tag, background=background)

        ttk.Label(self.compare_tab, textvariable=self.status, anchor="w").pack(
            fill="x", padx=10, pady=(0, 7))
        self._set_edit_buttons(False)

    def _build_detail_tabs(self):
        try:
            operation_class, command_class, self.command_model = \
                _load_devstudio_classes(self.project_root)
        except Exception as error:
            message = "既存DevStudio画面を読み込めません: {}".format(error)
            ttk.Label(self.operation_tab, text=message, foreground="#a00000").pack(
                padx=12, pady=12, anchor="w")
            ttk.Label(self.command_tab, text=message, foreground="#a00000").pack(
                padx=12, pady=12, anchor="w")
            self.operation_editor = None
            self.command_workspace = None
            self.command_model = None
            return

        source_path = ""
        try:
            _source, source_path = _source_value(self.source_provider())
        except Exception:
            pass
        self.operation_editor = operation_class(
            self.operation_tab, initial_session=self.operation_session,
            source_path=source_path,
            image_folders_provider=self.image_folders_provider,
            register_image_check_callback=self.register_image_check_callback)
        self.operation_editor.pack(fill="both", expand=True)
        self.command_workspace = command_class(
            self.command_tab, initial_recording=self.command_recording,
            open_source_callback=self._open_source_callback)
        self.command_workspace.pack(fill="both", expand=True)
        self._details_ready = True

        # A path selected inside either reused workspace must also become the
        # saved PokeConStudio profile path and refresh the three-way view.
        self._operation_trace = self.operation_editor.session_path.trace_add(
            "write", lambda *_args: self._detail_path_changed("operation"))
        self._command_trace = self.command_workspace.folder_value.trace_add(
            "write", lambda *_args: self._detail_path_changed("command"))

    def _detail_path_changed(self, kind):
        if self._closing or not self._details_ready:
            return
        if kind == "operation":
            path = self.operation_editor.session_path.get().strip()
            if path:
                self.operation_session = os.path.abspath(path)
                self.operation_name.set(_display_basename(path))
        else:
            path = self.command_workspace.folder_value.get().strip()
            if path:
                self.command_recording = os.path.abspath(path)
                self.command_name.set(_display_basename(path))
        self._notify_paths_changed()
        if self._path_refresh_job is not None:
            try:
                self.after_cancel(self._path_refresh_job)
            except tk.TclError:
                pass
        self._path_refresh_job = self.after(
            250, self._request_refresh_comparison)

    def _confirm_discard_state_draft(self, action):
        if not self._state_draft_dirty:
            return True
        return messagebox.askyesno(
            "未反映のSTATE構成",
            "STATE辞書の追加・削除・移動がまだエディタへ反映されていません。\n"
            "この構成draftを破棄して{}しますか？".format(action),
            parent=self)

    def _request_refresh_comparison(self):
        pending_job = self._path_refresh_job
        self._path_refresh_job = None
        if pending_job is not None:
            try:
                self.after_cancel(pending_job)
            except tk.TclError:
                pass
        operation_editor = getattr(self, "operation_editor", None)
        if (operation_editor is not None
                and getattr(operation_editor, "_loading", False)):
            self.status.set(
                "操作記録の入力索引を読込中です。完了後に3列を再読込してください。")
            return False
        if not self._confirm_discard_state_draft("3列を再読込"):
            self.status.set("未反映のSTATE構成draftを保持しています。")
            return False
        self._state_draft_dirty = False
        self.refresh_comparison()
        return True

    def _notify_paths_changed(self):
        if not callable(self.paths_changed_callback):
            return
        try:
            self.paths_changed_callback(
                self.operation_session, self.command_recording)
        except Exception as error:
            self.status.set("記録パス設定を保存できませんでした: {}".format(error))

    def choose_operation_session(self):
        folder = filedialog.askdirectory(
            parent=self, title="session.jsonがある操作記録を選択",
            initialdir=self.operation_session or self.project_root)
        if not folder:
            return
        if not self._confirm_discard_state_draft("操作記録を切替"):
            return
        self._state_draft_dirty = False
        self.operation_session = os.path.abspath(folder)
        self.operation_name.set(_display_basename(folder))
        self._notify_paths_changed()
        if self.operation_editor is not None:
            self.operation_editor.load_session_dir(folder)
        self.refresh_comparison()

    def choose_command_recording(self):
        folder = filedialog.askdirectory(
            parent=self, title="command_monitor.jsonがあるCommands録画を選択",
            initialdir=self.command_recording or self.project_root)
        if not folder:
            return
        if not self._confirm_discard_state_draft("Commands録画を切替"):
            return
        self._state_draft_dirty = False
        self.command_recording = os.path.abspath(folder)
        self.command_name.set(_display_basename(folder))
        self._notify_paths_changed()
        if self.command_workspace is not None:
            self.command_workspace.load_folder(folder)
        self.refresh_comparison()

    def _read_source(self):
        if not callable(self.source_provider):
            raise ValueError("現在ソースを取得するcallbackがありません。")
        source, path = _source_value(self.source_provider())
        if not source.strip():
            raise ValueError("PokeConStudioでソースを開いてください。")
        return source, os.path.abspath(path) if path else ""

    def refresh_comparison(self):
        if self._closing:
            return
        self._comparison_loading = True
        self._path_refresh_job = None
        self._load_generation += 1
        self._comparison_generation += 1
        generation = self._load_generation
        try:
            source, path = self._read_source()
        except Exception as error:
            self._comparison_loading = False
            self.status.set("現在ソースを取得できません: {}".format(error))
            return

        previous_table = self.current_table_id
        self.source_text = source
        self.source_path = path
        self.source_name.set(_display_basename(path))
        self.source_outline = None
        self.state_draft = None
        self.comparison_result = None
        self.table_labels = {}
        self.table_combo.configure(values=())
        self.table_choice.set("")
        self._set_edit_buttons(False)
        operation_path = self.operation_session
        command_path = self.command_recording
        operation_plan_snapshot = None
        operation_editor = getattr(self, "operation_editor", None)
        if (operation_path and operation_editor is not None
                and not getattr(operation_editor, "_loading", False)):
            editor_session = getattr(operation_editor, "session_dir", "")
            if (editor_session and os.path.normcase(os.path.abspath(
                    editor_session)) == os.path.normcase(os.path.abspath(
                        operation_path))):
                # Snapshot on Tk's thread.  A worker must never read a plan
                # while the embedded editor is mutating it.
                operation_plan_snapshot = copy.deepcopy(
                    getattr(operation_editor, "plan", {}))
        self.status.set("操作記録とCommands録画を読み込んでいます…")

        def worker():
            outline = None
            bundle = None
            recorded_outline = None
            metadata = {}
            events = []
            comparison = None
            operation_visits = []
            command_visits = []
            aligned_visits = []
            errors = []
            try:
                outline = parse_source_outline(source, source_path=path)
            except Exception as error:
                errors.append("現在ソース: {}".format(error))
            if operation_path:
                try:
                    bundle = load_recording_plan_bundle(
                        operation_path, build_input_index=False)
                    if operation_plan_snapshot is not None:
                        bundle = dict(bundle)
                        bundle["plan"] = operation_plan_snapshot
                        bundle["plan_in_memory"] = True
                    # The comparison needs the Step plan and explicit edits,
                    # not a full expansion of every immutable input record.
                    recorded_outline = recording_plan_outline(
                        bundle.get("plan", {}), input_index=None)
                except Exception as error:
                    errors.append("操作記録: {}".format(error))
            if command_path:
                try:
                    if self.command_model is None:
                        _op, _workspace, command_model = \
                            _load_devstudio_classes(self.project_root)
                    else:
                        command_model = self.command_model
                    metadata = command_model.load_command_recording(command_path)
                    events = command_model.load_command_timeline(command_path)
                except Exception as error:
                    errors.append("Commands録画: {}".format(error))
            operation_visits = _operation_visits(recorded_outline)
            known_names = [visit.get("name", "")
                           for visit in operation_visits]
            if outline is not None:
                for table in outline.get("tables", []):
                    known_names.extend(entry.get("name", "")
                                       for entry in table.get("entries", []))
            command_visits = _command_visits(events, known_names)
            aligned_visits = _align_visits(operation_visits, command_visits)
            if outline is not None and recorded_outline is not None:
                tables = outline.get("tables", [])
                table_id = previous_table if any(
                    table.get("id") == previous_table for table in tables
                ) else (tables[0].get("id", "") if tables else "")
                if table_id:
                    try:
                        comparison = compare_recording_to_source(
                            recorded_outline, outline, table_id)
                    except Exception as error:
                        errors.append("Step内容比較: {}".format(error))
            # Do not retain a second full timeline beside the compact visits.
            events = None
            self._worker_results.put(("refresh", (
                generation, source, path, previous_table, outline, bundle,
                recorded_outline, metadata, operation_visits,
                command_visits, aligned_visits, errors, comparison)))

        self._submit_latest_worker("load", worker)

    def _populate_table_choices(self, wanted_id=""):
        labels = {}
        values = []
        selected = ""
        for table in self.source_outline.get("tables", []):
            context = table.get("class_name") or table.get("function_name") or "source"
            label = "{}  —  {} / 行{}".format(
                table.get("name", "STATE"), context,
                table.get("assignment_line", "?"))
            suffix = 2
            original = label
            while label in labels:
                label = "{} ({})".format(original, suffix)
                suffix += 1
            labels[label] = table.get("id", "")
            values.append(label)
            if table.get("id") == wanted_id:
                selected = label
        self.table_labels = labels
        self.table_combo.configure(values=values)
        if not selected and values:
            selected = values[0]
        self.table_choice.set(selected)
        self.current_table_id = labels.get(selected, "")
        self._create_draft()

    def _create_draft(self):
        self.state_draft = None
        if not self.source_outline or not self.current_table_id:
            self._set_edit_buttons(False)
            return
        try:
            self.state_draft = create_state_table_draft(
                self.source_outline, self.current_table_id)
        except ValueError as error:
            self.status.set(str(error))
            self._set_edit_buttons(False)
            return
        self._set_edit_buttons(True)

    def _table_selected(self, _event=None):
        selected_id = self.table_labels.get(self.table_choice.get(), "")
        if (selected_id != self.current_table_id
                and not self._confirm_discard_state_draft("STATE辞書を切替")):
            previous_label = next(
                (label for label, table_id in self.table_labels.items()
                 if table_id == self.current_table_id), "")
            self.table_choice.set(previous_label)
            return
        self._state_draft_dirty = False
        self.current_table_id = selected_id
        self._create_draft()
        self.comparison_result = None
        self._render_comparison()
        self._start_table_comparison()

    def _finish_refresh(self, generation, source, path, previous_table, outline,
                        bundle, recorded_outline, metadata,
                        operation_visits, command_visits, aligned_visits,
                        errors, comparison=None):
        if self._closing or generation != self._load_generation:
            return
        self._comparison_loading = False
        self.source_text = source
        self.source_path = path
        self.source_outline = outline
        self.recording_bundle = bundle
        self.recording_outline = recorded_outline
        self.command_metadata = metadata
        self.operation_visits = operation_visits
        self.command_visits = command_visits
        self.aligned_visits = aligned_visits
        if outline is not None:
            self._populate_table_choices(previous_table)
        else:
            self.current_table_id = ""
            self.state_draft = None
            self._set_edit_buttons(False)
        self.comparison_result = comparison \
            if (comparison and comparison.get("table_id") == self.current_table_id) \
            else None
        self._render_comparison()
        message = " / ".join(errors)
        if message:
            self.status.set("一部を読み込めませんでした: " + message)
        else:
            self.status.set(
                "読込完了。時刻は使わず、Step名＋再訪順で整列しています。")

    def _start_table_comparison(self):
        if not (self.recording_outline and self.source_outline
                and self.current_table_id):
            return
        self._comparison_generation += 1
        generation = self._comparison_generation
        recording_outline = self.recording_outline
        source_outline = self.source_outline
        table_id = self.current_table_id
        self.status.set("選択したSTATE辞書との処理内容を比較しています…")

        def worker():
            try:
                result = compare_recording_to_source(
                    recording_outline, source_outline, table_id)
                error = ""
            except Exception as caught:
                result = None
                error = str(caught)
            self._worker_results.put((
                "comparison", (generation, table_id, result, error)))

        self._submit_latest_worker("comparison", worker)

    def _finish_table_comparison(self, generation, table_id, result, error):
        if (self._closing or generation != self._comparison_generation
                or table_id != self.current_table_id):
            return
        self.comparison_result = result
        self._render_comparison()
        if error:
            self.status.set("Step内容を比較できませんでした: " + error)
        else:
            self.status.set("選択したSTATE辞書との処理内容比較を更新しました。")

    def _selected_table(self):
        if not self.source_outline or not self.current_table_id:
            return None
        return next((table for table in self.source_outline.get("tables", [])
                     if table.get("id") == self.current_table_id), None)

    def _draft_source_entries(self):
        table = self._selected_table()
        if table is None:
            return []
        existing = {entry.get("id"): entry for entry in table.get("entries", [])}
        functions = self.source_outline.get("functions", {})
        result = []
        draft_entries = self.state_draft.get("entries", []) \
            if self.state_draft else table.get("entries", [])
        for draft_entry in draft_entries:
            original = existing.get(draft_entry.get("id"))
            if original is not None:
                # Detail items are immutable display data.  Keep their shared
                # references so a 90k-item source is not cloned on every move.
                value = dict(original)
            else:
                function = functions.get(draft_entry.get("method", ""), {})
                value = {
                    "id": draft_entry.get("id", ""),
                    "line": 0,
                    "function_line": int(function.get("line", 0) or 0),
                    "function_end_line": int(function.get("end_line", 0) or 0),
                    "items": function.get("items", []),
                }
            value.update({
                "name": draft_entry.get("name", ""),
                "method": draft_entry.get("method", ""),
                "is_new": bool(draft_entry.get("is_new")),
            })
            result.append(value)
        return result

    def _comparison_status_by_step(self):
        values = {}
        if not self.comparison_result:
            return values
        if self.comparison_result.get("table_id") != self.current_table_id:
            return values
        for row in self.comparison_result.get("rows", []):
            recorded = row.get("recording") or {}
            if recorded.get("id"):
                values[recorded.get("id")] = row.get("status", "")
        return values

    def _render_comparison(self):
        self.compare_tree.delete(*self.compare_tree.get_children())
        self.tree_meta = {}
        source_entries = self._draft_source_entries()
        operation_visits = self.operation_visits
        command_visits = self.command_visits
        aligned = self.aligned_visits
        operation_status = self._comparison_status_by_step()
        used_source_ids = set()
        same_count = changed_count = missing_count = 0

        for operation, command in aligned:
            operation_name = operation.get("name", "") if operation else ""
            command_name = command.get("name", "") if command else ""
            source_entry = _source_entry_for_visit(
                source_entries, operation=operation, command=command)
            if source_entry is not None:
                used_source_ids.add(source_entry.get("id"))
            visit_same = bool(operation and command
                              and operation.get("key") == command.get("key"))
            op_status = ""
            if operation and operation.get("step"):
                op_status = operation_status.get(
                    operation["step"].get("id"), "")
            if not operation or not command or source_entry is None:
                tag = "missing"
                missing_count += 1
            elif not visit_same or op_status in ("changed", "recording_only"):
                tag = "changed"
                changed_count += 1
            elif source_entry.get("is_new"):
                tag = "draft"
                changed_count += 1
            else:
                tag = "same"
                same_count += 1

            source_text = ""
            if source_entry is not None:
                source_text = "{}  →  {}()".format(
                    source_entry.get("name", ""),
                    source_entry.get("method", ""))
                if source_entry.get("is_new"):
                    source_text += "  [未反映]"
            if op_status:
                label = _STATUS_LABELS.get(op_status, op_status)
                source_text = (source_text + "  /  " + label).strip(" / ")
            iid = "compare-{}".format(len(self.tree_meta) + 1)
            self.compare_tree.insert(
                "", "end", iid=iid, text=_visit_label(operation),
                values=(_visit_label(command), source_text), tags=(tag,),
                open=False)
            recorded_items = (operation.get("step", {}).get("items", [])
                              if operation else [])
            source_items = source_entry.get("items", []) if source_entry else []
            self.tree_meta[iid] = {
                "kind": "step", "source_entry": source_entry,
                "draft_id": source_entry.get("id") if source_entry else "",
                "operation": operation, "command": command,
                "command_rows": command.get("command_rows", [])
                if command else [],
                "recorded_items": recorded_items,
                "source_items": source_items,
                "details_loaded": False,
            }
            if recorded_items or source_items or (command and command.get(
                    "command_rows")):
                self.compare_tree.insert(
                    iid, "end", iid=iid + "-placeholder",
                    text="展開すると処理詳細を表示", values=("", ""),
                    tags=("detail",))

        for source_entry in source_entries:
            if source_entry.get("id") in used_source_ids:
                continue
            iid = "source-{}".format(len(self.tree_meta) + 1)
            source_text = "{}  →  {}()".format(
                source_entry.get("name", ""), source_entry.get("method", ""))
            if source_entry.get("is_new"):
                source_text += "  [未反映]"
            self.compare_tree.insert(
                "", "end", iid=iid, text="", values=("", source_text),
                tags=("draft" if source_entry.get("is_new") else "source_only",),
                open=False)
            self.tree_meta[iid] = {
                "kind": "step", "source_entry": source_entry,
                "draft_id": source_entry.get("id", ""),
                "operation": None, "command": None,
                "recorded_items": [],
                "source_items": source_entry.get("items", []),
                "details_loaded": False,
            }
            if source_entry.get("items"):
                self.compare_tree.insert(
                    iid, "end", iid=iid + "-placeholder",
                    text="展開すると処理詳細を表示", values=("", ""),
                    tags=("detail",))
            missing_count += 1

        self.summary.set(
            "一致 {} / 差分 {} / 片側のみ {} / 操作Step {} / Commands訪問 {} / Source Step {}".format(
                same_count, changed_count, missing_count,
                len(operation_visits), len(command_visits), len(source_entries)))
        self._set_edit_buttons(bool(self.state_draft))

    def _tree_opened(self, _event=None):
        iid = self.compare_tree.focus()
        meta = self.tree_meta.get(iid)
        if not meta or meta.get("kind") != "step" or meta.get("details_loaded"):
            return
        meta["details_loaded"] = True
        for child in self.compare_tree.get_children(iid):
            self.compare_tree.delete(child)
            self.tree_meta.pop(child, None)
        aligned_items = _align_items(
            meta.get("recorded_items", []), meta.get("source_items", []))
        source_entry = meta.get("source_entry") or {}
        source_items = [item for _recorded, item, _status in aligned_items
                        if item is not None]
        assigned_rows, unmatched_rows = _assign_command_rows(
            meta.get("command_rows", []), source_items, self.source_path)
        assignments = {
            id(item): rows for item, rows in zip(source_items, assigned_rows)
        }

        for recorded_item, source_item, item_status in aligned_items:
            matching_rows = assignments.get(id(source_item), []) \
                if source_item is not None else []
            child = "detail-{}".format(len(self.tree_meta) + 1)
            while child in self.tree_meta or self.compare_tree.exists(child):
                child += "x"
            self.compare_tree.insert(
                iid, "end", iid=child, text=_item_text(recorded_item),
                values=(_command_row_text(matching_rows[0])
                        if matching_rows else "", _item_text(source_item)),
                tags=("detail" if item_status == "same" else "changed",))
            self.tree_meta[child] = {
                "kind": "item", "parent": iid,
                "source_entry": source_entry, "source_item": source_item,
                "draft_id": source_entry.get("id") if source_entry else "",
            }
            for row in matching_rows[1:]:
                extra = "detail-{}".format(len(self.tree_meta) + 1)
                while extra in self.tree_meta or self.compare_tree.exists(extra):
                    extra += "x"
                self.compare_tree.insert(
                    iid, "end", iid=extra, text="",
                    values=(_command_row_text(row), ""), tags=("detail",))
                self.tree_meta[extra] = {
                    "kind": "command_item", "parent": iid,
                    "source_entry": source_entry, "source_item": source_item,
                    "draft_id": source_entry.get("id")
                    if source_entry else "",
                }
        for row in unmatched_rows:
            child = "detail-{}".format(len(self.tree_meta) + 1)
            while child in self.tree_meta or self.compare_tree.exists(child):
                child += "x"
            self.compare_tree.insert(
                iid, "end", iid=child, text="",
                values=(_command_row_text(row), ""), tags=("changed",))
            self.tree_meta[child] = {
                "kind": "command_item", "parent": iid,
                "source_entry": source_entry, "source_item": None,
                "draft_id": source_entry.get("id") if source_entry else "",
            }

    def _tree_selected(self, _event=None):
        meta = self._selected_meta()
        self._update_replace_button()
        if not meta:
            return
        source_item = meta.get("source_item") or {}
        source_entry = meta.get("source_entry") or {}
        line = int(source_item.get("line", 0) or
                   source_entry.get("function_line", 0) or
                   source_entry.get("line", 0) or 0)
        if source_entry:
            self.status.set("{} → {}(){}".format(
                source_entry.get("name", ""), source_entry.get("method", ""),
                " / ソース行{}".format(line) if line else ""))

    def _selected_meta(self):
        selected = self.compare_tree.selection()
        if not selected:
            return None
        return self.tree_meta.get(selected[0])

    def _selected_step_meta(self):
        """Resolve a detail row back to its owning three-column Step row."""
        meta = self._selected_meta()
        visited = set()
        while meta and meta.get("kind") != "step":
            parent = meta.get("parent", "")
            if not parent or parent in visited:
                return None
            visited.add(parent)
            meta = self.tree_meta.get(parent)
        return meta

    def _update_replace_button(self):
        button = getattr(self, "replace_body_button", None)
        if button is None:
            return
        meta = self._selected_step_meta()
        enabled = bool(
            callable(self.apply_source_callback) and meta
            and not getattr(self, "_comparison_loading", False)
            and getattr(self, "source_outline", None)
            and meta.get("operation") and meta.get("source_entry")
            and int((meta.get("source_entry") or {}).get(
                "function_line", 0) or 0) > 0)
        button.configure(state="normal" if enabled else "disabled")

    def _current_operation_step(self, step_meta):
        """Return the live raw Step and its input index, never flattened rows."""
        operation = (step_meta or {}).get("operation") or {}
        outline_step = operation.get("step") or {}
        step_id = str(outline_step.get("id", "") or "")
        if not step_id:
            raise ValueError("選択した操作記録StepのIDがありません。")

        plan = None
        input_index = None
        is_dirty = False
        editor = self.operation_editor
        if editor is not None:
            editor_session = getattr(editor, "session_dir", "")
            same_session = bool(editor_session and self.operation_session and
                                os.path.normcase(os.path.abspath(editor_session)) ==
                                os.path.normcase(os.path.abspath(
                                    self.operation_session)))
            if same_session and getattr(editor, "_loading", False):
                raise ValueError(
                    "操作記録の入力索引を読み込み中です。完了後にやり直してください。")
            if same_session:
                plan = getattr(editor, "plan", None)
                input_index = getattr(editor, "input_index", None)
                is_dirty = bool(getattr(editor, "dirty", False))
        if plan is None:
            bundle = self.recording_bundle or {}
            plan = bundle.get("plan", {})
            input_index = bundle.get("input_index")
        step = next((value for value in plan.get("steps", ())
                     if str(value.get("id", "") or "") == step_id), None)
        if step is None:
            raise ValueError(
                "比較後に操作記録Stepが変更されています。3列を再読込してください。")
        if str(step.get("name", "") or "") != str(
                outline_step.get("name", "") or ""):
            raise ValueError(
                "比較後にStep名が変更されています。"
                "3列を再読込（未保存Step含む）してください。")
        known_step_names = {
            str(value.get("name", "") or "")
            for value in plan.get("steps", ())
            if str(value.get("name", "") or "")
        }
        return step, input_index, is_dirty, known_step_names

    def _confirm_function_replacement(self, replacement, note=""):
        dialog = _FunctionReplacementDialog(self, replacement, note=note)
        self.wait_window(dialog)
        return bool(dialog.result)

    def _selected_draft_id(self):
        meta = self._selected_meta()
        return meta.get("draft_id", "") if meta else ""

    def _select_draft_id(self, draft_id):
        for iid, meta in self.tree_meta.items():
            if meta.get("kind") == "step" and meta.get("draft_id") == draft_id:
                self.compare_tree.selection_set(iid)
                self.compare_tree.see(iid)
                return

    def _set_edit_buttons(self, enabled):
        state = "normal" if enabled else "disabled"
        for button in (self.add_button, self.delete_button, self.up_button,
                       self.down_button, self.apply_button, self.reset_button):
            button.configure(state=state)
        self._update_replace_button()

    def replace_selected_function_body(self):
        """Apply one live operation-plan Step to one verified source method."""
        if not callable(self.apply_source_callback):
            return
        step_meta = self._selected_step_meta()
        if not step_meta or not step_meta.get("operation") \
                or not step_meta.get("source_entry"):
            messagebox.showinfo(
                "関数本体を反映",
                "操作記録と現在ソースの両方があるStepを選択してください。",
                parent=self)
            return
        if self._state_draft_dirty:
            messagebox.showinfo(
                "関数本体を反映",
                "未反映のSTATE構成draftがあります。先にSTATE辞書へ反映するか、"
                "構成編集を戻してから関数本体を反映してください。",
                parent=self)
            return
        source_entry = step_meta.get("source_entry") or {}
        if int(source_entry.get("function_line", 0) or 0) <= 0:
            messagebox.showinfo(
                "関数本体を反映",
                "このSTATE参照は self.<関数名> として現在ソースの関数へ"
                "一意に対応できないため、関数本体へ反映できません。",
                parent=self)
            return
        self.status.set("選択Stepから関数本体の反映内容を作成しています…")
        try:
            self.update_idletasks()
        except tk.TclError:
            return
        try:
            latest_source, latest_path = self._read_source()
            latest_path = os.path.abspath(latest_path) if latest_path else ""
            compared_path = os.path.abspath(self.source_path) \
                if self.source_path else ""
            if os.path.normcase(latest_path) != os.path.normcase(compared_path):
                raise ValueError(
                    "比較後に別のソースへ切り替わりました。3列を再読込してください。")
            raw_step, input_index, plan_dirty, known_step_names = \
                self._current_operation_step(step_meta)
            replacement = prepare_recording_step_replacement(
                latest_source, raw_step, source_entry.get("method", ""),
                expected_source_hash=(self.source_outline or {}).get(
                    "source_hash", ""),
                expected_function_line=source_entry.get("function_line", 0),
                input_index=input_index,
                known_step_names=known_step_names)
        except (ValueError, OSError, TypeError, SyntaxError) as error:
            messagebox.showerror("関数本体を反映", str(error), parent=self)
            return
        except Exception as error:
            messagebox.showerror(
                "関数本体を反映",
                "置換内容を作成できません: {}".format(error), parent=self)
            return

        if replacement.get("old_function_source") == \
                replacement.get("new_function_source"):
            messagebox.showinfo(
                "関数本体を反映", "現在ソースとの関数差分はありません。", parent=self)
            return
        notes = []
        if plan_dirty:
            notes.append(
                "操作記録Step編集の未保存内容を使用します。Step計画の保存状態は変えません。")
        shared_note = _shared_method_note(
            self.source_outline, source_entry.get("method"))
        if shared_note:
            notes.append(shared_note)
        warnings = replacement.get("warnings", ())
        if warnings:
            notes.append("Step計画の警告: " + " / ".join(warnings))
        if not self._confirm_function_replacement(
                replacement, note="\n".join(notes)):
            return
        try:
            current_source, current_path = self._read_source()
            if (os.path.normcase(os.path.abspath(current_path or "")) !=
                    os.path.normcase(latest_path) or
                    current_source != latest_source):
                raise ValueError(
                    "確認画面を開いた後にソースが変更されました。再読込してください。")
            result = self.apply_source_callback(
                replacement.get("source", ""), latest_path)
            if result is False:
                return
        except (ValueError, OSError, TypeError) as error:
            messagebox.showerror("関数本体を反映", str(error), parent=self)
            return
        except Exception as error:
            messagebox.showerror(
                "関数本体を反映",
                "エディタへ反映できません: {}".format(error), parent=self)
            return
        self.status.set(
            "{} の処理を {}() 本体へ反映しました。"
            "ソースとStep計画は必要な側だけ保存してください。".format(
                replacement.get("step_name", "Step"),
                replacement.get("method", "")))
        self.refresh_comparison()

    def add_state_step(self):
        if not self.state_draft:
            return
        dialog = _NewStateStepDialog(
            self, self.state_draft.get("available_methods", []))
        self.wait_window(dialog)
        if not dialog.result:
            return
        selected_id = self._selected_draft_id()
        index = None
        if selected_id:
            for position, entry in enumerate(self.state_draft.get("entries", [])):
                if entry.get("id") == selected_id:
                    index = position + 1
                    break
        try:
            entry = add_state_step(
                self.state_draft, dialog.result[0], dialog.result[1], index=index)
        except ValueError as error:
            messagebox.showerror("Step追加", str(error), parent=self)
            return
        self._render_comparison()
        self._select_draft_id(entry.get("id", ""))
        self._state_draft_dirty = True
        self.status.set("Stepを構成draftへ追加しました。反映まではソースを変更しません。")

    def delete_state_step(self):
        if not self.state_draft:
            return
        draft_id = self._selected_draft_id()
        entry = next((value for value in self.state_draft.get("entries", [])
                      if value.get("id") == draft_id), None)
        if entry is None:
            messagebox.showinfo("Step削除", "ソース側のStepを選択してください。",
                                parent=self)
            return
        if not messagebox.askyesno(
                "Step削除",
                "STATE辞書から {} を削除するdraftを作りますか？\n"
                "関数本体は削除しません。".format(entry.get("name", "")),
                parent=self):
            return
        delete_state_step(self.state_draft, draft_id)
        self._render_comparison()
        self._state_draft_dirty = True
        self.status.set("Stepを構成draftから削除しました。関数本体は変更しません。")

    def move_state_step(self, amount):
        if not self.state_draft:
            return
        draft_id = self._selected_draft_id()
        if not draft_id:
            messagebox.showinfo("Step移動", "ソース側のStepを選択してください。",
                                parent=self)
            return
        if not move_state_step(self.state_draft, draft_id, amount):
            return
        self._render_comparison()
        self._select_draft_id(draft_id)
        self._state_draft_dirty = True
        self.status.set("Step順を構成draftで変更しました。")

    def reset_state_draft(self):
        if not self.current_table_id:
            return
        if self._state_draft_dirty and not messagebox.askyesno(
                "構成編集を戻す", "未反映の追加・削除・移動をすべて戻しますか？",
                parent=self):
            return
        self._state_draft_dirty = False
        self._create_draft()
        self._render_comparison()
        self.status.set("STATE辞書の構成draftを現在ソースへ戻しました。")

    def apply_state_draft(self):
        if not self.state_draft or not callable(self.apply_source_callback):
            return
        if not messagebox.askyesno(
                "STATE辞書を反映",
                "追加・削除・移動を現在のソースエディタへ反映します。\n"
                "関数名と関数内部、録画証拠、step_plan.jsonは変更しません。\n"
                "ファイル保存はPokeConStudioのソース側で行います。",
                parent=self):
            return
        try:
            latest_source, latest_path = self._read_source()
            latest_path = os.path.abspath(latest_path) if latest_path else ""
            original_path = os.path.abspath(self.source_path) \
                if self.source_path else ""
            if (os.path.normcase(latest_path) != os.path.normcase(original_path)):
                raise ValueError(
                    "比較後に別のソースへ切り替わりました。3列を再読込してください。")
            # Validation inside StepModel also compares the source hash, so an
            # edit made after this draft was created cannot be overwritten.
            updated = apply_state_table_draft(latest_source, self.state_draft)
            result = self.apply_source_callback(updated, latest_path)
            if result is False:
                return
        except (ValueError, OSError, TypeError) as error:
            messagebox.showerror("STATE辞書を反映", str(error), parent=self)
            return
        except Exception as error:
            messagebox.showerror(
                "STATE辞書を反映", "エディタへ反映できません: {}".format(error),
                parent=self)
            return
        self._state_draft_dirty = False
        self.status.set("現在のエディタへ反映しました。保存はソース側で行ってください。")
        self.refresh_comparison()

    def _open_source_callback(self, path, line=0):
        if callable(self.open_source_callback):
            return self.open_source_callback(path, int(line or 0))
        return False

    def open_selected_source(self):
        if not callable(self.open_source_callback):
            return
        meta = self._selected_meta()
        if not meta:
            return
        source_item = meta.get("source_item") or {}
        source_entry = meta.get("source_entry") or {}
        line = int(source_item.get("line", 0) or
                   source_entry.get("function_line", 0) or
                   source_entry.get("line", 0) or 1)
        self.open_source_callback(self.source_path, line)

    def close(self):
        if self._closing:
            return
        if not self._confirm_discard_state_draft("比較画面を閉じる"):
            return
        if self.operation_editor is not None:
            if getattr(self.operation_editor, "_exporting", False):
                messagebox.showinfo(
                    "確認用出力", "確認用出力の完了後に閉じてください。",
                    parent=self)
                return
            if (getattr(self.operation_editor, "dirty", False)
                    and not messagebox.askyesno(
                        "未保存",
                        "操作記録Step編集に未保存の変更があります。閉じますか？",
                        parent=self)):
                return
        self._closing = True
        self._load_generation += 1
        self._comparison_generation += 1
        self._notify_paths_changed()
        self.destroy()

    def destroy(self):
        if not self._closing:
            self._closing = True
            self._load_generation += 1
            self._comparison_generation += 1
        with self._load_lock:
            self._load_request = None
        with self._comparison_lock:
            self._comparison_request = None
        if self._result_poll_after is not None:
            try:
                self.after_cancel(self._result_poll_after)
            except tk.TclError:
                pass
            self._result_poll_after = None
        if self._path_refresh_job is not None:
            try:
                self.after_cancel(self._path_refresh_job)
            except tk.TclError:
                pass
            self._path_refresh_job = None
        for widget_name in ("operation_editor", "command_workspace"):
            widget = getattr(self, widget_name, None)
            if widget is None:
                continue
            try:
                if widget.winfo_exists():
                    widget.destroy()
            except tk.TclError:
                pass
            setattr(self, widget_name, None)
        try:
            tk.Toplevel.destroy(self)
        except tk.TclError:
            pass


__all__ = [
    "RecordingComparisonWindow",
    "_shared_method_note",
    "_source_entry_for_visit",
    "_state_method_references",
]
