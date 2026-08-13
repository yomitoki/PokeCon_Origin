#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge one Commands run's short recording chunks into one retained clip."""
from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import time
import uuid


def find_ffmpeg():
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _safe_source_directory(output_root, value):
    root = os.path.abspath(output_root)
    source = os.path.abspath(value)
    try:
        if os.path.commonpath([root, source]) != root or source == root:
            raise ValueError("録画保存フォルダ外の分割録画は結合できません。")
    except ValueError:
        raise ValueError("録画保存フォルダ外の分割録画は結合できません。")
    return source


def _concat_file_line(path):
    # FFmpeg's concat demuxer accepts forward slashes on Windows.  Escape a
    # quote using the syntax documented for concat list files.
    value = os.path.abspath(path).replace("\\", "/").replace("'", "'\\''")
    return "file '{}'\n".format(value)


def _chunk_duration(chunk):
    saved = chunk.get("duration_saved")
    if saved not in (None, ""):
        try:
            return max(0.0, float(saved))
        except (TypeError, ValueError):
            pass
    try:
        return max(0.0, float(chunk.get("ended")) - float(chunk.get("started")))
    except (TypeError, ValueError):
        return 0.0


def _ordered_unique(values):
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _event_offset(event, chunk):
    keys = ("video_time", "chunk_time", "elapsed") if chunk.get("merged") \
        else ("chunk_time", "elapsed", "video_time")
    for key in keys:
        try:
            if event.get(key) not in (None, ""):
                return max(0.0, float(event[key]))
        except (TypeError, ValueError):
            pass
    try:
        event_wall = datetime.datetime.fromisoformat(str(event.get("time", "")))
        chunk_wall = datetime.datetime.fromisoformat(str(chunk.get("started_wall", "")))
        return max(0.0, (event_wall - chunk_wall).total_seconds())
    except (TypeError, ValueError):
        return 0.0


def _copy_timeline_snapshot(event, source_dir, building, prefix):
    location = event.get("location")
    if not isinstance(location, dict):
        return event
    relative = str(location.get("snapshot", "") or "")
    if not relative:
        return event
    source = os.path.abspath(os.path.join(source_dir, relative))
    try:
        if os.path.commonpath([source_dir, source]) != source_dir:
            return event
    except ValueError:
        return event
    if not os.path.isfile(source):
        return event
    target_relative = os.path.join(
        "source_snapshots", "{}_{}".format(prefix, os.path.basename(source)))
    target = os.path.join(building, target_relative)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if not os.path.isfile(target):
        shutil.copy2(source, target)
    updated = dict(event)
    updated_location = dict(location)
    updated_location["snapshot"] = target_relative
    updated["location"] = updated_location
    return updated


