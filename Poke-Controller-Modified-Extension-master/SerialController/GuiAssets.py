#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
# from typing import Tuple

import cv2
import os
import time
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import numpy as np
import datetime
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from tkinter import filedialog

from PIL import Image, ImageTk

from Commands import UnitCommand

# from Commands import StickCommand
from Commands.Keys import Direction, Stick, Touchscreen, NEUTRAL, KeyPress

import logging
from logging import StreamHandler, getLogger, DEBUG, NullHandler
from Commands.PythonCommandBase import PythonCommand
from UiResponsiveness import (compensated_after_delay,
                              foreground_process_matches,
                              preview_capture_interval, preview_priority,
                              preview_render_due, preview_render_interval,
                              resize_safe_preview_intervals)

if os.name == "nt":
    try:
        import ctypes
        from ctypes import wintypes
    except (ImportError, OSError):
        ctypes = None
        wintypes = None
else:
    ctypes = None
    wintypes = None

try:
    os.makedirs("log")
except FileExistsError:
    pass

isTakeLog = False
# logger_stick = getLogger(__name__)
nowtime = datetime.datetime.fromtimestamp(time.time()).strftime("%Y%m%d_%H%M%S")


def prepare_preview_image(image_bgr, show_size):
    """Convert/resize a BGR frame without touching Tk.

    This function is intentionally safe to run on a worker thread. At 720p,
    BGR conversion plus Pillow's array copy can consume most of a 60-FPS Tk
    callback by itself.
    """
    if image_bgr is None:
        return None
    frame = image_bgr if image_bgr.flags.c_contiguous \
        else np.ascontiguousarray(image_bgr)
    height, width = frame.shape[:2]
    image_pil = Image.frombuffer(
        "RGB", (width, height), frame, "raw", "BGR", 0, 1)
    size = (max(1, int(show_size[0])), max(1, int(show_size[1])))
    if image_pil.size != size:
        image_pil = image_pil.resize(size)
    return image_pil


def prepare_disabled_preview_image(image_pil, show_size):
    """Return a placeholder which covers the complete preview surface."""
    size = (max(1, int(show_size[0])), max(1, int(show_size[1])))
    if image_pil is None:
        return Image.new("RGB", size, "black")
    if image_pil.size != size:
        return image_pil.resize(size)
    return image_pil.copy()


def hold_last_preview_on_missing_frame(displaying_live_preview,
                                       missing_since, now,
                                       grace_seconds=3.0):
    """Keep a valid frame visible during a short input hand-off.

    Camera/Window switching intentionally clears the shared frame before the
    replacement DirectShow/WGC source publishes its first image.  Showing the
    placeholder during that normal gap creates a visible ``No Image`` flash.
    """
    if not displaying_live_preview:
        return False
    if missing_since is None:
        return True
    return float(now) - float(missing_since) < max(0.0, float(grace_seconds))


if ctypes is not None:
    class _BitmapInfoHeader(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]


    class _BitmapInfo(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", _BitmapInfoHeader),
            ("bmiColors", wintypes.DWORD * 3),
        ]


class WindowsCanvasPreview:
    """Draw BGR frames straight to a Tk Canvas HWND using Windows GDI."""

    DIB_RGB_COLORS = 0
    SRCCOPY = 0x00CC0020
    BLACKNESS = 0x00000042

    def __init__(self, widget):
        if ctypes is None:
            raise RuntimeError("Windows GDI preview is unavailable")
        self.widget = widget
        self.hwnd = int(widget.winfo_id())
        self._draw_lock = threading.Lock()
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.user32.GetDC.argtypes = [wintypes.HWND]
        self.user32.GetDC.restype = wintypes.HDC
        self.user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        self.user32.ReleaseDC.restype = ctypes.c_int
        self._bitmap_info = None
        self._source_size = None
        self.gdi32.StretchDIBits.argtypes = [
            wintypes.HDC,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT, wintypes.DWORD,
        ]
        self.gdi32.StretchDIBits.restype = ctypes.c_int
        self.gdi32.PatBlt.argtypes = [
            wintypes.HDC,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.DWORD,
        ]
        self.gdi32.PatBlt.restype = wintypes.BOOL

    def _info_for(self, width, height):
        size = (int(width), int(height))
        if self._source_size == size and self._bitmap_info is not None:
            return self._bitmap_info
        info = _BitmapInfo()
        info.bmiHeader.biSize = ctypes.sizeof(_BitmapInfoHeader)
        info.bmiHeader.biWidth = size[0]
        # A negative height declares a normal top-down image.
        info.bmiHeader.biHeight = -size[1]
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 24
        info.bmiHeader.biCompression = 0
        self._source_size = size
        self._bitmap_info = info
        return info

    def draw(self, image_bgr, destination_size):
        if image_bgr is None or getattr(image_bgr, "ndim", 0) != 3 \
                or image_bgr.shape[2] != 3 or not image_bgr.flags.c_contiguous:
            return False
        source_height, source_width = image_bgr.shape[:2]
        # A 24-bit DIB scanline is DWORD-aligned. Standard PokeCon capture
        # widths (1280/1920) already satisfy this; unusual widths use Pillow.
        if (source_width * 3) % 4:
            return False
        destination_width = max(1, int(destination_size[0]))
        destination_height = max(1, int(destination_size[1]))
        hwnd = self.hwnd
        hdc = self.user32.GetDC(hwnd)
        if not hdc:
            return False
        try:
            with self._draw_lock:
                info = self._info_for(source_width, source_height)
                result = self.gdi32.StretchDIBits(
                    hdc,
                    0, 0, destination_width, destination_height,
                    0, 0, source_width, source_height,
                    ctypes.c_void_p(int(image_bgr.ctypes.data)),
                    ctypes.byref(info), self.DIB_RGB_COLORS, self.SRCCOPY)
                return result not in (0, -1)
        finally:
            self.user32.ReleaseDC(hwnd, hdc)

    def clear(self, destination_size):
        """Erase all pixels previously written outside Tk's paint cycle."""
        requested_width = max(1, int(destination_size[0]))
        requested_height = max(1, int(destination_size[1]))
        try:
            width = max(requested_width, int(self.widget.winfo_width()))
            height = max(requested_height, int(self.widget.winfo_height()))
        except (AttributeError, tk.TclError):
            width, height = requested_width, requested_height
        hwnd = self.hwnd
        hdc = self.user32.GetDC(hwnd)
        if not hdc:
            return False
        try:
            with self._draw_lock:
                return bool(self.gdi32.PatBlt(
                    hdc, 0, 0, width, height, self.BLACKNESS))
        finally:
            self.user32.ReleaseDC(hwnd, hdc)


class MouseStick(PythonCommand):
    NAME = "MOUSEスティック"

    def __init__(self):
        super().__init__()
        self._logger = getLogger(__name__)
        self._logger.addHandler(NullHandler())
        self._logger.setLevel(DEBUG)
        self._logger.propagate = True

    def do(self):
        pass

    def stick(self, buttons, duration=0.1, wait=0.1):
        self.keys.input(buttons, ifPrint=False)
        self.wait(duration)
        self.wait(wait)

    # press button at duration times(s)
    def stickEnd(self, buttons):
        self.keys.inputEnd(buttons)


