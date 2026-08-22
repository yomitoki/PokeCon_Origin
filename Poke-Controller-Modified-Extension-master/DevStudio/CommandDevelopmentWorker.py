#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot subprocess for GIL-isolated Commands source analysis."""
from __future__ import annotations

import json
import sys
import tokenize

from CommandDevelopmentTools import analyze_command_source


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        raise SystemExit("usage: CommandDevelopmentWorker.py COMMAND_SOURCE")
    source_path = argv[0]
    with tokenize.open(source_path) as stream:
        source = stream.read()
    result = analyze_command_source(source, source_path)
    list_keys = ("states", "transitions", "issues", "functions")
    header = {key: value for key, value in result.items()
              if key not in list_keys}
    json.dump({"kind": "header", "value": header}, sys.stdout,
              ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    for key in list_keys:
        values = result.get(key, [])
        for offset in range(0, len(values), 100):
            json.dump({"kind": key, "values": values[offset:offset + 100]}, sys.stdout,
                      ensure_ascii=False, separators=(",", ":"))
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
