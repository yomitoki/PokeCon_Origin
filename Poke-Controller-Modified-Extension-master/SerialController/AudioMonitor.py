"""Low-latency audio pass-through for HDMI/USB capture devices."""
from __future__ import annotations

from collections import deque
import threading
import numpy as np

from AudioLevelControl import AdaptivePeakNormalizer, amplitude_to_dbfs


def fit_audio_block(samples, output_frames):
    """Fit a near-equal PCM block without a discontinuous sample drop.

    Independent capture and speaker devices have slightly different clocks.
    Consuming one extra/fewer source frame occasionally keeps their FIFO
    bounded.  Interpolating across the complete block spreads that one-frame
    correction over the callback instead of producing an audible click at one
    sample boundary.
    """
    source = np.asarray(samples, dtype=np.float32)
    if source.ndim == 1:
        source = source.reshape((-1, 1))
    output_frames = max(0, int(output_frames))
    if output_frames == len(source):
        return source
    if output_frames <= 0:
        return np.empty((0, source.shape[1]), dtype=np.float32)
    if not len(source):
        return np.zeros((output_frames, source.shape[1]), dtype=np.float32)
    if len(source) == 1:
        return np.repeat(source, output_frames, axis=0)
    positions = np.linspace(
        0.0, float(len(source) - 1), output_frames, dtype=np.float64)
    left = np.floor(positions).astype(np.intp)
    right = np.minimum(left + 1, len(source) - 1)
    fraction = (positions - left).astype(np.float32).reshape((-1, 1))
    return np.asarray(
        source[left] * (1.0 - fraction) + source[right] * fraction,
        dtype=np.float32)


def plan_audio_buffer_consume(available, frames, playback_started,
                              soft_buffer_limit):
    """Return ``(source_frames, correction)`` for one output callback."""
    available = max(0, int(available))
    frames = max(0, int(frames))
    soft_buffer_limit = max(0, int(soft_buffer_limit))
    correction = 0
    startup_target = max(frames, soft_buffer_limit)
    # Input and output callbacks are independent.  Even when their clocks are
    # identical, callback phase makes the observed FIFO occupancy jump by
    # roughly one speaker block around the target.  Correcting on every target
    # crossing alternates +1/-1 interpolation continuously and sounds like
    # low-level jitter or fizz.  A one-block Schmitt-trigger band ignores that
    # ordinary phase movement; a real clock mismatch eventually leaves the
    # band and is still followed one frame at a time.
    correction_margin = max(2, frames)
    low_correction_limit = max(
        frames, soft_buffer_limit - correction_margin)
    high_correction_limit = soft_buffer_limit + correction_margin
    if not playback_started and available < startup_target:
        # Prime the normal soft-latency target before the first audible block.
        # Real WASAPI capture/output callbacks can start several periods out
        # of phase, so a single callback of reserve is not always enough.
        consume = 0
    elif available > high_correction_limit and available >= frames + 1:
        correction = 1
        consume = frames + correction
    elif (playback_started and frames > 1
          and frames - 1 <= available < low_correction_limit):
        # If the input clock is fractionally slower, the FIFO can otherwise
        # lose a complete callback of reserve before the old "one frame short"
        # condition ever fires.  Begin the one-frame interpolation correction
        # below the occupancy target so the reserve remains available.  The
        # one-block hysteresis above prevents normal input/output callback
        # phase changes from reversing this correction every callback.
        correction = -1
        consume = frames + correction
    else:
        consume = frames
    return min(available, max(0, consume)), correction


