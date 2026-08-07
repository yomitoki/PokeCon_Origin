import datetime
import os
import sys
import unittest
from collections import namedtuple


SERIAL_CONTROLLER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "SerialController"))
if SERIAL_CONTROLLER not in sys.path:
    sys.path.insert(0, SERIAL_CONTROLLER)
DEV_STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "DevStudio"))
if DEV_STUDIO not in sys.path:
    sys.path.insert(0, DEV_STUDIO)

from AutomationTriggers import StableRuleEvaluator, discover_state_values, resolve_command_value
from ControllerInputLog import (python_replacement_body, replay_recording,
                                rotate_log_range, rotate_serial_message)
from DiskSpaceGuard import disk_space_violations
from SampleFunctionSync import replace_class_functions
from StepDebugAssist import extract_step_method, execute_operation
from QuickActions import ACTION_BY_ID, normalize_action_ids, normalize_position


class _StepDebugSample:
    def __init__(self):
        self.ready = True
        self.values = []

    def sample_step(self):
        self.values.append("first")
        if self.ready:
            self.values.append("conditional")
        return "NEXT_STEP"


class StepDebugAssistTests(unittest.TestCase):
    def test_method_is_split_and_literal_next_step_is_found(self):
        sample = _StepDebugSample()
        info = extract_step_method(sample.sample_step)
        self.assertEqual(info["next_states"], ["NEXT_STEP"])
        self.assertEqual(len(info["operations"]), 2)
        self.assertIn("IF", info["operations"][1]["context"])

    def test_single_operation_executes_without_calling_whole_method(self):
        sample = _StepDebugSample()
        info = extract_step_method(sample.sample_step)
        execute_operation(sample, sample.sample_step, info["operations"][0]["code"])
        self.assertEqual(sample.values, ["first"])


class QuickActionsTests(unittest.TestCase):
    def test_saved_actions_are_deduplicated_and_unknown_ids_are_removed(self):
        saved = '["camera.capture", "missing", "camera.capture", "recording.toggle"]'
        self.assertEqual(
            normalize_action_ids(saved),
            ["camera.capture", "recording.toggle"],
        )
        self.assertIn("commands.start_stop", ACTION_BY_ID)
        self.assertEqual(ACTION_BY_ID["recording.toggle"]["textvariable"], "record_button_text")

    def test_invalid_position_falls_back_to_top(self):
        self.assertEqual(normalize_position("中央"), "上")
        self.assertEqual(normalize_position("下"), "下")


class FunctionReplacementTests(unittest.TestCase):
    def test_selected_function_can_replace_multiple_differently_named_methods(self):
        source = '''
class Command:
    def first_target(self):
        return "old-1"

    def second_target(self):
        return "old-2"

    def untouched(self):
        return "keep"
'''
        replacement = '''
def sample_function(self):
    value = "replacement"
    return value
'''
        updated = replace_class_functions(
            source,
            {"first_target": replacement, "second_target": replacement},
        )
        compile(updated, "<replacement-test>", "exec")
        self.assertIn("def first_target(self):", updated)
        self.assertIn("def second_target(self):", updated)
        self.assertEqual(updated.count('value = "replacement"'), 2)
        self.assertIn('return "keep"', updated)
        self.assertNotIn("def sample_function(self):", updated)


class TriggerTests(unittest.TestCase):
    def test_state_table_values_are_available_for_search(self):
        source = """
class Command:
    def __init__(self):
        self.STATE_1_STORY_FUNCTION = {
            '1_STORY_OUT_HOTEL_Z_72': self.step_72,
            '1_STORY_OUT_HOTEL_Z_75': self.step_75,
        }
"""
        self.assertEqual(
            discover_state_values(source, "STATE_1_STORY_FUNCTION"),
            ["1_STORY_OUT_HOTEL_Z_72", "1_STORY_OUT_HOTEL_Z_75"],
        )

    def test_story_alias_and_stable_duration(self):
        command = type("Command", (), {"_1_story_current_state": "1_STORY_OUT_HOTEL_Z_72"})()
        found, value, actual = resolve_command_value(command, "STATE_1_STORY_FUNCTION")
        self.assertTrue(found)
        self.assertEqual(value, "1_STORY_OUT_HOTEL_Z_72")
        self.assertEqual(actual, "_1_story_current_state")
        evaluator = StableRuleEvaluator()
        rule = {"id": "start", "variable": "STATE_1_STORY_FUNCTION",
                "value": "1_STORY_OUT_HOTEL_Z_72", "seconds": 2.0}
        self.assertFalse(evaluator.evaluate(rule, command, now=10.0)["triggered"])
        self.assertTrue(evaluator.evaluate(rule, command, now=12.0)["triggered"])


class ControllerLogTests(unittest.TestCase):
    def test_rotate_left_stick_range_by_ninety_degrees(self):
        # 0x0002 means that the left-stick coordinate pair follows the hat.
        rotated = rotate_serial_message("0x0002 8 ff 80", 90, "left")
        self.assertEqual(rotated, "0x0002 8 80 ff")
        lines = ["2026-08-07 12:00:00.000000,0x0002 8 ff 80\n"]
        self.assertEqual(rotate_log_range(lines, 1, 1, 90)[0].split(",", 1)[1].strip(),
                         "0x0002 8 80 ff")

    def test_generate_replacement_preserves_relative_timing(self):
        first = datetime.datetime(2026, 8, 7, 12, 0, 0)
        lines = [
            first.isoformat(sep=" ") + ",0x0010 8\n",
            (first + datetime.timedelta(milliseconds=250)).isoformat(sep=" ") + ",0x0000 8\n",
        ]
        body = python_replacement_body(lines)
        self.assertIn("self.direct_serial", body)
        self.assertIn("0.25", body)

    def test_registered_recording_can_be_replayed(self):
        class FakeSender:
            def __init__(self):
                self.messages = []

            def writeRow_wo_perf_counter(self, message, is_show=False):
                self.messages.append(message)

        sender = FakeSender()
        lines = ["2026-08-07 12:00:00.000000,0x0010 8\n"]
        self.assertTrue(replay_recording(lines, sender))
        self.assertEqual(sender.messages, ["0x0010 8"])


class RecordingDiskGuardTests(unittest.TestCase):
    def test_same_drive_is_checked_once_and_thresholds_are_reported(self):
        usage_type = namedtuple("usage", "total used free")
        gib = 1024 ** 3
        calls = []

        def nearly_full(path):
            calls.append(path)
            return usage_type(100 * gib, 96 * gib, 4 * gib)

        violations = disk_space_violations(
            (("tool", SERIAL_CONTROLLER), ("output", os.path.dirname(SERIAL_CONTROLLER))),
            min_free_gb=5, max_usage_percent=95, usage_provider=nearly_full,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(violations), 1)
        self.assertIn("tool", violations[0]["label"])
        self.assertIn("output", violations[0]["label"])

    def test_drive_below_limits_has_no_violation(self):
        usage_type = namedtuple("usage", "total used free")
        gib = 1024 ** 3
        healthy = lambda path: usage_type(100 * gib, 80 * gib, 20 * gib)
        self.assertEqual(
            disk_space_violations((("output", SERIAL_CONTROLLER),), 5, 95, healthy),
            [],
        )


if __name__ == "__main__":
    unittest.main()
