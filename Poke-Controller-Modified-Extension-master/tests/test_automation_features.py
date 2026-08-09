import datetime
import inspect
import os
import sys
import json
import tempfile
import threading
import time
import unittest
import struct
from collections import namedtuple
from unittest import mock


SERIAL_CONTROLLER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "SerialController"))
if SERIAL_CONTROLLER not in sys.path:
    sys.path.insert(0, SERIAL_CONTROLLER)
DEV_STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "DevStudio"))
if DEV_STUDIO not in sys.path:
    sys.path.insert(0, DEV_STUDIO)

from AutomationTriggers import (StableRuleEvaluator, discover_state_values,
                                discover_state_variables, resolve_command_value)
from CommandStartOverride import apply_command_start_override
from ControllerInputLog import (python_replacement_body, replay_recording,
                                rotate_log_range, rotate_serial_message)
from DiskSpaceGuard import disk_space_violations
from SampleFunctionSync import replace_class_functions
from StepDebugAssist import (DELETE_OPERATION_CODE, derive_follow_step_rule,
                             extract_step_method, execute_operation,
                             recommended_next_state, replacement_is_enabled)
from StepDebugSource import (apply_operation_replacements, extract_named_method_info,
                             extract_state_method_info, resolve_state_method_name,
                             build_runtime_replacement_function,
                             split_mixed_step_rule)
from ThreadCancellation import raise_in_thread, request_stop_flags
from SourceFunctionTools import (build_rename_map, register_source_functions,
                                 rename_source_functions, source_function_records,
                                 step_function_names)
from SharedDebugLibrary import (SharedDebugConflictError, read_shared_debug,
                                write_shared_debug)
from QuickActions import ACTION_BY_ID, normalize_action_ids, normalize_position
from InputSetData import (INPUT_SET_VARIABLES, SCHEMA_VERSION,
                          has_complete_snapshot, legacy_combined_snapshot,
                          input_set_commands_enabled, strip_commands_from_snapshot,
                          sync_command_start_overrides, sync_commands_assist_rules,
                          sync_quick_actions,
                          sync_step_debug_rules)
from InputSetRuntimeRegistry import (ActiveInputSetRegistry,
                                     default_window_activity_registry_path,
                                     process_identity, read_active_input_sets)
from ImageDetectionMonitor import filter_target_names, load_detection_library
from ImageHealthCheck import audit_image_library, suggested_crop
from ImageDetectionLibrary import generate_image_check
from CompletionEngine import CompletionEngine
from PokeConShowInfo import (installed_distribution_version,
                             requirement_distribution_name)
from UiResponsiveness import preview_render_interval
from CommandMonitorRecording import (CommandStateTimeline,
                                     historical_retention_ids,
                                     relevant_state_path,
                                     runtime_state_snapshot,
                                     temporary_chunk_ids_for_session)
from CommandRecordingMerge import merge_command_recording_chunks
from Commands.CommandBase import Command
from Commands.Keys import Button, Direction, KeyPress, Stick
import Utility as command_utility


class DevStudioCompletionTests(unittest.TestCase):
    def test_source_names_regex_uses_python_314_compatible_flags(self):
        source = (
            "class StoryCommand:\n"
            "    selected_step = 'START'\n"
            "    def run(self):\n"
            "        self.current_step = selected_step\n"
        )
        names = {item["label"] for item in CompletionEngine._source_candidates(source)}
        self.assertTrue(
            {"StoryCommand", "selected_step", "run", "current_step"}.issubset(names))


class _StepDebugSample:
    def __init__(self):
        self.ready = True
        self.values = []

    def sample_step(self):
        self.values.append("first")
        if self.ready:
            self.values.append("conditional")
        return "NEXT_STEP"

    def return_only_condition(self):
        if self.ready:
            return "READY"
        return "WAIT"


class StepDebugNextStateTests(unittest.TestCase):
    def test_mapping_fallback_selects_state_after_current(self):
        states = ["STEP_1", "STEP_2", "STEP_3", "STEP_4"]
        self.assertEqual(
            recommended_next_state("STEP_3", [], states), "STEP_4")

    def test_explicit_backtrack_is_kept_when_forward_is_not_returnable(self):
        states = ["STEP_1", "STEP_2", "STEP_3", "STEP_4"]
        self.assertEqual(
            recommended_next_state("STEP_3", ["STEP_2", "STEP_3"], states),
            "STEP_2")

    def test_declared_forward_return_wins_over_earlier_candidate(self):
        states = ["STEP_1", "STEP_2", "STEP_3", "STEP_4"]
        self.assertEqual(
            recommended_next_state(
                "STEP_3", ["STEP_2", "STEP_4", "STEP_3"], states),
            "STEP_4")


class _StartOverrideSample:
    def __init__(self):
        self.STATE_MAIN_FUNCTION = {"MAIN_1_Z_LANK": self.main_story}
        self.main_current_state = "MAIN_STATE_INIT"
        self.main_current_state_init = ""
        self.STATE_1_STORY_FUNCTION = {
            "1_STORY_A": self.story_a,
            "1_STORY_B": self.story_b,
        }
        self._1_story_current_state = "1_STORY_A"
        self._1_story_current_state_init = ""

    def main_story(self):
        self._1_story_current_state = self.STATE_1_STORY_FUNCTION[
            self._1_story_current_state]()
        return "MAIN_1_Z_LANK"

    def story_a(self):
        return "1_STORY_B"

    def story_b(self):
        return "1_STORY_B"


class CommandStartOverrideTests(unittest.TestCase):
    def test_nested_story_start_uses_existing_init_attributes(self):
        command = _StartOverrideSample()
        applied = apply_command_start_override(
            command, "STATE_1_STORY_FUNCTION", "1_STORY_B")
        self.assertEqual(command._1_story_current_state_init, "1_STORY_B")
        self.assertEqual(command.main_current_state_init, "MAIN_1_Z_LANK")
        self.assertEqual(
            [(item["attribute"], item["value"]) for item in applied],
            [("_1_story_current_state_init", "1_STORY_B"),
             ("main_current_state_init", "MAIN_1_Z_LANK")],
        )


