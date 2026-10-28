"""No devices, real inference, restarts or controller packets in these tests."""
import json
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

SERIAL = Path(__file__).resolve().parents[1] / "SerialController"
sys.path.insert(0, str(SERIAL))
import SubscriptionAgent as agent
from LiveAssistCommands import LiveCommandRegistry, validate_operation
from CommandQuickRun import (CommandQuickRun, CURRENT, FIRST, FRESH,
                             location_choices, observed_location)


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.config = agent.normalize_settings(dict(enabled=True, idle_seconds=5, dark_seconds=2, cooldown_seconds=60))
        self.detector = agent.StallDetector()
        self.sample(0)

    def sample(self, now, brightness=0, ratio=1, session="run1", running=True):
        return self.detector.check(session, running, brightness, ratio, self.config, now)

    def test_both_conditions_and_one_report_per_episode(self):
        for now in range(1, 5):
            self.assertIsNone(self.sample(now))
        self.assertIsNotNone(self.sample(5))
        for now in range(6, 100):
            self.assertIsNone(self.sample(now))

    def test_input_including_manual_input_restarts_idle(self):
        for now in range(1, 5):
            self.sample(now)
        self.detector.activity(4)
        for now in range(5, 9):
            self.assertIsNone(self.sample(now))
        self.assertIsNotNone(self.sample(9))

    def test_light_image_or_missing_camera_never_counts_as_dark(self):
        for brightness, ratio in ((80, 1), (0, .5), (None, None), (float("nan"), 1)):
            for now in range(1, 12):
                self.assertIsNone(self.sample(now, brightness, ratio))

    def test_frame_gap_requires_new_consecutive_dark_observations(self):
        self.sample(1)
        self.sample(2)
        self.assertIsNone(self.sample(30))
        self.assertIsNone(self.sample(31))
        self.assertIsNotNone(self.sample(32))

    def test_stop_and_new_command_clear_timers(self):
        for now in range(1, 5):
            self.sample(now)
        self.assertIsNone(self.sample(5, session="run2"))
        self.assertIsNone(self.sample(6, running=False))
        self.assertIsNone(self.sample(7))

    def test_recovery_rearms_only_after_cooldown(self):
        for now in range(1, 6):
            self.sample(now)
        self.sample(6, 100, 0)
        for now in range(7, 65):
            self.assertIsNone(self.sample(now))
        self.assertIsNotNone(self.sample(65))


