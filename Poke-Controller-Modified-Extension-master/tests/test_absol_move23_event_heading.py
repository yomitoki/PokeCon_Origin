"""MOVE23 heading regression using the saved source and memory-only inputs."""
from __future__ import annotations

import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py"
STEP = "2_STORY_ABSOL_MOVE23"
NEXT = "2_STORY_ABSOL_MOVE24"
KEY = "_2_story_absol_move23"
FIELD = "POKEMON_ZA_NO_BATTLE_FIELD_HARD_CHECK"


class Stopped(Exception):
    pass


class MemoryCommand:
    def __init__(self):
        self.field = True
        self.marker_result = True
        self.action_ready = True
        self.pending = False
        self.events = []
        self.continuation = None
        self.stop_from_marker = False
        self.stop_after_marker = False
        self.stop_in_guard = False
        self.stopped = False

    def checkIfAlive(self):
        if self.stopped:
            raise Stopped("stopped after EVENT alignment")

    def ZA_story_movement_a_pending(self, key):
        self.events.append(("pending", key))
        return self.pending

    def ZA_story_resume_movement_a(self, key):
        self.events.append(("resume", key))
        if not self.action_ready:
            return STEP
        self.pending = False
        return self.continuation()

    def image_check(self, name):
        self.events.append(("image", name))
        return self.field if name == FIELD else False

    def ZA_markerdir(self, *args, **options):
        self.events.append(("marker", args, options))
        if self.stop_from_marker:
            raise Stopped("stopped during EVENT alignment")
        if self.stop_after_marker:
            self.stopped = True
        return self.marker_result

    def press(self, direction, **options):
        self.events.append(("move", direction, options))

    def wait(self, seconds):
        self.events.append(("wait", seconds))

    def pressRep(self, button, **options):
        self.events.append(("button", button, options))

    def ZA_story_checked_movement_action(self, key, pictures, action, waiting_result, **options):
        self.events.append(("guard", key, pictures, waiting_result, options))
        if self.stop_in_guard:
            raise Stopped("stopped during A confirmation")
        if self.action_ready:
            return action()
        self.pending = True
        self.continuation = action
        return waiting_result


class AbsolMove23EventHeadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_text = SOURCE.read_text(encoding="utf-8-sig")
        tree = ast.parse(cls.source_text)
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name == KEY)
        namespace = {"Direction": lambda stick, angle: (stick, angle),
                     "Stick": SimpleNamespace(LEFT="LEFT"), "Button": SimpleNamespace(A="A")}
        exec(compile(ast.Module(body=[copy.deepcopy(method)], type_ignores=[]), str(SOURCE), "exec"), namespace)
        cls.run_step = staticmethod(namespace[KEY])

    def actions(self, command, kind):
        return [event for event in command.events if event[0] == kind]

    def test_existing_pending_resumes_without_field_marker_or_movement(self):
        command = MemoryCommand()
        command.pending = True
        command.continuation = lambda: NEXT
        self.assertEqual(self.run_step(command), NEXT)
        self.assertEqual(command.events, [("pending", KEY), ("resume", KEY)])

    def test_without_field_no_marker_move_or_a_input(self):
        command = MemoryCommand()
        command.field = False
        self.assertEqual(self.run_step(command), STEP)
        self.assertEqual(command.events, [("pending", KEY), ("image", FIELD)])

    def test_event_alignment_failure_never_starts_route_or_a_guard(self):
        command = MemoryCommand()
        command.marker_result = False
        self.assertEqual(self.run_step(command), STEP)
        self.assertEqual(self.actions(command, "marker"), [("marker", ("EVENT",), {})])
        self.assertEqual(self.actions(command, "move"), [])
        self.assertEqual(self.actions(command, "button"), [])
        self.assertEqual(self.actions(command, "guard"), [])

    def test_event_success_precedes_forward_four_seconds_and_existing_a_action(self):
        command = MemoryCommand()
        self.assertEqual(self.run_step(command), NEXT)
        self.assertEqual(command.events, [
            ("pending", KEY), ("image", FIELD), ("marker", ("EVENT",), {}),
            ("move", ("LEFT", 90), {"duration": 4.0, "wait": 1.0}), ("wait", .5),
            ("guard", KEY, ("POKEMON_ZA_OUT_MARKER",), STEP, {"dialogue_state": NEXT}),
            ("button", "A", {"repeat": 1, "duration": .15, "wait": .5, "interval": .1})])

    def test_a_wait_retry_does_not_repeat_event_or_forward_movement(self):
        command = MemoryCommand()
        command.action_ready = False
        self.assertEqual(self.run_step(command), STEP)
        self.assertEqual(self.run_step(command), STEP)
        command.action_ready = True
        self.assertEqual(self.run_step(command), NEXT)
        self.assertEqual(len(self.actions(command, "marker")), 1)
        self.assertEqual(len(self.actions(command, "move")), 1)
        self.assertEqual(len(self.actions(command, "guard")), 1)
        self.assertEqual(len(self.actions(command, "button")), 1)

    def test_stop_during_event_propagates_without_left_route_or_a(self):
        command = MemoryCommand()
        command.stop_from_marker = True
        with self.assertRaisesRegex(Stopped, "during EVENT"):
            self.run_step(command)
        self.assertEqual(self.actions(command, "move"), [])
        self.assertEqual(self.actions(command, "button"), [])

    def test_stop_after_event_prevents_forward_route_and_a(self):
        command = MemoryCommand()
        command.stop_after_marker = True
        with self.assertRaisesRegex(Stopped, "after EVENT"):
            self.run_step(command)
        self.assertEqual(self.actions(command, "move"), [])
        self.assertEqual(self.actions(command, "button"), [])

    def test_stop_during_existing_a_confirmation_does_not_send_a(self):
        command = MemoryCommand()
        command.stop_in_guard = True
        with self.assertRaisesRegex(Stopped, "during A"):
            self.run_step(command)
        self.assertEqual(len(self.actions(command, "marker")), 1)
        self.assertEqual(len(self.actions(command, "move")), 1)
        self.assertEqual(self.actions(command, "button"), [])


if __name__ == "__main__":
    unittest.main()
