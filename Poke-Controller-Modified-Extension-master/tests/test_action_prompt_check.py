"""Runtime action prompt checks with one in-memory camera and temp catalogs."""
from __future__ import annotations

import copy
import ast
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import cv2
import numpy as np

sys.dont_write_bytecode = True
SERIAL_CONTROLLER = Path(__file__).resolve().parents[1] / "SerialController"
sys.path.insert(0, str(SERIAL_CONTROLLER))
from Commands.PythonCommands.LocalFunction import ActionPromptCheck as runtime


class MemoryCamera:
    def __init__(self, frame):
        self.frame = frame
        self.reads = 0

    def readFreshFrame(self, timeout=.75):
        self.reads += 1
        return self.frame


class ActionPromptCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.random = np.random.RandomState(803)
        self.frame = self.random.randint(0, 256, (720, 1280, 3), dtype=np.uint8)
        self.glyph = self.random.randint(0, 256, (23, 23, 3), dtype=np.uint8)
        self.frame[400:423, 700:723] = self.glyph
        self.image("Template/ZA_Story_PIC/Common/other_a_marker.png", self.glyph)
        self.word_path = "Template/ZA_Story_PIC/ActionPrompts/word.png"
        self.image(self.word_path, self.random.randint(0, 256, (24, 80, 3), dtype=np.uint8))
        self.picture = "POKEMON_ZA_IN_MARKER"
        self.candidate = {"id": "in", "picture": self.picture, "template_path": self.word_path,
                          "threshold": .99, "use_gray": True, "crop": [550, 250, 900, 550]}
        self.catalog_path = self.root / "Template/ZA_Story_PIC/ActionPrompts/catalog.json"
        self.catalog_path.write_text(json.dumps({"candidates": [self.candidate]}), encoding="utf-8")
        self.source_path = self.root / "command.py"
        self.source_path.write_text('def enter(self):\n    return self.image_check("POKEMON_ZA_IN_MARKER")\n', encoding="utf-8")
        self.source = {"source_path": str(self.source_path), "line": 2, "runtime_line": 2,
                       "function": "enter", "runtime_code_sha256": "code_a", "callsite_key": "endpoint_a",
                       "action_first_line": 3, "pictures": [self.picture], "step": "STEP_21",
                       "context": ["STEP_21", "COMMON_START"]}
        self.output_root = self.root / "history"
        self.command = self.command_instance()

    def image(self, name, array):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        ok, encoded = cv2.imencode(".png", array)
        self.assertTrue(ok)
        path.write_bytes(encoded.tobytes())
        return path

    def register(self, command, target, x, y):
        name = "templates/" + target + ".png"
        self.image(name, self.frame[y:y + 9, x:x + 9])
        command.IMAGE_DETECTION_TARGETS[target] = [{
            "template_path": name, "threshold": .99, "use_gray": True,
            "crop": [x - 1, y - 1, x + 10, y + 10]}]

    def command_instance(self):
        command = SimpleNamespace(
            camera=MemoryCamera(self.frame), Debug_A_Check=True,
            _action_prompt_template_root=str(self.root), _action_prompt_debug_root=str(self.output_root),
            _za_story_pre_step_gate_last_dispatch_state="STEP_21", Common_current_state="COMMON_START",
            _za_movement_a_pending={"key": "endpoint_a", "_action_prompt_source": copy.deepcopy(self.source)},
            checkIfAlive=lambda: None, IMAGE_DETECTION_TARGETS={}, IMAGE_DETECTION_OPERATORS={})
        self.register(command, "POKEMON_ZA_FIELD_W", 20, 30)
        self.register(command, "POKEMON_ZA_WANINOKO_ICON", 40, 30)
        return command

    def check(self, command=None, count=True):
        return runtime.check_action_prompt(command or self.command, (self.picture,), count_attempt=count)

    def set_source(self, **changes):
        self.command._za_movement_a_pending["_action_prompt_source"].update(changes)

    def exhaust_two_attempts(self):
        self.assertFalse(self.check())
        self.assertFalse(self.check())

    def test_normal_full_word_prompt_succeeds_even_with_debug_off(self):
        self.image(self.word_path, self.frame[360:384, 610:690])
        self.command.Debug_A_Check = False
        self.assertTrue(self.check())
        self.assertEqual(self.command.last_action_prompt_detection["status"], "word")
        self.assertEqual(self.command.camera.reads, 1)
        self.assertFalse(self.output_root.exists())
        self.assertEqual(self.command._action_prompt_attempts, {})

    def test_debug_off_never_accepts_glyph_or_saves_evidence(self):
        self.command.Debug_A_Check = False
        for unused in range(5):
            self.assertFalse(self.check())
        self.assertEqual(self.command._action_prompt_attempts, {})
        self.assertFalse(self.output_root.exists())

    def test_third_logical_attempt_allows_glyph_and_saves_exact_fresh_frame(self):
        self.exhaust_two_attempts()
        self.assertFalse(self.output_root.exists())
        self.assertTrue(self.check())
        detail = self.command.last_action_prompt_detection
        self.assertEqual(detail["status"], "debug_glyph")
        self.assertEqual(detail["attempt"], 3)
        self.assertEqual(self.command.camera.reads, 3)
        folder = Path(detail["evidence"]["event_dir"])
        saved = cv2.imdecode(np.frombuffer((folder / "frame.png").read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        np.testing.assert_array_equal(saved, self.frame)
        event = json.loads((folder / "event.json").read_text(encoding="utf-8"))
        self.assertEqual(len(event["ranking"]), 1)
        self.assertFalse(event["ranking"][0]["matched"])
        self.assertEqual(event["comparison_crop"], [550, 250, 900, 550])
        self.assertEqual(self.command._action_prompt_attempts, {})

    def test_samples_inside_wait_never_count_as_failed_logical_attempts(self):
        for unused in range(6):
            self.assertFalse(self.check(count=False))
        self.assertEqual(self.command._action_prompt_attempts, {})
        self.exhaust_two_attempts()
        for unused in range(4):
            self.assertFalse(self.check(count=False))
        self.assertEqual(list(self.command._action_prompt_attempts.values()), [2])
        self.assertTrue(self.check())

    def test_distinct_lines_and_pending_actions_do_not_share_attempt_counts(self):
        self.exhaust_two_attempts()
        self.set_source(line=10, runtime_line=10)
        self.exhaust_two_attempts()
        self.set_source(line=2, runtime_line=2, action_first_line=99)
        self.exhaust_two_attempts()
        self.assertEqual(sorted(self.command._action_prompt_attempts.values()), [2, 2, 2])
        self.set_source(action_first_line=3)
        self.assertTrue(self.check())

    def test_distinct_source_files_and_code_revisions_do_not_share_attempts(self):
        self.exhaust_two_attempts()
        self.set_source(source_path=str(self.root / "other.py"))
        self.assertFalse(self.check())
        self.set_source(source_path=str(self.source_path), runtime_code_sha256="code_b")
        self.assertFalse(self.check())
        self.assertEqual(sorted(self.command._action_prompt_attempts.values()), [1, 1, 2])

    def test_missing_frames_do_not_increment_or_clear_existing_attempts(self):
        self.assertFalse(self.check())
        self.command.camera.frame = None
        for unused in range(4):
            self.assertFalse(self.check())
            self.assertEqual(self.command.last_action_prompt_detection["status"], "no_frame")
        self.assertEqual(list(self.command._action_prompt_attempts.values()), [1])
        self.command.camera.frame = self.frame
        self.assertFalse(self.check())
        self.assertTrue(self.check())

    def test_save_failure_never_returns_success_or_clears_failure_count(self):
        self.exhaust_two_attempts()
        with mock.patch.object(runtime, "save_action_prompt_debug", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.check()
        self.assertFalse(self.command.last_action_prompt_detection["matched"])
        self.assertEqual(list(self.command._action_prompt_attempts.values()), [3])
        self.assertFalse(self.output_root.exists())

    def test_title_missing_field_battle_and_comments_suppress_glyph_fallback(self):
        for blocker in ("title", "POKEMON_ZA_BATTLE_BALL_CHECK", "POKEMON_ZA_ESCAPE",
                        "POKEMON_ZA_TEXT_WHITE_COMMENT", "POKEMON_ZA_TEXT_BLACK_COMMENT",
                        "POKEMON_ZA_TEXT_GREEN_COMMENT", "POKEMON_ZA_HELP_MARKER",
                        "POKEMON_ZA_2_SELECT"):
            with self.subTest(blocker=blocker):
                command = self.command_instance()
                if blocker == "title":
                    command.IMAGE_DETECTION_TARGETS = {}
                else:
                    self.register(command, blocker, 60, 30)
                for unused in range(3):
                    self.assertFalse(self.check(command))
                self.assertEqual(command.last_action_prompt_detection["status"], "fallback_not_field")
                self.assertFalse(self.output_root.exists())

    def test_glyph_missing_after_three_attempts_is_not_a_success(self):
        self.command.camera.frame = self.random.randint(0, 256, self.frame.shape, dtype=np.uint8)
        # Keep the synthetic field references while removing only the glyph.
        self.command.camera.frame[29:41, 19:51] = self.frame[29:41, 19:51]
        for unused in range(3):
            self.assertFalse(self.check())
        detail = self.command.last_action_prompt_detection
        self.assertFalse(detail["fallback"]["matched"])
        self.assertFalse(self.output_root.exists())

    def test_full_word_success_resets_attempt_counter(self):
        self.exhaust_two_attempts()
        self.image(self.word_path, self.frame[360:384, 610:690])
        self.assertTrue(self.check())
        self.assertEqual(self.command._action_prompt_attempts, {})
        self.image(self.word_path, self.random.randint(0, 256, (24, 80, 3), dtype=np.uint8))
        self.assertFalse(self.check())
        self.assertEqual(list(self.command._action_prompt_attempts.values()), [1])

    def test_history_accumulates_across_command_instances(self):
        for unused in range(2):
            self.assertFalse(self.check())
        self.assertTrue(self.check())
        first = self.command.last_action_prompt_detection["evidence"]
        first_bytes = (Path(first["event_dir"]) / "event.json").read_bytes()
        second_command = self.command_instance()
        for unused in range(2):
            self.assertFalse(self.check(second_command))
        self.assertTrue(self.check(second_command))
        self.assertEqual((Path(first["event_dir"]) / "event.json").read_bytes(), first_bytes)
        index = [json.loads(line) for line in (self.output_root / "index.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(index), 2)
        self.assertNotEqual(index[0]["event_id"], index[1]["event_id"])

    def test_capture_keeps_nested_endpoint_action_identity_and_restores_pending(self):
        pending = self.command._za_movement_a_pending
        def action_one():
            pass
        def action_two():
            pass
        first = runtime.capture_action_prompt_source(self.command, (self.picture,), "same", action_one)
        second = runtime.capture_action_prompt_source(self.command, (self.picture,), "same", action_two)
        self.assertIs(self.command._za_movement_a_pending, pending)
        self.assertEqual(first["action_first_line"], action_one.__code__.co_firstlineno)
        self.assertEqual(second["action_first_line"], action_two.__code__.co_firstlineno)
        self.assertNotEqual(first["action_first_line"], second["action_first_line"])
        self.assertEqual(first["function"], self.test_capture_keeps_nested_endpoint_action_identity_and_restores_pending.__name__)

    def integrated_command(self):
        """Bind the saved ZA source methods, without importing/starting Commands."""
        source_path = SERIAL_CONTROLLER / "Commands/PythonCommands/ZA/ZA_story/ZA_story.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
        names = {"ZA_story_wait_movement_a", "ZA_story_movement_a_check",
                 "ZA_story_checked_movement_action", "ZA_story_movement_a_context",
                 "ZA_story_movement_a_pending", "ZA_story_resume_movement_a",
                 "image_check", "_2_story_absol_move21"}
        methods = [copy.deepcopy(node) for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name in names]
        self.assertEqual(len(methods), len(names))
        clock = SimpleNamespace(now=100., monotonic=lambda: clock.now)
        namespace = {"time": clock, "Button": SimpleNamespace(A="A", L="L"),
                     "Stick": SimpleNamespace(LEFT="LEFT"), "Direction": lambda *args: args}
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(source_path), "exec"), namespace)
        command = type("IntegratedCommand", (), {name: namespace[name] for name in names})()
        command.__dict__.update(vars(self.command_instance()))
        command._za_movement_a_pending = None
        command._za_story_pre_step_gate_last_dispatch_state = "2_STORY_ABSOL_MOVE21"
        command.presses = []
        command.buttons = []
        def wait(seconds):
            # Simulate delayed scheduling so a three-second wait needs four
            # samples, while keeping its real deadline/completed-attempt logic.
            clock.now += max(float(seconds), 1.)
        def press(direction, **options):
            command.presses.append((direction, options))
            clock.now += options.get("duration", 0.) + options.get("wait", 0.)
        command.wait = wait
        command.press = press
        command.pressRep = lambda button, **options: command.buttons.append((button, options))
        command._image_check_target = lambda target: target == "POKEMON_ZA_NO_BATTLE_FIELD_HARD_CHECK"
        command.image_check_exception = command._image_check_target
        return command, clock

    def test_source_move21_completes_third_wait_and_never_replays_movement(self):
        command, clock = self.integrated_command()
        self.assertEqual(command._2_story_absol_move21(), "2_STORY_ABSOL_MOVE21")
        source = dict(command._za_movement_a_pending["_action_prompt_source"])
        self.assertEqual(list(command._action_prompt_attempts.values()), [1])
        self.assertEqual(len(command.presses), 1)
        # An earlier long delay must not trigger the old 12-second reset before
        # this call site has completed its second and third logical attempts.
        clock.now += 20.
        self.assertEqual(command._2_story_absol_move21(), "2_STORY_ABSOL_MOVE21")
        self.assertIsNone(command._za_movement_a_failure)
        self.assertEqual(list(command._action_prompt_attempts.values()), [2])
        self.assertEqual(command._za_movement_a_pending["_action_prompt_source"], source)
        self.assertEqual(command._2_story_absol_move21(), "2_STORY_ABSOL_MOVE22")
        self.assertEqual(len(command.presses), 1)
        self.assertEqual([entry[0] for entry in command.buttons], ["L", "A"])
        self.assertIsNone(command._za_movement_a_pending)
        self.assertIsNone(command._za_movement_a_failure)
        self.assertEqual(command._action_prompt_attempts, {})
        self.assertEqual(command.last_action_prompt_detection["attempt"], 3)
        self.assertGreater(command.camera.reads, 3)

    def test_source_move21_debug_off_keeps_word_check_and_existing_failure(self):
        command, clock = self.integrated_command()
        command.Debug_A_Check = False
        self.assertEqual(command._2_story_absol_move21(), "2_STORY_ABSOL_MOVE21")
        clock.now += 20.
        self.assertEqual(command._2_story_absol_move21(), "2_STORY_ABSOL_MOVE21")
        self.assertIsNotNone(command._za_movement_a_failure)
        self.assertEqual(command._action_prompt_attempts, {})
        self.assertNotIn("A", [entry[0] for entry in command.buttons])
        self.assertFalse(self.output_root.exists())

    def test_source_nested_same_key_endpoints_have_independent_three_trial_counts(self):
        command, clock = self.integrated_command()
        completed = []
        def second_action():
            completed.append("second")
            return "DONE"
        def first_action():
            completed.append("first")
            return command.ZA_story_checked_movement_action(
                "same_key", (self.picture,), second_action, "WAIT_SECOND", allow_recenter=False)
        result = command.ZA_story_checked_movement_action(
            "same_key", (self.picture,), first_action, "WAIT_FIRST", allow_recenter=False)
        self.assertEqual(result, "WAIT_FIRST")
        first_source = command._za_movement_a_pending["_action_prompt_source"]
        self.assertEqual(command.ZA_story_resume_movement_a("same_key"), "WAIT_FIRST")
        self.assertEqual(command.ZA_story_resume_movement_a("same_key"), "WAIT_SECOND")
        second_source = command._za_movement_a_pending["_action_prompt_source"]
        self.assertNotEqual(first_source["action_first_line"], second_source["action_first_line"])
        self.assertEqual(list(command._action_prompt_attempts.values()), [1])
        self.assertEqual(completed, ["first"])
        self.assertEqual(command.ZA_story_resume_movement_a("same_key"), "WAIT_SECOND")
        self.assertEqual(command.ZA_story_resume_movement_a("same_key"), "DONE")
        self.assertEqual(completed, ["first", "second"])
        self.assertEqual(command._action_prompt_attempts, {})
        self.assertIsNone(command._za_movement_a_pending)

    def test_source_zero_timeout_counts_one_attempt_per_call(self):
        command, clock = self.integrated_command()
        results = [command.ZA_story_wait_movement_a((self.picture,), timeout=0.) for unused in range(3)]
        self.assertEqual(results, [False, False, True])
        self.assertEqual(command.camera.reads, 3)

    def test_source_image_check_accepts_manual_target_and_research_alias(self):
        self.image(self.word_path, self.frame[360:384, 610:690])
        research = dict(self.candidate, id="research", picture="ZA_RESEARCH_A")
        self.catalog_path.write_text(json.dumps({"candidates": [self.candidate, research]}), encoding="utf-8")
        command, clock = self.integrated_command()
        command.Debug_A_Check = False
        self.assertTrue(command.image_check("ZA_ACTION_PROMPT_IN"))
        self.assertTrue(command.image_check("ZA_RESEARCH_A"))
        self.assertTrue(command.image_check("ZA_STORY_COMMON_ZA_RESEARCH_A"))
        self.assertTrue(command.image_check("ZA_STORY_COMMON_ZA_RESEARCH_A"))
        self.assertEqual(command.last_action_prompt_detection["source"]["pictures"],
                         ["ZA_STORY_COMMON_ZA_RESEARCH_A"])
        self.assertTrue(command.image_check("ZA_ACTION_PROMPT_RESEARCH"))
        self.assertFalse(command.image_check("ZA_ACTION_PROMPT_IN", nocheckflag=0))
        self.assertFalse(self.output_root.exists())


if __name__ == "__main__":
    unittest.main()
