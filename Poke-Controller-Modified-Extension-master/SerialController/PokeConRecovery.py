#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safely close one registered PokeCon process from another process."""
from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys

from InputSetRuntimeRegistry import (default_window_activity_registry_path,
                                     process_identity,
                                     read_active_input_sets)


POKECON_TITLE_MARKERS = ("poke-controller modified extension",)


class PokeConRecoveryError(RuntimeError):
    """Raised when a recovery action cannot safely identify its target."""


def default_profiles_root():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")


def _entry_key(entry):
    return str(entry.get("process_identity", ""))


def discover_running_pokecon(profiles_root=None, exclude_pid=None,
                             identity_provider=None, activity_path=None):
    """Return live PokeCon processes across profiles, deduplicated by identity."""
    profiles_root = os.path.abspath(profiles_root or default_profiles_root())
    identity_provider = identity_provider or process_identity
    activity_path = activity_path or default_window_activity_registry_path()
    found = {}

    try:
        profile_names = sorted(
            name for name in os.listdir(profiles_root)
            if os.path.isdir(os.path.join(profiles_root, name)))
    except OSError:
        profile_names = []

    for profile_name in profile_names:
        path = os.path.join(profiles_root, profile_name, "active_input_sets.json")
        if not os.path.isfile(path):
            continue
        try:
            entries = read_active_input_sets(path, identity_provider=identity_provider)
        except (OSError, TimeoutError, ValueError):
            continue
        for source in entries:
            item = dict(source)
            item["profile"] = str(item.get("profile", "") or profile_name)
            item["registry_path"] = path
            found[_entry_key(item)] = item

    # The machine-wide activity registry also contains PokeCon windows that
    # have not selected an InputSet.  Merge its device/resource information
    # into profile entries and keep otherwise-unlisted processes visible.
    try:
        activity_entries = read_active_input_sets(
            activity_path, identity_provider=identity_provider)
    except (OSError, TimeoutError, ValueError):
        activity_entries = []
    for source in activity_entries:
        key = _entry_key(source)
        existing = found.get(key)
        if existing is None:
            existing = dict(source)
            existing["registry_path"] = activity_path
            found[key] = existing
            continue
        for field in ("devices", "resource", "last_focused_ns", "last_focused_at"):
            if field in source:
                existing[field] = source[field]

    result = []
    for item in found.values():
        try:
            pid = int(item.get("pid", 0))
        except (TypeError, ValueError):
            continue
        if exclude_pid is not None and pid == int(exclude_pid):
            continue
        item["pid"] = pid
        result.append(item)
    return sorted(result, key=lambda item: (
        str(item.get("input_set", "")).casefold(),
        str(item.get("profile", "")).casefold(), item["pid"]))


def validate_recovery_target(entry, identity_provider=None, self_pid=None):
    """Verify that an entry still identifies exactly the registered process."""
    identity_provider = identity_provider or process_identity
    try:
        pid = int(entry.get("pid", 0))
    except (AttributeError, TypeError, ValueError):
        raise PokeConRecoveryError("終了対象のPIDが正しくありません。")
    if pid <= 0:
        raise PokeConRecoveryError("終了対象のPIDが正しくありません。")
    if pid == int(os.getpid() if self_pid is None else self_pid):
        raise PokeConRecoveryError("復旧画面自身は終了対象にできません。")
    expected = str(entry.get("process_identity", ""))
    current = identity_provider(pid)
    if not current:
        raise PokeConRecoveryError("対象のPokeConはすでに終了しています。")
    if not expected or str(current) != expected:
        raise PokeConRecoveryError(
            "PIDの開始情報が変わったため終了を中止しました。一覧を更新してください。")
    return pid