class StreamingAudioRateConverter:
    """Continuously convert callback chunks without per-block edge resets."""

    def __init__(self, input_rate, output_rate, channels):
        self.input_rate = max(1.0, float(input_rate))
        self.output_rate = max(1.0, float(output_rate))
        self.channels = max(1, int(channels))
        self._total_input = 0
        self._next_source_position = 0.0
        self._last_sample = None
        ratio = self.input_rate / self.output_rate
        factor = int(round(ratio))
        self._decimation_factor = factor \
            if factor >= 2 and abs(ratio - factor) < 1.0e-6 else 0
        self._filter = None
        self._filter_state = None
        if self._decimation_factor:
            # USB capture audio commonly exposes 96 kHz while the matching
            # low-latency speaker endpoint is 48 kHz. A stateful low-pass FIR
            # avoids the high-frequency aliasing and callback-edge artefacts
            # of independently interpolating every PortAudio block.
            from scipy.signal import firwin, lfilter
            # The previous 63-tap/Hamming filter still left a narrow, weak
            # transition near the 48-kHz Nyquist limit.  Some game effects
            # contain enough energy there for the residual alias to sound like
            # intermittent fizz.  A 127-tap Kaiser filter moves the passband
            # edge to about 20 kHz for 96 -> 48 kHz and gives the stopband much
            # stronger attenuation while adding less than 1 ms group delay.
            taps = firwin(
                127, 0.84 / self._decimation_factor,
                window=("kaiser", 8.6)).astype(np.float32)
            self._filter = (taps, lfilter)
            self._filter_state = np.zeros(
                (len(taps) - 1, self.channels), dtype=np.float32)

    def process(self, samples):
        chunk = np.asarray(samples, dtype=np.float32)
        if chunk.ndim == 1:
            chunk = chunk.reshape((-1, 1))
        if not len(chunk) or self.input_rate == self.output_rate:
            return chunk
        if self._decimation_factor and self._filter is not None:
            taps, lfilter = self._filter
            filtered, self._filter_state = lfilter(
                taps, [1.0], chunk, axis=0, zi=self._filter_state)
            start = (-self._total_input) % self._decimation_factor
            self._total_input += len(chunk)
            return np.asarray(
                filtered[start::self._decimation_factor], dtype=np.float32)

        # General rational fallback. Preserve the preceding sample and the
        # fractional source position so adjacent callbacks remain continuous.
        start_index = self._total_input
        if self._last_sample is None:
            source = chunk
            source_start = start_index
        else:
            source = np.vstack((self._last_sample, chunk))
            source_start = start_index - 1
        last_index = start_index + len(chunk) - 1
        step = self.input_rate / self.output_rate
        count = max(0, int(np.floor(
            (last_index - self._next_source_position) / step)) + 1)
        if count:
            positions = self._next_source_position + step * np.arange(count)
            local = positions - source_start
            domain = np.arange(len(source), dtype=np.float64)
            output = np.stack([
                np.interp(local, domain, source[:, channel])
                for channel in range(source.shape[1])], axis=1)
            self._next_source_position += step * count
        else:
            output = np.empty((0, source.shape[1]), dtype=np.float32)
        self._last_sample = chunk[-1:].copy()
        self._total_input += len(chunk)
        return np.asarray(output, dtype=np.float32)


