#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for the ZA_story stock-0.1.9 compatibility layer."""

import ast
import os
import sys
import unittest


REPOSITORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERIAL_CONTROLLER = os.path.join(REPOSITORY, "SerialController")
if SERIAL_CONTROLLER not in sys.path:
    sys.path.insert(0, SERIAL_CONTROLLER)

from LocalFunction.ImageDetection import read_command_frame  # noqa: E402


class _Command:
    def __init__(self, camera):
        self.camera = camera


class _Stock019Camera:
    def __init__(self, frame):
        self.frame = frame
        self.calls = 0

    def readFrame(self):
        self.calls += 1
        return self.frame


class _ExtendedCamera:
    def __init__(self, frame):
        self.frame = frame
        self.timeouts = []

    def readFreshFrame(self, timeout=None):
        self.timeouts.append(timeout)
        return self.frame


class _NoArgumentFreshCamera:
    def __init__(self, frame):
        self.frame = frame
        self.calls = 0

    def readFreshFrame(self):
        self.calls += 1
        return self.frame


class ZaGeneric019CompatibilityTests(unittest.TestCase):
    def test_stock_019_camera_uses_read_frame(self):
        frame = object()
        camera = _Stock019Camera(frame)

        self.assertIs(read_command_frame(_Command(camera)), frame)
        self.assertEqual(camera.calls, 1)

    def test_extended_camera_prefers_fresh_frame(self):
        frame = object()
        camera = _ExtendedCamera(frame)

        self.assertIs(
            read_command_frame(_Command(camera), timeout=0.25), frame)
        self.assertEqual(camera.timeouts, [0.25])

    def test_fresh_frame_without_timeout_argument_is_supported(self):
        frame = object()
        camera = _NoArgumentFreshCamera(frame)

        self.assertIs(read_command_frame(_Command(camera)), frame)
        self.assertEqual(camera.calls, 1)

    def test_za_story_keeps_core_compatibility_inside_copy_scope(self):
        source_path = os.path.join(
            SERIAL_CONTROLLER, "Commands", "PythonCommands", "ZA",
            "ZA_story", "ZA_story.py")
        with open(source_path, encoding="utf-8") as stream:
            tree = ast.parse(stream.read(), source_path)

        base = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ZA_story_Base")
        methods = {
            node.name for node in base.body if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("_read_camera_frame", methods)
        self.assertIn("show_output", methods)

        imported = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        self.assertFalse(any(
            name == "ThreadCancellation" or
            name.endswith(".ThreadCancellation")
            for name in imported))


if __name__ == "__main__":
    unittest.main()
