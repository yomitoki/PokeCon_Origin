#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Process termination used only after PokeCon's controlled GUI shutdown."""

import os
import ctypes
import json
import subprocess
import sys
import tempfile
import time
import uuid


FINALIZE_QUEUE_DIRECTORY = "PokeConMp4FinalizeQueue"
FINALIZE_WORKER_REGISTRY = "worker.json"
FINALIZE_WORKER_STARTING = "worker.starting"


def process_is_alive(pid):
    """Return whether *pid* still identifies a running process."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == 0x00000102
        finally:
            kernel32.CloseHandle(handle)
    except (AttributeError, OSError):
        return False


def recording_finalize_queue_dir():
    return os.path.join(tempfile.gettempdir(), FINALIZE_QUEUE_DIRECTORY)


def _write_json_atomic(path, payload):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    temporary = "{}.{}.tmp".format(path, uuid.uuid4().hex)
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        try:
            os.remove(temporary)
        except OSError:
            pass


def _read_worker_registry(queue_dir):
    path = os.path.join(queue_dir, FINALIZE_WORKER_REGISTRY)
    try:
        with open(path, "r", encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _worker_accepts_jobs(queue_dir):
    worker = _read_worker_registry(queue_dir)
    return bool(worker.get("accepting", True) and
                process_is_alive(worker.get("pid", 0)))


def _acquire_worker_start(queue_dir):
    marker = os.path.join(queue_dir, FINALIZE_WORKER_STARTING)
    for attempt in range(2):
        try:
            descriptor = os.open(
                marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                stale = time.time() - os.path.getmtime(marker) > 15.0
            except OSError:
                stale = True
            if not stale or attempt:
                return None
            try:
                os.remove(marker)
            except OSError:
                return None
            continue
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(str(os.getpid()))
        return marker
    return None


def _enqueue_finalize_request(queue_dir, jobs, wait_pid):
    request_path = os.path.join(
        queue_dir,
        "request_{:020d}_{}_{}.json".format(
            time.time_ns(), os.getpid(), uuid.uuid4().hex))
    _write_json_atomic(request_path, {
        "version": 1,
        "jobs": jobs,
        "wait_pid": max(0, int(wait_pid or 0)),
    })
    return request_path


def launch_recording_finalize_worker(
        manifest_paths, wait_pid=0, popen=None, executable=None,
        queue_dir=None):
    """Append MP4 jobs to the shared GUI, starting it only when necessary."""
    jobs = []
    for path in manifest_paths or []:
        path = os.path.abspath(str(path))
        if path not in jobs and os.path.isfile(path):
            jobs.append(path)
    if not jobs:
        return None

    queue_dir = os.path.abspath(
        queue_dir or recording_finalize_queue_dir())
    os.makedirs(queue_dir, exist_ok=True)
    _enqueue_finalize_request(queue_dir, jobs, wait_pid)
    if _worker_accepts_jobs(queue_dir):
        return None

    start_marker = _acquire_worker_start(queue_dir)
    if start_marker is None:
        return None
    process_started = False
    try:
        python = executable or sys.executable
        if os.name == "nt":
            candidate = os.path.join(
                os.path.dirname(python), "pythonw.exe")
            if os.path.isfile(candidate):
                python = candidate
        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "RecordingFinalizeWorker.py")
        command = [
            python, script, "--queue-dir", queue_dir,
        ]
        options = {
            "cwd": os.path.dirname(script),
            "close_fds": True,
        }
        if os.name == "nt":
            options["creationflags"] = (
                getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                | getattr(
                    subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
            )
        process = (popen or subprocess.Popen)(command, **options)
        process_started = True
        worker_pid = int(getattr(process, "pid", 0) or 0)
        if worker_pid > 0:
            _write_json_atomic(
                os.path.join(queue_dir, FINALIZE_WORKER_REGISTRY), {
                    "version": 1,
                    "pid": worker_pid,
                    "accepting": True,
                    "started_at": time.time(),
                })
        return process
    finally:
        # Keep the startup marker until the child has registered its real PID.
        # This also covers venv launchers which can briefly have a different
        # PID from the long-lived Python GUI process.
        if not process_started:
            try:
                os.remove(start_marker)
            except OSError:
                pass


def terminate_after_gui_shutdown(exit_code=0, exit_function=None, streams=None):
    """End this PokeCon even if a native or non-daemon worker is still alive.

    The caller is responsible for completing recorder, audio, camera, settings,
    and Tk cleanup first.  ``os._exit`` is intentional here: ``sys.exit`` still
    waits for non-daemon workers and would leave the launch PowerShell/Cmd open.
    """
    if streams is None:
        streams = (sys.stdout, sys.stderr)
    for stream in streams:
        if stream is None:
            continue
        try:
            stream.flush()
        except Exception:
            pass

    if exit_function is None:
        exit_function = os._exit
    return exit_function(int(exit_code))
