"""Capture-pixel, independent Commands, and AV-preserving highlight regressions."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

import cv2
import numpy as np

SERIAL = Path(__file__).resolve().parents[1] / "SerialController"
sys.path.insert(0, str(SERIAL))
from CaptureGeometry import capture_frame_size, display_rect_to_capture, fit_preview_size
from EventClips import EventSequence, EventMatcher, event_intervals, validate_rule, snapshot_rule, export_event_clips, za_field_hard_targets, _run_ffmpeg
from InputSetRuntimeRegistry import ActiveInputSetRegistry, canonical_device_key, device_usage_conflicts


def rule_for(path):
    target = {"name": "marker", "variants": [{"template_path": str(path),
        "threshold": .9, "use_gray": False, "crop": [0, 0, 64, 64]}]}
    return validate_rule({"stages": [{"operator": "AND", "targets": [target]}],
        "pre_seconds": .2, "post_seconds": .4, "interval_seconds": 0,
        "cooldown_seconds": 1, "max_total_gb": .01})


class GeometryTests(unittest.TestCase):
    def test_real_frame_dimensions_override_negotiation(self):
        camera = types.SimpleNamespace(capture_size=(1280, 720), image_bgr=np.zeros((480, 640, 3)))
        self.assertEqual(capture_frame_size(camera), (640, 480))

    def test_display_resize_keeps_raw_crop_identical(self):
        raw = np.arange(480 * 640).reshape(480, 640)
        expected = raw[120:360, 160:480]
        for display in ((640, 480), (320, 240), (800, 300)):
            w, h = display
            x1, y1, x2, y2 = display_rect_to_capture((w/4, h/4, w*3/4, h*3/4), display, (640, 480))
            np.testing.assert_array_equal(raw[y1:y2, x1:x2], expected)

    def test_reverse_and_outside_drag_clamps(self):
        self.assertEqual(display_rect_to_capture((150, 100, -5, -5), (100, 100), (640, 480)), (0, 0, 640, 480))

    def test_fitting_keeps_source_aspect(self):
        self.assertEqual(fit_preview_size((1280, 720), (1000, 400)), (711, 400))
        self.assertEqual(fit_preview_size((640, 480), (400, 400)), (400, 300))

    def test_range_screenshot_uses_capture_pixels_in_actual_handler(self):
        from GuiAssets import CaptureArea
        camera = types.SimpleNamespace(image_bgr=np.zeros((480, 640, 3)), saveCapture=mock.Mock())
        preview = types.SimpleNamespace(camera=camera, show_size=(800, 300),
            min_x=200, min_y=75, max_x=600, max_y=225, _logger=mock.Mock(),
            after=mock.Mock(), delete=mock.Mock(),
            master=types.SimpleNamespace(is_use_left_stick_mouse=mock.Mock(get=lambda: False),
                                         is_use_right_stick_mouse=mock.Mock(get=lambda: False)))
        CaptureArea.ReleaseRangeSS(preview, None)
        camera.saveCapture.assert_called_once_with(crop=1, crop_ax=[160, 120, 480, 360])


class EventSequenceTests(unittest.TestCase):
    def setUp(self):
        self.rule = rule_for("unused")
        self.rule["stages"].append(copy.deepcopy(self.rule["stages"][0]))
        self.rule["stages"][1]["stable_seconds"] = .3
        self.rule["within_seconds"] = 1

    def test_then_needs_later_frame_and_stability(self):
        sequence = EventSequence(self.rule)
        self.assertIsNone(sequence.update(0, [True, True]))
        self.assertIsNone(sequence.update(.1, [False, True]))
        self.assertIsNone(sequence.update(.2, [False, True]))
        self.assertEqual(sequence.update(.4, [False, True])["confirmed_seconds"], .4)

    def test_timeout_cannot_reuse_earlier_first_condition(self):
        sequence = EventSequence(self.rule)
        sequence.update(0, [True, False])
        self.assertIsNone(sequence.update(2, [False, True]))
        self.assertIsNone(sequence.update(3, [False, True]))

    def test_false_sample_resets_stability(self):
        sequence = EventSequence(self.rule)
        sequence.update(0, [True, False])
        sequence.update(.1, [False, True])
        sequence.update(.2, [False, False])
        self.assertIsNone(sequence.update(.4, [False, True]))
        self.assertIsNone(sequence.update(.6, [False, True]))
        self.assertIsNotNone(sequence.update(.7, [False, True]))

    def test_persistent_marker_fires_once(self):
        rule = rule_for("unused")
        sequence = EventSequence(rule)
        self.assertIsNotNone(sequence.update(0, [True]))
        self.assertIsNone(sequence.update(3, [True]))
        self.assertIsNone(sequence.update(4, [False]))
        self.assertIsNotNone(sequence.update(5, [True]))

    def test_ranges_merge_without_crossing_media_end(self):
        rule = rule_for("unused")
        result = event_intervals([{"confirmed_seconds": .1}, {"confirmed_seconds": .5}], rule, .7)
        self.assertEqual(result, [[0.0, .7]])

    def test_nan_and_empty_conditions_fail_closed(self):
        for value in (float("nan"), float("inf"), -1):
            rule = rule_for("unused")
            rule["pre_seconds"] = value
            with self.assertRaises(ValueError):
                validate_rule(rule)
        with self.assertRaises(ValueError):
            validate_rule({"stages": []})


class IndependentCommandTests(unittest.TestCase):
    def test_exit_stops_primary_before_waiting_for_secondary_encoder(self):
        import ast
        source = ast.parse((SERIAL / "Window.py").read_text(encoding="utf-8-sig"))
        app_class = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "PokeControllerApp")
        method = next(n for n in app_class.body if isinstance(n, ast.FunctionDef) and n.name == "exit")
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "exit-test", "exec"), namespace)
        actions = []
        app = types.SimpleNamespace(companion_pane=types.SimpleNamespace(
            close=lambda: actions.append("secondary-stop")), recorder=types.SimpleNamespace(active=True),
            toggle_recording=lambda: actions.append("primary-stop"), root=mock.Mock(),
            cur_command=types.SimpleNamespace(thread=types.SimpleNamespace(is_alive=lambda: True)),
            stopPlay=lambda: actions.append("primary-command-stop"))
        namespace["exit"](app)
        self.assertEqual(actions, ["primary-command-stop", "primary-stop", "secondary-stop"])

    def test_second_protocol_is_not_changed_by_primary_settings(self):
        from Commands.Keys import KeyPress
        primary = KeyPress(types.SimpleNamespace())
        secondary = KeyPress(types.SimpleNamespace(serial_data_format_name="Default"))
        with mock.patch.object(KeyPress, "serial_data_format_name", "Qingpi"):
            self.assertEqual(primary.serial_data_format_name, "Qingpi")
            self.assertEqual(secondary.serial_data_format_name, "Default")

    def test_outputs_and_pause_are_instance_local(self):
        from Commands.CommandBase import Command
        from CompanionPane import bind_companion_command
        first, second = Command(), Command()
        first.NAME = second.NAME = "test"
        primary, secondary = [], []
        with mock.patch.object(Command, "output", staticmethod(lambda *args, **kwargs: primary.append(kwargs.get("text")))):
            bind_companion_command(second, object(), object(),
                lambda *args, **kwargs: secondary.append(kwargs.get("text")), lambda *args: None)
            first.show_output("Analysis", text="one")
            second.show_output("Analysis", text="two")
            with mock.patch.object(Command, "isPause", True):
                self.assertTrue(first.isPause)
                self.assertFalse(second.isPause)
        self.assertEqual(primary, ["one"])
        self.assertEqual(secondary, ["two"])

    def test_saved_identity_never_falls_back_to_numeric_id(self):
        from CompanionPane import resolve_companion_camera
        with self.assertRaises(ValueError):
            resolve_companion_camera({"camera_id": 2, "device_path": "old-device"}, {2: "other-device"})
        self.assertEqual(resolve_companion_camera({"device_path": "physical-A"}, {5: "name physical-A"}), 5)

    def test_second_device_visible_to_other_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ActiveInputSetRegistry(os.path.join(directory, "registry.json"))
            key = canonical_device_key("camera", "physical-A")
            registry.set_device("camera_secondary", key, "second")
            self.assertEqual(len(device_usage_conflicts(registry.entries(include_self=True), "camera", key)), 1)
            registry.close()


class ClipMediaTests(unittest.TestCase):
    def test_real_av_cut_preserves_size_rate_and_relative_audio_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = root / "session"
            session.mkdir()
            template = np.random.default_rng(3).integers(0, 255, (12, 12, 3), dtype=np.uint8)
            template_path = root / "marker.png"
            cv2.imwrite(str(template_path), template)
            video = session / "source.avi"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 64))
            for frame_no in range(90):
                frame = np.zeros((64, 64, 3), np.uint8)
                if 30 <= frame_no < 45:
                    frame[8:20, 8:20] = template
                writer.write(frame)
            writer.release()
            import wave
            rate = 48000
            samples = np.zeros(rate * 3, np.int16)
            t = np.arange(2400) / rate
            samples[rate:rate+2400] = (np.sin(2*np.pi*1000*t)*20000).astype(np.int16)
            audio = session / "audio.wav"
            with wave.open(str(audio), "wb") as stream:
                stream.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                stream.writeframes(samples.tobytes())
            mp4 = session / "recording.mp4"
            _run_ffmpeg(["-y", "-i", str(video), "-i", str(audio), "-c:v", "libx264", "-threads", "1",
                         "-c:a", "aac", "-shortest", str(mp4)], threading.Event())
            rule = snapshot_rule(rule_for(template_path), root)
            rule["stages"][0]["targets"][0]["variants"][0]["threshold"] = .8
            rule["stages"][0]["targets"][0]["variants"][0]["use_gray"] = True
            result = export_event_clips(mp4, rule, root / "separate-drive-folder")
            self.assertTrue(result["complete"])
            self.assertEqual(len(result["clips"]), 1)
            clip = result["clips"][0]
            capture = cv2.VideoCapture(clip["path"])
            self.assertEqual((capture.get(cv2.CAP_PROP_FRAME_WIDTH), capture.get(cv2.CAP_PROP_FRAME_HEIGHT)), (64, 64))
            self.assertEqual(capture.get(cv2.CAP_PROP_FPS), 30)
            capture.release()
            decoded = root / "cut.wav"
            _run_ffmpeg(["-y", "-i", clip["path"], "-vn", "-ac", "1", "-ar", str(rate), str(decoded)], threading.Event())
            with wave.open(str(decoded), "rb") as stream:
                signal = np.frombuffer(stream.readframes(stream.getnframes()), np.int16)
            audible = np.flatnonzero(np.abs(signal.astype(float)) > 5000)
            self.assertAlmostEqual(audible[0] / rate, 1 - clip["start_seconds"], delta=.025)
            cached = export_event_clips(mp4, rule, root / "separate-drive-folder")
            self.assertEqual(cached["clips"], result["clips"])
            self.assertEqual(cached["manifest"], result["manifest"])
            failing_destination = root / "failed"
            def failed_encoder(arguments, cancel):
                Path(arguments[-1]).write_bytes(b"partial output")
                raise RuntimeError("cancelled")
            with mock.patch("EventClips._run_ffmpeg", side_effect=failed_encoder):
                with self.assertRaises(RuntimeError):
                    export_event_clips(mp4, rule, failing_destination)
            self.assertFalse(list(failing_destination.rglob("*.partial.mp4")))
            # Unrelated saved clips consume the configured budget but remain.
            full = root / "capacity"
            full.mkdir()
            sentinel = full / "keep.mp4"
            sentinel.write_bytes(b"0" * (11 * 1024 * 1024))
            limited = export_event_clips(mp4, rule, full)
            self.assertEqual(limited["clips"], [])
            self.assertEqual(len(limited["skipped_capacity"]), 1)
            self.assertEqual(sentinel.stat().st_size, 11 * 1024 * 1024)
            sentinel.unlink()
            resumed = export_event_clips(mp4, rule, full)
            self.assertEqual(len(resumed["clips"]), 1)
            self.assertEqual(resumed["skipped_capacity"], [])
            self.assertTrue(mp4.exists())

    def test_template_change_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.png"
            cv2.imwrite(str(path), np.random.default_rng(2).integers(0, 255, (8, 8, 3), dtype=np.uint8))
            rule = snapshot_rule(rule_for(path), directory)
            path.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                EventMatcher(rule)

    def test_upload_still_has_full_source_if_clip_drive_fails(self):
        from YouTubeArchive import prepare_event_clips_for_upload
        job = {"media_path": "whole.mp4", "event_clip_rule": {}, "delete_local_after_processing": True}
        with mock.patch("EventClips.export_event_clips", side_effect=OSError("drive missing")):
            result = prepare_event_clips_for_upload(job)
        self.assertEqual(job["media_path"], "whole.mp4")
        self.assertFalse(job["delete_local_after_processing"])
        self.assertIn("drive missing", result["error"])


class RegisteredConditionsTests(unittest.TestCase):
    def test_registered_three_of_four_and_template_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pattern.png"
            template = np.random.default_rng(8).integers(0, 255, (24, 24, 3), dtype=np.uint8)
            cv2.imwrite(str(path), template)
            rule = rule_for(path)
            target = rule["stages"][0]["targets"][0]
            target["operator"] = "AT_LEAST_3"
            positions = ((0, 0), (32, 0), (0, 32), (32, 32))
            target["variants"] = [{"template_path": str(path), "template_crop": [6, 6, 18, 18],
                "crop": [x, y, x+24, y+24], "threshold": .99, "use_gray": False}
                for x, y in positions]
            matcher = EventMatcher(snapshot_rule(rule, directory))
            frame = np.zeros((64, 64, 3), np.uint8)
            for x, y in positions[:2]:
                frame[y:y+12, x:x+12] = template[6:18, 6:18]
            self.assertEqual(matcher.matches(frame), [False])
            frame[32:44, 0:12] = template[6:18, 6:18]
            self.assertEqual(matcher.matches(frame), [True])
            matcher.rule["stages"][0]["targets"][0]["expected"] = False
            self.assertEqual(matcher.matches(frame), [False])
            frame[32:44, 0:12] = 0
            self.assertEqual(matcher.matches(frame), [True])

    def test_hard_preset_agrees_with_current_za_predicate_on_one_frame(self):
        import ast
        import itertools
        source = SERIAL / "Commands/PythonCommands/ZA/ZA_story/ZA_story.py"
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        names = ("ZA_story_Template_Field_HardGaurd", "ZA_no_battle_filed_check_HardGaurd")
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = {}
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), "exec"), namespace)
        library = json.loads((SERIAL / "Template/image_detection_profiles.json").read_text(encoding="utf-8"))
        targets = za_field_hard_targets(library)
        inputs = list(dict.fromkeys(name for target in targets for name in target["source_targets"]))
        # Frozen frame: the live helper's repeated checks see the same image.
        for flags in itertools.product((False, True), repeat=len(inputs)):
            values = dict(zip(inputs, flags))
            command = types.SimpleNamespace(image_check=lambda name: values.get(name, False))
            for name in names:
                setattr(command, name, types.MethodType(namespace[name], command))
            expected = command.ZA_no_battle_filed_check_HardGaurd()
            actual = all(any(values[name] for name in target["source_targets"]) == target["expected"]
                         for target in targets)
            self.assertEqual(actual, expected, values)

    def test_solid_color_is_not_a_match_everything_template(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "solid.png"
            color = np.zeros((12, 12, 3), np.uint8)
            color[:, :, 2] = 255
            cv2.imwrite(str(path), color)
            with self.assertRaisesRegex(ValueError, "単色"):
                EventMatcher(rule_for(path))


class ClipSettingsTests(unittest.TestCase):
    def test_save_preserves_newer_unrelated_settings_and_literal_path(self):
        from Settings import GuiSettings, create_settings_parser
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.ini"
            path.write_text("[Recording]\noutput_dir=D:/whole\n[Other]\nvalue=newer\n", encoding="utf-8")
            settings = GuiSettings.__new__(GuiSettings)
            settings.SETTING_PATH = str(path)
            settings.setting = create_settings_parser()
            settings.setting.read_dict({"Other": {"value": "stale"}})
            value = json.dumps({"output_dir": "E:/clips/100%/日本語", "max_total_gb": 25}, ensure_ascii=False)
            settings.save_event_clip_rule(value)
            actual = create_settings_parser()
            actual.read(path, encoding="utf-8")
            self.assertEqual(actual["Other"]["value"], "newer")
            self.assertEqual(actual["Recording"]["output_dir"], "D:/whole")
            self.assertEqual(actual["Recording"]["event_clip_rule"], value)


if __name__ == "__main__":
    unittest.main()
