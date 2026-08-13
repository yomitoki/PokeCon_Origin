#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate isolated, runnable Commands used only for operation debugging."""
from __future__ import print_function

import ast
import datetime
import hashlib
import json
import os
import re
import shutil
import textwrap

from OperationSessionModel import atomic_json


DEBUG_SCHEMA_VERSION = 1


def _identifier(value, fallback):
    text = re.sub(r"\W+", "_", str(value or "").strip(), flags=re.UNICODE).strip("_")
    if not text:
        text = fallback
    if text[:1].isdigit():
        text = "_" + text
    return text


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _write_text(path, source):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = path + ".tmp-" + _stamp()
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(source)
    os.replace(temporary, path)


def debug_output_paths(session_dir):
    root = os.path.join(os.path.abspath(session_dir), "debug_command")
    return {
        "root": root,
        "templates": os.path.join(root, "templates"),
        "vision": os.path.join(root, "vision"),
        "logs": os.path.join(root, "logs"),
        "intermediate_history": os.path.join(root, "intermediate_history"),
        "generated_history": os.path.join(root, "generated_history"),
        "working_history": os.path.join(root, "working_history"),
        "working": os.path.join(root, "working_command.py"),
        "manifest": os.path.join(root, "debug_manifest.json"),
    }


def save_intermediate_revision(session_dir, source, generation_target="switch"):
    paths = debug_output_paths(session_dir)
    stamp = _stamp()
    target = os.path.join(
        paths["intermediate_history"],
        "{}_{}.py".format(stamp, _identifier(generation_target, "switch")))
    _write_text(target, source)
    return target


def intermediate_revisions(session_dir):
    folder = debug_output_paths(session_dir)["intermediate_history"]
    try:
        paths = [item.path for item in os.scandir(folder)
                 if item.is_file() and item.name.lower().endswith(".py")]
    except OSError:
        return []
    return sorted(paths)


def build_debug_draft_mappings(inputs, center_time=0.0, window_seconds=60.0,
                               step_seconds=12.0, max_steps=5):
    """Create a small debug-only Step draft around the selected video time."""
    rows = sorted(
        (item for item in inputs if isinstance(item, dict)),
        key=lambda item: (float(item.get("time", 0.0)), int(item.get("line", 0))))
    if not rows:
        return []
    center = max(0.0, float(center_time or 0.0))
    start_time = max(0.0, center - 3.0)
    end_time = start_time + max(1.0, float(window_seconds))
    selected = [item for item in rows
                if start_time <= float(item.get("time", 0.0)) <= end_time]
    if not selected:
        nearest = min(
            range(len(rows)),
            key=lambda index: abs(float(rows[index].get("time", 0.0)) - center))
        selected = rows[nearest:nearest + 500]
    chunks = []
    chunk = []
    chunk_started = 0.0
    previous_time = None
    for item in selected:
        item_time = float(item.get("time", 0.0))
        split = bool(chunk and (
            item_time - chunk_started >= max(1.0, float(step_seconds))
            or (previous_time is not None and item_time - previous_time >= 1.5)))
        if split:
            chunks.append(chunk)
            chunk = []
            if len(chunks) >= max(1, int(max_steps)):
                break
        if not chunk:
            chunk_started = item_time
        chunk.append(item)
        previous_time = item_time
    if chunk and len(chunks) < max(1, int(max_steps)):
        chunks.append(chunk)
    mappings = []
    for index, items in enumerate(chunks, 1):
        name = "DEBUG_AUTO_STEP_{:02d}".format(index)
        next_name = "DEBUG_AUTO_STEP_{:02d}".format(index + 1) \
            if index < len(chunks) else ""
        mappings.append({
            "start_line": int(items[0].get("line", 1)),
            "end_line": int(items[-1].get("line", 1)),
            "kind": "step", "step_name": name,
            "next_step": next_name, "function_name": "",
            "call_from_step": "",
            "notes": "デバッグ専用の自動仮Step（最終版へ反映しない）",
        })
    return mappings


def _detection_targets(metadata):
    result = []
    for item in (metadata or {}).get("candidates", []):
        roi = [int(value) for value in item.get("roi", [])]
        if len(roi) == 4:
            x1, y1, x2, y2 = roi
            debug_roi = [x1, y1, max(0, x2 - x1), max(0, y2 - y1)]
        else:
            debug_roi = [0, 0, 0, 0]
        result.append({
            "name": str(item.get("logical_name", "screen")),
            "path": os.path.abspath(str(item.get("template_path", ""))),
            "threshold": float(item.get("threshold", 0.82)),
            "roi": debug_roi,
            "grayscale": True,
            "reference_resolution": list(item.get("frame_size", [1280, 720])),
        })
    return result


