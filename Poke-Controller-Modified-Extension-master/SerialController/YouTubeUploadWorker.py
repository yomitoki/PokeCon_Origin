#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Background entry point for PokeCon's shared YouTube upload queue."""
from __future__ import annotations

import argparse
import os
import time

from YouTubeArchive import run_upload_queue


def _pid_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
        except Exception:
            return False
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-dir", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--wait-pid", type=int, default=0)
    args = parser.parse_args(argv)
    while args.wait_pid and _pid_alive(args.wait_pid):
        time.sleep(0.5)
    result = run_upload_queue(args.queue_dir, args.store)
    return 1 if result.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
