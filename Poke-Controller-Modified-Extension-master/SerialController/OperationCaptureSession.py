#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capture and finalize long PC-controller authoring sessions.

The format deliberately keeps raw input, clean video and authoring metadata
separate.  DevStudio can therefore change Step/function mappings repeatedly
without altering the evidence captured from the game.
"""
from __future__ import annotations

import bisect
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import uuid

cv2 = None

from CommandRecordingMerge import find_ffmpeg


SCHEMA_VERSION = 1
DEVSTUDIO_MANIFEST_FIELDS = (
    "generation", "final_source", "source_backup", "video_sync_offset",
)
BUTTON_NAMES = (
    "R_STICK", "L_STICK", "Y", "B", "A", "X", "L", "R",
    "ZL", "ZR", "MINUS", "PLUS", "LCLICK", "RCLICK", "HOME", "CAPTURE",
)
HAT_NAMES = ("UP", "UP_RIGHT", "RIGHT", "DOWN_RIGHT", "DOWN",
             "DOWN_LEFT", "LEFT", "UP_LEFT", "CENTER")
RECORDABLE_OPERATION_SOURCES = frozenset((
    "pc_gamepad", "software_controller",
))


def operation_input_source_is_recordable(source):
    """Return whether an input source may enter operation/Commands records."""
    return str(source or "pc_gamepad").strip().lower() in RECORDABLE_OPERATION_SOURCES


def _opencv():
    global cv2
    if cv2 is None:
        try:
            import cv2 as module
        except ImportError:
            raise RuntimeError("この処理にはOpenCVが必要です。")
        cv2 = module
    return cv2


def _atomic_json(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = path + ".tmp-" + uuid.uuid4().hex
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def _safe_name(value):
    text = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or "").strip())
    return text.strip("._-")[:60]


def _stick_details(x, y):
    dx, dy = int(x) - 128, 128 - int(y)
    magnitude = min(1.0, math.sqrt(dx * dx + dy * dy) / 127.0)
    if magnitude < 0.05:
        return {"x": int(x), "y": int(y), "angle": None, "magnitude": 0.0}
    angle = (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0
    return {"x": int(x), "y": int(y), "angle": round(angle, 2),
            "magnitude": round(magnitude, 4)}


def decode_serial_message(message):
    """Return human-readable controls and stick values for one serial packet."""
    parts = str(message or "").split()
    if len(parts) < 2:
        return {"buttons": [], "hat": "CENTER", "left_stick": None,
                "right_stick": None, "summary": str(message or "")}
    try:
        bits = int(parts[0], 16)
        hat_index = int(parts[1])
    except (TypeError, ValueError):
        return {"buttons": [], "hat": "CENTER", "left_stick": None,
                "right_stick": None, "summary": str(message or "")}
    buttons = [name for index, name in enumerate(BUTTON_NAMES)
               if index >= 2 and bits & (1 << index)]
    hat = HAT_NAMES[hat_index] if 0 <= hat_index < len(HAT_NAMES) else "CENTER"
    position = 2
    left = right = None
    try:
        if bits & 0x2:
            left = _stick_details(int(parts[position], 16), int(parts[position + 1], 16))
            position += 2
        if bits & 0x1:
            right = _stick_details(int(parts[position], 16), int(parts[position + 1], 16))
    except (IndexError, ValueError):
        pass
    controls = list(buttons)
    if hat != "CENTER":
        controls.append("DPAD_" + hat)
    if left and left.get("angle") is not None:
        controls.append("L@{:.0f}deg/{:.0%}".format(left["angle"], left["magnitude"]))
    if right and right.get("angle") is not None:
        controls.append("R@{:.0f}deg/{:.0%}".format(right["angle"], right["magnitude"]))
    return {"buttons": buttons, "hat": hat, "left_stick": left,
            "right_stick": right, "summary": " + ".join(controls) or "NEUTRAL"}


def load_manifest(session_dir):
    path = os.path.join(os.path.abspath(session_dir), "session.json")
    with open(path, "r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("操作セッション情報の形式が正しくありません。")
    return value


def find_paused_session(output_root, name):
    """Return the newest paused session having the exact recording name."""
    target_name = str(name or "").strip()
    if not target_name:
        return ""
    root = os.path.abspath(output_root)
    try:
        folders = [item.path for item in os.scandir(root) if item.is_dir()]
    except OSError:
        return ""
    candidates = []
    for folder in folders:
        try:
            manifest = load_manifest(folder)
        except (OSError, TypeError, ValueError):
            continue
        if (manifest.get("status") != "paused"
                or str(manifest.get("name", "")).strip() != target_name):
            continue
        updated = str(manifest.get("updated_at", "") or
                      manifest.get("created_at", ""))
        candidates.append((updated, os.path.abspath(folder)))
    return max(candidates, default=("", ""))[1]


def paused_session_names(output_root):
    """Return unique recording names that can currently be resumed."""
    root = os.path.abspath(output_root)
    try:
        folders = [item.path for item in os.scandir(root) if item.is_dir()]
    except OSError:
        return []
    newest_by_name = {}
    for folder in folders:
        try:
            manifest = load_manifest(folder)
        except (OSError, TypeError, ValueError):
            continue
        if manifest.get("status") != "paused":
            continue
        name = str(manifest.get("name", "") or "").strip()
        if not name:
            continue
        updated = str(manifest.get("updated_at", "") or
                      manifest.get("created_at", ""))
        if updated >= newest_by_name.get(name, ""):
            newest_by_name[name] = updated
    return sorted(newest_by_name, key=str.casefold)


def remove_session_directory(session_dir, attempts=120, delay=0.5):
    """Remove a discarded session, retrying transient Windows file locks."""
    path = os.path.abspath(session_dir)
    last_error = ""
    for attempt in range(max(1, int(attempts))):
        try:
            shutil.rmtree(path)
            return ""
        except FileNotFoundError:
            return ""
        except OSError as error:
            last_error = str(error)
            if attempt + 1 < max(1, int(attempts)):
                time.sleep(max(0.0, float(delay)))
    return last_error


def load_inputs(session_dir):
    result = []
    path = os.path.join(os.path.abspath(session_dir), "inputs.jsonl")
    try:
        with open(path, "r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict) and item.get("kind") == "input":
                    result.append(item)
    except OSError:
        pass
    return sorted(result, key=lambda item: (float(item.get("time", 0.0)),
                                             int(item.get("line", 0))))


class OperationCaptureSession:
    """Thread-safe session writer used by PokeCon's gamepad worker."""

    def __init__(self, output_root, input_set="", name="", fps=60.0,
                 frame_size=(1280, 720), session_dir=None):
        self.lock = threading.RLock()
        self.output_root = os.path.abspath(output_root)
        os.makedirs(self.output_root, exist_ok=True)
        if session_dir:
            self.session_dir = os.path.abspath(session_dir)
            self.manifest = load_manifest(self.session_dir)
        else:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            suffix = _safe_name(name)
            session_id = stamp + (("_" + suffix) if suffix else "")
            self.session_dir = os.path.join(self.output_root, session_id)
            os.makedirs(self.session_dir)
            os.makedirs(os.path.join(self.session_dir, "segments"))
            os.makedirs(os.path.join(self.session_dir, "captures"))
            os.makedirs(os.path.join(self.session_dir, "source"))
            self.manifest = {
                "schema_version": SCHEMA_VERSION,
                "session_id": session_id,
                "name": str(name or session_id),
                "input_set": str(input_set or ""),
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "status": "ready",
                "fps": float(fps),
                "frame_size": [int(frame_size[0]), int(frame_size[1])],
                "active_duration": 0.0,
                "segments": [],
                "pause_images": [],
                "input_count": 0,
                "outputs": {},
                "video_sync_offset": 0.0,
                "bot_dataset_compatible": True,
            }
            self._save()
        self._segment_started = None
        self._last_manifest_save = 0.0
        self._input_stream = open(os.path.join(self.session_dir, "inputs.jsonl"),
                                  "a", encoding="utf-8", buffering=1)
        self._legacy_stream = open(os.path.join(self.session_dir, "controller_log.txt"),
                                   "a", encoding="utf-8", buffering=1)

    @property
    def status(self):
        with self.lock:
            return self.manifest.get("status", "")

    @property
    def active(self):
        with self.lock:
            return (self.manifest.get("status") == "recording"
                    and self._segment_started is not None)

    def summary(self):
        """Small coherent snapshot safe for a free-threaded UI reader."""
        with self.lock:
            return {
                "status": self.manifest.get("status", ""),
                "segments": len(self.manifest.get("segments", [])),
                "input_count": int(self.manifest.get("input_count", 0)),
                "active_duration": float(self.manifest.get("active_duration", 0.0)),
            }

    def set_input_configuration(self, gamepad="", gamepad_profile="",
                                gamepad_mapping=None):
        """Snapshot the selected input profile so a recording is reproducible."""
        with self.lock:
            configuration = {
                "gamepad": str(gamepad or ""),
                "gamepad_profile": str(gamepad_profile or ""),
                "gamepad_mapping": {
                    str(name): str(source)
                    for name, source in (gamepad_mapping or {}).items()
                },
            }
            self.manifest["input_configuration"] = configuration
            self._append_event({
                "kind": "input_configuration", "time": 0.0,
                "configuration": configuration,
            })
            self._save()
            return dict(configuration)

    def _save(self):
        # DevStudio may inspect and edit a paused session while this PokeCon
        # keeps the in-memory recorder object for Resume. Preserve the fields
        # DevStudio owns instead of overwriting them with the pre-pause copy.
        path = os.path.join(self.session_dir, "session.json")
        try:
            with open(path, "r", encoding="utf-8") as stream:
                external = json.load(stream)
            if isinstance(external, dict):
                for key in DEVSTUDIO_MANIFEST_FIELDS:
                    if key in external:
                        self.manifest[key] = external[key]
        except (OSError, ValueError):
            pass
        self.manifest["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        _atomic_json(path, self.manifest)

    def _append_event(self, event):
        with open(os.path.join(self.session_dir, "events.jsonl"), "a",
                  encoding="utf-8", newline="\n") as stream:
            json.dump(event, stream, ensure_ascii=False)
            stream.write("\n")

    def begin_segment(self, recorder_dir, started=None):
        with self.lock:
            if self.status in ("completed", "finalizing", "ready_to_edit"):
                raise RuntimeError("完了済みの操作セッションは再開できません。")
            if self.active:
                raise RuntimeError("操作セッションはすでに記録中です。")
            now = time.monotonic() if started is None else float(started)
            number = len(self.manifest["segments"]) + 1
            segment = {
                "number": number,
                "recorder_dir": os.path.abspath(recorder_dir),
                "timeline_start": float(self.manifest.get("active_duration", 0.0)),
                "started_wall": datetime.datetime.now().isoformat(timespec="milliseconds"),
                "duration": None,
                "media_hint": "",
            }
            self.manifest["segments"].append(segment)
            self._segment_started = now
            self.manifest["status"] = "recording"
            self._append_event({"kind": "resume" if number > 1 else "start",
                                "time": segment["timeline_start"], "segment": number,
                                "wall_time": segment["started_wall"]})
            self._save()
            return segment

    def record_input(self, message, occurred=None, wall_time=None,
                     source="pc_gamepad"):
        # Keyboard control is deliberately not authoring evidence.  Keep this
        # guard in the session backend as well as Window so a future caller
        # cannot accidentally mix keyboard shortcuts into inputs.jsonl.
        if not operation_input_source_is_recordable(source):
            return None
        with self.lock:
            if not self.active:
                return None
            now = time.monotonic() if occurred is None else float(occurred)
            segment = self.manifest["segments"][-1]
            segment_time = max(0.0, now - self._segment_started)
            timeline = float(segment["timeline_start"]) + segment_time
            line = int(self.manifest.get("input_count", 0)) + 1
            wall = wall_time or datetime.datetime.now().isoformat(timespec="milliseconds")
            decoded = decode_serial_message(message)
            item = {
                "kind": "input", "line": line, "time": round(timeline, 6),
                "segment": int(segment["number"]),
                "segment_time": round(segment_time, 6), "wall_time": wall,
                "message": str(message), "summary": decoded["summary"],
                "source": str(source or "pc_gamepad"),
                "buttons": decoded["buttons"], "hat": decoded["hat"],
                "left_stick": decoded["left_stick"],
                "right_stick": decoded["right_stick"],
            }
            json.dump(item, self._input_stream, ensure_ascii=False)
            self._input_stream.write("\n")
            self._legacy_stream.write("{},{}\n".format(wall, message))
            self.manifest["input_count"] = line
            # JSONL is flushed line-by-line, so the actual controller input is
            # durable immediately.  Rewriting session.json for every packet
            # can delay the gamepad worker; only its summary counter is
            # checkpointed periodically and is always saved on pause/close.
            if now - self._last_manifest_save >= 1.0:
                self._save()
                self._last_manifest_save = now
            return item

    def pause(self, frame=None, media_hint="", stopped=None):
        with self.lock:
            if not self.active:
                return ""
            now = time.monotonic() if stopped is None else float(stopped)
            segment = self.manifest["segments"][-1]
            duration = max(0.0, now - self._segment_started)
            segment["duration"] = round(duration, 6)
            segment["media_hint"] = str(media_hint or "")
            self.manifest["active_duration"] = round(
                float(segment["timeline_start"]) + duration, 6)
            pause_path = ""
            if frame is not None:
                module = _opencv()
                pause_path = os.path.join(
                    self.session_dir, "pause_{:04d}.png".format(segment["number"]))
                module.imwrite(pause_path, frame)
                self.manifest["pause_images"].append({
                    "segment": segment["number"], "time": self.manifest["active_duration"],
                    "path": pause_path,
                })
            self._append_event({"kind": "pause", "time": self.manifest["active_duration"],
                                "segment": segment["number"],
                                "wall_time": datetime.datetime.now().isoformat(timespec="milliseconds"),
                                "image": pause_path})
            self._segment_started = None
            self.manifest["status"] = "paused"
            self._save()
            return pause_path

    def complete(self):
        with self.lock:
            if self.active:
                raise RuntimeError("記録中の区間を一時停止してから完了してください。")
            if not self.manifest.get("segments"):
                raise RuntimeError("録画区間がありません。")
            self.manifest["status"] = "finalizing"
            self.manifest["completed_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            self._append_event({"kind": "complete",
                                "time": float(self.manifest.get("active_duration", 0.0)),
                                "wall_time": self.manifest["completed_at"]})
            self._save()
            self.close()

    def prepare_finalize_retry(self):
        """Mark an interrupted/failed/completed session for another merge."""
        with self.lock:
            status = self.manifest.get("status", "")
            if status not in ("finalizing", "finalize_error", "ready_to_edit"):
                raise RuntimeError(
                    "結合中・結合エラー・編集可能の操作セッションだけ再結合できます。")
            retried_at = datetime.datetime.now().isoformat(timespec="seconds")
            self.manifest["status"] = "finalizing"
            self.manifest["finalize_retry_count"] = int(
                self.manifest.get("finalize_retry_count", 0)) + 1
            self.manifest["finalize_retried_at"] = retried_at
            self.manifest.pop("finalize_error", None)
            self._append_event({
                "kind": "finalize_retry",
                "time": float(self.manifest.get("active_duration", 0.0)),
                "wall_time": retried_at,
            })
            self._save()
            return self.manifest["finalize_retry_count"]

    def discard(self):
        """Mark a stopped session as discarded before its files are removed."""
        with self.lock:
            if self.active:
                raise RuntimeError("記録中の操作セッションは一時停止してから削除してください。")
            discarded_at = datetime.datetime.now().isoformat(timespec="seconds")
            self.manifest["status"] = "discarded"
            self.manifest["discarded_at"] = discarded_at
            self._append_event({
                "kind": "discard",
                "time": float(self.manifest.get("active_duration", 0.0)),
                "wall_time": discarded_at,
            })
            self._save()
            session_dir = self.session_dir
        self.close()
        return session_dir

    def mark_finalized(self, outputs):
        with self.lock:
            self.manifest["outputs"] = dict(outputs or {})
            self.manifest["status"] = "ready_to_edit"
            self.manifest["finalized_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            self._save()

    def mark_finalize_error(self, error):
        with self.lock:
            self.manifest["status"] = "finalize_error"
            self.manifest["finalize_error"] = str(error)
            self._save()

    def close(self):
        try:
            self._save()
        except (OSError, ValueError):
            pass
        for stream_name in ("_input_stream", "_legacy_stream"):
            stream = getattr(self, stream_name, None)
            if stream is not None:
                try:
                    stream.flush()
                    stream.close()
                except OSError:
                    pass
                setattr(self, stream_name, None)


def _concat_line(path):
    value = os.path.abspath(path).replace("\\", "/").replace("'", "'\\''")
    return "file '{}'\n".format(value)


def _run_checked(command, description):
    completed = subprocess.run(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, text=True)
    if completed.returncode != 0:
        raise RuntimeError(description + "\n" + str(completed.stderr or "")[-800:])


def _render_input_overlay(clean_path, overlay_avi, inputs, output_size=(1280, 720)):
    module = _opencv()
    capture = module.VideoCapture(clean_path)
    if not capture.isOpened():
        raise RuntimeError("結合済み録画を開けません: " + clean_path)
    fps = float(capture.get(module.CAP_PROP_FPS) or 30.0)
    width, height = int(output_size[0]), int(output_size[1])
    writer = module.VideoWriter(overlay_avi, module.VideoWriter_fourcc(*"MJPG"),
                             max(1.0, fps), (width, height))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("操作情報付き録画の一時ファイルを作成できません。")
    times = [float(item.get("time", 0.0)) for item in inputs]
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame.shape[1] != width or frame.shape[0] != height:
            frame = module.resize(frame, (width, height), interpolation=module.INTER_AREA)
        current_time = frame_index / max(1.0, fps)
        position = bisect.bisect_right(times, current_time) - 1
        if position >= 0:
            item = inputs[position]
            module.rectangle(frame, (10, height - 84), (width - 10, height - 10),
                          (15, 15, 15), -1)
            module.putText(frame, "INPUT #{:04d}  t={:.3f}s".format(
                int(item.get("line", 0)), float(item.get("time", 0.0))),
                (24, height - 52), module.FONT_HERSHEY_SIMPLEX, 0.72,
                (90, 230, 255), 2, module.LINE_AA)
            module.putText(frame, str(item.get("summary", item.get("message", "")))[:120],
                           (24, height - 22), module.FONT_HERSHEY_SIMPLEX, 0.65,
                           (255, 255, 255), 2, module.LINE_AA)
        writer.write(frame)
        frame_index += 1
    writer.release()
    capture.release()


def finalize_operation_session(session_dir, ffmpeg_path=None):
    """Merge clean segments and create a second video with input overlays."""
    session_dir = os.path.abspath(session_dir)
    manifest = load_manifest(session_dir)
    segments = list(manifest.get("segments", []))
    if not segments:
        raise ValueError("結合する録画区間がありません。")
    ffmpeg_path = ffmpeg_path or find_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("FFmpegが見つからないため録画を結合できません。")
    video_paths = []
    audio_paths = []
    for segment in segments:
        folder = os.path.abspath(segment.get("recorder_dir", ""))
        try:
            if os.path.commonpath([session_dir, folder]) != session_dir:
                raise ValueError
        except ValueError:
            raise ValueError("操作セッション外の録画は結合できません。")
        avi = os.path.join(folder, "recording.avi")
        if not os.path.isfile(avi):
            raise OSError("分割録画が見つかりません: " + avi)
        video_paths.append(avi)
        audio_paths.append(os.path.join(folder, "recording.wav"))
    lists_dir = os.path.join(session_dir, ".merge-" + uuid.uuid4().hex)
    os.makedirs(lists_dir)
    clean_path = os.path.join(session_dir, "recording_clean.mp4")
    overlay_avi = os.path.join(lists_dir, "recording_with_inputs.avi")
    overlay_path = os.path.join(session_dir, "recording_with_inputs.mp4")
    try:
        video_list = os.path.join(lists_dir, "video.txt")
        with open(video_list, "w", encoding="utf-8", newline="\n") as stream:
            for path in video_paths:
                stream.write(_concat_line(path))
        command = [ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", video_list]
        complete_audio = all(os.path.isfile(path) for path in audio_paths)
        if complete_audio:
            audio_list = os.path.join(lists_dir, "audio.txt")
            with open(audio_list, "w", encoding="utf-8", newline="\n") as stream:
                for path in audio_paths:
                    stream.write(_concat_line(path))
            command.extend(["-f", "concat", "-safe", "0", "-i", audio_list,
                            "-map", "0:v:0", "-map", "1:a:0"])
        else:
            command.extend(["-map", "0:v:0", "-an"])
        command.extend(["-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                        "pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
                        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"])
        if complete_audio:
            command.extend(["-c:a", "aac", "-shortest"])
        command.extend(["-movflags", "+faststart", clean_path])
        _run_checked(command, "1280x720録画の結合に失敗しました。")

        inputs = load_inputs(session_dir)
        _render_input_overlay(clean_path, overlay_avi, inputs)
        overlay_command = [ffmpeg_path, "-y", "-i", overlay_avi, "-i", clean_path,
                           "-map", "0:v:0", "-map", "1:a?", "-c:v", "libx264",
                           "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "copy",
                           "-shortest", "-movflags", "+faststart", overlay_path]
        _run_checked(overlay_command, "操作情報付き録画の作成に失敗しました。")
        outputs = {"clean_video": clean_path, "input_overlay_video": overlay_path,
                   "input_log": os.path.join(session_dir, "inputs.jsonl"),
                   "controller_log": os.path.join(session_dir, "controller_log.txt")}
        manifest["outputs"] = outputs
        manifest["status"] = "ready_to_edit"
        manifest["finalized_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        _atomic_json(os.path.join(session_dir, "session.json"), manifest)
        return outputs
    finally:
        shutil.rmtree(lists_dir, ignore_errors=True)
