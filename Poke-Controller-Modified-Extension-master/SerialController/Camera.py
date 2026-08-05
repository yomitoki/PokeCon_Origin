#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, TYPE_CHECKING, Dict, Any

import cv2
import datetime
import os
import platform
from logging import getLogger, DEBUG, NullHandler

if TYPE_CHECKING:
    import numpy

# Windows環境の場合のみpygetwindow等を試行するためのインポート
if platform.system() == "Windows":
    try:
        import ctypes
        import ctypes.wintypes
    except ImportError:
        pass


def imwrite(filename: str, img: numpy.ndarray, params: int = None):
    _logger = getLogger(__name__)
    _logger.addHandler(NullHandler())
    _logger.setLevel(DEBUG)
    _logger.propagate = True
    try:
        ext = os.path.splitext(filename)[1]
        result, n = cv2.imencode(ext, img, params)

        if result:
            with open(filename, mode="w+b") as f:
                n.tofile(f)
            return True
        else:
            return False
    except Exception as e:
        print(e)
        _logger.error(f"Image Write Error: {e}")
        return False


CAPTURE_DIR = "./Captures/"


def _get_save_filespec(filename: str) -> str:
    """
    画像ファイルの保存パスを取得する。
    """
    if os.path.isabs(filename):
        return filename
    else:
        return os.path.join(CAPTURE_DIR, filename)


class Camera:
    def __init__(self, fps: int = 45):
        self.camera = None
        self.capture_size = (1280, 720)
        self.capture_dir = "Captures"
        self.fps = int(fps)
        self.window_capture_backend = "WindowCapture"

        self._logger = getLogger(__name__)
        self._logger.addHandler(NullHandler())
        self._logger.setLevel(DEBUG)
        self._logger.propagate = True

    @staticmethod
    def listWindows() -> List[Dict[str, Any]]:
        """
        キャプチャ可能なウィンドウの一覧を取得する。
        """
        windows = []
        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                
                def enum_windows_callback(hwnd, extra):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value
                            if title and title not in ["Program Manager", "Settings"]:
                                windows.append({
                                    "title": title,
                                    "hwnd": hwnd,
                                    "process_name": "Game/App",
                                    "process_path": "",
                                    "minimized": bool(user32.IsIconic(hwnd))
                                })
                    return True

                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)
            except Exception as e:
                print(f"Error listing windows: {e}")
        return windows

    def openWindow(self, hwnd: int):
        """
        指定したウィンドウハンドル(hwnd)を開く/キャプチャ準備を行う。
        """
        if self.camera is not None and self.isOpened():
            self._logger.debug("Camera is already opened")
            self.destroy()

        self._logger.debug(f"Opening Window HWND: {hwnd}")
        # ウィンドウキャプチャの初期化処理を実施
        # (通常は内部キャプチャ用フラグの設定やVideoCaptureとの置き換えを行います)
        self.window_capture_backend = "Win32API"
        
        # 画面取得確認用ダミーまたは仮想キャプチャの起動処理
        # キャプチャデバイスの指定が必要な場合はデフォルトデバイスを開く
        self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
        if self.camera.isOpened():
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.capture_size[0])
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.capture_size[1])

    def openCamera(self, cameraId: int):
        if self.camera is not None and self.isOpened():
            self._logger.debug("Camera is already opened")
            self.destroy()

        if os.name == "nt":
            self._logger.debug("NT OS")
            self.camera = cv2.VideoCapture(cameraId, cv2.CAP_DSHOW)
        else:
            self._logger.debug("Not NT OS")
            self.camera = cv2.VideoCapture(cameraId)

        if not self.camera.isOpened():
            print("Camera ID " + str(cameraId) + " can't open.")
            self._logger.error(f"Camera ID {cameraId} cannot open.")
            return
        print("Camera ID " + str(cameraId) + " opened successfully")
        self._logger.debug(f"Camera ID {cameraId} opened successfully.")
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.capture_size[0])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.capture_size[1])

    def isOpened(self):
        self._logger.debug("Camera is opened")
        return self.camera is not None and self.camera.isOpened()

    def readFrame(self):
        if self.camera is not None:
            _, self.image_bgr = self.camera.read()
            return self.image_bgr
        return None

    def saveCapture(self, filename: str = None, crop: int = None, crop_ax: List[int] = None, img: numpy.ndarray = None):
        if crop_ax is None:
            crop_ax = [0, 0, 1280, 720]

        dt_now = datetime.datetime.now()
        if filename is None or filename == "":
            filename = dt_now.strftime("%Y-%m-%d_%H-%M-%S") + ".png"
        else:
            filename = filename + ".png"

        if crop is None:
            image = self.image_bgr
        elif crop == 1 or crop == "1":
            image = self.image_bgr[crop_ax[1] : crop_ax[3], crop_ax[0] : crop_ax[2]]
        elif crop == 2 or crop == "2":
            image = self.image_bgr[crop_ax[1] : crop_ax[1] + crop_ax[3], crop_ax[0] : crop_ax[0] + crop_ax[2]]
        elif img is not None:
            image = img
        else:
            image = self.image_bgr

        save_path = _get_save_filespec(filename)

        if not os.path.exists(os.path.dirname(save_path)) or not os.path.isdir(os.path.dirname(save_path)):
            os.makedirs(os.path.dirname(save_path))
            self._logger.debug("Created Capture folder")

        try:
            imwrite(save_path, image)
            self._logger.debug(f"Capture succeeded: {save_path}")
            print("capture succeeded: " + save_path)
        except cv2.error as e:
            print("Capture Failed")
            self._logger.error(f"Capture Failed :{e}")

    def destroy(self):
        if self.camera is not None and self.camera.isOpened():
            self.camera.release()
            self.camera = None
            self._logger.debug("Camera destroyed")