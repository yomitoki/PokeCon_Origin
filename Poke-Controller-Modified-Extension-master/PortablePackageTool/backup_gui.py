#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Japanese GUI for PokeCon portable backup creation and restoration."""

from __future__ import annotations

import datetime as dt
import locale
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


MODES = {
    "軽量移行（おすすめ・録画なし）": "migration",
    "コマンド記録を保持（通常録画なし）": "command-recordings",
    "完全保存（録画を含む・非常に大きい）": "complete",
    "指定Commandsを個別配布": "command",
}
OVERWRITES = {
    "既存ファイルを退避して反映（おすすめ）": "Backup",
    "既存ファイルがあれば停止": "Fail",
    "既存ファイルは変更しない": "Skip",
    "既存ファイルを直接置換": "Replace",
}


def suggest_output(source: Path, mode: str, command: Path | None = None) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    label = "command_" + command.stem if mode == "command" and command else mode
    return source.parent / "PokeCon_Portable_Packages" / f"{label}_{stamp}"


def build_create_command(python: str, script: Path, source: Path, mode: str,
                         output: Path, max_mib: int, command: Path | None = None,
                         safe_assets: bool = True, dry_run: bool = False) -> list[str]:
    result = [str(python), "-u", str(script), "--source-root", str(source)]
    if mode == "command":
        if command is None:
            raise ValueError("指定Commandsを選択してください。")
        result += ["command", "--command", str(command), "--asset-mode",
                   "safe" if safe_assets else "minimal"]
    else:
        result += ["local", "--profile", mode]
    result += ["--max-volume-mib", str(max_mib), "--output", str(output)]
    if dry_run:
        result.append("--dry-run")
    return result


