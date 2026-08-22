#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DevStudio workspace for Commands video/source comparison."""
from __future__ import print_function

import bisect
import json
import os
import threading
import time
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import cv2
except ImportError:
    cv2 = None
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

from CommandRecordingModel import (filtered_timeline, load_command_recording,
                                   load_command_timeline, resolve_event_source,
                                   observed_source_lines, source_function_block,
                                   timeline_page,
                                   video_candidates)
from OperationSessionStudio import FrameCaptureDialog


PAGE_SIZE = 500


def _atomic_json(path, value):
    temporary = path + ".tmp-" + uuid.uuid4().hex
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def _clock(value):
    value = max(0.0, float(value or 0.0))
    minutes = int(value // 60)
    return "{:02d}:{:06.3f}".format(minutes, value - minutes * 60)


class CommandRecordingWorkspace(ttk.Frame):
    """Timeline, recorded video, and the executed source in one tab."""

    def __init__(self, parent, initial_recording="", open_source_callback=None,
                 open_image_callback=None, template_root_provider=None):
        ttk.Frame.__init__(self, parent)
        self.open_source_callback = open_source_callback
        self.open_image_callback = open_image_callback
        self.template_root_provider = template_root_provider
        self.command_development_window = None
        self.folder = ""
        self.metadata = {}
        self.events = []
        self.event_times = []
        self.filtered_events = []
        self.event_by_iid = {}
        self.page = 0
        self.current_event = None
        self.current_source_path = ""
        self.video_capture = None
        self.video_sources = {}
        self.video_fps = 30.0
        self.video_duration = 0.0
        self.current_time = 0.0
        self.current_frame = None
        self.playing = False
        self._play_job = None
        self._play_wall = 0.0
        self._play_origin = 0.0
        self._video_photo = None
        self._selection_from_video = False
        self._programmatic_selection_iid = ""
        self._last_event_index = 0
        self._source_refresh_job = None
        self._source_cache = {}
        self._load_generation = 0
        self._loading = False
        self._build()
        if initial_recording:
            self.after_idle(lambda: self.load_folder(initial_recording))

    def _build(self):
        self.folder_value = tk.StringVar()
        self.summary = tk.StringVar(value="Commands録画フォルダを選択してください。")
        self.status = tk.StringVar(value="① 録画を読込 → ② Step/関数を選択 → ③ 動画とソースを比較")
        self.search = tk.StringVar()
        self.stops_only = tk.BooleanVar(value=False)
        self.page_text = tk.StringVar(value="0件")
        self.video_choice = tk.StringVar()
        self.video_time_text = tk.StringVar(value="00:00.000 / 00:00.000")
        self.video_sync = tk.DoubleVar(value=0.0)
        self.source_title = tk.StringVar(value="関数を選ぶと、録画時ソースを表示します。")
        self.current_execution_text = tk.StringVar(
            value="▶ 動画を移動すると、その時刻の実行行を表示します。")

        guide = ttk.Label(
            self,
            text=("Commands実行時の動画と、状態変数／Step／実行関数／ソース行を比較します。"
                  " Commandsが生成した入力はソースを根拠にし、PCコントローラーで割り込んだ入力だけを別イベントで表示します。"),
            foreground="#174a7e", justify="left", wraplength=1450)
        guide.pack(fill="x", padx=8, pady=(7, 3))

        opener = ttk.Frame(self)
        opener.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(opener, text="Commands録画:").pack(side="left")
        ttk.Entry(opener, textvariable=self.folder_value).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(opener, text="選択…", command=self.choose_folder).pack(side="left")
        self.load_button = ttk.Button(opener, text="読込", command=self.load_typed_folder)
        self.load_button.pack(side="left", padx=3)
        ttk.Button(opener, text="フォルダを開く", command=self.open_folder).pack(side="left")
        ttk.Button(
            opener, text="Commands開発解析…",
            command=self.open_command_development).pack(side="left", padx=(3, 0))
        ttk.Label(self, textvariable=self.summary, anchor="w").pack(
            fill="x", padx=10, pady=(0, 4))

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=7, pady=(0, 4))
        timeline_panel = ttk.Frame(panes)
        source_panel = ttk.Frame(panes)
        video_panel = ttk.Frame(panes)
        panes.add(timeline_panel, weight=4)
        panes.add(source_panel, weight=4)
        panes.add(video_panel, weight=4)
        self._build_timeline(timeline_panel)
        self._build_source(source_panel)
        self._build_video(video_panel)
        ttk.Label(self, textvariable=self.status, anchor="w").pack(
            fill="x", padx=9, pady=(0, 6))

    def _build_timeline(self, parent):
        ttk.Label(parent, text="① 動画タイムライン（Step／関数）",
                  foreground="#174a7e").pack(anchor="w", padx=3)
        filters = ttk.Frame(parent)
        filters.pack(fill="x", padx=3, pady=3)
        entry = ttk.Entry(filters, textvariable=self.search)
        entry.pack(side="left", fill="x", expand=True)
        ttk.Checkbutton(filters, text="停止Stepのみ", variable=self.stops_only,
                        command=self.on_filter_changed).pack(side="left", padx=4)
        self.search.trace_add("write", lambda *_args: self.on_filter_changed())

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=3)
        self.timeline_tree = ttk.Treeview(
            tree_frame, columns=("number", "time", "event", "step", "function", "line"),
            show="headings", selectmode="browse", height=18)
        for column, label, width in (
                ("number", "#", 45), ("time", "動画", 72), ("event", "種別", 105),
                ("step", "Step", 230), ("function", "関数", 155), ("line", "行", 55)):
            self.timeline_tree.heading(column, text=label)
            self.timeline_tree.column(
                column, width=width, stretch=column in ("step", "function"))
        sy = ttk.Scrollbar(tree_frame, orient="vertical", command=self.timeline_tree.yview)
        sx = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.timeline_tree.xview)
        self.timeline_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.timeline_tree.grid(column=0, row=0, sticky="nsew")
        sy.grid(column=1, row=0, sticky="ns")
        sx.grid(column=0, row=1, sticky="ew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.timeline_tree.bind("<<TreeviewSelect>>", self.on_event_selected)

        pages = ttk.Frame(parent)
        pages.pack(fill="x", padx=3, pady=3)
        ttk.Button(pages, text="◀ 前500件", command=lambda: self.change_page(-1)).pack(side="left")
        ttk.Button(pages, text="次500件 ▶", command=lambda: self.change_page(1)).pack(side="left", padx=3)
        ttk.Label(pages, textvariable=self.page_text).pack(side="left", padx=5)
        ttk.Button(pages, text="次の停止Step", command=lambda: self.select_stop(True)).pack(side="right")
        ttk.Button(pages, text="前の停止Step", command=lambda: self.select_stop(False)).pack(
            side="right", padx=3)

    def _build_source(self, parent):
        ttk.Label(parent, text="② 記録時ソース／関数",
                  foreground="#174a7e").pack(anchor="w", padx=3)
        ttk.Label(parent, textvariable=self.source_title, anchor="w", wraplength=480).pack(
            fill="x", padx=3, pady=3)
        tk.Label(
            parent, textvariable=self.current_execution_text,
            anchor="w", justify="left", wraplength=480,
            background="#fff176", foreground="#111111",
            font=("TkDefaultFont", 9, "bold"), padx=5, pady=3).pack(
                fill="x", padx=3, pady=(0, 3))
        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=3, pady=(0, 3))
        ttk.Button(actions, text="ソース編集タブで開く",
                   command=self.open_current_source).pack(side="left")
        ttk.Button(actions, text="◀ 前の通過行",
                   command=lambda: self.select_visited_line(False)).pack(
                       side="left", padx=(3, 0))
        ttk.Button(actions, text="次の通過行 ▶",
                   command=lambda: self.select_visited_line(True)).pack(
                       side="left", padx=3)
        ttk.Button(actions, text="停止地点を動画で再確認",
                   command=self.seek_current_event).pack(side="left", padx=3)
        path_actions = ttk.Frame(parent)
        path_actions.pack(fill="x", padx=3, pady=(0, 3))
        ttk.Button(
            path_actions, text="◀ 前の実行行",
            command=lambda: self.select_path_event(False)).pack(side="left")
        ttk.Button(
            path_actions, text="次の実行行 ▶",
            command=lambda: self.select_path_event(True)).pack(side="left", padx=3)
        ttk.Button(
            path_actions, text="◀ 前の関数",
            command=lambda: self.select_visited_function(False)).pack(
                side="left", padx=(10, 0))
        ttk.Button(
            path_actions, text="次の関数 ▶",
            command=lambda: self.select_visited_function(True)).pack(
                side="left", padx=3)
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=3)
        self.source_text = tk.Text(
            frame, wrap="none", font=("Consolas", 9), background="#171717",
            foreground="#e5e5e5", insertbackground="white")
        sy = ttk.Scrollbar(frame, orient="vertical", command=self.source_text.yview)
        sx = ttk.Scrollbar(frame, orient="horizontal", command=self.source_text.xview)
        self.source_text.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.source_text.grid(column=0, row=0, sticky="nsew")
        sy.grid(column=1, row=0, sticky="ns")
        sx.grid(column=0, row=1, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.source_text.tag_configure(
            "visited", background="#173f5f", foreground="white")
        self.source_text.tag_configure(
            "current", background="#fff176", foreground="#111111",
            relief="raised", borderwidth=1,
            font=("Consolas", 9, "bold"))
        self.source_text.configure(state="disabled")

    def _build_video(self, parent):
        header = ttk.Frame(parent)
        header.pack(fill="x", padx=3)
        ttk.Label(header, text="③ 録画映像", foreground="#174a7e").pack(side="left")
        self.video_combo = ttk.Combobox(
            header, textvariable=self.video_choice, state="readonly", width=20)
        self.video_combo.pack(side="right")
        self.video_combo.bind("<<ComboboxSelected>>", lambda _event: self.open_video())
        self.video_label = tk.Label(
            parent, text="録画を読み込むと表示します。", background="black", foreground="white")
        self.video_label.pack(fill="both", expand=True, padx=3, pady=4)
        self.video_slider = ttk.Scale(parent, from_=0.0, to=1.0, command=self.on_slider)
        self.video_slider.pack(fill="x", padx=5)
        ttk.Label(parent, textvariable=self.video_time_text, anchor="center").pack(fill="x")
        controls = ttk.Frame(parent)
        controls.pack(fill="x", padx=3, pady=3)
        for label, amount in (("-1秒", -1.0), ("-0.1", -0.1)):
            ttk.Button(controls, text=label,
                       command=lambda value=amount: self.seek_video(self.current_time + value)).pack(
                           side="left", padx=1)
        self.play_button = ttk.Button(controls, text="▶ 再生", command=self.toggle_play)
        self.play_button.pack(side="left", padx=4)
        for label, amount in (("+0.1", 0.1), ("+1秒", 1.0)):
            ttk.Button(controls, text=label,
                       command=lambda value=amount: self.seek_video(self.current_time + value)).pack(
                           side="left", padx=1)
        sync = ttk.Frame(parent)
        sync.pack(fill="x", padx=3, pady=3)
        ttk.Label(sync, text="リンク補正秒:").pack(side="left")
        ttk.Spinbox(sync, from_=-30.0, to=30.0, increment=0.01,
                    textvariable=self.video_sync, width=8).pack(side="left", padx=3)
        ttk.Button(sync, text="保存", command=self.save_sync).pack(side="left")
        ttk.Button(sync, text="現在フレームから画像検知",
                   command=self.capture_frame).pack(side="right")

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
        self.stop_video()
        self.close_video()
        self._load_generation += 1
        generation = self._load_generation
        self._loading = True
        self.load_button.configure(state="disabled")
        self.folder_value.set(folder)
        self.status.set("録画情報とタイムラインをバックグラウンドで読み込んでいます...")

        def worker():
            try:
                result = (load_command_recording(folder), load_command_timeline(folder))
                error = ""
            except Exception as caught:  # File/JSON failures are reported on Tk's thread.
                result = None
                error = str(caught)
            try:
                self.after(0, lambda: self._finish_load_folder(
                    folder, generation, result, error))
            except tk.TclError:
                pass

        threading.Thread(
            target=worker, name="CommandRecordingLoad", daemon=True).start()
        return True

    def _finish_load_folder(self, folder, generation, result, error):
        if generation != self._load_generation:
            return False
        self._loading = False
        self.load_button.configure(state="normal")
        if error or result is None:
            messagebox.showerror("Commands録画", error or "録画を読み込めません。", parent=self)
            self.status.set("読込失敗: " + (error or folder))
            return False
        metadata, events = result
        self.folder = folder
        self.folder_value.set(folder)
        self.metadata = metadata
        self.events = events
        self.event_times = [float(event["video_time"]) for event in events]
        self._source_cache = {}
        self.video_sync.set(float(metadata.get("video_sync_offset", 0.0) or 0.0))
        self.page = 0
        self.summary.set(
            "Command: {} / {:.1f}秒 / リンク{}件 / Step: {}".format(
                metadata.get("command", "-"), float(metadata.get("duration", 0.0) or 0.0),
                len(events), " / ".join(metadata.get("states", [])[-4:]) or "-"))
        self.refresh_timeline()
        self.refresh_videos()
        if events:
            self.select_event(events[0], seek=True)
        self.status.set("読込完了。Stepまたは関数を選ぶと同時刻の動画と記録時ソースを表示します。")
        return True

    def open_folder(self):
        if self.folder and os.path.isdir(self.folder):
            try:
                os.startfile(self.folder)
            except (AttributeError, OSError):
                pass

    def on_filter_changed(self):
        self.page = 0
        self.refresh_timeline()

    def refresh_timeline(self):
        selected_index = int(self.current_event.get("index", 0)) if self.current_event else 0
        self.filtered_events = filtered_timeline(
            self.events, self.search.get(), self.stops_only.get())
        visible, self.page, page_count = timeline_page(
            self.filtered_events, self.page, PAGE_SIZE)
        self.timeline_tree.delete(*self.timeline_tree.get_children())
        self.event_by_iid = {}
        for event in visible:
            location = event.get("location", {})
            iid = "event-{}".format(event["index"])
            self.event_by_iid[iid] = event
            self.timeline_tree.insert("", "end", iid=iid, values=(
                event["index"], _clock(event["video_time"]), event.get("event", ""),
                event.get("step_text", "") or "-", location.get("function", "") or "-",
                location.get("line", "") or "-"))
            if int(event["index"]) == selected_index:
                self.timeline_tree.selection_set(iid)
        start = self.page * PAGE_SIZE + 1 if visible else 0
        finish = self.page * PAGE_SIZE + len(visible)
        self.page_text.set("{}～{} / {}件（{}/{}ページ）".format(
            start, finish, len(self.filtered_events), self.page + 1, page_count))

    def change_page(self, amount):
        _visible, _page, page_count = timeline_page(
            self.filtered_events, self.page, PAGE_SIZE)
        self.page = min(max(0, self.page + int(amount)), page_count - 1)
        self.refresh_timeline()

    def on_event_selected(self, _event=None):
        if self._selection_from_video:
            return
        selected = self.timeline_tree.selection()
        if selected and selected[0] == self._programmatic_selection_iid:
            self._programmatic_selection_iid = ""
            return
        if selected:
            self.select_event(self.event_by_iid[selected[0]], seek=True)

    def select_event(self, event, seek=False, defer_source=False):
        if not event:
            return
        self.current_event = event
        try:
            position = self.filtered_events.index(event)
        except ValueError:
            position = -1
        wanted_page = position // PAGE_SIZE if position >= 0 else self.page
        if wanted_page != self.page:
            self.page = wanted_page
            self.refresh_timeline()
        iid = "event-{}".format(event["index"])
        if self.timeline_tree.exists(iid):
            self._selection_from_video = not seek
            if not seek:
                self._programmatic_selection_iid = iid
            try:
                self.timeline_tree.selection_set(iid)
                self.timeline_tree.see(iid)
            finally:
                self._selection_from_video = False
        if defer_source:
            self._queue_event_source(event)
        else:
            self._cancel_source_refresh()
            self.show_event_source(event)
        if seek:
            self.seek_current_event()

    def _cancel_source_refresh(self):
        if self._source_refresh_job is not None:
            try:
                self.after_cancel(self._source_refresh_job)
            except tk.TclError:
                pass
            self._source_refresh_job = None

    def _queue_event_source(self, event):
        """Coalesce dense playback events so Tk can keep handling tabs and sashes."""
        self._cancel_source_refresh()
        event_index = int(event.get("index", 0))

        def refresh():
            self._source_refresh_job = None
            if self.current_event and int(self.current_event.get("index", 0)) == event_index:
                self.show_event_source(self.current_event)

        self._source_refresh_job = self.after(150, refresh)

    def select_stop(self, forward):
        stops = [event for event in self.events if event.get("event") == "step_debug_stop"]
        if not stops:
            self.status.set("この録画にはStepデバッグ停止イベントがありません。")
            return
        current = int(self.current_event.get("index", 0)) if self.current_event else 0
        if forward:
            event = next((item for item in stops if int(item["index"]) > current), stops[0])
        else:
            event = next((item for item in reversed(stops)
                          if int(item["index"]) < current), stops[-1])
        if self.stops_only.get() or not self.search.get().strip():
            self.filtered_events = filtered_timeline(
                self.events, self.search.get(), self.stops_only.get())
        self.select_event(event, seek=True)

    def show_event_source(self, event):
        path, location = resolve_event_source(self.folder, self.metadata, event)
        self.current_source_path = str(location.get("file", "") or path)
        try:
            linked_video_time = max(
                0.0, float(event.get("video_time", 0.0) or 0.0)
                + float(self.video_sync.get()))
        except (TypeError, ValueError, tk.TclError):
            linked_video_time = 0.0
        self.current_execution_text.set(
            "▶ 動画 {} に対応する実行行: {}() / {}行".format(
                _clock(linked_video_time),
                location.get("function", "-") or "-",
                location.get("line", "-") or "-"))
        self.source_text.configure(state="normal")
        self.source_text.delete("1.0", "end")
        if not path:
            self.source_text.insert("1.0", "ソースまたは録画時スナップショットが見つかりません。")
            self.source_text.configure(state="disabled")
            return
        try:
            stat = os.stat(path)
            cache_key = (
                os.path.abspath(path), str(location.get("function", "")),
                int(location.get("line", 0) or 0), int(stat.st_mtime), int(stat.st_size))
            block = self._source_cache.get(cache_key)
            if block is None:
                block = source_function_block(
                    path, location.get("function", ""), location.get("line", 0))
                if len(self._source_cache) >= 128:
                    self._source_cache.clear()
                self._source_cache[cache_key] = block
        except (OSError, UnicodeError) as error:
            self.source_text.insert("1.0", str(error))
            self.source_text.configure(state="disabled")
            return
        rendered = []
        for number, text in enumerate(
                block["text"].splitlines(True), start=block["start_line"]):
            rendered.append("{:6d} | {}".format(number, text))
        self.source_text.insert("1.0", "".join(rendered))
        original = str(location.get("file", "") or self.current_source_path or path)
        visited = observed_source_lines(self.events, original)
        visible_visited = 0
        for line in sorted(visited):
            if block["start_line"] <= line <= block["end_line"]:
                row = line - block["start_line"] + 1
                self.source_text.tag_add(
                    "visited", "{}.0".format(row), "{}.end".format(row))
                visible_visited += 1
        highlight = int(block.get("highlight_line", 0) or 0)
        if block["start_line"] <= highlight <= block["end_line"]:
            row = highlight - block["start_line"] + 1
            self.source_text.tag_add("current", "{}.0".format(row), "{}.end".format(row))
            self.source_text.tag_raise("current")
            self.source_text.see("{}.0".format(row))
            self.status.set(
                "動画 {} → {}() {}行を表示中".format(
                    _clock(linked_video_time),
                    location.get("function", "-") or "-", highlight))
        original = str(location.get("file", "") or "")
        source_kind = "録画時スナップショット" if os.path.abspath(path) != os.path.abspath(original or path) \
            else "現在のソース"
        self.source_title.set("{} / {}() / {}行 / 通過行{}件 / {}".format(
            source_kind, location.get("function", "-"), location.get("line", "-"),
            visible_visited, path))
        self.source_text.configure(state="disabled")

    def select_visited_line(self, forward):
        """Jump between distinct source lines that were observed in the trace."""
        distinct = []
        seen = set()
        for event in self.events:
            location = event.get("location", {}) if isinstance(event, dict) else {}
            if not isinstance(location, dict):
                continue
            path = str(location.get("file", "") or "")
            try:
                line = int(location.get("line", 0) or 0)
            except (TypeError, ValueError):
                line = 0
            if not path or line <= 0:
                continue
            key = (os.path.normcase(os.path.abspath(path)), line)
            if key not in seen:
                seen.add(key)
                distinct.append(event)
        if not distinct:
            self.status.set("この記録には通過したソース行がありません。")
            return
        current = int(self.current_event.get("index", 0)) if self.current_event else 0
        if forward:
            target = next(
                (event for event in distinct if int(event.get("index", 0)) > current),
                distinct[0])
        else:
            target = next(
                (event for event in reversed(distinct)
                 if int(event.get("index", 0)) < current), distinct[-1])
        self.select_event(target, seek=True)

    def select_path_event(self, forward):
        """Move one recorded execution event and seek the linked video."""
        candidates = []
        for event in self.events:
            location = event.get("location", {}) if isinstance(event, dict) else {}
            if not isinstance(location, dict):
                continue
            try:
                line = int(location.get("line", 0) or 0)
            except (TypeError, ValueError):
                line = 0
            if location.get("file") and line > 0:
                candidates.append(event)
        if not candidates:
            self.status.set("この動画範囲には実行行が記録されていません。")
            return
        current = int(self.current_event.get("index", 0)) if self.current_event else 0
        if forward:
            target = next(
                (event for event in candidates
                 if int(event.get("index", 0)) > current), candidates[0])
        else:
            target = next(
                (event for event in reversed(candidates)
                 if int(event.get("index", 0)) < current), candidates[-1])
        self.select_event(target, seek=True)

    def select_visited_function(self, forward):
        """Move to the previous/next function transition and seek the video."""
        transitions = []
        previous_key = None
        for event in self.events:
            location = event.get("location", {}) if isinstance(event, dict) else {}
            if not isinstance(location, dict):
                continue
            path = str(location.get("file", "") or "")
            function = str(location.get("function", "") or "")
            if not path or not function:
                continue
            key = (os.path.normcase(os.path.abspath(path)), function)
            if key != previous_key:
                transitions.append(event)
                previous_key = key
        if not transitions:
            self.status.set("この動画範囲には関数の実行経路が記録されていません。")
            return
        current = int(self.current_event.get("index", 0)) if self.current_event else 0
        if forward:
            target = next(
                (event for event in transitions
                 if int(event.get("index", 0)) > current), transitions[0])
        else:
            target = next(
                (event for event in reversed(transitions)
                 if int(event.get("index", 0)) < current), transitions[-1])
        self.select_event(target, seek=True)

    def open_current_source(self):
        event = self.current_event or {}
        location = event.get("location", {})
        original = str(location.get("file", "") or self.current_source_path)
        path = original if os.path.isfile(original) else self.current_source_path
        if path and self.open_source_callback:
            self.open_source_callback(path, int(location.get("line", 1) or 1))

    def _development_source_path(self):
        """Prefer the selected event's real source, then recording metadata."""
        event = self.current_event or {}
        location = event.get("location", {}) if isinstance(event, dict) else {}
        candidates = []
        if isinstance(location, dict):
            candidates.append(str(location.get("file", "") or ""))
        candidates.append(str(self.current_source_path or ""))
        source = self.metadata.get("source", {}) if isinstance(self.metadata, dict) else {}
        if isinstance(source, dict):
            candidates.append(str(source.get("file", "") or ""))
        for item in candidates:
            if item and os.path.isfile(item):
                return os.path.abspath(item)
        return ""

    def open_command_development(self):
        """Open bounded post-recording analysis without touching live Commands."""
        window = self.command_development_window
        try:
            if window is not None and window.winfo_exists():
                window.update_context(
                    folder=self.folder, metadata=self.metadata,
                    events=self.events, source_path=self._development_source_path())
                window.deiconify()
                return
        except tk.TclError:
            pass
        try:
            from CommandDevelopmentStudio import CommandDevelopmentWindow
            template_root = self.template_root_provider() \
                if callable(self.template_root_provider) else ""
            self.command_development_window = CommandDevelopmentWindow(
                self, folder=self.folder, metadata=self.metadata,
                events=self.events, source_path=self._development_source_path(),
                template_root=template_root,
                open_source_callback=self.open_source_callback)
        except Exception as error:
            self.command_development_window = None
            messagebox.showerror("Commands開発解析", str(error), parent=self)

    def seek_current_event(self):
        if self.current_event:
            self.seek_video(float(self.current_event["video_time"]) + float(self.video_sync.get()))

    def refresh_videos(self):
        candidates = video_candidates(self.folder)
        self.video_sources = dict(candidates)
        labels = [item[0] for item in candidates]
        self.video_combo.configure(values=labels)
        self.video_choice.set(labels[0] if labels else "")
        if labels:
            self.open_video()
        else:
            self.video_label.configure(image="", text="recording.mp4 / recording.aviが見つかりません。")

    def open_video(self):
        if cv2 is None or Image is None:
            self.status.set("OpenCVまたはPillowがないため動画を表示できません。")
            return
        path = self.video_sources.get(self.video_choice.get(), "")
        self.stop_video()
        self.close_video()
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            self.status.set("動画を開けません: " + path)
            return
        self.video_capture = capture
        self.video_fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        self.video_duration = frames / max(1.0, self.video_fps)
        self.video_slider.configure(to=max(0.001, self.video_duration))
        self.seek_video(min(self.current_time, self.video_duration))

    def close_video(self):
        capture, self.video_capture = self.video_capture, None
        if capture is not None:
            capture.release()

    def on_slider(self, value):
        if self.playing:
            return
        try:
            target = float(value)
        except (TypeError, ValueError):
            return
        if hasattr(self, "_slider_job"):
            try:
                self.after_cancel(self._slider_job)
            except tk.TclError:
                pass
        self._slider_job = self.after(100, lambda: self.seek_video(target))

    def seek_video(self, target):
        if self.video_capture is None:
            return
        self.stop_video()
        target = min(max(0.0, float(target)), max(0.0, self.video_duration))
        self.video_capture.set(cv2.CAP_PROP_POS_MSEC, target * 1000.0)
        ok, frame = self.video_capture.read()
        if not ok:
            return
        self.current_time = target
        self.current_frame = frame
        self.video_slider.set(target)
        self._show_frame(frame)
        self._update_video_text()
        self.highlight_event_at_time(target)

    def _show_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        width = max(320, self.video_label.winfo_width() - 8)
        height = max(180, self.video_label.winfo_height() - 8)
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        image.thumbnail((width, height), resampling)
        self._video_photo = ImageTk.PhotoImage(image)
        self.video_label.configure(image=self._video_photo, text="")

    def _update_video_text(self):
        self.video_time_text.set("{} / {}".format(
            _clock(self.current_time), _clock(self.video_duration)))

    def toggle_play(self):
        if self.playing:
            self.stop_video()
            return
        if self.video_capture is None:
            return
        self.playing = True
        self.play_button.configure(text="■ 一時停止")
        self._play_wall = time.monotonic()
        self._play_origin = self.current_time
        self.video_capture.set(cv2.CAP_PROP_POS_MSEC, self.current_time * 1000.0)
        self._play_tick()

    def _play_tick(self):
        if not self.playing or self.video_capture is None:
            return
        target = self._play_origin + time.monotonic() - self._play_wall
        if target >= self.video_duration:
            self.seek_video(self.video_duration)
            return
        decoded = float(self.video_capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
        if abs(decoded - target) > 0.15:
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
        self.video_slider.set(target)
        self._show_frame(frame)
        self._update_video_text()
        self.highlight_event_at_time(target)
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

    def highlight_event_at_time(self, video_time):
        if not self.events:
            return
        event_time = float(video_time) - float(self.video_sync.get())
        position = bisect.bisect_right(self.event_times, event_time) - 1
        if position < 0:
            return
        event = self.events[position]
        if int(event["index"]) != self._last_event_index:
            self._last_event_index = int(event["index"])
            # Playback must remain useful even when a search hides the event.
            if event in self.filtered_events:
                self.select_event(event, seek=False, defer_source=True)
            else:
                self.current_event = event
                self._queue_event_source(event)

    def save_sync(self):
        if not self.folder:
            return
        self.metadata["video_sync_offset"] = float(self.video_sync.get())
        try:
            _atomic_json(os.path.join(self.folder, "command_monitor.json"), self.metadata)
        except OSError as error:
            messagebox.showerror("リンク補正", str(error), parent=self)
            return
        self.status.set("動画とソースタイムラインの補正値を録画フォルダへ保存しました。")

    def capture_frame(self):
        if self.current_frame is None or Image is None:
            messagebox.showinfo("画像検知", "先に動画フレームを表示してください。", parent=self)
            return
        session = dict(self.metadata)
        session["session_id"] = str(
            self.metadata.get("command_session_id", "command-recording"))
        FrameCaptureDialog(
            self, self.current_frame.copy(), self.folder, session,
            self.current_time, self._captured_image)

    def _captured_image(self, path, crop, name, open_library):
        self.status.set("動画フレームから画像を保存しました: " + path)
        if open_library and self.open_image_callback:
            self.open_image_callback(path, crop, name)

    def destroy(self):
        self._load_generation += 1
        window, self.command_development_window = self.command_development_window, None
        try:
            if window is not None and window.winfo_exists():
                window.close()
        except tk.TclError:
            pass
        self._cancel_source_refresh()
        self.stop_video()
        self.close_video()
        ttk.Frame.destroy(self)
