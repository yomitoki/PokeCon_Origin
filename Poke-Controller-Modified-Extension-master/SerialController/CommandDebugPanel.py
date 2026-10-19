"""Compact Commands-tab controls; all device work belongs to the host.

Callbacks run on the Tk thread and must queue long-running work themselves.
This component never opens a device, sends a controller command, starts a
worker, changes window focus, or resumes Commands.  The host is responsible
for checking the active InputSet/owner and for neutralizing cancelled pulses.
"""

import re
import tkinter as tk
from tkinter import ttk


DURATION_PRESETS_MS = (25, 50, 100)
MIN_DURATION_MS = 10
MAX_DURATION_MS = 2000
DPAD_CONTROLS = (
    "UP_LEFT", "UP", "UP_RIGHT", "LEFT", "RIGHT",
    "DOWN_LEFT", "DOWN", "DOWN_RIGHT",
)
BUTTON_CONTROLS = ("A", "B", "X", "Y", "PLUS", "MINUS")
ALLOWED_CONTROLS = DPAD_CONTROLS + BUTTON_CONTROLS


def parse_duration_ms(value):
    """Accept only explicit whole milliseconds in the UI's bounded range."""
    if type(value) is int:
        duration = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]{1,4}", value.strip()):
        duration = int(value.strip())
    else:
        raise ValueError("入力時間は10～2000 msの整数を指定してください")
    if not MIN_DURATION_MS <= duration <= MAX_DURATION_MS:
        raise ValueError("入力時間は10～2000 msの整数を指定してください")
    return duration


