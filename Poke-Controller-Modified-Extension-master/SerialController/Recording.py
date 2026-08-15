"""Synchronized-ish capture recorder and low-cost template-triggered segments."""
from __future__ import annotations

import datetime
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import wave
from collections import deque

import cv2
import numpy as np

from AudioLevelControl import AdaptivePeakNormalizer


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
    def __init__(self, output_dir="Recordings"):
        self.output_dir = output_dir
        self.video = None
        self.audio = None
        self.audio_stream = None
        self.audio_queue = None
        self.audio_writer_thread = None
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
        self.process_audio = None
        self.process_audio_gain = 1.0
        self.active = False
        self.last_detection = 0.0
        self.last_check = 0.0
        self.template = None
        self.template_path = ""
        self.trigger_rules = []
        self.cleanup_rules = []
        self.minimum_duration = 0.0
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
        self.video_stop_drain_seconds = 0.0
        self.video_stop_drain_timeout = 0.0
        # Final MP4 encoding runs after capture has stopped.  Keep an explicit
        # count so the window can avoid being destroyed while ffmpeg still has
        # the recording files open.
        self._finalizing_count = 0
        # Commands monitoring rotates short clips.  Starting one ffmpeg thread
        # per clip lets encoders pile up when conversion is slower than
        # capture, eventually taking CPU away from Commands and controller
        # input.  Keep the jobs durable on disk and encode them one at a time.
        self._finalize_queue = queue.Queue()
        self._finalize_thread = threading.Thread(
            target=self._finalize_worker, daemon=True,
            name="CaptureRecordingFinalizer")
        self._finalize_thread.start()

    def start(self, frame, fps, audio_device="", audio_gain_percent=100,
              cleanup_rules=None, minimum_duration=0,
              audio_level_options=None):
        if self.active or frame is None:
            return
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
        self.video_first_presentation_at = 0.0
        self.video_last_presentation_at = 0.0
        self.video_presentation_frames = 0
        self.video_presentation_mode = ""
        self.video_stop_pending_presentations = 0
        self.video_stop_drain_seconds = 0.0
        self.video_stop_drain_timeout = 0.0
        if cleanup_rules is not None:
            self.cleanup_rules = list(cleanup_rules)
            self.minimum_duration = max(0.0, float(minimum_duration))
        self.active = True
        # MJPEG encoding stays outside Tk.  The worker advances the CFR file
        # from preview presentation timestamps, not from the later time at
        # which an asynchronously composed frame happens to arrive here.
        self.writer_thread = threading.Thread(target=self._video_writer_loop, daemon=True)
        self.writer_thread.start()
        if audio_device:
            self._start_audio(
                audio_device, audio_gain_percent, self.audio_level_options)

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
                self._advance_video_timeline(presented_at, frame)
                continue
            if stopped_at > 0.0:
                self._advance_video_timeline(stopped_at)
                return

    def _advance_video_timeline(self, timeline_at, next_frame=None):
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
        while (self.frames_written < target_frames
               and current is not None and self.video is not None):
            self.video.write(current)
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
            # Confirmation playback already contains the Audio-tab gain and
            # sample-rate conversion. Do not apply either a second time.
            self._prepare_audio_writer(
                sample_rate, channels, gain_percent=100,
                level_options={"auto_level": False})

            def listener(outdata, frames, _time_info, status):
                if self.audio_first_presentation_at <= 0.0:
                    presented_at = audio_callback_presentation_time(
                        _time_info)
                    self.audio_first_presentation_at = presented_at
                    initial_frames = int(round(max(
                        0.0, presented_at - getattr(
                            self, "started_at", presented_at)) * sample_rate))
                    self.audio_initial_alignment_frames = initial_frames
                    self.audio_pending_gap_frames += initial_frames
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
        if audio_queue is None or not self.audio_accepting_packets:
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
            self._write_audio_silence(gap_frames)
            self.audio_gap_frames_written += gap_frames
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
        if self.audio and stopped_at is not None and self.audio_sample_rate:
            target_frames = int(round(
                max(0.0, float(stopped_at) - self.started_at)
                * self.audio_sample_rate))
            if target_frames > self.audio_frames_written:
                trailing_frames = target_frames - self.audio_frames_written
                self._write_audio_silence(trailing_frames)
                self.audio_trailing_silence_frames += trailing_frames
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
                level_control = dict(self.audio_monitor.level_info() or {})
                level_control["processing_source"] = "AudioMonitor"
            except Exception:
                level_control = {}
        else:
            level_control = dict(getattr(
                self.audio_peak_normalizer, "last_info", {}) or {})
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
                "stop_drain_seconds": float(self.video_stop_drain_seconds),
                "stop_drain_timeout_seconds": float(
                    self.video_stop_drain_timeout),
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
                "sample_rate": wav_rate,
                "channels": wav_channels,
                "frames": wav_frames,
                "duration_seconds": (
                    float(wav_frames) / wav_rate if wav_rate else 0.0),
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
        if self.active and frame is not None:
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
        if not self.active:
            return None
        stopped_at = time.monotonic()
        self.active = False
        with self.video_frame_condition:
            self.video_stop_at = stopped_at
            self.video_stop_pending_presentations = len(
                self.video_frame_queue)
            if self.writer_stop:
                self.writer_stop.set()
            self.video_frame_condition.notify()
        if self.writer_thread:
            # A small transient queue must never turn into missing AVI frames.
            # The fast intermediate codec normally leaves this near zero; the
            # dynamic allowance also gives a busy disk time to drain safely.
            self.video_stop_drain_timeout = max(
                30.0, min(
                    300.0,
                    10.0 + self.video_stop_pending_presentations
                    / max(1.0, self.requested_fps * 0.5)))
            drain_started_at = time.monotonic()
            self.writer_thread.join(timeout=self.video_stop_drain_timeout)
            self.video_stop_drain_seconds = max(
                0.0, time.monotonic() - drain_started_at)
            if self.writer_thread.is_alive():
                raise RuntimeError(
                    "表示時刻に基づく録画映像の書き込みを{:.0f}秒以内に"
                    "完了できませんでした。".format(
                        self.video_stop_drain_timeout))
        self.writer_thread = None
        self.writer_stop = None
        # Stop the shared PokeCon-output producer before draining/closing its
        # WAV writer.  This is intentionally independent of audio_stream,
        # because confirmation playback is owned by AudioMonitor.
        self._stop_monitored_audio_listener()
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
        self._stop_audio_writer(stopped_at)
        if self.process_audio:
            process = self.process_audio
            self.process_audio = None
            try:
                if process.stdin:
                    process.stdin.write("\n")
                    process.stdin.flush()
                process.wait(timeout=8)
            except Exception:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except Exception:
                    process.kill()
        if self.audio:
            self.audio.close()
            self.audio = None
        if self.video:
            self.video.release()
            self.video = None
        if discard and not getattr(self, "frames_written", 0):
            shutil.rmtree(getattr(self, "session_dir", ""), ignore_errors=True)
            print("[RECORDING] Discarded recording by command-variable rule.")
            return None
        if not getattr(self, "frames_written", 0):
            print("[RECORDING] No video frames were received; keeping audio file only.")
            return self.wav_path if os.path.isfile(self.wav_path) else None
        video_path, wav_path, mp4_path = self.video_path, self.wav_path, self.mp4_path
        # Do not include process-audio shutdown/WAV finalization in captured
        # video time. Including it made the measured FPS too low and stretched
        # the final video relative to audio.
        elapsed = max(0.001, stopped_at - self.started_at)
        output_fps = max(1.0, float(self.requested_fps))
        wall_clock_frame_rate = max(1.0, self.frames_written / elapsed)
        self._write_timing_report(
            elapsed, output_fps, wall_clock_frame_rate)
        # Re-encoding can take seconds.  Never wait for it in the Tk/capture
        # thread: recording is already stopped and the UI may continue.
        with self.lock:
            self._finalizing_count += 1
        process_audio_gain = self.process_audio_gain
        cleanup_rules = list(self.cleanup_rules)
        minimum_duration = float(self.minimum_duration)
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

    def _finalize_worker(self):
        """Serialize CPU-heavy mux/cleanup jobs without blocking capture."""
        while True:
            job = self._finalize_queue.get()
            try:
                self._finalize(*job)
            except Exception as error:
                # A failed encoder must not terminate the sole worker and
                # leave every later recording permanently queued.
                print("[RECORDING] Finalizing failed: {}".format(error))
            finally:
                with self.lock:
                    self._finalizing_count = max(
                        0, self._finalizing_count - 1)
                self._finalize_queue.task_done()

    def _finalize(self, video_path, wav_path, mp4_path, output_fps, elapsed,
                  process_audio_gain=1.0, discard=False,
                  cleanup_rules=None, minimum_duration=0.0):
        if discard:
            session_dir = os.path.dirname(video_path)
            print("[RECORDING] Discarded recording by command-variable rule.")
            shutil.rmtree(session_dir, ignore_errors=True)
            return None
        reason = self._discard_reason(
            video_path, elapsed, cleanup_rules, minimum_duration)
        if reason:
            session_dir = os.path.dirname(video_path)
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
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, total // 120)  # analyse at most about 120 frames per clip
        matches = [0] * len(cleanup_rules)
        sampled = 0
        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index % step == 0:
                sampled += 1
                for pos, rule in enumerate(cleanup_rules):
                    image = rule.get("image")
                    if image is None or frame.shape[0] < image.shape[0] or frame.shape[1] < image.shape[1]:
                        continue
                    _, score, _, _ = cv2.minMaxLoc(cv2.matchTemplate(frame, image, cv2.TM_CCOEFF_NORMED))
                    if score >= float(rule.get("threshold", 0.9)):
                        matches[pos] += 1
            index += 1
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
        if not ffmpeg or not os.path.isfile(wav_path):
            print("[RECORDING] Keeping video-only AVI (FFmpeg or WAV unavailable).")
            return video_path
        # Re-encode the AVI intermediate and explicitly map both tracks. CRF
        # 18 avoids compounding visible artefacts from the real-time MPEG-4
        # intermediate while ``veryfast`` keeps background finalization short.
        command = [
            # The AVI timeline has already been filled from presentation
            # timestamps at the configured CFR.  Keep that exact rate in MP4;
            # never substitute frames/elapsed measurement jitter here.
            ffmpeg, "-y", "-r", "{:.6f}".format(output_fps),
            "-i", video_path, "-i", wav_path,
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        ]
        if abs(float(process_audio_gain) - 1.0) > 0.001:
            command.extend(["-filter:a", "volume={:.4f}".format(process_audio_gain)])
        command.extend(["-c:a", "aac", "-shortest", "-movflags", "+faststart", mp4_path])
        completed = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if completed.returncode == 0 and os.path.isfile(mp4_path):
            print("[RECORDING] MP4 finalized: " + mp4_path)
            return mp4_path
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
                          allow_start=True, audio_level_options=None):
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
                return self.stop()
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
                    audio_level_options=audio_level_options)
        elif allow_start and self.active and now - self.last_detection > release_seconds:
            return self.stop()
        return None
