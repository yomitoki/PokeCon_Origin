"""Real-time peak normalization shared by Audio monitoring and recording."""
from __future__ import annotations

import math

import numpy as np


def dbfs_to_amplitude(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = -6.0
    return 10.0 ** (value / 20.0)


def amplitude_to_dbfs(value):
    try:
        value = abs(float(value))
    except (TypeError, ValueError):
        value = 0.0
    return 20.0 * math.log10(max(value, 1.0e-9))


def sanitize_audio_level_settings(gain_percent=100, target_dbfs=-6.0,
                                  max_auto_gain_percent=800,
                                  limiter_ceiling_dbfs=-1.0):
    """Repair persisted/UI values and keep useful limiter headroom."""
    try:
        gain = float(gain_percent)
    except (TypeError, ValueError):
        gain = 100.0
    if not math.isfinite(gain) or not 0.0 <= gain <= 400.0:
        gain = 100.0
    try:
        target = float(target_dbfs)
    except (TypeError, ValueError):
        target = -6.0
    if not math.isfinite(target) or not -18.0 <= target <= -1.0:
        target = -6.0
    try:
        maximum = int(max_auto_gain_percent)
    except (TypeError, ValueError):
        maximum = 800
    if not 100 <= maximum <= 800:
        maximum = 800
    try:
        ceiling = float(limiter_ceiling_dbfs)
    except (TypeError, ValueError):
        ceiling = -1.0
    if not math.isfinite(ceiling) or not -6.0 <= ceiling <= -0.1:
        ceiling = -1.0
    # Less than 3 dB between the level target and limiter causes nearly every
    # normal block to be attenuated and can sound like distortion/pumping.
    target = min(target, ceiling - 3.0)
    target = max(-18.0, target)
    return {
        "gain_percent": int(round(gain)),
        "auto_level": True,
        "target_dbfs": float(target),
        "max_auto_gain_percent": int(maximum),
        "limiter_ceiling_dbfs": float(ceiling),
    }


def suggest_audio_level_settings(raw_peak_dbfs, raw_rms_dbfs=None,
                                 raw_clip_blocks=0,
                                 raw_loud_peak_dbfs=None):
    """Build a loudness-preserving preset from measured peak and RMS.

    The manual stage stays at 100% so it cannot clip before automatic level
    control. Peak-to-RMS difference selects the target and limiter headroom;
    the adaptive stage then follows the current programme level continuously.
    """
    try:
        raw_peak = float(raw_peak_dbfs)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(raw_peak) or raw_peak < -60.0:
        return None
    try:
        raw_rms = float(raw_rms_dbfs)
    except (TypeError, ValueError):
        raw_rms = float("nan")
    if bool(raw_clip_blocks):
        # Software can attenuate an already clipped source but cannot restore
        # its waveform. Keep this preset deliberately conservative.
        target_dbfs = -9.0
        limiter_dbfs = -3.0
        transient_reserve_db = 0.0
    elif math.isfinite(raw_rms) and -90.0 < raw_rms <= raw_peak:
        desired_rms_dbfs = -18.0
        predicted_peak = raw_peak + (desired_rms_dbfs - raw_rms)
        # Use the measured crest factor to approach a comfortable average
        # level, while bounding the peak target to a conservative range.
        target_dbfs = round(
            max(-9.0, min(-4.0, predicted_peak)) * 2.0) / 2.0
        try:
            loud_peak = float(raw_loud_peak_dbfs)
        except (TypeError, ValueError):
            loud_peak = raw_peak
        excursion_db = loud_peak - raw_peak \
            if math.isfinite(loud_peak) else 0.0
        # The 95th-percentile reference preserves useful programme volume.
        # A repeatable 99th-percentile loud effect adds at most 2 dB of peak
        # protection without lowering the normal target or maximum auto gain.
        # One isolated spike therefore cannot make repeated calibration quieter.
        if excursion_db >= 12.0:
            transient_reserve_db = 2.0
        elif excursion_db >= 8.0:
            transient_reserve_db = 1.5
        elif excursion_db >= 4.0:
            transient_reserve_db = 1.0
        elif excursion_db >= 2.5:
            transient_reserve_db = 0.5
        else:
            transient_reserve_db = 0.0
        normal_limiter_dbfs = round(
            max(-3.0, min(-1.0, target_dbfs + 3.0)) * 2.0) / 2.0
        # Move only the peak ceiling. Keep at least 3 dB between target and
        # ceiling so everyday programme level remains unchanged.
        limiter_dbfs = round(max(
            target_dbfs + 3.0,
            normal_limiter_dbfs - transient_reserve_db) * 2.0) / 2.0
    else:
        target_dbfs = -6.0
        limiter_dbfs = -1.0
        transient_reserve_db = 0.0
    needed_gain = dbfs_to_amplitude(target_dbfs) / dbfs_to_amplitude(raw_peak)
    max_auto_gain = int(math.ceil(
        max(1.0, min(8.0, needed_gain)) * 100.0 / 25.0) * 25)
    return {
        "gain_percent": 100,
        "auto_level": True,
        "target_dbfs": target_dbfs,
        "max_auto_gain_percent": max(100, min(800, max_auto_gain)),
        "limiter_ceiling_dbfs": limiter_dbfs,
        "transient_reserve_db": transient_reserve_db,
    }


class AdaptivePeakNormalizer:
    """Move recent peaks toward a target without pumping every sample.

    Gain reduction is quick so a loud effect cannot remain over-amplified.
    Gain recovery is deliberately slower, and silence below -60 dBFS does not
    raise gain.  A final ceiling protects the shared playback/recording PCM.
    """

    def __init__(self, sample_rate, enabled=False, target_dbfs=-6.0,
                 max_gain_percent=200, ceiling_dbfs=-1.0):
        self.sample_rate = max(1.0, float(sample_rate or 48000))
        self.enabled = bool(enabled)
        safe = sanitize_audio_level_settings(
            target_dbfs=target_dbfs,
            max_auto_gain_percent=max_gain_percent,
            limiter_ceiling_dbfs=ceiling_dbfs)
        self.target_dbfs = safe["target_dbfs"]
        self.max_gain = safe["max_auto_gain_percent"] / 100.0
        self.ceiling_dbfs = safe["limiter_ceiling_dbfs"]
        self.target_amplitude = dbfs_to_amplitude(self.target_dbfs)
        self.ceiling_amplitude = dbfs_to_amplitude(self.ceiling_dbfs)
        self.current_gain = 1.0
        self._recent_peak = 0.0
        self._limiter_gain = 1.0
        self._last_output_gain = 1.0
        self._has_signal = False
        self.input_peak_max = 0.0
        self.pre_limiter_peak_max = 0.0
        self.output_peak_max = 0.0
        self.limited_blocks = 0
        self.last_info = {
            "enabled": self.enabled,
            "input_peak_dbfs": -180.0,
            "input_peak_max_dbfs": -180.0,
            "pre_limiter_peak_dbfs": -180.0,
            "pre_limiter_peak_max_dbfs": -180.0,
            "output_peak_dbfs": -180.0,
            "output_peak_max_dbfs": -180.0,
            "adaptive_gain": 1.0,
            "limiter_gain": 1.0,
            "limited": False,
            "limited_blocks": 0,
        }

    def reset_statistics(self):
        """Reset peak holds without causing an audible gain discontinuity."""
        self.input_peak_max = 0.0
        self.pre_limiter_peak_max = 0.0
        self.output_peak_max = 0.0
        self.limited_blocks = 0
        self.last_info.update({
            "input_peak_max_dbfs": -180.0,
            "pre_limiter_peak_max_dbfs": -180.0,
            "output_peak_max_dbfs": -180.0,
            "limited": False,
            "limited_blocks": 0,
        })

    def process(self, samples):
        array = np.asarray(samples, dtype=np.float32)
        if not array.size:
            return array
        input_peak = float(np.max(np.abs(array)))
        self.input_peak_max = max(self.input_peak_max, input_peak)
        gain = 1.0
        if self.enabled and input_peak >= dbfs_to_amplitude(-60.0):
            frames = array.shape[0] if array.ndim else 1
            duration = max(1.0 / self.sample_rate,
                           frames / self.sample_rate)
            # Retain loud effects for about half a second. Gain therefore
            # follows the current programme level rather than jumping upward
            # again on every quiet tail between effects.
            peak_decay = math.exp(-duration / 0.5)
            self._recent_peak = max(
                input_peak, self._recent_peak * peak_decay)
            desired = max(0.25, min(
                self.max_gain, self.target_amplitude /
                max(self._recent_peak, 1.0e-9)))
            if not self._has_signal:
                self.current_gain = desired
                self._has_signal = True
            else:
                # Reduce within roughly 50 ms; recover over roughly 1 second.
                seconds = 0.05 if desired < self.current_gain else 1.0
                alpha = 1.0 - math.exp(-duration / seconds)
                self.current_gain += (desired - self.current_gain) * alpha
            gain = self.current_gain
        elif self.enabled:
            gain = self.current_gain
        before_limit = input_peak * gain
        self.pre_limiter_peak_max = max(
            self.pre_limiter_peak_max, before_limit)
        ceiling = self.ceiling_amplitude if self.enabled else 1.0
        limited = before_limit > ceiling
        required_limiter_gain = min(
            1.0, ceiling / max(before_limit, 1.0e-9))
        if required_limiter_gain < self._limiter_gain:
            self._limiter_gain = required_limiter_gain
        elif self._limiter_gain < 1.0:
            frames = array.shape[0] if array.ndim else 1
            duration = max(1.0 / self.sample_rate,
                           frames / self.sample_rate)
            release_alpha = 1.0 - math.exp(-duration / 0.25)
            self._limiter_gain += (
                1.0 - self._limiter_gain) * release_alpha
        output_gain = gain * self._limiter_gain
        previous_gain = self._last_output_gain
        can_ramp = output_gain > previous_gain or \
            input_peak * previous_gain <= ceiling
        frames = array.shape[0] if array.ndim else 1
        if can_ramp and frames > 1 and abs(output_gain - previous_gain) > 1.0e-6:
            # Ramp safe gain changes across the block so callback boundaries
            # do not add small clicks. An unsafe loud transition is reduced
            # immediately to guarantee the ceiling.
            ramp_shape = (frames,) + (1,) * max(0, array.ndim - 1)
            ramp = np.linspace(
                previous_gain, output_gain, frames,
                dtype=np.float32).reshape(ramp_shape)
            output = array * ramp
        else:
            output = array * output_gain
        self._last_output_gain = output_gain
        if limited:
            self.limited_blocks += 1
        output_peak = float(np.max(np.abs(output))) if output.size else 0.0
        self.output_peak_max = max(self.output_peak_max, output_peak)
        self.last_info = {
            "enabled": self.enabled,
            "input_peak_dbfs": amplitude_to_dbfs(input_peak),
            "input_peak_max_dbfs": amplitude_to_dbfs(
                self.input_peak_max),
            "pre_limiter_peak_dbfs": amplitude_to_dbfs(before_limit),
            "pre_limiter_peak_max_dbfs": amplitude_to_dbfs(
                self.pre_limiter_peak_max),
            "output_peak_dbfs": amplitude_to_dbfs(output_peak),
            "output_peak_max_dbfs": amplitude_to_dbfs(
                self.output_peak_max),
            "adaptive_gain": float(gain),
            "limiter_gain": float(self._limiter_gain),
            "limited": bool(limited),
            "limited_blocks": int(self.limited_blocks),
            "target_dbfs": self.target_dbfs,
            "ceiling_dbfs": self.ceiling_dbfs,
        }
        return output.astype(np.float32, copy=False)
