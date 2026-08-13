import datetime
import ast
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
from CommandRunOptions import (apply_command_run_options,
                               apply_profile_to_dialogue_result,
                               discover_command_run_options,
                               preserve_location_selection,
                               perform_failure_save_recovery)
from ControllerInputLog import (python_replacement_body, replay_recording,
                                rotate_log_range, rotate_serial_message)
from DiskSpaceGuard import disk_space_violations
from SampleFunctionSync import (compare_folder as compare_sample_function_folder,
                                comparison_source_text,
                                create_sample_sync_backup,
                                function_records as sample_sync_function_records,
                                latest_sample_sync_backup,
                                merge_sample_names_with_source_bodies,
                                reflect_fragment_function_text,
                                fragment_function_stats,
                                remove_fragment_function_text,
                                replace_fragment_function_text,
                                replace_class_functions,
                                restore_sample_sync_backup,
                                side_by_side_diff_rows,
                                source_paths_for_folder,
                                update_fragments as update_sample_fragments,
                                update_source as update_source_from_samples)
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
from SourceDependencyTools import (analyze_source_dependencies,
                                   analyze_state_dictionary_dependencies,
                                   compare_preview_functions,
                                   compare_preview_support,
                                   generate_state_machine_main,
                                   merge_preview_functions_safely,
                                   merge_preview_support_safely,
                                   register_dependency_group,
                                   state_dictionary_current_state,
                                   state_dictionary_handlers,
                                   state_dictionary_names,
                                   suggest_state_dictionary)
from SampleLibrary import compose_preview, save_library
from SampleOriginSync import (apply_sample_list_to_origins,
                              compare_sample_list_origins,
                              restore_origin_sync_backup)
from SharedDebugLibrary import (SharedDebugConflictError, read_shared_debug,
                                write_shared_debug)
from QuickActions import ACTION_BY_ID, normalize_action_ids, normalize_position
from InputSetData import (INPUT_SET_VARIABLES, SCHEMA_VERSION,
                          has_complete_snapshot, legacy_combined_snapshot,
                          input_set_commands_enabled, strip_commands_from_snapshot,
                          snapshot_values_with_defaults,
                          sync_command_start_overrides, sync_commands_assist_rules,
                          sync_output_layout,
                          sync_quick_actions,
                          sync_step_debug_rules)
from SoftwareControllerState import SoftwareControllerState
from InputSetRuntimeRegistry import (ActiveInputSetRegistry,
                                     canonical_device_key,
                                     default_window_activity_registry_path,
                                     device_usage_conflicts,
                                     main_resource_conflicts,
                                     process_identity, read_active_input_sets)
from ResourceControl import (clamp_cpu_target, resource_throttle_level,
                             throttle_multiplier)
from ImageDetectionMonitor import (filter_target_names, format_show_value_entries,
                                   load_detection_library,
                                   padded_search_crop,
                                   prune_show_value_entries,
                                   update_show_value_entries)
from ImageHealthCheck import audit_image_library, suggested_crop
from ImageCheckReferenceAudit import (audit_image_check_references,
                                      merge_library_targets_into_source,
                                      preserve_library_import_block)
from ImageDetectionLibrary import generate_image_check
from CompletionEngine import CompletionEngine
from PokeConShowInfo import (installed_distribution_version,
                             requirement_distribution_name)
from UiResponsiveness import preview_capture_interval, preview_render_interval
from CommandMonitorRecording import (CommandInputActivityTracker,
                                     CommandStateTimeline, DarkStillFrameDetector,
                                     command_source_descriptor,
                                     failure_evidence_end,
                                     runtime_execution_location,
                                     historical_retention_ids,
                                     relevant_state_path,
                                     runtime_state_snapshot,
                                     temporary_chunk_ids_for_session)
from CommandRecordingMerge import merge_command_recording_chunks
from OperationCaptureSession import (OperationCaptureSession,
                                     decode_serial_message,
                                     find_paused_session, load_manifest,
                                     operation_input_source_is_recordable,
                                     paused_session_names,
                                     remove_session_directory)
from PythonSourceSafety import (normalize_and_compile_python,
                                normalize_python_indentation)
from OperationGamepadMap import (OperationGamepadMapDialog,
                                 OperationGamepadProfileStore,
                                 controls_for_token,
                                 gamepad_axis_token,
                                 normalize_gamepad_mapping,
                                 opposite_axis_tokens)
from OperationSessionModel import (GENERATION_TARGET_PORTABLE,
                                   STICK_MODE_EIGHT_WAY, STICK_MODE_EXACT,
                                   compact_line_ranges, generate_intermediate, pending_lines,
                                   input_row_is_commands_recordable,
                                   operation_video_sources,
                                   quantize_serial_stick_message,
                                   replace_generated_region, save_mappings,
                                   semantic_controls, source_class_names)
from OperationVisionSample import (generate_vision_sample,
                                   vision_output_paths)
from OperationDebugCommand import (create_debug_command_package,
                                   build_debug_draft_mappings,
                                   debug_output_paths, deploy_debug_command,
                                   intermediate_revisions,
                                   save_intermediate_revision)
from CommandRecordingModel import (filtered_timeline, load_command_timeline,
                                   source_function_block, timeline_page)
from Commands.CommandBase import Command
from Commands.Keys import Button, Direction, Hat, KeyPress, Stick
try:
    from Commands.ProController import ProController
except ModuleNotFoundError as error:
    if error.name != "pygame":
        raise
    with mock.patch.dict(sys.modules, {"pygame": mock.MagicMock()}):
        from Commands.ProController import ProController
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


