"""Synchronized-ish capture recorder and low-cost template-triggered segments."""
from __future__ import annotations

import ctypes
import datetime
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
import wave
from collections import deque

import cv2
import numpy as np

from AudioLevelControl import AdaptivePeakNormalizer
from ProcessShutdown import process_is_alive


DETECTION_STOP_REQUESTED = "template_stop_requested"
FINALIZE_MANIFEST_NAME = "mp4_finalize_job.json"
SEGMENT_MERGE_VIDEO_NAME = "recording.youtube_merge.avi"
SEGMENT_MERGE_WAV_NAME = "recording.youtube_merge.wav"


class FinalizeJobAlreadyRunning(RuntimeError):
    """Raised when another live process owns a durable finalization job."""


def _json_cleanup_rules(cleanup_rules):
    """Remove decoded image arrays while keeping enough data to reload them."""
    serialized = []
    for rule in cleanup_rules or []:
        item = {
            str(key): value for key, value in dict(rule).items()
            if key != "image" and isinstance(
                value, (str, int, float, bool, type(None)))
        }
        if item.get("path"):
            item["path"] = os.path.abspath(str(item["path"]))
        serialized.append(item)
    return serialized


def _write_json_atomic(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = "{}.{}.{}.tmp".format(
        path, os.getpid(), threading.get_ident())
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            try:
                os.fsync(stream.fileno())
            except OSError:
                pass
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass


def write_finalize_manifest(video_path, wav_path, mp4_path, output_fps,
                            elapsed, process_audio_gain=1.0, discard=False,
                            cleanup_rules=None, minimum_duration=0.0,
                            status="pending", worker_pid=0,
                            youtube_upload_job_path=""):
    """Persist one MP4 job so PokeCon may close before encoding starts."""
    manifest_path = os.path.join(
        os.path.dirname(os.path.abspath(video_path)), FINALIZE_MANIFEST_NAME)
    payload = {
        "version": 1,
        "status": str(status or "pending"),
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "video_path": os.path.abspath(video_path),
        "wav_path": os.path.abspath(wav_path),
        "mp4_path": os.path.abspath(mp4_path),
        "output_fps": float(output_fps),
        "elapsed": float(elapsed),
        "process_audio_gain": float(process_audio_gain),
        "discard": bool(discard),
        "cleanup_rules": _json_cleanup_rules(cleanup_rules),
        "minimum_duration": float(minimum_duration),
    }
    upload_job_path = str(youtube_upload_job_path or "").strip()
    if upload_job_path:
        payload["youtube_upload_job_path"] = os.path.abspath(
            upload_job_path)
    if worker_pid:
        payload["worker_pid"] = int(worker_pid)
    _write_json_atomic(manifest_path, payload)
    return manifest_path


def load_finalize_manifest(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict) or int(payload.get("version", 0)) != 1:
        raise ValueError("未対応のMP4作成ジョブです。")
    return payload


def _finalize_manifest_needs_work(payload):
    """Return whether a durable MP4 job is safe to start or recover."""
    status = str(dict(payload or {}).get("status", "pending") or "pending")
    if status in ("pending", "failed"):
        return True
    if status in ("recording", "closing", "processing"):
        # A hard PokeCon/PC interruption can leave the last durable state at
        # ``processing``.  Retry only after its recorded owner is gone so a
        # live external finalizer is never raced by a second FFmpeg process.
        return not process_is_alive(dict(payload or {}).get("worker_pid", 0))
    return False


def _claim_finalize_manifest(manifest_path):
    """Atomically claim a manifest, recovering a dead owner's stale lock."""
    lock_path = os.path.abspath(manifest_path) + ".lock"
    for _attempt in range(3):
        token = uuid.uuid4().hex
        try:
            descriptor = os.open(
                lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                with open(lock_path, "r", encoding="utf-8") as stream:
                    owner = json.load(stream)
            except (OSError, ValueError, TypeError):
                # os.open(O_EXCL) publishes the directory entry immediately,
                # just before its owner writes JSON.  A second process must not
                # mistake that tiny construction window for a stale lock.
                try:
                    lock_age = max(
                        0.0, time.time() - os.path.getmtime(lock_path))
                except OSError:
                    lock_age = 0.0
                if lock_age < 30.0:
                    raise FinalizeJobAlreadyRunning(
                        "別のMP4作成処理がこの録画を確保中です。")
                owner = {}
            if process_is_alive(dict(owner or {}).get("worker_pid", 0)):
                raise FinalizeJobAlreadyRunning(
                    "別のMP4作成処理がこの録画を確定中です。")
            try:
                os.remove(lock_path)
            except FileNotFoundError:
                pass
            except OSError as error:
                raise FinalizeJobAlreadyRunning(
                    "MP4作成ジョブの古いロックを回収できません。") from error
            continue
        payload = json.dumps({
            "version": 1,
            "worker_pid": os.getpid(),
            "token": token,
            "claimed_at": datetime.datetime.now().isoformat(
                timespec="seconds"),
        }, ensure_ascii=False).encode("utf-8")
        try:
            os.write(descriptor, payload)
            try:
                os.fsync(descriptor)
            except OSError:
                pass
        finally:
            os.close(descriptor)
        return lock_path, token
    raise FinalizeJobAlreadyRunning("MP4作成ジョブを確保できません。")


def _release_finalize_manifest_claim(lock_path, token):
    try:
        with open(lock_path, "r", encoding="utf-8") as stream:
            owner = json.load(stream)
        if str(dict(owner or {}).get("token", "") or "") != str(token):
            return
        os.remove(lock_path)
    except (OSError, ValueError, TypeError):
        pass


def retire_finalize_manifest_for_segment_merge(manifest_path,
                                               expected_video_path):
    """Atomically hand one raw clip from the MP4 worker to a segment merge.

    The same ``.lock`` protocol used by :func:`finalize_recording_manifest`
    closes the check/use race: an already-running per-clip encoder wins and
    the caller retries, while a queued encoder sees the retired manifest and
    cannot start after the merge has claimed its AVI.
    """
    path = os.path.abspath(str(manifest_path or ""))
    expected_video = os.path.abspath(str(expected_video_path or ""))
    if os.path.basename(path) != FINALIZE_MANIFEST_NAME:
        raise ValueError("MP4確定ジョブのファイル名が不正です。")
    if os.path.normcase(os.path.dirname(path)) != os.path.normcase(
            os.path.dirname(expected_video)):
        raise ValueError("MP4確定ジョブと結合元動画の場所が一致しません。")
    if not os.path.isfile(path):
        return True

    lock_path, claim_token = _claim_finalize_manifest(path)
    try:
        if not os.path.isfile(path):
            return True
        try:
            payload = load_finalize_manifest(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            # Commands' command_monitor.json is the durable merge journal.
            # Once this exact sidecar has been claimed in the same directory,
            # a malformed legacy manifest may safely be retired while the raw
            # AVI remains untouched for reconciliation.
            payload = {}
        status = str(dict(payload or {}).get(
            "status", "pending") or "pending").strip().lower()
        owner_pid = dict(payload or {}).get("worker_pid", 0)
        if (status in ("recording", "closing", "processing")
                and process_is_alive(owner_pid)):
            # A live capture is not locked yet, and builds predating the lock
            # protocol advertised an active encoder only through this PID.
            # Conservatively honour either owner before touching its AVI.
            raise FinalizeJobAlreadyRunning(
                "録画または旧方式のMP4作成処理がこの動画を使用中です。")
        saved_video = str(dict(payload or {}).get("video_path", "") or "")
        if saved_video and os.path.normcase(os.path.abspath(saved_video)) != \
                os.path.normcase(expected_video):
            raise ValueError("MP4確定ジョブが別の結合元動画を参照しています。")
        os.remove(path)
        return True
    finally:
        _release_finalize_manifest_claim(lock_path, claim_token)


def prepare_segment_merge_source_alias(source_path):
    """Create a no-copy hard-link which survives a legacy finalizer race.

    A pre-lock worker can load a pending manifest immediately before the new
    merger retires it, then delete ``recording.avi`` after its own MP4 encode.
    The merge reads this second directory entry instead.  Both names reference
    the same immutable, already-closed bytes and therefore consume no extra
    recording capacity.
    """
    source = os.path.abspath(str(source_path or ""))
    name = os.path.basename(source).lower()
    aliases = {
        "recording.avi": SEGMENT_MERGE_VIDEO_NAME,
        "recording.wav": SEGMENT_MERGE_WAV_NAME,
    }
    if name not in aliases:
        raise ValueError("結合保護リンクの録画ファイル名が不正です。")
    alias = os.path.join(os.path.dirname(source), aliases[name])
    if os.path.isfile(alias):
        if os.path.exists(source):
            try:
                if not os.path.samefile(source, alias):
                    raise OSError("既存の結合保護リンクが別ファイルです。")
            except OSError:
                raise
        return alias
    if not os.path.isfile(source):
        raise OSError("結合元の録画が見つかりません: " + source)
    try:
        os.link(source, alias)
    except FileExistsError:
        if not os.path.isfile(alias):
            raise
        if os.path.exists(source) and not os.path.samefile(source, alias):
            raise OSError("競合した結合保護リンクが別ファイルです。")
    return alias


def discover_finalize_manifests(output_dir):
    """Find durable jobs, including work abandoned by a dead finalizer."""
    root = os.path.abspath(output_dir or "Recordings")
    if not os.path.isdir(root):
        return []
    found = []
    try:
        entries = list(os.scandir(root))
    except OSError:
        return []
    for entry in entries:
        if not entry.is_dir(follow_symlinks=False):
            continue
        path = os.path.join(entry.path, FINALIZE_MANIFEST_NAME)
        if not os.path.isfile(path):
            continue
        try:
            needs_work = _finalize_manifest_needs_work(
                load_finalize_manifest(path))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            needs_work = True
        if needs_work:
            found.append(os.path.abspath(path))
    return sorted(found)


def evenly_spaced_frame_indexes(total_frames, maximum_samples=120):
    """Return bounded sample positions spanning the complete recording."""
    try:
        total_frames = max(0, int(total_frames))
        maximum_samples = max(0, int(maximum_samples))
    except (TypeError, ValueError, OverflowError):
        return []
    sample_count = min(total_frames, maximum_samples)
    if sample_count <= 0:
        return []
    if sample_count == 1:
        return [0]
    return [
        position * (total_frames - 1) // (sample_count - 1)
        for position in range(sample_count)
    ]


def set_current_thread_below_normal():
    """Keep a recording finalizer from starving capture and Tk on Windows."""
    if os.name != "nt":
        return False
    try:
        kernel32 = ctypes.windll.kernel32
        current_thread = kernel32.GetCurrentThread()
        # THREAD_PRIORITY_BELOW_NORMAL.  This changes only the finalizer
        # worker, not Camera, native preview, or the Tk window thread.
        return bool(kernel32.SetThreadPriority(current_thread, -1))
    except (AttributeError, OSError):
        return False


def audio_callback_presentation_time(time_info, now=None):
    """Map PortAudio's scheduled DAC time onto Python's monotonic clock."""
    now = time.monotonic() if now is None else float(now)

    def value(name):
        try:
            if isinstance(time_info, dict):
                return float(time_info.get(name))
            return float(getattr(time_info, name))
        except (AttributeError, TypeError, ValueError):
            return None

    current = value("currentTime")
    presented = value("outputBufferDacTime")
    if current is None or presented is None:
        return now
    # Reject a broken host timestamp rather than adding seconds of silence.
    return now + max(0.0, min(2.0, presented - current))


class CaptureRecorder:
    def __init__(self, output_dir="Recordings", start_finalize_worker=True):
        self.output_dir = output_dir
        self.video = None
        self.audio = None
        self.audio_stream = None
        self.audio_queue = None
        self.audio_writer_thread = None
        self.audio_start_thread = None
        self.audio_start_started_at = 0.0
        self.audio_start_finished_at = 0.0
        self.audio_start_error = ""
        self.audio_sample_rate = 0
        self.audio_channels = 0
        self.audio_gain = 1.0
        self.audio_peak_normalizer = None
        self.audio_level_options = {}
        self.audio_frames_written = 0
        self.audio_pending_gap_frames = 0
        self.audio_gap_frames_written = 0
        self.audio_trailing_silence_frames = 0
        self.audio_queue_dropped_frames = 0
        self.audio_callback_warning_count = 0
        self.audio_queue_drop_count = 0
        self.audio_write_error = None
        self.audio_selected_device = ""
        self.audio_actual_device_index = None
        self.audio_actual_device_name = ""
        self.audio_host_api = ""
        self.audio_stream_latency = 0.0
        self.audio_capture_latency = 0.0
        self.audio_playback_latency = 0.0
        self.audio_tap_point = ""
        self.audio_source_mode = ""
        self.audio_monitor = None
        self.audio_monitor_listener_token = None
        self.audio_accepting_packets = False
        self.audio_first_presentation_at = 0.0
        self.audio_initial_alignment_frames = 0
        self.audio_last_presentation_at = 0.0
        self.audio_last_presentation_frames = 0
        self.audio_presentation_frames = 0
        self.audio_presentation_timestamp_regressions = 0
        self.audio_stop_target_frames = None
        self.audio_stop_overrun_frames = 0
        self.audio_monitor_counter_start = {}
        self.audio_monitor_counter_end = {}
        self.process_audio = None
        self.process_audio_gain = 1.0
        self.active = False
        # A normal recorder accepts frames/audio immediately.  Rotation may
        # explicitly suspend this at ``start()`` until the handoff timestamp,
        # but helpers/tests that prepare an already-active recorder must keep
        # the long-standing immediate-timeline behaviour.
        self.timeline_active = True
        self.last_detection = 0.0
        self.last_check = 0.0
        self.template = None
        self.template_path = ""
        self.trigger_rules = []
        self.cleanup_rules = []
        self.minimum_duration = 0.0
        self._capture_cleanup_rules = []
        self._capture_minimum_duration = 0.0
        self.last_score = None
        self.last_scores = []
        # Immutable snapshots consumed by the recording compositor.  Keeping
        # this data outside Tk lets the video overlay be drawn without taking
        # a screenshot of the GUI or querying widgets from a worker thread.
        self.last_detection_details = []
        self.last_detection_checked_at = 0.0
        self.last_found = False
        self.last_roi = (0, 0, 0, 0)
        self.lock = threading.Lock()
        # Stop may be requested concurrently by a segment rotation, an
        # InputSet change, and application shutdown.  Only one caller may
        # close the capture resources or enqueue the durable MP4 job.
        self.stop_lock = threading.Lock()
        self.frame_lock = threading.Lock()
        self.video_frame_condition = threading.Condition(self.frame_lock)
        self.writer_thread = None
        self.writer_stop = None
        self.latest_frame = None
        self.video_frame_queue = deque()
        self.video_frame_queue_max_depth = 0
        self.video_compositor_queue_max_depth = 0
        self.video_stop_at = 0.0
        self.video_current_frame = None
        self.video_coalesced_presentation_frames = 0
        self.video_timestamp_regressions = 0
        self.video_delivery_delay_total = 0.0
        self.video_delivery_delay_max = 0.0
        self.video_delivery_delay_samples = 0
        self.video_first_presentation_at = 0.0
        self.video_last_presentation_at = 0.0
        self.video_presentation_frames = 0
        self.video_presentation_mode = ""
        self.video_codec = ""
        self.video_stop_pending_presentations = 0
        self.video_stop_target_frames = 0
        self.video_stop_pending_frames = 0
        self.video_stop_drain_seconds = 0.0
        self.video_stop_drain_timeout = 0.0
        self.video_stop_drain_timed_out = False
        self.video_close_pending = False
        self.video_writer_error = None
        self.video_writer_released = False
        self._video_late_close_thread = None
        self.video_queue_depth_samples = []
        self.video_queue_last_sample_at = 0.0
        self.audio_presentation_clock_samples = []
        self.audio_presentation_clock_last_sample_at = 0.0
        # Final MP4 encoding runs after capture has stopped.  Keep an explicit
        # count so the window can avoid being destroyed while ffmpeg still has
        # the recording files open.
        self._finalizing_count = 0
        # Commands monitoring rotates short clips.  Starting one ffmpeg thread
        # per clip lets encoders pile up when conversion is slower than
        # capture, eventually taking CPU away from Commands and controller
        # input.  Keep the jobs durable on disk and encode them one at a time.
        self._finalize_queue = queue.Queue()
        self._finalize_thread = None
        self._finalize_retirement_requested = False
        self.defer_finalization = False
        # YouTube jobs need a crash-recoverable MP4 manifest even when the
        # normal in-process finalizer starts immediately.
        self.durable_finalization = False
        self.youtube_upload_job_path = ""
        self._active_finalize_manifest = ""
        self._deferred_finalize_manifests = []
        self._inprocess_finalize_manifests = set()
        if start_finalize_worker:
            self._finalize_thread = threading.Thread(
                target=self._finalize_worker, daemon=True,
                name="CaptureRecordingFinalizer")
            self._finalize_thread.start()

    def start(self, frame, fps, audio_device="", audio_gain_percent=100,
              cleanup_rules=None, minimum_duration=0,
              audio_level_options=None, async_audio_start=False,
              defer_timeline_activation=False,
              session_started_callback=None):
        if self.active or frame is None:
            return
        writer_thread = self.writer_thread
        if (self.video_close_pending or self.video is not None
                or (writer_thread is not None and writer_thread.is_alive())):
            # A timed-out close must never reuse the mutable queue/video
            # fields while its old writer still owns them.  Doing so lets two
            # threads consume the new session and write the same VideoWriter.
            raise RuntimeError(
                "前回の録画映像を安全に閉じているため、新しい録画を開始できません。")
        self._active_finalize_manifest = ""
        self.youtube_upload_job_path = ""
        # Sub-second suffix prevents a rotating Commands monitor from reusing
        # the previous chunk folder when capture is restarted within a second.
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        # Keep all artefacts belonging to one recording together.  A new
        # template-triggered segment gets its own timestamped folder too.
        self.session_dir = os.path.join(self.output_dir, stamp)
        os.makedirs(self.session_dir, exist_ok=True)
        self.video_path = os.path.join(self.session_dir, "recording.avi")
        self.wav_path = os.path.join(self.session_dir, "recording.wav")
        self.mp4_path = os.path.join(self.session_dir, "recording.mp4")
        height, width = frame.shape[:2]
        self.video, self.video_codec = self._open_video_writer(
            self.video_path, fps, (width, height))
        if self.video is None:
            raise RuntimeError("動画ファイルを作成できませんでした。")
        self.frames_written = 0
        # Presentation timestamps decide which configured-CFR slots are
        # written.  Wall-clock frames/elapsed remains diagnostic only.
        self.started_at = time.monotonic()
        self.timeline_active = not bool(defer_timeline_activation)
        self.requested_fps = max(1.0, float(fps))
        initial_frame = frame.copy()
        self.latest_frame = initial_frame
        self.video_current_frame = initial_frame
        self.video_frame_queue.clear()
        self.video_frame_queue_max_depth = 0
        self.video_compositor_queue_max_depth = 0
        self.video_stop_at = 0.0
        self.video_coalesced_presentation_frames = 0
        self.video_timestamp_regressions = 0
        self.video_delivery_delay_total = 0.0
        self.video_delivery_delay_max = 0.0
        self.video_delivery_delay_samples = 0
        self.writer_stop = threading.Event()
        self.process_audio_gain = 1.0
        self.audio_level_options = dict(audio_level_options or {})
        self.audio_peak_normalizer = None
        self.audio_sample_rate = 0
        self.audio_channels = 0
        self.audio_frames_written = 0
        self.audio_pending_gap_frames = 0
        self.audio_gap_frames_written = 0
        self.audio_trailing_silence_frames = 0
        self.audio_queue_dropped_frames = 0
        self.audio_callback_warning_count = 0
        self.audio_queue_drop_count = 0
        self.audio_write_error = None
        self.audio_selected_device = str(audio_device or "")
        self.audio_actual_device_index = None
        self.audio_actual_device_name = ""
        self.audio_host_api = ""
        self.audio_stream_latency = 0.0
        self.audio_capture_latency = 0.0
        self.audio_playback_latency = 0.0
        self.audio_tap_point = ""
        self.audio_source_mode = ""
        self.audio_monitor_listener_token = None
        self.audio_accepting_packets = False
        self.audio_first_presentation_at = 0.0
        self.audio_initial_alignment_frames = 0
        self.audio_last_presentation_at = 0.0
        self.audio_last_presentation_frames = 0
        self.audio_presentation_frames = 0
        self.audio_presentation_timestamp_regressions = 0
        self.audio_stop_target_frames = None
        self.audio_stop_overrun_frames = 0
        self.audio_monitor_counter_start = {}
        self.audio_monitor_counter_end = {}
        self.audio_start_thread = None
        self.audio_start_started_at = 0.0
        self.audio_start_finished_at = 0.0
        self.audio_start_error = ""
        self.video_first_presentation_at = 0.0
        self.video_last_presentation_at = 0.0
        self.video_presentation_frames = 0
        self.video_presentation_mode = ""
        self.video_stop_pending_presentations = 0
        self.video_stop_target_frames = 0
        self.video_stop_pending_frames = 0
        self.video_stop_drain_seconds = 0.0
        self.video_stop_drain_timeout = 0.0
        self.video_stop_drain_timed_out = False
        self.video_close_pending = False
        self.video_writer_error = None
        self.video_writer_released = False
        self._video_late_close_thread = None
        self.video_queue_depth_samples = []
        self.video_queue_last_sample_at = 0.0
        self.audio_presentation_clock_samples = []
        self.audio_presentation_clock_last_sample_at = 0.0
        if cleanup_rules is not None:
            self.cleanup_rules = list(cleanup_rules)
            self.minimum_duration = max(0.0, float(minimum_duration))
        # Rules belong to the segment that just started. Applying another
        # InputSet while Stop drains asynchronously must not retroactively
        # discard this recording under the new InputSet's cleanup policy.
        self._capture_cleanup_rules = list(self.cleanup_rules)
        self._capture_minimum_duration = float(self.minimum_duration)
        self.active = True
        # MJPEG encoding stays outside Tk.  The worker advances the CFR file
        # from preview presentation timestamps, not from the later time at
        # which an asynchronously composed frame happens to arrive here.
        self.writer_thread = threading.Thread(target=self._video_writer_loop, daemon=True)
        self.writer_thread.start()
        if self.defer_finalization or self.durable_finalization:
            # Publish a recovery journal while capture is still live, rather
            # than waiting until Stop.  A power loss or hard process kill can
            # then salvage the AVI/WAV after this owner PID disappears.
            try:
                self._active_finalize_manifest = write_finalize_manifest(
                    self.video_path, self.wav_path, self.mp4_path,
                    self.requested_fps, 0.001, self.process_audio_gain, False,
                    self.cleanup_rules, self.minimum_duration,
                    status="recording", worker_pid=os.getpid())
                if self._active_finalize_manifest not in \
                        self._deferred_finalize_manifests:
                    self._deferred_finalize_manifests.append(
                        self._active_finalize_manifest)
            except OSError as error:
                # Failure to write the sidecar must not leave an opened AVI
                # and audio device with no normal Stop path.
                self._active_finalize_manifest = ""
                print("[RECORDING] Recovery journal could not be created: {}"
                      .format(error))
        if callable(session_started_callback):
            try:
                upload_job_path = session_started_callback(self)
                if upload_job_path:
                    self.bind_youtube_upload_job(upload_job_path)
            except Exception as error:
                # Capture remains stoppable and its recovery manifest remains
                # intact even when the upload-intent journal cannot be queued.
                print("[RECORDING] Session-start callback failed: {}".format(
                    error))
        if audio_device:
            if async_audio_start:
                # Reopening some Windows/PortAudio devices can block for
                # close to a minute. Commands monitoring must keep feeding
                # real preview frames and observing Step changes meanwhile;
                # otherwise the exact loop/failure interval is replaced by
                # one repeated frame. Stop joins this worker before touching
                # any audio resources, so the recorder is never reused while
                # a late device-open attempt can still mutate it.
                self.audio_start_started_at = time.monotonic()

                def start_audio():
                    try:
                        self._start_audio(
                            audio_device, audio_gain_percent,
                            self.audio_level_options)
                    except Exception as error:
                        self.audio_start_error = str(error)
                        print("[RECORDING] Async audio capture failed: {}".format(
                            error))
                    finally:
                        self.audio_start_finished_at = time.monotonic()

                self.audio_start_thread = threading.Thread(
                    target=start_audio, daemon=True,
                    name="CaptureAudioStarter")
                self.audio_start_thread.start()
            else:
                self.audio_start_started_at = time.monotonic()
                try:
                    self._start_audio(
                        audio_device, audio_gain_percent,
                        self.audio_level_options)
                finally:
                    self.audio_start_finished_at = time.monotonic()

    def bind_youtube_upload_job(self, job_path):
        """Attach one durable upload intent to this capture session."""
        path = str(job_path or "").strip()
        if not path:
            return ""
        path = os.path.abspath(path)
        self.youtube_upload_job_path = path
        manifest_path = str(getattr(
            self, "_active_finalize_manifest", "") or "")
        if manifest_path and os.path.isfile(manifest_path):
            try:
                payload = load_finalize_manifest(manifest_path)
                payload["youtube_upload_job_path"] = path
                _write_json_atomic(manifest_path, payload)
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
                # Stop writes a complete replacement manifest with the same
                # path. Keep capture alive if this early journal update hits
                # an exceptional filesystem condition.
                print("[RECORDING] Upload intent could not be attached to "
                      "the recovery journal: {}".format(error))
        return path

    def activate_timeline(self, frame=None, started_at=None):
        """Begin a prepared recorder at the handoff timestamp.

        Audio devices can take many seconds to open.  During that preparation
        no video or callback audio is accepted, so resetting ``started_at``
        here cannot create a long repeated-frame prefix in the next segment.
        """
        activation = time.monotonic() if started_at is None else float(started_at)
        with self.video_frame_condition:
            if not self.active:
                return False
            if self.frames_written or self.video_frame_queue:
                raise RuntimeError("録画開始時刻をフレーム書き込み後に変更できません。")
            self.started_at = activation
            if frame is not None:
                initial = frame.copy()
                self.latest_frame = initial
                self.video_current_frame = initial
            self.video_first_presentation_at = 0.0
            self.video_last_presentation_at = 0.0
            self.video_presentation_frames = 0
            self.video_queue_last_sample_at = 0.0
            self.timeline_active = True
        return True

    @property
    def audio_start_in_progress(self):
        thread = self.audio_start_thread
        return bool(thread is not None and thread.is_alive())

    def _join_audio_start(self):
        """Wait for one asynchronous device-open before closing its state."""
        thread = self.audio_start_thread
        if thread is None:
            return
        if thread is threading.current_thread():
            return
        thread.join()
        self.audio_start_thread = None

    @staticmethod
    def _open_video_writer(path, fps, size):
        """Open a 60-FPS-capable AVI writer without a slow MJPEG backlog.

        At 1280x720 the bundled OpenCV MJPEG encoder measured far below 60
        frames/sec on the target machine. Its ordered queue therefore grew for
        the whole recording and Stop could not finish it without either a long
        freeze or missing frames. MPEG-4 Part 2 in AVI is handled by the same
        bundled FFmpeg backend, preserves the exact CFR/timeline, and has ample
        throughput for the presentation-ordered writer.
        """
        for codec in ("mp4v", "XVID"):
            writer = cv2.VideoWriter(
                path, cv2.VideoWriter_fourcc(*codec),
                max(1.0, float(fps)), tuple(size))
            if writer.isOpened():
                print("[RECORDING] AVI intermediate codec: {}".format(codec))
                return writer, codec
            writer.release()
        return None, ""

    def _video_writer_loop(self):
        # Keep a session-local handle.  A failed Stop must never redirect an
        # old worker to a later session's ``self.video`` object.
        writer = self.video
        try:
            while True:
                with self.video_frame_condition:
                    while (not self.video_frame_queue
                           and self.video_stop_at <= 0.0):
                        self.video_frame_condition.wait()
                    if self.video_frame_queue:
                        presented_at, frame = self.video_frame_queue.popleft()
                    else:
                        frame = None
                        presented_at = 0.0
                    stopped_at = self.video_stop_at
                if frame is not None:
                    self._advance_video_timeline(
                        presented_at, frame, writer=writer)
                    continue
                if stopped_at > 0.0:
                    self._advance_video_timeline(stopped_at, writer=writer)
                    return
        except Exception as error:
            self.video_writer_error = error
        finally:
            # VideoWriter is owned by this thread while writes are in flight.
            # Closing it here makes even a late completion after Stop timeout
            # flush the AVI safely; another thread never releases mid-write.
            release = getattr(writer, "release", None)
            if callable(release):
                try:
                    release()
                except Exception as error:
                    if self.video_writer_error is None:
                        self.video_writer_error = error
            self.video_writer_released = True
            with self.video_frame_condition:
                self.video_frame_condition.notify_all()

    def _advance_video_timeline(self, timeline_at, next_frame=None,
                                writer=None):
        """Write CFR slots up to one real preview-presentation timestamp."""
        try:
            timeline_at = float(timeline_at)
        except (TypeError, ValueError):
            timeline_at = self.started_at
        target_frames = int(round(max(
            0.0, timeline_at - self.started_at) * self.requested_fps))
        if target_frames < self.frames_written:
            self.video_timestamp_regressions += 1
            target_frames = self.frames_written
        current = self.video_current_frame
        video_writer = self.video if writer is None else writer
        while (self.frames_written < target_frames
               and current is not None and video_writer is not None):
            video_writer.write(current)
            self.frames_written += 1
        if next_frame is not None:
            self.video_current_frame = next_frame

    def _start_audio(self, device, gain_percent=100, level_options=None):
        if str(device).startswith("選択ゲーム音声 [PID:"):
            try:
                self.audio_source_mode = "application_loopback"
                self.process_audio_gain = max(0.0, min(float(gain_percent) / 100.0, 4.0))
                process_id = int(str(device).split("[PID:", 1)[1].split("]", 1)[0])
                helper = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "Tools", "ApplicationLoopback.exe")
                if not os.path.isfile(helper):
                    raise FileNotFoundError("ApplicationLoopback.exe is missing")
                creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                self.process_audio = subprocess.Popen(
                    [helper, str(process_id), "includetree", os.path.abspath(self.wav_path)],
                    # The helper's output was never consumed.  A PIPE can fill
                    # during a long recording and stall its audio process.
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True, creationflags=creation_flags)
                return
            except Exception as error:
                self.process_audio = None
                print("[RECORDING] Process audio capture failed: {}".format(error))
                return
        if self._start_monitored_audio(device):
            return
        try:
            import sounddevice as sd
            from AudioMonitor import AudioMonitor

            selected_index = int(str(device).split(":", 1)[0])
            candidates = AudioMonitor._candidate_input_indices(
                sd, selected_index)
            errors = []
            for candidate in candidates:
                try:
                    self._start_sounddevice_audio(
                        sd, candidate, selected_index, device,
                        gain_percent=gain_percent,
                        level_options=level_options)
                    return
                except Exception as error:
                    errors.append((candidate, error))
                    self._close_sounddevice_audio_attempt()
            if errors:
                candidate, error = errors[-1]
                raise RuntimeError(
                    "Audio device {} failed: {}".format(candidate, error))
        except Exception as error:
            self._close_sounddevice_audio_attempt()
            print("[RECORDING] Audio capture failed: {}".format(error))

    def _start_sounddevice_audio(self, sd, device_index, selected_index,
                                 selected_label, gain_percent=100,
                                 level_options=None):
        info = sd.query_devices(int(device_index))
        channels = min(2, int(info["max_input_channels"]))
        if channels < 1:
            raise ValueError("Audio input has no channels")
        sample_rate = int(info["default_samplerate"])
        self._prepare_audio_writer(
            sample_rate, channels, gain_percent=gain_percent,
            level_options=level_options)
        self.audio_source_mode = "direct_input"
        self.audio_selected_device = str(selected_label)
        self.audio_actual_device_index = int(device_index)
        self.audio_actual_device_name = str(info.get("name", ""))
        try:
            host_api = sd.query_hostapis(int(info.get("hostapi", -1)))
            self.audio_host_api = str(host_api.get("name", ""))
        except Exception:
            self.audio_host_api = ""

        def callback(indata, frames, _time_info, status):
            self._queue_audio_packet(indata, frames, status)

        self.audio_stream = sd.InputStream(
            device=int(device_index), channels=channels,
            samplerate=sample_rate, dtype="int16", callback=callback,
            blocksize=0, latency="low")
        self.audio_stream.start()
        try:
            self.audio_stream_latency = float(self.audio_stream.latency)
        except (AttributeError, TypeError, ValueError):
            self.audio_stream_latency = float(
                info.get("default_low_input_latency", 0.0) or 0.0)
        self.audio_capture_latency = self.audio_stream_latency
        self.audio_tap_point = "input_callback"
        print(
            "[RECORDING] Audio capture selected={} actual={} api={} "
            "rate={}Hz latency={:.1f}ms".format(
                selected_index, self.audio_actual_device_index,
                self.audio_host_api or "unknown", sample_rate,
                self.audio_stream_latency * 1000.0))

    def _prepare_audio_writer(self, sample_rate, channels, gain_percent=100,
                              level_options=None):
        self.audio = wave.open(self.wav_path, "wb")
        self.audio.setnchannels(channels)
        self.audio.setsampwidth(2)
        self.audio.setframerate(sample_rate)
        self.audio_sample_rate = sample_rate
        self.audio_channels = channels
        self.audio_gain = max(
            0.0, min(float(gain_percent) / 100.0, 4.0))
        options = dict(level_options or {})
        self.audio_peak_normalizer = AdaptivePeakNormalizer(
            sample_rate,
            enabled=options.get("auto_level", False),
            target_dbfs=options.get("target_dbfs", -6.0),
            max_gain_percent=options.get("max_auto_gain_percent", 200),
            ceiling_dbfs=options.get("limiter_ceiling_dbfs", -1.0))
        self.audio_frames_written = 0
        self.audio_pending_gap_frames = 0
        self.audio_gap_frames_written = 0
        self.audio_trailing_silence_frames = 0
        self.audio_queue_dropped_frames = 0
        self.audio_callback_warning_count = 0
        self.audio_queue_drop_count = 0
        self.audio_write_error = None
        self.audio_accepting_packets = True
        self.audio_stop_target_frames = None
        self.audio_stop_overrun_frames = 0
        self.audio_queue = queue.Queue(maxsize=256)
        self.audio_writer_thread = threading.Thread(
            target=self._audio_writer_loop, daemon=True,
            name="CaptureAudioWriter")
        self.audio_writer_thread.start()

    def _start_monitored_audio(self, selected_label):
        monitor = self.audio_monitor
        if monitor is None or not hasattr(monitor, "recording_output_info"):
            return False
        info = monitor.recording_output_info()
        if not info:
            return False
        try:
            selected_index = int(str(selected_label).split(":", 1)[0])
        except (TypeError, ValueError):
            return False
        monitor_selected = info.get("selected_input_device_index")
        if monitor_selected is not None and selected_index != int(monitor_selected):
            return False
        sample_rate = int(info["sample_rate"])
        channels = int(info["channels"])
        try:
            if hasattr(monitor, "level_info"):
                try:
                    self.audio_monitor_counter_start = dict(
                        monitor.level_info() or {})
                except Exception:
                    self.audio_monitor_counter_start = {}
            # Confirmation playback already contains the Audio-tab gain and
            # sample-rate conversion. Do not apply either a second time.
            self._prepare_audio_writer(
                sample_rate, channels, gain_percent=100,
                level_options={"auto_level": False})

            def listener(outdata, frames, _time_info, status):
                if not self.timeline_active:
                    return
                presented_at = audio_callback_presentation_time(
                    _time_info)
                if self.audio_first_presentation_at <= 0.0:
                    self.audio_first_presentation_at = presented_at
                    initial_frames = int(round(max(
                        0.0, presented_at - getattr(
                            self, "started_at", presented_at)) * sample_rate))
                    self.audio_initial_alignment_frames = initial_frames
                    self.audio_pending_gap_frames += initial_frames
                if self.audio_last_presentation_at > 0.0 \
                        and presented_at < self.audio_last_presentation_at:
                    self.audio_presentation_timestamp_regressions += 1
                self.audio_last_presentation_at = presented_at
                self.audio_last_presentation_frames = max(0, int(frames))
                self.audio_presentation_frames += max(0, int(frames))
                if presented_at - self.audio_presentation_clock_last_sample_at \
                        >= 1.0:
                    presentation_span = max(
                        0.0,
                        presented_at
                        + max(0, int(frames)) / max(1, sample_rate)
                        - self.audio_first_presentation_at)
                    self.audio_presentation_clock_samples.append({
                        "offset_seconds": max(
                            0.0, presented_at - getattr(
                                self, "started_at", presented_at)),
                        "clock_error_ms": (
                            self.audio_presentation_frames
                            / max(1, sample_rate)
                            - presentation_span) * 1000.0,
                    })
                    self.audio_presentation_clock_last_sample_at = presented_at
                pcm = np.clip(
                    np.asarray(outdata, dtype=np.float32), -1.0, 1.0)
                pcm = np.rint(pcm * 32767.0).astype(np.int16)
                self._queue_audio_packet(pcm, frames, status)

            token = monitor.add_recording_output_listener(
                listener, sample_rate, channels)
            if token is None:
                raise RuntimeError("Confirmation audio changed during subscribe")
            self.audio_monitor_listener_token = token
            self.audio_tap_point = str(
                info.get("tap_point", "speaker_output_callback"))
            self.audio_source_mode = "pokecon_presented_output" \
                if self.audio_tap_point == "speaker_output_callback" \
                else "pokecon_confirmation_playback"
            self.audio_selected_device = str(selected_label)
            self.audio_actual_device_index = info.get("actual_input_device_index")
            self.audio_actual_device_name = str(info.get("input_device_name", ""))
            self.audio_host_api = "{} -> {}".format(
                info.get("input_host_api", "") or "input",
                info.get("output_host_api", "") or "output")
            self.audio_stream_latency = float(info.get("latency", 0.0) or 0.0)
            self.audio_capture_latency = float(
                info.get("capture_latency", 0.0) or 0.0)
            self.audio_playback_latency = float(
                info.get("playback_latency", 0.0) or 0.0)
            print(
                "[RECORDING] Sharing PokeCon presented audio "
                "rate={}Hz channels={} capture_latency={:.1f}ms "
                "playback_latency={:.1f}ms tap={}".format(
                    sample_rate, channels,
                    self.audio_capture_latency * 1000.0,
                    self.audio_playback_latency * 1000.0,
                    self.audio_tap_point or "unknown"))
            return True
        except Exception as error:
            self._stop_monitored_audio_listener()
            self._stop_audio_writer()
            if self.audio:
                self.audio.close()
                self.audio = None
            print("[RECORDING] Confirmation audio share failed: {}".format(error))
            return False

    def _stop_monitored_audio_listener(self):
        self.audio_accepting_packets = False
        token, self.audio_monitor_listener_token = (
            self.audio_monitor_listener_token, None)
        monitor = self.audio_monitor
        if token is not None and monitor is not None \
                and hasattr(monitor, "level_info"):
            try:
                self.audio_monitor_counter_end = dict(
                    monitor.level_info() or {})
            except Exception:
                self.audio_monitor_counter_end = {}
        if token is not None and monitor is not None \
                and hasattr(monitor, "remove_recording_output_listener"):
            try:
                monitor.remove_recording_output_listener(token)
            except Exception:
                pass

    def _close_sounddevice_audio_attempt(self):
        self.audio_accepting_packets = False
        self._stop_monitored_audio_listener()
        stream, self.audio_stream = self.audio_stream, None
        if stream is not None:
            try:
                if bool(getattr(stream, "active", False)):
                    stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        self._stop_audio_writer()
        if self.audio:
            try:
                self.audio.close()
            except Exception:
                pass
            self.audio = None

    def _queue_audio_packet(self, indata, frames, status=None):
        """Queue contiguous PCM and recover only confirmed missing packets."""
        audio_queue = self.audio_queue
        if (audio_queue is None or not self.audio_accepting_packets
                or not self.timeline_active):
            return False
        frames = max(0, int(frames))
        gap_frames = max(0, int(self.audio_pending_gap_frames))
        if status:
            self.audio_callback_warning_count += 1
            if bool(getattr(status, "input_overflow", False)):
                # PortAudio does not report the exact count. One callback block
                # is a bounded estimate and is recorded in the timing report.
                gap_frames += frames
        packet = (gap_frames, frames, indata.tobytes())
        try:
            audio_queue.put_nowait(packet)
            self.audio_pending_gap_frames = 0
            return True
        except queue.Full:
            self.audio_queue_drop_count += 1
            self.audio_queue_dropped_frames += frames
            self.audio_pending_gap_frames = gap_frames + frames
            return False

    def _write_audio_silence(self, frame_count):
        frame_count = max(0, int(frame_count))
        target_frames = self.audio_stop_target_frames
        if target_frames is not None:
            frame_count = min(
                frame_count,
                max(0, int(target_frames) - self.audio_frames_written))
        if not self.audio or not frame_count:
            return
        frame_width = max(1, int(self.audio_channels)) * 2
        block_frames = max(1, min(frame_count, max(1, self.audio_sample_rate)))
        silence = b"\0" * (block_frames * frame_width)
        remaining = frame_count
        while remaining:
            count = min(remaining, block_frames)
            self.audio.writeframesraw(silence[:count * frame_width])
            self.audio_frames_written += count
            remaining -= count

    def _write_audio_packet(self, gap_frames, frame_count, payload):
        """Append one packet, inserting silence only for a confirmed gap."""
        if not self.audio:
            return
        frame_count = max(0, int(frame_count))
        frame_width = max(1, int(self.audio_channels)) * 2
        gap_frames = max(0, int(gap_frames))
        if gap_frames:
            before_gap = self.audio_frames_written
            self._write_audio_silence(gap_frames)
            self.audio_gap_frames_written += (
                self.audio_frames_written - before_gap)
        if frame_count <= 0:
            return
        target_frames = self.audio_stop_target_frames
        if target_frames is not None:
            frame_count = min(
                frame_count,
                max(0, int(target_frames) - self.audio_frames_written))
        if frame_count <= 0:
            return
        payload = payload[:frame_count * frame_width]
        normalizer = self.audio_peak_normalizer
        if normalizer is not None:
            samples = np.frombuffer(payload, dtype=np.int16).astype(np.float32)
            samples = samples.reshape((-1, max(1, int(self.audio_channels))))
            samples = normalizer.process(
                (samples / 32768.0) * self.audio_gain)
            payload = np.rint(samples * 32767.0).astype(np.int16).tobytes()
        elif abs(self.audio_gain - 1.0) > 0.001:
            samples = np.frombuffer(payload, dtype=np.int16).astype(np.float32)
            samples = np.clip(samples * self.audio_gain, -32768, 32767)
            payload = samples.astype(np.int16).tobytes()
        self.audio.writeframesraw(payload)
        self.audio_frames_written += frame_count

    def _audio_writer_loop(self):
        while self.audio_queue is not None:
            packet = self.audio_queue.get()
            if packet is None:
                return
            try:
                self._write_audio_packet(*packet)
            except Exception as error:
                self.audio_write_error = error

    def _stop_audio_writer(self, stopped_at=None):
        # Freeze the producer side before placing the sentinel.  In
        # particular, a confirmation-playback callback can otherwise append a
        # packet after the sentinel and leave that packet unwritten.
        target_frames = None
        if stopped_at is not None and self.audio_sample_rate:
            target_frames = int(round(
                max(0.0, float(stopped_at) - self.started_at)
                * self.audio_sample_rate))
        self.audio_stop_target_frames = target_frames
        self.audio_accepting_packets = False
        audio_queue = self.audio_queue
        writer = self.audio_writer_thread
        if audio_queue is not None and writer is not None:
            try:
                audio_queue.put(None, timeout=5)
            except queue.Full:
                pass
            writer.join(timeout=10)
        self.audio_writer_thread = None
        self.audio_queue = None
        if self.audio and target_frames is not None:
            if target_frames > self.audio_frames_written:
                trailing_frames = target_frames - self.audio_frames_written
                self._write_audio_silence(trailing_frames)
                self.audio_trailing_silence_frames += trailing_frames
            elif self.audio_frames_written > target_frames:
                # A writer may already be inside one small callback write when
                # Stop fixes the target.  Record that bounded race explicitly;
                # all queued packets after it are capped by the target above.
                self.audio_stop_overrun_frames = (
                    self.audio_frames_written - target_frames)
        if (self.audio_callback_warning_count or self.audio_queue_drop_count
                or self.audio_write_error is not None):
            print(
                "[RECORDING] Audio timing recovery: callback_status={}, "
                "queue_drops={}, write_error={}".format(
                    self.audio_callback_warning_count,
                    self.audio_queue_drop_count,
                    self.audio_write_error or "none"))

    def _write_timing_report(self, elapsed, output_fps,
                             wall_clock_frame_rate):
        """Persist enough evidence to diagnose later recordings safely."""
        wav_frames = int(self.audio_frames_written)
        wav_rate = int(self.audio_sample_rate)
        wav_channels = int(self.audio_channels)
        if os.path.isfile(getattr(self, "wav_path", "")):
            try:
                with wave.open(self.wav_path, "rb") as audio_file:
                    wav_frames = int(audio_file.getnframes())
                    wav_rate = int(audio_file.getframerate())
                    wav_channels = int(audio_file.getnchannels())
            except (OSError, EOFError, wave.Error):
                pass
        if self.audio_source_mode in (
                "pokecon_presented_output",
                "pokecon_processed_input",
                "pokecon_confirmation_playback") \
                and self.audio_monitor is not None \
                and hasattr(self.audio_monitor, "level_info"):
            try:
                level_control = dict(
                    self.audio_monitor_counter_end
                    or self.audio_monitor.level_info() or {})
                counter_start = self.audio_monitor_counter_start
                for key in (
                        "audio_input_status_count",
                        "audio_output_status_count",
                        "software_buffer_startup_silence_frames",
                        "software_buffer_underflow_frames",
                        "software_buffer_overflow_trimmed_frames",
                        "software_buffer_drift_drop_frames",
                        "software_buffer_drift_insert_frames"):
                    if key in level_control and key in counter_start:
                        level_control[key] = max(
                            0, int(level_control[key])
                            - int(counter_start[key]))
                level_control["processing_source"] = "AudioMonitor"
            except Exception:
                level_control = {}
        else:
            try:
                last_info = getattr(
                    self.audio_peak_normalizer, "last_info", {}) or {}
                level_control = (last_info.copy()
                                 if isinstance(last_info, dict)
                                 else dict(last_info))
            except (RuntimeError, TypeError, ValueError):
                # Timing evidence is diagnostic only.  A callback updating a
                # third-party mapping must never make Stop fail and leave an
                # AVI/audio handle open.
                level_control = {}
            if level_control:
                level_control["processing_source"] = "CaptureRecorder"
        report = {
            "schema_version": 1,
            "video": {
                "frames": int(getattr(self, "frames_written", 0)),
                "requested_fps": float(getattr(self, "requested_fps", 0.0)),
                "intermediate_codec": str(self.video_codec),
                # AVI and final MP4 remain at the configured CFR.  The small
                # frames/elapsed difference is diagnostics only; feeding it
                # back into ffmpeg would turn a requested 60/1 stream into
                # values such as 60.005 FPS.
                "container_fps": float(output_fps),
                "corrected_fps": float(output_fps),
                "wall_clock_frame_rate": float(wall_clock_frame_rate),
                "elapsed_seconds": float(elapsed),
                "presentation_mode": self.video_presentation_mode,
                "timeline_mode": "preview_presentation_timestamped_cfr",
                "presentation_frames": int(self.video_presentation_frames),
                "coalesced_presentation_frames": int(
                    self.video_coalesced_presentation_frames),
                "presentation_queue_max_depth": int(
                    self.video_frame_queue_max_depth),
                "compositor_queue_max_depth": int(
                    self.video_compositor_queue_max_depth),
                "timestamp_regressions": int(
                    self.video_timestamp_regressions),
                "stop_pending_presentations": int(
                    self.video_stop_pending_presentations),
                "stop_target_frames": int(
                    self.video_stop_target_frames),
                "stop_pending_frames": int(
                    self.video_stop_pending_frames),
                "stop_drain_seconds": float(self.video_stop_drain_seconds),
                "stop_drain_timeout_seconds": float(
                    self.video_stop_drain_timeout),
                "stop_drain_timed_out": bool(
                    self.video_stop_drain_timed_out),
                "writer_error": str(
                    self.video_writer_error or ""),
                "queue_depth_samples": list(
                    self.video_queue_depth_samples),
                "compositor_delivery_delay_average_ms": (
                    self.video_delivery_delay_total * 1000.0
                    / self.video_delivery_delay_samples
                    if self.video_delivery_delay_samples else None),
                "compositor_delivery_delay_max_ms": (
                    self.video_delivery_delay_max * 1000.0
                    if self.video_delivery_delay_samples else None),
                "first_presentation_offset_ms": (
                    max(0.0, self.video_first_presentation_at
                        - self.started_at) * 1000.0
                    if self.video_first_presentation_at > 0.0 else None),
            },
            "audio": {
                "source_mode": self.audio_source_mode,
                "selected_device": self.audio_selected_device,
                "actual_device_index": self.audio_actual_device_index,
                "actual_device_name": self.audio_actual_device_name,
                "host_api": self.audio_host_api,
                "stream_latency_ms": float(self.audio_stream_latency) * 1000.0,
                "capture_latency_ms": (
                    float(self.audio_capture_latency) * 1000.0),
                "playback_latency_ms": (
                    float(self.audio_playback_latency) * 1000.0),
                "tap_point": self.audio_tap_point,
                "first_presentation_offset_ms": (
                    max(0.0, self.audio_first_presentation_at
                        - self.started_at) * 1000.0
                    if self.audio_first_presentation_at > 0.0 else None),
                "initial_alignment_frames": int(
                    self.audio_initial_alignment_frames),
                "presentation_frames": int(
                    self.audio_presentation_frames),
                "presentation_timestamp_regressions": int(
                    self.audio_presentation_timestamp_regressions),
                "presentation_span_seconds": (
                    max(0.0,
                        self.audio_last_presentation_at
                        + self.audio_last_presentation_frames
                        / max(1, self.audio_sample_rate)
                        - self.audio_first_presentation_at)
                    if self.audio_first_presentation_at > 0.0
                    and self.audio_last_presentation_at > 0.0 else None),
                "presentation_sample_duration_seconds": (
                    self.audio_presentation_frames
                    / max(1, self.audio_sample_rate)
                    if self.audio_presentation_frames else None),
                "presentation_clock_error_ms": (
                    (self.audio_presentation_frames
                     / max(1, self.audio_sample_rate)
                     - max(0.0,
                           self.audio_last_presentation_at
                           + self.audio_last_presentation_frames
                           / max(1, self.audio_sample_rate)
                           - self.audio_first_presentation_at)) * 1000.0
                    if self.audio_presentation_frames
                    and self.audio_first_presentation_at > 0.0
                    and self.audio_last_presentation_at > 0.0 else None),
                "presentation_clock_samples": list(
                    self.audio_presentation_clock_samples),
                "sample_rate": wav_rate,
                "channels": wav_channels,
                "frames": wav_frames,
                "duration_seconds": (
                    float(wav_frames) / wav_rate if wav_rate else 0.0),
                "duration_error_ms": (
                    (float(wav_frames) / wav_rate - float(elapsed)) * 1000.0
                    if wav_rate else None),
                "stop_target_frames": (
                    int(self.audio_stop_target_frames)
                    if self.audio_stop_target_frames is not None else None),
                "stop_overrun_frames": int(
                    self.audio_stop_overrun_frames),
                "callback_status_count": int(self.audio_callback_warning_count),
                "queue_drop_packets": int(self.audio_queue_drop_count),
                "queue_dropped_frames": int(self.audio_queue_dropped_frames),
                "confirmed_gap_silence_frames": int(max(
                    0, self.audio_gap_frames_written
                    - self.audio_initial_alignment_frames)),
                "trailing_padding_frames": int(self.audio_trailing_silence_frames),
                "write_error": str(self.audio_write_error or ""),
                "monitor_input_status_count": int(
                    level_control.get("audio_input_status_count", 0)),
                "monitor_output_status_count": int(
                    level_control.get("audio_output_status_count", 0)),
                "monitor_software_underflow_frames": int(
                    level_control.get(
                        "software_buffer_underflow_frames", 0)),
                "monitor_overflow_trimmed_frames": int(
                    level_control.get(
                        "software_buffer_overflow_trimmed_frames", 0)),
                "monitor_drift_drop_frames": int(
                    level_control.get(
                        "software_buffer_drift_drop_frames", 0)),
                "monitor_drift_insert_frames": int(
                    level_control.get(
                        "software_buffer_drift_insert_frames", 0)),
                "level_control": level_control,
            },
        }
        path = os.path.join(self.session_dir, "recording_timing.json")
        try:
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
        except OSError as error:
            print("[RECORDING] Timing report failed: {}".format(error))

    def add_frame(self, frame, presented_at=None,
                  presentation_mode=None):
        if self.active and self.timeline_active and frame is not None:
            try:
                timestamp = float(presented_at)
            except (TypeError, ValueError):
                timestamp = time.monotonic()
            if timestamp <= 0.0:
                timestamp = time.monotonic()
            delivered_at = time.monotonic()
            delivery_delay = max(0.0, delivered_at - timestamp)
            with self.video_frame_condition:
                if not self.active or self.video_stop_at > 0.0:
                    return
                # Camera publishes a new ndarray for every captured frame and
                # the compositor also returns a completed ndarray. Retaining
                # that immutable-by-convention object keeps this callback fast
                # enough for the native 60-Hz presentation thread while the
                # writer consumes every presented frame in order.
                self.latest_frame = frame
                self.video_frame_queue.append((timestamp, frame))
                self.video_frame_queue_max_depth = max(
                    self.video_frame_queue_max_depth,
                    len(self.video_frame_queue))
                if timestamp - self.video_queue_last_sample_at >= 1.0:
                    self.video_queue_depth_samples.append({
                        "offset_seconds": max(
                            0.0, timestamp - getattr(
                                self, "started_at", timestamp)),
                        "depth": len(self.video_frame_queue),
                    })
                    self.video_queue_last_sample_at = timestamp
                self.video_delivery_delay_total += delivery_delay
                self.video_delivery_delay_max = max(
                    self.video_delivery_delay_max, delivery_delay)
                self.video_delivery_delay_samples += 1
                if self.video_first_presentation_at <= 0.0:
                    self.video_first_presentation_at = timestamp
                self.video_last_presentation_at = timestamp
                self.video_presentation_frames += 1
                self.video_presentation_mode = str(
                    presentation_mode or "preview_presented")
                self.video_frame_condition.notify()

    def stop(self, discard=False):
        with self.stop_lock:
            return self._stop_locked(discard=discard)

    def _persist_video_close_failure(self, error, writer_active=False):
        """Keep a failed AVI out of finalization while preserving evidence."""
        manifest_path = str(
            getattr(self, "_active_finalize_manifest", "") or "")
        if not manifest_path or not os.path.isfile(manifest_path):
            return False
        try:
            payload = load_finalize_manifest(manifest_path)
            payload["status"] = "close_failed"
            payload["worker_pid"] = os.getpid() if writer_active else 0
            payload["close_writer_active"] = bool(writer_active)
            payload["close_error"] = str(error or "")
            payload["close_failed_at"] = datetime.datetime.now().isoformat(
                timespec="seconds")
            payload["stop_target_frames"] = int(
                getattr(self, "video_stop_target_frames", 0) or 0)
            payload["stop_pending_frames"] = int(max(
                0, payload["stop_target_frames"]
                - int(getattr(self, "frames_written", 0) or 0)))
            payload["frames_written"] = int(
                getattr(self, "frames_written", 0) or 0)
            payload["stop_drain_timeout_seconds"] = float(
                getattr(self, "video_stop_drain_timeout", 0.0) or 0.0)
            payload["stop_drain_timed_out"] = bool(
                getattr(self, "video_stop_drain_timed_out", False))
            _write_json_atomic(manifest_path, payload)
            return True
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as caught:
            print("[RECORDING] Close-failure journal update failed: {}".format(
                caught))
            return False

    def _watch_late_video_close(self, writer_thread, writer, reason):
        """Quarantine a timed-out writer, then release this recorder for reuse."""
        try:
            writer_thread.join()
        finally:
            with self.stop_lock:
                if (self.writer_thread is writer_thread
                        and self.video is writer):
                    late_error = self.video_writer_error or reason
                    self._persist_video_close_failure(
                        late_error, writer_active=False)
                    # Publish reusable state only after the old manifest has
                    # been quarantined; start() does not take stop_lock.
                    self.writer_thread = None
                    self.writer_stop = None
                    self.video = None
                    self.video_close_pending = False

    def _stop_locked(self, discard=False):
        if not self.active:
            if self.video_close_pending:
                raise RuntimeError(
                    "前回の録画映像を安全に閉じています。完了するまで待ってください。")
            return None
        stopped_at = time.monotonic()
        self.active = False
        self.video_close_pending = True
        video_path, wav_path, mp4_path = (
            str(getattr(self, "video_path", "") or ""),
            str(getattr(self, "wav_path", "") or ""),
            str(getattr(self, "mp4_path", "") or ""))
        timeline_stopped_at = (stopped_at if self.timeline_active
                               else self.started_at)
        elapsed = max(0.001, timeline_stopped_at - self.started_at)
        output_fps = max(1.0, float(self.requested_fps))
        process_audio_gain = self.process_audio_gain
        cleanup_rules = list(getattr(
            self, "_capture_cleanup_rules", self.cleanup_rules))
        minimum_duration = float(getattr(
            self, "_capture_minimum_duration", self.minimum_duration))
        manifest_path = self._active_finalize_manifest or None
        if (self.defer_finalization or self.durable_finalization
                or manifest_path):
            # Persist ownership before audio shutdown or the ordered AVI drain.
            # If the process dies anywhere below, a later PokeCon can recover
            # the raw files once this owner PID is no longer alive.
            try:
                manifest_path = write_finalize_manifest(
                    video_path, wav_path, mp4_path, output_fps, elapsed,
                    process_audio_gain, bool(discard), cleanup_rules,
                    minimum_duration, status="closing", worker_pid=os.getpid(),
                    youtube_upload_job_path=getattr(
                        self, "youtube_upload_job_path", ""))
                self._active_finalize_manifest = manifest_path
                if manifest_path not in self._deferred_finalize_manifests:
                    self._deferred_finalize_manifests.append(manifest_path)
            except OSError as error:
                # Continue closing every writer even when the journal cannot
                # be refreshed.  A start-time journal may still be recoverable.
                print("[RECORDING] Recovery journal could not be updated: {}"
                      .format(error))
        with self.video_frame_condition:
            self.video_stop_at = timeline_stopped_at
            self.video_stop_pending_presentations = len(
                self.video_frame_queue)
            self.video_stop_target_frames = int(round(max(
                0.0, timeline_stopped_at - self.started_at)
                * self.requested_fps))
            # Queue depth misses the presentation already popped by the
            # writer.  CFR frame debt measures the actual remaining writes,
            # including a long preview/UI gap represented by one timestamp.
            self.video_stop_pending_frames = max(
                0, self.video_stop_target_frames - self.frames_written)
            if self.writer_stop:
                self.writer_stop.set()
            self.video_frame_condition.notify()

        # Freeze audio at the same logical Stop timestamp before waiting for
        # the ordered video queue.  A busy 60-fps writer can need many seconds
        # to drain; leaving the speaker listener attached during that wait
        # made WAV continue growing after the video timeline had already
        # stopped (13.7 seconds in the 2026-08-16 reproduction).
        if self.writer_thread:
            self.video_stop_drain_timeout = max(
                30.0, min(
                    300.0,
                    10.0 + max(
                        self.video_stop_pending_frames,
                        self.video_stop_pending_presentations)
                    / max(1.0, self.requested_fps * 0.5)))
        audio_close_errors = []

        def remember_audio_close_error(stage, error):
            audio_close_errors.append((str(stage), error))
            print("[RECORDING] Audio shutdown failed at {}: {}".format(
                stage, error))

        # An unplugged or reset audio device may make one of these operations
        # fail.  Video owns a separate writer thread and must still be joined
        # (or quarantined by the late-close watcher) before Stop reports that
        # audio error; otherwise this recorder remains permanently stuck in
        # ``video_close_pending`` with its AVI handle still published.
        try:
            self._join_audio_start()
        except Exception as error:
            remember_audio_close_error("audio device start", error)
        try:
            self._stop_monitored_audio_listener()
        except Exception as error:
            remember_audio_close_error("audio monitor listener", error)
        audio_stream, self.audio_stream = self.audio_stream, None
        if audio_stream:
            try:
                audio_stream.stop()
            except Exception as error:
                remember_audio_close_error("audio stream stop", error)
            try:
                audio_stream.close()
            except Exception as error:
                remember_audio_close_error("audio stream close", error)
        try:
            self._stop_audio_writer(stopped_at)
        except Exception as error:
            remember_audio_close_error("audio writer", error)
        if self.process_audio:
            process = self.process_audio
            self.process_audio = None
            try:
                if process.stdin:
                    process.stdin.write("\n")
                    process.stdin.flush()
                process.wait(timeout=8)
            except Exception:
                try:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except Exception:
                        process.kill()
                except Exception as error:
                    remember_audio_close_error("process audio", error)
        audio_file, self.audio = self.audio, None
        if audio_file:
            try:
                audio_file.close()
            except Exception as error:
                remember_audio_close_error("audio file", error)

        if self.writer_thread:
            # A small transient queue must never turn into missing AVI frames.
            # The fast intermediate codec normally leaves this near zero; the
            # dynamic allowance also gives a busy disk time to drain safely.
            # Audio/device shutdown has its own latency and must not consume
            # the advertised allowance for draining video frames.
            drain_started_at = time.monotonic()
            self.writer_thread.join(timeout=self.video_stop_drain_timeout)
            self.video_stop_drain_seconds = max(
                0.0, time.monotonic() - drain_started_at)
            if self.writer_thread.is_alive():
                self.video_stop_drain_timed_out = True
                timeout_error = RuntimeError(
                    "表示時刻に基づく録画映像の書き込みを{:.0f}秒以内に"
                    "完了できませんでした。".format(
                        self.video_stop_drain_timeout))
                self._persist_video_close_failure(
                    timeout_error, writer_active=True)
                writer_thread = self.writer_thread
                writer = self.video
                late_thread = threading.Thread(
                    target=self._watch_late_video_close,
                    args=(writer_thread, writer, timeout_error), daemon=True,
                    name="CaptureRecordingLateClose")
                self._video_late_close_thread = late_thread
                late_thread.start()
                raise timeout_error
            writer_error = self.video_writer_error
        else:
            writer_error = None
        self.writer_thread = None
        self.writer_stop = None
        if self.video and not self.video_writer_released:
            self.video.release()
        self.video = None
        self.video_close_pending = False
        if writer_error is not None:
            close_error = RuntimeError(
                "録画映像の書き込みに失敗しました: {}".format(
                    writer_error))
            self._persist_video_close_failure(close_error, writer_active=False)
            raise close_error
        if audio_close_errors:
            details = "; ".join(
                "{}: {}".format(stage, error)
                for stage, error in audio_close_errors)
            close_error = RuntimeError(
                "録画音声の停止に失敗しました（映像は安全に閉じました）: {}".format(
                    details))
            self._persist_video_close_failure(close_error, writer_active=False)
            raise close_error
        if not getattr(self, "frames_written", 0):
            upload_job_path = str(getattr(
                self, "youtube_upload_job_path", "") or "")
            if upload_job_path and not self._cancel_youtube_upload_intent(
                    upload_job_path,
                    "Recording stopped before receiving a video frame"):
                # Do not remove the crash journal or local artifacts while an
                # upload intent with uncertain remote state still exists.
                print("[RECORDING] No video frames were received, but the "
                      "YouTube upload intent could not be cancelled; keeping "
                      "the session for manual recovery.")
                return None
            if discard:
                shutil.rmtree(
                    getattr(self, "session_dir", ""), ignore_errors=True)
                self._active_finalize_manifest = ""
                print("[RECORDING] Discarded recording by command-variable rule.")
                return None
            if manifest_path and os.path.isfile(manifest_path):
                try:
                    os.remove(manifest_path)
                except OSError:
                    pass
            self._active_finalize_manifest = ""
            print("[RECORDING] No video frames were received; keeping audio file only.")
            # A YouTube intent always names recording.mp4.  Returning WAV here
            # would let Window enqueue a second, invalid audio-only job.
            if upload_job_path:
                return None
            return self.wav_path if os.path.isfile(self.wav_path) else None
        # Do not include process-audio shutdown/WAV finalization in captured
        # video time. Including it made the measured FPS too low and stretched
        # the final video relative to audio.
        wall_clock_frame_rate = max(1.0, self.frames_written / elapsed)
        try:
            self._write_timing_report(
                elapsed, output_fps, wall_clock_frame_rate)
        except Exception as error:
            # Recording closure and durable hand-off are authoritative; a
            # diagnostics failure must not abort them or disable subsequent
            # Commands monitor chunks.
            print("[RECORDING] Timing report failed: {}".format(error))
        if (self.defer_finalization or self.durable_finalization
                or manifest_path):
            inprocess = bool(
                self.durable_finalization and not self.defer_finalization)
            try:
                manifest_path = write_finalize_manifest(
                    video_path, wav_path, mp4_path, output_fps, elapsed,
                    process_audio_gain, bool(discard), cleanup_rules,
                    minimum_duration,
                    status="processing" if inprocess else "pending",
                    worker_pid=os.getpid() if inprocess else 0,
                    youtube_upload_job_path=getattr(
                        self, "youtube_upload_job_path", ""))
                self._active_finalize_manifest = manifest_path
                if manifest_path not in self._deferred_finalize_manifests:
                    self._deferred_finalize_manifests.append(manifest_path)
            except OSError as error:
                print("[RECORDING] Recovery journal could not be finalized: {}"
                      .format(error))
        if self.defer_finalization:
            print("[RECORDING] MP4 creation deferred: " + str(
                manifest_path or mp4_path))
            return mp4_path
        # Re-encoding can take seconds.  Never wait for it in the Tk/capture
        # thread: recording is already stopped and the UI may continue.
        with self.lock:
            self._finalizing_count += 1
        if manifest_path:
            with self.lock:
                self._inprocess_finalize_manifests.add(
                    os.path.abspath(manifest_path))
            self._finalize_queue.put({"manifest_path": manifest_path})
        else:
            self._finalize_queue.put((
                video_path, wav_path, mp4_path, output_fps, elapsed,
                process_audio_gain, bool(discard), cleanup_rules,
                minimum_duration))
        print("[RECORDING] Finalizing MP4 in background "
              "({:.3f} CFR, {:.3f} wall-clock frames/sec): {}".format(
                  output_fps, wall_clock_frame_rate, mp4_path))
        return mp4_path

    @property
    def is_finalizing(self):
        with self.lock:
            return self._finalizing_count > 0

    def deferred_finalize_manifests(self):
        """Return durable jobs for this output root, including older failures."""
        known = list(self._deferred_finalize_manifests)
        known.extend(discover_finalize_manifests(self.output_dir))
        unique = []
        with self.lock:
            inprocess = set(self._inprocess_finalize_manifests)
        for path in known:
            path = os.path.abspath(path)
            if path in inprocess or path in unique or not os.path.isfile(path):
                continue
            try:
                needs_work = _finalize_manifest_needs_work(
                    load_finalize_manifest(path))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                needs_work = True
            if needs_work:
                unique.append(path)
        return unique

    def _finalize_worker(self):
        """Serialize CPU-heavy mux/cleanup jobs without blocking capture."""
        set_current_thread_below_normal()
        while True:
            job = self._finalize_queue.get()
            if job is None:
                self._finalize_queue.task_done()
                return
            manifest_path = ""
            try:
                if isinstance(job, dict):
                    manifest_path = os.path.abspath(str(
                        job.get("manifest_path", "") or ""))
                    finalize_recording_manifest(manifest_path)
                else:
                    self._finalize(*job)
            except Exception as error:
                # A failed encoder must not terminate the sole worker and
                # leave every later recording permanently queued.
                print("[RECORDING] Finalizing failed: {}".format(error))
            finally:
                with self.lock:
                    if manifest_path:
                        self._inprocess_finalize_manifests.discard(
                            manifest_path)
                    self._finalizing_count = max(
                        0, self._finalizing_count - 1)
                self._finalize_queue.task_done()

    def retire_finalize_worker(self):
        """Stop this segment's private finalizer after all queued work."""
        with self.lock:
            thread = self._finalize_thread
            if (thread is None or not thread.is_alive()
                    or self._finalize_retirement_requested):
                return thread
            self._finalize_retirement_requested = True
            self._finalize_queue.put(None)
        return thread

    @staticmethod
    def _cancel_youtube_upload_intent(job_path, reason):
        path = str(job_path or "").strip()
        if not path:
            return True
        try:
            # Lazy import avoids a module cycle; YouTubeArchive only imports
            # Recording from its recovery helper at runtime.
            from YouTubeArchive import cancel_upload_job
            return bool(cancel_upload_job(path, reason))
        except Exception as error:
            print("[RECORDING] Upload intent cancellation failed; keeping "
                  "local media: {}".format(error))
            return False

    def _finalize(self, video_path, wav_path, mp4_path, output_fps, elapsed,
                  process_audio_gain=1.0, discard=False,
                  cleanup_rules=None, minimum_duration=0.0,
                  youtube_upload_job_path=""):
        reason = ("command-variable rule" if discard else
                  self._discard_reason(
                      video_path, elapsed, cleanup_rules, minimum_duration))
        if reason:
            session_dir = os.path.dirname(video_path)
            upload_job_path = str(youtube_upload_job_path or "").strip()
            cancelled = self._cancel_youtube_upload_intent(
                upload_job_path,
                "Recording discarded: {}".format(reason))
            if not cancelled:
                # A worker may already own remote state. Deleting the source
                # would strand that upload, so complete the MP4 instead.
                print("[RECORDING] Discard was not safe after YouTube upload "
                      "claim; finalizing the recording instead.")
                return self._mux(
                    video_path, wav_path, mp4_path, output_fps,
                    process_audio_gain)
            print("[RECORDING] Discarded recording: " + reason)
            # ``session_dir`` is always the timestamp folder created by start.
            shutil.rmtree(session_dir, ignore_errors=True)
            return None
        return self._mux(video_path, wav_path, mp4_path, output_fps,
                         process_audio_gain)

    def _discard_reason(self, video_path, elapsed, cleanup_rules=None,
                        minimum_duration=None):
        cleanup_rules = self.cleanup_rules if cleanup_rules is None else cleanup_rules
        minimum_duration = self.minimum_duration if minimum_duration is None else minimum_duration
        if minimum_duration and elapsed < minimum_duration:
            return "duration {:.2f}s is below {:.2f}s".format(elapsed, minimum_duration)
        if not cleanup_rules:
            return None
        capture = cv2.VideoCapture(video_path)
        total = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        matches = [0] * len(cleanup_rules)
        sampled = 0
        sample_indexes = evenly_spaced_frame_indexes(total, 120)

        def analyse(frame):
            nonlocal sampled
            sampled += 1
            for pos, rule in enumerate(cleanup_rules):
                image = rule.get("image")
                if (image is None or frame.shape[0] < image.shape[0]
                        or frame.shape[1] < image.shape[1]):
                    continue
                _, score, _, _ = cv2.minMaxLoc(cv2.matchTemplate(
                    frame, image, cv2.TM_CCOEFF_NORMED))
                if score >= float(rule.get("threshold", 0.9)):
                    matches[pos] += 1

        try:
            if sample_indexes:
                # The former loop decoded every frame and merely ran image
                # matching every Nth frame.  A long 60-fps recording could
                # therefore pin one CPU core for minutes.  Seek directly to
                # the same bounded number of positions across the full clip.
                for index in sample_indexes:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, index)
                    ok, frame = capture.read()
                    if ok:
                        analyse(frame)
            else:
                # Some containers do not report a frame count.  Keep even
                # that fallback bounded instead of decoding the entire file.
                for _ in range(120):
                    ok, frame = capture.read()
                    if not ok:
                        break
                    analyse(frame)
        finally:
            capture.release()
        if not sampled:
            return None
        for pos, rule in enumerate(cleanup_rules):
            percent = 100.0 * matches[pos] / sampled
            if percent >= float(rule.get("minimum_percent", 100.0)):
                return "discard image {} detected in {:.1f}% of sampled frames".format(pos + 1, percent)
        return None

    def _mux(self, video_path, wav_path, mp4_path, output_fps,
             process_audio_gain=1.0):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg = None
        if not ffmpeg:
            print("[RECORDING] Keeping video-only AVI (FFmpeg unavailable).")
            return video_path
        has_audio = os.path.isfile(wav_path) and os.path.getsize(wav_path) > 44
        mux_wav_path = wav_path
        alignment_report = None
        timing_path = os.path.join(
            os.path.dirname(os.path.abspath(wav_path)),
            "recording_timing.json")
        if has_audio and os.path.isfile(timing_path):
            try:
                from RecordingSyncRepair import (
                    store_presentation_alignment_report,
                    write_presentation_aligned_audio)
                aligned_path = os.path.join(
                    os.path.dirname(os.path.abspath(wav_path)),
                    "recording_presentation_aligned.wav")
                alignment_report = write_presentation_aligned_audio(
                    wav_path, timing_path, aligned_path)
                if alignment_report.get("applied"):
                    mux_wav_path = aligned_path
                    print(
                        "[RECORDING] Correcting accumulated audio clock drift "
                        "from presentation timestamps ({:.3f}s, fixed offset 0ms)."
                        .format(alignment_report.get(
                            "final_drift_seconds", 0.0)))
                store_presentation_alignment_report(
                    timing_path, alignment_report)
            except Exception as error:
                alignment_report = None
                print(
                    "[RECORDING] Presentation-clock audio alignment failed; "
                    "keeping original WAV: {}".format(error))
        # Re-encode the AVI intermediate and explicitly map both tracks. CRF
        # 18 avoids compounding visible artefacts from the real-time MPEG-4
        # intermediate while ``veryfast`` keeps background finalization short.
        # One encoder/filter thread makes the offline job yield predictable
        # CPU headroom without changing the source CFR, CRF, or audio timing.
        # The upload worker may already be waiting for ``mp4_path``. Never let
        # it observe FFmpeg's partially written output as a complete video.
        temporary_mp4_path = mp4_path + ".building.mp4"
        try:
            if os.path.isfile(temporary_mp4_path):
                os.remove(temporary_mp4_path)
        except OSError:
            pass
        command = [
            # The AVI timeline has already been filled from presentation
            # timestamps at the configured CFR.  Keep that exact rate in MP4;
            # never substitute frames/elapsed measurement jitter here.
            ffmpeg, "-y", "-r", "{:.6f}".format(output_fps),
            "-i", video_path,
        ]
        if has_audio:
            command.extend(["-i", mux_wav_path])
        command.extend([
            "-map", "0:v:0",
        ])
        if has_audio:
            command.extend(["-map", "1:a:0"])
        command.extend([
            "-c:v", "libx264",
            "-threads", "1", "-filter_threads", "1",
            "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p",
        ])
        if has_audio and abs(float(process_audio_gain) - 1.0) > 0.001:
            command.extend(["-filter:a", "volume={:.4f}".format(process_audio_gain)])
        if has_audio:
            command.extend(["-c:a", "aac", "-shortest"])
        else:
            command.append("-an")
        command.extend([
            # Use the Microsoft-compatible MP4 brand and an explicit AVC tag.
            # The encoded streams are unchanged, but Windows Media Foundation
            # is less likely to reject the container with 0xc00d36c4.
            "-brand", "mp42", "-tag:v", "avc1",
            "-video_track_timescale", "60000",
            "-movflags", "+faststart", temporary_mp4_path])
        run_options = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.PIPE,
            "text": True,
        }
        if os.name == "nt":
            # The main PokeCon intentionally runs above normal priority.  Do
            # not let its ffmpeg child inherit that class and pre-empt Camera,
            # preview, and Tk while an MP4 is being finalized. Idle priority
            # lets Windows take CPU back immediately when PokeCon needs it.
            run_options["creationflags"] = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                | getattr(subprocess, "IDLE_PRIORITY_CLASS", 0x00000040)
            )
        completed = subprocess.run(command, **run_options)
        if (completed.returncode == 0
                and os.path.isfile(temporary_mp4_path)
                and os.path.getsize(temporary_mp4_path) > 1024):
            os.replace(temporary_mp4_path, mp4_path)
            if alignment_report is not None:
                try:
                    alignment_report["used_for_final_mp4"] = bool(
                        alignment_report.get("applied"))
                    store_presentation_alignment_report(
                        timing_path, alignment_report)
                except Exception:
                    pass
            print("[RECORDING] MP4 finalized: " + mp4_path)
            return mp4_path
        if os.path.isfile(temporary_mp4_path):
            try:
                os.remove(temporary_mp4_path)
            except OSError:
                pass
        print("[RECORDING] MP4 mux failed: " + completed.stderr[-500:])
        return video_path

    def configure_template(self, path):
        self.template_path = path
        self.template = cv2.imread(path, cv2.IMREAD_COLOR) if path else None

    def configure_trigger_rules(self, rules):
        """All configured images must match before a segment starts."""
        configured = []
        for rule in rules:
            path = rule.get("path", "")
            image = cv2.imread(path, cv2.IMREAD_COLOR) if path else None
            if image is not None:
                configured.append({"path": path, "image": image, "threshold": float(rule.get("threshold", 0.9))})
        self.trigger_rules = configured

    def configure_cleanup_rules(self, rules, minimum_duration=0):
        configured = []
        for rule in rules:
            path = rule.get("path", "")
            image = cv2.imread(path, cv2.IMREAD_COLOR) if path else None
            if image is not None:
                item = dict(rule)
                item["image"] = image
                configured.append(item)
        self.cleanup_rules = configured
        self.minimum_duration = max(0.0, float(minimum_duration))

    def process_detection(self, frame, fps, audio_device, audio_gain_percent,
                          threshold, roi, interval, release_seconds,
                          allow_start=True, audio_level_options=None,
                          session_started_callback=None):
        """Check only a small ROI at a controlled interval to keep CPU low."""
        now = time.monotonic()
        rules = self.trigger_rules or ([{"image": self.template, "threshold": threshold}] if self.template is not None else [])
        if not rules:
            self.last_scores = []
            self.last_detection_details = []
            self.last_score = None
            self.last_found = False
            return None
        if now - self.last_check < interval:
            if allow_start and self.active and now - self.last_detection > release_seconds:
                return DETECTION_STOP_REQUESTED
            return None
        self.last_check = now
        self.last_detection_checked_at = now
        x, y, width, height = roi
        if width <= 0 or height <= 0:
            height, width = frame.shape[:2]
            x, y = 0, 0
        self.last_roi = (x, y, width, height)
        image = frame[y : y + height, x : x + width] if width > 0 and height > 0 else frame
        self.last_scores = []
        self.last_detection_details = []
        found = True
        for index, rule in enumerate(rules):
            template = rule["image"]
            rule_threshold = float(rule.get("threshold", threshold))
            location = None
            if image.shape[0] < template.shape[0] or image.shape[1] < template.shape[1]:
                score = None
            else:
                _, score, _, max_location = cv2.minMaxLoc(
                    cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
                )
                score = float(score)
                location = (
                    x + int(max_location[0]), y + int(max_location[1]),
                    int(template.shape[1]), int(template.shape[0]),
                )
            self.last_scores.append(score)
            self.last_detection_details.append({
                "name": os.path.basename(rule.get("path", "")) or "template {}".format(index + 1),
                "path": rule.get("path", ""),
                "score": score,
                "threshold": rule_threshold,
                "matched": score is not None and score >= rule_threshold,
                "rect": location,
            })
            if score is None or score < rule_threshold:
                found = False
        self.last_score = min((score for score in self.last_scores if score is not None), default=None)
        self.last_found = found
        if found:
            self.last_detection = now
            if allow_start and not self.active:
                self.start(
                    frame, fps, audio_device, audio_gain_percent,
                    audio_level_options=audio_level_options,
                    session_started_callback=session_started_callback)
        elif allow_start and self.active and now - self.last_detection > release_seconds:
            return DETECTION_STOP_REQUESTED
        return None