class ForceStopTests(unittest.TestCase):
    def test_normal_stop_request_never_waits_on_pause_checkpoint(self):
        class Connection:
            alive = True
        class CommandState:
            alive = True
            pause_requested = True
            socket0 = Connection()
            mqtt0 = Connection()
        command = CommandState()
        started = time.perf_counter()
        request_stop_flags(command)
        self.assertLess(time.perf_counter() - started, 0.2)
        self.assertFalse(command.alive)
        self.assertFalse(command.pause_requested)

    def test_force_stop_can_interrupt_live_python_worker(self):
        class ForcedStopForTest(Exception):
            pass
        started = threading.Event()
        stopped = threading.Event()
        def work():
            try:
                started.set()
                while True:
                    time.sleep(0.01)
            except ForcedStopForTest:
                stopped.set()
        worker = threading.Thread(target=work, daemon=True)
        worker.start(); self.assertTrue(started.wait(1.0))
        self.assertTrue(raise_in_thread(worker, ForcedStopForTest))
        self.assertTrue(stopped.wait(1.0))
        worker.join(1.0)


class CommandOutputTests(unittest.TestCase):
    def test_command_text_output_uses_dispatcher_instead_of_tk_widget(self):
        calls = []
        previous = Command.text_output
        Command.text_output = lambda panel, mode, text: calls.append((panel, mode, text))
        try:
            # Bypass Command.__init__; this test concerns GUI dispatch only and
            # must not open socket/MQTT configuration resources.
            command = object.__new__(Command)
            command.text_area_1 = None
            command.text_area_2 = None
            command.print_t1("first")
            command.print_t2b("w", "second", end="")
        finally:
            Command.text_output = previous
        self.assertEqual(calls, [
            ("Output#1", "a", "first\n"),
            ("Output#2", "w", "second"),
        ])


class CommandModuleLoadingTests(unittest.TestCase):
    def test_broken_command_file_does_not_hide_other_commands(self):
        loaded = object()
        errors = []

        def import_one(name):
            if name == "Commands.PythonCommands.broken":
                raise TabError("mixed indentation")
            return loaded

        with mock.patch.object(
                command_utility, "getModuleNames",
                return_value=["Commands.PythonCommands.broken",
                              "Commands.PythonCommands.working"]), \
                mock.patch.object(command_utility.importlib, "import_module",
                                  side_effect=import_one):
            modules = command_utility.importAllModules("unused", errors=errors)

        self.assertEqual(modules, [loaded])
        self.assertEqual(errors[0]["module"], "Commands.PythonCommands.broken")
        self.assertIn("mixed indentation", errors[0]["error"])


class StepDebugAssistTests(unittest.TestCase):
    def test_saved_replacement_enable_flag_is_backward_compatible(self):
        self.assertTrue(replacement_is_enabled({"type": "code", "code": "self.ready = True"}))
        self.assertFalse(replacement_is_enabled(
            {"type": "code", "code": "self.ready = True", "enabled": False}))
        self.assertFalse(replacement_is_enabled({}))

    def test_following_next_step_gets_an_independent_saved_rule(self):
        original = {
            "id": "72", "command": "ZA", "variable": "STATE_STORY_FUNCTION",
            "state": "STEP_72", "auto_follow": True,
            "replacements": {"op72": {"type": "code", "code": "self.press(1)"}},
            "source": {"method": "step_72"},
        }
        followed = derive_follow_step_rule(
            original, "ZA", "STATE_STORY_FUNCTION", "STEP_73", "73")
        self.assertEqual(followed["state"], "STEP_73")
        self.assertEqual(followed["replacements"], {})
        self.assertEqual(followed["source"], {})
        self.assertEqual(followed["follow_origin_id"], "72")
        self.assertIn("op72", original["replacements"])
        self.assertIn("処理削除", DELETE_OPERATION_CODE)

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

    def test_return_only_condition_is_visible_as_one_operation(self):
        sample = _StepDebugSample()
        info = extract_step_method(sample.return_only_condition)
        self.assertEqual(len(info["operations"]), 1)
        self.assertIn("if self.ready", info["operations"][0]["summary"])
        self.assertEqual(info["next_states"], ["READY", "WAIT"])
        self.assertEqual(
            execute_operation(sample, sample.return_only_condition,
                              info["operations"][0]["code"]),
            "READY",
        )


