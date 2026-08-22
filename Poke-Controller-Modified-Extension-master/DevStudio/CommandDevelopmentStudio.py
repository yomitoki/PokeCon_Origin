#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-modal, bounded DevStudio tools for Commands recordings and source."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tokenize
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from CommandDevelopmentTools import (
    analyze_recording_events, build_regression_case, load_image_library,
    profile_recorded_video, render_regression_unittest,
)
from CommandRecordingModel import load_command_recording, load_command_timeline


DISPLAY_LIMIT = 500


def _tree(parent, columns, headings, widths, selectmode="browse"):
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(
        frame, columns=columns, show="headings", selectmode=selectmode)
    for column, heading, width in zip(columns, headings, widths):
        tree.heading(column, text=heading)
        tree.column(column, width=width, stretch=True)
    sy = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    sx = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    tree.grid(column=0, row=0, sticky="nsew")
    sy.grid(column=1, row=0, sticky="ns")
    sx.grid(column=0, row=1, sticky="ew")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    frame.pack(fill="both", expand=True, padx=5, pady=5)
    return tree


class CommandDevelopmentWindow(tk.Toplevel):
    """Analyze retained data without executing or importing a Commands class."""

    def __init__(self, parent, folder="", metadata=None, events=None,
                 source_path="", template_root="", open_source_callback=None):
        tk.Toplevel.__init__(self, parent)
        self.parent_workspace = parent
        self.open_source_callback = open_source_callback
        self.template_root = os.path.abspath(template_root) if template_root else ""
        self.metadata = dict(metadata or {})
        self.events = list(events or [])
        self.source_analysis = {}
        self.runtime_analysis = {}
        self.image_library = {"targets": {}, "lists": {}}
        self.source_text = ""
        self._analysis_generation = 0
        self._analysis_processes = set()
        self._analysis_process_lock = threading.Lock()
        self._work_queue = queue.Queue()
        self._profile_cancel = threading.Event()
        self._profile_running = False
        self._quality_rows = {}
        self._transition_rows = {}

        self.title("Commands開発解析（オフライン）")
        self.geometry("1380x850")
        self.minsize(920, 620)
        self.source_path = tk.StringVar(value=source_path)
        self.recording_folder = tk.StringVar(value=folder)
        self.summary = tk.StringVar(
            value="録画とソースを解析します。Commandsの実行・入力送信は行いません。")
        self.profile_interval = tk.DoubleVar(value=0.5)
        self.profile_limit = tk.IntVar(value=600)
        self.profile_status = tk.StringVar(value="画像検知は最大600フレームをバックグラウンド処理します。")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self._drain_work)
        if folder or source_path:
            self.after_idle(self.analyze)

    def _build(self):
        guide = ttk.Label(
            self,
            text=("この画面は録画後のデータだけを使用します。ライブCamera、Commands worker、"
                  "Serial入力には接続しません。条件付きブレークポイントは含みません。"),
            foreground="#174a7e", wraplength=1320, justify="left")
        guide.pack(fill="x", padx=8, pady=(7, 3))

        source_row = ttk.Frame(self)
        source_row.pack(fill="x", padx=8, pady=2)
        ttk.Label(source_row, text="Commandsソース:").pack(side="left")
        ttk.Entry(source_row, textvariable=self.source_path).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(source_row, text="選択…", command=self.choose_source).pack(side="left")
        recording_row = ttk.Frame(self)
        recording_row.pack(fill="x", padx=8, pady=2)
        ttk.Label(recording_row, text="Commands録画:").pack(side="left")
        ttk.Entry(recording_row, textvariable=self.recording_folder).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(recording_row, text="選択…", command=self.choose_recording).pack(side="left")
        self.analyze_button = ttk.Button(
            recording_row, text="ソース・録画を解析", command=self.analyze)
        self.analyze_button.pack(side="left", padx=(5, 0))
        self.regression_button = ttk.Button(
            recording_row, text="回帰ケース＋テスト生成",
            command=self.save_regression_bundle, state="disabled")
        self.regression_button.pack(side="left", padx=3)

        ttk.Label(self, textvariable=self.summary, anchor="w", wraplength=1320).pack(
            fill="x", padx=10, pady=(2, 4))
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=7, pady=(0, 7))
        quality_tab = ttk.Frame(tabs)
        transition_tab = ttk.Frame(tabs)
        variables_tab = ttk.Frame(tabs)
        profile_tab = ttk.Frame(tabs)
        tabs.add(quality_tab, text="品質チェック")
        tabs.add(transition_tab, text="Step遷移")
        tabs.add(variables_tab, text="変数履歴")
        tabs.add(profile_tab, text="録画画像検知再現")

        self.quality_tree = _tree(
            quality_tab,
            ("severity", "code", "function", "line", "message"),
            ("重要度", "種類", "関数", "行", "内容"),
            (75, 180, 220, 60, 760))
        self.quality_tree.tag_configure(
            "ERROR", foreground="#8b0000", background="#ffe7e7")
        self.quality_tree.tag_configure(
            "WARNING", foreground="#7a4200", background="#fff3cd")
        self.quality_tree.bind("<Double-Button-1>", self.open_quality_source)

        self.transition_tree = _tree(
            transition_tab,
            ("kind", "mapping", "from", "to", "count", "time", "function", "line"),
            ("根拠", "状態辞書", "移動元", "移動先", "回数", "最初", "関数", "行"),
            (75, 190, 260, 260, 65, 80, 210, 60))
        self.transition_tree.bind("<Double-Button-1>", self.open_transition_source)

        self.variable_tree = _tree(
            variables_tab,
            ("time", "name", "before", "after", "step"),
            ("動画時刻", "変数", "変更前", "変更後", "Step"),
            (90, 250, 270, 270, 480))
        self.variable_tree.bind("<Double-Button-1>", self.seek_variable_event)

        profile_controls = ttk.Frame(profile_tab)
        profile_controls.pack(fill="x", padx=6, pady=5)
        ttk.Label(profile_controls, text="間隔(秒):").pack(side="left")
        ttk.Spinbox(
            profile_controls, from_=0.05, to=10.0, increment=0.05,
            textvariable=self.profile_interval, width=7).pack(side="left", padx=3)
        ttk.Label(profile_controls, text="最大サンプル:").pack(side="left", padx=(8, 0))
        ttk.Spinbox(
            profile_controls, from_=10, to=2000, increment=10,
            textvariable=self.profile_limit, width=7).pack(side="left", padx=3)
        self.profile_button = ttk.Button(
            profile_controls, text="選択検知を録画で再現",
            command=self.start_profile, state="disabled")
        self.profile_button.pack(side="left", padx=(8, 3))
        self.profile_cancel_button = ttk.Button(
            profile_controls, text="中止", command=self.cancel_profile,
            state="disabled")
        self.profile_cancel_button.pack(side="left")
        ttk.Label(profile_controls, textvariable=self.profile_status).pack(
            side="left", fill="x", expand=True, padx=8)

        profile_panes = ttk.Panedwindow(profile_tab, orient="horizontal")
        profile_panes.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        target_box = ttk.Labelframe(profile_panes, text="ソースで使用する登録画像検知")
        result_box = ttk.Labelframe(profile_panes, text="録画全体の結果")
        profile_panes.add(target_box, weight=1)
        profile_panes.add(result_box, weight=4)
        target_frame = ttk.Frame(target_box)
        target_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.image_targets = tk.Listbox(
            target_frame, selectmode="extended", exportselection=False)
        target_y = ttk.Scrollbar(
            target_frame, orient="vertical", command=self.image_targets.yview)
        target_x = ttk.Scrollbar(
            target_frame, orient="horizontal", command=self.image_targets.xview)
        self.image_targets.configure(
            yscrollcommand=target_y.set, xscrollcommand=target_x.set)
        self.image_targets.grid(column=0, row=0, sticky="nsew")
        target_y.grid(column=1, row=0, sticky="ns")
        target_x.grid(column=0, row=1, sticky="ew")
        target_frame.columnconfigure(0, weight=1)
        target_frame.rowconfigure(0, weight=1)
        target_actions = ttk.Frame(target_box)
        target_actions.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(target_actions, text="すべて選択", command=self.select_all_targets).pack(
            side="left")
        self.profile_tree = _tree(
            result_box,
            ("name", "samples", "matches", "rate", "minimum", "average",
             "maximum", "milliseconds", "changes"),
            ("検知名", "回数", "一致", "一致率", "最小", "平均", "最大",
             "平均ms", "一致切替"),
            (300, 65, 65, 75, 75, 75, 75, 80, 90))

    def choose_source(self):
        path = filedialog.askopenfilename(
            parent=self, title="Commandsソースを選択",
            initialdir=os.path.dirname(self.source_path.get()) or os.getcwd(),
            filetypes=(("Python", "*.py"), ("All files", "*.*")))
        if path:
            self.source_path.set(path)

    def choose_recording(self):
        folder = filedialog.askdirectory(
            parent=self, title="Commands録画フォルダを選択",
            initialdir=self.recording_folder.get() or os.getcwd())
        if folder:
            self.recording_folder.set(folder)

    @staticmethod
    def _infer_source(requested_source, metadata, events):
        """Resolve a source path using only worker-owned plain values."""
        candidates = [str(requested_source or "").strip()]
        source = metadata.get("source", {}) if isinstance(metadata, dict) else {}
        if isinstance(source, dict):
            candidates.append(str(source.get("file", "") or ""))
        for event in events:
            location = event.get("location", {}) if isinstance(event, dict) else {}
            if isinstance(location, dict):
                candidates.append(str(location.get("file", "") or ""))
        return next((os.path.abspath(path) for path in candidates
                     if path and os.path.isfile(path)), "")

    def analyze(self):
        self._cancel_analysis_process()
        self._analysis_generation += 1
        generation = self._analysis_generation
        folder = os.path.abspath(self.recording_folder.get().strip()) \
            if self.recording_folder.get().strip() else ""
        requested_source = self.source_path.get().strip()
        library_path = self._library_path()
        self.analyze_button.configure(state="disabled")
        self.regression_button.configure(state="disabled")
        self.summary.set("ソースと録画をバックグラウンドで解析しています...")

        def worker():
            try:
                if folder:
                    metadata = load_command_recording(folder)
                    events = load_command_timeline(folder)
                else:
                    metadata = dict(self.metadata)
                    events = list(self.events)
                source_path = os.path.abspath(requested_source) \
                    if requested_source and os.path.isfile(requested_source) \
                    else self._infer_source(requested_source, metadata, events)
                if not source_path:
                    raise ValueError("解析するCommandsソースを選択してください。")
                with tokenize.open(source_path) as stream:
                    source_text = stream.read()
                source_analysis = self._analyze_source_out_of_process(source_path)
                runtime_analysis = analyze_recording_events(events)
                image_library = load_image_library(library_path)
                value = (metadata, events, source_path, source_text,
                         source_analysis, runtime_analysis, image_library)
                self._work_queue.put(("analysis", generation, True, value))
            except Exception as error:
                self._work_queue.put(("analysis", generation, False, error))

        threading.Thread(
            target=worker, daemon=True, name="CommandDevelopmentAnalysis").start()

    def _analyze_source_out_of_process(self, source_path):
        """Keep CPython AST parsing from holding DevStudio's Tk GIL."""
        worker_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "CommandDevelopmentWorker.py")
        options = {
            "cwd": os.path.dirname(worker_path),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
        }
        if os.name == "nt":
            # A DevStudio launched from PokeCon already inherits its detached
            # below-normal process priority.  For a standalone DevStudio,
            # forcing the child lower can starve it indefinitely while several
            # capture processes are active, so only suppress a console window.
            options["creationflags"] = getattr(
                subprocess, "CREATE_NO_WINDOW", 0x08000000)
        process = subprocess.Popen(
            [sys.executable, worker_path, source_path], **options)
        with self._analysis_process_lock:
            self._analysis_processes.add(process)
        timed_out = threading.Event()

        def stop_after_timeout():
            if process.poll() is None:
                timed_out.set()
                try:
                    process.kill()
                except OSError:
                    pass

        timer = threading.Timer(120.0, stop_after_timeout)
        timer.daemon = True
        timer.start()
        try:
            result = {key: [] for key in (
                "states", "transitions", "issues", "functions")}
            for line in process.stdout:
                if not line.strip():
                    continue
                record = json.loads(line)
                kind, value = record.get("kind"), record.get("value")
                if kind == "header" and isinstance(value, dict):
                    result.update(value)
                elif kind in result and isinstance(record.get("values"), list):
                    result[kind].extend(record["values"])
            stderr = process.stderr.read()
            process.wait()
        except Exception:
            if process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass
                process.wait()
            raise
        finally:
            timer.cancel()
            with self._analysis_process_lock:
                self._analysis_processes.discard(process)
        if timed_out.is_set():
            raise RuntimeError("ソース静的解析が120秒を超えたため中止しました。")
        if process.returncode:
            detail = (stderr or "解析プロセスが終了しました。").strip()
            raise RuntimeError(detail[-4000:])
        if not isinstance(result, dict):
            raise RuntimeError("ソース解析結果の形式が不正です。")
        return result

    def _cancel_analysis_process(self):
        with self._analysis_process_lock:
            processes = list(self._analysis_processes)
        for process in processes:
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass

    def _drain_work(self):
        try:
            while True:
                kind, generation, succeeded, value = self._work_queue.get_nowait()
                if kind == "analysis" and generation == self._analysis_generation:
                    self._finish_analysis(succeeded, value)
                elif kind == "profile":
                    self._finish_profile(succeeded, value)
                elif kind == "regression":
                    self._finish_regression(succeeded, value)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self._drain_work)

    def _finish_analysis(self, succeeded, value):
        if not succeeded:
            self.analyze_button.configure(state="normal")
            self.summary.set("解析失敗: " + str(value))
            messagebox.showerror("Commands開発解析", str(value), parent=self)
            return
        (self.metadata, self.events, source_path, self.source_text,
         self.source_analysis, self.runtime_analysis, self.image_library) = value
        self.source_path.set(source_path)
        if self.metadata.get("session_dir"):
            self.recording_folder.set(self.metadata["session_dir"])
        self._populate_analysis()

    def update_context(self, folder="", metadata=None, events=None,
                       source_path=""):
        """Refresh an already open window after selecting another recording."""
        self.recording_folder.set(str(folder or ""))
        self.metadata = dict(metadata or {})
        self.events = list(events or [])
        if source_path:
            self.source_path.set(source_path)
        self.analyze()

    def _populate_analysis(self):
        generation = self._analysis_generation
        operations = []
        for tree in (self.quality_tree, self.transition_tree, self.variable_tree):
            operations.extend(("delete", tree, iid) for iid in tree.get_children())
        self._quality_rows = {}
        self._transition_rows = {}
        issues = list(self.source_analysis.get("issues", []))
        library = self.image_library
        registered = library.get("targets", {}) if isinstance(library, dict) else {}
        reference_audit = self.source_analysis.get("image_reference_audit", {})
        resolved_in_source = set(reference_audit.get("target_names", []))
        resolved_in_source.update(reference_audit.get("set_names", []))
        resolved_in_source.update(reference_audit.get("exception_names", []))
        for name in self.source_analysis.get("image_checks", []):
            if name not in registered and name not in resolved_in_source:
                issues.append({
                    "severity": "ERROR", "code": "missing_image_registration",
                    "function": "", "line": 0,
                    "message": "画像検知 {} はDevStudio登録にありません。".format(name),
                })
        for index, issue in enumerate(issues[:DISPLAY_LIMIT]):
            iid = "issue-{}".format(index)
            self._quality_rows[iid] = issue
            severity = str(issue.get("severity", "INFO"))
            operations.append(("insert", self.quality_tree, iid,
                               (severity,), (
                                   severity, issue.get("code", ""),
                                   issue.get("function", ""), issue.get("line", ""),
                                   issue.get("message", ""))))

        row_index = 0
        for item in self.source_analysis.get("transitions", [])[:DISPLAY_LIMIT]:
            iid = "transition-{}".format(row_index); row_index += 1
            self._transition_rows[iid] = item
            operations.append(("insert", self.transition_tree, iid, (), (
                "ソース", item.get("mapping", ""), item.get("from_state", ""),
                item.get("to_state", ""), "", "", item.get("from_function", ""),
                item.get("line", ""))))
        for item in self.runtime_analysis.get("transitions", [])[:DISPLAY_LIMIT - row_index]:
            iid = "transition-{}".format(row_index); row_index += 1
            self._transition_rows[iid] = item
            operations.append(("insert", self.transition_tree, iid, (), (
                "録画", "", item.get("from_step", ""), item.get("to_step", ""),
                item.get("count", 0), "{:.3f}".format(item.get("first_time", 0.0)),
                "", "")))
        for index, item in enumerate(
                self.runtime_analysis.get("variable_history", [])[:DISPLAY_LIMIT]):
            operations.append(("insert", self.variable_tree,
                               "variable-{}".format(index), (), (
                                   "{:.3f}".format(item.get("time", 0.0)),
                                   item.get("name", ""), item.get("before", ""),
                                   item.get("after", ""), item.get("step", ""))))

        self.image_targets.delete(0, "end")
        source_targets = list(self.source_analysis.get("image_checks", []))
        for name in source_targets:
            if name in registered:
                operations.append(("target", name))
        loop_count = len(self.runtime_analysis.get("loops", []))
        suffix = " / 表示上限{}件".format(DISPLAY_LIMIT) if (
            len(issues) > DISPLAY_LIMIT
            or len(self.runtime_analysis.get("variable_history", [])) > DISPLAY_LIMIT) else ""
        final_summary = (
            "品質{}件 / STATE{}件 / ソース遷移{}件 / 録画遷移{}件 / "
            "変数変更{}件 / 反復候補{}件{}".format(
                len(issues), len(self.source_analysis.get("states", [])),
                len(self.source_analysis.get("transitions", [])),
                len(self.runtime_analysis.get("transitions", [])),
                len(self.runtime_analysis.get("variable_history", [])), loop_count, suffix))
        self.summary.set("解析完了。結果一覧を小分けに反映しています...")
        self.after(100, lambda: self._apply_population_batch(
            generation, operations, 0, final_summary))

    def _apply_population_batch(self, generation, operations, offset,
                                final_summary):
        if generation != self._analysis_generation:
            return
        finish = min(len(operations), offset + 10)
        for operation in operations[offset:finish]:
            if operation[0] == "delete":
                _kind, tree, iid = operation
                if tree.exists(iid):
                    tree.delete(iid)
            elif operation[0] == "target":
                self.image_targets.insert("end", operation[1])
            else:
                _kind, tree, iid, tags, values = operation
                tree.insert("", "end", iid=iid, tags=tags, values=values)
        if finish < len(operations):
            self.after(100, lambda: self._apply_population_batch(
                generation, operations, finish, final_summary))
            return
        self.analyze_button.configure(state="normal")
        self.regression_button.configure(
            state="normal" if self.events else "disabled")
        self.profile_button.configure(
            state="normal" if self.image_targets.size() and self._video_path()
            else "disabled")
        self.summary.set(final_summary)

    def _library_path(self):
        return os.path.join(self.template_root, "image_detection_profiles.json") \
            if self.template_root else ""

    def _video_path(self):
        folder = self.recording_folder.get().strip()
        for name in ("recording.mp4", "recording.avi"):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                return path
        return ""

    def open_quality_source(self, _event=None):
        selected = self.quality_tree.selection()
        if not selected:
            return
        issue = self._quality_rows.get(selected[0], {})
        if self.open_source_callback:
            self.open_source_callback(
                self.source_path.get(), max(1, int(issue.get("line", 1) or 1)))

    def open_transition_source(self, _event=None):
        selected = self.transition_tree.selection()
        if not selected:
            return
        item = self._transition_rows.get(selected[0], {})
        line = int(item.get("line", 0) or 0)
        if line and self.open_source_callback:
            self.open_source_callback(self.source_path.get(), line)

    def seek_variable_event(self, _event=None):
        selected = self.variable_tree.selection()
        if not selected or not hasattr(self.parent_workspace, "seek_video"):
            return
        values = self.variable_tree.item(selected[0], "values")
        try:
            self.parent_workspace.seek_video(float(values[0]))
        except (TypeError, ValueError, IndexError):
            pass

    def select_all_targets(self):
        if self.image_targets.size():
            self.image_targets.selection_set(0, "end")

    def start_profile(self):
        if self._profile_running:
            return
        selected = [self.image_targets.get(index)
                    for index in self.image_targets.curselection()]
        if not selected:
            messagebox.showinfo(
                "録画画像検知再現", "画像検知を1件以上選択してください。", parent=self)
            return
        video_path = self._video_path()
        if not video_path:
            messagebox.showwarning(
                "録画画像検知再現", "recording.mp4／aviがありません。", parent=self)
            return
        try:
            interval = max(0.05, float(self.profile_interval.get()))
            limit = min(2000, max(10, int(self.profile_limit.get())))
        except (tk.TclError, TypeError, ValueError):
            interval, limit = 0.5, 600
        library_path = self._library_path()
        template_root = self.template_root
        self._profile_cancel.clear()
        self._profile_running = True
        self.profile_button.configure(state="disabled")
        self.profile_cancel_button.configure(state="normal")
        self.profile_status.set(
            "{}件を最大{}フレーム、バックグラウンドで再現中...".format(len(selected), limit))

        def worker():
            try:
                library = load_image_library(library_path)
                value = profile_recorded_video(
                    video_path, library, template_root, selected,
                    sample_interval=interval, max_samples=limit,
                    cancel_event=self._profile_cancel)
                folder = os.path.dirname(video_path)
                report_path = os.path.join(folder, "command_image_profile.json")
                temporary = report_path + ".tmp"
                with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                os.replace(temporary, report_path)
                value["report_path"] = report_path
                self._work_queue.put(("profile", 0, True, value))
            except Exception as error:
                self._work_queue.put(("profile", 0, False, error))

        threading.Thread(
            target=worker, daemon=True, name="CommandVideoImageProfile").start()

    def cancel_profile(self):
        self._profile_cancel.set()
        self.profile_status.set("中止要求を送りました。処理中フレームの完了を待っています...")

    def _finish_profile(self, succeeded, value):
        self._profile_running = False
        self.profile_button.configure(
            state="normal" if self.image_targets.size() and self._video_path() else "disabled")
        self.profile_cancel_button.configure(state="disabled")
        if not succeeded:
            self.profile_status.set("画像検知再現失敗: " + str(value))
            messagebox.showerror("録画画像検知再現", str(value), parent=self)
            return
        self.profile_tree.delete(*self.profile_tree.get_children())
        for item in value.get("targets", []):
            self.profile_tree.insert("", "end", values=(
                item.get("name", ""), item.get("samples", 0), item.get("matches", 0),
                "{:.1f}%".format(item.get("match_rate", 0.0) * 100.0),
                "{:.4f}".format(item.get("minimum", -1.0)),
                "{:.4f}".format(item.get("average", -1.0)),
                "{:.4f}".format(item.get("maximum", -1.0)),
                "{:.2f}".format(item.get("average_ms", 0.0)),
                len(item.get("changes", []))))
        report_path = str(value.get("report_path", "") or "")
        self.profile_status.set(
            "{}フレーム処理（{:.2f}秒）{}{} / {}".format(
                value.get("processed_samples", 0), value.get("elapsed", 0.0),
                "・総照合数の安全上限で短縮" if value.get("work_capped") else "",
                "・中止済み" if value.get("cancelled") else "", report_path))

    def save_regression_bundle(self):
        if not self.events or not self.source_analysis:
            messagebox.showinfo(
                "回帰ケース", "先にソース・録画を解析してください。", parent=self)
            return
        initial = self.recording_folder.get().strip() or os.getcwd()
        path = filedialog.asksaveasfilename(
            parent=self, title="回帰ケースを保存", initialdir=initial,
            initialfile="command_regression_case.json",
            defaultextension=".json", filetypes=(("JSON", "*.json"),))
        if not path:
            return
        test_path = os.path.join(
            os.path.dirname(path),
            "test_" + os.path.splitext(os.path.basename(path))[0] + ".py")
        metadata = dict(self.metadata)
        events = list(self.events)
        source_analysis = dict(self.source_analysis)
        source_text = self.source_text
        source_path = self.source_path.get()
        self.regression_button.configure(state="disabled")
        self.summary.set("回帰ケースとテストをバックグラウンドで生成しています...")

        def worker():
            try:
                case = build_regression_case(
                    metadata, events, source_analysis,
                    source_text=source_text, source_path=source_path)
                temporary = path + ".tmp"
                with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
                    json.dump(case, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                os.replace(temporary, path)
                temporary_test = test_path + ".tmp"
                with open(temporary_test, "w", encoding="utf-8", newline="\n") as stream:
                    stream.write(render_regression_unittest(path))
                os.replace(temporary_test, test_path)
                self._work_queue.put(("regression", 0, True, test_path))
            except Exception as error:
                self._work_queue.put(("regression", 0, False, error))

        threading.Thread(
            target=worker, daemon=True, name="CommandRegressionExport").start()

    def _finish_regression(self, succeeded, value):
        self.regression_button.configure(
            state="normal" if self.events and self.source_analysis else "disabled")
        if not succeeded:
            self.summary.set("回帰ケース生成失敗: " + str(value))
            messagebox.showerror("回帰ケース", str(value), parent=self)
            return
        self.summary.set("回帰ケースと実行可能なunittestを保存しました: {}".format(value))

    def close(self):
        self._profile_cancel.set()
        self._cancel_analysis_process()
        self._analysis_generation += 1
        self.destroy()
