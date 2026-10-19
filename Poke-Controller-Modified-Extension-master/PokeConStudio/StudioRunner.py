#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Subprocess runner used by PokeConStudio's source-debug controls."""
from __future__ import print_function

import argparse
import json
import os
import runpy
import sys
import traceback

try:
    from StudioCore import (DEFAULT_OPERATION_PATTERNS, operation_call_lines,
                            read_source)
except ImportError:  # pragma: no cover - module execution fallback
    from .StudioCore import (DEFAULT_OPERATION_PATTERNS,
                             operation_call_lines, read_source)


EVENT_PREFIX = "[POKECON_STUDIO_EVENT]"


class _StopRun(Exception):
    pass


def emit(event, **detail):
    payload = {"event": event}
    payload.update(detail)
    sys.stdout.write(EVENT_PREFIX + json.dumps(
        payload, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()


class SourceTracer(object):
    def __init__(self, source_path, source_text=None, break_line=0,
                 pause_before_operations=False, operation_patterns=None):
        self.source_path = os.path.normcase(os.path.abspath(source_path))
        self.break_line = max(0, int(break_line or 0))
        self.break_hit = False
        self.pause_before_operations = bool(pause_before_operations)
        self.operation_patterns = list(
            operation_patterns or DEFAULT_OPERATION_PATTERNS)
        source = (read_source(source_path)[0]
                  if source_text is None else source_text)
        self.operation_lines = set(operation_call_lines(
            source, self.operation_patterns))
        self.single_step = False
        self.last_paused = None

    def _is_target(self, frame):
        return os.path.normcase(os.path.abspath(frame.f_code.co_filename)) == self.source_path

    def _pause(self, frame, reason):
        line = int(frame.f_lineno)
        self.last_paused = line
        emit("paused", line=line, reason=reason,
             function=str(frame.f_code.co_name))
        while True:
            command = sys.stdin.readline()
            if command == "":
                raise _StopRun()
            command = command.strip().lower()
            if command in ("continue", "resume", "c"):
                self.single_step = False
                emit("resumed", line=line)
                return
            if command in ("step", "next", "s"):
                self.single_step = True
                emit("resumed", line=line, mode="step")
                return
            if command in ("stop", "quit", "q"):
                raise _StopRun()
            emit("message", text="continue / step / stop を指定してください。")

    def trace(self, frame, event, arg):
        if event != "line" or not self._is_target(frame):
            return self.trace
        line = int(frame.f_lineno)
        reason = ""
        if self.single_step and line != self.last_paused:
            reason = "step"
        elif self.break_line and not self.break_hit and line >= self.break_line:
            self.break_hit = True
            reason = "cursor"
        elif self.pause_before_operations and line in self.operation_lines:
            reason = "operation"
        if reason:
            self.single_step = False
            self._pause(frame, reason)
        return self.trace


def main(argv=None):
    parser = argparse.ArgumentParser(description="PokeConStudio source runner")
    parser.add_argument("--source", required=True)
    parser.add_argument("--break-line", type=int, default=0)
    parser.add_argument("--pause-before-operations", action="store_true")
    parser.add_argument("--operation-patterns", default="")
    parser.add_argument("--include-dir", action="append", default=[])
    parser.add_argument("--snapshot", default="")
    parser.add_argument("--working-dir", default="")
    args = parser.parse_args(argv)

    source_path = os.path.abspath(args.source)
    patterns = list(DEFAULT_OPERATION_PATTERNS)
    if args.operation_patterns:
        try:
            value = json.loads(args.operation_patterns)
            if isinstance(value, list):
                patterns = [str(item) for item in value if str(item).strip()]
        except (ValueError, TypeError):
            pass

    source_directory = os.path.dirname(source_path)
    search_paths = [source_directory] + [
        os.path.abspath(path) for path in args.include_dir
        if path and os.path.isdir(path)
    ]
    for path in reversed(search_paths):
        if path not in sys.path:
            sys.path.insert(0, path)
    working_directory = os.path.abspath(args.working_dir) \
        if args.working_dir else source_directory
    os.chdir(working_directory)
    sys.argv = [source_path]

    source_text = None
    if args.snapshot:
        source_text = read_source(os.path.abspath(args.snapshot))[0]

    tracer = SourceTracer(
        source_path,
        source_text=source_text,
        break_line=args.break_line,
        pause_before_operations=args.pause_before_operations,
        operation_patterns=patterns)
    emit("started", source=source_path,
         break_line=args.break_line,
         operation_lines=sorted(tracer.operation_lines))
    try:
        sys.settrace(tracer.trace)
        if source_text is None:
            runpy.run_path(source_path, run_name="__main__")
        else:
            namespace = {
                "__name__": "__main__",
                "__file__": source_path,
                "__package__": None,
                "__cached__": None,
                "__builtins__": __builtins__,
            }
            exec(compile(source_text, source_path, "exec"), namespace, namespace)
    except _StopRun:
        emit("stopped", source=source_path)
        return 0
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 0
        emit("finished", source=source_path, exit_code=code)
        return code
    except BaseException as error:
        sys.settrace(None)
        traceback.print_exc()
        emit("error", source=source_path, error=str(error))
        return 1
    finally:
        sys.settrace(None)
    emit("finished", source=source_path, exit_code=0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
