"""Action prompt evidence tests: supplied frames and temporary files only."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import cv2
import numpy as np

sys.dont_write_bytecode = True
SERIAL_CONTROLLER = Path(__file__).resolve().parents[1] / "SerialController"
sys.path.insert(0, str(SERIAL_CONTROLLER))
from Commands.PythonCommands.LocalFunction import ActionPromptDebug as debug


class ActionPromptDebugTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        random = np.random.RandomState(507)
        self.frame = random.randint(0, 256, (80, 120, 3), dtype=np.uint8)
        self.template = self.frame[31:43, 42:58].copy()
        self.template_path = self.root / "参照.png"
        self.write_image(self.template_path, self.template)
        self.candidate = {"id": "in", "picture": "IN", "template_path": self.template_path.name,
                          "threshold": .9, "use_gray": True, "crop": [0, 0, 120, 80],
                          "source_provenance": {"catalog": "registered", "line": 10}}
        self.source_path = self.root / "command.py"
        self.source_text = '''class Command:
    def enter(self):
        return self.ZA_story_checked_movement_action(
            "enter_a", ("IN", "CHAT"), callback, "enter")
    def wait(self):
        self.ZA_story_wait_movement_a(("IN",))
        return self.image_check("CHAT")
    def again(self):
        return self.image_check("IN")
'''
        self.source_path.write_text(self.source_text, encoding="utf-8")
        self.source = {"source_path": str(self.source_path), "line": 1, "function": "enter",
                       "source_text": "runtime code before edits", "pictures": ["IN"],
                       "callsite_key": "enter_a", "step": "STEP_21", "context": ["STEP_21", "START"]}

    def write_image(self, path, array):
        ok, data = cv2.imencode(".png", array)
        self.assertTrue(ok)
        path.write_bytes(data.tobytes())

    def rank(self, candidates=None, **options):
        return debug.rank_action_prompt_candidates(
            self.frame, candidates or [self.candidate], template_root=self.root, **options)

    def save(self, **options):
        return debug.save_action_prompt_debug(
            self.frame, [self.candidate], self.source, self.root / "history",
            template_root=self.root, **options)

    def test_supplied_frame_ranking_has_position_and_exact_reference_score(self):
        bad = dict(self.candidate, id="bad", picture="OUT", template_path="different.png")
        self.write_image(self.root / "different.png", 255 - self.template)
        rows = self.rank([bad, self.candidate])
        self.assertEqual([row["id"] for row in rows], ["in", "bad"])
        self.assertGreater(rows[0]["score"], .999)
        self.assertTrue(rows[0]["matched"])
        self.assertEqual(rows[0]["position"], [42, 31])
        self.assertEqual(rows[0]["template_size"], [16, 12])
        self.assertLess(rows[1]["score"], .9)

    def test_ties_have_shared_rank_and_stable_ids(self):
        rows = self.rank([dict(self.candidate, id="z"), dict(self.candidate, id="a")])
        self.assertEqual([row["id"] for row in rows], ["a", "z"])
        self.assertEqual([row["rank"] for row in rows], [1, 1])

    def test_missing_corrupt_constant_and_invalid_threshold_are_error_rows_last(self):
        self.write_image(self.root / "flat.png", np.full((12, 16, 3), 40, np.uint8))
        (self.root / "corrupt.png").write_bytes(b"corrupt")
        candidates = [dict(self.candidate, id="missing", template_path="missing.png"),
                      dict(self.candidate, id="corrupt", template_path="corrupt.png"),
                      dict(self.candidate, id="flat", template_path="flat.png"),
                      dict(self.candidate, id="nan", threshold=float("nan")), self.candidate]
        rows = self.rank(candidates)
        self.assertEqual(rows[0]["id"], "in")
        self.assertEqual(len(rows), 5)
        for row in rows[1:]:
            self.assertEqual(row["status"], "error")
            self.assertIsNone(row["score"])
            self.assertIsNone(row["rank"])
            self.assertFalse(row["matched"])
            self.assertTrue(row["error"])
        json.dumps(rows, allow_nan=False)

    def test_nonfinite_and_out_of_range_match_scores_never_succeed(self):
        for value in (float("nan"), float("inf"), -2., 1.5):
            with self.subTest(value=value), mock.patch.object(
                    debug.cv2, "matchTemplate", return_value=np.array([[value]], np.float32)):
                row = self.rank()[0]
                self.assertIsNone(row["score"])
                self.assertFalse(row["matched"])
                self.assertIn("finite", row["error"])

    def test_common_roi_and_template_crop_are_used_without_scaling(self):
        candidate = dict(self.candidate, template_crop=[2, 2, 12, 10], crop=[0, 0, 10, 10])
        row = self.rank([candidate], comparison_crop=[35, 25, 70, 60])[0]
        self.assertTrue(row["matched"])
        self.assertEqual(row["position"], [44, 33])
        self.assertEqual(row["template_size"], [10, 8])
        self.assertEqual(row["comparison_crop"], [35, 25, 70, 60])

    def test_color_mask_matches_original_pixels_and_rejects_empty_mask(self):
        mask = np.zeros(self.template.shape[:2], np.uint8)
        mask[1:11, 1:15] = 255
        self.write_image(self.root / "mask.png", mask)
        row = self.rank([dict(self.candidate, use_gray=False, mask_path="mask.png")])[0]
        self.assertTrue(row["matched"])
        self.assertEqual(row["position"], [42, 31])
        mask[:] = 0
        self.write_image(self.root / "mask.png", mask)
        row = self.rank([dict(self.candidate, mask_path="mask.png")])[0]
        self.assertFalse(row["matched"])
        self.assertIsNone(row["score"])

    def test_save_preserves_original_bgr_frame_source_digest_and_runtime_line(self):
        original = self.frame.copy()
        result = self.save(comparison_crop=[20, 20, 90, 65], fallback_detail={"score": .97})
        folder = Path(result["event_dir"])
        actual = cv2.imdecode(np.frombuffer((folder / "frame.png").read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        np.testing.assert_array_equal(actual, original)
        np.testing.assert_array_equal(self.frame, original)
        record = json.loads((folder / "event.json").read_text(encoding="utf-8"))
        self.assertEqual(record["frame_shape"], [80, 120, 3])
        self.assertEqual(record["fallback_detail"]["score"], .97)
        self.assertEqual(record["source"]["runtime_line"], 1)
        self.assertEqual(record["source"]["disk_callsite"]["line"], 3)
        self.assertEqual(record["source"]["disk_callsite"]["line_delta_from_runtime"], 2)
        self.assertTrue(record["source"]["disk_callsite_unique"])
        self.assertEqual(record["source"]["disk_source_sha256"], hashlib.sha256(self.source_path.read_bytes()).hexdigest())
        self.assertEqual((folder / "source_snapshot.py").read_bytes(), self.source_path.read_bytes())

    def test_all_source_references_have_function_line_and_operation(self):
        result = self.save()
        usages = result["ranking"][0]["source_usages"]
        self.assertEqual([(entry["line"], entry["function"], entry["operation"]) for entry in usages],
                         [(4, "enter", "ZA_story_checked_movement_action"),
                          (6, "wait", "ZA_story_wait_movement_a"), (9, "again", "image_check")])
        self.assertTrue(all(entry["source_path"] == str(self.source_path.resolve()) for entry in usages))
        row = result["ranking"][0]
        self.assertEqual(row["source_provenance"], {"catalog": "registered", "line": 10})
        folder = Path(result["event_dir"])
        with (folder / "ranking.csv").open(encoding="utf-8-sig", newline="") as stream:
            csv_rows = list(csv.DictReader(stream))
        self.assertEqual(json.loads(csv_rows[0]["source_usages"]), usages)
        report = (folder / "report.html").read_text(encoding="utf-8")
        self.assertIn("ZA_story_checked_movement_action", report)
        self.assertIn("ranking.csv", report)

    def test_existing_events_and_indexes_are_only_appended(self):
        root = self.root / "history"
        root.mkdir()
        (root / "index.jsonl").write_bytes(b'{"legacy":true}\n')
        (root / "index.html").write_bytes(b"<h1>Existing history</h1>\n")
        (root / "do_not_remove.txt").write_text("retained", encoding="utf-8")
        first = self.save()
        frame_bytes = (Path(first["event_dir"]) / "frame.png").read_bytes()
        first_index = (root / "index.jsonl").read_bytes()
        first_html = (root / "index.html").read_bytes()
        second = self.save()
        self.assertNotEqual(first["event_dir"], second["event_dir"])
        self.assertTrue((root / "index.jsonl").read_bytes().startswith(first_index))
        self.assertTrue((root / "index.html").read_bytes().startswith(first_html))
        self.assertEqual((Path(first["event_dir"]) / "frame.png").read_bytes(), frame_bytes)
        self.assertEqual(len((root / "index.jsonl").read_text(encoding="utf-8").splitlines()), 3)
        self.assertEqual((root / "do_not_remove.txt").read_text(encoding="utf-8"), "retained")

    def test_ambiguous_callsite_is_not_reported_as_exact_disk_location(self):
        self.source_path.write_text(self.source_text.replace(
            'callback, "enter")', 'callback, "enter")\n        self.image_check("IN")'), encoding="utf-8")
        source = dict(self.source)
        source.pop("callsite_key")
        result = debug.save_action_prompt_debug(self.frame, [self.candidate], source,
                                               self.root / "history", template_root=self.root)
        self.assertFalse(result["source"]["disk_callsite_unique"])
        self.assertIsNone(result["source"]["disk_callsite"])
        self.assertEqual(len(result["source"]["disk_callsite_candidates"]), 2)

    def test_manual_target_source_references_are_listed_with_same_candidate(self):
        self.source_path.write_text(self.source_text + '\ndef manual(self):\n    return self.image_check("ZA_ACTION_PROMPT_IN")\n', encoding="utf-8")
        candidate = dict(self.candidate, manual_target="ZA_ACTION_PROMPT_IN")
        result = debug.save_action_prompt_debug(self.frame, [candidate], self.source,
                                               self.root / "history", template_root=self.root)
        usages = result["ranking"][0]["source_usages"]
        self.assertTrue(any(usage["function"] == "manual" and "ZA_ACTION_PROMPT_IN" in usage["source_text"]
                            for usage in usages))

    def test_missing_source_does_not_lose_saved_frame_or_rankings(self):
        self.source_path.unlink()
        result = self.save()
        self.assertIsNotNone(result["source"]["source_error"])
        self.assertTrue(result["ranking"][0]["matched"])
        self.assertTrue((Path(result["event_dir"]) / "frame.png").exists())

    def test_stop_callback_interrupts_candidate_loop_without_any_camera_read(self):
        class Stopped(Exception):
            pass
        calls = []
        def check():
            calls.append(1)
            if len(calls) == 2:
                raise Stopped()
        with mock.patch.object(debug.cv2, "VideoCapture", side_effect=AssertionError("camera read")) as camera:
            with self.assertRaises(Stopped):
                self.rank([self.candidate, self.candidate], check_alive=check)
            self.save()
            camera.assert_not_called()
        self.assertEqual(len(calls), 2)

    def test_python37_syntax_and_no_hardware_dependencies(self):
        source = Path(debug.__file__).read_text(encoding="utf-8")
        ast.parse(source, feature_version=(3, 7))
        self.assertNotIn("readFreshFrame", source)
        self.assertNotIn("read_command_frame", source)


if __name__ == "__main__":
    unittest.main()