def finalize_recording_manifest(manifest_path):
    """Run one durable MP4 job outside the PokeCon GUI process."""
    manifest_path = os.path.abspath(manifest_path)
    lock_path, claim_token = _claim_finalize_manifest(manifest_path)
    try:
        payload = load_finalize_manifest(manifest_path)
        previous_status = str(payload.get("status", "pending") or "pending")
        if previous_status == "recording":
            # A hard-killed recorder never had a chance to persist its final
            # elapsed time.  Recover it from the encoded frame count so cleanup
            # minimum-duration rules do not mistake a long clip for 1 ms.
            capture = cv2.VideoCapture(str(payload.get("video_path", "") or ""))
            try:
                frame_count = max(0.0, float(
                    capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0))
                source_fps = max(0.0, float(
                    capture.get(cv2.CAP_PROP_FPS) or 0.0))
            finally:
                capture.release()
            fps = source_fps or max(
                1.0, float(payload.get("output_fps", 60.0) or 60.0))
            if frame_count > 0.0:
                payload["elapsed"] = max(
                    float(payload.get("elapsed", 0.001) or 0.001),
                    frame_count / fps)
            payload["recovered_from_abandoned_recording"] = True
        payload["status"] = "processing"
        payload["worker_pid"] = os.getpid()
        payload["worker_claim"] = claim_token
        payload["started_at"] = datetime.datetime.now().isoformat(
            timespec="seconds")
        payload.pop("error", None)
        _write_json_atomic(manifest_path, payload)

        cleanup_rules = []
        for saved in payload.get("cleanup_rules", []):
            item = dict(saved)
            path = str(item.get("path", "") or "")
            image = cv2.imread(path, cv2.IMREAD_COLOR) if path else None
            if image is not None:
                item["image"] = image
                cleanup_rules.append(item)
        recorder = CaptureRecorder(
            os.path.dirname(os.path.dirname(manifest_path)),
            start_finalize_worker=False)
        try:
            result = recorder._finalize(
                payload["video_path"], payload["wav_path"],
                payload["mp4_path"],
                float(payload.get("output_fps", 60.0)),
                float(payload.get("elapsed", 0.001)),
                float(payload.get("process_audio_gain", 1.0)),
                bool(payload.get("discard", False)), cleanup_rules,
                float(payload.get("minimum_duration", 0.0)),
                str(payload.get("youtube_upload_job_path", "") or ""))
            if not os.path.exists(manifest_path):
                return result
            succeeded = (result == payload["mp4_path"]
                         and os.path.isfile(payload["mp4_path"])
                         and os.path.getsize(payload["mp4_path"]) > 1024)
            if not succeeded:
                raise RuntimeError(
                    "MP4を作成できませんでした。AVI/WAVとジョブを保持します。")
            os.remove(manifest_path)
            return result
        except Exception as error:
            if os.path.isfile(manifest_path):
                try:
                    payload = load_finalize_manifest(manifest_path)
                    payload["status"] = "failed"
                    payload["error"] = str(error)
                    payload["failed_at"] = datetime.datetime.now().isoformat(
                        timespec="seconds")
                    _write_json_atomic(manifest_path, payload)
                except Exception:
                    pass
            raise
    finally:
        _release_finalize_manifest_claim(lock_path, claim_token)
