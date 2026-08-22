#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Low-priority GUI worker for deferred PokeCon MP4 jobs."""
from __future__ import annotations

import argparse
import json
import os
import queue
import threading
import time
import tkinter as tk
import tkinter.ttk as ttk
import uuid

from ProcessShutdown import (FINALIZE_WORKER_REGISTRY,
                             FINALIZE_WORKER_STARTING,
                             process_is_alive)
from Recording import finalize_recording_manifest


REQUEST_PREFIX = "request_"


def _write_json_atomic(path, payload):
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


def set_worker_registry(queue_dir, accepting):
    os.makedirs(queue_dir, exist_ok=True)
    _write_json_atomic(
        os.path.join(queue_dir, FINALIZE_WORKER_REGISTRY), {
            "version": 1,
            "pid": os.getpid(),
            "accepting": bool(accepting),
            "updated_at": time.time(),
        })


def remove_worker_registry(queue_dir):
    registry = os.path.join(queue_dir, FINALIZE_WORKER_REGISTRY)
    try:
        with open(registry, "r", encoding="utf-8") as stream:
            payload = json.load(stream)
        if int(payload.get("pid", 0)) != os.getpid():
            return
    except (OSError, ValueError, TypeError, AttributeError):
        return
    try:
        os.remove(registry)
    except OSError:
        pass


def collect_finalize_requests(queue_dir, known=None):
    """Atomically claim queued requests and return new manifest jobs.

    ``known`` is updated in place so duplicate additions from the same or a
    later PokeCon do not create duplicate MP4 work or duplicate result rows.
    """
    known = known if known is not None else set()
    try:
        names = sorted(
            name for name in os.listdir(queue_dir)
            if name.startswith(REQUEST_PREFIX) and name.endswith(".json"))
    except OSError:
        return []

    additions = []
    for name in names:
        source = os.path.join(queue_dir, name)
        claimed = os.path.join(
            queue_dir, ".claim_{}_{}_{}".format(
                os.getpid(), uuid.uuid4().hex, name))
        try:
            os.replace(source, claimed)
        except OSError:
            continue
        try:
            with open(claimed, "r", encoding="utf-8") as stream:
                payload = json.load(stream)
            if not isinstance(payload, dict):
                continue
            try:
                wait_pid = max(0, int(payload.get("wait_pid", 0) or 0))
            except (TypeError, ValueError):
                wait_pid = 0
            for item in payload.get("jobs", []):
                manifest = os.path.abspath(str(item))
                if manifest in known or not os.path.isfile(manifest):
                    continue
                known.add(manifest)
                additions.append({
                    "manifest": manifest,
                    "wait_pid": wait_pid,
                })
        except (OSError, ValueError, TypeError):
            pass
        finally:
            try:
                os.remove(claimed)
            except OSError:
                pass
    return additions


