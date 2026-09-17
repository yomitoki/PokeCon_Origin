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


def _video_duration_info(path):
    """Return decoded-container duration evidence without trusting metadata."""
    try:
        import cv2

        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            capture.release()
            return None
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0))
        capture.release()
    except (ImportError, TypeError, ValueError):
        return None
    if not (1.0 <= fps <= 240.0) or frames < 1:
        return None
    return {
        "fps": fps,
        "frames": frames,
        "duration": frames / fps,
    }


def _presentation_timing_info(source_dir):
    """Read evidence that the AVI contains live presented frames, not fill."""
    path = os.path.join(source_dir, "recording_timing.json")
    try:
        with open(path, "r", encoding="utf-8") as stream:
            report = json.load(stream)
    except (OSError, ValueError):
        return None
    video = report.get("video") if isinstance(report, dict) else None
    if not isinstance(video, dict):
        return None
    try:
        return {
            "elapsed_seconds": max(
                0.0, float(video.get("elapsed_seconds", 0.0) or 0.0)),
            "presentation_frames": max(
                0, int(video.get("presentation_frames", 0) or 0)),
            "presentation_mode": str(
                video.get("presentation_mode", "") or ""),
        }
    except (TypeError, ValueError):
        return None


def _validated_chunk_media(chunks, source_dirs, strict=True):
    """Use real AVI lengths and reject a grossly stalled preview source."""
    result = []
    for index, (chunk, source_dir) in enumerate(
            zip(chunks, source_dirs), start=1):
        path = os.path.join(source_dir, "recording.avi")
        declared = _chunk_duration(chunk)
        measured = _video_duration_info(path)
        if measured is None:
            if strict:
                raise RuntimeError(
                    "分割録画{}の実映像時間を確認できません。元録画は削除しません。"
                    .format(index))
            measured = {
                "fps": 0.0, "frames": 0, "duration": declared,
            }
        actual = max(0.0, float(measured["duration"]))
        tolerance = max(1.0, 3.0 / max(1.0, float(measured["fps"])))
        if declared > actual + tolerance:
            raise RuntimeError(
                "分割録画{}は管理上{:.1f}秒ですが実映像は{:.1f}秒です。"
                "ループまたは停止後映像が欠落しているため、結合せず元録画を保持します。"
                .format(index, declared, actual))

        timing = _presentation_timing_info(source_dir)
        if timing is not None:
            elapsed = timing["elapsed_seconds"]
            presentations = timing["presentation_frames"]
            # A static game screen still produces preview presentations. A
            # one-frame-per-several-seconds value instead means the Tk/video
            # feed was blocked and the CFR writer only duplicated an old
            # frame. Keep the raw chunks rather than labelling that as valid
            # 60-second failure evidence.
            minimum_presentations = int(max(2.0, elapsed * 0.5))
            if elapsed >= 5.0 and presentations < minimum_presentations:
                raise RuntimeError(
                    "分割録画{}は{:.1f}秒中、実表示フレームが{}枚しかありません。"
                    "ループ映像が欠落しているため、結合せず元録画を保持します。"
                    .format(index, elapsed, presentations))
        item = dict(measured)
        item["declared_duration"] = declared
        item["presentation"] = timing or {}
        result.append(item)
    return result


