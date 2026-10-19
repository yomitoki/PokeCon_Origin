"""Bounded manual pulses for the existing SoftwareControllerSender worker.

This module opens no device, creates no KeyPress/worker, and calls no UI API.
The host must pause or stop Commands before queueing a job, execute it only in
the existing software-controller worker, and never coalesce pulse jobs with
latest-state mouse events. A pulse never resumes any Commands pause.
"""
from __future__ import annotations

import copy
import math
import threading
import time
import uuid
from dataclasses import dataclass, field

from Commands.Keys import Button, Hat, controller_3ds_mode


PULSE_PRESETS_MS = (25, 50, 100)
MIN_PULSE_MS = 10
MAX_PULSE_MS = 2000
PULSE_POLL_SECONDS = .005
_BUTTONS = {name: getattr(Button, name)
            for name in ("A", "B", "X", "Y", "L", "R", "ZL", "ZR", "PLUS", "MINUS")}
_HATS = dict(UP=Hat.TOP, UP_RIGHT=Hat.TOP_RIGHT, RIGHT=Hat.RIGHT,
             DOWN_RIGHT=Hat.BTM_RIGHT, DOWN=Hat.BTM, DOWN_LEFT=Hat.BTM_LEFT,
             LEFT=Hat.LEFT, UP_LEFT=Hat.TOP_LEFT)
PULSE_CONTROL_NAMES = tuple(_HATS) + tuple(_BUTTONS)


def normalize_pulse_controls(controls):
    """Accept explicit whitelisted controls, never integer bitmasks or HOME."""
    if isinstance(controls, (str, Button, Hat)):
        controls = (controls,)
    if not isinstance(controls, (list, tuple)) or not controls:
        raise ValueError("Timed pulse requires explicit permitted controls")
    result = []
    for item in controls:
        if isinstance(item, str):
            name = item.strip().upper()
            name = name[4:] if name.startswith("HAT_") else name
            control = _BUTTONS.get(name, _HATS.get(name))
        elif type(item) is Button and item in _BUTTONS.values():
            control = item
        elif type(item) is Hat and item in _HATS.values():
            control = item
        else:
            control = None
        if control is None:
            raise ValueError("Timed pulse control is not permitted: {!r}".format(item))
        if not any(type(old) is type(control) and old == control for old in result):
            result.append(control)
    if sum(type(control) is Hat for control in result) > 1:
        raise ValueError("A timed pulse may specify only one D-pad direction")
    return tuple(result)


@dataclass(frozen=True)
class TimedPulseJob:
    """One-shot FIFO job tied to the host's immutable controller binding token."""
    controls: object
    duration_ms: object
    binding_signature: object
    context: object = None
    cancel_event: object = field(default_factory=threading.Event, compare=False)
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    _claim_lock: object = field(default_factory=threading.Lock, repr=False, compare=False)
    _claimed: bool = field(default=False, init=False, repr=False, compare=False)
    coalescible = False

    def __post_init__(self):
        object.__setattr__(self, "controls", normalize_pulse_controls(self.controls))
        if isinstance(self.duration_ms, bool):
            raise ValueError("Pulse duration must be milliseconds, not bool")
        duration = float(self.duration_ms)
        if not math.isfinite(duration) or not MIN_PULSE_MS <= duration <= MAX_PULSE_MS:
            raise ValueError("Pulse duration must be finite and within 10..2000 ms")
        if self.binding_signature is None:
            raise ValueError("A controller binding signature is required")
        if not callable(getattr(self.cancel_event, "is_set", None)) or not callable(getattr(self.cancel_event, "set", None)):
            raise TypeError("cancel_event must provide is_set() and set()")
        object.__setattr__(self, "duration_ms", duration)
        object.__setattr__(self, "context", copy.deepcopy(self.context))

    @property
    def duration_seconds(self):
        return self.duration_ms / 1000.0

    @property
    def signature(self):
        return self.binding_signature

    def cancel(self):
        self.cancel_event.set()

    def claim(self):
        with self._claim_lock:
            if self._claimed:
                return False
            object.__setattr__(self, "_claimed", True)
            return True