class CommandRunOptionsTests(unittest.TestCase):
    def test_filtering_end_chapter_does_not_reset_selected_start(self):
        selected_start = "2_STORY_TOWER_79"
        visible_end_candidates = ["7_STORY_START_CHECK", "7_STORY_END"]
        self.assertEqual(
            preserve_location_selection(
                selected_start, visible_end_candidates),
            selected_start)
        self.assertEqual(
            preserve_location_selection("", visible_end_candidates),
            "7_STORY_START_CHECK")
        self.assertEqual(
            preserve_location_selection(
                "（終了場所を指定しない）", visible_end_candidates,
                "（終了場所を指定しない）"),
            "（終了場所を指定しない）")

    def test_za_tower_step_is_exposed_for_both_run_location_pickers(self):
        path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "SerialController", "Commands",
            "PythonCommands", "ZA", "ZA_story", "ZA_story.py"))
        with open(path, "r", encoding="utf-8-sig") as stream:
            result = discover_command_run_options(
                stream.read(), class_name="ZA_story")
        item = next(row for row in result["locations"]
                    if row.get("value") == "2_STORY_TOWER_79")
        self.assertTrue(result["enabled"])
        self.assertEqual(item["label"], "2_STORY_TOWER_79")
        self.assertEqual(item["variable"], "STATE_2_STORY_FUNCTION")

    def test_discovers_numbered_routes_and_debug_like_frlg(self):
        source = '''
class Story:
    def do(self):
        self.cb_restart_flag = [
            " 0: 最初～町", " 1: 町～ジム", " 2: 終了"]
        self.DEBUG = False
'''
        result = discover_command_run_options(source)
        self.assertEqual(
            [(row["value"], row["description"])
             for row in result["locations"]],
            [(0, "最初～町"), (1, "町～ジム"), (2, "終了")])
        self.assertEqual(result["locations"][0]["end_variable"], "stop_flag")
        self.assertEqual(
            [row["attribute"] for row in result["debug_options"]], ["DEBUG"])

    def test_discovers_step_labels_and_state_docstrings(self):
        step = discover_command_run_options('''
class StepDemo:
    STEP_LABELS = ["準備", "実行"]
    STEP_KEYS = ["READY", "RUN"]
''')
        self.assertEqual(
            [row["value"] for row in step["locations"]], [0, 1])
        state = discover_command_run_options('''
class StateDemo:
    def __init__(self):
        self.STATE_MAIN_FUNCTION = {"START": self.start}
    def start(self):
        """開始画面から町まで進める"""
        return "START"
''')
        self.assertEqual(state["locations"][0]["description"],
                         "開始画面から町まで進める")

    def test_commands_owned_popup_flag_and_inherited_states_are_discovered(self):
        result = discover_command_run_options('''
class StoryBase:
    COMMAND_RUN_SETTINGS = True
    COMMAND_STEP_DESCRIPTIONS = {"START": "最初の町から開始"}
    def __init__(self):
        self.STATE_MAIN_FUNCTION = {"START": self.start, "END": self.end}
        self.DEBUG = False
    def start(self): return "END"
    def end(self): return "END"
class Story(StoryBase):
    NAME = "Story"
''', class_name="Story")
        self.assertTrue(result["enabled"])
        self.assertEqual([item["value"] for item in result["locations"]],
                         ["START", "END"])
        self.assertEqual(result["locations"][0]["description"],
                         "最初の町から開始")
        self.assertEqual(result["debug_options"][0]["attribute"], "DEBUG")

    def test_applies_step_debug_user_and_legacy_dialogue_values(self):
        class Demo:
            step = 0
        command = Demo()
        route = {
            "mode": "attribute", "variable": "restart_flag",
            "end_variable": "stop_flag", "value": 3,
            "dialog_value": " 3: 町～森", "dialog_start_index": 0,
            "dialog_end_index": 1, "label": "3: 町～森"}
        config = {
            "start": route, "end": dict(route), "debug": {"DEBUG": True},
            "save_delete_user_number": 7, "retry_on_failure": False}
        apply_command_run_options(command, config)
        self.assertEqual(command.restart_flag, 3)
        self.assertEqual(command.stop_flag, 3)
        self.assertTrue(command.DEBUG)
        self.assertEqual(command.save_delete_user_number, 7)
        result = apply_profile_to_dialogue_result(
            command,
            [["Combo", "スタート番号"], ["Combo", "ストップ番号"],
             ["Check", "DEBUG"]],
            ["old-start", "old-end", False])
        self.assertEqual(result, [" 3: 町～森", " 3: 町～森", True])

    def test_state_and_step_end_hooks_stop_after_successful_handler(self):
        class StateCommand:
            def __init__(self):
                self.events = []
                self.STATE_MAIN_FUNCTION = {
                    "START": self.start, "END": self.end}

            def start(self):
                self.events.append("start")
                return "END"

            def end(self):
                self.events.append("end")
                return "DONE"

            def sendStopRequest(self):
                self.events.append("stop")

        state_command = StateCommand()
        apply_command_run_options(state_command, {"end": {
            "kind": "state", "mode": "state",
            "variable": "STATE_MAIN_FUNCTION", "value": "END"}})
        self.assertEqual(state_command.STATE_MAIN_FUNCTION["END"](), "DONE")
        self.assertEqual(state_command.events, ["end", "stop"])

        class StepCommand:
            def __init__(self):
                self.events = []

            def _step_1(self):
                self.events.append("step")
                return 2

            def sendStopRequest(self):
                self.events.append("stop")

        step_command = StepCommand()
        apply_command_run_options(step_command, {"end": {
            "kind": "step", "mode": "attribute",
            "variable": "step", "value": 1}})
        self.assertEqual(step_command._step_1(), 2)
        self.assertEqual(step_command.events, ["step", "stop"])

    def test_failure_recovery_requires_hook_and_obeys_retry_limit(self):
        class Recoverable:
            def __init__(self):
                self.calls = []
                self._command_run_profile = {
                    "retry_on_failure": True, "max_retries": 1,
                    "recovery_method": "delete_save_for_user",
                    "save_delete_user_number": 4}
                self._command_failure_recovery_attempts = 0
            def delete_save_for_user(self, user_number):
                self.calls.append(user_number)
        command = Recoverable()
        self.assertTrue(perform_failure_save_recovery(command, RuntimeError()))
        self.assertEqual(command.calls, [4])
        self.assertFalse(perform_failure_save_recovery(command, RuntimeError()))


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

    def test_device_usage_is_shared_and_current_instance_is_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, "active_windows.json")
            provider = lambda pid: "{}:start".format(pid)
            first = ActiveInputSetRegistry(
                path, profile="one", identity_provider=provider,
                token="first", pid=601)
            second = ActiveInputSetRegistry(
                path, profile="two", identity_provider=provider,
                token="second", pid=602)
            camera_key = canonical_device_key("camera", "USB Capture A")
            first.mark_focused(marker=100)
            first.set_device("camera", camera_key, "USB Capture A")
            second.mark_focused(marker=200)
            conflicts = device_usage_conflicts(
                second.entries(include_self=False), "camera", camera_key)
            self.assertEqual([item["pid"] for item in conflicts], [601])
            self.assertEqual(conflicts[0]["devices"]["camera"]["label"],
                             "USB Capture A")
            self.assertTrue(second.is_last_focused())
            first.set_active("Profile B", "Combined B")
            conflicts = device_usage_conflicts(
                second.entries(include_self=False), "camera", camera_key)
            self.assertEqual([item["pid"] for item in conflicts], [601])
            self.assertEqual(conflicts[0]["input_set"], "Profile B")
            self.assertEqual(conflicts[0]["devices"]["camera"]["label"],
                             "USB Capture A")
            first.set_active("")
            conflicts = device_usage_conflicts(
                second.entries(include_self=False), "camera", camera_key)
            self.assertEqual([item["pid"] for item in conflicts], [601])
            self.assertEqual(conflicts[0]["input_set"], "")
            first.set_device("camera", "", "")
            self.assertEqual(device_usage_conflicts(
                second.entries(include_self=False), "camera", camera_key), [])

    def test_main_resource_role_is_unique_across_processes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, "active_windows.json")
            provider = lambda pid: "{}:start".format(pid)
            first = ActiveInputSetRegistry(
                path, identity_provider=provider, token="first", pid=701)
            second = ActiveInputSetRegistry(
                path, identity_provider=provider, token="second", pid=702)
            self.assertTrue(first.set_resource_state(main_requested=True))
            self.assertFalse(second.set_resource_state(main_requested=True))
            conflicts = main_resource_conflicts(second.entries(include_self=False))
            self.assertEqual([item["pid"] for item in conflicts], [701])
            first.close()
            self.assertTrue(second.set_resource_state(main_requested=True))


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
                       "step_debug_skip_confirm": True,
                       "operation_capture_last_session": "D:/operation"},
            "command_selection": {"python": "ZA_story"},
            "shortcuts": {"1": {"class": "Python", "name": "ZA_story"}},
            "commands_assist": {"step_debug_rules": [{"state": "STEP_A"}]},
            "controller_recordings": {"move": {}},
            "operation_capture": {"output_dir": "D:/recordings"},
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
                    "controller_recordings", "operation_capture"):
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
            "variable": "STATE_1_STORY_FUNCTION", "state": "1_STORY_STEP_B",
            "start": {
                "id": "state:STATE_1_STORY_FUNCTION:1_STORY_STEP_B",
                "mode": "state", "variable": "STATE_1_STORY_FUNCTION",
                "value": "1_STORY_STEP_B", "label": "ホテルを出る"},
            "end": {
                "id": "state:STATE_1_STORY_FUNCTION:1_STORY_STEP_D",
                "mode": "state", "variable": "STATE_1_STORY_FUNCTION",
                "value": "1_STORY_STEP_D", "label": "広場へ移動"},
            "debug": {"fastread": True, "TESTADDCODE": False},
            "save_delete_user_number": 2,
            "retry_on_failure": True,
            "recovery_method": "delete_save_for_user",
            "max_retries": 2,
        }}
        self.assertTrue(sync_command_start_overrides(data, "Switch", overrides))
        item = data["input_sets"]["Switch"]
        self.assertEqual(item["commands_assist"]["start_overrides"], overrides)
        self.assertEqual(
            item["all_tabs"]["commands_assist"]["start_overrides"], overrides)

    def test_command_run_favorites_are_mirrored_to_input_set(self):
        data = {"input_sets": {"Switch": {
            "commands": {"enabled": True}, "all_tabs": {}}}}
        overrides = {"ZA_story": {"start": {"id": "step-a"}}}
        favorites = {"ZA_story": [
            {"name": "ホテルから", "config": {
                "start": {"id": "step-a"}, "end": {"id": "step-c"}}},
            {"name": "バトル確認", "config": {
                "start": {"id": "step-b"}, "debug": {"fastread": True}}},
        ]}
        self.assertTrue(sync_command_start_overrides(
            data, "Switch", overrides, favorites=favorites))
        item = data["input_sets"]["Switch"]
        self.assertEqual(item["commands_assist"]["run_favorites"], favorites)
        self.assertEqual(
            item["all_tabs"]["commands_assist"]["run_favorites"], favorites)
        favorites["ZA_story"][0]["name"] = "changed"
        self.assertEqual(
            item["commands_assist"]["run_favorites"]["ZA_story"][0]["name"],
            "ホテルから")

    def test_manual_control_choices_belong_to_input_set(self):
        for name in (
                "is_use_keyboard", "is_use_left_stick_mouse",
                "is_use_right_stick_mouse", "pc_gamepad",
                "is_record_Pro_Controller", "is_use_Pro_Controller",
                "pc_gamepad_input_enabled"):
            self.assertIn(name, INPUT_SET_VARIABLES)
        snapshot = {
            "commands_enabled": False,
            "manual_control": {
                "hardware_enabled": True, "input_permission": True,
                "gamepad": "0: Controller"},
            "commands_assist": {"start_overrides": {"Story": {}}},
        }
        stripped = strip_commands_from_snapshot(snapshot)
        self.assertNotIn("commands_assist", stripped)
        self.assertEqual(stripped["manual_control"], snapshot["manual_control"])

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

    def test_log_boundary_sliders_are_mirrored_to_loaded_input_set(self):
        data = {"input_sets": {"Switch": {"all_tabs": {
            "values": {"fps": "60", "panel_ratio": 50},
        }}}}
        sliders = {
            "side_width_balance": 63,
            "panel_ratio": 42,
            "right_panel_ratio": 71,
        }
        self.assertTrue(sync_output_layout(data, "Switch", sliders))
        values = data["input_sets"]["Switch"]["all_tabs"]["values"]
        self.assertEqual(values["fps"], "60")
        self.assertEqual(
            {name: values[name] for name in sliders}, sliders)

    def test_log_boundary_sync_does_not_convert_legacy_input_set(self):
        data = {"input_sets": {"Legacy": {"camera": {}}}}
        self.assertFalse(sync_output_layout(
            data, "Legacy", {"side_width_balance": 60}))
        self.assertNotIn("all_tabs", data["input_sets"]["Legacy"])

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
        for required in ("side_width_balance", "panel_ratio", "right_panel_ratio",
                         "show_python_samples", "is_win_notification_start",
                         "object_detection_threshold", "step_debug_skip_confirm",
                         "window_capture_mode", "record_monitor_chunk_seconds",
                         "record_monitor_keep_steps", "record_monitor_loop_cycles",
                          "record_monitor_long_seconds",
                          "record_monitor_failure_tail_seconds",
                          "record_monitor_auto_arm",
                          "record_monitor_confirm_delete_on_stop",
                          "operation_capture_output_dir",
                          "operation_capture_include_audio",
                          "operation_capture_auto_controller",
                          "operation_capture_last_session"):
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

    def test_area_capture_registration_adds_arrow_move_margin(self):
        self.assertEqual(
            padded_search_crop((421, 184, 455, 54), 5, (720, 1280, 3)),
            [416, 179, 881, 243])

    def test_area_capture_registration_margin_is_clamped_to_frame(self):
        self.assertEqual(
            padded_search_crop((2, 3, 1277, 716), 5, (720, 1280, 3)),
            [0, 0, 1280, 720])

    def test_show_values_are_kept_separately_and_stale_names_disappear(self):
        entries = {}
        update_show_value_entries(entries, {
            "name": "FIELD", "score": 0.7, "threshold": 0.8,
            "matched": False, "position": (10, 20), "source": "Commands",
        }, now=10.0)
        update_show_value_entries(entries, {
            "name": "MENU", "variant": "2", "score": 0.9,
            "threshold": 0.85, "matched": True, "position": (30, 40),
            "source": "Commands",
        }, now=12.0)
        text = format_show_value_entries(entries, "ShowValue")
        self.assertIn("[ShowValue] FIELD", text)
        self.assertIn("[ShowValue] MENU / パターン2", text)
        self.assertIn("\n\n[ShowValue] MENU", text)

        removed = prune_show_value_entries(entries, 5.0, now=16.0)
        self.assertEqual(removed, [("FIELD", "")])
        self.assertNotIn("FIELD", format_show_value_entries(entries))
        self.assertIn("MENU", format_show_value_entries(entries))
        self.assertEqual(prune_show_value_entries(entries, 5.0, now=18.0), [
            ("MENU", "2")])
        self.assertEqual(format_show_value_entries(entries), "")

    def test_repeated_show_value_updates_replace_only_the_same_image(self):
        entries = {}
        update_show_value_entries(entries, {
            "name": "FIELD", "score": 0.1, "threshold": 0.8,
        }, now=1.0)
        update_show_value_entries(entries, {
            "name": "MENU", "score": 0.2, "threshold": 0.8,
        }, now=2.0)
        update_show_value_entries(entries, {
            "name": "FIELD", "score": 0.95, "threshold": 0.8,
            "matched": True,
        }, now=3.0)
        self.assertEqual(list(entries), [("MENU", ""), ("FIELD", "")])
        text = format_show_value_entries(entries)
        self.assertNotIn("0.100000", text)
        self.assertIn("0.950000", text)

    def test_za_kohuki_get5_uses_the_fifth_slot_as_a_separate_target(self):
        profile_path = os.path.join(
            SERIAL_CONTROLLER, "Template", "image_detection_profiles.json")
        with open(profile_path, "r", encoding="utf-8") as stream:
            library = json.load(stream)

        targets = library["targets"]
        get4 = targets["POKEMON_ZA_KOHUKI_ICON_GET4"]["variants"][0]
        get5 = targets["POKEMON_ZA_KOHUKI_ICON_GET5"]["variants"][0]
        fifth_slot_reference = targets["POKEMON_ZA_MERIP_ICON_GET5"]["variants"][0]
        self.assertEqual(get5["crop"], fifth_slot_reference["crop"])
        self.assertNotEqual(get5["crop"], get4["crop"])
        self.assertEqual(get5["template_path"], get4["template_path"])

        folder_members = library["lists"]["POKEMON_ZA_FOLDER_1_Z_LANK"]["members"]
        member_ids = {member["id"] for member in folder_members
                      if member.get("type") == "target"}
        self.assertIn("POKEMON_ZA_KOHUKI_ICON_GET5", member_ids)

        generated = generate_image_check(library, "POKEMON_ZA_ALL", "list")
        self.assertIn("POKEMON_ZA_KOHUKI_ICON_GET5", generated)

        source_path = os.path.join(
            SERIAL_CONTROLLER, "Commands", "PythonCommands", "ZA",
            "ZA_story", "ZA_story.py")
        with open(source_path, "r", encoding="utf-8-sig") as stream:
            source = stream.read()
        self.assertIn(
            'IMAGE_DETECTION_TARGETS["POKEMON_ZA_KOHUKI_ICON_GET5"]', source)
        self.assertRegex(
            source,
            r'image_check\("POKEMON_ZA_KOHUKI_ICON_GET4"\)\s*'
            r'and self\.image_check\("POKEMON_ZA_KOHUKI_ICON_GET5"\)')


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


