#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive recovery snippets for a paused Commands instance.

The editor lives in a Tk window, but execution is deliberately isolated from
Tk.  Recovery input uses Sender's priority/manual-override path so the paused
Commands worker cannot interleave controller packets with the user's snippet.
"""
from __future__ import annotations

import copy
import threading
import time
import traceback

from Commands.Keys import Button, Direction, Hat, KeyPress, Stick
from ThreadCancellation import raise_in_thread


DEFAULT_RECOVERY_SCRIPT = """# Commands復旧コード例
log("復旧処理を開始します")

# 例: Bを1回押す
press(Button.B, duration=0.1, wait=0.3)

# 例: 右スティックを右へ0.2秒
# stick(Stick.RIGHT, 0, strength=1.0, duration=0.2)
"""


class RecoveryScriptCancelled(BaseException):
    """Raised in the recovery worker when the user stops a snippet."""


class RecoveryCommandProxy:
    """Expose Commands helpers while protecting its execution lifecycle."""

    _BLOCKED_METHODS = frozenset({
        "do_safe", "end", "finish", "force_stop", "sendStopRequest", "start",
    })
    _BLOCKED_WRITES = frozenset({
        "_cleanup_started", "alive", "keys", "pause_requested", "postProcess",
        "thread",
    })

    def __init__(self, target):
        object.__setattr__(self, "_recovery_target", target)

    def __getattr__(self, name):
        if name in self._BLOCKED_METHODS:
            def blocked(*_args, **_kwargs):
                raise RuntimeError(
                    "復旧Pythonから元Commandsの{}()は実行できません。"
                    "終了する場合はCommandsタブのStopを使用してください。".format(name))
            return blocked
        return getattr(self._recovery_target, name)

    def __setattr__(self, name, value):
        if name in self._BLOCKED_WRITES:
            raise RuntimeError(
                "復旧Pythonから元Commandsの{}は変更できません。".format(name))
        setattr(self._recovery_target, name, value)


def validate_recovery_script(code):
    """Compile a recovery snippet without executing it."""
    value = str(code or "")
    if not value.strip():
        raise ValueError("実行するPythonコードが空です。")
    compile(value, "<pokecon-command-recovery>", "exec")
    return value


def normalize_recovery_favorites(items, limit=50):
    """Return unique, portable favorite dictionaries in display order."""
    result = []
    seen = set()
    for item in list(items or []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        code = str(item.get("code", ""))
        key = name.casefold()
        if not name or not code.strip() or key in seen:
            continue
        seen.add(key)
        result.append({"name": name, "code": code})
        if len(result) >= max(1, int(limit)):
            break
    return result


def save_recovery_favorite(items, name, code, original_name="", limit=50):
    """Create or replace one favorite and return a normalized new list."""
    saved = normalize_recovery_favorites(items, limit=limit)
    name = str(name or "").strip()
    original_name = str(original_name or "").strip()
    code = validate_recovery_script(code)
    if not name:
        raise ValueError("お気に入り名を入力してください。")
    target_key = original_name.casefold() if original_name else ""
    name_key = name.casefold()
    replaced = False
    for index, item in enumerate(saved):
        item_key = item["name"].casefold()
        if target_key and item_key == target_key:
            if any(other["name"].casefold() == name_key
                   for position, other in enumerate(saved) if position != index):
                raise ValueError("同じ名前のお気に入りが登録済みです。")
            saved[index] = {"name": name, "code": code}
            replaced = True
            break
    if not replaced:
        if any(item["name"].casefold() == name_key for item in saved):
            raise ValueError("同じ名前のお気に入りが登録済みです。上書き変更を使用してください。")
        if len(saved) >= max(1, int(limit)):
            raise ValueError("お気に入りは最大{}件です。".format(max(1, int(limit))))
        saved.append({"name": name, "code": code})
    return copy.deepcopy(saved)


def delete_recovery_favorite(items, name):
    key = str(name or "").strip().casefold()
    return [item for item in normalize_recovery_favorites(items)
            if item["name"].casefold() != key]


class CommandRecoveryExecutor:
    """Execute one snippet with priority input without stopping Commands.

    Cancellation belongs only to this executor's worker.  The running Commands
    lifecycle remains owned by Window.py and is kept paused at the same Step.
    """

    def __init__(self, sender, command=None, output=None):
        self.sender = sender
        self.command = command
        self.output = output if callable(output) else (lambda _text: None)
        self.cancel_event = threading.Event()
        self.worker = None
        self.keys = KeyPress(sender, priority=True)

    def request_stop(self, force=False):
        self.cancel_event.set()
        worker = self.worker
        if force and worker is not None and worker.is_alive():
            return bool(raise_in_thread(worker, RecoveryScriptCancelled))
        return False

    def _check_cancelled(self):
        if self.cancel_event.is_set():
            raise RecoveryScriptCancelled()

    def _wait(self, seconds):
        deadline = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < deadline:
            self._check_cancelled()
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    @staticmethod
    def _as_list(value):
        return list(value) if isinstance(value, (list, tuple)) else [value]

    def _press(self, buttons, duration=0.1, wait=0.1):
        self._check_cancelled()
        values = self._as_list(buttons)
        self.keys.input(values)
        try:
            self._wait(duration)
        finally:
            self.keys.inputEnd(values)
        self._wait(wait)

    def _press_rep(self, buttons, repeat=1, duration=0.1,
                   interval=0.1, wait=0.1):
        count = max(0, int(repeat))
        for index in range(count):
            self._press(buttons, duration=duration,
                        wait=0.0 if index == count - 1 else interval)
        self._wait(wait)

    def _hold(self, buttons):
        self._check_cancelled()
        self.keys.hold(buttons)

    def _release(self, buttons):
        self.keys.holdEnd(buttons)
        self._check_cancelled()

    def _release_all(self):
        self.keys.holdButton = []
        self.keys.end()

    def _stick(self, stick, angle, strength=1.0, duration=0.2, wait=0.1):
        direction = Direction(stick, float(angle), float(strength))
        self._press(direction, duration=duration, wait=wait)

    def _image_check(self, name):
        self._check_cancelled()
        command = self.command
        if command is None or not hasattr(command, "image_check"):
            raise RuntimeError("現在のCommandsではimage_checkを使用できません。")
        return command.image_check(str(name))

    def _log(self, *values, sep=" "):
        text = str(sep).join(str(value) for value in values)
        self.output(text)

    def namespace(self):
        """Names intentionally available to a recovery favorite."""
        command = (RecoveryCommandProxy(self.command)
                   if self.command is not None else None)
        return {
            "__builtins__": __builtins__,
            "self": command,
            "command": command,
            "keys": self.keys,
            "Button": Button,
            "Hat": Hat,
            "Stick": Stick,
            "Direction": Direction,
            "press": self._press,
            "press_rep": self._press_rep,
            "hold": self._hold,
            "release": self._release,
            "stick": self._stick,
            "wait": self._wait,
            "image_check": self._image_check,
            "release_all": self._release_all,
            "cancelled": self.cancel_event.is_set,
            "check_cancelled": self._check_cancelled,
            "log": self._log,
        }

    def run(self, code):
        """Run synchronously in the caller's worker and return diagnostics."""
        value = validate_recovery_script(code)
        self.worker = threading.current_thread()
        started = time.monotonic()
        result = {"success": False, "cancelled": False, "error": "",
                  "traceback": "", "elapsed": 0.0}
        override_started = False
        original_command_keys = None
        command_keys_replaced = False
        bypass_threads = getattr(
            self.command, "_pause_bypass_threads", None)
        worker_identifier = threading.get_ident()
        try:
            self.sender.begin_manual_override()
            override_started = True
            self._release_all()
            if isinstance(bypass_threads, set):
                bypass_threads.add(worker_identifier)
            if self.command is not None and hasattr(self.command, "keys"):
                original_command_keys = self.command.keys
                self.command.keys = self.keys
                command_keys_replaced = True
            self._check_cancelled()
            namespace = self.namespace()
            exec(compile(value, "<pokecon-command-recovery>", "exec"),
                 namespace, namespace)
            self._check_cancelled()
            result["success"] = True
        except RecoveryScriptCancelled:
            result["cancelled"] = True
            result["error"] = "実行を停止しました。"
        except BaseException as error:
            result["error"] = "{}: {}".format(type(error).__name__, error)
            result["traceback"] = traceback.format_exc()
        finally:
            try:
                self._release_all()
            except Exception:
                pass
            if command_keys_replaced:
                self.command.keys = original_command_keys
            if isinstance(bypass_threads, set):
                bypass_threads.discard(worker_identifier)
            if override_started:
                try:
                    self.sender.end_manual_override()
                except Exception:
                    pass
            result["elapsed"] = max(0.0, time.monotonic() - started)
        return result