class SubscriptionTests(unittest.TestCase):
    def test_remaining_uses_most_restrictive_window_and_bucket(self):
        payload = {"rateLimitsByLimitId": {
            "codex": {"primary": {"usedPercent": 20}, "secondary": {"usedPercent": 70}},
            "model": {"primary": {"usedPercent": 50}}}}
        self.assertEqual(agent.remaining_percent(payload), 30)

    def test_unknown_and_stale_limits_fail_closed(self):
        for payload in ({}, {"rateLimits": {}}, {"rateLimits": {"primary": {"usedPercent": None}}},
                        {"rateLimits": {"primary": {"usedPercent": float("nan")}}},
                        {"rateLimits": {"primary": {"usedPercent": 1, "resetsAt": 10}}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                agent.remaining_percent(payload, now=11)

    def test_reached_limit_blocks_even_if_percent_is_low(self):
        self.assertEqual(agent.remaining_percent({"rateLimits": {"rateLimitReachedType": "hard", "primary": {"usedPercent": 20}}}), 0)

    def test_api_environment_not_inherited_and_prompt_never_in_shell(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test", "CODEX_API_KEY": "test", "ANTHROPIC_API_KEY": "test"}):
            env = agent.child_environment()
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("CODEX_API_KEY", env)
            self.assertNotIn("ANTHROPIC_API_KEY", env)
        args = agent.build_exec_args("codex.exe", "C:/a b", "model;$x", "high", "out.txt")
        self.assertIn('forced_login_method="chatgpt"', args)
        self.assertIn("--ignore-user-config", args)
        self.assertIn("workspace-write", args)
        self.assertEqual(args[-1], "-")
        self.assertIn("model;$x", args)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", args)

    def test_bad_configuration_does_not_enable_monitor(self):
        for key, value in (("remaining_percent", 0), ("idle_seconds", -1), ("brightness", "nan"), ("effort", "invented")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                agent.normalize_settings({key: value})
        self.assertFalse(agent.normalize_settings({"enabled": "false"})["enabled"])

    def test_wrong_auth_type_never_reads_limits_or_runs_inference(self):
        with mock.patch.object(agent, "CodexConnection") as connection:
            client = connection.return_value
            client.call.side_effect = [{}, {"account": {"type": "apiKey"}}]
            with self.assertRaisesRegex(ValueError, "ChatGPT"):
                agent.probe_codex("codex.exe", ".")
            self.assertEqual(client.call.call_count, 2)
            client.close.assert_called_once()

    def test_dispatch_rechecks_quota_before_source_or_launch(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(agent, "resolve_codex", return_value="codex.exe"), \
                mock.patch.object(agent, "probe_codex", return_value={"remaining": 5}), \
                mock.patch.object(agent, "git_guard") as guard, \
                mock.patch.object(agent.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(ValueError, "未満"):
                agent.run_request(dict(model="test"), {"workspace": directory}, directory)
            guard.assert_not_called()
            launch.assert_not_called()

    def test_changed_source_blocks_before_inference(self):
        probe = {"remaining": 80, "models": [{"model": "test", "supportedReasoningEfforts": [{"reasoningEffort": "medium"}]}]}
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(agent, "resolve_codex", return_value="codex.exe"), \
                mock.patch.object(agent, "probe_codex", return_value=probe), \
                mock.patch.object(agent, "git_guard", return_value={"sha256": "changed"}), \
                mock.patch.object(agent.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(ValueError, "変更された"):
                agent.run_request(dict(model="test"), {"workspace": directory, "source": "command.py", "source_sha256": "old"}, directory)
            launch.assert_not_called()

    def test_complete_dispatch_uses_stdin_and_writes_result_without_real_inference(self):
        probe = {"remaining": 80, "models": [{"model": "test", "supportedReasoningEfforts": [{"reasoningEffort": "medium"}]}]}
        class Pipe(io.StringIO):
            def close(self):
                self.saved = self.getvalue()
                super().close()
        pipe = Pipe()
        proc = mock.Mock(stdin=pipe, returncode=0)
        proc.poll.return_value = 0
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(agent, "resolve_codex", return_value="codex.exe"), \
                mock.patch.object(agent, "probe_codex", return_value=probe), \
                mock.patch.object(agent, "git_guard", return_value={"sha256": "same"}) as guard, \
                mock.patch.object(agent.subprocess, "run", return_value=types.SimpleNamespace(stdout="--ignore-user-config")), \
                mock.patch.object(agent.subprocess, "Popen", return_value=proc) as launch:
            Path(directory, "result.txt").write_text("Test result", encoding="utf-8")
            result = agent.run_request(dict(model="test"), {"workspace": directory, "source": "command.py", "source_sha256": "same"}, directory)
            self.assertTrue(Path(result).is_file())
            self.assertEqual(guard.call_count, 2)
            self.assertIn("既存の作業中差分", pipe.saved)
            self.assertTrue(Path(directory, "completion.json").is_file())
            self.assertNotIn("shell", launch.call_args.kwargs)


class GitConditionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.nested = self.root / "nested"
        self.nested.mkdir()
        self.source = self.nested / "command.py"
        self.source.write_text("value = 1\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "initial")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root)] + list(args), check=True, capture_output=True)

    def test_nested_workspace_accepts_committed_command(self):
        self.assertEqual(agent.git_guard(self.nested, self.source)["source"], str(self.source.resolve()))

    def test_staged_and_unstaged_changes_block(self):
        self.source.write_text("value = 2\n")
        for staged in (False, True):
            if staged:
                self.git("add", ".")
            with self.subTest(staged=staged), self.assertRaises(ValueError):
                agent.git_guard(self.nested, self.source)

    def test_untracked_command_is_not_clean(self):
        source = self.nested / "new.py"
        source.write_text("pass")
        with self.assertRaises(ValueError):
            agent.git_guard(self.nested, source)

    def test_other_changes_only_block_repository_scope(self):
        (self.root / "other.txt").write_text("new")
        agent.git_guard(self.nested, self.source, "command")
        with self.assertRaises(ValueError):
            agent.git_guard(self.nested, self.source, "repository")


class RegistryTests(unittest.TestCase):
    def test_register_refresh_and_edit_without_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = LiveCommandRegistry(directory)
            registry.register("test", "Bを押す", "press(Button.B, duration=0.1)")
            self.assertEqual(registry.items["test"]["name"], "Bを押す")
            registry.register("test", "Aを押す", "press(Button.A)")
            self.assertIn("Button.A", registry.items["test"]["code"])
            self.assertFalse(registry.scan())
            Path(directory, "test.json").write_text("{partial", encoding="utf-8")
            registry.scan()
            self.assertFalse(registry.items)
            self.assertTrue(registry.errors)

    def test_arbitrary_code_and_lifecycle_access_are_rejected(self):
        for code in ("import os", "self.finish()", "__import__('os')", "open('a','w')", "while True: pass", "Button.__class__", "press = log"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                validate_operation(code)

    def test_movement_and_finite_loops_supported(self):
        validate_operation("for i in range(3):\n    press(Button.B, duration=0.1)\nstick(Stick.RIGHT, 90, duration=0.2)\nlog('done')")


def locations():
    return [{"id": "step:" + str(n), "kind": "step", "mode": "attribute", "variable": "step",
             "value": n, "label": "Step " + str(n), "description": "detail " + str(n)} for n in range(12)]


class StepTests(unittest.TestCase):
    def test_neighbours_are_from_same_table(self):
        items = locations()
        items.append(dict(items[0], id="other", variable="unrelated", value=100))
        self.assertEqual([item["value"] for item in location_choices(items, items[5])], list(range(2, 9)))

    def test_constructor_defaults_not_used_as_current(self):
        self.assertIsNone(observed_location(types.SimpleNamespace(step=7, alive=False, thread=None), locations()))
        command = types.SimpleNamespace(step=7, alive=False, thread=types.SimpleNamespace(ident=5))
        self.assertEqual(observed_location(command, locations())["value"], 7)

    def test_inactive_chapter_does_not_override_current(self):
        command = types.SimpleNamespace(alive=True, thread=None,
            STATE_MAIN_FUNCTION={"MAIN_2": None}, main_current_state="MAIN_2",
            STATE_2_STORY_FUNCTION={"2_STORY_5": None}, _2_story_current_state="2_STORY_5",
            STATE_3_STORY_FUNCTION={"3_STORY_INIT": None}, _3_story_current_state="3_STORY_INIT")
        rows = [{"id": str(i), "value": value} for i, value in enumerate(("MAIN_2", "2_STORY_5", "3_STORY_INIT"))]
        self.assertEqual(observed_location(command, rows)["value"], "2_STORY_5")


class EmbeddedUiTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.name = "Command"
        self.app = types.SimpleNamespace(root=self.root, command_start_overrides={}, command_run_favorites={},
            cur_command=types.SimpleNamespace(NAME=self.name, step=5, alive=True, thread=None),
            _selected_command_name=lambda: self.name,
            _command_run_options=lambda _: {"locations": locations(), "enabled": True},
            _command_classes=lambda _: [], _sync_command_start_overrides_to_active_input_set=lambda: True,
            fresh_start_current_command=mock.Mock())
        self.panel = CommandQuickRun(self.root, self.app)
        self.panel.pack()
        self.panel.refresh()

    def tearDown(self):
        self.root.destroy()

    def test_default_captures_current_before_fresh_instance(self):
        self.assertEqual(self.panel.choice.get(), CURRENT)
        self.assertTrue(self.panel.capture_before_start())
        fresh = types.SimpleNamespace(NAME=self.name, step=0)
        self.assertTrue(self.panel.prepare(fresh))
        with mock.patch("CommandImageCollection.arm_native_image_collection"):
            self.assertTrue(self.panel.apply(fresh))
        self.assertEqual(fresh.step, 5)
        self.assertFalse(self.app.command_start_overrides[self.name]["confirm"])

    def test_all_steps_search_and_options_do_not_create_toplevel(self):
        self.panel.scope.set("全Step")
        self.panel.refresh_choices()
        self.panel.search.set("detail 10")
        self.assertIn(self.panel.display(locations()[10]), self.panel.start_cb["values"])
        self.panel.toggle_options()
        self.panel.confirm("verify", lambda: None)
        self.root.update_idletasks()
        self.assertFalse(any(isinstance(widget, __import__('tkinter').Toplevel) for widget in self.root.winfo_children()))

    def test_game_specific_fresh_start_only_offered_for_capable_command(self):
        self.assertNotIn(FRESH, self.panel.start_cb["values"])
        self.app._command_classes = lambda _: [types.SimpleNamespace(POKECON_FRESH_START={})]
        self.panel.refresh_choices()
        self.assertIn(FRESH, self.panel.start_cb["values"])
        self.panel.choice.set(FRESH)
        self.assertFalse(self.panel.capture_before_start())
        self.app.fresh_start_current_command.assert_called_once()

    def test_input_set_switch_does_not_reuse_old_current_step(self):
        self.assertEqual(self.panel.current()["value"], 5)
        self.app._active_input_set_name = "different-device"
        self.panel.refresh()
        self.assertIsNone(self.panel.current())
        self.app.cur_command = types.SimpleNamespace(NAME=self.name, step=9, alive=True, thread=None)
        self.assertEqual(self.panel.current()["value"], 9)

    def test_favorites_keep_step_and_debug_without_a_dialog(self):
        self.panel.favorite.set("再確認")
        self.panel.save_favorite()
        self.panel.choice.set(FIRST)
        self.panel.load_favorite()
        self.assertEqual(self.panel.mapping[self.panel.choice.get()]["value"], 5)
        self.panel.delete_favorite()
        self.assertEqual(self.app.command_run_favorites[self.name], [])

    def test_same_command_shortcut_cannot_bypass_save_delete_confirmation(self):
        self.app._command_run_options = lambda _: {"locations": locations(), "enabled": True,
                                                   "save_recovery": {"available": True}}
        self.app.startPlay = mock.Mock()
        self.panel.refresh(force=True)
        self.panel.delete_user.set("1")
        fresh = types.SimpleNamespace(NAME=self.name, step=0)
        self.panel.prepared = (self.name, self.panel.current())
        self.assertFalse(self.panel.prepare(fresh))
        self.assertFalse(self.panel.capture_before_start())
        self.panel.confirm_button.invoke()
        self.app.startPlay.assert_called_once()
        self.assertTrue(self.panel.capture_before_start())
        self.assertTrue(self.panel.prepare(fresh))
        self.assertIsNone(self.panel.delete_authorization)

    def test_embedded_reference_preview_cancels_without_any_popup(self):
        self.app.controller_nb = types.SimpleNamespace(select=lambda _: None)
        self.app.commands_tab = object()
        self.app._command_debug_binding = lambda: ("device",)
        provider = types.SimpleNamespace(read_reference_frame=mock.Mock(side_effect=ValueError("no reference")))
        def cancel():
            def walk(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from walk(child)
            for widget in walk(self.panel):
                if isinstance(widget, __import__('tkinter').ttk.Button) and widget.cget("text") == "キャンセル":
                    widget.invoke()
        self.root.after(200, cancel)
        result = self.panel.show_start_preview(SERIAL, {"reference": {}, "recording": {}}, provider)
        self.assertIsNone(result)
        self.assertFalse(any(isinstance(widget, __import__('tkinter').Toplevel) for widget in self.root.winfo_children()))


class OperationUiTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from AiAssistPanel import AiAssistPanel
        self.root = tk.Tk()
        self.root.withdraw()
        self.directory = tempfile.TemporaryDirectory()
        self.app = types.SimpleNamespace(root=self.root, _active_input_set_name="first",
            cur_command=object(), _stop_command_recovery_script=mock.Mock(),
            _run_command_recovery_script=mock.Mock(return_value=True))
        self.panel = AiAssistPanel(self.root, self.app, tk.ttk.Frame(self.root))
        self.panel.base = Path(self.directory.name)
        self.panel.bind_profile()
        self.panel.settings["allow_registration"] = True
        self.panel.registry.register("one", "操作1", "press(Button.A)")
        self.panel.registry.register("two", "操作2", "press(Button.B)")
        self.panel.refresh_operations()
        self.panel.operation.set("操作1")

    def tearDown(self):
        self.root.destroy()
        self.directory.cleanup()

    def test_hot_updated_code_is_revalidated_and_run_without_restart(self):
        agent.atomic_json(self.panel.registry.directory / "one.json",
                          {"id": "one", "name": "操作1", "code": "press(Button.X)"})
        self.assertTrue(self.panel.execute())
        self.app._run_command_recovery_script.assert_called_once_with("press(Button.X)", auto_resume=False)

    def test_removed_selection_never_runs_another_default_operation(self):
        (self.panel.registry.directory / "one.json").unlink()
        self.assertFalse(self.panel.execute())
        self.app._run_command_recovery_script.assert_not_called()

    def test_input_set_change_before_tick_blocks_old_numbered_action(self):
        self.panel.slots["1"] = "one"
        self.app._active_input_set_name = "second"
        self.assertFalse(self.panel.execute(slot=1))
        self.app._run_command_recovery_script.assert_not_called()
        self.assertIn("InputSet", self.panel.status.get())

    def test_unreadable_update_never_executes_cached_code(self):
        with mock.patch.object(self.panel.registry, "scan", side_effect=OSError("file replaced")):
            self.assertFalse(self.panel.execute())
        self.app._run_command_recovery_script.assert_not_called()

    def test_profile_switch_blocks_stale_editor_registration(self):
        self.app._active_input_set_name = "second"
        self.panel.register()
        self.assertFalse(self.panel.registry.directory.exists())
        self.assertIn("InputSet", self.panel.status.get())


if __name__ == "__main__":
    unittest.main()