class CaptureArea(tk.Canvas):
    def __init__(
        self, camera, fps, right_mouse_mode, is_show, ser: KeyPress, master=None, show_width=640, show_height=360
    ):
        super().__init__(
            master, borderwidth=0, highlightthickness=0,
            background="black", cursor="tcross",
            width=show_width, height=show_height)

        self._logger = getLogger(__name__)
        self._logger.addHandler(NullHandler())
        self._logger.setLevel(DEBUG)
        self._logger.propagate = True

        self.master = master
        self.radius = 60  # 描画する円の半径
        self.camera = camera
        # self.show_size = (640, 360)
        self.show_width = int(show_width)
        self.show_height = int(show_height)
        self.show_size = (self.show_width, self.show_height)
        self.is_show_var = is_show
        self.lx_init, self.ly_init = 0, 0
        self.rx_init, self.ry_init = 0, 0
        self.min_x, self.min_y = 0, 0
        self.max_x, self.max_y = 0, 0
        self.keys = None
        self.ser = ser
        self.lcircle = None
        self.lcircle2 = None
        self.rcircle = None
        self.rcircle2 = None
        self.LStick = None
        self.RStick = None
        self.calc_time = None
        self.ss = None
        self.dq = None
        self._langle = None
        self._lmag = None
        self._rangle = None
        self._rmag = None
        self.RightMouseMode = "Default"
        self.touchscreen_start_x = 1
        self.touchscreen_start_y = 1
        self.touchscreen_end_x = 320
        self.touchscreen_end_y = 240
        # Called with a BGR crop and its source coordinates.  Keeping this in
        # the preview makes the feature available to every Python command too.
        self.region_listener = None
        self.frame_listener = None
        self.frame_work_provider = None
        self.record_listener = None
        self.presentation_listener = None
        self.render_priority_provider = None
        self.capture_work_provider = None
        self.resource_multiplier_provider = None
        self._last_listener_time = 0.0
        self._last_preview_render_time = 0.0
        self._last_rendered_frame_sequence = -1
        self._measured_preview_fps = 0.0
        self._preview_fps_measure_started = 0.0
        self._preview_fps_measure_frames = 0
        self._last_preview_frame_at = 0.0
        self._last_submitted_frame_sequence = -1
        self._last_consumed_frame_sequence = -1
        self._layout_busy_until = 0.0
        self._ui_interaction_busy_until = 0.0
        self._capture_high_precision_requested = False
        self._preview_prepare_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="PokeConPreview")
        self._preview_prepare_future = None
        self._live_preview_tk = None
        self._live_preview_size = None
        self._displaying_live_preview = False
        self._missing_frame_started_at = None
        self._native_preview = None
        self._native_preview_active = False
        self._native_render_mode_lock = threading.Lock()
        self._native_render_enabled = False
        self._native_render_stop = threading.Event()
        self._native_render_wake = threading.Event()
        self._native_render_thread = None
        self._feature_limited = False
        if os.name == "nt" and ctypes is not None:
            try:
                self._native_preview = WindowsCanvasPreview(self)
            except (AttributeError, OSError, RuntimeError):
                self._native_preview = None
        self._requested_fps = 30
        self._last_lstick_send = 0.0
        self._last_rstick_send = 0.0
        self._last_lstick_position = None
        self._last_rstick_position = None
        # A default serial packet is roughly 15-20 ms at 9600 bps.  Sending
        # every mouse-motion event builds a firmware/driver backlog.
        self._manual_stick_interval = 0.020

        self.stick_handler = StreamHandler()
        self.stick_logging_level = DEBUG
        self.stick_handler.setLevel(self.stick_logging_level)
        # self._logger.setLevel(self.stick_logging_level)
        # self._logger.addHandler(self.stick_handler)
        # self._logger.propagate = False
        if isTakeLog:
            filename_base = os.path.join("log", f"{nowtime}")
            self.LS = logging.FileHandler(filename=f"{filename_base}_LStick.log", encoding="utf-8")
            self.LS.setLevel(logging.DEBUG)
            self.LSTICK_logger = logging.getLogger("L_STICK")
            self.LSTICK_logger.setLevel(logging.DEBUG)
            self.LSTICK_logger.addHandler(self.LS)

            self.RS = logging.FileHandler(filename=f"{filename_base}_RStick.log", encoding="utf-8")
            self.RS.setLevel(logging.DEBUG)
            self.RSTICK_logger = logging.getLogger("R_STICK")
            self.RSTICK_logger.setLevel(logging.DEBUG)
            self.RSTICK_logger.addHandler(self.RS)
        # self.circle =

        self.setFps(fps)
        self.changeRightMouseMode(right_mouse_mode)

        self._bind_range_selection()

        # Set disabled image first
        disabled_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "Images", "disabled.png"))
        disabled_img = cv2.imread(disabled_path, cv2.IMREAD_GRAYSCALE)
        disabled_pil = Image.fromarray(disabled_img) \
            if disabled_img is not None else None
        self._disabled_source_pil = disabled_pil
        disabled_pil = prepare_disabled_preview_image(
            self._disabled_source_pil, self.show_size)
        self.disabled_tk = ImageTk.PhotoImage(disabled_pil, master=self)
        self.im = self.disabled_tk
        # self.configure(image=self.disabled_tk)  # labelからキャンバスに変更したので微修正
        self.im_ = self.create_image(0, 0, image=self.disabled_tk, anchor=tk.NW)
        # Windows sends a short burst of Configure events while maximizing or
        # dragging the outer frame. Rendering 720p PhotoImages at 60 FPS during
        # that burst can starve Tk's own resize messages.
        self.winfo_toplevel().bind(
            "<Configure>", self._note_layout_change, add="+")
        if self._native_preview is not None:
            self._native_render_thread = threading.Thread(
                target=self._native_render_loop,
                name="PokeConNativePreview", daemon=True)
            self._native_render_thread.start()

    def _note_layout_change(self, event=None):
        try:
            if event is not None and event.widget is not self.winfo_toplevel():
                return
        except tk.TclError:
            return
        # Wait for the outer window and its large notebook/panes to settle.
        # Camera readers and record listeners continue independently; only the
        # expensive Tk PhotoImage replacement is paused during this debounce.
        self._layout_busy_until = time.monotonic() + 0.8

    def prioritizeUiInteraction(self, seconds=0.45):
        """Temporarily yield PhotoImage work to tabs and other Tk controls."""
        try:
            seconds = max(0.05, float(seconds))
        except (TypeError, ValueError):
            seconds = 0.45
        self._ui_interaction_busy_until = max(
            self._ui_interaction_busy_until, time.monotonic() + seconds)

    def _bind_range_selection(self):
        self.bind("<Control-ButtonPress-1>", self.mouseCtrlLeftPress)
        self.bind("<Control-ButtonRelease-1>", self.mouseCtrlLeftRelease)
        self.bind("<Control-Shift-ButtonPress-1>", self.StartRangeSS)
        self.bind("<Control-Shift-Button1-Motion>", self.MotionRangeSS)
        self.bind("<Control-Shift-ButtonRelease-1>", self.ReleaseRangeSS)
        self.bind("<Control-Alt-ButtonPress-1>", self.StartRangeSS)
        self.bind("<Control-Alt-Button1-Motion>", self.MotionRangeSS)
        self.bind("<Control-Alt-ButtonRelease-1>", self.ReleaseRangeSS_asksaveasfilename)
        # Shift-drag is a persistent "send to output" selection. Ctrl+Shift
        # retains the existing behaviour (save a cropped capture).
        self.bind("<Shift-ButtonPress-1>", self.StartOutputRegion)
        self.bind("<Shift-Button1-Motion>", self.MotionRangeSS)
        self.bind("<Shift-ButtonRelease-1>", self.ReleaseOutputRegion)
        self.bind("<Control-ButtonPress-3>", self.StartRangeTouchscreen)
        self.bind("<Control-Button3-Motion>", self.MotionRangeTouchscreen)
        self.bind("<Control-ButtonRelease-3>", self.ReleaseRangeTouchscreen)

    def setFeatureLimited(self, limited):
        """Disable Tk video-range/overlay features for a lightweight InputSet."""
        self._feature_limited = bool(limited)
        range_events = (
            "<Control-ButtonPress-1>", "<Control-ButtonRelease-1>",
            "<Control-Shift-ButtonPress-1>", "<Control-Shift-Button1-Motion>",
            "<Control-Shift-ButtonRelease-1>", "<Control-Alt-ButtonPress-1>",
            "<Control-Alt-Button1-Motion>", "<Control-Alt-ButtonRelease-1>",
            "<Shift-ButtonPress-1>", "<Shift-Button1-Motion>",
            "<Shift-ButtonRelease-1>", "<Control-ButtonPress-3>",
            "<Control-Button3-Motion>", "<Control-ButtonRelease-3>",
        )
        if self._feature_limited:
            for sequence in range_events:
                self.unbind(sequence)
            for item in self.find_all():
                if item != self.im_:
                    self.delete(item)
        else:
            self._disable_threaded_native_preview(clear=False)
            self._bind_range_selection()

    def ApplyLStickMouse(self):
        if self.master.is_use_left_stick_mouse.get():
            self.BindLeftClick()
        else:
            self.UnbindLeftClick()

    def ApplyRStickMouse(self):
        if self.master.is_use_right_stick_mouse.get():
            self.BindRightClick()
        else:
            self.UnbindRightClick()

    def StartRangeSS(self, event):
        self.ss = self.camera.image_bgr
        if self.master.is_use_left_stick_mouse.get():
            self.UnbindLeftClick()
        if self.master.is_use_right_stick_mouse.get():
            self.UnbindRightClick()

        self.min_x, self.min_y = event.x, event.y
        self.delete("SelectArea")
        self.create_rectangle(
            self.min_x, self.min_y, self.min_x + 1, self.min_y + 1, width=3.0, outline="red", tag="SelectArea"
        )

        ratio_x = float(self.camera.capture_size[0] / self.show_size[0])
        ratio_y = float(self.camera.capture_size[1] / self.show_size[1])
        print(
            "Mouse down: Show ({}, {}) / Capture ({}, {})".format(
                self.min_x, self.min_y, int(self.min_x * ratio_x), int(self.min_y * ratio_y)
            )
        )
        self._logger.info(
            "Mouse down: Show ({}, {}) / Capture ({}, {})".format(
                self.min_x, self.min_y, int(self.min_x * ratio_x), int(self.min_y * ratio_y)
            )
        )

        if self.master.is_use_left_stick_mouse.get():
            self.BindLeftClick()
        if self.master.is_use_right_stick_mouse.get():
            self.BindRightClick()

    def set_region_listener(self, listener):
        """Set ``listener(image_bgr, (x, y, width, height))`` for Shift-drag."""
        self.region_listener = listener

    def set_frame_listener(self, listener):
        """Set a low-rate callback for live BGR frames (max. 4 calls/sec)."""
        self.frame_listener = listener

    def set_frame_work_provider(self, provider):
        """Set a callback indicating whether low-rate analysis needs frames."""
        self.frame_work_provider = provider

    def set_record_listener(self, listener):
        """Set a callback for every capture frame, before preview throttling."""
        self.record_listener = listener

    @staticmethod
    def _notify_capture_listener(preview, listener_name, image_bgr,
                                 copy_frame=False):
        """Keep one failed consumer from terminating the preview timer.

        Tk does not reschedule ``capture`` when an exception escapes its
        callback. Recording and analysis are optional consumers, so their
        failure must be reported without freezing the displayed image.
        """
        listener = getattr(preview, listener_name, None)
        if listener is None or image_bgr is None:
            return False
        try:
            listener(image_bgr.copy() if copy_frame else image_bgr)
            return True
        except Exception as error:
            now = time.monotonic()
            error_times = getattr(
                preview, "_capture_listener_error_times", None)
            if not isinstance(error_times, dict):
                error_times = {}
                preview._capture_listener_error_times = error_times
            # A failed listener can be called at 60 Hz. Keep the log useful
            # without turning the same failure into a new load source.
            if now - float(error_times.get(listener_name, 0.0)) >= 1.0:
                error_times[listener_name] = now
                logger = getattr(preview, "_logger", None)
                if logger is not None:
                    logger.warning(
                        "%s failed; preview capture will continue: %s",
                        listener_name, error)
            return False

    def set_presentation_listener(self, listener):
        """Observe frames after they were actually drawn in the preview."""
        self.presentation_listener = listener

    @staticmethod
    def _notify_presented_frame(preview, image_bgr, frame_sequence,
                                presented_at):
        listener = getattr(preview, "presentation_listener", None)
        if listener is None or image_bgr is None:
            return
        try:
            listener(image_bgr, frame_sequence, float(presented_at))
        except Exception as error:
            logger = getattr(preview, "_logger", None)
            if logger is not None:
                logger.warning("Preview presentation listener failed: %s", error)

    def set_render_priority_provider(self, provider):
        """Set a callback returning (last-active-PokeCon, allow-full-rate)."""
        self.render_priority_provider = provider

    def set_capture_work_provider(self, provider):
        """Set a callback which is true while recording needs every frame."""
        self.capture_work_provider = provider

    def set_resource_multiplier_provider(self, provider):
        """Provide a cooperative background-preview interval multiplier."""
        self.resource_multiplier_provider = provider

    def StartOutputRegion(self, event):
        self.min_x, self.min_y = event.x, event.y
        self.delete("OutputRegion")
        self.create_rectangle(event.x, event.y, event.x + 1, event.y + 1,
                              width=3, outline="red", tag="OutputRegion")

    def ReleaseOutputRegion(self, event):
        self.max_x = min(max(event.x, 0), self.show_width)
        self.max_y = min(max(event.y, 0), self.show_height)
        x1, x2 = sorted((self.min_x, self.max_x))
        y1, y2 = sorted((self.min_y, self.max_y))
        self.coords("OutputRegion", x1, y1, x2, y2)
        if not self.region_listener or not hasattr(self.camera, "image_bgr"):
            return
        ratio_x = self.camera.capture_size[0] / self.show_width
        ratio_y = self.camera.capture_size[1] / self.show_height
        sx, sy = int(x1 * ratio_x), int(y1 * ratio_y)
        ex, ey = int(x2 * ratio_x), int(y2 * ratio_y)
        image = self.camera.image_bgr[sy:ey, sx:ex].copy()
        if image.size:
            self.region_listener(image, (sx, sy, ex - sx, ey - sy))

    def MotionRangeSS(self, event):
        if event.x < 0:
            self.max_x = 0
        else:
            self.max_x = min(self.show_width, event.x)
        if event.y < 0:
            self.max_y = 0
        else:
            self.max_y = min(self.show_height, event.y)
        self.coords("SelectArea", self.min_x, self.min_y, self.max_x + 1, self.max_y + 1)
        self.coords("SelectAreaFilled", self.min_x, self.min_y, self.max_x + 1, self.max_y + 1)

    def ReleaseRangeSS(self, event):
        # self.max_x, self.max_y = event.x, event.y
        ratio_x = float(self.camera.capture_size[0] / self.show_size[0])
        ratio_y = float(self.camera.capture_size[1] / self.show_size[1])
        print(
            "Mouse up: Show ({}, {}) / Capture ({}, {})".format(
                self.max_x, self.max_y, int(self.max_x * ratio_x), int(self.max_y * ratio_y)
            )
        )
        self._logger.info(
            "Mouse up: Show ({}, {}) / Capture ({}, {})".format(
                self.max_x, self.max_y, int(self.max_x * ratio_x), int(self.max_y * ratio_y)
            )
        )
        if self.min_x > self.max_x:
            self.min_x, self.max_x = self.max_x, self.min_x
        if self.min_y > self.max_y:
            self.min_y, self.max_y = self.max_y, self.min_y

        self.camera.saveCapture(
            crop=1,
            crop_ax=[
                int(self.min_x * ratio_x),
                int(self.min_y * ratio_x),
                int(self.max_x * ratio_x),
                int(self.max_y * ratio_x),
            ],
        )

        # t = 0
        self.after(250, self.delete("SelectArea"))

        if self.master.is_use_left_stick_mouse.get():
            self.BindLeftClick()
        if self.master.is_use_right_stick_mouse.get():
            self.BindRightClick()

    def ReleaseRangeSS_asksaveasfilename(self, event):
        # self.max_x, self.max_y = event.x, event.y
        ratio_x = float(self.camera.capture_size[0] / self.show_size[0])
        ratio_y = float(self.camera.capture_size[1] / self.show_size[1])
        print(
            "Mouse up: Show ({}, {}) / Capture ({}, {})".format(
                self.max_x, self.max_y, int(self.max_x * ratio_x), int(self.max_y * ratio_y)
            )
        )
        self._logger.info(
            "Mouse up: Show ({}, {}) / Capture ({}, {})".format(
                self.max_x, self.max_y, int(self.max_x * ratio_x), int(self.max_y * ratio_y)
            )
        )
        if self.min_x > self.max_x:
            self.min_x, self.max_x = self.max_x, self.min_x
        if self.min_y > self.max_y:
            self.min_y, self.max_y = self.max_y, self.min_y

        filename = filedialog.asksaveasfilename(
            title="名前を付けて保存", filetypes=[("PNG", ".png")], initialdir="./TEMPLATE/", defaultextension="png"
        )
        if filename != "":
            self.camera.saveCapture(
                filename=filename[:-4],
                crop=1,
                crop_ax=[
                    int(self.min_x * ratio_x),
                    int(self.min_y * ratio_x),
                    int(self.max_x * ratio_x),
                    int(self.max_y * ratio_x),
                ],
            )

        # t = 0
        self.after(250, self.delete("SelectArea"))

        if self.master.is_use_left_stick_mouse.get():
            self.BindLeftClick()
        if self.master.is_use_right_stick_mouse.get():
            self.BindRightClick()

    def StartRangeTouchscreen(self, event):
        self.ss = self.camera.image_bgr
        if self.master.is_use_left_stick_mouse.get():
            self.UnbindLeftClick()
        if self.master.is_use_right_stick_mouse.get():
            self.UnbindRightClick()

        self.touchscreen_start_x, self.touchscreen_start_y = event.x, event.y
        self.delete("SelectArea")
        self.create_rectangle(
            self.touchscreen_start_x,
            self.touchscreen_start_y,
            self.touchscreen_start_x + 1,
            self.touchscreen_start_y + 1,
            width=3.0,
            outline="red",
            tag="SelectArea",
        )

        if self.master.is_use_left_stick_mouse.get():
            self.BindLeftClick()
        if self.master.is_use_right_stick_mouse.get():
            self.BindRightClick()

    def MotionRangeTouchscreen(self, event):
        if event.x < 0:
            self.touchscreen_end_x = 0
        else:
            self.touchscreen_end_x = min(self.show_width, event.x)
        if event.y < 0:
            self.touchscreen_end_y = 0
        else:
            self.touchscreen_end_y = min(self.show_height, event.y)
        self.coords(
            "SelectArea",
            self.touchscreen_start_x,
            self.touchscreen_start_y,
            self.touchscreen_end_x + 1,
            self.touchscreen_end_y + 1,
        )
        self.coords(
            "SelectAreaFilled",
            self.touchscreen_start_x,
            self.touchscreen_start_y,
            self.touchscreen_end_x + 1,
            self.touchscreen_end_y + 1,
        )

    def ReleaseRangeTouchscreen(self, event):
        if self.touchscreen_start_x > self.touchscreen_end_x:
            self.touchscreen_start_x, self.touchscreen_end_x = self.touchscreen_end_x, self.touchscreen_start_x
        if self.touchscreen_start_y > self.touchscreen_end_y:
            self.touchscreen_start_y, self.touchscreen_end_y = self.touchscreen_end_y, self.touchscreen_start_y

        print(
            f"Touchscreen Area: ({self.touchscreen_start_x}, {self.touchscreen_start_y}), ({self.touchscreen_end_x}, {self.touchscreen_end_y})"
        )

        # t = 0
        self.after(250, self.delete("SelectArea"))

        if self.master.is_use_left_stick_mouse.get():
            self.BindLeftClick()
        if self.master.is_use_right_stick_mouse.get():
            self.BindRightClick()

    def setFps(self, fps):
        # self.next_frames = int(16 * (60 / int(fps)))
        self._requested_fps = max(1, int(fps))
        self.next_frames = max(1, int(1000 / self._requested_fps))
        self._logger.info(f"FPS set to {fps}")

    def setShowsize(self, show_height, show_width):
        self._discard_prepared_preview()
        self._leave_native_preview()
        self.show_width = int(show_width)
        self.show_height = int(show_height)
        self.show_size = (self.show_width, self.show_height)
        self._last_preview_render_time = 0.0
        self._last_rendered_frame_sequence = -1
        self._last_submitted_frame_sequence = -1
        self._live_preview_tk = None
        self._live_preview_size = None
        self._displaying_live_preview = False
        self.config(width=self.show_width, height=self.show_height)
        disabled_pil = prepare_disabled_preview_image(
            self._disabled_source_pil, self.show_size)
        self.disabled_tk = ImageTk.PhotoImage(disabled_pil, master=self)
        current_frame = self.camera.readFrame()
        current_sequence = self.camera.frameSequence() \
            if current_frame is not None and hasattr(self.camera, "frameSequence") \
            else None
        if current_frame is not None and self._native_preview is not None \
                and self._draw_native_preview(current_frame, current_sequence):
            # GDI has already repainted the new preview extent.  Do not place
            # the No Image bitmap over it while waiting for the next frame.
            self._missing_frame_started_at = None
        elif current_frame is not None:
            image_pil = prepare_preview_image(current_frame, self.show_size)
            self._live_preview_tk = ImageTk.PhotoImage(image_pil, master=self)
            self._live_preview_size = tuple(self.show_size)
            self.im = self._live_preview_tk
            self.itemconfig(self.im_, image=self._live_preview_tk, state="normal")
            self._displaying_live_preview = True
            self._last_rendered_frame_sequence = current_sequence
            self._missing_frame_started_at = None
        else:
            self.im = self.disabled_tk
            self.itemconfig(self.im_, image=self.disabled_tk, state="normal")
        print("Show size set to {0} x {1}".format(self.show_width, self.show_height))
        self._logger.info("Show size set to {0} x {1}".format(self.show_width, self.show_height))

    def changeRightMouseMode(self, mode):
        self.RightMouseMode = mode

    def setTouchscreenArea(self, touchscreen_start_x, touchscreen_start_y, touchscreen_end_x, touchscreen_end_y):
        self.touchscreen_start_x = touchscreen_start_x
        self.touchscreen_start_y = touchscreen_start_y
        self.touchscreen_end_x = touchscreen_end_x
        self.touchscreen_end_y = touchscreen_end_y

    def mouseCtrlLeftPress(self, event):
        _img = cv2.cvtColor(self.camera.image_bgr, cv2.COLOR_BGR2RGB)
        if self.master.is_use_left_stick_mouse.get():
            self.UnbindLeftClick()
        x, y = event.x, event.y
        ratio_x = float(self.camera.capture_size[0] / self.show_size[0])
        ratio_y = float(self.camera.capture_size[1] / self.show_size[1])
        print("Mouse down: Show ({}, {}) / Capture ({}, {})".format(x, y, int(x * ratio_x), int(y * ratio_y)))
        print(
            f"Color [R: {_img[int(y * ratio_y), int(x * ratio_x)][0]}, "
            f"G: {_img[int(y * ratio_y), int(x * ratio_x)][1]}, "
            f"B: {_img[int(y * ratio_y), int(x * ratio_x)][2]}]"
        )
        self._logger.info(
            "Mouse down: Show ({}, {}) / Capture ({}, {})".format(x, y, int(x * ratio_x), int(y * ratio_y))
        )

    def mouseCtrlLeftRelease(self, event):
        if self.master.is_use_left_stick_mouse.get():
            self.BindLeftClick()

    def mouseLeftPress(self, event, ser):
        self.ser.begin_manual_override()
        self._last_lstick_send = 0.0
        self._last_lstick_position = None
        if self.master.is_use_right_stick_mouse.get():
            self.UnbindRightClick()
        self.config(cursor="dot")
        self.lx_init, self.ly_init = event.x, event.y
        self.lcircle = self.create_oval(
            self.lx_init - self.radius,
            self.ly_init - self.radius,
            self.lx_init + self.radius,
            self.ly_init + self.radius,
            outline="cyan",
            tag="lcircle",
        )
        self.lcircle2 = self.create_oval(
            self.lx_init - self.radius // 10,
            self.ly_init - self.radius // 10,
            self.lx_init + self.radius // 10,
            self.ly_init + self.radius // 10,
            fill="cyan",
            tag="lcircle2",
        )
        # self.LStick = StickCommand.StickLeft()
        # self.LStick.start(ser)
        if isTakeLog:
            if self.dq is None:
                self.dq = deque()
            else:
                self.dq.clear()

            if self.calc_time is None:
                self.calc_time = time.perf_counter()
            else:
                # LSTICK_logger.debug(f"{0},{0},{time.perf_counter() - self.calc_time}")
                self.dq.append([0, 0, time.perf_counter() - self.calc_time])
            self._langle = None
            self._lmag = None

    def mouseLeftPressing(self, event, ser, angle=0):
        # _time = self.calc_time
        langle = np.rad2deg(np.arctan2(self.ly_init - event.y, event.x - self.lx_init))
        mag = np.sqrt((self.ly_init - event.y) ** 2 + (event.x - self.lx_init) ** 2) / self.radius
        if mag <= 0:
            mag = 0
        elif mag >= 1:
            mag = 1

        if (self._langle and self._lmag) is not None and isTakeLog:
            _time = time.perf_counter()
            if _time - self.calc_time > 0.05:
                self.ser.input(
                    Direction(
                        Stick.LEFT,
                        (
                            int(128 + mag * 127.5 * np.cos(np.deg2rad(langle))),
                            255 - int(128 - mag * 127.5 * np.sin(np.deg2rad(langle))),
                        ),
                    )
                )
                self.dq.append([langle, mag, _time - self.calc_time])
                self.calc_time = _time
        elif not isTakeLog:
            position = (
                int(128 + mag * 127.5 * np.cos(np.deg2rad(langle))),
                255 - int(128 - mag * 127.5 * np.sin(np.deg2rad(langle))),
            )
            now = time.perf_counter()
            if (position != self._last_lstick_position
                    and now - self._last_lstick_send >= self._manual_stick_interval):
                self.ser.input(Direction(Stick.LEFT, position))
                self._last_lstick_position = position
                self._last_lstick_send = now

        if mag >= 1:
            center_x = (self.radius + self.radius // 11) * np.cos(np.deg2rad(langle))
            center_y = (self.radius + self.radius // 11) * np.sin(np.deg2rad(langle))
            circ_x_1 = self.lx_init + center_x - self.radius // 10
            circ_x_2 = self.lx_init + center_x + self.radius // 10
            circ_y_1 = self.ly_init - center_y - self.radius // 10
            circ_y_2 = self.ly_init - center_y + self.radius // 10
        else:
            circ_x_1 = event.x - self.radius // 10
            circ_x_2 = event.x + self.radius // 10
            circ_y_1 = event.y - self.radius // 10
            circ_y_2 = event.y + self.radius // 10

        self.coords(
            "lcircle2",
            circ_x_1,
            circ_y_1,
            circ_x_2,
            circ_y_2,
        )
        self._langle = langle
        self._lmag = mag

    def mouseLeftRelease(self, ser):
        self.config(cursor="tcross")
        try:
            self.ser.input(Direction(Stick.LEFT, NEUTRAL))
        finally:
            self.ser.end_manual_override()
            self._last_lstick_position = None
        self.delete("lcircle")
        self.delete("lcircle2")
        if self.master.is_use_right_stick_mouse.get():
            self.BindRightClick()
        # self.event_generate('<Motion>', warp=True, x=self.lx_init, y=self.ly_init)
        if isTakeLog:
            self.dq.append([self._langle, self._lmag, time.perf_counter() - self.calc_time])
            for _ in self.dq:
                self.LSTICK_logger.debug(",".join(list(map(str, _))))

    def mouseRightPress(self, event, ser):
        self.ser.begin_manual_override()
        self._last_rstick_send = 0.0
        self._last_rstick_position = None
        if self.master.is_use_left_stick_mouse.get():
            self.UnbindLeftClick()

        if self.RightMouseMode == "Qingpi":
            if (
                self.touchscreen_start_x < event.x
                and event.x < self.touchscreen_end_x
                and self.touchscreen_start_y < event.y
                and event.y < self.touchscreen_end_y
            ):
                width = self.touchscreen_end_x - self.touchscreen_start_x
                height = self.touchscreen_end_y - self.touchscreen_start_y
                pos_x = int(320.0 * (event.x - self.touchscreen_start_x) / width)
                pos_y = int(240.0 * (event.y - self.touchscreen_start_y) / height)
                position = (pos_x, pos_y)
                now = time.perf_counter()
                if (position != self._last_rstick_position
                        and now - self._last_rstick_send >= self._manual_stick_interval):
                    ser.input(Touchscreen(pos_x, pos_y))
                    self._last_rstick_position = position
                    self._last_rstick_send = now
        else:
            self.config(cursor="dot")
            self.rx_init, self.ry_init = event.x, event.y
            self.rcircle = self.create_oval(
                self.rx_init - self.radius,
                self.ry_init - self.radius,
                self.rx_init + self.radius,
                self.ry_init + self.radius,
                outline="red",
                tag="rcircle",
            )
            self.rcircle2 = self.create_oval(
                self.rx_init - self.radius // 10,
                self.ry_init - self.radius // 10,
                self.rx_init + self.radius // 10,
                self.ry_init + self.radius // 10,
                fill="red",
                tag="rcircle2",
            )

            # self.RStick = StickCommand.StickRight()
            # self.RStick.start(ser)
            if isTakeLog:
                if self.dq is None:
                    self.dq = deque()
                else:
                    self.dq.clear()

                if self.calc_time is None:
                    self.calc_time = time.perf_counter()
                else:
                    # LSTICK_logger.debug(f"{0},{0},{time.perf_counter() - self.calc_time}")
                    self.dq.append([0, 0, time.perf_counter() - self.calc_time])
            self._rangle = None
            self._rmag = None

    def mouseRightPressing(self, event, ser, angle=0):
        if self.RightMouseMode == "Qingpi":
            if (
                self.touchscreen_start_x < event.x
                and event.x < self.touchscreen_end_x
                and self.touchscreen_start_y < event.y
                and event.y < self.touchscreen_end_y
            ):
                width = self.touchscreen_end_x - self.touchscreen_start_x
                height = self.touchscreen_end_y - self.touchscreen_start_y
                pos_x = int(320.0 * (event.x - self.touchscreen_start_x) / width)
                pos_y = int(240.0 * (event.y - self.touchscreen_start_y) / height)
                position = (pos_x, pos_y)
                now = time.perf_counter()
                if (position != self._last_rstick_position
                        and now - self._last_rstick_send >= self._manual_stick_interval):
                    ser.input(Touchscreen(pos_x, pos_y))
                    self._last_rstick_position = position
                    self._last_rstick_send = now
        else:
            rangle = np.rad2deg(np.arctan2(self.ry_init - event.y, event.x - self.rx_init))
            mag = np.sqrt((self.ry_init - event.y) ** 2 + (event.x - self.rx_init) ** 2) / self.radius
            if mag <= 0:
                mag = 0
            elif mag >= 1:
                mag = 1
            if (self._langle and self._lmag) is not None and isTakeLog:
                _time = time.perf_counter()
                if _time - self.calc_time > 0.05:
                    self.ser.input(
                        Direction(
                            Stick.RIGHT,
                            (
                                int(128 + mag * 127.5 * np.cos(np.deg2rad(rangle))),
                                255 - int(128 - mag * 127.5 * np.sin(np.deg2rad(rangle))),
                            ),
                        )
                    )
                    self.dq.append([rangle, mag, _time - self.calc_time])
                    self.calc_time = _time
            elif not isTakeLog:
                position = (
                    int(128 + mag * 127.5 * np.cos(np.deg2rad(rangle))),
                    255 - int(128 - mag * 127.5 * np.sin(np.deg2rad(rangle))),
                )
                now = time.perf_counter()
                if (position != self._last_rstick_position
                        and now - self._last_rstick_send >= self._manual_stick_interval):
                    self.ser.input(Direction(Stick.RIGHT, position))
                    self._last_rstick_position = position
                    self._last_rstick_send = now
            if mag >= 1:
                center_x = (self.radius + self.radius // 11) * np.cos(np.deg2rad(rangle))
                center_y = (self.radius + self.radius // 11) * np.sin(np.deg2rad(rangle))
                circ_x_1 = self.rx_init + center_x - self.radius // 10
                circ_x_2 = self.rx_init + center_x + self.radius // 10
                circ_y_1 = self.ry_init - center_y - self.radius // 10
                circ_y_2 = self.ry_init - center_y + self.radius // 10
            else:
                circ_x_1 = event.x - self.radius // 10
                circ_x_2 = event.x + self.radius // 10
                circ_y_1 = event.y - self.radius // 10
                circ_y_2 = event.y + self.radius // 10

            self.coords(
                "rcircle2",
                circ_x_1,
                circ_y_1,
                circ_x_2,
                circ_y_2,
            )
            self._rangle = rangle
            self._rmag = mag

    def mouseRightRelease(self, ser):
        try:
            if self.RightMouseMode == "Qingpi":
                ser.inputEnd(Touchscreen(0, 0))
            else:
                self.config(cursor="tcross")
                self.ser.input(Direction(Stick.RIGHT, NEUTRAL))
        finally:
            self.ser.end_manual_override()
            self._last_rstick_position = None
        if self.RightMouseMode != "Qingpi":
            self.delete("rcircle")
            self.delete("rcircle2")
            if self.master.is_use_left_stick_mouse.get():
                self.BindLeftClick()

            # self.event_generate('<Motion>', warp=True, x=self.rx_init, y=self.ry_init)
            if isTakeLog:
                self.dq.append([self._rangle, self._rmag, time.perf_counter() - self.calc_time])
                for _ in self.dq:
                    self.RSTICK_logger.debug(",".join(list(map(str, _))))

    def startCapture(self):
        self.capture()

    def _schedule_next_capture(self, interval, started_at,
                               high_precision=False):
        # The unique 60-FPS owner enables Windows' 1-ms timer resolution.
        # Polling Tk itself every 1 ms, however, runs this entire callback up
        # to 1000 times/sec and can starve the actual GDI draw down to ~40 FPS.
        # A 4-ms poll remains for recording and compatible-rendering paths
        # which must consume asynchronously arriving 60-Hz frames in Tk.
        # Feature-limited GDI display follows Camera's frame event instead.
        high_precision = bool(
            high_precision or self._capture_high_precision_requested)
        delay = compensated_after_delay(interval, started_at)
        if high_precision:
            delay = min(4, delay)
        self.after(delay, self.capture)

    @staticmethod
    def _prepare_preview_frame(image_bgr, show_size, frame_sequence,
                               submitted_at=None):
        return (frame_sequence, tuple(show_size),
                prepare_preview_image(image_bgr, show_size), image_bgr,
                time.monotonic() if submitted_at is None
                else float(submitted_at))

    def _discard_prepared_preview(self):
        """Drop a compatibility frame that must not survive a mode change."""
        future, self._preview_prepare_future = \
            self._preview_prepare_future, None
        if future is not None and not future.done():
            future.cancel()

    def _take_prepared_preview(self):
        future = self._preview_prepare_future
        if future is None or not future.done():
            return None
        self._preview_prepare_future = None
        try:
            return future.result()
        except Exception as error:
            self._logger.warning("Preview frame preparation failed: %s", error)
            return None

    def _submit_preview_prepare(self, image_bgr, frame_sequence):
        if image_bgr is None or self._preview_prepare_future is not None:
            return False
        if frame_sequence is not None \
                and frame_sequence == self._last_submitted_frame_sequence:
            return False
        self._last_submitted_frame_sequence = frame_sequence
        self._preview_prepare_future = self._preview_prepare_executor.submit(
            self._prepare_preview_frame, image_bgr, tuple(self.show_size),
            frame_sequence, time.monotonic())
        return True

    def _install_prepared_preview(self, prepared):
        if not prepared:
            return False
        frame_sequence, prepared_size, image_pil, image_bgr, submitted_at = \
            prepared
        if image_pil is None or tuple(prepared_size) != tuple(self.show_size):
            return False
        # A completed Pillow conversion can remain pending while GDI owns the
        # canvas or while a background PokeCon is throttled.  Never install it
        # seconds later when a Commands overlay returns to compatibility mode.
        # At 60 FPS, 0.25 seconds is enough headroom for a 5-FPS background
        # render without allowing a previous command's final image through.
        now = time.monotonic()
        if now - float(submitted_at) > 0.25:
            return False
        current_sequence = self.camera.frameSequence() \
            if hasattr(self.camera, "frameSequence") else None
        max_sequence_gap = max(2, int(self._requested_fps * 0.25))
        if current_sequence is not None and frame_sequence is not None \
                and current_sequence - frame_sequence > max_sequence_gap:
            return False
        if frame_sequence is not None \
                and frame_sequence == self._last_rendered_frame_sequence:
            return False
        if self._live_preview_tk is None \
                or self._live_preview_size != tuple(prepared_size):
            self._live_preview_tk = ImageTk.PhotoImage(image_pil, master=self)
            self._live_preview_size = tuple(prepared_size)
            self.itemconfig(self.im_, image=self._live_preview_tk)
        else:
            # Reusing the Tcl image avoids allocating and deleting a 720p
            # PhotoImage every frame. On the target machine this reduces Tk
            # work from about 18 ms to about 11 ms per frame.
            self._live_preview_tk.paste(image_pil)
            if not self._displaying_live_preview:
                self.itemconfig(self.im_, image=self._live_preview_tk)
        self.im = self._live_preview_tk
        self._displaying_live_preview = True
        self._last_rendered_frame_sequence = frame_sequence
        self._last_preview_render_time = now
        self._note_preview_frame(self._last_preview_render_time)
        CaptureArea._notify_presented_frame(
            self, image_bgr, frame_sequence,
            self._last_preview_render_time)
        return True

    def _native_preview_available(self, image_bgr):
        if self._native_preview is None or image_bgr is None:
            return False
        try:
            # The base image is the only normal permanent Canvas item. While
            # range/analysis overlays exist, Pillow is used so Tk can compose
            # those items above the video correctly.
            return tuple(self.find_all()) == (self.im_,)
        except tk.TclError:
            return False

    def _draw_native_preview(self, image_bgr, frame_sequence,
                             render_started_at=None):
        try:
            if not self._native_preview_active:
                self._discard_prepared_preview()
                self.itemconfig(self.im_, state="hidden")
            if not self._native_preview.draw(image_bgr, self.show_size):
                if not self._native_preview_active:
                    self.itemconfig(self.im_, state="normal")
                return False
            self._native_preview_active = True
            self._displaying_live_preview = True
            self._last_rendered_frame_sequence = frame_sequence
            self._last_preview_render_time = time.monotonic() \
                if render_started_at is None else float(render_started_at)
            self._note_preview_frame(self._last_preview_render_time)
            CaptureArea._notify_presented_frame(
                self, image_bgr, frame_sequence,
                self._last_preview_render_time)
            return True
        except (AttributeError, OSError, tk.TclError):
            return False

    def _enable_threaded_native_preview(self):
        """Hand feature-limited GDI drawing to the camera-frame worker."""
        if self._native_preview is None:
            return False
        try:
            if not self._native_preview_active:
                self._discard_prepared_preview()
                self.itemconfig(self.im_, state="hidden")
        except tk.TclError:
            return False
        with self._native_render_mode_lock:
            already_enabled = self._native_render_enabled
            self._native_render_enabled = True
        self._native_preview_active = True
        self._displaying_live_preview = True
        if not already_enabled:
            self._native_render_wake.set()
            if hasattr(self.camera, "wakeFrameWait"):
                self.camera.wakeFrameWait()
        return True

    def _disable_threaded_native_preview(self, clear=False):
        """Stop worker draws before Tk changes the canvas or its size."""
        with self._native_render_mode_lock:
            was_enabled = self._native_render_enabled
            self._native_render_enabled = False
            if clear and self._native_preview is not None:
                try:
                    self._native_preview.clear(self.show_size)
                except (AttributeError, OSError, tk.TclError):
                    pass
        if was_enabled and hasattr(self.camera, "wakeFrameWait"):
            self.camera.wakeFrameWait()
        self._native_render_wake.set()

    def _native_render_loop(self):
        """Draw each new camera frame without routing it through Tk's loop."""
        rendered_sequence = -1
        while not self._native_render_stop.is_set():
            if not self._native_render_enabled:
                self._native_render_wake.wait(0.1)
                self._native_render_wake.clear()
                continue
            try:
                sequence, image_bgr = self.camera.waitForFrame(
                    rendered_sequence, timeout=0.1)
            except Exception as error:
                self._logger.warning("Native preview frame wait failed: %s", error)
                self._native_render_stop.wait(0.05)
                continue
            if self._native_render_stop.is_set():
                break
            if sequence == rendered_sequence:
                continue
            if image_bgr is None:
                # Camera.destroy() advances the sequence as it clears the
                # image. Consume that state once, then sleep until a new input
                # publishes a frame instead of spinning on ``None``.
                rendered_sequence = sequence
                continue
            with self._native_render_mode_lock:
                if not self._native_render_enabled:
                    continue
                try:
                    drawn = self._native_preview.draw(
                        image_bgr, tuple(self.show_size))
                except Exception as error:
                    self._logger.warning("Native preview draw failed: %s", error)
                    drawn = False
                # A rejected frame must still be consumed. Otherwise an
                # unsupported buffer format would make this worker spin on the
                # same sequence instead of sleeping for the next camera event.
                rendered_sequence = sequence
                if drawn:
                    now = time.monotonic()
                    self._last_rendered_frame_sequence = sequence
                    self._last_preview_render_time = now
                    self._note_preview_frame(now)
                    CaptureArea._notify_presented_frame(
                        self, image_bgr, sequence, now)

    def _leave_native_preview(self, image_bgr=None, frame_sequence=None):
        if not self._native_preview_active:
            return False
        if hasattr(self, "_discard_prepared_preview"):
            self._discard_prepared_preview()
        replacement_ready = False
        replacement_pil = None
        if image_bgr is not None:
            try:
                replacement_pil = prepare_preview_image(
                    image_bgr, tuple(self.show_size))
                replacement_ready = replacement_pil is not None
                if replacement_ready:
                    if self._live_preview_tk is None \
                            or self._live_preview_size != tuple(self.show_size):
                        self._live_preview_tk = ImageTk.PhotoImage(
                            replacement_pil, master=self)
                        self._live_preview_size = tuple(self.show_size)
                    else:
                        self._live_preview_tk.paste(replacement_pil)
                    # Update the hidden Tk image before erasing the GDI surface.
                    # Unhiding below therefore reveals the current frame, not a
                    # black canvas or the final frame of a previous command.
                    self.itemconfig(self.im_, image=self._live_preview_tk)
                    self.im = self._live_preview_tk
            except (AttributeError, OSError, tk.TclError):
                replacement_ready = False
        self._disable_threaded_native_preview(clear=True)
        self._native_preview_active = False
        try:
            self.itemconfig(self.im_, state="normal")
        except tk.TclError:
            pass
        if replacement_ready:
            self._displaying_live_preview = True
            self._last_rendered_frame_sequence = frame_sequence
            self._last_submitted_frame_sequence = frame_sequence
            now = time.monotonic()
            self._last_preview_render_time = now
            self._note_preview_frame(now)
            CaptureArea._notify_presented_frame(
                self, image_bgr, frame_sequence, now)
        return replacement_ready

    def _note_preview_frame(self, now=None):
        now = time.monotonic() if now is None else float(now)
        self._last_preview_frame_at = now
        if self._preview_fps_measure_started <= 0.0:
            self._preview_fps_measure_started = now
            self._preview_fps_measure_frames = 0
            return
        self._preview_fps_measure_frames += 1
        elapsed = now - self._preview_fps_measure_started
        if elapsed >= 0.75:
            self._measured_preview_fps = \
                self._preview_fps_measure_frames / elapsed
            self._preview_fps_measure_started = now
            self._preview_fps_measure_frames = 0

    def measuredPreviewFps(self, now=None):
        """Return recently measured successful preview draws."""
        now = time.monotonic() if now is None else float(now)
        if self._last_preview_frame_at <= 0.0 \
                or now - self._last_preview_frame_at > 1.5:
            return 0.0
        return max(0.0, float(self._measured_preview_fps))

    def capture(self):
        cycle_started = time.monotonic()
        try:
            top = self.winfo_toplevel()
            viewable = bool(top.winfo_viewable()) and top.state() != "iconic"
            foreground = foreground_process_matches()
            focused = (top.focus_displayof() is not None) \
                if foreground is None else foreground
        except (tk.TclError, KeyError):
            viewable, focused = True, True
        main_tool, allow_foreground_full_rate, keep_warm = False, False, False
        if callable(self.render_priority_provider):
            try:
                priority_values = tuple(self.render_priority_provider())
                if len(priority_values) >= 2:
                    main_tool, allow_foreground_full_rate = priority_values[:2]
                if len(priority_values) >= 3:
                    keep_warm = bool(priority_values[2])
            except Exception as error:
                self._logger.warning("Preview priority provider failed: %s", error)
        prioritized, full_rate = preview_priority(
            focused=focused, main_tool=main_tool,
            allow_foreground_full_rate=allow_foreground_full_rate,
            keep_warm=keep_warm)
        background_work = False
        if callable(self.capture_work_provider):
            try:
                background_work = bool(self.capture_work_provider())
            except Exception as error:
                self._logger.warning("Capture work provider failed: %s", error)
        frame_work = self.frame_listener is not None
        if callable(self.frame_work_provider):
            try:
                frame_work = bool(self.frame_work_provider())
            except Exception as error:
                self._logger.warning("Frame work provider failed: %s", error)
        resource_multiplier = 1.0
        if callable(self.resource_multiplier_provider):
            try:
                resource_multiplier = max(
                    1.0, float(self.resource_multiplier_provider()))
            except Exception as error:
                self._logger.warning("Resource multiplier provider failed: %s", error)
        capture_interval = preview_capture_interval(
            self._requested_fps, focused=prioritized, viewable=viewable,
            full_rate=full_rate,
            background_work=background_work,
            resource_multiplier=resource_multiplier)
        if frame_work:
            # Analysis rules are specified as a 0.25-second periodic check.
            capture_interval = min(capture_interval, 0.25)
            capture_interval *= resource_multiplier
        # A reduced visible preview must not accidentally reduce a 60-FPS
        # recording to ~30 FPS because Windows coalesces Tk's 15-16 ms timer.
        # The sequence gate below still forwards each camera frame only once.
        self._capture_high_precision_requested = bool(
            background_work and capture_interval <= (1.0 / 50.0))
        layout_busy = time.monotonic() < self._layout_busy_until
        interaction_busy = time.monotonic() < self._ui_interaction_busy_until
        if not self.is_show_var.get():
            if self._native_render_enabled:
                self._disable_threaded_native_preview(clear=False)
            self._schedule_next_capture(capture_interval, cycle_started)
            return

        # readFrame() is a non-blocking latest-frame lookup.  Physical camera
        # drivers and WGC are drained on their own reader threads.
        image_bgr = self.camera.readFrame()
        now = time.monotonic()
        if image_bgr is not None:
            self._missing_frame_started_at = None
        elif self._missing_frame_started_at is None:
            self._missing_frame_started_at = now
        if image_bgr is None and hold_last_preview_on_missing_frame(
                self._displaying_live_preview,
                self._missing_frame_started_at, now):
            # Source replacement runs outside Tk and can legitimately have no
            # published frame for a moment.  Keep the last complete image;
            # recording/analysis still receive no stale frame here.
            self._schedule_next_capture(capture_interval, cycle_started)
            return
        frame_sequence = self.camera.frameSequence() \
            if image_bgr is not None and hasattr(self.camera, "frameSequence") \
            else None
        new_capture_frame = frame_sequence is None \
            or frame_sequence != self._last_consumed_frame_sequence
        if image_bgr is not None and new_capture_frame:
            self._last_consumed_frame_sequence = frame_sequence
            if self.record_listener is not None:
                self._notify_capture_listener(
                    self, "record_listener", image_bgr)
            if frame_work and self.frame_listener is not None \
                    and now - self._last_listener_time >= 0.25:
                self._last_listener_time = now
                self._notify_capture_listener(
                    self, "frame_listener", image_bgr, copy_frame=True)

        render_interval = preview_render_interval(
            self._requested_fps, focused=prioritized, viewable=viewable,
            full_rate=full_rate,
            resource_multiplier=resource_multiplier)
        native_render_interval = render_interval
        capture_interval, render_interval = resize_safe_preview_intervals(
            capture_interval, render_interval,
            resizing=bool(layout_busy or interaction_busy),
            background_work=background_work)
        native_preview = self._native_preview_available(image_bgr)
        threaded_native = bool(
            native_preview and self._feature_limited
            and full_rate and prioritized
            and hasattr(self.camera, "waitForFrame"))
        if threaded_native and self._enable_threaded_native_preview():
            # The GDI worker now follows the camera's frame event directly.
            # Tk only needs to service policy, recording and analysis work.
            self._schedule_next_capture(
                capture_interval, cycle_started, high_precision=False)
            return
        if self._native_render_enabled:
            # Keep the last GDI frame visible while returning ownership to the
            # normal Tk capture callback.
            self._disable_threaded_native_preview(clear=False)
        if native_preview:
            # GDI draws a 720p frame in a fraction of a millisecond and does
            # not allocate a Tcl PhotoImage. It therefore remains safe during
            # window and control interaction, while capture stays at 60 FPS.
            if preview_render_due(
                    now - self._last_preview_render_time,
                    native_render_interval,
                    full_rate=bool(full_rate), prioritized=prioritized,
                    viewable=viewable):
                if frame_sequence is None \
                        or frame_sequence != self._last_rendered_frame_sequence:
                    self._draw_native_preview(
                        image_bgr, frame_sequence, render_started_at=now)
            self._schedule_next_capture(
                capture_interval, cycle_started,
                high_precision=bool(full_rate and prioritized))
            return
        self._leave_native_preview(image_bgr, frame_sequence)
        if layout_busy or interaction_busy:
            # Rendering a 720p PhotoImage while Tk is recalculating every tab
            # and pane can delay maximize/restore or tab-change messages for
            # several seconds. Keep capture/recording above, but let the UI
            # operation finish before the next visible frame is installed.
            # Drop a completed stale conversion so interaction ends with the
            # newest camera frame rather than a queued pre-interaction frame.
            self._discard_prepared_preview()
            self._schedule_next_capture(capture_interval, cycle_started)
            return
        # The full-rate path already schedules capture at the render cadence.
        # Render every such callback so sub-millisecond Tk timer jitter cannot
        # turn an occasional early callback into a skipped frame (and 30 FPS).
        if not preview_render_due(
                now - self._last_preview_render_time, render_interval,
                full_rate=bool(full_rate and not layout_busy),
                prioritized=prioritized,
                viewable=viewable):
            self._schedule_next_capture(capture_interval, cycle_started)
            return
        if image_bgr is not None:
            prepared = self._take_prepared_preview()
            if self._install_prepared_preview(prepared):
                # Start preparing the newest frame after consuming the prior
                # one.  At normal/full cadence this keeps conversion off Tk.
                self._submit_preview_prepare(image_bgr, frame_sequence)
            elif prepared is not None or render_interval > 0.25 \
                    or not self._displaying_live_preview:
                # A strongly throttled background PokeCon may render only once
                # per second or less. Its completed worker image is then old by
                # design; showing it would make Commands appear to jump back in
                # time. Convert the current frame synchronously at that low
                # cadence instead of waiting another full render interval.
                self._discard_prepared_preview()
                current = self._prepare_preview_frame(
                    image_bgr, tuple(self.show_size), frame_sequence,
                    time.monotonic())
                self._install_prepared_preview(current)
                self._last_submitted_frame_sequence = frame_sequence
            else:
                # Bootstrap the asynchronous pipeline while the current live
                # image remains visible.  Do not synchronously convert every
                # 60-FPS compatibility frame merely because the first worker
                # result is not ready yet.
                self._submit_preview_prepare(image_bgr, frame_sequence)
        else:
            self._leave_native_preview()
            self.im = self.disabled_tk
            self._displaying_live_preview = False
            # self.configure(image=self.disabled_tk)
            self.itemconfig(self.im_, image=self.disabled_tk)

        self._schedule_next_capture(capture_interval, cycle_started)

    def destroy(self):
        self._native_render_stop.set()
        with self._native_render_mode_lock:
            self._native_render_enabled = False
        self._native_render_wake.set()
        if hasattr(self.camera, "wakeFrameWait"):
            self.camera.wakeFrameWait()
        native_thread = getattr(self, "_native_render_thread", None)
        if native_thread is not None \
                and native_thread is not threading.current_thread():
            native_thread.join(timeout=0.5)
        executor = getattr(self, "_preview_prepare_executor", None)
        if executor is not None:
            self._preview_prepare_executor = None
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                # ``cancel_futures`` was added after Python 3.7.
                executor.shutdown(wait=False)
        super().destroy()

    def saveCapture(self):
        self.camera.saveCapture()

    def ImgRect(self, x1, y1, x2, y2, outline, tag, ms, flag=True):
        if self._feature_limited:
            return None
        ratio_x = float(self.show_size[0] / self.camera.capture_size[0])
        ratio_y = float(self.show_size[1] / self.camera.capture_size[1])
        self.create_rectangle(
            (x1 - 1.0) * ratio_x,
            (y1 - 1.0) * ratio_y,
            (x2 + 1.0) * ratio_x,
            (y2 + 1.0) * ratio_y,
            width=4.5,
            outline="white",
            tag=tag,
        )
        self.create_rectangle(
            x1 * ratio_x, y1 * ratio_y, x2 * ratio_x, y2 * ratio_y, width=2.5, outline=outline, tag=tag
        )
        if flag:
            self.after(ms, self.deleteImageRect, tag)

    def deleteImageRect(self, tag):
        self.delete(tag)

    def ImgText(
        self, x1, y1, txt, tag, ms, ft=("UD デジタル 教科書体 NP-B", 20), color: str = "black", flag: bool = True
    ):
        if self._feature_limited:
            return None
        ratio_x = float(self.show_size[0] / self.camera.capture_size[0])
        ratio_y = float(self.show_size[1] / self.camera.capture_size[1])
        str_len = 0.3528 * ft[1] * len(txt)  # 1[pt] = 0.3528[mm]
        self.create_text(((x1 - 1.0) * ratio_x) + str_len, (y1 - 1.0) * ratio_y, text=txt, font=ft, tag=tag, fill=color)
        if flag:
            self.after(ms, self.deleteImageText, tag)

    def deleteImageText(self, tag):
        self.delete(tag)

    def BindLeftClick(self):
        self.bind("<ButtonPress-1>", lambda ev: self.mouseLeftPress(ev, self.ser))
        self.bind("<Button1-Motion>", lambda ev: self.mouseLeftPressing(ev, self.ser))
        self.bind("<ButtonRelease-1>", lambda ev: self.mouseLeftRelease(self.ser))
        self._logger.debug("Bind <ButtonPress-1>")
        self._logger.debug("Bind <Button1-Motion>")
        self._logger.debug("Bind <ButtonRelease-1>")

    def BindRightClick(self):
        self.bind("<ButtonPress-3>", lambda ev: self.mouseRightPress(ev, self.ser))
        self.bind("<Button3-Motion>", lambda ev: self.mouseRightPressing(ev, self.ser))
        self.bind("<ButtonRelease-3>", lambda ev: self.mouseRightRelease(self.ser))
        self._logger.debug("Bind <ButtonPress-3>")
        self._logger.debug("Bind <Button3-Motion>")
        self._logger.debug("Bind <ButtonRelease-3>")

    def UnbindLeftClick(self):
        self.unbind("<ButtonPress-1>")
        self.unbind("<Button1-Motion>")
        self.unbind("<ButtonRelease-1>")
        self._logger.debug("Unbind <ButtonPress-1>")
        self._logger.debug("Unbind <Button1-Motion>")
        self._logger.debug("Unbind <ButtonRelease-1>")

    def UnbindRightClick(self):
        self.unbind("<ButtonPress-3>")
        self.unbind("<Button3-Motion>")
        self.unbind("<ButtonRelease-3>")
        self._logger.debug("Unbind <ButtonPress-3>")
        self._logger.debug("Unbind <Button3-Motion>")
        self._logger.debug("Unbind <ButtonRelease-3>")


# GUI of switch controller simulator
class ControllerGUI:
    def __init__(self, root, ser):
        self._logger = getLogger(__name__)
        self._logger.addHandler(NullHandler())
        self._logger.setLevel(DEBUG)
        self._logger.propagate = True

        self.window = tk.Toplevel(root)
        self.window.title("Switch Controller Simulator")
        root_geometry = root.geometry().split("+")
        root_x = int(root_geometry[1])
        root_y = int(root_geometry[2])
        self.window.geometry("%dx%d%+d%+d" % (600, 300, 250 + root_x, 125 + root_y))
        self.window.resizable(False, False)

        joycon_L_color = "#95f1ff"
        joycon_R_color = "#ff6b6b"

        joycon_L_frame = tk.Frame(self.window, width=300, height=300, relief="flat", bg=joycon_L_color)
        joycon_R_frame = tk.Frame(self.window, width=300, height=300, relief="flat", bg=joycon_R_color)
        hat_frame = tk.Frame(joycon_L_frame, relief="flat", bg=joycon_L_color)
        abxy_frame = tk.Frame(joycon_R_frame, relief="flat", bg=joycon_R_color)

        # ABXY
        tk.Button(abxy_frame, text="A", command=lambda: UnitCommand.A().start(ser)).grid(row=1, column=2)
        tk.Button(abxy_frame, text="B", command=lambda: UnitCommand.B().start(ser)).grid(row=2, column=1)
        tk.Button(abxy_frame, text="X", command=lambda: UnitCommand.X().start(ser)).grid(row=0, column=1)
        tk.Button(abxy_frame, text="Y", command=lambda: UnitCommand.Y().start(ser)).grid(row=1, column=0)
        abxy_frame.place(relx=0.2, rely=0.3)

        # HAT
        tk.Button(hat_frame, text="UP", command=lambda: UnitCommand.UP().start(ser)).grid(row=0, column=1)
        tk.Button(hat_frame, text="", command=lambda: UnitCommand.UP_RIGHT().start(ser)).grid(row=0, column=2)
        tk.Button(hat_frame, text="RIGHT", command=lambda: UnitCommand.RIGHT().start(ser)).grid(row=1, column=2)
        tk.Button(hat_frame, text="", command=lambda: UnitCommand.DOWN_RIGHT().start(ser)).grid(row=2, column=2)
        tk.Button(hat_frame, text="DOWN", command=lambda: UnitCommand.DOWN().start(ser)).grid(row=2, column=1)
        tk.Button(hat_frame, text="", command=lambda: UnitCommand.DOWN_LEFT().start(ser)).grid(row=2, column=0)
        tk.Button(hat_frame, text="LEFT", command=lambda: UnitCommand.LEFT().start(ser)).grid(row=1, column=0)
        tk.Button(hat_frame, text="", command=lambda: UnitCommand.UP_LEFT().start(ser)).grid(row=0, column=0)
        hat_frame.place(relx=0.2, rely=0.6)

        # L side
        tk.Button(joycon_L_frame, text="L", width=20, command=lambda: UnitCommand.L().start(ser)).place(x=30, y=30)
        tk.Button(joycon_L_frame, text="ZL", width=20, command=lambda: UnitCommand.ZL().start(ser)).place(x=30, y=0)
        tk.Button(joycon_L_frame, text="LCLICK", width=7, command=lambda: UnitCommand.LCLICK().start(ser)).place(
            x=120, y=120
        )
        tk.Button(joycon_L_frame, text="MINUS", width=5, command=lambda: UnitCommand.MINUS().start(ser)).place(
            x=220, y=70
        )
        tk.Button(joycon_L_frame, text="CAP", width=5, command=lambda: UnitCommand.CAPTURE().start(ser)).place(
            x=200, y=270
        )

        # R side
        tk.Button(joycon_R_frame, text="R", width=20, command=lambda: UnitCommand.R().start(ser)).place(x=120, y=30)
        tk.Button(joycon_R_frame, text="ZR", width=20, command=lambda: UnitCommand.ZR().start(ser)).place(x=120, y=0)
        tk.Button(joycon_R_frame, text="RCLICK", width=7, command=lambda: UnitCommand.RCLICK().start(ser)).place(
            x=120, y=205
        )
        tk.Button(joycon_R_frame, text="PLUS", width=5, command=lambda: UnitCommand.PLUS().start(ser)).place(x=35, y=70)
        tk.Button(joycon_R_frame, text="HOME", width=5, command=lambda: UnitCommand.HOME().start(ser)).place(
            x=50, y=270
        )

        joycon_L_frame.grid(row=0, column=0)
        joycon_R_frame.grid(row=0, column=1)

        # button style settings
        for button in abxy_frame.winfo_children():
            self.applyButtonSetting(button)
        for button in hat_frame.winfo_children():
            self.applyButtonSetting(button)
        for button in [b for b in joycon_L_frame.winfo_children() if type(b) is tk.Button]:
            self.applyButtonColor(button)
        for button in [b for b in joycon_R_frame.winfo_children() if type(b) is tk.Button]:
            self.applyButtonColor(button)

        self._logger.debug("Create GUI controller")

    def applyButtonSetting(self, button):
        button["width"] = 7
        self.applyButtonColor(button)

    def applyButtonColor(self, button):
        button["bg"] = "#343434"
        button["fg"] = "#fff"

    def bind(self, event, func):
        self.window.bind(event, func)

    def protocol(self, event, func):
        self.window.protocol(event, func)

    def focus_force(self):
        self.window.focus_force()

    def destroy(self):
        self.window.destroy()
        self._logger.debug("GUI controller destroyed")


# To avoid the error says 'ScrolledText' object has no attribute 'flush'
class MyScrolledText(ScrolledText):
    def flush(self):
        pass