def _create_loop_skip_media(source_video, source_wav, building, index,
                            omitted_seconds, duration=1.0):
    """Create a short 60-FPS slate and matching silence for a removed loop."""
    import cv2
    import numpy
    import wave

    duration = max(0.5, float(duration))
    capture = cv2.VideoCapture(source_video)
    width = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH))) \
        if capture.isOpened() else 0
    height = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))) \
        if capture.isOpened() else 0
    fps = float(capture.get(cv2.CAP_PROP_FPS)) if capture.isOpened() else 0.0
    capture.release()
    width = width if width > 0 else 1280
    height = height if height > 0 else 720
    fps = fps if 1.0 <= fps <= 240.0 else 60.0
    if abs(fps - 60.0) < 0.1:
        fps = 60.0

    frame = numpy.zeros((height, width, 3), dtype=numpy.uint8)
    frame[:, :] = (44, 34, 24)
    omitted_text = "約{:.0f}秒分".format(max(0.0, float(omitted_seconds)))
    rendered = False
    try:
        from PIL import Image, ImageDraw, ImageFont

        font_root = os.environ.get("WINDIR", r"C:\Windows")
        candidates = [
            os.path.join(font_root, "Fonts", "meiryo.ttc"),
            os.path.join(font_root, "Fonts", "YuGothM.ttc"),
            os.path.join(font_root, "Fonts", "msgothic.ttc"),
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        font_path = next((path for path in candidates if os.path.isfile(path)), "")
        if font_path:
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(image)
            title_font = ImageFont.truetype(
                font_path, max(24, int(round(height * 0.065))))
            detail_font = ImageFont.truetype(
                font_path, max(18, int(round(height * 0.038))))

            def centered(text, y, font, fill):
                box = draw.textbbox((0, 0), text, font=font)
                text_width = box[2] - box[0]
                draw.text(((width - text_width) / 2.0, y), text,
                          font=font, fill=fill)

            centered("長いループ処理を省略しました",
                     height * 0.39, title_font, (245, 245, 245))
            centered("中間の録画 {} を破棄し、終了側へ移動します".format(
                omitted_text), height * 0.53, detail_font, (185, 215, 255))
            frame = cv2.cvtColor(numpy.asarray(image), cv2.COLOR_RGB2BGR)
            rendered = True
    except (ImportError, OSError, TypeError, ValueError):
        rendered = False
    if not rendered:
        title = "LONG LOOP PROCESSING SKIPPED"
        detail = "discarded middle: about {:.0f} seconds".format(
            max(0.0, float(omitted_seconds)))
        for text, y, scale in (
                (title, int(height * 0.45), max(0.6, height / 900.0)),
                (detail, int(height * 0.56), max(0.45, height / 1300.0))):
            size = cv2.getTextSize(
                text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)[0]
            cv2.putText(
                frame, text, (max(10, (width - size[0]) // 2), y),
                cv2.FONT_HERSHEY_SIMPLEX, scale, (245, 245, 245), 2,
                cv2.LINE_AA)

    video_path = os.path.join(
        building, "loop_skip_{:03d}.avi".format(int(index)))
    writer = None
    for codec in ("mp4v", "XVID"):
        candidate = cv2.VideoWriter(
            video_path, cv2.VideoWriter_fourcc(*codec), fps, (width, height))
        if candidate.isOpened():
            writer = candidate
            break
        candidate.release()
    if writer is None:
        raise RuntimeError("ループ省略表示の動画を作成できませんでした。")
    try:
        for _ in range(max(1, int(round(fps * duration)))):
            writer.write(frame)
    finally:
        writer.release()

    wav_path = ""
    if source_wav and os.path.isfile(source_wav):
        wav_path = os.path.join(
            building, "loop_skip_{:03d}.wav".format(int(index)))
        with wave.open(source_wav, "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            sample_rate = source.getframerate()
            compression = source.getcomptype()
            compression_name = source.getcompname()
        with wave.open(wav_path, "wb") as target:
            target.setnchannels(channels)
            target.setsampwidth(sample_width)
            target.setframerate(sample_rate)
            target.setcomptype(compression, compression_name)
            silent_frames = max(1, int(round(sample_rate * duration)))
            target.writeframes(
                b"\x00" * silent_frames * channels * sample_width)
    return video_path, wav_path, duration


def _copy_timeline_snapshot(event, source_dir, building, prefix):
    updated = dict(event)
    location = event.get("location")
    if isinstance(location, dict):
        relative = str(location.get("snapshot", "") or "")
        source = os.path.abspath(os.path.join(source_dir, relative)) \
            if relative else ""
        try:
            safe = bool(source) and \
                os.path.commonpath([source_dir, source]) == source_dir
        except ValueError:
            safe = False
        if safe and os.path.isfile(source):
            target_relative = os.path.join(
                "source_snapshots",
                "{}_{}".format(prefix, os.path.basename(source)))
            target = os.path.join(building, target_relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if not os.path.isfile(target):
                shutil.copy2(source, target)
            updated_location = dict(location)
            updated_location["snapshot"] = target_relative
            updated["location"] = updated_location
        # Focused-repair targets can be an outer caller while the innermost
        # helper is the primary location. Preserve every recorded project
        # stack frame's source snapshot as well, so the target function remains
        # available after source chunks are removed.
        current_location = dict(updated.get("location", location) or {})
        stack = []
        for stack_index, frame in enumerate(location.get("stack", []), start=1):
            if not isinstance(frame, dict):
                continue
            copied = _copy_timeline_snapshot(
                {"location": frame}, source_dir, building,
                "{}_s{:02d}".format(prefix, stack_index))
            stack.append(dict(copied.get("location", frame) or {}))
        if stack:
            current_location["stack"] = stack
            updated["location"] = current_location

    # Step-start images are captured before the recording compositor adds
    # image-detection boxes or log panels. Keep and relink them when short
    # chunks are consolidated, just like source snapshots.
    relative = str(event.get("step_frame", "") or "")
    source = os.path.abspath(os.path.join(source_dir, relative)) \
        if relative else ""
    try:
        safe = bool(source) and \
            os.path.commonpath([source_dir, source]) == source_dir
    except ValueError:
        safe = False
    if safe and os.path.isfile(source):
        target_relative = os.path.join(
            "step_frames", "{}_{}".format(prefix, os.path.basename(source)))
        target = os.path.join(building, target_relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not os.path.isfile(target):
            shutil.copy2(source, target)
        updated["step_frame"] = target_relative
        updated["clean_frame"] = True
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

    use_default_runner = run_command is None
    source_media = _validated_chunk_media(
        chunks, source_dirs, strict=use_default_runner)
    source_durations = [float(item["duration"]) for item in source_media]

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
        wav_paths = [os.path.join(path, "recording.wav") for path in source_dirs]
        has_complete_audio = all(os.path.isfile(path) for path in wav_paths)
        loop_gaps = {}
        for chunk_index in range(1, len(chunks)):
            chunk = chunks[chunk_index]
            if not chunk.get("loop_gap_before"):
                continue
            try:
                omitted = max(0.0, float(
                    chunk.get("loop_gap_seconds", 0.0) or 0.0))
            except (TypeError, ValueError):
                omitted = 0.0
            skip_video, skip_wav, skip_duration = _create_loop_skip_media(
                video_paths[0], wav_paths[0] if has_complete_audio else "",
                building, chunk_index, omitted)
            loop_gaps[chunk_index] = {
                "after_source_chunk_id": str(
                    chunks[chunk_index - 1].get("id", "")),
                "before_source_chunk_id": str(chunk.get("id", "")),
                "omitted_seconds": omitted,
                "marker_seconds": skip_duration,
                "video": skip_video,
                "audio": skip_wav,
            }

        video_list = os.path.join(building, "video_concat.txt")
        with open(video_list, "w", encoding="utf-8", newline="\n") as stream:
            for chunk_index, path in enumerate(video_paths):
                gap = loop_gaps.get(chunk_index)
                if gap:
                    stream.write(_concat_file_line(gap["video"]))
                stream.write(_concat_file_line(path))

        duration = (sum(source_durations)
                    + sum(float(gap["marker_seconds"])
                          for gap in loop_gaps.values()))

        output_media = os.path.join(building, "recording.mp4")
        command = [
            ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", video_list,
        ]
        if has_complete_audio:
            audio_list = os.path.join(building, "audio_concat.txt")
            with open(audio_list, "w", encoding="utf-8", newline="\n") as stream:
                for chunk_index, path in enumerate(wav_paths):
                    gap = loop_gaps.get(chunk_index)
                    if gap:
                        stream.write(_concat_file_line(gap["audio"]))
                    stream.write(_concat_file_line(path))
            command.extend(["-f", "concat", "-safe", "0", "-i", audio_list])
            command.extend(["-map", "0:v:0", "-map", "1:a:0"])
        else:
            command.extend(["-map", "0:v:0", "-an"])
        command.extend([
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        ])
        if has_complete_audio:
            # A failed/reopened Windows audio chunk can be shorter than its
            # AVI. Pad it so -shortest follows the complete video timeline
            # instead of deleting the loop/failure tail from the final MP4.
            command.extend(["-filter:a", "apad", "-c:a", "aac", "-shortest"])
        command.extend(["-movflags", "+faststart", output_media])
        run_options = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.PIPE,
            "text": True,
        }
        if use_default_runner and os.name == "nt":
            run_options["creationflags"] = getattr(
                subprocess, "CREATE_NO_WINDOW", 0x08000000)
        completed = run_command(command, **run_options)
        if completed.returncode != 0 or not os.path.isfile(output_media):
            detail = str(getattr(completed, "stderr", "") or "")[-500:]
            raise RuntimeError("FFmpegによる録画結合に失敗しました。" + ("\n" + detail if detail else ""))
        if use_default_runner:
            output_info = _video_duration_info(output_media)
            if output_info is None:
                raise RuntimeError(
                    "結合MP4の実映像時間を確認できません。元録画は削除しません。")
            output_duration = float(output_info["duration"])
            if output_duration + 1.0 < duration:
                raise RuntimeError(
                    "結合MP4は予定{:.1f}秒に対して実映像{:.1f}秒です。"
                    "ループまたは停止後映像が欠落しているため、元録画を保持します。"
                    .format(duration, output_duration))

        step_output = os.path.join(building, "steps.jsonl")
        timeline_event_count = 0
        with open(step_output, "w", encoding="utf-8", newline="\n") as target:
            video_offset = 0.0
            for chunk_index, (source, chunk) in enumerate(
                    zip(source_dirs, chunks), start=1):
                gap = loop_gaps.get(chunk_index - 1)
                if gap:
                    gap["video_time"] = video_offset
                    event = {
                        "time": str(chunk.get("started_wall", "")),
                        "event": "loop_processing_skipped",
                        "states": {},
                        "step_path": "長いループ処理の中間を省略",
                        "location": {},
                        "video_time": round(video_offset, 6),
                        "loop_omitted_seconds": gap["omitted_seconds"],
                        "marker_seconds": gap["marker_seconds"],
                        "chunk_index": chunk_index,
                        "source_chunk_id": str(chunk.get("id", "")),
                    }
                    json.dump(event, target, ensure_ascii=False)
                    target.write("\n")
                    timeline_event_count += 1
                    video_offset += float(gap["marker_seconds"])
                chunk_duration = source_durations[chunk_index - 1]
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
                            event_offset = _event_offset(event, chunk)
                            # A delayed trace writer can finish just after the
                            # recorder. Keep a small end-boundary tolerance,
                            # but never carry an event from outside this saved
                            # video chunk into the merged execution path.
                            if event_offset > chunk_duration + 0.25:
                                continue
                            event_offset = min(event_offset, chunk_duration)
                            event["video_time"] = round(
                                video_offset + event_offset, 6)
                            event["chunk_index"] = chunk_index
                            event["source_chunk_id"] = str(chunk.get("id", ""))
                            event = _copy_timeline_snapshot(
                                event, source, building,
                                "{:03d}".format(chunk_index))
                            json.dump(event, target, ensure_ascii=False)
                            target.write("\n")
                            timeline_event_count += 1
                except OSError:
                    pass
                video_offset += chunk_duration

        log_output = os.path.join(building, "commands.log")
        with open(log_output, "w", encoding="utf-8", newline="\n") as target:
            for index, source in enumerate(source_dirs, start=1):
                gap = loop_gaps.get(index - 1)
                if gap:
                    target.write(
                        "===== 長いループ処理の中間 約{:.0f}秒分を省略 =====\n".format(
                            gap["omitted_seconds"]))
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

        try:
            started = min(float(chunk.get("started", 0.0) or 0.0) for chunk in chunks)
        except (TypeError, ValueError):
            started = time.monotonic()
        states = _ordered_unique(
            state for chunk in chunks for state in chunk.get("states", []))
        focus_targets = _ordered_unique(
            target for chunk in chunks
            for target in dict(chunk.get("focus_repair", {}) or {}).get(
                "targets", []))
        focus_matches = _ordered_unique(
            name for chunk in chunks
            for name in dict(chunk.get("focus_repair", {}) or {}).get(
                "matched_functions", []))
        focus_enabled = any(bool(dict(
            chunk.get("focus_repair", {}) or {}).get("enabled"))
            for chunk in chunks)
        focus_trace_dropped = max(
            [int(dict(chunk.get("focus_repair", {}) or {}).get(
                "trace_dropped", 0) or 0) for chunk in chunks] or [0])
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
            "source_media": source_media,
            "loop_compaction": {
                "applied": bool(loop_gaps),
                "marker_seconds": 1.0,
                "gaps": [
                    {key: value for key, value in gap.items()
                     if key not in ("video", "audio")}
                    for _index, gap in sorted(loop_gaps.items())
                ],
            },
            "source": dict(sources[0]) if sources else {},
            "sources": sources,
            "focus_matched": bool(focus_matches),
            "focus_repair": {
                "enabled": bool(focus_enabled or focus_targets),
                "targets": focus_targets,
                "matched_functions": focus_matches,
                "scope": "retained_video_only",
                "trace_mode": "selected_function_lines",
                "trace_dropped": focus_trace_dropped,
            },
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
            "execution_path": {
                "file": "steps.jsonl",
                "scope": "retained_video_only",
                "video_start": 0.0,
                "video_end": duration,
                "event_count": timeline_event_count,
                "sample_interval_seconds": 0.1,
                "focused_function_trace": "worker_local_exact_lines"
                if focus_enabled or focus_targets else "disabled",
            },
        })
        with open(os.path.join(building, "command_monitor.json"),
                  "w", encoding="utf-8", newline="\n") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
            stream.write("\n")

        # The concat lists contain source paths and are implementation details,
        # not part of the retained evidence folder.
        implementation_paths = [
            video_list, os.path.join(building, "audio_concat.txt")]
        for gap in loop_gaps.values():
            implementation_paths.extend((gap["video"], gap["audio"]))
        for path in implementation_paths:
            try:
                if path:
                    os.remove(path)
            except OSError:
                pass
        os.replace(building, destination)
        runtime_chunk["session_dir"] = destination
        return runtime_chunk
    except Exception:
        shutil.rmtree(building, ignore_errors=True)
        raise