class StepDebugSourceTests(unittest.TestCase):
    SOURCE = '''
class Story:
    def __init__(self):
        self.STATE_1_STORY_FUNCTION = {
            "STEP_A": self._step_a,
            "STEP_B": self._step_b,
        }

    def _step_a(self):
        self.press(10)
        if self.ready:
            self.press(20)
        return "STEP_B"

    def untouched_but_existing(self):
        return "STEP_B"

    def _step_b(self):
        self.press(30)
        return "STEP_B"
'''

    def test_state_mapping_and_operations_are_resolved_without_running_command(self):
        self.assertEqual(
            resolve_state_method_name(self.SOURCE, "STATE_1_STORY_FUNCTION", "STEP_A"),
            "_step_a",
        )
        info = extract_state_method_info(
            self.SOURCE, "STATE_1_STORY_FUNCTION", "STEP_A")
        self.assertEqual(len(info["operations"]), 2)
        self.assertEqual(info["next_states"], ["STEP_B"])

    def test_state_mapping_wins_over_stale_saved_method_name(self):
        self.assertEqual(
            resolve_state_method_name(
                self.SOURCE, "STATE_1_STORY_FUNCTION", "STEP_A",
                preferred="untouched_but_existing"),
            "_step_a",
        )

    def test_offline_operation_ids_match_live_step_debug_ids(self):
        live = extract_step_method(_StepDebugSample().sample_step)
        offline = extract_named_method_info(inspect.getsource(_StepDebugSample), "sample_step")
        self.assertEqual(
            [item["id"] for item in offline["operations"]],
            [item["id"] for item in live["operations"]],
        )

    def test_selected_operation_can_be_applied_to_source(self):
        info = extract_state_method_info(
            self.SOURCE, "STATE_1_STORY_FUNCTION", "STEP_A")
        updated = apply_operation_replacements(
            self.SOURCE, info, {info["operations"][0]["id"]: "self.press(99)"})
        self.assertIn("self.press(99)", updated)
        self.assertNotIn("self.press(10)", updated)
        compile(updated, "<step-debug-source-test>", "exec")

    def test_operation_can_be_replaced_with_safe_deletion(self):
        info = extract_state_method_info(
            self.SOURCE, "STATE_1_STORY_FUNCTION", "STEP_A")
        updated = apply_operation_replacements(
            self.SOURCE, info, {info["operations"][0]["id"]: DELETE_OPERATION_CODE})
        self.assertNotIn("self.press(10)", updated)
        self.assertIn("PokeCon Stepデバッグ: 処理削除", updated)
        compile(updated, "<step-debug-delete-test>", "exec")

    def test_legacy_mixed_rule_is_split_by_source_function(self):
        info_a = extract_state_method_info(
            self.SOURCE, "STATE_1_STORY_FUNCTION", "STEP_A")
        info_b = extract_state_method_info(
            self.SOURCE, "STATE_1_STORY_FUNCTION", "STEP_B")
        op_a, op_b = info_a["operations"][0], info_b["operations"][0]
        mixed = {
            "id": "original", "command": "Story",
            "variable": "STATE_1_STORY_FUNCTION", "state": "STEP_A",
            "source": {"method": "_step_b"},
            "replacements": {
                op_a["id"]: {"type": "code", "code": "self.press(11)",
                              "line": op_a["line"]},
                op_b["id"]: {"type": "code", "code": "self.press(31)",
                              "line": op_b["line"]},
            },
        }
        split, changed = split_mixed_step_rule(
            mixed, self.SOURCE, lambda state, index: "new-{}".format(index))
        self.assertTrue(changed)
        self.assertEqual([item["state"] for item in split], ["STEP_A", "STEP_B"])
        self.assertEqual(split[0]["source"]["method"], "_step_a")
        self.assertEqual(split[1]["source"]["method"], "_step_b")
        self.assertIn(op_a["id"], split[0]["replacements"])
        self.assertIn(op_b["id"], split[1]["replacements"])

    def test_whole_function_replacement_can_run_without_editing_source(self):
        sample = _StepDebugSample()
        info = extract_step_method(sample.sample_step)
        replacement = build_runtime_replacement_function(
            sample.sample_step,
            {info["operations"][0]["id"]: 'self.values.append("runtime")'},
        )
        result = replacement(sample)
        self.assertEqual(result, "NEXT_STEP")
        self.assertEqual(sample.values, ["runtime", "conditional"])


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


class InputSetRuntimeRegistryTests(unittest.TestCase):
    def test_current_process_has_reusable_identity(self):
        self.assertEqual(process_identity(os.getpid()), process_identity(os.getpid()))

    def test_multiple_instances_are_listed_and_one_can_unregister(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, "active_input_sets.json")
            identities = {101: "101:start-a", 202: "202:start-b"}
            provider = lambda pid: identities.get(pid)
            first = ActiveInputSetRegistry(
                path, profile="default", identity_provider=provider,
                token="first", pid=101)
            second = ActiveInputSetRegistry(
                path, profile="default", identity_provider=provider,
                token="second", pid=202)
            first.set_active("Switch_No1", "PokeCon Switch 1")
            second.set_active("Switch_No2", "PokeCon Switch 2")

            entries = read_active_input_sets(path, identity_provider=provider)
            self.assertEqual(
                [(entry["input_set"], entry["pid"]) for entry in entries],
                [("Switch_No1", 101), ("Switch_No2", 202)])

            first.close()
            entries = read_active_input_sets(path, identity_provider=provider)
            self.assertEqual([entry["input_set"] for entry in entries], ["Switch_No2"])

    def test_crashed_or_pid_reused_entry_is_pruned(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, "active_input_sets.json")
            identities = {303: "303:first-start"}
            provider = lambda pid: identities.get(pid)
            registry = ActiveInputSetRegistry(
                path, identity_provider=provider, token="stale", pid=303)
            registry.set_active("Switch_No3")

            identities[303] = "303:reused-pid"
            self.assertEqual(
                read_active_input_sets(path, identity_provider=provider), [])
            with open(path, "r", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream)["entries"], {})

    def test_current_instance_can_be_excluded_from_popup_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, "active_input_sets.json")
            provider = lambda pid: "{}:start".format(pid)
            registry = ActiveInputSetRegistry(
                path, identity_provider=provider, token="self", pid=404)
            registry.set_active("Switch_No4")
            self.assertEqual(registry.entries(include_self=False), [])
            self.assertEqual(
                registry.entries(include_self=True)[0]["input_set"], "Switch_No4")

    def test_last_focused_live_pokecon_wins_even_after_browser_focus(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, "active_windows.json")
            provider = lambda pid: "{}:start".format(pid)
            first = ActiveInputSetRegistry(
                path, identity_provider=provider, token="first", pid=501)
            second = ActiveInputSetRegistry(
                path, identity_provider=provider, token="second", pid=502)
            first.mark_focused(marker=100)
            second.mark_focused(marker=200)
            self.assertFalse(first.is_last_focused())
            self.assertTrue(second.is_last_focused())
            # No focus event is written when the user moves to a browser, so
            # the last PokeCon remains the full-rate preview owner.
            self.assertTrue(second.is_last_focused())
            first.mark_focused(marker=300)
            self.assertTrue(first.is_last_focused())
            second.close()
            first.close()

    def test_activity_registry_is_shared_outside_individual_profiles(self):
        path = default_window_activity_registry_path()
        self.assertEqual(os.path.basename(path), "active_windows.json")
        self.assertIn("PokeConModifiedExtension", path)


