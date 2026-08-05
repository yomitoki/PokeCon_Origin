#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CommandsAssist recovery command example.

Copy this file in the same folder, rename the class/NAME, and implement only
the recovery operation.  Returning from do() is treated as normal completion;
PokeCon then starts the interrupted command again.
"""
from Commands.PythonCommandBase import PythonCommand


class RecoveryCommandSample(PythonCommand):
    NAME = "Recovery sample (no operation)"
    TAGS = ["@CommandsAssist"]

    def do(self):
        # Add recovery inputs here.  Long loops must call checkIfAlive().
        self.checkIfAlive()

