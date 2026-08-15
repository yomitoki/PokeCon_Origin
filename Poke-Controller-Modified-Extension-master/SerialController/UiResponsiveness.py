"""Small policy helpers for keeping multiple Tk application instances responsive."""
from __future__ import annotations

import os
import time


_WINDOWS_USER32 = None
_WINDOWS_CTYPES = None
_WINDOWS_WINTYPES = None
if os.name == "nt":
    try:
        import ctypes as _ctypes
        from ctypes import wintypes as _wintypes

        _WINDOWS_USER32 = _ctypes.WinDLL("user32", use_last_error=True)
        _WINDOWS_USER32.GetForegroundWindow.argtypes = []
        _WINDOWS_USER32.GetForegroundWindow.restype = _wintypes.HWND
        _WINDOWS_USER32.GetWindowThreadProcessId.argtypes = [
            _wintypes.HWND, _ctypes.POINTER(_wintypes.DWORD)]
        _WINDOWS_USER32.GetWindowThreadProcessId.restype = _wintypes.DWORD
        _WINDOWS_CTYPES = _ctypes
        _WINDOWS_WINTYPES = _wintypes
    except (AttributeError, ImportError, OSError):
        _WINDOWS_USER32 = None


def preview_priority(focused=False, main_tool=False,
                     allow_foreground_full_rate=False, keep_warm=False):
    """Return (prioritized, full-rate) for one preview.

    A visible main tool always uses its configured preview FPS.  The checkbox
    remains the opt-in for an ordinary foreground PokeCon.
    """
    prioritized = bool(focused or main_tool or keep_warm)
    full_rate = bool(
        main_tool or (allow_foreground_full_rate and prioritized))
    return prioritized, full_rate


def preview_rate_permissions(main_tool=False, other_pokecon_foreground=False,
                             allow_foreground_full_rate=False,
                             suspended=False):
    """Return the roles that may request a 60-FPS visible preview.

    The one machine-wide main/60-FPS owner keeps its rate regardless of which
    application is in front. ``other_pokecon_foreground`` remains in the API
    for compatibility but cannot revoke the unique owner's permission.
    Exit/finalization waits still revoke it explicitly.
    """
    if suspended:
        return False, False
    return (bool(main_tool),
            bool(allow_foreground_full_rate))


def confirmation_audio_action(requested=False, runtime_owner=False,
                              other_output_active=False, stream_active=False,
                              recording_uses_output=False):
    """Choose the cross-process confirmation-playback lifecycle action.

    The effective full-rate PokeCon is the single audio-output owner.  If a
    recorder already shares its speaker callback, that stream is retained
    until recording ends so an ownership change cannot truncate the MP4 audio;
    the new owner waits for the published output claim to be released.
    """
    requested = bool(requested)
    runtime_owner = bool(runtime_owner)
    other_output_active = bool(other_output_active)
    stream_active = bool(stream_active)
    recording_uses_output = bool(recording_uses_output)
    if stream_active:
        if recording_uses_output:
            return "keep"
        # A second published output can appear during the short hand-off race.
        # Release this non-recording stream first; once both claims settle, only
        # the effective runtime owner is eligible to start again.
        if other_output_active:
            return "stop"
        if runtime_owner:
            return "keep"
        return "stop"
    if requested and runtime_owner and not other_output_active:
        return "start"
    return "wait" if requested else "off"


def compensated_after_delay(interval, started_at, now=None, minimum_ms=1):
    """Convert an interval to a Tk delay without adding callback work time.

    Tk's ``after`` delay starts only after frame conversion has finished.  A
    fixed 17-ms delay therefore turns a nominal 60-FPS preview into 17 ms plus
    all conversion time.  Subtracting work already spent keeps the next frame
    close to the requested cadence.
    """
    try:
        interval = max(0.0, float(interval))
        started_at = float(started_at)
        now = time.monotonic() if now is None else float(now)
        minimum_ms = max(1, int(minimum_ms))
    except (TypeError, ValueError):
        return 1
    remaining = interval - max(0.0, now - started_at)
    return max(minimum_ms, int(round(remaining * 1000.0)))