class InputSetDataTests(unittest.TestCase):
    def test_commands_disabled_input_set_rejects_debug_auto_sync(self):
        data = {"input_sets": {"CameraOnly": {
            "commands": {"enabled": False}, "all_tabs": {}}}}
        self.assertFalse(sync_step_debug_rules(
            data, "CameraOnly", [{"state": "STEP_A"}]))
        self.assertFalse(sync_commands_assist_rules(
            data, "CameraOnly", [{"function_replacement": True}]))
        self.assertFalse(sync_command_start_overrides(
            data, "CameraOnly", {"ZA": {"state": "STEP_A"}}))
        self.assertNotIn("commands_assist", data["input_sets"]["CameraOnly"])

    def test_commands_disabled_quick_sync_removes_command_buttons(self):
        data = {"input_sets": {"CameraOnly": {
            "commands": {"enabled": False}, "all_tabs": {}}}}
        quick = {
            "left": {"position": "上", "items": [
                "commands.start_stop", "camera.capture"]},
            "right": {"position": "下", "items": ["watch.enabled"]},
        }
        self.assertTrue(sync_quick_actions(data, "CameraOnly", quick))
        saved = data["input_sets"]["CameraOnly"]["all_tabs"]["quick_actions"]
        self.assertEqual(saved["left"]["items"], ["camera.capture"])
        self.assertEqual(saved["right"]["items"], [])

    def test_commands_disabled_snapshot_drops_command_owned_settings(self):
        source = {
            "values": {"fps": "60", "command_watch_enabled": True,
                       "step_debug_skip_confirm": True},
            "command_selection": {"python": "ZA_story"},
            "shortcuts": {"1": {"class": "Python", "name": "ZA_story"}},
            "commands_assist": {"step_debug_rules": [{"state": "STEP_A"}]},
            "controller_recordings": {"move": {}},
            "quick_actions": {
                "left": {"position": "上", "items": [
                    "commands.start_stop", "camera.capture", "watch.enabled"]},
                "right": {"position": "下", "items": []},
            },
        }
        saved = strip_commands_from_snapshot(source)
        self.assertFalse(saved["commands_enabled"])
        self.assertEqual(saved["values"], {"fps": "60"})
        for key in ("command_selection", "shortcuts", "commands_assist",
                    "controller_recordings"):
            self.assertNotIn(key, saved)
        self.assertEqual(saved["quick_actions"]["left"]["items"],
                         ["camera.capture"])

    def test_old_input_set_keeps_commands_until_user_makes_explicit_choice(self):
        self.assertTrue(input_set_commands_enabled({"all_tabs": {}}))
        self.assertFalse(input_set_commands_enabled(
            {"commands": {"enabled": False}, "all_tabs": {}}))

    def test_image_detection_monitor_choices_belong_to_input_set(self):
        for name in ("image_detection_monitor_search",
                     "image_detection_monitor_target",
                     "image_detection_monitor_variant",
                     "image_detection_monitor_enabled",
                     "image_detection_monitor_interval",
                     "image_detection_monitor_output",
                     "image_detection_monitor_output_tag"):
            self.assertIn(name, INPUT_SET_VARIABLES)

    def test_function_replacement_mappings_are_continuously_mirrored(self):
        data = {"input_sets": {"Switch": {"all_tabs": {}}}}
        rules = [{"function_replacement": True, "value": "STEP_A",
                  "replacement_type": "step_debug_function"}]
        self.assertTrue(sync_commands_assist_rules(data, "Switch", rules))
        item = data["input_sets"]["Switch"]
        self.assertEqual(item["commands_assist"]["rules"], rules)
        self.assertEqual(item["all_tabs"]["commands_assist"]["rules"], rules)

    def test_command_start_overrides_are_mirrored_to_input_set(self):
        data = {"input_sets": {"Switch": {"all_tabs": {}}}}
        overrides = {"ZA_story": {
            "variable": "STATE_1_STORY_FUNCTION", "state": "1_STORY_STEP_B"}}
        self.assertTrue(sync_command_start_overrides(data, "Switch", overrides))
        item = data["input_sets"]["Switch"]
        self.assertEqual(item["commands_assist"]["start_overrides"], overrides)
        self.assertEqual(
            item["all_tabs"]["commands_assist"]["start_overrides"], overrides)

    def test_quick_actions_are_mirrored_to_schema3_input_set(self):
        data = {"input_sets": {"Switch": {"all_tabs": {}}}}
        quick = {"left": {"position": "上", "items": ["camera.capture"]},
                 "right": {"position": "下", "items": []}}
        self.assertTrue(sync_quick_actions(data, "Switch", quick))
        self.assertEqual(data["input_sets"]["Switch"]["all_tabs"]["quick_actions"], quick)
        quick["left"]["items"].append("recording.toggle")
        self.assertEqual(
            data["input_sets"]["Switch"]["all_tabs"]["quick_actions"]["left"]["items"],
            ["camera.capture"],
        )

    def test_quick_action_sync_preserves_legacy_input_set_format(self):
        data = {"input_sets": {"Legacy": {"camera": {}}}}
        quick = {"left": {"position": "非表示", "items": []},
                 "right": {"position": "上", "items": ["commands.force_stop"]}}
        self.assertTrue(sync_quick_actions(data, "Legacy", quick))
        self.assertNotIn("all_tabs", data["input_sets"]["Legacy"])
        self.assertEqual(data["input_sets"]["Legacy"]["quick_actions"], quick)

    def test_step_debug_replacements_are_continuously_mirrored(self):
        data = {"input_sets": {"Switch": {"all_tabs": {}}}}
        rules = [{"state": "STEP_A", "replacements": {"op": {"code": "self.press(1)"}}}]
        self.assertTrue(sync_step_debug_rules(data, "Switch", rules))
        item = data["input_sets"]["Switch"]
        self.assertEqual(item["commands_assist"]["step_debug_rules"], rules)
        self.assertEqual(item["all_tabs"]["commands_assist"]["step_debug_rules"], rules)
        rules[0]["state"] = "CHANGED_AFTER_SAVE"
        self.assertEqual(
            item["all_tabs"]["commands_assist"]["step_debug_rules"][0]["state"],
            "STEP_A",
        )

    def test_step_debug_sync_does_not_convert_legacy_input_set(self):
        data = {"input_sets": {"Legacy": {"camera": {}}}}
        self.assertTrue(sync_step_debug_rules(data, "Legacy", [{"state": "STEP_A"}]))
        self.assertNotIn("all_tabs", data["input_sets"]["Legacy"])
        self.assertEqual(
            data["input_sets"]["Legacy"]["commands_assist"]["step_debug_rules"],
            [{"state": "STEP_A"}],
        )

    def test_complete_input_set_owns_quick_actions_and_all_tab_settings(self):
        item = {"all_tabs": {"quick_actions": {
            "left": {"position": "上", "items": ["camera.capture"]},
            "right": {"position": "下", "items": []},
        }}}
        self.assertGreaterEqual(SCHEMA_VERSION, 3)
        self.assertTrue(has_complete_snapshot(item))
        for required in ("panel_ratio", "show_python_samples", "is_win_notification_start",
                         "object_detection_threshold", "step_debug_skip_confirm",
                         "window_capture_mode", "record_monitor_chunk_seconds",
                         "record_monitor_keep_steps", "record_monitor_loop_cycles",
                         "record_monitor_long_seconds", "record_monitor_auto_arm",
                         "record_monitor_confirm_delete_on_stop"):
            self.assertIn(required, INPUT_SET_VARIABLES)

    def test_complete_input_set_is_not_overridden_by_old_combination(self):
        legacy_snapshot = {"values": {"panel_ratio": 10}, "quick_actions": {}}
        combined = {"all_tabs": legacy_snapshot}
        self.assertEqual(legacy_combined_snapshot({}, combined), legacy_snapshot)
        self.assertEqual(legacy_combined_snapshot({"all_tabs": {"values": {}}}, combined), {})


