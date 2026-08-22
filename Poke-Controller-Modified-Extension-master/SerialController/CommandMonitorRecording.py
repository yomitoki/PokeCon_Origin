#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""State/Step timeline helpers for bounded Commands monitoring recordings."""
from __future__ import annotations

import inspect
import linecache
import os
import re
import sys
import threading


def runtime_state_snapshot(command):
    """Return every state-machine's current scalar value without running it."""
    if command is None:
        return {}
    snapshot = {}
    values = vars(command)
    # Older Commands contain mixed-case names such as
    # ``Common_current_state``.  Resolve candidates case-insensitively while
    # preserving the actual attribute name used by the command instance.
    actual_names = {str(name).lower(): name for name in values}
    for mapping_name, mapping in values.items():
        upper = str(mapping_name).upper()
        if not (isinstance(mapping, dict)
                and upper.startswith("STATE_") and upper.endswith("_FUNCTION")):
            continue
        base = mapping_name[6:-9]
        story = re.fullmatch(r"(\d+)_STORY", base, re.IGNORECASE)
        candidates = []
        if story:
            candidates.append("_{}_story_current_state".format(story.group(1)))
        candidates.extend((
            base.lower() + "_current_state",
            mapping_name.lower().replace("state_", "", 1).replace("_function", "")
            + "_current_state",
        ))
        if upper == "STATE_MAIN_FUNCTION":
            candidates.insert(0, "main_current_state")
        current_name = next(
            (actual_names[name.lower()] for name in candidates
             if name.lower() in actual_names), "")
        if current_name:
            current = values.get(current_name)
            if isinstance(current, (str, int, float, bool)) or current is None:
                snapshot[str(mapping_name)] = str(current)
    for name in ("current_step", "step_name", "step"):
        if name in values and not isinstance(values[name], (dict, list, tuple, set)):
            snapshot.setdefault(name, str(values[name]))
    return snapshot


def snapshot_key(snapshot):
    return tuple(sorted((str(name), str(value)) for name, value in snapshot.items()))


def _state_mapping_base(variable):
    upper = str(variable).upper()
    if upper.startswith("STATE_") and upper.endswith("_FUNCTION"):
        return upper[6:-9]
    return ""


def _is_initial_state(value):
    upper = str(value).upper()
    return upper.endswith("_START") or upper.endswith("_INIT")


def relevant_state_path(snapshot):
    """Return the active outer-to-inner state path, excluding idle machines."""
    if not isinstance(snapshot, dict):
        return []
    state_items = [(str(name), str(value)) for name, value in snapshot.items()
                   if _state_mapping_base(name) and value not in (None, "")]
    selected = []

    def select(variable):
        if variable not in selected:
            selected.append(variable)

    variables = {name: value for name, value in state_items}
    if "STATE_MAIN_FUNCTION" in variables:
        select("STATE_MAIN_FUNCTION")
    else:
        main_candidates = [name for name, value in state_items
                           if _state_mapping_base(name).endswith("MAIN")
                           and not _is_initial_state(value)]
        if not main_candidates and state_items:
            main_candidates = [state_items[0][0]]
        for name in main_candidates:
            select(name)

    def expand_referenced_states():
        changed = True
        while changed:
            changed = False
            active_values = [variables[name].upper() for name in selected]
            for name, _value in state_items:
                if name in selected:
                    continue
                base = _state_mapping_base(name)
                tokens = [token for token in base.split("_")
                          if token not in ("MAIN", "FUNCTION", "STATE", "STORY")]
                matched = False
                story = re.fullmatch(r"(\d+)_STORY", base)
                for active in active_values:
                    if story and re.search(
                            r"(?:^|_){}(?:_|$)".format(story.group(1)), active):
                        matched = True
                        break
                    significant = [token for token in tokens
                                   if len(token) > 1 or token.isdigit()]
                    if significant and all(
                            re.search(r"(?:^|_){}(?:_|$)".format(re.escape(token)), active)
                            for token in significant):
                        matched = True
                        break
                if matched:
                    select(name)
                    changed = True

    # First follow the outer MAIN into its story/child machine so the display
    # order represents the actual hierarchy.
    expand_referenced_states()
    # A composed Command can enter another MAIN machine while the outer Step
    # stays unchanged.  Include an unreferenced one after it leaves START/INIT.
    for name, value in state_items:
        if (name != "STATE_MAIN_FUNCTION"
                and _state_mapping_base(name).endswith("MAIN")
                and not _is_initial_state(value)):
            select(name)
    expand_referenced_states()

    result = [variables[name] for name in selected]
    for name in ("current_step", "step_name", "step"):
        value = snapshot.get(name)
        if value not in (None, "") and str(value) not in result:
            result.append(str(value))
    if not result:
        result = [str(value) for _name, value in state_items[:1]]
    return result


