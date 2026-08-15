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
    }


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
        "-c:a", "aac", "-shortest", "-movflags", "+faststart",
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
        repair_session(
            session, repair_synthetic_silence=not args.fps_only,
            audio_advance_ms=args.audio_advance_ms)
        return 0
    except Exception as error:
        print("[録画再同期] エラー: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
