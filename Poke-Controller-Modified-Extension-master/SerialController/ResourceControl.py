"""Cooperative CPU-load control for multiple running PokeCon windows."""
from __future__ import annotations

import os


THROTTLE_MULTIPLIERS = {
    "normal": 1.0,
    "light": 2.0,
    "medium": 4.0,
    "strong": 8.0,
}


def clamp_cpu_target(value, minimum=50, maximum=95):
    """Normalize the user-facing target without accepting unsafe extremes."""
    try:
        value = int(float(value))
    except (TypeError, ValueError):
        value = 90
    return max(int(minimum), min(int(maximum), value))


def resource_throttle_level(enabled, cpu_percent, target_percent,
                            main_tool=False, protected=False,
                            foreground=False):
    """Return the background-work tier for the current system load.

    Commands, active manual control and the unique main tool are deliberately
    protected.  This is cooperative throttling: it reduces PokeCon preview and
    optional-monitor work, rather than changing process priority underneath a
    running controller command.
    """
    if not enabled or main_tool or protected:
        return "normal"
    try:
        cpu = float(cpu_percent)
    except (TypeError, ValueError):
        return "normal"
    target = clamp_cpu_target(target_percent)
    if cpu >= target + 8:
        return "strong"
    # ``foreground`` is retained for compatibility with older callers, but
    # the most recently opened/focused non-main PokeCon no longer receives a
    # lighter tier. Real Commands/manual/recording work uses ``protected``.
    if cpu >= target:
        return "strong"
    if cpu >= target - 4:
        return "light"
    return "normal"


def throttle_multiplier(level):
    return float(THROTTLE_MULTIPLIERS.get(str(level), 1.0))


class SystemCpuSampler:
    """Small dependency-free total CPU sampler for Windows and Linux."""

    def __init__(self):
        self._previous = None

    @staticmethod
    def _windows_times():
        import ctypes
        from ctypes import wintypes

        idle = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetSystemTimes.argtypes = [
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        kernel32.GetSystemTimes.restype = wintypes.BOOL
        if not kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            raise OSError(ctypes.get_last_error(), "GetSystemTimes failed")

        def value(item):
            return (int(item.dwHighDateTime) << 32) | int(item.dwLowDateTime)

        idle_value = value(idle)
        return idle_value, value(kernel) + value(user)

    @staticmethod
    def _proc_times():
        with open("/proc/stat", "r", encoding="ascii") as stream:
            parts = stream.readline().split()[1:]
        values = [int(item) for item in parts]
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return idle, sum(values)

    def sample(self):
        try:
            current = self._windows_times() if os.name == "nt" else self._proc_times()
        except (OSError, ValueError, IndexError, AttributeError):
            return None
        previous, self._previous = self._previous, current
        if previous is None:
            return None
        idle_delta = current[0] - previous[0]
        total_delta = current[1] - previous[1]
        if total_delta <= 0:
            return None
        percent = 100.0 * (1.0 - (idle_delta / float(total_delta)))
        return max(0.0, min(100.0, percent))
