"""Keep one recoverable Step selector for each PokeCon instance."""
import functools
import os
import tkinter as tk

from UiResponsiveness import dialog_owner_attachment_allowed


def _owner_work_area(root):
    """Use the owner's monitor, including monitors at negative coordinates."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class MonitorInfo(ctypes.Structure):
                _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                            ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
            user32.MonitorFromWindow.restype = wintypes.HANDLE
            user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
            user32.GetMonitorInfoW.restype = wintypes.BOOL
            info = MonitorInfo()
            info.size = ctypes.sizeof(info)
            monitor = user32.MonitorFromWindow(root.winfo_id(), 2)
            if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return (info.work.left, info.work.top,
                        info.work.right, info.work.bottom)
        except (AttributeError, OSError, tk.TclError):
            pass
    return (0, 0, root.winfo_screenwidth(), root.winfo_screenheight())


def _belongs_to(widget, ancestor):
    while widget is not None:
        if widget is ancestor:
            return True
        widget = getattr(widget, "master", None)
    return False


def _place_on_owner_monitor(dialog, root, center=False):
    left, top, right, bottom = _owner_work_area(root)
    # Tk reports client geometry; leave room for the native title bar/borders.
    left, top, right, bottom = left + 8, top + 32, right - 8, bottom - 16
    max_width, max_height = max(1, right - left), max(1, bottom - top)
    width = min(max_width, dialog.winfo_width())
    height = min(max_height, dialog.winfo_height())
    x, y = dialog.winfo_rootx(), dialog.winfo_rooty()
    if not center and (left <= x and top <= y
                       and x + width <= right and y + height <= bottom
                       and width == dialog.winfo_width()
                       and height == dialog.winfo_height()):
        return
    x = root.winfo_rootx() + (root.winfo_width() - width) // 2
    y = root.winfo_rooty() + (root.winfo_height() - height) // 2
    x = max(left, min(x, right - width))
    y = max(top, min(y, bottom - height))
    min_width, min_height = dialog.minsize()
    dialog.minsize(min(min_width, max_width), min(min_height, max_height))
    # The leading '+' keeps negative multi-monitor coordinates absolute in Tk.
    dialog.geometry("{}x{}+{}+{}".format(width, height, x, y))


class CommandRunDialog:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.dialog = None
        self._focus_binding = None
        self._activating = False

    def attach(self, dialog):
        self.dialog = dialog
        dialog.withdraw()
        dialog.bind("<ButtonPress-1>", self._parent_click, add="+")
        dialog.bind("<F5>", self._reactivate, add="+")
        dialog.bind("<F6>", self._reactivate, add="+")
        self._focus_binding = self.root.bind(
            "<FocusIn>", self._owner_focus, add="+")

    def present(self):
        dialog = self.dialog
        attach_to_owner = dialog_owner_attachment_allowed()
        if attach_to_owner:
            dialog.transient(self.root)
        dialog.update_idletasks()
        _place_on_owner_monitor(dialog, self.root, center=True)
        dialog.deiconify()
        dialog.update_idletasks()
        dialog.grab_set()
        self.activate()

    def activate(self):
        """Only explicit input/owner focus may restore this pending dialog."""
        dialog = self.dialog
        if dialog is None or self._activating or not dialog_owner_attachment_allowed():
            return
        self._activating = True
        try:
            if not dialog.winfo_exists():
                return
            grabbed = self.root.grab_current()
            target = dialog
            if grabbed is not None and grabbed is not dialog:
                # Preserve a nested confirmation, favorite editor or popdown.
                if not _belongs_to(grabbed, dialog):
                    return
                target = grabbed.winfo_toplevel()
            if dialog.state() in ("iconic", "withdrawn"):
                dialog.deiconify()
            dialog.update_idletasks()
            _place_on_owner_monitor(dialog, self.root)
            if target is not dialog:
                if target.state() in ("iconic", "withdrawn"):
                    target.deiconify()
                target.update_idletasks()
                _place_on_owner_monitor(target, self.root)
            target.lift()
            focused = target.focus_lastfor()
            if not _belongs_to(focused, target):
                focused = target
            focused.focus_set()
            if grabbed is None:
                dialog.grab_set()
        except (tk.TclError, KeyError):
            # Tcl-only popdowns/message boxes must retain their own grab.
            return
        finally:
            self._activating = False

    def _reactivate(self, _event=None):
        self.activate()
        return "break"

    def _parent_click(self, event):
        # A local Tk grab redirects clicks on the parent to this Toplevel;
        # the parent's Start/Reload callbacks cannot handle those clicks.
        try:
            under_pointer = self.root.winfo_containing(event.x_root, event.y_root)
            if under_pointer is not None and under_pointer.winfo_toplevel() is self.root:
                return self._reactivate()
        except (tk.TclError, KeyError):
            pass
        return None

    def _owner_focus(self, event):
        try:
            if event.widget.winfo_toplevel() is self.root:
                self.activate()
        except tk.TclError:
            pass

    def close(self):
        # Remove the owner handler before destruction can return focus to it.
        if self._focus_binding:
            try:
                self.root.unbind("<FocusIn>", self._focus_binding)
            except tk.TclError:
                pass
            self._focus_binding = None
        dialog, self.dialog = self.dialog, None
        if dialog is not None:
            try:
                dialog.destroy()
            except tk.TclError:
                pass


def single_command_run_dialog(callback):
    """Guard nested Start calls and always clean up a failed/cancelled build."""
    @functools.wraps(callback)
    def wrapped(app, *args, **kwargs):
        pending = getattr(app, "_command_run_dialog", None)
        if pending is not None:
            pending.activate()
            return False
        pending = CommandRunDialog(app)
        app._command_run_dialog = pending
        try:
            return callback(app, *args, **kwargs)
        finally:
            pending.close()
            if getattr(app, "_command_run_dialog", None) is pending:
                app._command_run_dialog = None
    return wrapped
