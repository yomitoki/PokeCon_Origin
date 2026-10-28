"""Recording settings regressions without starting PokeCon or its devices."""

import ast
import configparser
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import types
import unittest
from unittest import mock


SERIAL_CONTROLLER = Path(__file__).resolve().parents[1] / "SerialController"
if str(SERIAL_CONTROLLER) not in sys.path:
    sys.path.insert(0, str(SERIAL_CONTROLLER))

from InputSetData import (
    COMMAND_INPUT_SET_VARIABLES,
    snapshot_values_with_defaults,
    strip_commands_from_snapshot,
)
from Settings import GuiSettings, create_settings_parser


class Variable:
    def __init__(self, value, on_write=None):
        self.value = value
        self.on_write = on_write
        self.writes = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.writes.append(value)
        if self.on_write is not None:
            self.on_write()


def load_window_methods():
    """Execute actual methods without importing Window's hardware modules."""
    path = SERIAL_CONTROLLER / "Window.py"
    source = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    app = next(node for node in source.body
               if isinstance(node, ast.ClassDef)
               and node.name == "PokeControllerApp")
    names = {
        "_input_set_recording_data",
        "_legacy_recording_preset_data",
        "_effective_record_output_dir",
        "_apply_record_output_dir",
        "_record_output_dir_changed",
        "choose_record_output_dir",
        "clear_record_output_dir",
        "_commit_record_output_dir",
        "_apply_all_tabs_snapshot",
        "load_recording_preset",
    }
    app.body = [node for node in app.body
                if isinstance(node, ast.FunctionDef) and node.name in names]
    app.bases = []
    namespace = {
        "configparser": configparser,
        "copy": copy,
        "os": os,
        "tk": tk,
        "tkmsg": types.SimpleNamespace(showerror=mock.Mock()),
        "COMMAND_INPUT_SET_VARIABLES": COMMAND_INPUT_SET_VARIABLES,
        "COMMAND_MONITOR_RETENTION_SMART": "smart",
        "snapshot_values_with_defaults": snapshot_values_with_defaults,
        "strip_commands_from_snapshot": strip_commands_from_snapshot,
        "normalize_recovery_favorites": lambda value: value,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=[app], type_ignores=[])), str(path), "exec"), namespace)
    return namespace["PokeControllerApp"], namespace["tkmsg"]


class RecordingSettingsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_type, cls.messages = load_window_methods()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.input_sets_path = self.folder / "input_sets.json"
        self.settings_path = self.folder / "settings.ini"
        self.initial_data = {
            "input_sets": {
                "loaded": {
                    "camera": {"device_path": "preserve-camera"},
                    "recording": {
                        "output_dir": "old-top",
                        "mode": "Template",
                        "storage_destination": "youtube",
                    },
                    "all_tabs": {
                        "recording": {
                            "output_dir": "old-nested",
                            "youtube_channel_profile": "preserve-channel",
                        },
                        "values": {
                            "record_output_dir": "old-values",
                            "audio_gain": 73,
                        },
                    },
                },
                "other": {"recording": {"output_dir": "other-folder"}},
            },
            "combined_sets": {"startup": {
                "input_set": "loaded", "recording_set": "separate-preset"}},
            "startup": {"default": "startup"},
        }
        self.input_sets_path.write_text(
            json.dumps(self.initial_data), encoding="utf-8")
        self.settings_path.write_text(
            "[Recording]\noutput_dir = old-profile\nmode = Manual\n"
            "[General Setting]\nfps = 60\n", encoding="utf-8")
        settings = GuiSettings.__new__(GuiSettings)
        settings.SETTING_PATH = str(self.settings_path)
        settings.setting = create_settings_parser()
        settings.setting.read_dict({
            "Recording": {"output_dir": "old-memory"},
            "General Setting": {"fps": "5"},
        })
        settings.record_output_dir = "old-memory"
        self.app = self.app_type()
        self.app.root = object()
        self.app.settings = settings
        self.app.recorder = types.SimpleNamespace(active=False)
        self.app.record_armed = False
        self.app._active_input_set_name = "loaded"
        self.app.record_output_dir = Variable(
            "old-ui", self.app._record_output_dir_changed)
        self.app._read_input_sets = lambda: json.loads(
            self.input_sets_path.read_text(encoding="utf-8"))
        self.app._write_input_sets = mock.Mock(side_effect=lambda data:
            self.input_sets_path.write_text(json.dumps(data), encoding="utf-8"))
        self.messages.showerror.reset_mock()

    def assert_persisted_path(self, expected):
        data = self.app._read_input_sets()
        item = data["input_sets"]["loaded"]
        self.assertEqual(item["recording"]["output_dir"], expected)
        self.assertEqual(item["all_tabs"]["recording"]["output_dir"], expected)
        self.assertEqual(
            item["all_tabs"]["values"]["record_output_dir"], expected)
        parser = create_settings_parser()
        parser.read(self.settings_path, encoding="utf-8")
        self.assertEqual(parser["Recording"]["output_dir"], expected)
        self.assertEqual(parser["General Setting"]["fps"], "60")
        self.assertEqual(parser["Recording"]["mode"], "Manual")
        self.assertEqual(
            data["input_sets"]["other"], self.initial_data["input_sets"]["other"])
        self.assertEqual(data["combined_sets"], self.initial_data["combined_sets"])
        self.assertEqual(item["camera"], {"device_path": "preserve-camera"})
        self.assertEqual(item["recording"]["storage_destination"], "youtube")
        self.assertEqual(
            item["all_tabs"]["recording"]["youtube_channel_profile"],
            "preserve-channel")
        self.assertEqual(item["all_tabs"]["values"]["audio_gain"], 73)
        self.assertEqual(self.app.settings.record_output_dir, expected)
        self.messages.showerror.assert_not_called()

    def test_picker_commits_all_saved_copies_and_preserves_other_settings(self):
        destination = self.folder / "録画 100% 完了" / "new"
        with mock.patch("tkinter.filedialog.askdirectory",
                        return_value=str(destination)) as picker:
            self.app.choose_record_output_dir()
        self.assert_persisted_path(os.path.abspath(destination))
        self.assertIs(picker.call_args.kwargs["parent"], self.app.root)
        self.assertTrue(os.path.isdir(picker.call_args.kwargs["initialdir"]))
        self.assertEqual(
            self.app.recorder.output_dir, os.path.abspath(destination))

    def test_picker_cancel_preserves_current_and_persisted_paths(self):
        with mock.patch("tkinter.filedialog.askdirectory", return_value=""):
            self.app.choose_record_output_dir()
        self.assertEqual(self.app.record_output_dir.get(), "old-ui")
        self.assertEqual(self.app._read_input_sets(), self.initial_data)
        self.app._write_input_sets.assert_not_called()

    def test_picker_uses_existing_parent_for_missing_saved_destination(self):
        self.app.record_output_dir.set(str(self.folder / "gone" / "nested"))
        with mock.patch("tkinter.filedialog.askdirectory",
                        return_value="") as picker:
            self.app.choose_record_output_dir()
        self.assertEqual(picker.call_args.kwargs["initialdir"], str(self.folder))

    def test_picker_focusout_does_not_commit_pending_text_when_cancelled(self):
        pending = str(self.folder / "typed-but-not-confirmed")
        self.app.record_output_dir.set(pending)
        before_input_sets = self.input_sets_path.read_bytes()
        before_profile = self.settings_path.read_bytes()
        focusout_results = []

        def cancel_picker(**kwargs):
            focusout_results.append(
                self.app._commit_record_output_dir(object()))
            return ""

        with mock.patch("tkinter.filedialog.askdirectory",
                        side_effect=cancel_picker):
            self.app.choose_record_output_dir()
        self.assertEqual(focusout_results, [False])
        self.assertEqual(self.app.record_output_dir.get(), pending)
        self.assertEqual(self.input_sets_path.read_bytes(), before_input_sets)
        self.assertEqual(self.settings_path.read_bytes(), before_profile)
        self.app._write_input_sets.assert_not_called()
        self.assertFalse(self.app._record_output_dir_picking)

    def test_clear_persists_default_destination(self):
        self.app.clear_record_output_dir()
        self.assert_persisted_path("")
        self.assertEqual(self.app.recorder.output_dir, "Recordings")

    def test_manual_commit_strips_space_and_avoids_duplicate_disk_writes(self):
        destination = str(self.folder / "new folder")
        self.app.record_output_dir.set("  " + destination + "  ")
        self.assertTrue(self.app._commit_record_output_dir(object()))
        self.assertTrue(self.app._commit_record_output_dir(object()))
        self.app._write_input_sets.assert_called_once()
        self.assert_persisted_path(destination)

    def test_programmatic_path_trace_does_not_save_loaded_input_set(self):
        destination = str(self.folder / "other-set-folder")
        self.app.record_output_dir.set(destination)
        self.assertEqual(self.app.recorder.output_dir, destination)
        self.assertEqual(self.app._read_input_sets(), self.initial_data)
        self.app._write_input_sets.assert_not_called()
        self.assertEqual(self.app.settings.record_output_dir, "old-memory")

    def test_suspended_programmatic_restore_cannot_commit(self):
        self.app._record_output_reload_suspended = True
        self.app.record_output_dir.set(str(self.folder / "restoring"))
        self.assertFalse(self.app._commit_record_output_dir())
        self.app._write_input_sets.assert_not_called()
        self.assertEqual(self.app.settings.record_output_dir, "old-memory")

    def test_profile_only_session_can_commit_without_input_set(self):
        self.app._active_input_set_name = ""
        destination = str(self.folder / "unassigned")
        self.app.record_output_dir.set(destination)
        self.assertTrue(self.app._commit_record_output_dir())
        self.app._write_input_sets.assert_not_called()
        parser = create_settings_parser()
        parser.read(self.settings_path, encoding="utf-8")
        self.assertEqual(parser["Recording"]["output_dir"], destination)

    def test_existing_file_is_rejected_without_saving(self):
        self.app.record_output_dir.set(str(self.settings_path))
        self.assertFalse(self.app._commit_record_output_dir())
        self.app._write_input_sets.assert_not_called()
        self.messages.showerror.assert_called_once()
        self.assertEqual(self.app.settings.record_output_dir, "old-memory")

    def test_write_failure_reports_error_and_allows_retry(self):
        destination = str(self.folder / "retry")
        self.app.record_output_dir.set(destination)
        save = self.app._write_input_sets
        with mock.patch.object(self.app, "_write_input_sets",
                               side_effect=OSError("disk unavailable")):
            self.assertFalse(self.app._commit_record_output_dir())
        self.messages.showerror.assert_called_once()
        self.messages.showerror.reset_mock()
        self.assertTrue(self.app._commit_record_output_dir())
        save.assert_called_once()
        self.assert_persisted_path(destination)

    def test_corrupt_profile_reports_error_and_preserves_the_file(self):
        corrupted = "not an INI section\noutput_dir = broken\n"
        self.settings_path.write_text(corrupted, encoding="utf-8")
        self.app.record_output_dir.set(str(self.folder / "new-folder"))
        self.assertFalse(self.app._commit_record_output_dir())
        self.messages.showerror.assert_called_once()
        self.assertEqual(
            self.settings_path.read_text(encoding="utf-8"), corrupted)
        self.assertEqual(self.app.settings.record_output_dir, "old-memory")
        self.assertFalse(self.app._record_output_dir_committing)

    def test_error_popup_focusout_reentry_is_blocked_and_retry_succeeds(self):
        self.app.record_output_dir.set(str(self.settings_path))
        reentry_results = []
        with mock.patch.object(
                self.messages, "showerror",
                side_effect=lambda *args, **kwargs: reentry_results.append(
                    self.app._commit_record_output_dir(object()))) as popup:
            self.assertFalse(self.app._commit_record_output_dir(object()))
        popup.assert_called_once()
        self.assertEqual(reentry_results, [False])
        self.assertFalse(self.app._record_output_dir_committing)
        self.app._write_input_sets.assert_not_called()
        destination = str(self.folder / "corrected-folder")
        self.app.record_output_dir.set(destination)
        self.assertTrue(self.app._commit_record_output_dir(object()))
        self.assertFalse(self.app._record_output_dir_committing)
        self.assert_persisted_path(destination)

    def prepare_legacy_recording_preset(self):
        data = self.app._read_input_sets()
        del data["input_sets"]["loaded"]["all_tabs"]
        self.input_sets_path.write_text(json.dumps(data), encoding="utf-8")
        preset = {
            "output_dir": "shared-preset-folder",
            "mode": "Template",
            "storage_destination": "youtube",
            "youtube_channel_profile": "shared-channel",
            "trigger_rules": [{"path": "unchanged-template.png", "threshold": 0.85}],
        }
        self.app.recording_preset_name = Variable("shared")
        self.app._read_recording_presets = lambda: {"shared": preset}
        self.app._apply_recording_preset_data = mock.Mock(
            side_effect=lambda recording, **kwargs:
                self.app.record_output_dir.set(recording["output_dir"]))
        return preset

    def assert_legacy_folder_restore(self, expected, preset):
        item = self.app._read_input_sets()["input_sets"]["loaded"]
        self.assertEqual(item["record_output_dir_override"], expected)
        self.assertEqual(item["recording"]["output_dir"], expected)
        self.assertNotIn("all_tabs", item)
        saved_preset = copy.deepcopy(preset)
        self.app.record_output_dir.set("intermediate-combined-snapshot")
        self.app.load_recording_preset(input_item=item)
        applied = self.app._apply_recording_preset_data.call_args.args[0]
        expected_data = copy.deepcopy(preset)
        expected_data["output_dir"] = expected
        self.assertEqual(applied, expected_data)
        self.assertEqual(self.app.record_output_dir.get(), expected)
        self.assertEqual(preset, saved_preset)
        self.assertIsNot(applied["trigger_rules"], preset["trigger_rules"])
        self.assertEqual(
            self.app._legacy_recording_preset_data(item, preset), expected_data)
        self.messages.showerror.assert_not_called()

    def test_legacy_folder_choice_survives_linked_shared_preset_restore(self):
        preset = self.prepare_legacy_recording_preset()
        destination = os.path.abspath(self.folder / "legacy-chosen")
        with mock.patch("tkinter.filedialog.askdirectory",
                        return_value=destination):
            self.app.choose_record_output_dir()
        self.assert_legacy_folder_restore(destination, preset)

    def test_legacy_clear_survives_linked_shared_preset_restore(self):
        preset = self.prepare_legacy_recording_preset()
        self.app.clear_record_output_dir()
        self.assert_legacy_folder_restore("", preset)

    def test_explicit_recording_preset_load_uses_its_own_folder(self):
        preset = self.prepare_legacy_recording_preset()
        destination = str(self.folder / "legacy-override")
        self.app.record_output_dir.set(destination)
        self.assertTrue(self.app._commit_record_output_dir())
        self.app.load_recording_preset()
        self.assertEqual(
            self.app.record_output_dir.get(), preset["output_dir"])
        applied = self.app._apply_recording_preset_data.call_args.args[0]
        self.assertEqual(applied, preset)
        self.assertIsNot(applied, preset)
        item = self.app._read_input_sets()["input_sets"]["loaded"]
        self.assertEqual(item["record_output_dir_override"], destination)

    def test_legacy_preset_without_explicit_override_keeps_shared_path(self):
        preset = self.prepare_legacy_recording_preset()
        item = self.app._read_input_sets()["input_sets"]["loaded"]
        self.app.load_recording_preset(input_item=item)
        self.assertEqual(self.app.record_output_dir.get(), preset["output_dir"])
        self.app._write_input_sets.assert_not_called()

    def prepare_snapshot_runtime(self):
        app = self.app
        app._resource_main_open_downgraded = False
        app.object_detection_assist_window = None
        app.shortcut_command_class = {}
        app.shortcut_command_name = {}
        app.panel_slots = {}
        app.command_watch_variables = []
        app._commands_assist_evaluator = types.SimpleNamespace(reset=mock.Mock())
        app.command_nb = types.SimpleNamespace(tabs=lambda: ())
        app.mcu_cb = {"values": ()}
        app.pc_gamepad_cb = {"values": ()}
        for name in (
                "camera_feature_limited", "commands_assist_enabled",
                "commands_assist_recovery_command",
                "command_recovery_auto_pause_disabled", "is_use_keyboard",
                "is_use_left_stick_mouse", "is_use_right_stick_mouse",
                "is_record_Pro_Controller", "is_use_Pro_Controller",
                "pc_gamepad_input_enabled", "pc_gamepad",
                "py_name", "sample_py_name", "mcu_name"):
            setattr(app, name, Variable(False))
        for name in (
                "_apply_camera_feature_limited", "_cache_resource_control_config",
                "_refresh_resource_control_status",
                "_refresh_command_recovery_window_favorites",
                "_refresh_commands_assist_rule_list", "_refresh_command_start_status",
                "_refresh_inline_command_run_panel", "_apply_quick_actions_snapshot",
                "_refresh_preview_priority_status", "apply_panel_assignment",
                "switchStdoutDestination", "mode_change_notification",
                "toggle_image_analysis_assist", "mode_change_show_value",
                "mode_change_show_guide", "change_buttons_position",
                "reset_command_watch", "applyFilterPy", "applyFilterSamplePy",
                "applyFilterMcu", "refresh_pc_gamepads"):
            setattr(app, name, mock.Mock())
        app._apply_recording_preset_data = mock.Mock(side_effect=lambda recording:
            app.record_output_dir.set(recording["output_dir"]))
        return app

    def test_authoritative_recording_wins_without_transient_old_path(self):
        app = self.prepare_snapshot_runtime()
        app._apply_all_tabs_snapshot({
            "values": {"record_output_dir": "old-values"},
            "recording": {"output_dir": "authoritative-nested"},
        }, runtime=False)
        self.assertEqual(app.record_output_dir.get(), "authoritative-nested")
        self.assertEqual(
            app.record_output_dir.writes, ["authoritative-nested"])
        app._write_input_sets.assert_not_called()

    def test_top_level_recording_survives_old_all_tabs_recording_and_values(self):
        app = self.prepare_snapshot_runtime()
        item = {
            "recording": {"output_dir": "authoritative-top"},
            "all_tabs": {
                "recording": {"output_dir": "old-nested"},
                "values": {"record_output_dir": "old-values"},
            },
        }
        app._apply_recording_preset_data(app._input_set_recording_data(item))
        app._apply_all_tabs_snapshot(
            item["all_tabs"], runtime=False, apply_recording=False)
        self.assertEqual(app.record_output_dir.get(), "authoritative-top")
        self.assertEqual(app.record_output_dir.writes, ["authoritative-top"])

    def test_delayed_command_restore_preserves_committed_path_and_policy(self):
        app = self.prepare_snapshot_runtime()
        destination = str(self.folder / "chosen-after-startup")
        app.record_output_dir.set(destination)
        app.record_min_free_gb = Variable(8)
        app.record_mode = Variable("Manual")
        app.record_monitor_retention_mode = Variable("keep_all")
        self.assertTrue(app._commit_record_output_dir())
        with mock.patch.object(self.app_type, "_command_debug_wait_for_release",
                               return_value=False, create=True):
            app._apply_all_tabs_snapshot({
                "recording": {"output_dir": "old-nested"},
                "values": {
                    "record_output_dir": "old-values",
                    "record_min_free_gb": 5,
                    "record_mode": "Template",
                    "record_monitor_retention_mode": "smart",
                },
            }, runtime=True, apply_recording=False)
        self.assertEqual(app.record_output_dir.get(), destination)
        self.assertEqual(app.record_output_dir.writes, [destination])
        self.assertEqual(app.record_min_free_gb.get(), 8)
        self.assertEqual(app.record_mode.get(), "Manual")
        self.assertEqual(app.record_monitor_retention_mode.get(), "keep_all")
        self.assert_persisted_path(destination)
        app._apply_recording_preset_data.assert_not_called()

    def test_legacy_snapshot_values_restore_when_no_recording_object_exists(self):
        app = self.prepare_snapshot_runtime()
        app._apply_all_tabs_snapshot({
            "values": {"record_output_dir": "legacy-path"},
        }, runtime=False)
        self.assertEqual(app.record_output_dir.get(), "legacy-path")
        app._apply_recording_preset_data.assert_not_called()


if __name__ == "__main__":
    unittest.main()
