"""Rebuild a PokeCon recording without overwriting its original files."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import wave

import cv2
import numpy as np


DEFAULT_ROOT = r"D:\SSR_pic"
ZERO_DEFECT_THRESHOLD = 0.01


def ffmpeg_executable():
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as error:
        raise RuntimeError("FFmpegが見つかりません: {}".format(error))


def select_session(initial_dir=DEFAULT_ROOT):
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        return filedialog.askdirectory(
            title="再作成する録画の日付フォルダを選択",
            initialdir=initial_dir if os.path.isdir(initial_dir) else os.getcwd(),
            mustexist=True)
    finally:
        root.destroy()


def video_info(path):
    capture = cv2.VideoCapture(path)
    try:
        if not capture.isOpened():
            raise RuntimeError("動画を開けません: " + path)
        frames = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
        height = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    finally:
        capture.release()
    return {
        "frames": frames,
        "fps": fps,
        "duration_seconds": frames / fps if fps else 0.0,
        "width": width,
        "height": height,
    }


def wav_info(path, scan_zeros=True):
    with wave.open(path, "rb") as audio:
        channels = int(audio.getnchannels())
        sample_width = int(audio.getsampwidth())
        sample_rate = int(audio.getframerate())
        frames = int(audio.getnframes())
        zero_frames = 0
        maximum_zero_run = 0
        current_zero_run = 0
        if scan_zeros:
            if sample_width != 2:
                raise RuntimeError("16-bit PCM以外のWAVには対応していません。")
            while True:
                payload = audio.readframes(1024 * 1024)
                if not payload:
                    break
                samples = np.frombuffer(payload, dtype=np.int16)
                samples = samples.reshape(-1, channels)
                zero = np.all(samples == 0, axis=1)
                zero_frames += int(np.count_nonzero(zero))
                edges = np.flatnonzero(np.diff(np.r_[False, zero, False]))
                runs = edges[1::2] - edges[::2]
                if zero[0]:
                    if runs.size:
                        runs[0] += current_zero_run
                    else:
                        current_zero_run += len(zero)
                else:
                    current_zero_run = 0
                if runs.size:
                    maximum_zero_run = max(
                        maximum_zero_run, int(np.max(runs)))
                    current_zero_run = int(runs[-1]) if zero[-1] else 0
                elif not zero[-1]:
                    current_zero_run = 0
        duration = frames / sample_rate if sample_rate else 0.0
    return {
        "frames": frames,
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width": sample_width,
        "duration_seconds": duration,
        "exact_zero_frames": zero_frames,
        "exact_zero_seconds": zero_frames / sample_rate if sample_rate else 0.0,
        "exact_zero_fraction": zero_frames / frames if frames else 0.0,
        "maximum_exact_zero_ms": (
            maximum_zero_run * 1000.0 / sample_rate if sample_rate else 0.0),
        "zero_scan_performed": bool(scan_zeros),
    }


def presentation_clock_mapping(timing, source_frames, sample_rate):
    """Build a source-PCM to presentation-time map without a fixed offset.

    ``presentation_clock_samples`` records how far contiguous callback PCM has
    advanced compared with the speaker's actual presentation clock.  Mapping
    those samples back onto the WAV timeline repairs accumulating drift while
    preserving the aligned start of the recording.
    """
    audio = timing.get("audio", {}) if isinstance(timing, dict) else {}
    rate = max(1, int(sample_rate))
    source_frames = max(0, int(source_frames))
    target_frames = max(0, int(audio.get("frames", source_frames)))
    trailing = max(0, min(
        source_frames, int(audio.get("trailing_padding_frames", 0) or 0)))
    content_frames = max(0, source_frames - trailing)
    first_offset = float(audio.get("first_presentation_offset_ms", 0.0) or 0.0) / 1000.0
    initial_frames = max(0, int(audio.get("initial_alignment_frames", 0) or 0))

    points = [(0, 0)]
    first_target = max(0, min(target_frames, int(round(first_offset * rate))))
    first_source = max(0, min(content_frames, initial_frames))
    if first_target > 0:
        points.append((first_target, first_source))

    for sample in audio.get("presentation_clock_samples", []) or []:
        if not isinstance(sample, dict):
            continue
        try:
            offset = float(sample.get("offset_seconds"))
            error = float(sample.get("clock_error_ms")) / 1000.0
        except (TypeError, ValueError):
            continue
        target = int(round(max(0.0, offset) * rate))
        if target <= points[-1][0] or target >= target_frames:
            continue
        # Error is measured at the start of the current callback because the
        # current block duration appears on both sides of the diagnostic.
        source_seconds = initial_frames / rate + offset - first_offset + error
        source = max(points[-1][1], min(
            content_frames, int(round(max(0.0, source_seconds) * rate))))
        points.append((target, source))

    if target_frames > points[-1][0]:
        points.append((target_frames, max(points[-1][1], content_frames)))
    elif points:
        points[-1] = (target_frames, max(points[-1][1], content_frames))

    target_points = np.asarray([point[0] for point in points], dtype=np.float64)
    source_points = np.asarray([point[1] for point in points], dtype=np.float64)
    final_drift_frames = int(target_frames - content_frames)
    return {
        "target_points": target_points,
        "source_points": source_points,
        "source_frames": source_frames,
        "content_source_frames": content_frames,
        "target_frames": target_frames,
        "trailing_padding_frames_removed": trailing,
        "final_drift_frames": final_drift_frames,
        "final_drift_seconds": final_drift_frames / rate,
        "mapping_point_count": len(points),
        "first_presentation_offset_ms": first_offset * 1000.0,
        "fixed_offset_ms": 0.0,
    }


def write_presentation_aligned_audio(source_path, timing_path,
                                     destination_path, minimum_drift_ms=20.0):
    """Re-time audio from speaker-clock samples without changing its pitch."""
    with open(timing_path, "r", encoding="utf-8") as stream:
        timing = json.load(stream)
    with wave.open(source_path, "rb") as source:
        if source.getsampwidth() != 2:
            raise RuntimeError("16-bit PCM以外のWAVには対応していません。")
        channels = int(source.getnchannels())
        sample_rate = int(source.getframerate())
        source_frames = int(source.getnframes())
    mapping = presentation_clock_mapping(timing, source_frames, sample_rate)
    drift_ms = abs(mapping["final_drift_seconds"] * 1000.0)
    applied = bool(
        mapping["mapping_point_count"] >= 3
        and mapping["content_source_frames"] > 1
        and mapping["target_frames"] > 1
        and drift_ms >= max(0.0, float(minimum_drift_ms)))
    report = {
        "method": "piecewise_presentation_clock_pitch_preserving_stretch",
        "applied": applied,
        "fixed_offset_ms": 0.0,
        "pitch_preserved": True,
        "pitch_scale": 1.0,
        "sample_rate": sample_rate,
        "channels": channels,
        "source_frames": mapping["source_frames"],
        "content_source_frames": mapping["content_source_frames"],
        "target_frames": mapping["target_frames"],
        "trailing_padding_frames_removed": mapping[
            "trailing_padding_frames_removed"],
        "final_drift_frames": mapping["final_drift_frames"],
        "final_drift_seconds": mapping["final_drift_seconds"],
        "mapping_point_count": mapping["mapping_point_count"],
        "first_presentation_offset_ms": mapping[
            "first_presentation_offset_ms"],
        "destination_path": os.path.abspath(destination_path) if applied else "",
    }
    if not applied:
        return report

    os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)
    content_frames = int(mapping["content_source_frames"])
    target_frames = int(mapping["target_frames"])
    raw_target = mapping["target_points"]
    raw_source = mapping["source_points"]

    # A single sample-rate conversion shifts every musical pitch.  Use short,
    # slowly varying pitch-preserving stretches instead.  Five-second clock
    # points keep the graph small enough for Windows while following drift
    # curvature closely.  Retain the first observation as well so initial
    # alignment is not absorbed into a later interval.
    maximum_segment_frames = max(1, int(round(sample_rate * 5.0)))
    selected = [0]
    if len(raw_target) > 2 and 0 < raw_target[1] < maximum_segment_frames:
        selected.append(1)
    last_target = raw_target[selected[-1]]
    for index in range(selected[-1] + 1, len(raw_target) - 1):
        if raw_target[index] - last_target >= maximum_segment_frames:
            selected.append(index)
            last_target = raw_target[index]
    selected.append(len(raw_target) - 1)
    selected = sorted(set(selected))
    target_points = raw_target[selected]
    source_points = raw_source[selected]
    approximated = np.interp(raw_target, target_points, source_points)
    maximum_clock_error_ms = float(
        np.max(np.abs(approximated - raw_source)) * 1000.0 / sample_rate)

    segments = []
    for index in range(len(target_points) - 1):
        target_start = int(round(target_points[index]))
        target_end = int(round(target_points[index + 1]))
        source_start = int(round(source_points[index]))
        source_end = int(round(source_points[index + 1]))
        target_length = max(1, target_end - target_start)
        source_length = max(0, source_end - source_start)
        segments.append({
            "target_start": target_start,
            "target_end": target_end,
            "source_start": source_start,
            "source_end": source_end,
            "tempo": source_length / target_length,
            "silent": source_length <= 0,
        })

    # Adjacent stretches receive the same small source neighbourhood and are
    # cross-faded.  This avoids a click when the local tempo changes, without
    # moving the start of the recording or introducing a fixed offset.
    default_fade_half_frames = max(1, int(round(sample_rate * 0.040)))
    crossfade_after = [
        not segments[index]["silent"] and not segments[index + 1]["silent"]
        for index in range(len(segments) - 1)
    ]
    # The first presentation observation can be shorter than 40 ms.  FFmpeg's
    # acrossfade may then return success with zero output instead of reporting
    # that its requested overlap is longer than the segment.  Bound each side
    # of every fade by both adjacent base segment lengths.
    fade_half_after = []
    for index, enabled in enumerate(crossfade_after):
        if not enabled:
            fade_half_after.append(0)
            continue
        left_length = max(
            1, segments[index]["target_end"]
            - segments[index]["target_start"])
        right_length = max(
            1, segments[index + 1]["target_end"]
            - segments[index + 1]["target_start"])
        fade_half_after.append(min(
            default_fade_half_frames, left_length, right_length))
    positive_count = sum(not segment["silent"] for segment in segments)
    channel_layout = "mono" if channels == 1 else (
        "stereo" if channels == 2 else "{}c".format(channels))

    def filter_graph(engine):
        graph = []
        source_labels = []
        if positive_count == 1:
            source_labels = ["0:a"]
        elif positive_count > 1:
            source_labels = ["src{}".format(index)
                             for index in range(positive_count)]
            graph.append(
                "[0:a]asplit={}".format(positive_count)
                + "".join("[{}]".format(label) for label in source_labels))

        source_index = 0
        for index, segment in enumerate(segments):
            output_label = "a{}".format(index)
            target_length = (
                segment["target_end"] - segment["target_start"])
            if segment["silent"]:
                graph.append(
                    "anullsrc=r={}:cl={},atrim=end_sample={},"
                    "asetpts=PTS-STARTPTS[{}]".format(
                        sample_rate, channel_layout, target_length,
                        output_label))
                continue

            left_extension = (
                fade_half_after[index - 1] if index > 0
                and crossfade_after[index - 1] else 0)
            right_extension = (
                fade_half_after[index] if index < len(crossfade_after)
                and crossfade_after[index] else 0)
            tempo = float(segment["tempo"])
            source_start = max(0, int(round(
                segment["source_start"] - tempo * left_extension)))
            source_end = min(content_frames, int(round(
                segment["source_end"] + tempo * right_extension)))
            stretch = (
                "rubberband=tempo={:.10f}:pitch=1:transients=crisp:"
                "detector=compound:phase=laminar:window=standard:"
                "smoothing=on:formant=preserved:pitchq=quality:"
                "channels=together".format(tempo)
                if engine == "rubberband"
                else "atempo={:.10f}".format(tempo))
            expected_output_frames = (
                target_length + left_extension + right_extension)
            graph.append(
                "[{}]atrim=start_sample={}:end_sample={},"
                "asetpts=PTS-STARTPTS,{},apad=whole_len={},"
                "atrim=end_sample={}[{}]".format(
                    source_labels[source_index], source_start, source_end,
                    stretch, expected_output_frames,
                    expected_output_frames, output_label))
            source_index += 1

        current = "a0"
        for index in range(len(segments) - 1):
            output_label = "m{}".format(index)
            if crossfade_after[index]:
                crossfade_frames = fade_half_after[index] * 2
                operation = (
                    "[{}][a{}]acrossfade=nb_samples={}:c1=tri:c2=tri[{}]"
                    .format(current, index + 1, crossfade_frames,
                            output_label))
            else:
                operation = (
                    "[{}][a{}]concat=n=2:v=0:a=1[{}]".format(
                        current, index + 1, output_label))
            graph.append(operation)
            current = output_label
        graph.append(
            "[{}]apad=whole_len={},atrim=end_sample={},"
            "asetpts=N/SR/TB[out]".format(
                current, target_frames, target_frames))
        return ";".join(graph)

    ffmpeg = ffmpeg_executable()
    last_error = ""
    used_engine = ""
    output_frames = 0
    for engine in ("rubberband", "atempo"):
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", source_path, "-filter_complex", filter_graph(engine),
            "-map", "[out]", "-ar", str(sample_rate), "-ac", str(channels),
            "-c:a", "pcm_s16le", destination_path,
        ]
        completed = subprocess.run(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace")
        candidate_frames = 0
        if completed.returncode == 0 and os.path.isfile(destination_path):
            try:
                with wave.open(destination_path, "rb") as output:
                    candidate_frames = int(output.getnframes())
            except (OSError, EOFError, wave.Error):
                candidate_frames = 0
        if candidate_frames == target_frames:
            used_engine = engine
            output_frames = candidate_frames
            break
        last_error = completed.stderr.strip()
        if not last_error:
            last_error = (
                "FFmpegが予定{} framesに対し{} framesを出力"
                .format(target_frames, candidate_frames))
    if not used_engine:
        raise RuntimeError(
            "音程維持での提示時計補正に失敗しました: " + last_error)

    tempos = [float(segment["tempo"])
              for segment in segments if not segment["silent"]]
    active_crossfades = [frames * 2 for frames in fade_half_after if frames]
    report.update({
        "engine": used_engine,
        "segment_seconds": 5.0,
        "segment_count": len(segments),
        "segment_output_length_enforced": True,
        "crossfade_ms": (
            max(active_crossfades) * 1000.0 / sample_rate
            if active_crossfades else 0.0),
        "minimum_crossfade_ms": (
            min(active_crossfades) * 1000.0 / sample_rate
            if active_crossfades else 0.0),
        "maximum_mapping_approximation_error_ms": maximum_clock_error_ms,
        "minimum_tempo": min(tempos) if tempos else 1.0,
        "maximum_tempo": max(tempos) if tempos else 1.0,
        "output_frames": output_frames,
        "output_duration_seconds": output_frames / sample_rate,
    })
    return report


def store_presentation_alignment_report(timing_path, report):
    """Atomically append mux-time audio alignment evidence to timing JSON."""
    with open(timing_path, "r", encoding="utf-8") as stream:
        timing = json.load(stream)
    timing.setdefault("audio", {})["presentation_alignment_repair"] = dict(report)
    temporary = timing_path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(timing, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, timing_path)


def write_without_exact_zeros(source_path, destination_path):
    kept_frames = 0
    removed_frames = 0
    with wave.open(source_path, "rb") as source:
        if source.getsampwidth() != 2:
            raise RuntimeError("16-bit PCM以外のWAVには対応していません。")
        channels = source.getnchannels()
        with wave.open(destination_path, "wb") as destination:
            destination.setparams(source.getparams())
            while True:
                payload = source.readframes(1024 * 1024)
                if not payload:
                    break
                samples = np.frombuffer(payload, dtype=np.int16)
                samples = samples.reshape(-1, channels)
                keep = np.any(samples != 0, axis=1)
                cleaned = np.ascontiguousarray(samples[keep])
                destination.writeframesraw(cleaned.tobytes())
                kept_frames += int(np.count_nonzero(keep))
                removed_frames += int(len(keep) - np.count_nonzero(keep))
    return kept_frames, removed_frames


def media_duration(ffmpeg, path):
    completed = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", path],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace")
    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", completed.stderr)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600.0 + int(minutes) * 60.0 + float(seconds)


def audio_advance_filter(milliseconds, prefix=""):
    seconds = max(0.0, float(milliseconds) / 1000.0)
    if seconds <= 0.0:
        return ""
    return (
        "{}atrim=start={:.6f},asetpts=PTS-STARTPTS,"
        "apad=pad_dur={:.6f}".format(prefix, seconds, seconds))


def create_audio_advance_variants(source_mp4, offsets_ms):
    """Create quick comparison MP4s while stream-copying the video track."""
    source_mp4 = os.path.abspath(source_mp4)
    if not os.path.isfile(source_mp4):
        raise RuntimeError("比較元MP4が見つかりません: " + source_mp4)
    offsets = sorted({max(0, int(round(float(value))))
                      for value in offsets_ms if float(value) > 0.0})
    if not offsets:
        raise ValueError("1つ以上の正の音声前進値が必要です。")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(
        os.path.dirname(source_mp4), "offset_compare_" + stamp)
    os.makedirs(output_dir, exist_ok=False)
    ffmpeg = ffmpeg_executable()
    results = []
    for milliseconds in offsets:
        output_mp4 = os.path.join(
            output_dir, "audio_advance_{:04d}ms.mp4".format(milliseconds))
        filter_graph = "[0:a]{}[a]".format(
            audio_advance_filter(milliseconds))
        command = [
            ffmpeg, "-y", "-i", source_mp4,
            "-filter_complex", filter_graph,
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac",
            "-brand", "mp42", "-tag:v", "avc1",
            "-video_track_timescale", "60000",
            "-movflags", "+faststart", output_mp4,
        ]
        print(
            "[録画再同期] 音声を{}ms前進: {}".format(
                milliseconds, output_mp4), flush=True)
        completed = subprocess.run(command)
        if completed.returncode != 0 or not os.path.isfile(output_mp4):
            raise RuntimeError(
                "{}ms比較版の作成に失敗しました。".format(milliseconds))
        results.append({
            "audio_advance_ms": milliseconds,
            "path": output_mp4,
            "duration_seconds": media_duration(ffmpeg, output_mp4),
        })
    report = {
        "schema_version": 1,
        "source_mp4": source_mp4,
        "video_stream_copied": True,
        "variants": results,
        "completed_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    report_path = os.path.join(output_dir, "offset_comparison_report.json")
    with open(report_path, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return report


def rebuild_presentation_clock_session(session_dir):
    """Create a no-fixed-offset MP4 from the recorded presentation clocks."""
    session_dir = os.path.abspath(session_dir)
    wav_path = os.path.join(session_dir, "recording.wav")
    timing_path = os.path.join(session_dir, "recording_timing.json")
    source_mp4 = os.path.join(session_dir, "recording.mp4")
    source_avi = os.path.join(session_dir, "recording.avi")
    if not os.path.isfile(wav_path) or not os.path.isfile(timing_path):
        raise RuntimeError(
            "recording.wav と recording_timing.json が必要です: " + session_dir)
    source_video = (
        source_mp4
        if os.path.isfile(source_mp4) and os.path.getsize(source_mp4) > 1024
        else source_avi)
    if not os.path.isfile(source_video):
        raise RuntimeError("recording.mp4 または recording.avi が必要です。")

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(
        session_dir, "presentation_rebuild_" + stamp)
    os.makedirs(output_dir, exist_ok=False)
    aligned_wav = os.path.join(
        output_dir, "recording_presentation_aligned.wav")
    output_mp4 = os.path.join(
        output_dir, "recording_presentation_aligned.mp4")
    report_path = os.path.join(output_dir, "presentation_rebuild_report.json")
    alignment = write_presentation_aligned_audio(
        wav_path, timing_path, aligned_wav)
    if not alignment.get("applied"):
        raise RuntimeError(
            "提示時計ドリフトが検出されず、再構築を適用しませんでした。")

    ffmpeg = ffmpeg_executable()
    command = [
        ffmpeg, "-y", "-i", source_video, "-i", aligned_wav,
        "-map", "0:v:0", "-map", "1:a:0",
    ]
    if source_video.lower().endswith(".mp4"):
        command.extend(["-c:v", "copy"])
    else:
        command.extend([
            "-r", "60", "-c:v", "libx264", "-threads", "2",
            "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"])
    command.extend([
        "-c:a", "aac", "-shortest",
        "-brand", "mp42", "-tag:v", "avc1",
        "-video_track_timescale", "60000",
        "-movflags", "+faststart", output_mp4])
    report = {
        "schema_version": 1,
        "source_session": session_dir,
        "source_video": source_video,
        "source_audio": wav_path,
        "source_timing": timing_path,
        "original_files_preserved": True,
        "video_stream_copied": source_video.lower().endswith(".mp4"),
        "fixed_offset_ms": 0.0,
        "alignment": alignment,
        "ffmpeg_command": command,
        "output_mp4": output_mp4,
        "status": "encoding",
    }
    with open(report_path, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(
        "[録画再同期] 提示時計ドリフトを区間補正（固定offsetなし）: "
        + output_mp4, flush=True)
    completed = subprocess.run(command)
    if completed.returncode != 0 or not os.path.isfile(output_mp4):
        report["status"] = "failed"
        report["ffmpeg_returncode"] = int(completed.returncode)
        with open(report_path, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        raise RuntimeError("提示時計ベースMP4の再作成に失敗しました。")
    output_video = video_info(output_mp4)
    output_audio = wav_info(aligned_wav, scan_zeros=True)
    output_duration = media_duration(ffmpeg, output_mp4)
    report.update({
        "status": "complete",
        "output_video": output_video,
        "output_audio": output_audio,
        "output_media_duration_seconds": output_duration,
        "completed_at": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    with open(report_path, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return report


def repair_session(session_dir, repair_synthetic_silence=True,
                   audio_advance_ms=0.0):
    session_dir = os.path.abspath(session_dir)
    avi_path = os.path.join(session_dir, "recording.avi")
    wav_path = os.path.join(session_dir, "recording.wav")
    if not os.path.isfile(avi_path) or not os.path.isfile(wav_path):
        raise RuntimeError(
            "recording.avi と recording.wav の両方が必要です: " + session_dir)

    source_video = video_info(avi_path)
    source_audio = wav_info(wav_path)
    if source_video["frames"] < 1 or source_audio["duration_seconds"] <= 0.0:
        raise RuntimeError("映像または音声の長さを取得できませんでした。")
    corrected_fps = (
        source_video["frames"] / source_audio["duration_seconds"])
    defect_detected = (
        source_audio["exact_zero_fraction"] >= ZERO_DEFECT_THRESHOLD)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(session_dir, "sync_repair_" + stamp)
    os.makedirs(output_dir, exist_ok=False)
    cleaned_wav = os.path.join(output_dir, "recording_audio_continuity.wav")
    output_mp4 = os.path.join(output_dir, "recording_repaired.mp4")
    report_path = os.path.join(output_dir, "repair_report.json")
    ffmpeg = ffmpeg_executable()

    audio_input = wav_path
    audio_filters = []
    removed_frames = 0
    cleaned_frames = source_audio["frames"]
    if defect_detected and repair_synthetic_silence:
        cleaned_frames, removed_frames = write_without_exact_zeros(
            wav_path, cleaned_wav)
        cleaned_duration = cleaned_frames / source_audio["sample_rate"]
        # The previous recorder discarded PCM around jittery timestamps and
        # replaced it with exact zeros. Removed samples cannot be recovered;
        # stretch the remaining continuous PCM over the original wall time so
        # later sounds do not retain the accumulated delay.
        tempo = cleaned_duration / source_audio["duration_seconds"]
        audio_filters.append("atempo={:.10f}".format(tempo))
        audio_input = cleaned_wav
    advance_filter = audio_advance_filter(audio_advance_ms)
    if advance_filter:
        audio_filters.append(advance_filter)
    audio_filter = ",".join(audio_filters)

    command = [
        ffmpeg, "-y", "-r", "{:.9f}".format(corrected_fps),
        "-i", avi_path, "-i", audio_input,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
    ]
    if audio_filter:
        command.extend(["-filter:a", audio_filter])
    command.extend([
        "-c:a", "aac", "-shortest",
        "-brand", "mp42", "-tag:v", "avc1",
        "-video_track_timescale", "60000", "-movflags", "+faststart",
        output_mp4,
    ])

    report = {
        "schema_version": 1,
        "source_session": session_dir,
        "original_files_preserved": True,
        "source_video": source_video,
        "source_audio": source_audio,
        "corrected_fps": corrected_fps,
        "synthetic_silence_defect_detected": defect_detected,
        "synthetic_silence_repair_applied": bool(
            defect_detected and repair_synthetic_silence),
        "removed_exact_zero_frames": removed_frames,
        "cleaned_audio_frames": cleaned_frames,
        "audio_filter": audio_filter or "",
        "audio_advance_ms": float(audio_advance_ms),
        "output_mp4": output_mp4,
        "ffmpeg_command": command,
        "status": "encoding",
    }
    with open(report_path, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)

    print("[録画再同期] 元ファイルは変更しません: " + session_dir, flush=True)
    print("[録画再同期] 補正FPS: {:.6f}".format(corrected_fps), flush=True)
    if defect_detected:
        print(
            "[録画再同期] 旧補正由来の完全無音を検出: {:.3f}秒 ({:.2f}%)".format(
                source_audio["exact_zero_seconds"],
                source_audio["exact_zero_fraction"] * 100.0), flush=True)
    print("[録画再同期] MP4を作成中: " + output_mp4, flush=True)
    completed = subprocess.run(command)
    if completed.returncode != 0 or not os.path.isfile(output_mp4):
        report["status"] = "failed"
        report["ffmpeg_returncode"] = int(completed.returncode)
        with open(report_path, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        raise RuntimeError("FFmpegによるMP4再作成に失敗しました。")

    output_video = video_info(output_mp4)
    output_duration = media_duration(ffmpeg, output_mp4)
    duration_error = abs(
        output_duration - source_audio["duration_seconds"])
    report.update({
        "status": "complete" if duration_error <= 0.10 else "verify",
        "output_video": output_video,
        "output_media_duration_seconds": output_duration,
        "duration_error_seconds": duration_error,
        "completed_at": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    with open(report_path, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(
        "[録画再同期] 完了: 尺差 {:.3f}秒 / {}".format(
            duration_error, output_mp4), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="AVIとWAVからFPS・音声連続性を補正したMP4を再作成")
    parser.add_argument("session", nargs="?", help="日付録画フォルダ")
    parser.add_argument(
        "--fps-only", action="store_true",
        help="旧タイムスタンプ補正の完全無音を修復せずFPSだけ補正")
    parser.add_argument(
        "--audio-advance-ms", type=float, default=0.0,
        help="再作成時に音声を指定ミリ秒だけ前へ移動")
    parser.add_argument(
        "--compare-offsets", default="",
        help="MP4を映像再圧縮せず比較版を作成（例: 250,500,750,1000）")
    parser.add_argument(
        "--presentation-clock", action="store_true",
        help="記録済み提示時計から蓄積ドリフトを区間補正（固定offsetなし）")
    args = parser.parse_args(argv)
    session = args.session or select_session()
    if not session:
        return 1
    try:
        if args.compare_offsets:
            offsets = [float(value.strip())
                       for value in args.compare_offsets.split(",")
                       if value.strip()]
            create_audio_advance_variants(session, offsets)
            return 0
        if args.presentation_clock:
            rebuild_presentation_clock_session(session)
            return 0
        repair_session(
            session, repair_synthetic_silence=not args.fps_only,
            audio_advance_ms=args.audio_advance_ms)
        return 0
    except Exception as error:
        print("[録画再同期] エラー: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
