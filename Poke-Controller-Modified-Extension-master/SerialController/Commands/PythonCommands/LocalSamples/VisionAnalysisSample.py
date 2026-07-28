#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vision_rules.json を使って敵HP色・HP数値などを出力する例。"""

import json
from Commands.PythonCommandBase import ImageProcPythonCommand
from VisionAutomation import VisionAutomation


class VisionAnalysisSample(ImageProcPythonCommand):
    NAME = "Local: HP / OCR 映像解析サンプル"

    def __init__(self, cam, gui=None):
        super().__init__(cam, gui)
        self.vision = VisionAutomation("Commands/PythonCommands/Samples/vision_rules.json")

    def do(self):
        self.vision.set_mode("battle")
        result = self.vision.analyse(self.camera.readFrame())

        # OCR結果・白赤HPバー判定はJSONとして表示されます。
        self.show_output("Analysis", text=result.to_json())
        self.show_output("right_top", text=json.dumps({
            "hp_colors": result.hp_colors,
            "ocr": result.text,
        }, ensure_ascii=False, indent=2))