def merge_command_recording_chunks(chunks, output_root, session_id,
                                   ffmpeg_path=None, run_command=None,
                                   now=None):
    """Create one MP4 plus combined Step/log files; source folders stay intact."""
    chunks = sorted(
        [dict(chunk) for chunk in chunks],
        key=lambda chunk: (
            str(chunk.get("started_wall", "")),
            float(chunk.get("started", 0.0) or 0.0)))
    if len(chunks) < 2:
        raise ValueError("結合対象の分割録画が2本以上必要です。")
    session_id = str(session_id or "").strip()
    if not session_id:
        raise ValueError("Commands実行セッションを特定できません。")

    root = os.path.abspath(output_root)
    os.makedirs(root, exist_ok=True)
    source_dirs = [
        _safe_source_directory(root, chunk.get("session_dir", ""))
        for chunk in chunks
    ]
    video_paths = [os.path.join(path, "recording.avi") for path in source_dirs]
    missing = [path for path in video_paths if not os.path.isfile(path)]
    if missing:
        raise OSError("結合元の録画が見つかりません: " + os.path.basename(os.path.dirname(missing[0])))

    ffmpeg_path = ffmpeg_path or find_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("FFmpegが見つからないため分割録画を結合できません。")
    run_command = run_command or subprocess.run
    timestamp = now or datetime.datetime.now()
    base_name = timestamp.strftime("%Y%m%d_%H%M%S_%f") + "_Commands_merged"
    destination = os.path.join(root, base_name)
    suffix = 2
    while os.path.exists(destination):
        destination = os.path.join(root, "{}_{}".format(base_name, suffix))
        suffix += 1
    building = destination + ".building-" + uuid.uuid4().hex
    os.makedirs(building)

    try:
        video_list = os.path.join(building, "video_concat.txt")
        with open(video_list, "w", encoding="utf-8", newline="\n") as stream:
            for path in video_paths:
                stream.write(_concat_file_line(path))

        wav_paths = [os.path.join(path, "recording.wav") for path in source_dirs]
        has_complete_audio = all(os.path.isfile(path) for path in wav_paths)
        output_media = os.path.join(building, "recording.mp4")
        command = [
            ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", video_list,
        ]
        if has_complete_audio:
            audio_list = os.path.join(building, "audio_concat.txt")
            with open(audio_list, "w", encoding="utf-8", newline="\n") as stream:
                for path in wav_paths:
                    stream.write(_concat_file_line(path))
            command.extend(["-f", "concat", "-safe", "0", "-i", audio_list])
            command.extend(["-map", "0:v:0", "-map", "1:a:0"])
        else:
            command.extend(["-map", "0:v:0", "-an"])
        command.extend([
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        ])
        if has_complete_audio:
            command.extend(["-c:a", "aac", "-shortest"])
        command.extend(["-movflags", "+faststart", output_media])
        completed = run_command(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if completed.returncode != 0 or not os.path.isfile(output_media):
            detail = str(getattr(completed, "stderr", "") or "")[-500:]
            raise RuntimeError("FFmpegによる録画結合に失敗しました。" + ("\n" + detail if detail else ""))

        step_output = os.path.join(building, "steps.jsonl")
        with open(step_output, "w", encoding="utf-8", newline="\n") as target:
            video_offset = 0.0
            for chunk_index, (source, chunk) in enumerate(
                    zip(source_dirs, chunks), start=1):
                path = os.path.join(source, "steps.jsonl")
                try:
                    with open(path, "r", encoding="utf-8") as stream:
                        for text in stream:
                            try:
                                event = json.loads(text)
                            except ValueError:
                                continue
                            if not isinstance(event, dict):
                                continue
                            event["video_time"] = round(
                                video_offset + _event_offset(event, chunk), 6)
                            event["chunk_index"] = chunk_index
                            event["source_chunk_id"] = str(chunk.get("id", ""))
                            event = _copy_timeline_snapshot(
                                event, source, building,
                                "{:03d}".format(chunk_index))
                            json.dump(event, target, ensure_ascii=False)
                            target.write("\n")
                except OSError:
                    pass
                video_offset += _chunk_duration(chunk)

        log_output = os.path.join(building, "commands.log")
        with open(log_output, "w", encoding="utf-8", newline="\n") as target:
            for index, source in enumerate(source_dirs, start=1):
                path = os.path.join(source, "commands.log")
                try:
                    with open(path, "r", encoding="utf-8") as stream:
                        value = stream.read()
                except OSError:
                    continue
                target.write("===== 分割録画 {} / {} =====\n".format(index, len(source_dirs)))
                target.write(value)
                if value and not value.endswith("\n"):
                    target.write("\n")

        duration = sum(_chunk_duration(chunk) for chunk in chunks)
        try:
            started = min(float(chunk.get("started", 0.0) or 0.0) for chunk in chunks)
        except (TypeError, ValueError):
            started = time.monotonic()
        states = _ordered_unique(
            state for chunk in chunks for state in chunk.get("states", []))
        sources = []
        for chunk_index, (source_dir, chunk) in enumerate(
                zip(source_dirs, chunks), start=1):
            descriptor = dict(chunk.get("source", {}) or {})
            if descriptor:
                copied = _copy_timeline_snapshot(
                    {"location": descriptor}, source_dir, building,
                    "{:03d}".format(chunk_index)).get("location", descriptor)
                if copied not in sources:
                    sources.append(copied)
        chunk_id = "merged-{}-{}".format(session_id, uuid.uuid4().hex)
        runtime_chunk = {
            "id": chunk_id,
            "session_dir": destination,
            "started": started,
            "started_wall": str(chunks[0].get("started_wall", "")),
            "ended": started + duration,
            "states": states,
            # If even one source was explicitly protected, the merged result
            # must inherit that protection before source folders are removed.
            "pinned": any(bool(chunk.get("pinned")) for chunk in chunks),
            "loop_anchor": False,
            "delete_pending": False,
            "command": str(chunks[0].get("command", "")),
            "command_session_id": session_id,
            "merged": True,
            "source_chunk_ids": [str(chunk.get("id", "")) for chunk in chunks],
            "duration_saved": duration,
            "source": dict(sources[0]) if sources else {},
            "sources": sources,
        }
        metadata = {key: value for key, value in runtime_chunk.items()
                    if key not in ("started", "ended", "session_dir")}
        metadata.update({
            "session_dir": destination,
            "started_monotonic": started,
            "ended_monotonic": started + duration,
            "duration": duration,
            "mode": "Commands monitoring recording (merged)",
            "merged_at": timestamp.isoformat(timespec="seconds"),
        })
        with open(os.path.join(building, "command_monitor.json"),
                  "w", encoding="utf-8", newline="\n") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
            stream.write("\n")

        # The concat lists contain source paths and are implementation details,
        # not part of the retained evidence folder.
        for path in (video_list, os.path.join(building, "audio_concat.txt")):
            try:
                os.remove(path)
            except OSError:
                pass
        os.replace(building, destination)
        runtime_chunk["session_dir"] = destination
        return runtime_chunk
    except Exception:
        shutil.rmtree(building, ignore_errors=True)
        raise
