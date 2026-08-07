"""Utilities for reusing PC-controller recordings as replacement actions."""
from __future__ import annotations

import datetime
import math
import time


def split_record_line(line):
    """Return ``(timestamp, serial_message)`` for one controller log line."""
    text = str(line).rstrip("\r\n")
    timestamp, separator, message = text.partition(",")
    if not separator or not message.strip():
        raise ValueError("controller log line must be '<timestamp>,<serial message>'")
    datetime.datetime.fromisoformat(timestamp.strip())
    return timestamp.strip(), message.strip()


def _rotate_pair(x, y, degrees, center=128):
    radians = math.radians(float(degrees))
    offset_x, offset_y = int(x) - center, int(y) - center
    rotated_x = math.cos(radians) * offset_x - math.sin(radians) * offset_y
    rotated_y = math.sin(radians) * offset_x + math.cos(radians) * offset_y
    return (max(0, min(255, int(round(rotated_x + center)))),
            max(0, min(255, int(round(rotated_y + center)))))


def rotate_serial_message(message, degrees, sticks="both"):
    """Rotate every encoded stick vector in one PokeCon serial message."""
    parts = str(message).split()
    if len(parts) < 2:
        raise ValueError("invalid serial message")
    buttons = int(parts[0], 16)
    position = 2
    values = list(parts)
    if buttons & 0x2:
        if len(values) < position + 2:
            raise ValueError("left-stick coordinates are missing")
        if sticks in ("both", "left"):
            x, y = _rotate_pair(int(values[position], 16), int(values[position + 1], 16), degrees)
            values[position:position + 2] = ["{:02x}".format(x), "{:02x}".format(y)]
        position += 2
    if buttons & 0x1:
        if len(values) < position + 2:
            raise ValueError("right-stick coordinates are missing")
        if sticks in ("both", "right"):
            x, y = _rotate_pair(int(values[position], 16), int(values[position + 1], 16), degrees)
            values[position:position + 2] = ["{:02x}".format(x), "{:02x}".format(y)]
    return " ".join(values)


def rotate_log_range(lines, start_line, end_line, degrees, sticks="both"):
    """Rotate an inclusive one-based range, leaving non-stick rows intact."""
    result = list(lines)
    start = max(1, int(start_line))
    end = min(len(result), int(end_line))
    if end < start:
        raise ValueError("end line must be greater than or equal to start line")
    for index in range(start - 1, end):
        timestamp, message = split_record_line(result[index])
        result[index] = timestamp + "," + rotate_serial_message(message, degrees, sticks) + "\n"
    return result


def python_replacement_body(lines):
    """Generate a direct_serial call that preserves recorded relative timing."""
    parsed = [split_record_line(line) for line in lines if str(line).strip()]
    if not parsed:
        return "# Controller recording is empty.\n"
    timestamps = [datetime.datetime.fromisoformat(item[0]) for item in parsed]
    waits = [0.0]
    waits.extend(max(0.0, (timestamps[index] - timestamps[index - 1]).total_seconds())
                 for index in range(1, len(timestamps)))
    commands = [item[1] for item in parsed]
    return ("# Generated from a PC-controller recording.\n"
            "self.direct_serial({!r}, {!r})\n".format(commands, waits))


def replay_recording(lines, sender, should_continue=None):
    """Replay a registered log through a Sender while preserving timing."""
    parsed = [split_record_line(line) for line in lines if str(line).strip()]
    previous = None
    for timestamp_text, message in parsed:
        if should_continue is not None and not should_continue():
            return False
        timestamp = datetime.datetime.fromisoformat(timestamp_text)
        if previous is not None:
            delay = max(0.0, (timestamp - previous).total_seconds())
            deadline = time.monotonic() + delay
            while time.monotonic() < deadline:
                if should_continue is not None and not should_continue():
                    return False
                time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        sender.writeRow_wo_perf_counter(message, is_show=False)
        previous = timestamp
    return True
