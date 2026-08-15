"""Small safety policies for selecting a live video input."""
from __future__ import annotations


def consume_combobox_mousewheel(event=None):
    """Prevent a focused ttk Combobox from changing on an accidental wheel."""
    return "break"


def guard_combobox_mousewheel(combobox, scroll_handler=None):
    """Keep wheel scrolling from silently changing a Combobox selection.

    A containing scroll area may optionally keep receiving the wheel action;
    the Combobox value itself is always left unchanged.
    """
    callback = consume_combobox_mousewheel
    if callable(scroll_handler):
        def callback(event):
            scroll_handler(event)
            return "break"
    return combobox.bind(
        "<MouseWheel>", callback, add="+")


def is_pokecon_window_title(title, application_name):
    """Return true for a PokeCon window, which must never capture itself."""
    title = str(title or "").strip().casefold()
    application_name = str(application_name or "").strip().casefold()
    return bool(application_name) and (
        title == application_name or title.startswith(application_name + " "))
