#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, TYPE_CHECKING, Dict, Any

import cv2
import datetime
import mmap
import os
import platform
import struct
import subprocess
import threading
import time
import uuid
import numpy as np
from logging import getLogger, DEBUG, NullHandler

if TYPE_CHECKING:
    import numpy

# Windows環境の場合のみpygetwindow等を試行するためのインポート
if platform.system() == "Windows":
    try:
        import ctypes
        import ctypes.wintypes
        from ctypes import wintypes
    except ImportError:
        pass


if platform.system() == "Windows":
    class _RGBQUAD(ctypes.Structure):
        _fields_ = [("rgbBlue", ctypes.c_ubyte), ("rgbGreen", ctypes.c_ubyte),
                    ("rgbRed", ctypes.c_ubyte), ("rgbReserved", ctypes.c_ubyte)]


    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]


    class _BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", _BITMAPINFOHEADER),
                    ("bmiColors", _RGBQUAD * 1)]


def _capture_window_bgr(hwnd: int):
    """Capture a Win32 client area without opening any camera device."""
    if platform.system() != "Windows":
        raise RuntimeError("Window映像入力はWindowsでのみ使用できます。")
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, wintypes.HDC,
                             ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi32.BitBlt.restype = wintypes.BOOL
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                                wintypes.UINT, wintypes.LPVOID,
                                ctypes.POINTER(_BITMAPINFO), wintypes.UINT]
    gdi32.GetDIBits.restype = ctypes.c_int
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    hwnd = wintypes.HWND(int(hwnd))
    if not user32.IsWindow(hwnd):
        raise RuntimeError("選択したゲームウィンドウは終了しています。")
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("ゲームウィンドウの表示範囲を取得できません。")
    width, height = int(rect.right - rect.left), int(rect.bottom - rect.top)
    if width <= 0 or height <= 0:
        raise RuntimeError("ゲームウィンドウの表示サイズが0です。")

    window_dc = user32.GetDC(hwnd)
    if not window_dc:
        raise RuntimeError("ゲームウィンドウの描画領域を取得できません。")
    memory_dc = bitmap = old_bitmap = None
    try:
        memory_dc = gdi32.CreateCompatibleDC(window_dc)
        bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
        if not memory_dc or not bitmap:
            raise RuntimeError("ウィンドウ映像用バッファーを作成できません。")
        old_bitmap = gdi32.SelectObject(memory_dc, bitmap)
        # DirectX windows commonly return black from their own window DC.
        # For a visible window, copy the DWM-composited desktop pixels at the
        # client-area position instead. This does not open a camera device.
        SRCCOPY = 0x00CC0020
        if user32.IsIconic(hwnd):
            captured = bool(user32.PrintWindow(
                hwnd, memory_dc, 0x00000001 | 0x00000002))  # CLIENTONLY | RENDERFULLCONTENT
        else:
            origin = wintypes.POINT(0, 0)
            if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
                raise RuntimeError("ゲームウィンドウの画面位置を取得できません。")
            desktop_dc = user32.GetDC(None)
            if not desktop_dc:
                raise RuntimeError("デスクトップ映像を取得できません。")
            try:
                captured = bool(gdi32.BitBlt(
                    memory_dc, 0, 0, width, height, desktop_dc,
                    int(origin.x), int(origin.y), SRCCOPY))
            finally:
                user32.ReleaseDC(None, desktop_dc)
            if not captured:
                captured = bool(user32.PrintWindow(
                    hwnd, memory_dc, 0x00000001 | 0x00000002))
        if not captured:
            raise RuntimeError("ゲームウィンドウの映像を取得できません。")
        info = _BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # top-down pixels
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0  # BI_RGB
        frame = np.empty((height, width, 4), dtype=np.uint8)
        rows = gdi32.GetDIBits(
            memory_dc, bitmap, 0, height,
            frame.ctypes.data_as(ctypes.c_void_p), ctypes.byref(info), 0)
        if rows != height:
            raise RuntimeError("ゲームウィンドウの画素を取得できません。")
        bgr = np.ascontiguousarray(frame[:, :, :3])
        if user32.IsIconic(hwnd) and int(bgr.max()) == 0:
            raise RuntimeError(
                "最小化中のゲームが映像を提供していません。ゲーム画面を最小化解除してください。")
        return bgr
    finally:
        if old_bitmap and memory_dc:
            gdi32.SelectObject(memory_dc, old_bitmap)
        if bitmap:
            gdi32.DeleteObject(bitmap)
        if memory_dc:
            gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


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
_WINDOW_CAPTURE_MAPPING_SIZE = 64 * 1024 * 1024
_WINDOW_CAPTURE_DATA_OFFSET = 512
_WINDOW_CAPTURE_HEADER = struct.Struct("<16siiiiii")
_WINDOW_CAPTURE_MAGIC = "PKWGC01".encode("utf-16-le")


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
        self.window_hwnd = None
        self._window_capture_process = None
        self._window_capture_mapping = None
        self._window_capture_sequence = -1
        self._window_capture_error = ""
        self._window_reader_stop = None
        self._window_reader_thread = None
        self._window_raw_bgr = None
        self.window_capture_mode = "client"
        self.image_bgr = None
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
                user32.IsWindowVisible.argtypes = [wintypes.HWND]
                user32.IsWindowVisible.restype = wintypes.BOOL
                user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
                user32.GetWindowTextLengthW.restype = ctypes.c_int
                user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
                user32.GetWindowTextW.restype = ctypes.c_int
                user32.IsIconic.argtypes = [wintypes.HWND]
                user32.IsIconic.restype = wintypes.BOOL
                
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
                                    "hwnd": int(hwnd),
                                    "process_name": "Game/App",
                                    "process_path": "",
                                    "minimized": bool(user32.IsIconic(hwnd))
                                })
                    return True

                # HWND is pointer-sized. c_int truncates handles on 64-bit
                # Windows and later makes the selected window impossible to
                # capture even though its title remains visible in the GUI.
                EnumWindowsProc = ctypes.WINFUNCTYPE(
                    wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
                user32.EnumWindows.restype = wintypes.BOOL
                user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)
            except Exception as e:
                print(f"Error listing windows: {e}")
        return windows

    def openWindow(self, hwnd: int):
        """
        指定したウィンドウハンドル(hwnd)を開く/キャプチャ準備を行う。
        """
        self.destroy()
        if platform.system() != "Windows":
            raise RuntimeError("ゲームウィンドウ映像入力はWindowsでのみ使用できます。")
        helper_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "WindowCaptureHelper", "PokeConWindowCapture.exe")
        if not os.path.isfile(helper_path):
            raise RuntimeError(
                "ゲーム専用キャプチャーが見つかりません。"
                "WindowCaptureHelper/PokeConWindowCapture.exeを確認してください。")

        self._logger.debug(f"Opening game HWND with Windows Graphics Capture: {hwnd}")
        self.window_hwnd = int(hwnd)
        self.window_capture_backend = "Windows Graphics Capture (game window only)"
        mapping_name = "Local\\PokeConWGC_{}_{}".format(
            os.getpid(), uuid.uuid4().hex)
        try:
            # A minimized DirectX game generally stops publishing frames.
            # Restore it without activation; WGC can then keep capturing the
            # game surface even while PokeCon or another tool covers it.
            user32 = ctypes.windll.user32
            user32.IsIconic.argtypes = [wintypes.HWND]
            user32.IsIconic.restype = wintypes.BOOL
            user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.ShowWindowAsync.restype = wintypes.BOOL
            native_hwnd = wintypes.HWND(self.window_hwnd)
            if user32.IsIconic(native_hwnd):
                user32.ShowWindowAsync(native_hwnd, 4)  # SW_SHOWNOACTIVATE
                time.sleep(0.2)
            self._window_capture_mapping = mmap.mmap(
                -1, _WINDOW_CAPTURE_MAPPING_SIZE, tagname=mapping_name,
                access=mmap.ACCESS_WRITE)
            self._window_capture_mapping[0:_WINDOW_CAPTURE_DATA_OFFSET] = \
                b"\0" * _WINDOW_CAPTURE_DATA_OFFSET
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._window_capture_process = subprocess.Popen(
                [helper_path, str(self.window_hwnd), mapping_name, str(os.getpid())],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=creation_flags)

            # Catch startup failures here so Apply input shows a useful message
            # instead of leaving a black preview. A previously received frame
            # remains available if the game is minimized later.
            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                frame = self._read_window_frame()
                if frame is not None:
                    self._window_raw_bgr = frame
                    self.image_bgr = self._resize_window_frame(frame)
                    self._start_window_reader()
                    return True
                if self._window_capture_error:
                    raise RuntimeError(self._window_capture_error)
                if self._window_capture_process.poll() is not None:
                    raise RuntimeError("ゲーム専用キャプチャーが予期せず終了しました。")
                time.sleep(0.03)
            raise RuntimeError(
                "ゲーム映像を受信できません。ゲーム画面が最小化中の場合は、"
                "いったん最小化を解除してから「Apply input」を押してください。")
        except Exception:
            self.destroy()
            raise

    def _window_capture_header(self):
        mapping = self._window_capture_mapping
        if mapping is None:
            return None
        values = _WINDOW_CAPTURE_HEADER.unpack_from(mapping, 0)
        magic, sequence, status, width, height, stride, frame_bytes = values
        if magic[:len(_WINDOW_CAPTURE_MAGIC)] != _WINDOW_CAPTURE_MAGIC:
            return None
        return sequence, status, width, height, stride, frame_bytes

    def _read_window_error(self):
        mapping = self._window_capture_mapping
        if mapping is None:
            return ""
        raw = bytes(mapping[40:_WINDOW_CAPTURE_DATA_OFFSET])
        try:
            return raw.decode("utf-16-le", errors="ignore").split("\0", 1)[0].strip()
        except Exception:
            return ""

    def _read_window_frame(self):
        mapping = self._window_capture_mapping
        if mapping is None:
            return None
        for _attempt in range(3):
            header = self._window_capture_header()
            if header is None:
                return None
            sequence, status, width, height, stride, frame_bytes = header
            if status < 0:
                self._window_capture_error = self._read_window_error() or \
                    "ゲームウィンドウの取得が停止しました。"
                return None
            if status != 1 or sequence <= 0 or sequence % 2 or \
                    width <= 0 or height <= 0 or stride != width * 4:
                return None
            if sequence == self._window_capture_sequence:
                return None
            expected = stride * height
            if frame_bytes != expected or expected > \
                    _WINDOW_CAPTURE_MAPPING_SIZE - _WINDOW_CAPTURE_DATA_OFFSET:
                self._window_capture_error = "ゲーム映像のサイズが不正です。"
                return None
            raw = bytes(mapping[
                _WINDOW_CAPTURE_DATA_OFFSET:
                _WINDOW_CAPTURE_DATA_OFFSET + expected])
            confirm = self._window_capture_header()
            if confirm is None or confirm[0] != sequence or confirm[0] % 2:
                continue
            bgra = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 4))
            self._window_capture_sequence = sequence
            return np.ascontiguousarray(bgra[:, :, :3])
        return None

    def _resize_window_frame(self, frame):
        frame = self._crop_window_frame(frame)
        if frame.shape[1::-1] != self.capture_size:
            return cv2.resize(frame, self.capture_size, interpolation=cv2.INTER_AREA)
        return frame

    def setWindowCaptureMode(self, mode):
        """Switch between the game client area and the complete app window."""
        self.window_capture_mode = "window" if str(mode).lower() == "window" else "client"
        raw = self._window_raw_bgr
        if raw is not None:
            self.image_bgr = self._resize_window_frame(raw)

    def _crop_window_frame(self, frame):
        """Remove title/border pixels when game-client-only mode is selected."""
        if self.window_capture_mode == "window" or self.window_hwnd is None or \
                platform.system() != "Windows":
            return frame
        try:
            user32 = ctypes.windll.user32
            hwnd = wintypes.HWND(int(self.window_hwnd))
            client = wintypes.RECT()
            user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.GetClientRect.restype = wintypes.BOOL
            user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
            user32.ClientToScreen.restype = wintypes.BOOL
            user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.GetWindowRect.restype = wintypes.BOOL
            if not user32.GetClientRect(hwnd, ctypes.byref(client)):
                return frame
            top_left = wintypes.POINT(client.left, client.top)
            bottom_right = wintypes.POINT(client.right, client.bottom)
            if not user32.ClientToScreen(hwnd, ctypes.byref(top_left)) or not \
                    user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
                return frame

            outer = wintypes.RECT()
            got_outer = False
            try:
                dwmapi = ctypes.windll.dwmapi
                dwmapi.DwmGetWindowAttribute.argtypes = [
                    wintypes.HWND, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
                dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
                # Extended frame bounds exclude the invisible resize margin
                # and match the pixels supplied by Windows Graphics Capture.
                got_outer = dwmapi.DwmGetWindowAttribute(
                    hwnd, 9, ctypes.byref(outer), ctypes.sizeof(outer)) == 0
            except Exception:
                got_outer = False
            if not got_outer and not user32.GetWindowRect(hwnd, ctypes.byref(outer)):
                return frame

            outer_width = int(outer.right - outer.left)
            outer_height = int(outer.bottom - outer.top)
            client_width = int(bottom_right.x - top_left.x)
            client_height = int(bottom_right.y - top_left.y)
            frame_height, frame_width = frame.shape[:2]
            if min(outer_width, outer_height, client_width, client_height,
                   frame_width, frame_height) <= 0:
                return frame

            # Some applications already expose only their client surface to
            # WGC. Detect that before applying offsets a second time.
            outer_scale_x = frame_width / float(outer_width)
            outer_scale_y = frame_height / float(outer_height)
            client_scale_x = frame_width / float(client_width)
            client_scale_y = frame_height / float(client_height)
            outer_error = abs(outer_scale_x - outer_scale_y) / max(outer_scale_x, outer_scale_y)
            client_error = abs(client_scale_x - client_scale_y) / max(client_scale_x, client_scale_y)
            if client_error + 0.005 < outer_error:
                return frame

            x0 = int(round((top_left.x - outer.left) * outer_scale_x))
            y0 = int(round((top_left.y - outer.top) * outer_scale_y))
            x1 = int(round((bottom_right.x - outer.left) * outer_scale_x))
            y1 = int(round((bottom_right.y - outer.top) * outer_scale_y))
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(frame_width, x1), min(frame_height, y1)
            if x1 - x0 < 16 or y1 - y0 < 16:
                return frame
            return np.ascontiguousarray(frame[y0:y1, x0:x1])
        except Exception as error:
            self._logger.debug("Could not calculate game client crop: %s", error)
            return frame

    def _start_window_reader(self):
        stop_event = threading.Event()
        self._window_reader_stop = stop_event

        def read_latest_frames():
            while not stop_event.is_set():
                process = self._window_capture_process
                if process is None or process.poll() is not None:
                    break
                try:
                    frame = self._read_window_frame()
                    if frame is not None:
                        # Assign only after conversion is complete. Tk's read
                        # path therefore always sees a complete frame object.
                        self._window_raw_bgr = frame
                        self.image_bgr = self._resize_window_frame(frame)
                except Exception as error:
                    self._logger.warning("Game capture reader failed: %s", error)
                stop_event.wait(max(0.005, 1.0 / max(1, int(self.fps))))

        self._window_reader_thread = threading.Thread(
            target=read_latest_frames, daemon=True, name="GameWindowCapture")
        self._window_reader_thread.start()

    def openCamera(self, cameraId: int):
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
        if self.window_hwnd is not None and platform.system() == "Windows":
            process_alive = self._window_capture_process is not None and \
                self._window_capture_process.poll() is None
            return process_alive and bool(ctypes.windll.user32.IsWindow(
                wintypes.HWND(int(self.window_hwnd))))
        return self.camera is not None and self.camera.isOpened()

    def readFrame(self):
        if self.window_hwnd is not None:
            # Windows Graphics Capture runs in the helper and the frame-reader
            # thread. Keep the Tk capture callback non-blocking.
            return self.image_bgr
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
        if self._window_reader_stop is not None:
            self._window_reader_stop.set()
        if self._window_reader_thread is not None and \
                self._window_reader_thread is not threading.current_thread():
            self._window_reader_thread.join(timeout=0.5)
        self._window_reader_stop = None
        self._window_reader_thread = None
        if self.camera is not None:
            if self.camera.isOpened():
                self.camera.release()
            self.camera = None
        if self._window_capture_process is not None:
            try:
                if self._window_capture_process.poll() is None:
                    self._window_capture_process.terminate()
                    try:
                        self._window_capture_process.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        self._window_capture_process.kill()
            except Exception:
                pass
            self._window_capture_process = None
        if self._window_capture_mapping is not None:
            try:
                self._window_capture_mapping.close()
            except Exception:
                pass
            self._window_capture_mapping = None
        self.window_hwnd = None
        self._window_capture_sequence = -1
        self._window_capture_error = ""
        self._window_raw_bgr = None
        self.image_bgr = None
        self._logger.debug("Video input destroyed")
