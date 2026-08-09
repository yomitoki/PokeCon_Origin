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

from CommandBuilder import command_path, folder_segment, python_identifier, template_source
from SampleLibrary import (catalog, compose_preview, detect_conflicts, load_fragment,
                           load_library, merge_preview, resolve_members, save_library)
from SampleProgramLoader import inspect_sample_program
from SampleFunctionSync import compare_folder as compare_sample_function_folder
from SampleFunctionSync import update_fragments as update_sample_function_fragments
from SampleFunctionSync import update_source as update_source_sample_functions
from SampleFunctionSync import propagate_functions as propagate_sample_functions
from SampleFunctionSync import replace_class_functions
from SampleFunctionSync import function_records as sample_sync_function_records
from ImageDetectionLibrary import (folder_tags as image_folder_tags,
                                   generate_image_check,
                                   load_library as load_image_library,
                                   resolve_list as resolve_image_list,
                                   save_library as save_image_library)
from ImageDetectionSync import (compare_settings as compare_image_detection_settings,
                                parse_source_settings as parse_source_image_detection_settings,
                                update_library_from_source)
from ImageHealthCheck import audit_image_library, suggested_crop
from CompletionEngine import CompletionEngine
from SourceFunctionTools import (build_rename_map, register_source_functions,
                                 rename_source_functions, source_function_records,
                                 step_function_names)


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
    def __init__(self, parent, choices_provider, initial=None):
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
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.columnconfigure(1, weight=1); self.columnconfigure(2, weight=1)
        self.rowconfigure(1, weight=1)
        self.set_tags(initial or [])

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

    def set_tags(self, tags):
        self.listbox.delete(0, "end")
        for tag in tags:
            value = str(tag).strip()
            if value and value not in self.get_tags():
                self.listbox.insert("end", value)
        self.refresh_choices()


