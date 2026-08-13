"""Small policy helpers for keeping multiple Tk application instances responsive."""
from __future__ import annotations


def preview_render_interval(fps, focused=True, viewable=True, full_rate=False,
                            resource_multiplier=1.0):
    """Bound Tk image creation while leaving capture/record listeners untouched."""
    try:
        multiplier = max(1.0, float(resource_multiplier))
    except (TypeError, ValueError):
        multiplier = 1.0
    if not viewable:
        return 0.5 * multiplier
    if not focused:
        return 0.2 * multiplier
    try:
        requested = max(1, int(fps))
    except (TypeError, ValueError):
        requested = 30
    # Tk/Pillow image conversion is normally capped at 30 FPS.  A user may
    # explicitly allow the foreground or main-tool PokeCon to render at the
    # camera setting (up to the 60-FPS choice exposed by the GUI).
    limit = min(60, requested) if full_rate else min(30, requested)
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
