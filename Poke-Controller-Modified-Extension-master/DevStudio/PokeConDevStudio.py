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
import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from CommandBuilder import command_path, python_identifier, template_source


PYTHON_SUFFIXES = (".py",)
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
        self._build()
        self._build_menu()
        self.after_idle(self.set_default_pane_sizes)
        self.after(100, self.restore_ui_state)
        self.protocol("WM_DELETE_WINDOW", self.close_dev_studio)
        self.refresh_index()
        self.refresh_local_explorer()

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
        self.config(menu=menu)
        self.bind_all("<Control-n>", lambda event: (self.new_file(), "break"))

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
        # This appears only while the left pane is hidden; its normal Hide
        # control stays next to the left-side tabs.
        self.left_reveal_bar = ttk.Frame(self)
        self.show_left_button = ttk.Button(self.left_reveal_bar, text="Show left", command=self.toggle_left_panel)
        self.show_left_button.pack(side="left")
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=7, pady=(0, 7))
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
        search_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(explorer_tab, text="Explorer")
        self.left_tabs.add(local_explorer_tab, text="LocalExplorer")
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
        self.add_editor_document("", None)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill="x", padx=7, pady=(0, 5))

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
        if not messagebox.askyesno("Apply Step hierarchy", "Rebuild the generated Step skeleton with this hierarchy?\nCustom code inside the generated skeleton will be replaced.", parent=self):
            return
        special_steps = list(self.special_step_list.get(0, "end"))
        source = template_source(self.step_template_mode.get(), command.name, name, tags, steps, self.step_loop.get(), step_start=int(self.step_start.get().split()[0]), special_steps=special_steps)
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
