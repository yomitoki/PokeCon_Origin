#!/usr/bin/env python3
# Double-click launcher for Windows (uses the Python GUI file association).
import os
import runpy

runpy.run_path(os.path.join(os.path.dirname(__file__), "PokeConDevStudio.py"), run_name="__main__")
