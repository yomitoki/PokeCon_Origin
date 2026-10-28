"""Local event clips remain independent, native-pixel image-check sources."""
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "SerialController"))
sys.path.insert(0, str(ROOT / "DevStudio"))
from EventClips import (CLIP_EXPORT_VERSION, EventMatcher, _run_ffmpeg,
                        export_event_clips, snapshot_rule)
from ImageDetectionLibrary import empty_library, save_library
from ImageDetectionMonitor import load_detection_library
from OperationSessionStudio import save_frame_capture, frame_capture_detection_row
from tests.test_capture_workspace_features import rule_for


def read_frames(path):
    capture = cv2.VideoCapture(str(path))
    frames = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                return frames
            frames.append(frame)
    finally:
        capture.release()


class EventClipRegistrationTests(unittest.TestCase):
    def test_native_pixels_and_registered_roi_survive_original_removal(self):
        # 4:4:4 catches accidental forced chroma reduction. Fractional FPS
        # and a changing background catch wrong-frame seeks or duplicated frames.
        for pixel_format, rate in (("yuv420p", "30"),
                                   ("yuv444p", "30000/1001"),
                                   ("yuv420p", "60000/1001")):
            with self.subTest(pixel_format=pixel_format, rate=rate):
                with tempfile.TemporaryDirectory() as directory:
                    self.check_round_trip(Path(directory), pixel_format, rate)

    def check_round_trip(self, root, pixel_format, rate):
        numerator, _, denominator = rate.partition("/")
        fps = float(numerator) / float(denominator or 1)
        session = root / "session"
        session.mkdir()
        raw = session / "source.avi"
        writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"FFV1"), fps, (64, 64))
        self.assertTrue(writer.isOpened())
        marker = np.random.default_rng(51).integers(0, 255, (12, 12, 3), dtype=np.uint8)
        background = np.random.default_rng(8).integers(0, 80, (64, 64, 3), dtype=np.uint8)
        first_positive = int(math.ceil(fps))
        try:
            for index in range(int(fps * 2)):
                frame = background + index % 120
                if first_positive <= index < first_positive + 8:
                    frame[8:20, 8:20] = marker
                writer.write(frame)
        finally:
            writer.release()
        marker_path = root / "marker.png"
        cv2.imencode(".png", marker)[1].tofile(str(marker_path))
        source = session / "recording.mp4"
        _run_ffmpeg(["-y", "-i", str(raw), "-c:v", "libx264", "-threads", "1",
                     "-crf", "18", "-pix_fmt", pixel_format, "-r", rate, str(source)], threading.Event())
        originals = read_frames(source)
        rule = rule_for(marker_path)
        rule["stages"][0]["targets"][0]["variants"][0].update(threshold=.75, use_gray=True)
        rule = snapshot_rule(rule, root)
        destination = root / "別ドライブ相当"

        # The old implementation would return this CRF-18 cache as complete.
        identity = (source.stat().st_size, source.stat().st_mtime_ns)
        legacy_key = hashlib.sha256((str(source.resolve()) + repr(identity)
                                    + json.dumps(rule, sort_keys=True)).encode()).hexdigest()[:20]
        legacy = destination / legacy_key / "events.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('{"complete":true,"clips":[]}', encoding="utf-8")
        legacy_bytes = legacy.read_bytes()
        result = export_event_clips(source, rule, destination)
        self.assertEqual(result["export_version"], CLIP_EXPORT_VERSION)
        self.assertEqual(result["video_encoding"], "h264_lossless")
        self.assertEqual(result["frame_size"], [64, 64])
        self.assertEqual(len(result["clips"]), 1)
        self.assertEqual(legacy.read_bytes(), legacy_bytes)
        clip = result["clips"][0]

        if pixel_format == "yuv444p":
            failed = root / "unexpected-downsampling"
            def downsample(arguments, cancel):
                return _run_ffmpeg(arguments[:-1] + ["-pix_fmt", "yuv420p", arguments[-1]], cancel)
            with mock.patch("EventClips._run_ffmpeg", side_effect=downsample):
                with self.assertRaisesRegex(RuntimeError, "色形式"):
                    export_event_clips(source, rule, failed)
            self.assertTrue(source.is_file())
            self.assertFalse(list(failed.rglob("*.mp4")))

        # The retained clip is the only video needed for subsequent extraction.
        source.unlink()
        raw.unlink()
        local_frames = read_frames(clip["path"])
        self.assertGreater(len(local_frames), 10)
        original_hashes = [hashlib.sha256(frame.tobytes()).digest() for frame in originals]
        local_hashes = [hashlib.sha256(frame.tobytes()).digest() for frame in local_frames]
        # Lossy source encoding can make neighbouring source frames identical;
        # match the whole sequence rather than assuming each hash is unique.
        offsets = [index for index in range(len(originals) - len(local_frames) + 1)
                   if original_hashes[index:index + len(local_frames)] == local_hashes]
        self.assertTrue(offsets, "The local clip differs from the source-frame sequence")
        indices = list(range(offsets[0], offsets[0] + len(local_frames)))
        self.assertAlmostEqual(indices[0] / fps, clip["start_seconds"], delta=1 / fps)
        self.assertAlmostEqual((indices[-1] + 1) / fps, clip["end_seconds"], delta=1 / fps)
        local_index = indices.index(first_positive + 2)
        full_frame = local_frames[local_index]
        crop = [8, 8, 20, 20]
        metadata = save_frame_capture(
            full_frame, crop, str(root / "registration"), {"session_id": "event-clip"},
            local_index / fps, "LOCAL_EVENT", image_root=str(root / "Template"),
            threshold=.999, use_gray=False,
            extra_metadata={"source_video": clip["path"]})
        png = cv2.imdecode(np.fromfile(metadata["template_path"], np.uint8), cv2.IMREAD_COLOR)
        np.testing.assert_array_equal(png, originals[first_positive + 2][8:20, 8:20])
        self.assertEqual(metadata["source_frame_size"], [64, 64])
        row = frame_capture_detection_row(metadata)
        library = empty_library()
        library["targets"][row["name"]] = {"operator": "OR", "variants": [row["variant_settings"]]}
        catalog = root / "Template" / "image_detection_profiles.json"
        save_library(str(catalog), library)
        loaded = load_detection_library(str(catalog))
        registered = snapshot_rule({"stages": [{"targets": [loaded["targets"]["LOCAL_EVENT"]]}]}, root)
        matcher = EventMatcher(registered)
        self.assertEqual(matcher.matches(originals[first_positive + 2]), [True])
        self.assertEqual(matcher.matches(full_frame), [True])
        self.assertEqual(matcher.matches(originals[0]), [False])
        shifted = np.roll(full_frame, 20, axis=1)
        self.assertEqual(matcher.matches(shifted), [False])


if __name__ == "__main__":
    unittest.main()
