#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tk editor for Commands recovery snippets and InputSet favorites."""
from __future__ import annotations

import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk

from CommandRecoveryScripts import DEFAULT_RECOVERY_SCRIPT


class CommandRecoveryWindow:
    """One non-modal recovery editor owned by one PokeCon process."""

    def __init__(self, root, favorites_provider, save_favorite,
                 delete_favorite, execute, stop, pause, resume, closed):
        self.root = root
        self.favorites_provider = favorites_provider
        self.save_favorite_callback = save_favorite
        self.delete_favorite_callback = delete_favorite
        self.execute_callback = execute
        self.stop_callback = stop
        self.pause_callback = pause
        self.resume_callback = resume
        self.closed_callback = closed
        self.running = False
        self.favorite_names = []

        self.window = tk.Toplevel(root)
        self.window.title("Commands 復旧Python")
        self.window.geometry("1040x760")
        self.window.minsize(760, 560)
        # This window can be opened by background monitoring.  Do not use
        # transient/topmost/lift/focus_force; preserve the user's PokeCon Z order.
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.reason = tk.StringVar(value="手動で開きました。")
        self.context = tk.StringVar(value="Commands: 未実行")
        self.status = tk.StringVar(value="コードを編集して実行できます。")
        self.favorite_name = tk.StringVar()
        self.auto_resume = tk.BooleanVar(value=True)

        header = ttk.Labelframe(self.window, text="検出内容・実行対象")
        header.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(header, textvariable=self.reason, foreground="#a13d00",
                  wraplength=980, justify="left").pack(
                      fill="x", padx=8, pady=(6, 2))
        ttk.Label(header, textvariable=self.context, wraplength=980,
                  justify="left").pack(fill="x", padx=8, pady=(2, 6))

        panes = ttk.Panedwindow(self.window, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=4)

        favorite_frame = ttk.Labelframe(
            panes, text="お気に入り（InputSetへ保存・最大50件）")
        editor_frame = ttk.Labelframe(panes, text="Pythonコード")
        panes.add(favorite_frame, weight=1)
        panes.add(editor_frame, weight=4)

        ttk.Label(favorite_frame, text="登録名").pack(
            fill="x", padx=6, pady=(6, 1))
        self.name_entry = ttk.Entry(
            favorite_frame, textvariable=self.favorite_name)
        self.name_entry.pack(fill="x", padx=6, pady=(0, 5))

        list_frame = ttk.Frame(favorite_frame)
        list_frame.pack(fill="both", expand=True, padx=6, pady=2)
        self.favorite_list = tk.Listbox(
            list_frame, exportselection=False, width=24)
        favorite_scroll = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.favorite_list.yview)
        self.favorite_list.configure(yscrollcommand=favorite_scroll.set)
        self.favorite_list.grid(column=0, row=0, sticky="nsew")
        favorite_scroll.grid(column=1, row=0, sticky="ns")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.favorite_list.bind("<<ListboxSelect>>", self._selection_changed)
        self.favorite_list.bind("<Double-1>", lambda _event: self.load_selected())

        favorite_buttons = ttk.Frame(favorite_frame)
        favorite_buttons.pack(fill="x", padx=6, pady=(3, 6))
        ttk.Button(favorite_buttons, text="新規", command=self.new_script).grid(
            column=0, row=0, padx=2, pady=2, sticky="ew")
        ttk.Button(favorite_buttons, text="呼出", command=self.load_selected).grid(
            column=1, row=0, padx=2, pady=2, sticky="ew")
        self.execute_selected_button = ttk.Button(
            favorite_buttons, text="選択を実行", command=self.execute_selected)
        self.execute_selected_button.grid(
            column=0, columnspan=2, row=1, padx=2, pady=2, sticky="ew")
        ttk.Button(favorite_buttons, text="新規登録", command=self.save_new).grid(
            column=0, row=2, padx=2, pady=2, sticky="ew")
        ttk.Button(favorite_buttons, text="上書き変更", command=self.overwrite).grid(
            column=1, row=2, padx=2, pady=2, sticky="ew")
        ttk.Button(favorite_buttons, text="削除", command=self.delete_selected).grid(
            column=0, columnspan=2, row=3, padx=2, pady=2, sticky="ew")
        favorite_buttons.columnconfigure(0, weight=1)
        favorite_buttons.columnconfigure(1, weight=1)

        editor_scroll_y = ttk.Scrollbar(editor_frame, orient="vertical")
        editor_scroll_x = ttk.Scrollbar(editor_frame, orient="horizontal")
        self.editor = tk.Text(
            editor_frame, wrap="none", undo=True, font=("Consolas", 11),
            yscrollcommand=editor_scroll_y.set,
            xscrollcommand=editor_scroll_x.set)
        editor_scroll_y.configure(command=self.editor.yview)
        editor_scroll_x.configure(command=self.editor.xview)
        self.editor.grid(column=0, row=0, sticky="nsew", padx=(6, 0), pady=(6, 0))
        editor_scroll_y.grid(column=1, row=0, sticky="ns", pady=(6, 0))
        editor_scroll_x.grid(column=0, row=1, sticky="ew", padx=(6, 0))
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(0, weight=1)
        self.editor.insert("1.0", DEFAULT_RECOVERY_SCRIPT)

        ttk.Label(
            editor_frame,
            text=("利用可能: command/self, keys, Button, Hat, Stick, Direction, "
                  "press, press_rep, hold, release, stick, wait, image_check, "
                  "release_all, log。元Commandsは終了せず同じStepで一時停止し、"
                  "このコードを再指示として優先実行します。元Commandsの終了関数は使用できません。"),
            foreground="#174a7e", wraplength=760, justify="left").grid(
                column=0, columnspan=2, row=2, sticky="ew", padx=6, pady=6)

        output_frame = ttk.Labelframe(self.window, text="実行結果")
        output_frame.pack(fill="both", padx=8, pady=4)
        # Keep execution/resume controls visible on 760px-high windows and
        # high-DPI desktops. The result area remains scrollable.
        self.output = tk.Text(output_frame, height=4, wrap="word", state="disabled")
        output_scroll = ttk.Scrollbar(
            output_frame, orient="vertical", command=self.output.yview)
        self.output.configure(yscrollcommand=output_scroll.set)
        self.output.grid(column=0, row=0, sticky="nsew", padx=(6, 0), pady=6)
        output_scroll.grid(column=1, row=0, sticky="ns", pady=6)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        action_frame = ttk.Frame(self.window)
        action_frame.pack(fill="x", padx=8, pady=(2, 8))
        ttk.Checkbutton(
            action_frame, text="成功時にCommandsを自動再開",
            variable=self.auto_resume).pack(side="left", padx=(0, 8))
        self.execute_button = ttk.Button(
            action_frame, text="Pythonを実行", command=self.execute)
        self.execute_button.pack(side="left", padx=2)
        self.stop_button = ttk.Button(
            action_frame, text="復旧コードだけ停止", command=self.stop_callback,
            state="disabled")
        self.stop_button.pack(side="left", padx=2)
        ttk.Button(
            action_frame, text="Commandsを一時停止",
            command=self.pause_callback).pack(side="left", padx=2)
        ttk.Button(
            action_frame, text="Commandsを再開",
            command=self.resume_callback).pack(side="left", padx=2)
        self.close_button = ttk.Button(
            action_frame, text="閉じる", command=self.close)
        self.close_button.pack(side="right", padx=2)
        ttk.Label(self.window, textvariable=self.status, foreground="#555555",
                  wraplength=1000).pack(fill="x", padx=10, pady=(0, 8))

        self.refresh_favorites()

    def exists(self):
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def set_context(self, reason, context):
        self.reason.set(str(reason or ""))
        self.context.set(str(context or ""))

    def refresh_favorites(self, select_name=""):
        current = str(select_name or self.selected_name() or "")
        items = list(self.favorites_provider() or [])
        self.favorite_names = [str(item.get("name", "")) for item in items]
        self.favorite_list.delete(0, "end")
        for name in self.favorite_names:
            self.favorite_list.insert("end", name)
        if current in self.favorite_names:
            index = self.favorite_names.index(current)
            self.favorite_list.selection_set(index)
            self.favorite_list.see(index)
            self.favorite_name.set(current)

    def selected_name(self):
        selected = self.favorite_list.curselection()
        return self.favorite_names[selected[0]] if selected else ""

    def selected_item(self):
        name = self.selected_name()
        return next((item for item in self.favorites_provider()
                     if str(item.get("name", "")) == name), None)

    def _selection_changed(self, _event=None):
        name = self.selected_name()
        if name:
            self.favorite_name.set(name)

    def new_script(self):
        if self.running:
            return
        self.favorite_list.selection_clear(0, "end")
        self.favorite_name.set("")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", DEFAULT_RECOVERY_SCRIPT)

    def load_selected(self):
        if self.running:
            return
        item = self.selected_item()
        if item is None:
            self.status.set("呼び出すお気に入りを選択してください。")
            return
        self.favorite_name.set(str(item.get("name", "")))
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", str(item.get("code", "")))
        self.status.set("お気に入り「{}」を読み込みました。".format(item.get("name", "")))

    def save_new(self):
        if self.running:
            return
        ok, message = self.save_favorite_callback(
            self.favorite_name.get(), self.editor.get("1.0", "end-1c"), "")
        self.status.set(message)
        if ok:
            self.refresh_favorites(self.favorite_name.get().strip())

    def overwrite(self):
        if self.running:
            return
        selected = self.selected_name()
        if not selected:
            self.status.set("上書き変更するお気に入りを選択してください。")
            return
        ok, message = self.save_favorite_callback(
            self.favorite_name.get(), self.editor.get("1.0", "end-1c"), selected)
        self.status.set(message)
        if ok:
            self.refresh_favorites(self.favorite_name.get().strip())

    def delete_selected(self):
        if self.running:
            return
        name = self.selected_name()
        if not name:
            self.status.set("削除するお気に入りを選択してください。")
            return
        if not messagebox.askyesno(
                "Commands 復旧Python",
                "お気に入り「{}」を削除しますか？".format(name),
                parent=self.window):
            return
        ok, message = self.delete_favorite_callback(name)
        self.status.set(message)
        if ok:
            self.refresh_favorites()
            self.favorite_name.set("")

    def execute(self):
        if self.running:
            return
        self.execute_callback(
            self.editor.get("1.0", "end-1c"), bool(self.auto_resume.get()))

    def execute_selected(self):
        """Load and run the selected saved snippet in one explicit action."""
        if self.running:
            return
        item = self.selected_item()
        if item is None:
            self.status.set("実行するお気に入りを選択してください。")
            return
        name = str(item.get("name", ""))
        code = str(item.get("code", ""))
        self.favorite_name.set(name)
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", code)
        self.status.set("お気に入り「{}」を実行します。".format(name))
        self.execute_callback(code, bool(self.auto_resume.get()))

    def append_output(self, text):
        if not self.exists():
            return
        self.output.configure(state="normal")
        self.output.insert("end", str(text).rstrip() + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def set_running(self, running, status=""):
        self.running = bool(running)
        self.execute_button.configure(state="disabled" if running else "normal")
        self.execute_selected_button.configure(
            state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.close_button.configure(state="disabled" if running else "normal")
        self.editor.configure(state="disabled" if running else "normal")
        if status:
            self.status.set(str(status))

    def close(self):
        if self.running:
            self.status.set("Python実行中です。［復旧コードだけ停止］後に閉じてください。")
            return
        try:
            self.window.destroy()
        finally:
            self.closed_callback()