class ImageDetectionMonitorTests(unittest.TestCase):
    def test_library_search_uses_names_descriptions_tags_and_paths(self):
        library = {"targets": {
            "HOTEL_DOOR": {"description": "入口", "tags": ["Pokemon_ZA"],
                           "variants": [{"template_path": "Template/ZA/door.png"}]},
            "EMPTY": {"description": "no image", "variants": []},
        }}
        self.assertEqual(filter_target_names(library, "hotel"), ["HOTEL_DOOR"])
        self.assertEqual(filter_target_names(library, "pokemon_za"), ["HOTEL_DOOR"])
        self.assertEqual(filter_target_names(library, "door.png"), ["HOTEL_DOOR"])

    def test_invalid_library_is_loaded_as_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "library.json")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("[]")
            self.assertEqual(load_detection_library(path)["targets"], {})


class ImageHealthCheckTests(unittest.TestCase):
    @staticmethod
    def _write_bmp(path, width, height):
        row_size = (width * 3 + 3) & ~3
        pixels = bytearray()
        for y in range(height):
            row = bytearray()
            for x in range(width):
                row.extend(((x * 13) % 256, (y * 17) % 256, ((x + y) * 11) % 256))
            row.extend(b"\x00" * (row_size - width * 3))
            pixels.extend(row)
        header_size = 14 + 40
        file_size = header_size + len(pixels)
        header = b"BM" + struct.pack("<IHHI", file_size, 0, 0, header_size)
        info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0,
                           len(pixels), 2835, 2835, 0, 0)
        with open(path, "wb") as stream:
            stream.write(header + info + pixels)

    def test_template_larger_than_crop_is_reported_before_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            template_root = os.path.join(root, "Template")
            os.makedirs(template_root)
            path = os.path.join(template_root, "marker.bmp")
            self._write_bmp(path, 20, 15)
            data = {"targets": {"MARKER": {"variants": [{
                "template_path": "Template/marker.bmp", "threshold": 0.8,
                "crop": [0, 0, 10, 10],
            }]}}, "lists": {}}
            rows = audit_image_library(data, template_root, (100, 80))
            self.assertEqual(rows[0]["status"], "エラー")
            self.assertIn("template_larger_than_crop", rows[0]["codes"])
            self.assertEqual(rows[0]["image_size"], (20, 15))
            self.assertTrue(rows[0]["repairable"])

    def test_missing_image_and_broken_list_are_reported(self):
        with tempfile.TemporaryDirectory() as root:
            template_root = os.path.join(root, "Template")
            os.makedirs(template_root)
            data = {
                "targets": {"LOST": {"variants": [{
                    "template_path": "Template/missing.png", "threshold": 1.2,
                    "crop": [0, 0, 0, 0],
                }]}},
                "lists": {"BROKEN": {"members": [
                    {"type": "target", "id": "UNKNOWN"}]}}
            }
            rows = audit_image_library(data, template_root, (1280, 720))
            codes = {code for row in rows for code in row["codes"]}
            self.assertIn("missing_file", codes)
            self.assertIn("invalid_threshold", codes)
            self.assertIn("invalid_list", codes)

    def test_crop_auto_repair_expands_only_to_required_size(self):
        self.assertEqual(
            suggested_crop([100, 50, 110, 60], (25, 30), (1280, 720)),
            [100, 50, 125, 80])
        with self.assertRaises(ValueError):
            suggested_crop([1270, 700, 1280, 720], (25, 30), (1280, 720))

    def test_intentional_single_color_warning_can_be_ignored_per_variant(self):
        with tempfile.TemporaryDirectory() as root:
            template_root = os.path.join(root, "Template")
            os.makedirs(template_root)
            path = os.path.join(template_root, "solid.bmp")
            self._write_bmp(path, 30, 20)
            variant = {
                "template_path": "Template/solid.bmp", "threshold": 0.8,
                "crop": [0, 0, 100, 100],
                "health_ignored_warnings": ["low_contrast"],
            }
            data = {"targets": {"TEXT_COLOR": {"variants": [variant]}}, "lists": {}}
            with mock.patch(
                    "ImageHealthCheck._optional_image_statistics",
                    return_value={"contrast": 0.0, "alpha_nonzero": None}):
                row = audit_image_library(data, template_root, (1280, 720))[0]
            self.assertEqual(row["status"], "除外")
            self.assertEqual(row["ignored_warning_codes"], ["low_contrast"])
            self.assertNotIn("low_contrast", row["codes"])

    def test_health_metadata_is_removed_from_generated_runtime_arguments(self):
        data = {"targets": {"TEXT_COLOR": {
            "operator": "OR", "description": "", "variants": [{
                "template_path": "Template/solid.bmp", "threshold": 0.8,
                "crop": [0, 0, 0, 0],
                "health_ignored_warnings": ["low_contrast"],
            }]}}, "lists": {}}
        source = generate_image_check(data, "TEXT_COLOR", "target")
        self.assertIn("detect_settings.pop('health_ignored_warnings', None)", source)


