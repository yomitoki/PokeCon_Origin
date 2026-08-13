"""Low-latency audio pass-through for HDMI/USB capture devices."""
from __future__ import annotations

from collections import deque
import threading
import numpy as np


class AudioMonitor:
    def __init__(self):
        self.input_stream = None
        self.output_stream = None
        self.buffer = deque()
        self.buffer_lock = threading.Lock()
        self.process_loopback = False
        self.actual_input_device_index = None
        self.last_start_notice = ""

    @staticmethod
    def devices(kind="input"):
        try:
            import sounddevice as sd
            channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
            return [f"{index}: {item['name']}" for index, item in enumerate(sd.query_devices()) if item[channel_key]]
        except Exception:
            return []

    @staticmethod
    def _candidate_input_indices(sd, selected_index):
        """Prefer the selected device, then the same endpoint via other APIs."""
        selected_index = int(selected_index)
        try:
            devices = list(sd.query_devices())
            selected = devices[selected_index]
            target_name = str(selected.get("name", "")).strip().casefold()
            hostapis = list(sd.query_hostapis())
        except Exception:
            return [selected_index]

        def host_priority(index):
            try:
                host_name = str(hostapis[int(devices[index].get("hostapi", -1))]
                                .get("name", "")).casefold()
            except (IndexError, KeyError, TypeError, ValueError):
                host_name = ""
            if "wasapi" in host_name:
                return 0
            if "directsound" in host_name:
                return 1
            if "mme" in host_name:
                return 2
            if "wdm-ks" in host_name or "asio" in host_name:
                return 4
            return 3

        equivalents = []
        for index, item in enumerate(devices):
            if index == selected_index or int(item.get("max_input_channels", 0) or 0) < 1:
                continue
            if str(item.get("name", "")).strip().casefold() == target_name:
                equivalents.append(index)
        return [selected_index] + sorted(equivalents, key=host_priority)

    @staticmethod
    def failure_message(error):
        detail = str(error)
        if "-9992" in detail or "insufficient memory" in detail.casefold():
            return (
                "Audioデバイスを開けませんでした。PortAudioがデバイス用のストリームを"
                "確保できていません。\n\n"
                "同じAudioを使用中の別PokeCon、録画ソフト、配信ソフトがある場合は、"
                "そのAudio監視を停止してから［再検索］→［Start audio］を押してください。\n\n"
                "詳細: " + detail)
        if isinstance(error, (ImportError, ModuleNotFoundError)):
            return "sounddeviceを読み込めません。依存パッケージを再インストールしてください。\n\n" + detail
        return "Audioデバイスを開始できませんでした。デバイスを再検索して選択し直してください。\n\n" + detail

    def start(self, input_device, output_device=None, gain_percent=100):
        """Open monitoring with bounded compatibility fallbacks."""
        self.stop()
        if str(input_device).startswith("選択ゲーム音声 [PID:"):
            self.process_loopback = True
            return
        import sounddevice as sd
        selected_index = int(str(input_device).split(":", 1)[0])
        attempts = []
        candidates = self._candidate_input_indices(sd, selected_index)
        profiles = ((False, False), (True, False), (True, True))
        for candidate in candidates:
            for conservative, force_mono in profiles:
                try:
                    self._start_streams(
                        candidate, output_device=output_device,
                        gain_percent=gain_percent,
                        conservative=conservative, force_mono=force_mono)
                    self.actual_input_device_index = candidate
                    if candidate != selected_index or conservative or force_mono:
                        self.last_start_notice = (
                            "Audioを互換モードで開始しました "
                            "(device {}, {}ch, {}).".format(
                                candidate, 1 if force_mono else "auto",
                                "stable buffer" if conservative else "low latency"))
                    return
                except Exception as error:
                    attempts.append(error)
                    self.stop()
        if attempts:
            raise attempts[-1]
        raise RuntimeError("Audio input device is unavailable")

    def _start_streams(self, input_device, output_device=None, gain_percent=100,
                       conservative=False, force_mono=False):
        """Start input -> speaker monitoring. ``blocksize=0`` requests the
        lowest stable latency supported by the selected audio driver."""
        self.stop()
        if str(input_device).startswith("選択ゲーム音声 [PID:"):
            # The selected game is already rendered by Windows. Replaying its
            # process loopback here would produce doubled audio; recording is
            # handled independently by CaptureRecorder.
            self.process_loopback = True
            return
        import sounddevice as sd
        input_index = int(str(input_device).split(":", 1)[0])
        # None means the Windows default playback device.  This is normally
        # the headphones/speakers already used by every other application.
        output_index = sd.default.device[1] if not output_device else int(str(output_device).split(":", 1)[0])
        if output_index is None or output_index < 0:
            raise ValueError("Windowsの既定の再生デバイス（ヘッドホン等）を設定してください。")
        input_info = sd.query_devices(input_index)
        output_info = sd.query_devices(output_index)
        input_channels = min(2, input_info['max_input_channels'])
        output_channels = min(2, output_info['max_output_channels'])
        if force_mono:
            input_channels = min(1, input_channels)
            output_channels = min(1, output_channels)
        if input_channels < 1 or output_channels < 1:
            raise ValueError("選択したデバイスに共通の音声チャンネルがありません。")
        gain = max(0.0, min(float(gain_percent) / 100.0, 4.0))
        input_rate = float(input_info['default_samplerate'])
        output_rate = float(output_info['default_samplerate'])
        buffered_frames = 0
        buffer_limit = max(1, int(output_rate * 0.2))

        def input_callback(indata, frames, time_info, status):
            nonlocal buffered_frames
            chunk = (indata.copy() * gain).clip(-1.0, 1.0)
            # Resample each small chunk when the capture card and headphones
            # use different sample rates (commonly 44.1 kHz vs 48 kHz).
            if input_rate != output_rate and len(chunk) > 1:
                target_length = max(1, round(len(chunk) * output_rate / input_rate))
                source = np.linspace(0, len(chunk) - 1, len(chunk))
                target = np.linspace(0, len(chunk) - 1, target_length)
                chunk = np.stack([np.interp(target, source, chunk[:, ch]) for ch in range(input_channels)], axis=1)
            if input_channels != output_channels:
                if input_channels == 1:
                    chunk = np.repeat(chunk, output_channels, axis=1)
                else:
                    chunk = chunk[:, :output_channels]
            with self.buffer_lock:
                self.buffer.append(chunk)
                buffered_frames += len(chunk)
                # Keep roughly 0.2 seconds: low latency without frequent dropouts.
                # Track the length incrementally; repeatedly summing the deque
                # in PortAudio's callback needlessly consumes CPU under load.
                while buffered_frames > buffer_limit and self.buffer:
                    buffered_frames -= len(self.buffer.popleft())

        def output_callback(outdata, frames, time_info, status):
            nonlocal buffered_frames
            outdata.fill(0)
            offset = 0
            with self.buffer_lock:
                while self.buffer and offset < frames:
                    chunk = self.buffer[0]
                    count = min(frames - offset, len(chunk))
                    outdata[offset : offset + count] = chunk[:count]
                    offset += count
                    if count == len(chunk):
                        self.buffer.popleft()
                    else:
                        self.buffer[0] = chunk[count:]
                    buffered_frames = max(0, buffered_frames - count)

        # Independent streams work even if capture and headphone devices use
        # different PortAudio/Windows host APIs.
        blocksize = 1024 if conservative else 0
        latency = 'high' if conservative else 'low'
        self.input_stream = sd.InputStream(device=input_index, channels=input_channels,
                                           samplerate=input_rate, callback=input_callback,
                                           blocksize=blocksize, latency=latency)
        self.output_stream = sd.OutputStream(device=output_index, channels=output_channels,
                                             samplerate=output_rate, callback=output_callback,
                                             blocksize=blocksize, latency=latency)
        self.input_stream.start()
        self.output_stream.start()

    def stop(self):
        for stream in (self.input_stream, self.output_stream):
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
        self.input_stream = None
        self.output_stream = None
        self.process_loopback = False
        self.actual_input_device_index = None
        self.last_start_notice = ""
        with self.buffer_lock:
            self.buffer.clear()