def generate_debug_command_source(session, intermediate_source, vision_source,
                                  metadata, mappings):
    """Wrap generated fragments in one editable ImageProcPythonCommand."""
    ast.parse(intermediate_source)
    ast.parse(vision_source)
    session_id = str(session.get("session_id", "operation"))
    display_name = str(session.get("name", session_id) or session_id)
    class_name = _identifier(display_name, "Operation") + "_DebugCommand"
    candidates = {
        str(item.get("step_name", "")): item
        for item in (metadata or {}).get("candidates", [])
    }
    step_names = []
    for item in mappings:
        if item.get("kind") != "step":
            continue
        name = _identifier(item.get("step_name"), "RECORDED_STEP")
        if name not in step_names:
            step_names.append(name)
    runner = []
    for name in step_names:
        method = "VISION_SAMPLE_{}".format(name) if name in candidates else name
        runner.extend([
            "        self.checkIfAlive()",
            "        self.{}()".format(method),
        ])
    if not runner:
        runner = ["        print('[DEBUG] 実行できるStep割当がありません。')"]
    targets = _detection_targets(metadata)
    lines = [
        "#!/usr/bin/env python3",
        "# -*- coding: utf-8 -*-",
        "# Operation Session専用のデバッグCommandsです。",
        "# 再生成・手動調整しても最終ソースへ自動反映されません。",
        "from Commands.PythonCommandBase import ImageProcPythonCommand",
        "",
        "",
        "class {}(ImageProcPythonCommand):".format(class_name),
        "    NAME = {!r}".format("[DEBUG] " + display_name),
        "    TAGS = ['DEBUG', 'OperationSession']",
        "    SESSION_ID = {!r}".format(session_id),
        "",
        "    def __init__(self, cam):",
        "        super().__init__(cam)",
        "",
        "    @classmethod",
        "    def get_detection_targets(cls):",
        "        return {!r}".format(targets),
        "",
        "    def do(self):",
    ]
    lines.extend(runner)
    lines.extend([
        "        self.finish()",
        "",
        "    # ---- 操作記録から生成した中間コード（調整可能） ----",
        textwrap.indent(intermediate_source.rstrip(), "    "),
        "",
        "    # ---- 動画から生成した画像判定候補（調整可能） ----",
        textwrap.indent(vision_source.rstrip(), "    "),
        "",
    ])
    source = "\n".join(lines)
    ast.parse(source)
    return source


def create_debug_command_package(session_dir, session, intermediate_source,
                                 vision_source, metadata, mappings,
                                 intermediate_revision=""):
    paths = debug_output_paths(session_dir)
    source = generate_debug_command_source(
        session, intermediate_source, vision_source, metadata, mappings)
    stamp = _stamp()
    generated = os.path.join(paths["generated_history"], stamp + "_debug_command.py")
    _write_text(generated, source)
    working = paths["working"]
    working_backup = ""
    if os.path.isfile(working):
        working_backup = os.path.join(
            paths["working_history"], stamp + "_working_before_regenerate.py")
        os.makedirs(os.path.dirname(working_backup), exist_ok=True)
        shutil.copy2(working, working_backup)
    _write_text(working, source)
    manifest = {
        "schema_version": DEBUG_SCHEMA_VERSION,
        "session_id": str(session.get("session_id", "operation")),
        "generated_at": datetime.datetime.now().astimezone().isoformat(),
        "latest_generated": generated,
        "working": working,
        "working_backup": working_backup,
        "intermediate_revision": intermediate_revision,
        "templates": paths["templates"],
        "isolated_from_final_source": True,
        "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
    }
    atomic_json(paths["manifest"], manifest)
    return manifest


def deploy_debug_command(working_path, project_root, session_id, backup_dir=""):
    with open(working_path, "r", encoding="utf-8") as stream:
        source = stream.read()
    ast.parse(source)
    project_root = os.path.abspath(project_root)
    serial_root = project_root if os.path.isdir(
        os.path.join(project_root, "Commands", "PythonCommands")) else os.path.join(
            project_root, "SerialController")
    folder = os.path.join(
        serial_root, "Commands", "PythonCommands", "GeneratedDebug")
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, _identifier(session_id, "operation") + "_debug.py")
    if os.path.isfile(target) and backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(target, os.path.join(
            backup_dir, _stamp() + "_deployed_debug.py"))
    _write_text(target, source)
    return target
