"""Synchronized-ish capture recorder and low-cost template-triggered segments."""
from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import threading
import time
import wave

import cv2
import numpy as np


class CaptureRecorder:
    def __init__(self, output_dir="Recordings"):
        self.output_dir = output_dir
        self.video = None
        self.audio = None
        self.audio_stream = None
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
        self.last_found = False
        self.last_roi = (0, 0, 0, 0)
        self.lock = threading.Lock()

    def start(self, frame, fps, audio_device="", audio_gain_percent=100, cleanup_rules=None, minimum_duration=0):
        if self.active or frame is None:
            return
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # Keep all artefacts belonging to one recording together.  A new
        # template-triggered segment gets its own timestamped folder too.
        self.session_dir = os.path.join(self.output_dir, stamp)
        os.makedirs(self.session_dir, exist_ok=True)
        self.video_path = os.path.join(self.session_dir, "recording.avi")
        self.wav_path = os.path.join(self.session_dir, "recording.wav")
        self.mp4_path = os.path.join(self.session_dir, "recording.mp4")
        height, width = frame.shape[:2]
        self.video = cv2.VideoWriter(self.video_path, cv2.VideoWriter_fourcc(*"MJPG"), max(1, float(fps)), (width, height))
        if not self.video.isOpened():
            self.video = None
            raise RuntimeError("動画ファイルを作成できませんでした。")
        self.frames_written = 0
        # Tk's timer and a USB capture device do not always deliver the FPS
        # selected in the Camera tab.  Keep wall-clock timing so the final
        # MP4 uses the rate that was actually captured.
        self.started_at = time.monotonic()
        self.requested_fps = max(1.0, float(fps))
        if cleanup_rules is not None:
            self.cleanup_rules = list(cleanup_rules)
            self.minimum_duration = max(0.0, float(minimum_duration))
        self.active = True
        if audio_device:
            self._start_audio(audio_device, audio_gain_percent)

    def _start_audio(self, device, gain_percent=100):
        try:
            import sounddevice as sd
            info = sd.query_devices(int(str(device).split(":", 1)[0]))
            channels = min(2, info["max_input_channels"])
            self.audio = wave.open(self.wav_path, "wb")
            self.audio.setnchannels(channels)
            self.audio.setsampwidth(2)
            self.audio.setframerate(int(info["default_samplerate"]))
            gain = max(0.0, min(float(gain_percent) / 100.0, 4.0))

            def callback(indata, frames, time_info, status):
                with self.lock:
                    if self.audio:
                        # The MP4 recording follows the same gain selected on
                        # the Audio tab (100% = unchanged, up to 400%).
                        samples = np.clip(indata.astype(np.float32) * gain, -32768, 32767)
                        self.audio.writeframes(samples.astype(np.int16).tobytes())

            self.audio_stream = sd.InputStream(device=int(str(device).split(":", 1)[0]), channels=channels,
                                               samplerate=info["default_samplerate"], dtype="int16", callback=callback,
                                               blocksize=0, latency="low")
            self.audio_stream.start()
        except Exception:
            self.audio_stream = None
            if self.audio:
                self.audio.close()
                self.audio = None

    def add_frame(self, frame):
        if self.active and self.video:
            self.video.write(frame)
            self.frames_written += 1

    def stop(self):
        if not self.active:
            return None
        self.active = False
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
        if self.audio:
            self.audio.close()
            self.audio = None
        if self.video:
            self.video.release()
            self.video = None
        if not getattr(self, "frames_written", 0):
            print("[RECORDING] No video frames were received; keeping audio file only.")
            return self.wav_path if os.path.isfile(self.wav_path) else None
        video_path, wav_path, mp4_path = self.video_path, self.wav_path, self.mp4_path
        elapsed = max(0.001, time.monotonic() - self.started_at)
        actual_fps = max(1.0, self.frames_written / elapsed)
        # Re-encoding can take seconds.  Never wait for it in the Tk/capture
        # thread: recording is already stopped and the UI may continue.
        threading.Thread(target=self._finalize, args=(video_path, wav_path, mp4_path, actual_fps, elapsed), daemon=True).start()
        print("[RECORDING] Finalizing MP4 in background ({:.2f} captured FPS): {}".format(actual_fps, mp4_path))
        return mp4_path

    def _finalize(self, video_path, wav_path, mp4_path, actual_fps, elapsed):
        reason = self._discard_reason(video_path, elapsed)
        if reason:
            session_dir = os.path.dirname(video_path)
            print("[RECORDING] Discarded recording: " + reason)
            # ``session_dir`` is always the timestamp folder created by start.
            shutil.rmtree(session_dir, ignore_errors=True)
            return None
        return self._mux(video_path, wav_path, mp4_path, actual_fps)

    def _discard_reason(self, video_path, elapsed):
        if self.minimum_duration and elapsed < self.minimum_duration:
            return "duration {:.2f}s is below {:.2f}s".format(elapsed, self.minimum_duration)
        if not self.cleanup_rules:
            return None
        capture = cv2.VideoCapture(video_path)
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, total // 120)  # analyse at most about 120 frames per clip
        matches = [0] * len(self.cleanup_rules)
        sampled = 0
        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index % step == 0:
                sampled += 1
                for pos, rule in enumerate(self.cleanup_rules):
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
        for pos, rule in enumerate(self.cleanup_rules):
            percent = 100.0 * matches[pos] / sampled
            if percent >= float(rule.get("minimum_percent", 100.0)):
                return "discard image {} detected in {:.1f}% of sampled frames".format(pos + 1, percent)
        return None

    def _mux(self, video_path, wav_path, mp4_path, actual_fps):
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
        # AVI/MJPEG copied into MP4 is not reliably playable by Windows apps.
        # Re-encode it and explicitly map both tracks.
        command = [
            # Override the temporary AVI's requested FPS with the measured
            # frame rate.  Without this, a 45-FPS header with 30 captured
            # frames per second makes the video play about 1.5x too fast.
            ffmpeg, "-y", "-r", "{:.3f}".format(actual_fps), "-i", video_path, "-i", wav_path,
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", "-movflags", "+faststart", mp4_path,
        ]
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

    def process_detection(self, frame, fps, audio_device, audio_gain_percent, threshold, roi, interval, release_seconds,
                          allow_start=True):
        """Check only a small ROI at a controlled interval to keep CPU low."""
        now = time.monotonic()
        rules = self.trigger_rules or ([{"image": self.template, "threshold": threshold}] if self.template is not None else [])
        if not rules or now - self.last_check < interval:
            if allow_start and self.active and now - self.last_detection > release_seconds:
                return self.stop()
            return None
        self.last_check = now
        x, y, width, height = roi
        if width <= 0 or height <= 0:
            height, width = frame.shape[:2]
            x, y = 0, 0
        self.last_roi = (x, y, width, height)
        image = frame[y : y + height, x : x + width] if width > 0 and height > 0 else frame
        self.last_scores = []
        found = True
        for rule in rules:
            template = rule["image"]
            if image.shape[0] < template.shape[0] or image.shape[1] < template.shape[1]:
                score = None
            else:
                _, score, _, _ = cv2.minMaxLoc(cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED))
                score = float(score)
            self.last_scores.append(score)
            if score is None or score < float(rule.get("threshold", threshold)):
                found = False
        self.last_score = min((score for score in self.last_scores if score is not None), default=None)
        self.last_found = found
        if found:
            self.last_detection = now
            if allow_start and not self.active:
                self.start(frame, fps, audio_device, audio_gain_percent)
        elif allow_start and self.active and now - self.last_detection > release_seconds:
            return self.stop()
        return None
