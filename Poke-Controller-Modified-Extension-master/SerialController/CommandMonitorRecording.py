#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""State/Step timeline helpers for bounded Commands monitoring recordings."""
from __future__ import annotations

import re


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


def historical_retention_ids(chunks, keep_unique_steps=5,
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
            and chunk.get("id") not in (None, ""))
    }


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

    def recent_loop_cutoff(self, cycles=None):
        if not self.active_loop or not self.events:
            return None
        cycles = max(1, int(cycles or self.loop_cycles))
        count = self.active_loop["period"] * cycles
        return self.events[max(0, len(self.events) - count)]["time"]

    def retention(self, now, keep_unique_steps=5, long_step_seconds=180.0,
                  loop_cycles=None):
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
        return {"keep_after": min(cutoffs), "loop_anchors": anchors}