class ManualControllerResponsivenessTests(unittest.TestCase):
    class _ShowSerial:
        def __init__(self):
            self.calls = 0

        def get(self):
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("Tk variable was read from a writer thread")
            return False

    class _Serial:
        def __init__(self):
            self.rows = []

        def write(self, value):
            self.rows.append(value)

    def test_manual_packet_bypasses_override_while_command_waits(self):
        show_serial = self._ShowSerial()
        serial_module = mock.MagicMock()
        serial_module.serialutil.SerialException = OSError
        with mock.patch.dict(sys.modules, {"serial": serial_module}):
            from Commands.Sender import Sender as TestSender
        sender = TestSender(show_serial)
        sender.ser = self._Serial()
        sender.begin_manual_override()
        completed = threading.Event()

        def command_write():
            sender.writeRow("command")
            completed.set()

        worker = threading.Thread(target=command_write)
        worker.start()
        self.assertFalse(completed.wait(0.03))
        sender.writeRow("manual", priority=True)
        self.assertEqual(sender.ser.rows, [b"manual\r\n"])
        sender.end_manual_override()
        self.assertTrue(completed.wait(0.3))
        worker.join(timeout=0.3)
        self.assertEqual(sender.ser.rows, [b"manual\r\n", b"command\r\n"])
        self.assertEqual(show_serial.calls, 1)

    def test_priority_keypress_marks_serial_packet_as_manual(self):
        class CaptureSender:
            def __init__(self):
                self.priority = None

            def writeRow(self, _row, is_show=False, priority=False):
                self.priority = priority

        sender = CaptureSender()
        KeyPress(sender, priority=True).input(Button.A)
        self.assertTrue(sender.priority)

    def test_tuple_stick_position_does_not_flood_standard_output(self):
        logger = Direction(Stick.LEFT, (128, 127))._logger
        before = len(logger.handlers)
        with mock.patch("builtins.print") as output:
            for value in range(20):
                Direction(Stick.LEFT, (value, 127))
        output.assert_not_called()
        self.assertEqual(len(logger.handlers), before)


