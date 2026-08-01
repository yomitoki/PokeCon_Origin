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
import json
import os
import queue
import re
import subprocess
import sys
import threading
import textwrap
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from CommandBuilder import command_path, folder_segment, python_identifier, template_source
from SampleLibrary import (catalog, compose_preview, detect_conflicts, load_fragment,
                           load_library, merge_preview, resolve_members, save_library)
from SampleProgramLoader import inspect_sample_program


PYTHON_SUFFIXES = (".py", ".pyfrag")
TAG_RE = re.compile(r"@pokedev\s*:\s*(.+)", re.IGNORECASE)
BEGIN_RE = re.compile(r"@pokedev-begin\s*:\s*(.+)", re.IGNORECASE)
END_RE = re.compile(r"@pokedev-end", re.IGNORECASE)


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
        self.title("PokeCon Dev Studio")
        self.geometry("1280x780")
        self.minsize(900, 560)
        self.root_dir = tk.StringVar(value=os.path.abspath(initial_root))
        self.search_text = tk.StringVar()
        self.tag_text = tk.StringVar()
        self.files = []
        self.fragments = []
        self.editing_fragment_id = None
        self.search_hits = []
        self.current_path = None
        self.editor_dirty = False
        self.editor_documents = {}
        self.active_editor_tab = None
        self._switching_editor_tab = False
        self.ui_state = self.load_ui_state()
        self.run_process = None
        self.run_queue = queue.Queue()
        self.find_text = tk.StringVar()
        self.replace_text = tk.StringVar()
        self.ui_language = tk.StringVar(value="日本語")
        self._build()
        self._build_menu()
        self.apply_language()
        self.after_idle(self.set_default_pane_sizes)
        self.after(100, self.restore_ui_state)
        self.protocol("WM_DELETE_WINDOW", self.close_dev_studio)
        self.refresh_index()
        self.refresh_local_explorer()
        self.refresh_sample_apply_lists()
        self.refresh_sample_lists_tab()
        self.refresh_registered_fragment_choices()

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
                 "active_path": self.current_path, "documents": documents}
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
        ttk.Button(edit_tools, text="Check syntax", command=self.check_syntax).pack(side="left")
        ttk.Button(edit_tools, text="Run  F5", command=self.run_current).pack(side="left", padx=(8, 3))
        ttk.Button(edit_tools, text="Stop", command=self.stop_run).pack(side="left")
        ttk.Label(edit_tools, text="   Find:").pack(side="left")
        find_entry = ttk.Entry(edit_tools, textvariable=self.find_text, width=16)
        find_entry.pack(side="left", padx=2)
        find_entry.bind("<Return>", lambda event: self.find_next())
        ttk.Button(edit_tools, text="Next", command=self.find_next).pack(side="left")
        ttk.Entry(edit_tools, textvariable=self.replace_text, width=16).pack(side="left", padx=(7, 2))
        ttk.Button(edit_tools, text="Replace", command=self.replace_one).pack(side="left")
        ttk.Button(edit_tools, text="All", command=self.replace_all).pack(side="left", padx=2)
        self.right_panel_button = ttk.Button(edit_tools, text="Hide right", command=self.toggle_right_panel)
        self.right_panel_button.pack(side="right")
        self.workspace_tabs = ttk.Notebook(self)
        self.workspace_tabs.pack(fill="both", expand=True, padx=7, pady=(0, 7), before=top)
        source_workspace = ttk.Frame(self.workspace_tabs)
        sample_functions_workspace = ttk.Frame(self.workspace_tabs)
        sample_lists_workspace = ttk.Frame(self.workspace_tabs)
        sample_program_workspace = ttk.Frame(self.workspace_tabs)
        self.workspace_tabs.add(source_workspace, text="🟦 ソース編集")
        self.workspace_tabs.add(sample_functions_workspace, text="🟩 サンプル関数")
        self.workspace_tabs.add(sample_lists_workspace, text="🟨 サンプルリスト")
        self.workspace_tabs.add(sample_program_workspace, text="🟦 サンプルプログラム")
        self.workspace_tabs.tab(source_workspace, padding=(10, 4))
        self.workspace_tabs.tab(sample_functions_workspace, padding=(10, 4))
        self.workspace_tabs.tab(sample_lists_workspace, padding=(10, 4))
        self.workspace_tabs.tab(sample_program_workspace, padding=(10, 4))
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

        ttk.Label(sample_apply_tab, text="Apply saved sample lists to the current source / selected Step.").pack(anchor="w", padx=4, pady=4)
        self.sample_apply_list = tk.Listbox(sample_apply_tab, exportselection=False)
        self.sample_apply_list.pack(fill="both", expand=True, padx=4, pady=4)
        ttk.Button(sample_apply_tab, text="Refresh lists", command=self.refresh_sample_apply_lists).pack(side="left", padx=4, pady=4)
        ttk.Button(sample_apply_tab, text="Apply selected", command=self.apply_selected_sample_list).pack(side="right", padx=4, pady=4)

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
        step_hierarchy_tab = ttk.Frame(self.right_tabs)
        self.right_tabs.add(image_targets_tab, text="Image detection")
        self.right_tabs.add(step_hierarchy_tab, text="Step hierarchy")
        self.step_hierarchy_tab = step_hierarchy_tab
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
                                    wrap="none", background="#f0f0f0", foreground="#666666")
        self.line_numbers.pack(fill="y", side="left")
        self.editor = tk.Text(editor_box, wrap="none", undo=True, background="#1e1e1e", foreground="#d4d4d4",
                              insertbackground="white", selectbackground="#264f78")
        self.editor.pack(fill="both", expand=True, side="left")
        editor_scroll = ttk.Scrollbar(editor_box, orient="vertical", command=self._scroll_editor)
        editor_scroll.pack(fill="y", side="right")
        self.editor.configure(yscrollcommand=lambda first, last: self._sync_editor_scroll(editor_scroll, first, last))
        self.editor.bind("<<Modified>>", self.editor_modified)
        self.editor.bind("<KeyRelease>", lambda event: self.after_idle(self.update_editor_view))
        self.editor.bind("<Control-s>", lambda event: (self.save_current(), "break"))
        self.editor.bind("<F5>", lambda event: (self.run_current(), "break"))
        self.editor.tag_configure("keyword", foreground="#569cd6")
        self.editor.tag_configure("string", foreground="#ce9178")
        self.editor.tag_configure("comment", foreground="#6a9955")
        editor_actions = ttk.Frame(center)
        editor_actions.pack(fill="x", pady=(4, 0))
        ttk.Button(editor_actions, text="Save output as...", command=self.save_output).pack(side="left")
        ttk.Button(editor_actions, text="Clear", command=lambda: self.editor.delete("1.0", "end")).pack(side="left", padx=4)
        console_frame = ttk.Labelframe(center, text="Run output")
        console_frame.pack(fill="x", pady=(5, 0))
        self.console = tk.Text(console_frame, height=8, wrap="word", background="#111111", foreground="#dddddd",
                               insertbackground="white", state="disabled")
        self.console.pack(fill="both", expand=True, padx=3, pady=3)
        self._build_image_targets_tab(image_targets_tab)
        self._build_step_hierarchy_tab(step_hierarchy_tab)
        self._build_sample_functions_tab(sample_functions_workspace)
        self._build_sample_lists_tab(sample_lists_workspace)
        self._build_sample_program_tab(sample_program_workspace)
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

    def _build_step_hierarchy_tab(self, parent):
        self.step_entry = tk.StringVar()
        self.step_loop = tk.BooleanVar(value=True)
        self.step_template_mode = tk.StringVar(value="Step (state transition / 状態遷移)")
        self.step_start = tk.StringVar(value="0 (_step_0)")
        self.special_step_entry = tk.StringVar()
        ttk.Label(parent, text="Add steps after creating a Step command. Apply rebuilds its generated Step skeleton.").grid(column=0, columnspan=3, row=0, padx=7, pady=(7, 3), sticky="w")
        ttk.Button(parent, text="Load current command", command=self.load_steps_from_editor).grid(column=3, row=0, padx=5, pady=(7, 3), sticky="e")
        ttk.Entry(parent, textvariable=self.step_entry).grid(column=0, columnspan=3, row=1, padx=7, pady=4, sticky="ew")
        self.step_tree = ttk.Treeview(parent, show="tree", height=15)
        self.step_tree.grid(column=0, columnspan=3, row=2, padx=7, pady=4, sticky="nsew")
        ttk.Button(parent, text="Add chapter", command=lambda: self.add_step_item("")).grid(column=0, row=3, padx=5, pady=4)
        ttk.Button(parent, text="Add child", command=lambda: self.add_step_item(self.step_tree.focus())).grid(column=1, row=3, padx=5, pady=4)
        ttk.Button(parent, text="Rename", command=self.rename_step_item).grid(column=2, row=3, padx=5, pady=4)
        ttk.Button(parent, text="Remove", command=self.remove_step_item).grid(column=3, row=3, padx=5, pady=4)
        ttk.Checkbutton(parent, text="Use loop to advance steps", variable=self.step_loop).grid(column=0, columnspan=2, row=4, padx=7, pady=3, sticky="w")
        ttk.Combobox(parent, state="readonly", width=34, textvariable=self.step_template_mode, values=("Step (state transition / 状態遷移)", "Step (nested chapters / 階層チャプター)")).grid(column=2, columnspan=2, row=4, padx=3, pady=3, sticky="e")
        ttk.Label(parent, text="First step:").grid(column=0, row=5, padx=7, pady=3, sticky="w")
        ttk.Combobox(parent, state="readonly", width=12, textvariable=self.step_start, values=("0 (_step_0)", "1 (_step_1)")).grid(column=1, row=5, padx=3, pady=3, sticky="w")
        ttk.Button(parent, text="Apply to current Step command", command=self.apply_steps_to_editor).grid(column=3, row=5, padx=5, pady=5, sticky="e")
        special_box = ttk.Labelframe(parent, text="Special steps (called explicitly, not in normal order)")
        special_box.grid(column=0, columnspan=4, row=6, padx=7, pady=(5, 7), sticky="nsew")
        ttk.Entry(special_box, textvariable=self.special_step_entry, width=24).pack(side="left", padx=4, pady=4)
        self.special_step_list = tk.Listbox(special_box, height=3, exportselection=False)
        self.special_step_list.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        ttk.Button(special_box, text="Add", command=self.add_special_step).pack(side="left", padx=2)
        ttk.Button(special_box, text="Remove", command=self.remove_special_step).pack(side="left", padx=4)
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

    def on_right_tool_tab_changed(self, event=None):
        if self.right_tabs.select() == str(self.step_hierarchy_tab):
            self.load_steps_from_editor(silent=True)

    def add_step_item(self, parent):
        label = self.step_entry.get().strip()
        if not label:
            label = "New child step" if parent else "New chapter"
        item = self.step_tree.insert(parent, "end", text=label, open=True)
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
        try:
            tree = ast.parse(self.editor.get("1.0", "end-1c"))
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
            if not silent:
                messagebox.showwarning("Step hierarchy", "The current source must be a generated Step command with STEP_LABELS.", parent=self)
            return
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

    def apply_steps_to_editor(self):
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

    def _build_image_targets_tab(self, parent):
        self.image_detection_targets = []
        self.image_target_name = tk.StringVar(value="target")
        self.image_target_path = tk.StringVar()
        self.image_target_threshold = tk.DoubleVar(value=0.80)
        self.image_target_roi = tk.StringVar(value="0,0,0,0")
        self.image_target_gray = tk.BooleanVar(value=False)
        self.image_target_resolution = tk.StringVar(value="0,0")
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
        self.image_target_tree = ttk.Treeview(parent, columns=("name", "image", "threshold", "roi", "mode", "resolution"), show="headings", height=12)
        for column, label, width in (("name", "Name", 110), ("image", "Image", 330), ("threshold", "Threshold", 72), ("roi", "ROI", 100), ("mode", "Mode", 82), ("resolution", "Reference", 95)):
            self.image_target_tree.heading(column, text=label)
            self.image_target_tree.column(column, width=width, stretch=(column == "image"))
        self.image_target_tree.grid(column=0, columnspan=6, row=3, padx=7, pady=(5, 5), sticky="nsew")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.image_target_tree.yview)
        scrollbar.grid(column=6, row=3, padx=(0, 5), pady=(5, 5), sticky="ns")
        self.image_target_tree.configure(yscrollcommand=scrollbar.set)
        self.image_target_tree.bind("<<TreeviewSelect>>", self.load_selected_image_target)
        controls = ttk.Frame(parent)
        controls.grid(column=0, columnspan=7, row=4, padx=7, pady=(0, 6), sticky="e")
        ttk.Button(controls, text="Add", command=self.add_image_target).pack(side="left", padx=2)
        ttk.Button(controls, text="Change selected", command=self.change_image_target).pack(side="left", padx=2)
        ttk.Button(controls, text="Remove selected", command=self.remove_image_target).pack(side="left", padx=2)
        ttk.Button(controls, text="Apply to current command", command=self.apply_image_targets_to_editor).pack(side="left", padx=(14, 2))
        parent.columnconfigure(3, weight=1)
        parent.rowconfigure(3, weight=1)

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
        ttk.Label(form, text="関数・処理コード:").grid(column=0, row=5, padx=6, pady=4, sticky="nw")
        ttk.Label(form, text="Tabは半角スペース4文字です。改行時はインデントを維持し、行番号のドラッグで複数行を選択できます。").grid(
            column=1, row=5, padx=6, pady=(0, 2), sticky="nw")
        fragment_editor_frame = ttk.Frame(form)
        fragment_editor_frame.grid(column=1, row=5, padx=6, pady=(24, 4), sticky="nsew")
        self.fragment_line_numbers = tk.Text(fragment_editor_frame, width=6, padx=4, takefocus=0, state="disabled",
                                             wrap="none", background="#252526", foreground="#858585",
                                             selectbackground="#264f78", cursor="arrow")
        self.fragment_line_numbers.pack(side="left", fill="y")
        self.fragment_body = tk.Text(fragment_editor_frame, height=20, undo=True, wrap="none", tabs=("4c",))
        self.fragment_body.insert("1.0", "# @pokedev-fragment: new_fragment\n# Inserted into the selected Step user block.\n")
        fragment_y = ttk.Scrollbar(fragment_editor_frame, orient="vertical", command=self._scroll_fragment_editor)
        fragment_y.pack(side="right", fill="y")
        fragment_x = ttk.Scrollbar(fragment_editor_frame, orient="horizontal", command=self.fragment_body.xview)
        fragment_x.pack(side="bottom", fill="x")
        self.fragment_body.pack(side="left", fill="both", expand=True)
        self.fragment_body.configure(
            yscrollcommand=lambda first, last: self._sync_fragment_scroll(fragment_y, first, last),
            xscrollcommand=fragment_x.set)
        for editor in (self.fragment_imports, self.fragment_class_vars, self.fragment_body):
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
        helpers.grid(column=2, columnspan=2, row=3, rowspan=3, padx=6, pady=4, sticky="ns")
        ttk.Button(helpers, text="関数枠を追加", command=self.insert_fragment_function_skeleton).pack(fill="x", padx=4, pady=(4, 2))
        ttk.Button(helpers, text="Step処理を追加", command=self.insert_fragment_step_skeleton).pack(fill="x", padx=4, pady=2)
        ttk.Button(helpers, text="Import例を追加", command=self.insert_fragment_import_examples).pack(fill="x", padx=4, pady=2)
        ttk.Button(helpers, text="クラス変数例を追加", command=self.insert_fragment_class_var_example).pack(fill="x", padx=4, pady=(2, 4))
        self.fragment_save_button = ttk.Button(form, text="サンプルとして保存", command=self.create_fragment_from_tab)
        self.fragment_save_button.grid(column=1, row=6, padx=6, pady=8, sticky="e")
        ttk.Button(form, text="サンプルライブラリを開く", command=self.open_fragment_library).grid(column=0, row=6, padx=6, pady=8, sticky="w")
        registered = ttk.Frame(form)
        registered.grid(column=2, columnspan=2, row=6, padx=6, pady=8, sticky="e")
        self.registered_fragment_choice = tk.StringVar()
        ttk.Label(registered, text="登録済みサンプル関数:").pack(side="left", padx=(0, 3))
        self.registered_fragment_combo = ttk.Combobox(registered, textvariable=self.registered_fragment_choice, state="readonly", width=34)
        self.registered_fragment_combo.pack(side="left", padx=2)
        ttk.Button(registered, text="変更", command=self.edit_registered_fragment).pack(side="left", padx=2)
        ttk.Button(registered, text="削除", command=self.delete_registered_fragment).pack(side="left", padx=2)
        ttk.Button(registered, text="新規へ戻る", command=self.cancel_fragment_edit).pack(side="left", padx=2)
        form.columnconfigure(1, weight=1)
        form.rowconfigure(5, weight=1)

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
        metadata = {"schema_version": 1, "name": self.fragment_name.get().strip() or safe_name,
                    "tags": self.fragment_tag_picker.get_tags(),
                    "imports": import_lines,
                    "class_variables": [item.strip() for item in self.fragment_class_vars.get("1.0", "end-1c").splitlines() if item.strip()],
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
        for widget in (self.fragment_imports, self.fragment_class_vars, self.fragment_body): widget.delete("1.0", "end")
        self.fragment_body.insert("1.0", "# @pokedev-fragment: new_fragment\n# Inserted into the selected Step user block.\n")
        self.fragment_save_button.configure(text="サンプルとして保存")
        self.status.set(self.ui_text("New sample-function mode", "サンプル関数の新規登録モード"))

    def delete_fragment(self, fragment_id):
        try:
            metadata, _, metadata_path, body_path = load_fragment(self.fragment_root(), fragment_id)
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("Fragment", str(error), parent=self); return
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
                                 metadata.get("name", fragment_id), detail), parent=self): return
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
                                              "リストからの参照は削除されましたが、ファイルを削除できませんでした: {}").format(error), parent=self); return
        if self.editing_fragment_id == fragment_id: self.cancel_fragment_edit()
        self.refresh_registered_fragment_choices(); self.refresh_sample_lists_tab(select=self.sample_list_name.get().strip())
        self.refresh_catalog_tag_choices(); self.rebuild_catalog_folder_tree()
        self.status.set(self.ui_text("Deleted registered sample function: ", "登録済みサンプル関数を削除しました: ") + metadata.get("name", fragment_id))

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
        return catalog(self.fragment_root())

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
        summary = self.ui_text(
            "Apply '{}':\n\n{}\n\nConflicts / changes are shown before insertion. Continue?",
            "「{}」を反映します。\n\n{}\n\n競合・変更内容を確認して挿入を続けますか？").format(
                name, "\n".join("- " + item for item in conflicts) if conflicts
                else self.ui_text("No conflicts detected.", "競合は検出されませんでした。"))
        if not messagebox.askyesno(self.ui_text("Apply sample list", "サンプルリストの反映"), summary, parent=self):
            return
        merged = merge_preview(source, preview, name)
        self.editor.delete("1.0", "end"); self.editor.insert("1.0", merged)
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
                                                   selectbackground="#264f78", cursor="arrow")
        self.sample_program_line_numbers.pack(side="left", fill="y")
        self.sample_program_editor = tk.Text(editor_frame, undo=True, wrap="none", tabs=("4c",),
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
        step_blocks, helper_blocks = [], []
        for member in resolve_members(data, name):
            metadata, body, _, _ = load_fragment(self.fragment_root(), member["id"])
            if metadata.get("target") == "step_user_block":
                step_blocks.append(self._fragment_region(member["id"], body, "        "))
            else:
                helper_blocks.append(self._fragment_region(member["id"], body, "    "))
        step_source = "\n".join(step_blocks)
        helper_source = "\n".join(helper_blocks)
        return ("#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n"
                "# Authored by PokeCon Dev Studio from sample list: {name}\n"
                "from Commands.PythonSampleCommand import PythonSampleCommand\n"
                "{imports}\n"
                "class {safe}(PythonSampleCommand):\n"
                "    NAME = {name!r}\n    SAMPLE_LIST = {name!r}\n    INCLUDED_SAMPLES = {included!r}\n"
                "{variables}\n"
                "    def do(self):\n        self.checkIfAlive()\n"
                "        # POKECON_USER_DO_BEGIN\n"
                "        # Compose/call selected sample functions here.\n"
                "        # POKECON_USER_DO_END\n"
                "{step_source}\n\n{helper_source}\n"
                "    # POKECON_USER_METHODS_BEGIN\n"
                "    # Add methods that must be preserved across sample updates here.\n"
                "    # POKECON_USER_METHODS_END\n").format(
                    name=name, imports=imports, safe=safe, included=preview["included"],
                    variables=variables, step_source=step_source, helper_source=helper_source)

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
            for region_name in ("DO", "METHODS"):
                body = self._extract_user_region(current, region_name)
                if body is not None: updated = self._replace_user_region(updated, region_name, body)
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
        return {"name": self.image_target_name.get().strip() or os.path.basename(path), "path": path, "threshold": threshold,
                "roi": roi, "grayscale": bool(self.image_target_gray.get()), "reference_resolution": resolution}

    def refresh_image_target_tree(self, selected=None):
        self.image_target_tree.delete(*self.image_target_tree.get_children())
        for index, item in enumerate(self.image_detection_targets):
            self.image_target_tree.insert("", "end", iid=str(index), values=(item["name"], item["path"], item["threshold"],
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

    def load_selected_image_target(self, event=None):
        selected = self.image_target_tree.selection()
        if not selected:
            return
        item = self.image_detection_targets[int(selected[0])]
        self.image_target_name.set(item["name"]); self.image_target_path.set(item["path"]); self.image_target_threshold.set(item["threshold"])
        self.image_target_roi.set(",".join(str(value) for value in item["roi"])); self.image_target_gray.set(bool(item.get("grayscale")))
        self.image_target_resolution.set(",".join(str(value) for value in item.get("reference_resolution", (0, 0))))

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

    def editor_modified(self, event=None):
        if self.editor.edit_modified():
            self.editor_dirty = True
            if self.active_editor_tab in self.editor_documents:
                self.editor_documents[self.active_editor_tab]["dirty"] = True
            self.editor.edit_modified(False)
            self.update_editor_view()

    def update_editor_view(self):
        count = max(1, int(self.editor.index("end-1c").split(".")[0]))
        self.line_numbers.configure(state="normal")
        self.line_numbers.delete("1.0", "end")
        self.line_numbers.insert("1.0", "\n".join(str(number) for number in range(1, count + 1)))
        self.line_numbers.configure(state="disabled")
        self._highlight_python()
        title = self.current_path or "Unsaved output"
        self.editor_title.set(("* " if self.editor_dirty else "") + title)
        if self.active_editor_tab in self.editor_documents:
            document = self.editor_documents[self.active_editor_tab]
            document["dirty"] = self.editor_dirty
            self.editor_tabs.tab(self.active_editor_tab, text=self._editor_tab_label(document))

    def _highlight_python(self):
        text = self.editor.get("1.0", "end-1c")
        for tag in ("keyword", "string", "comment"):
            self.editor.tag_remove(tag, "1.0", "end")
        for match in re.finditer(r"#.*$", text, re.MULTILINE):
            self.editor.tag_add("comment", "1.0+{}c".format(match.start()), "1.0+{}c".format(match.end()))
        for match in re.finditer(r"(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")", text):
            self.editor.tag_add("string", "1.0+{}c".format(match.start()), "1.0+{}c".format(match.end()))
        keywords = r"\b(?:and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield)\b"
        for match in re.finditer(keywords, text):
            self.editor.tag_add("keyword", "1.0+{}c".format(match.start()), "1.0+{}c".format(match.end()))

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

    def find_next(self):
        needle = self.find_text.get()
        if not needle:
            return
        self.editor.tag_remove("find", "1.0", "end")
        start = self.editor.index("insert+1c")
        found = self.editor.search(needle, start, stopindex="end", nocase=True)
        if not found:
            found = self.editor.search(needle, "1.0", stopindex="end", nocase=True)
        if found:
            end = "{}+{}c".format(found, len(needle))
            self.editor.tag_configure("find", background="#515c6a")
            self.editor.tag_add("find", found, end)
            self.editor.mark_set("insert", end)
            self.editor.see(found)
            self.editor.focus_set()

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
        self.console.configure(state="normal")
        self.console.insert("end", text)
        self.console.see("end")
        self.console.configure(state="disabled")

    def run_current(self):
        if self.run_process:
            messagebox.showinfo("Run", "A Python process is already running.")
            return
        if not self.current_path:
            messagebox.showwarning("Run", "Run requires a saved Python file.")
            return
        if self.editor_dirty and not self.save_current():
            return
        if not self.check_syntax():
            return
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")
        self.console_write("$ {} {}\n\n".format(sys.executable, self.current_path))
        try:
            self.run_process = subprocess.Popen([sys.executable, self.current_path], cwd=os.path.dirname(self.current_path),
                                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                                                bufsize=1)
        except OSError as error:
            self.console_write("Could not start: {}\n".format(error))
            self.run_process = None
            return
        def read_output(process):
            for line in iter(process.stdout.readline, ""):
                self.run_queue.put(line)
            process.stdout.close()
            self.run_queue.put("\n[process finished: {}]\n".format(process.wait()))
            self.run_queue.put(None)
        threading.Thread(target=read_output, args=(self.run_process,), daemon=True).start()
        self.after(50, self.drain_run_output)
        self.status.set("Running " + os.path.basename(self.current_path))

    def drain_run_output(self):
        alive = True
        while True:
            try:
                item = self.run_queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                alive = False
                self.run_process = None
            else:
                self.console_write(item)
        if alive and self.run_process:
            self.after(50, self.drain_run_output)
        elif not self.run_process:
            self.status.set("Run finished")

    def stop_run(self):
        if self.run_process:
            self.run_process.terminate()
            self.console_write("\n[stop requested]\n")

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
        self.local_tree.delete(*self.local_tree.get_children())
        root_id = self.local_tree.insert("", "end", text=os.path.basename(base), open=True, values=("",))
        nodes = {base: root_id}
        for directory, dirs, filenames in os.walk(base):
            dirs[:] = sorted(item for item in dirs if item != "__pycache__")
            parent = nodes[directory]
            for directory_name in dirs:
                path = os.path.join(directory, directory_name)
                nodes[path] = self.local_tree.insert(parent, "end", text=directory_name, open=True, values=("",))
            for filename in sorted(filenames):
                if filename.lower().endswith(".py"):
                    path = os.path.join(directory, filename)
                    self.local_tree.insert(parent, "end", text=filename, values=(path,))

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
        self.files, self.fragments = [], []
        self.tree.delete(*self.tree.get_children())
        nodes = {"": ""}
        for directory, dirs, filenames in os.walk(root):
            dirs[:] = [item for item in dirs if item not in ("__pycache__", ".git", ".venv", "venv")]
            for filename in sorted(filenames):
                if not filename.lower().endswith(PYTHON_SUFFIXES):
                    continue
                path = os.path.join(directory, filename)
                self.files.append(path)
                relative = os.path.relpath(path, root)
                parent = ""
                cumulative = ""
                for part in relative.split(os.sep)[:-1]:
                    cumulative = os.path.join(cumulative, part)
                    if cumulative not in nodes:
                        nodes[cumulative] = self.tree.insert(parent, "end", text=part, open=True, values=("",))
                    parent = nodes[cumulative]
                self.tree.insert(parent, "end", text=filename, values=(path,))
                self.fragments.extend(self.extract_fragments(path))
        self.status.set("{} Python files, {} tagged code fragments indexed".format(len(self.files), len(self.fragments)))

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
        hits = []
        for path in self.files:
            for number, line in enumerate(self._read_lines(path), 1):
                if needle in line.lower():
                    hits.append((path, number, line))
        self._show_results(hits)

    def filter_tags(self):
        wanted = set(self._split_tags(self.tag_text.get()))
        hits = [item for item in self.fragments if not wanted or wanted.issubset(set(item.tags))]
        self._show_results(hits)

    def find_reusable(self):
        # A practical first pass: show every function/class.  Tagged entries
        # are included with their tag information, while untagged definitions
        # can be inspected and then tagged by the developer.
        hits = list(self.fragments)
        for path in self.files:
            lines = self._read_lines(path)
            try:
                parsed = ast.parse("".join(lines), filename=path)
            except SyntaxError:
                continue
            tagged = {(item.path, item.start, item.end) for item in hits}
            for node in ast.walk(parsed):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    key = (path, node.lineno, getattr(node, "end_lineno", node.lineno))
                    if key not in tagged:
                        hits.append(Fragment(path, node.lineno, key[2], (),
                                             "class" if isinstance(node, ast.ClassDef) else "function",
                                             node.name, "".join(lines[node.lineno - 1:key[2]])))
        self._show_results(sorted(hits, key=lambda item: (item.name.lower(), item.path, item.start)))

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