class AudioMonitor:
    def __init__(self):
        self.input_stream = None
        self.output_stream = None
        self.buffer = deque()
        self.buffer_lock = threading.Lock()
        self.process_loopback = False
        self.actual_input_device_index = None
        self.last_start_notice = ""
        self.selected_input_device_index = None
        self.recording_input_device_name = ""
        self.recording_input_host_api = ""
        self.recording_output_host_api = ""
        self.recording_output_device_index = None
        self.recording_output_device_name = ""
        self.recording_output_rate = 0
        self.recording_output_channels = 0
        self.recording_input_latency = 0.0
        self.recording_output_latency = 0.0
        self.rate_converter = None
        self._recording_output_listeners = {}
        self._recording_output_listener_lock = threading.Lock()
        self._recording_output_listener_sequence = 0
        self.recording_output_listener_errors = 0
        self.peak_normalizer = None
        self._last_raw_peak = 0.0
        self._last_raw_rms = 0.0
        self._raw_peak_max = 0.0
        self._raw_clip_blocks = 0
        self._raw_square_sum = 0.0
        self._raw_sample_count = 0
        self._raw_active_block_peaks_dbfs = deque(maxlen=20000)
        self._raw_active_block_rms_dbfs = deque(maxlen=20000)
        self.audio_input_status_count = 0
        self.audio_output_status_count = 0
        self.software_buffer_startup_silence_frames = 0
        self.software_buffer_underflow_frames = 0
        self.software_buffer_overflow_trimmed_frames = 0
        self.software_buffer_drift_drop_frames = 0
        self.software_buffer_drift_insert_frames = 0
        self.software_buffer_peak_frames = 0

    @staticmethod
    def devices(kind="input"):
        try:
            import sounddevice as sd
            channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
            return [f"{index}: {item['name']}" for index, item in enumerate(sd.query_devices()) if item[channel_key]]
        except Exception:
            return []

    @staticmethod
    def _same_input_endpoint(selected_name, candidate_name):
        """Match PortAudio names even when legacy APIs truncate at 31 chars."""
        selected = str(selected_name or "").strip().casefold()
        candidate = str(candidate_name or "").strip().casefold()
        if not selected or not candidate:
            return False
        if selected == candidate:
            return True
        # MME exposes names such as ``... (3- USB2 Di`` while WASAPI exposes
        # the complete ``... (3- USB2 Digital Audio)`` endpoint name.
        shorter, longer = sorted((selected, candidate), key=len)
        return len(shorter) >= 20 and longer.startswith(shorter)

    @staticmethod
    def _candidate_input_indices(sd, selected_index):
        """Prefer low-latency APIs for the selected physical endpoint."""
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
            if AudioMonitor._same_input_endpoint(
                    target_name, item.get("name", "")):
                equivalents.append(index)
        # The selected dropdown entry identifies the physical endpoint. MME
        # names are often listed first by PortAudio, but its timestamps and
        # 90-180 ms buffers are unsuitable for synchronized recording. Try the
        # equivalent WASAPI endpoint first and retain the selection as fallback.
        return sorted(
            [selected_index] + equivalents,
            key=lambda index: (host_priority(index),
                               0 if index == selected_index else 1, index))

    @staticmethod
    def _candidate_output_indices(sd, selected_index):
        """Prefer the WASAPI form of the selected physical speaker."""
        selected_index = int(selected_index)
        try:
            devices = list(sd.query_devices())
            selected = devices[selected_index]
            target_name = str(selected.get("name", "")).strip().casefold()
            hostapis = list(sd.query_hostapis())
        except Exception:
            return [selected_index]

        def host_name(index):
            try:
                return str(hostapis[int(devices[index].get("hostapi", -1))]
                           .get("name", "")).casefold()
            except (IndexError, KeyError, TypeError, ValueError):
                return ""

        equivalents = []
        for index, item in enumerate(devices):
            if index == selected_index \
                    or int(item.get("max_output_channels", 0) or 0) < 1:
                continue
            if AudioMonitor._same_input_endpoint(
                    target_name, item.get("name", "")):
                equivalents.append(index)

        def priority(index):
            api = host_name(index)
            if "wasapi" in api:
                return 0
            if index == selected_index:
                return 1
            if "mme" in api:
                return 2
            if "directsound" in api:
                return 3
            return 4

        return sorted([selected_index] + equivalents,
                      key=lambda index: (priority(index), index))

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

    def start(self, input_device, output_device=None, gain_percent=100,
              auto_level=False, target_dbfs=-6.0,
              max_auto_gain_percent=200, limiter_ceiling_dbfs=-1.0):
        """Open monitoring with bounded compatibility fallbacks."""
        self.stop()
        if str(input_device).startswith("選択ゲーム音声 [PID:"):
            self.process_loopback = True
            return
        import sounddevice as sd
        selected_index = int(str(input_device).split(":", 1)[0])
        self.selected_input_device_index = selected_index
        selected_output_index = sd.default.device[1] \
            if not output_device else int(str(output_device).split(":", 1)[0])
        if selected_output_index is None or selected_output_index < 0:
            raise ValueError(
                "Windowsの既定の再生デバイス（ヘッドホン等）を設定してください。")
        attempts = []
        candidates = self._candidate_input_indices(sd, selected_index)
        output_candidates = self._candidate_output_indices(
            sd, selected_output_index)
        profiles = ((False, False), (True, False), (True, True))
        for candidate in candidates:
            for output_candidate in output_candidates:
                for conservative, force_mono in profiles:
                    try:
                        self._start_streams(
                            candidate, output_device=output_candidate,
                            gain_percent=gain_percent,
                            conservative=conservative, force_mono=force_mono,
                            auto_level=auto_level, target_dbfs=target_dbfs,
                            max_auto_gain_percent=max_auto_gain_percent,
                            limiter_ceiling_dbfs=limiter_ceiling_dbfs)
                        self.actual_input_device_index = candidate
                        if candidate != selected_index \
                                or output_candidate != selected_output_index \
                                or conservative or force_mono:
                            self.last_start_notice = (
                                "Audioを低遅延/互換経路で開始しました "
                                "(input {}, output {}, {}ch, {}).".format(
                                    candidate, output_candidate,
                                    1 if force_mono else "auto",
                                    "stable buffer" if conservative
                                    else "low latency"))
                        return
                    except Exception as error:
                        attempts.append(error)
                        self.stop()
        if attempts:
            raise attempts[-1]
        raise RuntimeError("Audio input device is unavailable")

    def _start_streams(self, input_device, output_device=None, gain_percent=100,
                       conservative=False, force_mono=False,
                       auto_level=False, target_dbfs=-6.0,
                       max_auto_gain_percent=200,
                       limiter_ceiling_dbfs=-1.0):
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
        output_index = sd.default.device[1] if output_device is None \
            else int(str(output_device).split(":", 1)[0])
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
        try:
            host_apis = list(sd.query_hostapis())
            self.recording_input_host_api = str(
                host_apis[int(input_info.get("hostapi", -1))].get("name", ""))
            self.recording_output_host_api = str(
                host_apis[int(output_info.get("hostapi", -1))].get("name", ""))
        except (IndexError, KeyError, TypeError, ValueError):
            self.recording_input_host_api = ""
            self.recording_output_host_api = ""
        self.actual_input_device_index = input_index
        self.recording_input_device_name = str(input_info.get("name", ""))
        self.recording_output_device_index = output_index
        self.recording_output_device_name = str(output_info.get("name", ""))
        self.recording_output_rate = int(round(output_rate))
        self.recording_output_channels = int(output_channels)
        self.peak_normalizer = AdaptivePeakNormalizer(
            input_rate, enabled=auto_level, target_dbfs=target_dbfs,
            max_gain_percent=max_auto_gain_percent,
            ceiling_dbfs=limiter_ceiling_dbfs)
        self.rate_converter = StreamingAudioRateConverter(
            input_rate, output_rate, input_channels)
        self.audio_input_status_count = 0
        self.audio_output_status_count = 0
        self.software_buffer_startup_silence_frames = 0
        self.software_buffer_underflow_frames = 0
        self.software_buffer_overflow_trimmed_frames = 0
        self.software_buffer_drift_drop_frames = 0
        self.software_buffer_drift_insert_frames = 0
        self.software_buffer_peak_frames = 0
        buffered_frames = 0
        # Normal scheduling oscillates around one callback block.  Keep a soft
        # latency boundary for gradual one-frame clock correction and a much
        # higher emergency boundary.  The old 50-ms policy dropped a complete
        # deque chunk, which could create a sporadic broadband click.
        soft_buffer_limit = max(
            1, int(output_rate * (0.15 if conservative else 0.08)))
        hard_buffer_limit = max(
            soft_buffer_limit + 1,
            int(output_rate * (0.40 if conservative else 0.25)))
        playback_started = False
        recovering_from_silence = True
        pending_discontinuity_fade = False
        last_output_frame = np.zeros(
            (output_channels,), dtype=np.float32)

        def discard_buffered_frames_locked(count):
            nonlocal buffered_frames
            remaining = max(0, min(int(count), buffered_frames))
            discarded = remaining
            while remaining and self.buffer:
                chunk = self.buffer[0]
                take = min(remaining, len(chunk))
                if take == len(chunk):
                    self.buffer.popleft()
                else:
                    self.buffer[0] = chunk[take:]
                remaining -= take
                buffered_frames -= take
            return discarded - remaining

        def take_buffered_frames_locked(count):
            nonlocal buffered_frames
            remaining = max(0, min(int(count), buffered_frames))
            parts = []
            while remaining and self.buffer:
                chunk = self.buffer[0]
                take = min(remaining, len(chunk))
                parts.append(chunk[:take])
                if take == len(chunk):
                    self.buffer.popleft()
                else:
                    self.buffer[0] = chunk[take:]
                remaining -= take
                buffered_frames -= take
            if not parts:
                return np.empty(
                    (0, output_channels), dtype=np.float32)
            if len(parts) == 1:
                return np.asarray(parts[0], dtype=np.float32)
            return np.concatenate(parts, axis=0).astype(
                np.float32, copy=False)

        def input_callback(indata, frames, time_info, status):
            nonlocal buffered_frames, pending_discontinuity_fade
            if status:
                self.audio_input_status_count += 1
            raw = indata.copy()
            self._last_raw_peak = float(np.max(np.abs(raw))) \
                if raw.size else 0.0
            if raw.size:
                raw64 = raw.astype(np.float64, copy=False)
                block_square_sum = float(np.sum(raw64 * raw64))
                self._last_raw_rms = float(np.sqrt(
                    block_square_sum / raw.size))
                self._raw_square_sum += block_square_sum
                self._raw_sample_count += int(raw.size)
                block_rms_dbfs = amplitude_to_dbfs(self._last_raw_rms)
                if block_rms_dbfs >= -60.0:
                    self._raw_active_block_peaks_dbfs.append(
                        amplitude_to_dbfs(self._last_raw_peak))
                    self._raw_active_block_rms_dbfs.append(block_rms_dbfs)
            else:
                self._last_raw_rms = 0.0
            self._raw_peak_max = max(
                self._raw_peak_max, self._last_raw_peak)
            if self._last_raw_peak >= 0.999:
                self._raw_clip_blocks += 1
            chunk = self.peak_normalizer.process(raw * gain)
            chunk = self.rate_converter.process(chunk)
            if input_channels != output_channels:
                if input_channels == 1:
                    chunk = np.repeat(chunk, output_channels, axis=1)
                else:
                    chunk = chunk[:, :output_channels]
            with self.buffer_lock:
                self.buffer.append(chunk)
                buffered_frames += len(chunk)
                self.software_buffer_peak_frames = max(
                    self.software_buffer_peak_frames, buffered_frames)
                if buffered_frames > hard_buffer_limit:
                    # A device/driver stall still needs a hard latency bound.
                    # Trim only the exact excess and crossfade the next output;
                    # never jump forward by an arbitrary whole callback block.
                    trimmed = discard_buffered_frames_locked(
                        buffered_frames - soft_buffer_limit)
                    self.software_buffer_overflow_trimmed_frames += trimmed
                    pending_discontinuity_fade = bool(trimmed)

        def output_callback(outdata, frames, time_info, status):
            nonlocal buffered_frames, playback_started
            nonlocal recovering_from_silence, pending_discontinuity_fade
            nonlocal last_output_frame
            if status:
                self.audio_output_status_count += 1
            outdata.fill(0)
            with self.buffer_lock:
                available = buffered_frames
                consume, correction = plan_audio_buffer_consume(
                    available, frames, playback_started, soft_buffer_limit)
                source = take_buffered_frames_locked(consume)
            if correction and len(source) == frames + correction:
                outdata[:] = fit_audio_block(source, frames)
                if correction > 0:
                    self.software_buffer_drift_drop_frames += correction
                else:
                    self.software_buffer_drift_insert_frames += -correction
                written = frames
            else:
                written = min(frames, len(source))
                if written:
                    outdata[:written] = source[:written]
            if written:
                if recovering_from_silence or pending_discontinuity_fade:
                    fade_frames = min(96, written)
                    fade = np.linspace(
                        0.0, 1.0, fade_frames,
                        dtype=np.float32).reshape((-1, 1))
                    outdata[:fade_frames] = (
                        last_output_frame.reshape((1, -1)) * (1.0 - fade)
                        + outdata[:fade_frames] * fade)
                    recovering_from_silence = False
                    pending_discontinuity_fade = False
                playback_started = True
            if written < frames:
                missing = frames - written
                if playback_started:
                    self.software_buffer_underflow_frames += missing
                else:
                    self.software_buffer_startup_silence_frames += missing
                if written:
                    fade_frames = min(96, written)
                    fade = np.linspace(
                        1.0, 0.0, fade_frames,
                        dtype=np.float32).reshape((-1, 1))
                    outdata[written - fade_frames:written] *= fade
                recovering_from_silence = True
            last_output_frame = outdata[-1].copy()
            # Pair the exact block handed to the speaker with the frame PokeCon
            # actually drew. CaptureRecorder uses PortAudio's presentation
            # timestamp for the initial timeline alignment.
            self._publish_recording_output(
                outdata, frames, time_info, status)

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
        self.output_stream.start()
        # Start playback first so input cannot accumulate a large initial
        # backlog while a legacy output API is still opening.
        self.input_stream.start()
        try:
            self.recording_input_latency = float(self.input_stream.latency)
        except (AttributeError, TypeError, ValueError):
            self.recording_input_latency = float(
                input_info.get("default_low_input_latency", 0.0) or 0.0)
        try:
            self.recording_output_latency = float(self.output_stream.latency)
        except (AttributeError, TypeError, ValueError):
            self.recording_output_latency = float(
                output_info.get("default_low_output_latency", 0.0) or 0.0)

    def recording_output_info(self):
        stream = self.output_stream
        if stream is None or not bool(getattr(stream, "active", False)):
            return None
        if self.recording_output_rate < 1 or self.recording_output_channels < 1:
            return None
        return {
            "selected_input_device_index": self.selected_input_device_index,
            "actual_input_device_index": self.actual_input_device_index,
            "input_device_name": self.recording_input_device_name,
            "output_device_index": self.recording_output_device_index,
            "output_device_name": self.recording_output_device_name,
            "input_host_api": self.recording_input_host_api,
            "output_host_api": self.recording_output_host_api,
            "sample_rate": self.recording_output_rate,
            "channels": self.recording_output_channels,
            "latency": self.recording_output_latency,
            "capture_latency": self.recording_input_latency,
            "playback_latency": self.recording_output_latency,
            "tap_point": "speaker_output_callback",
        }

    def level_info(self):
        info = dict(getattr(
            getattr(self, "peak_normalizer", None), "last_info", {}) or {})
        info["raw_peak_dbfs"] = amplitude_to_dbfs(self._last_raw_peak)
        info["raw_rms_dbfs"] = amplitude_to_dbfs(self._last_raw_rms)
        info["raw_peak_max_dbfs"] = amplitude_to_dbfs(
            self._raw_peak_max)
        measured_rms = np.sqrt(
            self._raw_square_sum / self._raw_sample_count) \
            if self._raw_sample_count else 0.0
        info["raw_measured_rms_dbfs"] = amplitude_to_dbfs(measured_rms)
        if self._raw_active_block_peaks_dbfs:
            info["raw_reference_peak_dbfs"] = float(np.percentile(
                tuple(self._raw_active_block_peaks_dbfs), 95.0))
            info["raw_loud_peak_dbfs"] = float(np.percentile(
                tuple(self._raw_active_block_peaks_dbfs), 99.0))
            info["raw_reference_rms_dbfs"] = float(np.percentile(
                tuple(self._raw_active_block_rms_dbfs), 50.0))
            info["raw_active_blocks"] = len(
                self._raw_active_block_rms_dbfs)
        else:
            info["raw_reference_peak_dbfs"] = -180.0
            info["raw_loud_peak_dbfs"] = -180.0
            info["raw_reference_rms_dbfs"] = -180.0
            info["raw_active_blocks"] = 0
        info["raw_clip_blocks"] = int(self._raw_clip_blocks)
        info.update({
            "audio_input_status_count": int(
                self.audio_input_status_count),
            "audio_output_status_count": int(
                self.audio_output_status_count),
            "software_buffer_startup_silence_frames": int(
                self.software_buffer_startup_silence_frames),
            "software_buffer_underflow_frames": int(
                self.software_buffer_underflow_frames),
            "software_buffer_overflow_trimmed_frames": int(
                self.software_buffer_overflow_trimmed_frames),
            "software_buffer_drift_drop_frames": int(
                self.software_buffer_drift_drop_frames),
            "software_buffer_drift_insert_frames": int(
                self.software_buffer_drift_insert_frames),
            "software_buffer_peak_frames": int(
                self.software_buffer_peak_frames),
        })
        return info

    def reset_level_statistics(self):
        """Start a new raw/post-gain peak observation window."""
        self._raw_peak_max = 0.0
        self._raw_clip_blocks = 0
        self._raw_square_sum = 0.0
        self._raw_sample_count = 0
        self._raw_active_block_peaks_dbfs.clear()
        self._raw_active_block_rms_dbfs.clear()
        normalizer = self.peak_normalizer
        if normalizer is not None and hasattr(normalizer, "reset_statistics"):
            normalizer.reset_statistics()

    def add_recording_output_listener(self, callback, sample_rate, channels):
        info = self.recording_output_info()
        if info is None or int(info["sample_rate"]) != int(sample_rate) \
                or int(info["channels"]) != int(channels):
            return None
        with self._recording_output_listener_lock:
            self._recording_output_listener_sequence += 1
            token = self._recording_output_listener_sequence
            self._recording_output_listeners[token] = (
                callback, int(sample_rate), int(channels))
        return token

    def remove_recording_output_listener(self, token):
        with self._recording_output_listener_lock:
            return self._recording_output_listeners.pop(token, None) is not None

    def _publish_recording_output(self, outdata, frames, time_info, status):
        with self._recording_output_listener_lock:
            listeners = tuple(self._recording_output_listeners.values())
        for callback, sample_rate, channels in listeners:
            if sample_rate != self.recording_output_rate \
                    or channels != self.recording_output_channels:
                continue
            try:
                callback(outdata, frames, time_info, status)
            except Exception:
                self.recording_output_listener_errors += 1

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
        self.recording_input_device_name = ""
        self.recording_input_host_api = ""
        self.recording_output_host_api = ""
        self.recording_output_device_index = None
        self.recording_output_device_name = ""
        self.recording_output_rate = 0
        self.recording_output_channels = 0
        self.recording_input_latency = 0.0
        self.recording_output_latency = 0.0
        self.rate_converter = None
        self.peak_normalizer = None
        self._last_raw_peak = 0.0
        self._last_raw_rms = 0.0
        self._raw_peak_max = 0.0
        self._raw_clip_blocks = 0
        self._raw_square_sum = 0.0
        self._raw_sample_count = 0
        self._raw_active_block_peaks_dbfs.clear()
        self._raw_active_block_rms_dbfs.clear()
        self.audio_input_status_count = 0
        self.audio_output_status_count = 0
        self.software_buffer_startup_silence_frames = 0
        self.software_buffer_underflow_frames = 0
        self.software_buffer_overflow_trimmed_frames = 0
        self.software_buffer_drift_drop_frames = 0
        self.software_buffer_drift_insert_frames = 0
        self.software_buffer_peak_frames = 0
        with self.buffer_lock:
            self.buffer.clear()
