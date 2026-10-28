import configparser
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
from unittest import mock


SERIAL_CONTROLLER = Path(__file__).resolve().parents[1] / "SerialController"
if str(SERIAL_CONTROLLER) not in sys.path:
    sys.path.insert(0, str(SERIAL_CONTROLLER))

from KeyConfig import PokeKeycon
from Settings import GuiSettings, create_settings_parser


class SettingsPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "settings.ini"
        self.interpreter = tk.Tcl()
        for name in ("IntVar", "StringVar", "BooleanVar"):
            variable = getattr(tk, name)
            patcher = mock.patch(
                "Settings.tk." + name,
                side_effect=lambda _variable=variable, **kwargs: _variable(
                    master=self.interpreter, **kwargs))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.settings_class = type(
            "TemporarySettings", (GuiSettings,), {"SETTING_PATH": str(self.path)})

    def _key_config(self):
        dialog = PokeKeycon.__new__(PokeKeycon)
        dialog.SETTING_PATH = str(self.path)
        dialog.setting = create_settings_parser()
        dialog.setting.read(str(self.path), encoding="utf-8")
        dialog._logger = mock.Mock()
        dialog.listener = None
        return dialog

    def test_percent_paths_and_user_text_round_trip(self):
        settings = self.settings_class()
        values = {
            "record_output_dir": r"D:\録画\100% 完了",
            "record_template_path": r"D:\画像\50%%_match.png",
            "operation_capture_output_dir": r"D:\%USERPROFILE%\操作",
            "operation_capture_last_session": r"D:\操作\%(camera_id)s",
            "window_title": "Game 100% - %(window_process)s",
            "record_trigger_rules": '[{"template": "99%一致.png"}]',
            "analysis_rules": '[{"text": "50%% と 100%"}]',
            "commands_assist_rules": '[{"message": "%(command)s"}]',
        }
        for name, value in values.items():
            setattr(settings, name, value)
        settings.command_name_dict["1"].set("100%クリア")
        settings.save()
        restored = self.settings_class()
        for name, expected in values.items():
            with self.subTest(setting=name):
                self.assertEqual(getattr(restored, name), expected)
        self.assertEqual(restored.command_name_dict["1"].get(), "100%クリア")

    def test_existing_escaped_analysis_rules_still_load(self):
        self.settings_class()
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(str(self.path), encoding="utf-8")
        parser["Analysis"]["rules"] = '[{"text": "100%%完了"}]'
        with self.path.open("w", encoding="utf-8") as stream:
            parser.write(stream)
        settings = self.settings_class()
        self.assertEqual(settings.analysis_rules, '[{"text": "100%完了"}]')
        settings.save()
        self.assertEqual(
            self.settings_class().analysis_rules, '[{"text": "100%完了"}]')

    def test_existing_escaped_paths_keep_legacy_reader_compatibility(self):
        self.settings_class()
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(str(self.path), encoding="utf-8")
        parser["Recording"]["output_dir"] = r"D:\録画\100%%完了"
        parser["Operation Capture"]["output_dir"] = r"D:\操作\50%%%%"
        with self.path.open("w", encoding="utf-8") as stream:
            parser.write(stream)
        settings = self.settings_class()
        self.assertEqual(settings.record_output_dir, r"D:\録画\100%完了")
        self.assertEqual(settings.operation_capture_output_dir, r"D:\操作\50%%")
        for _ in range(2):
            settings.save()
            settings = self.settings_class()
        parser.read(str(self.path), encoding="utf-8")
        self.assertEqual(parser["Recording"]["output_dir"], r"D:\録画\100%完了")
        self.assertEqual(parser["Operation Capture"]["output_dir"], r"D:\操作\50%%")

    def test_unescaped_percent_in_existing_path_is_literal(self):
        self.settings_class()
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read(str(self.path), encoding="utf-8")
        parser["Recording"]["output_dir"] = r"D:\録画\100%完了"
        parser["General Setting"]["window_title"] = "%(com_port)s"
        with self.path.open("w", encoding="utf-8") as stream:
            parser.write(stream)
        settings = self.settings_class()
        self.assertEqual(settings.record_output_dir, r"D:\録画\100%完了")
        self.assertEqual(settings.window_title, "%(com_port)s")

    def test_first_run_creates_missing_profile_directories(self):
        path = Path(self.folder.name) / "profiles" / "new profile" / "settings.ini"
        self.settings_class.SETTING_PATH = str(path)
        settings = self.settings_class()
        self.assertTrue(path.is_file())
        self.assertEqual(settings.record_mode, "Manual")

    def test_save_accepts_filename_in_current_directory(self):
        settings = self.settings_class()
        settings.record_output_dir = r"D:\録画"
        previous_cwd = os.getcwd()
        try:
            os.chdir(self.folder.name)
            settings.save("export.ini")
        finally:
            os.chdir(previous_cwd)
        exported = Path(self.folder.name) / "export.ini"
        self.assertTrue(exported.is_file())

    def test_failed_write_keeps_previous_file_and_removes_temporary_file(self):
        settings = self.settings_class()
        before = self.path.read_bytes()
        settings.record_output_dir = r"D:\new"

        def fail_after_partial_write(stream):
            stream.write("[General Setting]\ncamera_id = ")
            raise OSError("disk full")

        with mock.patch.object(
                settings.setting, "write", side_effect=fail_after_partial_write):
            with self.assertRaisesRegex(OSError, "disk full"):
                settings.save()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(Path(self.folder.name).iterdir()), [self.path])

    def test_failed_replace_keeps_previous_file_and_removes_temporary_file(self):
        settings = self.settings_class()
        before = self.path.read_bytes()
        with mock.patch("Settings.os.replace", side_effect=PermissionError("busy")):
            with self.assertRaisesRegex(PermissionError, "busy"):
                settings.save()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(Path(self.folder.name).iterdir()), [self.path])

    def test_invalid_audio_numbers_reach_existing_sanitizer(self):
        self.settings_class()
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(str(self.path), encoding="utf-8")
        parser["Audio"].update({
            "gain": "bad gain", "target_dbfs": "bad target",
            "max_auto_gain": "", "limiter_ceiling_dbfs": "bad ceiling",
        })
        with self.path.open("w", encoding="utf-8") as stream:
            parser.write(stream)
        settings = self.settings_class()
        self.assertEqual(settings.audio_gain, "100")
        self.assertEqual(settings.audio_target_dbfs, -6.0)
        self.assertEqual(settings.audio_max_auto_gain, 800)
        self.assertEqual(settings.audio_limiter_ceiling_dbfs, -1.0)

    def test_main_save_preserves_keys_applied_after_startup(self):
        settings = self.settings_class()
        dialog = self._key_config()
        dialog.setting["KeyMap-Button"]["Button.A"] = "z"
        dialog.setting["KeyMap-Hat"]["Hat.TOP"] = "Key.page_up"
        dialog.apply_setting()
        settings.record_output_dir = r"D:\new folder"
        settings.save()
        restored = self.settings_class()
        self.assertEqual(restored.setting["KeyMap-Button"]["Button.A"], "z")
        self.assertEqual(restored.setting["KeyMap-Hat"]["Hat.TOP"], "Key.page_up")
        self.assertEqual(restored.record_output_dir, r"D:\new folder")

    def test_key_apply_preserves_settings_changed_after_dialog_opened(self):
        settings = self.settings_class()
        dialog = self._key_config()
        settings.record_output_dir = r"D:\100%録画"
        settings.window_title = "New capture window"
        settings.save()
        dialog.setting["KeyMap-Button"]["Button.A"] = "%"
        dialog.apply_setting()
        restored = self.settings_class()
        self.assertEqual(restored.record_output_dir, r"D:\100%録画")
        self.assertEqual(restored.window_title, "New capture window")
        # The keyboard controller uses the standard INI reader.
        legacy = configparser.ConfigParser()
        legacy.optionxform = str
        legacy.read(str(self.path), encoding="utf-8")
        self.assertEqual(legacy["KeyMap-Button"]["Button.A"], "%")

    def test_key_save_config_preserves_settings_changed_after_dialog_opened(self):
        settings = self.settings_class()
        dialog = self._key_config()
        for name in ("ZL", "L", "LCLICK", "ZR", "R", "RCLICK", "MINUS",
                     "CAPTURE", "A", "B", "X", "Y", "PLUS", "HOME"):
            setattr(dialog, name, tk.StringVar(
                value=dialog.setting["KeyMap-Button"]["Button." + name]))
        for name, key in (("HAT_UP", "TOP"), ("HAT_RIGHT", "RIGHT"),
                          ("HAT_DOWN", "BTM"), ("HAT_LEFT", "LEFT")):
            setattr(dialog, name, tk.StringVar(
                value=dialog.setting["KeyMap-Hat"]["Hat." + key]))
        settings.record_output_dir = r"D:\new folder"
        settings.save()
        dialog.A.set("z")
        dialog.save_config()
        restored = self.settings_class()
        self.assertEqual(restored.record_output_dir, r"D:\new folder")
        self.assertEqual(restored.setting["KeyMap-Button"]["Button.A"], "z")

    def test_record_folder_commit_preserves_current_disk_settings(self):
        settings = self.settings_class()
        other = self.settings_class()
        other.window_title = "Newer capture title"
        other.analysis_rules = '[{"text": "new 100% rule"}]'
        other.save()
        dialog = self._key_config()
        dialog.setting["KeyMap-Button"]["Button.A"] = "z"
        dialog.apply_setting()
        settings.save_record_output_dir(r"D:\100%録画")
        self.assertEqual(settings.record_output_dir, r"D:\100%録画")
        self.assertEqual(
            settings.setting["Recording"]["output_dir"], r"D:\100%録画")
        restored = self.settings_class()
        self.assertEqual(restored.record_output_dir, r"D:\100%録画")
        self.assertEqual(restored.window_title, "Newer capture title")
        self.assertEqual(restored.analysis_rules, '[{"text": "new 100% rule"}]')
        self.assertEqual(restored.setting["KeyMap-Button"]["Button.A"], "z")

    def test_failed_record_folder_commit_preserves_saved_and_runtime_folder(self):
        settings = self.settings_class()
        settings.record_output_dir = r"D:\original"
        settings.save()
        before = self.path.read_bytes()
        with mock.patch("Settings.os.replace", side_effect=PermissionError("busy")):
            with self.assertRaisesRegex(PermissionError, "busy"):
                settings.save_record_output_dir(r"D:\new")
        self.assertEqual(settings.record_output_dir, r"D:\original")
        self.assertEqual(
            settings.setting["Recording"]["output_dir"], r"D:\original")
        self.assertEqual(self.path.read_bytes(), before)

    def test_record_folder_can_be_cleared_and_saved_again(self):
        settings = self.settings_class()
        settings.save_record_output_dir(r"D:\録画")
        settings.save_record_output_dir("")
        settings.save()
        self.assertEqual(self.settings_class().record_output_dir, "")

    def test_unreadable_current_settings_are_not_replaced_by_partial_settings(self):
        settings = self.settings_class()
        before = self.path.read_bytes()
        with mock.patch("builtins.open", side_effect=PermissionError("unreadable")):
            with self.assertRaisesRegex(PermissionError, "unreadable"):
                settings.save_record_output_dir(r"D:\new")
        self.assertEqual(settings.record_output_dir, "")
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
