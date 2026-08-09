#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Process-safe user library for sharing Step-debug drafts between PokeCon copies."""
from __future__ import annotations

import copy
import datetime
import json
import os
import tempfile
import time


SCHEMA_VERSION = 1


class SharedDebugConflictError(RuntimeError):
    pass


def default_library_path():
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        root = os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(root, "PokeConModifiedExtension", "shared_debug_library.json")


def _empty_library():
    return {"schema_version": SCHEMA_VERSION, "sets": {}}


def read_library(path=None):
    path = os.path.abspath(path or default_library_path())
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return _empty_library()
    if not isinstance(data, dict):
        return _empty_library()
    data.setdefault("sets", {})
    if not isinstance(data["sets"], dict):
        data["sets"] = {}
    data["schema_version"] = SCHEMA_VERSION
    return data


def read_shared_debug(key, path=None):
    key = str(key or "").strip()
    if not key:
        return None
    item = read_library(path).get("sets", {}).get(key)
    return copy.deepcopy(item) if isinstance(item, dict) else None


class _ExclusiveFileLock:
    def __init__(self, path, timeout=4.0):
        self.path = path
        self.timeout = timeout
        self.stream = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.stream = open(self.path, "a+b")
        self.stream.seek(0)
        if self.stream.read(1) == b"":
            self.stream.seek(0)
            self.stream.write(b"0")
            self.stream.flush()
        if os.name != "nt":
            return self
        import msvcrt
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self.stream.close()
                    self.stream = None
                    raise TimeoutError("共有デバッグライブラリをほかのPokeConが更新中です。")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.stream is None:
            return
        if os.name == "nt":
            import msvcrt
            try:
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        self.stream.close()


def write_shared_debug(key, step_debug_rules, function_replacements, path=None,
                       writer="", expected_revision=None, force=False,
                       controller_recordings=None):
    key = str(key or "").strip()
    if not key:
        raise ValueError("共有名を入力してください。")
    path = os.path.abspath(path or default_library_path())
    lock_path = path + ".lock"
    with _ExclusiveFileLock(lock_path):
        data = read_library(path)
        previous = data["sets"].get(key, {})
        try:
            previous_revision = int(previous.get("revision", 0))
        except (TypeError, ValueError):
            previous_revision = 0
        if expected_revision is not None and int(expected_revision) != previous_revision \
                and not force:
            raise SharedDebugConflictError(
                "共有内容が別のPokeConで更新されています（共有:{} / この画面:{}）。"
                "「共有から再読込」で最新内容を確認してください。".format(
                    previous_revision, expected_revision))
        revision = previous_revision + 1
        item = {
            "revision": revision,
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "writer": str(writer or ""),
            "step_debug_rules": copy.deepcopy(list(step_debug_rules or [])),
            "function_replacements": copy.deepcopy(list(function_replacements or [])),
            "controller_recordings": copy.deepcopy(
                controller_recordings if isinstance(controller_recordings, dict) else {}),
        }
        data["sets"][key] = item
        data["schema_version"] = SCHEMA_VERSION
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file_descriptor, temporary = tempfile.mkstemp(
            prefix=os.path.basename(path) + ".", suffix=".tmp",
            dir=os.path.dirname(path))
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    return copy.deepcopy(item)