class ImageCheckReferenceAuditTests(unittest.TestCase):
    def test_missing_literal_is_compared_with_all_runtime_registration_forms(self):
        source = '''
class Command:
    IMAGE_DETECTION_TARGETS = {"READY": [{}]}
    IMAGE_DETECTION_TARGETS["EXTRA"] = [{}]
    IMAGE_DETECTION_TARGETS.update({"UPDATED": [{}]})
    IMAGE_DETECTION_SETS = {"ANY_READY": {"members": []}}

    def image_check_exception(self, targetimage):
        if targetimage in ("TRUE_RETURN", "FALSE_RETURN"):
            return targetimage == "TRUE_RETURN"
        return False

    def run(self, selected):
        self.image_check("READY")
        self.image_check("EXTRA")
        self.image_check("UPDATED")
        self.image_check("ANY_READY")
        self.image_check("TRUE_RETURN")
        self.image_check("MISSING")
        self.image_check(selected)
'''
        result = audit_image_check_references(source)
        self.assertEqual([row["name"] for row in result["missing"]], ["MISSING"])
        self.assertEqual(result["dynamic"][0]["expression"], "selected")
        resolved = {row["name"]: row["resolved_by"] for row in result["references"]}
        self.assertEqual(resolved["READY"], "画像検知")
        self.assertEqual(resolved["ANY_READY"], "検知セット")
        self.assertEqual(resolved["TRUE_RETURN"], "例外判定")

    def test_duplicate_references_keep_all_source_lines(self):
        source = '''
IMAGE_DETECTION_TARGETS = {}
image_check("LOST")
self.image_check("LOST")
'''
        result = audit_image_check_references(source)
        self.assertEqual(len(result["missing"]), 1)
        self.assertEqual(result["missing"][0]["lines"], [3, 4])
        self.assertEqual(result["missing"][0]["count"], 2)

    def test_invalid_python_is_reported_as_syntax_error(self):
        with self.assertRaises(SyntaxError):
            audit_image_check_references('self.image_check("BROKEN"')

    def test_registered_library_target_can_be_merged_without_replacing_existing_targets(self):
        source = '''
class Command:
    IMAGE_DETECTION_TARGETS = {"READY": [{"template_path": "ready.png"}]}
    IMAGE_DETECTION_OPERATORS = {"READY": "OR"}
    IMAGE_DETECTION_DESCRIPTIONS = {"targets": {"READY": "ready"}}

    def _image_check_target(self, targetimage):
        return targetimage in self.IMAGE_DETECTION_TARGETS

    def run(self):
        return self.image_check("MISSING")
'''
        library = {"targets": {"MISSING": {
            "operator": "AND", "description": "added from DevStudio",
            "variants": [{"template_path": "missing.png", "threshold": 0.8,
                          "health_ignored_warnings": ["low_contrast"]}],
        }}}
        updated, added = merge_library_targets_into_source(source, library, ["MISSING"])
        self.assertEqual(added, ["MISSING"])
        self.assertIn('IMAGE_DETECTION_TARGETS = {"READY"', updated)
        self.assertIn("POKECON_IMAGE_CHECK_LIBRARY_IMPORTS_BEGIN", updated)
        self.assertNotIn("health_ignored_warnings", updated)
        result = audit_image_check_references(updated)
        self.assertEqual(result["missing"], [])
        self.assertIn("MISSING", result["target_names"])

    def test_multiple_merges_accumulate_and_generated_code_preserves_managed_block(self):
        source = '''
class Command:
    IMAGE_DETECTION_TARGETS = {}
    IMAGE_DETECTION_OPERATORS = {}
    IMAGE_DETECTION_DESCRIPTIONS = {"targets": {}}
    def _image_check_target(self, targetimage):
        return False
'''
        library = {"targets": {
            "ONE": {"operator": "OR", "description": "one",
                    "variants": [{"template_path": "one.png"}]},
            "TWO": {"operator": "OR", "description": "two",
                    "variants": [{"template_path": "two.png"}]},
        }}
        first, _ = merge_library_targets_into_source(source, library, ["ONE"])
        second, _ = merge_library_targets_into_source(first, library, ["TWO"])
        self.assertIn("'ONE'", second)
        self.assertIn("'TWO'", second)
        generated = '''
IMAGE_DETECTION_TARGETS = {"BASE": []}
IMAGE_DETECTION_OPERATORS = {"BASE": "OR"}
IMAGE_DETECTION_DESCRIPTIONS = {"targets": {}}
def _image_check_target(self, targetimage):
    return False
'''
        preserved = preserve_library_import_block(generated, second)
        self.assertIn("POKECON_IMAGE_CHECK_LIBRARY_IMPORTS_BEGIN", preserved)
        self.assertIn("'ONE'", preserved)
        self.assertIn("'TWO'", preserved)

    def test_merge_supports_older_generated_source_without_operator_dictionary(self):
        source = '''
class Command:
    IMAGE_DETECTION_TARGETS = {}
    IMAGE_DETECTION_DESCRIPTIONS = {"targets": {}}
    def _image_check_target(self, targetimage):
        return False
'''
        library = {"targets": {"MARKER": {
            "operator": "OR", "description": "marker",
            "variants": [{"template_path": "marker.png"}],
        }}}
        updated, _ = merge_library_targets_into_source(source, library, ["MARKER"])
        namespace = {}
        exec(compile(updated, "<old-generated-source>", "exec"), namespace)
        command = namespace["Command"]
        self.assertIn("MARKER", command.IMAGE_DETECTION_TARGETS)
        self.assertEqual(
            command.IMAGE_DETECTION_DESCRIPTIONS["targets"]["MARKER"], "marker")


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
        activities = []
        sender.set_activity_callback(
            lambda payload, priority: activities.append((payload, priority)))
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
        self.assertEqual(activities, [("manual", True), ("command", False)])
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

    def test_latest_software_controller_state_supersedes_delayed_press(self):
        state = SoftwareControllerState()
        press_version = state.update("hold", Button.A)
        release_version = state.update("holdEnd", Button.A)
        self.assertIsNone(state.snapshot_if_current(press_version))
        self.assertEqual(state.snapshot_if_current(release_version), ())

    def test_button_and_hat_with_same_integer_value_remain_distinct(self):
        class CaptureSender:
            def __init__(self):
                self.rows = []

            def writeRow(self, row, is_show=False, priority=False):
                self.rows.append(row)

        # Button.B and Hat.RIGHT are both int-backed value 2.  They must still
        # survive as two separate controls during a simultaneous GUI press.
        state = SoftwareControllerState()
        state.update("hold", Button.B)
        version = state.update("hold", Hat.RIGHT)
        controls = state.snapshot_if_current(version)
        self.assertEqual(len(controls), 2)

        sender = CaptureSender()
        keys = KeyPress(sender, priority=True)
        keys.replace_hold(controls)
        self.assertEqual(len(keys.holdButton), 2)
        packet = sender.rows[-1].split()
        self.assertEqual(int(packet[0], 16) >> 2, int(Button.B))
        self.assertEqual(packet[1], str(int(Hat.RIGHT)))

        keys.replace_hold([])
        neutral = sender.rows[-1].split()
        self.assertEqual(int(neutral[0], 16) >> 2, 0)
        self.assertEqual(neutral[1], str(int(Hat.CENTER)))

    def test_tuple_stick_position_does_not_flood_standard_output(self):
        logger = Direction(Stick.LEFT, (128, 127))._logger
        before = len(logger.handlers)
        with mock.patch("builtins.print") as output:
            for value in range(20):
                Direction(Stick.LEFT, (value, 127))
        output.assert_not_called()
        self.assertEqual(len(logger.handlers), before)


