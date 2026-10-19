#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PokeConStudio: edit, inspect image matching, and run source iteratively."""
from __future__ import print_function

import argparse
import ast
import datetime
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from StudioCore import (DEFAULT_OPERATION_PATTERNS,
                            DEFAULT_PANEL_VISIBILITY, ProfileStore,
                            add_detection_to_source,
                            build_detection_catalog,
                            default_profile_store_path, detection_sort_key,
                            discover_source_files, match_detection_row,
                            normalize_profile,
                            read_source)
except ImportError:  # pragma: no cover - module execution fallback
    from .StudioCore import (DEFAULT_OPERATION_PATTERNS,
                             DEFAULT_PANEL_VISIBILITY, ProfileStore,
                             add_detection_to_source,
                             build_detection_catalog,
                             default_profile_store_path, detection_sort_key,
                             discover_source_files, match_detection_row,
                             normalize_profile,
                             read_source)


EVENT_PREFIX = "[POKECON_STUDIO_EVENT]"
PANEL_LABELS = (
    ("source_list", "ソース一覧"),
    ("source_editor", "ソース編集"),
    ("image_detection", "画像検知"),
    ("run_support", "実行支援"),
)


def _display_basename(path):
    """Return a compact label while callers continue holding the full path."""
    value = str(path or "")
    if not value:
        return ""
    return os.path.basename(os.path.normpath(value)) or value


def _append_unique(listbox, values):
    current = [listbox.get(index) for index in range(listbox.size())]
    known = set(os.path.normcase(os.path.abspath(path)) for path in current)
    for value in values:
        path = os.path.abspath(value)
        key = os.path.normcase(path)
        if key not in known:
            listbox.insert("end", path)
            known.add(key)


