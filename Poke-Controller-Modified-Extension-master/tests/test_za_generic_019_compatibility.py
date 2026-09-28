#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for the ZA_story stock-0.1.9 compatibility layer."""

import ast
import os
import sys
import unittest


REPOSITORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERIAL_CONTROLLER = os.path.join(REPOSITORY, "SerialController")
if SERIAL_CONTROLLER not in sys.path:
    sys.path.insert(0, SERIAL_CONTROLLER)

from LocalFunction.ImageDetection import read_command_frame  # noqa: E402
from LocalFunction.CommandStartSelector import (  # noqa: E402
    PORTABLE_START_CANCEL,
    apply_story_start,
    discover_story_locations,
    show_portable_start_dialog,
)


class _Command:
    def __init__(self, camera):
        self.camera = camera


class _Stock019Camera:
    def __init__(self, frame):
        self.frame = frame
        self.calls = 0

    def readFrame(self):
        self.calls += 1
        return self.frame


class _ExtendedCamera:
    def __init__(self, frame):
        self.frame = frame
        self.timeouts = []

    def readFreshFrame(self, timeout=None):
        self.timeouts.append(timeout)
        return self.frame


class _NoArgumentFreshCamera:
    def __init__(self, frame):
        self.frame = frame
        self.calls = 0

    def readFreshFrame(self):
        self.calls += 1
        return self.frame


class _PortableZaStory:
    COMMAND_STEP_LABELS = {
        "MAIN_ZA_BATTLE_INFI": "ZA_battle_infi_main（単独実行モード）",
    }
    COMMAND_STEP_DESCRIPTIONS = {
        "MAIN_ZA_BATTLE_INFI": "ZAバトル周回を単独で実行します。",
    }

    def __init__(self):
        self.STATE_MAIN_FUNCTION = {
            "MAIN_STATE_INIT": object(),
            "MAIN_0_START": object(),
            "MAIN_3_F_LANK": object(),
            "MAIN_ZA_BATTLE_INFI": object(),
        }
        self.STATE_3_STORY_FUNCTION = {
            "3_STORY_CANARI_6": object(),
            "3_STORY_CANARI_7": object(),
        }
        self.STATE_ZA_INFI_MAIN_FUNCTION = {
            "ZA_INFI_MAIN_START": object(),
        }
        self.main_current_state = "MAIN_STATE_INIT"
        self.main_current_state_init = ""
        self._3_story_current_state_init = "3_STORY_END"