class CommandMonitorRecordingTests(unittest.TestCase):
    class _SolidFrame:
        shape = (40, 60, 3)

        def __init__(self, value):
            self.value = int(value)

        def __getitem__(self, _position):
            return (self.value, self.value, self.value)

    def test_ten_thousand_source_links_are_paged_without_truncation(self):
        events = [{
            "index": index, "video_time": index / 10.0,
            "event": "execution", "step_text": "STEP_{}".format(index % 5),
            "location": {"function": "move", "line": index},
        } for index in range(1, 10001)]
        filtered = filtered_timeline(events, "step_3")
        self.assertEqual(len(filtered), 2000)
        visible, page, page_count = timeline_page(events, page=19, page_size=500)
        self.assertEqual((page, page_count, len(visible)), (19, 20, 500))
        self.assertEqual(visible[-1]["index"], 10000)

    def test_recorded_function_block_works_on_python_37_ast_positions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "story.py")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(
                    "class Story(object):\n"
                    "    def move_to_hotel(self):\n"
                    "        value = 1\n"
                    "        return value\n")
            block = source_function_block(path, "move_to_hotel", 3)
            self.assertEqual((block["start_line"], block["end_line"]), (2, 4))
            self.assertIn("return value", block["text"])

    def test_running_command_location_links_to_user_function_without_source_edit(self):
        ready = threading.Event()
        release = threading.Event()

        def recorded_story_function():
            ready.set()
            release.wait(2.0)

        command = type("RecordedCommand", (), {"NAME": "Recorded"})()
        worker = threading.Thread(target=recorded_story_function)
        command.thread = worker
        worker.start()
        try:
            self.assertTrue(ready.wait(1.0))
            location = runtime_execution_location(
                command, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
            self.assertEqual(location["function"], "recorded_story_function")
            self.assertTrue(location["file"].endswith("test_automation_features.py"))
            descriptor = command_source_descriptor(command)
            self.assertEqual(descriptor["class"], "RecordedCommand")
        finally:
            release.set()
            worker.join(2.0)

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
                snapshot_relative = os.path.join(
                    "source_snapshots", "story{}.py".format(index))
                os.makedirs(os.path.join(session_dir, "source_snapshots"))
                with open(os.path.join(session_dir, snapshot_relative),
                          "w", encoding="utf-8") as stream:
                    stream.write("def step_{}(self):\n    pass\n".format(index))
                with open(os.path.join(session_dir, "steps.jsonl"),
                          "w", encoding="utf-8") as stream:
                    stream.write(json.dumps({
                        "event": "execution", "step_path": state,
                        "chunk_time": 1.25,
                        "location": {
                            "file": "story.py", "function": "step_{}".format(index),
                            "line": 1, "snapshot": snapshot_relative,
                        },
                    }) + "\n")
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
                    "source": {
                        "file": "story.py", "function": "step_{}".format(index),
                        "line": 1, "snapshot": snapshot_relative,
                    },
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
            timeline = load_command_timeline(merged["session_dir"])
            self.assertEqual(len(timeline), 2)
            self.assertEqual(timeline[0]["video_time"], 1.25)
            self.assertEqual(timeline[1]["video_time"], 4.25)
            self.assertTrue(os.path.isfile(os.path.join(
                merged["session_dir"], timeline[0]["location"]["snapshot"])))
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

    def test_unescaped_loop_keeps_five_preceding_steps_and_only_three_cycles(self):
        timeline = CommandStateTimeline(loop_cycles=3)
        values = ("P1", "P2", "P3", "P4", "P5",
                  "A", "B", "A", "B", "A", "B", "A", "B")
        for now, value in enumerate(values):
            timeline.add({"STATE": value}, now)
        retention = timeline.retention(
            120, keep_unique_steps=5, long_step_seconds=180, loop_cycles=3)
        self.assertEqual(retention["mode"], "loop")
        self.assertEqual(retention["keep_after"], 0.0)
        self.assertEqual(retention["keep_before"], 10.0)
        self.assertEqual(timeline.active_loop["period"], 2)

    def test_dark_still_failure_keeps_only_the_last_five_steps_to_detection(self):
        timeline = CommandStateTimeline(loop_cycles=3)
        for now, value in enumerate(("A", "B", "C", "D", "E", "F")):
            timeline.add({"STATE": value}, now)
        retention = timeline.retention(
            60, keep_unique_steps=5, long_step_seconds=180,
            loop_cycles=3, terminal_time=5.0)
        self.assertEqual(retention["mode"], "dark_still")
        self.assertEqual(retention["keep_after"], 1.0)
        self.assertEqual(retention["keep_before"], 5.0)

    def test_key_inactivity_waits_sixty_seconds_and_clears_on_recovery(self):
        tracker = CommandInputActivityTracker(timeout_seconds=60.0)
        tracker.reset(0.0)
        self.assertFalse(tracker.check(59.9)["stall_started"])
        stalled = tracker.check(60.0)
        self.assertTrue(stalled["stall_started"])
        self.assertEqual(stalled["active"]["started_at"], 0.0)
        tracker.mark_activity(61.0)
        recovered = tracker.check(61.0)
        self.assertTrue(recovered["recovered"])
        self.assertIsNone(recovered["active"])

    def test_key_inactivity_retention_ends_at_last_key_activity(self):
        timeline = CommandStateTimeline(loop_cycles=3)
        for now, value in enumerate(("A", "B", "C", "D", "E", "F")):
            timeline.add({"STATE": value}, now * 10.0)
        retention = timeline.retention(
            120, keep_unique_steps=5, long_step_seconds=180,
            terminal_time=50.0, terminal_mode="key_inactivity")
        self.assertEqual(retention["mode"], "key_inactivity")
        self.assertEqual(retention["keep_after"], 10.0)
        self.assertEqual(retention["keep_before"], 50.0)

    def test_failure_evidence_keeps_sixty_seconds_of_stalled_screen(self):
        self.assertEqual(failure_evidence_end(100.0, 125.0, 60.0), 125.0)
        self.assertEqual(failure_evidence_end(100.0, 200.0, 60.0), 160.0)
        timeline = CommandStateTimeline(loop_cycles=3)
        for now, value in enumerate(("A", "B", "C", "D", "E", "STUCK")):
            timeline.add({"STATE": value}, now * 20.0)
        cutoff = failure_evidence_end(100.0, 200.0, 60.0)
        retention = timeline.retention(
            200.0, keep_unique_steps=5, long_step_seconds=180,
            terminal_time=cutoff, terminal_mode="key_inactivity")
        self.assertEqual(retention["keep_before"], 160.0)
        self.assertEqual(retention["mode"], "key_inactivity")

    def test_dark_still_detector_ignores_bright_static_screen(self):
        detector = DarkStillFrameDetector(hold_seconds=2.0, sample_interval=0.5)
        bright = self._SolidFrame(180)
        results = [detector.add(bright, index * 0.5) for index in range(8)]
        self.assertFalse(any(result.get("stall_started") for result in results))
        self.assertIsNone(detector.active)

    def test_dark_still_detector_marks_failure_then_recovers_on_change(self):
        detector = DarkStillFrameDetector(hold_seconds=2.0, sample_interval=0.5)
        dark = self._SolidFrame(0)
        results = []
        for index in range(7):
            results.append(detector.add(dark, index * 0.5))
        self.assertTrue(any(result.get("stall_started") for result in results))
        self.assertIsNotNone(detector.active)
        changed = self._SolidFrame(160)
        recovered = detector.add(changed, 3.5)
        self.assertTrue(recovered["recovered"])
        self.assertIsNone(detector.active)

    def test_loop_anchor_is_released_after_different_step(self):
        timeline = CommandStateTimeline(loop_cycles=3)
        for now, value in enumerate(("A", "B", "A", "B", "A", "B")):
            timeline.add({"STATE": value}, now)
        result = timeline.add({"STATE": "C"}, 6)
        self.assertTrue(result["loop_ended"])
        self.assertIsNone(timeline.active_loop)
        retention = timeline.retention(
            10, keep_unique_steps=5, long_step_seconds=180, loop_cycles=3)
        self.assertEqual(retention["mode"], "normal")
        self.assertIsNone(retention["keep_before"])

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
            {"id": "trimmed", "command_session_id": "run-2", "pinned": False,
             "delete_pending": True},
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

    def test_resource_choices_belong_to_each_input_set(self):
        self.assertTrue({"resource_control_enabled", "resource_cpu_target",
                         "resource_main_tool"}.issubset(INPUT_SET_VARIABLES))

    def test_old_input_set_does_not_inherit_previous_main_resource_role(self):
        old_snapshot = {"values": {"fps": "30"}}
        restored = snapshot_values_with_defaults(old_snapshot)
        self.assertFalse(restored["resource_main_tool"])
        self.assertTrue(restored["resource_control_enabled"])
        self.assertEqual(restored["resource_cpu_target"], 90)

        saved_snapshot = {"values": {
            "resource_control_enabled": True,
            "resource_cpu_target": 80,
            "resource_main_tool": True,
        }}
        restored = snapshot_values_with_defaults(saved_snapshot)
        self.assertTrue(restored["resource_main_tool"])
        self.assertEqual(restored["resource_cpu_target"], 80)

        normal_snapshot = {"values": {
            "resource_control_enabled": True,
            "resource_cpu_target": 80,
            "resource_main_tool": False,
        }}
        restored = snapshot_values_with_defaults(normal_snapshot)
        self.assertFalse(restored["resource_main_tool"])

    def test_cpu_target_throttles_only_unprotected_non_main_work(self):
        self.assertEqual(clamp_cpu_target(120), 95)
        self.assertEqual(clamp_cpu_target(10), 50)
        self.assertEqual(
            resource_throttle_level(True, 91, 90, foreground=False), "strong")
        self.assertEqual(
            resource_throttle_level(True, 91, 90, foreground=True), "strong")
        self.assertEqual(
            resource_throttle_level(True, 87, 90, foreground=True), "light")
        self.assertEqual(
            resource_throttle_level(True, 99, 90, main_tool=True), "normal")
        self.assertEqual(
            resource_throttle_level(True, 99, 90, protected=True), "normal")
        self.assertEqual(throttle_multiplier("strong"), 8.0)

    def test_resource_multiplier_extends_background_preview_interval(self):
        self.assertEqual(
            preview_render_interval(
                60, False, True, resource_multiplier=4), 0.8)

    def test_preview_rendering_is_throttled_for_non_active_instances(self):
        self.assertAlmostEqual(preview_render_interval(60, True, True), 1.0 / 30)
        self.assertAlmostEqual(
            preview_render_interval(60, True, True, full_rate=True), 1.0 / 60)
        self.assertEqual(preview_render_interval(60, False, True), 0.2)
        # Minimized windows stay inexpensive even when full-rate display was
        # requested; recording explicitly restores the capture cadence.
        self.assertEqual(
            preview_render_interval(60, True, False, full_rate=True), 0.5)
        self.assertEqual(preview_render_interval(60, False, False), 0.5)

    def test_inactive_frame_consumption_is_throttled_unless_recording(self):
        self.assertEqual(
            preview_capture_interval(60, False, True, background_work=False), 0.2)
        self.assertEqual(
            preview_capture_interval(60, False, False, background_work=False), 0.5)
        self.assertAlmostEqual(
            preview_capture_interval(60, False, False, background_work=True),
            1.0 / 60.0)


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


class PythonSourceSafetyTests(unittest.TestCase):
    def test_mixed_leading_tabs_are_normalized_without_changing_string_data(self):
        source = ("def sample():\n"
                  "\tif True:\n"
                  "\t\tvalue = 1\n"
                  "    text = \"\"\"line one\n"
                  "\tkeep this tab in the string\n"
                  "\"\"\"\n"
                  "    return value, text\n")
        normalized = normalize_and_compile_python(source, "mixed.py")
        self.assertNotIn("\tif True", normalized)
        self.assertNotIn("\t\tvalue", normalized)
        self.assertIn("\tkeep this tab in the string", normalized)

    def test_fragment_replacement_removes_pasted_indentation_tabs(self):
        fragment = "def sample(self):\n    return 1\n"
        replacement = (
            "def sample(self):\n"
            "\tif True:\n"
            "\t\treturn 2\n")
        updated = replace_fragment_function_text(
            fragment, "sample", replacement)
        self.assertEqual(normalize_python_indentation(updated), updated)
        compile(updated, "sample.pyfrag", "exec")


class SampleFunctionSyncTests(unittest.TestCase):
    def test_fragment_stats_count_functions_and_references(self):
        fragment = (
            "def first(self):\n"
            "    return self.second()\n\n"
            "def second(self):\n"
            "    return self.second\n")
        self.assertEqual(
            fragment_function_stats(fragment, "second"),
            {"function_count": 2, "reference_count": 2})

    def test_sample_to_sample_reflection_replaces_function_and_keeps_name(self):
        source_function = (
            "def ZA_sample(self):\n"
            "    return self.ZA_sample()\n")
        target_fragment = (
            "def sample(self):\n"
            "    return False\n\n"
            "def untouched(self):\n"
            "    return True\n")
        updated = reflect_fragment_function_text(
            source_function, "ZA_sample", target_fragment, "sample")
        self.assertIn("def sample(self):", updated)
        self.assertIn("self.sample()", updated)
        self.assertIn("def untouched(self):", updated)
        self.assertNotIn("ZA_sample", updated)
        compile(updated, "sample.pyfrag", "exec")

    def test_manual_fragment_edit_replaces_only_selected_function(self):
        fragment = (
            "def first(self):\n    return 1\n\n"
            "def second(self):\n    return 2\n")
        updated = replace_fragment_function_text(
            fragment, "first", "def first(self):\n    return 3\n")
        self.assertIn("return 3", updated)
        self.assertIn("def second(self):\n    return 2", updated)
        compile(updated, "sample.pyfrag", "exec")

    def test_discard_duplicate_removes_only_selected_function(self):
        fragment = (
            "def first(self):\n    return 1\n\n"
            "def second(self):\n    return 2\n")
        updated = remove_fragment_function_text(fragment, "first")
        self.assertNotIn("def first", updated)
        self.assertIn("def second(self):\n    return 2", updated)
        compile(updated, "sample.pyfrag", "exec")

    def test_manual_fragment_edit_rejects_function_rename(self):
        with self.assertRaises(ValueError):
            replace_fragment_function_text(
                "def first(self):\n    return 1\n", "first",
                "def renamed(self):\n    return 1\n")

    def test_duplicate_samples_report_same_or_different_content(self):
        source = '''
class Demo:
    def sample(self):
        return True
'''
        with tempfile.TemporaryDirectory() as root:
            for folder_name in ("one", "two"):
                folder = os.path.join(root, folder_name)
                os.makedirs(folder)
                with open(os.path.join(folder, "sample.pyfrag"), "w",
                          encoding="utf-8") as stream:
                    stream.write("def sample(self):\n    return True\n")
            comparisons = compare_sample_function_folder(source, root, root)
            self.assertEqual(comparisons[0]["status"], "duplicate")
            self.assertEqual(comparisons[0]["duplicate_kind"], "same")
            with open(os.path.join(root, "two", "sample.pyfrag"), "w",
                      encoding="utf-8") as stream:
                stream.write("def sample(self):\n    return False\n")
            comparisons = compare_sample_function_folder(source, root, root)
            self.assertEqual(comparisons[0]["duplicate_kind"], "different")

    def test_lowercase_semantic_prefix_is_not_treated_as_function_rename(self):
        source = '''
class Demo:
    def image_check(self, name):
        return bool(name)
'''
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "game_input_router")
            os.makedirs(folder)
            with open(os.path.join(folder, "router.pyfrag"), "w",
                      encoding="utf-8") as stream:
                stream.write(
                    "def game_image_check(self, logical_name):\n"
                    "    return self.image_check(logical_name)\n")
            comparisons = compare_sample_function_folder(source, root, root)
            self.assertEqual(len(comparisons), 1)
            self.assertEqual(comparisons[0]["name"], "game_image_check")
            self.assertEqual(comparisons[0]["status"], "missing_source")

    def test_uppercase_namespace_prefix_remains_a_rename_candidate(self):
        source = '''
class Demo:
    def move(self):
        return True
'''
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "Pokemon")
            os.makedirs(folder)
            with open(os.path.join(folder, "move.pyfrag"), "w",
                      encoding="utf-8") as stream:
                stream.write("def ZA_move(self):\n    return True\n")
            comparisons = compare_sample_function_folder(source, root, root)
            self.assertEqual(comparisons[0]["name"], "move")
            self.assertEqual(comparisons[0]["sample_name"], "ZA_move")
            self.assertEqual(comparisons[0]["status"], "name_different")

    def test_clean_editor_recheck_reads_externally_updated_source(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "Demo.py")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("class Demo:\n    pass\n")
            source, mode = comparison_source_text(
                path, path, "class Old:\n    pass\n", editor_dirty=False)
            self.assertEqual(mode, "disk")
            self.assertIn("class Demo", source)

    def test_dirty_editor_recheck_keeps_unsaved_reflection(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "Demo.py")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("class Disk:\n    pass\n")
            editor_source = "class Edited:\n    pass\n"
            source, mode = comparison_source_text(
                path, path, editor_source, editor_dirty=True)
            self.assertEqual((source, mode), (editor_source, "editor"))

    def test_class_method_extraction_ignores_shallow_comment_indent(self):
        source = '''
class Demo:
    def first(self):
        return True

  # comment saved with shallower indentation by an older source
    def second(self):
        return False
'''
        records = sample_sync_function_records(source, class_only=True)
        self.assertTrue(records["second"]["text"].startswith("def second"))
        compile(records["second"]["text"], "second.pyfrag", "exec")

    def test_python37_fallback_keeps_unindented_comment_with_function_body(self):
        source = '''
def sample(self):
# explanatory comment saved by an older sample
    return True

def next_sample(self):
    return False
'''
        records = sample_sync_function_records(source)
        self.assertIn("return True", records["sample"]["text"])
        compile(records["sample"]["text"], "sample.pyfrag", "exec")

    def test_side_by_side_diff_highlights_only_changed_characters(self):
        rows = side_by_side_diff_rows(
            "def old_name(self):\n    return 1\n",
            "def new_name(self):\n    return 1\n")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["kind"], "replace")
        self.assertEqual(rows[0]["left_spans"], [(4, 7)])
        self.assertEqual(rows[0]["right_spans"], [(4, 7)])
        self.assertEqual(rows[1]["kind"], "equal")
        self.assertEqual(rows[1]["left_spans"], [])
        self.assertEqual(rows[1]["right_spans"], [])

    def test_side_by_side_diff_aligns_added_lines_with_a_blank_side(self):
        rows = side_by_side_diff_rows(
            "def sample(self):\n    return True\n",
            "# comment\ndef sample(self):\n    return True\n")
        self.assertIsNone(rows[0]["left_line"])
        self.assertEqual(rows[0]["right_line"], 1)
        self.assertEqual(rows[0]["kind"], "insert")
        self.assertEqual(rows[1]["left"], "def sample(self):")
        self.assertEqual(rows[1]["right"], "def sample(self):")
        self.assertEqual(rows[1]["kind"], "equal")

    def test_renamed_sample_compares_and_syncs_with_its_recorded_origin(self):
        original_source = '''
class Demo:
    def original(self):
        self.original()
        return 1
'''
        changed_source = '''
class Demo:
    def original(self):
        self.original()
        return 3
'''
        with tempfile.TemporaryDirectory() as root:
            source_path = os.path.join(root, "Demo.py")
            sample_dir = os.path.join(root, "Imported", "ZA_original")
            os.makedirs(sample_dir)
            with open(source_path, "w", encoding="utf-8") as stream:
                stream.write(original_source)
            metadata_path = os.path.join(sample_dir, "ZA_original.pokesample.json")
            body_path = os.path.join(sample_dir, "ZA_original.pyfrag")
            with open(metadata_path, "w", encoding="utf-8") as stream:
                json.dump({
                    "name": "ZA_original",
                    "fragment": "ZA_original.pyfrag",
                    "source": {"path": source_path, "function": "original"},
                }, stream)
            with open(body_path, "w", encoding="utf-8") as stream:
                stream.write(
                    "def ZA_original(self):\n"
                    "    self.ZA_original()\n"
                    "    return 2\n")

            comparisons = compare_sample_function_folder(
                original_source, root, os.path.join(root, "Imported"))
            self.assertEqual(len(comparisons), 1)
            self.assertEqual(comparisons[0]["sample_name"], "ZA_original")
            self.assertEqual(comparisons[0]["name"], "original")
            self.assertEqual(comparisons[0]["status"], "different")
            self.assertEqual(
                source_paths_for_folder(root, os.path.join(root, "Imported")),
                [os.path.abspath(source_path)])

            updated = update_source_from_samples(
                original_source, comparisons, ["original"])
            self.assertIn("def original(self):", updated)
            self.assertIn("self.original()", updated)
            self.assertIn("return 2", updated)
            self.assertNotIn("ZA_original", updated)

            update_sample_fragments(
                changed_source, comparisons, ["original"])
            with open(body_path, "r", encoding="utf-8") as stream:
                updated_sample = stream.read()
            self.assertIn("def ZA_original(self):", updated_sample)
            self.assertIn("self.ZA_original()", updated_sample)
            self.assertIn("return 3", updated_sample)
            self.assertNotIn("def original(self):", updated_sample)

    def test_merge_keeps_sample_name_and_source_processing(self):
        source = '''
class Demo:
    def original(self):
        self.original()
        return "source-correct"
'''
        with tempfile.TemporaryDirectory() as root:
            source_path = os.path.join(root, "Demo.py")
            sample_dir = os.path.join(root, "Imported", "ZA_original")
            os.makedirs(sample_dir)
            with open(source_path, "w", encoding="utf-8") as stream:
                stream.write(source)
            metadata_path = os.path.join(sample_dir, "ZA_original.pokesample.json")
            body_path = os.path.join(sample_dir, "ZA_original.pyfrag")
            with open(metadata_path, "w", encoding="utf-8") as stream:
                json.dump({
                    "name": "ZA_original",
                    "fragment": "ZA_original.pyfrag",
                    "source": {"path": source_path, "function": "original"},
                }, stream)
            with open(body_path, "w", encoding="utf-8") as stream:
                stream.write(
                    "def ZA_original(self):\n"
                    "    self.ZA_original()\n"
                    "    return \"sample-old\"\n")
            comparisons = compare_sample_function_folder(
                source, root, os.path.join(root, "Imported"), source_path)
            updated, changed, mapping = merge_sample_names_with_source_bodies(
                source, comparisons, ["original"])
            self.assertEqual(mapping, {"original": "ZA_original"})
            self.assertEqual(changed, [body_path])
            self.assertIn("def ZA_original(self):", updated)
            self.assertIn("self.ZA_original()", updated)
            self.assertIn('return "source-correct"', updated)
            self.assertNotIn("def original(self):", updated)
            with open(body_path, "r", encoding="utf-8") as stream:
                sample = stream.read()
            self.assertIn("def ZA_original(self):", sample)
            self.assertIn('return "source-correct"', sample)
            self.assertNotIn("sample-old", sample)
            with open(metadata_path, "r", encoding="utf-8") as stream:
                metadata = json.load(stream)
            self.assertEqual(metadata["source"]["function"], "ZA_original")

    def test_batch_merge_updates_same_name_sample_from_source(self):
        source = '''
class Demo:
    def same_name(self):
        return "source-correct"
'''
        with tempfile.TemporaryDirectory() as root:
            sample_dir = os.path.join(root, "Imported", "same_name")
            os.makedirs(sample_dir)
            metadata_path = os.path.join(sample_dir, "same_name.pokesample.json")
            body_path = os.path.join(sample_dir, "same_name.pyfrag")
            with open(metadata_path, "w", encoding="utf-8") as stream:
                json.dump({
                    "name": "same_name", "fragment": "same_name.pyfrag",
                    "source": {"path": "Demo.py", "function": "same_name"},
                }, stream)
            with open(body_path, "w", encoding="utf-8") as stream:
                stream.write(
                    "def same_name(self):\n    return \"sample-old\"\n")
            comparisons = compare_sample_function_folder(
                source, root, os.path.join(root, "Imported"))
            updated, changed, mapping = merge_sample_names_with_source_bodies(
                source, comparisons, ["same_name"])
            self.assertEqual(updated, source)
            self.assertEqual(mapping, {})
            self.assertEqual(changed, [body_path])
            with open(body_path, "r", encoding="utf-8") as stream:
                self.assertIn('return "source-correct"', stream.read())

    def test_batch_backup_can_restore_samples_and_source_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            source_path = os.path.join(root, "Demo.py")
            sample_dir = os.path.join(root, "Imported", "sample")
            backup_root = os.path.join(root, "Backups")
            os.makedirs(sample_dir)
            body_path = os.path.join(sample_dir, "sample.pyfrag")
            metadata_path = os.path.join(sample_dir, "sample.pokesample.json")
            source_before = "class Demo:\n    pass\n"
            with open(source_path, "w", encoding="utf-8") as stream:
                stream.write(source_before)
            with open(body_path, "w", encoding="utf-8") as stream:
                stream.write("def sample(self):\n    return 1\n")
            with open(metadata_path, "w", encoding="utf-8") as stream:
                json.dump({"name": "sample", "fragment": "sample.pyfrag"}, stream)
            comparisons = [{
                "name": "sample",
                "fragments": [{"path": body_path}],
            }]
            backup = create_sample_sync_backup(
                source_path, source_before, comparisons, ["sample"], backup_root)
            self.assertEqual(
                latest_sample_sync_backup(backup_root), backup["manifest_path"])
            with open(body_path, "w", encoding="utf-8") as stream:
                stream.write("changed")
            with open(metadata_path, "w", encoding="utf-8") as stream:
                stream.write("{}")
            restored_source, restored_path, manifest = restore_sample_sync_backup(
                backup["manifest_path"])
            self.assertEqual(restored_source, source_before)
            self.assertEqual(restored_path, os.path.abspath(source_path))
            self.assertEqual(manifest["created"], backup["created"])
            with open(body_path, "r", encoding="utf-8") as stream:
                self.assertIn("return 1", stream.read())
            with open(metadata_path, "r", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream)["name"], "sample")

    def test_batch_backup_restores_deleted_sample_and_extra_file(self):
        with tempfile.TemporaryDirectory() as root:
            sample_dir = os.path.join(root, "Imported", "sample")
            os.makedirs(sample_dir)
            body_path = os.path.join(sample_dir, "sample.pyfrag")
            extra_path = os.path.join(root, "sample_lists.json")
            with open(body_path, "w", encoding="utf-8") as stream:
                stream.write("def sample(self):\n    return 1\n")
            with open(extra_path, "w", encoding="utf-8") as stream:
                stream.write('{"before": true}')
            comparisons = [{
                "name": "sample", "fragments": [{"path": body_path}]}]
            backup = create_sample_sync_backup(
                "", "", comparisons, ["sample"],
                os.path.join(root, "Backups"), extra_paths=[extra_path])
            os.remove(body_path)
            with open(extra_path, "w", encoding="utf-8") as stream:
                stream.write('{"after": true}')
            restore_sample_sync_backup(backup["manifest_path"])
            with open(body_path, "r", encoding="utf-8") as stream:
                self.assertIn("return 1", stream.read())
            with open(extra_path, "r", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), {"before": True})