class FinalizeProgressWindow:
    FOREGROUND_POLL_MS = 250
    BACKGROUND_POLL_MS = 1000
    REQUEST_POLL_SECONDS = 0.5

    def __init__(self, queue_dir):
        self.queue_dir = os.path.abspath(queue_dir)
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.busy = False
        self.closed = False
        self.total = 0
        self.completed = 0
        self.failed = 0

        self.root = tk.Tk()
        self.root.title("PokeCon MP4一括作成")
        self.root.geometry("760x380")
        self.root.minsize(620, 300)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status = tk.StringVar(value="追加される録画を待っています。")
        self.count_text = tk.StringVar(value="完了 0 / 0　失敗 0")
        ttk.Label(
            self.root, text="録画MP4を別プロセスで順番に作成します。",
            font=("Yu Gothic UI", 11, "bold")).pack(
                fill="x", padx=12, pady=(12, 4))
        ttk.Label(
            self.root, textvariable=self.status, wraplength=720,
            justify="left").pack(fill="x", padx=12, pady=4)
        self.progress = ttk.Progressbar(
            self.root, mode="determinate", maximum=1)
        self.progress.pack(fill="x", padx=12, pady=6)
        ttk.Label(self.root, textvariable=self.count_text).pack(
            fill="x", padx=12, pady=(0, 6))

        output_frame = ttk.Labelframe(self.root, text="処理済み録画")
        output_frame.pack(fill="both", expand=True, padx=12, pady=6)
        self.output = tk.Text(
            output_frame, height=8, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(
            output_frame, orient="vertical", command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        self.output.grid(column=0, row=0, sticky="nsew", padx=(6, 0), pady=6)
        scroll.grid(column=1, row=0, sticky="ns", pady=6)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        buttons = ttk.Frame(self.root)
        buttons.pack(fill="x", padx=12, pady=(2, 10))
        self.close_button = ttk.Button(
            buttons, text="閉じる", command=self.close)
        self.close_button.pack(side="right")

        set_worker_registry(self.queue_dir, True)
        try:
            os.remove(os.path.join(
                self.queue_dir, FINALIZE_WORKER_STARTING))
        except OSError:
            pass
        self.worker = threading.Thread(
            target=self._run_jobs, daemon=False, name="DeferredMp4Finalizer")
        self.worker.start()
        self.root.after(self.FOREGROUND_POLL_MS, self._drain_events)

    def _run_jobs(self):
        pending = []
        known = set()
        last_state = None
        try:
            while not self.stop_event.is_set():
                additions = collect_finalize_requests(
                    self.queue_dir, known=known)
                if additions:
                    pending.extend(additions)
                    self.events.put(("added", len(additions)))
                    last_state = None

                ready_index = next((
                    index for index, job in enumerate(pending)
                    if not job["wait_pid"] or
                    not process_is_alive(job["wait_pid"])), None)
                if ready_index is not None:
                    job = pending.pop(ready_index)
                    manifest = job["manifest"]
                    folder = os.path.dirname(manifest)
                    self.events.put(("started", folder))
                    try:
                        result = finalize_recording_manifest(manifest)
                        self.events.put(("completed", folder, result))
                    except Exception as error:
                        self.events.put(("failed", folder, str(error)))
                    last_state = None
                    continue

                state = "waiting_parent" if pending else "idle"
                if state != last_state:
                    self.events.put((state, len(pending)))
                    last_state = state
                self.stop_event.wait(self.REQUEST_POLL_SECONDS)
        finally:
            remove_worker_registry(self.queue_dir)

    def _append_output(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", str(text).rstrip() + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _update_count(self):
        self.progress["maximum"] = max(1, self.total)
        self.progress["value"] = self.completed + self.failed
        self.count_text.set(
            "完了 {} / {}　失敗 {}".format(
                self.completed, self.total, self.failed))

    def _drain_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "added":
                    self.total += event[1]
                    self.busy = True
                    self.close_button.configure(state="disabled")
                    self.status.set(
                        "録画を{}件追加しました。未処理分を続けます。".format(
                            event[1]))
                elif kind == "started":
                    self.busy = True
                    self.close_button.configure(state="disabled")
                    self.status.set("MP4作成中: {}".format(event[1]))
                elif kind == "completed":
                    self.completed += 1
                    self._append_output("完了: {}".format(event[1]))
                elif kind == "failed":
                    self.failed += 1
                    self._append_output(
                        "失敗: {}\n  {}".format(event[1], event[2]))
                elif kind == "waiting_parent":
                    self.busy = True
                    self.close_button.configure(state="disabled")
                    self.status.set(
                        "PokeCon本体の終了を待っています（{}件）。".format(
                            event[1]))
                elif kind == "idle":
                    self.busy = False
                    self.close_button.configure(state="normal")
                    if self.total:
                        self.status.set(
                            "現在の一括処理が終了しました。追加録画を待機しています。"
                            "失敗時はAVI/WAVと再試行ジョブを保持します。")
                    else:
                        self.status.set("追加される録画を待っています。")
                self._update_count()
        except queue.Empty:
            pass
        if not self.closed:
            # A minimized/background window does not need high-frequency GUI
            # polling. ffmpeg itself reports only per-file completion here.
            delay = (self.FOREGROUND_POLL_MS
                     if self.root.focus_displayof() is not None
                     else self.BACKGROUND_POLL_MS)
            self.root.after(delay, self._drain_events)

    def close(self):
        if self.busy:
            self.status.set(
                "処理中です。ウィンドウを最小化し、バックグラウンドで継続します。")
            self.root.iconify()
            return
        self.closed = True
        set_worker_registry(self.queue_dir, False)
        self.stop_event.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        self.worker.join(timeout=self.REQUEST_POLL_SECONDS + 0.5)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-dir", required=True)
    args = parser.parse_args(argv)
    os.makedirs(args.queue_dir, exist_ok=True)
    FinalizeProgressWindow(args.queue_dir).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
