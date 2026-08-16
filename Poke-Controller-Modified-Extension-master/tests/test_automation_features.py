import datetime
import ast
import inspect
import os
import queue
import sys
import json
import tempfile
import threading
import time
import types
import unittest
import struct
import wave
import cv2
import numpy
from PIL import Image
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
                                format_function_update_status,
                                function_update_status,
                                function_records as sample_sync_function_records,
                                latest_sample_sync_backup,
                                mark_comparisons_synchronized,
                                merge_sample_names_with_source_bodies,
                                reflect_fragment_function_text,
                                fragment_function_stats,
                                remove_fragment_function_text,
                                replace_fragment_function_text,
                                replace_class_functions,
                                restore_sample_sync_backup,
                                resolve_fragment_folder,
                                save_reflected_source,
                                side_by_side_diff_rows,
                                source_paths_equivalent,
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
from SourceFunctionTools import (build_rename_map,
                                 classify_function_registration,
                                 function_content_hash,
                                 register_source_functions,
                                 rename_source_functions, source_function_records,
                                 step_function_names)
from SourceDependencyTools import (analyze_source_dependencies,
                                   analyze_state_dictionary_dependencies,
                                   catalog_function_candidates,
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
from PokeConDevStudio import find_match_index, pack_scrollable_widget
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
                                     last_active_pokecon_pid,
                                     main_resource_conflicts,
                                     process_identity, read_active_input_sets)
from PokeConRecovery import (PokeConRecoveryError, discover_running_pokecon,
                             force_terminate, request_normal_close,
                             validate_recovery_target)
from ResourceControl import (clamp_cpu_target, resource_throttle_level,
                             throttle_multiplier)
from ImageDetectionMonitor import (filter_target_names,
                                   format_show_value_blocks,
                                   format_show_value_entries,
                                   load_detection_library,
                                   matched_show_value_spans,
                                   padded_search_crop,
                                   prune_show_value_entries,
                                   update_show_value_entries)
from ImageHealthCheck import audit_image_library, suggested_crop
from ImageCheckReferenceAudit import (audit_image_check_references,
                                      merge_library_targets_into_source,
                                      preserve_library_import_block)
from ImageDetectionLibrary import (filter_image_library_variants,
                                   generate_image_check,
                                   image_preview_size)
from CompletionEngine import CompletionEngine
from Camera import (Camera, camera_fourcc_name,
                    camera_frame_freshness_timeout, camera_reader_backoff)
from Commands.PythonCommandBase import (ImageProcPythonCommand,
                                        PythonCommand)
from LocalFunction.ImageDetection import _command_frame
from AudioMonitor import (AudioMonitor, StreamingAudioRateConverter,
                          fit_audio_block, plan_audio_buffer_consume)
from AudioLevelControl import (AdaptivePeakNormalizer,
                               sanitize_audio_level_settings,
                               suggest_audio_level_settings)
from WindowsAudioIdentity import (enrich_saved_audio_identity,
                                  identity_for_audio_label,
                                  normalized_audio_name,
                                  physical_usb_key,
                                  resolve_saved_audio,
                                  upgrade_input_set_audio_identities,
                                  usb_connection_token)
from GuiAssets import (CaptureArea, hold_last_preview_on_missing_frame,
                       prepare_disabled_preview_image,
                       prepare_preview_image)
from PokeConShowInfo import (installed_distribution_version,
                             requirement_distribution_name)
from Recording import (CaptureRecorder, audio_callback_presentation_time,
                       evenly_spaced_frame_indexes)
from RecordingSyncRepair import (audio_advance_filter, wav_info,
                                 write_presentation_aligned_audio,
                                 write_without_exact_zeros)
from UiResponsiveness import (compensated_after_delay,
                              confirmation_audio_action,
                              dialog_owner_attachment_allowed,
                              foreground_process_id,
                              foreground_process_matches,
                              keyboard_listener_should_run,
                              preview_capture_interval, preview_priority,
                              preview_rate_permissions,
                              preview_render_due, preview_render_interval,
                              resize_safe_preview_intervals)
from VideoInputPolicy import (consume_combobox_mousewheel,
                              guard_combobox_mousewheel,
                              is_pokecon_window_title)
