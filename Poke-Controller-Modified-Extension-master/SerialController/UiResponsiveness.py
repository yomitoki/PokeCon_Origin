"""Small policy helpers for keeping multiple Tk application instances responsive."""
from __future__ import annotations


def preview_render_interval(fps, focused=True, viewable=True, full_rate=False):
    """Bound Tk image creation while leaving capture/record listeners untouched."""
    if not viewable:
        return 0.5
    if not focused:
        return 0.2
    try:
        requested = max(1, int(fps))
    except (TypeError, ValueError):
        requested = 30
    # Tk/Pillow image conversion is normally capped at 30 FPS.  A user may
    # explicitly allow the most recently used PokeCon to render at the camera
    # setting (up to the 60-FPS choice exposed by the GUI).
    limit = min(60, requested) if full_rate else min(30, requested)
    return 1.0 / limit