class SourceDependencyToolsTests(unittest.TestCase):
    SOURCE = '''
import time

class Demo:
    CLASS_LIMIT = 3

    def __init__(self):
        self.STATE_FLOW_FUNCTION = {
            "START": self.flow_start,
            "END": self.flow_end,
        }
        self.flow_state = "START"
        self.delay = 0.2

    def flow_main(self):
        while True:
            self.flow_state = self.STATE_FLOW_FUNCTION[self.flow_state]()
            self.wait(self.delay)

    def flow_start(self):
        self.helper()
        return "END"

    def flow_end(self):
        return "END"

    def helper(self):
        return self.CLASS_LIMIT

    def unrelated(self):
        return False
'''

    def test_state_dictionary_drives_dependency_group(self):
        analysis = analyze_source_dependencies(self.SOURCE, ["flow_main"])
        self.assertEqual(
            analysis["methods"],
            ["flow_main", "flow_start", "flow_end", "helper"])
        self.assertEqual(
            analysis["state_dictionaries"]["STATE_FLOW_FUNCTION"],
            [{"state": "START", "handler": "flow_start"},
             {"state": "END", "handler": "flow_end"}])
        self.assertIn("self.STATE_FLOW_FUNCTION", analysis["initializer"])
        self.assertIn("CLASS_LIMIT = 3", analysis["class_variables"])
        self.assertEqual(
            state_dictionary_handlers(self.SOURCE, "STATE_FLOW_FUNCTION"),
            [("START", "flow_start"), ("END", "flow_end")])

    def test_state_machine_main_can_be_generated_from_dictionary_names(self):
        generated = generate_state_machine_main(
            "flow_main", "STATE_FLOW_FUNCTION", "flow_state", "self.delay")
        self.assertIn(
            "self.flow_state = self.STATE_FLOW_FUNCTION[self.flow_state]()",
            generated)
        compile(generated, "generated.py", "exec")

    def test_state_dictionary_can_be_the_authoritative_group_root(self):
        analysis = analyze_state_dictionary_dependencies(
            self.SOURCE, "STATE_FLOW_FUNCTION")
        self.assertEqual(
            analysis["methods"], ["flow_start", "flow_end", "helper"])
        self.assertEqual(analysis["root_state_dictionary"],
                         "STATE_FLOW_FUNCTION")
        self.assertEqual(analysis["current_state_attribute"], "flow_state")
        self.assertEqual(
            state_dictionary_current_state(self.SOURCE, "STATE_FLOW_FUNCTION"),
            "flow_state")
        self.assertEqual(
            state_dictionary_names(self.SOURCE), ["STATE_FLOW_FUNCTION"])
        ordinary = analyze_source_dependencies(self.SOURCE, ["flow_main"])
        self.assertEqual(
            suggest_state_dictionary(ordinary, "flow_main"),
            "STATE_FLOW_FUNCTION")

    def test_managed_image_dictionaries_are_external_requirements(self):
        source = '''
class Demo:
    IMAGE_DETECTION_TARGETS = {"A": [{"threshold": 0.8}]}

    def __init__(self):
        self.state = "START"

    def check(self):
        return self.IMAGE_DETECTION_TARGETS.get("A")
'''
        analysis = analyze_source_dependencies(source, ["check"])
        self.assertEqual(analysis["class_variables"], [])
        self.assertEqual(
            analysis["external_class_variables"],
            ["IMAGE_DETECTION_TARGETS"])
        self.assertNotIn("IMAGE_DETECTION_TARGETS",
                         analysis["unresolved_attributes"])

    def test_function_scoped_sample_member_extracts_only_requested_method(self):
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "group")
            os.makedirs(folder)
            metadata_path = os.path.join(folder, "group.pokesample.json")
            body_path = os.path.join(folder, "group.pyfrag")
            with open(metadata_path, "w", encoding="utf-8") as stream:
                json.dump({
                    "name": "group", "fragment": "group.pyfrag",
                    "imports": [], "class_variables": [],
                }, stream)
            with open(body_path, "w", encoding="utf-8") as stream:
                stream.write(
                    "def wanted(self):\n    return 1\n\n"
                    "def unwanted(self):\n    return 2\n")
            library_path = os.path.join(root, "sample_lists.json")
            save_library(library_path, {
                "schema_version": 2,
                "lists": {"OnlyWanted": {"tags": [], "members": [{
                    "type": "fragment", "id": "group/group.pokesample.json",
                    "function": "wanted"}]}}})
            with open(library_path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
            preview = compose_preview(root, data, "OnlyWanted")
            self.assertEqual(preview["included"], ["wanted"])
            self.assertIn("def wanted", preview["bodies"][0])
            self.assertNotIn("def unwanted", preview["bodies"][0])

    def test_safe_apply_reuses_matches_adds_missing_and_blocks_differences(self):
        source = '''
class Demo:
    def __init__(self):
        pass

    def same(self):
        return 1
'''
        preview = {
            "imports": ["import time"],
            "class_variables": ["LIMIT = 3"],
            "initializers": ["self.state = 'START'"],
            "bodies": [
                "def same(self):\n    return 1",
                "def added(self):\n    return self.LIMIT"],
        }
        self.assertEqual(
            [row["status"] for row in compare_preview_functions(source, preview)],
            ["match", "missing"])
        self.assertTrue(all(
            row["status"] == "missing"
            for row in compare_preview_support(source, preview)))
        updated, _ = merge_preview_support_safely(source, preview)
        updated, _ = merge_preview_functions_safely(updated, preview, "DemoGroup")
        compile(updated, "merged.py", "exec")
        self.assertIn("import time", updated)
        self.assertIn("LIMIT = 3", updated)
        self.assertIn("self.state = 'START'", updated)
        self.assertIn("def added", updated)
        different = dict(preview)
        different["bodies"] = ["def same(self):\n    return 9"]
        with self.assertRaises(ValueError):
            merge_preview_functions_safely(source, different, "DemoGroup")

    def test_register_dependency_group_creates_function_scoped_members(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch(
                    "SourceDependencyTools.catalog_function_candidates",
                    wraps=sys.modules[
                        "SourceDependencyTools"].catalog_function_candidates) as scan:
                plan, members = register_dependency_group(
                    self.SOURCE, ["flow_main"], root,
                    "Imported/DemoFlow", "DemoFlow", source_path="Demo.py")
            # Missing functions are completed from the just-created file list;
            # the entire sample library must not be parsed for a second pass.
            self.assertEqual(scan.call_count, 1)
            self.assertEqual(len(plan["methods"]), 4)
            self.assertTrue(all(
                row["status"] == "created" for row in plan["registration"]))
            functions = [member.get("function") for member in members
                         if member.get("function")]
            self.assertEqual(
                functions, ["flow_main", "flow_start", "flow_end", "helper"])
            scoped = [member for member in members if member.get("function")]
            self.assertTrue(all(
                member.get("origin_path") == "Demo.py" and
                member.get("origin_function") == member.get("function")
                for member in scoped))
            self.assertTrue(members[0]["id"].endswith(
                "DemoFlow__support/DemoFlow__support.pokesample.json"))


class SampleOriginSyncTests(unittest.TestCase):
    SOURCE = '''
class Demo:
    def reusable(self):
        return 1

    def untouched(self):
        return 5
'''

    def _create_library(self, root, origin_paths):
        folder = os.path.join(root, "shared")
        os.makedirs(folder)
        body_path = os.path.join(folder, "shared.pyfrag")
        metadata_path = os.path.join(folder, "shared.pokesample.json")
        with open(body_path, "w", encoding="utf-8") as stream:
            stream.write("def reusable(self):\n    return 9\n")
        with open(metadata_path, "w", encoding="utf-8") as stream:
            json.dump({
                "name": "shared", "fragment": "shared.pyfrag",
                "imports": [], "class_variables": [], "initializer": "",
                "source": {"path": origin_paths[0],
                           "function": "reusable"},
            }, stream)
        members = []
        for path in origin_paths:
            members.append({
                "type": "fragment", "id": "shared/shared.pokesample.json",
                "function": "reusable", "origin_path": path,
                "origin_function": "reusable"})
        data = {"schema_version": 2, "lists": {
            "SharedCommands": {"tags": [], "members": members}}}
        save_library(os.path.join(root, "sample_lists.json"), data)
        with open(os.path.join(root, "sample_lists.json"),
                  "r", encoding="utf-8") as stream:
            return json.load(stream)

    def test_sample_list_can_update_selected_origin_commands_and_restore(self):
        with tempfile.TemporaryDirectory() as root:
            command1 = os.path.join(root, "Command1.py")
            command2 = os.path.join(root, "Command2.py")
            for path in (command1, command2):
                with open(path, "w", encoding="utf-8") as stream:
                    stream.write(self.SOURCE)
            data = self._create_library(root, [command1, command2])
            rows = compare_sample_list_origins(
                root, data, "SharedCommands")
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row["status"] == "different" for row in rows))
            result = apply_sample_list_to_origins(
                rows, [rows[0]["key"]], os.path.join(root, "Backups"),
                "SharedCommands")
            self.assertEqual(result["functions"], 1)
            with open(command1, "r", encoding="utf-8-sig") as stream:
                self.assertIn("return 9", stream.read())
            with open(command2, "r", encoding="utf-8-sig") as stream:
                self.assertIn("return 1", stream.read())
            restore_origin_sync_backup(result["backup"]["manifest_path"])
            with open(command1, "r", encoding="utf-8-sig") as stream:
                restored = stream.read()
            self.assertIn("return 1", restored)
            self.assertIn("return 5", restored)

    def test_missing_origin_function_is_added(self):
        with tempfile.TemporaryDirectory() as root:
            command = os.path.join(root, "Command.py")
            with open(command, "w", encoding="utf-8") as stream:
                stream.write("class Demo:\n    pass\n")
            data = self._create_library(root, [command])
            rows = compare_sample_list_origins(root, data, "SharedCommands")
            self.assertEqual(rows[0]["status"], "missing_source")
            apply_sample_list_to_origins(
                rows, [rows[0]["key"]], os.path.join(root, "Backups"),
                "SharedCommands")
            with open(command, "r", encoding="utf-8-sig") as stream:
                updated = stream.read()
            compile(updated, command, "exec")
            self.assertIn("def reusable", updated)


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

    def test_source_record_ignores_shallow_comment_indent(self):
        source = '''
class Demo:
    def first(self):
        return True

  # shallower comment must not affect the following method extraction
    def second(self):
        return False
'''
        records = {item["name"]: item for item in source_function_records(source)}
        self.assertTrue(records["second"]["text"].startswith("def second"))
        compile(records["second"]["text"], "second.pyfrag", "exec")

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


