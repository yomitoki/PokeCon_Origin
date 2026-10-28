import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy


SERIAL_CONTROLLER = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "SerialController"))
if SERIAL_CONTROLLER not in sys.path:
    sys.path.insert(0, SERIAL_CONTROLLER)

from Recording import CaptureRecorder


class RecordingStartRecoveryTests(unittest.TestCase):
    def test_invalid_cleanup_setting_leaves_recorder_available_for_retry(self):
        frame = numpy.zeros((8, 12, 3), dtype=numpy.uint8)
        writer = mock.Mock()
        with tempfile.TemporaryDirectory() as folder:
            recorder = CaptureRecorder(folder, start_finalize_worker=False)
            recorder.defer_finalization = True
            with mock.patch.object(
                    recorder, "_open_video_writer",
                    return_value=(writer, "mp4v")) as open_writer:
                with self.assertRaises(ValueError):
                    recorder.start(
                        frame, 60, cleanup_rules=[], minimum_duration="bad")
                self.assertFalse(recorder.active)
                self.assertIsNone(recorder.video)
                open_writer.assert_not_called()

                recorder.start(frame, 60, cleanup_rules=[], minimum_duration=0)
                self.assertTrue(recorder.active)
                recorder.stop()

    def test_worker_start_failure_releases_writer_and_allows_retry(self):
        frame = numpy.zeros((8, 12, 3), dtype=numpy.uint8)
        failed_writer, next_writer = mock.Mock(), mock.Mock()
        with tempfile.TemporaryDirectory() as folder:
            recorder = CaptureRecorder(folder, start_finalize_worker=False)
            recorder.defer_finalization = True
            with mock.patch.object(
                    recorder, "_open_video_writer",
                    side_effect=[(failed_writer, "mp4v"),
                                 (next_writer, "mp4v")]):
                with mock.patch(
                        "Recording.threading.Thread.start",
                        side_effect=RuntimeError("cannot start worker")):
                    with self.assertRaisesRegex(
                            RuntimeError, "cannot start worker"):
                        recorder.start(frame, 60)
                self.assertFalse(recorder.active)
                self.assertIsNone(recorder.video)
                self.assertIsNone(recorder.writer_thread)
                self.assertIsNone(recorder.writer_stop)
                failed_writer.release.assert_called_once_with()

                recorder.start(frame, 60)
                self.assertTrue(recorder.active)
                recorder.stop()
                next_writer.release.assert_called_once_with()

    def test_initial_frame_copy_failure_does_not_open_video(self):
        frame = mock.Mock(shape=(8, 12, 3))
        frame.copy.side_effect = MemoryError("frame allocation failed")
        with tempfile.TemporaryDirectory() as folder:
            recorder = CaptureRecorder(folder, start_finalize_worker=False)
            with mock.patch.object(
                    recorder, "_open_video_writer",
                    return_value=(mock.Mock(), "mp4v")) as open_writer:
                with self.assertRaises(MemoryError):
                    recorder.start(frame, 60)
                self.assertFalse(recorder.active)
                self.assertIsNone(recorder.video)
                open_writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
