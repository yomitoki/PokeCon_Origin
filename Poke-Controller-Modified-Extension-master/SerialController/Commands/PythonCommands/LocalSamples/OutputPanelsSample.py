#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Othersタブで設定した出力枠へ、テキストと現在のカメラ画像を送る例。"""

from Commands.PythonCommandBase import ImageProcPythonCommand


class OutputPanelsSample(ImageProcPythonCommand):
    NAME = "Local: 出力枠 (ログ・画像・HTML) サンプル"

    def __init__(self, cam, gui=None):
        super().__init__(cam, gui)

    def do(self):
        frame = self.camera.readFrame()

        # Othersタブの "Log: Output#1" を選んだ枠へ表示します。
        self.show_output("Output#1", text="Output#1 に送ったログです。")

        # 位置を直接指定すると、左上枠へ画像を表示します。
        # image は OpenCV の BGR ndarray を渡します。
        self.show_output("left_top", image=frame, text="現在のキャプチャー画像")

        # HTMLは安全のため既定ブラウザで開きます。
        # self.show_output("right_bottom", html_path=r"C:\path\to\result.html")

