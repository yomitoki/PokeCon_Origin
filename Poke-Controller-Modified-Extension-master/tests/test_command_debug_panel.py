"""Headless callback/validation tests: importing this creates no Tk window."""

import os
import sys
import unittest
from unittest import mock


SERIAL_CONTROLLER = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "SerialController"))
if SERIAL_CONTROLLER not in sys.path:
    sys.path.insert(0, SERIAL_CONTROLLER)

from CommandDebugPanel import (
    ALLOWED_CONTROLS, DURATION_PRESETS_MS, CommandDebugPanel, parse_duration_ms,
)
import CommandDebugPanel as panel_module


class FakeVar:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeWidget:
    created = []

    def __init__(self, *args, **kwargs):
        self.parent = args[0] if args else None
        self.options = dict(kwargs)
        self.created.append(self)

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def grid(self, **kwargs):
        self.grid_options = kwargs

    def pack(self, **kwargs):
        self.pack_options = kwargs


class CommandDebugPanelTests(unittest.TestCase):
    def setUp(self):
        # Allocate only Python state: no Tcl interpreter/display, controller,
        # camera, worker, subprocess, or real PokeCon instance is created.
        self.panel = object.__new__(CommandDebugPanel)
        self.calls = []
        self.panel._callbacks = {
            name: self.recorder(name)
            for name in ("pulse", "capture", "retest", "stop", "maximize", "restart", "fresh_start")
        }
        self.panel._enabled = True
        self.panel._busy = False
        self.panel._fresh_start_supported = True
        self.panel._maximize_committed = False
        self.panel.duration_var = FakeVar("50")
        self.panel.maximize_var = FakeVar(False)
        self.panel.status_var = FakeVar("")
        self.panel._status_label = FakeWidget()
        self.widgets = {name: FakeWidget() for name in (
            "pulse", "capture", "retest", "maximize", "duration", "restart", "fresh_start")}
        self.panel._operation_widgets = [
            (widget, None if name == "duration" else name)
            for name, widget in self.widgets.items()
        ]
        self.panel._stop_widget = FakeWidget()

    def recorder(self, name):
        return lambda *args: self.calls.append((name, args))

    def test_all_and_only_ui_controls_are_canonical(self):
        expected = {
            "UP", "UP_RIGHT", "RIGHT", "DOWN_RIGHT", "DOWN", "DOWN_LEFT",
            "LEFT", "UP_LEFT", "A", "B", "X", "Y", "PLUS", "MINUS",
        }
        self.assertEqual(set(ALLOWED_CONTROLS), expected)
        for control in ALLOWED_CONTROLS:
            self.assertTrue(self.panel._dispatch_pulse(control))
        self.assertEqual(self.calls, [("pulse", (control, 50))
                                     for control in ALLOWED_CONTROLS])

    def test_widget_buttons_bind_each_direction_without_tk_or_home(self):
        FakeWidget.created = []
        self.panel._operation_widgets = []
        self.panel.columnconfigure = lambda *args, **kwargs: None
        with mock.patch.multiple(panel_module.ttk, **{
                name: FakeWidget for name in (
                    "Frame", "Label", "Radiobutton", "Entry", "Checkbutton", "Button")}):
            self.panel._build_widgets()
        widgets = {widget.options.get("text"): widget
                   for widget in FakeWidget.created if "command" in widget.options}
        for label, control in (("↖", "UP_LEFT"), ("↑", "UP"), ("↗", "UP_RIGHT"),
                               ("←", "LEFT"), ("→", "RIGHT"), ("↙", "DOWN_LEFT"),
                               ("↓", "DOWN"), ("↘", "DOWN_RIGHT"), ("Y", "Y"),
                               ("X", "X"), ("B", "B"), ("A", "A"),
                               ("PLUS", "PLUS"), ("MINUS", "MINUS")):
            widgets[label].options["command"]()
            self.assertEqual(self.calls[-1], ("pulse", (control, 50)))
        self.assertNotIn("HOME", widgets)
        self.assertEqual(len(self.calls), 14)
        widgets["画像＋判定保存"].options["command"]()
        widgets["停止→Reload→同Step再試験"].options["command"]()
        widgets["停止"].options["command"]()
        self.assertEqual(self.calls[-3:], [("capture", ()), ("retest", ()), ("stop", ())])

    def test_disallowed_controls_never_reach_callback(self):
        for control in ("HOME", "CAPTURE", "L", "R", "ZL", "ZR", "a",
                        "HAT_UP", "STICK", "LCLICK", "", None, True, [], 1):
            with self.subTest(control=control):
                self.assertFalse(self.panel._dispatch_pulse(control))
        self.assertEqual(self.calls, [])

    def test_status_has_fixed_positive_width_for_short_and_long_paths(self):
        self.panel._operation_widgets = []
        self.panel.columnconfigure = lambda *args, **kwargs: None
        with mock.patch.multiple(panel_module.ttk, **{
                name: FakeWidget for name in (
                    "Frame", "Label", "Radiobutton", "Entry", "Checkbutton", "Button")}):
            self.panel._build_widgets()
        label = self.panel._status_label
        self.assertEqual(label.options["width"], 72)
        self.assertEqual(label.options["wraplength"], 530)
        self.assertIs(label.options["textvariable"], self.panel.status_var)
        for text in ("完了", "画像＋判定保存: C:/Recording/" + "long_directory/" * 40 + "frame.png"):
            self.panel.set_status(text)
            self.assertEqual(self.panel.status_var.get(), text)
            self.assertEqual(label.options["width"], 72)
            self.assertEqual(label.options["wraplength"], 530)

    def test_presets_and_custom_are_bounded_integer_milliseconds(self):
        self.assertEqual(DURATION_PRESETS_MS, (25, 50, 100))
        for value in (10, 25, 50, 100, 2000):
            for text in (value, str(value), " {} ".format(value)):
                with self.subTest(value=text):
                    self.assertEqual(parse_duration_ms(text), value)
        self.panel.duration_var.set("125")
        self.assertTrue(self.panel._dispatch_pulse("UP"))
        self.assertEqual(self.calls, [("pulse", ("UP", 125))])

    def test_invalid_duration_does_not_fall_back_or_send(self):
        for value in (None, True, False, -1, 0, 9, 2001, 25.0, float("nan"),
                      float("inf"), "", " ", "NaN", "inf", "25.0", "2e2",
                      "-25", "+25", "1_000", "２０", "99999", [], {}):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_duration_ms(value)
                self.panel.duration_var.set(value)
                self.assertFalse(self.panel._dispatch_pulse("A"))
        self.assertEqual(self.calls, [])

    def test_disabled_panel_rejects_every_action(self):
        self.panel.set_enabled(False)
        self.panel.maximize_var.set(True)
        for action in (lambda: self.panel._dispatch_pulse("A"),
                       self.panel._dispatch_capture, self.panel._dispatch_retest,
                       self.panel._dispatch_stop, self.panel._dispatch_maximize,
                       self.panel._dispatch_restart, self.panel._dispatch_fresh_start):
            self.assertFalse(action())
        self.assertFalse(self.panel.maximize_var.get())
        self.assertTrue(all(widget.options["state"] == "disabled"
                            for widget in self.widgets.values()))
        self.assertEqual(self.panel._stop_widget.options["state"], "disabled")
        self.assertEqual(self.calls, [])

    def test_busy_panel_blocks_new_actions_but_stop_remains_available(self):
        self.panel.set_busy(True)
        self.assertFalse(self.panel._dispatch_pulse("A"))
        self.assertFalse(self.panel._dispatch_capture())
        self.assertFalse(self.panel._dispatch_retest())
        self.assertFalse(self.panel._dispatch_restart())
        self.assertFalse(self.panel._dispatch_fresh_start())
        self.assertFalse(self.panel._dispatch_maximize())
        self.assertTrue(self.panel._dispatch_stop())
        self.assertEqual(self.calls, [("stop", ())])
        self.assertTrue(all(widget.options["state"] == "disabled"
                            for widget in self.widgets.values()))
        self.assertEqual(self.panel._stop_widget.options["state"], "normal")
        self.panel.set_busy(False)
        self.assertTrue(all(widget.options["state"] == "normal"
                            for widget in self.widgets.values()))

    def test_missing_callbacks_disable_their_buttons(self):
        self.panel._callbacks.update(pulse=None, stop=None)
        self.panel._refresh_enabled()
        self.assertEqual(self.widgets["pulse"].options["state"], "disabled")
        self.assertEqual(self.widgets["capture"].options["state"], "normal")
        self.assertEqual(self.panel._stop_widget.options["state"], "disabled")
        self.assertFalse(self.panel._dispatch_pulse("A"))
        self.assertFalse(self.panel._dispatch_stop())

    def test_capture_and_retest_call_once_without_arguments(self):
        self.assertTrue(self.panel._dispatch_capture())
        self.assertTrue(self.panel._dispatch_retest())
        self.assertEqual(self.calls, [("capture", ()), ("retest", ())])

    def test_maximize_load_is_callback_free_and_user_toggle_passes_bool(self):
        self.panel.set_maximize(True)
        self.assertTrue(self.panel.maximize_var.get())
        self.assertEqual(self.calls, [])
        self.panel.maximize_var.set(False)
        self.assertTrue(self.panel._dispatch_maximize())
        self.assertEqual(self.calls, [("maximize", (False,))])
        self.assertFalse(self.panel._maximize_committed)

    def test_rejected_maximize_restores_persisted_value(self):
        self.panel.set_maximize(True)
        self.panel._callbacks["maximize"] = lambda _value: False
        self.panel.maximize_var.set(False)
        self.assertFalse(self.panel._dispatch_maximize())
        self.assertTrue(self.panel.maximize_var.get())
        self.assertTrue(self.panel._maximize_committed)

    def test_callback_exceptions_become_error_status_without_replay(self):
        def reject(*args):
            self.calls.append(("failed", args))
            raise RuntimeError("未接続")
        self.panel._callbacks["pulse"] = reject
        self.assertFalse(self.panel._dispatch_pulse("A"))
        self.assertEqual(self.calls, [("failed", ("A", 50))])
        self.assertIn("未接続", self.panel.status_var.get())
        self.assertEqual(self.panel._status_label.options["foreground"], "#b42318")

    def test_callback_rejection_does_not_retry_or_mark_panel_busy(self):
        self.panel._callbacks["capture"] = lambda: False
        self.assertFalse(self.panel._dispatch_capture())
        self.assertFalse(self.panel._busy)
        self.assertIn("実行されません", self.panel.status_var.get())

    def test_success_callback_status_is_not_overwritten(self):
        self.panel._callbacks["capture"] = lambda: self.panel.set_status("保存済み")
        self.assertTrue(self.panel._dispatch_capture())
        self.assertEqual(self.panel.status_var.get(), "保存済み")
        self.assertEqual(self.panel._status_label.options["foreground"], "")

    def test_reenable_preserves_busy_until_host_finishes(self):
        self.panel.set_busy(True)
        self.panel.set_enabled(False)
        self.panel.set_enabled(True)
        self.assertFalse(self.panel._dispatch_pulse("A"))
        self.assertEqual(self.panel._stop_widget.options["state"], "normal")
        self.panel.set_busy(False)
        self.assertTrue(self.panel._dispatch_pulse("A"))

    def test_restart_is_optional_and_invoked_once_without_arguments(self):
        self.assertEqual(self.calls, [])
        self.assertTrue(self.panel._dispatch_restart())
        self.assertEqual(self.calls, [("restart", ())])
        self.panel._callbacks["restart"] = None
        self.panel._refresh_enabled()
        self.assertEqual(self.widgets["restart"].options["state"], "disabled")
        self.assertFalse(self.panel._dispatch_restart())
        self.assertEqual(self.calls, [("restart", ())])

    def test_restart_button_creation_never_invokes_permission_or_restart(self):
        FakeWidget.created = []
        self.panel._operation_widgets = []
        self.panel.columnconfigure = lambda *args, **kwargs: None
        with mock.patch.multiple(panel_module.ttk, **{
                name: FakeWidget for name in (
                    "Frame", "Label", "Radiobutton", "Entry", "Checkbutton", "Button")}):
            self.panel._build_widgets()
        restart = next(widget for widget in FakeWidget.created
                       if widget.options.get("text") == "このPokeConを同じ設定で再起動")
        self.assertEqual(self.calls, [])
        self.assertIn((restart, "restart"), self.panel._operation_widgets)
        self.panel.set_busy(True)
        self.assertEqual(restart.options["state"], "disabled")
        self.assertFalse(restart.options["command"]())
        self.assertEqual(self.calls, [])
        self.panel.set_busy(False)
        self.assertTrue(restart.options["command"]())
        self.assertEqual(self.calls, [("restart", ())])

    def test_restart_parameter_preserves_all_existing_positional_callback_arguments(self):
        callbacks = [self.recorder(name) for name in ("pulse", "capture", "retest", "maximize", "stop")]
        restart = self.recorder("restart")
        variables = lambda **options: FakeVar(options.get("value"))
        with mock.patch.object(panel_module.ttk.Frame, "__init__", return_value=None), \
                mock.patch.object(panel_module.tk, "StringVar", side_effect=variables), \
                mock.patch.object(panel_module.tk, "BooleanVar", side_effect=variables), \
                mock.patch.object(CommandDebugPanel, "_build_widgets"), \
                mock.patch.object(CommandDebugPanel, "_refresh_enabled"):
            panel = CommandDebugPanel(None, *callbacks, on_restart=restart)
        self.assertEqual(self.calls, [])
        for name, callback in zip(("pulse", "capture", "retest", "maximize", "stop"), callbacks):
            self.assertIs(panel._callbacks[name], callback)
        self.assertIs(panel._callbacks["restart"], restart)

    def test_fresh_start_requires_explicit_host_support_even_with_a_callback(self):
        self.panel.set_fresh_start_supported(False)
        self.assertEqual(self.widgets["fresh_start"].options["state"], "disabled")
        self.assertFalse(self.panel._dispatch_fresh_start())
        self.assertEqual(self.calls, [])
        self.panel.set_fresh_start_supported(True)
        self.assertEqual(self.widgets["fresh_start"].options["state"], "normal")
        self.assertEqual(self.calls, [])
        self.assertTrue(self.panel._dispatch_fresh_start())
        self.assertEqual(self.calls, [("fresh_start", ())])
        self.panel.set_fresh_start_supported(False)
        self.assertFalse(self.panel._dispatch_fresh_start())
        self.assertEqual(self.calls, [("fresh_start", ())])
        self.assertEqual(self.widgets["restart"].options["state"], "normal")

    def test_fresh_start_missing_callback_and_busy_or_disabled_support_changes_never_send(self):
        self.panel._callbacks["fresh_start"] = None
        self.panel.set_fresh_start_supported(True)
        self.assertEqual(self.widgets["fresh_start"].options["state"], "disabled")
        self.assertFalse(self.panel._dispatch_fresh_start())
        self.panel._callbacks["fresh_start"] = self.recorder("fresh_start")
        self.panel.set_busy(True)
        self.panel.set_fresh_start_supported(True)
        self.assertEqual(self.widgets["fresh_start"].options["state"], "disabled")
        self.assertFalse(self.panel._dispatch_fresh_start())
        self.panel.set_busy(False)
        self.panel.set_enabled(False)
        self.panel.set_fresh_start_supported(True)
        self.assertFalse(self.panel._dispatch_fresh_start())
        self.assertEqual(self.calls, [])

    def test_fresh_start_callback_rejection_or_exception_does_not_retry(self):
        def rejected():
            self.calls.append(("reject", ()))
            return False
        self.panel._callbacks["fresh_start"] = rejected
        self.assertFalse(self.panel._dispatch_fresh_start())
        self.assertEqual(self.calls, [("reject", ())])
        self.assertFalse(self.panel._busy)
        def failed():
            self.calls.append(("error", ()))
            raise RuntimeError("開始中止")
        self.panel._callbacks["fresh_start"] = failed
        self.assertFalse(self.panel._dispatch_fresh_start())
        self.assertEqual(self.calls, [("reject", ()), ("error", ())])
        self.assertIn("開始中止", self.panel.status_var.get())

    def test_game_specific_fresh_start_is_not_a_permanent_button(self):
        FakeWidget.created = []
        self.panel._operation_widgets = []
        self.panel.columnconfigure = lambda *args, **kwargs: None
        self.panel._fresh_start_supported = False
        with mock.patch.multiple(panel_module.ttk, **{
                name: FakeWidget for name in (
                    "Frame", "Label", "Radiobutton", "Entry", "Checkbutton", "Button")}):
            self.panel._build_widgets()
        buttons = {widget.options.get("text"): widget for widget in FakeWidget.created
                   if "command" in widget.options}
        self.assertNotIn("タイトル→はじめから実行", buttons)
        restart = buttons["このPokeConを同じ設定で再起動"]
        self.assertEqual(restart.parent.grid_options["row"], 2)
        self.assertEqual(restart.pack_options["side"], "left")
        self.assertEqual(self.panel._status_label.grid_options["row"], 3)
        self.assertEqual(self.calls, [])
        self.panel._refresh_enabled()
        self.panel.set_fresh_start_supported(True)
        self.assertEqual(self.calls, [])
        # The callback remains available for the Commands dropdown.
        self.assertTrue(self.panel._dispatch_fresh_start())
        self.assertEqual(self.calls, [("fresh_start", ())])

    def test_fresh_start_is_optional_and_preserves_restart_positional_contract(self):
        names = ("pulse", "capture", "retest", "maximize", "stop", "restart")
        callbacks = [self.recorder(name) for name in names]
        fresh = self.recorder("fresh_start")
        variables = lambda **options: FakeVar(options.get("value"))
        with mock.patch.object(panel_module.ttk.Frame, "__init__", return_value=None), \
                mock.patch.object(panel_module.tk, "StringVar", side_effect=variables), \
                mock.patch.object(panel_module.tk, "BooleanVar", side_effect=variables), \
                mock.patch.object(CommandDebugPanel, "_build_widgets"), \
                mock.patch.object(CommandDebugPanel, "_refresh_enabled"):
            panel = CommandDebugPanel(None, *callbacks, on_fresh_start=fresh)
            legacy = CommandDebugPanel(None, *callbacks)
        for name, callback in zip(names, callbacks):
            self.assertIs(panel._callbacks[name], callback)
            self.assertIs(legacy._callbacks[name], callback)
        self.assertIs(panel._callbacks["fresh_start"], fresh)
        self.assertIsNone(legacy._callbacks["fresh_start"])
        self.assertFalse(panel._fresh_start_supported)
        self.assertFalse(legacy._fresh_start_supported)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