class ZaGeneric019CompatibilityTests(unittest.TestCase):
    def test_stock_019_camera_uses_read_frame(self):
        frame = object()
        camera = _Stock019Camera(frame)

        self.assertIs(read_command_frame(_Command(camera)), frame)
        self.assertEqual(camera.calls, 1)

    def test_extended_camera_prefers_fresh_frame(self):
        frame = object()
        camera = _ExtendedCamera(frame)

        self.assertIs(
            read_command_frame(_Command(camera), timeout=0.25), frame)
        self.assertEqual(camera.timeouts, [0.25])

    def test_fresh_frame_without_timeout_argument_is_supported(self):
        frame = object()
        camera = _NoArgumentFreshCamera(frame)

        self.assertIs(read_command_frame(_Command(camera)), frame)
        self.assertEqual(camera.calls, 1)

    def test_za_story_keeps_core_compatibility_inside_copy_scope(self):
        source_path = os.path.join(
            SERIAL_CONTROLLER, "Commands", "PythonCommands", "ZA",
            "ZA_story", "ZA_story.py")
        with open(source_path, encoding="utf-8") as stream:
            tree = ast.parse(stream.read(), source_path)

        base = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ZA_story_Base")
        methods = {
            node.name for node in base.body if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("_read_camera_frame", methods)
        self.assertIn("show_output", methods)

        imported = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        self.assertFalse(any(
            name == "ThreadCancellation" or
            name.endswith(".ThreadCancellation")
            for name in imported))

    def test_za_story_embeds_selector_fallback_when_helper_was_not_copied(self):
        source_path = os.path.join(
            SERIAL_CONTROLLER, "Commands", "PythonCommands", "ZA",
            "ZA_story", "ZA_story.py")
        with open(source_path, encoding="utf-8") as stream:
            tree = ast.parse(stream.read(), source_path)
        command_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ZA_story")
        methods = {
            node.name: node for node in command_class.body
            if isinstance(node, ast.FunctionDef)
        }
        namespace = {}
        for name in (
                "_portable_start_apply_without_helper",
                "_portable_start_records_without_helper",
                "_portable_start_locations_without_helper"):
            module = ast.Module(body=[methods[name]], type_ignores=[])
            ast.fix_missing_locations(module)
            exec(compile(module, source_path, "exec"), namespace)

        class EmbeddedFallback:
            COMMAND_RUN_STATE_VARIABLES = (
                "STATE_MAIN_FUNCTION", "STATE_3_STORY_FUNCTION")
            COMMAND_RUN_STATE_PARENTS = {
                "STATE_3_STORY_FUNCTION": (
                    "STATE_MAIN_FUNCTION", "MAIN_3_F_LANK"),
            }
            COMMAND_STEP_LABELS = {
                "MAIN_ZA_BATTLE_INFI": "ZA_battle_infi_main（単独実行モード）",
            }
            COMMAND_STEP_DESCRIPTIONS = {}
            _portable_start_apply_without_helper = namespace[
                "_portable_start_apply_without_helper"]
            _portable_start_records_without_helper = namespace[
                "_portable_start_records_without_helper"]
            _portable_start_locations_without_helper = namespace[
                "_portable_start_locations_without_helper"]

            def __init__(self):
                self.STATE_MAIN_FUNCTION = {
                    "MAIN_STATE_INIT": object(),
                    "MAIN_3_F_LANK": object(),
                    "MAIN_ZA_BATTLE_INFI": object(),
                }
                self.STATE_3_STORY_FUNCTION = {
                    "3_STORY_CANARI_6": object(),
                }
                self.STATE_ZA_INFI_MAIN_FUNCTION = {
                    "ZA_INFI_MAIN_START": object(),
                }
                self.main_current_state = "MAIN_STATE_INIT"
                self.main_current_state_init = ""
                self._3_story_current_state_init = "3_STORY_END"

        command = EmbeddedFallback()
        records = command._portable_start_records_without_helper()
        helper_records = discover_story_locations(command)
        record_fields = (
            "variable", "state", "label", "description", "group", "order")
        self.assertEqual(
            [tuple(item[field] for field in record_fields)
             for item in records],
            [tuple(item[field] for field in record_fields)
             for item in helper_records])
        self.assertEqual(
            {item["group"] for item in records}, {"MAIN", "3_STORY"})
        self.assertFalse(any(
            item["variable"] == "STATE_ZA_INFI_MAIN_FUNCTION"
            for item in records))
        self.assertEqual(
            command._portable_start_locations_without_helper(
                "ZA_battle_infi_main")[0][:2],
            ("STATE_MAIN_FUNCTION", "MAIN_ZA_BATTLE_INFI"))
        command._portable_start_apply_without_helper(
            "STATE_3_STORY_FUNCTION", "3_STORY_CANARI_6")
        self.assertEqual(command.main_current_state_init, "MAIN_3_F_LANK")
        self.assertEqual(
            command._3_story_current_state_init, "3_STORY_CANARI_6")

        show_dialog = methods[
            "_show_portable_start_dialog_without_helper"]
        constants = {
            node.value for node in ast.walk(show_dialog)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        attributes = {
            node.attr for node in ast.walk(show_dialog)
            if isinstance(node, ast.Attribute)
        }
        self.assertTrue({
            "検索・章フィルター", "開始Step", "文字検索:", "章:",
            "開始をやめる", "Commands既定で開始", "選択Stepから開始",
        }.issubset(constants))
        self.assertTrue({
            "Toplevel", "Entry", "Combobox", "Button", "grab_set",
            "lift", "focus_set", "wait_window",
        }.issubset(attributes))

    def test_portable_selector_exposes_story_and_standalone_infi_only(self):
        command = _PortableZaStory()
        locations = discover_story_locations(command)
        pairs = {(item["variable"], item["state"]) for item in locations}

        self.assertIn(
            ("STATE_3_STORY_FUNCTION", "3_STORY_CANARI_6"), pairs)
        self.assertIn(
            ("STATE_MAIN_FUNCTION", "MAIN_ZA_BATTLE_INFI"), pairs)
        self.assertNotIn(
            ("STATE_ZA_INFI_MAIN_FUNCTION", "ZA_INFI_MAIN_START"), pairs)
        infi = next(
            item for item in locations
            if item["state"] == "MAIN_ZA_BATTLE_INFI")
        self.assertIn("ZA_battle_infi_main", infi["label"])
        self.assertIn("単独", infi["description"])

    def test_portable_selector_cancels_when_gui_parent_is_unavailable(self):
        self.assertEqual(
            show_portable_start_dialog(_PortableZaStory()),
            PORTABLE_START_CANCEL)

    def test_portable_canari6_start_sets_child_and_main_parent(self):
        command = _PortableZaStory()

        assignments = apply_story_start(
            command, "STATE_3_STORY_FUNCTION", "3_STORY_CANARI_6")

        self.assertEqual(
            command._3_story_current_state_init, "3_STORY_CANARI_6")
        self.assertEqual(command.main_current_state_init, "MAIN_3_F_LANK")
        self.assertEqual(command.main_current_state, "MAIN_STATE_INIT")
        self.assertEqual(
            [(item["attribute"], item["value"]) for item in assignments],
            [("main_current_state", "MAIN_STATE_INIT"),
             ("_3_story_current_state_init", "3_STORY_CANARI_6"),
             ("main_current_state_init", "MAIN_3_F_LANK")])

    def test_portable_main_state_init_selection_means_normal_start(self):
        command = _PortableZaStory()
        apply_story_start(
            command, "STATE_MAIN_FUNCTION", "MAIN_STATE_INIT")
        self.assertEqual(command.main_current_state_init, "")


if __name__ == "__main__":
    unittest.main()