class ProfileDialog(tk.Toplevel):
    """Edit the four multi-value path groups in one reviewable dialog."""

    def __init__(self, parent, name, profile, project_root):
        tk.Toplevel.__init__(self, parent)
        self.title("PokeConStudio 設定")
        self.transient(parent)
        self.result = None
        self.project_root = project_root
        self.name_var = tk.StringVar(value=name)
        self.capture_var = tk.StringVar(
            value=str(profile.get("capture_source", "0")))
        self.path_lists = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        name_row = ttk.Frame(self)
        name_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        ttk.Label(name_row, text="設定名:").pack(side="left")
        ttk.Entry(name_row, textvariable=self.name_var, width=32).pack(
            side="left", fill="x", expand=True, padx=5)

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        definitions = (
            ("source_files", "ソースファイル", True),
            ("source_folders", "ソースフォルダ", False),
            ("image_folders", "画像フォルダ", False),
            ("include_folders", "その他Includeフォルダ", False),
        )
        for key, title, is_file in definitions:
            page = ttk.Frame(notebook)
            page.columnconfigure(0, weight=1)
            page.rowconfigure(0, weight=1)
            listbox = tk.Listbox(page, selectmode="extended", height=10)
            listbox.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=5)
            scroll = ttk.Scrollbar(page, orient="vertical", command=listbox.yview)
            scroll.grid(row=0, column=1, sticky="ns", pady=5)
            listbox.configure(yscrollcommand=scroll.set)
            actions = ttk.Frame(page)
            actions.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5,
                         pady=(0, 5))
            ttk.Button(
                actions, text="追加…",
                command=lambda box=listbox, file_mode=is_file:
                    self._add_path(box, file_mode)).pack(side="left")
            ttk.Button(
                actions, text="選択を削除",
                command=lambda box=listbox: self._remove_paths(box)).pack(
                    side="left", padx=5)
            notebook.add(page, text=title)
            self.path_lists[key] = listbox
            _append_unique(listbox, profile.get(key, []))

        options = ttk.Labelframe(self, text="画像検知・実行設定")
        options.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        ttk.Label(options, text="入力 (0 / 動画 / 画像):").grid(
            row=0, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(options, textvariable=self.capture_var, width=55).grid(
            row=0, column=1, sticky="ew", padx=5, pady=4)
        ttk.Button(options, text="ファイル…", command=self._choose_capture).grid(
            row=0, column=2, padx=5, pady=4)
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="操作コード判定 (正規表現、1行1件):").grid(
            row=1, column=0, columnspan=3, sticky="w", padx=5)
        self.patterns = tk.Text(options, height=5, wrap="none")
        self.patterns.grid(row=2, column=0, columnspan=3, sticky="ew",
                           padx=5, pady=(2, 5))
        self.patterns.insert("1.0", "\n".join(
            profile.get("operation_patterns", DEFAULT_OPERATION_PATTERNS)))

        buttons = ttk.Frame(self)
        buttons.grid(row=3, column=0, sticky="e", padx=8, pady=(4, 8))
        ttk.Button(buttons, text="保存", command=self._accept).pack(
            side="left", padx=3)
        ttk.Button(buttons, text="キャンセル", command=self.destroy).pack(
            side="left", padx=3)
        self.geometry("840x610")
        self.minsize(650, 480)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()

    def _add_path(self, listbox, is_file):
        if is_file:
            values = filedialog.askopenfilenames(
                parent=self, title="ソースファイルを追加",
                initialdir=self.project_root,
                filetypes=(("Python", "*.py *.pyw *.pyfrag"),
                           ("All files", "*.*")))
        else:
            selected = filedialog.askdirectory(
                parent=self, title="フォルダを追加",
                initialdir=self.project_root)
            values = (selected,) if selected else ()
        _append_unique(listbox, values)

    @staticmethod
    def _remove_paths(listbox):
        for index in reversed(listbox.curselection()):
            listbox.delete(index)

    def _choose_capture(self):
        path = filedialog.askopenfilename(
            parent=self, title="画像検知入力を選択",
            filetypes=(("Video / image", "*.mp4 *.avi *.mkv *.mov *.png *.jpg *.jpeg *.bmp *.webp"),
                       ("All files", "*.*")))
        if path:
            self.capture_var.set(path)

    def _accept(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("PokeConStudio", "設定名を入力してください。",
                                   parent=self)
            return
        profile = {}
        for key, listbox in self.path_lists.items():
            profile[key] = [listbox.get(index)
                            for index in range(listbox.size())]
        profile["capture_source"] = self.capture_var.get().strip() or "0"
        profile["operation_patterns"] = [
            line.strip() for line in self.patterns.get("1.0", "end").splitlines()
            if line.strip()
        ]
        self.result = (name, profile)
        self.destroy()


class PokeConStudioWindow(tk.Toplevel):
    def __init__(self, master, project_root, profile_store_path=None,
                 initial_source="", frame_provider=None,
                 frame_sequence_provider=None, runtime_actions=None,
                 close_root=False):
        tk.Toplevel.__init__(self, master)
        self.project_root = os.path.abspath(project_root)
        self.serial_root = os.path.join(self.project_root, "SerialController")
        self.studio_root = os.path.dirname(os.path.abspath(__file__))
        self.store = ProfileStore(
            profile_store_path or default_profile_store_path(),
            self.project_root)
        self.profile_name = tk.StringVar()
        self.source_filter = tk.StringVar()
        self.source_only = tk.BooleanVar(value=True)
        self.capture_source = tk.StringVar(value="0")
        self.pause_before_operations = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="起動中…")
        self.detection_status = tk.StringVar(value="未初期化")
        self.run_status = tk.StringVar(value="実行待ち")
        self.panel_visibility_vars = {
            key: tk.BooleanVar(value=default)
            for key, default in DEFAULT_PANEL_VISIBILITY.items()
        }
        self.panel_toggle_buttons = {}
        self._layout_groups = []
        self._comparison_opener = None
        self.recording_comparison_window = None
        self._comparison_profile_name = ""
        self.current_profile = {}
        self.source_paths = []
        self.current_path = ""
        self.current_encoding = "utf-8"
        self.editor_dirty = False
        self._ignore_editor_modified = False
        self.catalog = []
        self.catalog_by_id = {}
        self._scan_generation = 0
        self._scan_thread = None
        self._scan_request = None
        self._scan_cancel = None
        self._scan_lock = threading.Lock()
        self._detection_generation = 0
        self._event_queue = queue.Queue()
        self._detection_stop = None
        self._detection_pause = None
        self._detection_thread = None
        self._detection_tree_dirty = False
        self._detection_tree_last_refresh = 0.0
        self._detection_tree_refresh_after = None
        self.run_process = None
        self.run_snapshot = ""
        self.run_selection_mode = False
        self._run_generation = 0
        self._run_pending_lock = threading.Lock()
        self._run_pending_lines = 0
        self._run_pending_chars = 0
        self._run_dropped_lines = 0
        self._run_drop_notice_queued = False
        self._run_display_chars = 0
        self._closing = False
        self._event_drain_after = None
        self.frame_provider = frame_provider
        self.frame_sequence_provider = frame_sequence_provider
        self.runtime_actions = dict(runtime_actions or {})
        self.close_root = bool(close_root)

        self.title("PokeConStudio - PokeCon操作アシスト")
        self.geometry("1500x900")
        self.minsize(1050, 650)
        self._build_ui()
        self.set_comparison_opener(self.open_recording_comparison)
        self.protocol("WM_DELETE_WINDOW", self.close)
        # A Toplevel binding is inherited by its child widgets through their
        # bindtags, but disappears with this window.  bind_all would overwrite
        # PokeCon-wide shortcuts and leave a dead Tcl callback after closing.
        self.bind("<Control-s>", lambda _event: self.save_source())
        self.bind("<F5>", lambda _event: self.run_source("normal"))
        initial_profile = self.store.data.get("last_profile") or self.store.names()[0]
        self.load_profile(initial_profile, initial_source=initial_source)
        self._event_drain_after = self.after(75, self._drain_events)

    def _build_ui(self):
        profile_bar = ttk.Frame(self)
        profile_bar.pack(fill="x", padx=6, pady=(6, 3))
        ttk.Label(profile_bar, text="設定:").pack(side="left")
        self.profile_combo = ttk.Combobox(
            profile_bar, textvariable=self.profile_name, state="readonly",
            width=28)
        self.profile_combo.pack(side="left", padx=4)
        self.profile_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.load_profile(self.profile_name.get()))
        ttk.Button(profile_bar, text="新規 / 複製…",
                   command=lambda: self.edit_profile(copy_profile=True)).pack(
                       side="left", padx=2)
        ttk.Button(profile_bar, text="設定を変更…",
                   command=self.edit_profile).pack(side="left", padx=2)
        ttk.Button(profile_bar, text="現在状態を保存",
                   command=self.save_profile_state).pack(side="left", padx=2)
        ttk.Button(profile_bar, text="削除", command=self.delete_profile).pack(
            side="left", padx=2)
        ttk.Label(profile_bar, textvariable=self.status).pack(
            side="left", fill="x", expand=True, padx=10)

        visibility_bar = ttk.Frame(self)
        visibility_bar.pack(fill="x", padx=6, pady=(0, 2))
        ttk.Label(visibility_bar, text="表示:").pack(side="left")
        for key, label in PANEL_LABELS:
            button = ttk.Checkbutton(
                visibility_bar, text=label,
                variable=self.panel_visibility_vars[key],
                command=lambda panel_key=key:
                    self._panel_visibility_changed(panel_key))
            button.pack(side="left", padx=(4, 0))
            self.panel_toggle_buttons[key] = button
        self.comparison_button = ttk.Button(
            visibility_bar, text="記録比較・Step編集…",
            command=self.open_step_comparison, state="disabled")
        self.comparison_button.pack(side="left", padx=(12, 0))
        ttk.Label(
            visibility_bar,
            text="（非表示にしても画像検知・実行処理は継続します）",
            foreground="#666666").pack(side="left", padx=10)

        self.workspace_pane = ttk.Panedwindow(self, orient="horizontal")
        self.workspace_pane.pack(fill="both", expand=True, padx=6, pady=3)
        self.source_side = ttk.Panedwindow(
            self.workspace_pane, orient="horizontal")
        self.right_side = ttk.Panedwindow(
            self.workspace_pane, orient="vertical")

        browser = ttk.Labelframe(self.source_side, text="ソース")
        editor_frame = ttk.Labelframe(self.source_side, text="編集")
        self.source_browser_frame = browser
        self.source_editor_frame = editor_frame
        self.source_side.add(browser, weight=2)
        self.source_side.add(editor_frame, weight=7)
        browser.columnconfigure(0, weight=1)
        browser.rowconfigure(2, weight=1)
        ttk.Label(browser, text="検索:").grid(row=0, column=0, sticky="w",
                                                   padx=5, pady=(5, 0))
        search = ttk.Entry(browser, textvariable=self.source_filter)
        search.grid(row=1, column=0, sticky="ew", padx=5, pady=3)
        self.source_filter.trace_add("write", lambda *_: self.refresh_source_tree())
        tree_holder = ttk.Frame(browser)
        tree_holder.grid(row=2, column=0, sticky="nsew", padx=5, pady=3)
        tree_holder.columnconfigure(0, weight=1)
        tree_holder.rowconfigure(0, weight=1)
        self.source_tree = ttk.Treeview(
            tree_holder, columns=("path",), show="tree", selectmode="browse")
        self.source_tree.grid(row=0, column=0, sticky="nsew")
        source_scroll = ttk.Scrollbar(
            tree_holder, orient="vertical", command=self.source_tree.yview)
        source_scroll.grid(row=0, column=1, sticky="ns")
        self.source_tree.configure(yscrollcommand=source_scroll.set)
        self.source_tree.bind("<<TreeviewSelect>>", self._source_selected)
        ttk.Button(browser, text="ソース一覧を再読込",
                   command=self.refresh_sources).grid(
                       row=3, column=0, sticky="ew", padx=5, pady=(3, 5))

        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(1, weight=1)
        editor_actions = ttk.Frame(editor_frame)
        editor_actions.grid(row=0, column=0, sticky="ew", padx=5, pady=4)
        self.source_label = ttk.Label(editor_actions, text="未選択")
        self.source_label.pack(side="left", fill="x", expand=True)
        ttk.Button(editor_actions, text="保存 (Ctrl+S)",
                   command=self.save_source).pack(side="left", padx=2)
        ttk.Button(editor_actions, text="ディスクから再読込",
                   command=self.reload_source).pack(side="left", padx=2)
        editor_holder = ttk.Frame(editor_frame)
        editor_holder.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 3))
        editor_holder.columnconfigure(0, weight=1)
        editor_holder.rowconfigure(0, weight=1)
        self.editor = tk.Text(
            editor_holder, wrap="none", undo=True,
            background="#1e1e1e", foreground="#d4d4d4",
            insertbackground="#ffffff", selectbackground="#264f78",
            font=("Consolas", 11), tabs=("4c",))
        self.editor.grid(row=0, column=0, sticky="nsew")
        editor_y = ttk.Scrollbar(editor_holder, orient="vertical",
                                 command=self.editor.yview)
        editor_y.grid(row=0, column=1, sticky="ns")
        editor_x = ttk.Scrollbar(editor_holder, orient="horizontal",
                                 command=self.editor.xview)
        editor_x.grid(row=1, column=0, sticky="ew")
        self.editor.configure(yscrollcommand=editor_y.set,
                              xscrollcommand=editor_x.set)
        self.editor.bind("<<Modified>>", self._editor_modified)
        self.editor.bind("<KeyRelease>", self._update_cursor_status, add="+")
        self.editor.tag_configure("paused_line", background="#664400")

        detection_frame = ttk.Labelframe(
            self.right_side, text="画像検知リスト（検知値→閾値→検知幅の高い順）")
        run_frame = ttk.Labelframe(
            self.right_side, text="途中実行・操作前一時停止")
        self.detection_frame = detection_frame
        self.run_frame = run_frame
        self.right_side.add(detection_frame, weight=6)
        self.right_side.add(run_frame, weight=4)
        self._build_detection_panel(detection_frame)
        self._build_run_panel(run_frame)

        self._layout_groups = [
            {
                "container": self.source_side,
                "weight": 7,
                "children": (
                    ("source_list", self.source_browser_frame, 2),
                    ("source_editor", self.source_editor_frame, 7),
                ),
            },
            {
                "container": self.right_side,
                "weight": 4,
                "children": (
                    ("image_detection", self.detection_frame, 6),
                    ("run_support", self.run_frame, 4),
                ),
            },
        ]
        self._apply_panel_visibility()

        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(
            fill="x", padx=6, pady=(0, 5))

    @staticmethod
    def _pane_has_child(pane, child):
        child_name = str(child)
        return any(str(item) == child_name for item in pane.panes())

    def _apply_panel_visibility(self):
        """Rebuild managed panes without destroying their widget contents."""
        if not self._layout_groups:
            return
        visible_groups = []
        for group in self._layout_groups:
            container = group["container"]
            for _key, child, _weight in group["children"]:
                if self._pane_has_child(container, child):
                    container.forget(child)
            group_visible = False
            for key, child, weight in group["children"]:
                if self.panel_visibility_vars[key].get():
                    container.add(child, weight=weight)
                    group_visible = True
            if group_visible:
                visible_groups.append(group)

        for group in self._layout_groups:
            container = group["container"]
            if self._pane_has_child(self.workspace_pane, container):
                self.workspace_pane.forget(container)
        for group in visible_groups:
            self.workspace_pane.add(
                group["container"], weight=group["weight"])

    def _panel_visibility_snapshot(self):
        return {
            key: bool(variable.get())
            for key, variable in self.panel_visibility_vars.items()
        }

    def _restore_panel_visibility(self):
        saved = self.current_profile.get("panel_visibility", {})
        for key, default in DEFAULT_PANEL_VISIBILITY.items():
            self.panel_visibility_vars[key].set(
                bool(saved.get(key, default)))
        self._apply_panel_visibility()

    def _panel_visibility_changed(self, _panel_key=None):
        self._apply_panel_visibility()
        if not self.current_profile:
            return
        self.current_profile["panel_visibility"] = \
            self._panel_visibility_snapshot()
        try:
            self.store.set(self.profile_name.get(), self.current_profile)
        except (OSError, TypeError, ValueError) as error:
            self.status.set("表示設定を保存できませんでした: {}".format(error))
            return
        self.status.set("パネルの表示設定を保存しました。")

    def set_comparison_opener(self, callback):
        """Register the optional recording/Commands comparison Toplevel."""
        self._comparison_opener = callback if callable(callback) else None
        self.comparison_button.configure(
            state="normal" if self._comparison_opener else "disabled")

    def open_step_comparison(self):
        if self._comparison_opener is not None:
            self._comparison_opener()

    def _comparison_source_snapshot(self):
        """Return the unsaved editor buffer without executing the source."""
        return {
            "source": self.editor.get("1.0", "end-1c"),
            "path": self.current_path,
        }

    def _apply_comparison_source(self, updated_source, source_path):
        """Replace only the current editor buffer; saving remains explicit."""
        if self._closing or not self.current_path:
            return False
        expected = os.path.normcase(os.path.abspath(source_path or ""))
        current = os.path.normcase(os.path.abspath(self.current_path))
        if expected != current:
            raise ValueError(
                "比較後に編集対象のソースが切り替わりました。3列を再読込してください。")
        ast.parse(updated_source)
        source_before_replace = self.editor.get("1.0", "end-1c")
        dirty_before_replace = self.editor_dirty
        cursor = self.editor.index("insert")
        ignore_before_replace = self._ignore_editor_modified
        self._ignore_editor_modified = True
        try:
            # One Tk ``replace`` command is one undo record.  Separate
            # delete/insert commands make the first Ctrl+Z leave an empty
            # editor, which is unsafe if that intermediate state is saved.
            self.editor.replace("1.0", "end", updated_source)
            self.editor.edit_modified(False)
            try:
                self.editor.mark_set("insert", cursor)
            except tk.TclError:
                self.editor.mark_set("insert", "1.0")
        except Exception:
            # A destroyed widget or Tcl failure can still interrupt a widget
            # update.  Restore the exact unsaved draft and its dirty state.
            try:
                self.editor.replace("1.0", "end", source_before_replace)
                self.editor.edit_modified(dirty_before_replace)
                try:
                    self.editor.mark_set("insert", cursor)
                except tk.TclError:
                    self.editor.mark_set("insert", "1.0")
            except Exception:
                pass
            self.editor_dirty = dirty_before_replace
            raise
        finally:
            self._ignore_editor_modified = ignore_before_replace
        self.editor_dirty = True
        self.source_label.configure(
            text=_display_basename(self.current_path) + " *")
        self.status.set(
            "比較画面の変更をエディタへ反映しました。確認後に保存してください。")
        self.editor.focus_set()
        return True

    def _comparison_open_source(self, path, line=0):
        """Open a live source, never a recording's immutable snapshot."""
        requested = os.path.abspath(path) if path else self.current_path
        recording_value = self.current_profile.get(
            "last_command_recording", "") or ""
        recording = os.path.abspath(recording_value) \
            if recording_value else ""
        is_recording_artifact = False
        if requested and recording:
            try:
                is_recording_artifact = os.path.normcase(os.path.commonpath(
                    (requested, recording))) == os.path.normcase(recording)
            except ValueError:
                is_recording_artifact = False
        if is_recording_artifact:
            requested = self.current_path
            self.status.set(
                "録画時ソースは証跡として保持し、現在ソースの対応行を表示します。")
        if requested and (not self.current_path or
                          os.path.normcase(requested) !=
                          os.path.normcase(self.current_path)):
            if not os.path.isfile(requested) or not self.open_source(requested):
                return False
        if not self.current_path:
            return False
        try:
            target_line = max(1, int(line or 1))
        except (TypeError, ValueError):
            target_line = 1
        last_line = max(1, int(self.editor.index("end-1c").split(".", 1)[0]))
        target_line = min(target_line, last_line)
        start = "{}.0".format(target_line)
        self.editor.mark_set("insert", start)
        self.editor.tag_remove("sel", "1.0", "end")
        self.editor.tag_add("sel", start, "{}.end".format(target_line))
        self.editor.see(start)
        self.deiconify()
        self.lift()
        self.editor.focus_set()
        self._update_cursor_status()
        return True

    def _comparison_paths_changed(self, operation_session,
                                  command_recording):
        profile_name = self._comparison_profile_name or self.profile_name.get()
        if not profile_name:
            return
        if profile_name == self.profile_name.get() and self.current_profile:
            profile = self.current_profile
        else:
            profile = self.store.get(profile_name)
        profile["last_operation_session"] = (
            os.path.abspath(operation_session) if operation_session else "")
        profile["last_command_recording"] = (
            os.path.abspath(command_recording) if command_recording else "")
        self.store.set(profile_name, profile, select=False)

    def _comparison_image_folders(self):
        """Expose full configured paths; capture UIs render basename labels."""
        profile = normalize_profile(self.current_profile, self.project_root)
        return list(profile.get("image_folders", []))

    def _merge_detection_rows_into_editor(self, rows, expected_source_path=""):
        """Merge registrations into the unsaved editor buffer atomically."""
        if self._closing or not self.current_path:
            raise ValueError("先に追加先のソースを開いてください。")
        if expected_source_path:
            expected = os.path.normcase(os.path.abspath(expected_source_path))
            current = os.path.normcase(os.path.abspath(self.current_path))
            if expected != current:
                raise ValueError(
                    "画像を選んだ後に編集対象ソースが切り替わりました。"
                    "比較画面を再読込してから登録してください。")
        source = self.editor.get("1.0", "end-1c")
        source_before_merge = source
        names = []
        for row in rows:
            source, name = add_detection_to_source(
                source, row, self.project_root)
            names.append(name)
        ast.parse(source)
        self._ignore_editor_modified = True
        try:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", source)
            self.editor.edit_modified(False)
        except Exception:
            # Tk text replacement is normally all-or-nothing at this scale,
            # but restore the prior draft if the widget is destroyed or a
            # Tcl error interrupts the insert.  The capture callback can then
            # safely roll its PNG transaction back as well.
            try:
                self.editor.delete("1.0", "end")
                self.editor.insert("1.0", source_before_merge)
                self.editor.edit_modified(self.editor_dirty)
            except Exception:
                pass
            raise
        finally:
            self._ignore_editor_modified = False
        self.editor_dirty = True
        # From here the editor draft references the new PNG.  Nonessential UI
        # refresh failures must not escape to the capture dialog, which would
        # otherwise restore the image while leaving a dangling source entry.
        try:
            self.source_label.configure(
                text=_display_basename(self.current_path) + " *")
            self.status.set(
                "画像検知{}件をソースへ追加しました。保存前に内容を確認できます。".format(
                    len(names)))
            # Rebuild against the unsaved editor snapshot so the default
            # source-only filter does not hide the just-created registration.
            self.initialize_detections()
        except Exception as error:
            try:
                self.status.set(
                    "画像検知はソースへ追加済み（未保存）ですが、一覧を再読込できません: {}".format(
                        error))
            except Exception:
                pass
        return names

    def _register_recording_image_check(self, row, source_path=""):
        names = self._merge_detection_rows_into_editor(
            [row], expected_source_path=source_path)
        return names[0]

    def open_recording_comparison(self):
        existing = self.recording_comparison_window
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    existing.focus_force()
                    return existing
            except tk.TclError:
                pass
        try:
            from RecordingComparison import RecordingComparisonWindow
        except ImportError:  # pragma: no cover - package import fallback
            from .RecordingComparison import RecordingComparisonWindow
        self._comparison_profile_name = self.profile_name.get()
        self.recording_comparison_window = RecordingComparisonWindow(
            self, self.project_root,
            source_provider=self._comparison_source_snapshot,
            apply_source_callback=self._apply_comparison_source,
            open_source_callback=self._comparison_open_source,
            paths_changed_callback=self._comparison_paths_changed,
            image_folders_provider=self._comparison_image_folders,
            register_image_check_callback=self._register_recording_image_check,
            initial_operation_session=self.current_profile.get(
                "last_operation_session", ""),
            initial_command_recording=self.current_profile.get(
                "last_command_recording", ""))
        return self.recording_comparison_window

    def _build_detection_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))
        self.detection_initialize_button = ttk.Button(
            controls, text="初期化 / 再読込",
            command=self.initialize_detections)
        self.detection_initialize_button.pack(side="left", padx=2)
        self.detection_start_button = ttk.Button(
            controls, text="開始", command=self.start_detection)
        self.detection_start_button.pack(side="left", padx=2)
        self.detection_pause_button = ttk.Button(
            controls, text="一時停止", command=self.toggle_detection_pause)
        self.detection_pause_button.pack(side="left", padx=2)
        ttk.Button(controls, text="終了", command=self.stop_detection).pack(
            side="left", padx=2)
        ttk.Checkbutton(
            controls, text="ソースで使う画像だけ",
            variable=self.source_only,
            command=self.refresh_detection_tree).pack(side="left", padx=8)
        input_row = ttk.Frame(parent)
        input_row.grid(row=1, column=0, sticky="ew", padx=5, pady=2)
        ttk.Label(input_row, text="入力:").pack(side="left")
        self.capture_entry = ttk.Entry(
            input_row, textvariable=self.capture_source, width=32)
        self.capture_entry.pack(
            side="left", fill="x", expand=True, padx=3)
        input_help = ("PokeConのFresh Frameを共有中"
                      if self.frame_provider is not None else
                      "0 / 動画 / 静止画")
        ttk.Label(input_row, text=input_help).pack(side="left")
        if self.frame_provider is not None:
            self.capture_source.set("PokeCon live")
            self.capture_entry.configure(state="disabled")
        tree_holder = ttk.Frame(parent)
        tree_holder.grid(row=2, column=0, sticky="nsew", padx=5, pady=3)
        tree_holder.columnconfigure(0, weight=1)
        tree_holder.rowconfigure(0, weight=1)
        columns = ("score", "threshold", "width", "image")
        self.detection_tree = ttk.Treeview(
            tree_holder, columns=columns, show="tree headings",
            selectmode="extended")
        self.detection_tree.heading("#0", text="検知名")
        for column, label, width in (
                ("score", "検知値", 75), ("threshold", "閾値", 65),
                ("width", "検知幅", 65), ("image", "画像", 260)):
            self.detection_tree.heading(column, text=label)
            self.detection_tree.column(column, width=width, stretch=column == "image")
        self.detection_tree.column("#0", width=190)
        self.detection_tree.grid(row=0, column=0, sticky="nsew")
        detection_scroll = ttk.Scrollbar(
            tree_holder, orient="vertical", command=self.detection_tree.yview)
        detection_scroll.grid(row=0, column=1, sticky="ns")
        self.detection_tree.configure(yscrollcommand=detection_scroll.set)
        self.detection_tree.tag_configure("matched", foreground="#159447")
        self.detection_tree.tag_configure("source", background="#eef6ff")
        self.detection_tree.tag_configure("error", foreground="#b42318")
        actions = ttk.Frame(parent)
        actions.grid(row=3, column=0, sticky="ew", padx=5, pady=(2, 3))
        ttk.Button(
            actions, text="選択した検知内容を現在ソースへ追加",
            command=self.add_selected_detections_to_source).pack(side="left")
        ttk.Label(actions, textvariable=self.detection_status).pack(
            side="left", fill="x", expand=True, padx=8)

    def _build_run_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        output_row = 4 if self.runtime_actions else 3
        parent.rowconfigure(output_row, weight=1)
        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))
        ttk.Button(controls, text="カーソルまで実行",
                   command=lambda: self.run_source("cursor")).pack(
                       side="left", padx=2)
        ttk.Button(controls, text="通常実行 (F5)",
                   command=lambda: self.run_source("normal")).pack(
                       side="left", padx=2)
        ttk.Button(controls, text="選択範囲を実行",
                   command=lambda: self.run_source("selection")).pack(
                       side="left", padx=2)
        ttk.Checkbutton(
            controls, text="操作コード直前で一時停止",
            variable=self.pause_before_operations).pack(side="left", padx=6)
        debug_controls = ttk.Frame(parent)
        debug_controls.grid(row=1, column=0, sticky="ew", padx=5, pady=2)
        ttk.Button(debug_controls, text="再開", command=lambda: self._send_run_command(
            "continue")).pack(side="left", padx=2)
        ttk.Button(debug_controls, text="1行進む", command=lambda: self._send_run_command(
            "step")).pack(side="left", padx=2)
        ttk.Button(debug_controls, text="停止", command=self.stop_run).pack(
            side="left", padx=2)
        ttk.Button(debug_controls, text="出力消去", command=lambda: self._set_run_output(
            "")).pack(side="left", padx=8)
        ttk.Label(debug_controls, textvariable=self.run_status).pack(
            side="left", fill="x", expand=True, padx=5)
        ttk.Label(
            parent,
            text=("上段は通常Python／選択断片の確認用です。"
                  "PokeCon Commandsの実機実行は下段の専用機能を使います。"
                  if self.runtime_actions else
                  "通常Python／選択断片を別プロセスで確認します。"),
            foreground="#555555").grid(
                row=2, column=0, sticky="w", padx=8, pady=(0, 2))
        if self.runtime_actions:
            runtime_controls = ttk.Frame(parent)
            runtime_controls.grid(row=3, column=0, sticky="ew", padx=5, pady=2)
            ttk.Label(runtime_controls, text="PokeCon実機:").pack(side="left")
            ttk.Button(
                runtime_controls, text="カーソルStepを実行範囲へ…",
                command=lambda: self._runtime_action("run_settings")).pack(
                    side="left", padx=2)
            ttk.Button(
                runtime_controls, text="カーソルStepの操作前で停止…",
                command=lambda: self._runtime_action("step_debug")).pack(
                    side="left", padx=2)
            ttk.Button(
                runtime_controls, text="Reload Commands",
                command=lambda: self._runtime_action("reload_commands")).pack(
                    side="left", padx=2)
        output_holder = ttk.Frame(parent)
        output_holder.grid(row=output_row, column=0,
                           sticky="nsew", padx=5, pady=(2, 5))
        output_holder.columnconfigure(0, weight=1)
        output_holder.rowconfigure(0, weight=1)
        self.run_output = tk.Text(
            output_holder, height=10, wrap="word", state="disabled",
            background="#101010", foreground="#e0e0e0",
            font=("Consolas", 9))
        self.run_output.grid(row=0, column=0, sticky="nsew")
        run_scroll = ttk.Scrollbar(
            output_holder, orient="vertical", command=self.run_output.yview)
        run_scroll.grid(row=0, column=1, sticky="ns")
        self.run_output.configure(yscrollcommand=run_scroll.set)

    def _confirm_editor_change(self):
        if not self.editor_dirty:
            return True
        answer = messagebox.askyesnocancel(
            "PokeConStudio", "現在のソースを保存しますか？", parent=self)
        if answer is None:
            return False
        if answer:
            return bool(self.save_source())
        return True

    def load_profile(self, name, initial_source=""):
        if not name or name not in self.store.data["profiles"]:
            return
        comparison = self.recording_comparison_window
        previous_profile = (self._comparison_profile_name or
                            self.store.data.get("last_profile", name))
        if (self.current_profile and name != previous_profile
                and comparison is not None):
            try:
                if comparison.winfo_exists():
                    comparison.close()
                    if comparison.winfo_exists():
                        self.profile_name.set(previous_profile)
                        if previous_profile in self.store.data["profiles"]:
                            self.store.select(previous_profile)
                        return
            except tk.TclError:
                pass
            self.recording_comparison_window = None
            self._comparison_profile_name = ""
        if not self._confirm_editor_change():
            self.profile_name.set(self.store.data.get("last_profile", name))
            return
        self.stop_detection()
        self.current_profile = self.store.get(name)
        self._restore_panel_visibility()
        self.profile_name.set(name)
        self.profile_combo.configure(values=self.store.names())
        self.capture_source.set(
            "PokeCon live" if self.frame_provider is not None else
            self.current_profile.get("capture_source", "0"))
        self.store.select(name)
        self.refresh_sources()
        target = os.path.abspath(initial_source) if initial_source else \
            self.current_profile.get("last_source", "")
        if target and any(os.path.normcase(path) == os.path.normcase(target)
                          for path in self.source_paths):
            self.open_source(target)
        elif self.source_paths:
            self.open_source(self.source_paths[0])
        else:
            self._clear_editor()
        self.initialize_detections()
        self.status.set("設定「{}」を読み込みました。".format(name))

    def edit_profile(self, copy_profile=False):
        name = self.profile_name.get() or self.store.names()[0]
        profile = dict(self.current_profile or self.store.get(name))
        dialog_name = (name + " のコピー") if copy_profile else name
        dialog = ProfileDialog(
            self, dialog_name, profile, self.project_root)
        self.wait_window(dialog)
        if not dialog.result:
            return
        new_name, edited_profile = dialog.result
        # The dialog edits only path/capture/pattern fields.  Keep resume
        # state such as panel visibility and recording selections when a
        # profile is edited or copied.
        new_profile = dict(profile)
        new_profile.update(edited_profile)
        if (new_name != name and new_name in self.store.data["profiles"] and
                not messagebox.askyesno(
                    "PokeConStudio", "設定「{}」を上書きしますか？".format(new_name),
                    parent=self)):
            return
        self.store.set(new_name, new_profile)
        if not copy_profile and new_name != name:
            self.store.delete(name)
        self.load_profile(new_name)

    def save_profile_state(self):
        if not self.current_profile:
            return True
        if self.frame_provider is None:
            self.current_profile["capture_source"] = self.capture_source.get().strip() or "0"
        self.current_profile["last_source"] = self.current_path
        self.current_profile["panel_visibility"] = \
            self._panel_visibility_snapshot()
        try:
            self.store.set(self.profile_name.get(), self.current_profile)
        except (OSError, TypeError, ValueError) as error:
            self.status.set("設定を保存できませんでした。")
            messagebox.showerror(
                "PokeConStudio - 設定保存エラー",
                "現在の設定を保存できませんでした。\n\n{}".format(error),
                parent=self)
            return False
        self.status.set("現在の入力と開いているソースを設定へ保存しました。")
        return True

    def delete_profile(self):
        name = self.profile_name.get()
        if not messagebox.askyesno(
                "PokeConStudio", "設定「{}」を削除しますか？".format(name),
                parent=self):
            return
        try:
            self.store.delete(name)
        except ValueError as error:
            messagebox.showwarning("PokeConStudio", str(error), parent=self)
            return
        self.load_profile(self.store.data["last_profile"])

    def refresh_sources(self):
        self.source_paths = discover_source_files(self.current_profile)
        self.refresh_source_tree()
        self.status.set("ソース{} 件を読み込みました。".format(
            len(self.source_paths)))

    def refresh_source_tree(self):
        if not hasattr(self, "source_tree"):
            return
        selected_path = self.current_path
        self.source_tree.delete(*self.source_tree.get_children())
        needle = self.source_filter.get().strip().casefold()
        selected_iid = ""
        for index, path in enumerate(self.source_paths):
            label = _display_basename(path)
            if needle and needle not in label.casefold():
                continue
            iid = "source-{}".format(index)
            self.source_tree.insert("", "end", iid=iid, text=label,
                                    values=(path,))
            if selected_path and os.path.normcase(path) == os.path.normcase(selected_path):
                selected_iid = iid
        if selected_iid:
            self.source_tree.selection_set(selected_iid)
            self.source_tree.see(selected_iid)

    def _source_selected(self, _event=None):
        selected = self.source_tree.selection()
        if not selected:
            return
        index = int(selected[0].split("-", 1)[1])
        if 0 <= index < len(self.source_paths):
            path = self.source_paths[index]
            if not self.current_path or os.path.normcase(path) != os.path.normcase(self.current_path):
                self.open_source(path)

    def _clear_editor(self):
        self._ignore_editor_modified = True
        self.editor.delete("1.0", "end")
        self.editor.edit_modified(False)
        self._ignore_editor_modified = False
        self.current_path = ""
        self.editor_dirty = False
        self.source_label.configure(text="ソースがありません")

    def open_source(self, path):
        if self.current_path and not self._confirm_editor_change():
            self.refresh_source_tree()
            return False
        try:
            source, encoding = read_source(path)
        except (OSError, UnicodeError) as error:
            messagebox.showerror("PokeConStudio", str(error), parent=self)
            return False
        self._ignore_editor_modified = True
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", source)
        self.editor.edit_modified(False)
        self._ignore_editor_modified = False
        self.current_path = os.path.abspath(path)
        self.current_encoding = encoding
        self.editor_dirty = False
        self.source_label.configure(text=_display_basename(self.current_path))
        self.current_profile["last_source"] = self.current_path
        self.refresh_source_tree()
        self._update_cursor_status()
        return True

    def reload_source(self):
        if not self.current_path:
            return
        if self.editor_dirty and not messagebox.askyesno(
                "PokeConStudio", "未保存の編集を破棄して再読込しますか？",
                parent=self):
            return
        self.editor_dirty = False
        self.open_source(self.current_path)

    def _editor_modified(self, _event=None):
        if self._ignore_editor_modified:
            return
        if self.editor.edit_modified():
            self.editor_dirty = True
            self.editor.edit_modified(False)
            self.source_label.configure(
                text=(_display_basename(self.current_path) or "未選択") + " *")

    def _update_cursor_status(self, _event=None):
        if not self.current_path:
            return
        line, column = self.editor.index("insert").split(".", 1)
        self.status.set("{}  /  行 {}  列 {}{}".format(
            _display_basename(self.current_path), line, column,
            "  (未保存)" if self.editor_dirty else ""))

    def save_source(self):
        if not self.current_path:
            return False
        source = self.editor.get("1.0", "end-1c")
        try:
            ast.parse(source)
        except SyntaxError as error:
            if not messagebox.askyesno(
                    "PokeConStudio",
                    "Python構文エラーがあります。それでも保存しますか？\n\n{}".format(error),
                    parent=self):
                return False
        directory = os.path.dirname(self.current_path)
        backup_dir = os.path.join(directory, ".pokecon-studio-backups")
        try:
            if not os.path.isdir(backup_dir):
                os.makedirs(backup_dir)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup = os.path.join(
                backup_dir, os.path.basename(self.current_path) + "." + stamp + ".bak")
            shutil.copy2(self.current_path, backup)
            handle, temporary = tempfile.mkstemp(
                prefix=".pokecon-studio-", suffix=".tmp", dir=directory)
            try:
                with os.fdopen(handle, "w", encoding=self.current_encoding,
                               newline="") as stream:
                    stream.write(source)
                os.replace(temporary, self.current_path)
            finally:
                if os.path.exists(temporary):
                    os.remove(temporary)
        except (OSError, UnicodeError) as error:
            messagebox.showerror("PokeConStudio", "保存できません。\n" + str(error),
                                 parent=self)
            return False
        self.editor_dirty = False
        self.source_label.configure(text=_display_basename(self.current_path))
        self.status.set("保存しました: " + _display_basename(self.current_path))
        return True

    def initialize_detections(self):
        self.stop_detection()
        self._scan_generation += 1
        generation = self._scan_generation
        profile = normalize_profile(self.current_profile, self.project_root)
        source_paths = list(self.source_paths)
        source_overrides = {}
        if self.current_path:
            current_key = os.path.normcase(os.path.abspath(self.current_path))
            if not any(os.path.normcase(os.path.abspath(path)) == current_key
                       for path in source_paths):
                source_paths.append(self.current_path)
            source_overrides[current_key] = self.editor.get("1.0", "end-1c")
        self.detection_status.set("ソースと画像フォルダを読込中…")
        self.detection_start_button.configure(state="disabled")
        cancel_event = threading.Event()
        with self._scan_lock:
            if self._scan_cancel is not None:
                self._scan_cancel.set()
            self._scan_cancel = cancel_event
            # Keep only the newest requested profile.  A running scan notices
            # its cancellation token and the single worker then processes this
            # request; repeated clicks cannot create parallel 25-second scans.
            self._scan_request = (
                generation, profile, source_paths, source_overrides,
                cancel_event)
            if self._scan_thread is not None:
                return
            self._scan_thread = threading.Thread(
                target=self._catalog_worker_loop, daemon=True,
                name="PokeConStudioCatalog")
            self._scan_thread.start()

    def _catalog_worker_loop(self):
        while True:
            with self._scan_lock:
                request = self._scan_request
                self._scan_request = None
                if request is None:
                    self._scan_thread = None
                    return
            generation, profile, source_paths, source_overrides, cancel_event = request
            try:
                rows = build_detection_catalog(
                    profile, source_paths, self.project_root,
                    cancel_event=cancel_event,
                    source_overrides=source_overrides)
                if not cancel_event.is_set():
                    self._event_queue.put(("scan_done", generation, rows))
            except BaseException as error:
                if not cancel_event.is_set():
                    self._event_queue.put(
                        ("scan_error", generation, str(error)))

    def refresh_detection_tree(self):
        if not hasattr(self, "detection_tree"):
            return
        selected = set(self.detection_tree.selection())
        self.detection_tree.delete(*self.detection_tree.get_children())
        visible = [row for row in self.catalog
                   if not self.source_only.get() or row.get("source_defined")]
        visible.sort(key=detection_sort_key)
        for row in visible:
            score = row.get("score")
            score_text = ("ERR" if row.get("last_error") else
                          "---" if score is None else
                          "{:.6f}".format(float(score)))
            tags = []
            if row.get("matched"):
                tags.append("matched")
            elif row.get("last_error"):
                tags.append("error")
            if row.get("source_defined"):
                tags.append("source")
            self.detection_tree.insert(
                "", "end", iid=row["id"], text=row["name"],
                values=(score_text, "{:.3f}".format(float(row.get("threshold", 0.8))),
                        (row.get("detection_width", 0) or "全幅"),
                        _display_basename(row.get("template_path", ""))),
                tags=tuple(tags))
        remaining = [iid for iid in selected if self.detection_tree.exists(iid)]
        if remaining:
            self.detection_tree.selection_set(remaining)
        error_count = sum(1 for row in visible if row.get("last_error"))
        suffix = " / エラー {}".format(error_count) if error_count else ""
        self.detection_status.set("表示 {} / 全 {} パターン{}".format(
            len(visible), len(self.catalog), suffix))
        self._detection_tree_last_refresh = time.monotonic()

    def _schedule_detection_tree_refresh(self):
        """Coalesce live score sorting so it cannot monopolize PokeCon's Tk."""
        self._detection_tree_dirty = True
        if self._detection_tree_refresh_after is not None:
            return
        elapsed = time.monotonic() - self._detection_tree_last_refresh
        delay_ms = max(1, int(max(0.0, 0.5 - elapsed) * 1000.0))
        self._detection_tree_refresh_after = self.after(
            delay_ms, self._flush_detection_tree_refresh)

    def _flush_detection_tree_refresh(self):
        self._detection_tree_refresh_after = None
        if not self._detection_tree_dirty:
            return
        self._detection_tree_dirty = False
        self._detection_tree_last_refresh = time.monotonic()
        self.refresh_detection_tree()

    def start_detection(self):
        if self._detection_thread and self._detection_thread.is_alive():
            if (self._detection_stop is not None and
                    self._detection_stop.is_set()):
                self.detection_status.set(
                    "画像検知の終了処理中です。完了後に開始してください。")
                return
            if self._detection_pause:
                self._detection_pause.clear()
                self.detection_pause_button.configure(text="一時停止")
                self.detection_status.set("画像検知を再開しました。")
            return
        if self._detection_thread is not None:
            # The worker has exited and only its queued completion notification
            # remains.  It is safe to retire this exact dead worker now.
            self._detection_thread = None
            self._detection_stop = None
            self._detection_pause = None
        with self._scan_lock:
            scan_running = self._scan_thread is not None
        if scan_running:
            self.detection_status.set("初期化中です。完了後に開始してください。")
            return
        if not self.catalog:
            self.initialize_detections()
            self.detection_status.set("初期化後にもう一度「開始」を押してください。")
            return
        self._detection_stop = threading.Event()
        self._detection_pause = threading.Event()
        self._detection_generation += 1
        generation = self._detection_generation
        baseline_sequence = (self.frame_sequence_provider()
                             if callable(self.frame_sequence_provider) else None)
        source = self.capture_source.get().strip() or "0"
        rows = [
            row for row in self.catalog
            if not self.source_only.get() or row.get("source_defined")]
        if not rows:
            self.detection_status.set(
                "ソースで使う画像がありません。チェックを外すか、ソースへ検知を追加してください。")
            return
        self._detection_thread = threading.Thread(
            target=self._detection_loop,
            args=(rows, source, self._detection_stop, self._detection_pause,
                  generation, baseline_sequence),
            daemon=True, name="PokeConStudioDetection")
        self._detection_thread.start()
        self.detection_pause_button.configure(text="一時停止")
        self.detection_status.set("画像検知を開始しました。")

    def _detection_loop(self, rows, source, stop_event, pause_event,
                        generation, baseline_sequence=None):
        capture = None
        try:
            import cv2
            import numpy as np
            static_frame = None
            source_path = os.path.abspath(source) if os.path.isfile(source) else ""
            if self.frame_provider is not None:
                pass
            elif source_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                static_frame = cv2.imdecode(
                    np.fromfile(source_path, dtype=np.uint8), cv2.IMREAD_COLOR)
                if static_frame is None:
                    raise ValueError("入力画像を読み込めません: " + source_path)
            else:
                capture_value = int(source) if source.isdigit() else source
                if isinstance(capture_value, int) and os.name == "nt":
                    capture = cv2.VideoCapture(capture_value, cv2.CAP_DSHOW)
                    if not capture.isOpened():
                        capture.release()
                        capture = cv2.VideoCapture(capture_value)
                else:
                    capture = cv2.VideoCapture(capture_value)
                if not capture.isOpened():
                    raise ValueError("入力を開けません: " + source)

            templates = {}
            index = 0
            while not stop_event.is_set():
                if pause_event.is_set():
                    stop_event.wait(0.08)
                    continue
                if not rows:
                    stop_event.wait(0.1)
                    continue
                if self.frame_provider is not None:
                    frame = self.frame_provider(baseline_sequence)
                    baseline_sequence = None
                    if frame is None:
                        stop_event.wait(0.05)
                        continue
                    try:
                        frame = frame.copy()
                    except AttributeError:
                        pass
                elif static_frame is not None:
                    frame = static_frame
                else:
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        if os.path.isfile(source):
                            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            stop_event.wait(0.05)
                            continue
                        stop_event.wait(0.05)
                        continue
                row = rows[index % len(rows)]
                index += 1
                try:
                    path = row.get("template_path", "")
                    modified = os.path.getmtime(path)
                    cached = templates.get(row["id"])
                    if cached is None or cached[0] != modified:
                        template = cv2.imdecode(
                            np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if template is None:
                            raise ValueError("画像を読み込めません: " + path)
                        cached = (modified, template)
                        templates[row["id"]] = cached
                    detail = match_detection_row(frame, cached[1], row)
                    self._event_queue.put(
                        ("detection", generation, row["id"], detail))
                except (OSError, ValueError, TypeError, cv2.error) as error:
                    self._event_queue.put(
                        ("detection_error", generation, row["id"], str(error)))
                # Matching every template on every 60-FPS frame would compete
                # with the preview/Commands threads.  One bounded match every
                # 30 ms keeps the ranked list moving without starving input.
                stop_event.wait(0.03)
        except BaseException as error:
            self._event_queue.put(
                ("detection_state", generation, "画像検知エラー: " + str(error)))
        finally:
            if capture is not None:
                capture.release()
            self._event_queue.put(
                ("detection_stopped", generation, threading.current_thread(),
                 stop_event, stop_event.is_set()))

    def toggle_detection_pause(self):
        if not self._detection_thread or not self._detection_thread.is_alive():
            self.detection_status.set("画像検知は開始されていません。")
            return
        if self._detection_pause.is_set():
            self._detection_pause.clear()
            self.detection_pause_button.configure(text="一時停止")
            self.detection_status.set("画像検知を再開しました。")
        else:
            self._detection_pause.set()
            self.detection_pause_button.configure(text="再開")
            self.detection_status.set("画像検知を一時停止しました。")

    def stop_detection(self):
        worker = self._detection_thread
        was_active = bool(worker and worker.is_alive())
        if self._detection_stop is not None and not self._detection_stop.is_set():
            self._detection_stop.set()
            # Ignore score events already queued by this worker while keeping
            # its identity until its final completion notification arrives.
            self._detection_generation += 1
        if worker is not None and not worker.is_alive():
            self._detection_thread = None
            self._detection_stop = None
            self._detection_pause = None
        self.detection_pause_button.configure(text="一時停止")
        if was_active:
            self.detection_status.set("画像検知を終了処理中…")

    def add_selected_detections_to_source(self):
        if not self.current_path:
            messagebox.showwarning("PokeConStudio", "先に追加先のソースを開いてください。",
                                   parent=self)
            return
        selected = self.detection_tree.selection()
        if not selected:
            messagebox.showwarning("PokeConStudio", "画像検知を選択してください。",
                                   parent=self)
            return
        try:
            rows = [self.catalog_by_id[iid] for iid in selected]
            self._merge_detection_rows_into_editor(rows)
        except (KeyError, SyntaxError, ValueError, OSError) as error:
            messagebox.showerror("PokeConStudio", "ソースへ追加できません。\n" + str(error),
                                 parent=self)
            return

    def run_source(self, mode):
        if not self.current_path:
            messagebox.showwarning("PokeConStudio", "実行するソースを開いてください。",
                                   parent=self)
            return
        if self.run_process and self.run_process.poll() is None:
            messagebox.showwarning("PokeConStudio", "現在の実行を停止してください。",
                                   parent=self)
            return
        source = self.editor.get("1.0", "end-1c")
        selection_mode = mode == "selection"
        if selection_mode:
            try:
                source = textwrap.dedent(self.editor.get("sel.first", "sel.last"))
            except tk.TclError:
                messagebox.showwarning("PokeConStudio", "実行する範囲を選択してください。",
                                       parent=self)
                return
        try:
            ast.parse(source)
        except SyntaxError as error:
            messagebox.showerror("PokeConStudio", "Python構文エラー:\n" + str(error),
                                 parent=self)
            return
        snapshot_dir = os.path.join(
            os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(),
            "PokeConModifiedExtension", "studio-runs")
        if not os.path.isdir(snapshot_dir):
            os.makedirs(snapshot_dir)
        handle, snapshot = tempfile.mkstemp(
            prefix="pokecon-studio-", suffix=".py", dir=snapshot_dir)
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(source)
            if not source.endswith("\n"):
                stream.write("\n")
        self._run_generation += 1
        generation = self._run_generation
        self.run_snapshot = snapshot
        self.run_selection_mode = selection_mode
        break_line = int(self.editor.index("insert").split(".", 1)[0]) \
            if mode == "cursor" else 0
        runner = os.path.join(self.studio_root, "StudioRunner.py")
        command = [sys.executable, "-u", runner,
                   "--source", self.current_path,
                   "--snapshot", snapshot,
                   "--working-dir", os.path.dirname(self.current_path),
                   "--break-line", str(break_line),
                   "--operation-patterns", json.dumps(
                       self.current_profile.get(
                           "operation_patterns", DEFAULT_OPERATION_PATTERNS),
                       ensure_ascii=False)]
        if self.pause_before_operations.get():
            command.append("--pause-before-operations")
        include_paths = list(self.current_profile.get("include_folders", []))
        include_paths.extend(self.current_profile.get("source_folders", []))
        for path in include_paths:
            command.extend(["--include-dir", path])
        options = {
            "cwd": os.path.dirname(self.current_path),
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if os.name == "nt":
            options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.run_process = subprocess.Popen(command, **options)
        except OSError as error:
            self._cleanup_run_snapshot()
            messagebox.showerror("PokeConStudio", str(error), parent=self)
            return
        self.editor.tag_remove("paused_line", "1.0", "end")
        self.run_status.set("実行中")
        self._append_run_output("\n=== {} / {} ===\n".format(
            os.path.basename(self.current_path), mode))

        def reader(process, run_generation, run_snapshot):
            try:
                for line in iter(process.stdout.readline, ""):
                    self._queue_run_line(run_generation, line)
            finally:
                process.stdout.close()
                process.wait()
                # EOF is a control event and must never be dropped, even when
                # ordinary output from the child has reached its bound.
                self._event_queue.put((
                    "run_eof", run_generation, process, run_snapshot,
                    process.returncode))

        threading.Thread(
            target=reader,
            args=(self.run_process, generation, snapshot), daemon=True,
                          name="PokeConStudioRunnerOutput").start()

    @staticmethod
    def _is_runner_control_line(line):
        if not line.startswith(EVENT_PREFIX):
            return False
        try:
            detail = json.loads(line[len(EVENT_PREFIX):])
        except (TypeError, ValueError):
            return False
        return isinstance(detail, dict) and bool(detail.get("event"))

    def _queue_run_line(self, generation, line):
        """Bound ordinary stdout while preserving runner control messages."""
        if self._is_runner_control_line(line):
            self._event_queue.put(("run_line", generation, line, 0))
            return
        maximum_lines = 1200
        maximum_chars = 250000
        text = str(line)
        if len(text) > maximum_chars:
            text = ("[PokeConStudio] 1行が長すぎるため末尾だけを表示します。\n"
                    + text[-(maximum_chars - 100):])
        queue_notice = False
        with self._run_pending_lock:
            if (self._run_pending_lines >= maximum_lines or
                    self._run_pending_chars + len(text) > maximum_chars):
                self._run_dropped_lines += 1
                if not self._run_drop_notice_queued:
                    self._run_drop_notice_queued = True
                    queue_notice = True
            else:
                self._run_pending_lines += 1
                self._run_pending_chars += len(text)
                self._event_queue.put(
                    ("run_line", generation, text, len(text)))
        if queue_notice:
            # This notification is separate from ordinary output and therefore
            # remains deliverable while that output is at its limit.
            self._event_queue.put(("run_output_dropped", generation))

    def _release_run_line_budget(self, length):
        if not length:
            return
        with self._run_pending_lock:
            self._run_pending_lines = max(0, self._run_pending_lines - 1)
            self._run_pending_chars = max(
                0, self._run_pending_chars - int(length))

    def _send_run_command(self, command):
        process = self.run_process
        if process is None or process.poll() is not None:
            self.run_status.set("実行中のソースはありません。")
            return
        try:
            process.stdin.write(command + "\n")
            process.stdin.flush()
        except (OSError, ValueError):
            self.run_status.set("実行プロセスへ送信できません。")

    def stop_run(self, wait=False):
        process = self.run_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
            self.run_status.set("停止中…")
        if wait and process is not None:
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait(timeout=2.0)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if process.poll() is None:
                self.run_status.set("実行プロセスを停止できませんでした。")
                return False
            self.run_process = None
            self._cleanup_run_snapshot()
        return True

    def _runtime_action(self, name):
        callback = self.runtime_actions.get(name)
        if not callable(callback):
            self.run_status.set("PokeCon実機機能へ接続できません。")
            return
        if self.editor_dirty:
            decision = messagebox.askyesnocancel(
                "PokeConStudio - 保存が必要です",
                "未保存の編集があります。\n"
                "保存してからCommandsを再読込しますか？\n\n"
                "［いいえ］または［キャンセル］では、古い保存版を誤って再読込しないため中止します。",
                parent=self)
            if decision is not True:
                self.run_status.set("未保存の編集があるため実機連携を中止しました。")
                return
            if not self.save_source():
                self.run_status.set("保存できなかったため実機連携を中止しました。")
                return
        try:
            if name in ("run_settings", "step_debug"):
                if not self.current_path:
                    messagebox.showwarning(
                        "PokeConStudio", "先に対象のソースを開いてください。",
                        parent=self)
                    return
                cursor_line = int(
                    self.editor.index("insert").split(".", 1)[0])
                callback(self.current_path, cursor_line)
            else:
                callback()
        except Exception as error:
            messagebox.showerror(
                "PokeConStudio", "PokeCon実機機能を開けません。\n" + str(error),
                parent=self)

    def _handle_run_line(self, line):
        if not line.startswith(EVENT_PREFIX):
            self._append_run_output(line)
            return
        try:
            detail = json.loads(line[len(EVENT_PREFIX):])
        except (ValueError, TypeError):
            self._append_run_output(line)
            return
        event = detail.get("event")
        if event == "paused":
            line_number = int(detail.get("line", 1))
            reason = {"cursor": "カーソル位置", "operation": "操作コード直前",
                      "step": "1行実行"}.get(detail.get("reason"), detail.get("reason"))
            self.run_status.set("{} で一時停止 (行 {})".format(reason, line_number))
            if not self.run_selection_mode:
                self.editor.tag_remove("paused_line", "1.0", "end")
                self.editor.tag_add(
                    "paused_line", "{}.0".format(line_number),
                    "{}.0 lineend".format(line_number))
                self.editor.see("{}.0".format(line_number))
            self._append_run_output("[PokeConStudio] {} / 行 {} で一時停止\n".format(
                reason, line_number))
        elif event == "started":
            self.run_status.set("実行中")
        elif event == "resumed":
            self.run_status.set("再開しました。")
            self.editor.tag_remove("paused_line", "1.0", "end")
        elif event == "error":
            self.run_status.set("実行エラー: " + str(detail.get("error", "")))
        elif event in ("finished", "stopped"):
            self.run_status.set("終了" if event == "finished" else "停止しました。")

    def _append_run_output(self, text):
        self.run_output.configure(state="normal")
        self.run_output.insert("end", text)
        self._run_display_chars += len(text)
        if self._run_display_chars > 250000:
            self.run_output.delete("1.0", "end-150000c")
            self._run_display_chars = 150000
        self.run_output.see("end")
        self.run_output.configure(state="disabled")

    def _set_run_output(self, text):
        self.run_output.configure(state="normal")
        self.run_output.delete("1.0", "end")
        self.run_output.insert("1.0", text)
        self._run_display_chars = len(text)
        self.run_output.configure(state="disabled")

    def _cleanup_run_snapshot(self, path=None):
        if path is None:
            path = self.run_snapshot
        if path and os.path.normcase(path) == os.path.normcase(
                self.run_snapshot or ""):
            self.run_snapshot = ""
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def _drain_events(self):
        # ``after`` belongs to the shared Tcl interpreter rather than to this
        # Toplevel's lifetime.  Without an explicit guard, closing an
        # integrated Studio window can leave this callback running against
        # destroyed widgets in the parent PokeCon process.
        self._event_drain_after = None
        if self._closing:
            return
        detection_changed = False
        processed = 0
        deadline = time.monotonic() + 0.02
        try:
            while processed < 250 and time.monotonic() < deadline:
                item = self._event_queue.get_nowait()
                processed += 1
                kind = item[0]
                if kind == "scan_done":
                    _kind, generation, rows = item
                    if generation == self._scan_generation:
                        self.catalog = rows
                        self.catalog_by_id = {row["id"]: row for row in rows}
                        self.detection_start_button.configure(state="normal")
                        self.refresh_detection_tree()
                elif kind == "scan_error":
                    _kind, generation, message = item
                    if generation == self._scan_generation:
                        self.detection_start_button.configure(state="normal")
                        self.detection_status.set("初期化エラー: " + message)
                elif kind == "detection":
                    _kind, generation, iid, detail = item
                    if generation != self._detection_generation:
                        continue
                    row = self.catalog_by_id.get(iid)
                    if row is not None:
                        row["score"] = detail.get("score")
                        row["matched"] = bool(detail.get("matched"))
                        row["position"] = detail.get("position")
                        row.pop("last_error", None)
                        detection_changed = True
                elif kind == "detection_error":
                    _kind, generation, iid, message = item
                    if generation != self._detection_generation:
                        continue
                    row = self.catalog_by_id.get(iid)
                    if row is not None:
                        row["score"] = None
                        row["matched"] = False
                        row.pop("position", None)
                        row["last_error"] = message
                        detection_changed = True
                elif kind == "detection_state":
                    _kind, generation, message = item
                    if generation == self._detection_generation:
                        self.detection_status.set(message)
                elif kind == "detection_stopped":
                    (_kind, generation, worker, stop_event,
                     requested) = item
                    is_current_worker = (
                        worker is self._detection_thread and
                        stop_event is self._detection_stop)
                    if is_current_worker:
                        self._detection_thread = None
                        self._detection_stop = None
                        self._detection_pause = None
                    if requested and is_current_worker:
                        with self._scan_lock:
                            scan_busy = bool(
                                self._scan_thread is not None or
                                self._scan_request is not None)
                        if not scan_busy:
                            self.detection_status.set("画像検知を終了しました。")
                elif kind == "run_line":
                    _kind, generation, line, length = item
                    self._release_run_line_budget(length)
                    if generation == self._run_generation:
                        self._handle_run_line(line)
                elif kind == "run_output_dropped":
                    _kind, generation = item
                    with self._run_pending_lock:
                        dropped = self._run_dropped_lines
                        self._run_dropped_lines = 0
                        self._run_drop_notice_queued = False
                    if generation == self._run_generation and dropped:
                        self._append_run_output(
                            "[PokeConStudio] 出力が上限を超えたため、{}行を省略しました。\n".format(
                                dropped))
                elif kind == "run_eof":
                    (_kind, generation, process, snapshot,
                     return_code) = item
                    self._cleanup_run_snapshot(snapshot)
                    if (generation == self._run_generation and
                            process is self.run_process):
                        self.run_status.set(
                            "終了 (exit={})".format(return_code))
                        self.run_process = None
                        self.editor.tag_remove(
                            "paused_line", "1.0", "end")
        except queue.Empty:
            pass
        if detection_changed:
            self._schedule_detection_tree_refresh()
        if self._closing:
            return
        try:
            delay = 10 if not self._event_queue.empty() else 75
            self._event_drain_after = self.after(
                delay, self._drain_events)
        except tk.TclError:
            self._event_drain_after = None

    def close(self):
        comparison = self.recording_comparison_window
        if comparison is not None:
            try:
                if comparison.winfo_exists():
                    comparison.close()
                    if comparison.winfo_exists():
                        return False
            except tk.TclError:
                pass
            self.recording_comparison_window = None
            self._comparison_profile_name = ""
        if self.editor_dirty:
            answer = messagebox.askyesnocancel(
                "PokeConStudio", "終了前に現在のソースを保存しますか？",
                parent=self)
            if answer is None:
                return False
            if answer and not self.save_source():
                return False
        if not self.save_profile_state():
            if not messagebox.askyesno(
                    "PokeConStudio - 設定未保存",
                    "設定を保存できませんでした。\n"
                    "設定変更は失われますが、それでも終了しますか？",
                    parent=self):
                return False
        with self._scan_lock:
            if self._scan_cancel is not None:
                self._scan_cancel.set()
            self._scan_request = None
        self.stop_detection()
        if self._detection_tree_refresh_after is not None:
            try:
                self.after_cancel(self._detection_tree_refresh_after)
            except tk.TclError:
                pass
            self._detection_tree_refresh_after = None
        # Do not leave StudioRunner alive when this Toplevel or the owning
        # PokeCon process closes.  Its temporary source snapshot can otherwise
        # remain behind and the child can continue executing user code.
        if not self.stop_run(wait=True):
            messagebox.showerror(
                "PokeConStudio",
                "実行中のPythonを停止できないため、終了を中止しました。",
                parent=self)
            return False
        self._closing = True
        if self._event_drain_after is not None:
            try:
                self.after_cancel(self._event_drain_after)
            except tk.TclError:
                pass
            self._event_drain_after = None
        self.destroy()
        if self.close_root:
            try:
                self.master.destroy()
            except tk.TclError:
                pass
        return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="PokeCon operation assistant")
    parser.add_argument(
        "project_root", nargs="?",
        default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser.add_argument("--profile-store", default="")
    parser.add_argument("--source", default="")
    args = parser.parse_args(argv)
    root = tk.Tk()
    root.withdraw()
    app = PokeConStudioWindow(
        root, args.project_root,
        profile_store_path=args.profile_store or None,
        initial_source=args.source, close_root=True)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