from CommandMonitorRecording import (CommandInputActivityTracker,
                                     CommandStateTimeline, DarkStillFrameDetector,
                                     apply_stopped_session_recording_choice,
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
from Keyboard import SwitchKeyboardController
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

    def test_manual_input_follows_foreground_pokecon_then_survives_browser(self):
        entries = [
            {"pid": 501, "token": "first", "started_at": "2026-08-16T10:00:00",
             "last_focused_ns": 100},
            {"pid": 502, "token": "second", "started_at": "2026-08-16T10:01:00",
             "last_focused_ns": 200},
        ]
        # Clicking a PokeCon switches immediately even before its asynchronous
        # focus marker reaches the shared registry.
        self.assertEqual(last_active_pokecon_pid(entries, foreground_pid=501), 501)
        # Chrome is not a registered PokeCon, so the last selected PokeCon is
        # retained as the keyboard/gamepad input target.
        self.assertEqual(last_active_pokecon_pid(entries, foreground_pid=999), 502)
        self.assertEqual(last_active_pokecon_pid(entries, foreground_pid=None), 502)

    def test_manual_input_owner_uses_newest_only_before_any_focus_marker(self):
        entries = [
            {"pid": 601, "started_at": "2026-08-16T10:00:00"},
            {"pid": 602, "started_at": "2026-08-16T10:01:00"},
        ]
        self.assertEqual(last_active_pokecon_pid(entries, foreground_pid=999), 602)
        self.assertIsNone(last_active_pokecon_pid([], foreground_pid=602))

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

    def test_confirmation_audio_output_claim_is_machine_wide(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, "active_windows.json")
            provider = lambda pid: "{}:start".format(pid)
            first = ActiveInputSetRegistry(
                path, identity_provider=provider, token="first", pid=611)
            second = ActiveInputSetRegistry(
                path, identity_provider=provider, token="second", pid=612)
            output_key = canonical_device_key(
                "audio_output", "confirmation")
            first.set_device(
                "audio_output", output_key,
                "PokeCon confirmation playback")
            conflicts = device_usage_conflicts(
                second.entries(include_self=False),
                "audio_output", output_key)
            self.assertEqual([entry["pid"] for entry in conflicts], [611])
            first.set_device("audio_output", "", "")
            self.assertEqual(device_usage_conflicts(
                second.entries(include_self=False),
                "audio_output", output_key), [])

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


class PokeConRecoveryTests(unittest.TestCase):
    def test_discovery_merges_profile_input_set_with_machine_activity(self):
        with tempfile.TemporaryDirectory() as temporary:
            profiles = os.path.join(temporary, "profiles")
            profile_dir = os.path.join(profiles, "default")
            os.makedirs(profile_dir)
            input_path = os.path.join(profile_dir, "active_input_sets.json")
            activity_path = os.path.join(temporary, "active_windows.json")
            identities = {101: "101:start-a", 202: "202:start-b"}
            provider = lambda pid: identities.get(pid)

            input_registry = ActiveInputSetRegistry(
                input_path, profile="default", identity_provider=provider,
                token="input", pid=101)
            input_registry.set_active("Switch_No1", "Switch 1")
            activity_registry = ActiveInputSetRegistry(
                activity_path, profile="default", identity_provider=provider,
                token="activity", pid=101)
            activity_registry.mark_focused(marker=10)
            activity_registry.set_resource_state(main_requested=True)
            unselected_registry = ActiveInputSetRegistry(
                activity_path, profile="spare", identity_provider=provider,
                token="unselected", pid=202)
            unselected_registry.mark_focused(marker=20)

            entries = discover_running_pokecon(
                profiles, identity_provider=provider, activity_path=activity_path)
            self.assertEqual([entry["pid"] for entry in entries], [202, 101])
            selected = next(entry for entry in entries if entry["pid"] == 101)
            self.assertEqual(selected["input_set"], "Switch_No1")
            self.assertEqual(selected["combined_set"], "Switch 1")
            self.assertTrue(selected["resource"]["main_effective"])

    def test_discovery_keeps_duplicate_input_set_processes_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            profiles = os.path.join(temporary, "profiles")
            profile_dir = os.path.join(profiles, "default")
            os.makedirs(profile_dir)
            input_path = os.path.join(profile_dir, "active_input_sets.json")
            activity_path = os.path.join(temporary, "missing_activity.json")
            identities = {301: "301:start-a", 302: "302:start-b"}
            provider = lambda pid: identities.get(pid)
            first = ActiveInputSetRegistry(
                input_path, identity_provider=provider, token="first", pid=301)
            second = ActiveInputSetRegistry(
                input_path, identity_provider=provider, token="second", pid=302)
            first.set_active("SameInputSet")
            second.set_active("SameInputSet")

            entries = discover_running_pokecon(
                profiles, identity_provider=provider, activity_path=activity_path)
            self.assertEqual([entry["pid"] for entry in entries], [301, 302])

    def test_pid_reuse_is_rejected_before_recovery_action(self):
        entry = {"pid": 401, "process_identity": "401:old"}
        with self.assertRaises(PokeConRecoveryError):
            validate_recovery_target(
                entry, identity_provider=lambda _pid: "401:new", self_pid=999)

    def test_force_terminate_targets_one_verified_pokecon_only(self):
        identities = {501: "501:start"}
        terminated = []
        entry = {"pid": 501, "process_identity": "501:start"}
        result = force_terminate(
            entry, identity_provider=lambda pid: identities.get(pid),
            window_provider=lambda _pid: [
                (11, "Poke-Controller Modified Extension ver.0.1.7")],
            terminator=terminated.append, self_pid=999)
        self.assertEqual(result, 501)
        self.assertEqual(terminated, [501])

    def test_force_terminate_refuses_non_pokecon_window(self):
        terminated = []
        entry = {"pid": 601, "process_identity": "601:start"}
        with self.assertRaises(PokeConRecoveryError):
            force_terminate(
                entry, identity_provider=lambda _pid: "601:start",
                window_provider=lambda _pid: [(12, "Google Chrome")],
                terminator=terminated.append, self_pid=999)
        self.assertEqual(terminated, [])

    def test_normal_close_posts_only_to_pokecon_main_window(self):
        posted = []
        entry = {"pid": 701, "process_identity": "701:start"}
        result = request_normal_close(
            entry, identity_provider=lambda _pid: "701:start",
            window_provider=lambda _pid: [
                (21, "PokeCon 固まり復旧"),
                (22, "Poke-Controller Modified Extension ver.0.1.7")],
            post_close=lambda hwnd: posted.append(hwnd) or True,
            self_pid=999)
        self.assertEqual(result, 701)
        self.assertEqual(posted, [22])


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
    def test_image_library_can_filter_grayscale_and_color_variants(self):
        library = {"targets": {
            "MIXED": {
                "description": "two modes", "tags": ["Common"],
                "variants": [
                    {"template_path": "Template/gray.png", "use_gray": True},
                    {"template_path": "Template/color.png", "use_gray": False},
                ],
            },
            "DEFAULT_GRAY": {
                "description": "use_gray omitted",
                "variants": [{"template_path": "Template/default.png"}],
            },
        }}
        self.assertEqual(filter_image_library_variants(library), [
            ("DEFAULT_GRAY", 0), ("MIXED", 0), ("MIXED", 1),
        ])
        self.assertEqual(filter_image_library_variants(library, grayscale="ON"), [
            ("DEFAULT_GRAY", 0), ("MIXED", 0),
        ])
        self.assertEqual(filter_image_library_variants(library, grayscale="OFF"), [
            ("MIXED", 1),
        ])
        self.assertEqual(
            filter_image_library_variants(library, "common", "OFF"),
            [("MIXED", 1)])

    def test_image_library_can_exclude_template_folders(self):
        library = {"targets": {
            "SAMPLE": {"variants": [{
                "template_path": "Template/Samples/demo.png"}]},
            "SAMPLE_TWO": {"variants": [{
                "template_path": "Template/Samples2/keep.png"}]},
            "DEBUG": {"variants": [{
                "template_path": "Template/Debug/test.png"}]},
            "STORY": {"variants": [{
                "template_path": "Template/ZA_Story/event.png"}]},
        }}
        self.assertEqual(
            filter_image_library_variants(
                library, excluded_folders="Template/Samples; Template/Debug"),
            [("SAMPLE_TWO", 0), ("STORY", 0)])
        self.assertEqual(
            filter_image_library_variants(
                library, excluded_folders="Template\\Samples\nTemplate/Debug"),
            [("SAMPLE_TWO", 0), ("STORY", 0)])

    def test_image_library_preview_preserves_aspect_ratio(self):
        self.assertEqual(image_preview_size(1280, 720), (391, 220))
        self.assertEqual(image_preview_size(20, 10), (80, 40))
        with self.assertRaises(ValueError):
            image_preview_size(0, 10)

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
        self.assertLess(text.index("[ShowValue] MENU"),
                        text.index("[ShowValue] FIELD"))

        blocks = format_show_value_blocks(entries, "ShowValue")
        self.assertEqual([matched for _text, matched in blocks], [True, False])
        self.assertEqual(
            matched_show_value_spans(blocks),
            [(0, len(blocks[0][0]))])

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
        self.assertIn("image_check_confirmation", generated)

        source_path = os.path.join(
            SERIAL_CONTROLLER, "Commands", "PythonCommands", "ZA",
            "ZA_story", "ZA_story.py")
        with open(source_path, "r", encoding="utf-8-sig") as stream:
            source = stream.read()
        source_tree = ast.parse(source)
        source_targets = ast.literal_eval(next(
            node.value for node in ast.walk(source_tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name)
                    and target.id == "IMAGE_DETECTION_TARGETS"
                    for target in node.targets)))
        self.assertEqual(
            source_targets["POKEMON_ZA_KOHUKI_ICON_GET5"],
            targets["POKEMON_ZA_KOHUKI_ICON_GET5"]["variants"])
        self.assertRegex(
            source,
            r'image_check\("POKEMON_ZA_KOHUKI_ICON_GET4"\)\s*'
            r'and self\.image_check\("POKEMON_ZA_KOHUKI_ICON_GET5"\)')

    def test_za_white_comment_accepts_both_arrow_animation_states(self):
        profile_path = os.path.join(
            SERIAL_CONTROLLER, "Template", "image_detection_profiles.json")
        with open(profile_path, "r", encoding="utf-8") as stream:
            library = json.load(stream)

        variants = library["targets"][
            "POKEMON_ZA_TEXT_WHITE_COMMENT"]["variants"]
        template_paths = {variant["template_path"] for variant in variants}
        self.assertEqual(template_paths, {
            "Template/ZA_Story/Common/white_comment.png",
            "Template/ZA_Story/Common/white_comment2.png",
        })
        self.assertEqual({tuple(variant["crop"]) for variant in variants}, {
            (300, 555, 1000, 700),
        })

        source_path = os.path.join(
            SERIAL_CONTROLLER, "Commands", "PythonCommands", "ZA",
            "ZA_story", "ZA_story.py")
        with open(source_path, "r", encoding="utf-8-sig") as stream:
            source = stream.read()
        source_tree = ast.parse(source)
        source_targets = ast.literal_eval(next(
            node.value for node in ast.walk(source_tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name)
                    and target.id == "IMAGE_DETECTION_TARGETS"
                    for target in node.targets)))
        self.assertEqual(
            source_targets["POKEMON_ZA_TEXT_WHITE_COMMENT"], variants)
        self.assertNotIn("def image_check_confirmation", source)

    def test_za_marker_positions_are_registered_and_steer_toward_center(self):
        profile_path = os.path.join(
            SERIAL_CONTROLLER, "Template", "image_detection_profiles.json")
        with open(profile_path, "r", encoding="utf-8") as stream:
            library = json.load(stream)

        map_exclusion = [0, 0, 210, 210]
        left_wide_upper = [210, 100, 680, 240]
        regions = {
            "CENTER": [640, 100, 680, 600],
            "CENTER_WIDE": [600, 100, 720, 600],
            "CENTER_WIDE_UPPER": [600, 0, 700, 130],
            "CENTER_WIDE_UPPER_LEFT": [210, 0, 650, 130],
            "CENTER_WIDE_UPPER_RIGHT": [650, 0, 1210, 130],
            "CENTER_WIDE_UPPER_LEFT_NEAR": [450, 0, 650, 130],
            "CENTER_WIDE_UPPER_RIGHT_NEAR": [650, 0, 850, 130],
            "CENTER_WIDE_DOWNER": [600, 570, 700, 720],
            "CENTER_WIDE_DOWNER_LEFT": [70, 570, 650, 720],
            "CENTER_WIDE_DOWNER_RIGHT": [650, 570, 1210, 720],
            "CENTER_WIDE_DOWNER_LEFT_NEAR": [450, 570, 650, 720],
            "CENTER_WIDE_DOWNER_RIGHT_NEAR": [650, 570, 850, 720],
            "CENTER_LEFT_SIDE": [0, 210, 100, 720],
            "CENTER_RIGHT_SIDE": [1180, 0, 1280, 720],
            "LEFT_WIDE": [70, 210, 680, 600],
            "RIGHT_WIDE": [640, 100, 1210, 600],
        }
        minimum_overlap = 30
        for upper, middle, downer in (
                ("CENTER_WIDE_UPPER", "CENTER", "CENTER_WIDE_DOWNER"),
                ("CENTER_WIDE_UPPER_RIGHT", "RIGHT_WIDE",
                 "CENTER_WIDE_DOWNER_RIGHT")):
            self.assertGreaterEqual(
                regions[upper][3] - regions[middle][1], minimum_overlap)
            self.assertGreaterEqual(
                regions[middle][3] - regions[downer][1], minimum_overlap)
        self.assertGreaterEqual(
            regions["CENTER_WIDE_UPPER_LEFT"][3] - left_wide_upper[1],
            minimum_overlap)
        self.assertGreaterEqual(
            left_wide_upper[3] - regions["LEFT_WIDE"][1],
            minimum_overlap)
        self.assertGreaterEqual(
            regions["LEFT_WIDE"][3]
            - regions["CENTER_WIDE_DOWNER_LEFT"][1], minimum_overlap)
        for suffix in ("LEFT_WIDE", "CENTER_WIDE_DOWNER_LEFT"):
            self.assertGreaterEqual(
                regions["CENTER_LEFT_SIDE"][2] - regions[suffix][0],
                minimum_overlap)
        for suffix in ("RIGHT_WIDE", "CENTER_WIDE_UPPER_RIGHT",
                       "CENTER_WIDE_DOWNER_RIGHT"):
            self.assertGreaterEqual(
                regions[suffix][2] - regions["CENTER_RIGHT_SIDE"][0],
                minimum_overlap)
        for center, left, right in (
                ("CENTER_WIDE_UPPER", "CENTER_WIDE_UPPER_LEFT",
                 "CENTER_WIDE_UPPER_RIGHT"),
                ("CENTER_WIDE_DOWNER", "CENTER_WIDE_DOWNER_LEFT",
                 "CENTER_WIDE_DOWNER_RIGHT")):
            self.assertGreaterEqual(
                regions[left][2] - regions[center][0], minimum_overlap)
            self.assertGreaterEqual(
                regions[center][2] - regions[right][0], minimum_overlap)
        for center, left_near, right_near in (
                ("CENTER_WIDE_UPPER", "CENTER_WIDE_UPPER_LEFT_NEAR",
                 "CENTER_WIDE_UPPER_RIGHT_NEAR"),
                ("CENTER_WIDE_DOWNER", "CENTER_WIDE_DOWNER_LEFT_NEAR",
                 "CENTER_WIDE_DOWNER_RIGHT_NEAR")):
            self.assertGreaterEqual(
                regions[left_near][2] - regions[center][0], minimum_overlap)
            self.assertGreaterEqual(
                regions[center][2] - regions[right_near][0], minimum_overlap)
        marker_settings = {
            "EVENT_MARKER": ("event_marker.png", False),
            "PIN_MARKER": ("pin_marker.png", True),
            "SIDE_MARKER": ("side_marker.png", False),
        }
        common_members = {
            member["id"]
            for member in library["lists"]["POKEMON_ZA_FOLDER_COMMON"]["members"]
            if member.get("type") == "target"
        }
        for marker, (template_name, use_gray) in marker_settings.items():
            for suffix, crop in regions.items():
                name = "POKEMON_ZA_{}_{}".format(marker, suffix)
                expected_crops = [crop]
                if suffix == "LEFT_WIDE":
                    expected_crops.append(left_wide_upper)
                variants = library["targets"][name]["variants"]
                self.assertEqual(
                    [variant["crop"] for variant in variants],
                    expected_crops, name)
                for variant in variants:
                    self.assertTrue(
                        variant["template_path"].endswith(template_name), name)
                    self.assertEqual(variant["use_gray"], use_gray, name)
                    self.assertEqual(variant["threshold"], 0.8, name)
                    has_map_overlap = (
                        max(variant["crop"][0], map_exclusion[0])
                        < min(variant["crop"][2], map_exclusion[2])
                        and max(variant["crop"][1], map_exclusion[1])
                        < min(variant["crop"][3], map_exclusion[3]))
                    self.assertFalse(has_map_overlap, name)
                self.assertIn(name, common_members)

        generated = generate_image_check(library, "POKEMON_ZA_ALL", "list")
        for marker in marker_settings:
            self.assertIn(
                "POKEMON_ZA_{}_CENTER_WIDE_DOWNER".format(marker), generated)

        source_path = os.path.join(
            SERIAL_CONTROLLER, "Commands", "PythonCommands", "ZA",
            "ZA_story", "ZA_story.py")
        with open(source_path, "r", encoding="utf-8-sig") as stream:
            source = stream.read()
        managed_imports = source.split(
            "# POKECON_IMAGE_CHECK_LIBRARY_IMPORTS_BEGIN", 1)[1].split(
                "# POKECON_IMAGE_CHECK_LIBRARY_IMPORTS_END", 1)[0]
        managed_tree = ast.parse("def _managed_imports():\n" + managed_imports)
        managed_update = next(
            node for node in ast.walk(managed_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "IMAGE_DETECTION_TARGETS"
            and node.func.attr == "update")
        managed_targets = ast.literal_eval(managed_update.args[0])
        for marker in marker_settings:
            for suffix in regions:
                name = "POKEMON_ZA_{}_{}".format(marker, suffix)
                self.assertIn(repr(name), managed_imports)
                expected_crops = [regions[suffix]]
                if suffix == "LEFT_WIDE":
                    expected_crops.append(left_wide_upper)
                self.assertEqual(
                    [variant["crop"] for variant in managed_targets[name]],
                    expected_crops, name)
                self.assertTrue(all(
                    variant["threshold"] == 0.8
                    for variant in managed_targets[name]), name)

        fragment_path = os.path.join(
            SERIAL_CONTROLLER, "DevTemplates", "Fragments", "SourceImports",
            "ZA_markerdir", "ZA_markerdir.pyfrag")
        with open(fragment_path, "r", encoding="utf-8") as stream:
            fragment = stream.read()
        namespace = {"Direction": Direction, "Stick": Stick}
        exec(compile(fragment, fragment_path, "exec"), namespace)
        markerdir = namespace["ZA_markerdir"]
        fragment_function = ast.parse(fragment).body[0]
        runtime_function = next(
            node for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.FunctionDef)
            and node.name == "ZA_markerdir")
        self.assertEqual(
            ast.dump(runtime_function, include_attributes=False),
            ast.dump(fragment_function, include_attributes=False))

        class MarkerCommand:
            def __init__(self, matched):
                self.matched = set(matched)
                self.pressed = []
                self.press_durations = []
                self.wait_durations = []

            def image_check(self, name):
                return name in self.matched

            def press(self, direction, duration=0.0, wait=0.0):
                self.pressed.append(direction)
                self.press_durations.append(duration)

            def wait(self, duration):
                self.wait_durations.append(duration)

        movement_cases = (
            ("CENTER_WIDE_DOWNER", 270, 0.0),
            ("CENTER_WIDE_UPPER", 90, 0.0),
            ("CENTER_WIDE_DOWNER_LEFT", 180, 0.03),
            ("CENTER_WIDE_DOWNER_RIGHT", 0, 0.03),
            ("CENTER_WIDE_UPPER_LEFT", 180, 0.03),
            ("CENTER_WIDE_UPPER_RIGHT", 0, 0.03),
            ("CENTER_LEFT_SIDE", 180, 0.03),
            ("CENTER_RIGHT_SIDE", 0, 0.03),
        )
        type_prefixes = {
            "EVENT": "POKEMON_ZA_EVENT_MARKER",
            "PIN": "POKEMON_ZA_PIN_MARKER",
            "SIDE_MARKER": "POKEMON_ZA_SIDE_MARKER",
        }
        for marker_type, prefix in type_prefixes.items():
            for suffix, angle, duration in movement_cases:
                command = MarkerCommand({prefix + "_" + suffix})
                self.assertFalse(markerdir(command, marker_type, nofiled=True))
                self.assertEqual(command.pressed[-1].angle_for_show, angle)
                self.assertAlmostEqual(command.press_durations[-1], duration)
                self.assertEqual(command.wait_durations[-1], 0.1)

        for marker_type, prefix in type_prefixes.items():
            right_side = prefix + "_CENTER_RIGHT_SIDE"
            command = MarkerCommand({right_side})
            self.assertFalse(markerdir(command, marker_type, nofiled=True))
            self.assertEqual(command.pressed[-1].angle_for_show, 0)
            self.assertEqual(command.pressed[-1].mag, 1.0)
            self.assertEqual(command.press_durations[-1], 0.03)

            command.matched.clear()
            press_count = len(command.pressed)
            self.assertFalse(markerdir(command, marker_type, nofiled=True))
            self.assertEqual(len(command.pressed), press_count + 1)
            self.assertEqual(command.pressed[-1].angle_for_show, 0)
            self.assertEqual(command.pressed[-1].mag, 1.0)
            self.assertEqual(command.press_durations[-1], 0.03)

            upper_left_near = prefix + "_CENTER_WIDE_UPPER_LEFT_NEAR"
            command.matched.add(upper_left_near)
            self.assertFalse(markerdir(command, marker_type, nofiled=True))
            self.assertEqual(command.pressed[-1].angle_for_show, 180)
            self.assertEqual(command.pressed[-1].mag, 0.2)
            self.assertEqual(command.press_durations[-1], 0.0)

            command.matched.clear()
            self.assertFalse(markerdir(command, marker_type, nofiled=True))
            self.assertEqual(command.pressed[-1].angle_for_show, 180)
            self.assertEqual(command.pressed[-1].mag, 0.2)
            self.assertEqual(command.press_durations[-1], 0.0)

            command.matched.add(prefix + "_CENTER")
            self.assertTrue(markerdir(command, marker_type, nofiled=True))
            command.matched.clear()
            self.assertFalse(markerdir(command, marker_type, nofiled=True))
            self.assertEqual(command.pressed[-1].angle_for_show, 180)
            self.assertEqual(command.pressed[-1].mag, 1.0)
            self.assertEqual(command.press_durations[-1], 0.0)

        near_movement_cases = (
            ("CENTER_WIDE_DOWNER_LEFT_NEAR", 180),
            ("CENTER_WIDE_DOWNER_RIGHT_NEAR", 0),
            ("CENTER_WIDE_UPPER_LEFT_NEAR", 180),
            ("CENTER_WIDE_UPPER_RIGHT_NEAR", 0),
        )
        for marker_type, prefix in type_prefixes.items():
            for suffix, angle in near_movement_cases:
                command = MarkerCommand({prefix + "_" + suffix})
                self.assertFalse(markerdir(command, marker_type, nofiled=True))
                self.assertEqual(command.pressed[-1].angle_for_show, angle)
                self.assertEqual(command.pressed[-1].mag, 0.2)
                self.assertEqual(command.press_durations[-1], 0.0)

        for marker_type, prefix in type_prefixes.items():
            for center_suffix, near_suffix, side_suffix, angle in (
                    ("CENTER_WIDE_UPPER", "CENTER_WIDE_UPPER_LEFT_NEAR",
                     "CENTER_WIDE_UPPER_LEFT", 90),
                    ("CENTER_WIDE_UPPER", "CENTER_WIDE_UPPER_RIGHT_NEAR",
                     "CENTER_WIDE_UPPER_RIGHT", 90),
                    ("CENTER_WIDE_DOWNER", "CENTER_WIDE_DOWNER_LEFT_NEAR",
                     "CENTER_WIDE_DOWNER_LEFT", 270),
                    ("CENTER_WIDE_DOWNER", "CENTER_WIDE_DOWNER_RIGHT_NEAR",
                     "CENTER_WIDE_DOWNER_RIGHT", 270)):
                command = MarkerCommand({prefix + "_" + center_suffix,
                                         prefix + "_" + near_suffix,
                                         prefix + "_" + side_suffix})
                self.assertFalse(
                    markerdir(command, marker_type, nofiled=True))
                self.assertEqual(command.pressed[-1].angle_for_show, angle)

        for marker_type, prefix in type_prefixes.items():
            for corner_suffix, edge_suffix, angle in (
                    ("CENTER_WIDE_UPPER_LEFT", "CENTER_LEFT_SIDE", 180),
                    ("CENTER_WIDE_DOWNER_LEFT", "CENTER_LEFT_SIDE", 180),
                    ("CENTER_WIDE_UPPER_RIGHT", "CENTER_RIGHT_SIDE", 0),
                    ("CENTER_WIDE_DOWNER_RIGHT", "CENTER_RIGHT_SIDE", 0)):
                command = MarkerCommand({prefix + "_" + corner_suffix,
                                         prefix + "_" + edge_suffix})
                self.assertFalse(
                    markerdir(command, marker_type, nofiled=True))
                self.assertEqual(command.pressed[-1].angle_for_show, angle)

        for suffix, angle in (("LEFT_WIDE", 180), ("RIGHT_WIDE", 0)):
            prefix = type_prefixes["EVENT"]
            command = MarkerCommand({prefix + "_" + suffix,
                                     prefix + "_CENTER_WIDE"})
            self.assertFalse(markerdir(command, "EVENT", nofiled=True))
            self.assertEqual(command.pressed[-1].angle_for_show, angle)
            self.assertEqual(command.pressed[-1].mag, 0.2)
            self.assertEqual(command.press_durations[-1], 0.0)

            command = MarkerCommand({prefix + "_" + suffix})
            self.assertFalse(markerdir(command, "EVENT", nofiled=True))
            self.assertEqual(command.pressed[-1].angle_for_show, angle)
            self.assertEqual(command.pressed[-1].mag, 1.0)
            self.assertAlmostEqual(command.press_durations[-1], 0.03)

    def test_za_mega_battle_lockon_rclick_defaults_on_and_forces_dir1(self):
        source_path = os.path.join(
            SERIAL_CONTROLLER, "Commands", "PythonCommands", "ZA",
            "ZA_story", "ZA_story.py")
        fragment_path = os.path.join(
            SERIAL_CONTROLLER, "DevTemplates", "Fragments", "Pokemon_ZA",
            "ZA_MovementAndEvent", "ZA_MovementAndEvent.pyfrag")
        with open(source_path, "r", encoding="utf-8-sig") as stream:
            source_tree = ast.parse(stream.read())
        with open(fragment_path, "r", encoding="utf-8") as stream:
            fragment_tree = ast.parse(stream.read())

        function_names = ("ZA_MOVE_LStick", "ZA_mega_evolution_battle")
        source_functions = {
            node.name: node for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name in function_names
        }
        fragment_functions = {
            node.name: node for node in ast.walk(fragment_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name in function_names
        }
        for name in function_names:
            self.assertEqual(
                ast.dump(source_functions[name], include_attributes=False),
                ast.dump(fragment_functions[name], include_attributes=False),
                name)

        battle_node = fragment_functions["ZA_mega_evolution_battle"]
        self.assertEqual(battle_node.args.args[-1].arg, "lockon_rclick")
        self.assertEqual(ast.literal_eval(battle_node.args.defaults[-1]), 1)
        battle_namespace = {"time": time, "Button": Button}
        exec(compile(ast.Module(body=[battle_node], type_ignores=[]),
                     fragment_path, "exec"), battle_namespace)
        battle = battle_namespace["ZA_mega_evolution_battle"]

        class BattleCommand:
            def __init__(self):
                self.ZL_state = 1
                self.end_checks = 0
                self.pressed = []
                self.moves = []

            def image_check(self, name):
                if name == "END":
                    self.end_checks += 1
                    return self.end_checks >= 2
                return name == "POKEMON_ZA_C+"

            def press(self, button, *args):
                self.pressed.append((button, args))

            def ZA_MOVE_LStick(self, *args):
                self.moves.append(args)

            def ZA_MOVE_SEE(self, *args, **kwargs):
                pass

            def ZA_ZL_ACTION(self, *args, **kwargs):
                pass

            def wait(self, _duration):
                pass

        enabled = BattleCommand()
        self.assertTrue(battle(enabled, endpicture="END"))
        self.assertEqual(
            [button for button, _args in enabled.pressed],
            [Button.RCLICK])
        self.assertIn((0, 0, 0, 0, 1, "RELOAD"), enabled.moves)

        disabled = BattleCommand()
        self.assertTrue(battle(
            disabled, endpicture="END", lockon_rclick=0))
        self.assertNotIn(
            Button.RCLICK,
            [button for button, _args in disabled.pressed])

        move_node = fragment_functions["ZA_MOVE_LStick"]
        move_namespace = {"time": time, "Direction": Direction,
                          "Stick": Stick}
        exec(compile(ast.Module(body=[move_node], type_ignores=[]),
                     fragment_path, "exec"), move_namespace)
        move = move_namespace["ZA_MOVE_LStick"]

        class MoveCommand:
            def __init__(self, until):
                self._za_mega_rclick_dir1_until = until
                self.Lstick_state = 0
                self.Lstick_state2 = 0
                self.Lstick_state3 = 0
                self.Lstick_state4 = 0
                self.Lstick_state_m1 = 0
                self.Lstick_state_m2 = 0
                self.held = []

            def hold(self, direction):
                self.held.append(direction)

            def holdEnd(self, _direction):
                pass

            def wait(self, _duration):
                pass

        approaching = MoveCommand(time.monotonic() + 1.0)
        move(approaching, 20, 340, 40, 300, 4, "RELOAD")
        self.assertEqual(approaching.held[-1].angle_for_show, 20)

        normal = MoveCommand(0.0)
        move(normal, 20, 340, 40, 300, 4, "RELOAD")
        self.assertEqual(normal.held[-1].angle_for_show, 300)

    def test_za_field_reach_checks_use_no_battle_hard_guard(self):
        source_path = os.path.join(
            SERIAL_CONTROLLER, "Commands", "PythonCommands", "ZA",
            "ZA_story", "ZA_story.py")
        with open(source_path, "r", encoding="utf-8-sig") as stream:
            source = stream.read()

        tree = ast.parse(source)
        protected = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "ZA_story_Template_Field_HardGaurd")
        source_lines = source.splitlines(keepends=True)
        audited_source = "".join(
            source_lines[:protected.lineno - 1]
            + source_lines[protected.end_lineno:])
        position_targets = {
            "POKEMON_ZA_FIELD_BACK_W",
            *("POKEMON_ZA_FIELD{}".format(index) for index in range(1, 7)),
            *("POKEMON_ZA_FIELD_BACK{}".format(index)
              for index in range(1, 7)),
        }
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "image_check"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value in position_targets):
                continue
            if protected.lineno <= node.lineno <= protected.end_lineno:
                continue
            self.assertIn(
                "POKEMON_ZA_NO_BATTLE_FIELD_HARD_CHECK",
                source_lines[node.lineno - 1])
        old_pair = (
            'self.image_check("POKEMON_ZA_FIELD_W") or '
            'self.image_check("POKEMON_ZA_FIELD_BACK_W")')
        self.assertNotIn(old_pair, audited_source)
        self.assertNotIn(
            'endpicture="POKEMON_ZA_FIELD_W"', audited_source)
        self.assertNotIn(
            'endpicture2="POKEMON_ZA_FIELD_BACK_W"', audited_source)

        changed_lines = [
            line for line in source.splitlines()
            if "#FIELDから変更" in line]
        self.assertEqual(len(changed_lines), 508)
        self.assertTrue(all(
            "POKEMON_ZA_NO_BATTLE_FIELD_HARD_CHECK" in line
            for line in changed_lines))

        fragment_paths = (
            os.path.join("SourceImports", "ZA_markerdir", "ZA_markerdir.pyfrag"),
            os.path.join("Pokemon_ZA", "ZA_BattleAndRoyale",
                         "ZA_BattleAndRoyale.pyfrag"),
            os.path.join("Pokemon_ZA", "ZA_CommonNavigation",
                         "ZA_CommonNavigation.pyfrag"),
            os.path.join("Pokemon_ZA", "ZA_CommonPokemonManagement",
                         "ZA_CommonPokemonManagement.pyfrag"),
            os.path.join("Pokemon_ZA", "ZA_MovementAndEvent",
                         "ZA_MovementAndEvent.pyfrag"),
        )
        fragment_root = os.path.join(
            SERIAL_CONTROLLER, "DevTemplates", "Fragments")
        fragment_changes = 0
        for relative_path in fragment_paths:
            with open(os.path.join(fragment_root, relative_path),
                      "r", encoding="utf-8") as stream:
                fragment = stream.read()
            fragment_tree = ast.parse(fragment)
            fragment_lines = fragment.splitlines(keepends=True)
            fragment_protected = next((
                node for node in ast.walk(fragment_tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == "ZA_story_Template_Field_HardGaurd"), None)
            for node in ast.walk(fragment_tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "image_check"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value in position_targets):
                    continue
                if (fragment_protected is not None
                        and fragment_protected.lineno <= node.lineno
                        <= fragment_protected.end_lineno):
                    continue
                self.assertIn(
                    "POKEMON_ZA_NO_BATTLE_FIELD_HARD_CHECK",
                    fragment_lines[node.lineno - 1], relative_path)
            if fragment_protected is not None:
                fragment = "".join(
                    fragment_lines[:fragment_protected.lineno - 1]
                    + fragment_lines[fragment_protected.end_lineno:])
            self.assertNotIn(old_pair, fragment, relative_path)
            self.assertNotIn(
                'endpicture="POKEMON_ZA_FIELD_W"', fragment, relative_path)
            self.assertNotIn(
                'endpicture2="POKEMON_ZA_FIELD_BACK_W"',
                fragment, relative_path)
            fragment_changes += fragment.count("#FIELDから変更")
        self.assertEqual(fragment_changes, 67)


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

    def test_dark_still_failure_keeps_five_steps_before_the_problem_step(self):
        timeline = CommandStateTimeline(loop_cycles=3)
        for now, value in enumerate(("A", "B", "C", "D", "E", "F")):
            timeline.add({"STATE": value}, now)
        retention = timeline.retention(
            60, keep_unique_steps=5, long_step_seconds=180,
            loop_cycles=3, terminal_time=60.0,
            terminal_started_at=5.0)
        self.assertEqual(retention["mode"], "dark_still")
        self.assertEqual(retention["keep_after"], 0.0)
        self.assertEqual(retention["keep_before"], 60.0)

    def test_problem_window_keeps_fifteen_distinct_prior_steps(self):
        timeline = CommandStateTimeline(loop_cycles=3)
        values = (["OLD"] + ["P{}".format(index) for index in range(1, 14)]
                  + ["A", "B", "A", "B", "STUCK"])
        for now, value in enumerate(values):
            timeline.add({"STATE": value}, now)
        retention = timeline.retention(
            100.0, keep_unique_steps=15, long_step_seconds=180,
            terminal_time=78.0, terminal_mode="manual_stop",
            terminal_started_at=18.0)
        # A/B/A/B contributes two distinct prior Steps, so OLD is the only
        # sixteenth prior Step excluded from the saved window.
        self.assertEqual(retention["keep_after"], 1.0)
        self.assertEqual(retention["keep_before"], 78.0)
        self.assertEqual(retention["mode"], "manual_stop")

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

    def test_stop_save_choice_protects_only_the_current_run(self):
        chunks = [
            {"id": "current", "command_session_id": "run-2",
             "pinned": False, "delete_pending": False},
            {"id": "protected", "command_session_id": "run-2",
             "pinned": True, "delete_pending": False},
            {"id": "previous", "command_session_id": "run-1",
             "pinned": False, "delete_pending": False},
        ]
        selected = apply_stopped_session_recording_choice(
            chunks, "run-2", save=True)
        self.assertEqual(selected, {"current"})
        self.assertTrue(chunks[0]["pinned"])
        self.assertFalse(chunks[0]["delete_pending"])
        self.assertFalse(chunks[2]["pinned"])

    def test_stop_do_not_save_choice_deletes_only_the_current_run(self):
        chunks = [
            {"id": "current", "command_session_id": "run-2",
             "pinned": False, "delete_pending": False},
            {"id": "protected", "command_session_id": "run-2",
             "pinned": True, "delete_pending": False},
            {"id": "previous", "command_session_id": "run-1",
             "pinned": False, "delete_pending": False},
        ]
        selected = apply_stopped_session_recording_choice(
            chunks, "run-2", save=False)
        self.assertEqual(selected, {"current"})
        self.assertFalse(chunks[0]["pinned"])
        self.assertTrue(chunks[0]["delete_pending"])
        self.assertFalse(chunks[2]["delete_pending"])


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
    def test_confirmation_audio_belongs_to_one_runtime_main(self):
        self.assertEqual(confirmation_audio_action(
            requested=True, runtime_owner=True), "start")
        self.assertEqual(confirmation_audio_action(
            requested=True, runtime_owner=False), "wait")
        self.assertEqual(confirmation_audio_action(
            requested=True, runtime_owner=True,
            other_output_active=True), "wait")
        self.assertEqual(confirmation_audio_action(
            requested=True, runtime_owner=False,
            stream_active=True), "stop")
        self.assertEqual(confirmation_audio_action(
            requested=True, runtime_owner=True, other_output_active=True,
            stream_active=True), "stop")
        self.assertEqual(confirmation_audio_action(
            requested=True, runtime_owner=False, stream_active=True,
            recording_uses_output=True), "keep")

    def test_preview_frame_preparation_is_tk_free_and_converts_bgr(self):
        frame = numpy.zeros((2, 3, 3), dtype=numpy.uint8)
        frame[0, 0] = (11, 22, 33)
        image = prepare_preview_image(frame, (3, 2))
        self.assertEqual(image.size, (3, 2))
        self.assertEqual(image.getpixel((0, 0)), (33, 22, 11))
        self.assertEqual(prepare_preview_image(frame, (6, 4)).size, (6, 4))

    def test_disabled_preview_always_covers_the_selected_show_size(self):
        placeholder = Image.new("RGB", (640, 360), "black")
        resized = prepare_disabled_preview_image(placeholder, (1280, 720))
        self.assertEqual(resized.size, (1280, 720))
        self.assertEqual(
            prepare_disabled_preview_image(None, (320, 180)).size,
            (320, 180))

    def test_leaving_native_preview_erases_direct_gdi_pixels(self):
        cleared = []
        configured = []
        wake_calls = []
        native = types.SimpleNamespace(
            clear=lambda size: cleared.append(tuple(size)))
        preview = types.SimpleNamespace(
            _native_preview_active=True, _native_preview=native,
            _native_render_mode_lock=threading.Lock(),
            _native_render_enabled=True,
            _native_render_wake=threading.Event(),
            camera=types.SimpleNamespace(
                wakeFrameWait=lambda: wake_calls.append(True)),
            show_size=(640, 360), im_=7,
            itemconfig=lambda item, **kwargs: configured.append(
                (item, kwargs)))
        preview._disable_threaded_native_preview = types.MethodType(
            CaptureArea._disable_threaded_native_preview, preview)
        CaptureArea._leave_native_preview(preview)
        self.assertEqual(cleared, [(640, 360)])
        self.assertEqual(wake_calls, [True])
        self.assertFalse(preview._native_preview_active)
        self.assertEqual(configured, [(7, {"state": "normal"})])

    def test_compatibility_preview_rejects_a_frame_left_from_previous_mode(self):
        configured = []
        preview = types.SimpleNamespace(
            show_size=(640, 360), camera=types.SimpleNamespace(
                frameSequence=lambda: 240),
            _requested_fps=60, _last_rendered_frame_sequence=239,
            _live_preview_tk=None, _live_preview_size=None, im_=7,
            itemconfig=lambda *args, **kwargs: configured.append(
                (args, kwargs)))
        prepared = (
            120, (640, 360), Image.new("RGB", (640, 360)),
            numpy.zeros((360, 640, 3), dtype=numpy.uint8),
            time.monotonic() - 1.0)
        self.assertFalse(
            CaptureArea._install_prepared_preview(preview, prepared))
        self.assertEqual(configured, [])

    def test_leaving_native_preview_seeds_current_tk_frame_before_clear(self):
        events = []

        class ExistingPhoto:
            def paste(self, image):
                events.append(("paste", image.getpixel((0, 0))))

        frame = numpy.zeros((2, 3, 3), dtype=numpy.uint8)
        frame[0, 0] = (11, 22, 33)
        preview = types.SimpleNamespace(
            _native_preview_active=True,
            _discard_prepared_preview=lambda: events.append(("discard",)),
            _disable_threaded_native_preview=lambda clear=False:
                events.append(("clear", clear)),
            _live_preview_tk=ExistingPhoto(), _live_preview_size=(3, 2),
            show_size=(3, 2), im_=7, im=None,
            itemconfig=lambda item, **kwargs:
                events.append(("itemconfig", item, kwargs)),
            _displaying_live_preview=False,
            _last_rendered_frame_sequence=-1,
            _last_submitted_frame_sequence=-1,
            _last_preview_render_time=0.0,
            _note_preview_frame=lambda now: events.append(("note", now)),
            presentation_listener=lambda image, sequence, now:
                events.append(("present", sequence)))
        self.assertTrue(CaptureArea._leave_native_preview(
            preview, frame, frame_sequence=42))
        self.assertLess(
            next(i for i, event in enumerate(events) if event[0] == "paste"),
            next(i for i, event in enumerate(events) if event[0] == "clear"))
        self.assertIn(("paste", (33, 22, 11)), events)
        self.assertEqual(preview._last_rendered_frame_sequence, 42)

    def test_image_command_first_check_requires_a_post_start_frame(self):
        old_frame = object()
        new_frame = object()

        class CameraStub:
            sequence = 10

            def frameSequence(self):
                return self.sequence

            def waitForFrame(self, last_sequence, timeout):
                if self.sequence == last_sequence:
                    return self.sequence, old_frame
                return self.sequence, new_frame

            def readFreshFrame(self, timeout):
                return new_frame

        command = ImageProcPythonCommand.__new__(ImageProcPythonCommand)
        command.camera = CameraStub()
        command._camera_frame_unavailable_logged = False
        command._logger = mock.Mock()
        command._command_start_frame_sequence = None
        command._require_new_frame_after_start = False
        with mock.patch.object(PythonCommand, "start", return_value="started"):
            self.assertEqual(command.start(None, None), "started")
        self.assertIsNone(command._read_camera_frame())
        command.camera.sequence = 11
        self.assertIs(command._read_camera_frame(), new_frame)
        self.assertFalse(command._require_new_frame_after_start)

    def test_feature_limited_native_worker_draws_new_frame_without_tk(self):
        draws = []
        notes = []
        presented = []
        stop = threading.Event()
        frame = numpy.zeros((2, 4, 3), dtype=numpy.uint8)

        def draw(image, size):
            draws.append((image, tuple(size)))
            stop.set()
            return True

        preview = types.SimpleNamespace(
            _native_render_stop=stop,
            _native_render_enabled=True,
            _native_render_wake=threading.Event(),
            _native_render_mode_lock=threading.Lock(),
            _native_preview=types.SimpleNamespace(draw=draw),
            camera=types.SimpleNamespace(
                waitForFrame=lambda _sequence, timeout: (4, frame)),
            show_size=(640, 360),
            _last_rendered_frame_sequence=-1,
            _last_preview_render_time=0.0,
            _note_preview_frame=notes.append,
            presentation_listener=lambda image, sequence, timestamp:
                presented.append((image, sequence, timestamp)),
            _logger=types.SimpleNamespace(warning=lambda *args: None))
        CaptureArea._native_render_loop(preview)
        self.assertEqual(draws, [(frame, (640, 360))])
        self.assertEqual(preview._last_rendered_frame_sequence, 4)
        self.assertEqual(len(notes), 1)
        self.assertEqual(len(presented), 1)
        self.assertIs(presented[0][0], frame)
        self.assertEqual(presented[0][1], 4)
        self.assertGreater(presented[0][2], 0.0)

    def test_dev_studio_scroll_helper_adds_both_bars_and_local_wheel(self):
        scrollbars = []

        class FakeScrollbar:
            def __init__(self, parent, orient, command):
                self.parent = parent
                self.orient = orient
                self.command = command
                self.packed = None
                scrollbars.append(self)

            def pack(self, **kwargs):
                self.packed = kwargs

            def set(self, *_args):
                pass

        class FakeWidget:
            def __init__(self):
                self.master = object()
                self.configured = {}
                self.packed = None
                self.bindings = []
                self.y_calls = []
                self.x_calls = []

            def yview(self, *_args):
                pass

            def xview(self, *_args):
                pass

            def yview_scroll(self, *args):
                self.y_calls.append(args)

            def xview_scroll(self, *args):
                self.x_calls.append(args)

            def configure(self, **kwargs):
                self.configured.update(kwargs)

            def pack(self, **kwargs):
                self.packed = kwargs

            def bind(self, event, callback, add=None):
                self.bindings.append((event, callback, add))

        widget = FakeWidget()
        with mock.patch("PokeConDevStudio.ttk.Scrollbar", FakeScrollbar):
            vertical, horizontal = pack_scrollable_widget(
                widget, horizontal=True)
        self.assertEqual(
            [item.orient for item in scrollbars], ["vertical", "horizontal"])
        self.assertIs(vertical, scrollbars[0])
        self.assertIs(horizontal, scrollbars[1])
        self.assertIn("yscrollcommand", widget.configured)
        self.assertIn("xscrollcommand", widget.configured)
        self.assertEqual(widget.bindings[0][0], "<MouseWheel>")
        self.assertEqual(widget.bindings[0][2], "+")
        wheel = widget.bindings[0][1]
        self.assertEqual(
            wheel(types.SimpleNamespace(delta=120, state=0)), "break")
        self.assertEqual(widget.y_calls, [(-1, "units")])
        self.assertEqual(
            wheel(types.SimpleNamespace(delta=-120, state=1)), "break")
        self.assertEqual(widget.x_calls, [(1, "units")])

    def test_native_worker_consumes_camera_clear_without_spinning(self):
        waits = []
        stop = threading.Event()

        def wait_for_frame(last_sequence, timeout):
            waits.append(last_sequence)
            if len(waits) > 1:
                stop.set()
            return 5, None

        preview = types.SimpleNamespace(
            _native_render_stop=stop,
            _native_render_enabled=True,
            _native_render_wake=threading.Event(),
            _native_render_mode_lock=threading.Lock(),
            _native_preview=types.SimpleNamespace(
                draw=lambda _image, _size: self.fail("None frame was drawn")),
            camera=types.SimpleNamespace(waitForFrame=wait_for_frame),
            show_size=(640, 360),
            _last_rendered_frame_sequence=-1,
            _last_preview_render_time=0.0,
            _note_preview_frame=lambda _now: None,
            _logger=types.SimpleNamespace(warning=lambda *args: None))
        CaptureArea._native_render_loop(preview)
        self.assertEqual(waits, [-1, 5])

    def test_tab_interaction_temporarily_yields_preview_rendering(self):
        preview = types.SimpleNamespace(_ui_interaction_busy_until=0.0)
        with mock.patch("GuiAssets.time.monotonic", return_value=10.0):
            CaptureArea.prioritizeUiInteraction(preview, seconds=0.45)
        self.assertEqual(preview._ui_interaction_busy_until, 10.45)

    def test_feature_limited_preview_removes_overlays_and_range_bindings(self):
        unbound = []
        deleted = []
        preview = types.SimpleNamespace(
            _feature_limited=False, im_=1,
            unbind=unbound.append, find_all=lambda: (1, 2, 3),
            delete=deleted.append,
            _bind_range_selection=lambda: None)
        CaptureArea.setFeatureLimited(preview, True)
        self.assertTrue(preview._feature_limited)
        self.assertIn("<Shift-ButtonPress-1>", unbound)
        self.assertEqual(deleted, [2, 3])

    def test_windows_foreground_pid_owns_keyboard_and_preview_focus(self):
        self.assertEqual(foreground_process_id(lambda: 123), 123)
        self.assertTrue(foreground_process_matches(
            pid=123, foreground_pid_provider=lambda: 123))
        self.assertFalse(foreground_process_matches(
            pid=123, foreground_pid_provider=lambda: 456))

    def test_multi_pokecon_ownership_monitor_never_raises_a_window(self):
        window_path = os.path.join(SERIAL_CONTROLLER, "Window.py")
        with open(window_path, "r", encoding="utf-8-sig") as stream:
            tree = ast.parse(stream.read())
        monitored_methods = {
            "_publish_window_focus",
            "_window_activity_monitor_loop",
            "_sync_manual_input_owner",
            "_sync_pc_gamepad_input_for_owner",
            "_drain_confirmation_audio_reconcile",
            "_revoke_duplicate_main_request",
            "_refresh_preview_priority_status",
        }
        forbidden_calls = {
            "lift", "focus_force", "focus_set", "deiconify",
            "SetForegroundWindow", "BringWindowToTop", "SetWindowPos",
        }
        found = {
            node.name: node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name in monitored_methods
        }
        self.assertEqual(set(found), monitored_methods)
        for method_name, method in found.items():
            for call in (node for node in ast.walk(method)
                         if isinstance(node, ast.Call)):
                function = call.func
                name = function.attr if isinstance(function, ast.Attribute) \
                    else function.id if isinstance(function, ast.Name) else ""
                self.assertNotIn(name, forbidden_calls, method_name)
                if name in {"attributes", "wm_attributes"} and call.args:
                    self.assertNotEqual(
                        getattr(call.args[0], "value", None),
                        "-topmost", method_name)

    def test_background_dialog_does_not_attach_to_pokecon_owner(self):
        self.assertTrue(dialog_owner_attachment_allowed(
            pid=123, foreground_pid_provider=lambda: 123))
        self.assertFalse(dialog_owner_attachment_allowed(
            pid=123, foreground_pid_provider=lambda: 456))

        dialogue_path = os.path.join(
            SERIAL_CONTROLLER, "PokeConDialogue.py")
        with open(dialogue_path, "r", encoding="utf-8-sig") as stream:
            dialogue_source = stream.read()
        self.assertIn(
            "attach_to_owner = dialog_owner_attachment_allowed()",
            dialogue_source)
        self.assertIn("owner is not None and attach_to_owner", dialogue_source)
        self.assertNotIn('attributes("-topmost"', dialogue_source)

        window_path = os.path.join(SERIAL_CONTROLLER, "Window.py")
        with open(window_path, "r", encoding="utf-8-sig") as stream:
            window_source = stream.read()
        window_tree = ast.parse(window_source)
        methods = {
            node.name: ast.get_source_segment(window_source, node)
            for node in ast.walk(window_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "_confirm_shared_device", "_choose_combined_set_dialog"}
        }
        self.assertEqual(
            set(methods),
            {"_confirm_shared_device", "_choose_combined_set_dialog"})
        for method_name, source in methods.items():
            self.assertIn(
                "attach_to_owner = dialog_owner_attachment_allowed()",
                source, method_name)
        self.assertNotIn(
            "focus_force", methods["_choose_combined_set_dialog"])

    def test_camera_reader_does_not_spin_faster_than_requested_fps(self):
        class ImmediateCapture:
            def __init__(self):
                self.read_count = 0
                self.opened = True

            def read(self):
                self.read_count += 1
                return True, object()

            def isOpened(self):
                return self.opened

            def release(self):
                self.opened = False

        camera = Camera(60)
        capture = ImmediateCapture()
        camera.camera = capture
        camera._start_camera_reader()
        time.sleep(0.12)
        camera.destroy()
        self.assertGreaterEqual(capture.read_count, 4)
        self.assertLessEqual(capture.read_count, 12)

    def test_blocking_60fps_camera_does_not_get_an_extra_short_wait(self):
        interval = 1.0 / 60.0
        self.assertEqual(camera_reader_backoff(interval, 0.015), 0.0)
        self.assertAlmostEqual(
            camera_reader_backoff(interval, 0.001), interval - 0.001)

    def test_camera_reports_measured_input_fps_and_detects_a_stall(self):
        camera = Camera(60)
        for timestamp in (10.0, 10.25, 10.50, 10.75):
            camera._note_frame_received(timestamp)
        self.assertAlmostEqual(camera.measuredFps(10.80), 4.0)
        self.assertEqual(camera.measuredFps(12.30), 0.0)

    def test_camera_does_not_publish_the_last_frame_after_input_stalls(self):
        camera = Camera(60)
        frame = object()
        camera.image_bgr = frame
        camera._last_frame_received_at = time.monotonic()
        self.assertIs(camera.readFrame(), frame)
        camera._last_frame_received_at = time.monotonic() - 1.0
        self.assertIsNone(camera.readFrame())
        self.assertIs(camera.readFrame(allow_stale=True), frame)

    def test_camera_fresh_read_waits_for_a_transient_gap_but_rejects_stall(self):
        camera = Camera(60)
        frame = object()

        def publish():
            time.sleep(0.03)
            camera.image_bgr = frame
            camera._frame_sequence += 1
            camera._note_frame_received()

        publisher = threading.Thread(target=publish)
        publisher.start()
        self.assertIs(camera.readFreshFrame(timeout=0.25), frame)
        publisher.join()
        camera._last_frame_received_at = time.monotonic() - 1.0
        self.assertIsNone(camera.readFreshFrame(timeout=0.02))

    def test_camera_frame_freshness_allows_driver_scheduling_headroom(self):
        self.assertEqual(camera_frame_freshness_timeout(60), 0.25)
        self.assertEqual(camera_frame_freshness_timeout(5), 0.8)
        self.assertEqual(camera_frame_freshness_timeout("invalid"), 0.25)

    def test_local_image_detection_does_not_fallback_to_stale_cache(self):
        stale_frame = object()
        camera = types.SimpleNamespace(
            image_bgr=stale_frame, readFrame=lambda: None)
        command = types.SimpleNamespace(camera=camera)
        with self.assertRaisesRegex(RuntimeError, "新しい映像"):
            _command_frame(command)

    def test_local_image_detection_uses_transient_gap_recovery(self):
        frame = object()
        camera = types.SimpleNamespace(
            readFreshFrame=lambda timeout: frame,
            readFrame=lambda: None)
        command = types.SimpleNamespace(camera=camera)
        self.assertIs(_command_frame(command), frame)

    def test_preview_reports_only_successful_draw_fps(self):
        preview = types.SimpleNamespace(
            _measured_preview_fps=0.0,
            _preview_fps_measure_started=0.0,
            _preview_fps_measure_frames=0,
            _last_preview_frame_at=0.0)
        for timestamp in (20.0, 20.25, 20.50, 20.75):
            CaptureArea._note_preview_frame(preview, timestamp)
        self.assertAlmostEqual(
            CaptureArea.measuredPreviewFps(preview, 20.80), 4.0)
        self.assertEqual(
            CaptureArea.measuredPreviewFps(preview, 22.30), 0.0)

    def test_resize_temporarily_yields_time_to_tk(self):
        capture, render = resize_safe_preview_intervals(
            1.0 / 60.0, 1.0 / 60.0, resizing=True)
        self.assertEqual(capture, 1.0 / 30.0)
        self.assertEqual(render, 1.0 / 15.0)
        recording_capture, _ = resize_safe_preview_intervals(
            1.0 / 60.0, 1.0 / 60.0,
            resizing=True, background_work=True)
        self.assertEqual(recording_capture, 1.0 / 60.0)

    def test_keyboard_listener_runs_only_for_active_input_owner(self):
        self.assertTrue(keyboard_listener_should_run(True, True))
        self.assertFalse(keyboard_listener_should_run(True, False))
        self.assertFalse(keyboard_listener_should_run(False, True))

    def test_keyboard_listener_releases_held_input_before_owner_switch(self):
        controller = SwitchKeyboardController.__new__(SwitchKeyboardController)
        controller.holding = ["a", "h"]
        controller.holdingDir = ["up"]
        controller.holdingHatDir = []
        controller.key_map = {
            "a": Button.A, "h": Hat.TOP, "up": Direction.UP}
        controller.key = mock.Mock()
        controller.listener = mock.Mock()
        controller._logger = mock.Mock()

        controller.stop()

        forwarded = controller.key.inputEnd.call_args.args[0]
        self.assertEqual(forwarded, [Button.A, Hat.TOP, Direction.UP])
        self.assertTrue(controller.key.inputEnd.call_args.kwargs["unset_hat"])
        self.assertEqual(controller.holding, [])
        self.assertEqual(controller.holdingDir, [])
        controller.listener.stop.assert_called_once_with()

    def test_requested_fps_is_applied_to_an_open_capture_device(self):
        calls = []

        class FakeCapture:
            def isOpened(self):
                return True

            def set(self, prop, value):
                calls.append((prop, value))
                return True

            def get(self, prop):
                return 60.0

        camera = Camera(30)
        camera.camera = FakeCapture()
        self.assertTrue(camera.setFps(60))
        self.assertEqual(camera.fps, 60)
        self.assertEqual(
            [prop for prop, _value in calls],
            [cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT,
             cv2.CAP_PROP_FPS, cv2.CAP_PROP_FOURCC])
        self.assertEqual(
            calls[-1][1], cv2.VideoWriter_fourcc(*"MJPG"))
        self.assertEqual(calls[-2][1], 60)

    def test_camera_fourcc_diagnostic_decodes_mjpg(self):
        self.assertEqual(camera_fourcc_name(
            cv2.VideoWriter_fourcc(*"MJPG")), "MJPG")
        self.assertEqual(camera_fourcc_name(-1), "")

    def test_camera_native_lifecycle_is_serialized(self):
        camera = Camera(60)
        active = 0
        peak = 0
        lock = threading.Lock()

        def fake_open(_camera_id):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with lock:
                active -= 1

        camera._open_camera_locked = fake_open
        first = threading.Thread(target=camera.openCamera, args=(0,))
        second = threading.Thread(target=camera.openCamera, args=(1,))
        first.start()
        second.start()
        first.join()
        second.join()
        self.assertEqual(peak, 1)

    def test_camera_open_returns_atomic_native_result(self):
        camera = Camera(60)
        camera._open_camera_locked = lambda camera_id: camera_id == 4
        self.assertTrue(camera.openCamera(4))
        self.assertFalse(camera.openCamera(3))

    def test_main_tool_keeps_full_rate_while_another_app_has_focus(self):
        self.assertEqual(
            preview_priority(False, True, False), (True, True))
        self.assertEqual(
            preview_priority(False, False, True), (False, False))
        self.assertEqual(
            preview_priority(True, False, True), (True, True))
        self.assertEqual(
            preview_priority(False, False, False, keep_warm=True),
            (True, False))
        self.assertAlmostEqual(
            preview_render_interval(
                60, focused=False, viewable=True, full_rate=True),
            1.0 / 60.0)
        self.assertAlmostEqual(
            preview_capture_interval(
                60, focused=False, viewable=True, full_rate=True),
            1.0 / 60.0)
        self.assertAlmostEqual(
            preview_render_interval(
                60, focused=False, viewable=False, full_rate=True),
            1.0 / 60.0)
        self.assertAlmostEqual(
            preview_render_interval(
                60, focused=False, viewable=True, full_rate=False),
            0.2)

    def test_main_preview_permission_follows_pokecon_owner_and_wait_state(self):
        # The checked owner is unique, so neither a browser nor another
        # PokeCon in front revokes its rate. A finalization wait still does.
        self.assertEqual(
            preview_rate_permissions(True, False, False, False), (True, False))
        self.assertEqual(
            preview_rate_permissions(True, True, False, False), (True, False))
        self.assertEqual(
            preview_rate_permissions(True, False, True, True), (False, False))

    def test_preview_timer_subtracts_frame_conversion_work(self):
        self.assertEqual(compensated_after_delay(
            1.0 / 60.0, started_at=10.0, now=10.006), 11)
        self.assertEqual(compensated_after_delay(
            1.0 / 60.0, started_at=10.0, now=10.020), 1)

    def test_recording_can_request_high_precision_capture_while_preview_is_capped(self):
        delays = []
        preview = types.SimpleNamespace(
            _capture_high_precision_requested=True,
            after=lambda delay, _callback: delays.append(delay),
            capture=lambda: None)
        with mock.patch(
                "GuiAssets.compensated_after_delay", return_value=14):
            CaptureArea._schedule_next_capture(
                preview, 1.0 / 60.0, time.monotonic(),
                high_precision=False)
        self.assertEqual(delays, [4])

    def test_audio_packet_gap_becomes_silence_without_shifting_later_audio(self):
        class FakeWave:
            def __init__(self):
                self.data = bytearray()

            def writeframesraw(self, payload):
                self.data.extend(payload)

        recorder = CaptureRecorder()
        recorder.audio = FakeWave()
        recorder.audio_channels = 1
        recorder.audio_sample_rate = 10
        recorder.audio_gain = 1.0
        recorder.audio_frames_written = 0
        first = struct.pack("<hh", 100, 200)
        second = struct.pack("<hh", 300, 400)
        recorder._write_audio_packet(0, 2, first)
        recorder._write_audio_packet(2, 2, second)
        self.assertEqual(
            struct.unpack("<hhhhhh", bytes(recorder.audio.data)),
            (100, 200, 0, 0, 300, 400))
        self.assertEqual(recorder.audio_frames_written, 6)

    def test_peak_normalizer_brings_measured_usb_level_to_target(self):
        normalizer = AdaptivePeakNormalizer(
            48000, enabled=True, target_dbfs=-6.0,
            max_gain_percent=200, ceiling_dbfs=-1.0)
        # The measured -23.8 dBFS input is first raised by the configured
        # manual 400% gain, then the automatic stage supplies the remainder.
        signal = numpy.full((480, 1), 0.064453 * 4.0, dtype=numpy.float32)
        output = normalizer.process(signal)
        self.assertAlmostEqual(float(numpy.max(numpy.abs(output))),
                               10 ** (-6.0 / 20.0), places=4)
        self.assertGreater(normalizer.last_info["adaptive_gain"], 1.9)

    def test_audio_auto_preset_keeps_loud_target_without_manual_pre_gain(self):
        settings = suggest_audio_level_settings(-23.8)
        self.assertEqual(settings["gain_percent"], 100)
        self.assertEqual(settings["target_dbfs"], -6.0)
        self.assertEqual(settings["max_auto_gain_percent"], 800)
        self.assertEqual(settings["limiter_ceiling_dbfs"], -1.0)
        self.assertIsNone(suggest_audio_level_settings(-80.0))
        self.assertIsNone(suggest_audio_level_settings("invalid"))

    def test_audio_auto_preset_adjusts_target_and_limiter_from_rms(self):
        settings = suggest_audio_level_settings(
            -23.8, raw_rms_dbfs=-39.4)
        self.assertEqual(settings["target_dbfs"], -4.0)
        self.assertEqual(settings["limiter_ceiling_dbfs"], -1.0)
        self.assertEqual(settings["max_auto_gain_percent"], 800)
        clipped = suggest_audio_level_settings(
            -0.01, raw_rms_dbfs=-12.0, raw_clip_blocks=3)
        self.assertEqual(clipped["target_dbfs"], -9.0)
        self.assertEqual(clipped["limiter_ceiling_dbfs"], -3.0)

    def test_audio_auto_preset_reserves_repeatable_loud_effect_headroom(self):
        settings = suggest_audio_level_settings(
            -24.5, raw_rms_dbfs=-35.5,
            raw_loud_peak_dbfs=-9.0)
        self.assertEqual(settings["target_dbfs"], -7.0)
        self.assertEqual(settings["max_auto_gain_percent"], 750)
        self.assertEqual(settings["limiter_ceiling_dbfs"], -4.0)
        self.assertEqual(settings["transient_reserve_db"], 2.0)

    def test_invalid_saved_audio_levels_are_repaired_before_use(self):
        repaired = sanitize_audio_level_settings(100, 40, 800, -20)
        self.assertEqual(repaired["gain_percent"], 100)
        self.assertEqual(repaired["target_dbfs"], -6.0)
        self.assertEqual(repaired["max_auto_gain_percent"], 800)
        self.assertEqual(repaired["limiter_ceiling_dbfs"], -1.0)
        no_headroom = sanitize_audio_level_settings(100, -1, 800, -6)
        self.assertEqual(no_headroom["target_dbfs"], -9.0)

    def test_limiter_recovers_gradually_after_a_loud_effect(self):
        normalizer = AdaptivePeakNormalizer(
            48000, enabled=True, target_dbfs=-6.0,
            max_gain_percent=800, ceiling_dbfs=-1.0)
        normalizer.process(numpy.full(
            (480, 1), 0.01, dtype=numpy.float32))
        normalizer.process(numpy.ones(
            (480, 1), dtype=numpy.float32))
        limited_gain = normalizer.last_info["limiter_gain"]
        normalizer.process(numpy.full(
            (480, 1), 0.01, dtype=numpy.float32))
        recovered_gain = normalizer.last_info["limiter_gain"]
        self.assertLess(limited_gain, recovered_gain)
        self.assertLess(recovered_gain, 1.0)

    def test_peak_normalizer_limits_a_sudden_loud_effect(self):
        normalizer = AdaptivePeakNormalizer(
            48000, enabled=True, target_dbfs=-6.0,
            max_gain_percent=800, ceiling_dbfs=-1.0)
        normalizer.process(numpy.full(
            (480, 1), 0.01, dtype=numpy.float32))
        output = normalizer.process(numpy.ones(
            (480, 1), dtype=numpy.float32))
        self.assertLessEqual(float(numpy.max(numpy.abs(output))),
                             10 ** (-1.0 / 20.0) + 1.0e-6)
        self.assertTrue(normalizer.last_info["limited"])

    def test_peak_limiter_preserves_waveform_and_holds_maximums(self):
        normalizer = AdaptivePeakNormalizer(
            48000, enabled=True, target_dbfs=-6.0,
            max_gain_percent=800, ceiling_dbfs=-1.0)
        normalizer.process(numpy.full(
            (480, 1), 0.01, dtype=numpy.float32))
        signal = numpy.array([[1.0], [0.5], [-0.25]], dtype=numpy.float32)
        output = normalizer.process(signal)
        self.assertAlmostEqual(
            abs(float(output[0, 0] / output[1, 0])), 2.0, places=5)
        self.assertAlmostEqual(
            normalizer.last_info["input_peak_max_dbfs"], 0.0, places=5)
        self.assertEqual(normalizer.last_info["limited_blocks"], 1)
        normalizer.reset_statistics()
        self.assertEqual(
            normalizer.last_info["input_peak_max_dbfs"], -180.0)
        self.assertEqual(normalizer.last_info["limited_blocks"], 0)

    def test_audio_monitor_reports_raw_peak_hold_and_clip_count(self):
        monitor = AudioMonitor()
        monitor._last_raw_peak = 0.5
        monitor._raw_peak_max = 1.0
        monitor._raw_clip_blocks = 2
        monitor.software_buffer_underflow_frames = 3
        monitor.software_buffer_drift_drop_frames = 4
        info = monitor.level_info()
        self.assertAlmostEqual(info["raw_peak_dbfs"], -6.0206, places=3)
        self.assertAlmostEqual(info["raw_peak_max_dbfs"], 0.0, places=5)
        self.assertEqual(info["raw_clip_blocks"], 2)
        self.assertEqual(info["software_buffer_underflow_frames"], 3)
        self.assertEqual(info["software_buffer_drift_drop_frames"], 4)
        monitor.reset_level_statistics()
        reset = monitor.level_info()
        self.assertEqual(reset["raw_peak_max_dbfs"], -180.0)
        self.assertEqual(reset["raw_clip_blocks"], 0)

    def test_audio_calibration_uses_robust_active_signal_references(self):
        monitor = AudioMonitor()
        monitor._raw_active_block_peaks_dbfs.extend(
            [-20.0] * 100 + [0.0])
        monitor._raw_active_block_rms_dbfs.extend(
            [-35.0] * 101)
        info = monitor.level_info()
        self.assertAlmostEqual(
            info["raw_reference_peak_dbfs"], -20.0, places=3)
        self.assertAlmostEqual(
            info["raw_loud_peak_dbfs"], -20.0, places=3)
        self.assertAlmostEqual(
            info["raw_reference_rms_dbfs"], -35.0, places=3)
        first = suggest_audio_level_settings(-20.0, -35.0)
        repeated = suggest_audio_level_settings(-20.2, -35.1)
        self.assertEqual(first, repeated)

    def test_audio_callback_packets_stay_contiguous_without_clock_correction(self):
        recorder = CaptureRecorder()
        recorder.audio_queue = queue.Queue(maxsize=2)
        recorder.audio_pending_gap_frames = 0
        recorder.audio_callback_warning_count = 0
        recorder.audio_queue_drop_count = 0
        recorder.audio_queue_dropped_frames = 0
        recorder.audio_accepting_packets = True
        packet = numpy.array([[10], [20]], dtype=numpy.int16)
        self.assertTrue(recorder._queue_audio_packet(packet, 2))
        gap, frames, payload = recorder.audio_queue.get_nowait()
        self.assertEqual((gap, frames), (0, 2))
        self.assertEqual(payload, packet.tobytes())

    def test_audio_queue_drop_is_replaced_once_by_confirmed_silence(self):
        recorder = CaptureRecorder()
        recorder.audio_queue = queue.Queue(maxsize=1)
        recorder.audio_queue.put_nowait((0, 1, b"old"))
        recorder.audio_pending_gap_frames = 0
        recorder.audio_callback_warning_count = 0
        recorder.audio_queue_drop_count = 0
        recorder.audio_queue_dropped_frames = 0
        recorder.audio_accepting_packets = True
        packet = numpy.array([[10], [20]], dtype=numpy.int16)
        self.assertFalse(recorder._queue_audio_packet(packet, 2))
        self.assertEqual(recorder.audio_pending_gap_frames, 2)
        recorder.audio_queue.get_nowait()
        self.assertTrue(recorder._queue_audio_packet(packet, 2))
        self.assertEqual(recorder.audio_queue.get_nowait()[:2], (2, 2))

    def test_audio_writer_caps_queued_packets_at_the_logical_stop(self):
        recorder = CaptureRecorder()
        with tempfile.TemporaryDirectory() as folder:
            recorder.wav_path = os.path.join(folder, "capped.wav")
            recorder.audio = wave.open(recorder.wav_path, "wb")
            recorder.audio.setnchannels(1)
            recorder.audio.setsampwidth(2)
            recorder.audio.setframerate(10)
            recorder.audio_channels = 1
            recorder.audio_sample_rate = 10
            recorder.audio_frames_written = 0
            recorder.audio_stop_target_frames = 10
            payload = numpy.arange(20, dtype=numpy.int16).tobytes()

            recorder._write_audio_packet(0, 20, payload)
            recorder.audio.close()
            recorder.audio = None

            with wave.open(recorder.wav_path, "rb") as audio:
                self.assertEqual(audio.getnframes(), 10)

    def test_stop_freezes_audio_before_waiting_for_video_drain(self):
        class FakeMonitor:
            def __init__(self):
                self.removed = []

            @staticmethod
            def level_info():
                return {}

            def remove_recording_output_listener(self, token):
                self.removed.append(token)
                return True

        recorder = CaptureRecorder()
        monitor = FakeMonitor()

        class FakeWriterThread:
            def join(self, timeout=None):
                self.timeout = timeout
                self.audio_was_frozen = (
                    not recorder.audio_accepting_packets
                    and recorder.audio_monitor_listener_token is None)

            @staticmethod
            def is_alive():
                return False

        writer = FakeWriterThread()
        recorder.active = True
        recorder.started_at = time.monotonic() - 1.0
        recorder.requested_fps = 60.0
        recorder.frames_written = 0
        recorder.writer_thread = writer
        recorder.writer_stop = threading.Event()
        recorder.audio_accepting_packets = True
        recorder.audio_monitor = monitor
        recorder.audio_monitor_listener_token = 9
        recorder.audio_sample_rate = 0
        recorder.wav_path = os.path.join(tempfile.gettempdir(),
                                         "missing-recording.wav")
        recorder.video = mock.Mock()

        recorder.stop()

        self.assertTrue(writer.audio_was_frozen)
        self.assertEqual(monitor.removed, [9])

    def test_truncated_mme_name_prefers_equivalent_wasapi_input(self):
        devices = [
            {"name": "デジタル オーディオ インターフェイス (3- USB2 Di",
             "max_input_channels": 2, "hostapi": 0},
            {"name": "デジタル オーディオ インターフェイス (3- USB2 Digital Audio)",
             "max_input_channels": 2, "hostapi": 1},
            {"name": "デジタル オーディオ インターフェイス (3- USB2 Digital Audio)",
             "max_input_channels": 2, "hostapi": 2},
        ]
        host_apis = [
            {"name": "MME"}, {"name": "Windows WASAPI"},
            {"name": "Windows DirectSound"},
        ]
        fake_sd = types.SimpleNamespace(
            query_devices=lambda: devices,
            query_hostapis=lambda: host_apis)
        self.assertEqual(
            AudioMonitor._candidate_input_indices(fake_sd, 0), [1, 2, 0])

    def test_default_mme_speaker_prefers_equivalent_wasapi_output(self):
        devices = [
            {"name": "スピーカー (Realtek Audio)",
             "max_output_channels": 2, "hostapi": 0},
            {"name": "スピーカー (Realtek Audio)",
             "max_output_channels": 2, "hostapi": 1},
            {"name": "スピーカー (Realtek Audio)",
             "max_output_channels": 2, "hostapi": 2},
        ]
        host_apis = [
            {"name": "MME"}, {"name": "Windows WASAPI"},
            {"name": "Windows DirectSound"},
        ]
        fake_sd = types.SimpleNamespace(
            query_devices=lambda: devices,
            query_hostapis=lambda: host_apis)
        self.assertEqual(
            AudioMonitor._candidate_output_indices(fake_sd, 0), [1, 0, 2])

    def test_streaming_audio_rate_converter_keeps_callback_continuity(self):
        converter = StreamingAudioRateConverter(96000, 48000, 1)
        first = converter.process(numpy.ones((960, 1), dtype=numpy.float32))
        second = converter.process(numpy.ones((960, 1), dtype=numpy.float32))
        self.assertEqual((len(first), len(second)), (480, 480))
        self.assertGreater(float(numpy.min(second)), 0.99)

    def test_96khz_converter_rejects_inaudible_alias_source(self):
        def converted_rms(frequency):
            frames = 9600
            time_axis = numpy.arange(frames, dtype=numpy.float64) / 96000.0
            source = numpy.sin(
                2.0 * numpy.pi * frequency * time_axis).astype(
                    numpy.float32).reshape((-1, 1))
            converter = StreamingAudioRateConverter(96000, 48000, 1)
            output = []
            offset = 0
            for size in (997, 1021, 883, 1103, 959, 1201, 743, 1307):
                if offset >= len(source):
                    break
                output.append(converter.process(source[offset:offset + size]))
                offset += size
            if offset < len(source):
                output.append(converter.process(source[offset:]))
            combined = numpy.concatenate(output, axis=0)[200:]
            return float(numpy.sqrt(numpy.mean(combined * combined)))

        self.assertGreater(converted_rms(19000.0), 0.45)
        self.assertLess(converted_rms(25000.0), 0.02)

    def test_elastic_audio_clock_correction_has_continuous_endpoints(self):
        source = numpy.sin(numpy.linspace(
            0.0, 8.0 * numpy.pi, 1025,
            dtype=numpy.float32)).reshape((-1, 1))
        corrected = fit_audio_block(source, 1024)

        self.assertEqual(corrected.shape, (1024, 1))
        self.assertAlmostEqual(float(corrected[0, 0]), float(source[0, 0]))
        self.assertAlmostEqual(float(corrected[-1, 0]), float(source[-1, 0]))
        self.assertLess(float(numpy.max(numpy.abs(numpy.diff(
            corrected[:, 0])))), 0.03)

    def test_audio_startup_waits_for_one_complete_output_block(self):
        self.assertEqual(
            plan_audio_buffer_consume(480, 960, False, 1920), (0, 0))
        self.assertEqual(
            plan_audio_buffer_consume(960, 960, False, 1920), (0, 0))
        self.assertEqual(
            plan_audio_buffer_consume(1440, 480, False, 1920), (0, 0))
        self.assertEqual(
            plan_audio_buffer_consume(1920, 960, False, 1920), (960, 0))
        self.assertEqual(
            plan_audio_buffer_consume(959, 960, True, 1920), (959, -1))
        self.assertEqual(
            plan_audio_buffer_consume(1440, 480, True, 1920), (480, 0))
        self.assertEqual(
            plan_audio_buffer_consume(2400, 480, True, 1920), (480, 0))
        self.assertEqual(
            plan_audio_buffer_consume(1439, 480, True, 1920), (479, -1))
        self.assertEqual(
            plan_audio_buffer_consume(2401, 480, True, 1920), (481, 1))

    def test_audio_identity_ignores_portaudio_and_windows_numbers(self):
        self.assertEqual(
            normalized_audio_name(
                "8: デジタル オーディオ (3- USB2 Digital Audio)"),
            normalized_audio_name(
                "2: デジタル オーディオ (USB2 Digital Audio)"))
        self.assertEqual(
            physical_usb_key(
                r"@device:pnp:\\?\usb#vid_345f&pid_2131&mi_00#b&2838c96c&0&0000#global"),
            "b&2838c96c&0")
        self.assertEqual(
            usb_connection_token(
                r"@device:pnp:\\?\usb#vid_345f&pid_2131&mi_00#a&2838c96c&0&0000#global"),
            "2838c96c")

    def test_short_input_handoff_keeps_last_valid_preview(self):
        self.assertTrue(hold_last_preview_on_missing_frame(
            True, 10.0, 12.9, grace_seconds=3.0))
        self.assertFalse(hold_last_preview_on_missing_frame(
            True, 10.0, 13.0, grace_seconds=3.0))
        self.assertFalse(hold_last_preview_on_missing_frame(
            False, None, 10.0, grace_seconds=3.0))

    def test_legacy_input_set_audio_identity_is_enriched(self):
        endpoints = [{
            "endpoint_id": "{stable-guid}",
            "friendly_name": "Audio (4- USB2 Digital Audio)",
            "device_instance_id": "stable-instance",
            "device_interface_path": "stable-interface",
            "physical_usb_key": "9&225d3b8d&0",
            "active": False,
        }]
        data = {"input_sets": {"Switch2": {
            "camera": {"device_path": (
                r"@device:pnp:\\?\usb#vid_345f&pid_2131&mi_00#9&225d3b8d&0&0000#global")},
            "audio": {"enabled": True,
                      "device_name": "5: Audio (4- USB2 Digital Audio)"},
        }}}
        self.assertTrue(upgrade_input_set_audio_identities(
            data, endpoints=endpoints))
        self.assertEqual(data["input_sets"]["Switch2"]["audio"]["endpoint_id"],
                         "{stable-guid}")
        self.assertFalse(upgrade_input_set_audio_identities(
            data, endpoints=endpoints))

    def test_stable_audio_identity_is_not_overwritten_during_enrichment(self):
        saved = {"enabled": True, "device_name": "Audio (USB2)",
                 "endpoint_id": "{missing-guid}"}
        endpoints = [{"endpoint_id": "{other-guid}",
                      "friendly_name": "Audio (USB2)",
                      "physical_usb_key": "a&111&0", "active": True}]
        self.assertFalse(enrich_saved_audio_identity(saved, endpoints=endpoints))
        self.assertEqual(saved["endpoint_id"], "{missing-guid}")

    def test_audio_endpoint_guid_tracks_shifted_display_numbers(self):
        endpoints = [{
            "endpoint_id": "{stable-guid}",
            "friendly_name": "デジタル オーディオ (5- USB2 Digital Audio)",
            "device_instance_id": r"USB\VID_345F&PID_2131\B&2838C96C&0&0002",
            "device_interface_path": "stable-path",
            "physical_usb_key": "b&2838c96c&0",
            "active": True,
        }]
        label = resolve_saved_audio(
            {"device_name": "8: デジタル オーディオ (3- USB2 Digital Audio)",
             "endpoint_id": "{STABLE-GUID}"},
            ["17: デジタル オーディオ (5- USB2 Digital Audio)"],
            endpoints=endpoints)
        self.assertEqual(
            label, "17: デジタル オーディオ (5- USB2 Digital Audio)")

    def test_missing_stable_audio_is_not_replaced_by_identical_device(self):
        endpoints = [{
            "endpoint_id": "{other-guid}",
            "friendly_name": "デジタル オーディオ (USB2 Digital Audio)",
            "device_instance_id": "other-instance",
            "device_interface_path": "other-path",
            "physical_usb_key": "a&111&0",
            "active": True,
        }]
        self.assertIsNone(resolve_saved_audio(
            {"device_name": "2: デジタル オーディオ (USB2 Digital Audio)",
             "endpoint_id": "{missing-guid}",
             "device_instance_id": "missing-instance"},
            ["5: デジタル オーディオ (USB2 Digital Audio)"],
            endpoints=endpoints))

    def test_legacy_audio_can_follow_its_camera_usb_location(self):
        endpoints = [
            {"endpoint_id": "{one}", "friendly_name": "Audio (USB2)",
             "physical_usb_key": "a&111&0", "active": True},
            {"endpoint_id": "{two}", "friendly_name": "Audio (2- USB2)",
             "physical_usb_key": "b&222&0", "active": True},
        ]
        label = resolve_saved_audio(
            {"device_name": "4: Audio (USB2)",
             "normalized_name": normalized_audio_name("Audio (USB2)")},
            ["10: Audio (USB2)", "11: Audio (2- USB2)"],
            camera_device_path=(
                r"@device:pnp:\\?\usb#vid_345f&pid_2131&mi_00#b&222&0&0000#global"),
            endpoints=endpoints)
        self.assertEqual(label, "11: Audio (2- USB2)")

    def test_selected_audio_saves_windows_endpoint_identity(self):
        endpoints = [{
            "endpoint_id": "{guid}", "friendly_name": "Audio (USB2)",
            "device_instance_id": "instance", "device_interface_path": "path",
            "physical_usb_key": "b&222&0", "active": True,
        }]
        identity = identity_for_audio_label(
            "4: Audio (USB2)", endpoints=endpoints)
        self.assertEqual(identity["endpoint_id"], "{guid}")
        self.assertEqual(identity["device_instance_id"], "instance")

    def test_audio_monitor_publishes_exact_confirmation_output(self):
        monitor = AudioMonitor()
        monitor.output_stream = types.SimpleNamespace(active=True)
        monitor.selected_input_device_index = 8
        monitor.actual_input_device_index = 36
        monitor.recording_input_device_name = "USB capture"
        monitor.recording_input_host_api = "Windows WASAPI"
        monitor.recording_output_host_api = "Windows WASAPI"
        monitor.recording_output_rate = 48000
        monitor.recording_output_channels = 2
        monitor.recording_output_latency = 0.003
        received = []
        token = monitor.add_recording_output_listener(
            lambda data, frames, timing, status: received.append(
                (data.copy(), frames, timing, status)),
            48000, 2)
        block = numpy.array([[0.25, -0.5], [0.75, 0.0]],
                            dtype=numpy.float32)
        monitor._publish_recording_output(block, 2, "clock", "status")
        self.assertIsNotNone(token)
        self.assertEqual(received[0][1:], (2, "clock", "status"))
        numpy.testing.assert_array_equal(received[0][0], block)
        self.assertTrue(monitor.remove_recording_output_listener(token))
        monitor._publish_recording_output(block, 2, None, None)
        self.assertEqual(len(received), 1)

    def test_recorder_uses_pokecon_confirmation_pcm_and_unsubscribes(self):
        class FakeMonitor:
            def __init__(self):
                self.listener = None
                self.removed = []

            @staticmethod
            def recording_output_info():
                return {
                    "selected_input_device_index": 8,
                    "actual_input_device_index": 36,
                    "input_device_name": "USB capture",
                    "input_host_api": "Windows WASAPI",
                    "output_host_api": "Windows WASAPI",
                    "sample_rate": 48000,
                    "channels": 2,
                    "latency": 0.003,
                    "capture_latency": 0.002,
                    "playback_latency": 0.004,
                    "tap_point": "speaker_output_callback",
                }

            def add_recording_output_listener(self, callback, rate, channels):
                self.listener = callback
                self.asserted_format = (rate, channels)
                return 17

            def remove_recording_output_listener(self, token):
                self.removed.append(token)
                self.listener = None
                return True

        with tempfile.TemporaryDirectory() as folder:
            monitor = FakeMonitor()
            recorder = CaptureRecorder(folder)
            recorder.wav_path = os.path.join(folder, "shared.wav")
            recorder.audio_monitor = monitor
            self.assertTrue(recorder._start_monitored_audio(
                "8: USB capture"))
            self.assertEqual(monitor.asserted_format, (48000, 2))
            self.assertEqual(
                recorder.audio_source_mode,
                "pokecon_presented_output")
            monitor.listener(
                numpy.array([[0.5, -0.5]], dtype=numpy.float32),
                1, None, None)
            recorder._stop_monitored_audio_listener()
            recorder._stop_audio_writer()
            recorder.audio.close()
            recorder.audio = None
            self.assertEqual(monitor.removed, [17])
            with wave.open(recorder.wav_path, "rb") as audio:
                samples = struct.unpack("<hh", audio.readframes(1))
            self.assertEqual(samples, (16384, -16384))

    def test_audio_callback_uses_scheduled_speaker_presentation_time(self):
        timing = {"currentTime": 20.0, "outputBufferDacTime": 20.125}
        self.assertEqual(
            audio_callback_presentation_time(timing, now=100.0), 100.125)
        self.assertEqual(
            audio_callback_presentation_time(None, now=100.0), 100.0)

    def test_recorder_tracks_presented_video_frames(self):
        recorder = CaptureRecorder()
        recorder.active = True
        recorder.latest_frame = None
        frame = numpy.zeros((2, 3, 3), dtype=numpy.uint8)
        recorder.add_frame(
            frame, presented_at=10.25,
            presentation_mode="preview_presented")
        self.assertEqual(recorder.video_first_presentation_at, 10.25)
        self.assertEqual(recorder.video_presentation_frames, 1)
        self.assertEqual(
            recorder.video_presentation_mode, "preview_presented")

    def test_video_timeline_uses_preview_timestamp_not_delivery_time(self):
        class FakeVideo:
            def __init__(self):
                self.values = []

            def write(self, frame):
                self.values.append(int(frame[0, 0, 0]))

        recorder = CaptureRecorder()
        recorder.started_at = 100.0
        recorder.requested_fps = 10.0
        recorder.frames_written = 0
        recorder.video = FakeVideo()
        recorder.video_current_frame = numpy.full(
            (1, 1, 3), 1, dtype=numpy.uint8)
        recorder._advance_video_timeline(
            100.2, numpy.full((1, 1, 3), 2, dtype=numpy.uint8))
        recorder._advance_video_timeline(
            100.5, numpy.full((1, 1, 3), 3, dtype=numpy.uint8))
        recorder._advance_video_timeline(100.6)
        self.assertEqual(recorder.video.values, [1, 1, 2, 2, 2, 3])

    def test_late_compositor_delivery_keeps_original_presentation_time(self):
        recorder = CaptureRecorder()
        recorder.active = True
        recorder.started_at = time.monotonic() - 5.0
        recorder.latest_frame = None
        frame = numpy.zeros((2, 3, 3), dtype=numpy.uint8)
        recorder.add_frame(
            frame, presented_at=recorder.started_at + 1.25,
            presentation_mode="preview_presented")
        queued_at, queued_frame = recorder.video_frame_queue[0]
        self.assertAlmostEqual(
            queued_at,
            recorder.started_at + 1.25)
        self.assertIs(queued_frame, frame)
        self.assertGreater(recorder.video_delivery_delay_max, 3.0)

    def test_video_writer_preserves_every_presented_frame_in_order(self):
        class FakeVideo:
            def __init__(self):
                self.values = []

            def write(self, frame):
                self.values.append(int(frame[0, 0, 0]))

        recorder = CaptureRecorder()
        recorder.active = True
        recorder.started_at = 100.0
        recorder.requested_fps = 10.0
        recorder.frames_written = 0
        recorder.video = FakeVideo()
        recorder.video_current_frame = numpy.full(
            (1, 1, 3), 1, dtype=numpy.uint8)
        recorder.add_frame(
            numpy.full((1, 1, 3), 2, dtype=numpy.uint8),
            presented_at=100.2)
        recorder.add_frame(
            numpy.full((1, 1, 3), 3, dtype=numpy.uint8),
            presented_at=100.5)
        recorder.video_stop_at = 100.6

        recorder._video_writer_loop()

        self.assertEqual(recorder.video.values, [1, 1, 2, 2, 2, 3])
        self.assertEqual(recorder.video_presentation_frames, 2)
        self.assertEqual(recorder.video_coalesced_presentation_frames, 0)
        self.assertEqual(recorder.video_frame_queue_max_depth, 2)

    def test_ordered_presentations_create_a_real_60_fps_avi(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "ordered_60fps.avi")
            recorder = CaptureRecorder()
            writer, codec = recorder._open_video_writer(
                path, 60.0, (160, 90))
            self.assertIsNotNone(writer)
            self.assertIn(codec, ("mp4v", "XVID"))
            recorder.active = True
            recorder.started_at = 100.0
            recorder.requested_fps = 60.0
            recorder.frames_written = 0
            recorder.video = writer
            recorder.video_current_frame = numpy.zeros(
                (90, 160, 3), dtype=numpy.uint8)
            for index in range(120):
                recorder.add_frame(
                    numpy.full(
                        (90, 160, 3), (index + 1) * 2,
                        dtype=numpy.uint8),
                    presented_at=100.0 + index / 60.0)
            recorder.video_stop_at = 102.0
            recorder._video_writer_loop()
            writer.release()

            capture = cv2.VideoCapture(path)
            self.assertAlmostEqual(capture.get(cv2.CAP_PROP_FPS), 60.0, places=3)
            means = []
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                means.append(int(round(float(frame.mean()))))
            capture.release()
            self.assertEqual(len(means), 120)
            self.assertEqual(len(set(means)), 120)
            self.assertLessEqual(max(
                abs(actual - expected)
                for actual, expected in zip(means, range(2, 241, 2))), 5)

    def test_recorder_prefers_fast_mpeg4_avi_over_mjpeg(self):
        opened = mock.Mock()
        opened.isOpened.return_value = True
        with mock.patch("Recording.cv2.VideoWriter", return_value=opened) as create:
            writer, codec = CaptureRecorder._open_video_writer(
                "recording.avi", 60.0, (1280, 720))

        self.assertIs(writer, opened)
        self.assertEqual(codec, "mp4v")
        self.assertEqual(
            create.call_args.args[1], cv2.VideoWriter_fourcc(*"mp4v"))
        self.assertEqual(create.call_args.args[2:], (60.0, (1280, 720)))

    def test_mp4_mux_keeps_the_configured_60_fps_cfr(self):
        recorder = CaptureRecorder()
        completed = types.SimpleNamespace(returncode=0, stderr="")
        with mock.patch("Recording.shutil.which", return_value="ffmpeg.exe"), \
                mock.patch("Recording.os.path.isfile", return_value=True), \
                mock.patch("Recording.os.path.getsize", return_value=2048), \
                mock.patch("Recording.subprocess.run",
                           return_value=completed) as run:
            result = recorder._mux(
                "recording.avi", "recording.wav", "recording.mp4", 60.0)

        command = run.call_args.args[0]
        rate_index = command.index("-r")
        self.assertEqual(command[rate_index + 1], "60.000000")
        self.assertEqual(command[command.index("-crf") + 1], "18")
        self.assertEqual(command[command.index("-preset") + 1], "veryfast")
        self.assertEqual(command[command.index("-threads") + 1], "2")
        self.assertEqual(command[command.index("-brand") + 1], "mp42")
        self.assertEqual(command[command.index("-tag:v") + 1], "avc1")
        self.assertEqual(
            command[command.index("-video_track_timescale") + 1], "60000")
        if os.name == "nt":
            flags = run.call_args.kwargs["creationflags"]
            self.assertTrue(flags & 0x00004000)  # below-normal process
            self.assertTrue(flags & 0x08000000)  # no console window
        self.assertEqual(result, "recording.mp4")

    def test_mp4_mux_uses_presentation_clock_audio_when_drift_accumulates(self):
        recorder = CaptureRecorder()
        completed = types.SimpleNamespace(returncode=0, stderr="")
        alignment = {
            "applied": True, "final_drift_seconds": 1.5,
            "fixed_offset_ms": 0.0}
        with mock.patch("Recording.shutil.which", return_value="ffmpeg.exe"), \
                mock.patch("Recording.os.path.isfile", return_value=True), \
                mock.patch("Recording.os.path.getsize", return_value=2048), \
                mock.patch(
                    "RecordingSyncRepair.write_presentation_aligned_audio",
                    return_value=alignment) as align, \
                mock.patch(
                    "RecordingSyncRepair.store_presentation_alignment_report") as store, \
                mock.patch("Recording.subprocess.run",
                           return_value=completed) as run:
            result = recorder._mux(
                "recording.avi", "recording.wav", "recording.mp4", 60.0)

        command = run.call_args.args[0]
        self.assertIn("recording_presentation_aligned.wav", " ".join(command))
        self.assertNotIn("adelay", " ".join(command))
        self.assertNotIn("atrim", " ".join(command))
        self.assertEqual(alignment["fixed_offset_ms"], 0.0)
        self.assertTrue(alignment["used_for_final_mp4"])
        align.assert_called_once()
        self.assertEqual(store.call_count, 2)
        self.assertEqual(result, "recording.mp4")

    def test_cleanup_sampling_seeks_to_at_most_120_frames_across_clip(self):
        class FakeCapture:
            def __init__(self, total=72000):
                self.total = total
                self.positions = []
                self.read_count = 0
                self.released = False

            def get(self, _property):
                return self.total

            def set(self, property_id, value):
                self.positions.append((property_id, int(value)))
                return True

            def read(self):
                self.read_count += 1
                return True, numpy.zeros((4, 4, 3), dtype=numpy.uint8)

            def release(self):
                self.released = True

        capture = FakeCapture()
        recorder = CaptureRecorder()
        rule = {
            "image": numpy.zeros((1, 1, 3), dtype=numpy.uint8),
            "threshold": 2.0,
            "minimum_percent": 100.0,
        }
        with mock.patch("Recording.cv2.VideoCapture", return_value=capture):
            self.assertIsNone(recorder._discard_reason(
                "recording.avi", 1200.0, [rule], 0.0))

        self.assertEqual(capture.read_count, 120)
        self.assertEqual(len(capture.positions), 120)
        self.assertEqual(capture.positions[0], (cv2.CAP_PROP_POS_FRAMES, 0))
        self.assertEqual(capture.positions[-1],
                         (cv2.CAP_PROP_POS_FRAMES, 71999))
        self.assertTrue(capture.released)

        unknown_length_capture = FakeCapture(total=0)
        with mock.patch("Recording.cv2.VideoCapture",
                        return_value=unknown_length_capture):
            self.assertIsNone(recorder._discard_reason(
                "unknown-length.avi", 1200.0, [rule], 0.0))
        self.assertEqual(unknown_length_capture.read_count, 120)
        self.assertEqual(unknown_length_capture.positions, [])
        self.assertTrue(unknown_length_capture.released)

    def test_cleanup_sample_indexes_are_bounded_and_cover_both_ends(self):
        indexes = evenly_spaced_frame_indexes(72000, 120)
        self.assertEqual(len(indexes), 120)
        self.assertEqual((indexes[0], indexes[-1]), (0, 71999))
        self.assertEqual(evenly_spaced_frame_indexes(3, 120), [0, 1, 2])
        self.assertEqual(evenly_spaced_frame_indexes(0, 120), [])

    def test_timing_report_separates_container_and_wall_clock_fps(self):
        recorder = CaptureRecorder()
        with tempfile.TemporaryDirectory() as folder:
            recorder.session_dir = folder
            recorder.started_at = 100.0
            recorder.requested_fps = 60.0
            recorder.video_codec = "mp4v"
            recorder.frames_written = 600
            recorder._write_timing_report(9.9992, 60.0, 60.0048)
            with open(os.path.join(folder, "recording_timing.json"),
                      "r", encoding="utf-8") as stream:
                report = json.load(stream)

        video = report["video"]
        self.assertEqual(video["intermediate_codec"], "mp4v")
        self.assertEqual(video["container_fps"], 60.0)
        self.assertEqual(video["corrected_fps"], 60.0)
        self.assertEqual(video["wall_clock_frame_rate"], 60.0048)

    def test_recording_repair_removes_only_all_channel_exact_zeros(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "source.wav")
            repaired = os.path.join(folder, "repaired.wav")
            samples = numpy.array([
                [10, 0], [0, 0], [0, 20], [0, 0], [30, 40],
            ], dtype=numpy.int16)
            with wave.open(source, "wb") as audio:
                audio.setnchannels(2)
                audio.setsampwidth(2)
                audio.setframerate(10)
                audio.writeframes(samples.tobytes())
            details = wav_info(source)
            self.assertEqual(details["exact_zero_frames"], 2)
            kept, removed = write_without_exact_zeros(source, repaired)
            self.assertEqual((kept, removed), (3, 2))
            with wave.open(repaired, "rb") as audio:
                result = numpy.frombuffer(
                    audio.readframes(audio.getnframes()),
                    dtype=numpy.int16).reshape(-1, 2)
            numpy.testing.assert_array_equal(
                result, samples[[0, 2, 4]])

    def test_recording_repair_audio_advance_keeps_total_duration(self):
        expression = audio_advance_filter(500)
        self.assertIn("atrim=start=0.500000", expression)
        self.assertIn("asetpts=PTS-STARTPTS", expression)
        self.assertIn("apad=pad_dur=0.500000", expression)

    def test_presentation_clock_rebuild_repairs_accumulated_drift_without_offset(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "source.wav")
            timing = os.path.join(folder, "recording_timing.json")
            rebuilt = os.path.join(folder, "rebuilt.wav")
            sample_rate = 48000
            content_frames = sample_rate * 12
            target_frames = sample_rate * 15
            time_axis = numpy.arange(content_frames) / sample_rate
            content_float = (
                numpy.sin(2.0 * numpy.pi * 440.0 * time_axis) * 1500.0)
            random = numpy.random.default_rng(7)
            burst_frames = int(sample_rate * 0.040)
            for burst_second in (2, 4, 6, 8, 10):
                start = burst_second * sample_rate
                content_float[start:start + burst_frames] += (
                    random.standard_normal(burst_frames)
                    * 9000.0 * numpy.hanning(burst_frames))
            content = numpy.clip(numpy.rint(
                content_float), -32768, 32767).astype(
                    numpy.int16).reshape(-1, 1)
            samples = numpy.vstack((
                content,
                numpy.zeros((target_frames - content_frames, 1),
                            dtype=numpy.int16),
            ))
            with wave.open(source, "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(sample_rate)
                audio.writeframes(samples.tobytes())
            with open(timing, "w", encoding="utf-8") as stream:
                json.dump({"audio": {
                    "frames": target_frames,
                    # Shorter than the normal 80 ms crossfade.  The overlap
                    # must shrink instead of allowing a 0-frame WAV.
                    "first_presentation_offset_ms": 35.0,
                    "initial_alignment_frames": int(sample_rate * 0.035),
                    "trailing_padding_frames": target_frames - content_frames,
                    "presentation_clock_samples": [{
                        "offset_seconds": float(second),
                        "clock_error_ms": -200.0 * second,
                    } for second in range(1, 15)],
                }}, stream)

            report = write_presentation_aligned_audio(
                source, timing, rebuilt, minimum_drift_ms=1.0)

            self.assertTrue(report["applied"])
            self.assertEqual(report["fixed_offset_ms"], 0.0)
            self.assertTrue(report["pitch_preserved"])
            self.assertEqual(report["pitch_scale"], 1.0)
            self.assertIn(report["engine"], ("rubberband", "atempo"))
            self.assertLessEqual(report["minimum_crossfade_ms"], 70.0)
            self.assertEqual(
                report["trailing_padding_frames_removed"], sample_rate * 3)
            self.assertGreaterEqual(report["segment_count"], 4)
            self.assertTrue(report["segment_output_length_enforced"])
            with wave.open(rebuilt, "rb") as audio:
                result = numpy.frombuffer(
                    audio.readframes(audio.getnframes()), dtype=numpy.int16)
            self.assertEqual(len(result), target_frames)
            # Direct PCM resampling would lower this 440 Hz tone to about
            # 352 Hz in the stretched section.  Pitch-preserving stretch must
            # retain the original fundamental while changing only duration.
            window = result[sample_rate * 8:sample_rate * 9].astype(float)
            window *= numpy.hanning(len(window))
            frequencies = numpy.fft.rfftfreq(len(window), 1.0 / sample_rate)
            peak = frequencies[numpy.argmax(
                numpy.abs(numpy.fft.rfft(window)))]
            self.assertAlmostEqual(float(peak), 440.0, delta=2.0)
            # Every Rubber Band segment has a small flush tail.  If those
            # tails are concatenated instead of trimmed to their requested
            # lengths, later transients advance by tens of milliseconds per
            # boundary even though the final WAV duration still matches.
            expected_frame = int((10.0 / 0.8) * sample_rate)
            radius = int(sample_rate * 0.100)
            energy_frames = int(sample_rate * 0.010)
            region = result[
                expected_frame - radius:expected_frame + radius].astype(float)
            energy = numpy.convolve(
                region * region,
                numpy.ones(energy_frames) / energy_frames,
                mode="valid")
            realized_frame = (
                expected_frame - radius + int(numpy.argmax(energy))
                + energy_frames // 2)
            self.assertLess(
                abs(realized_frame - expected_frame), int(sample_rate * 0.020))

    def test_main_full_rate_does_not_skip_on_early_timer_jitter(self):
        self.assertTrue(preview_render_due(
            0.016, 1.0 / 60.0, full_rate=True,
            prioritized=True, viewable=True))
        self.assertFalse(preview_render_due(
            0.005, 1.0 / 60.0, full_rate=True,
            prioritized=True, viewable=True))
        self.assertFalse(preview_render_due(
            0.016, 1.0 / 60.0, full_rate=False,
            prioritized=True, viewable=True))

    def test_video_input_combobox_does_not_change_with_mousewheel(self):
        calls = []

        class FakeCombobox:
            def bind(self, event, callback, add=None):
                calls.append((event, callback, add))
                return "binding-id"

        result = guard_combobox_mousewheel(FakeCombobox())
        self.assertEqual(result, "binding-id")
        self.assertEqual(calls[0][0], "<MouseWheel>")
        self.assertIs(calls[0][1], consume_combobox_mousewheel)
        self.assertEqual(calls[0][2], "+")
        self.assertEqual(calls[0][1](object()), "break")

    def test_input_set_combobox_forwards_wheel_only_to_tab_scroll(self):
        bindings = []
        scrolled = []

        class FakeCombobox:
            def bind(self, event, callback, add=None):
                bindings.append((event, callback, add))
                return "input-set-wheel-binding"

        wheel_event = object()
        result = guard_combobox_mousewheel(
            FakeCombobox(), lambda event: scrolled.append(event))
        self.assertEqual(result, "input-set-wheel-binding")
        self.assertEqual(bindings[0][0], "<MouseWheel>")
        self.assertEqual(bindings[0][1](wheel_event), "break")
        self.assertEqual(scrolled, [wheel_event])

    def test_pokecon_windows_are_rejected_as_capture_targets(self):
        name = "Poke-Controller Modified Extension"
        self.assertTrue(is_pokecon_window_title(
            name + " ver.0.1.7 (profile: default)", name))
        self.assertTrue(is_pokecon_window_title(name, name))
        self.assertFalse(is_pokecon_window_title("Google Chrome", name))
        self.assertFalse(is_pokecon_window_title("Pokemon Game", name))

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
        self.assertFalse(restored["camera_feature_limited"])

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
        # The single checked owner keeps its cadence while minimized too;
        # ordinary minimized windows remain inexpensive.
        self.assertAlmostEqual(
            preview_render_interval(60, True, False, full_rate=True),
            1.0 / 60.0)
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
    def test_za_story_status_shows_only_the_active_story_and_common_states(self):
        source_path = os.path.join(
            SERIAL_CONTROLLER, "Commands", "PythonCommands", "ZA",
            "ZA_story", "ZA_story.py")
        with open(source_path, "r", encoding="utf-8-sig") as stream:
            records = {
                item["name"]: item["text"]
                for item in source_function_records(stream.read())
            }
        namespace = {}
        exec(compile(records["ZA_story_status_text"], source_path, "exec"), namespace)

        command = types.SimpleNamespace(
            main_current_state="MAIN_1_Z_LANK",
            _1_story_current_state="1_STORY_OUT_HOTEL_Z_47",
            _2_story_current_state="2_STORY_START_CHECK",
            _3_story_current_state="3_STORY_START_CHECK",
            _4_story_current_state="4_STORY_START_CHECK",
            _5_story_current_state="5_STORY_START_CHECK",
            _6_story_current_state="6_STORY_START_CHECK",
            _7_story_current_state="7_STORY_START_CHECK",
            _8_story_current_state="8_STORY_START_CHECK",
            common_skill_change_current_state="COMMON_SKILL_CHANGE_START",
            common_box_change_current_state="COMMON_BOX_CHANGE_START",
            common_item_give_current_state="COMMON_ITEM_GIVE_START",
            common_evolution_current_state="COMMON_EVOLUTION_START",
        )
        status = namespace["ZA_story_status_text"](command)
        self.assertEqual(status, """----------------------------
 STATE_MAIN_FUNCTION   :: MAIN_1_Z_LANK :: 1_STORY_OUT_HOTEL_Z_47

 ### STATE_2_VAR ###

 SKILL_CHANGE_FUNCTION :: COMMON_SKILL_CHANGE_START
 BOX_CHANGE_FUNCTION   :: COMMON_BOX_CHANGE_START
 ITEM_GIVE_FUNCTION    :: COMMON_ITEM_GIVE_START
 EVOLUTION_FUNCTION    :: COMMON_EVOLUTION_START
----------------------------""")
        self.assertNotIn("2_STORY_START_CHECK", status)
        self.assertNotIn("BATTLE_COUNT", status)
        self.assertNotIn("WHITE_CHECK", status)

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
    def test_sample_comparison_uses_function_sync_history_not_file_time(self):
        base = "def sample(self):\n    return 1\n"
        source_new = "def sample(self):\n    return 2\n"
        sample_new = "def sample(self):\n    return 3\n"
        base_hash = function_content_hash(base)

        update = function_update_status(source_new, base, base_hash)
        self.assertEqual(update["status"], "source_newer")
        self.assertTrue(format_function_update_status(update).startswith(
            "ソース関数が新しい"))

        update = function_update_status(base, sample_new, base_hash)
        self.assertEqual(update["status"], "sample_newer")
        self.assertTrue(format_function_update_status(update).startswith(
            "サンプル関数が新しい"))

        update = function_update_status(source_new, sample_new, base_hash)
        self.assertEqual(update["status"], "both_changed")
        self.assertIn("両方変更", format_function_update_status(update))

        update = function_update_status(source_new, sample_new)
        self.assertEqual(update["status"], "unknown_history")
        self.assertIn("同期履歴なし", format_function_update_status(update))

        update = function_update_status(source_new, source_new)
        self.assertEqual(update["status"], "synchronized")

    def test_sample_comparison_includes_function_update_label(self):
        source = (
            "class Demo:\n"
            "    def sample(self):\n"
            "        return 2\n")
        base = "def sample(self):\n    return 1\n"
        with tempfile.TemporaryDirectory() as root:
            source_path = os.path.join(root, "Demo.py")
            fragment_path = os.path.join(root, "sample.pyfrag")
            metadata_path = os.path.join(root, "sample.pokesample.json")
            with open(source_path, "w", encoding="utf-8") as stream:
                stream.write(source)
            with open(fragment_path, "w", encoding="utf-8") as stream:
                stream.write(base)
            with open(metadata_path, "w", encoding="utf-8") as stream:
                json.dump({
                    "name": "sample", "fragment": "sample.pyfrag",
                    "source": {"path": source_path, "function": "sample"},
                    "function_sync": {
                        "sample": {
                            "source_function": "sample",
                            "base_hash": function_content_hash(base),
                            "synced_at": "2026-08-01T00:00:00+00:00",
                        },
                    },
                }, stream)

            comparisons = compare_sample_function_folder(
                source, root, root, source_path)
            self.assertEqual(comparisons[0]["function_update"]["status"],
                             "source_newer")
            self.assertIn("ソース関数が新しい",
                          comparisons[0]["function_update_label"])

            with open(metadata_path, "w", encoding="utf-8") as stream:
                json.dump({
                    "name": "sample", "fragment": "sample.pyfrag",
                    "source": {"path": source_path, "function": "sample"},
                }, stream)
            comparisons = compare_sample_function_folder(
                source, root, root, source_path)
            self.assertEqual(
                comparisons[0]["function_update"]["status"],
                "unknown_history")

    def test_source_to_sample_sync_records_a_function_baseline(self):
        source = (
            "class Demo:\n"
            "    def sample(self):\n"
            "        return 2\n")
        with tempfile.TemporaryDirectory() as root:
            source_path = os.path.join(root, "Demo.py")
            fragment_path = os.path.join(root, "sample.pyfrag")
            metadata_path = os.path.join(root, "sample.pokesample.json")
            with open(source_path, "w", encoding="utf-8") as stream:
                stream.write(source)
            with open(fragment_path, "w", encoding="utf-8") as stream:
                stream.write("def sample(self):\n    return 1\n")
            with open(metadata_path, "w", encoding="utf-8") as stream:
                json.dump({
                    "name": "sample", "fragment": "sample.pyfrag",
                    "source": {"path": source_path, "function": "sample"},
                }, stream)

            comparisons = compare_sample_function_folder(
                source, root, root, source_path)
            self.assertEqual(
                comparisons[0]["function_update"]["status"],
                "unknown_history")
            update_sample_fragments(source, comparisons, ["sample"])

            with open(metadata_path, "r", encoding="utf-8") as stream:
                metadata = json.load(stream)
            expected_text = next(
                item["text"] for item in source_function_records(source)
                if item["name"] == "sample")
            self.assertEqual(
                metadata["function_sync"]["sample"]["base_hash"],
                function_content_hash(expected_text))
            comparisons = compare_sample_function_folder(
                source, root, root, source_path)
            self.assertEqual(
                comparisons[0]["function_update"]["status"],
                "synchronized")

            changed_source = source.replace("return 2", "return 3")
            comparisons = compare_sample_function_folder(
                changed_source, root, root, source_path)
            self.assertEqual(
                comparisons[0]["function_update"]["status"],
                "source_newer")

    def test_reflected_source_is_atomically_saved_to_the_actual_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "Demo.py")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("class Demo:\n    value = 1\n")
            updated = "class Demo:\n    value = 2\n"
            saved_path = save_reflected_source(path, updated)
            self.assertEqual(saved_path, os.path.abspath(path))
            with open(path, "r", encoding="utf-8") as stream:
                self.assertEqual(stream.read(), updated)
            self.assertFalse(os.path.exists(
                path + ".sample-source-save.tmp"))

    def test_invalid_reflected_source_does_not_overwrite_actual_file(self):
        with self.assertRaises(ValueError):
            save_reflected_source("", "class Demo:\n    pass\n")
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "Demo.py")
            original = "class Demo:\n    value = 1\n"
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(original)
            with self.assertRaises(SyntaxError):
                save_reflected_source(path, "class Demo\n    value = 2\n")
            with open(path, "r", encoding="utf-8") as stream:
                self.assertEqual(stream.read(), original)

    def test_sample_check_source_reflections_save_the_actual_source(self):
        studio_path = os.path.join(DEV_STUDIO, "PokeConDevStudio.py")
        with open(studio_path, "r", encoding="utf-8-sig") as stream:
            tree = ast.parse(stream.read())
        outer = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "open_sample_function_check_mode")
        nested = {
            node.name: node for node in ast.walk(outer)
            if isinstance(node, ast.FunctionDef)
        }
        for function_name in (
                "library_to_source", "merge_names_and_source_bodies",
                "rollback_last_batch", "apply_replacement",
                "apply_to_all_usages"):
            calls = {
                call.func.id for call in ast.walk(nested[function_name])
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
            }
            self.assertIn("save_reflected_source", calls, function_name)

    def test_sample_reflection_saves_and_rechecks_from_disk(self):
        source = (
            "class Demo:\n"
            "    def sample(self):\n"
            "        return 1\n")
        with tempfile.TemporaryDirectory() as root:
            source_path = os.path.join(root, "Demo.py")
            sample_dir = os.path.join(root, "Samples")
            os.makedirs(sample_dir)
            fragment_path = os.path.join(sample_dir, "sample.pyfrag")
            with open(source_path, "w", encoding="utf-8") as stream:
                stream.write(source)
            with open(fragment_path, "w", encoding="utf-8") as stream:
                stream.write("def sample(self):\n    return 2\n")

            comparisons = compare_sample_function_folder(
                source, root, root, source_path)
            backup = create_sample_sync_backup(
                source_path, source, comparisons, ["sample"],
                os.path.join(root, "Backups"),
                source_will_be_saved=True)
            updated = update_source_from_samples(
                source, comparisons, ["sample"])
            save_reflected_source(source_path, updated)

            with open(source_path, "r", encoding="utf-8") as stream:
                saved_source = stream.read()
            rechecked = compare_sample_function_folder(
                saved_source, root, root, source_path)
            self.assertIn("return 2", saved_source)
            self.assertEqual(rechecked[0]["status"], "match")
            self.assertTrue(backup["source_was_saved"])

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

    def test_sample_check_project_root_resolves_to_fragment_library(self):
        with tempfile.TemporaryDirectory() as project:
            fragment_root = os.path.join(
                project, "SerialController", "DevTemplates", "Fragments")
            os.makedirs(fragment_root)
            self.assertEqual(
                resolve_fragment_folder(fragment_root, project),
                os.path.abspath(fragment_root))
            child = os.path.join(fragment_root, "Pokemon_ZA")
            os.makedirs(child)
            self.assertEqual(
                resolve_fragment_folder(fragment_root, child),
                os.path.abspath(child))
            unrelated = os.path.join(os.path.dirname(project), "unrelated")
            with self.assertRaises(ValueError):
                resolve_fragment_folder(fragment_root, unrelated)

    def test_sample_origin_path_survives_drive_and_workspace_move(self):
        old = ("D:/tools/PokeCon/Poke-Controller/SerialController/"
               "Commands/PythonCommands/ZA/ZA_story/ZA_story.py")
        current = ("C:/PokeCon/Poke-Controller/SerialController/"
                   "Commands/PythonCommands/ZA/ZA_story/ZA_story.py")
        relative = ("SerialController/Commands/PythonCommands/ZA/"
                    "ZA_story/ZA_story.py")
        self.assertTrue(source_paths_equivalent(old, current))
        self.assertTrue(source_paths_equivalent(relative, current))
        self.assertFalse(source_paths_equivalent(
            "SerialController/Commands/Other.py", current))

    def test_recheck_keeps_sample_registered_before_workspace_move(self):
        source = (
            "class Demo:\n"
            "    def updated(self):\n"
            "        return 'new'\n")
        with tempfile.TemporaryDirectory() as root:
            sample_dir = os.path.join(root, "Pokemon_ZA", "updated")
            os.makedirs(sample_dir)
            with open(os.path.join(sample_dir, "updated.pyfrag"), "w",
                      encoding="utf-8") as stream:
                stream.write(
                    "def updated(self):\n"
                    "    return 'old'\n")
            with open(os.path.join(
                    sample_dir, "updated.pokesample.json"), "w",
                    encoding="utf-8") as stream:
                json.dump({
                    "name": "updated", "fragment": "updated.pyfrag",
                    "source": {
                        "path": ("D:/old/PokeCon/SerialController/Commands/"
                                 "PythonCommands/ZA/ZA_story/ZA_story.py"),
                        "function": "updated",
                    },
                }, stream)
            comparisons = compare_sample_function_folder(
                source, root, root,
                "C:/new/PokeCon/SerialController/Commands/PythonCommands/"
                "ZA/ZA_story/ZA_story.py")
            self.assertEqual(len(comparisons), 1)
            self.assertEqual(comparisons[0]["status"], "different")

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
            self.assertFalse(backup["source_was_saved"])
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

    def test_dependency_group_records_reused_multi_function_history(self):
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "ExistingBundle")
            os.makedirs(folder)
            metadata_path = os.path.join(
                folder, "ExistingBundle.pokesample.json")
            body_path = os.path.join(folder, "ExistingBundle.pyfrag")
            flow_main = next(
                item["text"] for item in source_function_records(self.SOURCE)
                if item["name"] == "flow_main")
            with open(metadata_path, "w", encoding="utf-8") as stream:
                json.dump({
                    "name": "ExistingBundle",
                    "fragment": "ExistingBundle.pyfrag",
                }, stream)
            with open(body_path, "w", encoding="utf-8") as stream:
                stream.write(flow_main)

            plan, _members = register_dependency_group(
                self.SOURCE, ["flow_main"], root,
                "Imported/DemoFlow", "DemoFlow", source_path="Demo.py")
            flow_row = next(
                row for row in plan["registration"]
                if row["name"] == "flow_main")
            self.assertEqual(flow_row["status"], "reuse")
            with open(metadata_path, "r", encoding="utf-8") as stream:
                metadata = json.load(stream)
            self.assertEqual(
                metadata["function_sync"]["flow_main"]["base_hash"],
                function_content_hash(flow_main))


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

    def test_shared_find_selects_a_current_match_when_results_exist(self):
        matches = [("1.2", "1.5"), ("1.10", "1.13"), ("3.0", "3.3")]
        self.assertEqual(find_match_index(matches, cursor_index="1.0"), 0)
        self.assertEqual(find_match_index(matches, cursor_index="1.9"), 1)
        self.assertEqual(
            find_match_index(matches, current_index="3.0", cursor_index="1.0"),
            2)
        self.assertEqual(find_match_index(matches, cursor_index="4.0"), 0)
        self.assertEqual(find_match_index([], cursor_index="1.0"), -1)

    def test_discovers_class_functions_and_builds_bulk_names(self):
        records = source_function_records(self.SOURCE)
        self.assertEqual([item["name"] for item in records], ["move_old", "keep"])
        self.assertEqual(
            build_rename_map(["move_old"], "_old", "", prefix="ZA_"),
            {"move_old": "ZA_move"},
        )

    def test_function_registration_actions_remain_above_the_function_tree(self):
        studio_path = os.path.join(DEV_STUDIO, "PokeConDevStudio.py")
        with open(studio_path, "r", encoding="utf-8-sig") as stream:
            source = stream.read()
        tree = ast.parse(source)
        method = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "_build_source_functions_tab")
        method_source = ast.get_source_segment(source, method)
        self.assertIn('orient="vertical", command=tab_canvas.yview',
                      method_source)
        self.assertLess(
            method_source.index('text="選択をサンプルへ登録"'),
            method_source.index("self.source_function_tree = ttk.Treeview"))
        self.assertLess(
            method_source.index('text="選択1件の登録名を確認・変更"'),
            method_source.index("self.source_function_tree = ttk.Treeview"))

    def test_multi_function_fragment_is_recognized_as_registered(self):
        body = (
            "def first(self):\n    return 1\n\n"
            "def second(self):\n    return 2\n")
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "Bundle")
            os.makedirs(folder)
            metadata_path = os.path.join(folder, "Bundle.pokesample.json")
            body_path = os.path.join(folder, "Bundle.pyfrag")
            with open(metadata_path, "w", encoding="utf-8") as stream:
                json.dump({
                    "name": "Bundle", "fragment": "Bundle.pyfrag",
                }, stream)
            with open(body_path, "w", encoding="utf-8") as stream:
                stream.write(body)

            candidates = catalog_function_candidates(root)
            self.assertEqual(set(candidates), {"first", "second"})
            registration = classify_function_registration(
                "def second(self):\n    return 2\n",
                candidates["second"], "second")
            self.assertEqual(registration["status"], "登録済み")
            self.assertEqual(
                registration["fragment_id"],
                "Bundle/Bundle.pokesample.json")
            self.assertFalse(registration["overwrite_supported"])

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
            self.assertEqual(
                metadata["function_sync"]["ZA_move"]["source_function"],
                "move_old")
            self.assertEqual(
                metadata["function_sync"]["ZA_move"]["base_hash"],
                function_content_hash(next(
                    item["text"] for item in source_function_records(self.SOURCE)
                    if item["name"] == "move_old")))
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
