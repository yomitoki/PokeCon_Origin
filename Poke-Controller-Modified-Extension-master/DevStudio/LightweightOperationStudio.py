#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small, offline Step editor for an operation recording session.

This window deliberately does not import the PokeCon controller/runtime.  Its
inputs are the immutable recording files (``session.json``, ``mappings.json``
and ``inputs.jsonl``), while edits are stored in ``step_plan.json``.  The final
Commands source is never overwritten here; an independently generated preview
can be inspected before source-side work is performed.
"""
from __future__ import print_function

import argparse
import bisect
import copy
import keyword
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import cv2
except ImportError:  # Editing remains available without video dependencies.
    cv2 = None
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

from OperationSessionModel import (STICK_MODE_EXACT, load_mappings,
                                   load_session, operation_video_sources,
                                   readable_switch_operations)
from OperationStepPlan import (JsonlInputIndex, find_branch_arm, find_node,
                               hydrate_plan_times, load_step_plan,
                               materialize_step, move_node, move_step,
                               new_branch, new_call, new_operation, new_return,
                               new_step, rename_step_references, save_preview,
                               save_step_plan, split_step, validate_plan,
                               walk_nodes)
from OperationSourceBinding import (OperationSourceBindingReader,
                                    binding_summary, operation_step_binding)
from OperationSourceBindingView import show_source_binding


PAGE_SIZE = 200


def clock_text(value):
    """Format a duration without depending on a Tk instance."""
    value = max(0.0, float(value or 0.0))
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    seconds = value % 60
    if hours:
        return "{:02d}:{:02d}:{:06.3f}".format(hours, minutes, seconds)
    return "{:02d}:{:06.3f}".format(minutes, seconds)


def recorded_page_ranges(input_index, start_line, end_line, page_size=PAGE_SIZE):
    """Return input-line pages containing at most ``page_size`` raw rows.

    The compact arrays owned by :class:`JsonlInputIndex` are used directly;
    no JSON row is materialised while the hierarchy itself is being built.
    """
    if input_index is None:
        return []
    page_size = max(1, min(PAGE_SIZE, int(page_size or PAGE_SIZE)))
    start_line, end_line = int(start_line or 0), int(end_line or 0)
    if start_line > end_line:
        start_line, end_line = end_line, start_line
    left = bisect.bisect_left(input_index.lines, start_line)
    right = bisect.bisect_right(input_index.lines, end_line)
    result = []
    for offset in range(left, right, page_size):
        last = min(right, offset + page_size) - 1
        result.append({
            "start_line": int(input_index.lines[offset]),
            "end_line": int(input_index.lines[last]),
            "count": last - offset + 1,
        })
    return result


def _normalised_video_sources(sources):
    result = []
    for order, source in enumerate(sources or []):
        if not isinstance(source, dict):
            continue
        try:
            start = float(source.get("timeline_start", 0.0) or 0.0)
            duration = max(0.0, float(source.get("duration", 0.0) or 0.0))
        except (TypeError, ValueError):
            continue
        value = dict(source)
        value["timeline_start"] = start
        value["duration"] = duration
        value["_order"] = order
        result.append(value)
    return result


def select_video_source_for_time(sources, timeline_time, preferred_label=""):
    """Select the segment containing a session-timeline time.

    Segment ranges are half-open: ``[start, end)``.  Only the last distinct
    segment may include its end.  Consequently, a time exactly equal to the
    next segment's ``timeline_start`` always selects that next segment.  When
    clean and overlay videos cover the same range, ``preferred_label`` keeps
    the currently selected variant.
    """
    rows = _normalised_video_sources(sources)
    if not rows:
        return None
    value = float(timeline_time or 0.0)
    starts = sorted(set(item["timeline_start"] for item in rows))
    final_start = starts[-1]
    next_start = {
        start: (starts[index + 1] if index + 1 < len(starts) else None)
        for index, start in enumerate(starts)
    }

    candidates = []
    for item in rows:
        start = item["timeline_start"]
        following = next_start[start]
        declared_end = start + item["duration"] if item["duration"] else None
        if following is not None:
            end = following if declared_end is None else min(declared_end, following)
            contains = start <= value < end
        elif declared_end is None:
            contains = value >= start
        else:
            # The final segment is the sole inclusive-end exception.
            contains = start <= value <= declared_end
        if contains:
            candidates.append(item)
    if not candidates:
        return None

    # Prefer the latest starting segment.  This also protects the half-open
    # boundary when source durations overlap slightly.
    latest = max(item["timeline_start"] for item in candidates)
    candidates = [item for item in candidates
                  if item["timeline_start"] == latest]
    preferred = next((item for item in candidates
                      if item.get("label") == preferred_label), None)
    return preferred or min(candidates, key=lambda item: item["_order"])


def video_target_for_input(sources, input_time, sync_offset=0.0,
                           preferred_label=""):
    """Resolve an input timestamp to a source plus local video timestamp."""
    timeline_time = float(input_time or 0.0) + float(sync_offset or 0.0)
    source = select_video_source_for_time(
        sources, timeline_time, preferred_label=preferred_label)
    if source is None:
        return None
    return {
        "source": source,
        "timeline_time": timeline_time,
        "local_time": max(0.0, timeline_time - source["timeline_start"]),
    }


def _one_line(value, limit=110):
    text = " ".join(str(value or "").strip().splitlines())
    return text if len(text) <= limit else text[:max(0, limit - 1)] + "…"


def _python_identifier(value, fallback="RECORDED_STEP"):
    text = re.sub(r"\W+", "_", str(value or "").strip(),
                  flags=re.UNICODE).strip("_")
    if not text:
        text = fallback
    if text[:1].isdigit():
        text = "_" + text
    if keyword.iskeyword(text):
        text = "_" + text
    return text


def _condition_text(condition):
    if condition is None:
        return "else"
    condition = condition or {}
    if condition.get("kind") == "image_check":
        source = "self.image_check({!r})".format(
            condition.get("target", ""))
    else:
        source = condition.get("source", "") or "False"
    return "not ({})".format(source) if condition.get("negate") else source


class FieldsDialog(tk.Toplevel):
    """Tiny reusable modal form; field descriptions stay data-driven."""

    def __init__(self, parent, title, fields):
        tk.Toplevel.__init__(self, parent)
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.resizable(True, False)
        self.result = None
        self._fields = fields
        self._widgets = {}
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        for row, field in enumerate(fields):
            ttk.Label(body, text=field.get("label", field["key"])).grid(
                row=row, column=0, sticky="nw", padx=(0, 8), pady=4)
            kind = field.get("kind", "entry")
            value = field.get("value", "")
            if kind == "text":
                widget = tk.Text(body, width=58, height=field.get("height", 4),
                                 wrap="word")
                widget.insert("1.0", value)
            elif kind == "combo":
                variable = tk.StringVar(value=value)
                widget = ttk.Combobox(
                    body, textvariable=variable, state="readonly",
                    values=field.get("values", ()), width=48)
                widget._form_variable = variable
            elif kind == "check":
                variable = tk.BooleanVar(value=bool(value))
                widget = ttk.Checkbutton(body, variable=variable,
                                         text=field.get("check_text", ""))
                widget._form_variable = variable
            else:
                variable = tk.StringVar(value=value)
                widget = ttk.Entry(body, textvariable=variable, width=58)
                widget._form_variable = variable
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            self._widgets[field["key"]] = widget
        buttons = ttk.Frame(body)
        buttons.grid(row=len(fields), column=0, columnspan=2, sticky="e",
                     pady=(10, 0))
        ttk.Button(buttons, text="キャンセル", command=self.destroy).pack(
            side="right")
        ttk.Button(buttons, text="OK", command=self._accept).pack(
            side="right", padx=(0, 6))
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Control-Return>", lambda _event: self._accept())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        owner = parent.winfo_toplevel()
        x = owner.winfo_rootx() + max(20, (owner.winfo_width() - self.winfo_width()) // 2)
        y = owner.winfo_rooty() + max(20, (owner.winfo_height() - self.winfo_height()) // 3)
        self.geometry("+{}+{}".format(x, y))
        first = next(iter(self._widgets.values()), None)
        if first is not None:
            first.focus_set()
        self.grab_set()

    def _accept(self):
        result = {}
        for field in self._fields:
            key = field["key"]
            widget = self._widgets[key]
            if field.get("kind") == "text":
                value = widget.get("1.0", "end-1c")
            else:
                value = widget._form_variable.get()
            result[key] = value
        self.result = result
        self.destroy()


def ask_fields(parent, title, fields):
    dialog = FieldsDialog(parent, title, fields)
    parent.wait_window(dialog)
    return dialog.result


class LightweightOperationStudio(ttk.Frame):
    """Hierarchical Step plan and timestamp-linked, low-overhead video."""

    def __init__(self, parent, initial_session="", source_path="",
                 image_folders_provider=None,
                 register_image_check_callback=None):
        ttk.Frame.__init__(self, parent)
        self.session_dir = ""
        self.session = {}
        self.mappings = []
        self.plan = {"steps": []}
        self.input_index = None
        self.plan_existed = False
        self.dirty = False
        self._source_override = source_path
        self._source_binding_reader = OperationSourceBindingReader()
        self.image_folders_provider = image_folders_provider
        self.register_image_check_callback = register_image_check_callback
        self._load_generation = 0
        self._loading = False
        self._export_generation = 0
        self._exporting = False
        self._suppress_source_dirty = False
        self._tree_meta = {}
        self._iid_counter = 0
        self._suppress_tree_seek = False
        self.video_rows = []
        self.video_by_label = {}
        self.video_capture = None
        self.video_fps = 30.0
        self.video_duration = 0.0
        self.video_origin = 0.0
        self.current_time = 0.0
        self.current_frame = None
        self.playing = False
        self._play_job = None
        self._slider_job = None
        self._resize_job = None
        self._slider_internal = False
        self._video_photo = None
        self._build()
        if initial_session:
            self.after_idle(lambda: self.load_session_dir(initial_session))

    def _build(self):
        self.session_path = tk.StringVar()
        self.source_path = tk.StringVar(value=self._source_override)
        self.status = tk.StringVar(value="操作セッションを選択してください。")
        self.video_choice = tk.StringVar()
        self.video_sync = tk.StringVar(value="0.000")
        self.video_time_text = tk.StringVar(value="00:00.000 / 00:00.000")
        self.source_binding_summary = tk.StringVar(
            value="Stepを選ぶと編集対象ソースの対応関数を確認できます（計画とは別ファイル）。")
        self.source_path.trace_add("write", self._on_source_path_changed)

        opener = ttk.Frame(self, padding=(7, 7, 7, 3))
        opener.pack(fill="x")
        opener.columnconfigure(1, weight=1)
        ttk.Label(opener, text="操作セッション").grid(row=0, column=0, sticky="w")
        ttk.Entry(opener, textvariable=self.session_path).grid(
            row=0, column=1, sticky="ew", padx=5)
        ttk.Button(opener, text="選択…", command=self.choose_session).grid(
            row=0, column=2)
        ttk.Button(opener, text="読込", command=self.load_typed_session).grid(
            row=0, column=3, padx=(4, 0))
        ttk.Label(opener, text="Commands編集対象").grid(
            row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(opener, textvariable=self.source_path).grid(
            row=1, column=1, sticky="ew", padx=5, pady=(4, 0))
        ttk.Button(opener, text="ソース選択…", command=self.choose_source).grid(
            row=1, column=2, pady=(4, 0))
        ttk.Button(opener, text="外部で開く", command=self.open_source_external).grid(
            row=1, column=3, padx=(4, 0), pady=(4, 0))
        ttk.Label(opener, textvariable=self.source_binding_summary,
                  foreground="#174a7e", wraplength=1050).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(3, 0))
        ttk.Button(opener, text="ソース対応・処理順", command=self.show_source_binding).grid(
            row=2, column=3, padx=(4, 0), pady=(3, 0))

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=7, pady=(3, 3))
        tree_panel = ttk.Frame(panes)
        video_panel = ttk.Frame(panes)
        panes.add(tree_panel, weight=6)
        panes.add(video_panel, weight=5)
        self._build_tree_panel(tree_panel)
        self._build_video_panel(video_panel)
        ttk.Label(self, textvariable=self.status, anchor="w").pack(
            fill="x", padx=9, pady=(1, 7))

    def _build_tree_panel(self, parent):
        first = ttk.Frame(parent)
        first.pack(fill="x", pady=(0, 3))
        for text, command in (
                ("＋Step", self.add_step), ("編集", self.edit_selected),
                ("削除", self.delete_selected), ("↑", lambda: self.move_selected(-1)),
                ("↓", lambda: self.move_selected(1)), ("Step分割", self.split_selected_step)):
            ttk.Button(first, text=text, command=command).pack(side="left", padx=(0, 3))
        ttk.Button(first, text="計画を保存", command=self.save_plan).pack(
            side="right", padx=(3, 0))
        ttk.Button(first, text="確認用出力", command=self.export_preview).pack(side="right")

        second = ttk.Frame(parent)
        second.pack(fill="x", pady=(0, 4))
        for text, command in (
                ("＋操作", self.add_operation), ("＋関数", self.add_call),
                ("＋画像条件", lambda: self.add_branch("image_check")),
                ("＋式条件", lambda: self.add_branch("expression")),
                ("＋return", self.add_return), ("条件で囲む", self.wrap_selected)):
            ttk.Button(second, text=text, command=command).pack(
                side="left", padx=(0, 3))

        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True)
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        columns = ("time", "input", "kind", "detail")
        self.tree = ttk.Treeview(holder, columns=columns, show="tree headings",
                                 selectmode="browse")
        self.tree.heading("#0", text="記録プランのStep / 処理（Commands実体とは別）")
        self.tree.column("#0", width=340, minwidth=210, stretch=True)
        for column, title, width in (
                ("time", "記録時刻", 92), ("input", "入力行", 105),
                ("kind", "種類", 82), ("detail", "次Step / メモ", 220)):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, minwidth=60,
                             stretch=(column == "detail"))
        sy = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        sx = ttk.Scrollbar(holder, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<<TreeviewClose>>", self._on_tree_close)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda _event: self.edit_selected())

    def _build_video_panel(self, parent):
        controls = ttk.Frame(parent)
        controls.pack(fill="x", pady=(0, 4))
        ttk.Label(controls, text="映像").pack(side="left")
        self.video_combo = ttk.Combobox(
            controls, textvariable=self.video_choice, state="readonly", width=25)
        self.video_combo.pack(side="left", fill="x", expand=True, padx=4)
        self.video_combo.bind("<<ComboboxSelected>>", self.open_selected_video)
        ttk.Label(controls, text="同期補正(秒)").pack(side="left", padx=(4, 2))
        ttk.Entry(controls, textvariable=self.video_sync, width=8).pack(side="left")

        self.video_label = tk.Label(
            parent, text="映像を読み込んでいません。", bg="#101010", fg="#d8d8d8",
            anchor="center", compound="center")
        self.video_label.pack(fill="both", expand=True)
        self.video_label.bind("<Configure>", self._on_video_resize)

        seek = ttk.Frame(parent)
        seek.pack(fill="x", pady=(5, 0))
        self.play_button = ttk.Button(seek, text="▶ 再生", command=self.toggle_play)
        self.play_button.pack(side="left")
        ttk.Button(seek, text="－1秒", command=lambda: self.nudge_video(-1.0)).pack(
            side="left", padx=(4, 0))
        ttk.Button(seek, text="＋1秒", command=lambda: self.nudge_video(1.0)).pack(
            side="left", padx=(3, 5))
        self.video_slider = ttk.Scale(
            seek, from_=0.0, to=0.001, command=self.on_video_slider)
        self.video_slider.pack(side="left", fill="x", expand=True)
        ttk.Label(parent, textvariable=self.video_time_text, anchor="center").pack(
            fill="x", pady=(2, 0))
        capture = ttk.Frame(parent)
        capture.pack(fill="x", pady=(4, 0))
        ttk.Button(
            capture, text="－0.1秒",
            command=lambda: self.nudge_video(-0.1)).pack(side="left")
        ttk.Button(
            capture, text="＋0.1秒",
            command=lambda: self.nudge_video(0.1)).pack(side="left", padx=(3, 8))
        ttk.Button(
            capture, text="現在フレーム → imagecheck…",
            command=self.open_frame_capture).pack(side="left")
        ttk.Label(
            parent,
            text=("ツリー選択で、その操作に対応する映像へジャンプします。"
                  "ここではPokeConへ入力を送信しません。"),
            foreground="#365b7c", wraplength=620, justify="left").pack(
            fill="x", pady=(5, 0))

    def choose_session(self):
        folder = filedialog.askdirectory(
            parent=self, title="session.jsonがある操作セッションを選択")
        if folder:
            self.load_session_dir(folder)

    def load_typed_session(self):
        self.load_session_dir(self.session_path.get().strip())

    def choose_source(self):
        if not self._require_edit_ready():
            return
        path = filedialog.askopenfilename(
            parent=self, title="編集元のPythonソースを選択",
            filetypes=(("Python", "*.py"), ("すべて", "*.*")))
        if path:
            path = os.path.abspath(path)
            self._set_source_path(path)
            self.plan["source_path"] = path
            self._mark_dirty("編集元ソースを変更しました。")
            self._refresh_source_binding_summary()

    def _set_source_path(self, value):
        self._suppress_source_dirty = True
        try:
            self.source_path.set(str(value or ""))
        finally:
            self._suppress_source_dirty = False

    def _on_source_path_changed(self, *_args):
        if (self._suppress_source_dirty or self._loading
                or not self.session_dir):
            return
        value = self.source_path.get().strip()
        if self.plan.get("source_path", "") == value:
            return
        self.plan["source_path"] = value
        self._mark_dirty("編集元ソースを変更しました。")
        self._refresh_source_binding_summary()

    def load_session_dir(self, folder):
        folder = os.path.abspath(str(folder or ""))
        if os.path.isfile(folder):
            folder = os.path.dirname(folder)
        if self._exporting:
            self.session_path.set(self.session_dir)
            messagebox.showinfo(
                "セッション読込", "確認用出力の完了後に読み込んでください。",
                parent=self)
            return False
        if self.dirty and not messagebox.askyesno(
                "未保存", "未保存のStep編集があります。別の読込で破棄しますか？",
                parent=self):
            self.session_path.set(self.session_dir)
            return False
        self._load_generation += 1
        generation = self._load_generation
        self._loading = True
        self.status.set("入力索引をバックグラウンドで作成しています…")

        def worker():
            try:
                session = load_session(folder)
                mappings = load_mappings(folder)
                checkpoints = []
                for mapping in mappings:
                    checkpoints.extend((mapping.get("start_line", 0),
                                        mapping.get("end_line", 0)))
                input_index = JsonlInputIndex(
                    os.path.join(folder, "inputs.jsonl"),
                    checkpoint_lines=checkpoints)
                plan, existed = load_step_plan(
                    folder, session=session, mappings=mappings)
                hydrate_plan_times(plan, input_index)
                validation = validate_plan(plan, input_index=input_index)
                if validation["errors"]:
                    raise ValueError("\n".join(validation["errors"]))
            except Exception as error:
                try:
                    self.after(0, lambda value=str(error):
                               self._finish_session_load_error(
                                   generation, value))
                except (RuntimeError, tk.TclError):
                    pass
                return
            try:
                self.after(0, lambda: self._finish_session_load(
                    generation, folder, session, mappings, input_index,
                    plan, existed))
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(
            target=worker, name="LightweightStepIndex", daemon=True).start()
        return True

    def _finish_session_load_error(self, generation, error):
        if generation != self._load_generation or not self.winfo_exists():
            return
        self._loading = False
        self.session_path.set(self.session_dir)
        messagebox.showerror("セッション読込", error, parent=self)
        self.status.set("セッションを読み込めませんでした。")

    def _finish_session_load(self, generation, folder, session, mappings,
                             input_index, plan, existed):
        if generation != self._load_generation or not self.winfo_exists():
            return
        self._loading = False
        self.stop_video()
        self.close_video()
        self.session_dir = folder
        self.session = session
        self.mappings = mappings
        self.input_index = input_index
        self.plan = plan
        self.plan_existed = existed
        source = self._source_override or plan.get("source_path", "") \
            or session.get("final_source", "")
        if source and not os.path.isabs(source):
            candidate = os.path.join(folder, source)
            source = candidate if os.path.exists(candidate) else os.path.abspath(source)
        self._set_source_path(source)
        if source:
            self.plan["source_path"] = source
        self.session_path.set(folder)
        self.video_sync.set("{:.3f}".format(
            float(session.get("video_sync_offset", 0.0) or 0.0)))
        self._populate_roots()
        self._refresh_source_binding_summary()
        self.refresh_video_sources()
        self._set_dirty(False)
        self.status.set(
            "{} Step / {:,}入力を索引化しました。{}".format(
                len(plan.get("steps", [])), len(input_index),
                "保存済み計画を読込。" if existed else "mappingsから新規計画を作成。"))

    def _new_iid(self, prefix):
        self._iid_counter += 1
        return "{}-{}".format(prefix, self._iid_counter)

    def _remember(self, iid, **meta):
        self._tree_meta[iid] = meta
        return iid

    def _placeholder(self, parent):
        iid = self._new_iid("placeholder")
        self.tree.insert(parent, "end", iid=iid, text="読込…")
        self._remember(iid, type="placeholder")

    def _populate_roots(self, select_step_id=""):
        self._suppress_tree_seek = True
        self.tree.delete(*self.tree.get_children())
        self._tree_meta.clear()
        selected = ""
        for step in self.plan.get("steps", []):
            iid = "step-{}".format(step.get("id"))
            detail = "次: {}".format(step.get("next_step") or "（なし）")
            if step.get("label"):
                detail += " / " + _one_line(step.get("label"), 70)
            self.tree.insert(
                "", "end", iid=iid, text=step.get("name") or "（名称なし）",
                values=(clock_text(step.get("video_start", 0.0)),
                        self._line_text(step), "Step", detail), open=False)
            self._remember(iid, type="step", step_id=step.get("id"),
                           video_time=step.get("video_start", 0.0), loaded=False)
            if step.get("items"):
                self._placeholder(iid)
            if step.get("id") == select_step_id:
                selected = iid
        if selected:
            self.tree.selection_set(selected)
            self.tree.focus(selected)
            self.tree.see(selected)
        # Drain the virtual selection event while seeking is suppressed.  If
        # it fires after this method returns, a structural edit would jump the
        # movie back to the Step start instead of keeping the edited row.
        self.update_idletasks()
        self._suppress_tree_seek = False
        self._refresh_source_binding_summary()

    def _refresh_tree_selection(self, step_id, node_id="", arm_id=""):
        """Rebuild roots while restoring the edited hierarchy location."""
        self._populate_roots(step_id)
        root = "step-{}".format(step_id)
        if not self.tree.exists(root):
            return
        self._suppress_tree_seek = True
        self.tree.item(root, open=True)
        self._expand_tree_item(root)

        def page_contains(meta):
            if meta.get("type") != "node_page" or not node_id:
                return True
            items = meta.get("items", [])
            subset = items[meta.get("start", 0):meta.get("end", 0)]
            return any(node.get("id") == node_id
                       for node, _parent, _index in walk_nodes(subset))

        def find_target(parent):
            for child in self.tree.get_children(parent):
                meta = self._tree_meta.get(child, {})
                if ((node_id and meta.get("node_id") == node_id
                     and meta.get("type") not in ("placeholder", "preview_operation"))
                        or (arm_id and meta.get("arm_id") == arm_id)):
                    return child
                # Explicit plan pages and branch containers are cheap to
                # rebuild.  Recorded ranges stay collapsed so restoring a
                # selection never decodes input behind the user's back.
                if meta.get("type") in ("node_page", "branch", "arm"):
                    if not page_contains(meta):
                        continue
                    self.tree.item(child, open=True)
                    self._expand_tree_item(child)
                    found = find_target(child)
                    if found:
                        return found
            return ""

        selected = find_target(root) if (node_id or arm_id) else root
        if not selected:
            selected = root
        self.tree.selection_set(selected)
        self.tree.focus(selected)
        self.tree.see(selected)
        self.update_idletasks()
        self._suppress_tree_seek = False

    @staticmethod
    def _line_text(value):
        start = int((value or {}).get("input_start", 0) or 0)
        end = int((value or {}).get("input_end", 0) or 0)
        if not start:
            return "追加"
        return "#{:,}".format(start) if start == end else "#{:,}–#{:,}".format(start, end)

    def _forget_children(self, parent):
        def forget(iid):
            for child in self.tree.get_children(iid):
                forget(child)
            self._tree_meta.pop(iid, None)
        for child in self.tree.get_children(parent):
            forget(child)
            self.tree.delete(child)

    def _on_tree_open(self, _event=None):
        iid = self.tree.focus()
        if iid:
            self.after_idle(lambda value=iid: self._expand_tree_item(value))

    def _on_tree_close(self, _event=None):
        iid = self.tree.focus()
        if iid:
            self.after_idle(lambda value=iid: self._collapse_tree_item(value))

    def _collapse_tree_item(self, iid):
        if not self.tree.exists(iid) or self.tree.item(iid, "open"):
            return
        meta = self._tree_meta.get(iid, {})
        if meta.get("type") not in (
                "step", "recorded", "recorded_page", "node_page",
                "operation_page", "branch", "arm"):
            return
        self._forget_children(iid)
        meta["loaded"] = False
        self._placeholder(iid)
        if self.input_index is not None:
            self.input_index.clear_cache()

    def _expand_tree_item(self, iid):
        if not self.tree.exists(iid):
            return
        meta = self._tree_meta.get(iid, {})
        if meta.get("loaded"):
            return
        kind = meta.get("type")
        self._forget_children(iid)
        if kind == "step":
            step = self._find_step(meta.get("step_id"))
            if step:
                self._insert_item_list(iid, step, step.get("items", []))
        elif kind == "recorded":
            self._expand_recorded(iid, meta)
        elif kind == "recorded_page":
            self._insert_recorded_operations(
                iid, meta.get("step_id"), meta.get("node_id"),
                meta.get("input_start", 0), meta.get("input_end", 0))
        elif kind == "node_page":
            items = meta.get("items", [])
            self._insert_item_list(
                iid, self._find_step(meta.get("step_id")),
                items[meta.get("start", 0):meta.get("end", 0)], allow_pages=False)
        elif kind == "operation_page":
            self._insert_operation_leaves(
                iid, meta.get("operations", []), meta.get("step_id"),
                meta.get("node_id"), allow_pages=False)
        elif kind == "branch":
            self._expand_branch(iid, meta)
        elif kind == "arm":
            step = self._find_step(meta.get("step_id"))
            arm = find_branch_arm(step, meta.get("arm_id")) if step else None
            if arm is not None:
                self._insert_item_list(iid, step, arm.get("items", []))
        meta["loaded"] = True

    def _insert_item_list(self, parent, step, items, allow_pages=True):
        if step is None:
            return
        if allow_pages and len(items) > PAGE_SIZE:
            for start in range(0, len(items), PAGE_SIZE):
                end = min(len(items), start + PAGE_SIZE)
                subset = items[start:end]
                iid = self._new_iid("node-page")
                self.tree.insert(
                    parent, "end", iid=iid,
                    text="処理 {:,}–{:,}".format(start + 1, end),
                    values=(clock_text((subset[0] if subset else {}).get(
                                "video_start", 0.0)),
                            "{}件".format(end - start), "ページ", ""))
                self._remember(
                    iid, type="node_page", step_id=step.get("id"), items=items,
                    start=start, end=end,
                    video_time=(subset[0] if subset else {}).get("video_start", 0.0),
                    loaded=False)
                self._placeholder(iid)
            return
        for node in items:
            self._insert_model_node(parent, step, node)

    def _insert_model_node(self, parent, step, node):
        kind = node.get("kind")
        iid = "node-{}-{}".format(node.get("id"), self._new_iid("view"))
        label, kind_label, detail = "", kind, ""
        expandable = False
        meta_type = "node"
        if kind == "recorded":
            label, kind_label, expandable, meta_type = "記録操作", "操作範囲", True, "recorded"
            detail = "展開時だけ読込み"
        elif kind in ("operation", "opaque"):
            label, kind_label = _one_line(node.get("source")), "操作"
        elif kind == "call":
            # A mapped function is intentionally a leaf: only its name is
            # shown; its body belongs in the external source editor.
            label, kind_label = node.get("name") or "（関数名なし）", "関数"
        elif kind == "return":
            label, kind_label = "return " + (node.get("target") or "''"), "return"
        elif kind == "branch":
            first = (node.get("branches") or [{}])[0]
            label = "if " + _condition_text(first.get("condition"))
            kind_label, expandable, meta_type = "条件分岐", True, "branch"
            detail = "imagecheck / 式"
        elif kind in ("ignore", "comment"):
            label = node.get("text") or ("反映不要" if kind == "ignore" else "コメント")
            kind_label = "反映不要" if kind == "ignore" else "コメント"
        else:
            label = kind or "処理"
        self.tree.insert(
            parent, "end", iid=iid, text=label,
            values=(clock_text(node.get("video_start", 0.0)), self._line_text(node),
                    kind_label, detail), open=False)
        self._remember(
            iid, type=meta_type, step_id=step.get("id"), node_id=node.get("id"),
            node_kind=kind, input_start=node.get("input_start", 0),
            input_end=node.get("input_end", 0),
            video_time=node.get("video_start", 0.0), loaded=False)
        if expandable:
            self._placeholder(iid)

    def _expand_recorded(self, parent, meta):
        # Decode one selected recorded range as a continuous stream before
        # paging the resulting operations.  Splitting raw rows first changes
        # a press spanning the boundary into hold/holdEnd, so the Tree would
        # no longer match the final preview.
        self._insert_recorded_operations(
            parent, meta.get("step_id"), meta.get("node_id"),
            meta.get("input_start", 0), meta.get("input_end", 0))

    def _insert_recorded_operations(self, parent, step_id, node_id,
                                    start_line, end_line):
        rows = self.input_index.read_range(start_line, end_line)
        if not rows:
            self.tree.insert(
                parent, "end", text="入力なし", values=("", "", "情報", ""))
            return
        operations = readable_switch_operations(
            rows, stick_mode=STICK_MODE_EXACT,
            initial_state=self.input_index.state_before(start_line),
            origin_time=self.input_index.time_before_line(start_line, 0.0))
        self._insert_operation_leaves(
            parent, operations, step_id, node_id, allow_pages=True)

    def _insert_operation_leaves(self, parent, operations, step_id, node_id,
                                 allow_pages=True):
        if allow_pages and len(operations) > PAGE_SIZE:
            for start in range(0, len(operations), PAGE_SIZE):
                subset = operations[start:start + PAGE_SIZE]
                iid = self._new_iid("operation-page")
                self.tree.insert(
                    parent, "end", iid=iid,
                    text="操作 {:,}–{:,}".format(
                        start + 1, start + len(subset)),
                    values=(clock_text((subset[0] if subset else {}).get("time", 0.0)),
                            "{}件".format(len(subset)), "ページ", ""))
                self._remember(
                    iid, type="operation_page", step_id=step_id, node_id=node_id,
                    operations=subset,
                    video_time=(subset[0] if subset else {}).get("time", 0.0),
                    loaded=False)
                self._placeholder(iid)
            return
        for operation in operations:
            iid = self._new_iid("preview-operation")
            self.tree.insert(
                parent, "end", iid=iid, text=_one_line(operation.get("code")),
                values=(clock_text(operation.get("time", 0.0)),
                        "#{:,}–#{:,}".format(
                            int(operation.get("start_line", 0) or 0),
                            int(operation.get("end_line", 0) or 0)),
                        "記録操作", ""))
            self._remember(
                iid, type="preview_operation", step_id=step_id, node_id=node_id,
                node_kind="operation", source=operation.get("code", ""),
                input_start=operation.get("start_line", 0),
                input_end=operation.get("end_line", 0),
                video_time=operation.get("time", 0.0))

    def _expand_branch(self, parent, meta):
        step = self._find_step(meta.get("step_id"))
        node, _items, _index = find_node(step, meta.get("node_id")) if step else (None, None, -1)
        if not node:
            return
        for index, arm in enumerate(node.get("branches", [])):
            condition = arm.get("condition")
            label = ("if " if index == 0 else "elif ") + _condition_text(condition)
            if condition is None:
                label = "else"
            iid = "arm-{}-{}".format(arm.get("id"), self._new_iid("view"))
            self.tree.insert(
                parent, "end", iid=iid, text=label,
                values=(clock_text(node.get("video_start", 0.0)), "", "分岐先",
                        "{}処理".format(len(arm.get("items", [])))))
            self._remember(
                iid, type="arm", step_id=step.get("id"), node_id=node.get("id"),
                arm_id=arm.get("id"), video_time=node.get("video_start", 0.0),
                loaded=False)
            if arm.get("items"):
                self._placeholder(iid)

    def _on_tree_select(self, _event=None):
        if self._suppress_tree_seek:
            return
        meta = self._selected_meta()
        if not meta or meta.get("type") == "placeholder":
            return
        self._refresh_source_binding_summary()
        if "video_time" in meta:
            self.seek_input_time(meta.get("video_time", 0.0))

    def _selected_source_binding(self, force=False):
        meta = self._selected_meta() or {}
        step = self._find_step(meta.get("step_id")) or {}
        document = self._source_binding_reader.read(
            self.source_path.get().strip(), force=force)
        return operation_step_binding(
            self.session_dir, self.session, self.plan, step, document)

    def _refresh_source_binding_summary(self):
        if hasattr(self, "source_binding_summary"):
            self.source_binding_summary.set(binding_summary(
                self._selected_source_binding()))

    def show_source_binding(self):
        if not self.session_dir or self._loading:
            messagebox.showinfo("ソース対応", "先に操作セッションを読み込んでください。", parent=self)
            return
        show_source_binding(self, self._selected_source_binding(force=True))

    def _selected_meta(self):
        selection = self.tree.selection()
        return self._tree_meta.get(selection[0]) if selection else None

    def _require_edit_ready(self):
        if self._loading:
            self.status.set("入力索引の作成中は編集できません。")
            return False
        if self._exporting:
            self.status.set("確認用出力の作成中は編集できません。")
            return False
        if not self.session_dir and self.input_index is None:
            self.status.set("先に操作セッションを読み込んでください。")
            return False
        return True

    def _find_step(self, step_id):
        return next((step for step in self.plan.get("steps", [])
                     if step.get("id") == step_id), None)

    def _step_for_selection(self, meta=None):
        meta = meta or self._selected_meta()
        return self._find_step((meta or {}).get("step_id"))

    def _sync_value(self):
        try:
            return float(self.video_sync.get() or 0.0)
        except (tk.TclError, TypeError, ValueError):
            return 0.0

    def _materialize_for_edit(self, step):
        if step is None:
            return
        has_recorded = any(node.get("kind") == "recorded"
                           for node, _parent, _index in walk_nodes(step.get("items", [])))
        if not step.get("materialized") or has_recorded:
            self.status.set("{} の記録操作だけを編集用に展開しています…".format(
                step.get("name", "Step")))
            self.update_idletasks()
            materialize_step(step, self.input_index)

    def _resolve_node_after_materialize(self, step, meta):
        node_id = meta.get("node_id", "")
        if node_id:
            node, parent, index = find_node(step, node_id)
            if node is not None:
                return node, parent, index
        line = int(meta.get("input_start", 0) or 0)
        end = int(meta.get("input_end", line) or line)
        source = str(meta.get("source", "") or "")
        candidates = []
        for node, parent, index in walk_nodes(step.get("items", [])):
            if node.get("kind") != "operation":
                continue
            start_line = int(node.get("input_start", 0) or 0)
            end_line = int(node.get("input_end", start_line) or start_line)
            score = (0 if source and node.get("source") == source else 1,
                     0 if start_line <= line <= end_line else 1,
                     abs(start_line - line), abs(end_line - end))
            candidates.append((score, node, parent, index))
        if candidates:
            _score, node, parent, index = min(candidates, key=lambda item: item[0])
            return node, parent, index
        return None, None, -1

    def _content_insertion(self):
        meta = self._selected_meta()
        step = self._step_for_selection(meta)
        if step is None:
            messagebox.showinfo("処理追加", "追加先のStepを選択してください。", parent=self)
            return None
        if meta.get("type") in (
                "node_page", "operation_page", "recorded_page", "placeholder"):
            messagebox.showinfo(
                "処理追加", "ページを開き、追加位置の処理行を選択してください。",
                parent=self)
            return None
        if meta.get("type") == "arm":
            arm = find_branch_arm(step, meta.get("arm_id"))
            if arm is not None:
                return step, arm.setdefault("items", []), len(arm.get("items", [])), meta
        if meta.get("type") != "step":
            if meta.get("type") == "preview_operation":
                self._materialize_for_edit(step)
                node, parent, index = self._resolve_node_after_materialize(
                    step, meta)
            else:
                node, parent, index = find_node(step, meta.get("node_id"))
            if node is not None:
                return step, parent, index + 1, meta
        return step, step.setdefault("items", []), len(step.get("items", [])), meta

    @staticmethod
    def _anchor(meta):
        return {
            "input_start": int((meta or {}).get("input_start", 0) or 0),
            "input_end": int((meta or {}).get("input_end", 0) or 0),
            "video_start": float((meta or {}).get("video_time", 0.0) or 0.0),
            "video_end": float((meta or {}).get("video_time", 0.0) or 0.0),
        }

    def add_step(self):
        if not self._require_edit_ready():
            return
        selected = self._step_for_selection()
        result = ask_fields(self, "Step追加", (
            {"key": "name", "label": "Step名", "value": "NEW_STEP"},
            {"key": "next", "label": "次Step", "value": ""},
            {"key": "label", "label": "説明", "value": "", "kind": "text"},
        ))
        if not result:
            return
        name = result["name"].strip()
        if not name:
            messagebox.showerror("Step追加", "Step名を入力してください。", parent=self)
            return
        created = new_step(name, result["next"].strip(), result["label"].strip())
        steps = self.plan.setdefault("steps", [])
        if selected in steps:
            steps.insert(steps.index(selected) + 1, created)
        else:
            steps.append(created)
        self._mark_dirty("Stepを追加しました。")
        self._populate_roots(created.get("id"))

    def _edit_step(self, step):
        result = ask_fields(self, "Step編集", (
            {"key": "name", "label": "Step名", "value": step.get("name", "")},
            {"key": "next", "label": "次Step", "value": step.get("next_step", "")},
            {"key": "label", "label": "説明", "value": step.get("label", ""),
             "kind": "text"},
            {"key": "auto", "label": "出力", "kind": "check",
             "value": step.get("auto_next", True),
             "check_text": "末尾に次Stepへのreturnを出力"},
            {"key": "refs", "label": "名前変更", "kind": "check", "value": True,
             "check_text": "他Stepの参照名も更新"},
        ))
        if not result:
            return
        name = result["name"].strip()
        if not name:
            messagebox.showerror("Step編集", "Step名を入力してください。", parent=self)
            return
        old = step.get("name", "")
        step.update({
            "name": name, "method": _python_identifier(name),
            "next_step": result["next"].strip(), "label": result["label"].strip(),
            "auto_next": bool(result["auto"]),
        })
        if result["refs"] and old and old != name:
            rename_step_references(self.plan, old, name)
        self._mark_dirty("Stepを変更しました。")
        self._populate_roots(step.get("id"))

    def edit_selected(self):
        if not self._require_edit_ready():
            return
        meta = self._selected_meta()
        step = self._step_for_selection(meta)
        if not meta or step is None:
            return
        if meta.get("type") == "step":
            self._edit_step(step)
            return
        if meta.get("type") == "recorded":
            messagebox.showinfo(
                "編集", "記録操作を開き、編集する個別の操作行を選択してください。",
                parent=self)
            return
        if meta.get("type") not in ("node", "preview_operation", "branch"):
            messagebox.showinfo("編集", "Stepまたは処理行を選択してください。", parent=self)
            return
        if meta.get("type") == "preview_operation":
            # Ask first.  Cancelling an edit must not expand thousands of
            # compact recorded rows or make the plan differ in memory.
            result = ask_fields(self, "操作編集", ({
                "key": "source", "label": "Python操作",
                "value": meta.get("source", ""),
                "kind": "text", "height": 6},))
            if not result:
                return
            before = copy.deepcopy(step)
            self._materialize_for_edit(step)
            node, _parent, _index = self._resolve_node_after_materialize(
                step, meta)
            if node is None:
                step.clear()
                step.update(before)
                messagebox.showerror(
                    "編集", "編集対象を特定できませんでした。", parent=self)
                return
            node["source"] = result["source"].strip()
            self._mark_dirty("処理を変更しました。")
            self._refresh_tree_selection(step.get("id"), node.get("id"))
            return
        else:
            node, _parent, _index = find_node(step, meta.get("node_id"))
        if node is None:
            messagebox.showerror("編集", "編集対象を特定できませんでした。", parent=self)
            return
        kind = node.get("kind")
        if kind in ("operation", "opaque"):
            result = ask_fields(self, "操作編集", ({
                "key": "source", "label": "Python操作", "value": node.get("source", ""),
                "kind": "text", "height": 6},))
            if result:
                node["source"] = result["source"].strip()
        elif kind == "call":
            result = ask_fields(self, "関数名編集", ({
                "key": "name", "label": "関数名", "value": node.get("name", "")},))
            if result:
                node["name"] = result["name"].strip()
        elif kind == "return":
            result = ask_fields(self, "return編集", ({
                "key": "target", "label": "戻り先", "value": node.get("target", "")},))
            if result:
                node["target"] = result["target"].strip()
        elif kind == "branch":
            condition = (node.get("branches") or [{}])[0].get("condition") or {}
            result = self._ask_condition(condition.get("kind", "image_check"), condition)
            if result:
                node["branches"][0]["condition"] = result
        elif kind in ("comment", "ignore"):
            result = ask_fields(self, "説明編集", ({
                "key": "text", "label": "内容", "value": node.get("text", ""),
                "kind": "text"},))
            if result:
                node["text"] = result["text"].strip()
        else:
            result = None
            messagebox.showinfo("編集", "この行は直接編集できません。", parent=self)
        if result:
            self._mark_dirty("処理を変更しました。")
            self._refresh_tree_selection(step.get("id"), node.get("id"))

    def delete_selected(self):
        if not self._require_edit_ready():
            return
        meta = self._selected_meta()
        step = self._step_for_selection(meta)
        if not meta or step is None:
            return
        if meta.get("type") == "step":
            if not messagebox.askyesno(
                    "Step削除", "{} を計画から削除しますか？".format(step.get("name")),
                    parent=self):
                return
            self.plan["steps"].remove(step)
            self._mark_dirty("Stepを削除しました。")
            self._populate_roots()
            return
        if meta.get("type") not in ("node", "recorded", "preview_operation", "branch"):
            return
        if meta.get("type") == "preview_operation":
            if not messagebox.askyesno(
                    "処理削除", "選択した処理を計画から削除しますか？",
                    parent=self):
                return
            before = copy.deepcopy(step)
            self._materialize_for_edit(step)
            node, parent, index = self._resolve_node_after_materialize(
                step, meta)
        else:
            node, parent, index = find_node(step, meta.get("node_id"))
        if node is None:
            if meta.get("type") == "preview_operation":
                step.clear()
                step.update(before)
                messagebox.showerror(
                    "処理削除", "削除対象を特定できませんでした。", parent=self)
            return
        noun = "記録操作範囲" if node.get("kind") == "recorded" else "処理"
        if meta.get("type") != "preview_operation":
            if not messagebox.askyesno(
                    "処理削除", "選択した{}を計画から削除しますか？".format(noun),
                    parent=self):
                return
        del parent[index]
        adjacent = parent[min(index, len(parent) - 1)] if parent else None
        self._mark_dirty("処理を削除しました。")
        self._refresh_tree_selection(
            step.get("id"), (adjacent or {}).get("id", ""))

    def move_selected(self, amount):
        if not self._require_edit_ready():
            return
        meta = self._selected_meta()
        step = self._step_for_selection(meta)
        if not meta or step is None:
            return
        if meta.get("type") == "step":
            changed = move_step(self.plan, step.get("id"), amount)
        elif meta.get("type") in ("node", "recorded", "preview_operation", "branch"):
            if meta.get("type") == "preview_operation":
                before = copy.deepcopy(step)
                self._materialize_for_edit(step)
                node, _parent, _index = self._resolve_node_after_materialize(
                    step, meta)
            else:
                node, _parent, _index = find_node(step, meta.get("node_id"))
            changed = bool(node and move_node(step, node.get("id"), amount))
            if meta.get("type") == "preview_operation" and not changed:
                step.clear()
                step.update(before)
                self.status.set("これ以上移動できません。")
        else:
            changed = False
        if changed:
            self._mark_dirty("順序を変更しました。")
            if meta.get("type") == "step":
                self._populate_roots(step.get("id"))
            else:
                self._refresh_tree_selection(step.get("id"), node.get("id"))

    def split_selected_step(self):
        if not self._require_edit_ready():
            return
        meta = self._selected_meta()
        step = self._step_for_selection(meta)
        if not meta or step is None or meta.get("node_kind") != "operation":
            messagebox.showinfo(
                "Step分割", "分割後の先頭にする記録操作を選択してください。", parent=self)
            return
        split_line = int(meta.get("input_start", 0) or 0)
        if split_line <= int(step.get("input_start", 0) or 0):
            messagebox.showinfo("Step分割", "Step先頭では分割できません。", parent=self)
            return
        result = ask_fields(self, "Step分割", ({
            "key": "name", "label": "後半のStep名",
            "value": (step.get("name") or "STEP") + "_2"},))
        if not result or not result["name"].strip():
            return
        try:
            created = split_step(
                self.plan, step.get("id"), split_line, result["name"].strip(),
                split_node_id=(meta.get("node_id", "")
                               if meta.get("type") == "node" else ""))
            hydrate_plan_times(self.plan, self.input_index)
        except ValueError as error:
            messagebox.showerror("Step分割", str(error), parent=self)
            return
        self._mark_dirty("Stepを分割しました。")
        self._populate_roots(created.get("id"))

    def _insert_new_node(self, node, message):
        if not self._require_edit_ready():
            return
        location = self._content_insertion()
        if location is None:
            return
        step, items, index, _meta = location
        items.insert(index, node)
        self._mark_dirty(message)
        self._refresh_tree_selection(step.get("id"), node.get("id"))

    def add_operation(self):
        if not self._require_edit_ready():
            return
        result = ask_fields(self, "操作追加", ({
            "key": "source", "label": "Python操作",
            "value": "self.press(Button.A, wait=0.0)", "kind": "text", "height": 5},))
        if not result or not result["source"].strip():
            return
        meta = self._selected_meta() or {}
        self._insert_new_node(
            new_operation(result["source"].strip(), self._anchor(meta)),
            "操作を追加しました。")

    def add_call(self):
        if not self._require_edit_ready():
            return
        result = ask_fields(self, "関数呼出し追加", ({
            "key": "name", "label": "関数名", "value": "function_name"},))
        if not result or not result["name"].strip():
            return
        meta = self._selected_meta() or {}
        self._insert_new_node(
            new_call(result["name"].strip(), self._anchor(meta)),
            "関数呼出しを追加しました。")

    def _ask_condition(self, default_kind="image_check", condition=None):
        condition = condition or {}
        default_value = (condition.get("target", "") if default_kind == "image_check"
                         else condition.get("source", ""))
        result = ask_fields(self, "条件設定", (
            {"key": "kind", "label": "条件種類", "kind": "combo",
             "values": ("image_check", "expression"), "value": default_kind},
            {"key": "value", "label": "画像名 / 条件式", "value": default_value},
            {"key": "negate", "label": "反転", "kind": "check",
             "value": condition.get("negate", False), "check_text": "条件を反転（not）"},
        ))
        if not result or not result["value"].strip():
            return None
        return {
            "kind": result["kind"],
            "target": result["value"].strip() if result["kind"] == "image_check" else "",
            "source": result["value"].strip() if result["kind"] == "expression" else "",
            "negate": bool(result["negate"]),
        }

    def add_branch(self, kind):
        if not self._require_edit_ready():
            return
        condition = self._ask_condition(kind)
        if condition is None:
            return
        selected_kind = condition["kind"]
        value = (condition["target"] if selected_kind == "image_check"
                 else condition["source"])
        meta = self._selected_meta() or {}
        node = new_branch(
            selected_kind, value, condition["negate"], anchor=self._anchor(meta))
        self._insert_new_node(node, "条件分岐を追加しました。")

    def add_return(self):
        if not self._require_edit_ready():
            return
        result = ask_fields(self, "return追加", ({
            "key": "target", "label": "戻り先Step / 値", "value": ""},))
        if not result:
            return
        meta = self._selected_meta() or {}
        self._insert_new_node(
            new_return(result["target"].strip(), self._anchor(meta)),
            "returnを追加しました。")

    def wrap_selected(self):
        if not self._require_edit_ready():
            return
        meta = self._selected_meta()
        step = self._step_for_selection(meta)
        if not meta or step is None or meta.get("node_kind") != "operation":
            messagebox.showinfo("条件で囲む", "囲む操作行を選択してください。", parent=self)
            return
        condition = self._ask_condition("image_check")
        if condition is None:
            return
        if meta.get("type") == "preview_operation":
            self._materialize_for_edit(step)
            node, parent, index = self._resolve_node_after_materialize(
                step, meta)
        else:
            node, parent, index = find_node(step, meta.get("node_id"))
        if node is None or node.get("kind") != "operation":
            messagebox.showerror("条件で囲む", "対象操作を特定できませんでした。", parent=self)
            return
        value = condition["target"] if condition["kind"] == "image_check" \
            else condition["source"]
        parent[index] = new_branch(
            condition["kind"], value, condition["negate"],
            wrapped_item=node, anchor=node)
        self._mark_dirty("操作を条件分岐で囲みました。")
        self._refresh_tree_selection(step.get("id"), parent[index].get("id"))

    def save_plan(self):
        if not self._require_edit_ready() or not self.session_dir:
            return
        self.plan["source_path"] = self.source_path.get().strip()
        validation = validate_plan(self.plan, input_index=self.input_index)
        if validation["errors"]:
            messagebox.showerror(
                "計画保存", "\n".join(validation["errors"]), parent=self)
            return
        try:
            self.plan = save_step_plan(
                self.session_dir, self.plan, input_index=self.input_index)
            hydrate_plan_times(self.plan, self.input_index)
        except (OSError, ValueError) as error:
            messagebox.showerror("計画保存", str(error), parent=self)
            return
        self.plan_existed = True
        self._set_dirty(False)
        suffix = " / 警告{}件".format(len(validation["warnings"])) \
            if validation["warnings"] else ""
        self.status.set(
            "step_plan.jsonへ保存しました（revision {}）{}。".format(
                self.plan.get("revision", 0), suffix))
        if validation["warnings"]:
            messagebox.showwarning(
                "計画保存の警告", "\n".join(validation["warnings"]),
                parent=self)

    def export_preview(self):
        if not self._require_edit_ready() or not self.session_dir:
            return
        self.plan["source_path"] = self.source_path.get().strip()
        generation = self._export_generation + 1
        self._export_generation = generation
        self._exporting = True
        session_dir = self.session_dir
        plan = copy.deepcopy(self.plan)
        input_index = (self.input_index.fork_reader()
                       if self.input_index is not None else None)
        self.status.set("確認用ソースをバックグラウンドで作成しています…")

        def worker():
            try:
                paths, warnings = save_preview(
                    session_dir, plan, input_index=input_index)
            except Exception as error:
                try:
                    self.after(0, lambda value=str(error):
                               self._finish_preview_error(generation, value))
                except (RuntimeError, tk.TclError):
                    pass
                return
            try:
                self.after(0, lambda: self._finish_preview(
                    generation, paths, warnings))
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(
            target=worker, name="LightweightStepPreview", daemon=True).start()

    def _finish_preview_error(self, generation, error):
        if generation != self._export_generation or not self.winfo_exists():
            return
        self._exporting = False
        messagebox.showerror("確認用出力", error, parent=self)
        self.status.set("確認用出力に失敗しました。")

    def _finish_preview(self, generation, paths, warnings):
        if generation != self._export_generation or not self.winfo_exists():
            return
        self._exporting = False
        suffix = " / 警告{}件".format(len(warnings)) if warnings else ""
        self.status.set("最終ソースとは別に確認用ソースを出力: {}{}".format(
            paths["source"], suffix))
        messagebox.showinfo(
            "確認用出力",
            "最終ソースは変更していません。\n\n{}{}".format(
                paths["source"],
                "\n\n警告:\n" + "\n".join(warnings) if warnings else ""),
            parent=self)

    def open_source_external(self):
        path = self.source_path.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showinfo("ソースを開く", "存在するソースを指定してください。", parent=self)
            return
        try:
            if os.name == "nt":
                os.startfile(os.path.abspath(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", os.path.abspath(path)])
            else:
                subprocess.Popen(["xdg-open", os.path.abspath(path)])
        except (OSError, subprocess.SubprocessError) as error:
            messagebox.showerror("ソースを開く", str(error), parent=self)

    def _mark_dirty(self, message=""):
        self._set_dirty(True)
        if message:
            self.status.set(message + " 未保存です。")

    def _capture_input_time(self):
        """Translate the displayed video position back to the input timeline."""
        return max(0.0, float(self.video_origin) + float(self.current_time) -
                   self._sync_value())

    def _capture_anchor(self, metadata=None):
        value = metadata if isinstance(metadata, dict) else {}
        try:
            raw_time = value["input_time"] if "input_time" in value \
                else self._capture_input_time()
            input_time = float(raw_time)
        except (TypeError, ValueError):
            input_time = self._capture_input_time()
        line = self.input_index.line_at_time(input_time) \
            if self.input_index is not None else 0
        return {
            "input_start": int(line or 0),
            "input_end": int(line or 0),
            "video_start": input_time,
            "video_end": input_time,
        }

    def _capture_image_roots(self):
        if not callable(self.image_folders_provider):
            return []
        values = self.image_folders_provider() or []
        result, seen = [], set()
        for value in values:
            path = os.path.abspath(str(value or "")) if value else ""
            key = os.path.normcase(path)
            if path and key not in seen:
                result.append(path)
                seen.add(key)
        return result

    def open_frame_capture(self):
        """Freeze the displayed recording frame and open the shared ROI editor."""
        if not self._require_edit_ready():
            return
        if self.current_frame is None or Image is None or cv2 is None:
            messagebox.showinfo(
                "imagecheck登録", "先に映像の対象フレームを表示してください。",
                parent=self)
            return
        source = self.video_by_label.get(self.video_choice.get(), {})
        if "操作情報付き" in str(source.get("label", "")):
            if not messagebox.askyesno(
                    "操作情報付き映像",
                    "操作表示も画像へ写り込む可能性があります。\n"
                    "このフレームから続けて作成しますか？", parent=self):
                return
        if self._slider_job is not None:
            try:
                self.after_cancel(self._slider_job)
            except tk.TclError:
                pass
            self._slider_job = None
        self.stop_video()
        input_time = self._capture_input_time()
        try:
            from OperationSessionStudio import FrameCaptureDialog
        except ImportError as error:
            messagebox.showerror("imagecheck登録", str(error), parent=self)
            return
        capture_context = {
            "load_generation": self._load_generation,
            "session_dir": os.path.normcase(os.path.abspath(
                self.session_dir)) if self.session_dir else "",
            "source_path": self.source_path.get().strip(),
            "selection": tuple(self.tree.selection()),
        }
        FrameCaptureDialog(
            self, self.current_frame.copy(), self.session_dir, self.session,
            float(self.video_origin) + float(self.current_time), None,
            image_roots=self._capture_image_roots(),
            details_callback=lambda metadata, register_source, add_to_plan: (
                self._captured_frame_registration(
                    metadata, register_source, add_to_plan,
                    capture_context=capture_context)),
            allow_step_registration=self._step_for_selection() is not None,
            register_button_text=(
                "保存してimagecheck登録"
                if callable(self.register_image_check_callback)
                else "画像保存＋Step条件追加"),
            extra_metadata={
                "input_time": input_time,
                "video_local_time": float(self.current_time),
                "video_sync_offset": self._sync_value(),
                "source_video": str(source.get("path", "") or ""),
                "source_video_label": str(source.get("label", "") or ""),
            })

    def _captured_frame_registration(self, metadata, register_source,
                                     add_to_plan, capture_context=None):
        path = str((metadata or {}).get("template_path", "") or "")
        if not register_source:
            self.status.set(
                "画像を保存しました: {}（ソースとStepは変更していません）".format(
                    os.path.basename(path)))
            return True

        context = capture_context if isinstance(capture_context, dict) else {}
        if context:
            current_session = os.path.normcase(os.path.abspath(
                self.session_dir)) if self.session_dir else ""
            session_changed = (
                int(context.get("load_generation", -1)) !=
                int(self._load_generation) or
                str(context.get("session_dir", "")) != current_session)
            source_changed = (
                str(context.get("source_path", "")) !=
                self.source_path.get().strip())
            selection_changed = (
                add_to_plan and tuple(context.get("selection", ())) !=
                tuple(self.tree.selection()))
            if session_changed or source_changed or selection_changed:
                details = []
                if session_changed:
                    details.append("操作記録")
                if source_changed:
                    details.append("ソース")
                if selection_changed:
                    details.append("Step選択")
                messagebox.showerror(
                    "imagecheck登録",
                    "切り出し画面を開いた後に{}が変わりました。"
                    "いったん閉じ、現在フレームからやり直してください。".format(
                        "・".join(details)), parent=self)
                return False

        location = None
        node = None
        if add_to_plan:
            location = self._content_insertion()
            if location is None:
                return False
        try:
            from OperationSessionStudio import frame_capture_detection_row
            row = frame_capture_detection_row(metadata)
        except (ImportError, TypeError, ValueError) as error:
            messagebox.showerror("imagecheck登録", str(error), parent=self)
            return False

        registered_name = row["name"]
        if location is not None:
            node = new_branch(
                "image_check", registered_name,
                anchor=self._capture_anchor(metadata))
        source_registered = False
        if callable(self.register_image_check_callback):
            result = self.register_image_check_callback(
                row, str(context.get(
                    "source_path", self.source_path.get().strip())))
            if result is False:
                return False
            if isinstance(result, str) and result:
                registered_name = result
            source_registered = True

        plan_registered = False
        if location is not None:
            step, items, index, _meta = location
            try:
                if registered_name != row["name"]:
                    node["branches"][0]["condition"]["target"] = registered_name
                items.insert(index, node)
                plan_registered = True
                self._mark_dirty("画像条件をStepへ追加しました。")
                self._refresh_tree_selection(step.get("id"), node.get("id"))
            except Exception as error:
                # Once either draft references the PNG, do not let a later Tk
                # refresh failure make the dialog restore that image.  If the
                # insertion itself failed before any commit, rollback remains
                # safe and the error should still propagate.
                if not source_registered and not plan_registered:
                    raise
                if plan_registered:
                    self.dirty = True
                try:
                    self.status.set(
                        "画像登録は完了しましたが、Step表示を更新できません: {}".format(
                            error))
                except Exception:
                    pass
                return True

        try:
            if source_registered and location is not None:
                self.status.set(
                    "画像・ソース定義・Step条件を作成しました。ソースとStep計画は未保存です。")
            elif source_registered:
                self.status.set(
                    "画像とソース定義を作成しました。ソースは未保存です。")
            elif location is not None:
                self.status.set(
                    "画像とStep条件を作成しました。Step計画は未保存です。"
                    "ソース登録はPokeConStudioから行えます。")
            else:
                self.status.set(
                    "画像と登録情報を保存しました。ソース登録はPokeConStudioから行えます。")
        except Exception:
            if not source_registered and not plan_registered:
                raise
        return True

    def _set_dirty(self, dirty):
        self.dirty = bool(dirty)
        owner = self.winfo_toplevel()
        base = "軽量 Step 編集"
        if self.session_dir:
            base += " — " + os.path.basename(self.session_dir)
        owner.title(("* " if self.dirty else "") + base)

    def refresh_video_sources(self):
        self._clear_video_frame(reset_time=True)
        self.video_rows = operation_video_sources(self.session, self.session_dir)
        self.video_by_label = {item.get("label", ""): item
                               for item in self.video_rows}
        labels = [item.get("label", "") for item in self.video_rows]
        self.video_combo.configure(values=labels)
        self.video_choice.set(labels[0] if labels else "")
        if not labels:
            self.video_label.configure(
                image="", text="再生できる記録映像がありません。")
            return
        if cv2 is None or Image is None or ImageTk is None:
            self.video_label.configure(
                image="", text="OpenCV / Pillowがないため映像表示は無効です。\nStep編集は続けられます。")
            return
        # Opening a long movie can allocate codec buffers and delay initial
        # display.  Keep it lazy: selecting a Step/operation (or a combobox
        # entry) opens only the segment that is actually needed.
        self.video_label.configure(
            image="", text="Stepまたは操作を選ぶと、対応する映像を開きます。")

    def close_video(self):
        capture, self.video_capture = self.video_capture, None
        if capture is not None:
            capture.release()

    def _clear_video_frame(self, reset_time=False, text=""):
        self.current_frame = None
        self._video_photo = None
        if reset_time:
            self.current_time = 0.0
            self.video_origin = 0.0
            self.video_duration = 0.0
            self._set_video_slider(0.0)
            self._update_video_time()
        if hasattr(self, "video_label"):
            self.video_label.configure(
                image="", text=text or "映像フレームを表示していません。")

    def open_selected_video(self, _event=None):
        if cv2 is None or Image is None:
            self._clear_video_frame(
                reset_time=True,
                text="OpenCV / Pillowがないため映像を開けません。")
            return False
        source = self.video_by_label.get(self.video_choice.get())
        if not source:
            self._clear_video_frame(reset_time=False)
            return False
        previous_time = self.current_time
        self.stop_video()
        self.close_video()
        self._clear_video_frame(reset_time=False)
        capture = cv2.VideoCapture(source.get("path", ""))
        if not capture.isOpened():
            self._clear_video_frame(reset_time=True, text="映像を開けません。")
            self.status.set("映像を開けません: " + source.get("path", ""))
            return False
        self.video_capture = capture
        self.video_origin = float(source.get("timeline_start", 0.0) or 0.0)
        self.video_fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        measured = frames / max(1.0, self.video_fps)
        self.video_duration = measured or float(source.get("duration", 0.0) or 0.0)
        self.video_slider.configure(to=max(0.001, self.video_duration))
        self.seek_video_local(min(previous_time, self.video_duration))
        return True

    def seek_input_time(self, input_time):
        target = video_target_for_input(
            self.video_rows, input_time, self._sync_value(),
            preferred_label=self.video_choice.get())
        if target is None:
            self.status.set("この操作時刻に対応する映像区間がありません。")
            return False
        source = target["source"]
        if (self.video_choice.get() != source.get("label")
                or self.video_capture is None):
            self.video_choice.set(source.get("label"))
            if not self.open_selected_video():
                return False
        self.seek_video_local(target["local_time"])
        return True

    def on_video_slider(self, value):
        if self._slider_internal or self.playing:
            return
        try:
            target = float(value)
        except (TypeError, ValueError):
            return
        if self._slider_job is not None:
            try:
                self.after_cancel(self._slider_job)
            except tk.TclError:
                pass
        self._slider_job = self.after(
            80, lambda when=target: self.seek_video_local(when))

    def seek_video_local(self, target):
        if self.video_capture is None:
            return False
        self.stop_video()
        requested = min(max(0.0, float(target)), max(0.0, self.video_duration))
        decode_at = requested
        if self.video_duration and requested >= self.video_duration:
            decode_at = max(0.0, self.video_duration - 1.0 / max(1.0, self.video_fps))
        self.video_capture.set(cv2.CAP_PROP_POS_MSEC, decode_at * 1000.0)
        ok, frame = self.video_capture.read()
        if not ok:
            self._clear_video_frame(
                reset_time=False, text="この位置のフレームを取得できません。")
            return False
        self.current_time = requested
        self.current_frame = frame
        self._set_video_slider(requested)
        self._show_frame(frame)
        self._update_video_time()
        return True

    def _set_video_slider(self, value):
        self._slider_internal = True
        try:
            self.video_slider.set(value)
        finally:
            self._slider_internal = False

    def _show_frame(self, frame):
        if frame is None or Image is None or ImageTk is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        width = max(320, self.video_label.winfo_width() - 10)
        height = max(180, self.video_label.winfo_height() - 10)
        resampling = getattr(Image, "Resampling", Image)
        image.thumbnail((width, height), resampling.LANCZOS)
        self._video_photo = ImageTk.PhotoImage(image)
        self.video_label.configure(image=self._video_photo, text="")

    def _on_video_resize(self, _event=None):
        if self.current_frame is None:
            return
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except tk.TclError:
                pass
        self._resize_job = self.after(
            100, lambda: self._show_frame(self.current_frame))

    def _update_video_time(self):
        global_time = self.video_origin + self.current_time
        self.video_time_text.set(
            "全体 {} / 区間 {} / {}".format(
                clock_text(global_time), clock_text(self.current_time),
                clock_text(self.video_duration)))

    def nudge_video(self, amount):
        self.seek_video_local(self.current_time + float(amount))

    def toggle_play(self):
        if self.playing:
            self.stop_video()
            return
        if self.video_capture is None:
            return
        self.playing = True
        self.play_button.configure(text="Ⅱ 一時停止")
        self._play_origin = self.current_time
        self._play_wall = time.monotonic()
        self.video_capture.set(cv2.CAP_PROP_POS_MSEC, self.current_time * 1000.0)
        self._play_tick()

    def _play_tick(self):
        if not self.playing or self.video_capture is None:
            return
        target = self._play_origin + time.monotonic() - self._play_wall
        if target >= self.video_duration:
            self.stop_video()
            self.seek_video_local(self.video_duration)
            return
        decoded_at = float(
            self.video_capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
        if abs(decoded_at - target) > 0.18:
            self.video_capture.set(cv2.CAP_PROP_POS_MSEC, target * 1000.0)
        else:
            for _index in range(max(0, int(round(self.video_fps / 30.0)) - 1)):
                self.video_capture.grab()
        ok, frame = self.video_capture.read()
        if not ok:
            self.stop_video()
            return
        self.current_time = target
        self.current_frame = frame
        self._set_video_slider(target)
        self._show_frame(frame)
        self._update_video_time()
        self._play_job = self.after(33, self._play_tick)

    def stop_video(self):
        self.playing = False
        if hasattr(self, "play_button"):
            self.play_button.configure(text="▶ 再生")
        if self._play_job is not None:
            try:
                self.after_cancel(self._play_job)
            except tk.TclError:
                pass
            self._play_job = None

    def request_close(self):
        if self._exporting:
            messagebox.showinfo(
                "確認用出力", "確認用出力の完了後に閉じてください。",
                parent=self)
            return
        if self.dirty and not messagebox.askyesno(
                "未保存", "未保存のStep編集があります。閉じますか？", parent=self):
            return
        self.stop_video()
        self.close_video()
        self.winfo_toplevel().destroy()

    def destroy(self):
        self._load_generation += 1
        self._export_generation += 1
        for attribute in ("_slider_job", "_resize_job"):
            job = getattr(self, attribute, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, attribute, None)
        self.stop_video()
        self.close_video()
        ttk.Frame.destroy(self)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="操作記録を映像と並べて編集する軽量Step Studio")
    parser.add_argument("--session", default="", help="session.jsonがあるフォルダ")
    parser.add_argument("--source", default="", help="外部で編集する最終Pythonソース")
    arguments = parser.parse_args(argv)
    root = tk.Tk()
    root.geometry("1500x850")
    root.minsize(980, 620)
    workspace = LightweightOperationStudio(
        root, initial_session=arguments.session, source_path=arguments.source)
    workspace.pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", workspace.request_close)
    if not arguments.session:
        root.after_idle(workspace.choose_session)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