class CommandMonitorRecordingTests(unittest.TestCase):
    def test_kept_command_chunks_are_merged_with_step_and_output_logs(self):
        with tempfile.TemporaryDirectory() as root:
            chunks = []
            for index, state in enumerate(("STEP_A", "STEP_B"), start=1):
                session_dir = os.path.join(root, "chunk{}".format(index))
                os.makedirs(session_dir)
                with open(os.path.join(session_dir, "recording.avi"), "wb") as stream:
                    stream.write(b"avi" + bytes([index]))
                with open(os.path.join(session_dir, "recording.wav"), "wb") as stream:
                    stream.write(b"wav" + bytes([index]))
                with open(os.path.join(session_dir, "steps.jsonl"),
                          "w", encoding="utf-8") as stream:
                    stream.write('{"state":"' + state + '"}\n')
                with open(os.path.join(session_dir, "commands.log"),
                          "w", encoding="utf-8") as stream:
                    stream.write("log {}\n".format(index))
                chunks.append({
                    "id": "chunk{}".format(index),
                    "session_dir": session_dir,
                    "started": float(index * 10),
                    "ended": float(index * 10 + 3),
                    "started_wall": "2026-08-09T00:00:0{}".format(index),
                    "states": [state],
                    "command": "ZA_story",
                    "command_session_id": "run-1",
                })
            chunks[0]["pinned"] = True

            class Completed:
                returncode = 0
                stderr = ""

            def fake_ffmpeg(command, **_kwargs):
                with open(command[-1], "wb") as stream:
                    stream.write(b"merged mp4")
                return Completed()

            merged = merge_command_recording_chunks(
                chunks, root, "run-1", ffmpeg_path="ffmpeg",
                run_command=fake_ffmpeg,
                now=datetime.datetime(2026, 8, 9, 12, 0, 0))
            self.assertTrue(merged["merged"])
            self.assertTrue(merged["pinned"])
            self.assertEqual(merged["states"], ["STEP_A", "STEP_B"])
            self.assertEqual(merged["duration_saved"], 6.0)
            self.assertTrue(os.path.isfile(os.path.join(
                merged["session_dir"], "recording.mp4")))
            with open(os.path.join(merged["session_dir"], "commands.log"),
                      "r", encoding="utf-8") as stream:
                log = stream.read()
            self.assertIn("log 1", log)
            self.assertIn("log 2", log)
            with open(os.path.join(merged["session_dir"], "command_monitor.json"),
                      "r", encoding="utf-8") as stream:
                metadata = json.load(stream)
            self.assertEqual(metadata["source_chunk_ids"], ["chunk1", "chunk2"])
            # Source deletion is deliberately a later GUI step, only after a
            # fully written merged folder is returned.
            self.assertTrue(os.path.isdir(chunks[0]["session_dir"]))

    def test_runtime_snapshot_includes_story_and_za_infi_states(self):
        command = type("Story", (), {})()
        command.STATE_1_STORY_FUNCTION = {"A": object(), "B": object()}
        command._1_story_current_state = "B"
        command.STATE_ZA_INFI_MAIN_FUNCTION = {"LOOP": object()}
        command.za_infi_main_current_state = "LOOP"
        self.assertEqual(runtime_state_snapshot(command), {
            "STATE_1_STORY_FUNCTION": "B",
            "STATE_ZA_INFI_MAIN_FUNCTION": "LOOP",
        })

    def test_runtime_snapshot_accepts_legacy_mixed_case_state_attribute(self):
        command = type("Story", (), {})()
        command.STATE_COMMON_FUNCTION = {"COMMON_START": object()}
        command.Common_current_state = "COMMON_START"
        self.assertEqual(runtime_state_snapshot(command), {
            "STATE_COMMON_FUNCTION": "COMMON_START",
        })

    def test_two_step_loop_counts_as_two_unique_steps_and_detects_three_cycles(self):
        timeline = CommandStateTimeline(loop_cycles=3)
        for now, value in enumerate(("A", "B", "A", "B", "A", "B")):
            result = timeline.add({"STATE": value}, now)
        self.assertTrue(result["loop_started"])
        self.assertEqual(timeline.active_loop["period"], 2)
        self.assertEqual(timeline.recent_unique_cutoff(5), 0.0)
        self.assertEqual(timeline.recent_loop_cutoff(3), 0.0)

    def test_loop_anchor_is_released_after_different_step(self):
        timeline = CommandStateTimeline(loop_cycles=3)
        for now, value in enumerate(("A", "B", "A", "B", "A", "B")):
            timeline.add({"STATE": value}, now)
        result = timeline.add({"STATE": "C"}, 6)
        self.assertTrue(result["loop_ended"])
        self.assertIsNone(timeline.active_loop)

    def test_long_same_step_keeps_time_window_even_without_transitions(self):
        timeline = CommandStateTimeline(loop_cycles=3)
        timeline.add({"STATE": "LONG"}, 0)
        retention = timeline.retention(
            600, keep_unique_steps=5, long_step_seconds=180, loop_cycles=3)
        self.assertEqual(retention["keep_after"], 420.0)

    def test_relevant_path_hides_idle_sibling_state_machines(self):
        snapshot = {
            "STATE_MAIN_FUNCTION": "MAIN_2_Y_LANK",
            "STATE_2_STORY_FUNCTION": "2_STORY_ZA_INFI",
            "STATE_ZA_INFI_MAIN_FUNCTION": "ZA_INFI_MAIN_BATTLE_LOOP",
            "STATE_BENCH_FUNCTION": "BENCH_START",
            "STATE_BATTLE_FUNCTION": "BATTLE_MOVE",
            "STATE_QUASAR_FUNCTION": "QUASAR_START",
        }
        self.assertEqual(relevant_state_path(snapshot), [
            "MAIN_2_Y_LANK", "2_STORY_ZA_INFI",
            "ZA_INFI_MAIN_BATTLE_LOOP", "BATTLE_MOVE",
        ])

    def test_previous_session_retention_discards_old_unpinned_chunks(self):
        chunks = [{
            "id": str(index), "states": ["STEP_{}".format(index % 2)],
            "duration_saved": 30.0, "pinned": False,
        } for index in range(12)]
        kept = historical_retention_ids(
            chunks, keep_unique_steps=5, long_step_seconds=180, loop_cycles=3)
        self.assertEqual(kept, {"6", "7", "8", "9", "10", "11"})

    def test_stop_cleanup_selects_only_current_run_unprotected_chunks(self):
        chunks = [
            {"id": "current", "command_session_id": "run-2", "pinned": False},
            {"id": "protected", "command_session_id": "run-2", "pinned": True},
            {"id": "previous", "command_session_id": "run-1", "pinned": False},
            {"id": "loaded", "command_session_id": "run-2", "pinned": False,
             "historical": True},
            {"id": "legacy", "pinned": False},
        ]
        self.assertEqual(
            temporary_chunk_ids_for_session(chunks, "run-2"), {"current"})
        self.assertEqual(temporary_chunk_ids_for_session(chunks, ""), set())


class PackageVersionCompatibilityTests(unittest.TestCase):
    def test_requirement_name_supports_versions_and_environment_markers(self):
        self.assertEqual(
            requirement_distribution_name(
                'pygame-ce>=2.5; python_version >= "3.14"'),
            "pygame-ce")
        self.assertEqual(requirement_distribution_name("# comment"), "")

    def test_standard_library_distribution_lookup_does_not_need_pkg_resources(self):
        self.assertIsNotNone(installed_distribution_version("pip"))


class MultiInstanceResponsivenessTests(unittest.TestCase):
    def test_full_rate_choice_belongs_to_each_input_set(self):
        self.assertIn("last_active_preview_full_fps", INPUT_SET_VARIABLES)

    def test_preview_rendering_is_throttled_without_reducing_capture_callbacks(self):
        self.assertAlmostEqual(preview_render_interval(60, True, True), 1.0 / 30)
        self.assertAlmostEqual(
            preview_render_interval(60, True, True, full_rate=True), 1.0 / 60)
        self.assertEqual(preview_render_interval(60, False, True), 0.2)
        # Minimized windows stay inexpensive even when full-rate display was
        # requested; recording runs on the separate listener path.
        self.assertEqual(
            preview_render_interval(60, True, False, full_rate=True), 0.5)
        self.assertEqual(preview_render_interval(60, False, False), 0.5)


