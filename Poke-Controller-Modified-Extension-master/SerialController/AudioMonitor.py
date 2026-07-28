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

    @staticmethod
    def devices(kind="input"):
        try:
            import sounddevice as sd
            channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
            return [f"{index}: {item['name']}" for index, item in enumerate(sd.query_devices()) if item[channel_key]]
        except Exception:
            return []

    def start(self, input_device, output_device=None, gain_percent=100):
        """Start input -> speaker monitoring. ``blocksize=0`` requests the
        lowest stable latency supported by the selected audio driver."""
        self.stop()
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
        if input_channels < 1 or output_channels < 1:
            raise ValueError("選択したデバイスに共通の音声チャンネルがありません。")
        gain = max(0.0, min(float(gain_percent) / 100.0, 4.0))
        input_rate = float(input_info['default_samplerate'])
        output_rate = float(output_info['default_samplerate'])

        def input_callback(indata, frames, time_info, status):
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
                # Keep roughly 0.2 seconds: low latency without frequent dropouts.
                while sum(len(item) for item in self.buffer) > output_rate * 0.2:
                    self.buffer.popleft()

        def output_callback(outdata, frames, time_info, status):
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

        # Independent streams work even if capture and headphone devices use
        # different PortAudio/Windows host APIs.
        self.input_stream = sd.InputStream(device=input_index, channels=input_channels,
                                           samplerate=input_rate, callback=input_callback,
                                           blocksize=0, latency='low')
        self.output_stream = sd.OutputStream(device=output_index, channels=output_channels,
                                             samplerate=output_rate, callback=output_callback,
                                             blocksize=0, latency='low')
        self.input_stream.start()
        self.output_stream.start()

    def stop(self):
        for stream in (self.input_stream, self.output_stream):
            if stream is not None:
                stream.stop()
                stream.close()
        self.input_stream = None
        self.output_stream = None
        with self.buffer_lock:
            self.buffer.clear()