class OperationCaptureSessionTests(unittest.TestCase):
    def test_keyboard_input_is_rejected_from_operation_recording(self):
        self.assertFalse(operation_input_source_is_recordable("keyboard"))
        self.assertTrue(operation_input_source_is_recordable("pc_gamepad"))
        self.assertTrue(operation_input_source_is_recordable("software_controller"))
        with tempfile.TemporaryDirectory() as folder:
            session = OperationCaptureSession(folder, input_set="Switch", name="keyboard")
            segment = os.path.join(session.session_dir, "segments", "first")
            os.makedirs(segment)
            session.begin_segment(segment, started=10.0)
            item = session.record_input(
                "0x0004 8", occurred=10.5, source="keyboard")
            self.assertIsNone(item)
            self.assertEqual(session.manifest["input_count"], 0)
            session.pause(stopped=11.0)
            session.close()

    def test_serial_packet_is_decoded_for_video_and_devstudio(self):
        decoded = decode_serial_message("0x0012 8 ff 80")
        self.assertIn("A", decoded["buttons"])
        self.assertAlmostEqual(decoded["left_stick"]["angle"], 0.0)
        self.assertIn("L@0deg", decoded["summary"])

    def test_pause_gap_is_not_added_to_the_authoring_timeline(self):
        with tempfile.TemporaryDirectory() as folder:
            session = OperationCaptureSession(folder, input_set="Switch", name="story")
            first = os.path.join(session.session_dir, "segments", "first")
            second = os.path.join(session.session_dir, "segments", "second")
            os.makedirs(first)
            os.makedirs(second)
            session.begin_segment(first, started=100.0)
            session.record_input("0x0010 8", occurred=101.0)
            session.record_input("0x0000 8", occurred=102.0)
            session.pause(stopped=103.0)
            session.begin_segment(second, started=200.0)
            item = session.record_input("0x0008 8", occurred=201.0)
            session.pause(stopped=202.0)
            self.assertEqual(item["time"], 4.0)
            self.assertEqual(session.manifest["active_duration"], 5.0)
            session.complete()
            saved = load_manifest(session.session_dir)
            self.assertEqual(saved["status"], "finalizing")
            self.assertEqual(saved["input_count"], 3)
            self.assertEqual(len(saved["segments"]), 2)

    def test_interrupted_operation_merge_can_be_prepared_for_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            session = OperationCaptureSession(folder, name="retry")
            segment = os.path.join(session.session_dir, "segments", "first")
            os.makedirs(segment)
            session.begin_segment(segment, started=10.0)
            session.pause(stopped=11.0)
            session.complete()

            reopened = OperationCaptureSession(
                folder, session_dir=session.session_dir)
            self.assertEqual(reopened.prepare_finalize_retry(), 1)
            reopened.close()
            saved = load_manifest(session.session_dir)
            self.assertEqual(saved["status"], "finalizing")
            self.assertEqual(saved["finalize_retry_count"], 1)
            self.assertIn("finalize_retried_at", saved)

    def test_paused_operation_merge_cannot_be_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            session = OperationCaptureSession(folder, name="paused")
            segment = os.path.join(session.session_dir, "segments", "first")
            os.makedirs(segment)
            session.begin_segment(segment, started=10.0)
            session.pause(stopped=11.0)
            with self.assertRaises(RuntimeError):
                session.prepare_finalize_retry()
            session.close()

    def test_selected_gamepad_profile_and_full_mapping_are_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            session = OperationCaptureSession(folder, input_set="Switch", name="keys")
            mapping = normalize_gamepad_mapping({"A": "button:1", "B": "button:0"})
            session.set_input_configuration(
                gamepad="0: Controller", gamepad_profile="Story pad",
                gamepad_mapping=mapping)
            saved = load_manifest(session.session_dir)["input_configuration"]
            self.assertEqual(saved["gamepad_profile"], "Story pad")
            self.assertEqual(saved["gamepad_mapping"]["A"], "button:1")
            self.assertEqual(saved["gamepad_mapping"]["B"], "button:0")
            self.assertEqual(saved["gamepad"], "0: Controller")
            session.close()

    def test_software_controller_home_is_identified_in_operation_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            session = OperationCaptureSession(folder, input_set="Switch", name="home")
            segment = os.path.join(session.session_dir, "segments", "first")
            os.makedirs(segment)
            session.begin_segment(segment, started=10.0)
            item = session.record_input(
                "0x4003 8 80 80 80 80", occurred=10.5,
                source="software_controller")
            self.assertEqual(item["source"], "software_controller")
            self.assertIn("HOME", item["buttons"])
            session.pause(stopped=11.0)
            session.close()

    def test_paused_operation_session_can_be_discarded_before_deletion(self):
        with tempfile.TemporaryDirectory() as folder:
            session = OperationCaptureSession(folder, input_set="Switch", name="mistake")
            segment = os.path.join(session.session_dir, "segments", "first")
            os.makedirs(segment)
            session.begin_segment(segment, started=10.0)
            session.record_input("0x0010 8", occurred=10.2)
            session.pause(stopped=10.5)
            session_dir = session.discard()
            saved = load_manifest(session_dir)
            self.assertEqual(saved["status"], "discarded")
            self.assertIn("discarded_at", saved)
            self.assertEqual(find_paused_session(folder, "mistake"), "")
            self.assertNotIn("mistake", paused_session_names(folder))

    def test_paused_session_names_are_available_for_editable_dropdown(self):
        with tempfile.TemporaryDirectory() as folder:
            sessions = []
            for index, name in enumerate(("Route B", "Route A", "Route A"), 1):
                session = OperationCaptureSession(folder, name=name)
                segment = os.path.join(session.session_dir, "segments", str(index))
                os.makedirs(segment)
                session.begin_segment(segment, started=float(index))
                session.pause(stopped=float(index) + 0.5)
                session.close()
                sessions.append(session.session_dir)
            self.assertEqual(paused_session_names(folder), ["Route A", "Route B"])

    def test_discarded_session_directory_retries_transient_windows_lock(self):
        with mock.patch("OperationCaptureSession.shutil.rmtree",
                        side_effect=(PermissionError("locked"), None)) as remove:
            with mock.patch("OperationCaptureSession.time.sleep") as sleep:
                self.assertEqual(
                    remove_session_directory("discarded", attempts=3, delay=0.01), "")
        self.assertEqual(remove.call_count, 2)
        sleep.assert_called_once_with(0.01)

    def test_devstudio_edits_survive_resume_from_pause(self):
        with tempfile.TemporaryDirectory() as folder:
            session = OperationCaptureSession(folder, input_set="Switch", name="resume")
            first = os.path.join(session.session_dir, "segments", "first")
            second = os.path.join(session.session_dir, "segments", "second")
            os.makedirs(first)
            os.makedirs(second)
            session.begin_segment(first, started=10.0)
            session.pause(stopped=11.0)
            path = os.path.join(session.session_dir, "session.json")
            with open(path, "r", encoding="utf-8") as stream:
                external = json.load(stream)
            external["generation"] = {
                "input_target": "switch_steam_ps4",
                "vision_sample": {"candidate_count": 2},
            }
            external["video_sync_offset"] = 0.125
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(external, stream)
            session.begin_segment(second, started=20.0)
            saved = load_manifest(session.session_dir)
            self.assertEqual(saved["generation"]["input_target"], "switch_steam_ps4")
            self.assertEqual(saved["generation"]["vision_sample"]["candidate_count"], 2)
            self.assertEqual(saved["video_sync_offset"], 0.125)
            session.pause(stopped=21.0)
            session.close()

    def test_newest_paused_session_can_be_found_again_by_recording_name(self):
        with tempfile.TemporaryDirectory() as folder:
            older = OperationCaptureSession(folder, name="story")
            older_segment = os.path.join(
                older.session_dir, "segments", "first")
            os.makedirs(older_segment)
            older.begin_segment(older_segment, started=10.0)
            older.pause(stopped=11.0)
            older.close()

            newer = OperationCaptureSession(folder, name="story")
            newer_segment = os.path.join(
                newer.session_dir, "segments", "first")
            os.makedirs(newer_segment)
            newer.begin_segment(newer_segment, started=20.0)
            newer.pause(stopped=21.0)
            newer.close()

            completed = OperationCaptureSession(folder, name="story")
            completed_segment = os.path.join(
                completed.session_dir, "segments", "first")
            os.makedirs(completed_segment)
            completed.begin_segment(completed_segment, started=30.0)
            completed.pause(stopped=31.0)
            completed.complete()

            self.assertEqual(
                find_paused_session(folder, "story"), newer.session_dir)
            self.assertEqual(find_paused_session(folder, "unknown"), "")


