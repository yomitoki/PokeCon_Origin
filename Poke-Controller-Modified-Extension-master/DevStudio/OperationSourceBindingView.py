#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A read-only source/recording correspondence view shared by both studios."""
from __future__ import print_function

import tkinter as tk
from tkinter import ttk

from OperationSourceBinding import binding_details


def show_source_binding(parent, binding, open_source_callback=None):
    window = tk.Toplevel(parent)
    window.title("録画と編集対象ソースの対応 - " + binding.get("step_name", ""))
    window.geometry("1120x780")
    window.minsize(700, 420)
    window.transient(parent.winfo_toplevel())
    controls = ttk.Frame(window, padding=6)
    controls.pack(fill="x")
    ttk.Label(controls, text=("読み取り専用です。元の録画・Step計画・Commandsソースは別ファイルです。"
                              "この画面では保存／反映しません。")).pack(side="left")
    function = binding.get("function") or {}
    path = binding.get("source", {}).get("path", "")
    if open_source_callback and path and function:
        ttk.Button(controls, text="この関数へ移動", command=lambda:
                   open_source_callback(path, function["line"])).pack(side="right")
    holder = ttk.Frame(window)
    holder.pack(fill="both", expand=True, padx=6, pady=(0, 6))
    holder.rowconfigure(0, weight=1)
    holder.columnconfigure(0, weight=1)
    text = tk.Text(holder, wrap="none", font=("Consolas", 10))
    sy = ttk.Scrollbar(holder, orient="vertical", command=text.yview)
    sx = ttk.Scrollbar(holder, orient="horizontal", command=text.xview)
    text.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    text.grid(row=0, column=0, sticky="nsew")
    sy.grid(row=0, column=1, sticky="ns")
    sx.grid(row=1, column=0, sticky="ew")
    text.insert("1.0", binding_details(binding))
    text.configure(state="disabled")
    return window
