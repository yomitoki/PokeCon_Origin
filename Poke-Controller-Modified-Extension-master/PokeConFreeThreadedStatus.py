#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Show the safe Python 3.14 free-threaded readiness state for PokeCon."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import sysconfig
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parent
COMMANDS_ROOT = ROOT / "SerialController" / "Commands" / "PythonCommands"
CORE_MODULES = ("tkinter", "numpy", "PIL", "pandas", "scipy", "serial", "pynput", "sounddevice")


def compile_commands():
    checked = 0
    errors = []
    if not COMMANDS_ROOT.is_dir():
        return checked, [f"Commands folder not found: {COMMANDS_ROOT}"]
    for path in sorted(COMMANDS_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        checked += 1
        try:
            with tokenize.open(path) as source_file:
                compile(source_file.read(), str(path), "exec")
        except Exception as error:
            errors.append(f"{path.relative_to(COMMANDS_ROOT)}: {error}")
    return checked, errors


def collect_status():
    imports = {}
    for name in CORE_MODULES:
        try:
            importlib.import_module(name)
            imports[name] = "OK"
        except Exception as error:
            imports[name] = f"NG: {error}"

    command_count, command_errors = compile_commands()
    gil_supported = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    gil_enabled = bool(sys._is_gil_enabled()) if hasattr(sys, "_is_gil_enabled") else True
    return {
        "python": sys.version.splitlines()[0],
        "free_threaded_build": gil_supported,
        "gil_enabled": gil_enabled,
        "gil_disabled": gil_supported and not gil_enabled,
        "core_imports": imports,
        "commands_checked": command_count,
        "command_syntax_errors": command_errors,
        "full_pokecon_ready": False,
        "blockers": [
            "opencv-python has no safe official Windows cp314t build",
            "pygame currently re-enables the GIL",
            "pythonnet cannot initialize safely in this free-threaded environment",
        ],
    }


def show_gui(status):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("PokeCon Python 3.14t GILなし対応状況")
    root.geometry("780x600")
    root.minsize(680, 500)

    frame = ttk.Frame(root, padding=14)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Python 3.14t / GILなし対応状況", font=("Meiryo UI", 15, "bold")).pack(anchor="w")

    gil_text = "GIL無効：確認済み" if status["gil_disabled"] else "GIL無効：確認できません"
    ttk.Label(frame, text=gil_text, font=("Meiryo UI", 11, "bold")).pack(anchor="w", pady=(8, 2))
    ttk.Label(frame, text=status["python"], wraplength=740).pack(anchor="w")

    summary = (
        "現在はOpenCVなどの公式free-threaded対応が不足しているため、PokeCon本体と既存Commandsの実行は"
        "『Python 3.14（Commands互換／GILあり）』を使用してください。"
        "非公式OpenCVを強制導入してクラッシュする構成にはしていません。"
    )
    ttk.Label(frame, text=summary, wraplength=740, foreground="#a05000").pack(anchor="w", pady=10)

    text = tk.Text(frame, height=20, wrap="word", font=("Consolas", 10))
    text.pack(fill="both", expand=True)
    text.insert("end", f"Commands構文確認: {status['commands_checked']}ファイル\n")
    text.insert("end", f"構文エラー: {len(status['command_syntax_errors'])}件\n\n")
    text.insert("end", "GILなしで読み込み確認したコア依存:\n")
    for name, result in status["core_imports"].items():
        text.insert("end", f"  {name}: {result}\n")
    text.insert("end", "\nPokeCon本体をGILなしで開始できない理由:\n")
    for blocker in status["blockers"]:
        text.insert("end", f"  - {blocker}\n")
    if status["command_syntax_errors"]:
        text.insert("end", "\nCommands構文エラー:\n")
        for error in status["command_syntax_errors"]:
            text.insert("end", f"  - {error}\n")
    text.configure(state="disabled")

    ttk.Button(frame, text="閉じる", command=root.destroy).pack(anchor="e", pady=(10, 0))
    root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    status = collect_status()
    if args.check_only:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["gil_disabled"] and not status["command_syntax_errors"] else 1
    show_gui(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
