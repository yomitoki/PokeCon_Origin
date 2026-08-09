#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Last-resort CPython worker interruption used only by the Force stop UI."""
from __future__ import annotations

import ctypes
import threading


def request_stop_flags(command):
    """Set cooperative cancellation flags without calling blocking methods."""
    command.alive = False
    if hasattr(command, "pause_requested"):
        command.pause_requested = False
    if hasattr(command, "socket0"):
        command.socket0.alive = False
    if hasattr(command, "mqtt0"):
        command.mqtt0.alive = False


def raise_in_thread(thread, exception_type):
    """Raise ``exception_type`` in a live non-current CPython thread."""
    if thread is None or thread is threading.current_thread():
        return False
    identifier = getattr(thread, "ident", None)
    if identifier is None or not thread.is_alive():
        return False
    api = ctypes.pythonapi.PyThreadState_SetAsyncExc
    result = api(ctypes.c_ulong(identifier), ctypes.py_object(exception_type))
    if result == 1:
        return True
    if result > 1:
        # Defensive rollback: affecting multiple thread states must never be
        # allowed, even though CPython thread identifiers should be unique.
        api(ctypes.c_ulong(identifier), None)
    return False