class DevStudio(tk.Tk):
    def __init__(self, initial_root):
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
        self.editing_fragment_id = None
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
        self.find_text = tk.StringVar()
        self.find_result_text = tk.StringVar(value="0 / 0")
        self.replace_text = tk.StringVar()
        self.ui_language = tk.StringVar(value="日本語")
        self._build()
        self._build_menu()
        self.apply_language()
        self.after_idle(self.set_default_pane_sizes)
        self.after(100, self.restore_ui_state)
        self.after(50, self._drain_background_tasks)
        self.protocol("WM_DELETE_WINDOW", self.close_dev_studio)
        self.refresh_index()
        self.refresh_local_explorer()
        self.refresh_sample_apply_lists()
        self.refresh_sample_lists_tab()
        self.refresh_registered_fragment_choices()

    def run_background(self, key, label, worker, on_success, on_error=None):
        """Run non-Tk work without blocking the UI and marshal completion safely."""
        if key in self.background_tasks:
            self.status.set(label + "（処理中です）")
            return False
        self.background_tasks.add(key)
        self.status.set(label + "...")
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
                if not self.background_tasks:
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
            titles = ("🟦 ソース編集", "🟩 サンプル関数", "🟨 サンプルリスト") if self.ui_language.get() == "日本語" else ("🟦 Source edit", "🟩 Sample functions", "🟨 Sample lists")
            for tab, title in zip(self.workspace_tabs.tabs(), titles):
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
                    self.add_editor_document(document.get("content", ""), document["path"])
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
        find_entry = ttk.Entry(edit_tools, textvariable=self.find_text, width=16)
        find_entry.pack(side="left", padx=2)
        find_entry.bind("<Return>", lambda event: self.find_next())
        self.find_text.trace_add("write", lambda *args: self.debounce(
            "editor_find_count", 120, self.refresh_find_count))
        ttk.Button(edit_tools, text="前へ", command=self.find_previous).pack(side="left")
        ttk.Button(edit_tools, text="次へ", command=self.find_next).pack(side="left", padx=(2, 0))
        ttk.Label(edit_tools, textvariable=self.find_result_text, width=9, anchor="center").pack(side="left", padx=(3, 0))
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
        sample_functions_workspace = ttk.Frame(self.workspace_tabs)
        sample_lists_workspace = ttk.Frame(self.workspace_tabs)
        sample_program_workspace = ttk.Frame(self.workspace_tabs)
        image_library_workspace = ttk.Frame(self.workspace_tabs)
        self.image_library_workspace = image_library_workspace
        self.workspace_tabs.add(source_workspace, text="🟦 ソース編集")
        self.workspace_tabs.add(sample_functions_workspace, text="🟩 サンプル関数")
        self.workspace_tabs.add(sample_lists_workspace, text="🟨 サンプルリスト")
        self.workspace_tabs.add(sample_program_workspace, text="🟦 サンプルプログラム")
        self.workspace_tabs.tab(source_workspace, padding=(10, 4))
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
        self.search_tab = search_tab

        ttk.Label(explorer_tab, text="Python files").pack(anchor="w")
        self.tree = ttk.Treeview(explorer_tab, show="tree")
        self.tree.pack(fill="both", expand=True, side="left")
        tree_scroll = ttk.Scrollbar(explorer_tab, orient="vertical", command=self.tree.yview)
        tree_scroll.pack(fill="y", side="right")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self.open_tree_file)

        ttk.Label(local_explorer_tab, text="Local commands: SerialController/Commands/PythonCommands").pack(anchor="w")
        self.local_tree = ttk.Treeview(local_explorer_tab, show="tree")
        self.local_tree.pack(fill="both", expand=True, side="left")
        local_scroll = ttk.Scrollbar(local_explorer_tab, orient="vertical", command=self.local_tree.yview)
        local_scroll.pack(fill="y", side="right")
        self.local_tree.configure(yscrollcommand=local_scroll.set)
        self.local_tree.bind("<<TreeviewSelect>>", self.open_local_tree_file)

        sample_apply_pane = ttk.Panedwindow(sample_apply_tab, orient="vertical")
        sample_apply_pane.pack(fill="both", expand=True)
        function_apply = ttk.Labelframe(sample_apply_pane, text="サンプル関数リスト")
        image_apply = ttk.Labelframe(sample_apply_pane, text="画像検知設定")
        sample_apply_pane.add(function_apply, weight=2); sample_apply_pane.add(image_apply, weight=3)
        self.sample_apply_list = tk.Listbox(function_apply, exportselection=False)
        self.sample_apply_list.pack(fill="both", expand=True, padx=4, pady=4)
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
        self.sample_apply_image_tree.pack(side="left", fill="both", expand=True)
        image_tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.sample_apply_image_tree.yview)
        image_tree_scroll.pack(side="right", fill="y"); self.sample_apply_image_tree.configure(yscrollcommand=image_tree_scroll.set)
        image_add_row = ttk.Frame(image_apply); image_add_row.pack(fill="x", padx=4, pady=3)
        ttk.Button(image_add_row, text="＋必要リストへ追加", command=self.add_sample_apply_image_selection).pack(side="left")
        ttk.Button(image_add_row, text="－必要リストから外す", command=self.remove_sample_apply_image_selection).pack(side="left", padx=3)
        self.sample_apply_image_selected = tk.Listbox(image_apply, exportselection=False, height=4)
        self.sample_apply_image_selected.pack(fill="x", padx=4)
        ttk.Button(image_apply, text="必要な画像検知を編集中ソースへ反映", command=self.apply_sample_apply_images).pack(fill="x", padx=4, pady=4)

        ttk.Label(search_tab, text="Search / tagged / reusable results (Ctrl+click to select multiple)").pack(anchor="w")
        self.results = tk.Listbox(search_tab, selectmode="extended", exportselection=False)
        self.results.pack(fill="both", expand=True, side="left")
        result_scroll = ttk.Scrollbar(search_tab, orient="vertical", command=self.results.yview)
        result_scroll.pack(fill="y", side="right")
        self.results.configure(yscrollcommand=result_scroll.set)
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
        step_hierarchy_tab = ttk.Frame(self.right_tabs)
        completion_tab = ttk.Frame(self.right_tabs)
        source_functions_tab = ttk.Frame(self.right_tabs)
        self.right_tabs.add(image_targets_tab, text="Image detection")
        self.right_tabs.add(image_health_tab, text="画像チェック")
        self.right_tabs.add(step_hierarchy_tab, text="Step hierarchy")
        self.right_tabs.add(completion_tab, text="Completion")
        self.right_tabs.add(source_functions_tab, text="関数登録")
        self.step_hierarchy_tab = step_hierarchy_tab
        self.completion_tab = completion_tab
        self.source_functions_tab = source_functions_tab
        self.image_health_tab = image_health_tab
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
        self.editor.pack(fill="both", expand=True, side="left")
        editor_scroll = ttk.Scrollbar(editor_box, orient="vertical", command=self._scroll_editor)
        editor_scroll.pack(fill="y", side="right")
        self.editor.configure(yscrollcommand=lambda first, last: self._sync_editor_scroll(editor_scroll, first, last))
        self.editor.bind("<<Modified>>", self.editor_modified)
        self.editor.bind("<KeyRelease>", self.on_editor_key_release)
        self.editor.bind("<ButtonRelease-1>", lambda event: self.debounce(
            "editor_completion_click", 80, self.refresh_completion))
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
        todo_frame = ttk.Labelframe(center, text="TODO / 改修予定（ソースファイル別）")
        todo_frame.pack(fill="x", pady=(5, 0))
        todo_top = ttk.Frame(todo_frame); todo_top.pack(fill="x", padx=3, pady=(3, 0))
        self.todo_source_label = tk.StringVar(value="保存済みソースを開くとTODOを記録できます。")
        ttk.Label(todo_top, textvariable=self.todo_source_label).pack(side="left", fill="x", expand=True)
        ttk.Button(todo_top, text="＋項目", command=self.insert_todo_item).pack(side="right", padx=2)
        ttk.Button(todo_top, text="＋現在の関数へ紐づけ", command=self.insert_linked_todo_item).pack(side="right", padx=2)
        ttk.Button(todo_top, text="TODOを保存", command=self.save_current_todo).pack(side="right", padx=2)
        self.todo_editor = tk.Text(todo_frame, height=8, wrap="word", undo=True,
                                   background="#171717", foreground="#dddddd", insertbackground="white")
        self.todo_editor.pack(fill="both", expand=True, padx=3, pady=3)
        self.todo_editor.bind("<<Modified>>", self.todo_modified)
        self.todo_editor.bind("<FocusOut>", lambda event: self.save_current_todo(silent=True))
        self.todo_editor.bind("<Double-Button-1>", self.open_todo_source_location)
        self.bind_text_undo_redo(self.todo_editor)
        self._build_image_targets_tab(image_targets_tab)
        self._build_image_health_tab(image_health_tab)
        self._build_step_hierarchy_tab(step_hierarchy_tab)
        self._build_completion_tab(completion_tab)
        self._build_source_functions_tab(source_functions_tab)
        self._build_sample_functions_tab(sample_functions_workspace)
        self._build_sample_lists_tab(sample_lists_workspace)
        self._build_sample_program_tab(sample_program_workspace)
        self._build_image_library_workspace(image_library_workspace)
        self.add_editor_document("", None)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(source_workspace, textvariable=self.status, anchor="w").pack(fill="x", pady=(0, 5))

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
        self.completion_tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.completion_tree.yview)
        scroll.pack(side="right", fill="y")
        self.completion_tree.configure(yscrollcommand=scroll.set)
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
        if self.completion_mode.get() != "無効":
            self.debounce("editor_completion", 140, self.refresh_completion)

    def show_completion_now(self, event=None):
        if self.completion_mode.get() == "無効":
            return "break"
        self.refresh_completion(explicit=True)
        return "break"

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
        self.completion_popup_list.pack(fill="both", expand=True)
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
        self.step_tree.pack(side="left", fill="both", expand=True)
        step_tree_scroll = ttk.Scrollbar(step_tree_frame, orient="vertical", command=self.step_tree.yview)
        step_tree_scroll.pack(side="right", fill="y")
        self.step_tree.configure(yscrollcommand=step_tree_scroll.set)
        ttk.Checkbutton(parent, text="Use loop to advance steps", variable=self.step_loop).grid(column=0, columnspan=2, row=4, padx=7, pady=3, sticky="w")
        ttk.Combobox(parent, state="readonly", width=34, textvariable=self.step_template_mode, values=("Step (state transition / 状態遷移)", "Step (nested chapters / 階層チャプター)")).grid(column=2, columnspan=2, row=4, padx=3, pady=3, sticky="e")
        ttk.Label(parent, text="First step:").grid(column=0, row=5, padx=7, pady=3, sticky="w")
        ttk.Combobox(parent, state="readonly", width=12, textvariable=self.step_start, values=("0 (_step_0)", "1 (_step_1)")).grid(column=1, row=5, padx=3, pady=3, sticky="w")
        special_box = ttk.Labelframe(parent, text="Special steps (called explicitly, not in normal order)")
        special_box.grid(column=0, columnspan=4, row=6, padx=7, pady=(5, 7), sticky="nsew")
        ttk.Entry(special_box, textvariable=self.special_step_entry, width=24).pack(side="left", padx=4, pady=4)
        self.special_step_list = tk.Listbox(special_box, height=3, exportselection=False)
        self.special_step_list.pack(side="left", fill="x", expand=True, padx=4, pady=4)
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
        self.source_function_summary = tk.StringVar(value="現在のソースを解析します。")
        self.source_function_rows = {}
        self.source_function_name_overrides = {}
        self.source_function_last_registered = []

        help_box = ttk.Label(
            parent,
            text="①関数を選択 → ②登録名を確認 → ③ソース改名またはサンプル登録\n"
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
        sample_box.columnconfigure(1, weight=1)

        actions = ttk.Frame(parent); actions.pack(fill="x", padx=6, pady=4)
        ttk.Button(actions, text="選択名をソースへ一括反映",
                   command=self.apply_source_function_renames).pack(fill="x", pady=2)
        ttk.Button(actions, text="選択をサンプルへ登録",
                   command=self.register_selected_source_functions).pack(fill="x", pady=2)
        ttk.Button(actions, text="選択サンプルを変更画面で開く",
                   command=self.open_selected_source_sample).pack(fill="x", pady=2)
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
        catalog_by_name = {}
        for item in self.fragment_catalog():
            catalog_by_name.setdefault(item.get("name", ""), []).append(item)
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
            registered = catalog_by_name.get(new_name, [])
            if len(registered) == 1:
                status = "登録済み"; fragment_id = registered[0]["id"]; registered_count += 1
            elif len(registered) > 1:
                status = "同名複数"; fragment_id = ""
            else:
                status = "未登録"; fragment_id = ""
            iid = self.source_function_tree.insert(
                "", "end", text=old_name,
                values=(new_name, record["line"], status))
            row = dict(record)
            row.update({"new_name": new_name, "fragment_id": fragment_id})
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
        source = self.editor.get("1.0", "end-1c")
        names = [row["name"] for row in rows]
        rename_map = {row["name"]: row["new_name"] for row in rows}
        tags = [value.strip() for value in self.source_function_tags.get().split(",")
                if value.strip()]
        detail = self._source_function_mapping_detail(rows)
        overwrite = self.source_function_overwrite.get()
        action = "登録済みサンプルは内容を更新します。" if overwrite else \
            "登録済みと同名の場合は中断します。"
        if not messagebox.askyesno(
                "ソースからサンプル登録",
                "{}関数をサンプルへ登録します。\n{}\n\n{}\n\n続行しますか？".format(
                    len(rows), action, detail), parent=self):
            return
        root = self.fragment_root()
        folder = self.source_function_folder.get().strip() or "SourceImports"
        current_path = self.current_path or ""

        def worker():
            return register_source_functions(
                source, names, root, folder=folder, rename_map=rename_map,
                tags=tags, overwrite=overwrite, source_path=current_path)

        def completed(created):
            self._fragment_catalog_cache = None
            self.source_function_last_registered = [item["id"] for item in created]
            self.refresh_index()
            self.refresh_registered_fragment_choices()
            self.refresh_sample_lists_tab(select=self.sample_list_name.get().strip())
            self.refresh_sample_apply_lists()
            self.refresh_source_functions(select_names=names, reload_source=False)
            self.status.set("ソースからサンプル関数を{}件登録しました。".format(len(created)))
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

    def open_or_name_source_function(self, event=None):
        rows = self._selected_source_functions(require=False)
        if len(rows) == 1 and rows[0].get("fragment_id"):
            self.load_fragment_for_editing(rows[0]["fragment_id"])
        elif len(rows) == 1:
            self.edit_source_function_target_name()

    def on_right_tool_tab_changed(self, event=None):
        if self.right_tabs.select() == str(self.image_health_tab):
            self.run_image_health_check()
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
        self.image_target_tree = ttk.Treeview(parent, columns=("name", "description", "image", "threshold", "roi", "mode", "resolution"), show="headings", height=12)
        for column, label, width in (("name", "Name", 110), ("description", "説明", 170), ("image", "Image", 300), ("threshold", "Threshold", 72), ("roi", "ROI", 100), ("mode", "Mode", 82), ("resolution", "Reference", 95)):
            self.image_target_tree.heading(column, text=label)
            self.image_target_tree.column(column, width=width, stretch=(column == "image"))
        self.image_target_tree.grid(column=0, columnspan=6, row=4, padx=7, pady=(5, 5), sticky="nsew")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.image_target_tree.yview)
        scrollbar.grid(column=6, row=4, padx=(0, 5), pady=(5, 5), sticky="ns")
        self.image_target_tree.configure(yscrollcommand=scrollbar.set)
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

    def _build_image_library_workspace(self, parent):
        pane = ttk.Panedwindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left, right = ttk.Frame(pane), ttk.Frame(pane)
        pane.add(left, weight=3); pane.add(right, weight=2)

        self.image_library_search = tk.StringVar()
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
        ttk.Button(search, text="Template画像を再読込", command=self.scan_template_images).pack(side="right")

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

        self.image_library_tree = ttk.Treeview(left, columns=("path", "threshold", "crop", "tags"), show="tree headings")
        self.image_library_tree.heading("#0", text="検知名 / パターン")
        for column, label, width in (("path", "画像", 280), ("threshold", "閾値", 55), ("crop", "範囲", 120), ("tags", "タグ", 130)):
            self.image_library_tree.heading(column, text=label); self.image_library_tree.column(column, width=width)
        self.image_library_tree.pack(fill="both", expand=True)
        self.image_library_tree.bind("<<TreeviewSelect>>", self.load_selected_image_library_variant)

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
        self.image_library_lists = tk.Listbox(list_box, height=7, exportselection=False)
        self.image_library_lists.pack(fill="x", padx=5)
        self.image_library_lists.bind("<<ListboxSelect>>", self.load_image_detection_list)
        member_row = ttk.Frame(list_box); member_row.pack(fill="x", padx=5, pady=5)
        self.image_library_member_combo = ttk.Combobox(member_row, textvariable=self.image_library_member, state="readonly")
        self.image_library_member_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(member_row, text="＋追加", command=self.add_image_detection_member).pack(side="left", padx=3)
        ttk.Button(member_row, text="－外す", command=self.remove_image_detection_member).pack(side="left")
        self.image_library_members = tk.Listbox(list_box, height=9, exportselection=False)
        self.image_library_members.pack(fill="both", expand=True, padx=5)
        apply_row = ttk.Frame(right); apply_row.pack(fill="x", pady=6)
        ttk.Combobox(apply_row, textvariable=self.image_library_apply_target, state="readonly",
                     values=("サンプルプログラム", "ソース編集"), width=18).pack(side="left")
        ttk.Button(apply_row, text="image_checkを生成/更新", command=self.apply_image_detection_code).pack(side="left", padx=5)
        ttk.Button(apply_row, text="生成内容を確認", command=self.preview_image_detection_code).pack(side="left")
        ttk.Button(right, text="ソース ⇄ 画像検知記録：差分チェック・同期",
                   command=self.open_image_detection_sync_mode).pack(fill="x", pady=(0, 3))
        ttk.Button(right, text="ソース → 画像検知記録へ直接更新", command=self.load_image_detection_from_source).pack(fill="x", pady=(0, 6))
        self.refresh_image_library_workspace()

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
        tree = ttk.Treeview(dialog, columns=("status", "source", "library"), show="tree headings")
        tree.heading("#0", text="画像検知名"); tree.heading("status", text="状態")
        tree.heading("source", text="ソース設定"); tree.heading("library", text="画像検知記録")
        tree.column("#0", width=390); tree.column("status", width=150)
        tree.column("source", width=250); tree.column("library", width=250)
        tree.pack(fill="both", expand=True, padx=7, pady=4)
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
        self.fragment_tag_picker = TagPicker(form, self.fragment_tag_choices, initial=["image"])
        self.fragment_tag_picker.grid(column=1, columnspan=3, row=1, padx=6, pady=4, sticky="nsew")
        ttk.Label(form, text="保存フォルダ:").grid(column=0, row=2, padx=6, pady=4, sticky="w")
        ttk.Entry(form, textvariable=self.fragment_folder).grid(column=1, row=2, padx=6, pady=4, sticky="ew")
        ttk.Button(form, text="選択", command=self.choose_fragment_folder).grid(column=2, row=2, padx=3, pady=4)
        ttk.Button(form, text="+ フォルダ", command=self.add_fragment_folder).grid(column=3, row=2, padx=3, pady=4)
        ttk.Label(form, text="Imports（import / from形式・1行ずつ）:").grid(column=0, row=3, padx=6, pady=4, sticky="nw")
        self.fragment_imports = tk.Text(form, height=4, undo=True)
        self.fragment_imports.grid(column=1, row=3, padx=6, pady=4, sticky="ew")
        ttk.Label(form, text="クラス変数（1行ずつ）:").grid(column=0, row=4, padx=6, pady=4, sticky="nw")
        self.fragment_class_vars = tk.Text(form, height=4, undo=True)
        self.fragment_class_vars.grid(column=1, row=4, padx=6, pady=4, sticky="ew")
        ttk.Label(form, text="実行開始時の初期化コード:").grid(column=0, row=5, padx=6, pady=4, sticky="nw")
        self.fragment_initializer = tk.Text(form, height=5, undo=True, wrap="none",
                                            font=self.code_font, tabs=self.code_tabs)
        self.fragment_initializer.grid(column=1, row=5, padx=6, pady=4, sticky="ew")
        ttk.Label(form, text="Start後、関数処理より前に実行します。self.xxx = 0 やSteam画面のアクティブ化を記述します。").grid(
            column=2, columnspan=2, row=5, padx=6, pady=4, sticky="nw")
        ttk.Label(form, text="関数・処理コード:").grid(column=0, row=6, padx=6, pady=4, sticky="nw")
        ttk.Label(form, text="Tabは半角スペース4文字です。改行時はインデントを維持し、行番号のドラッグで複数行を選択できます。").grid(
            column=1, row=6, padx=6, pady=(0, 2), sticky="nw")
        fragment_editor_frame = ttk.Frame(form)
        fragment_editor_frame.grid(column=1, row=6, padx=6, pady=(24, 4), sticky="nsew")
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
        for editor in (self.fragment_imports, self.fragment_class_vars, self.fragment_initializer, self.fragment_body):
            editor.bind("<Tab>", lambda event, widget=editor: self._python_editor_tab(widget))
            editor.bind("<Shift-Tab>", lambda event, widget=editor: self._python_editor_shift_tab(widget))
            editor.bind("<Return>", lambda event, widget=editor: self._python_editor_newline(widget))
        self.fragment_body.bind("<<Modified>>", self._fragment_editor_modified)
        self.fragment_body.bind("<KeyRelease>", lambda event: self.after_idle(self._update_fragment_line_numbers))
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
        self.fragment_save_button = ttk.Button(form, text="サンプルとして保存", command=self.create_fragment_from_tab)
        self.fragment_save_button.grid(column=1, row=7, padx=6, pady=8, sticky="e")
        ttk.Button(form, text="サンプルライブラリを開く", command=self.open_fragment_library).grid(column=0, row=7, padx=6, pady=8, sticky="w")
        registered = ttk.Frame(form)
        registered.grid(column=2, columnspan=2, row=7, padx=6, pady=8, sticky="e")
        self.registered_fragment_choice = tk.StringVar()
        ttk.Label(registered, text="登録済みサンプル関数:").pack(side="left", padx=(0, 3))
        self.registered_fragment_combo = ttk.Combobox(registered, textvariable=self.registered_fragment_choice, state="readonly", width=34)
        self.registered_fragment_combo.pack(side="left", padx=2)
        ttk.Button(registered, text="変更", command=self.edit_registered_fragment).pack(side="left", padx=2)
        ttk.Button(registered, text="削除", command=self.delete_registered_fragment).pack(side="left", padx=2)
        ttk.Button(registered, text="新規へ戻る", command=self.cancel_fragment_edit).pack(side="left", padx=2)
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
        dialog.geometry("1050x650")
        dialog.transient(self)
        folder_var = tk.StringVar(value=self.fragment_folder.get() or self.fragment_root())
        search_var = tk.StringVar()
        summary_var = tk.StringVar(value="")
        top = ttk.Frame(dialog); top.pack(fill="x", padx=7, pady=7)
        ttk.Label(top, text="比較フォルダー:").pack(side="left")
        ttk.Entry(top, textvariable=folder_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Label(top, text="関数検索:").pack(side="left", padx=(8, 2))
        ttk.Entry(top, textvariable=search_var, width=24).pack(side="left", padx=2)
        state = {"comparisons": [], "visible": {}}
        tree = ttk.Treeview(dialog, columns=("status", "path"), show="tree headings", selectmode="extended")
        tree.heading("#0", text="関数名"); tree.heading("status", text="状態"); tree.heading("path", text="サンプル関数ファイル")
        tree.column("#0", width=330); tree.column("status", width=150); tree.column("path", width=520)
        tree.pack(fill="both", expand=True, padx=7, pady=4)
        tree.tag_configure("different", foreground="#b36b00")
        tree.tag_configure("missing_source", foreground="#a00000")
        tree.tag_configure("duplicate", foreground="#a00000")
        status_labels = {"match": "一致", "different": "不一致", "missing_source": "ソース側に未登録", "duplicate": "サンプル側で重複"}

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
            for item in state["comparisons"]:
                counts[item["status"]] += 1
                paths = ", ".join(os.path.relpath(value["path"], root) for value in item["fragments"])
                searchable = "{} {} {}".format(item["name"], paths, status_labels[item["status"]]).casefold()
                if needle and needle not in searchable:
                    continue
                iid = tree.insert("", "end", text=item["name"],
                                  values=(status_labels[item["status"]], paths), tags=(item["status"],))
                state["visible"][iid] = item
                shown += 1
            summary_var.set("表示{} / 全{}件 / 一致{} / 不一致{} / 未登録{} / 重複{}".format(
                shown, len(state["comparisons"]), counts["match"], counts["different"],
                counts["missing_source"], counts["duplicate"]))

        def refresh():
            source, root, folder = self.editor.get("1.0", "end-1c"), self.fragment_root(), folder_var.get()
            def completed(comparisons):
                if not dialog_alive(): return
                state["comparisons"] = comparisons
                populate()
            def failed(error):
                if dialog_alive(): messagebox.showwarning("サンプル関数チェック", str(error), parent=dialog)
            self.run_background("sample_function_check", "サンプル関数を比較中",
                                lambda: compare_sample_function_folder(source, root, folder), completed, failed)

        def choose_folder():
            selected = filedialog.askdirectory(parent=dialog, initialdir=folder_var.get() or self.fragment_root())
            if selected:
                folder_var.set(selected); self.fragment_folder.set(selected); refresh()

        def selected_items():
            return [state["visible"][iid] for iid in tree.selection() if iid in state["visible"]]

        def mismatch_names(for_source, selected_only=False):
            allowed = ("different", "missing_source") if for_source else ("different",)
            source_items = selected_items() if selected_only else state["comparisons"]
            return [item["name"] for item in source_items if item["status"] in allowed]

        def library_to_source(selected_only=False):
            names = mismatch_names(True, selected_only)
            if not names:
                messagebox.showinfo("サンプル関数チェック", "ソースへ反映する不一致はありません。", parent=dialog); return
            if not messagebox.askyesno("サンプル関数 → ソース", "{}件の関数を現在のソースへ反映しますか？".format(len(names)), parent=dialog): return
            source, comparisons = self.editor.get("1.0", "end-1c"), list(state["comparisons"])
            def completed(updated):
                if not dialog_alive(): return
                self.set_editor_content(updated, self.current_path)
                self.editor_dirty = True; self.update_editor_view(); refresh()
                self.status.set("サンプル関数からソースへ{}件反映しました。保存してください。".format(len(names)))
            self.run_background("sample_to_source", "サンプル関数をソースへ反映中",
                                lambda: update_source_sample_functions(source, comparisons, names), completed)

        def source_to_library(selected_only=False):
            names = mismatch_names(False, selected_only)
            if not names:
                messagebox.showinfo("サンプル関数チェック", "サンプル関数へ反映する不一致はありません。", parent=dialog); return
            if not messagebox.askyesno("ソース → サンプル関数", "{}件のサンプル関数を現在のソース内容で更新しますか？".format(len(names)), parent=dialog): return
            source, comparisons = self.editor.get("1.0", "end-1c"), list(state["comparisons"])
            def completed(changed):
                if not dialog_alive(): return
                refresh(); self.refresh_index(); self.refresh_registered_fragment_choices()
                self.status.set("ソースからサンプル関数{}件（{}ファイル）を更新しました。".format(len(names), len(changed)))
            self.run_background("source_to_samples", "ソース内容をサンプル関数へ反映中",
                                lambda: update_sample_function_fragments(source, comparisons, names), completed)

        def fragment_id_for(item):
            if len(item.get("fragments", [])) != 1:
                return None
            wanted = os.path.abspath(item["fragments"][0]["path"])
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
            fragment_id = fragment_id_for(items[0])
            if not fragment_id:
                messagebox.showwarning("関数置換", "サンプル関数の登録情報を特定できません。", parent=dialog); return
            dialog.destroy()
            self.load_fragment_for_editing(fragment_id)

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
            source_tree = ttk.Treeview(source_frame, columns=("origin",), show="tree headings", selectmode="browse")
            source_tree.heading("#0", text="関数名"); source_tree.heading("origin", text="取得元")
            source_tree.column("#0", width=240); source_tree.column("origin", width=280)
            source_tree.pack(fill="both", expand=True, padx=5, pady=(0, 5))
            target_filter = ttk.Frame(target_frame); target_filter.pack(fill="x", padx=5, pady=5)
            ttk.Label(target_filter, text="検索:").pack(side="left")
            ttk.Entry(target_filter, textvariable=target_search_var).pack(side="left", fill="x", expand=True, padx=3)
            target_tree = ttk.Treeview(target_frame, columns=("line",), show="tree headings", selectmode="extended")
            target_tree.heading("#0", text="関数名"); target_tree.heading("line", text="現在ソースの行")
            target_tree.column("#0", width=300); target_tree.column("line", width=140)
            target_tree.pack(fill="both", expand=True, padx=5, pady=(0, 5))

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
                detail = "\nプロジェクト内の同名関数の使用箇所にも反映します。" if use_everywhere else ""
                if not messagebox.askyesno(
                        "関数置換",
                        "置換元: {}\n反映先: {}{}\n\n反映しますか？".format(
                            source["name"], ", ".join(row["name"] for row in target_rows), detail), parent=picker):
                    return
                current_source = self.editor.get("1.0", "end-1c")
                try:
                    updated = replace_class_functions(current_source, function_texts)
                except (SyntaxError, ValueError) as error:
                    messagebox.showerror("関数置換", str(error), parent=picker); return
                if updated == current_source:
                    messagebox.showinfo("関数置換", "反映対象に変更はありません。", parent=picker); return
                self.set_editor_content(updated, self.current_path)
                self.editor_dirty = True; self.update_editor_view(); populate_targets(); refresh()
                if not use_everywhere:
                    self.status.set("関数を{}件置換しました。現在のソースを保存してください。".format(len(function_texts)))
                    messagebox.showinfo("関数置換", "現在のソースへ反映しました。\n保存してください。", parent=picker)
                    return
                current_path = os.path.abspath(self.current_path) if self.current_path else ""
                disk_paths = [path for path in self.files if str(path).lower().endswith(".py")
                              and os.path.abspath(path) != current_path]

                def completed(changed_paths):
                    self.refresh_index(); refresh()
                    parent = picker if picker.winfo_exists() else self
                    messagebox.showinfo("使用箇所へ反映", "{}ファイルへ反映しました。\n現在のソースは保存してください。".format(
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
                changed_paths = propagate_sample_functions(disk_paths, function_texts)
                try:
                    updated_current = replace_class_functions(current_source, function_texts)
                except (SyntaxError, ValueError):
                    updated_current = current_source
                return changed_paths, updated_current

            def completed(result):
                if not dialog_alive(): return
                changed_paths, updated_current = result
                current_changed = updated_current != current_source
                if current_changed:
                    self.set_editor_content(updated_current, self.current_path)
                    self.editor_dirty = True
                    self.update_editor_view()
                self.refresh_index(); refresh()
                messagebox.showinfo(
                    "使用箇所へ反映",
                    "{}ファイルへ反映しました。{}".format(
                        len(changed_paths) + (1 if current_changed else 0),
                        "現在のソースは保存してください。" if current_changed else ""), parent=dialog)
            self.run_background("sample_usage_replace", "サンプル関数を使用箇所へ反映中", worker, completed)

        ttk.Button(top, text="フォルダー選択", command=choose_folder).pack(side="left", padx=2)
        ttk.Button(top, text="再チェック", command=refresh).pack(side="left", padx=2)
        search_var.trace_add("write", lambda *args: self.debounce("sample_function_search", 120, populate))
        selected_actions = ttk.Frame(dialog); selected_actions.pack(fill="x", padx=7, pady=(2, 0))
        ttk.Button(selected_actions, text="関数を選んで置換...",
                   command=open_replacement_picker).pack(side="left", padx=3)
        ttk.Button(selected_actions, text="選択 サンプル関数 → 現在ソース",
                   command=lambda: library_to_source(True)).pack(side="left", padx=3)
        ttk.Button(selected_actions, text="選択 現在ソース → サンプル関数",
                   command=lambda: source_to_library(True)).pack(side="left", padx=3)
        ttk.Button(selected_actions, text="選択サンプルを使用箇所すべてへ反映",
                   command=apply_to_all_usages).pack(side="left", padx=3)
        ttk.Button(selected_actions, text="編集", command=edit_selected).pack(side="right", padx=3)
        ttk.Button(selected_actions, text="削除", command=delete_selected).pack(side="right", padx=3)
        bottom = ttk.Frame(dialog); bottom.pack(fill="x", padx=7, pady=7)
        ttk.Label(bottom, textvariable=summary_var).pack(side="left")
        ttk.Button(bottom, text="画像検知も ソース → 登録設定", command=lambda: (
            self.image_library_apply_target.set("ソース編集"), self.load_image_detection_from_source())).pack(side="right", padx=3)
        ttk.Button(bottom, text="不一致をすべて ソース → サンプル関数", command=source_to_library).pack(side="right", padx=3)
        ttk.Button(bottom, text="不一致をすべて サンプル関数 → ソース", command=library_to_source).pack(side="right", padx=3)
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
        initializer = textwrap.dedent(self.fragment_initializer.get("1.0", "end-1c")).strip("\n")
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
        try:
            os.makedirs(root, exist_ok=True)
            with open(metadata_path, "w", encoding="utf-8", newline="\n") as file:
                json.dump(metadata, file, ensure_ascii=False, indent=2)
            with open(body_path, "w", encoding="utf-8", newline="\n") as file:
                file.write(self.fragment_body.get("1.0", "end-1c") + "\n")
        except OSError as error:
            messagebox.showerror("Fragment", str(error), parent=self)
            return
        self.refresh_index()
        self.show_file(body_path)
        self.status.set(self.ui_text(("Updated" if self.editing_fragment_id else "Created") + " sample function: " + metadata["name"],
                                     ("サンプル関数を更新しました: " if self.editing_fragment_id else "サンプル関数を登録しました: ") + metadata["name"]))
        self.fragment_tag_picker.refresh_choices()
        self.refresh_catalog_tag_choices()
        self.rebuild_catalog_folder_tree()
        self.refresh_registered_fragment_choices(select=self.editing_fragment_id)
        self.refresh_sample_lists_tab(select=self.sample_list_name.get().strip())

    def fragment_tag_choices(self):
        return [tag for item in self.fragment_catalog() for tag in item.get("tags", [])]

    def refresh_registered_fragment_choices(self, select=None):
        items = self.fragment_catalog()
        self.registered_fragment_items = items
        labels = ["{}  ({})".format(item.get("name", item["id"]), item["id"]) for item in items]
        if hasattr(self, "registered_fragment_combo"):
            self.registered_fragment_combo.configure(values=labels)
            target = select or self.editing_fragment_id
            index = next((i for i, item in enumerate(items) if item["id"] == target), None)
            if index is not None: self.registered_fragment_choice.set(labels[index])
        if hasattr(self, "sample_preview_fragment_combo"):
            self._refresh_preview_fragment_choices()

    def _registered_fragment_id(self):
        value = self.registered_fragment_choice.get()
        labels = [str(item) for item in self.registered_fragment_combo.cget("values")]
        try: return self.registered_fragment_items[labels.index(value)]["id"]
        except (ValueError, IndexError): return None

    def edit_registered_fragment(self):
        fragment_id = self._registered_fragment_id()
        if fragment_id: self.load_fragment_for_editing(fragment_id)

    def delete_registered_fragment(self):
        fragment_id = self._registered_fragment_id()
        if fragment_id: self.delete_fragment(fragment_id)

    def cancel_fragment_edit(self):
        self.editing_fragment_id = None
        self.fragment_name.set("new_fragment")
        self.fragment_tag_picker.set_tags([])
        self.fragment_folder.set(self.fragment_root())
        for widget in (self.fragment_imports, self.fragment_class_vars, self.fragment_initializer, self.fragment_body): widget.delete("1.0", "end")
        self.fragment_body.insert("1.0", "# @pokedev-fragment: new_fragment\n# Inserted into the selected Step user block.\n")
        self.fragment_save_button.configure(text="サンプルとして保存")
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

    def load_fragment_for_editing(self, fragment_id):
        try:
            metadata, body, metadata_path, body_path = load_fragment(self.fragment_root(), fragment_id)
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("Fragment", str(error), parent=self); return
        self.editing_fragment_id = fragment_id
        self.fragment_name.set(metadata.get("name", ""))
        self.fragment_tag_picker.set_tags(metadata.get("tags", []))
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
        self.fragment_save_button.configure(text="変更を保存")
        self.workspace_tabs.select(self.sample_functions_workspace)
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
        self._refresh_preview_fragment_choices()
        try:
            text = self._sample_program_source(name)
            compile(text, "<sample-list-preview>", "exec")
        except (OSError, ValueError, KeyError) as error:
            text = "Preview error: " + str(error)
        except SyntaxError as error:
            text = "Preview syntax error: " + str(error)
        self.sample_list_preview.configure(state="normal"); self.sample_list_preview.delete("1.0", "end")
        self.sample_list_preview.insert("1.0", text); self.sample_list_preview.configure(state="disabled")

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

        ttk.Label(controls, text="登録済みサンプルリスト（版付きJSON・入れ子対応）").grid(column=0, columnspan=3, row=0, padx=6, pady=(0, 4), sticky="w")
        ttk.Label(controls, text="リスト名:").grid(column=0, row=1, padx=6, pady=3, sticky="w")
        ttk.Entry(controls, textvariable=self.sample_list_name).grid(column=1, columnspan=2, row=1, padx=4, pady=3, sticky="ew")
        ttk.Label(controls, text="検索:").grid(column=0, row=2, padx=6, pady=3, sticky="w")
        ttk.Entry(controls, textvariable=self.sample_list_filter).grid(column=1, columnspan=2, row=2, padx=4, pady=3, sticky="ew")
        self.sample_list_filter.trace_add("write", lambda *_: self.refresh_sample_lists_tab())
        self.sample_lists_tree = tk.Listbox(controls, exportselection=False, height=5)
        self.sample_lists_tree.grid(column=0, columnspan=3, row=3, padx=6, pady=3, sticky="nsew")
        self.sample_lists_tree.bind("<<ListboxSelect>>", self.load_selected_sample_list)
        ttk.Button(controls, text="新規作成 / 更新", command=self.create_sample_list).grid(column=1, row=4, padx=3, pady=3, sticky="ew")
        ttk.Button(controls, text="リスト削除", command=self.delete_sample_list).grid(column=2, row=4, padx=3, pady=3, sticky="ew")
        ttk.Label(controls, text="リストタグ:").grid(column=0, columnspan=3, row=5, padx=6, pady=(5, 2), sticky="w")
        self.sample_list_tag_picker = TagPicker(controls, self.sample_list_tag_choices)
        self.sample_list_tag_picker.grid(column=0, columnspan=3, row=6, padx=6, pady=3, sticky="nsew")
        self.sample_list_details = tk.StringVar(value="選択したリストのサンプル数を表示します。")
        ttk.Label(controls, textvariable=self.sample_list_details).grid(column=0, columnspan=3, row=7, padx=6, pady=3, sticky="w")
        self.sample_member_list = tk.Listbox(controls, exportselection=False, height=5)
        self.sample_member_list.grid(column=0, columnspan=2, row=8, padx=6, pady=3, sticky="nsew")
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
        self.sample_catalog_folder_tree.pack(side="left", fill="both", expand=True)
        folder_scroll = ttk.Scrollbar(folder_frame, orient="vertical", command=self.sample_catalog_folder_tree.yview)
        folder_scroll.pack(side="right", fill="y")
        self.sample_catalog_folder_tree.configure(yscrollcommand=folder_scroll.set)
        self.sample_catalog_folder_tree.bind("<ButtonRelease-1>", self.toggle_catalog_folder)
        self.sample_catalog_folder_tree.bind("<space>", self.toggle_catalog_folder)
        ttk.Button(controls, text="候補を検索", command=self.refresh_sample_catalog).grid(column=2, row=14, padx=3, pady=2, sticky="e")
        self.sample_catalog_list = tk.Listbox(controls, exportselection=False, height=5)
        self.sample_catalog_list.grid(column=0, columnspan=2, row=14, rowspan=2, padx=6, pady=3, sticky="nsew")
        self.sample_catalog_list.bind("<Double-Button-1>", self.open_selected_catalog_fragment)
        self.sample_catalog_list.bind("<Return>", lambda event: self.edit_selected_catalog_fragment())
        candidate_actions = ttk.Frame(controls)
        candidate_actions.grid(column=2, row=15, padx=3, pady=2, sticky="e")
        ttk.Button(candidate_actions, text="変更", command=self.edit_selected_catalog_fragment).pack(side="left", padx=1)
        ttk.Button(candidate_actions, text="+ 追加", command=self.add_catalog_sample_to_list).pack(side="left", padx=1)
        ttk.Label(controls, text="登録済みサンプルリスト候補:").grid(column=0, columnspan=3, row=16, padx=6, pady=(5, 2), sticky="w")
        self.sample_nested_list = tk.Listbox(controls, exportselection=False, height=4)
        self.sample_nested_list.grid(column=0, columnspan=2, row=17, padx=6, pady=3, sticky="nsew")
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

    def sample_list_tag_choices(self):
        data = self._read_sample_lists()
        return [tag for item in data["lists"].values() for tag in item.get("tags", [])]

    def refresh_sample_lists_tab(self, select=None, member=None):
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
        self.refresh_sample_catalog()
        if target:
            self._display_sample_list(target, member)
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

    def _display_sample_list(self, name, selected_member=None):
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
        self.refresh_sample_list_preview()

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

    def refresh_sample_apply_lists(self):
        if not hasattr(self, "sample_apply_list"):
            return
        self.sample_apply_list.delete(0, "end")
        for name in sorted(self._read_sample_lists()["lists"]):
            self.sample_apply_list.insert("end", name)
        self.refresh_sample_apply_image_tree()

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

    def _image_code_for_target_names(self, target_names):
        names = list(dict.fromkeys(str(name) for name in target_names if str(name).strip()))
        if not names:
            return ""
        data = self._read_image_library()
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
        image_targets = preview.get("image_targets", [])
        image_code = self._image_code_for_target_names(image_targets)
        missing_image_targets = self._missing_image_target_names(image_targets)
        summary = self.ui_text(
            "Apply '{}':\n\n{}\n\nConflicts / changes are shown before insertion. Continue?",
            "「{}」を反映します。\n\n{}\n\n競合・変更内容を確認して挿入を続けますか？").format(
                name, "\n".join("- " + item for item in conflicts) if conflicts
                else self.ui_text("No conflicts detected.", "競合は検出されませんでした。"))
        if image_targets:
            summary += "\n\n必要な画像検知{}件も同時に反映します。".format(len(image_targets))
        if missing_image_targets:
            summary += "\n画像ライブラリ未登録（例外判定として保持）: " + ", ".join(missing_image_targets)
        if not messagebox.askyesno(self.ui_text("Apply sample list", "サンプルリストの反映"), summary, parent=self):
            return
        merged = merge_preview(source, preview, name)
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

    def _sample_program_source(self, name):
        data = self._read_sample_lists()
        preview = compose_preview(self.fragment_root(), data, name)
        safe = python_identifier(name) + "SampleCommand"
        imports = self._generated_region("IMPORTS", "\n".join(preview["imports"]), "")
        variables = self._generated_region("CLASS_VARIABLES", "\n".join("    " + line for line in preview["class_variables"]), "    ")
        initializer_body = "\n".join(self._indent_source(value, "        ") for value in preview.get("initializers", []))
        initializers = self._generated_region("INITIALIZERS", initializer_body or "        pass", "        ")
        step_blocks, helper_blocks = [], []
        for member in resolve_members(data, name):
            metadata, body, _, _ = load_fragment(self.fragment_root(), member["id"])
            if metadata.get("target") == "step_user_block":
                step_blocks.append(self._fragment_region(member["id"], body, "        "))
            else:
                helper_blocks.append(self._fragment_region(member["id"], body, "    "))
        step_source = "\n".join(step_blocks)
        helper_source = "\n".join(helper_blocks)
        image_code = self._image_code_for_target_names(preview.get("image_targets", []))
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
            if self.image_library_name.get().strip() in ("", "PROFILE"):
                self.image_library_name.set(os.path.splitext(os.path.basename(path))[0].upper())

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
        data, needle = self._read_image_library(), self.image_library_search.get().strip().lower()
        root = self.image_library_tree.insert("", "end", text="Template", values=("", "", "", ""), open=True)
        folder_nodes, target_nodes = {}, {}
        for name in sorted(data["targets"], key=str.lower):
            item = data["targets"][name]; searchable = " ".join([name, item.get("description", "")] + item.get("tags", []) + [v.get("template_path", "") for v in item["variants"]]).lower()
            if needle and needle not in searchable: continue
            for index, variant in enumerate(item["variants"]):
                parts = variant.get("template_path", "").replace("\\", "/").split("/")
                if parts and parts[0].lower() == "template": parts = parts[1:]
                parent, accumulated = root, []
                for folder in parts[:-1]:
                    accumulated.append(folder); key = "/".join(accumulated)
                    if key not in folder_nodes:
                        folder_nodes[key] = self.image_library_tree.insert(parent, "end", text=folder, values=("", "", "", folder), open=bool(needle))
                    parent = folder_nodes[key]
                target_key = (parent, name)
                if target_key not in target_nodes:
                    target_nodes[target_key] = self.image_library_tree.insert(parent, "end", text="{} [{}]".format(name, item.get("operator", "OR")),
                        values=(item.get("description", ""), "", "", ", ".join(item.get("tags", []))), open=True)
                iid = self.image_library_tree.insert(target_nodes[target_key], "end", text="パターン{}".format(index + 1),
                    values=(variant.get("template_path", ""), variant.get("threshold", 0.8), ",".join(map(str, variant.get("crop", []))), ", ".join(item.get("tags", []))))
                self.image_library_tree_ids[iid] = (name, index)
                if select == (name, index): self.image_library_tree.selection_set(iid); self.image_library_tree.see(iid)

    def load_selected_image_library_variant(self, event=None):
        selected = self.image_library_tree.selection()
        if not selected or selected[0] not in self.image_library_tree_ids: return
        name, index = self.image_library_tree_ids[selected[0]]; self.image_library_selected_variant = (name, index)
        variant = self._read_image_library()["targets"][name]["variants"][index]
        path = variant.get("template_path", "")
        if path and not os.path.isabs(path): path = os.path.join(os.path.dirname(self.template_root()), path)
        self.image_library_name.set(name); self.image_library_path.set(path)
        target = self._read_image_library()["targets"][name]
        self.image_library_description.set(target.get("description", ""))
        self.image_library_target_operator.set(target.get("operator", "OR"))
        self.image_library_threshold.set(variant.get("threshold", 0.8)); self.image_library_crop.set(",".join(map(str, variant.get("crop", [0,0,0,0]))))
        self.image_library_gray.set(bool(variant.get("use_gray", True))); self.image_library_show_value.set(bool(variant.get("show_value", False)))
        self.image_library_match_color.set(variant.get("match_color", "blue"))
        self.image_library_no_match_color.set(variant.get("no_match_color", "red"))

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
        editor = tk.Text(dialog, wrap="none", background="#1e1e1e", foreground="#d4d4d4"); editor.pack(fill="both", expand=True)
        editor.insert("1.0", code); editor.configure(state="disabled"); dialog.geometry("900x600")

    def apply_image_detection_code(self):
        try: code = self._current_image_detection_code()
        except ValueError as error: messagebox.showwarning("画像検知", str(error), parent=self); return
        editor = self.sample_program_editor if self.image_library_apply_target.get() == "サンプルプログラム" else self.editor
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
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview); scrollbar.pack(side="right", fill="y"); tree.configure(yscrollcommand=scrollbar.set)
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
        if self.completion_mode.get() == "右タブ":
            self.debounce("editor_completion_tab", 80, self.refresh_completion)
        if hasattr(self, "source_functions_tab") and \
                self.right_tabs.select() == str(self.source_functions_tab):
            self.debounce("source_function_editor_tab", 80, self.refresh_source_functions)

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
        executable = self.vscode_executable or self.find_vscode_executable()
        if not executable:
            messagebox.showwarning("VS Code", "VS Codeが見つかりません。", parent=self); return
        line = int(self.editor.index("insert").split(".")[0])
        target = "{}:{}".format(os.path.abspath(self.current_path), line)
        try:
            if executable.lower().endswith((".cmd", ".bat")):
                command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", executable, "--goto", target]
                subprocess.Popen(command, creationflags=0x08000000)
            else:
                subprocess.Popen([executable, "--goto", target])
        except OSError as error:
            messagebox.showerror("VS Code", str(error), parent=self); return
        self.status.set("VS Codeで開きました: {} 行{}".format(os.path.basename(self.current_path), line))

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
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(self.editor.get("1.0", "end-1c"))
        except OSError as error:
            messagebox.showerror("Save", str(error))
            return False
        self.current_path = path
        self.editor_dirty = False
        self.editor.edit_modified(False)
        if self.active_editor_tab in self.editor_documents:
            document = self.editor_documents[self.active_editor_tab]
            document.update({"path": path, "content": self.editor.get("1.0", "end-1c"), "dirty": False})
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

    def _find_matches(self):
        needle = self.find_text.get()
        if not needle:
            return []
        matches = []
        start = "1.0"
        count = tk.IntVar(value=0)
        while True:
            found = self.editor.search(needle, start, stopindex="end", nocase=True, count=count)
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
        self.editor.tag_remove("find", "1.0", "end")
        total = len(self._find_matches())
        self.find_result_text.set("0 / {}".format(total))

    def _show_find_match(self, matches, index):
        self.editor.tag_remove("find", "1.0", "end")
        if not matches:
            self.find_result_text.set("0 / 0")
            return
        index %= len(matches)
        found, end = matches[index]
        self.editor.tag_configure("find", background="#515c6a")
        self.editor.tag_add("find", found, end)
        self.editor.mark_set("insert", end)
        self.editor.see(found)
        self.editor.focus_set()
        self.find_result_text.set("{} / {}".format(index + 1, len(matches)))

    def find_next(self):
        matches = self._find_matches()
        if not matches:
            self._show_find_match([], 0)
            return
        ranges = self.editor.tag_ranges("find")
        if ranges:
            current = self.editor.index(ranges[0])
            index = next((i + 1 for i, item in enumerate(matches)
                          if self.editor.compare(item[0], "==", current)), 0)
        else:
            cursor = self.editor.index("insert")
            index = next((i for i, item in enumerate(matches)
                          if self.editor.compare(item[0], ">=", cursor)), 0)
        self._show_find_match(matches, index)

    def find_previous(self):
        matches = self._find_matches()
        if not matches:
            self._show_find_match([], 0)
            return
        ranges = self.editor.tag_ranges("find")
        if ranges:
            current = self.editor.index(ranges[0])
            index = next((i - 1 for i, item in enumerate(matches)
                          if self.editor.compare(item[0], "==", current)), len(matches) - 1)
        else:
            cursor = self.editor.index("insert")
            candidates = [i for i, item in enumerate(matches)
                          if self.editor.compare(item[0], "<", cursor)]
            index = candidates[-1] if candidates else len(matches) - 1
        self._show_find_match(matches, index)

    def replace_one(self):
        needle = self.find_text.get()
        if not needle:
            return
        ranges = self.editor.tag_ranges("find")
        if ranges:
            self.editor.delete(ranges[0], ranges[1])
            self.editor.insert(ranges[0], self.replace_text.get())
        self.find_next()

    def replace_all(self):
        needle = self.find_text.get()
        if not needle:
            return
        content = self.editor.get("1.0", "end-1c")
        count = content.lower().count(needle.lower())
        if not count:
            return
        content = re.sub(re.escape(needle), self.replace_text.get(), content, flags=re.IGNORECASE)
        self.set_editor_content(content, self.current_path)
        self.editor_dirty = True
        self.update_editor_view()
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
        import_box = tk.Text(dialog, height=3, width=54)
        import_box.grid(column=1, row=3, padx=7, pady=4, sticky="ew")
        ttk.Label(dialog, text="Requires (comma):").grid(column=0, row=4, padx=7, pady=4, sticky="w")
        ttk.Entry(dialog, textvariable=requires, width=44).grid(column=1, row=4, padx=7, pady=4, sticky="ew")
        ttk.Label(dialog, text="Fragment code:").grid(column=0, row=5, padx=7, pady=4, sticky="nw")
        body = tk.Text(dialog, height=14, width=66, undo=True)
        body.insert("1.0", "# @pokedev-fragment: new_fragment\n# Inserted into the selected Step user block.\n")
        body.grid(column=1, row=5, padx=7, pady=4, sticky="nsew")
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
        self.run_background("local_explorer", "コマンド一覧を更新中", worker, completed)

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
        tag_list = tk.Listbox(tag_box, height=4, exportselection=False)
        tag_list.grid(column=0, row=1, padx=5, pady=4, sticky="ew")
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
        self.run_background("refresh_index", "ソース索引を更新中", worker, completed)

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


if __name__ == "__main__":
    default_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    DevStudio(sys.argv[1] if len(sys.argv) > 1 else default_root).mainloop()