@dataclass(frozen=True)
class PulseResult:
    status: str
    elapsed_seconds: float = 0.0
    error: str = ""

    @property
    def success(self):
        return self.status == "completed"

    @property
    def cancelled(self):
        return self.status == "cancelled"


def enqueue_timed_pulse(target_queue, job):
    """Queue without replacing older jobs; Full propagates with the queue intact."""
    if not isinstance(job, TimedPulseJob):
        raise TypeError("Expected TimedPulseJob")
    target_queue.put_nowait(job)


def _snapshot_event(keys, job, phase, stamp):
    formatter = keys.format
    mode = controller_3ds_mode(keys.serial_data_format_name)
    if mode is not None:
        message = " ".join(map(str, formatter.convert2list2(mode=mode)))
    elif keys.serial_data_format_name == "Qingpi":
        message = " ".join(map(str, formatter.convert2list()))
    else:
        message = formatter.convert2str()
    return {"job_id": job.job_id, "phase": phase, "time": stamp,
            "message": message, "format": copy.deepcopy(formatter.format),
            "binding_signature": job.binding_signature,
            "duration_ms": job.duration_ms,
            "controls": tuple(job.controls)}


def _neutral_keys(keys):
    # replace_hold clears Buttons/Hat, but intentionally retains stick axes.
    # This API does not authorize sticks or touch, even from an old formatter.
    keys.format.resetAllDirections()
    keys.format.unsetTouchscreen()
    keys.replace_hold([])


class _PinnedSenderView:
    """Use the existing sender, but never retarget its pulse to a new port.

    ``Sender.openSerial`` replaces ``Sender.ser`` while KeyPress retains the
    same Sender instance. A signature check detects that change, but cleanup
    must still release the original transport. The view shares the sender's
    existing write lock, manual override and activity observer; it opens no
    device and creates no KeyPress or worker. Other sender state is forwarded
    so normal wire formatting/recording behavior is retained.

    The host must separately defer closing the original port until a cancelled
    pulse has finished. An already closed transport cannot be neutralized.
    """
    __slots__ = ("_sender", "_port")

    def __init__(self, sender):
        object.__setattr__(self, "_sender", sender)
        object.__setattr__(self, "_port", sender.ser)

    @property
    def ser(self):
        return self._port

    def __getattr__(self, name):
        return getattr(self._sender, name)

    def __setattr__(self, name, value):
        if name in self.__slots__ or name == "ser":
            raise AttributeError("Pulse sender binding is immutable")
        setattr(self._sender, name, value)

    def writeRow(self, *args, **kwargs):
        return type(self._sender).writeRow(self, *args, **kwargs)

    def writeList(self, *args, **kwargs):
        return type(self._sender).writeList(self, *args, **kwargs)


