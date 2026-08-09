"""Cross-process registry of InputSets used by running PokeCon instances."""
from __future__ import annotations

import contextlib
import datetime
import json
import os
import tempfile
import time
import uuid


REGISTRY_VERSION = 1


def default_window_activity_registry_path():
    """One machine-local file shared by PokeCon profiles and installations."""
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return os.path.join(base, "PokeConModifiedExtension", "active_windows.json")


def _utc_now_text():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def process_identity(pid):
    """Return an identity that changes when an OS process ID is reused."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None

    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            query_limited_information = 0x1000
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetProcessTimes.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
            ]
            kernel32.GetProcessTimes.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel32.OpenProcess(query_limited_information, False, pid)
            if not handle:
                return None
            try:
                created = wintypes.FILETIME()
                exited = wintypes.FILETIME()
                kernel = wintypes.FILETIME()
                user = wintypes.FILETIME()
                if not kernel32.GetProcessTimes(
                        handle, ctypes.byref(created), ctypes.byref(exited),
                        ctypes.byref(kernel), ctypes.byref(user)):
                    return None
                created_value = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
                return "{}:{}".format(pid, created_value)
            finally:
                kernel32.CloseHandle(handle)
        except (AttributeError, ImportError, OSError, ValueError):
            return None

    proc_stat = "/proc/{}/stat".format(pid)
    try:
        with open(proc_stat, "r", encoding="ascii") as stream:
            stat = stream.read()
        # Field 22 is the process start time.  Split after the final ')' so a
        # process name containing spaces or parentheses cannot shift fields.
        fields = stat[stat.rfind(")") + 2:].split()
        return "{}:{}".format(pid, fields[19])
    except (OSError, IndexError):
        try:
            os.kill(pid, 0)
            return "{}:alive".format(pid)
        except (OSError, AttributeError):
            return None


@contextlib.contextmanager
def _registry_lock(path, timeout=3.0):
    lock_path = path + ".lock"
    directory = os.path.dirname(os.path.abspath(lock_path))
    os.makedirs(directory, exist_ok=True)
    stream = open(lock_path, "a+b")
    locked = False
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            deadline = time.monotonic() + timeout
            while True:
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("InputSet起動中情報のロックを取得できませんでした。")
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            locked = True
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def _read_unlocked(path):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
            return {"version": REGISTRY_VERSION, "entries": {}}
        data["version"] = REGISTRY_VERSION
        return data
    except (OSError, ValueError):
        return {"version": REGISTRY_VERSION, "entries": {}}


def _write_unlocked(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    temporary = "{}.{}.{}.tmp".format(path, os.getpid(), uuid.uuid4().hex)
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass


def _live_entries(entries, identity_provider):
    live = {}
    for token, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        try:
            pid = int(entry.get("pid"))
        except (TypeError, ValueError):
            continue
        identity = str(entry.get("process_identity", ""))
        current_identity = identity_provider(pid)
        if current_identity and str(current_identity) == identity:
            item = dict(entry)
            item["pid"] = pid
            item["token"] = str(token)
            live[str(token)] = item
    return live


def read_active_input_sets(path, exclude_token="", identity_provider=None):
    """Return live registry entries and prune crashed or PID-reused entries."""
    identity_provider = identity_provider or process_identity
    with _registry_lock(path):
        data = _read_unlocked(path)
        original_count = len(data["entries"])
        live = _live_entries(data["entries"], identity_provider)
        if len(live) != original_count:
            data["entries"] = {
                token: {key: value for key, value in entry.items() if key != "token"}
                for token, entry in live.items()
            }
            _write_unlocked(path, data)
    result = [entry for token, entry in live.items() if token != exclude_token]
    return sorted(result, key=lambda item: (
        str(item.get("input_set", "")).casefold(), int(item.get("pid", 0))))


class ActiveInputSetRegistry:
    """Own one process entry and update it when the active InputSet changes."""

    def __init__(self, path, profile="", identity_provider=None, token=None, pid=None):
        self.path = os.path.abspath(path)
        self.profile = str(profile or "")
        self.identity_provider = identity_provider or process_identity
        self.pid = int(pid if pid is not None else os.getpid())
        self.process_identity = self.identity_provider(self.pid)
        if not self.process_identity:
            raise OSError("PokeConプロセスの開始情報を取得できませんでした。")
        self.token = str(token or uuid.uuid4().hex)
        self.started_at = _utc_now_text()
        self.closed = False

    def set_active(self, input_set, combined_set=""):
        input_set = str(input_set or "").strip()
        with _registry_lock(self.path):
            data = _read_unlocked(self.path)
            live = _live_entries(data["entries"], self.identity_provider)
            stored = {
                token: {key: value for key, value in entry.items() if key != "token"}
                for token, entry in live.items()
            }
            if input_set:
                stored[self.token] = {
                    "pid": self.pid,
                    "process_identity": str(self.process_identity),
                    "input_set": input_set,
                    "combined_set": str(combined_set or "").strip(),
                    "profile": self.profile,
                    "started_at": self.started_at,
                    "updated_at": _utc_now_text(),
                }
                self.closed = False
            else:
                stored.pop(self.token, None)
            data["entries"] = stored
            _write_unlocked(self.path, data)

    def entries(self, include_self=False):
        return read_active_input_sets(
            self.path, "" if include_self else self.token, self.identity_provider)

    def mark_focused(self, marker=None):
        """Register this process and make it the most recently focused PokeCon."""
        if self.closed:
            return
        marker = int(time.time_ns() if marker is None else marker)
        with _registry_lock(self.path):
            if self.closed:
                return
            data = _read_unlocked(self.path)
            live = _live_entries(data["entries"], self.identity_provider)
            stored = {
                token: {key: value for key, value in entry.items() if key != "token"}
                for token, entry in live.items()
            }
            existing = dict(stored.get(self.token, {}))
            existing.update({
                "pid": self.pid,
                "process_identity": str(self.process_identity),
                "input_set": str(existing.get("input_set", "")),
                "combined_set": str(existing.get("combined_set", "")),
                "profile": self.profile,
                "started_at": str(existing.get("started_at", self.started_at)),
                "updated_at": _utc_now_text(),
                "last_focused_ns": marker,
                "last_focused_at": _utc_now_text(),
            })
            stored[self.token] = existing
            data["entries"] = stored
            _write_unlocked(self.path, data)

    def is_last_focused(self):
        entries = self.entries(include_self=True)
        focused_entries = [entry for entry in entries
                           if entry.get("last_focused_ns") is not None]
        if not focused_entries:
            return False

        def focus_key(entry):
            try:
                marker = int(entry.get("last_focused_ns", 0))
            except (TypeError, ValueError):
                marker = 0
            return marker, str(entry.get("token", ""))

        return str(max(focused_entries, key=focus_key).get("token", "")) == self.token

    def close(self):
        if self.closed:
            return
        self.closed = True
        with _registry_lock(self.path):
            data = _read_unlocked(self.path)
            live = _live_entries(data["entries"], self.identity_provider)
            stored = {
                token: {key: value for key, value in entry.items() if key != "token"}
                for token, entry in live.items() if token != self.token
            }
            data["entries"] = stored
            _write_unlocked(self.path, data)
