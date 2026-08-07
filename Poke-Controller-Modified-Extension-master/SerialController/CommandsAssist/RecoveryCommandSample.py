#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CommandsAssist replacement command example.

Copy this file in the same folder, rename the class/NAME, and implement only
the replacement operation. Returning from do() is treated as normal completion;
PokeCon then resumes the interrupted command at its current Step checkpoint.
"""
from Commands.PythonCommandBase import PythonCommand


class RecoveryCommandSample(PythonCommand):
    NAME = "Recovery sample (no operation)"
    TAGS = ["@CommandsAssist"]

    def do(self):
        # Add replacement inputs here. Long loops must call checkIfAlive().
        self.checkIfAlive()