def execute_timed_pulse(job, keys_software_controller, *, current_binding,
                        is_cancelled=None, record=None, worker_ident=None,
                        clock=time.monotonic, sleep=time.sleep):
    """Run synchronously on the host's existing software-controller worker.

    ``current_binding()`` must return the signature captured when queued. The
    host should include InputSet, sender/port identity and Commands run token.
    ``is_cancelled()`` covers Stop/Reload/shutdown; job.cancel() is independent.
    ``record(event)`` receives frozen down/neutral wire messages AFTER release,
    so a slow recorder cannot extend a 25-ms press. No pause is ever resumed.

    Stale/cancelled/busy jobs do not touch a controller before acquisition. If
    binding changes during a pulse, finally neutralizes only the original keys.
    A non-Exception Stop signal propagates after the same cleanup.
    """
    if not isinstance(job, TimedPulseJob):
        raise TypeError("Expected TimedPulseJob")
    if not job.claim():
        return PulseResult("already_executed")
    keys = keys_software_controller
    if worker_ident is not None and threading.get_ident() != worker_ident:
        return PulseResult("wrong_worker", error="Pulse must run on SoftwareControllerSender")
    if not getattr(keys, "priority", False):
        return PulseResult("failed", error="Existing priority software-controller keys are required")
    if not callable(current_binding):
        return PulseResult("failed", error="current_binding callback is required")
    cancelled = is_cancelled or (lambda: False)
    acquired = False
    events = []
    started = None
    status, error = "failed", ""
    sender = None
    pinned_sender = None

    def check():
        if job.cancel_event.is_set() or cancelled():
            return "cancelled"
        if current_binding() != job.binding_signature:
            return "stale_binding"
        if pinned_sender is not None and keys.ser is not pinned_sender:
            return "stale_binding"
        return None

    try:
        refused = check()
        if refused:
            return PulseResult(refused)
        sender = getattr(keys, "ser", None)
        if (getattr(sender, "_manual_override", False) or getattr(keys, "holdButton", ())
                or int(keys.format.format.get("btn", 0))
                or int(keys.format.format.get("hat", int(Hat.CENTER))) != int(Hat.CENTER)
                or any(keys.format.format.get(axis) != keys.NEUTRAL.get(axis)
                       for axis in ("lx", "ly", "rx", "ry", "sx", "sy"))):
            return PulseResult("busy", error="Existing manual controls/override must finish first")
        # Production KeyPress keeps one mutable Sender for the lifetime of the
        # UI. Pin its current transport before acquiring manual ownership; a
        # reconnect must not redirect the final neutral packet to another Switch.
        if getattr(sender, "ser", None) is not None:
            pinned_sender = _PinnedSenderView(sender)
            keys.ser = pinned_sender
        refused = check()
        if refused:
            return PulseResult(refused)
        keys.begin_manual_override()
        acquired = True
        refused = check()
        if refused:
            status = refused
        else:
            # Force a neutral wire boundary so two equal pulse jobs are two
            # taps, not one coalesced hold. No command object is touched.
            _neutral_keys(keys)
            refused = check()
            if refused:
                status = refused
            else:
                started = clock()
                keys.replace_hold(list(job.controls))
                events.append(_snapshot_event(keys, job, "down", started))
                deadline = started + job.duration_seconds
                status = "completed"
                while True:
                    refused = check()
                    if refused:
                        status = refused
                        break
                    remaining = deadline - clock()
                    if remaining <= 0:
                        break
                    sleep(min(PULSE_POLL_SECONDS, remaining))
    except Exception as exc:
        status, error = "failed", "{}: {}".format(type(exc).__name__, exc)
    finally:
        # If an external owner replaced keys.ser too, release through our pinned
        # view and then preserve that external owner rather than overwriting it.
        restore_sender = sender
        if pinned_sender is not None and keys.ser is not pinned_sender:
            restore_sender = keys.ser
        try:
            if pinned_sender is not None:
                keys.ser = pinned_sender
            if acquired:
                try:
                    _neutral_keys(keys)
                    events.append(_snapshot_event(keys, job, "neutral", clock()))
                except Exception as exc:
                    status, error = "failed", "Neutral failed: {}: {}".format(type(exc).__name__, exc)
                finally:
                    try:
                        keys.end_manual_override()
                    except Exception as exc:
                        status, error = "failed", "Override release failed: {}: {}".format(type(exc).__name__, exc)
        finally:
            if pinned_sender is not None:
                keys.ser = restore_sender
    elapsed = max(0.0, clock() - started) if started is not None else 0.0
    if record is not None:
        try:
            for event in events:
                event["context"] = copy.deepcopy(job.context)
                record(event)
        except Exception as exc:
            status, error = "failed", "Record failed: {}: {}".format(type(exc).__name__, exc)
    return PulseResult(status, elapsed, error)
