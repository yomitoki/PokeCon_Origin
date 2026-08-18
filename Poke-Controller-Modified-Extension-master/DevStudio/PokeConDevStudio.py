#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small dependency-free code browser for extending PokeCon.

Tag reusable code immediately above a function/class, for example:
    # @pokedev: audio, recording
    def my_helper(...):

or mark an arbitrary block with ``@pokedev-begin`` / ``@pokedev-end``.
"""
from __future__ import print_function

import ast
import hashlib
import io
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import textwrap
import tokenize
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from PIL import Image as PILImage, ImageTk as PILImageTk
except ImportError:
    PILImage = PILImageTk = None

from CommandBuilder import command_path, folder_segment, python_identifier, template_source
from SampleLibrary import (catalog, compose_preview, detect_conflicts, load_fragment,
                           load_library, merge_preview, resolve_members, save_library)
from SampleOriginSync import (apply_sample_list_to_origins,
                              compare_sample_list_origins,
                              restore_origin_sync_backup)
from SampleProgramLoader import inspect_sample_program
from SampleFunctionSync import compare_folder as compare_sample_function_folder
from SampleFunctionSync import update_fragments as update_sample_function_fragments
from SampleFunctionSync import update_source as update_source_sample_functions
from SampleFunctionSync import propagate_functions as propagate_sample_functions
from SampleFunctionSync import replace_class_functions
from SampleFunctionSync import function_records as sample_sync_function_records
from SampleFunctionSync import source_paths_for_folder as sample_sync_source_paths
from SampleFunctionSync import comparison_source_text
from SampleFunctionSync import save_reflected_source
from SampleFunctionSync import merge_sample_names_with_source_bodies
from SampleFunctionSync import mark_comparisons_synchronized
from SampleFunctionSync import side_by_side_diff_rows
from SampleFunctionSync import replace_fragment_function_text
from SampleFunctionSync import reflect_fragment_function_text
from SampleFunctionSync import remove_fragment_function_text
from SampleFunctionSync import fragment_function_stats
from SampleFunctionSync import resolve_fragment_folder
from SampleFunctionSync import (create_sample_sync_backup,
                                latest_sample_sync_backup,
                                restore_sample_sync_backup)
from ImageDetectionLibrary import (folder_tags as image_folder_tags,
                                   filter_image_library_variants,
                                   generate_image_check,
                                   image_preview_size,
                                   load_library as load_image_library,
                                   rename_target as rename_image_library_target,
                                   resolve_list as resolve_image_list,
                                   save_library as save_image_library)
from ImageDetectionSync import (compare_settings as compare_image_detection_settings,
                                parse_source_settings as parse_source_image_detection_settings,
                                update_library_from_source)
from ImageHealthCheck import audit_image_library, suggested_crop
from ImageCheckReferenceAudit import (audit_image_check_references,
                                      delete_image_check_exception,
                                      image_check_exception_rules,
                                      merge_library_targets_into_source,
                                      preserve_library_import_block,
                                      rename_image_check_references,
                                      upsert_image_check_exception)
from CompletionEngine import CompletionEngine
from SourceFunctionTools import (build_rename_map,
                                 classify_function_registration,
                                 register_source_functions,
                                 rename_source_functions, source_function_records,
                                 step_function_names)
from SourceDependencyTools import (analyze_source_dependencies,
                                   analyze_state_dictionary_dependencies,
                                   catalog_function_candidates,
                                   compare_preview_functions,
                                   compare_preview_support,
                                   generate_state_machine_main,
                                   merge_preview_functions_safely,
                                   merge_preview_support_safely,
                                   register_dependency_group,
                                   state_dictionary_current_state,
                                   state_dictionary_names,
                                   suggest_state_dictionary)
from OperationSessionStudio import OperationSessionWorkspace
from CommandRecordingStudio import CommandRecordingWorkspace
from PythonSourceSafety import (normalize_and_compile_python,
                                normalize_python_indentation)


PYTHON_SUFFIXES = (".py", ".pyfrag")
TAG_RE = re.compile(r"@pokedev\s*:\s*(.+)", re.IGNORECASE)
BEGIN_RE = re.compile(r"@pokedev-begin\s*:\s*(.+)", re.IGNORECASE)
END_RE = re.compile(r"@pokedev-end", re.IGNORECASE)
TODO_HELP_MARKER = "# TODO紐づけの記載例"
TODO_SIMPLE_FUNCTION_HELP = "# 関数名だけで紐づけ: - [ ] [_1_story_out_hotel_z_18] 修正内容\n"
TODO_PLAIN_FUNCTION_HELP = "# 本文中の関数名でも移動: 1_STORY_OUT_HOTEL_Z_72 ログ出力を追加\n"
TODO_HELP_TEXT = (
    TODO_HELP_MARKER + "（項目をダブルクリックすると移動）\n"
    "# 行番号に紐づけ: - [ ] [L123] 修正内容\n"
    "# 関数に紐づけ: - [ ] [F:ClassName.function_name+0] [L123] 修正内容\n"
    + TODO_SIMPLE_FUNCTION_HELP
    + TODO_PLAIN_FUNCTION_HELP
    + "# ※［＋現在の関数へ紐づけ］を使うと自動で記載されます。\n\n"
)


def find_match_index(matches, current_index="", cursor_index="1.0"):
    """Choose a visible 1-based-search result without leaving it at 0 / N."""
    if not matches:
        return -1

    starts = [str(item[0]) for item in matches]
    current_index = str(current_index or "")
    if current_index in starts:
        return starts.index(current_index)

    def index_key(value):
        line, column = str(value).split(".", 1)
        return int(line), int(column)

    cursor_key = index_key(cursor_index)
    for index, start in enumerate(starts):
        if index_key(start) >= cursor_key:
            return index
    return 0


def pack_scrollable_widget(widget, horizontal=False):
    """Pack a list/text/tree with visible scrollbars and local wheel input."""
    parent = widget.master
    vertical = ttk.Scrollbar(parent, orient="vertical", command=widget.yview)
    vertical.pack(side="right", fill="y")
    horizontal_bar = None
    options = {"yscrollcommand": vertical.set}
    if horizontal:
        horizontal_bar = ttk.Scrollbar(
            parent, orient="horizontal", command=widget.xview)
        horizontal_bar.pack(side="bottom", fill="x")
        options["xscrollcommand"] = horizontal_bar.set
    widget.configure(**options)
    widget.pack(side="left", fill="both", expand=True)

    def wheel(event):
        delta = int(getattr(event, "delta", 0) or 0)
        if not delta:
            return None
        units = -1 if delta > 0 else 1
        if horizontal and (int(getattr(event, "state", 0) or 0) & 0x0001):
            widget.xview_scroll(units, "units")
        else:
            widget.yview_scroll(units, "units")
        return "break"

    widget.bind("<MouseWheel>", wheel, add="+")
    return vertical, horizontal_bar


def _literal_string(node):
    """Return a string AST literal across Python 3.7 through 3.14."""
    constant_type = getattr(ast, "Constant", ())
    if isinstance(node, constant_type) and isinstance(getattr(node, "value", None), str):
        return node.value
    legacy_type = getattr(ast, "Str", ())
    if isinstance(node, legacy_type) and isinstance(getattr(node, "s", None), str):
        return node.s
    return None


class Fragment(object):
    def __init__(self, path, start, end, tags, kind, name, source):
        self.path, self.start, self.end = path, start, end
        self.tags, self.kind, self.name, self.source = tags, kind, name, source

    @property
    def label(self):
        return "{}  {}:{}  [{}]".format(
            self.kind, self.name, self.start, ", ".join(self.tags) or "untagged")


class TagPicker(ttk.Frame):
    """Searchable tag picker that also accepts a new tag from the search box."""
    def __init__(self, parent, choices_provider, initial=None,
                 defer_choices=False):
        ttk.Frame.__init__(self, parent)
        self.choices_provider = choices_provider
        self.search = tk.StringVar()
        self.choice = tk.StringVar()
        self.search.trace_add("write", self._filter_choices)
        ttk.Label(self, text="タグ検索:").grid(column=0, row=0, padx=(0, 4), sticky="w")
        ttk.Entry(self, textvariable=self.search, width=18).grid(column=1, row=0, padx=2, sticky="ew")
        self.combo = ttk.Combobox(self, textvariable=self.choice, state="readonly", width=22)
        self.combo.grid(column=2, row=0, padx=2, sticky="ew")
        ttk.Button(self, text="＋ 追加（新規可）", command=self.add_selected).grid(column=3, row=0, padx=2)
        ttk.Button(self, text="－ 削除", command=self.remove_selected).grid(column=3, row=1, padx=2, sticky="n")
        list_frame = ttk.Frame(self)
        list_frame.grid(column=0, columnspan=3, row=1, pady=(4, 0), sticky="nsew")
        self.listbox = tk.Listbox(list_frame, height=4, exportselection=False)
        pack_scrollable_widget(self.listbox, horizontal=True)
        self.columnconfigure(1, weight=1); self.columnconfigure(2, weight=1)
        self.rowconfigure(1, weight=1)
        self.set_tags(initial or [], refresh_choices=not defer_choices)

    def _available_tags(self):
        return sorted(set(str(value).strip() for value in self.choices_provider() if str(value).strip()), key=str.lower)

    def _filter_choices(self, *args):
        needle = self.search.get().strip().lower()
        values = [tag for tag in self._available_tags() if not needle or needle in tag.lower()]
        self.combo.configure(values=values)
        if self.choice.get() not in values:
            self.choice.set(values[0] if values else "")

    def refresh_choices(self):
        self._filter_choices()

    def add_selected(self):
        # Prefer an explicitly selected existing tag.  When the search has no
        # exact match, treat the entered search text as a new tag.  This keeps
        # the existing-tag pull-down workflow while allowing the first sample
        # that introduces a tag to register it.
        selected = self.choice.get().strip()
        entered = self.search.get().strip()
        available = self._available_tags()
        exact = next((tag for tag in available if tag.lower() == entered.lower()), "")
        tag = exact or selected or entered
        current_lower = [value.lower() for value in self.get_tags()]
        if tag and tag.lower() not in current_lower:
            self.listbox.insert("end", tag)
        if tag:
            self.search.set("")

    def remove_selected(self):
        selected = list(self.listbox.curselection())
        for index in reversed(selected):
            self.listbox.delete(index)

    def get_tags(self):
        return list(self.listbox.get(0, "end"))

    def set_tags(self, tags, refresh_choices=True):
        self.listbox.delete(0, "end")
        for tag in tags:
            value = str(tag).strip()
            if value and value not in self.get_tags():
                self.listbox.insert("end", value)
        if refresh_choices:
            self.refresh_choices()


class DevStudio(tk.Tk):
    def __init__(self, initial_root, operation_session="", command_recording=""):
        tk.Tk.__init__(self)
        self.code_font = tkfont.Font(self, family="Consolas", size=10)
        self.code_tabs = (self.code_font.measure("    "),)
        self.title("PokeCon Dev Studio")
        self.geometry("1280x780")
        self.minsize(900, 560)
        self.root_dir = tk.StringVar(value=os.path.abspath(initial_root))
        self.search_text = tk.StringVar()
        self.tag_text = tk.StringVar()
        self.files = []
        self.fragments = []
        self.index_errors = []
        self._fragment_catalog_cache = None
        self._source_function_catalog_candidates = None
        self.editing_fragment_id = None
        self._fragment_loaded_body = ""
        self.search_hits = []
        self.current_path = None
        self.editor_dirty = False
        self.editor_documents = {}
        self.active_editor_tab = None
        self._switching_editor_tab = False
        self.ui_state = self.load_ui_state()
        self.completion_mode = tk.StringVar(value=self.ui_state.get("completion_mode", "右タブ"))
        self.completion_query = tk.StringVar(value=self.ui_state.get("completion_query", ""))
        self.completion_tag = tk.StringVar(value=self.ui_state.get("completion_tag", ""))
        self.completion_engine = CompletionEngine(lambda: self.root_dir.get())
        self.completion_candidates = []
        self.completion_analysis = None
        self.completion_popup = None
        self.completion_popup_list = None
        self.background_queue = queue.Queue()
        self.background_tasks = set()
        self.background_cursor_tasks = set()
        self.find_text = tk.StringVar()
        self.find_result_text = tk.StringVar(value="0 / 0")
        self.find_target_text = tk.StringVar(value="対象: ソース編集")
        self._find_editors = {}
        self._find_target_editor = None
        self.replace_text = tk.StringVar()
        self.ui_language = tk.StringVar(value="日本語")
        self.initial_operation_session = os.path.abspath(operation_session) \
            if operation_session else ""
        self.initial_command_recording = os.path.abspath(command_recording) \
            if command_recording else ""
        self._build()
        self._build_menu()
        self.apply_language()
        # Dev Studio is normally launched from a maximized PokeCon window.
        # Present it explicitly after construction so the detached GUI does
        # not appear to have failed while it is actually hidden behind PokeCon.
        self.after_idle(self.present_window)
        self.after_idle(self.set_default_pane_sizes)
        self.after(100, self.restore_ui_state)
        self.after(50, self._drain_background_tasks)
        self.protocol("WM_DELETE_WINDOW", self.close_dev_studio)
        self.refresh_index()
        self.refresh_local_explorer()
        self.refresh_sample_apply_lists(include_images=False)
        # Populate the controls at startup, but do not compose a potentially
        # very large sample program until its workspace is opened.
        self.refresh_sample_lists_tab(
            render_preview=False, refresh_catalog=False)
        # Fill the registered-sample pull-down after Tk has painted the first
        # frame.  Always schedule this even when the sample workspace is not
        # selected yet, otherwise its combo can remain blank indefinitely.
        self.registered_fragment_choice.set("（サンプル関数を読み込み中…）")
        self.registered_fragment_combo.configure(
            values=("（サンプル関数を読み込み中…）",))
        self.after(200, self.refresh_fragment_catalog_background)

    def run_background(self, key, label, worker, on_success, on_error=None,
                       busy_cursor=True):
        """Run non-Tk work without blocking the UI and marshal completion safely."""
        if key in self.background_tasks:
            self.status.set(label + "（処理中です）")
            return False
        self.background_tasks.add(key)
        self.status.set(label + "...")
        if busy_cursor:
            self.background_cursor_tasks.add(key)
            self.configure(cursor="watch")

        def run():
            try:
                self.background_queue.put((key, label, True, worker(), on_success, on_error))
            except Exception as error:
                self.background_queue.put((key, label, False, error, on_success, on_error))
        threading.Thread(target=run, daemon=True).start()
        return True

    def _drain_background_tasks(self):
        try:
            while True:
                key, label, succeeded, value, on_success, on_error = self.background_queue.get_nowait()
                self.background_tasks.discard(key)
                self.background_cursor_tasks.discard(key)
                if not self.background_cursor_tasks:
                    self.configure(cursor="")
                try:
                    if succeeded:
                        on_success(value)
                    elif on_error is not None:
                        on_error(value)
                    else:
                        messagebox.showerror("Dev Studio", "{}に失敗しました。\n{}".format(label, value), parent=self)
                except Exception as callback_error:
                    messagebox.showerror("Dev Studio", "{}の画面更新に失敗しました。\n{}".format(label, callback_error), parent=self)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(50, self._drain_background_tasks)

    def debounce(self, key, delay_ms, callback):
        jobs = getattr(self, "_debounce_jobs", None)
        if jobs is None:
            jobs = self._debounce_jobs = {}
        job = jobs.pop(key, None)
        if job is not None:
            try: self.after_cancel(job)
            except tk.TclError: pass
        def run():
            jobs.pop(key, None); callback()
        jobs[key] = self.after(delay_ms, run)

    def _build_menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Save", command=self.save_current, accelerator="Ctrl+S")
        file_menu.add_command(label="Save as...", command=self.save_output)
        file_menu.add_separator()
        file_menu.add_command(label="Open code folder...", command=self.choose_root)
        file_menu.add_command(label="Refresh index", command=self.refresh_index, accelerator="F5")
        menu.add_cascade(label="File", menu=file_menu)
        command_menu = tk.Menu(menu, tearoff=False)
        command_menu.add_command(label="New PokeCon Python Command...", command=self.open_command_builder)
        command_menu.add_command(label="Open generated commands folder", command=self.open_commands_folder)
        menu.add_cascade(label="Commands", menu=command_menu)
        language_menu = tk.Menu(menu, tearoff=False)
        language_menu.add_radiobutton(label="日本語", variable=self.ui_language, value="日本語", command=self.apply_language)
        language_menu.add_radiobutton(label="English", variable=self.ui_language, value="English", command=self.apply_language)
        menu.add_cascade(label="Language / 言語", menu=language_menu)
        self.config(menu=menu)
        self.bind_all("<Control-n>", lambda event: (self.new_file(), "break"))

    def apply_language(self):
        """Translate Dev Studio chrome only; user code and sample contents stay unchanged."""
        ja = {
            "Code folder:": "コードフォルダ:", "Browse": "参照", "Refresh index": "索引更新",
            "Text search:": "全文検索:", "Search all files": "全ファイル検索", "Find tagged code": "タグ検索",
            "Find reusable functions": "再利用関数検索", "Go to line": "行へ移動", "Check syntax": "構文確認",
            "Run  F5": "実行 F5", "Stop": "停止", "Next": "次へ", "Replace": "置換", "All": "すべて",
            "Hide right": "右を隠す", "Show right": "右を表示", "Hide": "隠す", "Show left": "左を表示",
            "Explorer": "エクスプローラー", "Search / Tags": "検索 / タグ", "Apply sample list": "サンプルリスト反映",
            "Image detection": "画像検知", "Step hierarchy": "Step階層", "Sample functions": "サンプル関数", "Sample lists": "サンプルリスト",
            "Save output as...": "名前を付けて保存...", "Clear": "クリア", "Close all": "すべて閉じる",
            "Load current command": "現在のコマンドを読込", "Add chapter": "章を追加", "Add child": "子を追加", "Rename": "名前変更", "Remove": "削除",
            "Apply to current Step command": "現在のStepコマンドへ反映", "New reusable function...": "再利用関数を作成...",
            "Open fragment library": "サンプルライブラリを開く", "Create empty list": "空リストを作成", "Refresh apply lists": "リスト更新",
            "Apply selected": "選択を反映", "Refresh lists": "リスト更新",
            "Registered sample functions:": "登録済みサンプル関数:",
        }
        mapping = ja if self.ui_language.get() == "日本語" else {value: key for key, value in ja.items()}
        def translate(widget):
            try:
                value = widget.cget("text")
                if value in mapping:
                    widget.configure(text=mapping[value])
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                translate(child)
        translate(self)
        if hasattr(self, "workspace_tabs"):
            if self.ui_language.get() == "日本語":
                titles = ((self.source_workspace, "🟦 ソース編集"),
                          (self.operation_workspace, "🟥 操作記録→Commands"),
                          (self.command_recording_workspace, "🟪 動画・ソース比較"),
                          (self.sample_functions_workspace, "🟩 サンプル関数"),
                          (self.sample_lists_workspace, "🟨 サンプルリスト"),
                          (self.sample_program_workspace, "🟦 サンプルプログラム"),
                          (self.image_library_workspace, "画像検知"))
            else:
                titles = ((self.source_workspace, "🟦 Source edit"),
                          (self.operation_workspace, "🟥 Operation → Commands"),
                          (self.command_recording_workspace, "🟪 Video / source compare"),
                          (self.sample_functions_workspace, "🟩 Sample functions"),
                          (self.sample_lists_workspace, "🟨 Sample lists"),
                          (self.sample_program_workspace, "🟦 Sample program"),
                          (self.image_library_workspace, "Image detection"))
            for tab, title in titles:
                self.workspace_tabs.tab(tab, text=title)
        if hasattr(self, "sample_lists_tree"):
            self.refresh_sample_lists_tab(select=self.sample_list_name.get().strip())

    def ui_text(self, english, japanese):
        """Return UI chrome/message text for the currently selected language."""
        return japanese if self.ui_language.get() == "日本語" else english

    def set_default_pane_sizes(self):
        """Start with a practical fixed-width image-target pane; users may drag it."""
        try:
            width = max(self.winfo_width(), 900)
            self.body.sashpos(0, min(300, max(210, width // 4)))
            self.body.sashpos(1, max(500, width - 310))
        except tk.TclError:
            pass

    def present_window(self):
        """Make an explicitly launched Dev Studio visible above its caller."""
        try:
            self.deiconify()
            self.lift()
            # A short topmost pulse is reliable even when the detached child
            # finishes building after Windows' foreground grace period.
            self.attributes("-topmost", True)
            self.focus_force()
            self.after(150, lambda: self.attributes("-topmost", False))
        except tk.TclError:
            pass

    def state_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "devstudio_state.json")

    def load_ui_state(self):
        try:
            with open(self.state_path(), "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {}

    def save_ui_state(self):
        self.capture_active_editor_document()
        documents = []
        for tab_id in self.editor_tabs.tabs():
            document = self.editor_documents.get(tab_id)
            if document:
                documents.append(document)
        state = {"left_visible": self.left_panel_visible, "right_visible": self.right_panel_visible,
                 "left_tab": self.left_tabs.index(self.left_tabs.select()), "right_tab": self.right_tabs.index(self.right_tabs.select()),
                 "active_path": self.current_path, "documents": documents,
                 "completion_mode": self.completion_mode.get(),
                 "completion_query": self.completion_query.get(),
                 "completion_tag": self.completion_tag.get()}
        try:
            state["sash0"] = self.body.sashpos(0)
            state["sash1"] = self.body.sashpos(1)
            with open(self.state_path(), "w", encoding="utf-8", newline="\n") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2)
        except (OSError, tk.TclError):
            pass

    def restore_ui_state(self):
        state = self.ui_state
        try:
            if "sash0" in state:
                self.body.sashpos(0, int(state["sash0"]))
            if "sash1" in state:
                self.body.sashpos(1, int(state["sash1"]))
            for document in state.get("documents", []):
                if document.get("path") and os.path.isfile(document["path"]):
                    content = document.get("content", "")
                    # A clean tab is only a restorable view, not an unsaved
                    # edit.  Reload it from disk so external fixes made while
                    # Dev Studio was closed are not replaced by a stale copy.
                    if not document.get("dirty", False):
                        try:
                            with open(document["path"], "r", encoding="utf-8") as handle:
                                content = handle.read()
                        except (OSError, UnicodeDecodeError):
                            pass
                    self.add_editor_document(content, document["path"])
            if state.get("left_tab") is not None:
                self.left_tabs.select(int(state["left_tab"]))
            else:
                self.left_tabs.select(1)  # LocalExplorer on a first launch
            if state.get("right_tab") is not None:
                self.right_tabs.select(int(state["right_tab"]))
            if not state.get("left_visible", True):
                self.toggle_left_panel()
            if not state.get("right_visible", True):
                self.toggle_right_panel()
        except (ValueError, tk.TclError):
            pass

    def close_dev_studio(self):
        self.save_current_todo(silent=True)
        self.save_ui_state()
        self.destroy()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=7, pady=6)
        ttk.Label(top, text="Code folder:").pack(side="left")
        ttk.Entry(top, textvariable=self.root_dir).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(top, text="Browse", command=self.choose_root).pack(side="left")
        ttk.Button(top, text="Refresh index", command=self.refresh_index).pack(side="left", padx=(4, 0))

        tools = ttk.Frame(self)
        tools.pack(fill="x", padx=7, pady=(0, 5))
        ttk.Label(tools, text="Text search:").pack(side="left")
        search = ttk.Entry(tools, textvariable=self.search_text, width=35)
        search.pack(side="left", padx=4)
        search.bind("<Return>", lambda event: self.search_all())
        ttk.Button(tools, text="Search all files", command=self.search_all).pack(side="left")
        ttk.Label(tools, text="  Tags:").pack(side="left")
        tag = ttk.Entry(tools, textvariable=self.tag_text, width=22)
        tag.pack(side="left", padx=4)
        tag.bind("<Return>", lambda event: self.filter_tags())
        ttk.Button(tools, text="Find tagged code", command=self.filter_tags).pack(side="left")
        ttk.Button(tools, text="Find reusable functions", command=self.find_reusable).pack(side="left", padx=(4, 0))

        edit_tools = ttk.Frame(self)
        edit_tools.pack(fill="x", padx=7, pady=(0, 5))
        ttk.Button(edit_tools, text="Go to line", command=self.go_to_line).pack(side="left", padx=(8, 3))
        ttk.Button(edit_tools, text="構文チェック  F5", command=self.check_syntax).pack(side="left")
        ttk.Label(edit_tools, text="   Find:").pack(side="left")
        self.find_entry = ttk.Entry(
            edit_tools, textvariable=self.find_text, width=16)
        self.find_entry.pack(side="left", padx=2)
        self.find_entry.bind("<Return>", lambda event: self.find_next())
        self.find_text.trace_add("write", lambda *args: self.debounce(
            "editor_find_count", 120, self.refresh_find_count))
        ttk.Button(edit_tools, text="前へ", command=self.find_previous).pack(side="left")
        ttk.Button(edit_tools, text="次へ", command=self.find_next).pack(side="left", padx=(2, 0))
        ttk.Label(edit_tools, textvariable=self.find_result_text, width=9, anchor="center").pack(side="left", padx=(3, 0))
        ttk.Label(edit_tools, textvariable=self.find_target_text,
                  width=22, anchor="w").pack(side="left", padx=(3, 0))
        ttk.Entry(edit_tools, textvariable=self.replace_text, width=16).pack(side="left", padx=(7, 2))
        ttk.Button(edit_tools, text="Replace", command=self.replace_one).pack(side="left")
        ttk.Button(edit_tools, text="All", command=self.replace_all).pack(side="left", padx=2)
        ttk.Label(edit_tools, text="  補完:").pack(side="left")
        completion_mode = ttk.Combobox(
            edit_tools, state="readonly", width=10, textvariable=self.completion_mode,
            values=("エディタ内", "右タブ", "無効"))
        completion_mode.pack(side="left", padx=2)
        completion_mode.bind("<<ComboboxSelected>>", self.on_completion_mode_changed)
        self.right_panel_button = ttk.Button(edit_tools, text="Hide right", command=self.toggle_right_panel)
        self.right_panel_button.pack(side="right")
        self.workspace_tabs = ttk.Notebook(self)
        # Keep the global toolbars pinned above the expanding workspace. Using
        # before=top placed the workspace first, so it consumed the available
        # height and pushed these controls below the visible window.
        self.workspace_tabs.pack(fill="both", expand=True, padx=7, pady=(0, 7))
        source_workspace = ttk.Frame(self.workspace_tabs)
        operation_workspace = ttk.Frame(self.workspace_tabs)
        command_recording_workspace = ttk.Frame(self.workspace_tabs)
        sample_functions_workspace = ttk.Frame(self.workspace_tabs)
        sample_lists_workspace = ttk.Frame(self.workspace_tabs)
        sample_program_workspace = ttk.Frame(self.workspace_tabs)
        image_library_workspace = ttk.Frame(self.workspace_tabs)
        self.source_workspace = source_workspace
        self.operation_workspace = operation_workspace
        self.command_recording_workspace = command_recording_workspace
        self.sample_functions_workspace = sample_functions_workspace
        self.sample_lists_workspace = sample_lists_workspace
        self.sample_program_workspace = sample_program_workspace
        self.image_library_workspace = image_library_workspace
        self.workspace_tabs.add(source_workspace, text="🟦 ソース編集")
        self.workspace_tabs.add(operation_workspace, text="🟥 操作記録→Commands")
        self.workspace_tabs.add(command_recording_workspace, text="🟪 動画・ソース比較")
        self.workspace_tabs.add(sample_functions_workspace, text="🟩 サンプル関数")
        self.workspace_tabs.add(sample_lists_workspace, text="🟨 サンプルリスト")
        self.workspace_tabs.add(sample_program_workspace, text="🟦 サンプルプログラム")
        self.workspace_tabs.tab(source_workspace, padding=(10, 4))
        self.workspace_tabs.tab(operation_workspace, padding=(10, 4))
        self.workspace_tabs.tab(command_recording_workspace, padding=(10, 4))
        self.workspace_tabs.tab(sample_functions_workspace, padding=(10, 4))
        self.workspace_tabs.tab(sample_lists_workspace, padding=(10, 4))
        self.workspace_tabs.tab(sample_program_workspace, padding=(10, 4))
        self.workspace_tabs.add(image_library_workspace, text="画像検知")
        self.workspace_tabs.tab(image_library_workspace, padding=(10, 4))
        style = ttk.Style(self)
        style.configure("Workspace.TNotebook.Tab", padding=(12, 5))
        self.workspace_tabs.configure(style="Workspace.TNotebook")
        self.left_reveal_bar = ttk.Frame(source_workspace)
        self.show_left_button = ttk.Button(self.left_reveal_bar, text="Show left", command=self.toggle_left_panel)
        self.show_left_button.pack(side="left")
        body = ttk.Panedwindow(source_workspace, orient="horizontal")
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        center = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(center, weight=4)
        body.add(right, weight=1)
        self.body = body
        self.center_panel = center
        self.left_panel, self.right_panel = left, right
        self.left_panel_visible = True
        self.right_panel_visible = True

        left_tab_bar = ttk.Frame(left)
        left_tab_bar.pack(fill="x")
        self.left_panel_button = ttk.Button(left_tab_bar, text="Hide", command=self.toggle_left_panel, width=7)
        self.left_panel_button.pack(side="right", padx=(0, 2), pady=(0, 2))
        self.left_tabs = ttk.Notebook(left)
        self.left_tabs.pack(fill="both", expand=True)
        explorer_tab = ttk.Frame(self.left_tabs)
        local_explorer_tab = ttk.Frame(self.left_tabs)
        sample_apply_tab = ttk.Frame(self.left_tabs)
        search_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(explorer_tab, text="Explorer")
        self.left_tabs.add(local_explorer_tab, text="LocalExplorer")
        self.left_tabs.add(sample_apply_tab, text="Apply sample list")
        self.left_tabs.add(search_tab, text="Search / Tags")
        self.sample_apply_tab = sample_apply_tab
        self._sample_apply_images_loaded = False
        self.left_tabs.bind(
            "<<NotebookTabChanged>>", self._left_workspace_tab_changed,
            add="+")
        self.search_tab = search_tab

        ttk.Label(explorer_tab, text="Python files").pack(anchor="w")
        explorer_tree_frame = ttk.Frame(explorer_tab)
        explorer_tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(explorer_tree_frame, show="tree")
        pack_scrollable_widget(self.tree, horizontal=True)
        self.tree.bind("<<TreeviewSelect>>", self.open_tree_file)

        ttk.Label(local_explorer_tab, text="Local commands: SerialController/Commands/PythonCommands").pack(anchor="w")
        local_tree_frame = ttk.Frame(local_explorer_tab)
        local_tree_frame.pack(fill="both", expand=True)
        self.local_tree = ttk.Treeview(local_tree_frame, show="tree")
        pack_scrollable_widget(self.local_tree, horizontal=True)
        self.local_tree.bind("<<TreeviewSelect>>", self.open_local_tree_file)

        sample_apply_pane = ttk.Panedwindow(sample_apply_tab, orient="vertical")
        sample_apply_pane.pack(fill="both", expand=True)
        function_apply = ttk.Labelframe(sample_apply_pane, text="サンプル関数リスト")
        image_apply = ttk.Labelframe(sample_apply_pane, text="画像検知設定")
        sample_apply_pane.add(function_apply, weight=2); sample_apply_pane.add(image_apply, weight=3)
        function_list_frame = ttk.Frame(function_apply)
        function_list_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.sample_apply_list = tk.Listbox(
            function_list_frame, exportselection=False)
        pack_scrollable_widget(self.sample_apply_list, horizontal=True)
        function_buttons = ttk.Frame(function_apply); function_buttons.pack(fill="x")
        ttk.Button(function_buttons, text="リスト更新", command=self.refresh_sample_apply_lists).pack(side="left", padx=4, pady=4)
        ttk.Button(function_buttons, text="選択を反映", command=self.apply_selected_sample_list).pack(side="right", padx=4, pady=4)

        self.sample_apply_image_search = tk.StringVar()
        image_search = ttk.Frame(image_apply); image_search.pack(fill="x", padx=4, pady=3)
        ttk.Label(image_search, text="階層検索:").pack(side="left")
        ttk.Entry(image_search, textvariable=self.sample_apply_image_search).pack(side="left", fill="x", expand=True, padx=3)
        self.sample_apply_image_search.trace_add("write", lambda *args: self.debounce(
            "sample_apply_image_search", 150, self.refresh_sample_apply_image_tree))
        tree_frame = ttk.Frame(image_apply); tree_frame.pack(fill="both", expand=True, padx=4)
        self.sample_apply_image_tree = ttk.Treeview(tree_frame, show="tree", selectmode="extended", height=8)
        pack_scrollable_widget(self.sample_apply_image_tree, horizontal=True)
        image_add_row = ttk.Frame(image_apply); image_add_row.pack(fill="x", padx=4, pady=3)
        ttk.Button(image_add_row, text="＋必要リストへ追加", command=self.add_sample_apply_image_selection).pack(side="left")
        ttk.Button(image_add_row, text="－必要リストから外す", command=self.remove_sample_apply_image_selection).pack(side="left", padx=3)
        selected_image_frame = ttk.Frame(image_apply)
        selected_image_frame.pack(fill="x", padx=4)
        self.sample_apply_image_selected = tk.Listbox(
            selected_image_frame, exportselection=False, height=4)
        pack_scrollable_widget(
            self.sample_apply_image_selected, horizontal=True)
        ttk.Button(image_apply, text="必要な画像検知を編集中ソースへ反映", command=self.apply_sample_apply_images).pack(fill="x", padx=4, pady=4)

        ttk.Label(search_tab, text="Search / tagged / reusable results (Ctrl+click to select multiple)").pack(anchor="w")
        result_frame = ttk.Frame(search_tab)
        result_frame.pack(fill="both", expand=True)
        self.results = tk.Listbox(
            result_frame, selectmode="extended", exportselection=False)
        pack_scrollable_widget(self.results, horizontal=True)
        self.results.bind("<<ListboxSelect>>", self.open_selected_result)
        actions = ttk.Frame(search_tab)
        actions.pack(fill="x", pady=(4, 0))
        ttk.Button(actions, text="Merge selected →", command=self.merge_selected).pack(side="left")
        ttk.Button(actions, text="Open file", command=self.open_selected_file).pack(side="left", padx=4)

        # The source editor is always the centre pane.  The right pane is for
        # auxiliary editing tools and may be hidden without hiding the source.
        self.right_tabs = ttk.Notebook(right)
        self.right_tabs.pack(fill="both", expand=True)
        image_targets_tab = ttk.Frame(self.right_tabs)
        image_health_tab = ttk.Frame(self.right_tabs)
        image_reference_tab = ttk.Frame(self.right_tabs)
        step_hierarchy_tab = ttk.Frame(self.right_tabs)
        completion_tab = ttk.Frame(self.right_tabs)
        source_functions_tab = ttk.Frame(self.right_tabs)
        self.right_tabs.add(image_targets_tab, text="画像検知・例外")
        self.right_tabs.add(image_health_tab, text="画像チェック")
        self.right_tabs.add(step_hierarchy_tab, text="Step hierarchy")
        self.right_tabs.add(completion_tab, text="Completion")
        self.right_tabs.add(source_functions_tab, text="関数登録")
        # Append new tools so saved numeric tab selections from older versions
        # keep pointing at the same existing tool.
        self.right_tabs.add(image_reference_tab, text="検知名チェック")
        self.step_hierarchy_tab = step_hierarchy_tab
        self.completion_tab = completion_tab
        self.source_functions_tab = source_functions_tab
        self.image_health_tab = image_health_tab
        self.image_reference_tab = image_reference_tab
        self.image_targets_tab = image_targets_tab
        self.right_tabs.bind("<<NotebookTabChanged>>", self.on_right_tool_tab_changed)
        source_tab_bar = ttk.Frame(center)
        source_tab_bar.pack(fill="x")
        ttk.Button(source_tab_bar, text="💾", width=3, command=self.save_current).pack(side="left", padx=(0, 4))
        self.editor_title = tk.StringVar(value="Source / merged output")
        ttk.Label(source_tab_bar, textvariable=self.editor_title).pack(side="left")
        ttk.Button(source_tab_bar, text="×", width=3, command=self.close_current_editor_tab).pack(side="right")
        ttk.Button(source_tab_bar, text="Close all", command=self.close_all_editor_tabs).pack(side="right", padx=(0, 4))
        self.editor_tabs = ttk.Notebook(center)
        self.editor_tabs.pack(fill="x")
        self.editor_tabs.bind("<<NotebookTabChanged>>", self.on_editor_tab_changed)
        editor_box = ttk.Frame(center)
        editor_box.pack(fill="both", expand=True)
        self.line_numbers = tk.Text(editor_box, width=5, padx=3, takefocus=0, state="disabled",
                                    wrap="none", background="#f0f0f0", foreground="#666666",
                                    font=self.code_font, tabs=self.code_tabs)
        self.line_numbers.pack(fill="y", side="left")
        self.editor = tk.Text(editor_box, wrap="none", undo=True, background="#1e1e1e", foreground="#d4d4d4",
                              insertbackground="white", selectbackground="#264f78",
                              font=self.code_font, tabs=self.code_tabs)
        editor_scroll = ttk.Scrollbar(editor_box, orient="vertical", command=self._scroll_editor)
        editor_scroll.pack(fill="y", side="right")
        editor_x_scroll = ttk.Scrollbar(
            editor_box, orient="horizontal", command=self.editor.xview)
        editor_x_scroll.pack(fill="x", side="bottom")
        self.editor.pack(fill="both", expand=True, side="left")
        self.editor.configure(
            yscrollcommand=lambda first, last: self._sync_editor_scroll(
                editor_scroll, first, last),
            xscrollcommand=editor_x_scroll.set)
        self.editor.bind("<<Modified>>", self.editor_modified)
        self.editor.bind("<KeyRelease>", self.on_editor_key_release)
        self.editor.bind("<ButtonRelease-1>", lambda event: self.debounce(
            "editor_completion_click", 80,
            self.refresh_completion_if_visible))
        self.editor.bind("<Control-s>", lambda event: (self.save_current(), "break"))
        self.bind_text_undo_redo(self.editor)
        self.editor.bind("<F5>", lambda event: (self.check_syntax(), "break"))
        self.editor.tag_configure("keyword", foreground="#569cd6")
        self.editor.tag_configure("string", foreground="#ce9178")
        self.editor.tag_configure("comment", foreground="#6a9955")
        editor_actions = ttk.Frame(center)
        editor_actions.pack(fill="x", pady=(4, 0))
        ttk.Button(editor_actions, text="Save output as...", command=self.save_output).pack(side="left")
        ttk.Button(editor_actions, text="Clear", command=lambda: self.editor.delete("1.0", "end")).pack(side="left", padx=4)
        ttk.Button(editor_actions, text="カーソル位置の画像検知を開く",
                   command=self.open_image_detection_at_cursor).pack(side="left", padx=4)
        self.vscode_executable = self.find_vscode_executable()
        if self.vscode_executable:
            ttk.Button(editor_actions, text="VS Codeで現在行を開く",
                       command=self.open_current_in_vscode).pack(side="left", padx=4)
        self.editor.bind("<Control-Alt-i>", lambda event: (self.open_image_detection_at_cursor(), "break"))
        self.editor.bind("<Control-space>", self.show_completion_now)
        self.editor.bind("<Escape>", self.completion_escape)
        self.editor.bind("<Down>", self.completion_down)
        self.editor.bind("<Up>", self.completion_up)
        self.editor.bind("<Return>", self.completion_accept_key)
        self.editor.bind("<Tab>", self.completion_accept_key)
        self._register_find_editor(self.editor, "ソース編集")
        todo_frame = ttk.Labelframe(center, text="TODO / 改修予定（ソースファイル別）")
        todo_frame.pack(fill="x", pady=(5, 0))
        todo_top = ttk.Frame(todo_frame); todo_top.pack(fill="x", padx=3, pady=(3, 0))
        self.todo_source_label = tk.StringVar(value="保存済みソースを開くとTODOを記録できます。")
        ttk.Label(todo_top, textvariable=self.todo_source_label).pack(side="left", fill="x", expand=True)
        ttk.Button(todo_top, text="＋項目", command=self.insert_todo_item).pack(side="right", padx=2)
        ttk.Button(todo_top, text="＋現在の関数へ紐づけ", command=self.insert_linked_todo_item).pack(side="right", padx=2)
        ttk.Button(todo_top, text="TODOを保存", command=self.save_current_todo).pack(side="right", padx=2)
        todo_editor_frame = ttk.Frame(todo_frame)
        todo_editor_frame.pack(fill="both", expand=True, padx=3, pady=3)
        self.todo_editor = tk.Text(todo_editor_frame, height=8, wrap="word", undo=True,
                                   background="#171717", foreground="#dddddd", insertbackground="white")
        pack_scrollable_widget(self.todo_editor)
        self.todo_editor.bind("<<Modified>>", self.todo_modified)
        self.todo_editor.bind("<FocusOut>", lambda event: self.save_current_todo(silent=True))
        self.todo_editor.bind("<Double-Button-1>", self.open_todo_source_location)
        self._register_find_editor(self.todo_editor, "ソースTODO")
        self.bind_text_undo_redo(self.todo_editor)
        self._build_image_targets_tab(image_targets_tab)
        self._build_image_health_tab(image_health_tab)
        self._build_image_reference_tab(image_reference_tab)
        self._build_step_hierarchy_tab(step_hierarchy_tab)
        self._build_completion_tab(completion_tab)
        self._build_source_functions_tab(source_functions_tab)
        self._build_sample_functions_tab(sample_functions_workspace)
        self._build_sample_lists_tab(sample_lists_workspace)
        self._build_sample_program_tab(sample_program_workspace)
        self._build_image_library_workspace(image_library_workspace)
        self.operation_session_workspace = OperationSessionWorkspace(
            operation_workspace, initial_session=self.initial_operation_session,
            code_root_provider=lambda: self.root_dir.get(),
            open_image_callback=self.open_operation_image_in_library,
            open_source_callback=self.show_file)
        self.operation_session_workspace.pack(fill="both", expand=True)
        self.command_recording_studio = CommandRecordingWorkspace(
            command_recording_workspace,
            initial_recording=self.initial_command_recording,
            open_image_callback=self.open_operation_image_in_library,
            open_source_callback=self.show_file)
        self.command_recording_studio.pack(fill="both", expand=True)
        for widget, label, replace in (
                (self.operation_session_workspace.intermediate_text,
                 "操作記録: 中間ファイル", True),
                (self.operation_session_workspace.final_text,
                 "操作記録: 反映後プレビュー", False),
                (self.operation_session_workspace.diff_text,
                 "操作記録: 差分", False),
                (self.operation_session_workspace.vision_sample_text,
                 "操作記録: 画像判断サンプル", True),
                (self.operation_session_workspace.intermediate_history_diff_text,
                 "操作記録: 中間コード差分", False),
                (self.command_recording_studio.source_text,
                 "動画・ソース比較: ソース", False)):
            self._register_find_editor(widget, label, replace=replace)
        self.operation_session_workspace.code_tabs.bind(
            "<<NotebookTabChanged>>",
            lambda _event: (
                self._active_find_editor(),
                self.refresh_find_count() if self.find_text.get() else None),
            add="+")
        self.workspace_tabs.bind(
            "<<NotebookTabChanged>>", self._workspace_tab_changed, add="+")
        self.bind("<Control-f>", self.focus_current_tab_find, add="+")
        if self.initial_command_recording:
            self.workspace_tabs.select(command_recording_workspace)
        elif self.initial_operation_session:
            self.workspace_tabs.select(operation_workspace)
        self.add_editor_document("", None)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(source_workspace, textvariable=self.status, anchor="w").pack(fill="x", pady=(0, 5))

    def open_operation_image_in_library(self, path, crop, name):
        """Hand an exact 1280x720 capture to the existing image-detection editor."""
        self.image_library_path.set(os.path.abspath(path))
        self.image_library_name.set(str(name or "OPERATION_CAPTURE").upper())
        self.image_library_description.set("操作記録の映像フレームから作成")
        self.image_library_crop.set(",".join(str(int(value)) for value in crop))
        self.image_library_threshold.set(0.80)
        self.image_library_gray.set(True)
        self.workspace_tabs.select(self.image_library_workspace)
        self._show_image_library_preview(path)
        self.status.set("操作記録の画像と1280x720検知範囲を引き渡しました。設定確認後に保存してください。")

    def _workspace_tab_changed(self, _event=None):
        """Do not decode operation video while another DevStudio tab is used."""
        if (hasattr(self, "operation_session_workspace")
                and self.workspace_tabs.select() != str(self.operation_workspace)):
            self.operation_session_workspace.stop_video()
        if (hasattr(self, "command_recording_studio")
                and self.workspace_tabs.select() != str(self.command_recording_workspace)):
            self.command_recording_studio.stop_video()
        if (hasattr(self, "image_library_workspace") and
                self.workspace_tabs.select() == str(self.image_library_workspace) and
                not getattr(self, "_image_library_workspace_loaded", False)):
            self._image_library_workspace_loaded = True
            self.after_idle(self.refresh_image_library_workspace)
        # Building a large sample-list preview reads and composes every member.
        # Registration may finish while this workspace is hidden, so defer
        # that visual-only work until the user actually opens the tab.
        if (hasattr(self, "sample_lists_workspace")
                and self.workspace_tabs.select() == str(self.sample_lists_workspace)):
            pending = getattr(self, "_sample_lists_refresh_deferred", "")
            if pending:
                self._sample_lists_refresh_deferred = ""
                self.refresh_sample_lists_tab(
                    select=pending,
                    refresh_catalog=self._fragment_catalog_cache is not None)
        sample_workspaces = {
            str(getattr(self, "sample_functions_workspace", "")),
            str(getattr(self, "sample_lists_workspace", "")),
        }
        if (hasattr(self, "_fragment_catalog_cache") and
                self._fragment_catalog_cache is None and
                self.workspace_tabs.select() in sample_workspaces):
            self.refresh_fragment_catalog_background()
        if hasattr(self, "find_target_text"):
            self._active_find_editor()
            if self.find_text.get():
                self.debounce(
                    "editor_find_count", 50, self.refresh_find_count)

    def _left_workspace_tab_changed(self, _event=None):
        if (hasattr(self, "sample_apply_tab") and
                self.left_tabs.select() == str(self.sample_apply_tab) and
                not getattr(self, "_sample_apply_images_loaded", False)):
            self._sample_apply_images_loaded = True
            # Let the selected tab paint before inserting the image tree.
            self.after_idle(self.refresh_sample_apply_image_tree)

    def toggle_left_panel(self):
        if self.left_panel_visible:
            self.body.forget(self.left_panel)
            self.left_panel_visible = False
            self.left_panel_button.configure(text="Show")
            self.left_reveal_bar.pack(fill="x", padx=7, pady=(0, 2), before=self.body)
        else:
            self.body.insert(0, self.left_panel)
            self.left_panel_visible = True
            self.left_panel_button.configure(text="Hide")
            self.left_reveal_bar.pack_forget()

    def toggle_right_panel(self):
        if self.right_panel_visible:
            self.body.forget(self.right_panel)
            self.right_panel_visible = False
            self.right_panel_button.configure(text="Show right")
        else:
            self.body.add(self.right_panel)
            self.right_panel_visible = True
            self.right_panel_button.configure(text="Hide right")

    def _build_completion_tab(self, parent):
        filters = ttk.Frame(parent)
        filters.pack(fill="x", padx=6, pady=6)
        ttk.Label(filters, text="検索:").grid(column=0, row=0, sticky="w")
        query = ttk.Entry(filters, textvariable=self.completion_query)
        query.grid(column=1, row=0, padx=3, sticky="ew")
        ttk.Label(filters, text="画像タグ:").grid(column=0, row=1, sticky="w", pady=(4, 0))
        self.completion_tag_combo = ttk.Combobox(
            filters, textvariable=self.completion_tag, values=("",), width=22)
        self.completion_tag_combo.grid(column=1, row=1, padx=3, pady=(4, 0), sticky="ew")
        ttk.Button(filters, text="再読込", command=lambda: self.refresh_completion(True)).grid(
            column=2, row=0, rowspan=2, padx=(3, 0), sticky="ns")
        filters.columnconfigure(1, weight=1)
        self.completion_query.trace_add(
            "write", lambda *args: self.debounce("completion_query", 150, self.refresh_completion))
        self.completion_tag.trace_add(
            "write", lambda *args: self.debounce("completion_tag", 150, self.refresh_completion))

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=6)
        self.completion_tree = ttk.Treeview(
            tree_frame, columns=("kind", "tags"), show="tree headings", selectmode="browse")
        self.completion_tree.heading("#0", text="候補")
        self.completion_tree.heading("kind", text="種類")
        self.completion_tree.heading("tags", text="タグ")
        self.completion_tree.column("#0", width=210, stretch=True)
        self.completion_tree.column("kind", width=75, stretch=False)
        self.completion_tree.column("tags", width=130, stretch=True)
        pack_scrollable_widget(self.completion_tree, horizontal=True)
        self.completion_tree.bind("<<TreeviewSelect>>", self.show_selected_completion_detail)
        self.completion_tree.bind("<Double-1>", self.insert_selected_completion)
        self.completion_tree.bind("<Return>", self.insert_selected_completion)
        self.completion_detail = tk.StringVar(value="Ctrl+Spaceで現在位置の候補を表示します。")
        ttk.Label(parent, textvariable=self.completion_detail, wraplength=290, justify="left").pack(
            fill="x", padx=6, pady=5)
        ttk.Button(parent, text="選択候補をエディタへ反映",
                   command=self.insert_selected_completion).pack(fill="x", padx=6, pady=(0, 6))

    def on_completion_mode_changed(self, event=None):
        self.hide_completion_popup()
        if self.completion_mode.get() == "右タブ":
            if not self.right_panel_visible:
                self.toggle_right_panel()
            self.right_tabs.select(self.completion_tab)
            self.refresh_completion()
        self.editor.focus_set()

    def on_editor_key_release(self, event=None):
        self.update_editor_view()
        if event is not None and event.keysym in (
                "Up", "Down", "Return", "Tab", "Escape", "Shift_L", "Shift_R",
                "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        if (self.completion_mode.get() == "エディタ内" or
                (self.completion_mode.get() == "右タブ" and
                 hasattr(self, "completion_tab") and
                 self.right_tabs.select() == str(self.completion_tab))):
            self.debounce("editor_completion", 140, self.refresh_completion)

    def show_completion_now(self, event=None):
        if self.completion_mode.get() == "無効":
            return "break"
        self.refresh_completion(explicit=True)
        return "break"

    def refresh_completion_if_visible(self):
        mode = self.completion_mode.get()
        if (mode == "エディタ内" or
                (mode == "右タブ" and
                 self.right_tabs.select() == str(self.completion_tab))):
            self.refresh_completion()

    def refresh_completion(self, explicit=False):
        if not hasattr(self, "completion_tree") or self.completion_mode.get() == "無効":
            self.hide_completion_popup()
            return
        source = self.editor.get("1.0", "end-1c")
        count = self.editor.count("1.0", "insert", "chars")
        cursor_offset = int(count[0]) if count else 0
        try:
            analysis = self.completion_engine.suggest(
                source, cursor_offset,
                query=self.completion_query.get() if self.completion_mode.get() == "右タブ" else "",
                tag=self.completion_tag.get(), limit=100)
        except (OSError, ValueError, TypeError) as error:
            self.completion_detail.set("補完候補を読み込めません: {}".format(error))
            self.hide_completion_popup()
            return
        self.completion_analysis = analysis
        self.completion_candidates = list(analysis.get("candidates", []))
        tags = sorted(
            {str(tag) for item in self.completion_candidates for tag in item.get("tags", [])}
            | set(self.completion_engine.image_tags()), key=str.lower)
        current_tag = self.completion_tag.get()
        self.completion_tag_combo.configure(values=("",) + tuple(tags))
        if current_tag and current_tag not in tags:
            self.completion_tag_combo.configure(values=("", current_tag) + tuple(tags))

        self.completion_tree.delete(*self.completion_tree.get_children())
        for index, item in enumerate(self.completion_candidates):
            self.completion_tree.insert(
                "", "end", iid="completion_{}".format(index), text=item.get("label", item.get("insert", "")),
                values=(item.get("kind", ""), ", ".join(item.get("tags", []))))
        if self.completion_candidates:
            self.completion_tree.selection_set("completion_0")
            self.show_selected_completion_detail()
        else:
            self.completion_detail.set("候補はありません。")

        if self.completion_mode.get() == "エディタ内":
            prefix = analysis.get("prefix", "")
            context = analysis.get("context", "normal")
            if self.completion_candidates and (explicit or prefix or context != "normal"):
                self.show_completion_popup()
            else:
                self.hide_completion_popup()

    def show_selected_completion_detail(self, event=None):
        selection = self.completion_tree.selection()
        if not selection:
            return
        try:
            index = int(selection[0].split("_", 1)[1])
            item = self.completion_candidates[index]
        except (ValueError, IndexError):
            return
        self.completion_detail.set(item.get("detail", item.get("insert", "")))

    def insert_selected_completion(self, event=None):
        selection = self.completion_tree.selection()
        if not selection:
            return "break" if event is not None else None
        try:
            index = int(selection[0].split("_", 1)[1])
            self.apply_completion(self.completion_candidates[index])
        except (ValueError, IndexError):
            pass
        return "break" if event is not None else None

    def _ensure_completion_popup(self):
        if self.completion_popup is not None:
            try:
                if self.completion_popup.winfo_exists():
                    return
            except tk.TclError:
                pass
        self.completion_popup = tk.Toplevel(self)
        self.completion_popup.overrideredirect(True)
        self.completion_popup.attributes("-topmost", True)
        self.completion_popup_list = tk.Listbox(
            self.completion_popup, height=10, width=52, exportselection=False,
            background="#252526", foreground="#dddddd", selectbackground="#094771")
        pack_scrollable_widget(
            self.completion_popup_list, horizontal=True)
        self.completion_popup_list.bind("<Double-1>", self.completion_accept_key)
        self.completion_popup_list.bind("<ButtonRelease-1>", lambda event: self.editor.focus_set())

    def show_completion_popup(self):
        self._ensure_completion_popup()
        self.completion_popup_list.delete(0, "end")
        for item in self.completion_candidates[:20]:
            self.completion_popup_list.insert(
                "end", "{}  [{}]".format(item.get("label", item.get("insert", "")), item.get("kind", "")))
        if not self.completion_popup_list.size():
            self.hide_completion_popup()
            return
        self.completion_popup_list.selection_set(0)
        bbox = self.editor.bbox("insert")
        if bbox is None:
            self.hide_completion_popup()
            return
        x = self.editor.winfo_rootx() + bbox[0]
        y = self.editor.winfo_rooty() + bbox[1] + bbox[3] + 2
        self.completion_popup.geometry("+{}+{}".format(x, y))
        self.completion_popup.deiconify()
        self.completion_popup.lift()
        self.editor.focus_set()

    def hide_completion_popup(self):
        if self.completion_popup is not None:
            try: self.completion_popup.withdraw()
            except tk.TclError: pass

    def completion_popup_visible(self):
        try:
            return bool(self.completion_popup and self.completion_popup.winfo_viewable()
                        and self.completion_popup_list.size())
        except tk.TclError:
            return False

    def completion_down(self, event=None):
        if not self.completion_popup_visible():
            return None
        current = self.completion_popup_list.curselection()
        index = min(self.completion_popup_list.size() - 1, (current[0] + 1) if current else 0)
        self.completion_popup_list.selection_clear(0, "end")
        self.completion_popup_list.selection_set(index)
        self.completion_popup_list.see(index)
        return "break"

    def completion_up(self, event=None):
        if not self.completion_popup_visible():
            return None
        current = self.completion_popup_list.curselection()
        index = max(0, (current[0] - 1) if current else 0)
        self.completion_popup_list.selection_clear(0, "end")
        self.completion_popup_list.selection_set(index)
        self.completion_popup_list.see(index)
        return "break"

    def completion_escape(self, event=None):
        if not self.completion_popup_visible():
            return None
        self.hide_completion_popup()
        return "break"

    def completion_accept_key(self, event=None):
        if not self.completion_popup_visible():
            # Tk.Text inserts a literal tab by default. All other DevStudio
            # Python editors use four spaces, so keep the main source editor
            # consistent when completion is closed.
            if event is not None and getattr(event, "keysym", "") == "Tab":
                return self._python_editor_tab(self.editor)
            return None
        selection = self.completion_popup_list.curselection()
        index = selection[0] if selection else 0
        if 0 <= index < min(20, len(self.completion_candidates)):
            self.apply_completion(self.completion_candidates[index])
        return "break"

    def apply_completion(self, candidate):
        source = self.editor.get("1.0", "end-1c")
        current_count = self.editor.count("1.0", "insert", "chars")
        current_offset = int(current_count[0]) if current_count else 0
        # Recalculate only the lightweight cursor context so a mouse move made
        # after the candidate list was built cannot replace an old location.
        analysis = self.completion_engine.analyze(source, current_offset)
        start_offset = int(analysis.get("replace_start", 0))
        cursor_offset = current_offset
        start_offset = max(0, min(start_offset, cursor_offset))
        start = "1.0+{}c".format(start_offset)
        try: self.editor.edit_separator()
        except tk.TclError: pass
        self.editor.delete(start, "insert")
        self.editor.insert(start, candidate.get("insert", ""))
        self.editor.mark_set("insert", "{}+{}c".format(start, len(candidate.get("insert", ""))))
        try: self.editor.edit_separator()
        except tk.TclError: pass
        self.editor.see("insert")
        self.editor.focus_set()
        self.hide_completion_popup()
        self.update_editor_view()

    def _build_step_hierarchy_tab(self, parent):
        self.step_source_mode = "generated"
        self.step_state_locations = {}
        self.step_state_original_names = {}
        self.step_state_dictionary_names = {}
        self._step_load_in_progress = False
        self.step_entry = tk.StringVar()
        self.step_loop = tk.BooleanVar(value=True)
        self.step_template_mode = tk.StringVar(value="Step (state transition / 状態遷移)")
        self.step_start = tk.StringVar(value="0 (_step_0)")
        self.special_step_entry = tk.StringVar()
        ttk.Label(parent, text="Add steps after creating a Step command. Apply rebuilds its generated Step skeleton.").grid(column=0, columnspan=3, row=0, padx=7, pady=(7, 3), sticky="w")
        ttk.Button(parent, text="Load current command", command=self.load_steps_from_editor).grid(column=3, row=0, padx=5, pady=(7, 3), sticky="e")
        ttk.Entry(parent, textvariable=self.step_entry).grid(column=0, columnspan=3, row=1, padx=7, pady=4, sticky="ew")
        step_actions = ttk.Frame(parent)
        step_actions.grid(column=0, columnspan=4, row=2, padx=5, pady=(0, 3), sticky="ew")
        ttk.Button(step_actions, text="辞書を追加", command=self.add_state_dictionary).pack(side="left", padx=2)
        ttk.Button(step_actions, text="ステップを追加", command=lambda: self.add_step_item(self.step_tree.focus())).pack(side="left", padx=2)
        ttk.Button(step_actions, text="名前を変更", command=self.rename_step_item).pack(side="left", padx=2)
        ttk.Button(step_actions, text="削除", command=self.remove_step_item).pack(side="left", padx=2)
        ttk.Button(step_actions, text="メソッドを開く", command=self.open_selected_state_method).pack(side="left", padx=2)
        ttk.Button(step_actions, text="変更をソースへ反映", command=self.apply_steps_to_editor).pack(side="right", padx=2)
        step_tree_frame = ttk.Frame(parent)
        step_tree_frame.grid(column=0, columnspan=4, row=3, padx=7, pady=4, sticky="nsew")
        self.step_tree = ttk.Treeview(step_tree_frame, show="tree", height=10)
        pack_scrollable_widget(self.step_tree, horizontal=True)
        ttk.Checkbutton(parent, text="Use loop to advance steps", variable=self.step_loop).grid(column=0, columnspan=2, row=4, padx=7, pady=3, sticky="w")
        ttk.Combobox(parent, state="readonly", width=34, textvariable=self.step_template_mode, values=("Step (state transition / 状態遷移)", "Step (nested chapters / 階層チャプター)")).grid(column=2, columnspan=2, row=4, padx=3, pady=3, sticky="e")
        ttk.Label(parent, text="First step:").grid(column=0, row=5, padx=7, pady=3, sticky="w")
        ttk.Combobox(parent, state="readonly", width=12, textvariable=self.step_start, values=("0 (_step_0)", "1 (_step_1)")).grid(column=1, row=5, padx=3, pady=3, sticky="w")
        special_box = ttk.Labelframe(parent, text="Special steps (called explicitly, not in normal order)")
        special_box.grid(column=0, columnspan=4, row=6, padx=7, pady=(5, 7), sticky="nsew")
        ttk.Entry(special_box, textvariable=self.special_step_entry, width=24).pack(side="left", padx=4, pady=4)
        special_step_frame = ttk.Frame(special_box)
        special_step_frame.pack(
            side="left", fill="x", expand=True, padx=4, pady=4)
        self.special_step_list = tk.Listbox(
            special_step_frame, height=3, exportselection=False)
        pack_scrollable_widget(self.special_step_list, horizontal=True)
        ttk.Button(special_box, text="Add", command=self.add_special_step).pack(side="left", padx=2)
        ttk.Button(special_box, text="Remove", command=self.remove_special_step).pack(side="left", padx=4)
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

    def _build_source_functions_tab(self, parent):
        self.source_function_search = tk.StringVar()
        self.source_function_find = tk.StringVar()
        self.source_function_replace = tk.StringVar()
        self.source_function_prefix = tk.StringVar()
        self.source_function_suffix = tk.StringVar()
        self.source_function_whole_name = tk.BooleanVar(value=True)
        self.source_function_show_steps = tk.BooleanVar(value=False)
        self.source_function_folder = tk.StringVar(value="SourceImports")
        self.source_function_tags = tk.StringVar(value="source")
        self.source_function_overwrite = tk.BooleanVar(value=False)
        self.source_function_rename_source_on_register = tk.BooleanVar(value=True)
        self.source_function_summary = tk.StringVar(value="現在のソースを解析します。")
        self.source_function_rows = {}
        self.source_function_name_overrides = {}
        self.source_function_last_registered = []
        self.source_dependency_list_name = tk.StringVar(value="")

        # This tab can be hosted in a narrow right pane.  Keep every option
        # reachable instead of letting the expanding function tree clip the
        # registration controls below it.
        scroll_host = ttk.Frame(parent)
        scroll_host.pack(fill="both", expand=True)
        tab_canvas = tk.Canvas(scroll_host, highlightthickness=0)
        tab_scroll = ttk.Scrollbar(
            scroll_host, orient="vertical", command=tab_canvas.yview)
        tab_canvas.configure(yscrollcommand=tab_scroll.set)
        tab_scroll.pack(side="right", fill="y")
        tab_canvas.pack(side="left", fill="both", expand=True)
        tab_content = ttk.Frame(tab_canvas)
        tab_window = tab_canvas.create_window(
            (0, 0), window=tab_content, anchor="nw")
        tab_content.bind(
            "<Configure>",
            lambda _event: tab_canvas.configure(
                scrollregion=tab_canvas.bbox("all")))
        tab_canvas.bind(
            "<Configure>",
            lambda event: tab_canvas.itemconfigure(
                tab_window, width=event.width))
        parent = tab_content

        help_box = ttk.Label(
            parent,
            text="①関数を選択 → ②登録名を確認 → ③サンプル登録\n"
                 "変更名は既定でソースの関数定義・呼び出しにも同時反映\n"
                 "登録済み行はダブルクリックでサンプル関数の変更画面へ移動",
            justify="left", foreground="#174a7e")
        help_box.pack(fill="x", padx=6, pady=(6, 3))

        search_row = ttk.Frame(parent); search_row.pack(fill="x", padx=6, pady=3)
        ttk.Label(search_row, text="検索:").pack(side="left")
        ttk.Entry(search_row, textvariable=self.source_function_search).pack(
            side="left", fill="x", expand=True, padx=3)
        ttk.Button(search_row, text="再読込", command=self.refresh_source_functions).pack(side="right")
        ttk.Checkbutton(
            search_row, text="Step関数も表示", variable=self.source_function_show_steps,
            command=lambda: self.refresh_source_functions(reload_source=False)).pack(
                side="right", padx=4)

        # Primary actions stay above the expanding list, so registration is
        # always possible even before scrolling to the detailed settings.
        primary_actions = ttk.Frame(parent)
        primary_actions.pack(fill="x", padx=6, pady=(2, 3))
        ttk.Button(
            primary_actions, text="選択をサンプルへ登録",
            command=self.register_selected_source_functions).pack(
                side="left", padx=(0, 3))
        ttk.Button(
            primary_actions, text="選択1件の登録名を確認・変更",
            command=self.edit_source_function_target_name).pack(
                side="left", padx=3)
        ttk.Button(
            primary_actions, text="登録済みサンプルを開く",
            command=self.open_selected_source_sample).pack(
                side="right", padx=(3, 0))

        tree_frame = ttk.Frame(parent); tree_frame.pack(fill="both", expand=True, padx=6, pady=3)
        self.source_function_tree = ttk.Treeview(
            tree_frame, columns=("new_name", "line", "status"),
            show="tree headings", selectmode="extended", height=12)
        self.source_function_tree.heading("#0", text="現在の関数名")
        self.source_function_tree.heading("new_name", text="登録・変更後")
        self.source_function_tree.heading("line", text="行")
        self.source_function_tree.heading("status", text="サンプル")
        self.source_function_tree.column("#0", width=175, stretch=True)
        self.source_function_tree.column("new_name", width=175, stretch=True)
        self.source_function_tree.column("line", width=42, stretch=False, anchor="e")
        self.source_function_tree.column("status", width=70, stretch=False)
        tree_x_scroll = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self.source_function_tree.xview)
        tree_x_scroll.pack(side="bottom", fill="x")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.source_function_tree.yview)
        tree_scroll.pack(side="right", fill="y")
        self.source_function_tree.pack(side="left", fill="both", expand=True)
        self.source_function_tree.configure(
            yscrollcommand=tree_scroll.set, xscrollcommand=tree_x_scroll.set)
        self.source_function_tree.bind("<Double-1>", self.open_or_name_source_function)

        rename_box = ttk.Labelframe(parent, text="関数名を一括作成")
        rename_box.pack(fill="x", padx=6, pady=3)
        ttk.Label(rename_box, text="検索文字").grid(column=0, row=0, padx=3, pady=2, sticky="w")
        ttk.Entry(rename_box, textvariable=self.source_function_find, width=12).grid(
            column=1, row=0, padx=3, pady=2, sticky="ew")
        ttk.Label(rename_box, text="→置換").grid(column=2, row=0, padx=3, pady=2)
        ttk.Entry(rename_box, textvariable=self.source_function_replace, width=12).grid(
            column=3, row=0, padx=3, pady=2, sticky="ew")
        ttk.Label(rename_box, text="先頭追加").grid(column=0, row=1, padx=3, pady=2, sticky="w")
        ttk.Entry(rename_box, textvariable=self.source_function_prefix, width=12).grid(
            column=1, row=1, padx=3, pady=2, sticky="ew")
        ttk.Label(rename_box, text="末尾追加").grid(column=2, row=1, padx=3, pady=2)
        ttk.Entry(rename_box, textvariable=self.source_function_suffix, width=12).grid(
            column=3, row=1, padx=3, pady=2, sticky="ew")
        ttk.Checkbutton(
            rename_box,
            text="完全一致（関数名全体が検索文字と同じ場合だけ置換・安全）",
            variable=self.source_function_whole_name).grid(
                column=0, columnspan=4, row=2, padx=3, pady=2, sticky="w")
        rename_buttons = ttk.Frame(rename_box); rename_buttons.grid(
            column=0, columnspan=4, row=3, padx=3, pady=3, sticky="ew")
        ttk.Button(rename_buttons, text="変更名をプレビュー",
                   command=self.preview_source_function_names).pack(side="left")
        ttk.Button(rename_buttons, text="選択1件の名前を直接指定",
                   command=self.edit_source_function_target_name).pack(side="left", padx=3)
        ttk.Button(rename_buttons, text="リセット",
                   command=self.reset_source_function_names).pack(side="right")
        rename_box.columnconfigure(1, weight=1); rename_box.columnconfigure(3, weight=1)

        sample_box = ttk.Labelframe(parent, text="サンプル登録先")
        sample_box.pack(fill="x", padx=6, pady=3)
        ttk.Label(sample_box, text="フォルダー").grid(column=0, row=0, padx=3, pady=2, sticky="w")
        ttk.Entry(sample_box, textvariable=self.source_function_folder).grid(
            column=1, row=0, padx=3, pady=2, sticky="ew")
        ttk.Label(sample_box, text="タグ（,区切り）").grid(column=0, row=1, padx=3, pady=2, sticky="w")
        ttk.Entry(sample_box, textvariable=self.source_function_tags).grid(
            column=1, row=1, padx=3, pady=2, sticky="ew")
        ttk.Checkbutton(sample_box, text="同名サンプルは内容を更新",
                        variable=self.source_function_overwrite).grid(
                            column=0, columnspan=2, row=2, padx=3, pady=2, sticky="w")
        ttk.Checkbutton(
            sample_box,
            text="登録時、変更名をソースの関数定義・全参照にも反映",
            variable=self.source_function_rename_source_on_register).grid(
                column=0, columnspan=2, row=3, padx=3, pady=2, sticky="w")
        sample_box.columnconfigure(1, weight=1)

        dependency_box = ttk.Labelframe(
            parent, text="main・状態辞書配下をまとめて登録")
        dependency_box.pack(fill="x", padx=6, pady=3)
        ttk.Label(
            dependency_box,
            text=("選択関数を入口にself関数とSTATE_*_FUNCTIONの全処理を追跡し、\n"
                  "各関数をサンプルとして再利用/登録してサンプルリストへまとめます。"),
            foreground="#174a7e", justify="left").grid(
                column=0, columnspan=2, row=0, padx=3, pady=2, sticky="w")
        ttk.Label(dependency_box, text="リスト名（空欄は入口名）").grid(
            column=0, row=1, padx=3, pady=2, sticky="w")
        ttk.Entry(
            dependency_box, textvariable=self.source_dependency_list_name).grid(
                column=1, row=1, padx=3, pady=2, sticky="ew")
        ttk.Button(
            dependency_box, text="選択を起点に依存処理を確認",
            command=self.preview_source_dependency_group).grid(
                column=0, row=2, padx=3, pady=3, sticky="ew")
        ttk.Button(
            dependency_box, text="依存処理をサンプル関数＋リストへ登録",
            command=self.register_source_dependency_group).grid(
                column=1, row=2, padx=3, pady=3, sticky="ew")
        ttk.Button(
            dependency_box, text="状態辞書からmainひな形を追加",
            command=self.create_state_dictionary_main_template).grid(
                column=0, columnspan=2, row=3, padx=3, pady=3, sticky="ew")
        ttk.Button(
            dependency_box, text="別の作成済みCommandsを開いて登録",
            command=self.open_commands_source_for_samples).grid(
                column=0, columnspan=2, row=4, padx=3, pady=3, sticky="ew")
        dependency_box.columnconfigure(1, weight=1)

        actions = ttk.Frame(parent); actions.pack(fill="x", padx=6, pady=4)
        ttk.Button(actions, text="選択名をソースへ一括反映",
                   command=self.apply_source_function_renames).pack(fill="x", pady=2)
        ttk.Label(parent, textvariable=self.source_function_summary,
                  wraplength=350, justify="left").pack(fill="x", padx=6, pady=(2, 6))
        self.source_function_search.trace_add(
            "write", lambda *_: self.debounce(
                "source_function_search", 120,
                lambda: self.refresh_source_functions(reload_source=False)))

    def _source_function_preview_map(self):
        names = [item["name"] for item in getattr(self, "source_function_records", [])]
        preview = build_rename_map(
            names, self.source_function_find.get(), self.source_function_replace.get(),
            self.source_function_prefix.get(), self.source_function_suffix.get(),
            whole_name=self.source_function_whole_name.get())
        preview.update({name: value for name, value in self.source_function_name_overrides.items()
                        if name in preview})
        # Validate explicit per-row changes and duplicate results as one set.
        for value in preview.values():
            build_rename_map([value])
        if len(set(preview.values())) != len(preview):
            raise ValueError("変更後の関数名が重複しています。")
        return preview

    def refresh_source_functions(self, select_names=None, reload_source=True):
        if not hasattr(self, "source_function_tree"):
            return
        if select_names is None:
            select_names = {self.source_function_rows[iid]["name"]
                            for iid in self.source_function_tree.selection()
                            if iid in self.source_function_rows}
        else:
            select_names = set(select_names)
        try:
            if reload_source:
                source = self.editor.get("1.0", "end-1c")
                self.source_function_records = source_function_records(source)
                self.source_function_step_names = step_function_names(source)
            records = getattr(self, "source_function_records", [])
            step_names = getattr(self, "source_function_step_names", set())
            preview = self._source_function_preview_map()
        except (SyntaxError, ValueError, tokenize.TokenError) as error:
            self.source_function_records = []
            self.source_function_rows = {}
            self.source_function_tree.delete(*self.source_function_tree.get_children())
            self.source_function_summary.set("ソースを解析できません: {}".format(error))
            return
        if reload_source or self._source_function_catalog_candidates is None:
            self._source_function_catalog_candidates = \
                catalog_function_candidates(self.fragment_root())
        catalog_by_name = self._source_function_catalog_candidates
        needle = self.source_function_search.get().strip().casefold()
        self.source_function_rows = {}
        self.source_function_tree.delete(*self.source_function_tree.get_children())
        selected_iids = []
        registered_count = 0
        hidden_step_count = 0
        for index, record in enumerate(records):
            old_name = record["name"]
            new_name = preview.get(old_name, old_name)
            if needle and needle not in (old_name + " " + new_name).casefold():
                continue
            if not self.source_function_show_steps.get() and old_name in step_names:
                hidden_step_count += 1
                continue
            expected_text = record["text"]
            if old_name != new_name:
                expected_text = rename_source_functions(
                    expected_text, {old_name: new_name},
                    require_definitions=False)
            registration = classify_function_registration(
                expected_text, catalog_by_name.get(new_name, []), new_name)
            status = registration["status"]
            fragment_id = registration["fragment_id"]
            overwrite_supported = registration["overwrite_supported"]
            if status == "登録済み":
                registered_count += 1
            iid = self.source_function_tree.insert(
                "", "end", text=old_name,
                values=(new_name, record["line"], status))
            row = dict(record)
            row.update({
                "new_name": new_name, "fragment_id": fragment_id,
                "registration_status": status,
                "overwrite_supported": overwrite_supported,
            })
            self.source_function_rows[iid] = row
            if old_name in select_names:
                selected_iids.append(iid)
        if selected_iids:
            self.source_function_tree.selection_set(selected_iids)
            self.source_function_tree.see(selected_iids[0])
        hidden_text = " / Step非表示{}件".format(hidden_step_count) \
            if hidden_step_count else ""
        self.source_function_summary.set(
            "{}関数を検出 / 表示{}件 / 登録済み{}件{}".format(
                len(records), len(self.source_function_rows), registered_count, hidden_text))

    def _selected_source_functions(self, require=True):
        rows = [self.source_function_rows[iid] for iid in self.source_function_tree.selection()
                if iid in self.source_function_rows]
        if require and not rows:
            messagebox.showinfo("関数登録", "関数を1つ以上選択してください。", parent=self)
        return rows

    def _selected_source_function_plan(self):
        rows = self._selected_source_functions()
        if not rows:
            return []
        try:
            preview = self._source_function_preview_map()
        except ValueError as error:
            messagebox.showwarning("関数名", str(error), parent=self); return []
        planned = []
        for row in rows:
            item = dict(row)
            item["new_name"] = preview.get(item["name"], item["name"])
            planned.append(item)
        return planned

    def preview_source_function_names(self):
        try:
            preview = self._source_function_preview_map()
        except ValueError as error:
            messagebox.showwarning("関数名", str(error), parent=self); return
        self.refresh_source_functions(reload_source=False)
        changed = sum(name != value for name, value in preview.items())
        self.source_function_summary.set("変更名をプレビューしました: {}件".format(changed))

    def reset_source_function_names(self):
        self.source_function_find.set(""); self.source_function_replace.set("")
        self.source_function_prefix.set(""); self.source_function_suffix.set("")
        self.source_function_name_overrides = {}
        self.refresh_source_functions(reload_source=False)

    def edit_source_function_target_name(self):
        rows = self._selected_source_functions()
        if len(rows) != 1:
            messagebox.showinfo("関数名", "直接指定する関数を1つだけ選択してください。", parent=self); return
        row = rows[0]
        value = simpledialog.askstring(
            "関数名を指定", "{} の登録・変更後の関数名:".format(row["name"]),
            initialvalue=row["new_name"], parent=self)
        if value is None:
            return
        try:
            build_rename_map([value.strip()])
        except ValueError as error:
            messagebox.showwarning("関数名", str(error), parent=self); return
        self.source_function_name_overrides[row["name"]] = value.strip()
        self.refresh_source_functions(select_names=[row["name"]], reload_source=False)

    def _source_function_mapping_detail(self, rows):
        lines = ["{} → {}".format(row["name"], row["new_name"]) for row in rows]
        if len(lines) > 15:
            lines = lines[:15] + ["ほか{}件".format(len(rows) - 15)]
        return "\n".join(lines)

    def apply_source_function_renames(self):
        rows = self._selected_source_function_plan()
        if not rows:
            return
        mapping = {row["name"]: row["new_name"] for row in rows
                   if row["name"] != row["new_name"]}
        if not mapping:
            messagebox.showinfo("関数名一括変更", "選択した関数の変更名が同じです。", parent=self); return
        if not messagebox.askyesno(
                "関数名一括変更",
                "関数定義とソース内の参照を一括変更します。\n\n{}\n\n反映しますか？".format(
                    self._source_function_mapping_detail(rows)), parent=self):
            return
        source = self.editor.get("1.0", "end-1c")
        try:
            updated = rename_source_functions(source, mapping)
        except (SyntaxError, ValueError, tokenize.TokenError) as error:
            messagebox.showerror("関数名一括変更", str(error), parent=self); return
        line = int(self.editor.index("insert").split(".")[0])
        self.set_editor_content(updated, self.current_path, line)
        self.editor_dirty = True
        self.update_editor_view()
        changed_names = list(mapping.values())
        self.source_function_find.set(""); self.source_function_replace.set("")
        self.source_function_prefix.set(""); self.source_function_suffix.set("")
        self.source_function_name_overrides = {}
        self.refresh_source_functions(select_names=changed_names)
        self.status.set("{}関数の名前と参照を変更しました。ソースを保存してください。".format(len(mapping)))

    def register_selected_source_functions(self):
        rows = self._selected_source_function_plan()
        if not rows:
            return
        overwrite = self.source_function_overwrite.get()
        registerable = [
            row for row in rows
            if row.get("registration_status") == "未登録" or
            (row.get("registration_status") == "処理差あり" and
             overwrite and row.get("overwrite_supported"))]
        if not registerable:
            statuses = {row.get("registration_status") for row in rows}
            if statuses == {"登録済み"}:
                messagebox.showinfo(
                    "ソースからサンプル登録",
                    "選択した関数は、関数本体まで含めてすでに登録済みです。\n"
                    "ダブルクリックまたは「登録済みサンプルを開く」で確認できます。",
                    parent=self)
            elif statuses == {"処理差あり"} and all(
                    row.get("overwrite_supported") for row in rows):
                messagebox.showinfo(
                    "ソースからサンプル登録",
                    "同名サンプルと処理が異なります。更新する場合は\n"
                    "「同名サンプルは内容を更新」をチェックしてください。",
                    parent=self)
            else:
                messagebox.showwarning(
                    "ソースからサンプル登録",
                    "複数関数サンプル内に同名関数が登録済み、または同名登録が複数あります。\n"
                    "サンプル関数チェックで差分と登録先を確認してください。",
                    parent=self)
            return
        skipped = len(rows) - len(registerable)
        rows = registerable
        source = self.editor.get("1.0", "end-1c")
        names = [row["name"] for row in rows]
        rename_map = {row["name"]: row["new_name"] for row in rows}
        changed_mapping = {
            old: new for old, new in rename_map.items() if old != new}
        rename_source = bool(
            changed_mapping and self.source_function_rename_source_on_register.get())
        tags = [value.strip() for value in self.source_function_tags.get().split(",")
                if value.strip()]
        detail = self._source_function_mapping_detail(rows)
        action = "登録済みサンプルは内容を更新します。" if overwrite else \
            "登録済みと同名の場合は中断します。"
        if skipped:
            action += "\n登録済みまたは競合中の{}関数は除外します。".format(
                skipped)
        if rename_source:
            action += "\n変更名をソースの関数定義と全呼び出しにも反映します。"
        if not messagebox.askyesno(
                "ソースからサンプル登録",
                "{}関数をサンプルへ登録します。\n{}\n\n{}\n\n続行しますか？".format(
                    len(rows), action, detail), parent=self):
            return
        root = self.fragment_root()
        folder = self.source_function_folder.get().strip() or "SourceImports"
        current_path = self.current_path or ""

        def worker():
            if rename_source:
                updated_source = rename_source_functions(source, changed_mapping)
                registered_names = [rename_map[name] for name in names]
                created = register_source_functions(
                    updated_source, registered_names, root, folder=folder,
                    tags=tags, overwrite=overwrite, source_path=current_path)
                return created, updated_source, registered_names
            created = register_source_functions(
                source, names, root, folder=folder, rename_map=rename_map,
                tags=tags, overwrite=overwrite, source_path=current_path)
            return created, source, names

        def completed(result):
            created, updated_source, selected_names = result
            if updated_source != source:
                line = int(self.editor.index("insert").split(".")[0])
                self.set_editor_content(updated_source, current_path, line)
                self.editor_dirty = True
                self.update_editor_view()
                self.source_function_find.set("")
                self.source_function_replace.set("")
                self.source_function_prefix.set("")
                self.source_function_suffix.set("")
                self.source_function_name_overrides = {}
            self._fragment_catalog_cache = None
            self._source_function_catalog_candidates = None
            self.source_function_last_registered = [item["id"] for item in created]
            self.refresh_index()
            self.refresh_registered_fragment_choices()
            self.refresh_sample_lists_tab(select=self.sample_list_name.get().strip())
            self.refresh_sample_apply_lists()
            self.refresh_source_functions(
                select_names=selected_names, reload_source=False)
            self.status.set(
                "ソースからサンプル関数を{}件登録しました。{}".format(
                    len(created),
                    " 関数名と参照も変更したため、ソースを保存してください。"
                    if updated_source != source else ""))
            if len(created) == 1 and messagebox.askyesno(
                    "サンプル登録完了",
                    "登録しました: {}\n\nサンプル関数タブで変更しますか？".format(created[0]["name"]),
                    parent=self):
                self.load_fragment_for_editing(created[0]["id"])
            elif len(created) > 1:
                messagebox.showinfo(
                    "サンプル登録完了",
                    "{}件登録しました。\n一覧で1件選択し「選択サンプルを変更画面で開く」を押すと編集できます。".format(
                        len(created)), parent=self)

        self.run_background(
            "source_function_register", "ソースからサンプル関数を登録中",
            worker, completed,
            lambda error: messagebox.showerror("ソースからサンプル登録", str(error), parent=self))

    def open_selected_source_sample(self):
        rows = self._selected_source_functions()
        if len(rows) != 1:
            messagebox.showinfo("サンプル関数", "開く関数を1つだけ選択してください。", parent=self); return
        fragment_id = rows[0].get("fragment_id")
        if not fragment_id:
            messagebox.showinfo("サンプル関数", "この登録名のサンプル関数はまだ登録されていません。", parent=self); return
        self.load_fragment_for_editing(fragment_id)

    def _source_dependency_selection(self):
        rows = self._selected_source_functions()
        if not rows:
            return None
        roots = [row["name"] for row in rows]
        list_name = self.source_dependency_list_name.get().strip() or (
            roots[0] if len(roots) == 1 else roots[0] + "_group")
        return roots, list_name

    def open_commands_source_for_samples(self):
        root = os.path.abspath(self.root_dir.get() or os.getcwd())
        candidates = [
            os.path.join(root, "SerialController", "Commands", "PythonCommands"),
            os.path.join(root, "Commands", "PythonCommands"), root]
        initial = next((path for path in candidates if os.path.isdir(path)), root)
        path = filedialog.askopenfilename(
            parent=self, title="サンプル登録する作成済みCommandsを選択",
            initialdir=initial,
            filetypes=[("Python Commands", "*.py"), ("All files", "*.*")])
        if not path:
            return
        self.show_file(path)
        self.after_idle(lambda: self.right_tabs.select(self.source_functions_tab))

    def _analyze_source_dependency_selection(self, source, roots):
        """Prefer a state dictionary as the root when a selected main uses one."""
        analysis = analyze_source_dependencies(source, roots)
        dictionary = suggest_state_dictionary(
            analysis, roots[0] if len(roots) == 1 else "")
        if dictionary:
            analysis = analyze_state_dictionary_dependencies(
                source, dictionary,
                main_function_name=roots[0] if len(roots) == 1 else "")
        return analysis

    def create_state_dictionary_main_template(self):
        """Add a main loop generated from a selected STATE_*_FUNCTION map."""
        source = self.editor.get("1.0", "end-1c")
        try:
            dictionaries = state_dictionary_names(source)
        except SyntaxError as error:
            messagebox.showwarning("状態辞書からmainを作成", str(error), parent=self)
            return
        if not dictionaries:
            messagebox.showinfo(
                "状態辞書からmainを作成",
                "__init__ に STATE_*_FUNCTION 辞書がありません。", parent=self)
            return
        selected = self._source_dependency_selection()
        selected_name = selected[0][0] if selected and len(selected[0]) == 1 else ""
        suggested = ""
        if selected:
            try:
                ordinary = analyze_source_dependencies(source, selected[0])
                suggested = suggest_state_dictionary(ordinary, selected_name)
            except (SyntaxError, ValueError):
                pass
        dictionary = simpledialog.askstring(
            "状態辞書からmainを作成",
            "正本にする状態辞書名:\n候補: {}".format(", ".join(dictionaries)),
            initialvalue=suggested or dictionaries[0], parent=self)
        if not dictionary:
            return
        dictionary = dictionary.strip()
        if dictionary not in dictionaries:
            messagebox.showwarning(
                "状態辞書からmainを作成",
                "指定した状態辞書がありません: " + dictionary, parent=self)
            return
        function_name = simpledialog.askstring(
            "状態辞書からmainを作成", "作成するmain関数名:",
            initialvalue=selected_name or dictionary[6:-9].lower() + "_main",
            parent=self)
        if not function_name:
            return
        current_state = state_dictionary_current_state(source, dictionary)
        current_state = simpledialog.askstring(
            "状態辞書からmainを作成", "現在状態を保持するself属性名:",
            initialvalue=current_state, parent=self)
        if not current_state:
            return
        try:
            generated = generate_state_machine_main(
                function_name.strip(), dictionary, current_state.strip())
            preview = {
                "imports": [], "class_variables": [], "initializers": [],
                "bodies": [generated], "included": [function_name.strip()]}
            comparison = compare_preview_functions(source, preview)[0]
            if comparison["status"] == "match":
                messagebox.showinfo(
                    "状態辞書からmainを作成",
                    "同じmain関数が既にあります。変更はありません。", parent=self)
                return
            if comparison["status"] != "missing":
                messagebox.showwarning(
                    "状態辞書からmainを作成",
                    "同名mainの処理が異なるため上書きしません。\n"
                    "サンプル関数チェックで差分を確認してください。", parent=self)
                return
            merged, _rows = merge_preview_functions_safely(
                source, preview, function_name.strip())
        except (SyntaxError, ValueError) as error:
            messagebox.showwarning("状態辞書からmainを作成", str(error), parent=self)
            return
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", merged)
        self.editor.edit_modified(True)
        self.refresh_source_functions(
            select_names=[function_name.strip()], reload_source=False)
        self.status.set("状態辞書 {} からmain {} を追加しました。".format(
            dictionary, function_name.strip()))

    def preview_source_dependency_group(self):
        selected = self._source_dependency_selection()
        if not selected:
            return
        roots, list_name = selected
        source = self.editor.get("1.0", "end-1c")
        try:
            analysis = self._analyze_source_dependency_selection(source, roots)
        except (SyntaxError, ValueError) as error:
            messagebox.showwarning("依存処理の解析", str(error), parent=self)
            return
        states = []
        for dictionary, entries in analysis.get("state_dictionaries", {}).items():
            states.append("{}: {}状態".format(dictionary, len(entries)))
        root_dictionary = analysis.get("root_state_dictionary", "")
        details = (
            "リスト名: {}\n入口: {}\n依存サンプル関数: {}件\n"
            "初期化ブロック: {}文字\nクラス変数ブロック: {}件\n状態辞書: {}\n"
            "正本の状態辞書: {}\n画像検知側の外部設定: {}\n\n{}"
        ).format(
            list_name, ", ".join(roots), len(analysis["methods"]),
            len(analysis["initializer"]), len(analysis["class_variables"]),
            ", ".join(states) if states else "なし",
            root_dictionary or "なし",
            ", ".join(analysis.get("external_class_variables", [])) or "なし",
            "\n".join(analysis["methods"]))
        viewer = tk.Toplevel(self)
        viewer.title("依存処理の確認 - " + list_name)
        viewer.geometry("760x720")
        viewer.transient(self)
        text = tk.Text(viewer, wrap="none", font=self.code_font)
        yscroll = ttk.Scrollbar(viewer, orient="vertical", command=text.yview)
        xscroll = ttk.Scrollbar(viewer, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        text.grid(column=0, row=0, sticky="nsew")
        yscroll.grid(column=1, row=0, sticky="ns")
        xscroll.grid(column=0, row=1, sticky="ew")
        text.insert("1.0", details)
        text.configure(state="disabled")
        viewer.columnconfigure(0, weight=1)
        viewer.rowconfigure(0, weight=1)
        ttk.Button(viewer, text="閉じる", command=viewer.destroy).grid(
            column=0, row=2, pady=6)

    def register_source_dependency_group(self):
        selected = self._source_dependency_selection()
        if not selected:
            return
        roots, list_name = selected
        source = self.editor.get("1.0", "end-1c")
        root = self.fragment_root()
        base_folder = self.source_function_folder.get().strip() or "SourceImports"
        folder = base_folder.rstrip("/\\") + "/" + python_identifier(list_name)
        source_path = self.current_path or ""

        def failed(error):
            if messagebox.askyesno(
                    "依存処理の登録を中断",
                    "{}\n\nサンプル関数チェックを開きますか？".format(error),
                    parent=self):
                self.open_sample_function_check_mode()

        def analysis_completed(analysis):
            states = ", ".join(
                "{}（{}状態）".format(name, len(entries))
                for name, entries in analysis.get("state_dictionaries", {}).items())
            summary = (
                "{}を入口として{}関数を登録・再利用します。\n"
                "状態辞書: {}\n保存リスト: {}\n\n"
                "登録済み関数はソースと完全一致する場合だけ再利用します。\n"
                "差分がある関数は上書きせず、サンプル関数チェックを要求します。\n\n"
                "続行しますか？"
            ).format(
                ", ".join(roots), len(analysis["methods"]), states or "なし",
                list_name)
            if not messagebox.askyesno(
                    "依存処理をまとめて登録", summary, parent=self):
                self.status.set("依存処理の登録をキャンセルしました。")
                return

            def worker():
                plan, members = register_dependency_group(
                    source, roots, root, folder, list_name,
                    source_path=source_path,
                    state_dictionary=analysis.get("root_state_dictionary", ""),
                    analysis=analysis)
                data = self._read_sample_lists()
                data["lists"][list_name] = {
                    "tags": ["source", "dependency-group"],
                    "members": members,
                    "origin_path": str(source_path),
                }
                self._write_sample_lists(data)
                # Populate the UI cache off the Tk thread as well.  The
                # catalog only contains plain dictionaries and is safe to
                # transfer through the background result queue.
                return plan, catalog(root)

            def completed(result):
                plan, catalog_items = result
                reused = sum(
                    row["status"] == "reuse" for row in plan["registration"])
                self._fragment_catalog_cache = list(catalog_items)
                self.refresh_index()
                entry_id = next((
                    row.get("selected", {}).get("id")
                    for row in plan["registration"]
                    if row.get("name") in roots and row.get("selected")), None)
                self.refresh_registered_fragment_choices(select=entry_id)
                if (hasattr(self, "sample_lists_workspace") and
                        self.workspace_tabs.select() == str(self.sample_lists_workspace)):
                    self.refresh_sample_lists_tab(select=list_name)
                else:
                    self._sample_lists_refresh_deferred = list_name
                self.refresh_sample_apply_lists()
                self.refresh_source_functions(
                    select_names=roots, reload_source=False)
                self.status.set(
                    "依存処理リスト「{}」を登録しました: {}関数（既存再利用{}件）".format(
                        list_name, len(plan["methods"]), reused))

            self.run_background(
                "source_dependency_group", "依存サンプルを比較・登録中",
                worker, completed, failed)

        self.run_background(
            "source_dependency_group", "依存関数を解析中",
            lambda: self._analyze_source_dependency_selection(source, roots),
            analysis_completed, failed)

    def open_or_name_source_function(self, event=None):
        rows = self._selected_source_functions(require=False)
        if len(rows) == 1 and rows[0].get("fragment_id"):
            self.load_fragment_for_editing(rows[0]["fragment_id"])
        elif len(rows) == 1:
            self.edit_source_function_target_name()

    def on_right_tool_tab_changed(self, event=None):
        if self.right_tabs.select() == str(self.image_targets_tab):
            self._on_image_management_tab_changed()
        elif self.right_tabs.select() == str(self.image_health_tab):
            self.run_image_health_check()
        elif self.right_tabs.select() == str(self.image_reference_tab):
            self.run_image_reference_check()
        elif self.right_tabs.select() == str(self.step_hierarchy_tab):
            self.load_steps_from_editor(silent=True)
        elif self.right_tabs.select() == str(self.completion_tab):
            self.refresh_completion()
        elif self.right_tabs.select() == str(self.source_functions_tab):
            self.refresh_source_functions()

    def add_step_item(self, parent):
        label = self.step_entry.get().strip()
        if not label:
            if self.step_source_mode == "state_machine":
                label = "NEW_STATE -> method_name" if parent else "STATE_NEW_FUNCTION"
            else:
                label = "New child step" if parent else "New chapter"
        if self.step_source_mode == "state_machine" and parent:
            dictionary_names = getattr(self, "step_state_dictionary_names", {})
            while parent and parent not in dictionary_names:
                parent = self.step_tree.parent(parent)
        item = self.step_tree.insert(parent, "end", text=label, open=True)
        if self.step_source_mode == "state_machine" and label.startswith("STATE_") and label.endswith("_FUNCTION"):
            self.step_state_dictionary_names[item] = label
        self.step_tree.selection_set(item)
        self.step_tree.focus(item)
        self.step_entry.set("")

    def add_state_dictionary(self):
        label = self.step_entry.get().strip() or "STATE_NEW_FUNCTION"
        parent = ""
        if self.step_source_mode == "state_machine":
            selected = self.step_tree.focus()
            if selected and selected not in getattr(self, "step_state_dictionary_names", {}):
                parent = selected
        item = self.step_tree.insert(parent, "end", text=label, open=True)
        if self.step_source_mode == "state_machine":
            self.step_state_dictionary_names[item] = label
        self.step_tree.selection_set(item)
        self.step_tree.focus(item)
        self.step_entry.set("")

    def rename_step_item(self):
        selected = self.step_tree.selection()
        label = self.step_entry.get().strip()
        if not selected:
            messagebox.showinfo("Step hierarchy", "Select a chapter or step to rename.", parent=self)
            return
        if not label:
            messagebox.showinfo("Step hierarchy", "Enter a new name above, then press Rename.", parent=self)
            return
        self.step_tree.item(selected[0], text=label)
        if selected[0] in getattr(self, "step_state_dictionary_names", {}):
            self.step_state_dictionary_names[selected[0]] = label
        self.step_entry.set("")

    def remove_step_item(self):
        selected = self.step_tree.selection()
        if selected:
            self.step_tree.delete(selected[0])

    def add_special_step(self):
        name = self.special_step_entry.get().strip()
        if name and name not in self.special_step_list.get(0, "end"):
            self.special_step_list.insert("end", name)
            self.special_step_entry.set("")

    def remove_special_step(self):
        selected = self.special_step_list.curselection()
        if selected:
            self.special_step_list.delete(selected[0])

    def _flatten_step_tree(self):
        try:
            start = int(self.step_start.get().split()[0])
        except ValueError:
            start = 0
        def flatten(item, key):
            values = [{"key": key, "label": self.step_tree.item(item, "text")}]
            for number, child in enumerate(self.step_tree.get_children(item), 1):
                values.extend(flatten(child, key + "_" + str(number)))
            return values
        values = []
        for number, item in enumerate(self.step_tree.get_children(""), start):
            values.extend(flatten(item, str(number)))
        return values

    def load_steps_from_editor(self, silent=False):
        if self._step_load_in_progress:
            return
        source = self.editor.get("1.0", "end-1c")
        try:
            tree = ast.parse(source)
            command = next(node for node in tree.body if isinstance(node, ast.ClassDef))
            assignment = next(node for node in command.body if isinstance(node, ast.Assign) and any(getattr(target, "id", "") == "STEP_LABELS" for target in node.targets))
            steps = ast.literal_eval(assignment.value)
            key_assignment = next((node for node in command.body if isinstance(node, ast.Assign) and any(getattr(target, "id", "") == "STEP_KEYS" for target in node.targets)), None)
            step_keys = ast.literal_eval(key_assignment.value) if key_assignment is not None else [str(index) for index in range(len(steps))]
            special_assignment = next((node for node in command.body if isinstance(node, ast.Assign) and any(getattr(target, "id", "") == "SPECIAL_STEP_KEYS" for target in node.targets)), None)
            special_steps = ast.literal_eval(special_assignment.value) if special_assignment is not None else []
            if not isinstance(steps, list):
                raise ValueError
        except (SyntaxError, StopIteration, ValueError, TypeError):
            if self._load_state_machine_steps(source):
                return
            if not silent:
                messagebox.showwarning("Step hierarchy", "The current source must be a generated Step command with STEP_LABELS.", parent=self)
            return
        self.step_source_mode = "generated"
        self.step_state_locations = {}
        self.step_state_original_names = {}
        self.step_state_dictionary_names = {}
        self.step_tree.delete(*self.step_tree.get_children())
        inserted = {}
        for key, label in zip(step_keys, steps):
            parent_key = key.rsplit("_", 1)[0] if "_" in key else ""
            inserted[key] = self.step_tree.insert(inserted.get(parent_key, ""), "end", text=str(label), open=True)
        self.step_start.set((str(step_keys[0]).split("_")[0] if step_keys else "0") + " (_step_" + (str(step_keys[0]).split("_")[0] if step_keys else "0") + ")")
        self.step_loop.set("while self.alive" in self.editor.get("1.0", "end-1c"))
        self.special_step_list.delete(0, "end")
        for value in special_steps:
            self.special_step_list.insert("end", value)
        self.status.set("Loaded {} step(s) from current command".format(len(steps)))

    def _load_state_machine_steps(self, source):
        """Read self.STATE_*_FUNCTION dictionaries without rewriting the command."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False
        methods = {}
        method_dictionary_refs = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.setdefault(node.name, node.lineno)
                method_dictionary_refs[node.name] = {
                    child.attr for child in ast.walk(node)
                    if isinstance(child, ast.Attribute) and
                    isinstance(child.value, ast.Name) and child.value.id == "self" and
                    child.attr.startswith("STATE_") and child.attr.endswith("_FUNCTION")
                }
        dictionaries = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            target_names = [target.attr for target in node.targets
                            if isinstance(target, ast.Attribute) and
                            isinstance(target.value, ast.Name) and target.value.id == "self" and
                            target.attr.startswith("STATE_") and target.attr.endswith("_FUNCTION")]
            if not target_names:
                continue
            members = []
            for key, value in zip(node.value.keys, node.value.values):
                state_name = _literal_string(key)
                if state_name is None:
                    continue
                if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name) and value.value.id == "self":
                    members.append((state_name, value.attr, methods.get(value.attr, getattr(value, "lineno", 1))))
            if members:
                dictionaries.append((target_names[0], members))
        if not dictionaries:
            return False
        self.step_tree.delete(*self.step_tree.get_children())
        self.step_state_locations = {}
        self.step_state_original_names = {}
        self.step_state_dictionary_names = {}
        state_items_by_method = {}
        count = 0
        self._step_load_in_progress = True
        try:
            for dictionary_name, members in dictionaries:
                parent_candidates = list(dict.fromkeys(
                    state_items_by_method[method_name]
                    for method_name, references in method_dictionary_refs.items()
                    if dictionary_name in references and method_name in state_items_by_method
                ))
                parent = parent_candidates[0] if len(parent_candidates) == 1 else ""
                root = self.step_tree.insert(parent, "end", text=dictionary_name, open=False)
                self.step_state_dictionary_names[root] = dictionary_name
                for state_name, method_name, line_number in members:
                    item = self.step_tree.insert(root, "end", text="{} -> {}".format(state_name, method_name))
                    self.step_state_locations[item] = (method_name, line_number)
                    self.step_state_original_names[item] = state_name
                    state_items_by_method.setdefault(method_name, item)
                    count += 1
                    if count % 100 == 0:
                        self.status.set("Step階層を読み込み中... {}件".format(count))
                        self.update()
        finally:
            self._step_load_in_progress = False
        self.step_source_mode = "state_machine"
        self.special_step_list.delete(0, "end")
        self.status.set("Loaded {} state-machine transition(s), read-only hierarchy".format(count))
        return True

    def open_selected_state_method(self):
        selected = self.step_tree.selection()
        if not selected or selected[0] not in self.step_state_locations:
            messagebox.showinfo("Step hierarchy", "Select a state transition first.", parent=self)
            return
        method_name, line_number = self.step_state_locations[selected[0]]
        self.editor.mark_set("insert", "{}.0".format(line_number))
        self.editor.see("{}.0".format(line_number))
        self.editor.tag_remove("sel", "1.0", "end")
        self.editor.tag_add("sel", "{}.0".format(line_number), "{}.end".format(line_number))
        self.editor.focus_set()
        self.status.set("Opened {} at line {}".format(method_name, line_number))

    def apply_steps_to_editor(self):
        if self._step_load_in_progress:
            messagebox.showinfo("Step hierarchy", "Step階層の読み込み完了後に反映してください。", parent=self)
            return
        if self.step_source_mode == "state_machine":
            self.apply_state_machine_steps_to_editor()
            return
        steps = self._flatten_step_tree()
        if not steps:
            messagebox.showwarning("Step hierarchy", "Add at least one chapter or step.", parent=self)
            return
        try:
            tree = ast.parse(self.editor.get("1.0", "end-1c"))
            command = next(node for node in tree.body if isinstance(node, ast.ClassDef))
            name = next(ast.literal_eval(node.value) for node in command.body if isinstance(node, ast.Assign) and any(getattr(target, "id", "") == "NAME" for target in node.targets))
            tags = next(ast.literal_eval(node.value) for node in command.body if isinstance(node, ast.Assign) and any(getattr(target, "id", "") == "TAGS" for target in node.targets))
        except (SyntaxError, StopIteration, ValueError, TypeError):
            messagebox.showwarning("Step hierarchy", "Open a generated Step command first.", parent=self)
            return
        source_before = self.editor.get("1.0", "end-1c")
        custom_bodies = {}
        marker_pattern = re.compile(r"(?ms)^\s*# POKECON_STEP_USER_BEGIN ([^\r\n]+)\r?\n(.*?)^\s*# POKECON_STEP_USER_END \1\s*$")
        for match in marker_pattern.finditer(source_before):
            custom_bodies[match.group(1).strip()] = match.group(2)
        if not messagebox.askyesno("Apply Step hierarchy", "Rebuild the Step skeleton and keep marked user code for unchanged Step keys?", parent=self):
            return
        special_steps = list(self.special_step_list.get(0, "end"))
        source = template_source(self.step_template_mode.get(), command.name, name, tags, steps, self.step_loop.get(), step_start=int(self.step_start.get().split()[0]), special_steps=special_steps, step_custom_bodies=custom_bodies)
        self.set_editor_content(source, self.current_path)
        self.editor_dirty = True
        self.update_editor_view()
        self.status.set("Applied {} step(s). Save the command to keep them.".format(len(steps)))

    def _state_machine_tree_values(self):
        definitions = []
        renames = {}
        dictionary_names = getattr(self, "step_state_dictionary_names", {})
        roots = []
        def collect_dictionaries(parent=""):
            for item in self.step_tree.get_children(parent):
                if item in dictionary_names:
                    roots.append(item)
                collect_dictionaries(item)
        collect_dictionaries()
        for root in roots:
            dictionary_name = self.step_tree.item(root, "text").strip()
            if not re.match(r"^STATE_[A-Za-z0-9_]*_FUNCTION$", dictionary_name):
                raise ValueError("Invalid state dictionary name: " + dictionary_name)
            members = []
            for item in self.step_tree.get_children(root):
                if item in dictionary_names:
                    continue
                label = self.step_tree.item(item, "text").strip()
                match = re.match(r"^([^\s]+)\s*->\s*([A-Za-z_]\w*)$", label)
                if not match:
                    raise ValueError("Use STATE_NAME -> method_name: " + label)
                state_name, method_name = match.groups()
                members.append((state_name, method_name))
                old_name = self.step_state_original_names.get(item)
                if old_name and old_name != state_name:
                    renames[old_name] = state_name
            definitions.append((dictionary_name, members))
        return definitions, renames

    @staticmethod
    def _rename_state_literals(source, renames):
        if not renames:
            return source
        tokens = []
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.STRING:
                try:
                    value = ast.literal_eval(token.string)
                except (SyntaxError, ValueError):
                    value = None
                if isinstance(value, str) and value in renames:
                    token = tokenize.TokenInfo(token.type, repr(renames[value]), token.start, token.end, token.line)
            tokens.append(token)
        return tokenize.untokenize(tokens)

    @staticmethod
    def _assignment_end_line(lines, start_index):
        depth = 0
        started = False
        for index in range(start_index, len(lines)):
            code = lines[index].split("#", 1)[0]
            for character in code:
                if character in "([{":
                    depth += 1
                    started = True
                elif character in ")]}":
                    depth -= 1
            if started and depth <= 0:
                return index + 1
        return start_index + 1

    def apply_state_machine_steps_to_editor(self):
        try:
            definitions, renames = self._state_machine_tree_values()
            source = self.editor.get("1.0", "end-1c")
            tree = ast.parse(source)
        except (SyntaxError, ValueError) as error:
            messagebox.showwarning("Step hierarchy", str(error), parent=self)
            return
        methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        missing = sorted({method for _, members in definitions for _, method in members if method not in methods})
        if missing:
            state_for_method = {method: state for _, members in definitions for state, method in members}
            command = next((node for node in tree.body if isinstance(node, ast.ClassDef)), None)
            if command is None:
                messagebox.showwarning("Step hierarchy", "A command class is required.", parent=self)
                return
            source_lines = source.splitlines(True)
            insert_at = next((node.lineno - 1 for node in tree.body
                              if isinstance(node, ast.ClassDef) and node.lineno > command.lineno), len(source_lines))
            method_blocks = ["\n"]
            for method in missing:
                state = state_for_method[method]
                method_blocks.extend([
                    "    def {}(self):\n".format(method),
                    "        # POKECON_STATE_USER_BEGIN {}\n".format(state),
                    "        # Add this state's processing and return the next state name.\n",
                    "        return {!r}\n".format(state),
                    "        # POKECON_STATE_USER_END {}\n\n".format(state),
                ])
            source_lines[insert_at:insert_at] = method_blocks
            source = "".join(source_lines)
            tree = ast.parse(source)
        existing = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                    existing[target.attr] = node.lineno - 1
        lines = source.splitlines(True)
        replacements = []
        new_blocks = []
        for dictionary_name, members in definitions:
            block = ["        self.{} = {{\n".format(dictionary_name)]
            block.extend("            {!r}: self.{},\n".format(state, method) for state, method in members)
            block.append("        }\n")
            if dictionary_name in existing:
                start = existing[dictionary_name]
                replacements.append((start, self._assignment_end_line(lines, start), block))
            else:
                new_blocks.extend(block)
        for start, end, block in sorted(replacements, reverse=True):
            lines[start:end] = block
        source = "".join(lines)
        if new_blocks:
            parsed = ast.parse(source)
            initializer = next((node for node in ast.walk(parsed) if isinstance(node, ast.FunctionDef) and node.name == "__init__"), None)
            if initializer is None:
                messagebox.showwarning("Step hierarchy", "__init__ is required to add a new state dictionary.", parent=self)
                return
            source_lines = source.splitlines(True)
            insert_at = next((index for index in range(initializer.lineno, len(source_lines))
                              if source_lines[index].startswith("    def ")), len(source_lines))
            source_lines[insert_at:insert_at] = ["\n"] + new_blocks
            source = "".join(source_lines)
        source = self._rename_state_literals(source, renames)
        try:
            ast.parse(source)
        except SyntaxError as error:
            messagebox.showerror("Step hierarchy", "Generated state dictionaries are invalid: {}".format(error), parent=self)
            return
        if not messagebox.askyesno("Apply state machine", "Apply {} state dictionaries to the current source? Renamed state literals are updated too.".format(len(definitions)), parent=self):
            return
        self.set_editor_content(source, self.current_path)
        self.editor_dirty = True
        self.update_editor_view()
        self.load_steps_from_editor(silent=True)
        self.status.set("Applied {} state-machine dictionaries".format(len(definitions)))

    def _build_image_reference_tab(self, parent):
        self.image_reference_problems_only = tk.BooleanVar(value=True)
        self.image_reference_show_dynamic = tk.BooleanVar(value=True)
        self.image_reference_summary = tk.StringVar(
            value="開いている.pyの image_check 指定名を確認します。")
        self.image_reference_result = None
        self.image_reference_rows = {}
        self._image_reference_request = 0

        ttk.Label(
            parent,
            text=("開いているソース内の image_check(\"検知名\") と、同じソースに登録された"
                  " IMAGE_DETECTION_TARGETS を照合します。ソースは実行しません。"),
            foreground="#174a7e", justify="left", wraplength=430,
        ).pack(fill="x", padx=6, pady=(7, 4))
        controls = ttk.Frame(parent)
        controls.pack(fill="x", padx=6, pady=3)
        ttk.Checkbutton(
            controls, text="未登録のみ", variable=self.image_reference_problems_only,
            command=self.refresh_image_reference_results,
        ).pack(side="left")
        ttk.Checkbutton(
            controls, text="動的指定も表示", variable=self.image_reference_show_dynamic,
            command=self.refresh_image_reference_results,
        ).pack(side="left", padx=(4, 0))
        ttk.Button(
            controls, text="再チェック", command=self.run_image_reference_check,
        ).pack(side="right")
        self.image_reference_summary_label = ttk.Label(
            parent, textvariable=self.image_reference_summary, wraplength=430)
        self.image_reference_summary_label.pack(fill="x", padx=6, pady=(1, 4))

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=6)
        self.image_reference_tree = ttk.Treeview(
            tree_frame, columns=("status", "name", "line", "count"),
            show="headings", height=12, selectmode="extended")
        for column, label, width in (
                ("status", "状態", 85), ("name", "検知名／式", 210),
                ("line", "行", 55), ("count", "回数", 48)):
            self.image_reference_tree.heading(column, text=label)
            self.image_reference_tree.column(
                column, width=width, stretch=(column == "name"), anchor="w")
        self.image_reference_tree.tag_configure("missing", foreground="#b00020")
        self.image_reference_tree.tag_configure("available", foreground="#174a7e")
        self.image_reference_tree.tag_configure("dynamic", foreground="#9a4e00")
        self.image_reference_tree.tag_configure("ok", foreground="#176b2c")
        tree_y = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.image_reference_tree.yview)
        tree_x = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self.image_reference_tree.xview)
        self.image_reference_tree.configure(
            yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        self.image_reference_tree.grid(column=0, row=0, sticky="nsew")
        tree_y.grid(column=1, row=0, sticky="ns")
        tree_x.grid(column=0, row=1, sticky="ew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.image_reference_tree.bind(
            "<<TreeviewSelect>>", self.show_selected_image_reference_detail)
        self.image_reference_tree.bind(
            "<Double-Button-1>", self.go_to_selected_image_reference)

        detail_box = ttk.Labelframe(parent, text="判定内容")
        detail_box.pack(fill="both", padx=6, pady=5)
        self.image_reference_detail = tk.Text(
            detail_box, height=7, wrap="word", background="#fafafa")
        detail_scroll = ttk.Scrollbar(
            detail_box, orient="vertical", command=self.image_reference_detail.yview)
        self.image_reference_detail.configure(yscrollcommand=detail_scroll.set)
        self.image_reference_detail.pack(side="left", fill="both", expand=True)
        detail_scroll.pack(side="right", fill="y")
        self.image_reference_detail.configure(state="disabled")
        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=6, pady=(0, 7))
        ttk.Button(
            actions, text="使用行へ移動",
            command=self.go_to_selected_image_reference).pack(side="left")
        ttk.Button(
            actions, text="選択を登録",
            command=lambda: self.apply_missing_image_references(False)).pack(
                side="left", padx=(4, 0))
        ttk.Button(
            actions, text="登録可能をすべて登録",
            command=lambda: self.apply_missing_image_references(True)).pack(
                side="right")

    def run_image_reference_check(self, silent=False):
        if not hasattr(self, "image_reference_tree"):
            return
        source = self.editor.get("1.0", "end-1c")
        tab_id = self.active_editor_tab
        self._image_reference_request += 1
        request = self._image_reference_request

        def worker():
            result = audit_image_check_references(source)
            library = self._read_image_library()
            result["library_available_names"] = sorted(
                name for name, item in library.get("targets", {}).items()
                if isinstance(item, dict) and item.get("variants"))
            return result

        def completed(result):
            if request != self._image_reference_request or tab_id != self.active_editor_tab:
                return
            self.image_reference_result = result
            self.refresh_image_reference_results()
            missing_count = len(result.get("missing", []))
            if not silent:
                if missing_count:
                    self.status.set("画像検知名チェック: 未登録{}件".format(missing_count))
                else:
                    self.status.set("画像検知名チェック: 未登録はありません")

        def failed(error):
            if request != self._image_reference_request or tab_id != self.active_editor_tab:
                return
            self.image_reference_result = None
            self.image_reference_summary.set(
                "構文エラーのため検知名を確認できません: {}".format(error))
            self.image_reference_summary_label.configure(foreground="#b00020")
            self.right_tabs.tab(self.image_reference_tab, text="検知名チェック (?)")
            self.image_reference_tree.delete(*self.image_reference_tree.get_children())
            self._set_image_reference_detail(str(error))

        self.run_background(
            "image_reference_check_{}".format(request), "画像検知名を確認中",
            worker, completed, failed, busy_cursor=not silent)

    def refresh_image_reference_results(self):
        if not hasattr(self, "image_reference_tree"):
            return
        self.image_reference_tree.delete(*self.image_reference_tree.get_children())
        self.image_reference_rows = {}
        result = self.image_reference_result
        if result is None:
            return
        references = result.get("references", [])
        displayed = references
        if self.image_reference_problems_only.get():
            displayed = [row for row in references if row.get("status") == "missing"]
        available_names = set(result.get("library_available_names", []))
        for row in displayed:
            can_register = row.get("status") == "missing" and row.get("name") in available_names
            if can_register:
                status = "登録可能"
            else:
                status = "未登録" if row.get("status") == "missing" else row.get("resolved_by", "登録済み")
            iid = self.image_reference_tree.insert(
                "", "end", values=(status, row.get("name", ""), row.get("line", ""),
                                     row.get("count", 1)),
                tags=("available" if can_register else
                      ("missing" if row.get("status") == "missing" else "ok"),))
            self.image_reference_rows[iid] = dict(
                row, row_type="literal", library_available=can_register)
        if self.image_reference_show_dynamic.get():
            for row in result.get("dynamic", []):
                iid = self.image_reference_tree.insert(
                    "", "end", values=("確認不可", row.get("expression", "<動的指定>"),
                                         row.get("line", ""), 1), tags=("dynamic",))
                self.image_reference_rows[iid] = dict(row, row_type="dynamic")

        missing_count = len(result.get("missing", []))
        available_count = sum(
            1 for row in result.get("missing", []) if row.get("name") in available_names)
        dynamic_count = len(result.get("dynamic", []))
        reference_count = len(references)
        registered_count = len(result.get("target_names", []))
        set_count = len(result.get("set_names", []))
        exception_count = len(result.get("exception_names", []))
        if missing_count:
            self.image_reference_summary.set(
                "⚠ 未登録 {missing}件（DevStudioから登録可能 {available}件） / 参照名 {refs}件 / 動的指定 {dynamic}件\n"
                "登録: 画像検知 {targets}件・セット {sets}件・例外判定 {exceptions}件".format(
                    missing=missing_count, available=available_count,
                    refs=reference_count, dynamic=dynamic_count,
                    targets=registered_count, sets=set_count, exceptions=exception_count))
            self.image_reference_summary_label.configure(foreground="#b00020")
            self.right_tabs.tab(
                self.image_reference_tab,
                text="⚠ 検知名チェック ({})".format(missing_count))
        else:
            self.image_reference_summary.set(
                "未登録なし / 参照名 {refs}件 / 動的指定 {dynamic}件\n"
                "登録: 画像検知 {targets}件・セット {sets}件・例外判定 {exceptions}件".format(
                    refs=reference_count, dynamic=dynamic_count, targets=registered_count,
                    sets=set_count, exceptions=exception_count))
            self.image_reference_summary_label.configure(foreground="#176b2c")
            self.right_tabs.tab(self.image_reference_tab, text="検知名チェック")
        self._set_image_reference_detail(
            "未登録の検知名を選ぶと使用行を確認できます。動的指定は実行時に値が決まるため、静的には登録確認できません。")

    def _set_image_reference_detail(self, value):
        self.image_reference_detail.configure(state="normal")
        self.image_reference_detail.delete("1.0", "end")
        self.image_reference_detail.insert("1.0", str(value))
        self.image_reference_detail.configure(state="disabled")

    def _selected_image_reference_row(self):
        selected = self.image_reference_tree.selection()
        return self.image_reference_rows.get(selected[0]) if selected else None

    def show_selected_image_reference_detail(self, event=None):
        row = self._selected_image_reference_row()
        if not row:
            return
        if row.get("row_type") == "dynamic":
            text = ("行 {line}: image_check({expression})\n\n"
                    "変数・式による動的指定のため、実行せずに登録名との一致を確定できません。".format(
                        line=row.get("line", "?"), expression=row.get("expression", "")))
        elif row.get("status") == "missing":
            availability = ("DevStudioの画像検知設定から登録できます。"
                            if row.get("library_available") else
                            "DevStudioの画像検知設定にも同名登録がありません。")
            text = ("未登録: {name}\n使用行: {lines}\n\n{availability}\n\n"
                    "この名前は IMAGE_DETECTION_TARGETS / IMAGE_DETECTION_SETS / "
                    "image_check_exception のいずれにも登録されていません。".format(
                        name=row.get("name", ""),
                        lines=", ".join(str(line) for line in row.get("lines", [])),
                        availability=availability))
        else:
            text = ("登録済み: {name}\n判定元: {resolved}\n使用行: {lines}".format(
                name=row.get("name", ""), resolved=row.get("resolved_by", ""),
                lines=", ".join(str(line) for line in row.get("lines", []))))
        self._set_image_reference_detail(text)

    def go_to_selected_image_reference(self, event=None):
        row = self._selected_image_reference_row()
        if not row:
            return
        line = int(row.get("line", 1))
        self.editor.mark_set("insert", "{}.0".format(line))
        self.editor.see("{}.0".format(line))
        self.editor.focus_set()
        self.status.set("画像検知の使用行へ移動しました: {}行".format(line))

    def apply_missing_image_references(self, apply_all=False):
        result = self.image_reference_result or {}
        available = set(result.get("library_available_names", []))
        if apply_all:
            names = [row.get("name") for row in result.get("missing", [])
                     if row.get("name") in available]
        else:
            names = []
            for iid in self.image_reference_tree.selection():
                row = self.image_reference_rows.get(iid, {})
                if row.get("row_type") == "literal" and row.get("status") == "missing" \
                        and row.get("library_available"):
                    names.append(row.get("name"))
        names = list(dict.fromkeys(name for name in names if name))
        if not names:
            messagebox.showinfo(
                "画像検知名チェック",
                "DevStudioから登録できる未登録名を選択してください。",
                parent=self)
            return
        if not messagebox.askyesno(
                "画像検知をソースへ登録",
                "次の{}件を、開いているソースへ登録しますか？\n\n{}\n\n"
                "既存の画像検知設定は保持され、ソースは未保存状態になります。".format(
                    len(names), "\n".join(names)), parent=self):
            return
        source = self.editor.get("1.0", "end-1c")
        try:
            updated, added = merge_library_targets_into_source(
                source, self._read_image_library(), names)
        except (SyntaxError, ValueError) as error:
            messagebox.showwarning("画像検知をソースへ登録", str(error), parent=self)
            return
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", updated)
        self.editor_dirty = True
        self.editor.edit_modified(False)
        if self.active_editor_tab in self.editor_documents:
            self.editor_documents[self.active_editor_tab].update(
                {"content": updated, "dirty": True})
        self.update_editor_view()
        self.status.set("DevStudioから画像検知{}件をソースへ登録しました。保存してください。".format(len(added)))
        self.debounce(
            "image_reference_after_apply", 100,
            lambda: self.run_image_reference_check(silent=True))

    def _build_image_health_tab(self, parent):
        self.image_health_reference = tk.StringVar(value="1280x720")
        self.image_health_problems_only = tk.BooleanVar(value=True)
        self.image_health_show_ignored = tk.BooleanVar(value=False)
        self.image_health_summary = tk.StringVar(value="［一括チェック］を押すと登録画像を検査します。")
        self.image_health_results = []
        self.image_health_tree_rows = {}

        ttk.Label(
            parent,
            text="登録画像を実行前に検査します。画像ファイルは変更せず、修正可能な検知範囲だけ確認後に更新します。",
            foreground="#174a7e", justify="left", wraplength=430,
        ).pack(fill="x", padx=6, pady=(7, 4))
        controls = ttk.Frame(parent)
        controls.pack(fill="x", padx=6, pady=3)
        ttk.Label(controls, text="基準画面:").pack(side="left")
        ttk.Entry(controls, textvariable=self.image_health_reference, width=11).pack(
            side="left", padx=(3, 7))
        ttk.Checkbutton(
            controls, text="問題のみ", variable=self.image_health_problems_only,
            command=self.refresh_image_health_results,
        ).pack(side="left")
        ttk.Checkbutton(
            controls, text="除外済みも表示", variable=self.image_health_show_ignored,
            command=self.refresh_image_health_results,
        ).pack(side="left", padx=(4, 0))
        ttk.Button(controls, text="一括チェック", command=self.run_image_health_check).pack(
            side="right")
        ttk.Label(parent, textvariable=self.image_health_summary, wraplength=430).pack(
            fill="x", padx=6, pady=(1, 4))

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=6)
        self.image_health_tree = ttk.Treeview(
            tree_frame, columns=("status", "name", "size", "crop"),
            show="headings", height=10, selectmode="browse")
        for column, label, width in (
                ("status", "結果", 52), ("name", "検知名", 190),
                ("size", "画像", 80), ("crop", "検知範囲", 90)):
            self.image_health_tree.heading(column, text=label)
            self.image_health_tree.column(column, width=width, stretch=(column == "name"))
        self.image_health_tree.tag_configure("error", foreground="#b00020")
        self.image_health_tree.tag_configure("warning", foreground="#9a4e00")
        self.image_health_tree.tag_configure("ok", foreground="#176b2c")
        self.image_health_tree.tag_configure("ignored", foreground="#666666")
        tree_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.image_health_tree.yview)
        tree_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.image_health_tree.xview)
        self.image_health_tree.configure(
            yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        self.image_health_tree.grid(column=0, row=0, sticky="nsew")
        tree_y.grid(column=1, row=0, sticky="ns")
        tree_x.grid(column=0, row=1, sticky="ew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.image_health_tree.bind(
            "<<TreeviewSelect>>", self.show_selected_image_health_detail)

        detail_box = ttk.Labelframe(parent, text="原因と直し方")
        detail_box.pack(fill="both", padx=6, pady=5)
        self.image_health_detail = tk.Text(
            detail_box, height=9, wrap="word", background="#fafafa")
        detail_scroll = ttk.Scrollbar(
            detail_box, orient="vertical", command=self.image_health_detail.yview)
        self.image_health_detail.configure(yscrollcommand=detail_scroll.set)
        self.image_health_detail.pack(side="left", fill="both", expand=True)
        detail_scroll.pack(side="right", fill="y")
        self.image_health_detail.configure(state="disabled")

        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=6, pady=(0, 7))
        ttk.Button(
            actions, text="画像検知タブで調整",
            command=self.open_selected_image_health_editor).pack(side="left")
        ttk.Button(
            actions, text="範囲を自動修正",
            command=self.repair_selected_image_health_crop).pack(side="left", padx=3)
        ttk.Button(
            actions, text="警告を除外／解除",
            command=self.toggle_selected_image_health_warning).pack(side="left", padx=3)

    def _image_health_frame_size(self):
        value = self.image_health_reference.get().strip()
        match = re.match(r"^(\d+)\s*[xX,×]\s*(\d+)$", value)
        if not match or int(match.group(1)) <= 0 or int(match.group(2)) <= 0:
            raise ValueError("基準画面は 1280x720 の形式で指定してください。")
        return int(match.group(1)), int(match.group(2))

    def run_image_health_check(self):
        if not hasattr(self, "image_health_tree"):
            return
        try:
            frame_size = self._image_health_frame_size()
        except ValueError as error:
            messagebox.showwarning("画像チェック", str(error), parent=self)
            return
        template_root = self.template_root()

        def worker():
            return audit_image_library(
                self._read_image_library(), template_root, frame_size)

        def completed(rows):
            self.image_health_results = rows
            self.refresh_image_health_results()
            self.status.set("登録画像のチェックが完了しました: {}件".format(len(rows)))

        self.run_background(
            "image_health_check", "登録画像をチェック中", worker, completed,
            lambda error: messagebox.showerror("画像チェック", str(error), parent=self))

    def refresh_image_health_results(self):
        if not hasattr(self, "image_health_tree"):
            return
        self.image_health_tree.delete(*self.image_health_tree.get_children())
        self.image_health_tree_rows = {}
        rows = list(getattr(self, "image_health_results", []))
        displayed = [row for row in rows if (
            (not self.image_health_problems_only.get()
             and row.get("status") != "除外")
            or row.get("status") in ("エラー", "警告")
            or (self.image_health_show_ignored.get()
                and row.get("status") == "除外"))]
        for row_index, row in enumerate(rows):
            if row not in displayed:
                continue
            image_size = row.get("image_size")
            crop_size = row.get("crop_size")
            name = row.get("name", "")
            if isinstance(row.get("index"), int):
                name += " / パターン{}".format(row["index"] + 1)
            iid = self.image_health_tree.insert(
                "", "end", values=(
                    row.get("status", ""), name,
                    "{}x{}".format(*image_size) if image_size else "-",
                    "{}x{}".format(*crop_size) if crop_size else "-"),
                tags=({"エラー": "error", "警告": "warning", "除外": "ignored"}.get(
                    row.get("status"), "ok"),))
            self.image_health_tree_rows[iid] = row_index
        counts = {name: sum(1 for row in rows if row.get("status") == name)
                  for name in ("エラー", "警告", "正常", "除外")}
        self.image_health_summary.set(
            "エラー {error}件 / 警告 {warning}件 / 除外 {ignored}件 / 正常 {ok}件（表示 {shown}件）".format(
                error=counts["エラー"], warning=counts["警告"],
                ignored=counts["除外"], ok=counts["正常"], shown=len(displayed)))
        self._set_image_health_detail(
            "問題行を選ぶと、例外の原因と修正方法をここに表示します。")

    def _set_image_health_detail(self, value):
        self.image_health_detail.configure(state="normal")
        self.image_health_detail.delete("1.0", "end")
        self.image_health_detail.insert("1.0", str(value))
        self.image_health_detail.configure(state="disabled")

    def _selected_image_health_row(self):
        selected = self.image_health_tree.selection()
        if not selected:
            return None
        index = self.image_health_tree_rows.get(selected[0])
        if index is None or not 0 <= index < len(self.image_health_results):
            return None
        return self.image_health_results[index]

    def show_selected_image_health_detail(self, event=None):
        row = self._selected_image_health_row()
        if not row:
            return
        lines = ["{}: {}".format(row.get("status", ""), row.get("name", ""))]
        if isinstance(row.get("index"), int):
            lines[0] += " / パターン{}".format(row["index"] + 1)
        if row.get("path"):
            lines.append("画像: " + row["path"])
        if row.get("image_size"):
            lines.append("画像サイズ: {}x{}".format(*row["image_size"]))
        if row.get("crop_size"):
            lines.append("検知範囲サイズ: {}x{}".format(*row["crop_size"]))
        lines.append("\n［検出内容］")
        lines.extend("・" + value for value in row.get("details", []))
        if row.get("fixes"):
            lines.append("\n［直し方］")
            lines.extend("・" + value for value in row["fixes"])
        if row.get("repairable"):
            lines.append("\nこの問題は［範囲を自動修正］で設定だけ修正できます。")
        if row.get("warning_codes"):
            lines.append("\n意図的な単色画像なら［警告を除外／解除］でこの画像だけ除外できます。")
        elif row.get("ignored_warning_codes"):
            lines.append("\nこの画像では警告を除外中です。同じボタンで解除できます。")
        self._set_image_health_detail("\n".join(lines))

    def open_selected_image_health_editor(self):
        row = self._selected_image_health_row()
        if not row or not isinstance(row.get("index"), int):
            messagebox.showinfo(
                "画像チェック", "編集する画像パターンを選択してください。", parent=self)
            return
        data = self._read_image_library()
        name, index = row["name"], row["index"]
        if name not in data.get("targets", {}) or index >= len(data["targets"][name].get("variants", [])):
            messagebox.showwarning(
                "画像チェック", "登録内容が更新されています。再チェックしてください。", parent=self)
            return
        self.workspace_tabs.select(self.image_library_workspace)
        self.refresh_image_library_workspace(select=(name, index))
        self.load_selected_image_library_variant()

    def repair_selected_image_health_crop(self):
        row = self._selected_image_health_row()
        if not row or not isinstance(row.get("index"), int):
            messagebox.showinfo("画像チェック", "修正する画像パターンを選択してください。", parent=self)
            return
        if not row.get("repairable"):
            messagebox.showinfo(
                "画像チェック",
                "この問題は範囲だけでは安全に直せません。［画像検知タブで調整］から直してください。",
                parent=self)
            return
        data = self._read_image_library()
        name, index = row["name"], row["index"]
        try:
            variant = data["targets"][name]["variants"][index]
            old_crop = list(variant.get("crop", [0, 0, 0, 0]))
            new_crop = suggested_crop(
                old_crop, row["image_size"], self._image_health_frame_size())
        except (KeyError, IndexError, TypeError, ValueError) as error:
            messagebox.showwarning("画像チェック", str(error), parent=self)
            return
        if old_crop == new_crop:
            messagebox.showinfo("画像チェック", "検知範囲の変更は不要です。", parent=self)
            return
        if not messagebox.askyesno(
                "検知範囲の自動修正",
                "{} / パターン{}\n\n{} → {}\n\n画像ファイルは変更せず、検知範囲だけ更新しますか？".format(
                    name, index + 1, ",".join(map(str, old_crop)),
                    ",".join(map(str, new_crop))), parent=self):
            return
        variant["crop"] = new_crop
        save_image_library(self._image_library_config_path(), data)
        self.refresh_image_library_workspace(select=(name, index))
        self.run_image_health_check()

    def toggle_selected_image_health_warning(self):
        row = self._selected_image_health_row()
        if not row or not isinstance(row.get("index"), int):
            messagebox.showinfo("画像チェック", "警告のある画像パターンを選択してください。", parent=self)
            return
        active = list(row.get("warning_codes", []))
        ignored = list(row.get("ignored_warning_codes", []))
        if not active and not ignored:
            messagebox.showinfo("画像チェック", "この画像に除外可能な警告はありません。", parent=self)
            return
        data = self._read_image_library()
        name, index = row["name"], row["index"]
        try:
            variant = data["targets"][name]["variants"][index]
        except (KeyError, IndexError, TypeError):
            messagebox.showwarning("画像チェック", "登録内容が更新されています。再チェックしてください。", parent=self)
            return
        configured = {str(value) for value in variant.get("health_ignored_warnings", [])}
        if active:
            action = "除外"
            changed_codes = active
            configured.update(active)
            question = (
                "{} / パターン{}\n\nこの画像だけ警告を除外しますか？\n"
                "文字画面の色判定など、意図的な単色画像に使用してください。").format(name, index + 1)
        else:
            action = "除外解除"
            changed_codes = ignored
            configured.difference_update(ignored)
            question = "{} / パターン{} の警告除外を解除しますか？".format(name, index + 1)
        if not messagebox.askyesno("画像警告の" + action, question, parent=self):
            return
        if configured:
            variant["health_ignored_warnings"] = sorted(configured)
        else:
            variant.pop("health_ignored_warnings", None)
        save_image_library(self._image_library_config_path(), data)
        self.status.set("{}: {} / {}".format(action, name, ", ".join(changed_codes)))
        self.run_image_health_check()

    def _build_image_targets_tab(self, parent):
        self.image_rename_calls = tk.BooleanVar(value=True)
        self.image_management_tabs = ttk.Notebook(parent)
        self.image_management_tabs.pack(fill="both", expand=True)
        command_tab = ttk.Frame(self.image_management_tabs)
        registered_tab = ttk.Frame(self.image_management_tabs)
        exception_tab = ttk.Frame(self.image_management_tabs)
        self.image_management_tabs.add(command_tab, text="ソース対象")
        self.image_management_tabs.add(registered_tab, text="登録済み画像検知")
        self.image_management_tabs.add(exception_tab, text="例外設定")
        self.registered_image_management_tab = registered_tab
        self.image_exception_management_tab = exception_tab
        self._registered_image_management_loaded = False
        self._build_command_image_targets_tab(command_tab)
        self._build_registered_image_management_tab(registered_tab)
        self._build_image_exception_management_tab(exception_tab)
        self.image_management_tabs.bind(
            "<<NotebookTabChanged>>", self._on_image_management_tab_changed)

    def _build_command_image_targets_tab(self, parent):
        self.image_detection_targets = []
        self.image_target_name = tk.StringVar(value="target")
        self.image_target_path = tk.StringVar()
        self.image_target_threshold = tk.DoubleVar(value=0.80)
        self.image_target_roi = tk.StringVar(value="0,0,0,0")
        self.image_target_gray = tk.BooleanVar(value=False)
        self.image_target_resolution = tk.StringVar(value="0,0")
        self.image_target_description = tk.StringVar()
        self.image_target_edit_mode = tk.StringVar(value="新規追加モード")
        ttk.Label(parent, text="Targets for the command currently open in Editor. They run only in Image match debug.").grid(column=0, columnspan=6, row=0, padx=7, pady=(7, 3), sticky="w")
        ttk.Button(parent, text="Load current command", command=self.load_image_targets_from_editor).grid(column=6, row=0, padx=5, pady=(7, 3), sticky="e")
        ttk.Label(parent, text="Name:").grid(column=0, row=1, padx=(7, 2), pady=3, sticky="w")
        ttk.Entry(parent, textvariable=self.image_target_name, width=16).grid(column=1, row=1, padx=2, pady=3, sticky="ew")
        ttk.Label(parent, text="Image:").grid(column=2, row=1, padx=(5, 2), pady=3, sticky="w")
        ttk.Entry(parent, textvariable=self.image_target_path).grid(column=3, columnspan=3, row=1, padx=2, pady=3, sticky="ew")
        ttk.Button(parent, text="Browse", command=self.choose_image_target).grid(column=6, row=1, padx=5, pady=3)
        ttk.Label(parent, text="Threshold:").grid(column=0, row=2, padx=(7, 2), pady=3, sticky="w")
        ttk.Spinbox(parent, from_=0.0, to=1.0, increment=0.01, textvariable=self.image_target_threshold, width=8).grid(column=1, row=2, padx=2, pady=3, sticky="w")
        ttk.Label(parent, text="ROI x,y,w,h:").grid(column=2, row=2, padx=(5, 2), pady=3, sticky="w")
        ttk.Entry(parent, textvariable=self.image_target_roi, width=16).grid(column=3, row=2, padx=2, pady=3, sticky="w")
        ttk.Checkbutton(parent, text="Monochrome", variable=self.image_target_gray).grid(column=4, row=2, padx=5, pady=3, sticky="w")
        ttk.Label(parent, text="Reference w,h:").grid(column=5, row=2, padx=(5, 2), pady=3, sticky="w")
        ttk.Entry(parent, textvariable=self.image_target_resolution, width=12).grid(column=6, row=2, padx=2, pady=3, sticky="w")
        ttk.Label(parent, text="説明:").grid(column=0, row=3, padx=(7, 2), pady=3, sticky="w")
        ttk.Entry(parent, textvariable=self.image_target_description).grid(column=1, columnspan=6, row=3, padx=2, pady=3, sticky="ew")
        target_tree_frame = ttk.Frame(parent)
        target_tree_frame.grid(
            column=0, columnspan=7, row=4, padx=7, pady=(5, 5),
            sticky="nsew")
        self.image_target_tree = ttk.Treeview(target_tree_frame, columns=("name", "description", "image", "threshold", "roi", "mode", "resolution"), show="headings", height=12)
        for column, label, width in (("name", "Name", 110), ("description", "説明", 170), ("image", "Image", 300), ("threshold", "Threshold", 72), ("roi", "ROI", 100), ("mode", "Mode", 82), ("resolution", "Reference", 95)):
            self.image_target_tree.heading(column, text=label)
            self.image_target_tree.column(column, width=width, stretch=(column == "image"))
        pack_scrollable_widget(self.image_target_tree, horizontal=True)
        self.image_target_tree.bind("<<TreeviewSelect>>", self.load_selected_image_target)
        self.image_target_tree.bind("<Double-1>", self.enter_selected_image_target_change_mode)
        controls = ttk.Frame(parent)
        controls.grid(column=0, columnspan=7, row=5, padx=7, pady=(0, 6), sticky="ew")
        target_actions = ttk.Frame(controls); target_actions.pack(fill="x")
        ttk.Label(target_actions, textvariable=self.image_target_edit_mode).pack(side="left", padx=(0, 8))
        ttk.Button(target_actions, text="新規追加", command=self.add_image_target).pack(side="left", padx=2)
        ttk.Button(target_actions, text="選択内容を変更", command=self.change_image_target).pack(side="left", padx=2)
        ttk.Button(target_actions, text="ソース対象から外す", command=self.remove_image_target).pack(side="left", padx=2)
        library_actions = ttk.Frame(controls); library_actions.pack(fill="x", pady=(3, 0))
        ttk.Button(library_actions, text="単品画像検知として登録", command=self.register_current_image_target).pack(side="left", padx=2)
        ttk.Button(library_actions, text="登録済みから追加/削除", command=self.open_registered_image_target_dialog).pack(side="left", padx=2)
        ttk.Button(library_actions, text="現在のコマンドへ反映", command=self.apply_image_targets_to_editor).pack(side="right", padx=2)
        parent.columnconfigure(3, weight=1)
        parent.rowconfigure(4, weight=1)

    def _build_registered_image_management_tab(self, parent):
        self.registered_image_search = tk.StringVar()
        search = ttk.Frame(parent)
        search.pack(fill="x", padx=6, pady=(6, 3))
        ttk.Label(search, text="登録名・説明・画像検索:").pack(side="left")
        ttk.Entry(search, textvariable=self.registered_image_search).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(
            search, text="再読込",
            command=self.refresh_registered_image_management).pack(side="right")
        self.registered_image_search.trace_add(
            "write", lambda *args: self.debounce(
                "registered_image_management", 120,
                self.refresh_registered_image_management))

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=6, pady=3)
        self.registered_image_tree = ttk.Treeview(
            tree_frame, columns=("description", "patterns", "operator"),
            show="tree headings", selectmode="browse")
        self.registered_image_tree.heading("#0", text="画像検知名")
        self.registered_image_tree.heading("description", text="説明")
        self.registered_image_tree.heading("patterns", text="画像数")
        self.registered_image_tree.heading("operator", text="判定")
        self.registered_image_tree.column("#0", width=220)
        self.registered_image_tree.column("description", width=260)
        self.registered_image_tree.column("patterns", width=55, anchor="center")
        self.registered_image_tree.column("operator", width=50, anchor="center")
        pack_scrollable_widget(self.registered_image_tree, horizontal=True)
        self.registered_image_tree.bind(
            "<Double-1>", lambda _event: self.open_registered_image_detail())

        rename_row = ttk.Frame(parent)
        rename_row.pack(fill="x", padx=6, pady=(2, 0))
        ttk.Checkbutton(
            rename_row, text="名称変更時にimage_check呼び出し側も変更",
            variable=self.image_rename_calls).pack(side="left")
        ttk.Button(
            rename_row, text="呼び出し名を変更",
            command=self.rename_registered_image_detection).pack(side="right")

        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=6, pady=(3, 6))
        ttk.Button(
            actions, text="新規追加（詳細設定へ）",
            command=lambda: self.open_registered_image_detail(new=True)).pack(
                side="left", padx=2)
        ttk.Button(
            actions, text="選択を変更（詳細設定へ）",
            command=self.open_registered_image_detail).pack(side="left", padx=2)
        ttk.Button(actions, text="ソースを保存", command=self.save_current).pack(
            side="right", padx=2)
        ttk.Button(
            actions, text="選択登録を削除",
            command=self.delete_registered_image_detection).pack(side="right", padx=2)

    def _build_image_exception_management_tab(self, parent):
        self.image_exception_name = tk.StringVar()
        self.image_exception_expression = tk.StringVar(value="False")
        form = ttk.Labelframe(parent, text="image_check_exception 設定")
        form.pack(fill="x", padx=6, pady=6)
        ttk.Label(form, text="呼び出し名:").grid(
            column=0, row=0, padx=4, pady=4, sticky="w")
        ttk.Entry(form, textvariable=self.image_exception_name).grid(
            column=1, row=0, padx=4, pady=4, sticky="ew")
        ttk.Label(form, text="戻り値式:").grid(
            column=0, row=1, padx=4, pady=4, sticky="w")
        ttk.Entry(form, textvariable=self.image_exception_expression).grid(
            column=1, row=1, padx=4, pady=4, sticky="ew")
        ttk.Checkbutton(
            form, text="名称変更時にimage_check呼び出し側も変更",
            variable=self.image_rename_calls).grid(
                column=0, columnspan=2, row=2, padx=4, pady=2, sticky="w")
        form.columnconfigure(1, weight=1)

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=6, pady=3)
        self.image_exception_tree = ttk.Treeview(
            tree_frame, columns=("expression", "line"),
            show="tree headings", selectmode="browse")
        self.image_exception_tree.heading("#0", text="例外の呼び出し名")
        self.image_exception_tree.heading("expression", text="戻り値式")
        self.image_exception_tree.heading("line", text="行")
        self.image_exception_tree.column("#0", width=270)
        self.image_exception_tree.column("expression", width=360)
        self.image_exception_tree.column("line", width=55, anchor="e")
        pack_scrollable_widget(self.image_exception_tree, horizontal=True)
        self.image_exception_tree.bind(
            "<<TreeviewSelect>>", self.load_selected_image_exception)
        self.image_exception_tree.bind(
            "<Double-1>", lambda _event: self.goto_selected_image_exception())

        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=6, pady=(3, 6))
        ttk.Button(actions, text="新規追加", command=self.add_image_exception).pack(
            side="left", padx=2)
        ttk.Button(actions, text="選択内容を変更", command=self.change_image_exception).pack(
            side="left", padx=2)
        ttk.Button(actions, text="選択を削除", command=self.remove_image_exception).pack(
            side="left", padx=2)
        ttk.Button(
            actions, text="同名画像検知の詳細",
            command=self.open_exception_image_detail).pack(side="left", padx=8)
        ttk.Button(actions, text="ソースを保存", command=self.save_current).pack(
            side="right", padx=2)

    def _on_image_management_tab_changed(self, event=None):
        if not hasattr(self, "image_management_tabs"):
            return
        selected = self.image_management_tabs.select()
        if selected == str(self.registered_image_management_tab):
            self._registered_image_management_loaded = True
            self.refresh_registered_image_management()
        elif selected == str(self.image_exception_management_tab):
            self.refresh_image_exception_management()

    def _selected_registered_image_name(self, required=True):
        selected = self.registered_image_tree.selection()
        name = self.registered_image_tree_ids.get(selected[0]) \
            if selected else None
        if required and not name:
            messagebox.showinfo(
                "登録済み画像検知", "画像検知名を選択してください。", parent=self)
        return name

    def refresh_registered_image_management(self, select=None):
        if not hasattr(self, "registered_image_tree"):
            return
        current = select or self._selected_registered_image_name(required=False)
        data = self._read_image_library()
        needle = self.registered_image_search.get().strip().casefold()
        self.registered_image_tree.delete(
            *self.registered_image_tree.get_children())
        self.registered_image_tree_ids = {}
        for index, name in enumerate(sorted(data["targets"], key=str.casefold)):
            item = data["targets"][name]
            searchable = " ".join(
                [name, item.get("description", "")] +
                [str(variant.get("template_path", ""))
                 for variant in item.get("variants", [])]).casefold()
            if needle and needle not in searchable:
                continue
            iid = "registered_{}".format(index)
            self.registered_image_tree.insert(
                "", "end", iid=iid, text=name,
                values=(item.get("description", ""),
                        len(item.get("variants", [])),
                        item.get("operator", "OR")))
            self.registered_image_tree_ids[iid] = name
            if name == current:
                self.registered_image_tree.selection_set(iid)
                self.registered_image_tree.see(iid)

    def open_registered_image_detail(self, new=False, name=None):
        if not new:
            name = name or self._selected_registered_image_name()
            if not name:
                return
        self.workspace_tabs.select(self.image_library_workspace)
        self._image_library_workspace_loaded = True
        if new:
            self.image_library_selected_variant = None
            self.image_library_search.set("")
            self.image_library_name.set("NEW_IMAGE_CHECK")
            self.image_library_description.set("")
            self.image_library_path.set("")
            self.image_library_threshold.set(0.8)
            self.image_library_crop.set("0,0,0,0")
            self.image_library_gray.set(True)
            self._clear_image_library_preview(
                "画像を選択し、設定後に［＋別パターンとして保存］を押してください。")
            self.refresh_image_library_workspace()
            self.status.set("新しい画像検知の詳細設定を開きました。")
            return
        data = self._read_image_library()
        if name not in data["targets"] or not data["targets"][name].get("variants"):
            messagebox.showwarning(
                "登録済み画像検知", "登録画像がありません: " + name,
                parent=self)
            return
        self.image_library_search.set(name)
        pending = getattr(self, "_debounce_jobs", {}).pop(
            "image_library_search", None)
        if pending is not None:
            try:
                self.after_cancel(pending)
            except tk.TclError:
                pass
        self.refresh_image_library_workspace(select=(name, 0))
        self.load_selected_image_library_variant()
        self.status.set("画像検知の詳細設定を開きました: " + name)

    def _replace_current_editor_source(self, source):
        cursor = self.editor.index("insert")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", source)
        try:
            self.editor.mark_set("insert", cursor)
        except tk.TclError:
            self.editor.mark_set("insert", "1.0")
        self.editor_dirty = True
        if self.active_editor_tab in self.editor_documents:
            document = self.editor_documents[self.active_editor_tab]
            document["content"] = source
            document["dirty"] = True
            self.editor_tabs.tab(
                self.active_editor_tab, text=self._editor_tab_label(document))
        self.update_editor_view()

    def rename_registered_image_detection(self):
        old_name = self._selected_registered_image_name()
        if not old_name:
            return
        new_name = simpledialog.askstring(
            "画像検知の呼び出し名を変更",
            "変更後の呼び出し名:\n\n設定・画像検知リストも同時に更新します。",
            initialvalue=old_name, parent=self)
        if new_name is None:
            return
        new_name = new_name.strip()
        source = self.editor.get("1.0", "end-1c")
        updated_source, changed = source, 0
        try:
            if self.image_rename_calls.get() and source.strip():
                updated_source, changed = rename_image_check_references(
                    source, old_name, new_name, include_definitions=True)
            data = self._read_image_library()
            rename_image_library_target(data, old_name, new_name)
        except (ValueError, SyntaxError) as error:
            messagebox.showwarning(
                "画像検知の呼び出し名を変更", str(error), parent=self)
            return
        save_image_library(self._image_library_config_path(), data)
        if updated_source != source:
            self._replace_current_editor_source(updated_source)
        self.refresh_registered_image_management(select=new_name)
        self.refresh_sample_apply_image_tree()
        if getattr(self, "_image_library_workspace_loaded", False):
            self.refresh_image_library_workspace()
        suffix = " / ソース内{}箇所も変更（未保存）".format(changed) \
            if changed else ""
        self.status.set(
            "画像検知名を変更しました: {} → {}{}".format(
                old_name, new_name, suffix))

    def delete_registered_image_detection(self):
        name = self._selected_registered_image_name()
        if not name:
            return
        try:
            result = audit_image_check_references(
                self.editor.get("1.0", "end-1c"))
            use_count = next((item["count"] for item in result["references"]
                              if item["name"] == name), 0)
        except SyntaxError:
            use_count = 0
        warning = "\n\n編集中ソースのimage_check呼び出し{}件は残ります。".format(
            use_count) if use_count else ""
        if not messagebox.askyesno(
                "登録済み画像検知を削除",
                "{} の全パターンとリスト参照を削除しますか？{}".format(
                    name, warning), parent=self):
            return
        data = self._read_image_library()
        data["targets"].pop(name, None)
        for item in data["lists"].values():
            item["members"] = [
                member for member in item.get("members", [])
                if not (member.get("type") == "target"
                        and member.get("id") == name)]
        save_image_library(self._image_library_config_path(), data)
        self.refresh_registered_image_management()
        self.refresh_sample_apply_image_tree()
        if getattr(self, "_image_library_workspace_loaded", False):
            self.refresh_image_library_workspace()
        self.status.set("登録済み画像検知を削除しました: " + name)

    def refresh_image_exception_management(self, select=None):
        if not hasattr(self, "image_exception_tree"):
            return
        current = select
        if current is None:
            selected = self.image_exception_tree.selection()
            current = self.image_exception_tree_ids.get(selected[0], {}).get(
                "name") if selected else None
        try:
            rules = image_check_exception_rules(
                self.editor.get("1.0", "end-1c"))
        except SyntaxError as error:
            self.status.set("例外設定を読めません: " + str(error))
            return
        self.image_exception_tree.delete(
            *self.image_exception_tree.get_children())
        self.image_exception_tree_ids = {}
        for index, rule in enumerate(rules):
            iid = "exception_{}".format(index)
            self.image_exception_tree.insert(
                "", "end", iid=iid, text=rule["name"],
                values=(rule["expression"], rule["line"]))
            self.image_exception_tree_ids[iid] = rule
            if rule["name"] == current:
                self.image_exception_tree.selection_set(iid)
                self.image_exception_tree.see(iid)

    def _selected_image_exception(self, required=True):
        selected = self.image_exception_tree.selection()
        rule = self.image_exception_tree_ids.get(selected[0]) \
            if selected else None
        if required and not rule:
            messagebox.showinfo(
                "画像検知の例外設定", "例外設定を選択してください。", parent=self)
        return rule

    def load_selected_image_exception(self, event=None):
        rule = self._selected_image_exception(required=False)
        if not rule:
            return
        self.image_exception_name.set(rule["name"])
        self.image_exception_expression.set(rule["expression"])

    def goto_selected_image_exception(self):
        rule = self._selected_image_exception()
        if not rule:
            return
        line = max(1, int(rule["line"]))
        self.editor.mark_set("insert", "{}.0".format(line))
        self.editor.see("{}.0".format(line))
        self.editor.focus_set()

    def _apply_image_exception_change(self, old_name=None):
        name = self.image_exception_name.get().strip()
        expression = self.image_exception_expression.get().strip()
        source = self.editor.get("1.0", "end-1c")
        try:
            updated = upsert_image_check_exception(
                source, name, expression, old_name=old_name)
            changed = 0
            if old_name and old_name != name and self.image_rename_calls.get():
                updated, changed = rename_image_check_references(
                    updated, old_name, name)
        except (ValueError, SyntaxError) as error:
            messagebox.showwarning(
                "画像検知の例外設定", str(error), parent=self)
            return
        self._replace_current_editor_source(updated)
        self.refresh_image_exception_management(select=name)
        suffix = " / image_check呼び出し{}件も変更".format(changed) \
            if changed else ""
        self.status.set("例外設定を反映しました（ソース未保存）: {}{}".format(
            name, suffix))

    def add_image_exception(self):
        self._apply_image_exception_change()

    def change_image_exception(self):
        rule = self._selected_image_exception()
        if rule:
            self._apply_image_exception_change(old_name=rule["name"])

    def remove_image_exception(self):
        rule = self._selected_image_exception()
        if not rule or not messagebox.askyesno(
                "画像検知の例外設定",
                "例外設定 {} を削除しますか？\n呼び出し側は変更しません。".format(
                    rule["name"]), parent=self):
            return
        try:
            updated = delete_image_check_exception(
                self.editor.get("1.0", "end-1c"), rule["name"])
        except (ValueError, SyntaxError) as error:
            messagebox.showwarning(
                "画像検知の例外設定", str(error), parent=self)
            return
        self._replace_current_editor_source(updated)
        self.refresh_image_exception_management()
        self.status.set(
            "例外設定を削除しました（ソース未保存）: " + rule["name"])

    def open_exception_image_detail(self):
        name = self.image_exception_name.get().strip()
        data = self._read_image_library()
        if name not in data["targets"]:
            messagebox.showinfo(
                "画像検知の詳細", "同名の登録済み画像検知はありません: " + name,
                parent=self)
            return
        self.open_registered_image_detail(name=name)

    def _build_image_library_workspace(self, parent):
        pane = ttk.Panedwindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left, right = ttk.Frame(pane), ttk.Frame(pane)
        pane.add(left, weight=3); pane.add(right, weight=2)

        self.image_library_search = tk.StringVar()
        self.image_library_gray_filter = tk.StringVar(value="すべて")
        self.image_library_excluded_folders = tk.StringVar(
            value="Template/Samples")
        self.image_library_name = tk.StringVar(value="PROFILE")
        self.image_library_description = tk.StringVar()
        self.image_library_path = tk.StringVar()
        self.image_library_threshold = tk.DoubleVar(value=0.80)
        self.image_library_crop = tk.StringVar(value="0,0,0,0")
        self.image_library_gray = tk.BooleanVar(value=True)
        self.image_library_show_value = tk.BooleanVar(value=False)
        self.image_library_match_color = tk.StringVar(value="blue")
        self.image_library_no_match_color = tk.StringVar(value="red")
        self.image_library_target_operator = tk.StringVar(value="OR")
        self.image_library_list_name = tk.StringVar(value="new_image_set")
        self.image_library_list_description = tk.StringVar()
        self.image_library_member = tk.StringVar()
        self.image_library_apply_target = tk.StringVar(value="サンプルプログラム")

        search = ttk.Frame(left); search.pack(fill="x")
        ttk.Label(search, text="検索（名前・タグ・フォルダ）:").pack(side="left")
        entry = ttk.Entry(search, textvariable=self.image_library_search)
        entry.pack(side="left", fill="x", expand=True, padx=5)
        self.image_library_search.trace_add("write", lambda *args: self.debounce(
            "image_library_search", 150, self.refresh_image_library_tree))
        ttk.Label(search, text="グレースケール:").pack(side="left", padx=(4, 2))
        gray_filter = ttk.Combobox(
            search, textvariable=self.image_library_gray_filter, state="readonly",
            values=("すべて", "ON", "OFF"), width=6)
        gray_filter.pack(side="left", padx=(0, 5))
        self.image_library_gray_filter.trace_add("write", lambda *args: self.debounce(
            "image_library_gray_filter", 50, self.refresh_image_library_tree))
        ttk.Button(search, text="Template画像を再読込", command=self.scan_template_images).pack(side="right")

        exclusions = ttk.Frame(left); exclusions.pack(fill="x", pady=(4, 0))
        ttk.Label(exclusions, text="一覧から除外するフォルダー:").pack(side="left")
        ttk.Entry(
            exclusions, textvariable=self.image_library_excluded_folders).pack(
                side="left", fill="x", expand=True, padx=5)
        ttk.Label(
            exclusions,
            text="カンマ区切り（例: Template/Samples, Template/Debug）",
            foreground="#666666").pack(side="left")
        self.image_library_excluded_folders.trace_add(
            "write", lambda *args: self.debounce(
                "image_library_excluded_folders", 100,
                self.refresh_image_library_tree))

        form = ttk.Labelframe(left, text="画像検知設定（同名で別パターンを追加可能）")
        form.pack(fill="x", pady=6)
        ttk.Label(form, text="検知名:").grid(column=0, row=0, padx=4, pady=3, sticky="w")
        ttk.Entry(form, textvariable=self.image_library_name).grid(column=1, row=0, padx=4, pady=3, sticky="ew")
        ttk.Label(form, text="説明:").grid(column=0, row=1, padx=4, pady=3, sticky="w")
        ttk.Entry(form, textvariable=self.image_library_description).grid(column=1, columnspan=2, row=1, padx=4, pady=3, sticky="ew")
        ttk.Label(form, text="画像:").grid(column=0, row=2, padx=4, pady=3, sticky="w")
        ttk.Entry(form, textvariable=self.image_library_path).grid(column=1, row=2, padx=4, pady=3, sticky="ew")
        ttk.Button(form, text="選択", command=self.choose_image_library_path).grid(column=2, row=2, padx=4)
        ttk.Label(form, text="閾値:").grid(column=0, row=3, padx=4, pady=3, sticky="w")
        ttk.Spinbox(form, from_=0.0, to=1.0, increment=0.01, textvariable=self.image_library_threshold, width=8).grid(column=1, row=3, padx=4, sticky="w")
        ttk.Label(form, text="範囲 x1,y1,x2,y2:").grid(column=0, row=4, padx=4, pady=3, sticky="w")
        ttk.Entry(form, textvariable=self.image_library_crop).grid(column=1, row=4, padx=4, sticky="ew")
        flags = ttk.Frame(form); flags.grid(column=1, row=5, sticky="w")
        ttk.Checkbutton(flags, text="グレースケール", variable=self.image_library_gray).pack(side="left")
        ttk.Checkbutton(flags, text="類似度をログ出力", variable=self.image_library_show_value).pack(side="left", padx=8)
        colors = ttk.Frame(form); colors.grid(column=1, columnspan=2, row=6, sticky="w")
        ttk.Label(colors, text="一致色:").pack(side="left")
        ttk.Entry(colors, textvariable=self.image_library_match_color, width=10).pack(side="left", padx=2)
        ttk.Label(colors, text="不一致色:").pack(side="left", padx=(8, 0))
        ttk.Entry(colors, textvariable=self.image_library_no_match_color, width=10).pack(side="left", padx=2)
        ttk.Label(form, text="複数画像の判定:").grid(column=0, row=7, padx=4, pady=3, sticky="w")
        ttk.Combobox(form, textvariable=self.image_library_target_operator, state="readonly",
                     values=("OR", "AND"), width=8).grid(column=1, row=7, padx=4, sticky="w")
        buttons = ttk.Frame(form); buttons.grid(column=1, columnspan=2, row=8, sticky="e", pady=4)
        ttk.Button(buttons, text="＋別パターンとして保存", command=self.save_image_library_variant).pack(side="left", padx=2)
        ttk.Button(buttons, text="選択パターンを上書き", command=self.overwrite_image_library_variant).pack(side="left", padx=2)
        ttk.Button(buttons, text="選択パターンを削除", command=self.delete_image_library_variant).pack(side="left", padx=2)
        form.columnconfigure(1, weight=1)

        library_tree_frame = ttk.Frame(left)
        library_tree_frame.pack(fill="both", expand=True)
        self.image_library_tree = ttk.Treeview(
            library_tree_frame,
            columns=("path", "threshold", "crop", "gray", "tags"),
            show="tree headings")
        self.image_library_tree.heading("#0", text="検知名 / パターン")
        for column, label, width in (("path", "画像", 280), ("threshold", "閾値", 55),
                                     ("crop", "範囲", 120), ("gray", "グレー", 55),
                                     ("tags", "タグ", 130)):
            self.image_library_tree.heading(column, text=label); self.image_library_tree.column(column, width=width)
        pack_scrollable_widget(self.image_library_tree, horizontal=True)
        self.image_library_tree.bind("<<TreeviewSelect>>", self.load_selected_image_library_variant)

        preview_box = ttk.Labelframe(right, text="選択中パターンの画像")
        preview_box.pack(fill="x", pady=(0, 6))
        preview_surface = tk.Frame(
            preview_box, height=220, background="#202124")
        preview_surface.pack(fill="x", padx=5, pady=(5, 2))
        preview_surface.pack_propagate(False)
        self.image_library_preview_label = tk.Label(
            preview_surface, text="左のツリーからパターンを選択してください。",
            background="#202124", foreground="#eeeeee", anchor="center")
        self.image_library_preview_label.pack(fill="both", expand=True)
        self.image_library_preview_info = tk.StringVar()
        ttk.Label(
            preview_box, textvariable=self.image_library_preview_info,
            anchor="w", justify="left", wraplength=480).pack(
                fill="x", padx=5, pady=(0, 3))
        ttk.Button(
            preview_box, text="現在の画像パスを再表示",
            command=lambda: self._show_image_library_preview(
                self.image_library_path.get())).pack(anchor="e", padx=5, pady=(0, 5))
        self.image_library_preview_photo = None

        list_box = ttk.Labelframe(right, text="画像検知フォルダー（フォルダー内フォルダー対応）")
        list_box.pack(fill="both", expand=True)
        row = ttk.Frame(list_box); row.pack(fill="x", padx=5, pady=5)
        ttk.Label(row, text="フォルダー名:").pack(side="left")
        ttk.Entry(row, textvariable=self.image_library_list_name).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(row, text="新規/更新", command=self.save_image_detection_list).pack(side="left")
        ttk.Button(row, text="削除", command=self.delete_image_detection_list).pack(side="left", padx=3)
        description_row = ttk.Frame(list_box); description_row.pack(fill="x", padx=5, pady=(0, 4))
        ttk.Label(description_row, text="フォルダー説明:").pack(side="left")
        ttk.Entry(description_row, textvariable=self.image_library_list_description).pack(side="left", fill="x", expand=True, padx=4)
        library_lists_frame = ttk.Frame(list_box)
        library_lists_frame.pack(fill="x", padx=5)
        self.image_library_lists = tk.Listbox(
            library_lists_frame, height=7, exportselection=False)
        pack_scrollable_widget(self.image_library_lists, horizontal=True)
        self.image_library_lists.bind("<<ListboxSelect>>", self.load_image_detection_list)
        member_row = ttk.Frame(list_box); member_row.pack(fill="x", padx=5, pady=5)
        self.image_library_member_combo = ttk.Combobox(member_row, textvariable=self.image_library_member, state="readonly")
        self.image_library_member_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(member_row, text="＋追加", command=self.add_image_detection_member).pack(side="left", padx=3)
        ttk.Button(member_row, text="－外す", command=self.remove_image_detection_member).pack(side="left")
        library_members_frame = ttk.Frame(list_box)
        library_members_frame.pack(fill="both", expand=True, padx=5)
        self.image_library_members = tk.Listbox(
            library_members_frame, height=9, exportselection=False)
        pack_scrollable_widget(self.image_library_members, horizontal=True)
        apply_row = ttk.Frame(right); apply_row.pack(fill="x", pady=6)
        ttk.Combobox(apply_row, textvariable=self.image_library_apply_target, state="readonly",
                     values=("サンプルプログラム", "ソース編集"), width=18).pack(side="left")
        ttk.Button(apply_row, text="image_checkを生成/更新", command=self.apply_image_detection_code).pack(side="left", padx=5)
        ttk.Button(apply_row, text="生成内容を確認", command=self.preview_image_detection_code).pack(side="left")
        ttk.Button(right, text="ソース ⇄ 画像検知記録：差分チェック・同期",
                   command=self.open_image_detection_sync_mode).pack(fill="x", pady=(0, 3))
        ttk.Button(right, text="ソース → 画像検知記録へ直接更新", command=self.load_image_detection_from_source).pack(fill="x", pady=(0, 6))
        # 247+ registered targets create many Tk rows.  Populate them only
        # when the image-library workspace is actually opened.
        self._image_library_workspace_loaded = False

    def open_image_detection_sync_mode(self):
        dialog = tk.Toplevel(self); dialog.title("画像検知：差分チェック・双方向同期")
        dialog.geometry("1100x680"); dialog.transient(self)
        state = {"comparisons": [], "source_settings": {}}
        search_var, mismatch_only = tk.StringVar(), tk.BooleanVar(value=True)
        summary_var = tk.StringVar(); sync_source_var = tk.StringVar(value="比較対象: 未選択")
        top = ttk.Frame(dialog); top.pack(fill="x", padx=7, pady=7)
        ttk.Label(top, textvariable=sync_source_var).pack(side="left", padx=(0, 10))
        ttk.Label(top, text="検知名検索:").pack(side="left")
        ttk.Entry(top, textvariable=search_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Checkbutton(top, text="不一致のみ表示", variable=mismatch_only).pack(side="left", padx=5)
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill="both", expand=True, padx=7, pady=4)
        tree = ttk.Treeview(tree_frame, columns=("status", "source", "library"), show="tree headings")
        tree.heading("#0", text="画像検知名"); tree.heading("status", text="状態")
        tree.heading("source", text="ソース設定"); tree.heading("library", text="画像検知記録")
        tree.column("#0", width=390); tree.column("status", width=150)
        tree.column("source", width=250); tree.column("library", width=250)
        pack_scrollable_widget(tree, horizontal=True)
        status_labels = {"match": "一致", "different": "設定不一致", "source_only": "ソースのみ", "library_only": "記録のみ"}
        tree.tag_configure("different", foreground="#b36b00")
        tree.tag_configure("source_only", foreground="#a00000")
        tree.tag_configure("library_only", foreground="#7050a0")

        def alive():
            try: return bool(dialog.winfo_exists())
            except tk.TclError: return False

        def setting_text(item):
            if not item: return "－"
            return "{} / {}画像".format(item.get("operator", "OR"), len(item.get("variants", [])))

        def populate():
            if not alive(): return
            needle = search_var.get().strip().lower(); only = mismatch_only.get()
            tree.delete(*tree.get_children()); shown = 0
            counts = {key: 0 for key in status_labels}
            for item in state["comparisons"]:
                counts[item["status"]] += 1
                if only and item["status"] == "match": continue
                if needle and needle not in item["name"].lower(): continue
                tree.insert("", "end", text=item["name"],
                            values=(status_labels[item["status"]], setting_text(item["source"]), setting_text(item["library"])),
                            tags=(item["status"],)); shown += 1
            summary_var.set("表示{}件 / 一致{} / 不一致{} / ソースのみ{} / 記録のみ{}".format(
                shown, counts["match"], counts["different"], counts["source_only"], counts["library_only"]))

        def refresh():
            source = self.editor.get("1.0", "end-1c")
            if "IMAGE_DETECTION_TARGETS" not in source:
                self.capture_active_editor_document()
                candidate = next(((tab_id, document) for tab_id, document in self.editor_documents.items()
                                  if "IMAGE_DETECTION_TARGETS" in document.get("content", "")), None)
                if candidate is not None:
                    tab_id, document = candidate
                    self._switching_editor_tab = True
                    self.editor_tabs.select(tab_id)
                    self._switching_editor_tab = False
                    self.load_editor_document(tab_id)
                    source = self.editor.get("1.0", "end-1c")
                    self.status.set("画像検知設定を持つソースへ自動切替しました: " + os.path.basename(document.get("path") or "Untitled"))
            if "IMAGE_DETECTION_TARGETS" not in source:
                sync_source_var.set("比較対象: 見つかりません")
                messagebox.showwarning("画像検知差分チェック",
                                       "開いているソースにIMAGE_DETECTION_TARGETSがありません。\n"
                                       "画像検知設定を含むソースを開くか、画像検知を一度ソースへ反映してください。",
                                       parent=dialog)
                return
            sync_source_var.set("比較対象: " + os.path.basename(self.current_path or "Untitled"))
            library = self._read_image_library()
            def worker():
                parsed = parse_source_image_detection_settings(source)
                return parsed, compare_image_detection_settings(parsed, library)
            def completed(result):
                if not alive(): return
                state["source_settings"], state["comparisons"] = result; populate()
            def failed(error):
                if alive(): messagebox.showwarning("画像検知差分チェック", str(error), parent=dialog)
            self.run_background("image_detection_compare", "画像検知設定を比較中", worker, completed, failed)

        def source_to_library():
            names = [item["name"] for item in state["comparisons"] if item["status"] in ("different", "source_only")]
            if not names:
                messagebox.showinfo("画像検知同期", "画像検知記録へ反映する不一致はありません。", parent=dialog); return
            if not messagebox.askyesno("ソース → 画像検知記録", "{}件をソース設定で画像検知記録へ更新しますか？".format(len(names)), parent=dialog): return
            source_settings = dict(state["source_settings"]); config_path = self._image_library_config_path()
            def worker():
                library = self._read_image_library()
                update_library_from_source(library, source_settings, names)
                save_image_library(config_path, library)
                return len(names)
            def completed(count):
                self.refresh_image_library_workspace(); refresh()
                self.status.set("ソースから画像検知記録へ{}件更新しました。".format(count))
            self.run_background("source_to_image_library", "ソース設定を画像検知記録へ更新中", worker, completed)

        def library_to_source():
            changed = [item for item in state["comparisons"] if item["status"] in ("different", "library_only")]
            if not changed:
                messagebox.showinfo("画像検知同期", "ソースへ反映する記録側の不一致はありません。", parent=dialog); return
            if not messagebox.askyesno("画像検知記録 → ソース", "記録側の不一致{}件をソースへ反映しますか？\nソースのみの設定は保持します。".format(len(changed)), parent=dialog): return
            source_settings = dict(state["source_settings"]); library = self._read_image_library()
            def worker():
                targets = {name: dict(item) for name, item in library["targets"].items()}
                for name, item in source_settings.items():
                    if name not in targets:
                        targets[name] = {"description": item.get("description", ""), "operator": item.get("operator", "OR"),
                                         "tags": [], "variants": item.get("variants", [])}
                names = sorted(set(source_settings) | set(library["targets"]), key=str.lower)
                temporary = {"schema_version": library.get("schema_version", 1), "targets": targets,
                             "lists": {"SyncSelection": {"description": "画像検知差分同期",
                                                          "members": [{"type": "target", "id": name} for name in names]}}}
                return generate_image_check(temporary, "SyncSelection", "list")
            def completed(code):
                if self._apply_image_code_to_editor(self.editor, code):
                    refresh(); self.status.set("画像検知記録の設定をソースへ反映しました。保存してください。")
            self.run_background("image_library_to_source", "画像検知記録をソースへ反映中", worker, completed)

        search_var.trace_add("write", lambda *args: self.debounce("image_sync_search", 150, populate))
        mismatch_only.trace_add("write", lambda *args: populate())
        buttons = ttk.Frame(dialog); buttons.pack(fill="x", padx=7, pady=7)
        ttk.Label(buttons, textvariable=summary_var).pack(side="left")
        ttk.Button(buttons, text="再チェック", command=refresh).pack(side="right", padx=3)
        ttk.Button(buttons, text="不一致をすべて 記録設定 → ソース", command=library_to_source).pack(side="right", padx=3)
        ttk.Button(buttons, text="不一致をすべて ソース → 画像検知記録", command=source_to_library).pack(side="right", padx=3)
        refresh()

    def open_image_detection_at_cursor(self):
        """Open the registered image target referenced at the source cursor."""
        data = self._read_image_library()
        target_names = set(data["targets"])
        name = None
        try:
            selected = self.editor.get("sel.first", "sel.last").strip().strip("'\" ,:()[]{}")
            if selected in target_names:
                name = selected
            else:
                name = next((value for value in target_names if value in selected), None)
        except tk.TclError:
            pass
        if name is None:
            insert = self.editor.index("insert")
            line_number, column = [int(value) for value in insert.split(".")]
            line = self.editor.get("{}.0".format(line_number), "{}.end".format(line_number))
            candidates = []
            for value in target_names:
                start = line.find(value)
                while start >= 0:
                    end = start + len(value)
                    distance = 0 if start <= column <= end else min(abs(column - start), abs(column - end))
                    candidates.append((distance, start, value))
                    start = line.find(value, start + 1)
            if candidates:
                name = min(candidates)[2]
        if name is None:
            messagebox.showinfo("画像検知", "画像検知名を選択するか、その名前の上へカーソルを置いてください。", parent=self)
            return
        variants = data["targets"][name].get("variants", [])
        if not variants:
            messagebox.showwarning("画像検知", "登録画像がありません: " + name, parent=self)
            return
        self.workspace_tabs.select(self.image_library_workspace)
        self.image_library_search.set(name)
        pending = getattr(self, "_debounce_jobs", {}).pop("image_library_search", None)
        if pending is not None:
            try: self.after_cancel(pending)
            except tk.TclError: pass
        self.refresh_image_library_workspace(select=(name, 0))
        self.load_selected_image_library_variant()
        self.status.set("画像検知設定を開きました: " + name)

    def _build_sample_functions_tab(self, parent):
        self.sample_functions_workspace = parent
        self.fragment_name = tk.StringVar(value="new_fragment")
        self.fragment_folder = tk.StringVar(value=self.fragment_root())
        form = ttk.Labelframe(parent, text="再利用関数サンプルを作成")
        form.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Label(form, text="名前:").grid(column=0, row=0, padx=6, pady=4, sticky="w")
        ttk.Entry(form, textvariable=self.fragment_name).grid(column=1, row=0, padx=6, pady=4, sticky="ew")
        ttk.Label(form, text="タグ:").grid(column=0, row=1, padx=6, pady=4, sticky="nw")
        self.fragment_tag_picker = TagPicker(
            form, self.fragment_tag_choices, initial=["image"],
            defer_choices=True)
        self.fragment_tag_picker.grid(column=1, columnspan=3, row=1, padx=6, pady=4, sticky="nsew")
        ttk.Label(form, text="保存フォルダ:").grid(column=0, row=2, padx=6, pady=4, sticky="w")
        ttk.Entry(form, textvariable=self.fragment_folder).grid(column=1, row=2, padx=6, pady=4, sticky="ew")
        ttk.Button(form, text="選択", command=self.choose_fragment_folder).grid(column=2, row=2, padx=3, pady=4)
        ttk.Button(form, text="+ フォルダ", command=self.add_fragment_folder).grid(column=3, row=2, padx=3, pady=4)
        ttk.Label(form, text="Imports（import / from形式・1行ずつ）:").grid(column=0, row=3, padx=6, pady=4, sticky="nw")
        fragment_imports_frame = ttk.Frame(form)
        fragment_imports_frame.grid(
            column=1, row=3, padx=6, pady=4, sticky="nsew")
        self.fragment_imports = tk.Text(
            fragment_imports_frame, height=4, undo=True, wrap="none")
        pack_scrollable_widget(self.fragment_imports, horizontal=True)
        ttk.Label(form, text="クラス変数（1行ずつ）:").grid(column=0, row=4, padx=6, pady=4, sticky="nw")
        fragment_class_vars_frame = ttk.Frame(form)
        fragment_class_vars_frame.grid(
            column=1, row=4, padx=6, pady=4, sticky="nsew")
        self.fragment_class_vars = tk.Text(
            fragment_class_vars_frame, height=4, undo=True, wrap="none")
        pack_scrollable_widget(self.fragment_class_vars, horizontal=True)
        ttk.Label(form, text="実行開始時の初期化コード:").grid(column=0, row=5, padx=6, pady=4, sticky="nw")
        fragment_initializer_frame = ttk.Frame(form)
        fragment_initializer_frame.grid(
            column=1, row=5, padx=6, pady=4, sticky="nsew")
        self.fragment_initializer = tk.Text(fragment_initializer_frame, height=5, undo=True, wrap="none",
                                            font=self.code_font, tabs=self.code_tabs)
        pack_scrollable_widget(self.fragment_initializer, horizontal=True)
        ttk.Label(form, text="Start後、関数処理より前に実行します。self.xxx = 0 やSteam画面のアクティブ化を記述します。").grid(
            column=2, columnspan=2, row=5, padx=6, pady=4, sticky="nw")
        ttk.Label(form, text="関数・処理コード:").grid(column=0, row=6, padx=6, pady=4, sticky="nw")
        ttk.Label(form, text="Tabは半角スペース4文字です。改行時はインデントを維持し、行番号のドラッグで複数行を選択できます。").grid(
            column=1, row=6, padx=6, pady=(0, 2), sticky="nw")
        fragment_editor_frame = ttk.Frame(form)
        fragment_editor_frame.grid(column=1, row=6, padx=6, pady=(24, 4), sticky="nsew")
        fragment_search = ttk.Frame(fragment_editor_frame)
        fragment_search.pack(side="top", fill="x", pady=(0, 3))
        self.fragment_search_scope = tk.StringVar(value="関数・処理コード")
        self.fragment_search_query = tk.StringVar()
        self.fragment_search_case = tk.BooleanVar(value=False)
        self.fragment_search_status = tk.StringVar(value="0件")
        ttk.Label(fragment_search, text="範囲内検索:").pack(side="left")
        ttk.Combobox(
            fragment_search, state="readonly", width=17,
            textvariable=self.fragment_search_scope,
            values=("Imports", "クラス変数", "初期化コード",
                    "関数・処理コード", "すべて")).pack(side="left", padx=3)
        self.fragment_search_entry = ttk.Entry(
            fragment_search, textvariable=self.fragment_search_query)
        self.fragment_search_entry.pack(side="left", fill="x", expand=True, padx=3)
        ttk.Checkbutton(
            fragment_search, text="大文字区別",
            variable=self.fragment_search_case,
            command=self._refresh_fragment_search).pack(side="left", padx=2)
        ttk.Button(fragment_search, text="▲前", width=6,
                   command=lambda: self._move_fragment_search(-1)).pack(side="left", padx=1)
        ttk.Button(fragment_search, text="次▼", width=6,
                   command=lambda: self._move_fragment_search(1)).pack(side="left", padx=1)
        ttk.Label(fragment_search, textvariable=self.fragment_search_status,
                  width=10, anchor="e").pack(side="left", padx=(3, 0))
        self.fragment_line_numbers = tk.Text(fragment_editor_frame, width=6, padx=4, takefocus=0, state="disabled",
                                             wrap="none", background="#252526", foreground="#858585",
                                             selectbackground="#264f78", cursor="arrow",
                                             font=self.code_font, tabs=self.code_tabs)
        self.fragment_line_numbers.pack(side="left", fill="y")
        self.fragment_body = tk.Text(fragment_editor_frame, height=20, undo=True, wrap="none",
                                     font=self.code_font, tabs=self.code_tabs)
        self.fragment_body.insert("1.0", "# @pokedev-fragment: new_fragment\n# Inserted into the selected Step user block.\n")
        fragment_y = ttk.Scrollbar(fragment_editor_frame, orient="vertical", command=self._scroll_fragment_editor)
        fragment_y.pack(side="right", fill="y")
        fragment_x = ttk.Scrollbar(fragment_editor_frame, orient="horizontal", command=self.fragment_body.xview)
        fragment_x.pack(side="bottom", fill="x")
        self.fragment_body.pack(side="left", fill="both", expand=True)
        self.fragment_body.configure(
            yscrollcommand=lambda first, last: self._sync_fragment_scroll(fragment_y, first, last),
            xscrollcommand=fragment_x.set)
        fragment_scopes = {
            self.fragment_imports: "Imports",
            self.fragment_class_vars: "クラス変数",
            self.fragment_initializer: "初期化コード",
            self.fragment_body: "関数・処理コード",
        }
        for editor in fragment_scopes:
            editor.bind("<Tab>", lambda event, widget=editor: self._python_editor_tab(widget))
            editor.bind("<Shift-Tab>", lambda event, widget=editor: self._python_editor_shift_tab(widget))
            editor.bind("<Return>", lambda event, widget=editor: self._python_editor_newline(widget))
            self._register_find_editor(
                editor, "サンプル関数: " + fragment_scopes[editor])
            editor.tag_configure("fragment_search_match", background="#fff2a8", foreground="#202020")
            editor.tag_configure("fragment_search_current", background="#ffad42", foreground="#202020")
        self._fragment_search_results = []
        self._fragment_search_index = -1
        self.fragment_search_query.trace_add(
            "write", lambda *_args: self.debounce(
                "fragment_range_search", 100, self._refresh_fragment_search))
        self.fragment_search_scope.trace_add(
            "write", lambda *_args: self.after_idle(self._refresh_fragment_search))
        self.fragment_search_entry.bind(
            "<Return>", lambda event: (self._move_fragment_search(1), "break")[1])
        self.fragment_search_entry.bind(
            "<Shift-Return>", lambda event: (self._move_fragment_search(-1), "break")[1])
        self.fragment_body.bind("<<Modified>>", self._fragment_editor_modified)
        self.fragment_body.bind("<KeyRelease>", lambda event: self.after_idle(self._update_fragment_line_numbers))
        for editor in fragment_scopes:
            editor.bind(
                "<KeyRelease>",
                lambda event: self.debounce(
                    "fragment_range_search", 100, self._refresh_fragment_search),
                add="+")
        self.fragment_line_numbers.bind("<Button-1>", self._fragment_line_select_start)
        self.fragment_line_numbers.bind("<B1-Motion>", self._fragment_line_select_drag)
        self.fragment_line_numbers.bind("<MouseWheel>", lambda event: self.fragment_body.yview_scroll(-1 if event.delta > 0 else 1, "units"))
        self._fragment_line_anchor = 1
        self._update_fragment_line_numbers()
        helpers = ttk.Labelframe(form, text="入力補助")
        helpers.grid(column=2, columnspan=2, row=3, rowspan=2, padx=6, pady=4, sticky="ns")
        ttk.Button(helpers, text="関数枠を追加", command=self.insert_fragment_function_skeleton).pack(fill="x", padx=4, pady=(4, 2))
        ttk.Button(helpers, text="Step処理を追加", command=self.insert_fragment_step_skeleton).pack(fill="x", padx=4, pady=2)
        ttk.Button(helpers, text="Import例を追加", command=self.insert_fragment_import_examples).pack(fill="x", padx=4, pady=2)
        ttk.Button(helpers, text="クラス変数例を追加", command=self.insert_fragment_class_var_example).pack(fill="x", padx=4, pady=(2, 4))
        ttk.Button(helpers, text="初期化例を追加", command=self.insert_fragment_initializer_example).pack(fill="x", padx=4, pady=(2, 4))
        ttk.Button(helpers, text="フォルダー比較・同期", command=self.open_sample_function_check_mode).pack(fill="x", padx=4, pady=(8, 4))
        self.fragment_dependency_frame = ttk.Labelframe(
            form, text="依存グループの関数（__supportは初期化・状態辞書の設定です）")
        self.fragment_dependency_frame.grid(
            column=1, columnspan=3, row=7, padx=6, pady=(2, 4), sticky="ew")
        self.fragment_dependency_notice = tk.StringVar()
        ttk.Label(
            self.fragment_dependency_frame,
            textvariable=self.fragment_dependency_notice,
            foreground="#b00020").pack(side="left", padx=5)
        self.fragment_dependency_function_choice = tk.StringVar()
        self.fragment_dependency_function_combo = ttk.Combobox(
            self.fragment_dependency_frame, state="readonly", width=46,
            textvariable=self.fragment_dependency_function_choice)
        self.fragment_dependency_function_combo.pack(
            side="left", fill="x", expand=True, padx=5, pady=4)
        ttk.Button(
            self.fragment_dependency_frame, text="選択した関数を変更",
            command=self.open_selected_dependency_fragment).pack(
                side="right", padx=5, pady=4)
        self.fragment_dependency_function_combo.bind(
            "<Double-1>", lambda _event: self.open_selected_dependency_fragment())
        self.fragment_dependency_frame.grid_remove()
        self.fragment_save_button = ttk.Button(form, text="サンプルとして保存", command=self.create_fragment_from_tab)
        self.fragment_save_button.grid(column=1, row=8, padx=6, pady=8, sticky="e")
        ttk.Button(form, text="サンプルライブラリを開く", command=self.open_fragment_library).grid(column=0, row=8, padx=6, pady=8, sticky="w")
        registered = ttk.Frame(form)
        registered.grid(column=2, columnspan=2, row=8, padx=6, pady=8, sticky="e")
        self.registered_fragment_choice = tk.StringVar()
        ttk.Label(registered, text="登録済みサンプル関数:").pack(side="left", padx=(0, 3))
        self.registered_fragment_combo = ttk.Combobox(registered, textvariable=self.registered_fragment_choice, state="readonly", width=34)
        self.registered_fragment_combo.pack(side="left", padx=2)
        ttk.Button(registered, text="変更", command=self.edit_registered_fragment).pack(side="left", padx=2)
        ttk.Button(registered, text="削除", command=self.delete_registered_fragment).pack(side="left", padx=2)
        ttk.Button(registered, text="新規へ戻る", command=self.cancel_fragment_edit).pack(side="left", padx=2)
        ttk.Button(registered, text="VS Codeで開く",
                   command=self.open_fragment_in_vscode).pack(side="left", padx=(8, 2))
        ttk.Button(registered, text="外部変更を再読込",
                   command=self.reload_fragment_external_changes).pack(side="left", padx=2)
        form.columnconfigure(1, weight=1)
        form.rowconfigure(6, weight=1)

    def _python_editor_selected_line_range(self, editor):
        try:
            first = int(editor.index("sel.first").split(".")[0])
            last_line, last_column = [int(value) for value in editor.index("sel.last").split(".")]
            return first, last_line - 1 if last_column == 0 and last_line > first else last_line
        except tk.TclError:
            line = int(editor.index("insert").split(".")[0])
            return line, line

    def _python_editor_select_lines(self, editor, first, last):
        start, end = sorted((first, last))
        editor.tag_remove("sel", "1.0", "end")
        editor.tag_add("sel", "{}.0".format(start), "{}.0".format(end + 1))
        editor.mark_set("insert", "{}.0".format(start))
        editor.see("{}.0".format(end))
        editor.focus_set()

    def _python_editor_tab(self, editor):
        try:
            editor.index("sel.first")
        except tk.TclError:
            editor.insert("insert", "    ")
            return "break"
        first, last = self._python_editor_selected_line_range(editor)
        for line in range(first, last + 1):
            editor.insert("{}.0".format(line), "    ")
        self._python_editor_select_lines(editor, first, last)
        return "break"

    def _python_editor_shift_tab(self, editor):
        first, last = self._python_editor_selected_line_range(editor)
        for line in range(first, last + 1):
            value = editor.get("{}.0".format(line), "{}.4".format(line))
            remove = min(4, len(value) - len(value.lstrip(" ")))
            if remove:
                editor.delete("{}.0".format(line), "{}.{}".format(line, remove))
            elif value.startswith("\t"):
                editor.delete("{}.0".format(line), "{}.1".format(line))
        if first != last:
            self._python_editor_select_lines(editor, first, last)
        return "break"

    def _python_editor_newline(self, editor):
        try:
            editor.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        before_cursor = editor.get(editor.index("insert linestart"), "insert")
        indent_match = re.match(r"[ \t]*", before_cursor)
        indent = indent_match.group(0).replace("\t", "    ") if indent_match else ""
        editor.insert("insert", "\n" + indent)
        return "break"

    def _scroll_fragment_editor(self, *args):
        self.fragment_body.yview(*args)
        self.fragment_line_numbers.yview(*args)

    def _sync_fragment_scroll(self, scrollbar, first, last):
        scrollbar.set(first, last)
        self.fragment_line_numbers.yview_moveto(first)

    def _fragment_editor_modified(self, event=None):
        if self.fragment_body.edit_modified():
            self.fragment_body.edit_modified(False)
            self.after_idle(self._update_fragment_line_numbers)

    def _update_fragment_line_numbers(self):
        if not hasattr(self, "fragment_body"):
            return
        line_count = int(self.fragment_body.index("end-1c").split(".")[0])
        self.fragment_line_numbers.configure(state="normal")
        self.fragment_line_numbers.delete("1.0", "end")
        self.fragment_line_numbers.insert("1.0", "\n".join(str(number) for number in range(1, line_count + 1)))
        self.fragment_line_numbers.configure(state="disabled")
        self.fragment_line_numbers.yview_moveto(self.fragment_body.yview()[0])

    def _fragment_line_at(self, y):
        return int(self.fragment_line_numbers.index("@0,{}".format(y)).split(".")[0])

    def _fragment_line_select_start(self, event):
        self._fragment_line_anchor = self._fragment_line_at(event.y)
        self._python_editor_select_lines(self.fragment_body, self._fragment_line_anchor, self._fragment_line_anchor)
        return "break"

    def _fragment_line_select_drag(self, event):
        self._python_editor_select_lines(self.fragment_body, self._fragment_line_anchor, self._fragment_line_at(event.y))
        return "break"

    def _fragment_search_widgets(self):
        return {
            "Imports": self.fragment_imports,
            "クラス変数": self.fragment_class_vars,
            "初期化コード": self.fragment_initializer,
            "関数・処理コード": self.fragment_body,
        }

    def _focus_fragment_search(self, widget, scope):
        self.fragment_search_scope.set(scope)
        try:
            selected = widget.get("sel.first", "sel.last")
        except tk.TclError:
            selected = ""
        if selected and "\n" not in selected:
            self.fragment_search_query.set(selected)
        self.fragment_search_entry.focus_set()
        self.fragment_search_entry.selection_range(0, "end")
        self._refresh_fragment_search()
        return "break"

    def _refresh_fragment_search(self):
        if not hasattr(self, "fragment_search_query"):
            return
        widgets = self._fragment_search_widgets()
        for widget in widgets.values():
            widget.tag_remove("fragment_search_match", "1.0", "end")
            widget.tag_remove("fragment_search_current", "1.0", "end")
        query = self.fragment_search_query.get()
        self._fragment_search_results = []
        self._fragment_search_index = -1
        if not query:
            self.fragment_search_status.set("0件")
            return
        selected_scope = self.fragment_search_scope.get()
        targets = list(widgets.items()) if selected_scope == "すべて" else [
            (selected_scope, widgets[selected_scope])]
        for scope, widget in targets:
            start = "1.0"
            while True:
                count = tk.IntVar(value=0)
                index = widget.search(
                    query, start, stopindex="end",
                    nocase=not self.fragment_search_case.get(), count=count)
                if not index:
                    break
                length = max(1, int(count.get()))
                end = "{}+{}c".format(index, length)
                widget.tag_add("fragment_search_match", index, end)
                self._fragment_search_results.append((scope, widget, index, end))
                start = end
        if not self._fragment_search_results:
            self.fragment_search_status.set("0件")
            return
        self._show_fragment_search_result(0, focus=False)

    def _show_fragment_search_result(self, index, focus=True):
        if not self._fragment_search_results:
            self.fragment_search_status.set("0件")
            return
        self._fragment_search_index = index % len(self._fragment_search_results)
        for widget in self._fragment_search_widgets().values():
            widget.tag_remove("fragment_search_current", "1.0", "end")
        scope, widget, start, end = self._fragment_search_results[
            self._fragment_search_index]
        widget.tag_add("fragment_search_current", start, end)
        widget.tag_raise("fragment_search_current")
        if focus:
            widget.mark_set("insert", start)
            widget.see(start)
            widget.focus_set()
        self.fragment_search_status.set(
            "{}/{}".format(
                self._fragment_search_index + 1,
                len(self._fragment_search_results)))
        self.status.set("サンプル関数検索: {} / {}".format(
            scope, self.fragment_search_status.get()))

    def _move_fragment_search(self, direction):
        if not self._fragment_search_results:
            self._refresh_fragment_search()
            if not self._fragment_search_results:
                return
        self._show_fragment_search_result(
            self._fragment_search_index + int(direction))

    def insert_fragment_function_skeleton(self):
        name = python_identifier(self.fragment_name.get()) + "_helper"
        self.fragment_body.insert("insert", "\n\ndef {}(self, frame=None):\n    \"\"\"Reusable helper / 再利用ヘルパー。\"\"\"\n    # TODO: implement\n    return None\n".format(name))

    def insert_fragment_step_skeleton(self):
        self.fragment_body.insert("insert", "\n# Insert inside POKECON_STEP_USER_BEGIN/END\nself.checkIfAlive()\n# TODO: step action / Step処理\n")

    def insert_fragment_import_examples(self):
        existing = self.fragment_imports.get("1.0", "end-1c")
        examples = ["import cv2", "import numpy as np"]
        self.fragment_imports.insert("end", "" if not existing else "\n")
        self.fragment_imports.insert("end", "\n".join(item for item in examples if item not in existing))

    def insert_fragment_class_var_example(self):
        self.fragment_class_vars.insert("end", "" if not self.fragment_class_vars.get("1.0", "end-1c") else "\n")
        self.fragment_class_vars.insert("end", "SAMPLE_ROI = (0, 0, 0, 0)  # x, y, width, height\n")

    def insert_fragment_initializer_example(self):
        existing = self.fragment_initializer.get("1.0", "end-1c")
        self.fragment_initializer.insert("end", "" if not existing else "\n")
        self.fragment_initializer.insert("end", "self.sample_count = 0\n# Steam画面のアクティブ化など、Start後に必要な準備処理\n")

    def open_sample_function_check_mode(self):
        dialog = tk.Toplevel(self)
        dialog.title("サンプル関数チェックモード")
        dialog.geometry("1150x760")
        dialog.minsize(760, 520)
        dialog.transient(self)
        try:
            initial_fragment_folder = resolve_fragment_folder(
                self.fragment_root(),
                self.fragment_folder.get() or self.fragment_root())
        except ValueError:
            initial_fragment_folder = self.fragment_root()
        self.fragment_folder.set(initial_fragment_folder)
        folder_var = tk.StringVar(value=initial_fragment_folder)
        source_path_var = tk.StringVar(value=(
            self.current_path if self.current_path and
            str(self.current_path).lower().endswith(".py") else ""))
        search_var = tk.StringVar()
        differences_only_var = tk.BooleanVar(value=False)
        hide_missing_source_var = tk.BooleanVar(value=False)
        summary_var = tk.StringVar(value="")
        source_mode_var = tk.StringVar(value="")
        top = ttk.Frame(dialog); top.pack(fill="x", padx=7, pady=7)
        ttk.Label(top, text="比較フォルダー:").pack(side="left")
        ttk.Entry(top, textvariable=folder_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Label(top, text="関数検索:").pack(side="left", padx=(8, 2))
        ttk.Entry(top, textvariable=search_var, width=24).pack(side="left", padx=2)
        ttk.Checkbutton(
            top, text="差分ありのみ表示", variable=differences_only_var,
            command=lambda: populate()).pack(side="left", padx=(6, 2))
        ttk.Checkbutton(
            top, text="ソース側未登録を非表示",
            variable=hide_missing_source_var,
            command=lambda: populate()).pack(side="left", padx=(6, 2))
        source_bar = ttk.Frame(dialog); source_bar.pack(fill="x", padx=7, pady=(0, 4))
        ttk.Label(source_bar, text="比較ソース:").pack(side="left")
        ttk.Entry(source_bar, textvariable=source_path_var).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Label(source_bar, textvariable=source_mode_var).pack(
            side="right", padx=(7, 2))
        ttk.Button(
            source_bar, text="ディスクから再読込",
            command=lambda: reload_comparison_source()).pack(
                side="right", padx=2)
        ttk.Button(source_bar, text="選択", command=lambda: choose_source()).pack(side="left", padx=2)
        backup_root = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "Backups",
            "SampleFunctionSync")
        latest_backup = latest_sample_sync_backup(backup_root)
        backup_status_var = tk.StringVar(
            value=("復元可能: " + os.path.basename(os.path.dirname(latest_backup))
                   if latest_backup else "一括反映履歴なし"))
        state = {"comparisons": [], "visible": {}, "source": "",
                 "source_path": "", "last_backup": latest_backup,
                 "reselect_name": ""}

        def ensure_source_save_path(preferred_path=""):
            selected = (str(preferred_path or "").strip()
                        or str(state.get("source_path", "")).strip()
                        or source_path_var.get().strip()
                        or str(self.current_path or "").strip())
            if not selected:
                selected = filedialog.asksaveasfilename(
                    parent=dialog, title="反映先の実ソースを保存",
                    defaultextension=".py",
                    filetypes=(("Python", "*.py"), ("すべて", "*.*")))
            if not selected:
                return ""
            selected = os.path.abspath(selected)
            source_path_var.set(selected)
            state["source_path"] = selected
            return selected

        def show_saved_source(updated_source, saved_path):
            saved_path = os.path.abspath(saved_path)
            self.set_editor_content(updated_source, saved_path)
            self.editor_dirty = False
            self.editor.edit_modified(False)
            self.update_editor_view()
            state["source"] = updated_source
            state["source_path"] = saved_path
            source_path_var.set(saved_path)
            source_mode_var.set("比較元: 実ソースへ保存済み")

        content = ttk.Panedwindow(dialog, orient="vertical")
        content.pack(fill="both", expand=True, padx=7, pady=4)
        tree_frame = ttk.Frame(content)
        diff_frame = ttk.LabelFrame(content, text="選択した関数の差分")
        content.add(tree_frame, weight=3)
        content.add(diff_frame, weight=2)

        tree = ttk.Treeview(tree_frame, columns=("status", "function_update", "path"),
                            show="tree headings", selectmode="extended")
        tree.heading("#0", text="関数名"); tree.heading("status", text="状態"); tree.heading("function_update", text="関数更新判定"); tree.heading("path", text="サンプル関数ファイル")
        tree.column("#0", width=300); tree.column("status", width=145); tree.column("function_update", width=390); tree.column("path", width=470)
        tree_y_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree_x_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=tree_y_scroll.set, xscrollcommand=tree_x_scroll.set)
        tree.grid(column=0, row=0, sticky="nsew")
        tree_y_scroll.grid(column=1, row=0, sticky="ns")
        tree_x_scroll.grid(column=0, row=1, sticky="ew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        tree.tag_configure("different", foreground="#b36b00")
        tree.tag_configure("name_different", foreground="#8a4d00")
        tree.tag_configure("missing_source", foreground="#a00000")
        tree.tag_configure("duplicate", foreground="#a00000")
        status_labels = {
            "match": "一致", "different": "処理不一致",
            "name_different": "関数名不一致",
            "missing_source": "ソース側に未登録",
            "duplicate": "サンプル側で重複"}

        def item_status_label(item):
            if item.get("status") != "duplicate":
                return status_labels[item["status"]]
            return ("サンプル側で重複（同内容）"
                    if item.get("duplicate_kind") == "same"
                    else "サンプル側で重複（内容差あり）")

        diff_header = ttk.Frame(diff_frame)
        diff_header.pack(fill="x", padx=5, pady=(4, 2))
        diff_status_var = tk.StringVar(value="一覧から関数を1件選択すると差分を表示します。")
        ttk.Label(diff_header, textvariable=diff_status_var).pack(
            side="left", fill="x", expand=True)
        diff_position_var = tk.StringVar(value="")
        ttk.Label(diff_header, textvariable=diff_position_var).pack(
            side="right", padx=3)
        ttk.Button(diff_header, text="次の差分▼",
                   command=lambda: move_diff_change(1)).pack(side="right", padx=2)
        ttk.Button(diff_header, text="▲前の差分",
                   command=lambda: move_diff_change(-1)).pack(side="right", padx=2)
        source_to_sample_button = ttk.Button(
            diff_header, text="この差分を 現在ソース → サンプル関数",
            state="disabled", command=lambda: source_to_library(True))
        source_to_sample_button.pack(side="right", padx=3)
        sample_to_source_button = ttk.Button(
            diff_header, text="この差分を サンプル関数 → ソース保存",
            state="disabled", command=lambda: library_to_source(True))
        sample_to_source_button.pack(side="right", padx=3)
        merge_name_body_button = ttk.Button(
            diff_header, text="名前=サンプル・処理=ソース",
            state="disabled", command=lambda: merge_names_and_source_bodies(True))
        merge_name_body_button.pack(side="right", padx=3)

        duplicate_compare_bar = ttk.Frame(diff_frame)
        duplicate_compare_bar.pack(fill="x", padx=5, pady=(0, 3))
        ttk.Label(duplicate_compare_bar, text="重複サンプル比較:").pack(
            side="left", padx=(0, 3))
        duplicate_count_var = tk.StringVar(value="サンプル関数: 0件")
        ttk.Label(
            duplicate_compare_bar, textvariable=duplicate_count_var,
            foreground="#174a7e").pack(side="left", padx=(0, 5))
        duplicate_left_var = tk.StringVar(value="")
        duplicate_right_var = tk.StringVar(value="")
        duplicate_left_stats_var = tk.StringVar(value="")
        duplicate_right_stats_var = tk.StringVar(value="")
        duplicate_left_combo = ttk.Combobox(
            duplicate_compare_bar, textvariable=duplicate_left_var,
            state="disabled", width=52)
        duplicate_right_combo = ttk.Combobox(
            duplicate_compare_bar, textvariable=duplicate_right_var,
            state="disabled", width=52)
        duplicate_left_combo.pack(side="left", fill="x", expand=True, padx=2)
        ttk.Label(duplicate_compare_bar, text="⇔").pack(side="left", padx=2)
        duplicate_right_combo.pack(side="left", fill="x", expand=True, padx=2)
        duplicate_left_open = ttk.Button(
            duplicate_compare_bar, text="左をVSCode", state="disabled",
            command=lambda: open_duplicate_in_vscode("left"))
        duplicate_right_open = ttk.Button(
            duplicate_compare_bar, text="右をVSCode", state="disabled",
            command=lambda: open_duplicate_in_vscode("right"))
        duplicate_left_open.pack(side="left", padx=2)
        duplicate_right_open.pack(side="left", padx=2)
        duplicate_left_edit = ttk.Button(
            duplicate_compare_bar, text="左を編集", state="disabled",
            command=lambda: edit_duplicate_sample("left"))
        duplicate_right_edit = ttk.Button(
            duplicate_compare_bar, text="右を編集", state="disabled",
            command=lambda: edit_duplicate_sample("right"))
        duplicate_left_edit.pack(side="left", padx=2)
        duplicate_right_edit.pack(side="left", padx=2)
        duplicate_compare_state = {"item": None, "fragments": {}}

        duplicate_stats_bar = ttk.Frame(diff_frame)
        duplicate_stats_bar.pack(fill="x", padx=5, pady=(0, 3))
        ttk.Label(
            duplicate_stats_bar, textvariable=duplicate_left_stats_var,
            foreground="#174a7e", anchor="w").pack(
                side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(
            duplicate_stats_bar, textvariable=duplicate_right_stats_var,
            foreground="#174a7e", anchor="w").pack(
                side="left", fill="x", expand=True, padx=(6, 0))

        duplicate_reflect_bar = ttk.Frame(diff_frame)
        duplicate_reflect_bar.pack(fill="x", padx=5, pady=(0, 4))
        duplicate_reflect_label = ttk.Label(
            duplicate_reflect_bar,
            text=("サンプル関数同士の操作です（現在ソースは変更しません）。"
                  "片方だけを採用して重複を破棄、またはマージ編集を選べます。"),
            foreground="#c00000")
        duplicate_reflect_label.pack(side="left", padx=(0, 8))

        duplicate_action_bar = ttk.Frame(diff_frame)
        duplicate_action_bar.pack(fill="x", padx=5, pady=(0, 4))
        duplicate_left_to_right = ttk.Button(
            duplicate_action_bar, text="左だけ採用 → 右サンプルを破棄",
            state="disabled",
            command=lambda: discard_duplicate_sample("left", "right"))
        duplicate_right_to_left = ttk.Button(
            duplicate_action_bar, text="右だけ採用 → 左サンプルを破棄",
            state="disabled",
            command=lambda: discard_duplicate_sample("right", "left"))
        duplicate_left_to_right.pack(side="left", padx=3)
        duplicate_right_to_left.pack(side="left", padx=3)
        duplicate_merge_to_right = ttk.Button(
            duplicate_action_bar, text="左と右をマージ編集 → 右へ保存",
            state="disabled",
            command=lambda: edit_duplicate_sample(
                "right", merge_from_side="left"))
        duplicate_merge_to_left = ttk.Button(
            duplicate_action_bar, text="左と右をマージ編集 → 左へ保存",
            state="disabled",
            command=lambda: edit_duplicate_sample(
                "left", merge_from_side="right"))
        duplicate_merge_to_right.pack(side="left", padx=(12, 3))
        duplicate_merge_to_left.pack(side="left", padx=3)

        diff_body = ttk.Frame(diff_frame)
        diff_body.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        diff_panes = ttk.Panedwindow(diff_body, orient="horizontal")
        diff_panes.grid(column=0, row=0, sticky="nsew")
        left_diff_frame = ttk.Frame(diff_panes)
        right_diff_frame = ttk.Frame(diff_panes)
        diff_panes.add(left_diff_frame, weight=1)
        diff_panes.add(right_diff_frame, weight=1)
        left_diff_title = tk.StringVar(value="現在ソース")
        right_diff_title = tk.StringVar(value="サンプル関数")
        ttk.Label(left_diff_frame, textvariable=left_diff_title,
                  anchor="w").grid(column=0, row=0, sticky="ew", padx=3)
        ttk.Label(right_diff_frame, textvariable=right_diff_title,
                  anchor="w").grid(column=0, row=0, sticky="ew", padx=3)
        diff_font = tkfont.nametofont("TkFixedFont")
        left_diff_text = tk.Text(
            left_diff_frame, wrap="none", state="disabled", height=12,
            font=diff_font, background="#ffffff", foreground="#202020")
        right_diff_text = tk.Text(
            right_diff_frame, wrap="none", state="disabled", height=12,
            font=diff_font, background="#ffffff", foreground="#202020")
        left_diff_x = ttk.Scrollbar(
            left_diff_frame, orient="horizontal", command=left_diff_text.xview)
        right_diff_x = ttk.Scrollbar(
            right_diff_frame, orient="horizontal", command=right_diff_text.xview)
        left_diff_text.configure(xscrollcommand=left_diff_x.set)
        right_diff_text.configure(xscrollcommand=right_diff_x.set)
        left_diff_text.grid(column=0, row=1, sticky="nsew")
        right_diff_text.grid(column=0, row=1, sticky="nsew")
        left_diff_x.grid(column=0, row=2, sticky="ew")
        right_diff_x.grid(column=0, row=2, sticky="ew")
        for pane_frame in (left_diff_frame, right_diff_frame):
            pane_frame.columnconfigure(0, weight=1)
            pane_frame.rowconfigure(1, weight=1)
        diff_scroll_state = {"syncing": False}

        def move_diff_y(*args):
            left_diff_text.yview(*args)
            right_diff_text.yview(*args)

        diff_y_scroll = ttk.Scrollbar(
            diff_body, orient="vertical", command=move_diff_y)
        diff_y_scroll.grid(column=1, row=0, sticky="ns", pady=(20, 0))

        def sync_diff_y(other, first, last):
            diff_y_scroll.set(first, last)
            if diff_scroll_state["syncing"]:
                return
            diff_scroll_state["syncing"] = True
            try:
                other.yview_moveto(first)
            finally:
                diff_scroll_state["syncing"] = False

        left_diff_text.configure(
            yscrollcommand=lambda first, last: sync_diff_y(
                right_diff_text, first, last))
        right_diff_text.configure(
            yscrollcommand=lambda first, last: sync_diff_y(
                left_diff_text, first, last))

        def wheel_diff(event):
            units = -1 if event.delta > 0 else 1
            left_diff_text.yview_scroll(units, "units")
            right_diff_text.yview_scroll(units, "units")
            return "break"

        left_diff_text.bind("<MouseWheel>", wheel_diff)
        right_diff_text.bind("<MouseWheel>", wheel_diff)
        diff_body.columnconfigure(0, weight=1)
        diff_body.rowconfigure(0, weight=1)
        for widget in (left_diff_text, right_diff_text):
            widget.tag_configure("diff_gutter", foreground="#777777",
                                 background="#f2f2f2")
            widget.tag_configure("diff_marker", foreground="#b36b00",
                                 background="#fff2cc")
            widget.tag_configure("diff_current_marker", foreground="#ffffff",
                                 background="#2878c8")
            widget.tag_configure("diff_note", foreground="#555555")
        left_diff_text.tag_configure(
            "diff_changed", foreground="#8a1010", background="#ffc7ce")
        right_diff_text.tag_configure(
            "diff_changed", foreground="#126b12", background="#c6efce")

        def dialog_alive():
            try: return bool(dialog.winfo_exists())
            except tk.TclError: return False

        def populate():
            if not dialog_alive(): return
            root = self.fragment_root()
            needle = search_var.get().strip().casefold()
            tree.delete(*tree.get_children())
            state["visible"] = {}
            counts = {key: 0 for key in status_labels}
            shown = 0
            reselect_iid = ""
            for item in state["comparisons"]:
                counts[item["status"]] += 1
                if differences_only_var.get() and item["status"] == "match":
                    continue
                if hide_missing_source_var.get() and \
                        item["status"] == "missing_source":
                    continue
                paths = ", ".join(os.path.relpath(value["path"], root) for value in item["fragments"])
                sample_name = item.get("sample_name", item["name"])
                display_name = ("{} → {}".format(sample_name, item["name"])
                                if sample_name != item["name"] else item["name"])
                function_update_label = item.get(
                    "function_update_label",
                    "判定不能（関数単位の同期履歴なし）")
                searchable = "{} {} {} {} {}".format(
                    display_name, item["name"], paths,
                    item_status_label(item), function_update_label).casefold()
                if needle and needle not in searchable:
                    continue
                iid = tree.insert("", "end", text=display_name,
                                  values=(item_status_label(item),
                                          function_update_label, paths),
                                  tags=(item["status"],))
                state["visible"][iid] = item
                if item["name"] == state.get("reselect_name", ""):
                    reselect_iid = iid
                shown += 1
            summary_var.set("表示{} / 全{}件 / 一致{} / 処理差{} / 名前差{} / 未登録{} / 重複{}".format(
                shown, len(state["comparisons"]), counts["match"], counts["different"],
                counts["name_different"],
                counts["missing_source"], counts["duplicate"]))
            if reselect_iid:
                state["reselect_name"] = ""
                tree.selection_set(reselect_iid)
                tree.focus(reselect_iid)
                tree.see(reselect_iid)
            show_selected_diff()

        def comparison_source():
            root, folder = self.fragment_root(), folder_var.get()
            editor_source = self.editor.get("1.0", "end-1c")
            editor_path = os.path.abspath(self.current_path) if self.current_path else ""
            selected_path = source_path_var.get().strip()
            if not selected_path:
                origins = sample_sync_source_paths(root, folder)
                if len(origins) == 1:
                    selected_path = origins[0]
                    source_path_var.set(selected_path)
                elif len(origins) > 1:
                    raise ValueError(
                        "元ソースが複数あります。比較ソースを選択してください。")
            selected_abs = os.path.abspath(selected_path) if selected_path else ""
            if selected_abs:
                source, source_mode = comparison_source_text(
                    selected_abs, editor_path, editor_source,
                    self.editor_dirty)
                same_editor = bool(editor_path) and (
                    os.path.normcase(editor_path) ==
                    os.path.normcase(selected_abs))
                # A clean editor can safely follow an external file update.
                # Keeping it synchronized also prevents a later Save from
                # reviving the old function definitions.
                if same_editor and source_mode == "disk" and \
                        source != editor_source:
                    self.set_editor_content(source, selected_abs)
            else:
                try:
                    tree_value = ast.parse(editor_source)
                except SyntaxError:
                    tree_value = None
                if tree_value is None or not any(
                        isinstance(node, ast.ClassDef) for node in tree_value.body):
                    raise ValueError(
                        "比較する元ソースを選択してください。\n"
                        "サンプルに元ソース情報があれば自動選択します。")
                source, selected_abs = editor_source, editor_path
                source_mode = "editor"
            # Produce the specific class error before starting the worker.
            tree_value = ast.parse(source)
            if not any(isinstance(node, ast.ClassDef) for node in tree_value.body):
                raise ValueError("比較ソース内にクラスがありません。")
            return source, selected_abs, source_mode

        def reload_comparison_source():
            selected = source_path_var.get().strip()
            if not selected:
                messagebox.showwarning(
                    "サンプル関数チェック", "比較ソースを選択してください。",
                    parent=dialog)
                return
            selected_abs = os.path.abspath(selected)
            editor_path = (os.path.abspath(self.current_path)
                           if self.current_path else "")
            same_editor = bool(editor_path) and (
                os.path.normcase(editor_path) ==
                os.path.normcase(selected_abs))
            if same_editor and self.editor_dirty and not messagebox.askyesno(
                    "比較ソースを再読込",
                    "未保存のエディタ編集があります。破棄してディスク上の内容を再読込しますか？",
                    parent=dialog):
                return
            try:
                source, _ = comparison_source_text(
                    selected_abs, editor_path,
                    self.editor.get("1.0", "end-1c"), editor_dirty=False)
            except OSError as error:
                messagebox.showwarning(
                    "サンプル関数チェック", str(error), parent=dialog)
                return
            if same_editor:
                self.set_editor_content(source, selected_abs)
            refresh()

        def refresh():
            root = self.fragment_root()
            try:
                folder = resolve_fragment_folder(root, folder_var.get())
                if os.path.normcase(os.path.abspath(folder_var.get())) != \
                        os.path.normcase(folder):
                    folder_var.set(folder)
                    self.fragment_folder.set(folder)
                source, source_path, source_mode = comparison_source()
            except (OSError, SyntaxError, ValueError) as error:
                messagebox.showwarning("サンプル関数チェック", str(error), parent=dialog)
                return
            state["source"], state["source_path"] = source, source_path
            source_mode_var.set(
                "比較元: 未保存のエディタ内容" if source_mode == "editor"
                else "比較元: ディスク再読込済み")
            def completed(comparisons):
                if not dialog_alive(): return
                state["comparisons"] = comparisons
                populate()
                if not comparisons:
                    messagebox.showwarning(
                        "サンプル関数チェック",
                        "比較フォルダーにサンプル関数がありません。\n"
                        "比較フォルダーと登録元ソースを確認してください。",
                        parent=dialog)
            def failed(error):
                if dialog_alive(): messagebox.showwarning("サンプル関数チェック", str(error), parent=dialog)
            self.run_background("sample_function_check", "サンプル関数を比較中",
                                lambda: compare_sample_function_folder(
                                    source, root, folder, source_path,
                                    source_unsaved=(source_mode == "editor")),
                                completed, failed)

        def choose_source():
            initial = source_path_var.get().strip() or self.root_dir.get()
            selected = filedialog.askopenfilename(
                parent=dialog,
                initialdir=os.path.dirname(initial) if os.path.isfile(initial) else initial,
                filetypes=(("Python", "*.py"), ("すべて", "*.*")))
            if selected:
                source_path_var.set(selected)
                refresh()

        def choose_folder():
            selected = filedialog.askdirectory(parent=dialog, initialdir=folder_var.get() or self.fragment_root())
            if selected:
                try:
                    selected = resolve_fragment_folder(
                        self.fragment_root(), selected)
                except ValueError as error:
                    messagebox.showwarning(
                        "サンプル関数チェック", str(error), parent=dialog)
                    return
                folder_var.set(selected)
                self.fragment_folder.set(selected)
                # Let the newly selected folder infer its recorded origin.
                if not (self.current_path and str(self.current_path).lower().endswith(".py")):
                    source_path_var.set("")
                refresh()

        def selected_items():
            return [state["visible"][iid] for iid in tree.selection() if iid in state["visible"]]

        diff_change_state = {"rows": [], "index": -1}

        def move_diff_change(direction):
            changed_rows = diff_change_state["rows"]
            if not changed_rows:
                diff_position_var.set("差分0件")
                return
            diff_change_state["index"] = (
                diff_change_state["index"] + int(direction)) % len(changed_rows)
            row_number = changed_rows[diff_change_state["index"]]
            for widget in (left_diff_text, right_diff_text):
                widget.configure(state="normal")
                widget.tag_remove("diff_current_marker", "1.0", "end")
                widget.tag_add(
                    "diff_current_marker", "{}.0".format(row_number),
                    "{}.1".format(row_number))
                widget.configure(state="disabled")
                widget.see("{}.0".format(row_number))
            diff_position_var.set(
                "差分 {}/{}".format(
                    diff_change_state["index"] + 1, len(changed_rows)))

        def render_diff_rows(rows):
            for widget in (left_diff_text, right_diff_text):
                widget.configure(state="normal")
                widget.delete("1.0", "end")
            for row_index, row in enumerate(rows, 1):
                changed = row["kind"] != "equal"
                marker = "!" if changed else " "
                for side, widget in (("left", left_diff_text),
                                     ("right", right_diff_text)):
                    number = row[side + "_line"]
                    number_text = "" if number is None else str(number)
                    prefix = "{} {:>5} │ ".format(marker, number_text)
                    line_index = "{}.0".format(row_index)
                    widget.insert("end", prefix + row[side] + "\n")
                    widget.tag_add(
                        "diff_marker" if changed else "diff_gutter",
                        line_index, "{}+1c".format(line_index))
                    widget.tag_add(
                        "diff_gutter", "{}+1c".format(line_index),
                        "{}+{}c".format(line_index, len(prefix)))
                    for start, end in row[side + "_spans"]:
                        widget.tag_add(
                            "diff_changed",
                            "{}+{}c".format(line_index, len(prefix) + start),
                            "{}+{}c".format(line_index, len(prefix) + end))
            diff_change_state["rows"] = [
                index for index, row in enumerate(rows, 1)
                if row["kind"] != "equal"]
            diff_change_state["index"] = -1
            diff_position_var.set(
                "差分{}件".format(len(diff_change_state["rows"])))
            if not rows:
                for widget in (left_diff_text, right_diff_text):
                    widget.insert("1.0", "差分はありません。", "diff_note")
            for widget in (left_diff_text, right_diff_text):
                widget.configure(state="disabled")
                widget.yview_moveto(0.0)
                widget.xview_moveto(0.0)
            if diff_change_state["rows"]:
                move_diff_change(1)

        def set_diff_message(message):
            left_diff_title.set("現在ソース")
            right_diff_title.set("サンプル関数")
            diff_change_state["rows"] = []
            diff_change_state["index"] = -1
            diff_position_var.set("")
            for widget in (left_diff_text, right_diff_text):
                widget.configure(state="normal")
                widget.delete("1.0", "end")
                widget.insert("1.0", message, "diff_note")
                widget.configure(state="disabled")

        def clear_duplicate_comparison():
            duplicate_compare_state["item"] = None
            duplicate_compare_state["fragments"] = {}
            duplicate_left_var.set("")
            duplicate_right_var.set("")
            duplicate_left_stats_var.set("")
            duplicate_right_stats_var.set("")
            duplicate_count_var.set("サンプル関数: 0件")
            duplicate_left_combo.configure(state="disabled", values=())
            duplicate_right_combo.configure(state="disabled", values=())
            duplicate_left_open.configure(state="disabled")
            duplicate_right_open.configure(state="disabled")
            duplicate_left_edit.configure(state="disabled")
            duplicate_right_edit.configure(state="disabled")
            duplicate_left_to_right.configure(state="disabled")
            duplicate_right_to_left.configure(state="disabled")
            duplicate_merge_to_right.configure(state="disabled")
            duplicate_merge_to_left.configure(state="disabled")

        def render_duplicate_comparison(*_args):
            item = duplicate_compare_state.get("item")
            fragments_by_label = duplicate_compare_state.get("fragments", {})
            left = fragments_by_label.get(duplicate_left_var.get())
            right = fragments_by_label.get(duplicate_right_var.get())
            if not item or not left or not right:
                return
            labels = list(fragments_by_label)
            left_index = labels.index(duplicate_left_var.get()) + 1
            right_index = labels.index(duplicate_right_var.get()) + 1
            duplicate_count_var.set(
                "サンプル関数: {}件（左 {}/{}・右 {}/{}）".format(
                    len(labels), left_index, len(labels),
                    right_index, len(labels)))
            left_path = os.path.relpath(
                left["path"], self.fragment_root())
            right_path = os.path.relpath(
                right["path"], self.fragment_root())
            left_name = left.get(
                "sample_name", item.get("sample_name", item["name"]))
            right_name = right.get(
                "sample_name", item.get("sample_name", item["name"]))
            try:
                with open(left["path"], "r", encoding="utf-8") as stream:
                    left_stats = fragment_function_stats(stream.read(), left_name)
                with open(right["path"], "r", encoding="utf-8") as stream:
                    right_stats = fragment_function_stats(stream.read(), right_name)
            except (OSError, SyntaxError, ValueError):
                left_stats = {"function_count": "?", "reference_count": "?"}
                right_stats = {"function_count": "?", "reference_count": "?"}
            left_diff_title.set("左サンプル: " + left_path)
            right_diff_title.set("右サンプル: " + right_path)
            duplicate_left_stats_var.set(
                "左参照: {} / ファイル内サンプル関数: {}件 / 対象関数参照: {}件".format(
                    left_path, left_stats["function_count"],
                    left_stats["reference_count"]))
            duplicate_right_stats_var.set(
                "右参照: {} / ファイル内サンプル関数: {}件 / 対象関数参照: {}件".format(
                    right_path, right_stats["function_count"],
                    right_stats["reference_count"]))
            render_diff_rows(side_by_side_diff_rows(
                left.get("text", ""), right.get("text", "")))
            detail = ("同内容" if item.get("duplicate_kind") == "same"
                      else "内容差あり")
            diff_status_var.set(
                "{}: 重複サンプル同士を比較中（{}）".format(
                    item["name"], detail))

        def configure_duplicate_comparison(item):
            source_record = item.get("source")
            source_normalized = (
                source_record.get("normalized", "") if source_record else "")
            labels = []
            fragments_by_label = {}
            for fragment in item.get("fragments", []):
                matches = bool(source_record) and (
                    fragment.get("comparison_normalized", "") ==
                    source_normalized)
                relation = "ソース一致" if matches else "内容差あり"
                relative = os.path.relpath(
                    fragment["path"], self.fragment_root())
                try:
                    with open(fragment["path"], "r", encoding="utf-8") as stream:
                        stats = fragment_function_stats(
                            stream.read(), fragment.get(
                                "sample_name",
                                item.get("sample_name", item["name"])))
                    count_label = "{}関数/{}参照".format(
                        stats["function_count"], stats["reference_count"])
                except (OSError, SyntaxError, ValueError):
                    count_label = "件数不明"
                label = "[{}・{}] {}".format(
                    relation, count_label, relative)
                labels.append(label)
                fragments_by_label[label] = fragment
            duplicate_compare_state["item"] = item
            duplicate_compare_state["fragments"] = fragments_by_label
            duplicate_count_var.set("サンプル関数: {}件".format(len(labels)))
            duplicate_left_combo.configure(state="readonly", values=labels)
            duplicate_right_combo.configure(state="readonly", values=labels)
            duplicate_left_open.configure(state="normal")
            duplicate_right_open.configure(state="normal")
            duplicate_left_edit.configure(state="normal")
            duplicate_right_edit.configure(state="normal")
            duplicate_left_to_right.configure(state="normal")
            duplicate_right_to_left.configure(state="normal")
            duplicate_merge_to_right.configure(state="normal")
            duplicate_merge_to_left.configure(state="normal")
            duplicate_left_var.set(labels[0] if labels else "")
            duplicate_right_var.set(
                labels[1] if len(labels) > 1 else (labels[0] if labels else ""))
            render_duplicate_comparison()

        def open_duplicate_in_vscode(side):
            label = (duplicate_left_var.get() if side == "left"
                     else duplicate_right_var.get())
            fragment = duplicate_compare_state.get("fragments", {}).get(label)
            if not fragment:
                return
            if not self._open_path_in_vscode(
                    fragment["path"], fragment.get("start", 0) + 1):
                messagebox.showwarning(
                    "VSCode", "VSCodeでファイルを開けませんでした。",
                    parent=dialog)

        def edit_duplicate_sample(side, merge_from_side=None):
            label = (duplicate_left_var.get() if side == "left"
                     else duplicate_right_var.get())
            fragment = duplicate_compare_state.get("fragments", {}).get(label)
            item = duplicate_compare_state.get("item")
            if not fragment or not item:
                return
            merge_source = None
            if merge_from_side:
                merge_label = (duplicate_left_var.get()
                               if merge_from_side == "left"
                               else duplicate_right_var.get())
                merge_source = duplicate_compare_state.get(
                    "fragments", {}).get(merge_label)
                if not merge_source:
                    return
                if os.path.abspath(merge_source["path"]) == os.path.abspath(
                        fragment["path"]):
                    messagebox.showinfo(
                        "サンプル関数のマージ編集",
                        "左右に同じサンプルが選択されています。",
                        parent=dialog)
                    return
            path = fragment["path"]
            function_name = fragment.get(
                "sample_name", item.get("sample_name", item["name"]))
            editor_window = tk.Toplevel(dialog)
            editor_window.title(
                ("サンプル関数をマージ編集 - " if merge_source else
                 "サンプル関数を手動編集 - ") + function_name)
            editor_window.geometry("1180x720" if merge_source else "980x680")
            editor_window.transient(dialog)
            header = ttk.Frame(editor_window)
            header.pack(fill="x", padx=8, pady=(8, 3))
            ttk.Label(
                header, text=os.path.relpath(path, self.fragment_root()),
                anchor="w").pack(side="left", fill="x", expand=True)
            ttk.Label(
                header,
                text=("左の参照内容を見ながら、右の統合結果を編集します。"
                      if merge_source else
                      "差分画面を残したまま、この関数だけ編集します。"),
                foreground="#174a7e").pack(side="right")
            body = ttk.Frame(editor_window)
            body.pack(fill="both", expand=True, padx=8, pady=4)
            edit_container = body
            if merge_source:
                merge_panes = ttk.Panedwindow(body, orient="horizontal")
                merge_panes.pack(fill="both", expand=True)
                reference_frame = ttk.LabelFrame(
                    merge_panes, text="反映元（参照専用）")
                edit_container = ttk.LabelFrame(
                    merge_panes, text="マージ結果（ここを編集して反映先へ保存）")
                merge_panes.add(reference_frame, weight=1)
                merge_panes.add(edit_container, weight=1)
                reference_text = tk.Text(
                    reference_frame, wrap="none",
                    font=tkfont.nametofont("TkFixedFont"))
                reference_y = ttk.Scrollbar(
                    reference_frame, orient="vertical",
                    command=reference_text.yview)
                reference_x = ttk.Scrollbar(
                    reference_frame, orient="horizontal",
                    command=reference_text.xview)
                reference_text.configure(
                    yscrollcommand=reference_y.set,
                    xscrollcommand=reference_x.set)
                reference_text.grid(column=0, row=0, sticky="nsew")
                reference_y.grid(column=1, row=0, sticky="ns")
                reference_x.grid(column=0, row=1, sticky="ew")
                reference_frame.columnconfigure(0, weight=1)
                reference_frame.rowconfigure(0, weight=1)
                source_name = merge_source.get(
                    "sample_name", item.get("sample_name", item["name"]))
                reference = merge_source.get("text", "")
                if source_name != function_name:
                    reference = rename_source_functions(
                        reference, {source_name: function_name},
                        require_definitions=True)
                reference_text.insert("1.0", reference)
                reference_text.configure(state="disabled")
            edit_text = tk.Text(
                edit_container, wrap="none", undo=True,
                font=tkfont.nametofont("TkFixedFont"))
            edit_y = ttk.Scrollbar(edit_container, orient="vertical",
                                   command=edit_text.yview)
            edit_x = ttk.Scrollbar(edit_container, orient="horizontal",
                                   command=edit_text.xview)
            edit_text.configure(yscrollcommand=edit_y.set,
                                xscrollcommand=edit_x.set)
            edit_text.grid(column=0, row=0, sticky="nsew")
            edit_y.grid(column=1, row=0, sticky="ns")
            edit_x.grid(column=0, row=1, sticky="ew")
            edit_container.columnconfigure(0, weight=1)
            edit_container.rowconfigure(0, weight=1)
            edit_text.insert("1.0", fragment.get("text", ""))
            edit_status = tk.StringVar(value="")
            merge_diff_status = tk.StringVar(value="")
            footer = ttk.Frame(editor_window)
            footer.pack(fill="x", padx=8, pady=(3, 8))
            ttk.Label(footer, textvariable=edit_status,
                      foreground="#a00000").pack(side="left")

            if merge_source:
                merge_diff_state = {
                    "rows": [], "index": -1, "after_id": None}
                reference_text.tag_configure(
                    "merge_changed", foreground="#8a1010",
                    background="#ffc7ce")
                edit_text.tag_configure(
                    "merge_changed", foreground="#126b12",
                    background="#c6efce")
                for widget in (reference_text, edit_text):
                    widget.tag_configure(
                        "merge_current", background="#fff2cc",
                        relief="solid", borderwidth=1)

                def mark_merge_line(widget, line_number, spans, tag):
                    if line_number is None:
                        return
                    line_start = "{}.0".format(line_number)
                    if spans:
                        for start, end in spans:
                            widget.tag_add(
                                tag,
                                "{}+{}c".format(line_start, start),
                                "{}+{}c".format(line_start, end))
                    else:
                        widget.tag_add(
                            tag, line_start, "{}.end+1c".format(line_number))

                def refresh_merge_diff():
                    merge_diff_state["after_id"] = None
                    right_value = edit_text.get("1.0", "end-1c")
                    rows = side_by_side_diff_rows(reference, right_value)
                    changed = [row for row in rows if row["kind"] != "equal"]
                    for widget in (reference_text, edit_text):
                        widget.tag_remove("merge_changed", "1.0", "end")
                        widget.tag_remove("merge_current", "1.0", "end")
                    for row in changed:
                        mark_merge_line(
                            reference_text, row["left_line"],
                            row["left_spans"], "merge_changed")
                        mark_merge_line(
                            edit_text, row["right_line"],
                            row["right_spans"], "merge_changed")
                    merge_diff_state["rows"] = changed
                    merge_diff_state["index"] = -1
                    merge_diff_status.set(
                        "差分{}行（赤=反映元、緑=マージ結果）".format(
                            len(changed)))

                def schedule_merge_diff(_event=None):
                    if not edit_text.edit_modified():
                        return
                    edit_text.edit_modified(False)
                    previous = merge_diff_state.get("after_id")
                    if previous:
                        try:
                            editor_window.after_cancel(previous)
                        except tk.TclError:
                            pass
                    merge_diff_state["after_id"] = editor_window.after(
                        180, refresh_merge_diff)

                def move_merge_diff(direction):
                    rows = merge_diff_state["rows"]
                    if not rows:
                        merge_diff_status.set("差分0行")
                        return
                    merge_diff_state["index"] = (
                        merge_diff_state["index"] + int(direction)) % len(rows)
                    selected = rows[merge_diff_state["index"]]
                    for widget, key in (
                            (reference_text, "left_line"),
                            (edit_text, "right_line")):
                        widget.tag_remove("merge_current", "1.0", "end")
                        line_number = selected[key]
                        if line_number is not None:
                            widget.tag_add(
                                "merge_current",
                                "{}.0".format(line_number),
                                "{}.end+1c".format(line_number))
                            widget.see("{}.0".format(line_number))
                    merge_diff_status.set(
                        "差分 {}/{}（赤=反映元、緑=マージ結果）".format(
                            merge_diff_state["index"] + 1, len(rows)))

                ttk.Label(
                    footer, textvariable=merge_diff_status,
                    foreground="#174a7e").pack(side="left", padx=(12, 3))
                ttk.Button(
                    footer, text="▲ 前の差分",
                    command=lambda: move_merge_diff(-1)).pack(
                        side="left", padx=2)
                ttk.Button(
                    footer, text="次の差分 ▼",
                    command=lambda: move_merge_diff(1)).pack(
                        side="left", padx=2)
                edit_text.edit_modified(False)
                edit_text.bind("<<Modified>>", schedule_merge_diff)
                refresh_merge_diff()

            def save_manual_edit():
                try:
                    with open(path, "r", encoding="utf-8") as stream:
                        current_fragment = stream.read()
                    updated_fragment = replace_fragment_function_text(
                        current_fragment, function_name,
                        edit_text.get("1.0", "end-1c"))
                    backup = create_sample_sync_backup(
                        state.get("source_path", ""), state.get("source", ""),
                        state.get("comparisons", []), [item["name"]],
                        backup_root)
                    temporary = path + ".manual-edit.tmp"
                    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
                        stream.write(updated_fragment)
                    os.replace(temporary, path)
                except (OSError, SyntaxError, ValueError) as error:
                    edit_status.set(str(error))
                    return
                state["last_backup"] = backup["manifest_path"]
                backup_status_var.set(
                    "復元可能: {} / {}".format(
                        backup["created"],
                        "サンプル関数のマージ編集" if merge_source
                        else "手動編集"))
                self._fragment_catalog_cache = None
                self.refresh_index()
                self.refresh_registered_fragment_choices()
                editor_window.destroy()
                state["reselect_name"] = item["name"]
                refresh()
                self.status.set(
                    "{} を{}保存しました。再チェック済みです。".format(
                        function_name,
                        "マージ編集して" if merge_source else "手動"))

            ttk.Button(
                footer,
                text=("マージ結果を反映先へ保存して再チェック"
                      if merge_source else "保存して再チェック"),
                       command=save_manual_edit).pack(side="right", padx=3)
            ttk.Button(footer, text="キャンセル",
                       command=editor_window.destroy).pack(side="right", padx=3)

        def discard_duplicate_sample(keep_side, discard_side):
            """Keep one duplicate and remove the other registration/definition."""
            variables = {
                "left": duplicate_left_var,
                "right": duplicate_right_var,
            }
            fragments_by_label = duplicate_compare_state.get("fragments", {})
            item = duplicate_compare_state.get("item")
            keep_fragment = fragments_by_label.get(variables[keep_side].get())
            discard_fragment = fragments_by_label.get(
                variables[discard_side].get())
            if not item or not keep_fragment or not discard_fragment:
                return
            if item.get("status") != "duplicate" or \
                    len(item.get("fragments", [])) < 2:
                messagebox.showwarning(
                    "重複サンプルの再チェック",
                    "現在の一覧情報では重複ではありません。再チェックしてから操作してください。",
                    parent=dialog)
                return
            keep_path = os.path.abspath(keep_fragment["path"])
            discard_path = os.path.abspath(discard_fragment["path"])
            if keep_path == discard_path:
                messagebox.showinfo(
                    "重複サンプルの破棄",
                    "左右に同じサンプルが選択されています。",
                    parent=dialog)
                return
            discard_name = discard_fragment.get(
                "sample_name", item.get("sample_name", item["name"]))
            keep_name = keep_fragment.get(
                "sample_name", item.get("sample_name", item["name"]))
            try:
                with open(keep_path, "r", encoding="utf-8") as stream:
                    keep_source = stream.read()
                with open(discard_path, "r", encoding="utf-8") as stream:
                    discard_source = stream.read()
                keep_records = sample_sync_function_records(
                    keep_source, class_only=False)
                records = sample_sync_function_records(
                    discard_source, class_only=False)
                if keep_name not in keep_records:
                    raise ValueError(
                        "採用対象の関数が見つかりません: " + keep_name)
                if discard_name not in records:
                    raise ValueError(
                        "破棄対象の関数が見つかりません: " + discard_name)
                stats = fragment_function_stats(discard_source, discard_name)

                canonical_name = item["name"]
                keep_function = keep_records[keep_name]["text"]
                discard_function = records[discard_name]["text"]
                if keep_name != canonical_name:
                    keep_function = rename_source_functions(
                        keep_function, {keep_name: canonical_name},
                        require_definitions=True)
                if discard_name != canonical_name:
                    discard_function = rename_source_functions(
                        discard_function, {discard_name: canonical_name},
                        require_definitions=True)
                normalize = lambda value: "\n".join(
                    line.rstrip() for line in
                    textwrap.dedent(value).strip().splitlines())
                same_content = (
                    normalize(keep_function) == normalize(discard_function))
            except (OSError, SyntaxError, ValueError) as error:
                messagebox.showerror(
                    "重複サンプルの破棄", str(error), parent=dialog)
                return

            catalog_record = None
            if len(records) == 1:
                for catalog_item in self.fragment_catalog():
                    try:
                        metadata, _, metadata_path, body_path = load_fragment(
                            self.fragment_root(), catalog_item["id"])
                    except (OSError, ValueError, KeyError):
                        continue
                    if os.path.normcase(os.path.abspath(body_path)) == \
                            os.path.normcase(discard_path):
                        catalog_record = {
                            "id": catalog_item["id"],
                            "metadata": metadata,
                            "metadata_path": metadata_path,
                            "body_path": body_path,
                        }
                        break
                if catalog_record is None:
                    messagebox.showerror(
                        "重複サンプルの破棄",
                        "単独サンプルの登録情報を特定できないため破棄できません。",
                        parent=dialog)
                    return

            keep_label = os.path.relpath(keep_path, self.fragment_root())
            discard_label = os.path.relpath(discard_path, self.fragment_root())
            if len(records) > 1:
                removal_detail = (
                    "破棄先は複数関数ファイルのため、対象関数の定義だけを削除します。")
            else:
                removal_detail = (
                    "破棄先は単独サンプルのため、登録情報とファイルを削除します。")
            duplicate_result = (
                "重複再チェック: 同じ検知名・同内容の重複です。"
                if same_content else
                "重複再チェック: 同じ検知名ですが、関数内容には差があります。")
            reference_warning = ""
            if stats["reference_count"]:
                reference_warning = (
                    "\n\n注意: 破棄先ファイル内に対象関数への参照が{}件あります。"
                    "採用側のサンプルも同時に使用してください。".format(
                        stats["reference_count"]))
            if not messagebox.askyesno(
                    "重複サンプルを1つにする",
                    "現在ソースは変更しません。復元用バックアップを作成します。\n\n"
                    "{}\n\n採用して残す: {}\n破棄する: {}\n\n{}{}\n\n"
                    "この重複サンプルを破棄しますか？".format(
                        duplicate_result, keep_label, discard_label,
                        removal_detail, reference_warning),
                    parent=dialog):
                return

            sample_lists_path = self.sample_lists_path()
            extra_paths = ([sample_lists_path]
                           if os.path.isfile(sample_lists_path) else [])
            backup = None
            try:
                backup = create_sample_sync_backup(
                    state.get("source_path", ""), state.get("source", ""),
                    state.get("comparisons", []), [item["name"]],
                    backup_root, extra_paths=extra_paths)
                if len(records) > 1:
                    updated = remove_fragment_function_text(
                        discard_source, discard_name)
                    temporary = discard_path + ".discard-duplicate.tmp"
                    with open(temporary, "w", encoding="utf-8",
                              newline="\n") as stream:
                        stream.write(updated)
                    os.replace(temporary, discard_path)
                else:
                    fragment_id = catalog_record["id"]
                    lists = self._read_sample_lists()
                    for sample_list in lists["lists"].values():
                        sample_list["members"] = [
                            member for member in sample_list["members"]
                            if not (member.get("type") == "fragment" and
                                    member.get("id") == fragment_id)]
                    if os.path.isfile(catalog_record["body_path"]):
                        os.remove(catalog_record["body_path"])
                    if os.path.isfile(catalog_record["metadata_path"]):
                        os.remove(catalog_record["metadata_path"])
                    self._write_sample_lists(lists)
                    try:
                        os.rmdir(os.path.dirname(
                            catalog_record["metadata_path"]))
                    except OSError:
                        pass
            except (OSError, SyntaxError, ValueError, KeyError) as error:
                if backup:
                    try:
                        restore_sample_sync_backup(backup["manifest_path"])
                    except (OSError, ValueError, KeyError):
                        pass
                messagebox.showerror(
                    "重複サンプルの破棄", str(error), parent=dialog)
                return

            state["last_backup"] = backup["manifest_path"]
            backup_status_var.set(
                "復元可能: {} / 重複サンプルを1件破棄".format(
                    backup["created"]))
            self._fragment_catalog_cache = None
            self.refresh_index()
            self.refresh_registered_fragment_choices()
            self.refresh_sample_apply_lists()
            self.refresh_sample_lists_tab(
                select=self.sample_list_name.get().strip())
            self.refresh_catalog_tag_choices()
            self.rebuild_catalog_folder_tree()
            state["reselect_name"] = item["name"]
            refresh()
            self.status.set(
                "採用側を残し、重複サンプルを1件破棄しました。"
                "現在ソースは変更していません。")

        def reflect_duplicate_sample(source_side, target_side):
            variables = {
                "left": duplicate_left_var,
                "right": duplicate_right_var,
            }
            fragments_by_label = duplicate_compare_state.get("fragments", {})
            item = duplicate_compare_state.get("item")
            source_fragment = fragments_by_label.get(
                variables[source_side].get())
            target_fragment = fragments_by_label.get(
                variables[target_side].get())
            if not item or not source_fragment or not target_fragment:
                return
            source_path = source_fragment["path"]
            target_path = target_fragment["path"]
            if os.path.abspath(source_path) == os.path.abspath(target_path):
                messagebox.showinfo(
                    "サンプル関数の反映",
                    "左右に同じサンプルが選択されています。",
                    parent=dialog)
                return
            source_name = source_fragment.get(
                "sample_name", item.get("sample_name", item["name"]))
            target_name = target_fragment.get(
                "sample_name", item.get("sample_name", item["name"]))
            source_label = os.path.relpath(source_path, self.fragment_root())
            target_label = os.path.relpath(target_path, self.fragment_root())
            if not messagebox.askyesno(
                    "サンプル関数の反映（完全置換）",
                    "マージ処理ではありません。現在ソースも変更しません。\n\n"
                    "反映元を採用し、反映先の現在の関数内容を破棄して完全置換します。\n"
                    "反映先のサンプル登録・ファイル自体は残ります。\n"
                    "反映元: {}\n反映先: {}\n\n"
                    "反映先を完全置換しますか？".format(
                        source_label, target_label),
                    parent=dialog):
                return
            try:
                with open(target_path, "r", encoding="utf-8") as stream:
                    target_source = stream.read()
                updated_target = reflect_fragment_function_text(
                    source_fragment.get("text", ""), source_name,
                    target_source, target_name)
                backup = create_sample_sync_backup(
                    state.get("source_path", ""), state.get("source", ""),
                    state.get("comparisons", []), [item["name"]],
                    backup_root)
                temporary = target_path + ".sample-reflect.tmp"
                with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
                    stream.write(updated_target)
                os.replace(temporary, target_path)
            except (OSError, SyntaxError, ValueError) as error:
                messagebox.showerror(
                    "サンプル関数の反映", str(error), parent=dialog)
                return
            state["last_backup"] = backup["manifest_path"]
            backup_status_var.set(
                "復元可能: {} / サンプル関数を完全置換".format(
                    backup["created"]))
            self._fragment_catalog_cache = None
            self.refresh_index()
            self.refresh_registered_fragment_choices()
            state["reselect_name"] = item["name"]
            refresh()
            self.status.set(
                "選択したサンプル関数を反対側へ反映し、関数全体を置換しました。"
                "現在ソースは変更していません。")

        duplicate_left_combo.bind(
            "<<ComboboxSelected>>", render_duplicate_comparison)
        duplicate_right_combo.bind(
            "<<ComboboxSelected>>", render_duplicate_comparison)

        def show_selected_diff(*_args):
            items = selected_items()
            sample_to_source_button.configure(state="disabled")
            source_to_sample_button.configure(state="disabled")
            merge_name_body_button.configure(state="disabled")
            if len(items) != 1:
                clear_duplicate_comparison()
                message = "一覧から関数を1件選択すると差分を表示します。" if not items else \
                    "差分表示は1件ずつです（現在{}件選択）。".format(len(items))
                diff_status_var.set(message)
                set_diff_message(message)
                return
            item = items[0]
            fragments = item.get("fragments", [])
            if item["status"] == "duplicate" or len(fragments) > 1:
                configure_duplicate_comparison(item)
                return
            clear_duplicate_comparison()
            source_record = item.get("source")
            source_text = source_record.get("text", "") if source_record else ""
            sample_text = fragments[0].get("text", "") if fragments else ""
            path = fragments[0].get("path", "") if fragments else ""
            try:
                path_label = os.path.relpath(path, self.fragment_root()) if path else "サンプルなし"
            except ValueError:
                path_label = path or "サンプルなし"
            left_diff_title.set(
                "左: 現在ソース（赤=ソースのみ）: {}".format(item["name"]))
            right_diff_title.set(
                "右: サンプル関数（緑=サンプルのみ）: {}".format(path_label))
            render_diff_rows(side_by_side_diff_rows(source_text, sample_text))
            if item["status"] == "missing_source":
                diff_status_var.set("{}: 現在ソースに未登録。緑色部分をソースへ追加できます。".format(
                    item["name"]))
                sample_to_source_button.configure(state="normal")
            elif item["status"] == "different":
                diff_status_var.set("{}: 赤＝現在ソースのみ／緑＝サンプル関数のみ".format(item["name"]))
                sample_to_source_button.configure(state="normal")
                source_to_sample_button.configure(state="normal")
                if item.get("sample_name", item["name"]) != item["name"]:
                    merge_name_body_button.configure(state="normal")
            elif item["status"] == "name_different":
                diff_status_var.set(
                    "{}: 処理は一致。サンプル名をソースへ反映できます。".format(
                        item["name"]))
                merge_name_body_button.configure(state="normal")
            else:
                diff_status_var.set("{}: 一致（反映不要）".format(item["name"]))

        def mismatch_names(for_source, selected_only=False):
            allowed = ("different", "missing_source") if for_source else ("different",)
            source_items = selected_items() if selected_only else state["comparisons"]
            return [item["name"] for item in source_items if item["status"] in allowed]

        def library_to_source(selected_only=False):
            names = mismatch_names(True, selected_only)
            if not names:
                messagebox.showinfo("サンプル関数チェック", "ソースへ反映する不一致はありません。", parent=dialog); return
            target_path = ensure_source_save_path()
            if not target_path:
                return
            if not messagebox.askyesno(
                    "サンプル関数 → 実ソース保存",
                    "{}件の関数を反映し、次の実ソースへ保存しますか？\n\n{}\n\n"
                    "反映前のバックアップも作成します。".format(
                        len(names), target_path), parent=dialog):
                return
            source, comparisons = state["source"], list(state["comparisons"])
            def worker():
                backup = create_sample_sync_backup(
                    target_path, source, comparisons, names, backup_root,
                    source_will_be_saved=True)
                try:
                    updated = update_source_sample_functions(
                        source, comparisons, names)
                    saved_path = save_reflected_source(target_path, updated)
                    mark_comparisons_synchronized(
                        updated, comparisons, names)
                    return updated, saved_path, backup
                except Exception:
                    original, _, _ = restore_sample_sync_backup(
                        backup["manifest_path"])
                    save_reflected_source(target_path, original)
                    raise
            def completed(payload):
                if not dialog_alive(): return
                updated, saved_path, backup = payload
                state["last_backup"] = backup["manifest_path"]
                backup_status_var.set(
                    "復元可能: {} / {}関数を実ソースへ保存".format(
                        backup["created"], len(names)))
                show_saved_source(updated, saved_path)
                refresh()
                self.status.set(
                    "サンプル関数から{}件反映し、実ソースへ保存しました: {}".format(
                        len(names), saved_path))
            self.run_background(
                "sample_to_source", "サンプル関数を実ソースへ保存中",
                worker, completed,
                lambda error: messagebox.showerror(
                    "サンプル関数 → 実ソース保存", str(error),
                    parent=dialog))

        def source_to_library(selected_only=False):
            names = mismatch_names(False, selected_only)
            if not names:
                messagebox.showinfo("サンプル関数チェック", "サンプル関数へ反映する不一致はありません。", parent=dialog); return
            if not messagebox.askyesno("ソース → サンプル関数", "{}件のサンプル関数を現在のソース内容で更新しますか？".format(len(names)), parent=dialog): return
            source, comparisons = state["source"], list(state["comparisons"])
            def completed(changed):
                if not dialog_alive(): return
                refresh(); self.refresh_index(); self.refresh_registered_fragment_choices()
                self.status.set("ソースからサンプル関数{}件（{}ファイル）を更新しました。".format(len(names), len(changed)))
            self.run_background("source_to_samples", "ソース内容をサンプル関数へ反映中",
                                lambda: update_sample_function_fragments(source, comparisons, names), completed)

        def merge_names_and_source_bodies(selected_only=False):
            candidates = selected_items() if selected_only else state["comparisons"]
            items = [
                item for item in candidates
                if item.get("source") and len(item.get("fragments", [])) == 1 and
                item.get("status") in ("different", "name_different")]
            if not items:
                messagebox.showinfo(
                    "関数名と処理を統合",
                    "名前または処理を統合する対象はありません。",
                    parent=dialog)
                return
            names = [item["name"] for item in items]
            target_path = ensure_source_save_path()
            if not target_path:
                return
            mappings = [
                ("{} → {} / 処理はソース".format(
                    item["name"], item["sample_name"])
                 if item.get("sample_name", item["name"]) != item["name"]
                 else "{} / 名前はそのまま・処理はソース".format(
                    item["name"]))
                for item in items]
            preview = "\n".join(mappings[:15])
            if len(mappings) > 15:
                preview += "\nほか{}件".format(len(mappings) - 15)
            if not messagebox.askyesno(
                    "関数名と処理を統合",
                    "関数名はサンプル側、処理内容はソース側を採用します。\n"
                    "ソース内の関数定義と全参照も変更します。\n\n{}\n\n"
                    "対象: {}関数 / 改名: {}関数 / サンプル更新: {}ファイル\n"
                    "実ソース保存先: {}\n"
                    "反映前に自動バックアップし、失敗時は自動復元します。\n\n"
                    "一括反映しますか？".format(
                        preview, len(items),
                        sum(item.get("sample_name", item["name"]) != item["name"]
                            for item in items),
                        len({item["fragments"][0]["path"] for item in items}),
                        target_path),
                    parent=dialog):
                return
            source = state["source"]
            comparisons = list(state["comparisons"])

            def worker():
                backup = create_sample_sync_backup(
                    target_path, source, comparisons, names, backup_root,
                    source_will_be_saved=True)
                try:
                    result = merge_sample_names_with_source_bodies(
                        source, comparisons, names)
                    updated_source, _, _ = result
                    saved_path = save_reflected_source(
                        target_path, updated_source)
                    return result, saved_path, backup
                except Exception:
                    restore_sample_sync_backup(backup["manifest_path"])
                    raise

            def completed(payload):
                if not dialog_alive():
                    return
                result, saved_path, backup = payload
                updated_source, changed_paths, mapping = result
                state["last_backup"] = backup["manifest_path"]
                backup_status_var.set(
                    "復元可能: {} / {}関数".format(
                        backup["created"], len(backup.get("names", []))))
                show_saved_source(updated_source, saved_path)
                self._fragment_catalog_cache = None
                self.refresh_index()
                self.refresh_registered_fragment_choices()
                refresh()
                self.status.set(
                    "サンプル名を{}関数のソース定義・参照へ反映し、"
                    "ソース処理でサンプル{}ファイルを更新しました。"
                    " 実ソースへ保存済みです: {}".format(
                        len(mapping), len(changed_paths), saved_path))

            self.run_background(
                "merge_sample_names_source_bodies",
                "サンプル名とソース処理を統合中",
                worker, completed,
                lambda error: messagebox.showerror(
                    "関数名と処理を統合", str(error), parent=dialog))

        def rollback_last_batch():
            manifest_path = state.get("last_backup", "")
            if not manifest_path or not os.path.isfile(manifest_path):
                messagebox.showinfo(
                    "一括反映を戻す", "復元できる一括反映履歴はありません。",
                    parent=dialog)
                return
            if not messagebox.askyesno(
                    "一括反映を戻す",
                    "直前の一括反映前のサンプルとソース内容へ戻します。\n"
                    "保存先が記録されている場合は実ソースも復元して保存します。\n\n"
                    "復元しますか？", parent=dialog):
                return

            def worker():
                source_text, source_path, manifest = \
                    restore_sample_sync_backup(manifest_path)
                saved_path = (save_reflected_source(source_path, source_text)
                              if source_path and
                              manifest.get("source_was_saved") else "")
                return source_text, source_path, manifest, saved_path

            def completed(result):
                if not dialog_alive():
                    return
                source_text, source_path, manifest, saved_path = result
                if saved_path:
                    show_saved_source(source_text, saved_path)
                else:
                    self.set_editor_content(
                        source_text, source_path or self.current_path)
                    self.editor_dirty = True
                    self.update_editor_view()
                self._fragment_catalog_cache = None
                self.refresh_index()
                self.refresh_registered_fragment_choices()
                refresh()
                backup_status_var.set(
                    "復元済み: {}".format(manifest.get("created", "")))
                self.status.set(
                    "直前の一括反映前へ復元しました。"
                    + (" 実ソースも保存済みです。" if saved_path else
                       " 保存先がないためソースは未保存です。"))

            self.run_background(
                "rollback_sample_function_batch", "一括反映前へ復元中",
                worker, completed,
                lambda error: messagebox.showerror(
                    "一括反映を戻す", str(error), parent=dialog))

        def choose_fragment_path(item, title="編集するサンプルを選択"):
            fragments = list(item.get("fragments", []))
            if not fragments:
                return ""
            if len(fragments) == 1:
                return fragments[0]["path"]
            picker = tk.Toplevel(dialog)
            picker.title(title)
            picker.geometry("820x300")
            picker.transient(dialog)
            picker.grab_set()
            ttk.Label(
                picker,
                text="重複しているサンプルを個別に選択してください。"
            ).pack(fill="x", padx=8, pady=(8, 4))
            choices_frame = ttk.Frame(picker)
            choices_frame.pack(fill="both", expand=True, padx=8, pady=4)
            choices = ttk.Treeview(
                choices_frame, columns=("source", "path"), show="headings",
                selectmode="browse")
            choices.heading("source", text="現在ソースとの関係")
            choices.heading("path", text="サンプル関数ファイル")
            choices.column("source", width=170, anchor="center")
            choices.column("path", width=610)
            pack_scrollable_widget(choices, horizontal=True)
            by_iid = {}
            source_record = item.get("source")
            source_normalized = (
                source_record.get("normalized", "") if source_record else "")
            for fragment in fragments:
                matches = bool(source_record) and (
                    fragment.get("comparison_normalized", "") ==
                    source_normalized)
                iid = choices.insert(
                    "", "end",
                    values=("ソースと一致" if matches else "内容差あり",
                            os.path.relpath(
                                fragment["path"], self.fragment_root())))
                by_iid[iid] = fragment["path"]
            result = {"path": ""}

            def accept(*_args):
                selection = choices.selection()
                if not selection:
                    return
                result["path"] = by_iid[selection[0]]
                picker.destroy()

            buttons = ttk.Frame(picker)
            buttons.pack(fill="x", padx=8, pady=(0, 8))
            ttk.Button(buttons, text="選択", command=accept).pack(
                side="right", padx=3)
            ttk.Button(buttons, text="キャンセル", command=picker.destroy).pack(
                side="right", padx=3)
            first = choices.get_children()
            if first:
                choices.selection_set(first[0])
                choices.focus(first[0])
            choices.bind("<Double-1>", accept)
            dialog.wait_window(picker)
            return result["path"]

        def fragment_id_for(item, selected_path=""):
            if selected_path:
                wanted = os.path.abspath(selected_path)
            elif len(item.get("fragments", [])) == 1:
                wanted = os.path.abspath(item["fragments"][0]["path"])
            else:
                return None
            for catalog_item in self.fragment_catalog():
                try:
                    _, _, _, body_path = load_fragment(self.fragment_root(), catalog_item["id"])
                except (OSError, ValueError, KeyError):
                    continue
                if os.path.abspath(body_path) == wanted:
                    return catalog_item["id"]
            return None

        def edit_selected():
            items = selected_items()
            if len(items) != 1:
                messagebox.showinfo("関数置換", "編集するサンプル関数を1つ選択してください。", parent=dialog); return
            selected_path = choose_fragment_path(items[0])
            if not selected_path:
                return
            fragment_id = fragment_id_for(items[0], selected_path)
            if not fragment_id:
                messagebox.showwarning("関数置換", "サンプル関数の登録情報を特定できません。", parent=dialog); return
            dialog.destroy()
            self.load_fragment_for_editing(fragment_id)

        def open_selected_in_vscode():
            items = selected_items()
            if len(items) != 1:
                messagebox.showinfo(
                    "関数編集", "開くサンプル関数を1つ選択してください。",
                    parent=dialog)
                return
            selected_path = choose_fragment_path(
                items[0], "VSCodeで開くサンプルを選択")
            if not selected_path:
                return
            line = 1
            try:
                with open(selected_path, "r", encoding="utf-8") as stream:
                    fragment_source = stream.read()
                records = sample_sync_function_records(
                    fragment_source, class_only=False)
                sample_name = items[0].get("sample_name", items[0]["name"])
                if sample_name in records:
                    line = records[sample_name]["start"] + 1
            except (OSError, SyntaxError, ValueError):
                pass
            if not self._open_path_in_vscode(selected_path, line):
                messagebox.showwarning(
                    "VSCode", "VSCodeでファイルを開けませんでした。",
                    parent=dialog)

        def delete_selected():
            items = selected_items()
            if len(items) != 1:
                messagebox.showinfo("関数置換", "削除するサンプル関数を1つ選択してください。", parent=dialog); return
            fragment_id = fragment_id_for(items[0])
            if not fragment_id:
                messagebox.showwarning("関数置換", "サンプル関数の登録情報を特定できません。", parent=dialog); return
            if self.delete_fragment(fragment_id):
                refresh()

        def open_replacement_picker():
            """Choose one sample/file function and apply it to selected current methods."""
            picker = tk.Toplevel(dialog)
            picker.title("関数置換 - 置換元と反映先を選択")
            picker.geometry("1080x680")
            picker.transient(dialog)
            mode_var = tk.StringVar(value="サンプル関数")
            source_path_var = tk.StringVar(value=self.current_path or "")
            source_search_var = tk.StringVar()
            target_search_var = tk.StringVar()
            propagate_var = tk.BooleanVar(value=False)
            picker_state = {"sources": {}, "targets": {}, "specified": []}

            source_top = ttk.Frame(picker); source_top.pack(fill="x", padx=8, pady=(8, 3))
            ttk.Label(source_top, text="置換元:").pack(side="left")
            mode_combo = ttk.Combobox(source_top, textvariable=mode_var, state="readonly", width=18,
                                      values=("サンプル関数", "指定Pythonファイル"))
            mode_combo.pack(side="left", padx=4)
            source_path_entry = ttk.Entry(source_top, textvariable=source_path_var)
            source_path_entry.pack(side="left", fill="x", expand=True, padx=4)

            panes = ttk.Panedwindow(picker, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=5)
            source_frame = ttk.LabelFrame(panes, text="置換元関数（1つ）")
            target_frame = ttk.LabelFrame(panes, text="反映先関数（複数選択可）")
            panes.add(source_frame, weight=1); panes.add(target_frame, weight=1)
            source_filter = ttk.Frame(source_frame); source_filter.pack(fill="x", padx=5, pady=5)
            ttk.Label(source_filter, text="検索:").pack(side="left")
            ttk.Entry(source_filter, textvariable=source_search_var).pack(side="left", fill="x", expand=True, padx=3)
            source_tree_frame = ttk.Frame(source_frame)
            source_tree_frame.pack(
                fill="both", expand=True, padx=5, pady=(0, 5))
            source_tree = ttk.Treeview(source_tree_frame, columns=("origin",), show="tree headings", selectmode="browse")
            source_tree.heading("#0", text="関数名"); source_tree.heading("origin", text="取得元")
            source_tree.column("#0", width=240); source_tree.column("origin", width=280)
            pack_scrollable_widget(source_tree, horizontal=True)
            target_filter = ttk.Frame(target_frame); target_filter.pack(fill="x", padx=5, pady=5)
            ttk.Label(target_filter, text="検索:").pack(side="left")
            ttk.Entry(target_filter, textvariable=target_search_var).pack(side="left", fill="x", expand=True, padx=3)
            target_tree_frame = ttk.Frame(target_frame)
            target_tree_frame.pack(
                fill="both", expand=True, padx=5, pady=(0, 5))
            target_tree = ttk.Treeview(target_tree_frame, columns=("line",), show="tree headings", selectmode="extended")
            target_tree.heading("#0", text="関数名"); target_tree.heading("line", text="現在ソースの行")
            target_tree.column("#0", width=300); target_tree.column("line", width=140)
            pack_scrollable_widget(target_tree, horizontal=True)

            options = ttk.Frame(picker); options.pack(fill="x", padx=8, pady=3)
            propagate_check = ttk.Checkbutton(
                options, text="サンプル関数の場合、プロジェクト内の同名関数の使用箇所すべてへ反映",
                variable=propagate_var)
            propagate_check.pack(side="left")

            def read_path_source(path):
                if path and self.current_path and os.path.abspath(path) == os.path.abspath(self.current_path):
                    return self.editor.get("1.0", "end-1c")
                return "".join(self._read_lines(path))

            def load_specified(show_errors=True):
                path = source_path_var.get().strip()
                if not path or not os.path.isfile(path):
                    picker_state["specified"] = []
                    if show_errors:
                        messagebox.showwarning("関数置換", "取得元のPythonファイルを選択してください。", parent=picker)
                    return
                try:
                    specified_source = read_path_source(path)
                    try:
                        records = sample_sync_function_records(specified_source, class_only=True)
                    except ValueError:
                        records = sample_sync_function_records(specified_source, class_only=False)
                except (SyntaxError, ValueError) as error:
                    picker_state["specified"] = []
                    if show_errors:
                        messagebox.showwarning("関数置換", "指定ファイルの関数を読み込めません:\n{}".format(error), parent=picker)
                    return
                picker_state["specified"] = [dict(record, name=name, path=path, kind="specified")
                                             for name, record in records.items()]

            def populate_sources():
                source_tree.delete(*source_tree.get_children())
                picker_state["sources"] = {}
                needle = source_search_var.get().strip().casefold()
                if mode_var.get() == "サンプル関数":
                    values = []
                    for item in state["comparisons"]:
                        if item.get("status") == "duplicate" or len(item.get("fragments", [])) != 1:
                            continue
                        fragment = item["fragments"][0]
                        values.append({"name": item["name"], "text": fragment["text"], "path": fragment["path"],
                                       "kind": "sample", "item": item})
                else:
                    values = picker_state["specified"]
                for value in sorted(values, key=lambda row: row["name"].casefold()):
                    origin = os.path.relpath(value["path"], self.root_dir.get()) if value.get("path") else ""
                    if needle and needle not in (value["name"] + " " + origin).casefold():
                        continue
                    iid = source_tree.insert("", "end", text=value["name"], values=(origin,))
                    picker_state["sources"][iid] = value

            def populate_targets():
                target_tree.delete(*target_tree.get_children())
                picker_state["targets"] = {}
                needle = target_search_var.get().strip().casefold()
                try:
                    records = sample_sync_function_records(self.editor.get("1.0", "end-1c"), class_only=True)
                except (SyntaxError, ValueError) as error:
                    messagebox.showwarning("関数置換", "現在のソースを解析できません:\n{}".format(error), parent=picker)
                    return
                for name, record in sorted(records.items(), key=lambda pair: pair[0].casefold()):
                    if needle and needle not in name.casefold():
                        continue
                    iid = target_tree.insert("", "end", text=name, values=(record["start"] + 1,))
                    picker_state["targets"][iid] = dict(record, name=name)

            def update_mode(*_args):
                specified = mode_var.get() == "指定Pythonファイル"
                source_path_entry.configure(state="normal" if specified else "disabled")
                browse_button.configure(state="normal" if specified else "disabled")
                reload_button.configure(state="normal" if specified else "disabled")
                propagate_check.configure(state="disabled" if specified else "normal")
                if specified:
                    propagate_var.set(False); load_specified(show_errors=False)
                populate_sources()

            def choose_source_file():
                initial = source_path_var.get().strip() or self.root_dir.get()
                selected = filedialog.askopenfilename(parent=picker,
                                                      initialdir=os.path.dirname(initial) if os.path.isfile(initial) else initial,
                                                      filetypes=(("Python", "*.py"), ("すべて", "*.*")))
                if selected:
                    source_path_var.set(selected); load_specified(); populate_sources()

            def selected_source():
                selection = source_tree.selection()
                return picker_state["sources"].get(selection[0]) if selection else None

            def edit_source():
                source = selected_source()
                if not source:
                    messagebox.showinfo("関数置換", "編集する置換元関数を1つ選択してください。", parent=picker); return
                if source["kind"] == "sample":
                    fragment_id = fragment_id_for(source["item"])
                    if not fragment_id:
                        messagebox.showwarning("関数置換", "サンプル関数の登録情報を特定できません。", parent=picker); return
                    picker.destroy(); dialog.destroy(); self.load_fragment_for_editing(fragment_id)
                    return
                path, line = source["path"], source["start"] + 1
                picker.destroy(); dialog.destroy()
                if self.current_path and os.path.abspath(path) == os.path.abspath(self.current_path):
                    self.editor.mark_set("insert", "{}.0".format(line)); self.editor.see("{}.0".format(line)); self.editor.focus_set()
                else:
                    self.show_file(path, line)

            def delete_source():
                source = selected_source()
                if not source or source["kind"] != "sample":
                    messagebox.showinfo("関数置換", "削除できるサンプル関数を1つ選択してください。", parent=picker); return
                fragment_id = fragment_id_for(source["item"])
                if not fragment_id:
                    messagebox.showwarning("関数置換", "サンプル関数の登録情報を特定できません。", parent=picker); return
                if self.delete_fragment(fragment_id):
                    state["comparisons"] = [item for item in state["comparisons"] if item is not source["item"]]
                    populate(); populate_sources()

            def apply_replacement():
                source = selected_source()
                target_rows = [picker_state["targets"][iid] for iid in target_tree.selection()
                               if iid in picker_state["targets"]]
                if not source or not target_rows:
                    messagebox.showinfo("関数置換", "置換元関数を1つ、反映先関数を1つ以上選択してください。", parent=picker); return
                function_texts = {row["name"]: source["text"] for row in target_rows}
                use_everywhere = source["kind"] == "sample" and propagate_var.get()
                target_path = ensure_source_save_path(self.current_path)
                if not target_path:
                    return
                detail = ("\nプロジェクト内の同名関数の使用箇所にも反映します。"
                          if use_everywhere else "")
                if not messagebox.askyesno(
                        "関数置換",
                        "置換元: {}\n反映先: {}{}\n実ソース保存先: {}\n\n"
                        "反映して保存しますか？".format(
                            source["name"],
                            ", ".join(row["name"] for row in target_rows),
                            detail, target_path), parent=picker):
                    return
                current_source = self.editor.get("1.0", "end-1c")
                try:
                    updated = replace_class_functions(current_source, function_texts)
                except (SyntaxError, ValueError) as error:
                    messagebox.showerror("関数置換", str(error), parent=picker); return
                if updated == current_source:
                    messagebox.showinfo("関数置換", "反映対象に変更はありません。", parent=picker); return
                try:
                    backup = create_sample_sync_backup(
                        target_path, current_source,
                        state.get("comparisons", []),
                        [row["name"] for row in target_rows], backup_root,
                        source_will_be_saved=True)
                    saved_path = save_reflected_source(target_path, updated)
                except (OSError, SyntaxError, ValueError) as error:
                    messagebox.showerror(
                        "関数置換とソース保存", str(error), parent=picker)
                    return
                state["last_backup"] = backup["manifest_path"]
                backup_status_var.set(
                    "復元可能: {} / 関数置換を実ソースへ保存".format(
                        backup["created"]))
                show_saved_source(updated, saved_path)
                populate_targets(); refresh()
                if not use_everywhere:
                    self.status.set(
                        "関数を{}件置換し、実ソースへ保存しました: {}".format(
                            len(function_texts), saved_path))
                    messagebox.showinfo(
                        "関数置換", "現在の実ソースへ反映・保存しました。",
                        parent=picker)
                    return
                current_path = os.path.abspath(self.current_path) if self.current_path else ""
                disk_paths = [path for path in self.files if str(path).lower().endswith(".py")
                              and os.path.abspath(path) != current_path]

                def completed(changed_paths):
                    self.refresh_index(); refresh()
                    parent = picker if picker.winfo_exists() else self
                    messagebox.showinfo(
                        "使用箇所へ反映",
                        "{}ファイルへ反映しました。現在の実ソースも保存済みです。".format(
                            len(changed_paths) + 1), parent=parent)
                self.run_background("picked_sample_usage_replace", "選択サンプルを使用箇所へ反映中",
                                    lambda: propagate_sample_functions(disk_paths, function_texts), completed)

            browse_button = ttk.Button(source_top, text="選択...", command=choose_source_file)
            browse_button.pack(side="left", padx=2)
            reload_button = ttk.Button(source_top, text="再読込", command=lambda: (load_specified(), populate_sources()))
            reload_button.pack(side="left", padx=2)
            buttons = ttk.Frame(picker); buttons.pack(fill="x", padx=8, pady=(3, 8))
            ttk.Button(buttons, text="選択した関数を反映", command=apply_replacement).pack(side="left", padx=3)
            ttk.Button(buttons, text="置換元を編集", command=edit_source).pack(side="left", padx=3)
            ttk.Button(buttons, text="置換元を削除", command=delete_source).pack(side="left", padx=3)
            ttk.Button(buttons, text="閉じる", command=picker.destroy).pack(side="right", padx=3)
            mode_combo.bind("<<ComboboxSelected>>", update_mode)
            source_search_var.trace_add("write", lambda *_args: self.debounce("replacement_source_search", 100, populate_sources))
            target_search_var.trace_add("write", lambda *_args: self.debounce("replacement_target_search", 100, populate_targets))
            populate_targets(); update_mode()

        def apply_to_all_usages():
            items = [item for item in selected_items()
                     if item.get("status") != "duplicate" and len(item.get("fragments", [])) == 1]
            if not items:
                messagebox.showinfo("関数置換", "反映するサンプル関数を選択してください。", parent=dialog); return
            function_texts = {item["name"]: item["fragments"][0]["text"] for item in items}
            target_path = ensure_source_save_path(self.current_path)
            if not target_path:
                return
            python_paths = [path for path in self.files if str(path).lower().endswith(".py")]
            current_path = os.path.abspath(self.current_path) if self.current_path else ""
            disk_paths = [path for path in python_paths if os.path.abspath(path) != current_path]
            if not messagebox.askyesno(
                    "使用箇所へ反映",
                    "選択した{}関数を、プロジェクト内の同名関数を使用している箇所へ反映します。\n"
                    "検索対象: {}ファイル\n続行しますか？".format(len(function_texts), len(python_paths)),
                    parent=dialog): return
            current_source = self.editor.get("1.0", "end-1c")

            def worker():
                try:
                    updated_current = replace_class_functions(current_source, function_texts)
                except (SyntaxError, ValueError):
                    updated_current = current_source
                saved_path = ""
                backup = None
                if updated_current != current_source:
                    backup = create_sample_sync_backup(
                        target_path, current_source,
                        state.get("comparisons", []),
                        list(function_texts), backup_root,
                        source_will_be_saved=True)
                    saved_path = save_reflected_source(
                        target_path, updated_current)
                changed_paths = propagate_sample_functions(
                    disk_paths, function_texts)
                return changed_paths, updated_current, saved_path, backup

            def completed(result):
                if not dialog_alive(): return
                changed_paths, updated_current, saved_path, backup = result
                current_changed = updated_current != current_source
                if current_changed:
                    show_saved_source(updated_current, saved_path)
                    state["last_backup"] = backup["manifest_path"]
                    backup_status_var.set(
                        "復元可能: {} / 使用箇所を実ソースへ保存".format(
                            backup["created"]))
                self.refresh_index(); refresh()
                messagebox.showinfo(
                    "使用箇所へ反映",
                    "{}ファイルへ反映しました。{}".format(
                        len(changed_paths) + (1 if current_changed else 0),
                        "現在の実ソースも保存済みです。"
                        if current_changed else ""), parent=dialog)
            self.run_background("sample_usage_replace", "サンプル関数を使用箇所へ反映中", worker, completed)

        ttk.Button(top, text="フォルダー選択", command=choose_folder).pack(side="left", padx=2)
        ttk.Button(top, text="再チェック", command=refresh).pack(side="left", padx=2)
        search_var.trace_add("write", lambda *args: self.debounce("sample_function_search", 120, populate))
        tree.bind("<<TreeviewSelect>>", show_selected_diff, add="+")
        selected_actions = ttk.Frame(dialog); selected_actions.pack(fill="x", padx=7, pady=(2, 0))
        ttk.Button(
            selected_actions, text="選択分を安全に一括反映・ソース保存",
            command=lambda: merge_names_and_source_bodies(True)).pack(
                side="left", padx=3)
        ttk.Button(
            selected_actions, text="表示中の差分を全選択",
            command=lambda: tree.selection_set([
                iid for iid, item in state["visible"].items()
                if item.get("status") != "match"])).pack(side="left", padx=3)
        ttk.Button(selected_actions, text="関数を選んで置換...",
                   command=open_replacement_picker).pack(side="left", padx=3)
        ttk.Button(selected_actions, text="選択サンプルを使用箇所すべてへ反映",
                   command=apply_to_all_usages).pack(side="left", padx=3)
        ttk.Button(selected_actions, text="編集", command=edit_selected).pack(side="right", padx=3)
        ttk.Button(selected_actions, text="VSCodeで開く",
                   command=open_selected_in_vscode).pack(side="right", padx=3)
        ttk.Button(selected_actions, text="削除", command=delete_selected).pack(side="right", padx=3)
        safety_row = ttk.Frame(dialog); safety_row.pack(fill="x", padx=7, pady=(3, 0))
        ttk.Label(safety_row, textvariable=backup_status_var,
                  foreground="#174a7e").pack(side="left")
        ttk.Button(safety_row, text="直前の一括反映を戻す",
                   command=rollback_last_batch).pack(side="right", padx=3)
        bottom = ttk.Frame(dialog); bottom.pack(fill="x", padx=7, pady=7)
        ttk.Label(bottom, textvariable=summary_var).pack(side="left")
        ttk.Button(bottom, text="画像検知も ソース → 登録設定", command=lambda: (
            self.image_library_apply_target.set("ソース編集"), self.load_image_detection_from_source())).pack(side="right", padx=3)
        ttk.Button(bottom, text="不一致をすべて ソース → サンプル関数", command=source_to_library).pack(side="right", padx=3)
        ttk.Button(bottom, text="不一致をすべて サンプル関数 → ソース保存", command=library_to_source).pack(side="right", padx=3)
        ttk.Button(
            bottom, text="安全に一括反映・ソース保存（名前=サンプル / 処理=ソース）",
            command=merge_names_and_source_bodies).pack(side="right", padx=3)
        refresh()

    def create_fragment_from_tab(self):
        safe_name = python_identifier(self.fragment_name.get())
        base = os.path.abspath(self.fragment_root())
        folder = os.path.abspath(self.fragment_folder.get() or base)
        if os.path.commonpath([base, folder]) != base:
            messagebox.showwarning(self.ui_text("Sample function", "サンプル関数"),
                                   self.ui_text("Choose a folder under the sample-function library.",
                                                "サンプル関数ライブラリ配下のフォルダを選択してください。"), parent=self)
            return
        existing = {}
        if self.editing_fragment_id:
            try:
                existing, _, metadata_path, body_path = load_fragment(base, self.editing_fragment_id)
            except (OSError, ValueError, KeyError) as error:
                messagebox.showerror("Fragment", str(error), parent=self); return
            root = os.path.dirname(metadata_path)
        else:
            root = os.path.join(folder, safe_name)
            metadata_path = os.path.join(root, safe_name + ".pokesample.json")
            body_path = os.path.join(root, safe_name + ".pyfrag")
        import_lines = [item.strip() for item in self.fragment_imports.get("1.0", "end-1c").splitlines()
                        if item.strip()]
        try:
            import_tree = ast.parse("\n".join(import_lines))
        except SyntaxError as error:
            messagebox.showwarning("Fragment", "Importsの構文を確認してください。\n{}".format(error), parent=self)
            return
        if any(not isinstance(node, (ast.Import, ast.ImportFrom)) for node in import_tree.body):
            messagebox.showwarning("Fragment", "Importsにはimport文またはfrom ... import ...文だけを入力してください。", parent=self)
            return
        initializer = normalize_python_indentation(textwrap.dedent(
            self.fragment_initializer.get("1.0", "end-1c"))).strip("\n")
        if initializer:
            try:
                compile("def _sample_initializer(self):\n" + textwrap.indent(initializer, "    ") + "\n",
                        "<sample-initializer>", "exec")
            except SyntaxError as error:
                messagebox.showwarning("Fragment", "実行開始時の初期化コードを確認してください。\n{}".format(error), parent=self)
                return
        metadata = {"schema_version": 1, "name": self.fragment_name.get().strip() or safe_name,
                    "tags": self.fragment_tag_picker.get_tags(),
                    "imports": import_lines,
                    "class_variables": [item.strip() for item in self.fragment_class_vars.get("1.0", "end-1c").splitlines() if item.strip()],
                    "initializer": initializer,
                    "fragment": os.path.basename(body_path)}
        if existing.get("target"):
            metadata["target"] = existing["target"]
        # Dependency support samples are editable too.  Keep their grouping
        # metadata when imports, initializer or class variables are changed.
        if existing.get("dependency_group"):
            metadata["dependency_group"] = existing["dependency_group"]
        # Samples registered from a source function keep their origin across
        # later edits.  The comparison/sync screen needs both the source path
        # and the original function name, especially when the sample was
        # registered under a different name.
        if existing.get("source"):
            metadata["source"] = existing["source"]
        if existing.get("function_sync"):
            metadata["function_sync"] = existing["function_sync"]
        body_content = normalize_python_indentation(
            self.fragment_body.get("1.0", "end-1c"))
        try:
            compile(body_content, body_path, "exec")
        except SyntaxError as error:
            messagebox.showwarning(
                "Fragment",
                "?????????Python??????????????????\n{}".format(error),
                parent=self)
            return
        current_body = self.fragment_body.get("1.0", "end-1c")
        if body_content != current_body:
            cursor = self.fragment_body.index("insert")
            self.fragment_body.delete("1.0", "end")
            self.fragment_body.insert("1.0", body_content)
            self.fragment_body.mark_set("insert", cursor)
            self._update_fragment_line_numbers()
        try:
            os.makedirs(root, exist_ok=True)
            with open(metadata_path, "w", encoding="utf-8", newline="\n") as file:
                json.dump(metadata, file, ensure_ascii=False, indent=2)
            with open(body_path, "w", encoding="utf-8", newline="\n") as file:
                file.write(body_content.rstrip("\n") + "\n")
        except OSError as error:
            messagebox.showerror("Fragment", str(error), parent=self)
            return
        self._fragment_loaded_body = body_content
        self.refresh_index()
        self.show_file(body_path)
        self.status.set(self.ui_text(("Updated" if self.editing_fragment_id else "Created") + " sample function: " + metadata["name"],
                                     ("サンプル関数を更新しました: " if self.editing_fragment_id else "サンプル関数を登録しました: ") + metadata["name"]))
        self.refresh_fragment_catalog_background(
            select=self.editing_fragment_id)
        self._sample_lists_refresh_deferred = \
            self.sample_list_name.get().strip()

    def fragment_tag_choices(self):
        return [tag for item in self.fragment_catalog() for tag in item.get("tags", [])]

    def refresh_registered_fragment_choices(self, select=None):
        items = self.fragment_catalog()
        self.registered_fragment_items = items
        labels = ["{}  ({})".format(item.get("name", item["id"]), item["id"]) for item in items]
        if hasattr(self, "registered_fragment_combo"):
            display_labels = labels or ["（登録済みサンプル関数はありません）"]
            self.registered_fragment_combo.configure(values=display_labels)
            target = select or self.editing_fragment_id
            index = next((i for i, item in enumerate(items) if item["id"] == target), None)
            if index is not None:
                self.registered_fragment_choice.set(labels[index])
            elif self.registered_fragment_choice.get() not in display_labels:
                self.registered_fragment_choice.set(display_labels[0])
        # The sample-list preview worker also prepares its fragment choices;
        # doing it here would synchronously resolve and reread the whole list.

    def refresh_fragment_catalog_background(self, select=None):
        """Scan the sample-function library without blocking Tk startup."""
        root = self.fragment_root()
        if self._fragment_catalog_cache is not None:
            self.refresh_registered_fragment_choices(select=select)
            return False
        if select:
            self._fragment_catalog_pending_select = select
        if "fragment_catalog" in self.background_tasks:
            return False
        if hasattr(self, "registered_fragment_combo"):
            self.registered_fragment_choice.set("（サンプル関数を読み込み中…）")
            self.registered_fragment_combo.configure(
                values=("（サンプル関数を読み込み中…）",))

        def completed(items):
            if os.path.abspath(root) != os.path.abspath(self.fragment_root()):
                return
            self._fragment_catalog_cache = list(items)
            pending_select = getattr(
                self, "_fragment_catalog_pending_select", "") or select
            self._fragment_catalog_pending_select = ""
            self.refresh_registered_fragment_choices(select=pending_select)
            editing_metadata = getattr(
                self, "_editing_fragment_metadata", None)
            if (self.editing_fragment_id and
                    isinstance(editing_metadata, dict) and
                    editing_metadata.get("dependency_group")):
                self._refresh_dependency_fragment_editor(
                    self.editing_fragment_id, editing_metadata)
            if hasattr(self, "fragment_tag_picker"):
                self.fragment_tag_picker.refresh_choices()
            if (hasattr(self, "sample_lists_workspace") and
                    self.workspace_tabs.select() == str(self.sample_lists_workspace)):
                self.refresh_catalog_tag_choices()
                self.rebuild_catalog_folder_tree()
                self.refresh_sample_catalog()

        return self.run_background(
            "fragment_catalog", "サンプル関数一覧を読み込み中",
            lambda: catalog(root), completed, busy_cursor=False)

    def _registered_fragment_id(self):
        value = self.registered_fragment_choice.get()
        labels = [str(item) for item in self.registered_fragment_combo.cget("values")]
        try: return getattr(self, "registered_fragment_items", [])[labels.index(value)]["id"]
        except (ValueError, IndexError): return None

    def edit_registered_fragment(self):
        fragment_id = self._registered_fragment_id()
        if fragment_id: self.load_fragment_for_editing(fragment_id)

    def delete_registered_fragment(self):
        fragment_id = self._registered_fragment_id()
        if fragment_id: self.delete_fragment(fragment_id)

    def cancel_fragment_edit(self):
        self.editing_fragment_id = None
        self._editing_fragment_metadata = None
        self._fragment_loaded_body = ""
        self.fragment_name.set("new_fragment")
        self.fragment_tag_picker.set_tags([])
        self.fragment_folder.set(self.fragment_root())
        for widget in (self.fragment_imports, self.fragment_class_vars, self.fragment_initializer, self.fragment_body): widget.delete("1.0", "end")
        self.fragment_body.insert("1.0", "# @pokedev-fragment: new_fragment\n# Inserted into the selected Step user block.\n")
        self._refresh_fragment_search()
        self.fragment_save_button.configure(text="サンプルとして保存")
        if hasattr(self, "fragment_dependency_frame"):
            self.fragment_dependency_items = []
            self.fragment_dependency_frame.grid_remove()
        self.status.set(self.ui_text("New sample-function mode", "サンプル関数の新規登録モード"))

    def delete_fragment(self, fragment_id):
        try:
            metadata, _, metadata_path, body_path = load_fragment(self.fragment_root(), fragment_id)
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("Fragment", str(error), parent=self); return False
        data = self._read_sample_lists(); used_by = []
        for list_name, item in data["lists"].items():
            if any(member["type"] == "fragment" and member["id"] == fragment_id for member in item["members"]):
                used_by.append(list_name)
        detail = (self.ui_text("\nUsed by: ", "\n使用中のサンプルリスト: ") + ", ".join(used_by)
                  if used_by else self.ui_text("\nNot used by a sample list.", "\n使用しているサンプルリストはありません。"))
        if not messagebox.askyesno(
                self.ui_text("Delete registered sample function", "登録済みサンプル関数の削除"),
                self.ui_text("Delete '{}'?{}\n\nThis removes its metadata/body files and list references.",
                             "「{}」を削除しますか？{}\n\nメタデータ、関数コード、リストからの参照が削除されます。").format(
                                 metadata.get("name", fragment_id), detail), parent=self): return False
        for item in data["lists"].values():
            item["members"] = [member for member in item["members"] if not (member["type"] == "fragment" and member["id"] == fragment_id)]
        self._write_sample_lists(data)
        try:
            if os.path.isfile(body_path): os.remove(body_path)
            if os.path.isfile(metadata_path): os.remove(metadata_path)
            try: os.rmdir(os.path.dirname(metadata_path))
            except OSError: pass
        except OSError as error:
            messagebox.showerror(self.ui_text("Sample function", "サンプル関数"),
                                 self.ui_text("References were removed, but a file could not be deleted: {}",
                                              "リストからの参照は削除されましたが、ファイルを削除できませんでした: {}").format(error), parent=self); return False
        self._fragment_catalog_cache = None
        if self.editing_fragment_id == fragment_id: self.cancel_fragment_edit()
        self.refresh_registered_fragment_choices(); self.refresh_sample_lists_tab(select=self.sample_list_name.get().strip())
        self.refresh_catalog_tag_choices(); self.rebuild_catalog_folder_tree()
        self.status.set(self.ui_text("Deleted registered sample function: ", "登録済みサンプル関数を削除しました: ") + metadata.get("name", fragment_id))
        return True

    def choose_fragment_folder(self):
        root = self.fragment_root()
        os.makedirs(root, exist_ok=True)
        selected = filedialog.askdirectory(parent=self, initialdir=self.fragment_folder.get() or root)
        if selected and os.path.abspath(selected).startswith(os.path.abspath(root)):
            self.fragment_folder.set(selected)

    def add_fragment_folder(self):
        name = simpledialog.askstring(self.ui_text("New folder", "新しいフォルダ"),
                                      self.ui_text("Folder name:", "フォルダ名:"), parent=self)
        if not name:
            return
        target = os.path.join(self.fragment_folder.get() or self.fragment_root(), folder_segment(name))
        os.makedirs(target, exist_ok=True)
        self.fragment_folder.set(target)

    def sample_lists_path(self):
        return os.path.join(self.fragment_root(), "sample_lists.json")

    def _read_sample_lists(self):
        return load_library(self.sample_lists_path())

    def _write_sample_lists(self, data):
        save_library(self.sample_lists_path(), data)

    def fragment_catalog(self):
        if self._fragment_catalog_cache is None:
            self._fragment_catalog_cache = catalog(self.fragment_root())
        return list(self._fragment_catalog_cache)

    def refresh_sample_catalog(self):
        if not hasattr(self, 'sample_catalog_list'): return
        needle = self.sample_catalog_search.get().strip().lower()
        tag = self.sample_catalog_tag.get().strip().lower() if hasattr(self, "sample_catalog_tag") else ""
        if tag == "（すべて）": tag = ""
        selected_folders = getattr(self, "sample_catalog_selected_folders", set())
        self.sample_catalog_items = []
        self.sample_catalog_list.delete(0, 'end')
        for item in self.fragment_catalog():
            text = '{} [{}] {}'.format(item.get('name',''), ','.join(item.get('tags',[])), item.get('id',''))
            if needle and needle not in item.get("name", "").lower(): continue
            if tag and tag not in [value.lower() for value in item.get("tags", [])]: continue
            item_folder = item.get("folder", "").replace("\\", "/")
            if selected_folders and not any(not folder or item_folder == folder or item_folder.startswith(folder + "/") for folder in selected_folders): continue
            self.sample_catalog_items.append(item); self.sample_catalog_list.insert('end', text)

    def refresh_catalog_tag_choices(self, *args):
        if not hasattr(self, "sample_catalog_tag_combo"): return
        needle = self.sample_catalog_tag_search.get().strip().lower()
        tags = sorted(set(tag for item in self.fragment_catalog() for tag in item.get("tags", [])), key=str.lower)
        values = ["（すべて）"] + [tag for tag in tags if not needle or needle in tag.lower()]
        self.sample_catalog_tag_combo.configure(values=values)
        if self.sample_catalog_tag.get() not in values:
            self.sample_catalog_tag.set(values[0])

    def rebuild_catalog_folder_tree(self):
        if not hasattr(self, "sample_catalog_folder_tree"): return
        tree = self.sample_catalog_folder_tree
        tree.delete(*tree.get_children())
        self.sample_catalog_folder_nodes = {}
        folders = sorted(set(item.get("folder", "").replace("\\", "/") for item in self.fragment_catalog()))
        root_id = tree.insert("", "end", text=self._folder_checkbox_text("", "サンプル関数ルート"), open=True)
        self.sample_catalog_folder_nodes[root_id] = ""
        nodes = {"": root_id}
        for folder in folders:
            parent_path = ""
            for segment in [part for part in folder.split("/") if part]:
                path = segment if not parent_path else parent_path + "/" + segment
                if path not in nodes:
                    node = tree.insert(nodes[parent_path], "end", text=self._folder_checkbox_text(path, segment), open=False)
                    nodes[path] = node; self.sample_catalog_folder_nodes[node] = path
                parent_path = path

    def _folder_checkbox_text(self, path, label):
        checked = path in getattr(self, "sample_catalog_selected_folders", set())
        return "[x] " + label if checked else "[ ] " + label

    def toggle_catalog_folder(self, event=None):
        tree = self.sample_catalog_folder_tree
        if event is not None and hasattr(event, "x") and "indicator" in tree.identify_element(event.x, event.y):
            return
        node = tree.identify_row(event.y) if event is not None and hasattr(event, "y") else (tree.selection()[0] if tree.selection() else "")
        if not node or node not in self.sample_catalog_folder_nodes: return
        path = self.sample_catalog_folder_nodes[node]
        if path in self.sample_catalog_selected_folders:
            self.sample_catalog_selected_folders.remove(path)
        else:
            self.sample_catalog_selected_folders.add(path)
        label = tree.item(node, "text")[4:]
        tree.item(node, text=self._folder_checkbox_text(path, label))
        self.refresh_sample_catalog()

    def open_selected_catalog_fragment(self, event=None):
        selected = self.sample_catalog_list.curselection()
        if not selected:
            return
        self.load_fragment_for_editing(self.sample_catalog_items[selected[0]]["id"])

    def _refresh_dependency_fragment_editor(self, fragment_id, metadata):
        frame = getattr(self, "fragment_dependency_frame", None)
        if frame is None:
            return
        group = metadata.get("dependency_group")
        if not isinstance(group, dict):
            self.fragment_dependency_items = []
            self.fragment_dependency_function_choice.set("")
            self.fragment_dependency_function_combo.configure(values=())
            frame.grid_remove()
            return
        items = []
        try:
            lists = self._read_sample_lists().get("lists", {})
            catalog_by_id = {
                item["id"]: item
                for item in (self._fragment_catalog_cache or [])}
            for list_name, value in lists.items():
                members = value.get("members", []) if isinstance(value, dict) else []
                if not any(
                        member.get("type") == "fragment" and
                        member.get("id") == fragment_id
                        for member in members if isinstance(member, dict)):
                    continue
                for member in members:
                    if (not isinstance(member, dict) or
                            member.get("type") != "fragment" or
                            member.get("id") == fragment_id or
                            not member.get("function")):
                        continue
                    item = catalog_by_id.get(member.get("id"), {})
                    label = "{}  ({})".format(
                        member["function"],
                        item.get("name", member.get("id", "")))
                    items.append({
                        "label": label, "id": member.get("id"),
                        "function": member["function"], "list": list_name})
        except (OSError, ValueError, KeyError):
            items = []
        self.fragment_dependency_items = items
        labels = [item["label"] for item in items]
        self.fragment_dependency_function_combo.configure(values=labels)
        self.fragment_dependency_function_choice.set(labels[0] if labels else "")
        self.fragment_dependency_notice.set(
            "関数本体は下の一覧から開きます（{}件）".format(len(items)))
        frame.grid()

    def open_selected_dependency_fragment(self):
        labels = [item["label"] for item in getattr(
            self, "fragment_dependency_items", [])]
        try:
            index = labels.index(self.fragment_dependency_function_choice.get())
            fragment_id = self.fragment_dependency_items[index]["id"]
        except (ValueError, IndexError, KeyError):
            messagebox.showinfo(
                "依存グループ", "変更する依存関数を選択してください。",
                parent=self)
            return
        self.load_fragment_for_editing(fragment_id)

    def load_fragment_for_editing(self, fragment_id):
        try:
            metadata, body, metadata_path, body_path = load_fragment(self.fragment_root(), fragment_id)
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("Fragment", str(error), parent=self); return
        self.editing_fragment_id = fragment_id
        self._editing_fragment_metadata = dict(metadata)
        self.fragment_name.set(metadata.get("name", ""))
        # Opening one sample must not scan every registered sample merely to
        # rebuild tag suggestions.  The catalog refresh below does that off
        # the UI thread.
        self.fragment_tag_picker.set_tags(
            metadata.get("tags", []), refresh_choices=False)
        self.fragment_folder.set(os.path.dirname(metadata_path))
        imports = metadata.get("imports", [])
        if not imports:
            imports = [value if value.startswith(("import ", "from ")) else "import " + value
                       for value in metadata.get("requires", [])]
        for widget, values in ((self.fragment_imports, imports),
                               (self.fragment_class_vars, metadata.get("class_variables", []))):
            widget.delete("1.0", "end"); widget.insert("1.0", "\n".join(values))
        self.fragment_initializer.delete("1.0", "end")
        self.fragment_initializer.insert("1.0", metadata.get("initializer", ""))
        self.fragment_body.delete("1.0", "end"); self.fragment_body.insert("1.0", body)
        self._fragment_loaded_body = self.fragment_body.get("1.0", "end-1c")
        self._refresh_fragment_search()
        self.fragment_save_button.configure(text="変更を保存")
        self._refresh_dependency_fragment_editor(fragment_id, metadata)
        self.workspace_tabs.select(self.sample_functions_workspace)
        if self._fragment_catalog_cache is None:
            self.refresh_fragment_catalog_background(select=fragment_id)
        if metadata.get("dependency_group"):
            self.status.set(
                "依存グループ設定を開きました。関数本体は上の一覧から変更できます: " +
                metadata.get("name", body_path))
        else:
            self.status.set(self.ui_text("Loaded sample function for editing: ", "サンプル関数の変更モードに入りました: ") + metadata.get("name", body_path))

    def add_catalog_sample_to_list(self):
        selected = self.sample_catalog_list.curselection(); name = self.sample_list_name.get().strip()
        if not selected or not name: return
        data = self._read_sample_lists(); item = data["lists"].setdefault(name, {"tags": [], "members": []}); members = item["members"]
        item_id = self.sample_catalog_items[selected[0]]['id']
        member = {"type": "fragment", "id": item_id}
        if member not in members: members.append(member)
        self._write_sample_lists(data)
        self.refresh_sample_apply_lists(); self.refresh_sample_lists_tab(select=name, member=len(members) - 1)

    def selected_catalog_fragment_id(self):
        selected = self.sample_catalog_list.curselection()
        return self.sample_catalog_items[selected[0]]["id"] if selected else None

    def edit_selected_catalog_fragment(self):
        fragment_id = self.selected_catalog_fragment_id()
        if fragment_id: self.load_fragment_for_editing(fragment_id)

    def delete_selected_catalog_fragment(self):
        fragment_id = self.selected_catalog_fragment_id()
        if fragment_id: self.delete_fragment(fragment_id)

    def selected_member_fragment_id(self):
        selected = self.sample_member_list.curselection(); name = self.sample_list_name.get().strip()
        if not selected or not name: return None
        members = self._read_sample_lists()["lists"].get(name, {}).get("members", [])
        if selected[0] >= len(members) or members[selected[0]]["type"] != "fragment": return None
        return members[selected[0]]["id"]

    def edit_selected_member_fragment(self):
        fragment_id = self.selected_member_fragment_id()
        if fragment_id: self.load_fragment_for_editing(fragment_id)
        else: messagebox.showinfo(self.ui_text("Sample function", "サンプル関数"),
                                  self.ui_text("Select a sample-function member (not a nested list).",
                                               "登録済みサンプル関数を選択してください（入れ子のサンプルリストは変更できません）。"), parent=self)

    def delete_selected_member_fragment(self):
        fragment_id = self.selected_member_fragment_id()
        if fragment_id: self.delete_fragment(fragment_id)
        else: messagebox.showinfo("Fragment", "Select a fragment member (not a nested list).", parent=self)

    def add_sample_list_to_list(self):
        selected = self.sample_nested_list.curselection(); name = self.sample_list_name.get().strip()
        if not selected or not name: return
        nested = self.sample_nested_list.get(selected[0])
        if nested == name:
            messagebox.showwarning(self.ui_text("Sample list", "サンプルリスト"),
                                   self.ui_text("A list cannot contain itself.", "サンプルリスト自身を入れ子として登録することはできません。"), parent=self); return
        data = self._read_sample_lists(); members = data["lists"].setdefault(name, {"tags": [], "members": []})["members"]
        member = {"type": "list", "id": nested}
        if member not in members: members.append(member)
        try:
            compose_preview(self.fragment_root(), data, name)
        except ValueError as error:
            members.remove(member); messagebox.showwarning("Sample list", str(error), parent=self); return
        self._write_sample_lists(data); self.refresh_sample_lists_tab(select=name, member=len(members) - 1)

    def remove_sample_member(self):
        selected = self.sample_member_list.curselection(); name = self.sample_list_name.get().strip()
        if not selected or not name: return
        data = self._read_sample_lists(); members = data["lists"].get(name, {}).get("members", [])
        index = selected[0]
        if index >= len(members): return
        del members[index]; self._write_sample_lists(data)
        self.refresh_sample_apply_lists(); self.refresh_sample_lists_tab(select=name, member=min(index, len(members) - 1))

    def refresh_sample_list_preview(self, event=None):
        name = self.sample_list_name.get().strip()
        if not name:
            return
        self.sample_list_preview.configure(state="normal")
        self.sample_list_preview.delete("1.0", "end")
        self.sample_list_preview.insert("1.0", "プレビューを生成中です...\n")
        self.sample_list_preview.configure(state="disabled")
        fragment_root = self.fragment_root()
        library_path = os.path.join(fragment_root, "sample_lists.json")
        image_library_path = self._image_library_config_path()
        cached_catalog = list(self._fragment_catalog_cache or [])

        def worker():
            try:
                data = load_library(library_path)
                image_library = load_image_library(image_library_path)
                text = self._sample_program_source(
                    name, fragment_root=fragment_root, data=data,
                    image_library=image_library)
                compile(text, "<sample-list-preview>", "exec")
                catalog_items = cached_catalog or catalog(fragment_root)
                catalog_by_id = {item["id"]: item for item in catalog_items}
                members = resolve_members(data, name)
                item_ids = [
                    member["id"] for member in members
                    if member["id"] in catalog_by_id]
                labels = ["{}  ({})".format(
                    catalog_by_id[item_id].get("name", item_id), item_id)
                    for item_id in item_ids]
                return text, item_ids, labels
            except (OSError, ValueError, KeyError) as error:
                return "Preview error: " + str(error), [], []
            except SyntaxError as error:
                return "Preview syntax error: " + str(error), [], []

        def completed(result):
            text, item_ids, labels = result
            # A different list may have been selected while this large preview
            # was being composed.  Never overwrite that newer selection.
            if self.sample_list_name.get().strip() != name:
                self.after_idle(self.refresh_sample_list_preview)
                return
            self.sample_preview_fragment_items = item_ids
            self.sample_preview_fragment_combo.configure(values=labels)
            current = self.sample_preview_fragment_choice.get()
            if current not in labels:
                self.sample_preview_fragment_choice.set(
                    labels[0] if labels else "")
            self.sample_list_preview.configure(state="normal")
            self.sample_list_preview.delete("1.0", "end")
            self.sample_list_preview.insert("1.0", text)
            self.sample_list_preview.configure(state="disabled")

        self.run_background(
            "sample_list_preview", "サンプルリストのプレビューを生成中",
            worker, completed)

    def _refresh_preview_fragment_choices(self):
        if not hasattr(self, "sample_preview_fragment_combo"): return
        name = self.sample_list_name.get().strip()
        try:
            members = resolve_members(self._read_sample_lists(), name)
            catalog_by_id = {item["id"]: item for item in self.fragment_catalog()}
            self.sample_preview_fragment_items = [member["id"] for member in members if member["id"] in catalog_by_id]
            labels = ["{}  ({})".format(catalog_by_id[item_id].get("name", item_id), item_id) for item_id in self.sample_preview_fragment_items]
        except ValueError:
            self.sample_preview_fragment_items, labels = [], []
        current = self.sample_preview_fragment_choice.get()
        self.sample_preview_fragment_combo.configure(values=labels)
        if current not in labels: self.sample_preview_fragment_choice.set(labels[0] if labels else "")

    def _preview_fragment_id(self):
        labels = [str(value) for value in self.sample_preview_fragment_combo.cget("values")]
        try: return self.sample_preview_fragment_items[labels.index(self.sample_preview_fragment_choice.get())]
        except (ValueError, IndexError): return None

    def edit_preview_fragment(self):
        fragment_id = self._preview_fragment_id()
        if fragment_id: self.load_fragment_for_editing(fragment_id)

    def delete_preview_fragment(self):
        fragment_id = self._preview_fragment_id()
        if fragment_id: self.delete_fragment(fragment_id)

    def _build_sample_lists_tab(self, parent):
        self.sample_list_name = tk.StringVar(value="new_sample_list")
        self.sample_list_filter = tk.StringVar()
        split = ttk.Panedwindow(parent, orient="horizontal")
        self.sample_lists_split = split
        split.bind("<Configure>", lambda event: split.sashpos(0, int(event.width * 0.66)) if event.width > 30 else None)
        split.pack(fill="both", expand=True, padx=8, pady=8)
        preview_pane = ttk.Frame(split)
        controls_pane = ttk.Frame(split)
        split.add(preview_pane, weight=2)
        split.add(controls_pane, weight=1)

        self.sample_controls_canvas = tk.Canvas(controls_pane, highlightthickness=0, borderwidth=0)
        controls_scroll = ttk.Scrollbar(controls_pane, orient="vertical", command=self.sample_controls_canvas.yview)
        self.sample_controls_canvas.configure(yscrollcommand=controls_scroll.set)
        self.sample_controls_canvas.pack(side="left", fill="both", expand=True)
        controls_scroll.pack(side="right", fill="y")
        controls = ttk.Frame(self.sample_controls_canvas)
        self.sample_controls_window = self.sample_controls_canvas.create_window((0, 0), window=controls, anchor="nw")
        controls.bind("<Configure>", self._update_sample_controls_scrollregion)
        self.sample_controls_canvas.bind("<Configure>", self._resize_sample_controls_width)
        self.bind_all("<MouseWheel>", self._scroll_sample_controls_with_wheel, add="+")

        preview_header = ttk.Frame(preview_pane)
        preview_header.pack(fill="x", pady=(0, 4))
        ttk.Label(preview_header, text="サンプル関数を合わせた結果（確認専用）").pack(side="left")
        self.sample_preview_fragment_choice = tk.StringVar()
        self.sample_preview_fragment_combo = ttk.Combobox(preview_header, textvariable=self.sample_preview_fragment_choice, state="readonly", width=34)
        self.sample_preview_fragment_combo.pack(side="left", padx=(12, 3))
        ttk.Button(preview_header, text="関数を変更", command=self.edit_preview_fragment).pack(side="left", padx=2)
        preview_box = ttk.Frame(preview_pane)
        preview_box.pack(fill="both", expand=True)
        self.sample_list_preview = tk.Text(preview_box, wrap="none", state="disabled",
                                           background="#1e1e1e", foreground="#d4d4d4",
                                           insertbackground="white")
        self.sample_list_preview.pack(side="left", fill="both", expand=True)
        preview_y = ttk.Scrollbar(preview_box, orient="vertical", command=self.sample_list_preview.yview)
        preview_y.pack(side="right", fill="y")
        preview_x = ttk.Scrollbar(preview_pane, orient="horizontal", command=self.sample_list_preview.xview)
        preview_x.pack(fill="x")
        self.sample_list_preview.configure(yscrollcommand=preview_y.set, xscrollcommand=preview_x.set)
        self._register_find_editor(
            self.sample_list_preview, "サンプルリストのプレビュー",
            replace=False)

        ttk.Label(controls, text="登録済みサンプルリスト（版付きJSON・入れ子対応）").grid(column=0, columnspan=3, row=0, padx=6, pady=(0, 4), sticky="w")
        ttk.Label(controls, text="リスト名:").grid(column=0, row=1, padx=6, pady=3, sticky="w")
        ttk.Entry(controls, textvariable=self.sample_list_name).grid(column=1, columnspan=2, row=1, padx=4, pady=3, sticky="ew")
        ttk.Label(controls, text="検索:").grid(column=0, row=2, padx=6, pady=3, sticky="w")
        ttk.Entry(controls, textvariable=self.sample_list_filter).grid(column=1, columnspan=2, row=2, padx=4, pady=3, sticky="ew")
        self.sample_list_filter.trace_add("write", lambda *_: self.refresh_sample_lists_tab())
        sample_lists_frame = ttk.Frame(controls)
        sample_lists_frame.grid(
            column=0, columnspan=3, row=3, padx=6, pady=3,
            sticky="nsew")
        self.sample_lists_tree = tk.Listbox(
            sample_lists_frame, exportselection=False, height=5)
        pack_scrollable_widget(self.sample_lists_tree, horizontal=True)
        self.sample_lists_tree.bind("<<ListboxSelect>>", self.load_selected_sample_list)
        ttk.Button(controls, text="新規作成 / 更新", command=self.create_sample_list).grid(column=1, row=4, padx=3, pady=3, sticky="ew")
        ttk.Button(controls, text="リスト削除", command=self.delete_sample_list).grid(column=2, row=4, padx=3, pady=3, sticky="ew")
        ttk.Button(
            controls, text="登録元Commandsとの差分・選択反映",
            command=self.open_sample_origin_sync).grid(
                column=0, row=4, padx=3, pady=3, sticky="ew")
        ttk.Label(controls, text="リストタグ:").grid(column=0, columnspan=3, row=5, padx=6, pady=(5, 2), sticky="w")
        self.sample_list_tag_picker = TagPicker(controls, self.sample_list_tag_choices)
        self.sample_list_tag_picker.grid(column=0, columnspan=3, row=6, padx=6, pady=3, sticky="nsew")
        self.sample_list_details = tk.StringVar(value="選択したリストのサンプル数を表示します。")
        ttk.Label(controls, textvariable=self.sample_list_details).grid(column=0, columnspan=3, row=7, padx=6, pady=3, sticky="w")
        sample_member_frame = ttk.Frame(controls)
        sample_member_frame.grid(
            column=0, columnspan=2, row=8, padx=6, pady=3,
            sticky="nsew")
        self.sample_member_list = tk.Listbox(
            sample_member_frame, exportselection=False, height=5)
        pack_scrollable_widget(self.sample_member_list, horizontal=True)
        self.sample_member_list.bind("<Double-Button-1>", lambda event: self.edit_selected_member_fragment())
        self.sample_member_list.bind("<Return>", lambda event: self.edit_selected_member_fragment())
        member_actions = ttk.Frame(controls)
        member_actions.grid(column=2, row=8, padx=3, pady=3, sticky="n")
        ttk.Button(member_actions, text="変更", command=self.edit_selected_member_fragment).pack(fill="x", pady=1)
        ttk.Button(member_actions, text="- リストから外す", command=self.remove_sample_member).pack(fill="x", pady=1)
        self.sample_catalog_search = tk.StringVar()
        self.sample_catalog_tag_search = tk.StringVar()
        self.sample_catalog_tag = tk.StringVar(value="（すべて）")
        self.sample_catalog_selected_folders = set()
        ttk.Label(controls, text="登録済みサンプル関数の候補フィルター:").grid(column=0, columnspan=3, row=9, padx=6, pady=(5, 2), sticky="w")
        ttk.Label(controls, text="名前:").grid(column=0, row=10, padx=3, pady=2, sticky="w")
        ttk.Entry(controls, textvariable=self.sample_catalog_search).grid(column=1, columnspan=2, row=10, padx=3, pady=2, sticky="ew")
        ttk.Label(controls, text="タグ検索:").grid(column=0, row=11, padx=3, pady=2, sticky="w")
        ttk.Entry(controls, textvariable=self.sample_catalog_tag_search).grid(column=1, row=11, padx=3, pady=2, sticky="ew")
        self.sample_catalog_tag_combo = ttk.Combobox(controls, textvariable=self.sample_catalog_tag, state="readonly")
        self.sample_catalog_tag_combo.grid(column=2, row=11, padx=3, pady=2, sticky="ew")
        self.sample_catalog_tag_search.trace_add("write", self.refresh_catalog_tag_choices)
        self.sample_catalog_tag_combo.bind("<<ComboboxSelected>>", lambda event: self.refresh_sample_catalog())
        ttk.Label(controls, text="フォルダ（複数選択・上位は配下すべて）:").grid(column=0, columnspan=3, row=12, padx=6, pady=(4, 2), sticky="w")
        folder_frame = ttk.Frame(controls)
        folder_frame.grid(column=0, columnspan=3, row=13, padx=6, pady=2, sticky="nsew")
        self.sample_catalog_folder_tree = ttk.Treeview(folder_frame, show="tree", height=5, selectmode="browse")
        pack_scrollable_widget(
            self.sample_catalog_folder_tree, horizontal=True)
        self.sample_catalog_folder_tree.bind("<ButtonRelease-1>", self.toggle_catalog_folder)
        self.sample_catalog_folder_tree.bind("<space>", self.toggle_catalog_folder)
        ttk.Button(controls, text="候補を検索", command=self.refresh_sample_catalog).grid(column=2, row=14, padx=3, pady=2, sticky="e")
        sample_catalog_frame = ttk.Frame(controls)
        sample_catalog_frame.grid(
            column=0, columnspan=2, row=14, rowspan=2, padx=6, pady=3,
            sticky="nsew")
        self.sample_catalog_list = tk.Listbox(
            sample_catalog_frame, exportselection=False, height=5)
        pack_scrollable_widget(self.sample_catalog_list, horizontal=True)
        self.sample_catalog_list.bind("<Double-Button-1>", self.open_selected_catalog_fragment)
        self.sample_catalog_list.bind("<Return>", lambda event: self.edit_selected_catalog_fragment())
        candidate_actions = ttk.Frame(controls)
        candidate_actions.grid(column=2, row=15, padx=3, pady=2, sticky="e")
        ttk.Button(candidate_actions, text="変更", command=self.edit_selected_catalog_fragment).pack(side="left", padx=1)
        ttk.Button(candidate_actions, text="+ 追加", command=self.add_catalog_sample_to_list).pack(side="left", padx=1)
        ttk.Label(controls, text="登録済みサンプルリスト候補:").grid(column=0, columnspan=3, row=16, padx=6, pady=(5, 2), sticky="w")
        sample_nested_frame = ttk.Frame(controls)
        sample_nested_frame.grid(
            column=0, columnspan=2, row=17, padx=6, pady=3,
            sticky="nsew")
        self.sample_nested_list = tk.Listbox(
            sample_nested_frame, exportselection=False, height=4)
        pack_scrollable_widget(self.sample_nested_list, horizontal=True)
        ttk.Button(controls, text="+ リストを追加", command=self.add_sample_list_to_list).grid(column=2, row=17, padx=3, pady=3, sticky="n")
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=1)
        controls.rowconfigure(3, weight=1)
        controls.rowconfigure(8, weight=1)
        controls.rowconfigure(13, weight=1)
        controls.rowconfigure(14, weight=1)
        controls.rowconfigure(17, weight=1)
        self.refresh_catalog_tag_choices()
        self.rebuild_catalog_folder_tree()

    def _update_sample_controls_scrollregion(self, event=None):
        self.sample_controls_canvas.configure(scrollregion=self.sample_controls_canvas.bbox("all"))

    def _resize_sample_controls_width(self, event):
        self.sample_controls_canvas.itemconfigure(self.sample_controls_window, width=max(1, event.width))

    def _scroll_sample_controls_with_wheel(self, event):
        canvas = getattr(self, "sample_controls_canvas", None)
        if canvas is None or not canvas.winfo_exists(): return
        x, y = self.winfo_pointerx(), self.winfo_pointery()
        if not (canvas.winfo_rootx() <= x < canvas.winfo_rootx() + canvas.winfo_width() and
                canvas.winfo_rooty() <= y < canvas.winfo_rooty() + canvas.winfo_height()):
            return
        canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def create_sample_list(self):
        name = self.sample_list_name.get().strip()
        if not name:
            return
        data = self._read_sample_lists()
        item = data["lists"].setdefault(name, {"tags": [], "members": []})
        item["tags"] = self.sample_list_tag_picker.get_tags()
        self._write_sample_lists(data)
        self.refresh_sample_apply_lists()
        self.refresh_sample_lists_tab(select=name)
        self.status.set(self.ui_text("Created/updated sample list: ", "サンプルリストを作成・更新しました: ") + name)

    def open_sample_origin_sync(self):
        selected = self.sample_lists_tree.curselection()
        name = (self.sample_lists_tree.get(selected[0]) if selected else
                self.sample_list_name.get().strip())
        data = self._read_sample_lists()
        if not name or name not in data["lists"]:
            messagebox.showinfo(
                "登録元Commands同期", "サンプルリストを選択してください。",
                parent=self)
            return

        dialog = tk.Toplevel(self)
        dialog.title("登録元Commandsとの差分・選択反映 - " + name)
        dialog.geometry("1280x780")
        dialog.minsize(850, 560)
        dialog.transient(self)
        state = {"rows": [], "items": {}, "backup": ""}
        summary = tk.StringVar(value="登録元を確認中…")

        help_text = (
            "サンプルリストに記録された登録元Commandsと関数単位で比較します。"
            "反映は選択関数の完全置換です。未選択の関数と他の流用先は変更しません。")
        ttk.Label(dialog, text=help_text, foreground="#174a7e",
                  wraplength=1180, justify="left").pack(
                      fill="x", padx=8, pady=(8, 3))
        ttk.Label(dialog, textvariable=summary).pack(
            fill="x", padx=8, pady=(0, 4))

        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=4)
        tree = ttk.Treeview(
            tree_frame, columns=("status", "origin", "sample"),
            show="tree headings", selectmode="extended", height=12)
        tree.heading("#0", text="登録元関数")
        tree.heading("status", text="状態")
        tree.heading("origin", text="登録元Commands")
        tree.heading("sample", text="使用サンプル")
        tree.column("#0", width=250)
        tree.column("status", width=135)
        tree.column("origin", width=500)
        tree.column("sample", width=360)
        tree_y = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        tree.grid(column=0, row=0, sticky="nsew")
        tree_y.grid(column=1, row=0, sticky="ns")
        tree_x.grid(column=0, row=1, sticky="ew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        tree.tag_configure("different", foreground="#b05a00")
        tree.tag_configure("missing_source", foreground="#8a4d00")
        tree.tag_configure("missing_origin", foreground="#a00000")
        tree.tag_configure("invalid_origin", foreground="#a00000")
        tree.tag_configure("binding_conflict", foreground="#a00000")
        labels = {
            "match": "一致", "different": "処理不一致",
            "missing_source": "登録元に関数なし",
            "missing_origin": "登録元ファイルなし",
            "invalid_origin": "登録元解析エラー",
            "binding_conflict": "同一登録先で競合",
            "duplicate_binding": "同じ登録先を参照",
        }

        diff = ttk.Panedwindow(dialog, orient="horizontal")
        diff.pack(fill="both", expand=True, padx=8, pady=4)
        left_frame, right_frame = ttk.Frame(diff), ttk.Frame(diff)
        diff.add(left_frame, weight=1); diff.add(right_frame, weight=1)
        ttk.Label(left_frame, text="登録元Commands（赤）").pack(anchor="w")
        ttk.Label(right_frame, text="サンプル関数（緑）").pack(anchor="w")
        left = tk.Text(left_frame, wrap="none", state="disabled",
                       font=self.code_font, height=13)
        right = tk.Text(right_frame, wrap="none", state="disabled",
                        font=self.code_font, height=13)
        pack_scrollable_widget(left, horizontal=True)
        pack_scrollable_widget(right, horizontal=True)
        left.tag_configure("changed", background="#ffc7ce", foreground="#8a1010")
        right.tag_configure("changed", background="#c6efce", foreground="#126b12")
        left.tag_configure("missing", background="#f2f2f2", foreground="#888888")
        right.tag_configure("missing", background="#f2f2f2", foreground="#888888")

        def render_row(row):
            for widget in (left, right):
                widget.configure(state="normal")
                widget.delete("1.0", "end")
            for value in side_by_side_diff_rows(
                    row.get("source_text", ""), row.get("comparison_text", "")):
                left_line = ("{:>5}  {}\n".format(
                    value["left_line"] or "", value["left"]))
                right_line = ("{:>5}  {}\n".format(
                    value["right_line"] or "", value["right"]))
                left.insert("end", left_line,
                            "changed" if value["kind"] != "equal" else ())
                right.insert("end", right_line,
                             "changed" if value["kind"] != "equal" else ())
            for widget in (left, right):
                widget.configure(state="disabled")

        def selected_rows():
            return [state["items"][iid] for iid in tree.selection()
                    if iid in state["items"]]

        def on_select(event=None):
            rows = selected_rows()
            if rows:
                render_row(rows[0])
        tree.bind("<<TreeviewSelect>>", on_select)

        def refresh():
            try:
                rows = compare_sample_list_origins(
                    self.fragment_root(), self._read_sample_lists(), name)
            except (OSError, SyntaxError, ValueError, KeyError) as error:
                messagebox.showerror("登録元Commands同期", str(error), parent=dialog)
                return
            state["rows"] = rows
            state["items"] = {}
            tree.delete(*tree.get_children())
            for row in rows:
                iid = tree.insert(
                    "", "end", text=row["origin_function"],
                    values=(labels.get(row["status"], row["status"]),
                            row["origin_path"] or "（未記録）",
                            row["sample_id"]), tags=(row["status"],))
                state["items"][iid] = row
            counts = {}
            for row in rows:
                counts[row["status"]] = counts.get(row["status"], 0) + 1
            summary.set("登録元{}ファイル / 関数{}件: {}".format(
                len({row["origin_path"] for row in rows if row["origin_path"]}),
                len(rows), ", ".join(
                    "{} {}件".format(labels.get(key, key), value)
                    for key, value in sorted(counts.items()))))
            for iid, row in state["items"].items():
                if row["status"] in ("different", "missing_source"):
                    tree.selection_add(iid)
            on_select()

        def dirty_paths():
            result = set()
            self.capture_active_editor_document()
            for document in self.editor_documents.values():
                if document.get("dirty") and document.get("path"):
                    result.add(os.path.normcase(os.path.abspath(document["path"])))
            return result

        def reload_changed_editor(paths):
            changed = {os.path.normcase(os.path.abspath(path)) for path in paths}
            for tab_id, document in self.editor_documents.items():
                path = document.get("path")
                if not path or os.path.normcase(os.path.abspath(path)) not in changed:
                    continue
                with open(path, "r", encoding="utf-8-sig") as stream:
                    document.update({"content": stream.read(), "dirty": False})
                if tab_id == self.active_editor_tab:
                    self.load_editor_document(tab_id)

        def apply_selected():
            rows = selected_rows()
            rows = [row for row in rows if row["status"] in (
                "different", "missing_source")]
            if not rows:
                messagebox.showinfo(
                    "登録元Commands同期", "反映対象の差分を選択してください。",
                    parent=dialog); return
            targets = {os.path.normcase(os.path.abspath(row["origin_path"]))
                       for row in rows if row["origin_path"]}
            overlapping = targets & dirty_paths()
            if overlapping:
                messagebox.showwarning(
                    "登録元Commands同期",
                    "保存していない登録元Commandsがあります。先に保存してください。\n" +
                    "\n".join(sorted(overlapping)), parent=dialog)
                return
            if not messagebox.askyesno(
                    "サンプル → 登録元Commands",
                    "選択した{}関数を{}ファイルへ反映しますか？\n"
                    "反映前バックアップを作成します。".format(
                        len(rows), len(targets)), parent=dialog):
                return
            backup_root = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "Backups",
                "SampleOriginSync")
            try:
                result = apply_sample_list_to_origins(
                    state["rows"], [row["key"] for row in rows],
                    backup_root, name)
            except (OSError, SyntaxError, ValueError) as error:
                messagebox.showerror("登録元Commands同期", str(error), parent=dialog)
                return
            if result.get("backup"):
                state["backup"] = result["backup"]["manifest_path"]
                restore_button.configure(state="normal")
            reload_changed_editor(result["changed"])
            self.status.set("サンプルから登録元Commandsへ{}関数反映しました。".format(
                result["functions"]))
            refresh()

        def restore_last():
            if not state["backup"]:
                return
            if not messagebox.askyesno(
                    "登録元Commands同期の復元",
                    "直前の反映前へ登録元Commandsを戻しますか？", parent=dialog):
                return
            try:
                manifest = restore_origin_sync_backup(state["backup"])
                paths = [entry["path"] for entry in manifest.get("files", [])]
                reload_changed_editor(paths)
            except (OSError, ValueError) as error:
                messagebox.showerror("登録元Commands同期", str(error), parent=dialog)
                return
            restore_button.configure(state="disabled")
            state["backup"] = ""
            refresh()

        actions = ttk.Frame(dialog)
        actions.pack(fill="x", padx=8, pady=(3, 8))
        ttk.Button(actions, text="再チェック", command=refresh).pack(side="left")
        ttk.Button(
            actions, text="差分をすべて選択",
            command=lambda: [tree.selection_add(iid) for iid, row in
                             state["items"].items() if row["status"] in
                             ("different", "missing_source")]).pack(
                                 side="left", padx=3)
        restore_button = ttk.Button(
            actions, text="直前の反映を復元", command=restore_last,
            state="disabled")
        restore_button.pack(side="right", padx=3)
        ttk.Button(
            actions, text="選択したサンプルを登録元へ反映",
            command=apply_selected).pack(side="right", padx=3)
        refresh()

    def sample_list_tag_choices(self):
        data = self._read_sample_lists()
        return [tag for item in data["lists"].values() for tag in item.get("tags", [])]

    def refresh_sample_lists_tab(self, select=None, member=None,
                                 render_preview=True, refresh_catalog=True):
        if not hasattr(self, "sample_lists_tree"):
            return
        data = self._read_sample_lists(); lists = data["lists"]
        self.sample_lists_tree.delete(0, "end")
        needle = self.sample_list_filter.get().strip().lower() if hasattr(self, "sample_list_filter") else ""
        visible = [name for name, item in lists.items() if not needle or needle in name.lower() or needle in [tag.lower() for tag in item.get("tags", [])]]
        target = select or self.sample_list_name.get().strip()
        if target not in visible:
            target = sorted(visible)[0] if visible else None
        for index, name in enumerate(sorted(visible)):
            self.sample_lists_tree.insert("end", name)
            if name == target:
                self.sample_lists_tree.selection_set(index)
                self.sample_lists_tree.see(index)
        if hasattr(self, "sample_nested_list"):
            self.sample_nested_list.delete(0, "end")
            for name in sorted(lists): self.sample_nested_list.insert("end", name)
        if hasattr(self, "sample_program_combo"):
            self.sample_program_combo.configure(values=sorted(lists))
        if hasattr(self, "sample_list_tag_picker"):
            self.sample_list_tag_picker.refresh_choices()
        if refresh_catalog:
            self.refresh_sample_catalog()
        if target:
            self._display_sample_list(
                target, member, render_preview=render_preview)
        elif hasattr(self, "sample_list_preview"):
            self.sample_list_preview.configure(state="normal")
            self.sample_list_preview.delete("1.0", "end")
            self.sample_list_preview.insert("1.0", self.ui_text("# No sample list selected\n", "# サンプルリストが選択されていません\n"))
            self.sample_list_preview.configure(state="disabled")

    def load_selected_sample_list(self, event=None):
        selected = self.sample_lists_tree.curselection()
        if not selected:
            return
        name = self.sample_lists_tree.get(selected[0])
        self._display_sample_list(name)

    def _display_sample_list(self, name, selected_member=None,
                             render_preview=True):
        item = self._read_sample_lists()["lists"].get(name, {"tags": [], "members": []}); values = item["members"]
        self.sample_list_name.set(name)
        self.sample_list_tag_picker.set_tags(item.get("tags", []))
        function_count = sum(1 for value in values if value["type"] == "fragment")
        list_count = sum(1 for value in values if value["type"] == "list")
        self.sample_list_details.set(self.ui_text(
            "Registered: {} sample function(s), {} nested sample list(s)".format(function_count, list_count),
            "登録済み: サンプル関数 {}件、入れ子のサンプルリスト {}件".format(function_count, list_count)))
        if hasattr(self, "sample_member_list"):
            self.sample_member_list.delete(0, "end")
            for value in values:
                kind = self.ui_text("Registered sample function", "登録済みサンプル関数") \
                    if value["type"] == "fragment" else self.ui_text("Registered sample list", "登録済みサンプルリスト")
                self.sample_member_list.insert("end", "{}: {}".format(kind, value["id"]))
            if selected_member is not None and 0 <= selected_member < len(values):
                self.sample_member_list.selection_set(selected_member); self.sample_member_list.see(selected_member)
        if render_preview:
            self.refresh_sample_list_preview()
        else:
            self._sample_lists_refresh_deferred = name
            self.sample_list_preview.configure(state="normal")
            self.sample_list_preview.delete("1.0", "end")
            self.sample_list_preview.insert(
                "1.0", "サンプルリストを開いたときにプレビューを生成します。\n")
            self.sample_list_preview.configure(state="disabled")

    def delete_sample_list(self):
        selected = self.sample_lists_tree.curselection()
        name = self.sample_lists_tree.get(selected[0]) if selected else self.sample_list_name.get().strip()
        data = self._read_sample_lists()
        if not name or name not in data["lists"]:
            return
        if not messagebox.askyesno(self.ui_text("Delete sample list", "サンプルリストの削除"),
                                   self.ui_text("Delete '{}'?", "「{}」を削除しますか？").format(name), parent=self):
            return
        del data["lists"][name]
        for item in data["lists"].values():
            item["members"] = [member for member in item["members"] if not (member["type"] == "list" and member["id"] == name)]
        self._write_sample_lists(data)
        self.refresh_sample_apply_lists()
        self.refresh_sample_lists_tab()
        self.sample_list_details.set(self.ui_text("Deleted sample list: ", "サンプルリストを削除しました: ") + name)

    def refresh_sample_apply_lists(self, include_images=True):
        if not hasattr(self, "sample_apply_list"):
            return
        self.sample_apply_list.delete(0, "end")
        for name in sorted(self._read_sample_lists()["lists"]):
            self.sample_apply_list.insert("end", name)
        if include_images:
            self.refresh_sample_apply_image_tree()
            self._sample_apply_images_loaded = True

    def refresh_sample_apply_image_tree(self):
        if not hasattr(self, "sample_apply_image_tree"):
            return
        tree = self.sample_apply_image_tree; tree.delete(*tree.get_children()); self.sample_apply_image_nodes = {}
        data = self._read_image_library(); needle = self.sample_apply_image_search.get().strip().lower()
        visible_targets = set()
        for name, item in data["targets"].items():
            searchable = " ".join([name, item.get("description", "")] + item.get("tags", []) + [v.get("template_path", "") for v in item.get("variants", [])]).lower()
            if not needle or needle in searchable: visible_targets.add(name)

        folder_nodes = {}
        root = tree.insert("", "end", text="Template画像階層", open=True)
        for name in sorted(visible_targets, key=str.lower):
            item = data["targets"][name]; variants = item.get("variants", [])
            path = variants[0].get("template_path", "") if variants else ""
            parts = path.replace("\\", "/").split("/")
            if parts and parts[0].lower() == "template": parts = parts[1:]
            parent, accumulated = root, []
            for folder in parts[:-1]:
                accumulated.append(folder); key = "/".join(accumulated)
                if key not in folder_nodes: folder_nodes[key] = tree.insert(parent, "end", text=folder, open=bool(needle))
                parent = folder_nodes[key]
            iid = tree.insert(parent, "end", text="画像検知: {} [{}]".format(name, item.get("operator", "OR")))
            self.sample_apply_image_nodes[iid] = "target:" + name

        list_root = tree.insert("", "end", text="画像検知リスト", open=True)
        counter = [0]
        def add_list(parent, list_name, stack):
            try: target_names = resolve_image_list(data, list_name)
            except ValueError: target_names = []
            list_item = data["lists"].get(list_name, {})
            searchable = " ".join([list_name, list_item.get("description", "")] + target_names).lower()
            if needle and needle not in searchable and not any(target in visible_targets for target in target_names): return
            counter[0] += 1; iid = tree.insert(parent, "end", text="フォルダー: {}".format(list_name), open=bool(needle))
            self.sample_apply_image_nodes[iid] = "list:" + list_name
            if list_name in stack: return
            for member in data["lists"].get(list_name, {}).get("members", []):
                if member["type"] == "list": add_list(iid, member["id"], stack + [list_name])
                elif member["id"] in visible_targets:
                    target_item = data["targets"].get(member["id"], {})
                    child = tree.insert(iid, "end", text="画像検知: {} [{}]".format(member["id"], target_item.get("operator", "OR")))
                    self.sample_apply_image_nodes[child] = "target:" + member["id"]
        for name in sorted(data["lists"], key=str.lower): add_list(list_root, name, [])

    def add_sample_apply_image_selection(self):
        existing = set(self.sample_apply_image_selected.get(0, "end"))
        for iid in self.sample_apply_image_tree.selection():
            value = self.sample_apply_image_nodes.get(iid)
            if value and value not in existing:
                self.sample_apply_image_selected.insert("end", value); existing.add(value)

    def remove_sample_apply_image_selection(self):
        selected = list(self.sample_apply_image_selected.curselection())
        for index in reversed(selected): self.sample_apply_image_selected.delete(index)

    def apply_sample_apply_images(self):
        values = list(self.sample_apply_image_selected.get(0, "end"))
        if not values:
            messagebox.showinfo("画像検知", "必要リストへ画像検知または画像検知リストを追加してください。", parent=self); return
        data = self._read_image_library(); targets, members = [], []
        try:
            for value in values:
                kind, name = value.split(":", 1)
                member = {"type": kind, "id": name}
                if member not in members: members.append(member)
                names = resolve_image_list(data, name) if kind == "list" else [name]
                for target in names:
                    if target not in targets: targets.append(target)
        except ValueError as error:
            messagebox.showwarning("画像検知", str(error), parent=self); return
        temporary_lists = {key: dict(value) for key, value in data["lists"].items()}
        temporary_lists["ApplySelection"] = {"description": "Apply Sample Listで選択", "members": members}
        temporary = {"schema_version": data.get("schema_version", 1), "targets": data["targets"], "lists": temporary_lists}
        code = generate_image_check(temporary, "ApplySelection", "list")
        if not messagebox.askyesno("画像検知を反映", "{}件の画像検知を編集中ソースへ生成・更新しますか？".format(len(targets)), parent=self): return
        self._apply_image_code_to_editor(self.editor, code)
        self.status.set("Apply Sample Listから{}件の画像検知を反映しました。".format(len(targets)))

    def _image_code_for_target_names(self, target_names, data=None):
        names = list(dict.fromkeys(str(name) for name in target_names if str(name).strip()))
        if not names:
            return ""
        data = self._read_image_library() if data is None else data
        names = [name for name in names if name in data["targets"]]
        if not names:
            return ""
        temporary = {
            "schema_version": data.get("schema_version", 1),
            "targets": data["targets"],
            "lists": {"SampleRequiredImages": {
                "description": "サンプル関数から自動抽出",
                "members": [{"type": "target", "id": name} for name in names],
            }},
        }
        return generate_image_check(temporary, "SampleRequiredImages", "list")

    def _missing_image_target_names(self, target_names):
        registered = self._read_image_library()["targets"]
        return [name for name in dict.fromkeys(target_names) if name not in registered]

    def apply_selected_sample_list(self):
        selected = self.sample_apply_list.curselection()
        if not selected:
            messagebox.showinfo(self.ui_text("Sample list", "サンプルリスト"),
                                self.ui_text("Select a sample list first.", "先にサンプルリストを選択してください。"), parent=self)
            return
        name = self.sample_apply_list.get(selected[0])
        try:
            preview = compose_preview(self.fragment_root(), self._read_sample_lists(), name)
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror(self.ui_text("Sample list", "サンプルリスト"), str(error), parent=self); return
        source = self.editor.get("1.0", "end-1c")
        conflicts = detect_conflicts(source, preview)
        function_comparison = compare_preview_functions(source, preview)
        support_comparison = compare_preview_support(source, preview)
        function_differences = [
            row for row in function_comparison
            if row["status"] in ("different", "duplicate")]
        support_differences = [
            row for row in support_comparison if row["status"] == "different"]
        if function_differences or support_differences:
            details = []
            if function_differences:
                details.append("関数: " + ", ".join(
                    row["name"] for row in function_differences))
            if support_differences:
                details.append("初期化・変数: " + ", ".join(
                    row["name"] for row in support_differences))
            if messagebox.askyesno(
                    "サンプルリストの差分確認が必要",
                    "既存ソースと内容が異なるため自動反映しません。\n\n{}\n\n"
                    "サンプル関数チェックを開きますか？".format("\n".join(details)),
                    parent=self):
                self.open_sample_function_check_mode()
            return
        image_targets = preview.get("image_targets", [])
        image_code = self._image_code_for_target_names(image_targets)
        missing_image_targets = self._missing_image_target_names(image_targets)
        external_variables = preview.get("external_class_variables", [])
        missing_external_variables = [
            variable for variable in external_variables
            if not re.search(
                r"(?m)^\s*" + re.escape(variable) + r"\s*=", source)]
        summary = self.ui_text(
            "Apply '{}':\n\n{}\n\nConflicts / changes are shown before insertion. Continue?",
            "「{}」を反映します。\n\n{}\n\n競合・変更内容を確認して挿入を続けますか？").format(
                name, "\n".join("- " + item for item in conflicts) if conflicts
                else self.ui_text("No conflicts detected.", "競合は検出されませんでした。"))
        if image_targets:
            summary += "\n\n必要な画像検知{}件も同時に反映します。".format(len(image_targets))
        if missing_image_targets:
            summary += "\n画像ライブラリ未登録（例外判定として保持）: " + ", ".join(missing_image_targets)
        if missing_external_variables:
            if image_code:
                summary += (
                    "\n画像検知側で管理する設定を同時生成: " +
                    ", ".join(missing_external_variables))
            else:
                summary += (
                    "\n注意: 別途登録が必要な外部設定: " +
                    ", ".join(missing_external_variables))
        if not messagebox.askyesno(self.ui_text("Apply sample list", "サンプルリストの反映"), summary, parent=self):
            return
        try:
            merged, _support_rows = merge_preview_support_safely(source, preview)
            merged, _function_rows = merge_preview_functions_safely(
                merged, preview, name)
        except (SyntaxError, ValueError) as error:
            messagebox.showwarning(
                "サンプルリストの安全反映", str(error), parent=self)
            return
        self.editor.delete("1.0", "end"); self.editor.insert("1.0", merged)
        if image_code:
            self._apply_image_code_to_editor(self.editor, image_code)
        self.editor.edit_modified(True)
        self.status.set(self.ui_text("Applied sample list after conflict review: ", "競合確認後にサンプルリストを反映しました: ") + name)

    def _build_sample_program_tab(self, parent):
        self.sample_program_list = tk.StringVar()
        self.sample_program_path = tk.StringVar()
        top = ttk.Frame(parent); top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="元リスト:").pack(side="left")
        self.sample_program_combo = ttk.Combobox(top, textvariable=self.sample_program_list, state="readonly", width=28)
        self.sample_program_combo.pack(side="left", padx=5)
        ttk.Button(top, text="編集シェル作成", command=self.create_sample_program_shell).pack(side="left", padx=3)
        ttk.Button(top, text="サンプル関数から更新", command=self.refresh_sample_program_fragments).pack(side="left", padx=3)
        ttk.Button(top, text="読込・検証", command=self.validate_sample_program).pack(side="left", padx=3)
        ttk.Button(top, text="サンプルソースを保存", command=self.publish_sample_program).pack(side="left", padx=3)
        ttk.Label(parent, text="更新時は POKECON_USER_DO / POKECON_USER_METHODS 内の編集を保持します。生成領域の直接編集は競合として確認します。").pack(fill="x", padx=10)
        ttk.Label(parent, text="TabはPython安全用の半角スペース4文字です。行番号をドラッグすると複数行を選択できます。").pack(fill="x", padx=10)
        ttk.Label(parent, textvariable=self.sample_program_path).pack(fill="x", padx=10)
        editor_frame = ttk.Frame(parent)
        editor_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.sample_program_line_numbers = tk.Text(editor_frame, width=6, padx=4, takefocus=0, state="disabled",
                                                   wrap="none", background="#252526", foreground="#858585",
                                                   selectbackground="#264f78", cursor="arrow",
                                                   font=self.code_font, tabs=self.code_tabs)
        self.sample_program_line_numbers.pack(side="left", fill="y")
        self.sample_program_editor = tk.Text(editor_frame, undo=True, wrap="none",
                                             font=self.code_font, tabs=self.code_tabs,
                                             background="#1e1e1e", foreground="#d4d4d4",
                                             insertbackground="white", selectbackground="#264f78")
        self.sample_program_editor.pack(side="left", fill="both", expand=True)
        editor_y = ttk.Scrollbar(editor_frame, orient="vertical", command=self._scroll_sample_program_editor)
        editor_y.pack(side="right", fill="y")
        editor_x = ttk.Scrollbar(parent, orient="horizontal", command=self.sample_program_editor.xview)
        editor_x.pack(fill="x", padx=10, pady=(0, 8))
        self.sample_program_editor.configure(
            yscrollcommand=lambda first, last: self._sync_sample_program_scroll(editor_y, first, last),
            xscrollcommand=editor_x.set)
        self.sample_program_editor.bind("<<Modified>>", self._sample_program_modified)
        self.sample_program_editor.bind("<KeyRelease>", lambda event: self.after_idle(self._update_sample_program_line_numbers))
        self.sample_program_editor.bind("<Tab>", self._sample_program_tab)
        self.sample_program_editor.bind("<Shift-Tab>", self._sample_program_shift_tab)
        self.sample_program_editor.bind("<Return>", self._sample_program_newline)
        self._register_find_editor(
            self.sample_program_editor, "サンプルプログラム")
        self.sample_program_line_numbers.bind("<Button-1>", self._sample_program_line_select_start)
        self.sample_program_line_numbers.bind("<B1-Motion>", self._sample_program_line_select_drag)
        self.sample_program_line_numbers.bind("<MouseWheel>", lambda event: self.sample_program_editor.yview_scroll(-1 if event.delta > 0 else 1, "units"))
        self._sample_program_line_anchor = 1
        self._update_sample_program_line_numbers()

    def _scroll_sample_program_editor(self, *args):
        self.sample_program_editor.yview(*args)
        self.sample_program_line_numbers.yview(*args)

    def _sync_sample_program_scroll(self, scrollbar, first, last):
        scrollbar.set(first, last)
        self.sample_program_line_numbers.yview_moveto(first)

    def _sample_program_modified(self, event=None):
        if self.sample_program_editor.edit_modified():
            self.sample_program_editor.edit_modified(False)
            self.after_idle(self._update_sample_program_line_numbers)

    def _update_sample_program_line_numbers(self):
        if not hasattr(self, "sample_program_editor"): return
        line_count = int(self.sample_program_editor.index("end-1c").split(".")[0])
        content = "\n".join(str(number) for number in range(1, line_count + 1))
        self.sample_program_line_numbers.configure(state="normal")
        self.sample_program_line_numbers.delete("1.0", "end")
        self.sample_program_line_numbers.insert("1.0", content)
        self.sample_program_line_numbers.configure(state="disabled")
        self.sample_program_line_numbers.yview_moveto(self.sample_program_editor.yview()[0])

    def _sample_program_line_at(self, y):
        return int(self.sample_program_line_numbers.index("@0,{}".format(y)).split(".")[0])

    def _sample_program_select_lines(self, first, last):
        start, end = sorted((first, last))
        self.sample_program_editor.tag_remove("sel", "1.0", "end")
        self.sample_program_editor.tag_add("sel", "{}.0".format(start), "{}.0".format(end + 1))
        self.sample_program_editor.mark_set("insert", "{}.0".format(start))
        self.sample_program_editor.see("{}.0".format(end))
        self.sample_program_editor.focus_set()

    def _sample_program_line_select_start(self, event):
        self._sample_program_line_anchor = self._sample_program_line_at(event.y)
        self._sample_program_select_lines(self._sample_program_line_anchor, self._sample_program_line_anchor)
        return "break"

    def _sample_program_line_select_drag(self, event):
        self._sample_program_select_lines(self._sample_program_line_anchor, self._sample_program_line_at(event.y))
        return "break"

    def _sample_program_selected_line_range(self):
        try:
            first = int(self.sample_program_editor.index("sel.first").split(".")[0])
            last_index = self.sample_program_editor.index("sel.last")
            last_line, last_column = [int(value) for value in last_index.split(".")]
            return first, last_line - 1 if last_column == 0 and last_line > first else last_line
        except tk.TclError:
            line = int(self.sample_program_editor.index("insert").split(".")[0])
            return line, line

    def _sample_program_tab(self, event=None):
        editor = self.sample_program_editor
        try:
            editor.index("sel.first")
        except tk.TclError:
            editor.insert("insert", "    ")
            return "break"
        first, last = self._sample_program_selected_line_range()
        for line in range(first, last + 1): editor.insert("{}.0".format(line), "    ")
        self._sample_program_select_lines(first, last)
        return "break"

    def _sample_program_shift_tab(self, event=None):
        editor = self.sample_program_editor
        first, last = self._sample_program_selected_line_range()
        for line in range(first, last + 1):
            value = editor.get("{}.0".format(line), "{}.4".format(line))
            remove = min(4, len(value) - len(value.lstrip(" ")))
            if remove: editor.delete("{}.0".format(line), "{}.{}".format(line, remove))
            elif value.startswith("\t"): editor.delete("{}.0".format(line), "{}.1".format(line))
        if first != last: self._sample_program_select_lines(first, last)
        return "break"

    def _sample_program_newline(self, event=None):
        editor = self.sample_program_editor
        try:
            editor.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        line_start = editor.index("insert linestart")
        before_cursor = editor.get(line_start, "insert")
        indent_match = re.match(r"[ \t]*", before_cursor)
        indent = indent_match.group(0).replace("\t", "    ") if indent_match else ""
        editor.insert("insert", "\n" + indent)
        return "break"

    def _highlight_sample_program_error(self, error):
        line = getattr(error, "lineno", None)
        if not line: return
        self._sample_program_select_lines(max(1, int(line)), max(1, int(line)))

    def _sample_program_source(self, name, fragment_root=None, data=None,
                               image_library=None):
        fragment_root = fragment_root or self.fragment_root()
        data = self._read_sample_lists() if data is None else data
        preview = compose_preview(fragment_root, data, name)
        safe = python_identifier(name) + "SampleCommand"
        imports = self._generated_region("IMPORTS", "\n".join(preview["imports"]), "")
        variables = self._generated_region("CLASS_VARIABLES", "\n".join("    " + line for line in preview["class_variables"]), "    ")
        initializer_body = "\n".join(self._indent_source(value, "        ") for value in preview.get("initializers", []))
        initializers = self._generated_region("INITIALIZERS", initializer_body or "        pass", "        ")
        step_blocks, helper_blocks = [], []
        for member in resolve_members(data, name):
            metadata, body, _, _ = load_fragment(fragment_root, member["id"])
            if metadata.get("target") == "step_user_block":
                step_blocks.append(self._fragment_region(member["id"], body, "        "))
            else:
                helper_blocks.append(self._fragment_region(member["id"], body, "    "))
        step_source = "\n".join(step_blocks)
        helper_source = "\n".join(helper_blocks)
        image_code = self._image_code_for_target_names(
            preview.get("image_targets", []), data=image_library)
        image_import = ("from LocalFunction.ImageDetection import SimilarityHistory, detect_image\n"
                        if image_code else "")
        image_source = textwrap.indent(image_code.rstrip(), "    ") + "\n\n" if image_code else ""
        return ("#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n"
                "# Authored by PokeCon Dev Studio from sample list: {name}\n"
                "from Commands.PythonSampleCommand import PythonSampleCommand\n"
                "{image_import}{imports}\n"
                "class {safe}(PythonSampleCommand):\n"
                "    NAME = {name!r}\n    SAMPLE_LIST = {name!r}\n    INCLUDED_SAMPLES = {included!r}\n"
                "{variables}\n"
                "    def initialize_sample(self):\n"
                "{initializers}"
                "        # POKECON_USER_INIT_BEGIN\n"
                "        # Add per-run initialization that must be preserved here.\n"
                "        # POKECON_USER_INIT_END\n\n"
                "    def do(self):\n        self.checkIfAlive()\n        self.initialize_sample()\n"
                "        # POKECON_USER_DO_BEGIN\n"
                "        # Compose/call selected sample functions here.\n"
                "        # POKECON_USER_DO_END\n"
                "{step_source}\n\n{helper_source}\n{image_source}"
                "    # POKECON_USER_METHODS_BEGIN\n"
                "    # Add methods that must be preserved across sample updates here.\n"
                "    # POKECON_USER_METHODS_END\n").format(
                    name=name, image_import=image_import, imports=imports, safe=safe, included=preview["included"],
                    variables=variables, initializers=initializers,
                    step_source=step_source, helper_source=helper_source, image_source=image_source)

    def _source_hash(self, value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _indent_source(self, source, indent):
        # A fragment pasted from an existing class often already has four
        # leading spaces.  Normalize its common indentation before placing it
        # in the generated command; otherwise a method becomes local to do().
        source = textwrap.dedent(source).rstrip()
        return "\n".join(indent + line if line else "" for line in source.splitlines())

    def _generated_region(self, name, content, indent):
        digest = self._source_hash(content)
        return ("{indent}# POKECON_GENERATED_{name}_BEGIN {digest}\n{content}\n"
                "{indent}# POKECON_GENERATED_{name}_END\n").format(
                    indent=indent, name=name, digest=digest, content=content)

    def _fragment_region(self, fragment_id, body, indent):
        content = self._indent_source(body, indent)
        digest = self._source_hash(content)
        return ("{indent}# POKECON_FRAGMENT_BEGIN {digest} {fragment_id}\n{content}\n"
                "{indent}# POKECON_FRAGMENT_END {fragment_id}\n").format(
                    indent=indent, digest=digest, fragment_id=fragment_id, content=content)

    def _extract_user_region(self, source, name):
        pattern = re.compile(r"(?ms)^(?P<indent>[ \t]*)# POKECON_USER_" + name + r"_BEGIN\n(?P<body>.*?)^\1# POKECON_USER_" + name + r"_END$")
        match = pattern.search(source)
        return match.group("body") if match else None

    def _replace_user_region(self, source, name, body):
        pattern = re.compile(r"(?ms)^(?P<indent>[ \t]*)# POKECON_USER_" + name + r"_BEGIN\n.*?^\1# POKECON_USER_" + name + r"_END$")
        match = pattern.search(source)
        if not match: return source
        indent = match.group("indent")
        replacement = indent + "# POKECON_USER_" + name + "_BEGIN\n" + body + indent + "# POKECON_USER_" + name + "_END"
        return source[:match.start()] + replacement + source[match.end():]

    def _extract_image_check_block(self, source):
        pattern = re.compile(r"(?ms)^(?P<indent>[ \t]*)# POKECON_IMAGE_CHECK_BEGIN\n.*?^\1# POKECON_IMAGE_CHECK_END\s*$")
        match = pattern.search(source)
        return match.group(0).rstrip() if match else None

    def _fragment_blocks(self, source):
        pattern = re.compile(r"(?ms)^(?P<indent>[ \t]*)# POKECON_FRAGMENT_BEGIN (?P<hash>[0-9a-f]{64}) (?P<id>[^\n]+)\n(?P<body>.*?)^\1# POKECON_FRAGMENT_END (?P=id)$")
        return {match.group("id"): match for match in pattern.finditer(source)}

    def _generated_blocks(self, source):
        pattern = re.compile(r"(?ms)^(?P<indent>[ \t]*)# POKECON_GENERATED_(?P<name>[A-Z_]+)_BEGIN (?P<hash>[0-9a-f]{64})\n(?P<body>.*?)^\1# POKECON_GENERATED_(?P=name)_END$")
        return {match.group("name"): match for match in pattern.finditer(source)}

    def refresh_sample_program_fragments(self):
        name = self.sample_program_list.get().strip()
        current = self.sample_program_editor.get("1.0", "end-1c")
        if not name:
            messagebox.showwarning(self.ui_text("Sample program", "サンプルプログラム"),
                                   self.ui_text("Select the source sample list first.", "元になるサンプルリストを選択してください。"), parent=self); return
        try:
            fresh = self._sample_program_source(name); compile(fresh, "<sample-program-update>", "exec")
        except (OSError, ValueError, KeyError, SyntaxError) as error:
            messagebox.showerror(self.ui_text("Sample program update", "サンプルプログラムの更新"), str(error), parent=self); return
        if "POKECON_FRAGMENT_BEGIN" not in current and "POKECON_USER_DO_BEGIN" not in current:
            if not messagebox.askyesno(self.ui_text("Sample program update", "サンプルプログラムの更新"),
                                       self.ui_text("This is an older markerless program. Its edits cannot be separated safely. Rebuild it using the latest samples?",
                                                    "更新用マーカーがない旧形式のプログラムです。編集内容を安全に分離できません。最新のサンプルから再生成しますか？"), parent=self): return
            updated = fresh
        else:
            current_blocks = self._fragment_blocks(current); fresh_blocks = self._fragment_blocks(fresh)
            edited = [fragment_id for fragment_id, match in current_blocks.items()
                      if self._source_hash(match.group("body").rstrip("\n")) != match.group("hash")]
            edited_metadata = [block_name for block_name, match in self._generated_blocks(current).items()
                               if self._source_hash(match.group("body").rstrip("\n")) != match.group("hash")]
            added = sorted(set(fresh_blocks) - set(current_blocks)); removed = sorted(set(current_blocks) - set(fresh_blocks))
            notices = []
            if edited: notices.append("Generated blocks edited directly: " + ", ".join(edited))
            if edited_metadata: notices.append("Generated metadata edited directly: " + ", ".join(edited_metadata))
            if added: notices.append(self.ui_text("New sample functions: ", "追加されたサンプル関数: ") + ", ".join(added))
            if removed: notices.append(self.ui_text("Removed sample functions: ", "外されたサンプル関数: ") + ", ".join(removed))
            if notices and not messagebox.askyesno(self.ui_text("Sample program update", "サンプルプログラムの更新"),
                                                   "\n".join(notices) + self.ui_text("\n\nReplace generated blocks and keep user regions?",
                                                                                     "\n\n生成領域を置き換え、ユーザー編集領域を保持しますか？"), parent=self): return
            updated = fresh
            for region_name in ("INIT", "DO", "METHODS"):
                body = self._extract_user_region(current, region_name)
                if body is not None: updated = self._replace_user_region(updated, region_name, body)
            image_user = self._extract_image_check_user(current)
            if image_user is not None and "POKECON_IMAGE_CHECK_BEGIN" in updated:
                updated = self._replace_image_check_user(updated, textwrap.dedent(image_user))
            image_check_block = self._extract_image_check_block(current)
            if image_check_block and "POKECON_IMAGE_CHECK_BEGIN" not in fresh:
                image_import = "from LocalFunction.ImageDetection import SimilarityHistory, detect_image"
                if image_import not in updated:
                    class_at = updated.find("class "); updated = updated[:class_at] + image_import + "\n\n" + updated[class_at:]
                marker = "    # POKECON_USER_METHODS_BEGIN"
                updated = updated.replace(marker, image_check_block + "\n\n" + marker, 1)
        try:
            compile(updated, "<sample-program-update>", "exec")
        except SyntaxError as error:
            self.sample_program_editor.delete("1.0", "end"); self.sample_program_editor.insert("1.0", updated)
            self._highlight_sample_program_error(error)
            messagebox.showerror(self.ui_text("Sample program update", "サンプルプログラムの更新"),
                                 self.ui_text("Preserved user code has a syntax error:\n{}", "保持したユーザーコードに構文エラーがあります:\n{}").format(error), parent=self); return
        self.sample_program_editor.delete("1.0", "end"); self.sample_program_editor.insert("1.0", updated)
        self.sample_program_path.set(self.ui_text("Updated in editor from sample list: ", "サンプルリストからエディタを更新しました: ") + name)
        self.status.set(self.ui_text("Updated sample functions; user regions were preserved: ", "ユーザー編集領域を保持してサンプル関数を更新しました: ") + name)

    def create_sample_program_shell(self):
        name = self.sample_program_list.get() or self.sample_list_name.get().strip()
        if not name:
            messagebox.showwarning("Sample program", "Select a sample list first.", parent=self); return
        try:
            source = self._sample_program_source(name); compile(source, "<sample-program>", "exec")
        except (OSError, ValueError, KeyError, SyntaxError) as error:
            if isinstance(error, SyntaxError): self._highlight_sample_program_error(error)
            messagebox.showerror("Sample program", str(error), parent=self); return
        self.sample_program_editor.delete("1.0", "end"); self.sample_program_editor.insert("1.0", source)
        self.sample_program_list.set(name); self.sample_program_path.set("Unsaved program based on: " + name)

    def validate_sample_program(self):
        root = self.sample_commands_root(); os.makedirs(root, exist_ok=True)
        path = filedialog.askopenfilename(parent=self, initialdir=root, filetypes=[("Python", "*.py")])
        if not path: return
        if not self._is_under_sample_commands(path):
            messagebox.showwarning("Sample source", "Choose a file under DevStudio/SampleCommands.", parent=self); return
        try:
            info = inspect_sample_program(path)
        except (OSError, SyntaxError, ValueError) as error:
            if isinstance(error, SyntaxError):
                try:
                    with open(path, "r", encoding="utf-8") as stream: source = stream.read()
                    self.sample_program_editor.delete("1.0", "end"); self.sample_program_editor.insert("1.0", source)
                    self._highlight_sample_program_error(error)
                except OSError:
                    pass
            messagebox.showerror("PythonSampleCommand loader", str(error), parent=self); return
        self.sample_program_editor.delete("1.0", "end"); self.sample_program_editor.insert("1.0", info["source"])
        list_match = re.search(r"(?m)^\s*SAMPLE_LIST\s*=\s*(['\"])(.*?)\1", info["source"])
        if list_match:
            self.sample_program_list.set(list_match.group(2))
        self.sample_program_path.set(info["path"]); self.status.set("Loaded PythonSampleCommand: " + info["class_name"])

    def publish_sample_program(self):
        source = self.sample_program_editor.get("1.0", "end-1c")
        root = self.sample_commands_root(); os.makedirs(root, exist_ok=True)
        initial_name = python_identifier(self.sample_program_list.get() or "sample_program") + ".py"
        output = filedialog.asksaveasfilename(parent=self, initialdir=root, initialfile=initial_name,
                                              defaultextension=".py", filetypes=[("Python", "*.py")])
        if not output: return
        if not self._is_under_sample_commands(output):
            messagebox.showwarning("Sample source", "Save under DevStudio/SampleCommands or one of its subfolders.", parent=self); return
        try:
            compile(source, output, "exec")
            temporary = output + ".tmp"
            with open(temporary, "w", encoding="utf-8", newline="\n") as stream: stream.write(source.rstrip() + "\n")
            os.replace(temporary, output)
            info = inspect_sample_program(output)
        except (OSError, SyntaxError, ValueError) as error:
            if isinstance(error, SyntaxError): self._highlight_sample_program_error(error)
            messagebox.showerror("PythonSampleCommand loader", str(error), parent=self); return
        self.sample_program_path.set(output)
        self.status.set("Saved sample source: " + info["class_name"])

    def sample_commands_root(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "SampleCommands")

    def _is_under_sample_commands(self, path):
        root = os.path.abspath(self.sample_commands_root())
        target = os.path.abspath(path)
        try:
            return os.path.commonpath([root, target]) == root
        except ValueError:
            return False

    def choose_image_target(self):
        path = filedialog.askopenfilename(parent=self, title="Select detection image", filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")])
        if path:
            self.image_target_path.set(path)
            if self.image_target_name.get().strip() in ("", "target"):
                self.image_target_name.set(os.path.splitext(os.path.basename(path))[0])

    def _image_library_config_path(self):
        return os.path.join(self.template_root(), "image_detection_profiles.json")

    def template_root(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "SerialController", "Template"))

    def _read_image_library(self):
        return load_image_library(self._image_library_config_path())

    def _portable_template_path(self, path):
        path = os.path.abspath(path)
        try:
            if os.path.commonpath([self.template_root(), path]) == self.template_root():
                return os.path.relpath(path, os.path.dirname(self.template_root())).replace("\\", "/")
        except ValueError:
            pass
        return path

    def choose_image_library_path(self):
        path = filedialog.askopenfilename(parent=self, initialdir=self.template_root(), title="画像検知テンプレートを選択",
                                          filetypes=[("画像", "*.png *.jpg *.jpeg *.bmp"), ("すべて", "*.*")])
        if path:
            self.image_library_path.set(path)
            self._show_image_library_preview(path)
            if self.image_library_name.get().strip() in ("", "PROFILE"):
                self.image_library_name.set(os.path.splitext(os.path.basename(path))[0].upper())

    def _clear_image_library_preview(self, message="左のツリーからパターンを選択してください。"):
        if not hasattr(self, "image_library_preview_label"):
            return
        self.image_library_preview_photo = None
        self.image_library_preview_label.configure(image="", text=message)
        self.image_library_preview_label.image = None
        self.image_library_preview_info.set("")

    def _show_image_library_preview(self, path):
        """Load a bounded template preview without retaining the source file."""
        if not hasattr(self, "image_library_preview_label"):
            return
        raw_path = str(path or "").strip()
        if not raw_path:
            self._clear_image_library_preview()
            return
        path = os.path.abspath(raw_path)
        if not os.path.isfile(path):
            self._clear_image_library_preview("画像ファイルが見つかりません。")
            self.image_library_preview_info.set(path)
            return
        if PILImage is None or PILImageTk is None:
            self._clear_image_library_preview("画像表示にはPillowが必要です。")
            self.image_library_preview_info.set(path)
            return
        try:
            with PILImage.open(path) as opened:
                original_size = opened.size
                image = opened.convert("RGBA")
            target_size = image_preview_size(
                original_size[0], original_size[1], 480, 210)
            if target_size != original_size:
                resampling = getattr(PILImage, "Resampling", PILImage)
                method = resampling.LANCZOS \
                    if target_size[0] < original_size[0] \
                    else resampling.NEAREST
                image = image.resize(target_size, method)
            photo = PILImageTk.PhotoImage(image, master=self)
        except (OSError, ValueError) as error:
            self._clear_image_library_preview("画像を表示できません。")
            self.image_library_preview_info.set("{}\n{}".format(path, error))
            return
        self.image_library_preview_photo = photo
        self.image_library_preview_label.configure(image=photo, text="")
        self.image_library_preview_label.image = photo
        self.image_library_preview_info.set(
            "{} × {} px\n{}".format(
                original_size[0], original_size[1], path))

    def _image_variant_fields(self):
        name, path = self.image_library_name.get().strip(), self.image_library_path.get().strip()
        if not name or not path or not os.path.isfile(os.path.abspath(path)):
            raise ValueError("検知名と存在する画像を指定してください。")
        try:
            crop = [int(part.strip()) for part in self.image_library_crop.get().split(",")]
            threshold = float(self.image_library_threshold.get())
            if len(crop) != 4 or not 0.0 <= threshold <= 1.0:
                raise ValueError
        except (ValueError, tk.TclError):
            raise ValueError("閾値は0～1、範囲はx1,y1,x2,y2で指定してください。")
        portable = self._portable_template_path(path)
        tags = image_folder_tags(self.template_root(), os.path.abspath(path))
        return name, {"template_path": portable, "threshold": threshold, "use_gray": bool(self.image_library_gray.get()),
                      "show_value": bool(self.image_library_show_value.get()), "show_position": True,
                      "show_only_true_rect": False, "ms": 2000,
                      "match_color": self.image_library_match_color.get().strip() or "blue",
                      "no_match_color": self.image_library_no_match_color.get().strip() or "red",
                      "crop": crop}, tags

    def save_image_library_variant(self):
        try:
            name, variant, tags = self._image_variant_fields()
        except ValueError as error:
            messagebox.showwarning("画像検知", str(error), parent=self); return
        data = self._read_image_library()
        target = data["targets"].setdefault(name, {"operator": "OR", "tags": [], "variants": []})
        target["description"] = self.image_library_description.get().strip()
        target["operator"] = self.image_library_target_operator.get()
        target["tags"] = list(dict.fromkeys(target.get("tags", []) + tags))
        target["variants"].append(variant)
        save_image_library(self._image_library_config_path(), data)
        self.refresh_image_library_workspace(select=(name, len(target["variants"]) - 1))

    def overwrite_image_library_variant(self):
        selected = getattr(self, "image_library_selected_variant", None)
        if selected is None:
            messagebox.showinfo("画像検知", "上書きするパターンを選択してください。", parent=self); return
        try:
            name, variant, tags = self._image_variant_fields()
        except ValueError as error:
            messagebox.showwarning("画像検知", str(error), parent=self); return
        old_name, index = selected
        data = self._read_image_library()
        if old_name not in data["targets"] or index >= len(data["targets"][old_name]["variants"]): return
        ignored_warnings = list(
            data["targets"][old_name]["variants"][index].get(
                "health_ignored_warnings", []))
        if ignored_warnings:
            variant["health_ignored_warnings"] = ignored_warnings
        if name != old_name:
            del data["targets"][old_name]["variants"][index]
            if not data["targets"][old_name]["variants"]: del data["targets"][old_name]
            target = data["targets"].setdefault(name, {"operator": "OR", "tags": [], "variants": []})
            target["variants"].append(variant); index = len(target["variants"]) - 1
        else:
            data["targets"][name]["variants"][index] = variant
            target = data["targets"][name]
        target["description"] = self.image_library_description.get().strip()
        target["operator"] = self.image_library_target_operator.get()
        target["tags"] = list(dict.fromkeys(target.get("tags", []) + tags))
        save_image_library(self._image_library_config_path(), data)
        self.refresh_image_library_workspace(select=(name, index))

    def delete_image_library_variant(self):
        selected = getattr(self, "image_library_selected_variant", None)
        if selected is None: return
        name, index = selected
        if not messagebox.askyesno("画像検知", "選択した検知パターンを削除しますか？", parent=self): return
        data = self._read_image_library()
        if name in data["targets"] and index < len(data["targets"][name]["variants"]):
            del data["targets"][name]["variants"][index]
            if not data["targets"][name]["variants"]:
                del data["targets"][name]
                for item in data["lists"].values():
                    item["members"] = [member for member in item["members"] if not (member["type"] == "target" and member["id"] == name)]
            save_image_library(self._image_library_config_path(), data)
        self.image_library_selected_variant = None
        self._clear_image_library_preview()
        self.refresh_image_library_workspace()

    def scan_template_images(self):
        data, template_root, config_path = self._read_image_library(), self.template_root(), self._image_library_config_path()
        def worker():
            added = 0
            known = {variant.get("template_path") for target in data["targets"].values() for variant in target["variants"]}
            for directory, _, names in os.walk(template_root):
                for filename in sorted(names):
                    if os.path.splitext(filename)[1].lower() not in (".png", ".jpg", ".jpeg", ".bmp"): continue
                    absolute = os.path.join(directory, filename)
                    portable = os.path.relpath(absolute, os.path.dirname(template_root)).replace("\\", "/")
                    if portable in known: continue
                    relative = os.path.relpath(absolute, template_root).replace("\\", "/")
                    target_name = os.path.splitext(relative)[0].replace("/", "_").upper()
                    target = data["targets"].setdefault(target_name, {"description": "Templateから自動登録", "operator": "OR", "tags": image_folder_tags(template_root, absolute), "variants": []})
                    target["variants"].append({"template_path": portable, "threshold": 0.8, "use_gray": True,
                                               "show_value": False, "show_position": True, "show_only_true_rect": False,
                                               "ms": 2000, "crop": [0, 0, 0, 0]})
                    known.add(portable); added += 1
            save_image_library(config_path, data)
            return added
        def completed(added):
            self.refresh_image_library_workspace()
            self.status.set("Template画像から{}件の検知設定を追加しました。".format(added))
        self.run_background("scan_template_images", "Template画像を走査中", worker, completed)

    def refresh_image_library_tree(self, select=None):
        if not hasattr(self, "image_library_tree"): return
        self.image_library_tree.delete(*self.image_library_tree.get_children()); self.image_library_tree_ids = {}
        data, needle = self._read_image_library(), self.image_library_search.get().strip()
        visible_variants = set(filter_image_library_variants(
            data, needle, self.image_library_gray_filter.get(),
            self.image_library_excluded_folders.get()))
        root = self.image_library_tree.insert("", "end", text="Template", values=("", "", "", "", ""), open=True)
        folder_nodes, target_nodes = {}, {}
        for name in sorted(data["targets"], key=str.lower):
            item = data["targets"][name]
            for index, variant in enumerate(item["variants"]):
                if (name, index) not in visible_variants: continue
                parts = variant.get("template_path", "").replace("\\", "/").split("/")
                if parts and parts[0].lower() == "template": parts = parts[1:]
                parent, accumulated = root, []
                for folder in parts[:-1]:
                    accumulated.append(folder); key = "/".join(accumulated)
                    if key not in folder_nodes:
                        folder_nodes[key] = self.image_library_tree.insert(parent, "end", text=folder, values=("", "", "", "", folder), open=bool(needle))
                    parent = folder_nodes[key]
                target_key = (parent, name)
                if target_key not in target_nodes:
                    target_nodes[target_key] = self.image_library_tree.insert(parent, "end", text="{} [{}]".format(name, item.get("operator", "OR")),
                        values=(item.get("description", ""), "", "", "", ", ".join(item.get("tags", []))), open=True)
                iid = self.image_library_tree.insert(target_nodes[target_key], "end", text="パターン{}".format(index + 1),
                    values=(variant.get("template_path", ""), variant.get("threshold", 0.8),
                            ",".join(map(str, variant.get("crop", []))),
                            "ON" if variant.get("use_gray", True) else "OFF",
                            ", ".join(item.get("tags", []))))
                self.image_library_tree_ids[iid] = (name, index)
                if select == (name, index): self.image_library_tree.selection_set(iid); self.image_library_tree.see(iid)

    def load_selected_image_library_variant(self, event=None):
        selected = self.image_library_tree.selection()
        if not selected or selected[0] not in self.image_library_tree_ids: return
        name, index = self.image_library_tree_ids[selected[0]]; self.image_library_selected_variant = (name, index)
        data = self._read_image_library()
        variant = data["targets"][name]["variants"][index]
        path = variant.get("template_path", "")
        if path and not os.path.isabs(path): path = os.path.join(os.path.dirname(self.template_root()), path)
        self.image_library_name.set(name); self.image_library_path.set(path)
        target = data["targets"][name]
        self.image_library_description.set(target.get("description", ""))
        self.image_library_target_operator.set(target.get("operator", "OR"))
        self.image_library_threshold.set(variant.get("threshold", 0.8)); self.image_library_crop.set(",".join(map(str, variant.get("crop", [0,0,0,0]))))
        self.image_library_gray.set(bool(variant.get("use_gray", True))); self.image_library_show_value.set(bool(variant.get("show_value", False)))
        self.image_library_match_color.set(variant.get("match_color", "blue"))
        self.image_library_no_match_color.set(variant.get("no_match_color", "red"))
        self._show_image_library_preview(path)

    def refresh_image_library_workspace(self, select=None):
        if not hasattr(self, "image_library_tree"): return
        self.refresh_image_library_tree(select)
        data = self._read_image_library(); selected_list = self.image_library_list_name.get().strip()
        self.image_library_lists.delete(0, "end")
        for name in sorted(data["lists"], key=str.lower):
            item = data["lists"][name]
            self.image_library_lists.insert("end", "{} {}".format(name, item.get("description", "")))
        choices = ["target:" + name for name in sorted(data["targets"])] + ["list:" + name for name in sorted(data["lists"])]
        self.image_library_member_combo.configure(values=choices)
        if choices and self.image_library_member.get() not in choices: self.image_library_member.set(choices[0])
        self.refresh_image_detection_members(selected_list)

    def refresh_image_detection_members(self, name=None):
        self.image_library_members.delete(0, "end"); data = self._read_image_library()
        if name in data["lists"]:
            for member in data["lists"][name]["members"]: self.image_library_members.insert("end", member["type"] + ":" + member["id"])

    def load_image_detection_list(self, event=None):
        selected = self.image_library_lists.curselection()
        if selected:
            data = self._read_image_library(); display = self.image_library_lists.get(selected[0])
            name = next((value for value in sorted(data["lists"]) if display == "{} {}".format(value, data["lists"][value].get("description", ""))), "")
            if not name: return
            item = data["lists"][name]; self.image_library_list_name.set(name)
            self.image_library_list_description.set(item.get("description", ""))
            self.refresh_image_detection_members(name)

    def save_image_detection_list(self):
        name = self.image_library_list_name.get().strip()
        if not name: messagebox.showwarning("画像検知リスト", "リスト名を入力してください。", parent=self); return
        data = self._read_image_library(); existing = data["lists"].get(name, {"members": []})
        existing["description"] = self.image_library_list_description.get().strip()
        data["lists"][name] = existing; save_image_library(self._image_library_config_path(), data); self.refresh_image_library_workspace()

    def delete_image_detection_list(self):
        name = self.image_library_list_name.get().strip(); data = self._read_image_library()
        used = [other for other, item in data["lists"].items() if any(m["type"] == "list" and m["id"] == name for m in item["members"])]
        if used: messagebox.showwarning("画像検知リスト", "次のリストから先に外してください: " + ", ".join(used), parent=self); return
        if name in data["lists"] and messagebox.askyesno("画像検知リスト", "リストを削除しますか？", parent=self):
            del data["lists"][name]; save_image_library(self._image_library_config_path(), data); self.image_library_list_name.set(""); self.refresh_image_library_workspace()

    def add_image_detection_member(self):
        list_name, value = self.image_library_list_name.get().strip(), self.image_library_member.get().strip()
        if not list_name or ":" not in value: return
        member_type, member_id = value.split(":", 1); data = self._read_image_library()
        item = data["lists"].setdefault(list_name, {"description": "", "members": []}); member = {"type": member_type, "id": member_id}
        if member not in item["members"]: item["members"].append(member)
        try: resolve_image_list(data, list_name)
        except ValueError as error:
            item["members"].remove(member); messagebox.showwarning("画像検知リスト", str(error), parent=self); return
        save_image_library(self._image_library_config_path(), data); self.refresh_image_library_workspace()

    def remove_image_detection_member(self):
        selected = self.image_library_members.curselection(); name = self.image_library_list_name.get().strip()
        if not selected: return
        data = self._read_image_library()
        if name in data["lists"] and selected[0] < len(data["lists"][name]["members"]):
            del data["lists"][name]["members"][selected[0]]; save_image_library(self._image_library_config_path(), data); self.refresh_image_library_workspace()

    def _current_image_detection_code(self):
        name = self.image_library_list_name.get().strip(); data = self._read_image_library()
        if name not in data["lists"]: raise ValueError("生成する画像検知リストを選択してください。")
        return generate_image_check(data, name, "list")

    def preview_image_detection_code(self):
        try: code = self._current_image_detection_code()
        except ValueError as error: messagebox.showwarning("画像検知", str(error), parent=self); return
        dialog = tk.Toplevel(self); dialog.title("生成されるimage_check")
        editor_frame = ttk.Frame(dialog)
        editor_frame.pack(fill="both", expand=True)
        editor = tk.Text(editor_frame, wrap="none", background="#1e1e1e", foreground="#d4d4d4")
        pack_scrollable_widget(editor, horizontal=True)
        editor.insert("1.0", code); editor.configure(state="disabled"); dialog.geometry("900x600")

    def apply_image_detection_code(self):
        try:
            code = self._current_image_detection_code()
            data = self._read_image_library()
            list_name = self.image_library_list_name.get().strip()
            selected_names = resolve_image_list(data, list_name)
        except ValueError as error: messagebox.showwarning("画像検知", str(error), parent=self); return
        editor = self.sample_program_editor if self.image_library_apply_target.get() == "サンプルプログラム" else self.editor
        source = editor.get("1.0", "end-1c")
        # A list-specific apply must not rebuild the complete generated block:
        # doing so removes every registration outside the selected list.  Once
        # image_check has been generated, update only the selected registrations.
        if "# POKECON_IMAGE_CHECK_BEGIN" in source:
            try:
                updated, added = merge_library_targets_into_source(
                    source, data, selected_names)
            except (SyntaxError, ValueError) as error:
                messagebox.showwarning("画像検知", str(error), parent=self)
                return
            editor.delete("1.0", "end")
            editor.insert("1.0", updated)
            if editor is self.sample_program_editor:
                self.sample_program_dirty = True
                self._update_sample_program_line_numbers()
            else:
                self.editor_dirty = True
                self.update_editor_view()
            self.status.set(
                "画像検知{}件を追加/更新しました。既存登録は保持しています。保存してください。".format(
                    len(added)))
            return
        if self._apply_image_code_to_editor(editor, code):
            self.status.set("image_checkを生成/更新しました。保存してください。")

    def _extract_image_check_user(self, source):
        pattern = re.compile(r"(?ms)^(?P<indent>[ \t]*)# POKECON_IMAGE_CHECK_USER_BEGIN\n(?P<body>.*?)^\1# POKECON_IMAGE_CHECK_USER_END[ \t]*$")
        match = pattern.search(source)
        return match.group("body") if match else None

    def _replace_image_check_user(self, code, body):
        pattern = re.compile(r"(?ms)^(?P<indent>[ \t]*)# POKECON_IMAGE_CHECK_USER_BEGIN\n.*?^\1# POKECON_IMAGE_CHECK_USER_END[ \t]*$")
        match = pattern.search(code)
        if not match or body is None: return code
        indent = match.group("indent")
        replacement = indent + "# POKECON_IMAGE_CHECK_USER_BEGIN\n" + body + indent + "# POKECON_IMAGE_CHECK_USER_END"
        return code[:match.start()] + replacement + code[match.end():]

    def _apply_image_code_to_editor(self, editor, code):
        source = editor.get("1.0", "end-1c")
        if "class " not in source:
            messagebox.showwarning("画像検知", "先に対象エディタへコマンドを作成または読込してください。", parent=self); return False
        preserved_user = self._extract_image_check_user(source)
        if preserved_user is not None: code = self._replace_image_check_user(code, textwrap.dedent(preserved_user))
        code = preserve_library_import_block(code, source)
        import_line = "from LocalFunction.ImageDetection import SimilarityHistory, detect_image"
        if import_line not in source:
            class_at = source.find("class "); source = source[:class_at] + import_line + "\n\n" + source[class_at:]
        indented = textwrap.indent(code.rstrip(), "    ")
        pattern = re.compile(r"(?ms)^[ \t]*# POKECON_IMAGE_CHECK_BEGIN\n.*?^[ \t]*# POKECON_IMAGE_CHECK_END[ \t]*$")
        if pattern.search(source):
            source = pattern.sub(indented, source, count=1)
        else:
            marker = "    # POKECON_USER_METHODS_BEGIN"
            source = source.replace(marker, indented + "\n\n" + marker, 1) if marker in source else source.rstrip() + "\n\n" + indented + "\n"
        editor.delete("1.0", "end"); editor.insert("1.0", source)
        if editor is self.sample_program_editor:
            self.sample_program_dirty = True; self._update_sample_program_line_numbers()
        else:
            self.editor_dirty = True; self.update_editor_view()
        return True

    def load_image_detection_from_source(self):
        editor = self.sample_program_editor if self.image_library_apply_target.get() == "サンプルプログラム" else self.editor
        source = editor.get("1.0", "end-1c")
        try:
            tree = ast.parse(source)
            assignments = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if getattr(target, "id", "").startswith("IMAGE_DETECTION_"):
                            assignments[target.id] = node.value
            targets = ast.literal_eval(assignments["IMAGE_DETECTION_TARGETS"])
            if not isinstance(targets, dict): raise ValueError
        except (SyntaxError, StopIteration, ValueError, TypeError):
            messagebox.showwarning("画像検知", "対象ソースにリテラル形式のIMAGE_DETECTION_TARGETSがありません。", parent=self); return
        try: operators = ast.literal_eval(assignments.get("IMAGE_DETECTION_OPERATORS")) if "IMAGE_DETECTION_OPERATORS" in assignments else {}
        except (ValueError, TypeError): operators = {}
        try: descriptions = ast.literal_eval(assignments.get("IMAGE_DETECTION_DESCRIPTIONS")) if "IMAGE_DETECTION_DESCRIPTIONS" in assignments else {}
        except (ValueError, TypeError): descriptions = {}
        data = self._read_image_library(); imported = 0; updated_targets = 0; first = None
        for name, variants in targets.items():
            if not isinstance(variants, list): continue
            target = data["targets"].setdefault(str(name), {"operator": "OR", "tags": [], "variants": []})
            before = (target.get("description", ""), target.get("operator", "OR"), list(target.get("variants", [])))
            target["description"] = str(descriptions.get("targets", {}).get(str(name), target.get("description", "")))
            target["operator"] = str(operators.get(str(name), target.get("operator", "OR"))).upper()
            new_variants = [dict(variant) for variant in variants if isinstance(variant, dict)]
            target["variants"] = new_variants
            if before != (target["description"], target["operator"], target["variants"]): updated_targets += 1
            imported += len(new_variants)
            for variant in new_variants:
                raw_path = variant.get("template_path", "")
                absolute = raw_path if os.path.isabs(raw_path) else os.path.join(os.path.dirname(self.template_root()), raw_path)
                target["tags"] = list(dict.fromkeys(target.get("tags", []) + image_folder_tags(self.template_root(), absolute)))
                if first is None: first = (str(name), target["variants"].index(variant))
        save_image_library(self._image_library_config_path(), data)
        self.refresh_image_library_workspace(select=first)
        if first: self.load_selected_image_library_variant()
        self.status.set("ソースから画像検知{}件・{}パターンを登録設定へ更新しました。".format(updated_targets, imported))

    def _image_target_from_fields(self):
        try:
            roi = tuple(int(part.strip()) for part in self.image_target_roi.get().split(","))
            resolution = tuple(int(part.strip()) for part in self.image_target_resolution.get().split(","))
            threshold = float(self.image_target_threshold.get())
            if len(roi) != 4 or len(resolution) != 2 or min(roi) < 0 or min(resolution) < 0 or not 0.0 <= threshold <= 1.0:
                raise ValueError
        except (ValueError, tk.TclError):
            raise ValueError("ROI must be x,y,w,h; reference resolution must be w,h; threshold is 0.00 to 1.00.")
        path = self.image_target_path.get().strip()
        if not path or not os.path.isfile(path):
            raise ValueError("Select an existing image file.")
        return {"name": self.image_target_name.get().strip() or os.path.basename(path), "description": self.image_target_description.get().strip(), "path": path, "threshold": threshold,
                "roi": roi, "grayscale": bool(self.image_target_gray.get()), "reference_resolution": resolution}

    def refresh_image_target_tree(self, selected=None):
        self.image_target_tree.delete(*self.image_target_tree.get_children())
        for index, item in enumerate(self.image_detection_targets):
            self.image_target_tree.insert("", "end", iid=str(index), values=(item["name"], item.get("description", ""), item["path"], item["threshold"],
                ",".join(str(value) for value in item["roi"]), "mono" if item.get("grayscale") else "color",
                ",".join(str(value) for value in item.get("reference_resolution", (0, 0)))))
        if selected is not None and 0 <= selected < len(self.image_detection_targets):
            self.image_target_tree.selection_set(str(selected))

    def add_image_target(self):
        try:
            self.image_detection_targets.append(self._image_target_from_fields())
        except ValueError as error:
            messagebox.showwarning("Image target", str(error), parent=self)
            return
        self.refresh_image_target_tree(len(self.image_detection_targets) - 1)

    def change_image_target(self):
        selected = self.image_target_tree.selection()
        if not selected:
            messagebox.showinfo("Image target", "Select a target to change.", parent=self)
            return
        try:
            index = int(selected[0])
            self.image_detection_targets[index] = self._image_target_from_fields()
        except ValueError as error:
            messagebox.showwarning("Image target", str(error), parent=self)
            return
        self.refresh_image_target_tree(index)

    def remove_image_target(self):
        selected = self.image_target_tree.selection()
        if selected:
            del self.image_detection_targets[int(selected[0])]
            self.refresh_image_target_tree()
            self.image_target_edit_mode.set("新規追加モード")

    def load_selected_image_target(self, event=None):
        selected = self.image_target_tree.selection()
        if not selected:
            return
        item = self.image_detection_targets[int(selected[0])]
        self.image_target_name.set(item["name"]); self.image_target_path.set(item["path"]); self.image_target_threshold.set(item["threshold"])
        self.image_target_description.set(item.get("description", ""))
        self.image_target_roi.set(",".join(str(value) for value in item["roi"])); self.image_target_gray.set(bool(item.get("grayscale")))
        self.image_target_resolution.set(",".join(str(value) for value in item.get("reference_resolution", (0, 0))))
        self.image_target_edit_mode.set("変更モード: {}".format(item["name"]))

    def enter_selected_image_target_change_mode(self, event=None):
        self.load_selected_image_target()
        self.after_idle(lambda: self.image_target_name.set(self.image_target_name.get()))

    def _debug_target_to_library_variant(self, item):
        x, y, width, height = [int(value) for value in item.get("roi", (0, 0, 0, 0))]
        crop = [x, y, x + width, y + height] if width and height else [0, 0, 0, 0]
        return {
            "template_path": self._portable_template_path(item["path"]),
            "threshold": float(item.get("threshold", 0.8)),
            "use_gray": bool(item.get("grayscale", False)),
            "show_value": False,
            "show_position": True,
            "show_only_true_rect": False,
            "ms": 2000,
            "crop": crop,
        }

    def _library_variant_to_debug_target(self, name, variant):
        raw_path = variant.get("template_path", "")
        path = raw_path if os.path.isabs(raw_path) else os.path.join(os.path.dirname(self.template_root()), raw_path)
        x1, y1, x2, y2 = [int(value) for value in variant.get("crop", [0, 0, 0, 0])]
        roi = (x1, y1, max(0, x2 - x1), max(0, y2 - y1)) if any((x1, y1, x2, y2)) else (0, 0, 0, 0)
        return {"name": str(name), "description": "", "path": os.path.abspath(path), "threshold": float(variant.get("threshold", 0.8)),
                "roi": roi, "grayscale": bool(variant.get("use_gray", True)), "reference_resolution": (0, 0)}

    def register_current_image_target(self):
        try:
            debug_target = self._image_target_from_fields()
        except ValueError as error:
            messagebox.showwarning("単品画像検知の登録", str(error), parent=self); return
        name = str(debug_target["name"]); variant = self._debug_target_to_library_variant(debug_target)
        data = self._read_image_library(); item = data["targets"].setdefault(name, {"operator": "OR", "tags": [], "variants": []})
        item["description"] = debug_target.get("description", "")
        tags = image_folder_tags(self.template_root(), debug_target["path"])
        item["tags"] = list(dict.fromkeys(item.get("tags", []) + tags))
        if variant not in item["variants"]: item["variants"].append(variant)
        single_list = "単品_" + name
        data["lists"].setdefault(single_list, {"description": debug_target.get("description", ""), "members": [{"type": "target", "id": name}]})
        save_image_library(self._image_library_config_path(), data)
        self.refresh_image_library_workspace(select=(name, item["variants"].index(variant)))
        self.refresh_sample_apply_image_tree()
        self.status.set("登録済み単品画像検知として保存しました: {}（リスト: {}）".format(name, single_list))

    def open_registered_image_target_dialog(self):
        dialog = tk.Toplevel(self); dialog.title("登録済み画像検知から追加・削除")
        dialog.geometry("920x620"); dialog.transient(self)
        search = tk.StringVar(); ttk.Label(dialog, text="名前・タグ・フォルダ検索:").pack(anchor="w", padx=7, pady=(7, 2))
        ttk.Entry(dialog, textvariable=search).pack(fill="x", padx=7)
        frame = ttk.Frame(dialog); frame.pack(fill="both", expand=True, padx=7, pady=6)
        tree = ttk.Treeview(frame, columns=("path", "threshold", "crop"), show="tree headings", selectmode="extended")
        tree.heading("#0", text="フォルダ / 登録名 / パターン"); tree.heading("path", text="画像")
        tree.heading("threshold", text="閾値"); tree.heading("crop", text="検知範囲")
        tree.column("path", width=410); tree.column("threshold", width=70); tree.column("crop", width=140)
        pack_scrollable_widget(tree, horizontal=True)
        nodes = {}

        def populate(*args):
            tree.delete(*tree.get_children()); nodes.clear(); data = self._read_image_library(); needle = search.get().strip().lower()
            root = tree.insert("", "end", text="Template", open=True); folders, targets = {}, {}
            for name in sorted(data["targets"], key=str.lower):
                item = data["targets"][name]
                text = " ".join([name, item.get("description", "")] + item.get("tags", []) + [v.get("template_path", "") for v in item["variants"]]).lower()
                if needle and needle not in text: continue
                for index, variant in enumerate(item["variants"]):
                    parts = variant.get("template_path", "").replace("\\", "/").split("/")
                    if parts and parts[0].lower() == "template": parts = parts[1:]
                    parent, accumulated = root, []
                    for folder in parts[:-1]:
                        accumulated.append(folder); key = "/".join(accumulated)
                        if key not in folders: folders[key] = tree.insert(parent, "end", text=folder, open=bool(needle))
                        parent = folders[key]
                    target_key = (parent, name)
                    if target_key not in targets: targets[target_key] = tree.insert(parent, "end", text="登録済み: {} / {}".format(name, item.get("description", "")), open=True)
                    iid = tree.insert(targets[target_key], "end", text="パターン{}".format(index + 1),
                        values=(variant.get("template_path", ""), variant.get("threshold", 0.8), ",".join(map(str, variant.get("crop", [])))))
                    nodes[iid] = (name, index)
        search.trace_add("write", populate); populate()

        def chosen(): return [nodes[iid] for iid in tree.selection() if iid in nodes]
        def add_to_source_targets():
            data = self._read_image_library(); added = 0
            for name, index in chosen():
                target = self._library_variant_to_debug_target(name, data["targets"][name]["variants"][index])
                target["description"] = data["targets"][name].get("description", "")
                if target not in self.image_detection_targets: self.image_detection_targets.append(target); added += 1
            self.refresh_image_target_tree(len(self.image_detection_targets) - 1 if added else None)
            self.status.set("登録済み画像検知をソース対象へ{}件追加しました。".format(added))
        def remove_from_source_targets():
            data = self._read_image_library(); selected_targets = []
            for n, i in chosen():
                target = self._library_variant_to_debug_target(n, data["targets"][n]["variants"][i])
                target["description"] = data["targets"][n].get("description", "")
                selected_targets.append(target)
            before = len(self.image_detection_targets)
            self.image_detection_targets = [item for item in self.image_detection_targets if item not in selected_targets]
            self.refresh_image_target_tree(); self.image_target_edit_mode.set("新規追加モード")
            self.status.set("ソース対象から{}件外しました。登録済み設定は削除していません。".format(before - len(self.image_detection_targets)))
        def apply_as_image_check():
            selections = chosen()
            if not selections: return
            data = self._read_image_library(); names = []
            for name, _ in selections:
                if name not in names: names.append(name)
            temporary = {"schema_version": 1, "targets": data["targets"],
                         "lists": {"RegisteredSelection": {"description": "登録済み選択", "members": [{"type": "target", "id": name} for name in names]}}}
            if self._apply_image_code_to_editor(self.editor, generate_image_check(temporary, "RegisteredSelection", "list")):
                self.status.set("登録済み画像検知{}件をimage_checkへ反映しました。".format(len(names)))
        def delete_registration():
            selections = chosen()
            if not selections or not messagebox.askyesno("登録そのものを削除", "選択パターンを登録ライブラリから削除しますか？", parent=dialog): return
            data = self._read_image_library()
            for name, index in sorted(selections, key=lambda value: (value[0], -value[1])):
                if name in data["targets"] and index < len(data["targets"][name]["variants"]): del data["targets"][name]["variants"][index]
                if name in data["targets"] and not data["targets"][name]["variants"]:
                    del data["targets"][name]
                    for item in data["lists"].values(): item["members"] = [m for m in item["members"] if not (m["type"] == "target" and m["id"] == name)]
            save_image_library(self._image_library_config_path(), data); populate(); self.refresh_image_library_workspace(); self.refresh_sample_apply_image_tree()
        buttons = ttk.Frame(dialog); buttons.pack(fill="x", padx=7, pady=(0, 7))
        ttk.Button(buttons, text="ソース対象へ追加", command=add_to_source_targets).pack(side="left", padx=2)
        ttk.Button(buttons, text="ソース対象から外す", command=remove_from_source_targets).pack(side="left", padx=2)
        ttk.Button(buttons, text="image_checkへ反映", command=apply_as_image_check).pack(side="left", padx=10)
        ttk.Button(buttons, text="登録そのものを削除", command=delete_registration).pack(side="right", padx=2)

    def load_image_targets_from_editor(self):
        try:
            tree = ast.parse(self.editor.get("1.0", "end-1c"))
            method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "get_detection_targets")
            returned = next(node.value for node in method.body if isinstance(node, ast.Return))
            values = ast.literal_eval(returned)
            if not isinstance(values, list):
                raise ValueError
            self.image_detection_targets = values
        except (SyntaxError, StopIteration, ValueError, TypeError):
            messagebox.showwarning("Image targets", "The current source must contain get_detection_targets() returning a literal list.", parent=self)
            return
        self.refresh_image_target_tree()
        self.status.set("Loaded {} image target(s) from current command".format(len(self.image_detection_targets)))

    def apply_image_targets_to_editor(self):
        source = self.editor.get("1.0", "end-1c")
        try:
            tree = ast.parse(source)
            method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "get_detection_targets")
            returned = next(node for node in method.body if isinstance(node, ast.Return))
        except (SyntaxError, StopIteration):
            messagebox.showwarning("Image targets", "Open a generated command that contains get_detection_targets() first.", parent=self)
            return
        lines = source.splitlines(True)
        indent = re.match(r"\s*", lines[returned.lineno - 1]).group(0)
        # Python 3.7's AST has no end_lineno; generated targets intentionally
        # use one return line so replacing that line is compatible with it.
        lines[returned.lineno - 1:returned.lineno] = [indent + "return " + repr(self.image_detection_targets) + "\n"]
        self.set_editor_content("".join(lines), self.current_path)
        self.editor_dirty = True
        self.update_editor_view()
        self.status.set("Applied {} image target(s). Save the command to keep them.".format(len(self.image_detection_targets)))

    def _editor_tab_label(self, document):
        name = os.path.basename(document["path"]) if document["path"] else "Untitled"
        return ("● " if document["dirty"] else "") + name

    def capture_active_editor_document(self):
        if self.active_editor_tab and self.active_editor_tab in self.editor_documents:
            document = self.editor_documents[self.active_editor_tab]
            document["content"] = self.editor.get("1.0", "end-1c")
            document["dirty"] = self.editor_dirty
            self.editor_tabs.tab(self.active_editor_tab, text=self._editor_tab_label(document))

    def add_editor_document(self, content, path, line=1):
        frame = ttk.Frame(self.editor_tabs)
        document = {"path": path, "content": content, "dirty": False, "line": line}
        self.editor_tabs.add(frame, text=self._editor_tab_label(document))
        tab_id = self.editor_tabs.tabs()[-1]
        self.editor_documents[tab_id] = document
        self._switching_editor_tab = True
        self.editor_tabs.select(tab_id)
        self._switching_editor_tab = False
        self.load_editor_document(tab_id, line)
        return tab_id

    def load_editor_document(self, tab_id, line=None):
        self.hide_completion_popup()
        if hasattr(self, "todo_editor"):
            self.save_current_todo(silent=True)
        document = self.editor_documents[tab_id]
        self.active_editor_tab = tab_id
        self.current_path = document["path"]
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", document["content"])
        target_line = line if line is not None else document.get("line", 1)
        self.editor.mark_set("insert", "{}.0".format(target_line))
        self.editor.see("{}.0".format(target_line))
        self.editor_dirty = document["dirty"]
        self.editor.edit_modified(False)
        self.update_editor_view()
        self.load_current_todo()
        if self.find_text.get():
            self.debounce("editor_find_count", 120, self.refresh_find_count)
        if (self.completion_mode.get() == "右タブ" and
                hasattr(self, "completion_tab") and
                self.right_tabs.select() == str(self.completion_tab)):
            self.debounce("editor_completion_tab", 80, self.refresh_completion)
        if hasattr(self, "source_functions_tab") and \
                self.right_tabs.select() == str(self.source_functions_tab):
            self.debounce("source_function_editor_tab", 80, self.refresh_source_functions)
        if hasattr(self, "image_reference_tab"):
            self.debounce(
                "image_reference_open", 350,
                lambda: self.run_image_reference_check(silent=True))

    def todo_storage_path(self):
        return os.path.join(os.path.dirname(__file__), "source_todos.json")

    def _read_source_todos(self):
        try:
            with open(self.todo_storage_path(), "r", encoding="utf-8") as stream:
                value = json.load(stream)
                return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def load_current_todo(self):
        if not hasattr(self, "todo_editor"):
            return
        self._loading_todo = True
        self.todo_editor.configure(state="normal")
        self.todo_editor.delete("1.0", "end")
        if self.current_path:
            key = os.path.normcase(os.path.abspath(self.current_path))
            value = self._read_source_todos().get(key, "")
            if TODO_HELP_MARKER not in value:
                value = TODO_HELP_TEXT + value.lstrip("\n")
            elif TODO_SIMPLE_FUNCTION_HELP.strip() not in value:
                value = TODO_SIMPLE_FUNCTION_HELP + value
            if TODO_PLAIN_FUNCTION_HELP.strip() not in value:
                value = TODO_PLAIN_FUNCTION_HELP + value
            self.todo_editor.insert("1.0", value)
            self.todo_source_label.set(os.path.basename(self.current_path) + " のTODO")
        else:
            self.todo_source_label.set("保存済みソースを開くとTODOを記録できます。")
            self.todo_editor.configure(state="disabled")
        self.todo_editor.edit_modified(False)
        self._loading_todo = False

    def save_current_todo(self, silent=False):
        if not hasattr(self, "todo_editor") or not self.current_path:
            return False
        job = getattr(self, "_todo_save_job", None)
        if job is not None:
            try: self.after_cancel(job)
            except tk.TclError: pass
            self._todo_save_job = None
        data = self._read_source_todos()
        key = os.path.normcase(os.path.abspath(self.current_path))
        value = self.todo_editor.get("1.0", "end-1c").rstrip()
        if value:
            data[key] = value + "\n"
        else:
            data.pop(key, None)
        path, temporary = self.todo_storage_path(), self.todo_storage_path() + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary, path)
        except OSError as error:
            if not silent: messagebox.showerror("TODO", str(error), parent=self)
            return False
        self.todo_editor.edit_modified(False)
        if not silent: self.status.set("TODOを保存しました: " + os.path.basename(self.current_path))
        return True

    def todo_modified(self, event=None):
        if getattr(self, "_loading_todo", False) or not self.todo_editor.edit_modified():
            return
        self.todo_editor.edit_modified(False)
        job = getattr(self, "_todo_save_job", None)
        if job is not None:
            try: self.after_cancel(job)
            except tk.TclError: pass
        self._todo_save_job = self.after(700, lambda: self.save_current_todo(silent=True))

    def insert_todo_item(self):
        if not self.current_path:
            messagebox.showinfo("TODO", "先にソースファイルを保存してください。", parent=self); return
        self.todo_editor.configure(state="normal")
        current = self.todo_editor.get("1.0", "end-1c")
        self.todo_editor.insert("end", ("" if not current or current.endswith("\n") else "\n") + "- [ ] ")
        self.todo_editor.focus_set()

    @staticmethod
    def bind_text_undo_redo(widget):
        """Give every editor an explicit, symmetric undo/redo shortcut."""
        def run(action):
            try:
                getattr(widget, action)()
            except tk.TclError:
                pass
            return "break"
        widget.bind("<Control-z>", lambda event: run("edit_undo"))
        widget.bind("<Control-Z>", lambda event: run("edit_undo"))
        widget.bind("<Control-y>", lambda event: run("edit_redo"))
        widget.bind("<Control-Y>", lambda event: run("edit_redo"))
        widget.bind("<Control-Shift-z>", lambda event: run("edit_redo"))
        widget.bind("<Control-Shift-Z>", lambda event: run("edit_redo"))

    @staticmethod
    def _source_function_locations(source):
        """Return qualified function names and their current source ranges."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        found = []

        def visit(nodes, parents=()):
            for node in nodes:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualified = ".".join(parents + (node.name,))
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        found.append((qualified, node.lineno,
                                      getattr(node, "end_lineno", node.lineno)))
                    visit(node.body, parents + (node.name,))
        visit(tree.body)
        return found

    def _resolve_source_function(self, displayed_name):
        """Resolve a function name or an upper-case state/log label."""
        name = displayed_name.strip()
        source = self.editor.get("1.0", "end-1c")
        functions = self._source_function_locations(source)
        candidates = (name, name.lower(), "_" + name.lower().lstrip("_"))
        for candidate in candidates:
            target = next((item for item in functions
                           if item[0] == candidate or item[0].rsplit(".", 1)[-1] == candidate), None)
            if target:
                return target
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                try:
                    key_value = ast.literal_eval(key)
                except (ValueError, TypeError, SyntaxError):
                    continue
                if str(key_value).upper() != name.upper():
                    continue
                if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name) and value.value.id == "self":
                    return next((item for item in functions
                                 if item[0].rsplit(".", 1)[-1] == value.attr), None)
        return None

    def insert_linked_todo_item(self):
        if not self.current_path:
            messagebox.showinfo("TODO", "先にソースファイルを保存してください。", parent=self); return
        try:
            source_index = self.editor.index("sel.first")
            selected = self.editor.get("sel.first", "sel.last").strip()
        except tk.TclError:
            source_index = self.editor.index("insert"); selected = ""
        line = int(source_index.split(".")[0])
        functions = self._source_function_locations(self.editor.get("1.0", "end-1c"))
        containing = [item for item in functions if item[1] <= line <= item[2]]
        function = min(containing, key=lambda item: item[2] - item[1]) if containing else None
        hint = next((value.strip() for value in selected.splitlines() if value.strip()), "")[:100]
        self.todo_editor.configure(state="normal")
        current = self.todo_editor.get("1.0", "end-1c")
        prefix = "" if not current or current.endswith("\n") else "\n"
        if function:
            anchor = "[F:{}+{}] [L{}]".format(function[0], line - function[1], line)
        else:
            anchor = "[L{}]".format(line)
        self.todo_editor.insert("end", prefix + "- [ ] {} {}".format(anchor, hint))
        self.todo_editor.focus_set(); self.todo_editor.see("end")

    def open_todo_source_location(self, event=None):
        try:
            index = self.todo_editor.index("@{},{}".format(event.x, event.y)) if event is not None else self.todo_editor.index("insert")
            text = self.todo_editor.get("{}.0".format(index.split(".")[0]), "{}.end".format(index.split(".")[0]))
        except tk.TclError:
            return
        function_match = re.search(r"\[F:([\w.]+)\+(\d+)\]", text)
        line_match = re.search(r"\[L(\d+)\]", text)
        simple_function_match = re.search(r"\[([A-Za-z_]\w*)\]", text)
        if simple_function_match and (simple_function_match.group(1).lower() == "x" or
                                      re.fullmatch(r"L\d+", simple_function_match.group(1))):
            simple_function_match = None
        functions = self._source_function_locations(self.editor.get("1.0", "end-1c"))
        plain_function = None
        if not function_match and not simple_function_match:
            words = {word.lower().lstrip("_") for word in re.findall(r"[A-Za-z0-9_]+", text)}
            plain_function = next((item for item in functions
                                   if item[0].rsplit(".", 1)[-1].lower().lstrip("_") in words), None)
        if not function_match and not line_match and not simple_function_match and not plain_function:
            return
        line = max(1, int(line_match.group(1))) if line_match else 1
        if function_match:
            qualified_name, offset = function_match.group(1), int(function_match.group(2))
            target = next((item for item in functions if item[0] == qualified_name), None)
            if target:
                line = min(target[2], target[1] + offset)
            else:
                self.status.set("紐づけ先の関数が見つからないため、保存時の行番号を開きます: " + qualified_name)
        elif simple_function_match:
            function_name = simple_function_match.group(1)
            target = next((item for item in functions
                           if item[0] == function_name or item[0].rsplit(".", 1)[-1] == function_name), None)
            if not target:
                self.status.set("紐づけ先の関数が見つかりません: " + function_name)
                return
            line = target[1]
        elif plain_function:
            line = plain_function[1]
        self.editor.mark_set("insert", "{}.0".format(line)); self.editor.see("{}.0".format(line))
        self.editor.tag_remove("sel", "1.0", "end")
        self.editor.tag_add("sel", "{}.0".format(line), "{}.end".format(line))
        self.editor.focus_set(); self.status.set("TODOの紐づけ先を開きました: {} 行{}".format(os.path.basename(self.current_path), line))

    @staticmethod
    def find_vscode_executable():
        local = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", "")
        candidates = [
            os.path.join(local, "Programs", "Microsoft VS Code", "Code.exe") if local else "",
            os.path.join(program_files, "Microsoft VS Code", "Code.exe") if program_files else "",
            shutil.which("code.exe") or "",
            shutil.which("code") or "",
        ]
        return next((path for path in candidates if path and os.path.isfile(path)), None)

    def open_current_in_vscode(self):
        if not self.current_path:
            messagebox.showinfo("VS Code", "先にソースファイルを保存してください。", parent=self); return
        line = int(self.editor.index("insert").split(".")[0])
        if self._open_path_in_vscode(self.current_path, line):
            self.status.set("VS Codeで開きました: {} 行{}".format(
                os.path.basename(self.current_path), line))

    def _open_path_in_vscode(self, path, line=1):
        executable = self.vscode_executable or self.find_vscode_executable()
        if not executable:
            messagebox.showwarning("VS Code", "VS Codeが見つかりません。", parent=self); return
        target = "{}:{}".format(os.path.abspath(path), max(1, int(line)))
        try:
            if executable.lower().endswith((".cmd", ".bat")):
                command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", executable, "--goto", target]
                subprocess.Popen(command, creationflags=0x08000000)
            else:
                subprocess.Popen([executable, "--goto", target])
        except OSError as error:
            messagebox.showerror("VS Code", str(error), parent=self)
            return False
        return True

    def open_fragment_in_vscode(self):
        if not self.editing_fragment_id:
            messagebox.showinfo(
                "VS Code", "先に登録済みサンプル関数を変更画面で開いてください。",
                parent=self)
            return
        try:
            _, _, _, body_path = load_fragment(
                self.fragment_root(), self.editing_fragment_id)
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("VS Code", str(error), parent=self)
            return
        current = self.fragment_body.get("1.0", "end-1c")
        if current != self._fragment_loaded_body and not messagebox.askyesno(
                "VS Code",
                "DevStudio側に未保存の変更があります。\n"
                "VS Codeでは最後に保存した内容を開きます。\n\nそれでも開きますか？",
                parent=self):
            return
        line = int(self.fragment_body.index("insert").split(".")[0])
        if self._open_path_in_vscode(body_path, line):
            self.status.set(
                "VS Codeでサンプル関数を開きました。保存後は「外部変更を再読込」を押してください: {}".format(
                    os.path.basename(body_path)))

    def reload_fragment_external_changes(self):
        if not self.editing_fragment_id:
            messagebox.showinfo(
                "外部変更を再読込",
                "先に登録済みサンプル関数を変更画面で開いてください。",
                parent=self)
            return
        current = self.fragment_body.get("1.0", "end-1c")
        if current != self._fragment_loaded_body and not messagebox.askyesno(
                "外部変更を再読込",
                "DevStudio側の未保存変更を破棄して、外部エディタの内容を再読込しますか？",
                parent=self):
            return
        fragment_id = self.editing_fragment_id
        self.load_fragment_for_editing(fragment_id)
        self.status.set("VS Code等の外部変更を再読込しました。")

    def on_editor_tab_changed(self, event=None):
        if self._switching_editor_tab:
            return
        selected = self.editor_tabs.select()
        if selected and selected != self.active_editor_tab:
            self.capture_active_editor_document()
            self.load_editor_document(selected)

    def close_current_editor_tab(self):
        tab_id = self.active_editor_tab
        if not tab_id:
            return
        self.capture_active_editor_document()
        document = self.editor_documents[tab_id]
        if document["dirty"]:
            answer = messagebox.askyesnocancel("Close source", "This source has unsaved changes. Save before closing?", parent=self)
            if answer is None:
                return
            if answer and not self.save_current():
                return
        self.editor_tabs.forget(tab_id)
        del self.editor_documents[tab_id]
        self.active_editor_tab = None
        tabs = self.editor_tabs.tabs()
        if tabs:
            self.editor_tabs.select(tabs[-1])
            self.load_editor_document(tabs[-1])
        else:
            self.add_editor_document("", None)

    def close_all_editor_tabs(self):
        for tab_id in list(self.editor_tabs.tabs()):
            self.editor_tabs.select(tab_id)
            self.load_editor_document(tab_id)
            self.close_current_editor_tab()
            # Cancel leaves the selected document open and stops the operation.
            if tab_id in self.editor_documents:
                return

    def _scroll_editor(self, *args):
        self.editor.yview(*args)
        self.line_numbers.yview(*args)

    def _sync_editor_scroll(self, scrollbar, first, last):
        scrollbar.set(first, last)
        self.line_numbers.yview_moveto(first)
        self._schedule_python_highlight()

    def editor_modified(self, event=None):
        if self.editor.edit_modified():
            self.editor_dirty = True
            if self.active_editor_tab in self.editor_documents:
                self.editor_documents[self.active_editor_tab]["dirty"] = True
            self.editor.edit_modified(False)
            self.update_editor_view()
            if self.find_text.get():
                self.debounce("editor_find_count", 120, self.refresh_find_count)
            if hasattr(self, "image_reference_tab") and \
                    self.right_tabs.select() == str(self.image_reference_tab):
                self.debounce(
                    "image_reference_edit", 650,
                    lambda: self.run_image_reference_check(silent=True))

    def update_editor_view(self):
        title = self.current_path or "Unsaved output"
        self.editor_title.set(("* " if self.editor_dirty else "") + title)
        if self.active_editor_tab in self.editor_documents:
            document = self.editor_documents[self.active_editor_tab]
            document["dirty"] = self.editor_dirty
            self.editor_tabs.tab(self.active_editor_tab, text=self._editor_tab_label(document))
        self._schedule_editor_decorations()

    def _schedule_editor_decorations(self):
        """Keep file opening responsive by decorating the editor after it is visible."""
        job = getattr(self, "_editor_decorations_job", None)
        if job is not None:
            try: self.after_cancel(job)
            except tk.TclError: pass
        self._editor_decorations_job = self.after(120, self._refresh_editor_decorations)

    def _refresh_editor_decorations(self):
        self._editor_decorations_job = None
        count = max(1, int(self.editor.index("end-1c").split(".")[0]))
        if count != getattr(self, "_line_number_count", None):
            self.line_numbers.configure(state="normal")
            self.line_numbers.delete("1.0", "end")
            self.line_numbers.insert("1.0", "\n".join(str(number) for number in range(1, count + 1)))
            self.line_numbers.configure(state="disabled")
            self._line_number_count = count
        self._highlight_python()

    def _schedule_python_highlight(self):
        job = getattr(self, "_python_highlight_job", None)
        if job is not None:
            try: self.after_cancel(job)
            except tk.TclError: pass
        self._python_highlight_job = self.after(80, self._run_scheduled_python_highlight)

    def _run_scheduled_python_highlight(self):
        self._python_highlight_job = None
        self._highlight_python()

    def _highlight_python(self):
        # Highlight only the visible area plus a margin. Full-file regex/tagging
        # made opening large command sources unnecessarily expensive.
        try:
            first_line = max(1, int(self.editor.index("@0,0").split(".")[0]) - 100)
            height = max(1, self.editor.winfo_height())
            last_line = int(self.editor.index("@0,{}".format(height)).split(".")[0]) + 100
        except (ValueError, tk.TclError):
            first_line, last_line = 1, 300
        start, end = "{}.0".format(first_line), "{}.0".format(last_line + 1)
        text = self.editor.get(start, end)
        for tag in ("keyword", "string", "comment"):
            self.editor.tag_remove(tag, "1.0", "end")
        for match in re.finditer(r"#.*$", text, re.MULTILINE):
            self.editor.tag_add("comment", "{}+{}c".format(start, match.start()), "{}+{}c".format(start, match.end()))
        for match in re.finditer(r"(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")", text):
            self.editor.tag_add("string", "{}+{}c".format(start, match.start()), "{}+{}c".format(start, match.end()))
        keywords = r"\b(?:and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield)\b"
        for match in re.finditer(keywords, text):
            self.editor.tag_add("keyword", "{}+{}c".format(start, match.start()), "{}+{}c".format(start, match.end()))

    def set_editor_content(self, content, path=None, line=1):
        self.capture_active_editor_document()
        for tab_id, document in self.editor_documents.items():
            if path and document["path"] == path:
                document.update({"content": content, "dirty": False, "line": line})
                self._switching_editor_tab = True
                self.editor_tabs.select(tab_id)
                self._switching_editor_tab = False
                self.load_editor_document(tab_id, line)
                return
        self.add_editor_document(content, path, line)

    def new_file(self):
        self.capture_active_editor_document()
        self.add_editor_document("", None)
        self.status.set("New unsaved Python file")

    def save_current(self):
        if not self.current_path:
            return self.save_output()
        return self._write_editor(self.current_path)

    def _write_editor(self, path):
        self.save_current_todo(silent=True)
        original = self.editor.get("1.0", "end-1c")
        try:
            source = normalize_and_compile_python(original, path)
        except SyntaxError as error:
            messagebox.showerror(
                "Save",
                "Python?????????????????\n"
                "? {}: {}".format(
                    getattr(error, "lineno", "?"),
                    getattr(error, "msg", str(error))))
            if getattr(error, "lineno", None):
                self.editor.mark_set("insert", "{}.0".format(error.lineno))
                self.editor.see("{}.0".format(error.lineno))
            return False
        if source != original:
            cursor = self.editor.index("insert")
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", source)
            self.editor.mark_set("insert", cursor)
            self.status.set("??Tab???????4??????????")
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(source)
        except OSError as error:
            messagebox.showerror("Save", str(error))
            return False
        self.current_path = path
        self.editor_dirty = False
        self.editor.edit_modified(False)
        if self.active_editor_tab in self.editor_documents:
            document = self.editor_documents[self.active_editor_tab]
            document.update({"path": path, "content": source, "dirty": False})
        self.update_editor_view()
        self.load_current_todo()
        self.status.set("Saved " + path)
        self.refresh_index()
        return True

    def go_to_line(self):
        dialog = tk.Toplevel(self)
        dialog.title("Go to line")
        dialog.transient(self)
        ttk.Label(dialog, text="Line number:").grid(column=0, row=0, padx=8, pady=8)
        number = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=number, width=10)
        entry.grid(column=1, row=0, padx=4, pady=8)
        def apply_line(event=None):
            try:
                line = max(1, int(number.get()))
            except ValueError:
                return
            self.editor.mark_set("insert", "{}.0".format(line))
            self.editor.see("{}.0".format(line))
            self.editor.focus_set()
            dialog.destroy()
        ttk.Button(dialog, text="Go", command=apply_line).grid(column=2, row=0, padx=8, pady=8)
        entry.bind("<Return>", apply_line)
        entry.focus_set()

    def _register_find_editor(self, editor, label, replace=True):
        self._find_editors[editor] = {
            "label": str(label), "replace": bool(replace)}
        editor.bind(
            "<FocusIn>",
            lambda _event, widget=editor: self._select_find_editor(widget),
            add="+")
        if self._find_target_editor is None:
            self._find_target_editor = editor

    def _select_find_editor(self, editor):
        if editor not in self._find_editors:
            return
        self._find_target_editor = editor
        self.find_target_text.set(
            "対象: " + self._find_editors[editor]["label"])
        if self.find_text.get():
            self.debounce(
                "editor_find_count", 50, self.refresh_find_count)

    def _current_tab_find_editors(self):
        try:
            workspace = self.workspace_tabs.select()
        except tk.TclError:
            return []
        if workspace == str(getattr(self, "source_workspace", "")):
            return [widget for widget in (
                getattr(self, "editor", None),
                getattr(self, "todo_editor", None)) if widget is not None]
        if workspace == str(getattr(self, "operation_workspace", "")):
            operation = getattr(self, "operation_session_workspace", None)
            if operation is None:
                return []
            widgets = [
                operation.intermediate_text, operation.final_text,
                operation.diff_text, operation.vision_sample_text,
                operation.intermediate_history_diff_text]
            try:
                selected = operation.code_tabs.select()
                visible = [widget for widget in widgets
                           if str(widget.master) == selected]
                return visible or widgets
            except tk.TclError:
                return widgets
        if workspace == str(getattr(self, "command_recording_workspace", "")):
            studio = getattr(self, "command_recording_studio", None)
            return [studio.source_text] if studio is not None else []
        if workspace == str(getattr(self, "sample_functions_workspace", "")):
            return [widget for widget in (
                getattr(self, "fragment_imports", None),
                getattr(self, "fragment_class_vars", None),
                getattr(self, "fragment_initializer", None),
                getattr(self, "fragment_body", None)) if widget is not None]
        if workspace == str(getattr(self, "sample_lists_workspace", "")):
            return [getattr(self, "sample_list_preview", None)]
        if workspace == str(getattr(self, "sample_program_workspace", "")):
            return [getattr(self, "sample_program_editor", None)]
        return []

    def _active_find_editor(self):
        candidates = [widget for widget in self._current_tab_find_editors()
                      if widget is not None]
        target = self._find_target_editor
        if target not in candidates:
            target = candidates[0] if candidates else getattr(self, "editor", None)
            if target is not None:
                self._select_find_editor(target)
        return target

    def focus_current_tab_find(self, event=None):
        focus = self.focus_get()
        candidates = self._current_tab_find_editors()
        if focus in candidates:
            self._select_find_editor(focus)
        else:
            self._active_find_editor()
        self.find_entry.focus_set()
        self.find_entry.selection_range(0, "end")
        return "break"

    def _find_matches(self):
        editor = self._active_find_editor()
        needle = self.find_text.get()
        if not needle or editor is None:
            return []
        matches = []
        start = "1.0"
        count = tk.IntVar(value=0)
        while True:
            found = editor.search(
                needle, start, stopindex="end", nocase=True, count=count)
            if not found:
                break
            length = count.get()
            if length <= 0:
                break
            end = "{}+{}c".format(found, length)
            matches.append((found, end))
            start = end
        return matches

    def refresh_find_count(self):
        editor = self._active_find_editor()
        if editor is None:
            self.find_result_text.set("0 / 0")
            return
        ranges = editor.tag_ranges("find")
        current = editor.index(ranges[0]) if ranges else ""
        matches = self._find_matches()
        if not matches:
            self._show_find_match([], 0, focus=False)
            return
        index = find_match_index(
            matches, current_index=current,
            cursor_index=editor.index("insert"))
        self._show_find_match(matches, index, focus=False)

    def _show_find_match(self, matches, index, focus=True):
        editor = self._active_find_editor()
        if editor is None:
            return
        editor.tag_remove("find", "1.0", "end")
        if not matches:
            self.find_result_text.set("0 / 0")
            return
        index %= len(matches)
        found, end = matches[index]
        editor.tag_configure("find", background="#515c6a")
        editor.tag_add("find", found, end)
        editor.see(found)
        if focus:
            editor.mark_set("insert", end)
            editor.focus_set()
        self.find_result_text.set("{} / {}".format(index + 1, len(matches)))

    def find_next(self):
        editor = self._active_find_editor()
        if editor is None:
            return
        matches = self._find_matches()
        if not matches:
            self._show_find_match([], 0)
            return
        ranges = editor.tag_ranges("find")
        if ranges:
            current = editor.index(ranges[0])
            index = next((i + 1 for i, item in enumerate(matches)
                          if editor.compare(item[0], "==", current)), 0)
        else:
            cursor = editor.index("insert")
            index = next((i for i, item in enumerate(matches)
                          if editor.compare(item[0], ">=", cursor)), 0)
        self._show_find_match(matches, index)

    def find_previous(self):
        editor = self._active_find_editor()
        if editor is None:
            return
        matches = self._find_matches()
        if not matches:
            self._show_find_match([], 0)
            return
        ranges = editor.tag_ranges("find")
        if ranges:
            current = editor.index(ranges[0])
            index = next((i - 1 for i, item in enumerate(matches)
                          if editor.compare(item[0], "==", current)), len(matches) - 1)
        else:
            cursor = editor.index("insert")
            candidates = [i for i, item in enumerate(matches)
                          if editor.compare(item[0], "<", cursor)]
            index = candidates[-1] if candidates else len(matches) - 1
        self._show_find_match(matches, index)

    def replace_one(self):
        editor = self._active_find_editor()
        needle = self.find_text.get()
        if not needle or editor is None:
            return
        if not self._find_editors.get(editor, {}).get("replace", True):
            self.status.set("現在の検索対象は読み取り専用です。")
            return
        ranges = editor.tag_ranges("find")
        if ranges:
            editor.delete(ranges[0], ranges[1])
            editor.insert(ranges[0], self.replace_text.get())
        self.find_next()

    def replace_all(self):
        editor = self._active_find_editor()
        needle = self.find_text.get()
        if not needle or editor is None:
            return
        if not self._find_editors.get(editor, {}).get("replace", True):
            self.status.set("現在の検索対象は読み取り専用です。")
            return
        content = editor.get("1.0", "end-1c")
        count = content.lower().count(needle.lower())
        if not count:
            return
        content = re.sub(re.escape(needle), self.replace_text.get(), content, flags=re.IGNORECASE)
        if editor is self.editor:
            self.set_editor_content(content, self.current_path)
            self.editor_dirty = True
            self.update_editor_view()
        else:
            editor.delete("1.0", "end")
            editor.insert("1.0", content)
        self.status.set("Replaced {} occurrence(s)".format(count))

    def check_syntax(self):
        source = self.editor.get("1.0", "end-1c")
        name = self.current_path or "<unsaved>"
        try:
            compile(source, name, "exec")
        except SyntaxError as error:
            self.console_write("Syntax error: {}\n".format(error))
            self.editor.mark_set("insert", "{}.0".format(error.lineno or 1))
            self.editor.see("insert")
            self.status.set("Syntax error at line {}".format(error.lineno))
            return False
        self.console_write("Syntax check passed: {}\n".format(name))
        self.status.set("Syntax check passed")
        return True

    def console_write(self, text):
        value = str(text).strip()
        if value:
            self.status.set(value)

    def run_current(self):
        messagebox.showinfo("PokeConコマンドの実行",
                            "PokeConコマンドの実行はPokeCon本体側で行ってください。\nDevStudioでは構文チェックを実行します。",
                            parent=self)
        return self.check_syntax()

    def commands_root(self):
        root = self.root_dir.get()
        candidate = os.path.join(root, "SerialController", "Commands", "PythonCommands")
        if os.path.isdir(candidate):
            return candidate
        candidate = os.path.join(root, "Commands", "PythonCommands")
        return candidate

    def fragment_root(self):
        return os.path.join(self.root_dir.get(), "SerialController", "DevTemplates", "Fragments")

    def open_fragment_library(self):
        root = self.fragment_root()
        os.makedirs(root, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(root)
        else:
            messagebox.showinfo("Fragment library", root)

    def open_fragment_builder(self):
        if hasattr(self, "sample_functions_workspace"):
            self.workspace_tabs.select(self.sample_functions_workspace)
            return
        dialog = tk.Toplevel(self)
        dialog.title("New reusable fragment")
        dialog.transient(self)
        name = tk.StringVar(value="new_fragment")
        tags = tk.StringVar(value="image")
        target = tk.StringVar(value="step_user_block")
        imports = tk.StringVar(value="")
        requires = tk.StringVar(value="")
        ttk.Label(dialog, text="Name:").grid(column=0, row=0, padx=7, pady=4, sticky="w")
        ttk.Entry(dialog, textvariable=name, width=44).grid(column=1, row=0, padx=7, pady=4, sticky="ew")
        ttk.Label(dialog, text="Tags (comma):").grid(column=0, row=1, padx=7, pady=4, sticky="w")
        ttk.Entry(dialog, textvariable=tags, width=44).grid(column=1, row=1, padx=7, pady=4, sticky="ew")
        ttk.Label(dialog, text="Insert target:").grid(column=0, row=2, padx=7, pady=4, sticky="w")
        ttk.Combobox(dialog, state="readonly", textvariable=target, values=("step_user_block", "command_helper", "class_import"), width=28).grid(column=1, row=2, padx=7, pady=4, sticky="w")
        ttk.Label(dialog, text="Imports (one per line):").grid(column=0, row=3, padx=7, pady=4, sticky="nw")
        import_frame = ttk.Frame(dialog)
        import_frame.grid(column=1, row=3, padx=7, pady=4, sticky="nsew")
        import_box = tk.Text(import_frame, height=3, width=54, wrap="none")
        pack_scrollable_widget(import_box, horizontal=True)
        ttk.Label(dialog, text="Requires (comma):").grid(column=0, row=4, padx=7, pady=4, sticky="w")
        ttk.Entry(dialog, textvariable=requires, width=44).grid(column=1, row=4, padx=7, pady=4, sticky="ew")
        ttk.Label(dialog, text="Fragment code:").grid(column=0, row=5, padx=7, pady=4, sticky="nw")
        body_frame = ttk.Frame(dialog)
        body_frame.grid(column=1, row=5, padx=7, pady=4, sticky="nsew")
        body = tk.Text(body_frame, height=14, width=66, undo=True,
                       wrap="none")
        body.insert("1.0", "# @pokedev-fragment: new_fragment\n# Inserted into the selected Step user block.\n")
        pack_scrollable_widget(body, horizontal=True)
        def create_fragment():
            safe_name = python_identifier(name.get())
            root = os.path.join(self.fragment_root(), safe_name)
            metadata = {"name": name.get().strip() or safe_name,
                        "tags": [item.strip() for item in tags.get().split(",") if item.strip()],
                        "target": target.get(),
                        "imports": [item.strip() for item in import_box.get("1.0", "end-1c").splitlines() if item.strip()],
                        "requires": [item.strip() for item in requires.get().split(",") if item.strip()],
                        "fragment": safe_name + ".pyfrag"}
            try:
                os.makedirs(root, exist_ok=True)
                with open(os.path.join(root, safe_name + ".pokesample.json"), "w", encoding="utf-8", newline="\n") as file:
                    json.dump(metadata, file, ensure_ascii=False, indent=2)
                with open(os.path.join(root, safe_name + ".pyfrag"), "w", encoding="utf-8", newline="\n") as file:
                    file.write(body.get("1.0", "end-1c") + "\n")
            except OSError as error:
                messagebox.showerror("Fragment", str(error), parent=dialog)
                return
            self.refresh_index()
            self.show_file(os.path.join(root, safe_name + ".pyfrag"))
            self.status.set("Created reusable fragment: " + metadata["name"])
            dialog.destroy()
        ttk.Button(dialog, text="Create fragment", command=create_fragment).grid(column=1, row=6, padx=7, pady=8, sticky="e")
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(column=0, row=6, padx=7, pady=8)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(5, weight=1)

    def refresh_local_explorer(self):
        """Show the local command root independently of the selected workspace."""
        if not hasattr(self, "local_tree"):
            return
        base = self.commands_root()
        os.makedirs(base, exist_ok=True)
        def worker():
            entries = []
            for directory, dirs, filenames in os.walk(base):
                dirs[:] = sorted(item for item in dirs if item != "__pycache__")
                entries.append((directory, list(dirs), [name for name in sorted(filenames) if name.lower().endswith(".py")]))
            return entries
        def completed(entries):
            self.local_tree.delete(*self.local_tree.get_children())
            root_id = self.local_tree.insert("", "end", text=os.path.basename(base), open=True, values=("",))
            nodes = {base: root_id}
            for directory, dirs, filenames in entries:
                parent = nodes.get(directory, root_id)
                for directory_name in dirs:
                    path = os.path.join(directory, directory_name)
                    nodes[path] = self.local_tree.insert(parent, "end", text=directory_name, open=False, values=("",))
                for filename in filenames:
                    path = os.path.join(directory, filename)
                    self.local_tree.insert(parent, "end", text=filename, values=(path,))
        self.run_background(
            "local_explorer", "コマンド一覧を更新中", worker, completed,
            busy_cursor=False)

    def open_local_tree_file(self, event=None):
        selected = self.local_tree.selection()
        if selected:
            values = self.local_tree.item(selected[0], "values")
            if values and values[0]:
                self.show_file(values[0])

    def existing_command_tags(self):
        base = self.commands_root()
        found = set()
        if os.path.isdir(base):
            for directory, dirs, _ in os.walk(base):
                dirs[:] = [item for item in dirs if item != "__pycache__"]
                if directory != base:
                    found.add(os.path.basename(directory))
        return sorted(found, key=lambda item: item.lower())

    def open_commands_folder(self):
        base = self.commands_root()
        os.makedirs(base, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(base)
        else:
            messagebox.showinfo("Commands folder", base)

    def open_command_builder(self):
        dialog = tk.Toplevel(self)
        dialog.title("New PokeCon Python Command")
        dialog.transient(self)
        dialog.resizable(True, True)
        filename = tk.StringVar(value="new_command")
        command_name = tk.StringVar(value="New PokeCon Command")
        kind = tk.StringVar(value="Loop")
        tag_entry = tk.StringVar()
        tags = []
        form = ttk.Labelframe(dialog, text="Command file")
        form.grid(column=0, row=0, padx=8, pady=6, sticky="nsew")
        ttk.Label(form, text="Python file name:").grid(column=0, row=0, padx=5, pady=4, sticky="w")
        ttk.Entry(form, textvariable=filename, width=27).grid(column=1, row=0, padx=(5, 0), pady=4, sticky="ew")
        ttk.Label(form, text=".py").grid(column=2, row=0, padx=(0, 5), pady=4, sticky="w")
        ttk.Label(form, text="Command name:").grid(column=0, row=1, padx=5, pady=4, sticky="w")
        ttk.Entry(form, textvariable=command_name, width=32).grid(column=1, columnspan=2, row=1, padx=5, pady=4, sticky="ew")
        shown_preview = tk.StringVar()
        class_preview = tk.StringVar()
        def update_name_preview(*_):
            shown_preview.set(command_name.get().strip())
            class_preview.set(python_identifier(command_name.get()) + "_Command")
        command_name.trace_add("write", update_name_preview)
        update_name_preview()
        ttk.Label(form, text="Shown in Commands:").grid(column=0, row=2, padx=5, pady=2, sticky="w")
        ttk.Label(form, textvariable=shown_preview).grid(column=1, columnspan=2, row=2, padx=5, pady=2, sticky="w")
        ttk.Label(form, text="Class name:").grid(column=0, row=3, padx=5, pady=2, sticky="w")
        ttk.Label(form, textvariable=class_preview).grid(column=1, columnspan=2, row=3, padx=5, pady=2, sticky="w")
        ttk.Label(form, text="Template:").grid(column=0, row=4, padx=5, pady=4, sticky="w")
        ttk.Combobox(form, state="readonly", textvariable=kind, values=("Loop", "Step (state transition / 状態遷移)", "Step (nested chapters / 階層チャプター)", "One shot"), width=34).grid(column=1, row=4, padx=5, pady=4, sticky="w")

        tag_box = ttk.Labelframe(dialog, text="Folder tags (tag1 / tag2 / tag3 creates nested folders)")
        tag_box.grid(column=0, row=1, padx=8, pady=6, sticky="nsew")
        tag_cb = ttk.Combobox(tag_box, textvariable=tag_entry, values=self.existing_command_tags(), width=30)
        tag_cb.grid(column=0, row=0, padx=5, pady=4, sticky="ew")
        tag_list_frame = ttk.Frame(tag_box)
        tag_list_frame.grid(
            column=0, row=1, padx=5, pady=4, sticky="nsew")
        tag_list = tk.Listbox(
            tag_list_frame, height=4, exportselection=False)
        pack_scrollable_widget(tag_list, horizontal=True)
        def refresh_tags():
            tag_list.delete(0, "end")
            for value in tags:
                tag_list.insert("end", value)
        def add_tag():
            value = tag_entry.get().strip()
            if value and value not in tags:
                if any(char in value for char in '\\/:*?"<>|'):
                    messagebox.showwarning("Tag", "タグに \\ / : * ? \" < > | は使用できません。", parent=dialog)
                    return
                tags.append(value)
                tag_entry.set("")
                refresh_tags()
        def remove_tag():
            picked = tag_list.curselection()
            if picked:
                del tags[picked[0]]
                refresh_tags()
        ttk.Button(tag_box, text="Add tag", command=add_tag).grid(column=1, row=0, padx=4, pady=4)
        ttk.Button(tag_box, text="Remove", command=remove_tag).grid(column=1, row=1, padx=4, pady=4)

        def create_command():
            if not filename.get().strip() or not command_name.get().strip():
                messagebox.showwarning("Command", "Python file name and displayed command name are required.", parent=dialog)
                return
            try:
                target = command_path(self.commands_root(), tags, filename.get())
                source = template_source(kind.get(), class_preview.get(), shown_preview.get(), tags, [], True)
            except ValueError as error:
                messagebox.showwarning("Command", str(error), parent=dialog)
                return
            if os.path.exists(target) and not messagebox.askyesno("Overwrite", "File already exists. Overwrite it?", parent=dialog):
                return
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(source)
            self.refresh_index()
            self.refresh_local_explorer()
            self.set_editor_content(source, target)
            self.status.set("Created {}. Use PokeCon's Reload Commands to load it.".format(target))
            dialog.destroy()
        buttons = ttk.Frame(dialog)
        buttons.grid(column=0, columnspan=2, row=2, padx=8, pady=(0, 8), sticky="e")
        ttk.Button(buttons, text="Create command", command=create_command).pack(side="left", padx=3)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=3)

    def choose_root(self):
        chosen = filedialog.askdirectory(initialdir=self.root_dir.get() or os.getcwd())
        if chosen:
            self.root_dir.set(chosen)
            self.refresh_index()

    def refresh_index(self):
        root = self.root_dir.get()
        if not os.path.isdir(root):
            messagebox.showwarning("Dev Studio", "Select an existing code folder.")
            return
        self._fragment_catalog_cache = None
        self._source_function_catalog_candidates = None
        def worker():
            files, fragments, errors = [], [], []
            for directory, dirs, filenames in os.walk(root):
                dirs[:] = [
                    item for item in dirs
                    if item not in ("__pycache__", ".git", "venv")
                    and not item.lower().startswith(".venv")
                ]
                for filename in sorted(filenames):
                    if filename.lower().endswith(PYTHON_SUFFIXES):
                        path = os.path.join(directory, filename)
                        files.append(path)
                        try:
                            fragments.extend(self.extract_fragments(path))
                        except Exception as error:
                            # One damaged/generated source must not prevent all
                            # other files from appearing in DevStudio.
                            errors.append((path, str(error)))
            return root, files, fragments, errors

        def completed(result):
            indexed_root, files, fragments, errors = result
            if os.path.abspath(indexed_root) != os.path.abspath(self.root_dir.get()):
                return
            self.files, self.fragments, self.index_errors = files, fragments, errors
            self.tree.delete(*self.tree.get_children())
            self._populate_index_tree(indexed_root, files, 0, {"": ""})
        self.run_background(
            "refresh_index", "ソース索引を更新中", worker, completed,
            busy_cursor=False)

    def _populate_index_tree(self, root, files, offset, nodes):
        """Populate large indexes in batches so Tk can process events between chunks."""
        for path in files[offset:offset + 100]:
            relative = os.path.relpath(path, root)
            parent, cumulative = "", ""
            for part in relative.split(os.sep)[:-1]:
                cumulative = os.path.join(cumulative, part)
                if cumulative not in nodes:
                    nodes[cumulative] = self.tree.insert(parent, "end", text=part, open=False, values=("",))
                parent = nodes[cumulative]
            self.tree.insert(parent, "end", text=os.path.basename(path), values=(path,))
        next_offset = offset + 100
        if next_offset < len(files):
            self.status.set("ソース一覧を表示中... {}/{}".format(min(next_offset, len(files)), len(files)))
            self.after(1, self._populate_index_tree, root, files, next_offset, nodes)
        else:
            status = "{} Python files, {} tagged code fragments indexed".format(
                len(files), len(self.fragments))
            if self.index_errors:
                first_path, first_error = self.index_errors[0]
                status += " / 読込除外 {}件: {} ({})".format(
                    len(self.index_errors), os.path.relpath(first_path, root), first_error)
            self.status.set(status)

    def _read_lines(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return handle.readlines()
        except UnicodeDecodeError:
            with open(path, "r", encoding="cp932", errors="replace") as handle:
                return handle.readlines()
        except OSError:
            return []

    def extract_fragments(self, path):
        lines = self._read_lines(path)
        if not lines:
            return []
        fragments, pending_tags, blocks = [], [], []
        for number, line in enumerate(lines, 1):
            match = TAG_RE.search(line)
            if match:
                pending_tags.extend(self._split_tags(match.group(1)))
            begin = BEGIN_RE.search(line)
            if begin:
                blocks.append((number, self._split_tags(begin.group(1))))
            if END_RE.search(line) and blocks:
                start, tags = blocks.pop()
                fragments.append(Fragment(path, start, number, tags, "block", "manual block", "".join(lines[start - 1:number])))
        try:
            parsed = ast.parse("".join(lines), filename=path)
        except SyntaxError:
            return fragments
        definitions = [node for node in ast.walk(parsed) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        for node in definitions:
            previous = "".join(lines[max(0, node.lineno - 5):node.lineno - 1])
            matches = TAG_RE.findall(previous)
            tags = []
            for match in matches:
                tags.extend(self._split_tags(match))
            if tags:
                start = node.lineno
                while start > 1 and lines[start - 2].lstrip().startswith("@"):
                    start -= 1
                end = getattr(node, "end_lineno", node.lineno)
                fragments.append(Fragment(path, start, end, tags,
                                          "class" if isinstance(node, ast.ClassDef) else "function",
                                          node.name, "".join(lines[start - 1:end])))
        return fragments

    @staticmethod
    def _split_tags(value):
        return [item.strip().lower() for item in re.split(r"[,\s]+", value) if item.strip()]

    def _show_results(self, hits):
        self.search_hits = hits
        self.left_tabs.select(self.search_tab)
        self.results.delete(0, "end")
        root = self.root_dir.get()
        for hit in hits:
            if isinstance(hit, Fragment):
                self.results.insert("end", "{} — {}".format(os.path.relpath(hit.path, root), hit.label))
            else:
                path, number, text = hit
                self.results.insert("end", "{}:{}  {}".format(os.path.relpath(path, root), number, text.strip()))
        self.status.set("{} result(s)".format(len(hits)))

    def search_all(self):
        needle = self.search_text.get().strip().lower()
        if not needle:
            return
        files = list(self.files)
        def worker():
            hits = []
            for path in files:
                for number, line in enumerate(self._read_lines(path), 1):
                    if needle in line.lower(): hits.append((path, number, line))
            return hits
        self.run_background("search_all", "全文検索中", worker, self._show_results)

    def filter_tags(self):
        wanted = set(self._split_tags(self.tag_text.get()))
        hits = [item for item in self.fragments if not wanted or wanted.issubset(set(item.tags))]
        self._show_results(hits)

    def find_reusable(self):
        # A practical first pass: show every function/class.  Tagged entries
        # are included with their tag information, while untagged definitions
        # can be inspected and then tagged by the developer.
        files, initial = list(self.files), list(self.fragments)
        def worker():
            hits = list(initial)
            tagged = {(item.path, item.start, item.end) for item in hits}
            for path in files:
                lines = self._read_lines(path)
                try: parsed = ast.parse("".join(lines), filename=path)
                except SyntaxError: continue
                for node in ast.walk(parsed):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        key = (path, node.lineno, getattr(node, "end_lineno", node.lineno))
                        if key not in tagged:
                            hits.append(Fragment(path, node.lineno, key[2], (),
                                                 "class" if isinstance(node, ast.ClassDef) else "function",
                                                 node.name, "".join(lines[node.lineno - 1:key[2]])))
            return sorted(hits, key=lambda item: (item.name.lower(), item.path, item.start))
        self.run_background("find_reusable", "再利用可能コードを解析中", worker, self._show_results)

    def open_tree_file(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        if values:
            self.show_file(values[0])

    def open_selected_result(self, event=None):
        selected = self.results.curselection()
        if not selected:
            return
        hit = self.search_hits[selected[0]]
        if isinstance(hit, Fragment):
            self.show_file(hit.path, hit.start)
        else:
            self.show_file(hit[0], hit[1])

    def show_file(self, path, line=1):
        lines = self._read_lines(path)
        if False:  # Opening another file uses a separate tab; do not discard the active tab.
            if not messagebox.askyesno("Open file", "保存していない変更を破棄しますか？"):
                return
        self.set_editor_content("".join(lines), path, line)
        self.status.set(path)

    def open_selected_file(self):
        selected = self.results.curselection()
        if selected:
            hit = self.search_hits[selected[0]]
            self.show_file(hit.path if isinstance(hit, Fragment) else hit[0])

    def merge_selected(self):
        selected = self.results.curselection()
        fragments = [self.search_hits[index] for index in selected if isinstance(self.search_hits[index], Fragment)]
        if not fragments:
            messagebox.showinfo("Merge", "タグ付きコードまたは再利用関数を選択してください。")
            return
        parts = ["# Generated by PokeCon Dev Studio\n"]
        for item in fragments:
            parts.append("\n# --- {}:{} {} {} ---\n".format(item.path, item.start, item.kind, item.name))
            parts.append(item.source.rstrip() + "\n")
        self.set_editor_content("".join(parts), None)
        self.editor_dirty = True
        self.update_editor_view()
        self.status.set("Merged {} code fragment(s). Review imports and duplicate names before use.".format(len(fragments)))

    def save_output(self):
        path = filedialog.asksaveasfilename(initialdir=self.root_dir.get(), defaultextension=".py",
                                            filetypes=(("Python", "*.py"), ("All files", "*.*")))
        if path:
            self._write_editor(path)


def startup_arguments(arguments):
    default_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    root, operation_session, command_recording = default_root, "", ""
    index = 0
    while index < len(arguments):
        value = arguments[index]
        if value == "--operation-session" and index + 1 < len(arguments):
            operation_session = arguments[index + 1]
            index += 2
            continue
        if value == "--command-recording" and index + 1 < len(arguments):
            command_recording = arguments[index + 1]
            index += 2
            continue
        if not value.startswith("--"):
            root = value
        index += 1
    return (os.path.abspath(root),
            os.path.abspath(operation_session) if operation_session else "",
            os.path.abspath(command_recording) if command_recording else "")


if __name__ == "__main__":
    startup_root, startup_session, startup_recording = startup_arguments(sys.argv[1:])
    DevStudio(startup_root, operation_session=startup_session,
              command_recording=startup_recording).mainloop()