class OperationGamepadMapTests(unittest.TestCase):
    class _Joystick:
        def __init__(self, axes, buttons=None, hats=None):
            self.axes = list(axes)
            self.buttons = list(buttons or [])
            self.hats = list(hats or [])

        def get_numaxes(self):
            return len(self.axes)

        def get_axis(self, index):
            return self.axes[index]

        def get_numbuttons(self):
            return len(self.buttons)

        def get_button(self, index):
            return self.buttons[index]

        def get_numhats(self):
            return len(self.hats)

        def get_hat(self, index):
            return self.hats[index]

    @staticmethod
    def _dialog_logic(mapping):
        dialog = OperationGamepadMapDialog.__new__(OperationGamepadMapDialog)
        dialog.mapping = normalize_gamepad_mapping(mapping)
        dialog.active_control = None
        dialog.capture_armed = False
        dialog.last_detected_token = ""
        dialog.pressed_controls = set()
        dialog.status = mock.Mock()
        dialog.assign_detected_text = mock.Mock()
        dialog.assign_detected_button = mock.Mock()
        dialog._update_tree_values = mock.Mock()
        dialog._paint_controls = mock.Mock()
        return dialog

    def test_profiles_preserve_selected_name_and_complete_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            store = OperationGamepadProfileStore(os.path.join(folder, "operation_gamepads.json"))
            data = store.load()
            data["profiles"]["Second"] = {"mapping": normalize_gamepad_mapping({
                "A": "button:1", "B": "button:0"})}
            data["selected"] = "Second"
            saved = store.save(data)
            loaded = store.load()
            self.assertEqual(saved["selected"], "Second")
            self.assertEqual(loaded["selected"], "Second")
            self.assertEqual(loaded["profiles"]["Second"]["mapping"]["A"], "button:1")
            self.assertIn("ZR", loaded["profiles"]["Second"]["mapping"])

    def test_dpad_alias_accepts_button_and_hat_devices(self):
        mapping = normalize_gamepad_mapping({"DPAD_UP": "dpad:up"})
        self.assertEqual(controls_for_token(mapping, "button:11"), {"DPAD_UP"})
        self.assertEqual(controls_for_token(mapping, "hat:up"), {"DPAD_UP"})

    def test_trigger_teaching_accepts_any_axis_and_both_directions(self):
        self.assertEqual(gamepad_axis_token(2, 1.0, 0.0), "axis:2+")
        self.assertEqual(gamepad_axis_token(2, -1.0, 0.0), "axis:2-")
        self.assertEqual(gamepad_axis_token(5, 0.1, 0.0), "")
        plus = ProController(control_mapping={"ZL": "axis:2+"})
        plus._apply_physical("axis:2+", True)
        self.assertEqual(plus.bits_16, 1 << 8)
        minus = ProController(control_mapping={"ZL": "axis:2-"})
        minus._apply_physical("axis:2-", True)
        self.assertEqual(minus.bits_16, 1 << 8)

    def test_direct_opposite_after_trigger_release_is_suppressed(self):
        self.assertTrue(opposite_axis_tokens("axis:4+", "axis:4-"))
        active = {4: "axis:4+"}
        suppressed = {}
        events = []
        callback = lambda token, pressed: events.append((token, pressed))
        ProController._axis_transition(
            4, "axis:4-", active, suppressed, callback)
        self.assertEqual(events, [("axis:4+", False)])
        self.assertEqual(active, {})
        self.assertEqual(suppressed, {4: "axis:4-"})
        ProController._axis_transition(
            4, "axis:4-", active, suppressed, callback)
        self.assertEqual(events, [("axis:4+", False)])
        ProController._axis_transition(
            4, "axis:4+", active, suppressed, callback)
        self.assertEqual(events[-1], ("axis:4+", True))
        self.assertEqual(active, {4: "axis:4+"})

    def test_explicitly_mapped_negative_axis_remains_available(self):
        controller = ProController(control_mapping={"ZR": "axis:5-"})
        active = {5: "axis:5+"}
        suppressed = {}
        events = []
        controller._axis_transition(
            5, "axis:5-", active, suppressed,
            lambda token, pressed: events.append((token, pressed)),
            allow_opposite=controller.physical_token_is_mapped)
        self.assertEqual(events, [("axis:5+", False), ("axis:5-", True)])
        self.assertEqual(active, {5: "axis:5-"})
        self.assertEqual(suppressed, {})

    def test_taught_trigger_axis_does_not_also_move_a_stick(self):
        controller = ProController(control_mapping={"ZL": "axis:2+"})
        controller.axis_baseline = {index: 0.0 for index in range(6)}
        controller.joystick_move_detection(self._Joystick([0, 0, 1, 0, 0, 0]))
        self.assertEqual(controller.stick_status_new, [128, 128, 128, 128])

    def test_mapped_trigger_axis_never_blocks_neutral_gate(self):
        controller = ProController(control_mapping={"ZL": "axis:4+"})
        controller.axis_baseline = {index: 0.0 for index in range(6)}
        joystick = self._Joystick([0, 0, 0, 0, -1, -1])
        self.assertEqual(controller.joystick_neutral_blocker(joystick), "")
        controller.stabilize_mapped_axis_baselines(joystick)
        self.assertEqual(controller.joystick_neutral_blocker(joystick), "")
        self.assertTrue(controller.joystick_is_neutral(joystick))

    def test_startup_held_button_does_not_block_entire_controller(self):
        controller = ProController(control_mapping={"A": "button:2"})
        controller.axis_baseline = {0: 0.0, 1: 0.0}
        joystick = self._Joystick([0, 0], buttons=[0, 0, 1])
        self.assertEqual(controller.joystick_neutral_blocker(joystick), "")
        self.assertTrue(controller.joystick_is_neutral(joystick))

    def test_polled_buttons_and_hat_reach_mapping_preview_and_switch(self):
        physical = []
        controller = ProController(
            control_mapping={"A": "button:1", "DPAD_UP": "hat:up"},
            physical_input_callback=lambda token, pressed: physical.append((token, pressed)))
        joystick = self._Joystick([0, 0], buttons=[0, 0], hats=[(0, 0)])
        controller.poll_digital_states(joystick, forward=True, report=True)
        joystick.buttons[1] = 1
        controller.poll_digital_states(joystick, forward=True, report=True)
        self.assertEqual(controller.bits_16, 1 << 4)
        self.assertEqual(physical[-1], ("button:1", True))
        joystick.hats[0] = (0, 1)
        controller.poll_digital_states(joystick, forward=True, report=True)
        self.assertEqual(controller.hat_status, 1)
        self.assertEqual(physical[-1], ("hat:up", True))
        joystick.buttons[1] = 0
        joystick.hats[0] = (0, 0)
        controller.poll_digital_states(joystick, forward=True, report=True)
        self.assertEqual(controller.bits_16, 0)
        self.assertEqual(controller.hat_status, 0)

    def test_unarmed_press_only_highlights_current_mapping(self):
        dialog = self._dialog_logic({"A": "button:0", "B": "button:1"})
        dialog.active_control = "A"
        original = dict(dialog.mapping)
        dialog.handle_physical_input("button:1", True)
        self.assertEqual(dialog.mapping, original)
        self.assertEqual(dialog.pressed_controls, {"B"})

    def test_explicit_change_button_arms_selected_target(self):
        dialog = self._dialog_logic({"A": "button:0"})
        dialog.active_control = "A"
        dialog._arm_selected()
        self.assertTrue(dialog.capture_armed)
        dialog._paint_controls.assert_called_once()

    def test_preview_detection_can_be_explicitly_registered_to_zl(self):
        dialog = self._dialog_logic({"ZL": ""})
        dialog.handle_physical_input("axis:4+", True)
        self.assertEqual(dialog.mapping["ZL"], "")
        self.assertEqual(dialog.last_detected_token, "axis:4+")
        dialog.active_control = "ZL"
        dialog._assign_last_detected()
        self.assertEqual(dialog.mapping["ZL"], "axis:4+")

    def test_selected_target_teaches_once_then_returns_to_preview(self):
        dialog = self._dialog_logic({"A": "button:0", "B": "button:1"})
        dialog.active_control = "A"
        dialog.capture_armed = True
        dialog.handle_physical_input("button:1", True)
        self.assertEqual(dialog.mapping["A"], "button:1")
        self.assertEqual(dialog.mapping["B"], "")
        self.assertFalse(dialog.capture_armed)
        dialog.handle_physical_input("button:2", True)
        self.assertEqual(dialog.mapping["A"], "button:1")

    def test_ab_swap_long_hold_and_release_only_one(self):
        physical = []
        controller = ProController(control_mapping={
            "A": "button:1", "B": "button:0", "HOME": "button:5"},
            physical_input_callback=lambda token, pressed: physical.append((token, pressed)))
        controller._apply_physical("button:0", True)
        self.assertEqual(controller.bits_16, 1 << 3)
        controller._apply_physical("button:1", True)
        self.assertEqual(controller.bits_16, (1 << 3) | (1 << 4))
        controller._apply_physical("button:0", False)
        self.assertEqual(controller.bits_16, 1 << 4)
        self.assertEqual(physical[-1], ("button:0", False))

    def test_home_is_mapped_when_driver_delivers_guide_button(self):
        controller = ProController(control_mapping={"HOME": "button:5"})
        controller._apply_physical("button:5", True)
        self.assertEqual(controller.bits_16, 1 << 14)

    def test_two_dpad_inputs_become_diagonal_and_release_independently(self):
        controller = ProController(control_mapping={
            "DPAD_UP": "button:11", "DPAD_RIGHT": "button:14"})
        controller._apply_physical("button:11", True)
        controller._apply_physical("button:14", True)
        self.assertEqual(controller.hat_status, 3)
        self.assertEqual(controller.hat_dict[controller.hat_status], 1)
        controller._apply_physical("button:11", False)
        self.assertEqual(controller.hat_status, 2)