def state_path_text(snapshot):
    return " > ".join(relevant_state_path(snapshot))


def command_source_descriptor(command):
    """Return stable source information for a running Commands instance."""
    if command is None:
        return {}
    command_class = command.__class__
    try:
        source_file = inspect.getsourcefile(command_class) or inspect.getfile(command_class)
    except (OSError, TypeError):
        source_file = ""
    try:
        first_line = int(inspect.getsourcelines(command_class)[1])
    except (OSError, TypeError):
        first_line = 0
    return {
        "command": str(getattr(command, "NAME", command_class.__name__)),
        "class": str(command_class.__name__),
        "module": str(getattr(command_class, "__module__", "")),
        "file": os.path.abspath(source_file) if source_file else "",
        "line": first_line,
    }


def _path_is_within(path, root):
    if not path or not root:
        return False
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) \
            == os.path.abspath(root)
    except (OSError, ValueError):
        return False


def runtime_execution_location(command, project_root=None):
    """Inspect the Commands worker stack without instrumenting user source.

    The returned frame is the innermost project function which is not one of
    PokeCon's controller/thread plumbing functions.  Therefore a state method
    or a reusable sample function is linked directly to the recording time.
    """
    worker = getattr(command, "thread", None) if command is not None else None
    ident = getattr(worker, "ident", None)
    if ident is None:
        return {}
    project_root = os.path.abspath(project_root) if project_root else ""
    ignored_files = {
        "pythoncommandbase.py", "commandbase.py", "keys.py", "sender.py",
        "threadcancellation.py", "procontroller.py", "window.py",
        "stepdebugassist.py", "commandstartoverride.py",
    }
    current_frames = sys._current_frames()
    frame = current_frames.get(ident)
    candidates = []
    try:
        while frame is not None:
            code = frame.f_code
            path = os.path.abspath(str(code.co_filename or ""))
            if (path.lower().endswith(".py")
                    and (not project_root or _path_is_within(path, project_root))):
                candidates.append({
                    "file": path,
                    "function": str(code.co_name),
                    "line": int(frame.f_lineno),
                    "source": linecache.getline(path, int(frame.f_lineno)).strip(),
                    "core": os.path.basename(path).lower() in ignored_files,
                })
            frame = frame.f_back
    finally:
        # Frames keep the entire Commands stack alive; never retain them after
        # this short sampling operation.
        del frame
        del current_frames
    if not candidates:
        return {}
    selected = next((item for item in candidates if not item["core"]), candidates[0])
    result = {key: value for key, value in selected.items() if key != "core"}
    result["stack"] = [
        {key: value for key, value in item.items() if key != "core"}
        for item in candidates if not item["core"]
    ][:8]
    return result


def runtime_execution_snapshot(command, project_root=None):
    """Capture one lightweight, read-only view of a running Commands worker.

    This deliberately samples the worker only when called.  It does not
    install ``sys.settrace`` or a line hook, so controller timing is unchanged
    while the execution-path tab is not being used.
    """
    states = runtime_state_snapshot(command)
    worker = getattr(command, "thread", None) if command is not None else None
    try:
        running = bool(worker is not None and worker.is_alive())
    except (AttributeError, RuntimeError):
        running = False
    return {
        "command": str(getattr(command, "NAME", "")) if command is not None else "",
        "running": running,
        "states": states,
        "step_path": state_path_text(states),
        "location": runtime_execution_location(command, project_root)
        if running else {},
    }


def execution_location_key(location):
    if not isinstance(location, dict):
        return ()
    return (str(location.get("file", "")), str(location.get("function", "")),
            int(location.get("line", 0) or 0))


def historical_retention_ids(chunks, keep_unique_steps=15,
                             long_step_seconds=180.0, loop_cycles=3):
    """Choose a bounded useful tail of unprotected previous recordings."""
    temporary = [chunk for chunk in chunks if not chunk.get("pinned")]
    if not temporary:
        return set()
    all_steps = {
        str(step) for chunk in temporary for step in chunk.get("states", []) if step
    }
    required_unique = min(max(1, int(keep_unique_steps)), len(all_steps))
    minimum_chunks = min(
        len(temporary), max(1, int(loop_cycles)) * 2 if len(all_steps) >= 2 else 1)
    required_seconds = max(1.0, float(long_step_seconds))
    kept = set()
    seen = set()
    duration = 0.0
    for chunk in reversed(temporary):
        kept.add(str(chunk.get("id", "")))
        seen.update(str(step) for step in chunk.get("states", []) if step)
        duration += max(0.0, float(chunk.get("duration_saved", 0.0) or 0.0))
        if (duration >= required_seconds
                and len(seen) >= required_unique
                and len(kept) >= minimum_chunks):
            break
    return kept


