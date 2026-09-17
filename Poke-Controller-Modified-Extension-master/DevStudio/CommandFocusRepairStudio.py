#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DevStudio workspace for target-function focused repair evidence."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from CommandFocusRepairModel import (build_focus_prompt, build_focus_report,
                                     export_focus_bundle,
                                     load_focus_request,
                                     save_focus_request)


def _clock(value):
    value = max(0.0, float(value or 0.0))
    minutes = int(value // 60)
    return "{:02d}:{:06.3f}".format(minutes, value - minutes * 60)


class CommandFocusRepairWorkspace(ttk.Frame):
    """Function intervals, source lines, desired Step notes and Codex export."""

    def __init__(self, parent, initial_recording="", open_recording_callback=None,
                 open_source_callback=None):
        ttk.Frame.__init__(self, parent)
        self.open_recording_callback = open_recording_callback
        self.open_source_callback = open_source_callback
        self.folder = ""
        self.metadata = {}
        self.events = []
        self.report = {}
        self.request = {}
        self.segment_by_id = {}
        self.event_by_iid = {}
        self.current_segment_id = ""
        self.last_export = ""
        self._load_generation = 0
        self._build()
        if initial_recording:
            self.after_idle(lambda: self.load_folder(initial_recording))

    def _build(self):
        self.folder_value = tk.StringVar()
        self.targets_value = tk.StringVar()
        self.padding_value = tk.DoubleVar(value=0.5)
        self.summary = tk.StringVar(value="Commands録画を読み込んでください。")
        self.status = tk.StringVar(
            value="①対象関数を確認 → ②区間ごとに本来のStepを記入 → ③解析資料を出力")
        self.expected_step = tk.StringVar()
        self.annotation_status = tk.StringVar(value="確認中")
        self.selected_title = tk.StringVar(value="対象区間を選択してください。")
        self.source_title = tk.StringVar(value="録画時の対象関数ソース")

        ttk.Label(
            self,
            text=("指定した関数が呼出しスタック内にある動画区間を抽出し、Step・実行行・"
                  "録画時ソースと修正メモを1つのCodex解析資料へまとめます。"),
            foreground="#174a7e", justify="left", wraplength=1450).pack(
                fill="x", padx=8, pady=(7, 3))

        opener = ttk.Frame(self)
        opener.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(opener, text="Commands録画:").pack(side="left")
        ttk.Entry(opener, textvariable=self.folder_value).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(opener, text="選択…", command=self.choose_folder).pack(side="left")
        self.load_button = ttk.Button(opener, text="読込", command=self.load_typed_folder)
        self.load_button.pack(side="left", padx=3)
        ttk.Button(opener, text="フォルダを開く", command=self.open_folder).pack(side="left")

        config = ttk.Labelframe(self, text="集中対象（self.付きでも指定可）")
        config.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(config, text="対象関数:").pack(side="left", padx=(6, 2), pady=5)
        ttk.Entry(config, textvariable=self.targets_value).pack(
            side="left", fill="x", expand=True, padx=3, pady=5)
        ttk.Label(config, text="動画前後余白:").pack(side="left", padx=(8, 2))
        ttk.Spinbox(config, from_=0.0, to=10.0, increment=0.1,
                    textvariable=self.padding_value, width=6).pack(side="left")
        ttk.Label(config, text="秒").pack(side="left", padx=(2, 5))
        ttk.Button(config, text="区間を再解析", command=self.reanalyse).pack(
            side="left", padx=(3, 6))
        ttk.Label(self, textvariable=self.summary, anchor="w").pack(
            fill="x", padx=10, pady=(0, 4))

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=7, pady=(0, 4))
        segment_panel = ttk.Frame(panes)
        evidence_panel = ttk.Frame(panes)
        request_panel = ttk.Frame(panes)
        panes.add(segment_panel, weight=4)
        panes.add(evidence_panel, weight=5)
        panes.add(request_panel, weight=4)
        self._build_segments(segment_panel)
        self._build_evidence(evidence_panel)
        self._build_request(request_panel)

        ttk.Label(self, textvariable=self.status, anchor="w").pack(
            fill="x", padx=9, pady=(0, 6))

    def _build_segments(self, parent):
        ttk.Label(parent, text="① 対象関数の実行区間",
                  foreground="#174a7e").pack(anchor="w", padx=3)
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=3, pady=3)
        self.segment_tree = ttk.Treeview(
            frame, columns=("function", "count", "start", "end", "duration", "step"),
            show="headings", selectmode="extended", height=18)
        for column, label, width in (
                ("function", "関数", 220), ("count", "回", 42),
                ("start", "開始", 78), ("end", "終了", 78),
                ("duration", "秒", 60), ("step", "実際のStep", 260)):
            self.segment_tree.heading(column, text=label)
            self.segment_tree.column(
                column, width=width, stretch=column in ("function", "step"))
        sy = ttk.Scrollbar(frame, orient="vertical", command=self.segment_tree.yview)
        sx = ttk.Scrollbar(frame, orient="horizontal", command=self.segment_tree.xview)
        self.segment_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.segment_tree.grid(column=0, row=0, sticky="nsew")
        sy.grid(column=1, row=0, sticky="ns")
        sx.grid(column=0, row=1, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.segment_tree.bind("<<TreeviewSelect>>", self.on_segment_selected)
        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=3, pady=(0, 3))
        ttk.Button(actions, text="動画・ソース比較で開く",
                   command=self.open_selected_in_recording).pack(side="left")
        ttk.Button(actions, text="対象関数をソース編集で開く",
                   command=self.open_selected_source).pack(side="left", padx=3)

    def _build_evidence(self, parent):
        ttk.Label(parent, text="② 録画時ソース／動画時刻→実行行",
                  foreground="#174a7e").pack(anchor="w", padx=3)
        ttk.Label(parent, textvariable=self.source_title, anchor="w",
                  wraplength=560).pack(fill="x", padx=3, pady=3)
        split = ttk.Panedwindow(parent, orient="vertical")
        split.pack(fill="both", expand=True, padx=3)
        source_frame = ttk.Frame(split)
        event_frame = ttk.Frame(split)
        split.add(source_frame, weight=3)
        split.add(event_frame, weight=2)
        self.source_text = tk.Text(
            source_frame, wrap="none", font=("Consolas", 9),
            background="#171717", foreground="#e5e5e5")
        sy = ttk.Scrollbar(source_frame, orient="vertical", command=self.source_text.yview)
        sx = ttk.Scrollbar(source_frame, orient="horizontal", command=self.source_text.xview)
        self.source_text.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.source_text.grid(column=0, row=0, sticky="nsew")
        sy.grid(column=1, row=0, sticky="ns")
        sx.grid(column=0, row=1, sticky="ew")
        source_frame.columnconfigure(0, weight=1)
        source_frame.rowconfigure(0, weight=1)
        self.source_text.tag_configure(
            "visited", background="#173f5f", foreground="white")
        self.source_text.configure(state="disabled")

        self.event_tree = ttk.Treeview(
            event_frame, columns=("time", "function", "line", "source", "step"),
            show="headings", selectmode="browse", height=7)
        for column, label, width in (
                ("time", "動画", 78), ("function", "実行関数", 170),
                ("line", "行", 50), ("source", "処理", 260),
                ("step", "Step", 240)):
            self.event_tree.heading(column, text=label)
            self.event_tree.column(
                column, width=width, stretch=column in ("source", "step"))
        sy2 = ttk.Scrollbar(event_frame, orient="vertical", command=self.event_tree.yview)
        sx2 = ttk.Scrollbar(event_frame, orient="horizontal", command=self.event_tree.xview)
        self.event_tree.configure(yscrollcommand=sy2.set, xscrollcommand=sx2.set)
        self.event_tree.grid(column=0, row=0, sticky="nsew")
        sy2.grid(column=1, row=0, sticky="ns")
        sx2.grid(column=0, row=1, sticky="ew")
        event_frame.columnconfigure(0, weight=1)
        event_frame.rowconfigure(0, weight=1)
        self.event_tree.bind("<Double-1>", lambda _event: self.open_event_in_recording())

    def _build_request(self, parent):
        ttk.Label(parent, text="③ 修正依頼メモ／Codex出力",
                  foreground="#174a7e").pack(anchor="w", padx=3)
        ttk.Label(parent, textvariable=self.selected_title, anchor="w",
                  wraplength=480).pack(fill="x", padx=3, pady=3)
        ttk.Label(parent, text="本来進むべきStep:").pack(anchor="w", padx=3)
        ttk.Entry(parent, textvariable=self.expected_step).pack(
            fill="x", padx=3, pady=(0, 4))
        state_row = ttk.Frame(parent)
        state_row.pack(fill="x", padx=3, pady=(0, 4))
        ttk.Label(state_row, text="状態:").pack(side="left")
        ttk.Combobox(
            state_row, textvariable=self.annotation_status, state="readonly",
            values=("未対応", "確認中", "完了"), width=10).pack(side="left", padx=3)
        ttk.Label(parent, text="この区間の問題・期待動作:").pack(anchor="w", padx=3)
        issue_frame = ttk.Frame(parent)
        issue_frame.pack(fill="both", expand=True, padx=3, pady=(0, 4))
        self.issue_text = tk.Text(issue_frame, height=7, wrap="word", undo=True)
        issue_scroll = ttk.Scrollbar(
            issue_frame, orient="vertical", command=self.issue_text.yview)
        self.issue_text.configure(yscrollcommand=issue_scroll.set)
        self.issue_text.pack(side="left", fill="both", expand=True)
        issue_scroll.pack(side="right", fill="y")
        ttk.Button(parent, text="選択区間のメモを保存",
                   command=self.save_current_annotation).pack(
                       fill="x", padx=3, pady=(0, 5))
        ttk.Label(parent, text="解析全体への依頼:").pack(anchor="w", padx=3)
        global_frame = ttk.Frame(parent)
        global_frame.pack(fill="both", expand=True, padx=3, pady=(0, 4))
        self.global_text = tk.Text(global_frame, height=7, wrap="word", undo=True)
        global_scroll = ttk.Scrollbar(
            global_frame, orient="vertical", command=self.global_text.yview)
        self.global_text.configure(yscrollcommand=global_scroll.set)
        self.global_text.pack(side="left", fill="both", expand=True)
        global_scroll.pack(side="right", fill="y")
        ttk.Button(parent, text="設定・メモを録画フォルダへ保存",
                   command=self.save_request).pack(fill="x", padx=3, pady=2)
        ttk.Button(parent, text="Codex用プロンプトをコピー",
                   command=self.copy_prompt).pack(fill="x", padx=3, pady=2)
        self.export_button = ttk.Button(
            parent, text="解析資料＋区間動画を出力（選択なし=全件）",
            command=self.export_bundle)
        self.export_button.pack(fill="x", padx=3, pady=2)
        ttk.Button(parent, text="前回の出力先を開く",
                   command=self.open_last_export).pack(fill="x", padx=3, pady=2)

    def choose_folder(self):
        path = filedialog.askdirectory(
            parent=self, title="Commands録画フォルダを選択",
            initialdir=self.folder_value.get() or os.getcwd())
        if path:
            self.folder_value.set(path)
            self.load_folder(path)

    def load_typed_folder(self):
        self.load_folder(self.folder_value.get())

    def load_folder(self, folder):
        folder = os.path.abspath(str(folder or ""))
        if not folder:
            return False
        self._store_current_annotation()
        self._load_generation += 1
        generation = self._load_generation
        self.load_button.configure(state="disabled")
        self.folder_value.set(folder)
        self.status.set("集中修正情報をバックグラウンドで読み込んでいます...")

        def worker():
            try:
                request = load_focus_request(folder)
                report = build_focus_report(folder, request.get("targets", []))
                result, error = (request, report), ""
            except Exception as caught:
                result, error = None, str(caught)
            try:
                self.after(0, lambda: self._finish_load(
                    folder, generation, result, error))
            except tk.TclError:
                pass

        threading.Thread(
            target=worker, name="CommandFocusRepairLoad", daemon=True).start()
        return True

    def _finish_load(self, folder, generation, result, error):
        if generation != self._load_generation:
            return False
        self.load_button.configure(state="normal")
        if error or result is None:
            messagebox.showerror(
                "集中修正", error or "録画を読み込めません。", parent=self)
            self.status.set("読込失敗: " + (error or folder))
            return False
        self.request, self.report = result
        self.folder = folder
        self.metadata = dict(self.report.get("metadata", {}))
        self.events = list(self.report.get("events", []))
        self.targets_value.set(", ".join(self.report.get("targets", [])))
        self.padding_value.set(float(
            self.request.get("clip_padding_seconds", 0.5)))
        self.global_text.delete("1.0", "end")
        self.global_text.insert("1.0", self.request.get("global_request", ""))
        self._refresh_segments()
        return True

    def reanalyse(self):
        if not self.folder:
            return
        self._store_current_annotation()
        targets = self.targets_value.get()
        try:
            self.report = build_focus_report(
                self.folder, targets, metadata=self.metadata, events=self.events)
        except Exception as error:
            messagebox.showerror("集中修正", str(error), parent=self)
            return
        self.targets_value.set(", ".join(self.report.get("targets", [])))
        self._refresh_segments()

    def _refresh_segments(self):
        self.segment_tree.delete(*self.segment_tree.get_children())
        self.segment_by_id = {}
        for segment in self.report.get("segments", []):
            iid = str(segment.get("id"))
            self.segment_by_id[iid] = segment
            self.segment_tree.insert("", "end", iid=iid, values=(
                segment.get("function", ""), segment.get("occurrence", 0),
                _clock(segment.get("start_time", 0.0)),
                _clock(segment.get("end_time", 0.0)),
                "{:.3f}".format(float(segment.get("duration", 0.0) or 0.0)),
                " / ".join(segment.get("step_paths", [])) or "-"))
        matched = sorted({segment.get("function", "")
                          for segment in self.report.get("segments", [])})
        missing = [target for target in self.report.get("targets", [])
                   if target not in matched]
        self.summary.set(
            "Command: {} / 対象{}関数 / 区間{}件 / 未検出: {}".format(
                self.metadata.get("command", "-"), len(self.report.get("targets", [])),
                len(self.report.get("segments", [])), ", ".join(missing) or "なし"))
        self.status.set(
            "区間を選択し、本来進むべきStepと問題内容を記入してください。")
        children = self.segment_tree.get_children()
        if children:
            self.segment_tree.selection_set(children[0])
            self.segment_tree.see(children[0])
        else:
            self._show_segment(None)

    def on_segment_selected(self, _event=None):
        selected = self.segment_tree.selection()
        if not selected:
            return
        wanted = selected[0]
        if wanted == self.current_segment_id:
            return
        self._store_current_annotation()
        self._show_segment(self.segment_by_id.get(wanted))

    def _store_current_annotation(self):
        if not self.current_segment_id or not self.request:
            return
        annotations = self.request.setdefault("annotations", {})
        annotations[self.current_segment_id] = {
            "expected_step": self.expected_step.get().strip(),
            "status": self.annotation_status.get().strip() or "確認中",
            "issue": self.issue_text.get("1.0", "end-1c").strip(),
        }

    def _show_segment(self, segment):
        self.current_segment_id = str(segment.get("id", "")) if segment else ""
        note = self.request.get("annotations", {}).get(
            self.current_segment_id, {}) if segment else {}
        self.expected_step.set(str(note.get("expected_step", "") or ""))
        self.annotation_status.set(str(note.get("status", "") or "確認中"))
        self.issue_text.delete("1.0", "end")
        self.issue_text.insert("1.0", str(note.get("issue", "") or ""))
        self.source_text.configure(state="normal")
        self.source_text.delete("1.0", "end")
        self.event_tree.delete(*self.event_tree.get_children())
        self.event_by_iid = {}
        if not segment:
            self.selected_title.set("対象区間がありません。")
            self.source_title.set("録画経路内で対象関数を検出できませんでした。")
            self.source_text.configure(state="disabled")
            return
        self.selected_title.set("{}() #{} / {}–{} / {:.3f}秒".format(
            segment.get("function", ""), segment.get("occurrence", 0),
            _clock(segment.get("start_time", 0.0)),
            _clock(segment.get("end_time", 0.0)),
            float(segment.get("duration", 0.0) or 0.0)))
        source = self.report.get("sources", {}).get(
            segment.get("function", ""), {})
        text = str(source.get("text", "") or "")
        start_line = int(source.get("start_line", 0) or 0)
        for number, line in enumerate(text.splitlines(True), start=start_line):
            self.source_text.insert("end", "{:6d} | {}".format(number, line))
        visited = set()
        all_events = list(segment.get("events", []) or [])
        if len(all_events) > 5000:
            visible_events = list(enumerate(all_events[:2500]))
            visible_events.extend(enumerate(
                all_events[-2500:], start=len(all_events) - 2500))
        else:
            visible_events = list(enumerate(all_events))
        for actual_index, event in visible_events:
            location = event.get("location", {}) if isinstance(event, dict) else {}
            if not isinstance(location, dict):
                location = {}
            frames = [location]
            frames.extend(frame for frame in location.get("stack", [])
                          if isinstance(frame, dict))
            target_location = next(
                (frame for frame in frames
                 if str(frame.get("function", "")) == segment.get("function", "")),
                location)
            try:
                line = int(target_location.get("line", 0) or 0)
            except (TypeError, ValueError):
                line = 0
            iid = "focus-event-{}".format(actual_index)
            self.event_by_iid[iid] = event
            self.event_tree.insert("", "end", iid=iid, values=(
                _clock(event.get("video_time", 0.0)),
                target_location.get("function", "") or "-", line or "-",
                target_location.get("source", "") or "-",
                event.get("step_text", "") or "-"), tags=(str(event.get("index", 0)),))
            if start_line and line >= start_line:
                visited.add(line - start_line + 1)
        for row in visited:
            self.source_text.tag_add(
                "visited", "{}.0".format(row), "{}.end".format(row))
        self.source_title.set("{} / {}–{}行 / {}".format(
            source.get("kind", ""), source.get("start_line", 0),
            source.get("end_line", 0), source.get("path", "") or "取得不能")
            + (" / 実行行{}件中5,000件表示".format(len(all_events))
               if len(all_events) > 5000 else ""))
        self.source_text.configure(state="disabled")

    def save_current_annotation(self):
        self._store_current_annotation()
        self.status.set("選択区間のメモを一時保存しました。録画フォルダへ保存してください。")

    def _collect_request(self):
        self._store_current_annotation()
        self.request["targets"] = list(self.report.get("targets", []))
        self.request["clip_padding_seconds"] = float(self.padding_value.get())
        self.request["global_request"] = self.global_text.get(
            "1.0", "end-1c").strip()
        return self.request

    def save_request(self):
        if not self.folder:
            return False
        try:
            self.request = save_focus_request(
                self.folder, self._collect_request())
        except (OSError, TypeError, ValueError, tk.TclError) as error:
            messagebox.showerror("集中修正", str(error), parent=self)
            return False
        self.status.set("集中対象・区間メモ・解析依頼を録画フォルダへ保存しました。")
        return True

    def copy_prompt(self):
        if not self.report:
            return
        request = self._collect_request()
        prompt = build_focus_prompt(self.report, request)
        self.clipboard_clear()
        self.clipboard_append(prompt)
        self.status.set("Codex用解析プロンプトをクリップボードへコピーしました。")

    def export_bundle(self):
        if not self.report or not self.save_request():
            return
        selected = list(self.segment_tree.selection())
        selected_ids = selected if selected else []
        count = len(selected_ids) if selected_ids else len(
            self.report.get("segments", []))
        self.export_button.configure(state="disabled")
        self.status.set("解析資料と区間動画{}件を出力しています...".format(count))
        request = dict(self.request)
        request["annotations"] = dict(self.request.get("annotations", {}))

        def progress(done, total, segment):
            text = "解析資料を出力中: {}/{}".format(done, total)
            if segment:
                text += " / {}() #{}".format(
                    segment.get("function", ""), segment.get("occurrence", 0))
            try:
                self.after(0, lambda text=text: self.status.set(text))
            except tk.TclError:
                pass

        def worker():
            try:
                result = export_focus_bundle(
                    self.report, request, selected_ids=selected_ids,
                    progress=progress)
                error = ""
            except Exception as caught:
                result, error = None, str(caught)
            try:
                self.after(0, lambda: self._finish_export(result, error))
            except tk.TclError:
                pass

        threading.Thread(
            target=worker, name="CommandFocusRepairExport", daemon=True).start()

    def _finish_export(self, result, error):
        self.export_button.configure(state="normal")
        if error or not result:
            messagebox.showerror(
                "集中修正資料", error or "出力に失敗しました。", parent=self)
            self.status.set("集中修正資料の出力に失敗しました。")
            return
        self.last_export = result["destination"]
        failures = list(result.get("errors", []))
        self.status.set(
            "解析資料を出力しました: {}{}".format(
                result["destination"],
                " / 動画失敗{}件".format(len(failures)) if failures else ""))
        message = (
            "Codex用Markdown、構造化manifest、対象関数ソース、区間動画を出力しました。\n\n"
            + result["destination"])
        if failures:
            message += "\n\n動画出力の失敗:\n" + "\n".join(failures[:5])
        messagebox.showinfo("集中修正資料", message, parent=self)

    def _selected_segment(self):
        selected = self.segment_tree.selection()
        return self.segment_by_id.get(selected[0]) if selected else None

    def open_selected_in_recording(self):
        segment = self._selected_segment()
        if segment and callable(self.open_recording_callback):
            self.open_recording_callback(
                self.folder, float(segment.get("start_time", 0.0)))

    def open_event_in_recording(self):
        segment = self._selected_segment()
        selected = self.event_tree.selection()
        if not segment or not selected or not callable(self.open_recording_callback):
            return
        event = self.event_by_iid.get(selected[0])
        if event is None:
            return
        self.open_recording_callback(
            self.folder, float(event.get("video_time", 0.0)))

    def open_selected_source(self):
        segment = self._selected_segment()
        if not segment or not callable(self.open_source_callback):
            return
        source = self.report.get("sources", {}).get(
            segment.get("function", ""), {})
        path = str(source.get("original_path", "") or source.get("path", ""))
        if os.path.isfile(path):
            self.open_source_callback(path, int(source.get("start_line", 1) or 1))

    def open_folder(self):
        if self.folder and os.path.isdir(self.folder):
            try:
                os.startfile(self.folder)
            except (AttributeError, OSError):
                pass

    def open_last_export(self):
        if self.last_export and os.path.isdir(self.last_export):
            try:
                os.startfile(self.last_export)
            except (AttributeError, OSError):
                pass
        else:
            self.status.set("この画面で出力した解析資料はまだありません。")

    def destroy(self):
        self._load_generation += 1
        self._store_current_annotation()
        ttk.Frame.destroy(self)
