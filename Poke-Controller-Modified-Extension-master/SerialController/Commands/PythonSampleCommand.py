#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base class for executable commands authored from Dev Studio sample lists."""
from Commands.PythonCommandBase import PythonCommand


class PythonSampleCommand(PythonCommand):
    SAMPLE_LIST = ""
    INCLUDED_SAMPLES = []

    def __init__(self, camera=None, gui=None):
        super(PythonSampleCommand, self).__init__()
        self.camera = camera
        self.gui = gui