def build_restore_command(package: Path, target: Path, overwrite: str,
                          verify_only: bool = False) -> list[str]:
    result = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
              "-File", str(package / "Restore-PokeConPackage.ps1"),
              "-PackageRoot", str(package), "-TargetRoot", str(target),
              "-Overwrite", overwrite]
    if verify_only:
        result.append("-VerifyOnly")
    return result


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.tool_root = Path(__file__).resolve().parent
        self.default_source = self.tool_root.parent
        self.events: queue.Queue = queue.Queue()
        self.process = None
        self.cancel_requested = False
        self.buttons = []
        root.title("PokeCon バックアップ・復元")
        root.geometry("900x720")
        root.minsize(760, 620)
        root.option_add("*Font", ("Yu Gothic UI", 10))
        self._ui()
        self._poll()

    def _ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="PokeCon バックアップ・復元ツール",
                  font=("Yu Gothic UI", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, foreground="#244a73",
                  text="おすすめ: ①用途を選ぶ → ②容量だけ確認 → ③バックアップ作成\n"
                       "別PC: ［復元］タブで ①破損確認 → ②復元開始").pack(anchor="w", pady=(3, 10))
        book = ttk.Notebook(outer)
        book.pack(fill="x")
        create = ttk.Frame(book, padding=12)
        restore = ttk.Frame(book, padding=12)
        book.add(create, text="バックアップ作成")
        book.add(restore, text="復元")
        self._create_ui(create)
        self._restore_ui(restore)
        frame = ttk.LabelFrame(outer, text="処理内容・結果", padding=6)
        frame.pack(fill="both", expand=True, pady=(10, 0))
        self.log = tk.Text(frame, height=13, wrap="word", state="disabled")
        bar = ttk.Scrollbar(frame, command=self.log.yview)
        self.log.configure(yscrollcommand=bar.set)
        self.log.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.status = tk.StringVar(value="待機中")
        ttk.Label(outer, textvariable=self.status, foreground="#244a73").pack(
            anchor="w", pady=(8, 2))
        progress_row = ttk.Frame(outer)
        progress_row.pack(fill="x")
        self.progress = ttk.Progressbar(progress_row, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True)
        self.cancel_button = ttk.Button(
            progress_row, text="処理を中止", command=self._cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))

    def _entry_row(self, parent, row, label, variable, action=None, action2=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        if action:
            ttk.Button(parent, text="参照...", command=action).grid(
                row=row, column=2, padx=(6, 0), pady=4)
        if action2:
            ttk.Button(parent, text="フォルダ...", command=action2).grid(
                row=row, column=3, padx=(6, 0), pady=4)
        return entry

    def _create_ui(self, tab):
        tab.columnconfigure(1, weight=1)
        self.source = tk.StringVar(value=str(self.default_source))
        self.mode = tk.StringVar(value=next(iter(MODES)))
        self.command = tk.StringVar()
        self.output = tk.StringVar()
        self.volume = tk.StringVar(value="1024")
        self.safe_assets = tk.BooleanVar(value=True)
        self._entry_row(tab, 0, "PokeConフォルダ", self.source, self._pick_source)
        ttk.Label(tab, text="保存内容").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        combo = ttk.Combobox(tab, textvariable=self.mode, values=list(MODES), state="readonly")
        combo.grid(row=1, column=1, columnspan=3, sticky="ew", pady=4)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._mode_changed())
        ttk.Label(tab, text="指定Commands").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.command_entry = ttk.Entry(tab, textvariable=self.command)
        self.command_entry.grid(row=2, column=1, sticky="ew", pady=4)
        self.command_file = ttk.Button(tab, text="ファイル...", command=self._pick_command_file)
        self.command_file.grid(row=2, column=2, padx=(6, 0), pady=4)
        self.command_dir = ttk.Button(tab, text="フォルダ...", command=self._pick_command_dir)
        self.command_dir.grid(row=2, column=3, padx=(6, 0), pady=4)
        self._entry_row(tab, 3, "バックアップ保存先", self.output, self._pick_output)
        ttk.Label(tab, text="1分割の上限 (MiB)").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Spinbox(tab, from_=4, to=65536, increment=128, textvariable=self.volume,
                    width=12).grid(row=4, column=1, sticky="w", pady=4)
        self.assets = ttk.Checkbutton(tab, variable=self.safe_assets,
                                      text="画像を安全側で同梱（Template全体・おすすめ）")
        self.assets.grid(row=5, column=1, columnspan=3, sticky="w", pady=4)
        self.note = ttk.Label(tab, foreground="#555555", wraplength=760)
        self.note.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(8, 4))
        actions = ttk.Frame(tab)
        actions.grid(row=7, column=0, columnspan=4, sticky="e", pady=(8, 0))
        self._button(actions, "① 容量だけ確認", lambda: self._create(True)).pack(side="left", padx=4)
        self._button(actions, "② バックアップ作成", lambda: self._create(False)).pack(side="left", padx=4)
        self._mode_changed()

    def _restore_ui(self, tab):
        tab.columnconfigure(1, weight=1)
        self.package = tk.StringVar()
        self.target = tk.StringVar(value=str(self.default_source))
        self.overwrite = tk.StringVar(value=next(iter(OVERWRITES)))
        self._entry_row(tab, 0, "バックアップフォルダ", self.package, self._pick_package)
        self._entry_row(tab, 1, "復元先PokeConフォルダ", self.target, self._pick_target)
        ttk.Label(tab, text="既存ファイル").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(tab, textvariable=self.overwrite, values=list(OVERWRITES),
                     state="readonly").grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Label(tab, foreground="#555555",
                  text="先に［破損確認］を実行してください。既定では既存ファイルを日時付きで退避します。"
                       "\nパッケージ内の相対位置どおりに復元します。").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(8, 4))
        actions = ttk.Frame(tab)
        actions.grid(row=4, column=0, columnspan=3, sticky="e", pady=(8, 0))
        self._button(actions, "① 破損確認", lambda: self._restore(True)).pack(side="left", padx=4)
        self._button(actions, "② 復元開始", lambda: self._restore(False)).pack(side="left", padx=4)

    def _button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        self.buttons.append(button)
        return button

    def _source_path(self):
        return Path(self.source.get().strip()).expanduser().resolve()

    def _mode_code(self):
        return MODES[self.mode.get()]

    def _command_path(self):
        value = self.command.get().strip()
        return Path(value).expanduser().resolve() if value else None

    def _set_suggested_output(self):
        try:
            self.output.set(str(suggest_output(
                self._source_path(), self._mode_code(), self._command_path())))
        except Exception:
            pass

    def _mode_changed(self):
        code = self._mode_code()
        state = "normal" if code == "command" else "disabled"
        for widget in (self.command_entry, self.command_file, self.command_dir, self.assets):
            widget.configure(state=state)
        notes = {
            "migration": "おすすめ。Commands・画像・設定を保存し、録画、コマンド記録、仮想環境、ログは除外します。",
            "command-recordings": "通常録画は除外し、CommandsRecordingを保持します。現在は約169GBです。",
            "complete": "Git管理外を全保存します。現在は約363GBで、録画はほとんど圧縮されません。",
            "command": "選択したCommandsと設定・参照画像を、他の人へ渡せる個別パッケージにします。",
        }
        self.note.configure(text=notes[code])
        self._set_suggested_output()

    def _pick_source(self):
        value = filedialog.askdirectory(title="PokeConフォルダを選択", initialdir=self.source.get())
        if value:
            self.source.set(value)
            self._set_suggested_output()

    def _pick_output(self):
        current = Path(self.output.get() or self.default_source.parent)
        initial = current if current.is_dir() else current.parent
        value = filedialog.askdirectory(title="空の保存先を選択または作成",
                                        initialdir=str(initial), mustexist=False)
        if value:
            self.output.set(value)

    def _command_root(self):
        return self._source_path() / "SerialController" / "Commands" / "PythonCommands"

    def _pick_command_file(self):
        value = filedialog.askopenfilename(title="配布するCommandを選択",
                                           initialdir=str(self._command_root()),
                                           filetypes=(("Python", "*.py"), ("すべて", "*.*")))
        if value:
            self.command.set(value)
            self._set_suggested_output()

    def _pick_command_dir(self):
        value = filedialog.askdirectory(title="配布するCommandフォルダを選択",
                                        initialdir=str(self._command_root()))
        if value:
            self.command.set(value)
            self._set_suggested_output()

    def _pick_package(self):
        value = filedialog.askdirectory(title="manifest.jsonがあるバックアップを選択")
        if value:
            self.package.set(value)

    def _pick_target(self):
        value = filedialog.askdirectory(title="復元先PokeConフォルダを選択",
                                        initialdir=self.target.get())
        if value:
            self.target.set(value)

    def _pick_volume(self):
        try:
            value = int(self.volume.get())
        except ValueError as exc:
            raise ValueError("分割サイズは整数で入力してください。") from exc
        if value < 4:
            raise ValueError("分割サイズは4 MiB以上にしてください。")
        return value

    def _create(self, dry_run):
        try:
            source = self._source_path()
            mode = self._mode_code()
            command = self._command_path()
            output = Path(self.output.get().strip()).expanduser().resolve()
            if not source.is_dir():
                raise ValueError("PokeConフォルダが見つかりません。")
            if mode == "command" and (command is None or not command.exists()):
                raise ValueError("配布するCommandsを選択してください。")
            if not dry_run and output.exists():
                if not output.is_dir() or any(output.iterdir()):
                    raise ValueError("保存先は空のフォルダを指定してください。")
            if not dry_run and mode in ("command-recordings", "complete"):
                size = "約169GB" if mode == "command-recordings" else "約363GB"
                if not messagebox.askyesno("大容量バックアップ", f"現在は{size}必要です。続けますか？"):
                    return
            cmd = build_create_command(sys.executable, self.tool_root / "portable_package.py",
                                       source, mode, output, self._pick_volume(), command,
                                       self.safe_assets.get(), dry_run)
            self._run(cmd, "容量確認" if dry_run else "バックアップ作成", "utf-8")
        except Exception as exc:
            messagebox.showerror("入力を確認してください", str(exc))

    def _restore(self, verify_only):
        try:
            package = Path(self.package.get().strip()).expanduser().resolve()
            target = Path(self.target.get().strip()).expanduser().resolve()
            if not (package / "manifest.json").is_file():
                raise ValueError("バックアップフォルダにmanifest.jsonがありません。")
            if not (package / "Restore-PokeConPackage.ps1").is_file():
                raise ValueError("バックアップフォルダに復元スクリプトがありません。")
            overwrite = OVERWRITES[self.overwrite.get()]
            if not verify_only:
                warning = "\n注意: 既存ファイルを直接置換します。" if overwrite == "Replace" else ""
                if not messagebox.askyesno("復元の確認", f"次へ復元します。\n{target}{warning}\n\n続けますか？"):
                    return
            self._run(build_restore_command(package, target, overwrite, verify_only),
                      "破損確認" if verify_only else "復元",
                      locale.getpreferredencoding(False) or "cp932")
        except Exception as exc:
            messagebox.showerror("入力を確認してください", str(exc))

    def _run(self, command, title, encoding):
        if self.process is not None:
            messagebox.showinfo("処理中", "現在の処理が終わるまでお待ちください。")
            return
        self._running(True)
        self.cancel_requested = False
        self._append(f"\n=== {title} ===\n実行: {subprocess.list2cmdline(command)}\n")

        def worker():
            env = os.environ.copy()
            if command[0] == sys.executable:
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUNBUFFERED"] = "1"
            try:
                self.process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding=encoding, errors="replace", env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for line in self.process.stdout:
                    self.events.put(("line", line))
                self.events.put(("done", (title, self.process.wait())))
            except Exception as exc:
                self.events.put(("error", (title, str(exc))))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "line":
                    self._append(value)
                    match = re.search(r"進捗:\s*([0-9.]+)%", value)
                    if match:
                        percent = min(float(match.group(1)), 100.0)
                        self.progress.stop()
                        self.progress.configure(mode="determinate", maximum=100, value=percent)
                        self.status.set(f"バックアップ処理中: {percent:.1f}%")
                    continue
                self.process = None
                self._running(False)
                title, detail = value
                if kind == "done" and detail == 0:
                    self.progress.configure(mode="determinate", value=100)
                    self.status.set("完了")
                    self._append(f"=== {title} 完了 ===\n")
                    messagebox.showinfo("完了", f"{title}が完了しました。")
                elif kind == "done" and self.cancel_requested:
                    self.status.set("中止しました")
                    self._append(
                        f"=== {title} 中止 ===\n"
                        "バックアップ途中の場合、保存先の未完成ファイルは復元に使えません。\n")
                    messagebox.showinfo("中止", f"{title}を中止しました。")
                elif kind == "done":
                    self.status.set("失敗")
                    self._append(f"=== {title} 失敗（終了コード {detail}） ===\n")
                    messagebox.showerror("失敗", "結果欄のエラーを確認してください。")
                else:
                    self.status.set("起動失敗")
                    self._append(f"=== {title} 起動失敗 ===\n{detail}\n")
                    messagebox.showerror("起動失敗", detail)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _append(self, value):
        self.log.configure(state="normal")
        self.log.insert("end", value)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _cancel(self):
        process = self.process
        if process is None or process.poll() is not None:
            messagebox.showinfo("処理中", "処理を起動しています。少し待ってから再度お試しください。")
            return
        if not messagebox.askyesno(
                "処理を中止",
                "処理を中止しますか？\n\n"
                "バックアップ途中の保存先は未完成となり、復元には使えません。"):
            return
        self.cancel_requested = True
        self.cancel_button.configure(state="disabled")
        self.status.set("中止しています...")
        self._append("中止を要求しました。処理の終了を待っています...\n")

        def terminate():
            try:
                if os.name == "nt":
                    result = subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding=locale.getpreferredencoding(False) or "cp932",
                        errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    if result.returncode:
                        self.events.put(("line", f"中止処理の警告: {result.stdout}\n"))
                else:
                    process.terminate()
            except Exception as exc:
                self.events.put(("line", f"中止処理の警告: {exc}\n"))

        threading.Thread(target=terminate, daemon=True).start()

    def _running(self, value):
        for button in self.buttons:
            button.configure(state="disabled" if value else "normal")
        self.cancel_button.configure(state="normal" if value else "disabled")
        if value:
            self.status.set("処理中...。大容量バックアップは数時間かかる場合があります。")
            self.progress.configure(mode="indeterminate", value=0)
            self.progress.start(10)
        else:
            self.progress.stop()


def main():
    if "--self-test" in sys.argv:
        print("GUI_SELF_TEST_OK")
        return 0
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