def temporary_chunk_ids_for_session(chunks, session_id):
    """Return only unprotected, current-runtime chunks from one Commands run."""
    session_id = str(session_id or "")
    if not session_id:
        return set()
    return {
        str(chunk.get("id", ""))
        for chunk in chunks
        if (str(chunk.get("command_session_id", "")) == session_id
            and not chunk.get("pinned")
            and not chunk.get("historical")
            and not chunk.get("delete_pending")
            and chunk.get("id") not in (None, ""))
    }


def apply_stopped_session_recording_choice(chunks, session_id, save):
    """Apply the explicit Stop dialog choice to this Commands run only.

    Saving also protects the retained chunks so the next historical cleanup
    cannot remove footage which the user explicitly chose to keep.
    """
    target_ids = temporary_chunk_ids_for_session(chunks, session_id)
    for chunk in chunks:
        if str(chunk.get("id", "")) not in target_ids:
            continue
        chunk["pinned"] = bool(save)
        chunk["delete_pending"] = not bool(save)
    return target_ids


class DarkStillFrameDetector:
    """Detect a persistently dark, visually unchanged capture frame.

    A merely static menu is not considered a failure.  Both low luminance and
    a very small frame-to-frame difference must continue for ``hold_seconds``.
    Frames are sampled to a tiny grayscale grid so this can run alongside the
    camera callback without affecting Commands or controller input.
    """

    def __init__(self, dark_threshold=28.0, difference_threshold=1.5,
                 hold_seconds=60.0, sample_interval=0.5, sample_size=24):
        self.dark_threshold = float(dark_threshold)
        self.difference_threshold = float(difference_threshold)
        self.hold_seconds = max(0.5, float(hold_seconds))
        self.sample_interval = max(0.1, float(sample_interval))
        self.sample_size = max(8, int(sample_size))
        self.reset()

    def reset(self):
        self.last_sample = None
        self.last_sample_at = None
        self.candidate_started_at = None
        self.active = None

    def _frame_sample(self, frame):
        try:
            height, width = frame.shape[:2]
        except (AttributeError, IndexError, TypeError, ValueError):
            return None
        height, width = int(height), int(width)
        if height <= 0 or width <= 0:
            return None
        row_count = min(self.sample_size, height)
        column_count = min(self.sample_size, width)
        rows = [int(round(index * (height - 1) / max(1, row_count - 1)))
                for index in range(row_count)]
        columns = [int(round(index * (width - 1) / max(1, column_count - 1)))
                   for index in range(column_count)]
        sampled = []
        try:
            for row in rows:
                for column in columns:
                    pixel = frame[row, column]
                    try:
                        if len(pixel) >= 3:
                            # Camera frames are BGR in PokeCon.
                            value = (float(pixel[0]) * 0.114
                                     + float(pixel[1]) * 0.587
                                     + float(pixel[2]) * 0.299)
                        else:
                            value = sum(float(item) for item in pixel) / len(pixel)
                    except TypeError:
                        value = float(pixel)
                    sampled.append(value)
        except (IndexError, TypeError, ValueError):
            return None
        return tuple(sampled)

    def add(self, frame, now):
        now = float(now)
        if (self.last_sample_at is not None
                and now - self.last_sample_at < self.sample_interval):
            return {"sampled": False, "stall_started": False,
                    "recovered": False,
                    "active": dict(self.active) if self.active else None}
        sample = self._frame_sample(frame)
        if sample is None:
            return {"sampled": False, "stall_started": False,
                    "recovered": False,
                    "active": dict(self.active) if self.active else None}
        brightness = sum(sample) / len(sample)
        difference = None
        if self.last_sample is not None and len(self.last_sample) == len(sample):
            difference = sum(
                abs(current - previous)
                for current, previous in zip(sample, self.last_sample)) / len(sample)
        dark_and_still = bool(
            difference is not None
            and brightness <= self.dark_threshold
            and difference <= self.difference_threshold)
        stall_started = False
        recovered = False
        if dark_and_still:
            if self.candidate_started_at is None:
                self.candidate_started_at = float(
                    self.last_sample_at if self.last_sample_at is not None else now)
            if (self.active is None
                    and now - self.candidate_started_at >= self.hold_seconds):
                self.active = {
                    "started_at": self.candidate_started_at,
                    "detected_at": now,
                    "brightness": brightness,
                    "difference": difference,
                }
                stall_started = True
            elif self.active is not None:
                self.active["brightness"] = brightness
                self.active["difference"] = difference
        else:
            recovered = self.active is not None
            self.candidate_started_at = None
            self.active = None
        self.last_sample = sample
        self.last_sample_at = now
        return {"sampled": True, "stall_started": stall_started,
                "recovered": recovered,
                "brightness": brightness, "difference": difference,
                "active": dict(self.active) if self.active else None}