class OperationSessionModelTests(unittest.TestCase):
    @staticmethod
    def _inputs():
        return [
            {"kind": "input", "line": line, "time": float(line),
             "message": "message-{}".format(line), "summary": "input {}".format(line)}
            for line in range(1, 7)
        ]

    def test_paused_session_exposes_every_closed_segment_to_devstudio(self):
        with tempfile.TemporaryDirectory() as folder:
            segments = []
            for number, start in ((1, 0.0), (2, 12.5)):
                segment_dir = os.path.join(folder, "segment-{}".format(number))
                os.makedirs(segment_dir)
                with open(os.path.join(segment_dir, "recording.avi"), "wb") as stream:
                    stream.write(b"RIFF-test")
                segments.append({
                    "number": number, "recorder_dir": segment_dir,
                    "timeline_start": start, "duration": 2.0,
                })
            sources = operation_video_sources({
                "status": "paused", "segments": segments, "outputs": {},
            })
            self.assertEqual(len(sources), 2)
            self.assertEqual(sources[1]["timeline_start"], 12.5)
            self.assertIn("2", sources[1]["label"])

    def test_large_pending_input_list_is_compacted_to_ranges(self):
        self.assertEqual(
            compact_line_ranges(list(range(1, 27591)) + [30000, 30002, 30003]),
            "#0001-#27590, #30000, #30002-#30003")

    def test_paused_session_can_generate_intermediate_code(self):
        inputs = [{
            "kind": "input", "line": 1, "time": 0.2,
            "message": "0x4003 8 80 80 80 80", "summary": "HOME",
        }]
        mappings = [{
            "start_line": 1, "end_line": 1, "kind": "step",
            "step_name": "OPEN_HOME", "next_step": "NEXT",
        }]
        generated = generate_intermediate(
            {"status": "paused", "session_id": "paused-home"},
            inputs, mappings)
        self.assertIn("def OPEN_HOME", generated)
        self.assertIn("0x4003", generated)

    def test_legacy_keyboard_rows_are_excluded_from_commands_generation(self):
        inputs = [
            {"kind": "input", "line": 1, "time": 0.1,
             "message": "keyboard-message", "source": "pc_keyboard"},
            {"kind": "input", "line": 2, "time": 0.2,
             "message": "gamepad-message", "source": "pc_gamepad"},
        ]
        mappings = [{"start_line": 1, "end_line": 2, "kind": "raw"}]
        generated = generate_intermediate(
            {"session_id": "without-keyboard"}, inputs, mappings)
        self.assertFalse(input_row_is_commands_recordable(inputs[0]))
        self.assertTrue(input_row_is_commands_recordable(inputs[1]))
        self.assertNotIn("keyboard-message", generated)
        self.assertIn("gamepad-message", generated)

    def test_function_range_is_called_in_order_inside_step_without_duplication(self):
        session = {"session_id": "session-a"}
        mappings = [
            {"start_line": 1, "end_line": 6, "kind": "step",
             "step_name": "STEP_A", "next_step": "STEP_B"},
            {"start_line": 2, "end_line": 3, "kind": "function",
             "function_name": "turn_corner", "call_from_step": "STEP_A"},
            {"start_line": 4, "end_line": 5, "kind": "ignore",
             "notes": "mistake during manual play"},
        ]
        generated = generate_intermediate(session, self._inputs(), mappings)
        self.assertIn("def STEP_A(self):", generated)
        self.assertIn("self.turn_corner()", generated)
        self.assertIn("def turn_corner(self):", generated)
        self.assertIn("return 'STEP_B'", generated)
        for line in (1, 2, 3, 6):
            self.assertEqual(generated.count("message-{}".format(line)), 1)
        for line in (4, 5):
            self.assertNotIn("message-{}".format(line), generated)
        self.assertEqual(pending_lines(self._inputs(), mappings), [])

    def test_generated_region_is_inserted_in_selected_class_and_updated_in_place(self):
        source = "class Story(object):\n    def existing(self):\n        pass\n"
        generated = ("# POKECON_OPERATION_SESSION:s1:BEGIN\n"
                     "def STEP_A(self):\n"
                     "    pass\n"
                     "# POKECON_OPERATION_SESSION:s1:END\n")
        updated = replace_generated_region(source, generated, "s1", class_name="Story")
        self.assertEqual(source_class_names(updated), ["Story"])
        self.assertIn("    def STEP_A(self):", updated)
        ast.parse(updated)
        changed = generated.replace("pass", "return 'NEXT'")
        replaced = replace_generated_region(updated, changed, "s1", class_name="Story")
        self.assertEqual(replaced.count("POKECON_OPERATION_SESSION:s1:BEGIN"), 1)
        self.assertIn("return 'NEXT'", replaced)
        ast.parse(replaced)

    def test_existing_method_is_replaced_instead_of_duplicated(self):
        source = ("class Story(object):\n"
                  "    def STEP_A(self):\n"
                  "        return 'OLD'\n")
        generated = ("# POKECON_OPERATION_SESSION:s2:BEGIN\n"
                     "def STEP_A(self):\n"
                     "    return 'NEW'\n"
                     "# POKECON_OPERATION_SESSION:s2:END\n")
        updated = replace_generated_region(source, generated, "s2", class_name="Story")
        self.assertEqual(updated.count("def STEP_A"), 1)
        self.assertNotIn("return 'OLD'", updated)
        self.assertIn("return 'NEW'", updated)
        ast.parse(updated)

    def test_mapping_draft_is_persistent_and_searchable_after_reload(self):
        from OperationSessionModel import load_mappings
        with tempfile.TemporaryDirectory() as folder:
            saved = save_mappings(folder, [{
                "start_line": 7, "end_line": 9, "kind": "function",
                "function_name": "move_to_door", "notes": "hotel",
            }])
            loaded = load_mappings(folder)
            self.assertEqual(loaded, saved)
            self.assertEqual(loaded[0]["function_name"], "move_to_door")

    def test_portable_generation_uses_editable_semantic_game_inputs(self):
        inputs = [
            {"kind": "input", "line": 1, "time": 1.0,
             "message": "switch-press", "buttons": ["A"], "hat": "RIGHT",
             "left_stick": {"angle": 90.0, "magnitude": 1.0},
             "right_stick": None},
            {"kind": "input", "line": 2, "time": 1.5,
             "message": "switch-neutral", "buttons": [], "hat": "CENTER",
             "left_stick": None, "right_stick": None},
        ]
        mappings = [{"start_line": 1, "end_line": 2, "kind": "step",
                     "step_name": "PORTABLE_STEP", "next_step": ""}]
        generated = generate_intermediate(
            {"session_id": "portable"}, inputs, mappings,
            generation_target=GENERATION_TARGET_PORTABLE)
        self.assertIn("Steam_Switch_Game_Input", generated)
        self.assertIn("self.game_input_state(", generated)
        self.assertIn("['A', 'Lbutton_right', 'Lstick@90.00/1.0000']", generated)
        self.assertIn("duration=0.5", generated)
        self.assertNotIn("self.direct_serial(", generated)
        self.assertIn("game_image_profiles", generated)
        ast.parse(generated)

        eight_way = generate_intermediate(
            {"session_id": "portable"}, inputs, mappings,
            generation_target=GENERATION_TARGET_PORTABLE,
            stick_mode=STICK_MODE_EIGHT_WAY)
        self.assertIn("['A', 'Lbutton_right', 'Lstick_up']", eight_way)
        self.assertNotIn("Lstick@", eight_way)

    def test_switch_stick_generation_defaults_to_exact_and_can_use_eight_way(self):
        row = {
            "kind": "input", "line": 1, "time": 1.0,
            "message": "0x0002 8 b5 6a", "buttons": [], "hat": "CENTER",
            "left_stick": {"angle": 20.0, "magnitude": 0.5},
            "right_stick": None,
        }
        mappings = [{"start_line": 1, "end_line": 1, "kind": "raw"}]
        exact = generate_intermediate(
            {"session_id": "exact"}, [row], mappings)
        self.assertIn("0x0002 8 b5 6a", exact)

        quantized_message = quantize_serial_stick_message(row)
        self.assertEqual(quantized_message, "0x0002 8 c0 80")
        eight_way = generate_intermediate(
            {"session_id": "eight"}, [row], mappings,
            stick_mode=STICK_MODE_EIGHT_WAY)
        self.assertIn("0x0002 8 c0 80", eight_way)
        self.assertNotIn("0x0002 8 b5 6a", eight_way)

    def test_semantic_stick_names_are_quantized_to_eight_directions(self):
        row = {"buttons": ["ZR"], "hat": "UP_LEFT",
               "left_stick": {"angle": 315.0, "magnitude": 0.8},
               "right_stick": {"angle": 180.0, "magnitude": 0.7}}
        self.assertEqual(semantic_controls(row), [
            "ZR", "Lbutton_up_left", "Lstick_down_right", "Rstick_left"])

    def test_game_input_sample_has_late_key_and_image_overrides(self):
        root = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "SerialController", "DevTemplates",
            "Fragments", "game_input_router"))
        with open(os.path.join(root, "game_input_router.pyfrag"),
                  "r", encoding="utf-8") as stream:
            fragment = stream.read()
        ast.parse(fragment)
        self.assertIn("def game_input_state", fragment)
        self.assertIn("def set_game_input_mapping", fragment)
        self.assertIn("def set_game_image_mapping", fragment)
        self.assertIn("def game_image_check", fragment)
        with open(os.path.join(root, "game_input_router.pokesample.json"),
                  "r", encoding="utf-8") as stream:
            sample = json.load(stream)
        self.assertIn("Direction", sample["imports"][0])
        self.assertIn("Stick", sample["imports"][0])

        namespace = {}
        exec(compile(fragment, "game_input_router.pyfrag", "exec"), namespace)
        methods = {name: value for name, value in namespace.items()
                   if inspect.isfunction(value)}
        PortableCommand = type("PortableCommand", (), methods)
        command = PortableCommand()
        command.game_input_target = "steam"
        command.game_input_profiles = [{"A": ["enter"]}]
        keyboard_calls = []
        command.steam_keyboard_press = lambda *keys, **options: keyboard_calls.append(
            (keys, options))
        command.select_game_input_profile(0)
        command.game_input_state(["A", "Lstick_up"], duration=0.4, wait=0.0)
        self.assertEqual(keyboard_calls[-1][0][:2], ("enter", "w"))
        command.game_input_state(["Lstick@136.25/0.8000"], wait=0.0)
        self.assertEqual(keyboard_calls[-1][0][:2], ("w", "a"))
        command.set_game_input_mapping("A", "space")
        command.game_input("A", duration=0.2, wait=0.0)
        self.assertEqual(keyboard_calls[-1][0][0], "space")

        switch_calls = []
        command.game_input_target = "switch"
        command.press = lambda controls, **options: switch_calls.append(
            (controls, options))
        command.game_input_state(["A", "Lstick_up"], duration=0.3, wait=0.0)
        self.assertEqual(len(switch_calls[-1][0]), 2)
        self.assertEqual(switch_calls[-1][1]["duration"], 0.3)
        command.game_input_state(["Lstick@136.25/0.8000"], wait=0.0)
        exact_stick = switch_calls[-1][0][0]
        self.assertAlmostEqual(exact_stick.angle_for_show, 136.25)
        self.assertAlmostEqual(exact_stick.mag, 0.8)

        command.image_check = lambda name, flag=1: (name, flag)
        command.game_input_target = "steam"
        self.assertEqual(command.game_image_check("READY"), ("READY", 1))
        command.set_game_image_mapping("steam", "READY", "READY_STEAM")
        self.assertEqual(command.game_image_check("READY"), ("READY_STEAM", 1))

    def test_video_vision_sample_is_separate_parseable_and_logs_support(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = vision_output_paths(folder)
            image_path = os.path.join(paths["image_dir"], "step_a.png")
            metadata = {"candidates": [{
                "step_name": "STEP_A", "next_step": "STEP_B",
                "logical_name": "AUTO_STEP_A_COMPLETE",
                "video_time": 12.4, "confidence": 0.78,
                "template_path": image_path, "roi": [100, 80, 400, 220],
                "threshold": 0.82,
            }]}
            source = generate_vision_sample(
                folder, {"session_id": "vision-test"}, metadata,
                support_timeout=1.0)
            ast.parse(source)
            self.assertIn("POKECON_OPERATION_VISION_SAMPLE", source)
            self.assertNotIn("POKECON_OPERATION_SESSION:vision-test:BEGIN", source)
            self.assertIn("def VISION_SAMPLE_STEP_A", source)
            self.assertIn("support_requested", source)
            self.assertIn("support_completed", source)

            namespace = {}
            exec(compile(source, "vision_sample.py", "exec"), namespace)
            methods = {name: value for name, value in namespace.items()
                       if inspect.isfunction(value)}
            SampleCommand = type("SampleCommand", (), methods)
            command = SampleCommand()
            results = iter((False, False, True))
            recorded = []
            command.STEP_A = lambda: recorded.append("STEP_A")
            command._operation_sample_detect = lambda *_args, **_options: next(results)
            command.wait = lambda _seconds: None
            self.assertEqual(command.VISION_SAMPLE_STEP_A(), "STEP_B")
            self.assertEqual(recorded, ["STEP_A"])
            with open(paths["support_log"], "r", encoding="utf-8") as stream:
                events = [json.loads(line)["event"] for line in stream if line.strip()]
            self.assertEqual(events, ["support_requested", "support_completed"])

    def test_debug_command_package_is_runnable_versioned_and_final_is_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            session = {"session_id": "debug-session", "name": "Route debug"}
            intermediate = (
                "# POKECON_OPERATION_SESSION:debug-session:BEGIN\n"
                "def STEP_A(self):\n"
                "    self.wait(0.1)\n"
                "# POKECON_OPERATION_SESSION:debug-session:END\n")
            paths = vision_output_paths(folder)
            template = os.path.join(paths["image_dir"], "step_a.png")
            metadata = {"candidates": [{
                "step_name": "STEP_A", "next_step": "STEP_B",
                "logical_name": "AUTO_STEP_A_COMPLETE", "video_time": 1.0,
                "confidence": 0.8, "template_path": template,
                "roi": [10, 20, 110, 70], "frame_size": [1280, 720],
                "threshold": 0.82,
            }]}
            vision = generate_vision_sample(folder, session, metadata, support_timeout=1.0)
            revision = save_intermediate_revision(folder, intermediate, "switch")
            final_path = os.path.join(folder, "final_command.py")
            with open(final_path, "w", encoding="utf-8") as stream:
                stream.write("FINAL_SOURCE = True\n")
            package = create_debug_command_package(
                folder, session, intermediate, vision, metadata,
                [{"kind": "step", "step_name": "STEP_A"}],
                intermediate_revision=revision)
            with open(package["working"], "r", encoding="utf-8") as stream:
                debug_source = stream.read()
            ast.parse(debug_source)
            self.assertIn("class Route_debug_DebugCommand", debug_source)
            self.assertIn("NAME = '[DEBUG] Route debug'", debug_source)
            self.assertIn("self.VISION_SAMPLE_STEP_A()", debug_source)
            self.assertTrue(os.path.abspath(template).startswith(
                debug_output_paths(folder)["templates"]))
            with open(final_path, "r", encoding="utf-8") as stream:
                self.assertEqual(stream.read(), "FINAL_SOURCE = True\n")

            with open(package["working"], "a", encoding="utf-8") as stream:
                stream.write("# manual debug adjustment\n")
            regenerated = create_debug_command_package(
                folder, session, intermediate, vision, metadata,
                [{"kind": "step", "step_name": "STEP_A"}],
                intermediate_revision=revision)
            self.assertTrue(os.path.isfile(regenerated["working_backup"]))
            with open(regenerated["working_backup"], "r", encoding="utf-8") as stream:
                self.assertIn("manual debug adjustment", stream.read())

            second = save_intermediate_revision(
                folder, intermediate.replace("0.1", "0.2"), "switch")
            self.assertEqual(intermediate_revisions(folder), [revision, second])
            deployed = deploy_debug_command(
                package["working"], folder, "debug-session")
            self.assertTrue(deployed.endswith(os.path.join(
                "GeneratedDebug", "debug_session_debug.py")))
            with open(deployed, "r", encoding="utf-8") as stream:
                ast.parse(stream.read())

    def test_unassigned_long_recording_gets_bounded_debug_only_draft_steps(self):
        inputs = [
            {"kind": "input", "line": index + 1, "time": index * 0.25,
             "message": "message-{}".format(index + 1)}
            for index in range(2000)
        ]
        mappings = build_debug_draft_mappings(
            inputs, center_time=200.0, window_seconds=60.0,
            step_seconds=12.0, max_steps=5)
        self.assertEqual(len(mappings), 5)
        self.assertTrue(all(item["kind"] == "step" for item in mappings))
        self.assertTrue(all(item["step_name"].startswith("DEBUG_AUTO_STEP_")
                            for item in mappings))
        self.assertGreaterEqual(mappings[0]["start_line"], 780)
        self.assertIn("最終版へ反映しない", mappings[0]["notes"])


if __name__ == "__main__":
    unittest.main()