class CommandDebugPanel(ttk.Frame):
    """Reusable manual-debug panel with no implicit device or window actions.

    ``on_pulse(control_name, duration_ms)`` receives one canonical direction
    (for example ``UP_LEFT``) or an allowed button, and integer milliseconds.
    Capture/retest/stop/restart/fresh-start callbacks take no arguments; ``on_maximize(enabled)``
    receives a bool for the host to persist.  Returning False rejects an action.

    The host owns ``set_busy`` and should call all setters on the Tk thread.
    Use ``set_maximize`` to restore a setting without firing its callback.
    Fresh-start stays unavailable until ``set_fresh_start_supported(True)``
    confirms that the selected Command provides the required safe-start hook.
    """

    def __init__(self, parent, on_pulse=None, on_capture=None, on_retest=None,
                 on_maximize=None, on_stop=None, on_restart=None, on_fresh_start=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._callbacks = {
            "pulse": on_pulse, "capture": on_capture, "retest": on_retest,
            "maximize": on_maximize, "stop": on_stop, "restart": on_restart,
            "fresh_start": on_fresh_start,
        }
        self._enabled = True
        self._busy = False
        self._fresh_start_supported = False
        self._maximize_committed = False
        self._operation_widgets = []
        self._stop_widget = None
        self.duration_var = tk.StringVar(master=self, value="50")
        self.maximize_var = tk.BooleanVar(master=self, value=False)
        self.status_var = tk.StringVar(master=self, value="手動入力は選択中のInputSetへ送信")
        self._build_widgets()
        self._refresh_enabled()

    def _register(self, widget, operation=None):
        self._operation_widgets.append((widget, operation))
        return widget

    def _build_widgets(self):
        self.columnconfigure(0, weight=1)
        settings = ttk.Frame(self)
        settings.grid(row=0, column=0, sticky="ew", padx=3, pady=(2, 1))
        ttk.Label(settings, text="入力時間").pack(side="left")
        for duration in DURATION_PRESETS_MS:
            self._register(ttk.Radiobutton(
                settings, text=str(duration), value=str(duration),
                variable=self.duration_var)).pack(side="left", padx=(3, 0))
        self._register(ttk.Entry(
            settings, textvariable=self.duration_var, width=5,
            justify="right")).pack(side="left", padx=(5, 1))
        ttk.Label(settings, text="ms (10～2000)").pack(side="left")
        self._register(ttk.Checkbutton(
            settings, text="検証開始時に最大化", variable=self.maximize_var,
            command=self._dispatch_maximize), "maximize").pack(side="right", padx=(8, 0))

        controls = ttk.Frame(self)
        controls.grid(row=1, column=0, sticky="ew", padx=3, pady=1)
        pad = ttk.Frame(controls)
        pad.pack(side="left")
        directions = (
            ("↖", "UP_LEFT", 0, 0), ("↑", "UP", 0, 1),
            ("↗", "UP_RIGHT", 0, 2), ("←", "LEFT", 1, 0),
            ("→", "RIGHT", 1, 2), ("↙", "DOWN_LEFT", 2, 0),
            ("↓", "DOWN", 2, 1), ("↘", "DOWN_RIGHT", 2, 2),
        )
        for text, control, row, column in directions:
            self._register(ttk.Button(
                pad, text=text, width=3,
                command=lambda name=control: self._dispatch_pulse(name)),
                "pulse").grid(row=row, column=column, padx=1, pady=1)
        self._stop_widget = ttk.Button(
            pad, text="停止", width=3, command=self._dispatch_stop)
        self._stop_widget.grid(row=1, column=1, padx=1, pady=1)

        buttons = ttk.Frame(controls)
        buttons.pack(side="left", padx=(6, 8))
        for text, row, column in (
                ("Y", 0, 0), ("X", 0, 1), ("PLUS", 0, 2),
                ("B", 1, 0), ("A", 1, 1), ("MINUS", 1, 2)):
            self._register(ttk.Button(
                buttons, text=text, width=5,
                command=lambda name=text: self._dispatch_pulse(name)),
                "pulse").grid(row=row, column=column, padx=1, pady=2)

        actions = ttk.Frame(controls)
        actions.pack(side="left", fill="x", expand=True)
        self._register(ttk.Button(
            actions, text="画像＋判定保存", command=self._dispatch_capture),
            "capture").pack(fill="x", pady=2)
        self._register(ttk.Button(
            actions, text="停止→Reload→同Step再試験", command=self._dispatch_retest),
            "retest").pack(fill="x", pady=2)
        session_actions = ttk.Frame(self)
        session_actions.grid(row=2, column=0, sticky="ew", padx=3, pady=1)
        self._register(ttk.Button(
            session_actions, text="このPokeConを同じ設定で再起動", command=self._dispatch_restart),
            "restart").pack(side="left", fill="x", expand=True, padx=(0, 3), pady=2)
        self._register(ttk.Button(
            session_actions, text="タイトル→はじめから実行", command=self._dispatch_fresh_start),
            "fresh_start").pack(side="left", fill="x", expand=True, pady=2)
        self._status_label = ttk.Label(
            # A positive character width keeps the panel's requested width
            # stable when a saved path replaces a short status message.
            self, textvariable=self.status_var, anchor="w", width=72, wraplength=530)
        self._status_label.grid(row=3, column=0, sticky="ew", padx=4, pady=(1, 2))

    def _available(self, operation, allow_busy=False):
        return (self._enabled and (allow_busy or not self._busy)
                and (operation != "fresh_start" or self._fresh_start_supported)
                and callable(self._callbacks.get(operation)))

    def _invoke(self, operation, *args):
        try:
            accepted = self._callbacks[operation](*args)
        except Exception as error:
            self.set_status("操作を実行できません: {}".format(error), error=True)
            return False
        if accepted is False:
            self.set_status("操作は実行されませんでした（接続・実行状態を確認）", error=True)
            return False
        return True

    def _dispatch_pulse(self, control):
        if not self._available("pulse"):
            return False
        if not isinstance(control, str) or control not in ALLOWED_CONTROLS:
            self.set_status("許可されていない入力です", error=True)
            return False
        try:
            duration = parse_duration_ms(self.duration_var.get())
        except ValueError as error:
            self.set_status(str(error), error=True)
            return False
        return self._invoke("pulse", control, duration)

    def _dispatch_capture(self):
        return self._available("capture") and self._invoke("capture")

    def _dispatch_retest(self):
        return self._available("retest") and self._invoke("retest")

    def _dispatch_restart(self):
        return self._available("restart") and self._invoke("restart")

    def _dispatch_fresh_start(self):
        return self._available("fresh_start") and self._invoke("fresh_start")

    def _dispatch_stop(self):
        return self._available("stop", allow_busy=True) and self._invoke("stop")

    def _dispatch_maximize(self):
        if not self._available("maximize"):
            self.maximize_var.set(self._maximize_committed)
            return False
        value = bool(self.maximize_var.get())
        if not self._invoke("maximize", value):
            self.maximize_var.set(self._maximize_committed)
            return False
        self._maximize_committed = value
        return True

    def set_maximize(self, value):
        """Load a persisted setting without maximizing or calling the host."""
        self._maximize_committed = bool(value)
        self.maximize_var.set(self._maximize_committed)

    def set_status(self, text, error=False):
        self.status_var.set(str(text))
        self._status_label.configure(foreground="#b42318" if error else "")

    def _refresh_enabled(self):
        for widget, operation in self._operation_widgets:
            available = self._enabled and not self._busy
            if operation is not None:
                available = self._available(operation)
            widget.configure(state="normal" if available else "disabled")
        if self._stop_widget is not None:
            self._stop_widget.configure(
                state="normal" if self._available("stop", allow_busy=True) else "disabled")

    def set_enabled(self, enabled):
        """Enable/disable the whole panel without sending or clearing input."""
        self._enabled = bool(enabled)
        self._refresh_enabled()

    def set_fresh_start_supported(self, supported):
        """Set host-confirmed Command support, without invoking its start hook."""
        self._fresh_start_supported = bool(supported)
        self._refresh_enabled()

    def set_busy(self, busy=True):
        """Block new actions while retaining the host's emergency stop button."""
        self._busy = bool(busy)
        self._refresh_enabled()