class CommandInputActivityTracker:
    """Turn a long gap in Commands key packets into bounded failure evidence."""

    def __init__(self, timeout_seconds=60.0):
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self._lock = threading.Lock()
        self.reset()

    def reset(self, now=None):
        with self._lock:
            self.last_activity_at = float(now) if now is not None else None
            self.active = None
            self._recovered_pending = False

    def mark_activity(self, now):
        now = float(now)
        with self._lock:
            if self.active is not None:
                self._recovered_pending = True
            self.last_activity_at = now
            self.active = None

    def check(self, now):
        now = float(now)
        with self._lock:
            if self.last_activity_at is None:
                self.last_activity_at = now
            stall_started = False
            if (self.active is None
                    and now - self.last_activity_at >= self.timeout_seconds):
                self.active = {
                    "started_at": self.last_activity_at,
                    "detected_at": now,
                    "idle_seconds": now - self.last_activity_at,
                }
                stall_started = True
            recovered = self._recovered_pending
            self._recovered_pending = False
            return {
                "stall_started": stall_started,
                "recovered": recovered,
                "active": dict(self.active) if self.active else None,
            }


def failure_evidence_end(started_at, now, tail_seconds=60.0):
    """Bound failure footage after preserving the visible stalled interval."""
    started_at = float(started_at)
    now = float(now)
    tail_seconds = max(0.0, float(tail_seconds))
    return min(now, started_at + tail_seconds)