class SharedDebugLibraryTests(unittest.TestCase):
    def test_two_pokecon_instances_can_read_the_same_debug_set(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "shared_debug.json")
            first = write_shared_debug(
                "ZA_story", [{"id": "step-1", "state": "STEP_A"}],
                [{"id": "replace-1", "function_replacement": True}],
                path=path, writer="PokeCon A",
                controller_recordings={"hotel_move": {"lines": ["0.0: LX MIN"]}})
            loaded = read_shared_debug("ZA_story", path=path)
            self.assertEqual(first["revision"], 1)
            self.assertEqual(loaded["step_debug_rules"][0]["state"], "STEP_A")
            self.assertEqual(
                loaded["function_replacements"][0]["id"], "replace-1")
            self.assertIn("hotel_move", loaded["controller_recordings"])

            second = write_shared_debug(
                "ZA_story", [{"id": "step-1", "state": "STEP_B"}], [],
                path=path, writer="PokeCon B")
            self.assertEqual(second["revision"], 2)
            self.assertEqual(
                read_shared_debug("ZA_story", path=path)["step_debug_rules"][0]["state"],
                "STEP_B")

    def test_updating_one_shared_name_preserves_other_names(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "shared_debug.json")
            write_shared_debug("Switch 1", [{"state": "A"}], [], path=path)
            write_shared_debug("Switch 2", [{"state": "B"}], [], path=path)
            write_shared_debug("Switch 1", [{"state": "C"}], [], path=path)
            self.assertEqual(read_shared_debug("Switch 1", path=path)["revision"], 2)
            self.assertEqual(
                read_shared_debug("Switch 2", path=path)["step_debug_rules"][0]["state"],
                "B")

    def test_stale_pokecon_cannot_silently_overwrite_newer_revision(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "shared_debug.json")
            first = write_shared_debug("ZA", [{"state": "A"}], [], path=path)
            write_shared_debug(
                "ZA", [{"state": "B"}], [], path=path,
                expected_revision=first["revision"])
            with self.assertRaises(SharedDebugConflictError):
                write_shared_debug(
                    "ZA", [{"state": "STALE"}], [], path=path,
                    expected_revision=first["revision"])
            self.assertEqual(
                read_shared_debug("ZA", path=path)["step_debug_rules"][0]["state"],
                "B")

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


class SourceFunctionToolsTests(unittest.TestCase):
    SOURCE = '''
import time
from Commands.Keys import Button

class Demo:
    def move_old(self):
        self.move_old()
        label = "move_old"
        # move_old remains in comments
        return label

    def keep(self):
        return self.move_old
'''

    def test_discovers_class_functions_and_builds_bulk_names(self):
        records = source_function_records(self.SOURCE)
        self.assertEqual([item["name"] for item in records], ["move_old", "keep"])
        self.assertEqual(
            build_rename_map(["move_old"], "_old", "", prefix="ZA_"),
            {"move_old": "ZA_move"},
        )

    def test_whole_name_replace_does_not_touch_similar_function_names(self):
        self.assertEqual(
            build_rename_map(
                ["markerdir", "load_markerdir", "markerdir_sub"],
                "markerdir", "ZA_markerdir", whole_name=True),
            {
                "markerdir": "ZA_markerdir",
                "load_markerdir": "load_markerdir",
                "markerdir_sub": "markerdir_sub",
            },
        )

    def test_step_functions_are_identified_for_optional_hiding(self):
        source = '''
class Story:
    STEP_LABELS = ["one"]
    STEP_KEYS = ["1"]

    def __init__(self):
        self.STATE_STORY_FUNCTION = {
            "STORY_A": self.story_a,
        }

    def story_a(self):
        pass

    def _step_1(self):
        pass

    def helper(self):
        pass
'''
        self.assertEqual(step_function_names(source), {"story_a", "_step_1"})

    def test_bulk_rename_updates_definition_and_references_not_text(self):
        updated = rename_source_functions(self.SOURCE, {"move_old": "move_new"})
        compile(updated, "<renamed>", "exec")
        self.assertIn("def move_new(self):", updated)
        self.assertEqual(updated.count("self.move_new"), 2)
        self.assertIn('label = "move_old"', updated)
        self.assertIn("# move_old remains in comments", updated)

    def test_registers_renamed_function_as_editable_sample(self):
        with tempfile.TemporaryDirectory() as root:
            created = register_source_functions(
                self.SOURCE, ["move_old"], root, folder="Imported/Movement",
                rename_map={"move_old": "ZA_move"}, tags=["source", "move"],
                source_path="Demo.py")
            self.assertEqual(len(created), 1)
            with open(created[0]["metadata_path"], "r", encoding="utf-8") as stream:
                metadata = json.load(stream)
            with open(created[0]["body_path"], "r", encoding="utf-8") as stream:
                body = stream.read()
            self.assertEqual(metadata["name"], "ZA_move")
            self.assertEqual(metadata["source"]["function"], "move_old")
            self.assertIn("from Commands.Keys import Button", metadata["imports"])
            self.assertIn("def ZA_move(self):", body)
            self.assertIn("self.ZA_move()", body)


class TriggerTests(unittest.TestCase):
    def test_state_variable_names_are_discovered(self):
        source = '''
class Story:
    def __init__(self):
        self.STATE_MAIN_FUNCTION = {"MAIN": self.main}
        self.STATE_1_STORY_FUNCTION = {"1_STORY_A": self.story}
        self.unrelated = {"x": 1}
'''
        self.assertEqual(discover_state_variables(source), [
            "STATE_1_STORY_FUNCTION", "STATE_MAIN_FUNCTION"])

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