def _windows_for_pid(pid):
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    windows = []

    @callback_type
    def callback(hwnd, _lparam):
        owner_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
        if int(owner_pid.value) != int(pid):
            return True
        length = int(user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        windows.append((int(hwnd), buffer.value))
        return True

    user32.EnumWindows(callback, 0)
    return windows


def _pokecon_windows(pid, window_provider=None):
    provider = window_provider or _windows_for_pid
    result = []
    for hwnd, title in provider(pid):
        normalized = str(title or "").casefold()
        if any(marker in normalized for marker in POKECON_TITLE_MARKERS):
            result.append((int(hwnd), str(title)))
    return result


def request_normal_close(entry, identity_provider=None, window_provider=None,
                         post_close=None, self_pid=None):
    """Post WM_CLOSE to the registered PokeCon main window."""
    pid = validate_recovery_target(
        entry, identity_provider=identity_provider, self_pid=self_pid)
    windows = _pokecon_windows(pid, window_provider=window_provider)
    if not windows:
        raise PokeConRecoveryError(
            "対象PIDにPokeCon本体の画面が見つかりません。強制終了を使用してください。")
    if post_close is None:
        if os.name != "nt":
            raise PokeConRecoveryError("通常終了の依頼はWindowsでのみ使用できます。")
        import ctypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        post_close = lambda hwnd: bool(user32.PostMessageW(hwnd, 0x0010, 0, 0))
    if not any(post_close(hwnd) for hwnd, _title in windows):
        raise PokeConRecoveryError("PokeConへ通常終了を依頼できませんでした。")
    return pid


def force_terminate(entry, identity_provider=None, terminator=None,
                    window_provider=None, require_pokecon_window=True,
                    self_pid=None):
    """Force-terminate one exact PokeCon process after identity checks."""
    identity_provider = identity_provider or process_identity
    pid = validate_recovery_target(
        entry, identity_provider=identity_provider, self_pid=self_pid)
    if require_pokecon_window and not _pokecon_windows(
            pid, window_provider=window_provider):
        raise PokeConRecoveryError(
            "対象PIDがPokeCon本体であることを確認できないため、強制終了を中止しました。")

    # Re-check immediately before the destructive operation.  This closes the
    # PID-reuse race between selecting a row and invoking the OS terminator.
    validate_recovery_target(
        entry, identity_provider=identity_provider, self_pid=self_pid)
    if terminator is not None:
        terminator(pid)
        return pid
    if os.name != "nt":
        raise PokeConRecoveryError("強制終了はWindowsでのみ使用できます。")

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=creation_flags, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PokeConRecoveryError("Windowsの強制終了処理に失敗しました: {}".format(error))
    if completed.returncode != 0 and identity_provider(pid):
        raise PokeConRecoveryError(
            "Windowsが対象の強制終了を完了できませんでした（終了コード {}）。".format(
                completed.returncode))
    return pid


def format_started_at(value):
    text = str(value or "").strip()
    if not text:
        return "不明"
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.strftime("%Y/%m/%d %H:%M:%S")
    except (TypeError, ValueError):
        return text


class PokeConRecoveryWindow:
    def __init__(self, root, profiles_root=None, exclude_pid=None, modal=False):
        import tkinter as tk
        import tkinter.messagebox as messagebox
        import tkinter.ttk as ttk

        self.root = root
        self.profiles_root = profiles_root or default_profiles_root()
        self.exclude_pid = exclude_pid
        self.messagebox = messagebox
        self.ttk = ttk
        self.entries = {}
        self._after_id = None

        root.title("PokeCon 固まり復旧")
        root.geometry("940x480")
        root.minsize(780, 410)
        if modal:
            root.transient(root.master)

        ttk.Label(
            root, text="終了するPokeConを1行だけ選択してください。",
            font=("Meiryo UI", 13, "bold")).pack(
                fill="x", padx=14, pady=(14, 3))
        ttk.Label(
            root,
            text=("InputSet・PID・起動時刻を確認してください。同じInputSetが複数あっても、"
                  "選択したPIDだけが終了します。"),
            wraplength=900, justify="left").pack(fill="x", padx=14, pady=(0, 8))

        tree_frame = ttk.Frame(root)
        tree_frame.pack(fill="both", expand=True, padx=14, pady=4)
        columns = ("input", "combined", "profile", "pid", "started", "role")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "input": "InputSet", "combined": "起動時セット", "profile": "プロファイル",
            "pid": "PID", "started": "起動時刻", "role": "状態",
        }
        widths = {"input": 180, "combined": 170, "profile": 100,
                  "pid": 75, "started": 155, "role": 100}
        for name in columns:
            self.tree.heading(name, text=headings[name])
            self.tree.column(name, width=widths[name], stretch=name in ("input", "combined"))
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.status = tk.StringVar(value="確認中...")
        ttk.Label(root, textvariable=self.status, anchor="w").pack(
            fill="x", padx=14, pady=(4, 2))
        ttk.Label(
            root,
            text="注意: 強制終了では、未保存の設定や録画末尾が失われる場合があります。",
            foreground="#b00020", anchor="w").pack(fill="x", padx=14, pady=(0, 5))

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", padx=14, pady=(2, 14))
        ttk.Button(buttons, text="一覧を更新", command=self.refresh).pack(side="left")
        self.normal_button = ttk.Button(
            buttons, text="通常終了を依頼", command=self.normal_close)
        self.normal_button.pack(side="left", padx=(8, 0))
        self.force_button = tk.Button(
            buttons, text="選択した1台を強制終了", command=self.force_close,
            background="#c62828", foreground="white", activebackground="#8e0000",
            activeforeground="white", relief="raised", padx=10, pady=3,
            font=("Meiryo UI", 9, "bold"))
        self.force_button.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="閉じる", command=self.close).pack(side="right")

        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        if modal:
            root.wait_visibility()
            root.lift()
            root.grab_set()

    def _selected(self):
        selected = self.tree.selection()
        return self.entries.get(selected[0]) if selected else None

    @staticmethod
    def _entry_label(entry):
        input_set = str(entry.get("input_set", "") or "InputSet未選択")
        return "{} / PID {} / {}".format(
            input_set, entry.get("pid", "?"), format_started_at(entry.get("started_at")))

    def _selection_changed(self, _event=None):
        enabled = bool(self._selected())
        self.normal_button.configure(state="normal" if enabled else "disabled")
        self.force_button.configure(state="normal" if enabled else "disabled")

    def refresh(self):
        previous_identity = _entry_key(self._selected() or {})
        for item_id in self.tree.get_children(""):
            self.tree.delete(item_id)
        self.entries = {}
        entries = discover_running_pokecon(
            profiles_root=self.profiles_root, exclude_pid=self.exclude_pid)
        selected_id = None
        for index, entry in enumerate(entries):
            item_id = "process_{}".format(index)
            self.entries[item_id] = entry
            resource = entry.get("resource", {})
            if isinstance(resource, dict) and resource.get("main_effective"):
                role = "メイン"
            elif isinstance(resource, dict) and resource.get("protected"):
                role = "動作中"
            else:
                role = "起動中"
            self.tree.insert("", "end", iid=item_id, values=(
                str(entry.get("input_set", "") or "（未選択）"),
                str(entry.get("combined_set", "") or "－"),
                str(entry.get("profile", "") or "default"),
                entry.get("pid", "?"), format_started_at(entry.get("started_at")), role))
            if previous_identity and _entry_key(entry) == previous_identity:
                selected_id = item_id
        if entries:
            selected_id = selected_id or "process_0"
            self.tree.selection_set(selected_id)
            self.tree.focus(selected_id)
            self.tree.see(selected_id)
            self.status.set("{}台のPokeConが起動中です。".format(len(entries)))
        else:
            self.status.set("起動中のPokeConはありません。")
        self._selection_changed()

    def normal_close(self):
        entry = self._selected()
        if not entry:
            return
        if not self.messagebox.askyesno(
                "通常終了の確認",
                "{} に通常終了を依頼しますか？\n\n対象側に終了確認が表示されます。".format(
                    self._entry_label(entry)), parent=self.root):
            return
        try:
            request_normal_close(entry)
        except PokeConRecoveryError as error:
            self.messagebox.showerror("通常終了できません", str(error), parent=self.root)
            self.refresh()
            return
        self.status.set("通常終了を依頼しました。対象側の確認画面をご確認ください。")
        self.root.after(1200, self.refresh)

    def force_close(self):
        entry = self._selected()
        if not entry:
            return
        message = (
            "次のPokeCon 1台だけを強制終了します。\n\n{}\n\n"
            "未保存の設定や録画末尾が失われる場合があります。実行しますか？"
        ).format(self._entry_label(entry))
        if not self.messagebox.askyesno(
                "1台だけ強制終了", message, icon="warning", parent=self.root):
            return
        try:
            pid = force_terminate(entry)
        except PokeConRecoveryError as error:
            self.messagebox.showerror("強制終了できません", str(error), parent=self.root)
            self.refresh()
            return
        self.status.set("PID {} のPokeConだけを強制終了しました。".format(pid))
        self.root.after(700, self.refresh)

    def close(self):
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
        self.root.destroy()


def show_recovery_dialog(parent, profiles_root=None, exclude_pid=None):
    import tkinter as tk

    dialog = tk.Toplevel(parent)
    PokeConRecoveryWindow(
        dialog, profiles_root=profiles_root, exclude_pid=exclude_pid, modal=True)
    dialog.wait_window()


def main(argv=None):
    parser = argparse.ArgumentParser(description="PokeCon recovery window")
    parser.add_argument("--profiles-root", default=default_profiles_root())
    args = parser.parse_args(argv)
    import tkinter as tk

    root = tk.Tk()
    PokeConRecoveryWindow(root, profiles_root=args.profiles_root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