class CommandStateTimeline:
    """Track changed state vectors and detect short repeated Step sequences."""

    def __init__(self, loop_cycles=3, max_events=5000):
        self.loop_cycles = max(2, int(loop_cycles))
        self.max_events = max(50, int(max_events))
        self.events = []
        self.active_loop = None

    def reset(self, loop_cycles=None):
        if loop_cycles is not None:
            self.loop_cycles = max(2, int(loop_cycles))
        self.events = []
        self.active_loop = None

    def add(self, snapshot, now):
        key = snapshot_key(snapshot)
        if not key or (self.events and self.events[-1]["key"] == key):
            return {"changed": False, "loop_started": False,
                    "loop_ended": False, "event": None}
        loop_ended = False
        if self.active_loop:
            offset = len(self.events) - self.active_loop["anchor_index"]
            expected = self.active_loop["signature"][offset % self.active_loop["period"]]
            if key != expected:
                self.active_loop = None
                loop_ended = True
        event = {"time": float(now), "snapshot": dict(snapshot), "key": key}
        self.events.append(event)
        if len(self.events) > self.max_events:
            removed = len(self.events) - self.max_events
            del self.events[:removed]
            if self.active_loop:
                self.active_loop["anchor_index"] = max(
                    0, self.active_loop["anchor_index"] - removed)
        loop_started = False
        if self.active_loop is None:
            detected = self._detect_loop()
            if detected:
                self.active_loop = detected
                loop_started = True
        return {"changed": True, "loop_started": loop_started,
                "loop_ended": loop_ended, "event": event,
                "loop": dict(self.active_loop) if self.active_loop else None}

    def _detect_loop(self):
        keys = [event["key"] for event in self.events]
        cycles = self.loop_cycles
        max_period = min(8, len(keys) // cycles)
        for period in range(2, max_period + 1):
            sample = keys[-period:]
            if len(set(sample)) < 2:
                continue
            if all(keys[-period * (index + 1):-period * index if index else None] == sample
                   for index in range(cycles)):
                anchor_index = len(keys) - period * cycles
                return {
                    "signature": tuple(sample), "period": period,
                    "anchor_index": anchor_index,
                    "anchor_start": self.events[anchor_index]["time"],
                    "anchor_end": self.events[-1]["time"],
                }
        return None

    def recent_unique_cutoff(self, count):
        """A/B/A/B counts as two Steps, while returning the oldest kept time."""
        count = max(1, int(count))
        found = set()
        cutoff = self.events[-1]["time"] if self.events else None
        for event in reversed(self.events):
            found.add(event["key"])
            cutoff = event["time"]
            if len(found) >= count:
                break
        return cutoff

    @staticmethod
    def _unique_cutoff(events, count):
        count = max(1, int(count))
        found = set()
        cutoff = events[-1]["time"] if events else None
        for event in reversed(events):
            found.add(event["key"])
            cutoff = event["time"]
            if len(found) >= count:
                break
        return cutoff

    def failure_window(self, keep_unique_steps=15, terminal_time=None,
                       terminal_mode="dark_still", terminal_started_at=None):
        """Return the useful evidence window ending at a detected failure.

        For an unescaped loop, only the distinct Steps immediately before the
        loop and the first detected loop cycles are useful.  A/B/A/B is two
        distinct Steps, not four.  For explicit Stop, dark/still, or input
        inactivity, callers pass both the problem start and the configured
        evidence cutoff (normally 60 seconds).  The configured number of
        distinct Steps before the problem is retained with that failure tail.
        """
        if self.active_loop:
            anchor_index = max(0, int(self.active_loop.get("anchor_index", 0)))
            preceding = self.events[:anchor_index]
            keep_after = self._unique_cutoff(preceding, keep_unique_steps)
            if keep_after is None:
                keep_after = float(self.active_loop["anchor_start"])
            return {
                "keep_after": float(keep_after),
                "keep_before": float(self.active_loop["anchor_end"]),
                "mode": "loop",
            }
        if terminal_time is not None:
            terminal_time = float(terminal_time)
            if terminal_started_at is None:
                preceding = [event for event in self.events
                             if float(event["time"]) <= terminal_time]
                problem_event = None
            else:
                terminal_started_at = float(terminal_started_at)
                problem_index = None
                for index, event in enumerate(self.events):
                    if float(event["time"]) <= terminal_started_at:
                        problem_index = index
                    else:
                        break
                problem_event = self.events[problem_index] \
                    if problem_index is not None else None
                # The configured count means Steps *before* the problem Step.
                # Repeated paths are deduplicated, so A/B/A/B still counts as
                # two prior Steps rather than four transitions.
                preceding = self.events[:problem_index] \
                    if problem_index is not None else []
            keep_after = self._unique_cutoff(preceding, keep_unique_steps)
            if keep_after is None:
                keep_after = float(problem_event["time"]) \
                    if problem_event is not None else float(
                        terminal_started_at if terminal_started_at is not None
                        else terminal_time)
            return {"keep_after": float(keep_after),
                    "keep_before": terminal_time,
                    "mode": str(terminal_mode or "terminal")}
        return None

    def recent_loop_cutoff(self, cycles=None):
        if not self.active_loop or not self.events:
            return None
        cycles = max(1, int(cycles or self.loop_cycles))
        count = self.active_loop["period"] * cycles
        return self.events[max(0, len(self.events) - count)]["time"]

    def retention(self, now, keep_unique_steps=15, long_step_seconds=180.0,
                   loop_cycles=None, terminal_time=None,
                   terminal_mode="dark_still", terminal_started_at=None):
        failure = self.failure_window(
            keep_unique_steps=keep_unique_steps, terminal_time=terminal_time,
            terminal_mode=terminal_mode,
            terminal_started_at=terminal_started_at)
        if failure is not None:
            return {
                "keep_after": failure["keep_after"],
                "keep_before": failure["keep_before"],
                "loop_anchors": [(failure["keep_after"], failure["keep_before"])],
                "mode": failure["mode"],
            }
        cutoffs = [float(now) - max(1.0, float(long_step_seconds))]
        unique_cutoff = self.recent_unique_cutoff(keep_unique_steps)
        # With fewer than the requested number of distinct Steps, a single
        # very long Step must still be bounded by the time window.
        distinct_count = len({event["key"] for event in self.events})
        if unique_cutoff is not None and distinct_count >= max(1, int(keep_unique_steps)):
            cutoffs.append(unique_cutoff)
        loop_cutoff = self.recent_loop_cutoff(loop_cycles)
        if loop_cutoff is not None:
            cutoffs.append(loop_cutoff)
        anchors = []
        if self.active_loop:
            anchors.append((self.active_loop["anchor_start"],
                            self.active_loop["anchor_end"]))
        return {"keep_after": min(cutoffs), "keep_before": None,
                "loop_anchors": anchors, "mode": "normal"}