def preview_render_due(elapsed, interval, full_rate=False,
                       prioritized=False, viewable=True):
    """Avoid halving a full-rate preview because of early timer jitter."""
    if full_rate and prioritized:
        try:
            # A 16-ms Tk timer is slightly early for 60 FPS (16.67 ms).  Accept
            # that normal jitter, but reject genuinely duplicated callbacks.
            return float(elapsed) >= float(interval) * 0.9
        except (TypeError, ValueError):
            return True
    try:
        return float(elapsed) >= float(interval)
    except (TypeError, ValueError):
        return True


def resize_safe_preview_intervals(capture_interval, render_interval,
                                  resizing=False, background_work=False):
    """Leave Tk time to process maximize/resize messages without freezing."""
    try:
        capture_interval = max(0.0, float(capture_interval))
        render_interval = max(0.0, float(render_interval))
    except (TypeError, ValueError):
        return capture_interval, render_interval
    if not resizing:
        return capture_interval, render_interval
    if not background_work:
        capture_interval = max(capture_interval, 1.0 / 30.0)
    return capture_interval, max(render_interval, 1.0 / 15.0)


def keyboard_listener_should_run(enabled=False, window_focused=False):
    """Global keyboard-to-Switch input belongs only to the focused PokeCon."""
    return bool(enabled and window_focused)


def foreground_process_id(foreground_pid_provider=None):
    """Return the actual Windows foreground process id when available."""
    if foreground_pid_provider is not None:
        try:
            return int(foreground_pid_provider())
        except (TypeError, ValueError, OSError):
            return None
    if os.name != "nt" or _WINDOWS_USER32 is None:
        return None
    try:
        hwnd = _WINDOWS_USER32.GetForegroundWindow()
        if not hwnd:
            return None
        foreground_pid = _WINDOWS_WINTYPES.DWORD()
        _WINDOWS_USER32.GetWindowThreadProcessId(
            hwnd, _WINDOWS_CTYPES.byref(foreground_pid))
        return int(foreground_pid.value) or None
    except (AttributeError, OSError, ValueError):
        return None


def foreground_process_matches(pid=None, foreground_pid_provider=None):
    """Return whether ``pid`` owns the actual Windows foreground window.

    Tk remembers its last focused child even after another application becomes
    active, so ``focus_displayof`` alone is not a reliable cross-app test.
    A provider argument keeps the policy deterministic in tests.
    """
    pid = os.getpid() if pid is None else int(pid)
    foreground_pid = foreground_process_id(foreground_pid_provider)
    if foreground_pid is None:
        return None if os.name != "nt" and foreground_pid_provider is None \
            else False
    return foreground_pid == pid


def preview_render_interval(fps, focused=True, viewable=True, full_rate=False,
                            resource_multiplier=1.0):
    """Bound Tk image creation while leaving capture/record listeners untouched."""
    try:
        multiplier = max(1.0, float(resource_multiplier))
    except (TypeError, ValueError):
        multiplier = 1.0
    try:
        requested = max(1, int(fps))
    except (TypeError, ValueError):
        requested = 30
    # ``full_rate`` is granted to the main PokeCon even when Chrome or another
    # non-PokeCon application owns the foreground window.  It must be checked
    # before the ordinary background cap; otherwise that permission was
    # silently converted to 5 FPS and looked like a stopped preview.
    if full_rate:
        return (1.0 / min(60, requested)) * multiplier
    if not viewable:
        return 0.5 * multiplier
    if not focused:
        return 0.2 * multiplier
    # Tk/Pillow image conversion is normally capped at 30 FPS.  A user may
    # explicitly allow the foreground or main-tool PokeCon to render at the
    # camera setting (up to the 60-FPS choice exposed by the GUI).
    limit = min(30, requested)
    return (1.0 / limit) * multiplier


def preview_capture_interval(fps, focused=True, viewable=True, full_rate=False,
                             background_work=False, resource_multiplier=1.0):
    """Choose how often Tk consumes the latest camera frame.

    Camera drivers are drained independently.  Tk only needs the requested
    rate while recording/detection work explicitly depends on every frame;
    otherwise its conversion cadence can follow the cheaper preview policy.
    """
    try:
        requested = max(1, int(fps))
    except (TypeError, ValueError):
        requested = 30
    if background_work:
        return 1.0 / requested
    return preview_render_interval(
        requested, focused=focused, viewable=viewable, full_rate=full_rate,
        resource_multiplier=resource_multiplier)
