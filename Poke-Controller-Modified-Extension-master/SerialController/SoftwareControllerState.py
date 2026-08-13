"""Thread-safe latest-state buffer for the on-screen controller."""

from __future__ import annotations

import threading


def control_identity(control):
    """Keep int-backed Button and Hat values in separate namespaces."""
    return type(control), control


class SoftwareControllerState:
    """Store only the controller state the user currently intends.

    Serial output can occasionally be slower than Tk mouse events.  Replaying
    every old press in that situation makes a released direction arrive late.
    A monotonically increasing version lets the sender discard those stale
    events and transmit the newest complete state instead.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._version = 0
        self._controls = {}

    def update(self, action, controls=None):
        if controls is None:
            controls = ()
        elif not isinstance(controls, (list, tuple)):
            controls = (controls,)
        with self._lock:
            if action == "neutral":
                self._controls.clear()
            elif action == "hold":
                for control in controls:
                    self._controls[control_identity(control)] = control
            elif action == "holdEnd":
                for control in controls:
                    self._controls.pop(control_identity(control), None)
            else:
                raise ValueError("unknown software-controller action: " + str(action))
            self._version += 1
            return self._version

    def snapshot_if_current(self, version):
        with self._lock:
            if version != self._version:
                return None
            return tuple(self._controls.values())

    def latest_snapshot(self):
        with self._lock:
            return self._version, tuple(self._controls.values())
