#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import datetime
import sys
import os
import re
import shutil
from os.path import dirname, abspath
import cv2
import numpy as np
import platform
import subprocess
import threading
import webbrowser
from pathlib import Path
import tkinter.ttk as ttk
import tkinter.messagebox as tkmsg
import Constant
from serial.tools import list_ports
from logging import getLogger, DEBUG, NullHandler

try:
    from plyer import notification

    flag_import_plyer = True
except Exception:
    flag_import_plyer = False
from Camera import Camera
import Settings
from CommandLoader import CommandLoader, FileCommandLoader
from GuiAssets import CaptureArea, ControllerGUI
from VisionAutomation import VisionAutomation
from AudioMonitor import AudioMonitor
from Recording import CaptureRecorder
from PIL import Image, ImageTk, ImageDraw
from KeyConfig import PokeKeycon
from Keyboard import SwitchKeyboardController
from LineNotify import Line_Notify
from DiscordNotify import Discord_Notify
from ExternalTools import SocketCommunications, MQTTCommunications
from Menubar import PokeController_Menubar
import PokeConLogger
import Utility as util
from Commands import McuCommandBase, PythonCommandBase, PythonSampleCommand, Sender
from Commands.Keys import KeyPress, Button, Hat, Stick, Direction
from Commands.ProController import ProController
from Commands.CommandBase import Command

addpath = dirname(dirname(dirname(abspath(__file__))))  # SerialControllerフォルダのパス
sys.path.append(addpath)


class PokeControllerApp:
    def __init__(self, master=None, profile="default"):
        self._logger = getLogger(__name__)
        self._logger.addHandler(NullHandler())

        self._logger.setLevel(DEBUG)
        self._logger.propagate = True

        self._logger.debug(f"User Profile Name: '{profile}'")

        self.root = master
        self.root.title(f"{Constant.NAME} ver.{Constant.VERSION} (profile: {args.profile})")
        # self.root.resizable(0, 0)
        self.controller = None
        self.poke_treeview = None
        self.keyPress = None
        self.keyboard = None

        self.camera_dic = None
        self.vision = VisionAutomation(os.path.join("Commands", "PythonCommands", "Samples", "vision_rules.json"))
        self.audio_monitor = AudioMonitor()
        self.recorder = CaptureRecorder()
        self.record_trigger_rules = []
        self.record_cleanup_rules = []
        # Template mode is an armed detector.  It must not create a file
        # until the configured image is actually found.
        self.record_armed = False
        self._last_vision_text = ""
        self.Line = None
        self.Discord = None

        self.procon = None

        self.pokeconname = Constant.NAME
        self.pokeconversion = Constant.VERSION

        self.profile = profile
        Command.app_name = f"{Constant.NAME} ver.{Constant.VERSION}"
        Command.profilename = profile

        """
        ここから
        """
        # build ui
        self.main_frame = ttk.Frame(master)
        self.camera_lf = ttk.Labelframe(self.main_frame)
        self.top_command_f = ttk.Frame(self.camera_lf)
        self.start_top_button = ttk.Button(self.top_command_f)
        self.start_top_button.configure(text="Start")
        self.start_top_button.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.start_top_button.configure(command=self.startPlay)
        self.simplecon_top_button = ttk.Button(self.top_command_f)
        self.simplecon_top_button.configure(text="Controller")
        self.simplecon_top_button.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.simplecon_top_button.configure(command=self.createControllerWindow)
        self.clear_top_button = ttk.Button(self.top_command_f)
        self.clear_top_button.configure(text="Clear Outputs")
        self.clear_top_button.grid(column="2", padx="5", pady="5", row="0")
        self.clear_top_button.configure(command=self.clearOutputs)
        self.capture_button = ttk.Button(self.top_command_f)
        self.capture_button.configure(text="Capture")
        self.capture_button.grid(column="3", padx="5", pady="5", row="0", sticky="ew")
        self.capture_button.configure(command=self.saveCapture)
        self.open_capture_button = ttk.Button(self.top_command_f)
        self.open_folder_img = tk.PhotoImage(file="./assets/icons8-OpenDir-16.png")  # modified
        self.open_capture_button.configure(image=self.open_folder_img)  # modified
        self.open_capture_button.grid(column="4", pady="5", row="0")
        self.open_capture_button.configure(command=self.OpenCaptureDir)
        # self.line_button = ttk.Button(self.top_command_f)
        # self.line_button.configure(text='Line')
        # self.line_button.grid(column='5', padx='5', pady='5', row='0', sticky='ew')
        # self.line_button.configure(command=self.sendLineImage)
        self.discord_button = ttk.Button(self.top_command_f)
        self.discord_button.configure(text="Discord")
        self.discord_button.grid(column="5", padx="5", pady="5", row="0", sticky="ew")
        self.discord_button.configure(command=self.sendDiscordImage)
        self.html_button = ttk.Button(self.top_command_f, text="Open HTML")
        self.html_button.grid(column="6", padx="5", pady="5", row="0", sticky="ew")
        self.html_button.configure(command=self.open_html_output)
        self.top_command_f.grid(column="0", row="0", sticky="w")
        self.top_command_f.grid_anchor("center")
        self.canvas_frame = ttk.Frame(self.camera_lf)
        self.canvas_frame.configure(height="360", relief="groove", width="640")
        self.canvas_frame.grid(column="0", columnspan="7", row="1")
        self.camera_lf.configure(text="Main Panel")  # modfied
        self.camera_lf.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.camera_lf.rowconfigure("0", uniform="0")
        self.controller_nb = ttk.Notebook(self.main_frame)
        self.camera_f = ttk.Frame(self.controller_nb)
        self.camera_settings_lf = ttk.Labelframe(self.camera_f)
        self.camera_id_label = ttk.Label(self.camera_settings_lf)
        self.camera_id_label.configure(anchor="center", text="Camera ID: ")
        self.camera_id_label.grid(column="0", padx="5", pady="5", row="1", sticky="ew")
        self.camera_id_entry = ttk.Entry(self.camera_settings_lf)
        self.camera_id = tk.IntVar(value="")
        self.camera_id_entry.configure(state="readonly", textvariable=self.camera_id, width="3")
        self.camera_id_entry.grid(column="1", padx="5", pady="5", row="1", sticky="ew")
        self.camera_separator_1 = ttk.Separator(self.camera_settings_lf)
        self.camera_separator_1.configure(orient="vertical")
        self.camera_separator_1.grid(column="2", padx="5", pady="5", row="1", sticky="ns")
        self.fps_label = ttk.Label(self.camera_settings_lf)
        self.fps_label.configure(text="FPS: ")
        self.fps_label.grid(column="3", padx="5", pady="5", row="1", sticky="ew")
        self.fps_cb = ttk.Combobox(self.camera_settings_lf)
        self.fps = tk.StringVar(value="")
        self.fps_cb.configure(justify="left", state="readonly", textvariable=self.fps, values="60 45 30 15 5")
        self.fps_cb.configure(width="3")
        self.fps_cb.grid(column="4", padx="10", pady="5", row="1", sticky="ew")
        self.fps_cb.bind("<<ComboboxSelected>>", self.applyFps, add="")
        self.camera_separator_2 = ttk.Separator(self.camera_settings_lf)
        self.camera_separator_2.configure(orient="vertical")
        self.camera_separator_2.grid(column="5", padx="5", pady="5", row="1", sticky="ns")
        self.show_size_label = ttk.Label(self.camera_settings_lf)
        self.show_size_label.configure(text="Show Size: ")
        self.show_size_label.grid(column="6", padx="5", pady="5", row="1", sticky="ew")
        self.show_size_cb = ttk.Combobox(self.camera_settings_lf)
        self.show_size = tk.StringVar(value="")
        show_size_list = ["320x180", "640x360", "960x540", "1280x720", "1600x900", "1920x1080"]
        self.show_size_cb.configure(state="readonly", textvariable=self.show_size, values=show_size_list)
        self.show_size_cb.grid(column="7", padx="5", row="1", sticky="ew")
        self.show_size_cb.bind("<<ComboboxSelected>>", self.applyWindowSize, add="")
        self.camera_separator_3 = ttk.Separator(self.camera_settings_lf)
        self.camera_separator_3.configure(orient="vertical")
        self.camera_separator_3.grid(column="8", padx="5", pady="5", row="1", sticky="ns")
        self.reload_button = ttk.Button(self.camera_settings_lf)
        self.reload_button.configure(text="Reload Camera")
        self.reload_button.grid(column="9", padx="5", pady="5", row="1", sticky="ew")
        self.reload_button.configure(command=self.openCamera)
        self.camera_name_label = ttk.Label(self.camera_settings_lf)
        self.camera_name_label.configure(anchor="center", text="Camera Name: ")
        self.camera_name_label.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.camera_name_cb = ttk.Combobox(self.camera_settings_lf)
        self.camera_name_fromDLL = tk.StringVar(value="")
        self.camera_name_cb.configure(state="normal", textvariable=self.camera_name_fromDLL)
        self.camera_name_cb.grid(column="1", columnspan="9", padx="5", pady="5", row="0", sticky="ew")
        self.camera_name_cb.bind("<<ComboboxSelected>>", self.set_cameraid, add="")
        self.camera_settings_lf.configure(text="Settings", width="420")
        self.camera_settings_lf.grid(column="0", padx="5", row="0", sticky="nw")
        self.display_settings_lf = ttk.Labelframe(self.camera_f)
        self.show_realtime_checkbox = ttk.Checkbutton(self.display_settings_lf)
        self.is_show_realtime = tk.BooleanVar()  # modified
        self.show_realtime_checkbox.configure(text="Show Realtime", variable=self.is_show_realtime)
        self.show_realtime_checkbox.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.show_value_checkbox = ttk.Checkbutton(self.display_settings_lf)
        self.is_show_value = tk.BooleanVar()  # modified
        self.show_value_checkbox.configure(text="Show Value", variable=self.is_show_value)
        self.show_value_checkbox.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.show_value_checkbox.configure(command=self.mode_change_show_value)
        self.show_guide_checkbox = ttk.Checkbutton(self.display_settings_lf)
        self.is_show_guide = tk.BooleanVar()  # modified
        self.show_guide_checkbox.configure(text="Show Guide", variable=self.is_show_guide)
        self.show_guide_checkbox.grid(column="2", padx="5", pady="5", row="0", sticky="ew")
        self.show_guide_checkbox.configure(command=self.mode_change_show_guide)
        # Audio is intentionally separate from camera/display settings.
        self.audio_f = ttk.Frame(self.controller_nb)
        self.audio_lf = ttk.Labelframe(self.audio_f, text="Capture Audio")
        self.audio_filter_camera = tk.BooleanVar(value=False)
        self.audio_filter_checkbox = ttk.Checkbutton(
            self.audio_lf, text="カメラ名に類似する音声のみ", variable=self.audio_filter_camera,
            command=self.update_audio_input_list,
        )
        self.audio_filter_checkbox.grid(column=0, row=0, columnspan=2, padx=5, pady=(3, 0), sticky="w")
        self.audio_auto_start = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.audio_lf, text="Start audio on launch", variable=self.audio_auto_start).grid(
            column=3, row=0, padx=5, pady=(3, 0), sticky="w"
        )
        ttk.Button(self.audio_lf, text="Refresh", command=self.refresh_audio_devices).grid(column=2, row=0, padx=5, pady=(3, 0))
        ttk.Label(self.audio_lf, text="Audio In:").grid(column=0, row=1, padx=(5, 2), pady=5, sticky="e")
        self.audio_input = tk.StringVar()
        self.audio_input_cb = ttk.Combobox(self.audio_lf, textvariable=self.audio_input, width=100, state="readonly")
        self.audio_input_cb.grid(column=1, columnspan=4, row=1, padx=2, pady=5, sticky="ew")
        self.audio_lf.columnconfigure(1, weight=1)
        self.audio_device_full_name = tk.StringVar(value="")
        ttk.Label(self.audio_lf, textvariable=self.audio_device_full_name, anchor="w", foreground="#404040").grid(
            column=1, columnspan=4, row=2, padx=2, pady=(0, 3), sticky="ew"
        )
        self.audio_input.trace_add("write", self._show_full_audio_device_name)
        self.audio_gain = tk.IntVar(value=100)
        ttk.Label(self.audio_lf, text="Gain:").grid(column=0, row=3, padx=(5, 2), pady=(0, 5), sticky="e")
        ttk.Spinbox(self.audio_lf, from_=0, to=400, increment=10, textvariable=self.audio_gain, width=5).grid(column=1, row=3, padx=(2, 2), pady=(0, 5), sticky="w")
        ttk.Label(self.audio_lf, text="%").grid(column=1, row=3, padx=(58, 0), pady=(0, 5), sticky="w")
        self.audio_start_button = ttk.Button(self.audio_lf, text="Start audio", command=self.start_audio_monitor)
        self.audio_start_button.grid(column=1, row=3, padx=(86, 2), pady=(0, 5), sticky="w")
        ttk.Button(self.audio_lf, text="Stop", command=self.stop_audio_monitor).grid(column=1, row=3, padx=(180, 0), pady=(0, 5), sticky="w")
        self.refresh_audio_devices()
        self.display_settings_lf.configure(height="200", text="Display Settings", width="200")
        self.display_settings_lf.grid(column="1", padx="5", pady="0", row="0", sticky="nw")
        self.camera_f.columnconfigure(0, weight=0)
        self.camera_f.columnconfigure(1, weight=1)
        self.analysis_f = ttk.Frame(self.controller_nb)
        self.vision_lf = ttk.Labelframe(self.analysis_f, text="Screen analysis / mode")
        self.vision_mode = tk.StringVar(value="default")
        self.vision_mode_cb = ttk.Combobox(self.vision_lf, state="readonly", width="15", textvariable=self.vision_mode,
                                           values=list(self.vision.modes.keys()))
        self.vision_mode_cb.grid(column=0, row=0, padx=5, pady=5)
        self.vision_mode_cb.bind("<<ComboboxSelected>>", self.change_vision_mode)
        ttk.Button(self.vision_lf, text="Reload rules", command=self.reload_vision_rules).grid(column=1, row=0, padx=5, pady=5)
        ttk.Label(self.vision_lf, text="Template detection / HP bar → Output#2 (no key input)").grid(column=2, row=0, padx=5, pady=5)
        self.vision_lf.grid(column=0, padx=5, pady=5, sticky="ew")
        # self.camera_f.configure(height='200', width='200')    # removed
        self.camera_f.pack(side="top")
        self.controller_nb.add(self.camera_f, padding="5", sticky="nsew", text="Camera")
        self.area_capture_f = ttk.Frame(self.controller_nb)
        self.area_capture_lf = ttk.Labelframe(self.area_capture_f, text="Capture selected camera area")
        ttk.Label(self.area_capture_lf, text="ROI x,y,w,h:").grid(column=0, row=0, padx=5, pady=5, sticky="w")
        self.area_capture_roi = tk.StringVar(value="0,0,0,0")
        self.area_capture_roi.trace_add("write", self.area_capture_roi_changed)
        self.area_capture_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.area_capture_lf, text="Active live preview", variable=self.area_capture_active,
                        command=self.toggle_area_capture_active).grid(column=4, row=1, padx=5, pady=2, sticky="w")
        ttk.Entry(self.area_capture_lf, textvariable=self.area_capture_roi, width=20).grid(column=1, row=0, padx=5, pady=5, sticky="w")
        ttk.Button(self.area_capture_lf, text="Capture area", command=self.save_area_capture).grid(column=2, row=0, padx=5, pady=5)
        ttk.Button(self.area_capture_lf, text="Open folder", command=self.open_area_capture_dir).grid(column=3, row=0, padx=5, pady=5)
        ttk.Label(self.area_capture_lf, text="Preview panel:").grid(column=0, row=1, padx=5, pady=2, sticky="w")
        self.area_capture_output_target = tk.StringVar(value="Output#1")
        self.area_capture_output_cb = ttk.Combobox(self.area_capture_lf, state="readonly", width=24,
                                                    textvariable=self.area_capture_output_target)
        self.area_capture_output_cb.grid(column=1, row=1, padx=5, pady=2, sticky="w")
        self.area_capture_output_cb.bind("<<ComboboxSelected>>", self.select_area_capture_preview)
        ttk.Label(self.area_capture_lf, text="Arrow move(px):").grid(column=2, row=1, padx=5, pady=2, sticky="e")
        self.area_capture_step = tk.IntVar(value=5)
        ttk.Spinbox(self.area_capture_lf, from_=1, to=200, textvariable=self.area_capture_step, width=5).grid(column=3, row=1, padx=5, pady=2, sticky="w")
        ttk.Button(self.area_capture_lf, text="Preview / edit...", command=self.open_area_capture_editor).grid(column=0, row=2, padx=5, pady=2, sticky="w")
        ttk.Label(self.area_capture_lf, text="Preview background:").grid(column=1, row=2, padx=5, pady=2, sticky="e")
        self.area_capture_background = tk.StringVar(value="#ffffff")
        self.area_capture_background.trace_add("write", self.apply_area_capture_background)
        ttk.Entry(self.area_capture_lf, textvariable=self.area_capture_background, width=10).grid(column=2, row=2, padx=2, pady=2, sticky="w")
        ttk.Button(self.area_capture_lf, text="Color...", command=self.choose_area_capture_background).grid(column=3, row=2, padx=5, pady=2, sticky="w")
        self.area_capture_status = tk.StringVar(value="")
        ttk.Label(self.area_capture_lf, textvariable=self.area_capture_status).grid(column=0, columnspan=5, row=3, padx=5, pady=(0, 5), sticky="w")
        self.area_capture_lf.pack(fill="x", padx=5, pady=5)
        self.area_capture_f.pack(side="top", fill="both", expand=True)
        self.controller_nb.add(self.area_capture_f, padding="5", sticky="nsew", text="Area Capture")
        self.audio_lf.pack(fill="x", padx=5, pady=5)
        self.audio_f.pack(side="top", fill="both", expand=True)
        self.controller_nb.add(self.audio_f, padding="5", sticky="nsew", text="Audio")
        self.analysis_f.pack(side="top", fill="both", expand=True)
        self.controller_nb.add(self.analysis_f, padding="5", sticky="nsew", text="Analysis")
        self.presets_f = ttk.Frame(self.controller_nb)
        self.presets_lf = ttk.Labelframe(self.presets_f, text="Saved setting sets")
        ttk.Label(self.presets_lf, text="Set name:").grid(column=0, row=0, padx=5, pady=5)
        self.preset_name = tk.StringVar()
        self.preset_cb = ttk.Combobox(self.presets_lf, textvariable=self.preset_name, width=32)
        self.preset_cb.grid(column=1, row=0, padx=5, pady=5)
        ttk.Button(self.presets_lf, text="Save all tabs", command=self.save_preset).grid(column=2, row=0, padx=5, pady=5)
        ttk.Button(self.presets_lf, text="Load", command=self.load_preset).grid(column=3, row=0, padx=5, pady=5)
        ttk.Button(self.presets_lf, text="Delete", command=self.delete_preset).grid(column=4, row=0, padx=5, pady=5)
        ttk.Button(self.presets_lf, text="Refresh", command=self.refresh_presets).grid(column=5, row=0, padx=5, pady=5)
        ttk.Label(self.presets_lf, text="Load applies the entire linked set after restarting PokeCon.").grid(column=0, columnspan=6, row=1, padx=5, pady=(0, 5), sticky="w")
        self.presets_lf.pack(fill="x", padx=5, pady=5)
        self.presets_f.pack(side="top", fill="both", expand=True)
        self.controller_nb.add(self.presets_f, padding="5", sticky="nsew", text="Presets")
        self.recording_f = ttk.Frame(self.controller_nb)
        self.recording_lf = ttk.Labelframe(self.recording_f, text="Video + audio recording")
        self.record_mode = tk.StringVar(value="Manual")
        ttk.Radiobutton(self.recording_lf, text="Manual", value="Manual", variable=self.record_mode).grid(column=0, row=0, padx=5, pady=5)
        ttk.Radiobutton(self.recording_lf, text="Template segments", value="Template", variable=self.record_mode).grid(column=1, row=0, padx=5, pady=5)
        ttk.Radiobutton(self.recording_lf, text="Command variable segments", value="Variable", variable=self.record_mode).grid(column=2, row=0, padx=5, pady=5)
        self.record_button = ttk.Button(self.recording_lf, text="Start recording", command=self.toggle_recording)
        self.record_button.grid(column=3, row=0, padx=5, pady=5)
        ttk.Button(self.recording_lf, text="Output layout...", command=self.open_recording_output_layout).grid(column=4, row=0, padx=5, pady=5)
        self.record_output_mode = tk.StringVar(value="Video only")
        self.record_output_logs = tk.StringVar(value="Output#1")
        self.record_output_guide = tk.BooleanVar(value=False)
        self.record_output_value = tk.BooleanVar(value=False)
        ttk.Label(self.recording_lf, text="Template:").grid(column=0, row=1, padx=5, pady=5)
        self.record_template_path = tk.StringVar()
        ttk.Entry(self.recording_lf, textvariable=self.record_template_path, width=34).grid(column=1, columnspan=5, row=1, sticky="ew")
        ttk.Button(self.recording_lf, text="Browse", command=self.choose_record_template).grid(column=6, row=1, padx=3)
        ttk.Button(self.recording_lf, text="Rules...", command=self.open_recording_rules).grid(column=7, row=1, padx=3)
        self.record_threshold = tk.DoubleVar(value=0.9)
        self.record_interval = tk.DoubleVar(value=0.5)
        self.record_release = tk.DoubleVar(value=1.0)
        ttk.Label(self.recording_lf, text="Threshold").grid(column=0, row=2, padx=(5, 2))
        ttk.Spinbox(self.recording_lf, from_=0.1, to=1.0, increment=0.05, textvariable=self.record_threshold, width=5).grid(column=1, row=2, sticky="w")
        ttk.Label(self.recording_lf, text="Interval(s)").grid(column=2, row=2, padx=(8, 2))
        ttk.Spinbox(self.recording_lf, from_=0.1, to=5.0, increment=0.1, textvariable=self.record_interval, width=5).grid(column=3, row=2, sticky="w")
        ttk.Label(self.recording_lf, text="Absent(s)").grid(column=4, row=2, padx=(8, 2))
        ttk.Spinbox(self.recording_lf, from_=0.1, to=30.0, increment=0.5, textvariable=self.record_release, width=5).grid(column=5, row=2, sticky="w")
        ttk.Label(self.recording_lf, text="ROI x,y,w,h").grid(column=6, row=2, padx=(8, 2))
        self.record_roi = tk.StringVar(value="0,0,0,0")
        self.record_minimum_duration = tk.DoubleVar(value=0.0)
        ttk.Entry(self.recording_lf, textvariable=self.record_roi, width=13).grid(column=7, row=2, sticky="w")
        self.record_debug = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.recording_lf, text="Show detection debug", variable=self.record_debug,
                        command=self.toggle_record_debug).grid(column=5, row=0, padx=5, pady=3, sticky="w")
        self.record_debug_status = tk.StringVar(value="Debug: disabled")
        ttk.Label(self.recording_lf, textvariable=self.record_debug_status).grid(
            column=6, columnspan=2, row=0, padx=5, pady=3, sticky="w"
        )
        self.record_variable_command = tk.StringVar()
        self.record_variable_name = tk.StringVar(value="current_step")
        self.record_variable_start = tk.StringVar()
        self.record_variable_stop = tk.StringVar()
        self.record_variable_status = tk.StringVar(value="Variable segments: inactive")
        ttk.Label(self.recording_lf, text="Variable command:").grid(column=0, row=4, padx=(5, 2), pady=3, sticky="w")
        self.record_variable_command_cb = ttk.Combobox(self.recording_lf, state="readonly", width=28, textvariable=self.record_variable_command)
        self.record_variable_command_cb.grid(column=1, columnspan=2, row=4, padx=2, pady=3, sticky="w")
        ttk.Label(self.recording_lf, text="Variable:").grid(column=3, row=4, padx=(5, 2), pady=3, sticky="w")
        ttk.Entry(self.recording_lf, textvariable=self.record_variable_name, width=16).grid(column=4, row=4, padx=2, pady=3, sticky="w")
        ttk.Label(self.recording_lf, text="Start value:").grid(column=5, row=4, padx=(5, 2), pady=3, sticky="w")
        ttk.Entry(self.recording_lf, textvariable=self.record_variable_start, width=16).grid(column=6, row=4, padx=2, pady=3, sticky="w")
        ttk.Label(self.recording_lf, text="Stop value:").grid(column=0, row=5, padx=(5, 2), pady=3, sticky="w")
        ttk.Entry(self.recording_lf, textvariable=self.record_variable_stop, width=16).grid(column=1, row=5, padx=2, pady=3, sticky="w")
        ttk.Label(self.recording_lf, text="Exact values; e.g. 1_1 → 2").grid(column=2, columnspan=3, row=5, padx=4, pady=3, sticky="w")
        ttk.Label(self.recording_lf, textvariable=self.record_variable_status).grid(column=5, columnspan=3, row=5, padx=4, pady=3, sticky="w")
        ttk.Label(self.recording_lf, text="Recording set:").grid(column=0, row=3, padx=(5, 2), pady=(3, 5), sticky="w")
        self.recording_preset_name = tk.StringVar()
        self.recording_preset_cb = ttk.Combobox(self.recording_lf, textvariable=self.recording_preset_name, width=18)
        self.recording_preset_cb.grid(column=1, columnspan=2, row=3, padx=2, pady=(3, 5), sticky="w")
        ttk.Button(self.recording_lf, text="Save", command=self.save_recording_preset).grid(column=3, row=3, padx=2, pady=(3, 5))
        ttk.Button(self.recording_lf, text="Load", command=self.load_recording_preset).grid(column=4, row=3, padx=2, pady=(3, 5))
        ttk.Button(self.recording_lf, text="Delete", command=self.delete_recording_preset).grid(column=5, row=3, padx=2, pady=(3, 5))
        self.recording_lf.pack(fill="x", padx=5, pady=5)
        self.recording_f.pack(side="top", fill="both", expand=True)
        self.controller_nb.add(self.recording_f, padding="5", sticky="nsew", text="Recording")
        self._build_input_set_tab()
        self.serial_f = ttk.Frame(self.controller_nb)
        self.settings_lf = ttk.Labelframe(self.serial_f)
        self.com_port_label = ttk.Label(self.settings_lf)
        if platform.system() == "Windows" or platform.system() == "Darwin":
            self.com_port_label.configure(text="COM Port: ")
        else:
            self.com_port_label.configure(text="Port: ")
        self.com_port_label.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        # self.label2.rowconfigure('0', uniform='None', weight='0')   # added
        self.com_port_entry = ttk.Entry(self.settings_lf)
        self.com_port = tk.IntVar(value="")
        self.com_port_name = tk.StringVar()  # added
        self.com_port_entry.configure(state="readonly", textvariable=self.com_port, width="5")
        self.com_port_entry.grid(column="1", padx="10", pady="5", row="0", sticky="ew")
        # self.ecom_port_entryntry2.rowconfigure('0', uniform='None', weight='0')   # added
        self.settings_separator_1 = ttk.Separator(self.settings_lf)
        self.settings_separator_1.configure(orient="vertical")
        self.settings_separator_1.grid(column="2", pady="5", row="0", sticky="ns")
        self.baud_rate_label = ttk.Label(self.settings_lf)
        self.baud_rate_label.configure(text="Baud Rate: ")
        self.baud_rate_label.grid(column="3", padx="5", pady="5", row="0", sticky="ew")
        self.baud_rate_cb = ttk.Combobox(self.settings_lf)
        self.baud_rate = tk.StringVar(value="")
        self.baud_rate_cb.configure(
            justify="right", state="readonly", textvariable=self.baud_rate, values="9600 4800 115200"
        )
        self.baud_rate_cb.configure(width="6")
        self.baud_rate_cb.grid(column="4", padx="10", pady="5", row="0", sticky="ew")
        self.baud_rate_cb.bind("<<ComboboxSelected>>", self.applyBaudRate, add="")
        self.settings_separator_2 = ttk.Separator(self.settings_lf)
        self.settings_separator_2.configure(orient="vertical")
        self.settings_separator_2.grid(column="5", pady="5", row="0", sticky="ns")
        self.reload_com_port_button = ttk.Button(self.settings_lf)
        self.reload_com_port_button.configure(text="Reload Port")
        self.reload_com_port_button.grid(column="6", padx="10", pady="5", row="0", sticky="ew")
        self.reload_com_port_button.configure(command=self.activateSerial)
        # self.reload_com_port.rowconfigure('0', uniform='None', weight='0')    # added
        self.disconnect_com_port_button = ttk.Button(self.settings_lf)
        self.disconnect_com_port_button.configure(text="Disconnect Port")
        self.disconnect_com_port_button.grid(column="7", padx="10", pady="5", row="0", sticky="ew")
        self.disconnect_com_port_button.configure(command=self.inactivateSerial)
        # self.disconnect_com_port_button.rowconfigure('0', uniform='None', weight='0') # added
        self.serial_device_name_label = ttk.Label(self.settings_lf)
        self.serial_device_name_label.configure(anchor="center", text="Device Name: ")
        self.serial_device_name_label.grid(column="0", padx="5", pady="5", row="1", sticky="ew")
        self.serial_device_name_cb = ttk.Combobox(self.settings_lf)
        self.serial_device_name = tk.StringVar(value="(選択してください)")
        self.serial_device_name_cb.configure(state="normal", textvariable=self.serial_device_name)
        self.serial_device_name_cb.grid(column="1", columnspan="6", padx="5", pady="5", row="1", sticky="ew")
        self.serial_device_name_cb.bind("<<ComboboxSelected>>", self.set_device, add="")
        self.scan_device_button = ttk.Button(self.settings_lf)
        self.scan_device_button.configure(text="Scan Device")
        self.scan_device_button.grid(column="7", padx="10", pady="3", row="1", sticky="ew")
        self.scan_device_button.configure(command=self.locateDeviceCmbbox)
        self.settings_lf.configure(text="Settings")
        self.settings_lf.grid(column="0", padx="5", row="0", sticky="ew")
        self.serial_data_lf = ttk.Labelframe(self.serial_f)
        self.serial_data_format_name_label = ttk.Label(self.serial_data_lf)
        self.serial_data_format_name_label.configure(anchor="center", text="Data Format: ")
        self.serial_data_format_name_label.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        serial_data_format_list = ["Default", "Qingpi", "3DS Controller"]
        self.serial_data_format_name_cb = ttk.Combobox(self.serial_data_lf)
        self.serial_data_format_name = tk.StringVar(value="Default")
        self.serial_data_format_name_cb.configure(
            state="normal", textvariable=self.serial_data_format_name, values=serial_data_format_list
        )
        self.serial_data_format_name_cb.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.serial_data_format_name_cb.bind("<<ComboboxSelected>>", self.set_serial_data_format)
        self.show_serial_checkbox = ttk.Checkbutton(self.serial_data_lf)
        self.is_show_serial = tk.BooleanVar()  # modified
        self.show_serial_checkbox.configure(text="Show Serial", variable=self.is_show_serial)
        self.show_serial_checkbox.grid(column="2", padx="5", pady="5", row="0", sticky="ew")
        self.serial_data_lf.configure(height="200", text="Data", width="200")
        self.serial_data_lf.grid(column="0", padx="5", row="1", sticky="ew")
        # self.serial_f.configure(height='200', width='200')    # removed
        self.serial_f.pack()
        self.controller_nb.add(self.serial_f, padding="5", sticky="nsew", text="Serial")
        self.manual_control_f = ttk.Frame(self.controller_nb)
        self.software_lf = ttk.Labelframe(self.manual_control_f)
        self.simplecon_button = ttk.Button(self.software_lf)
        self.simplecon_button.configure(text="Controller", width="15")
        self.simplecon_button.grid(column="0", padx="10", pady="5", row="0", sticky="ew")
        self.simplecon_button.configure(command=self.createControllerWindow)
        self.use_keyboard_checkbox = ttk.Checkbutton(self.software_lf)
        self.is_use_keyboard = tk.BooleanVar()  # modified
        self.use_keyboard_checkbox.configure(text="Use Keyboard", variable=self.is_use_keyboard)
        self.use_keyboard_checkbox.grid(column="0", padx="10", pady="5", row="1", sticky="ew")
        self.use_keyboard_checkbox.configure(command=self.activateKeyboard)
        self.left_stick_mouse_checkbox = ttk.Checkbutton(self.software_lf)
        self.camera_lf.is_use_left_stick_mouse = tk.BooleanVar()  # modified(継承いじるの面倒なので暫定的にこのまま)
        self.left_stick_mouse_checkbox.configure(
            text="Use LStick Mouse", variable=self.camera_lf.is_use_left_stick_mouse
        )  # modified
        self.left_stick_mouse_checkbox.grid(column="1", padx="10", pady="5", row="1", sticky="ew")
        self.left_stick_mouse_checkbox.configure(command=self.activate_Left_stick_mouse)
        self.right_stick_mouse_checkbox = ttk.Checkbutton(self.software_lf)
        self.camera_lf.is_use_right_stick_mouse = tk.BooleanVar()  # modified(継承いじるの面倒なので暫定的にこのまま)
        self.right_stick_mouse_checkbox.configure(
            text="Use RStick Mouse", variable=self.camera_lf.is_use_right_stick_mouse
        )  # modified
        self.right_stick_mouse_checkbox.grid(column="2", padx="10", pady="5", row="1", sticky="ew")
        self.right_stick_mouse_checkbox.configure(command=self.activate_Right_stick_mouse)
        self.software_lf.configure(height="200", text="Software")
        self.software_lf.grid(padx="5", sticky="ew")
        self.hardware_lf = ttk.Labelframe(self.manual_control_f)
        self.use_pro_controller_checkbox = ttk.Checkbutton(self.hardware_lf)
        self.is_use_Pro_Controller = tk.BooleanVar()  # modified
        self.use_pro_controller_checkbox.configure(text="Use Pro Controller", variable=self.is_use_Pro_Controller)
        self.use_pro_controller_checkbox.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.use_pro_controller_checkbox.configure(command=self.mode_change_Pro_Controller)
        self.record_pro_controller_checkbox = ttk.Checkbutton(self.hardware_lf)
        self.is_record_Pro_Controller = tk.BooleanVar()  # modified
        self.record_pro_controller_checkbox.configure(
            text="Record Pro Controller", variable=self.is_record_Pro_Controller
        )
        self.record_pro_controller_checkbox.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.record_pro_controller_checkbox.configure(command=self.record_Pro_Controller)
        self.hardware_lf.configure(height="200", text="Hardware", width="200")
        self.hardware_lf.grid(column="0", padx="5", row="1", sticky="ew")
        self.manual_control_f.configure(height="200", width="200")
        self.manual_control_f.pack()
        self.controller_nb.add(self.manual_control_f, padding="5", text="Manual Control")
        self.commands_f = ttk.Frame(self.controller_nb)
        self.select_commands_f = ttk.Frame(self.commands_f)
        self.command_nb = ttk.Notebook(self.select_commands_f)
        self.py_f = ttk.Frame(self.command_nb)
        self.command_filter_py_label = ttk.Label(self.py_f)
        self.command_filter_py_label.configure(text="Filter: ")
        self.command_filter_py_label.grid(column="0", padx="5", pady="4", row="0", sticky="ew")
        self.command_filter_py_cb = ttk.Combobox(self.py_f)
        self.command_filter_py_name = tk.StringVar(value="-")
        self.command_filter_py_cb.configure(state="readonly", textvariable=self.command_filter_py_name)
        self.command_filter_py_cb.grid(column="1", padx="5", pady="4", row="0", sticky="ew")
        self.command_filter_py_cb.bind("<<ComboboxSelected>>", self.applyFilterPy, add="")
        self.py_label = ttk.Label(self.py_f)
        self.py_label.configure(text="Command: ")
        self.py_label.grid(column="0", padx="5", pady="4", row="1", sticky="ew")
        self.py_cb = ttk.Combobox(self.py_f)
        self.py_name = tk.StringVar(value="")
        self.py_cb.configure(state="readonly", textvariable=self.py_name)
        self.py_cb.grid(column="1", padx="5", pady="4", row="1", sticky="ew")
        self.py_f.pack(fill="x", side="top")
        self.py_f.columnconfigure(1, weight=1)
        self.command_nb.add(self.py_f, padding="5", text="Python Command")
        self.sample_py_f = ttk.Frame(self.command_nb)
        ttk.Label(self.sample_py_f, text="Filter: ").grid(column="0", padx="5", pady="4", row="0", sticky="ew")
        self.command_filter_sample_py_name = tk.StringVar(value="-")
        self.command_filter_sample_py_cb = ttk.Combobox(
            self.sample_py_f, state="readonly", textvariable=self.command_filter_sample_py_name)
        self.command_filter_sample_py_cb.grid(column="1", padx="5", pady="4", row="0", sticky="ew")
        self.command_filter_sample_py_cb.bind("<<ComboboxSelected>>", self.applyFilterSamplePy, add="")
        ttk.Label(self.sample_py_f, text="Command: ").grid(column="0", padx="5", pady="4", row="1", sticky="ew")
        self.sample_py_name = tk.StringVar(value="")
        self.sample_py_cb = ttk.Combobox(self.sample_py_f, state="readonly", textvariable=self.sample_py_name)
        self.sample_py_cb.grid(column="1", padx="5", pady="4", row="1", sticky="ew")
        self.sample_py_f.pack(fill="x", side="top")
        self.sample_py_f.columnconfigure(1, weight=1)
        self.command_nb.add(self.sample_py_f, padding="5", text="Python Sample Command")
        self.mcu_f = ttk.Frame(self.command_nb)
        self.command_filter_mcu_label = ttk.Label(self.mcu_f)
        self.command_filter_mcu_label.configure(text="Filter: ")
        self.command_filter_mcu_label.grid(column="0", padx="5", pady="4", row="0", sticky="ew")
        self.command_filter_mcu_cb = ttk.Combobox(self.mcu_f)
        self.command_filter_mcu_name = tk.StringVar(value="-")
        self.command_filter_mcu_cb.configure(state="readonly", textvariable=self.command_filter_mcu_name)
        self.command_filter_mcu_cb.grid(column="1", padx="5", pady="4", row="0", sticky="ew")
        self.command_filter_mcu_cb.bind("<<ComboboxSelected>>", self.applyFilterMcu, add="")
        self.mcu_label = ttk.Label(self.mcu_f)
        self.mcu_label.configure(text="Command: ")
        self.mcu_label.grid(column="0", padx="5", pady="4", row="1", sticky="ew")
        self.mcu_cb = ttk.Combobox(self.mcu_f)
        self.mcu_name = tk.StringVar(value="")
        self.mcu_cb.configure(state="readonly", textvariable=self.mcu_name, validate="focusin")
        self.mcu_cb.grid(column="1", padx="5", pady="4", row="1", sticky="ew")
        self.mcu_f.pack(fill="x", side="top")
        self.mcu_f.columnconfigure(1, weight=1)
        self.command_nb.add(self.mcu_f, padding="5", text="Mcu Command")
        self.shortcut_f = ttk.Frame(self.command_nb)
        self.shortcut1_f = ttk.Frame(self.shortcut_f)
        self.shortcut_button_1 = ttk.Button(self.shortcut1_f)
        self.shortcut_1 = tk.StringVar(value="Shortcut(1)")
        self.shortcut_button_1.configure(textvariable=self.shortcut_1, width="7")
        self.shortcut_button_1.pack(expand="true", fill="both", padx="5", side="left")
        self.shortcut_button_1.configure(command=lambda: self.startShortcutPlay(num=1))
        self.shortcut_button_2 = ttk.Button(self.shortcut1_f)
        self.shortcut_2 = tk.StringVar(value="Shortcut(2)")
        self.shortcut_button_2.configure(textvariable=self.shortcut_2, width="7")
        self.shortcut_button_2.pack(expand="true", fill="both", padx="5", side="left")
        self.shortcut_button_2.configure(command=lambda: self.startShortcutPlay(num=2))
        self.shortcut_button_3 = ttk.Button(self.shortcut1_f)
        self.shortcut_3 = tk.StringVar(value="Shortcut(3)")
        self.shortcut_button_3.configure(textvariable=self.shortcut_3, width="7")
        self.shortcut_button_3.pack(expand="true", fill="both", padx="5", side="left")
        self.shortcut_button_3.configure(command=lambda: self.startShortcutPlay(num=3))
        self.shortcut_button_4 = ttk.Button(self.shortcut1_f)
        self.shortcut_4 = tk.StringVar(value="Shortcut(4)")
        self.shortcut_button_4.configure(textvariable=self.shortcut_4, width="7")
        self.shortcut_button_4.pack(expand="true", fill="both", padx="5", side="left")
        self.shortcut_button_4.configure(command=lambda: self.startShortcutPlay(num=4))
        self.shortcut_button_5 = ttk.Button(self.shortcut1_f)
        self.shortcut_5 = tk.StringVar(value="Shortcut(5)")
        self.shortcut_button_5.configure(textvariable=self.shortcut_5, width="7")
        self.shortcut_button_5.pack(expand="true", fill="both", padx="5", side="left")
        self.shortcut_button_5.configure(command=lambda: self.startShortcutPlay(num=5))
        self.shortcut1_f.configure(padding="2")
        self.shortcut1_f.pack(side="top", expand="true", fill="both")
        self.shortcut2_f = ttk.Frame(self.shortcut_f)
        self.shortcut_button_6 = ttk.Button(self.shortcut2_f)
        self.shortcut_6 = tk.StringVar(value="Shortcut(6)")
        self.shortcut_button_6.configure(textvariable=self.shortcut_6, width="7")
        self.shortcut_button_6.pack(expand="true", fill="both", padx="5", side="left")
        self.shortcut_button_6.configure(command=lambda: self.startShortcutPlay(num=6))
        self.shortcut_button_7 = ttk.Button(self.shortcut2_f)
        self.shortcut_7 = tk.StringVar(value="Shortcut(7)")
        self.shortcut_button_7.configure(textvariable=self.shortcut_7, width="7")
        self.shortcut_button_7.pack(expand="true", fill="both", padx="5", side="left")
        self.shortcut_button_7.configure(command=lambda: self.startShortcutPlay(num=7))
        self.shortcut_button_8 = ttk.Button(self.shortcut2_f)
        self.shortcut_8 = tk.StringVar(value="Shortcut(8)")
        self.shortcut_button_8.configure(textvariable=self.shortcut_8, width="7")
        self.shortcut_button_8.pack(expand="true", fill="both", padx="5", side="left")
        self.shortcut_button_8.configure(command=lambda: self.startShortcutPlay(num=8))
        self.shortcut_button_9 = ttk.Button(self.shortcut2_f)
        self.shortcut_9 = tk.StringVar(value="Shortcut(9)")
        self.shortcut_button_9.configure(textvariable=self.shortcut_9, width="7")
        self.shortcut_button_9.pack(expand="true", fill="both", padx="5", side="left")
        self.shortcut_button_9.configure(command=lambda: self.startShortcutPlay(num=9))
        self.shortcut_button_10 = ttk.Button(self.shortcut2_f)
        self.shortcut_10 = tk.StringVar(value="Shortcut(10)")
        self.shortcut_button_10.configure(textvariable=self.shortcut_10, width="7")
        self.shortcut_button_10.pack(expand="true", fill="both", padx="5", side="left")
        self.shortcut_button_10.configure(command=lambda: self.startShortcutPlay(num=10))
        self.shortcut2_f.configure(padding="2")
        self.shortcut2_f.pack(side="top", expand="true", fill="both")
        self.command_nb.add(self.shortcut_f, padding="5", text="Shortcut")
        self.command_nb.configure(padding="0", width="580")
        self.command_nb.pack(padx="5", pady="5", side="left")
        self.command_nb.pack(fill="both", expand=True, padx="5", pady="5", side="left")
        self.command_nb.bind("<<NotebookTabChanged>>", self.controllButtons, add="")
        self.open_command_dir_button = ttk.Button(self.select_commands_f)
        self.open_command_dir_button.config(image=self.open_folder_img)
        self.open_command_dir_button.pack(expand=False, side="left", ipadx="5", pady="15")
        self.open_command_dir_button.configure(command=self.OpenCommandDir)
        # self.select_commands_f.configure(height='200', width='200')
        self.select_commands_f.grid(column="0", row="0", sticky="ew")
        self.action_commands_f = ttk.Frame(self.commands_f)
        self.set_shortcut_label = ttk.Label(self.action_commands_f)
        self.set_shortcut_label.configure(text="Set Shortcut: ")
        self.set_shortcut_label.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.set_shortcut_num_sb = ttk.Spinbox(self.action_commands_f)
        self.set_shortcut_num = tk.StringVar(value="")
        self.set_shortcut_num_sb.configure(from_="1", increment="1", justify="left", textvariable=self.set_shortcut_num)
        self.set_shortcut_num_sb.configure(to="10", width="7")
        self.set_shortcut_num_sb.delete("0", "end")
        self.set_shortcut_num_sb.insert("0", """(select)""")
        self.set_shortcut_num_sb.grid(column="1", row="0", sticky="ew")
        self.shortcut_set_button = ttk.Button(self.action_commands_f)
        self.shortcut_set_button.configure(takefocus=False, text="Set")
        self.shortcut_set_button.grid(column="2", padx="10", pady="5", row="0", sticky="ew")
        self.shortcut_set_button.configure(command=self.assignShortcutButton)
        self.commands_separator_1 = ttk.Separator(self.action_commands_f)
        self.commands_separator_1.configure(orient="vertical")
        self.commands_separator_1.grid(column="3", pady="5", row="0", sticky="ns")
        self.reload_command_button = ttk.Button(self.action_commands_f)
        self.reload_command_button.configure(text="Reload")
        self.reload_command_button.grid(column="4", padx="10", pady="5", row="0", sticky="ew")
        self.reload_command_button.configure(command=self.reloadCommands)
        self.start_button = ttk.Button(self.action_commands_f)
        self.start_button.configure(text="Start")
        self.start_button.grid(column="5", padx="10", pady="5", row="0", sticky="ew")
        self.start_button.configure(command=self.startPlay)
        self.force_stop_button = ttk.Button(self.action_commands_f)
        self.force_stop_button.configure(text="Force stop", state="disabled", command=self.force_stop_play)
        self.force_stop_button.grid(column="6", padx=(0, 5), pady="5", row="0", sticky="ew")
        self.image_match_debug_button = ttk.Button(self.action_commands_f, text="Image match debug",
                                                   command=self.open_image_match_debug)
        self.image_match_debug_button.grid(column="7", padx=(0, 5), pady="5", row="0", sticky="ew")
        self.pause_button = ttk.Button(self.action_commands_f)
        self.pause_button.configure(text="Pause")
        self.pause_button.grid(column="8", padx="10", pady="5", row="0", sticky="ew")
        self.pause_button.configure(command=self.pausePlay)
        self.action_commands_f.configure(height="200", width="200")
        self.action_commands_f.grid(column="0", row="1", sticky="e")
        self.commands_f.configure(height="200", width="500")
        self.commands_f.pack(side="top")
        self.controller_nb.add(self.commands_f, padding="5", text="Commands")
        self.notification_f = ttk.Frame(self.controller_nb)
        self.windows_notification_lf = ttk.Labelframe(self.notification_f)
        self.win_notification_start_checkbox = ttk.Checkbutton(self.windows_notification_lf)
        self.is_win_notification_start = tk.BooleanVar()
        self.win_notification_start_checkbox.configure(text="Start", variable=self.is_win_notification_start)
        self.win_notification_start_checkbox.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.win_notification_start_checkbox.configure(command=self.mode_change_notification)
        self.win_notification_end_checkbox = ttk.Checkbutton(self.windows_notification_lf)
        self.is_win_notification_end = tk.BooleanVar()
        self.win_notification_end_checkbox.configure(text="End", variable=self.is_win_notification_end)
        self.win_notification_end_checkbox.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.win_notification_end_checkbox.configure(command=self.mode_change_notification)
        self.send_win_button = ttk.Button(self.windows_notification_lf)
        self.send_win_button.configure(text="Test")
        self.send_win_button.grid(column="2", padx="5", pady="5", row="0", sticky="ew")
        self.send_win_button.configure(command=self.sendWinNotfication)
        self.windows_notification_lf.configure(text="Windows Notification")
        self.windows_notification_lf.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.line_notification_lf = ttk.Labelframe(self.notification_f)
        self.line_notification_start_checkbox = ttk.Checkbutton(self.line_notification_lf)
        self.is_line_notification_start = tk.BooleanVar()
        self.line_notification_start_checkbox.configure(text="Start", variable=self.is_line_notification_start)
        self.line_notification_start_checkbox.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.line_notification_start_checkbox.configure(command=self.mode_change_notification)
        self.line_notification_end_checkbox = ttk.Checkbutton(self.line_notification_lf)
        self.is_line_notification_end = tk.BooleanVar()
        self.line_notification_end_checkbox.configure(text="End", variable=self.is_line_notification_end)
        self.line_notification_end_checkbox.grid(column="1", padx="5", pady="0", row="0", sticky="ew")
        self.line_notification_end_checkbox.configure(command=self.mode_change_notification)
        self.send_line_button = ttk.Button(self.line_notification_lf)
        self.send_line_button.configure(text="Test")
        self.send_line_button.grid(column="2", padx="5", pady="5", row="0", sticky="ew")
        self.send_line_button.configure(command=self.sendLineImage)
        self.line_notification_lf.configure(text="Line Notification")
        self.line_notification_lf.grid(column="1", padx="5", pady="0", row="0", sticky="ew")
        self.discord_notification_lf = ttk.Labelframe(self.notification_f)
        self.discord_notification_start_checkbox = ttk.Checkbutton(self.discord_notification_lf)
        self.is_discord_notification_start = tk.BooleanVar()
        self.discord_notification_start_checkbox.configure(text="Start", variable=self.is_discord_notification_start)
        self.discord_notification_start_checkbox.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.discord_notification_start_checkbox.configure(command=self.mode_change_notification)
        self.discord_notification_end_checkbox = ttk.Checkbutton(self.discord_notification_lf)
        self.is_discord_notification_end = tk.BooleanVar()
        self.discord_notification_end_checkbox.configure(text="End", variable=self.is_discord_notification_end)
        self.discord_notification_end_checkbox.grid(column="1", padx="5", pady="0", row="0", sticky="ew")
        self.discord_notification_end_checkbox.configure(command=self.mode_change_notification)
        self.send_discord_button = ttk.Button(self.discord_notification_lf)
        self.send_discord_button.configure(text="Test")
        self.send_discord_button.grid(column="2", padx="5", pady="5", row="0", sticky="ew")
        self.send_discord_button.configure(command=self.sendDiscordImage)
        self.discord_notification_lf.configure(text="Discord Notification")
        self.discord_notification_lf.grid(column="0", padx="5", pady="0", row="1", sticky="ew")
        self.notification_f.pack()
        self.controller_nb.add(self.notification_f, sticky="nsew", text="Notification")
        self.others_tab = ttk.Frame(self.controller_nb)
        self.others_canvas = tk.Canvas(self.others_tab, highlightthickness=0, borderwidth=0)
        self.others_scrollbar = ttk.Scrollbar(self.others_tab, orient="vertical", command=self.others_canvas.yview)
        self.others_canvas.configure(yscrollcommand=self.others_scrollbar.set)
        self.others_canvas.pack(side="left", fill="both", expand=True)
        self.others_scrollbar.pack(side="right", fill="y")
        self.others_f = ttk.Frame(self.others_canvas)
        self.others_canvas_window = self.others_canvas.create_window((0, 0), window=self.others_f, anchor="nw")
        self.others_f.bind("<Configure>", self._update_others_scrollregion)
        self.others_canvas.bind("<Configure>", self._resize_others_content)
        self.root.bind_all("<MouseWheel>", self._scroll_others_with_wheel, add="+")
        self.others_preset_lf = ttk.Labelframe(self.others_f, text="Others setting set")
        ttk.Label(self.others_preset_lf, text="Set:").grid(column=0, row=0, padx=(5, 2), pady=4)
        self.others_preset_name = tk.StringVar()
        self.others_preset_cb = ttk.Combobox(self.others_preset_lf, textvariable=self.others_preset_name, width=20)
        self.others_preset_cb.grid(column=1, row=0, padx=2, pady=4)
        self.others_preset_cb.bind("<<ComboboxSelected>>", lambda *_: self.load_others_preset())
        ttk.Button(self.others_preset_lf, text="Save", command=self.save_others_preset).grid(column=2, row=0, padx=2, pady=4)
        ttk.Button(self.others_preset_lf, text="Apply", command=self.load_others_preset).grid(column=3, row=0, padx=2, pady=4)
        ttk.Button(self.others_preset_lf, text="Delete", command=self.delete_others_preset).grid(column=4, row=0, padx=(2, 5), pady=4)
        ttk.Button(self.others_preset_lf, text="Open Dev Studio", command=self.open_dev_studio).grid(column=5, row=0, padx=(2, 5), pady=4)
        self.others_preset_lf.grid(column=0, row=0, padx=5, pady=(3, 0), sticky="ew")
        self.othres_outputs_lf = ttk.Labelframe(self.others_f)
        self.outputs_size_adjuster_lf = ttk.Labelframe(self.othres_outputs_lf)
        self.panel_split_adjuster_lf = ttk.Labelframe(self.othres_outputs_lf, text="Panel split")
        self.area_size_scale = ttk.Scale(self.outputs_size_adjuster_lf)
        self.area_size = tk.IntVar(value=20)
        self.area_size_scale.configure(from_="0", length="200", orient="horizontal", to="100")
        self.area_size_scale.configure(value="50", variable=self.area_size)
        self.area_size_scale.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.area_size_scale.configure(command=self.changeAreaSize)
        # Legacy text-area size control is superseded by layout-aware sizing.
        self.area_size_scale.grid_forget()
        self.side_width_balance = tk.IntVar(value=50)
        self.panel_ratio = tk.IntVar(value=50)
        self.right_panel_ratio = tk.IntVar(value=50)
        self.size_adjuster_label = ttk.Label(self.outputs_size_adjuster_lf, text="Left / right width")
        self.size_adjuster_scale = ttk.Scale(self.outputs_size_adjuster_lf, from_=20, to=80,
                                              orient="horizontal", variable=self.side_width_balance,
                                              command=lambda *_: self.apply_panel_assignment())
        self.panel_split_label = ttk.Label(self.panel_split_adjuster_lf, text="Left: top / bottom")
        self.panel_split_scale = ttk.Scale(self.panel_split_adjuster_lf, from_=10, to=90,
                                            orient="horizontal", variable=self.panel_ratio,
                                            command=lambda *_: self.apply_panel_assignment())
        self.right_panel_split_label = ttk.Label(self.panel_split_adjuster_lf, text="Right: top / bottom")
        self.right_panel_split_scale = ttk.Scale(self.panel_split_adjuster_lf, from_=10, to=90,
                                                  orient="horizontal", variable=self.right_panel_ratio,
                                                  command=lambda *_: self.apply_panel_assignment())
        self.outputs_size_adjuster_lf.configure(text="Size Adjuster")
        self.outputs_size_adjuster_lf.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.panel_split_adjuster_lf.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.outputs_stdout_dest_lf = ttk.Labelframe(self.othres_outputs_lf)
        self.stdout_destination_1_rb = ttk.Radiobutton(self.outputs_stdout_dest_lf)
        self.stdout_destination = tk.StringVar(value="1")
        self.stdout_destination_1_rb.configure(text="Output#1", value="1", variable=self.stdout_destination)
        self.stdout_destination_1_rb.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.stdout_destination_1_rb.configure(command=self.switchStdoutDestination)
        self.stdout_destination_2_rb = ttk.Radiobutton(self.outputs_stdout_dest_lf)
        self.stdout_destination_2_rb.configure(text="Output#2", value="2", variable=self.stdout_destination)
        self.stdout_destination_2_rb.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.stdout_destination_2_rb.configure(command=self.switchStdoutDestination)
        self.outputs_stdout_dest_lf.configure(text="Standard Output Destination")
        self.stdout_log_target = tk.StringVar()
        self.stdout_log_target_cb = ttk.Combobox(self.outputs_stdout_dest_lf, state="readonly", width=16,
                                                 textvariable=self.stdout_log_target)
        self.stdout_log_target_cb.grid(column=0, columnspan=2, row=1, padx=5, pady=3, sticky="ew")
        self.stdout_log_target_cb.bind("<<ComboboxSelected>>", self.select_stdout_log_target)
        self.stdout_destination_1_rb.grid_forget()
        self.stdout_destination_2_rb.grid_forget()
        self.outputs_stdout_dest_lf.grid(column="2", padx="5", pady="5", row="0", sticky="ew")
        self.outputs_clear_lf = ttk.Labelframe(self.othres_outputs_lf)
        self.outputs_text_area_1_clear_button = ttk.Button(self.outputs_clear_lf)
        self.outputs_text_area_1_clear_button.configure(text="Clear(#1)")
        self.outputs_text_area_1_clear_button.grid(column="0", padx="10", pady="5", row="0", sticky="ew")
        self.outputs_text_area_1_clear_button.configure(command=self.clearTextArea1)
        self.outputs_text_area_2_clear_button = ttk.Button(self.outputs_clear_lf)
        self.outputs_text_area_2_clear_button.configure(text="Clear(#2)")
        self.outputs_text_area_2_clear_button.grid(column="1", padx="10", pady="5", row="0", sticky="ew")
        self.outputs_text_area_2_clear_button.configure(command=self.clearTextArea2)
        self.outputs_clear_lf.configure(text="Clear Outputs")
        self.clear_log_target = tk.StringVar()
        self.clear_log_target_cb = ttk.Combobox(self.outputs_clear_lf, state="readonly", width=16,
                                                textvariable=self.clear_log_target)
        self.clear_log_target_cb.grid(column=0, columnspan=2, row=1, padx=5, pady=3, sticky="ew")
        ttk.Button(self.outputs_clear_lf, text="Clear selected", command=self.clear_selected_log).grid(
            column=0, columnspan=2, row=2, padx=5, pady=3
        )
        self.outputs_text_area_1_clear_button.grid_forget()
        self.outputs_text_area_2_clear_button.grid_forget()
        self.outputs_clear_lf.grid(column="3", padx="5", pady="5", row="0", sticky="ew")
        ttk.Button(self.othres_outputs_lf, text="Side panels...", command=self.open_side_panel_settings).grid(
            column=4, row=0, padx=5, pady=5, sticky="ew"
        )
        self.panel_assignment_lf = ttk.Labelframe(self.othres_outputs_lf, text="Side panel layout / content")
        self.panel_layout = tk.StringVar(value="Four panels (left/right, top/bottom)")  # legacy setting
        self.panel_sides = tk.StringVar(value="Both sides")
        self.panel_layout_cb = ttk.Combobox(
            self.panel_assignment_lf, state="readonly", textvariable=self.panel_sides, width=18,
            values=("Both sides", "Left side only", "Right side only", "Both sides hidden"),
        )
        self.panel_layout_cb.grid(column=0, columnspan=2, row=0, padx=5, pady=3, sticky="ew")
        self.panel_layout_cb.bind("<<ComboboxSelected>>", self.apply_panel_assignment)
        ttk.Label(self.panel_assignment_lf, text="Left panels").grid(column=0, row=5, padx=5, pady=2, sticky="w")
        self.left_panel_count = tk.StringVar(value="2")
        ttk.Combobox(self.panel_assignment_lf, state="readonly", values=("1", "2"), width=4,
                     textvariable=self.left_panel_count).grid(column=1, row=5, padx=5, pady=2, sticky="w")
        ttk.Label(self.panel_assignment_lf, text="Right panels").grid(column=2, row=5, padx=5, pady=2, sticky="w")
        self.right_panel_count = tk.StringVar(value="2")
        right_count_cb = ttk.Combobox(self.panel_assignment_lf, state="readonly", values=("1", "2"), width=4,
                                      textvariable=self.right_panel_count)
        right_count_cb.grid(column=2, row=6, padx=5, pady=2, sticky="w")
        for variable in (self.left_panel_count, self.right_panel_count):
            variable.trace_add("write", lambda *_: self.apply_panel_assignment())
        self.show_software_controller = tk.BooleanVar(value=True)
        self.show_software_controller_cb = ttk.Checkbutton(
            self.panel_assignment_lf, text="Show software controller", variable=self.show_software_controller,
            command=self.apply_panel_assignment,
        )
        self.show_software_controller_cb.grid(column=2, row=0, padx=5, pady=3, sticky="w")
        self.panel_slots = {}
        panel_values = ["Disabled", "Log: Output#1", "Log: Output#2", "Image", "HTML", "Analysis"]
        for row, (slot, label) in enumerate((("left_top", "Left / Top"), ("left_bottom", "Left / Bottom"),
                                             ("right_top", "Right / Top"), ("right_bottom", "Right / Bottom")), start=1):
            ttk.Label(self.panel_assignment_lf, text=label).grid(column=0, row=row, padx=5, pady=2, sticky="w")
            value = tk.StringVar(value="Disabled")
            combo = ttk.Combobox(self.panel_assignment_lf, state="readonly", values=panel_values,
                                 textvariable=value, width=14)
            combo.grid(column=1, row=row, padx=5, pady=2)
            combo.bind("<<ComboboxSelected>>", self.apply_panel_assignment)
            self.panel_slots[slot] = value
        ttk.Label(self.panel_assignment_lf, text="Top / bottom ratio").grid(column=2, row=1, padx=5)
        ttk.Scale(self.panel_assignment_lf, from_=10, to=90, variable=self.panel_ratio,
                  command=self.apply_panel_assignment).grid(column=2, row=1, rowspan=3, padx=5, sticky="ns")
        self.panel_assignment_lf.grid(column=0, columnspan=3, padx=5, pady=5, row=2, sticky="ew")
        self.othres_outputs_lf.configure(height="200", text="Outputs/Dialogue Settings", width="200")
        self.othres_outputs_lf.grid(column="0", padx="5", row="1", sticky="ew")
        # self.othres_right_frame_lf = ttk.Labelframe(self.others_f)
        self.select_right_frame_widget = ttk.Labelframe(self.othres_outputs_lf)
        self.select_right_frame_widget_cb = ttk.Combobox(self.select_right_frame_widget)
        self.right_frame_widget_mode = tk.StringVar(value="ALL (default)")
        right_frame_widget_mode_list = [
            "ALL (default)",
            "Output#1 + Output#2",
            "Output#1 + Software-Controller",
            "Output#2 + Software-Controller",
            "Output#1 Only",
            "Output#2 Only",
            "Software-Controller Only",
        ]
        self.select_right_frame_widget_cb.configure(
            justify="left",
            state="readonly",
            textvariable=self.right_frame_widget_mode,
            values=right_frame_widget_mode_list,
        )
        self.select_right_frame_widget_cb.configure(width="30")
        self.select_right_frame_widget_cb.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.select_right_frame_widget_cb.bind("<<ComboboxSelected>>", self.replace_right_frame_widget)
        self.select_right_frame_widget.configure(text="Widget Mode")
        # Widget Mode is retained only for old profiles.  Side-panel settings above supersede it.
        self.pos_software_controller_lf = ttk.Labelframe(self.othres_outputs_lf)
        self.pos_software_controller = tk.StringVar(value="2")
        self.pos_top_rb = ttk.Radiobutton(self.pos_software_controller_lf)
        self.pos_top_rb.configure(text="TOP", value="1", variable=self.pos_software_controller)
        self.pos_top_rb.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.pos_top_rb.configure(command=self.replace_right_frame_widget)
        self.pos_bottom_rb = ttk.Radiobutton(self.pos_software_controller_lf)
        self.pos_bottom_rb.configure(text="BOTTOM", value="2", variable=self.pos_software_controller)
        self.pos_bottom_rb.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.pos_bottom_rb.configure(command=self.replace_right_frame_widget)
        self.pos_software_controller_lf.configure(text="Software-Controller Position")
        self.pos_software_controller_lf.grid(column="1", padx="5", pady="5", row="1", sticky="ew")
        self.pos_dialogue_buttons_lf = ttk.Labelframe(self.othres_outputs_lf)
        self.pos_dialogue_buttons = tk.StringVar(value="2")
        self.pos_dialogue_top_rb = ttk.Radiobutton(self.pos_dialogue_buttons_lf)
        self.pos_dialogue_top_rb.configure(text="TOP", value="1", variable=self.pos_dialogue_buttons)
        self.pos_dialogue_top_rb.grid(column="0", padx="5", pady="5", row="0", sticky="ew")
        self.pos_dialogue_top_rb.configure(command=self.change_buttons_position)
        self.pos_dialogue_bottom_rb = ttk.Radiobutton(self.pos_dialogue_buttons_lf)
        self.pos_dialogue_bottom_rb.configure(text="BOTTOM", value="2", variable=self.pos_dialogue_buttons)
        self.pos_dialogue_bottom_rb.grid(column="1", padx="5", pady="5", row="0", sticky="ew")
        self.pos_dialogue_bottom_rb.configure(command=self.change_buttons_position)
        self.pos_dialogue_both_rb = ttk.Radiobutton(self.pos_dialogue_buttons_lf)
        self.pos_dialogue_both_rb.configure(text="BOTH", value="3", variable=self.pos_dialogue_buttons)
        self.pos_dialogue_both_rb.grid(column="2", padx="5", pady="5", row="0", sticky="ew")
        self.pos_dialogue_both_rb.configure(command=self.change_buttons_position)
        self.pos_dialogue_buttons_lf.configure(text="Dialogue OK/Cancel Position")
        self.pos_dialogue_buttons_lf.grid(column="2", padx="5", pady="5", row="1", sticky="ew")
        # self.othres_right_frame_lf.grid(column='1', padx='5', row='1', sticky='ew')
        # self.others_help_lf = ttk.Labelframe(self.others_f)
        # self.others_help_lf.configure(text='Help')
        # self.others_help_lf.grid(column='0', padx='5', row='1', sticky='ew')
        self.others_f.columnconfigure(0, weight=1)
        self.controller_nb.add(self.others_tab, sticky="nsew", text="Others")
        self.command_watch_f = ttk.Frame(self.controller_nb)
        self.command_watch_lf = ttk.Labelframe(self.command_watch_f, text="Watch variables from the active Python Command")
        self.command_watch_enabled = tk.BooleanVar(value=False)
        self.command_watch_command = tk.StringVar()
        self.command_watch_target = tk.StringVar(value="Output#1")
        self.command_watch_variable = tk.StringVar()
        ttk.Checkbutton(self.command_watch_lf, text="Enable watch", variable=self.command_watch_enabled,
                        command=self.reset_command_watch).grid(column=0, row=0, padx=5, pady=4, sticky="w")
        ttk.Label(self.command_watch_lf, text="Command:").grid(column=0, row=1, padx=5, pady=4, sticky="w")
        self.command_watch_command_cb = ttk.Combobox(self.command_watch_lf, state="readonly", width=42,
                                                     textvariable=self.command_watch_command)
        self.command_watch_command_cb.grid(column=1, columnspan=3, row=1, padx=5, pady=4, sticky="ew")
        ttk.Label(self.command_watch_lf, text="Log output:").grid(column=0, row=2, padx=5, pady=4, sticky="w")
        ttk.Combobox(self.command_watch_lf, state="readonly", width=14, textvariable=self.command_watch_target,
                     values=("Output#1", "Output#2")).grid(column=1, row=2, padx=5, pady=4, sticky="w")
        ttk.Label(self.command_watch_lf, text="Variable:").grid(column=0, row=3, padx=5, pady=4, sticky="w")
        ttk.Entry(self.command_watch_lf, textvariable=self.command_watch_variable, width=28).grid(column=1, row=3, padx=5, pady=4, sticky="ew")
        ttk.Button(self.command_watch_lf, text="Add", command=self.add_command_watch_variable).grid(column=2, row=3, padx=3, pady=4)
        ttk.Button(self.command_watch_lf, text="Remove", command=self.remove_command_watch_variable).grid(column=3, row=3, padx=3, pady=4)
        self.command_watch_list = tk.Listbox(self.command_watch_lf, height=4, exportselection=False)
        self.command_watch_list.grid(column=0, columnspan=4, row=4, padx=5, pady=4, sticky="ew")
        self.command_watch_status = tk.StringVar(value="Select a command and variable names (for example: step, loop_count).")
        self.command_watch_variables = []
        self.command_watch_last_values = {}
        ttk.Label(self.command_watch_lf, textvariable=self.command_watch_status).grid(column=0, columnspan=4, row=5, padx=5, pady=(0, 4), sticky="w")
        self.command_watch_lf.pack(fill="x", padx=5, pady=5)
        self.command_watch_f.pack(fill="both", expand=True)
        self.controller_nb.add(self.command_watch_f, padding="5", sticky="nsew", text="Command Watch")
        if platform.system() == "Windows" or platform.system() == "Darwin":
            self.controller_nb.configure(height="150")
        else:
            self.controller_nb.configure(height="180")
        self.controller_nb.grid(column="1", padx="5", pady="5", row="1", sticky="ew")
        self.output_area_f = ttk.Frame(self.main_frame)
        self.text_scroll_1 = ttk.LabelFrame(self.output_area_f, relief=tk.GROOVE)
        self.text_scroll_1.configure(text="Output#1")
        self.output_image_1 = ttk.Label(self.text_scroll_1, text="Shift + drag on video: send crop here", anchor="center")
        self.output_image_1.pack(fill="x", padx=5, pady=(5, 0))
        self.text_area_1 = tk.Text(self.text_scroll_1)
        self.text_area_1.config(blockcursor="true", height="3", insertunfocussed="none", maxundo="0")
        self.text_area_1.config(relief="flat", state="disabled", undo="false", width="50")
        self.yscroll_1 = tk.Scrollbar(self.text_scroll_1, orient=tk.VERTICAL, command=self.text_area_1.yview)
        self.yscroll_1.pack(side="right", fill="y", padx=(0, 5), pady="5")
        self.text_area_1["yscrollcommand"] = self.yscroll_1.set
        self.text_area_1.pack(expand="true", fill="both", padx=(5, 0), pady="5")
        self.text_scroll_1.pack(expand="true", fill="both", padx="0", pady="0", side="top")
        self.text_scroll_2 = ttk.LabelFrame(self.output_area_f, relief=tk.GROOVE)
        self.text_scroll_2.configure(text="Output#2")
        self.output_image_2 = ttk.Label(self.text_scroll_2, text="Analysis result / HTML source", anchor="center")
        self.output_image_2.pack(fill="x", padx=5, pady=(5, 0))
        self.text_area_2 = tk.Text(self.text_scroll_2)
        self.text_area_2.config(blockcursor="true", height="3", insertunfocussed="none", maxundo="0")
        self.text_area_2.config(relief="flat", state="disabled", undo="false", width="50")
        self.yscroll_2 = tk.Scrollbar(self.text_scroll_2, orient=tk.VERTICAL, command=self.text_area_2.yview)
        self.yscroll_2.pack(side="right", fill="y", padx=(0, 5), pady="5")
        self.text_area_2["yscrollcommand"] = self.yscroll_2.set
        self.text_area_2.pack(expand="true", fill="both", padx=(5, 0), pady="5")
        self.text_scroll_2.pack(expand="true", fill="both", padx="0", pady="0", side="top")
        self.left_output_area_f = ttk.Frame(self.main_frame)
        self.left_top_panel = ttk.LabelFrame(self.left_output_area_f, text="Left / Top")
        self.left_bottom_panel = ttk.LabelFrame(self.left_output_area_f, text="Left / Bottom")
        self.left_top_image = ttk.Label(self.left_top_panel, text="Left / Top", anchor="center")
        self.left_top_image.pack(fill="x", padx=5, pady=(5, 0))
        self.left_top_text = tk.Text(self.left_top_panel, height=5, width=28, state="disabled", relief="flat")
        self.left_top_text.pack(expand=True, fill="both", padx=5, pady=5)
        self.left_bottom_image = ttk.Label(self.left_bottom_panel, text="Left / Bottom", anchor="center")
        self.left_bottom_image.pack(fill="x", padx=5, pady=(5, 0))
        self.left_bottom_text = tk.Text(self.left_bottom_panel, height=5, width=28, state="disabled", relief="flat")
        self.left_bottom_text.pack(expand=True, fill="both", padx=5, pady=5)
        self.left_top_panel.pack(expand=True, fill="both", side="top")
        self.left_bottom_panel.pack(expand=True, fill="both", side="top")
        self.left_output_area_f.grid(column="0", padx="5", pady="5", row="0", rowspan="2", sticky="nsew")
        self.output_area_f.grid(column="2", padx="5", pady="5", row="0", rowspan="2", sticky="nsew")
        self.panel_widgets = {
            "left_top": (self.left_top_panel, self.left_top_image, self.left_top_text),
            "left_bottom": (self.left_bottom_panel, self.left_bottom_image, self.left_bottom_text),
            "right_top": (self.text_scroll_1, self.output_image_1, self.text_area_1),
            "right_bottom": (self.text_scroll_2, self.output_image_2, self.text_area_2),
        }
        self.area_capture_inline = {}
        self.area_capture_inline_zoom = {}
        self.area_capture_drag = {}
        self.base_text_areas = (self.text_area_1, self.text_area_2)
        self.softcon_frame = ttk.LabelFrame(self.output_area_f, relief=tk.GROOVE)
        self.softcon_frame.configure(text="Software-Controller")
        self.softcon_left_frame = tk.Frame(self.softcon_frame, bg="#56CCF2")
        self.softcon_left_frame.configure(height=200, width=200)
        self.softcon_zl_button = tk.Button(self.softcon_left_frame)
        self.softcon_zl_button.configure(text="ZL", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_zl_button.grid(column=0, padx=2, pady=2, row=0)
        self.softcon_l_button = tk.Button(self.softcon_left_frame)
        self.softcon_l_button.configure(text="L", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_l_button.grid(column=0, padx=2, pady=2, row=1)
        self.softcon_minus_button = tk.Button(self.softcon_left_frame)
        self.softcon_minus_button.configure(text="－", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_minus_button.grid(column=2, padx=2, pady=2, row=1)
        self.softcon_l_click_button = tk.Button(self.softcon_left_frame)
        self.softcon_l_click_button.configure(text="L-C", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_l_click_button.grid(column=1, padx=2, pady=2, row=1)
        self.softcon_up_button = tk.Button(self.softcon_left_frame)
        self.softcon_up_button.configure(text="↑", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_up_button.grid(column=1, padx=2, pady=2, row=2)
        self.softcon_left_button = tk.Button(self.softcon_left_frame)
        self.softcon_left_button.configure(text="←", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_left_button.grid(column=0, padx=2, pady=2, row=3)
        self.softcon_right_button = tk.Button(self.softcon_left_frame)
        self.softcon_right_button.configure(text="→", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_right_button.grid(column=2, padx=2, pady=2, row=3)
        self.softcon_down_button = tk.Button(self.softcon_left_frame)
        self.softcon_down_button.configure(text="↓", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_down_button.grid(column=1, padx=2, pady=2, row=4)
        self.softcon_capture_button = tk.Button(self.softcon_left_frame)
        self.softcon_capture_button.configure(text="CAP", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_capture_button.grid(column=2, padx=2, pady=2, row=4)
        self.softcon_left_frame.grid(column=0, ipadx=3, ipady=3, row=0, sticky="nsew")
        self.softcon_left_frame.grid_anchor("center")
        self.softcon_right_frame = tk.Frame(self.softcon_frame, bg="#E9514E")
        self.softcon_right_frame.configure(height=200, width=200)
        self.softcon_zr_button = tk.Button(self.softcon_right_frame)
        self.softcon_zr_button.configure(text="ZR", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_zr_button.grid(column=2, padx=2, pady=2, row=0)
        self.softcon_r_button = tk.Button(self.softcon_right_frame)
        self.softcon_r_button.configure(text="R", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_r_button.grid(column=2, padx=2, pady=2, row=1)
        self.softcon_plus_button = tk.Button(self.softcon_right_frame)
        self.softcon_plus_button.configure(text="＋", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_plus_button.grid(column=0, padx=2, pady=2, row=1)
        self.softcon_r_click_button = tk.Button(self.softcon_right_frame)
        self.softcon_r_click_button.configure(text="R-C", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_r_click_button.grid(column=1, padx=2, pady=2, row=4)
        self.softcon_x_button = tk.Button(self.softcon_right_frame)
        self.softcon_x_button.configure(text="X", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_x_button.grid(column=1, padx=2, pady=2, row=1)
        self.softcon_y_button = tk.Button(self.softcon_right_frame)
        self.softcon_y_button.configure(text="Y", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_y_button.grid(column=0, padx=2, pady=2, row=2)
        self.softcon_a_button = tk.Button(self.softcon_right_frame)
        self.softcon_a_button.configure(text="A", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_a_button.grid(column=2, padx=2, pady=2, row=2)
        self.softcon_b_button = tk.Button(self.softcon_right_frame)
        self.softcon_b_button.configure(text="B", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_b_button.grid(column=1, padx=2, pady=2, row=3)
        self.softcon_home_button = tk.Button(self.softcon_right_frame)
        self.softcon_home_button.configure(text="HOME", width=5, bg="#343434", fg="#FFFFFF")
        self.softcon_home_button.grid(column=0, padx=2, pady=2, row=4)
        self.softcon_right_frame.grid(column=1, ipadx=3, ipady=3, row=0, sticky="nsew")
        self.softcon_right_frame.grid_anchor("center")
        self.softcon_frame.pack(expand="true", fill="both", padx="0", pady="0", side="top")
        self.softcon_frame.grid_anchor("center")
        self.main_frame.config(height="720", padding="5", relief="flat", width="1280")
        self.main_frame.pack(expand="true", fill="both", side="top")
        self.main_frame.columnconfigure("0", weight="1")
        self.main_frame.columnconfigure("1", weight="3")
        self.main_frame.columnconfigure("2", weight="1")
        """
        ここまで
        """

        # ToolTip設定
        self.start_top_button_tooltip = ToolTip(self.start_top_button, "自動化スクリプトを実行します")
        self.simplecon_top_button_tooltip = ToolTip(
            self.simplecon_top_button, "switch用ソフトウェアコントローラを起動します"
        )
        self.clear_top_button_tooltip = ToolTip(self.clear_top_button, "ログ画面(output(#1)/output(#2))をクリアします")
        self.capture_button_tooltip = ToolTip(self.capture_button, "ゲーム画面のスクリーンショットを取得します")
        self.open_capture_button_tooltip = ToolTip(
            self.open_capture_button, "スクリーンショット画像を保存するディレクトリを開きます"
        )
        # self.line_button_tooltip = ToolTip(self.line_button, "現在のゲーム画像をLineに通知します")
        self.discord_button_tooltip = ToolTip(self.discord_button, "現在のゲーム画像をDiscordに通知します")
        self.camera_id_label_tooltip = ToolTip(self.camera_id_label, "使用するキャプチャデバイスのIDを設定します")
        self.camera_id_entry_tooltip = ToolTip(self.camera_id_entry, "使用するキャプチャデバイスのID")
        self.reload_button_tooltip = ToolTip(
            self.reload_button, "設定したキャプチャデバイスとの接続を確立し、画像読み込みを開始します"
        )
        self.fps_label_tooltip = ToolTip(self.fps_label, "FPSを設定します(即時反映)")
        self.fps_cb_tooltip = ToolTip(self.fps_cb, "設定されているFPS")
        self.show_size_label_tooltip = ToolTip(self.show_size_label, "表示する画像のサイズを設定します(即時反映)")
        self.show_size_cb_tooltip = ToolTip(self.show_size_cb, "表示されている画像のサイズ")
        self.camera_name_label_tooltip = ToolTip(self.camera_name_label, "使用するキャプチャデバイスを設定します")
        self.camera_name_cb_tooltip = ToolTip(self.camera_name_cb, "設定するキャプチャデバイス")
        self.show_realtime_checkbox_tooltip = ToolTip(
            self.show_realtime_checkbox,
            "画像をリアルタイムで更新する機能を有効化します\n(注意)本機能を有効化しないと画像は静止画のままとなります",
        )
        self.show_value_checkbox_tooltip = ToolTip(
            self.show_value_checkbox, "テンプレートマッチングの類似度をshow_valueの値によらず強制的に出力します。"
        )
        self.show_guide_checkbox_tooltip = ToolTip(
            self.show_guide_checkbox,
            "ガイド表示を有効化します\n自動化スクリプト次第で本チェックボックスは無効化される場合があります",
        )
        portheader = "COM" if platform.system() in ["Windows", "Darwin"] else ""
        self.com_port_label_tooltip = ToolTip(
            self.com_port_label, f"{portheader}ポート番号を設定します(デバイスマネージャーで確認可能です)"
        )
        self.com_port_entry_tooltip = ToolTip(self.com_port_entry, f"設定する{portheader}ポート番号")
        self.baud_rate_label_tooltip = ToolTip(self.baud_rate_label, "ボーレートを設定します(switch:9600, GC:4800)")
        self.baud_rate_cb_tooltip = ToolTip(self.baud_rate_cb, "設定するボーレート")
        self.reload_com_port_button_tooltip = ToolTip(
            self.reload_com_port_button,
            "設定したCOMポート番号とボーレートの情報に基づいてUSBシリアルとの接続を確立します",
        )
        self.disconnect_com_port_button_tooltip = ToolTip(
            self.disconnect_com_port_button, "USBシリアルとの接続を解除します"
        )
        self.serial_device_name_label_tooltip = ToolTip(
            self.serial_device_name_label, "使用するシリアルデバイスを設定します"
        )
        self.serial_device_name_cb_tooltip = ToolTip(self.serial_device_name_cb, "設定するシリアルデバイス名")
        self.scan_device_button_tooltip = ToolTip(self.scan_device_button, "シリアルデバイスをスキャンします")
        self.show_serial_checkbox_tooltip = ToolTip(self.show_serial_checkbox, "シリアル値を出力する機能を有効化します")
        self.simplecon_button_tooltip = ToolTip(self.simplecon_button, "switch用ソフトウェアコントローラを起動します")
        self.use_keyboard_checkbox_tooltip = ToolTip(
            self.use_keyboard_checkbox, "キーボードで操作する機能を有効化します"
        )
        self.left_stick_mouse_checkbox_tooltip = ToolTip(
            self.left_stick_mouse_checkbox,
            "ゲーム画面上で左クリックを押下した後、その状態でマウスを動かすことで左stickを動かす機能を有効化します",
        )
        self.right_stick_mouse_checkbox_tooltip = ToolTip(
            self.right_stick_mouse_checkbox,
            "ゲーム画面上で右クリックを押下した後、その状態でマウスを動かすことで右stickを動かす機能を有効化します",
        )
        self.use_pro_controller_checkbox_tooltip = ToolTip(
            self.use_pro_controller_checkbox, "pcに接続したproconでswitchを操作する機能を有効化します"
        )
        self.record_pro_controller_checkbox_tooltip = ToolTip(
            self.record_pro_controller_checkbox, "proconで操作している際のログを記録する機能を有効化します"
        )
        self.command_filter_py_label_tooltip = ToolTip(
            self.command_filter_py_label, "実行可能なスクリプト(python)のリストをフィルタリングします"
        )
        self.command_filter_py_cb_tooltip = ToolTip(
            self.command_filter_py_cb, "実行可能なスクリプト(python)のフィルタリング条件"
        )
        self.py_label_tooltip = ToolTip(self.py_label, "実行するスクリプト(python)を設定します")
        self.py_cb_tooltip = ToolTip(self.py_cb, "実行するスクリプト(python)")
        self.command_filter_mcu_label_tooltip = ToolTip(
            self.command_filter_mcu_label, "実行可能なスクリプト(mcu)のリストをフィルタリングします"
        )
        self.command_filter_mcu_cb_tooltip = ToolTip(
            self.command_filter_mcu_cb, "実行可能なスクリプト(mcu)のフィルタリング条件"
        )
        self.mcu_label_tooltip = ToolTip(self.mcu_label, "実行するスクリプト(mcu)を設定します")
        self.mcu_cb_tooltip = ToolTip(self.mcu_cb, "実行するスクリプト(mcu)")
        self.open_command_dir_button_tooltip = ToolTip(
            self.open_command_dir_button, "スクリプト(.py)を保存するディレクトリを開きます"
        )
        self.set_shortcut_label_tooltip = ToolTip(
            self.set_shortcut_label, "ショートカットボタンに選択されているスクリプトを割り当てます"
        )
        self.set_shortcut_num_sb_tooltip = ToolTip(
            self.set_shortcut_num_sb, "スクリプトを割り当てるショートカットボタンの番号"
        )
        self.shortcut_set_button_tooltip = ToolTip(
            self.shortcut_set_button, "ショートカットボタンへのスクリプトの割り当てを実行します"
        )
        self.reload_command_button_tooltip = ToolTip(self.reload_command_button, "自動化スクリプトを再度読み込みます")
        self.start_button_tooltip = ToolTip(self.start_button, "自動化スクリプトを実行します")
        self.pause_button_tooltip = ToolTip(self.pause_button, "自動化スクリプトを一時停止します")
        self.win_notification_start_checkbox_tooltip = ToolTip(
            self.win_notification_start_checkbox, "自動化スクリプト実行開始時に通知をします"
        )
        self.win_notification_end_checkbox_tooltip = ToolTip(
            self.win_notification_end_checkbox, "自動化スクリプト実行終了時に通知をします"
        )
        self.send_win_button_tooltip = ToolTip(self.send_win_button, "通知機能でテストメッセージを送信します")
        self.line_notification_start_checkbox_tooltip = ToolTip(
            self.line_notification_start_checkbox, "自動化スクリプト実行開始時にLineで通知をします"
        )
        self.line_notification_end_checkbox_tooltip = ToolTip(
            self.line_notification_end_checkbox, "自動化スクリプト実行終了時にLineで通知をします"
        )
        self.send_line_button_tooltip = ToolTip(self.send_line_button, "Lineでテストメッセージを送信します")
        self.discord_notification_start_checkbox_tooltip = ToolTip(
            self.discord_notification_start_checkbox, "自動化スクリプト実行開始時にDiscordで通知をします"
        )
        self.discord_notification_end_checkbox_tooltip = ToolTip(
            self.discord_notification_end_checkbox, "自動化スクリプト実行終了時にDiscordで通知をします"
        )
        self.send_discord_button_tooltip = ToolTip(self.send_discord_button, "Discordでテストメッセージを送信します")
        self.area_size_scale_tooltip = ToolTip(
            self.area_size_scale, "output(#1)(上側)とoutput(#2)(下側)の比率を調整します"
        )
        self.stdout_destination_1_rb_tooltip = ToolTip(
            self.stdout_destination_1_rb, "標準出力先にoutput(#1)(上側)を設定します"
        )
        self.stdout_destination_2_rb_tooltip = ToolTip(
            self.stdout_destination_2_rb, "標準出力先にoutput(#2)(下側)を設定します"
        )
        self.outputs_text_area_1_clear_button_tooltip = ToolTip(
            self.outputs_text_area_1_clear_button, "output(#1)(上側)をクリアします"
        )
        self.outputs_text_area_2_clear_button_tooltip = ToolTip(
            self.outputs_text_area_2_clear_button, "output(#2)(下側)をクリアします"
        )
        self.select_right_frame_widget_cb_tooltip = ToolTip(
            self.select_right_frame_widget_cb, "右側に表示するウィジェットの種類を設定します"
        )
        self.pos_top_rb_tooltip = ToolTip(self.pos_top_rb, "Software-Controllerを上側に表示します")
        self.pos_bottom_rb_tooltip = ToolTip(self.pos_bottom_rb, "Software-Controllerを下側に表示します")
        self.pos_dialogue_top_rb_tooltip = ToolTip(
            self.pos_dialogue_top_rb, "ダイアログ起動時におけるOK/Cancelボタンを上側に表示します"
        )
        self.pos_dialogue_bottom_rb_tooltip = ToolTip(
            self.pos_dialogue_bottom_rb, "ダイアログ起動時におけるOK/Cancelボタンを下側に表示します"
        )
        self.pos_dialogue_both_rb_tooltip = ToolTip(
            self.pos_dialogue_both_rb, "ダイアログ起動時におけるOK/Cancelボタンを上下両方に表示します"
        )
        # self.text_area_1_tooltip = ToolTip(self.text_area_1, "output(#1)")
        # self.text_area_2_tooltip = ToolTip(self.text_area_2, "output(#2)")

        # 仮置フレームを削除
        self.canvas_frame.destroy()

        # 標準出力をログにリダイレクト
        # sys.stdout = StdoutRedirector(self.text_area_1)
        # sys.stdout = StdoutRedirector(self.text_area_2)

        # ログ画面に自動化スクリプトからアクセスできるようにする。
        Command.text_area_1 = self.text_area_1
        Command.text_area_2 = self.text_area_2

        # 初期表示を出力
        # self.text_area_1.config(state='normal')
        # self.text_area_1.insert('1.0', '----------画面1----------\n')
        # self.text_area_1.config(state='disable')
        # self.text_area_2.config(state='normal')
        # self.text_area_2.insert('1.0', '----------画面2----------\n')
        # self.text_area_2.config(state='disable')

        # 引数設定時、使用するsetting.iniを変更
        print("User Profile Name:", Settings.GuiSettings.SETTING_PATH)
        profile_dirname = os.path.join("profiles", profile)
        if not os.path.isdir(profile_dirname):
            os.makedirs(profile_dirname)
            self._logger.debug(f"mkdir: '{profile_dirname}'")
        if profile != "default":
            setting_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles", profile, "settings.ini")
            Settings.GuiSettings.SETTING_PATH = setting_path
            line_token_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "profiles", profile, "line_token.ini"
            )
            Line_Notify.LINE_TOKEN_PATH = line_token_path
            discord_setting_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "profiles", profile, "discord_token.ini"
            )
            Discord_Notify.DISCORD_SETTING_PATH = discord_setting_path
            token_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "profiles", profile, "external_token.ini"
            )
            SocketCommunications.SOCKET_TOKEN_PATH = token_path
            MQTTCommunications.MQTT_TOKEN_PATH = token_path
            SwitchKeyboardController.SETTING_PATH = setting_path
            PokeKeycon.SETTING_PATH = setting_path
            self._logger.debug(f"Use Profile: '{setting_path}'")

        # load settings file
        self.loadSettings()
        # 各tk変数に設定値をセット(コピペ簡単のため)
        self.is_show_realtime.set(self.settings.is_show_realtime.get())
        self.is_show_value.set(self.settings.is_show_value.get())
        self.is_show_guide.set(self.settings.is_show_guide.get())
        self.is_show_serial.set(self.settings.is_show_serial.get())
        self.is_use_keyboard.set(self.settings.is_use_keyboard.get())
        self.fps.set(self.settings.fps.get())
        self.show_size.set(self.settings.show_size.get())
        self.com_port.set(self.settings.com_port.get())
        self.com_port_name.set(self.settings.com_port_name.get())
        self.baud_rate.set(self.settings.baud_rate.get())
        self.camera_id.set(self.settings.camera_id.get())
        self.serial_data_format_name.set(self.settings.serial_data_format_name.get())
        self.touchscreen_start_x = self.settings.touchscreen_start_x
        self.touchscreen_start_y = self.settings.touchscreen_start_y
        self.touchscreen_end_x = self.settings.touchscreen_end_x
        self.touchscreen_end_y = self.settings.touchscreen_end_y
        self.shortcut_command_name = {
            1: self.settings.command_name_dict["1"].get(),
            2: self.settings.command_name_dict["2"].get(),
            3: self.settings.command_name_dict["3"].get(),
            4: self.settings.command_name_dict["4"].get(),
            5: self.settings.command_name_dict["5"].get(),
            6: self.settings.command_name_dict["6"].get(),
            7: self.settings.command_name_dict["7"].get(),
            8: self.settings.command_name_dict["8"].get(),
            9: self.settings.command_name_dict["9"].get(),
            10: self.settings.command_name_dict["10"].get(),
        }
        # ショートカットに設定されたスクリプトのclass(python/mcu)はtk変数ではない
        self.shortcut_command_class = {
            1: self.settings.command_class_dict["1"],
            2: self.settings.command_class_dict["2"],
            3: self.settings.command_class_dict["3"],
            4: self.settings.command_class_dict["4"],
            5: self.settings.command_class_dict["5"],
            6: self.settings.command_class_dict["6"],
            7: self.settings.command_class_dict["7"],
            8: self.settings.command_class_dict["8"],
            9: self.settings.command_class_dict["9"],
            10: self.settings.command_class_dict["10"],
        }
        self.is_win_notification_start.set(self.settings.is_win_notification_start.get())
        self.is_win_notification_end.set(self.settings.is_win_notification_end.get())
        self.is_line_notification_start.set(self.settings.is_line_notification_start.get())
        self.is_line_notification_end.set(self.settings.is_line_notification_end.get())
        self.is_discord_notification_start.set(self.settings.is_discord_notification_start.get())
        self.is_discord_notification_end.set(self.settings.is_discord_notification_end.get())
        self.area_size.set(self.settings.area_size)
        self.stdout_destination.set(self.settings.stdout_destination)
        self.right_frame_widget_mode.set(self.settings.right_frame_widget_mode)
        self.pos_software_controller.set(self.settings.pos_software_controller)
        self.pos_dialogue_buttons.set(self.settings.pos_dialogue_buttons)
        self.panel_slots["left_top"].set(self.settings.panel_left_top)
        self.panel_slots["left_bottom"].set(self.settings.panel_left_bottom)
        self.panel_slots["right_top"].set(self.settings.panel_right_top)
        self.panel_slots["right_bottom"].set(self.settings.panel_right_bottom)
        self.panel_ratio.set(self.settings.panel_ratio)
        self.right_panel_ratio.set(self.settings.right_panel_ratio)
        self.panel_layout.set(self.settings.panel_layout)
        # Migrate the former layout choices once, while allowing new profiles
        # to persist the explicit left/right visibility setting.
        legacy_layout = self.settings.panel_layout
        if self.settings.panel_sides == "Both sides" and legacy_layout == "Two vertical panels":
            self.panel_sides.set("Right side only")
        elif self.settings.panel_sides == "Both sides" and legacy_layout == "Output panels hidden":
            self.panel_sides.set("Both sides hidden")
        else:
            self.panel_sides.set(self.settings.panel_sides)
        self.left_panel_count.set(self.settings.left_panel_count)
        self.right_panel_count.set(self.settings.right_panel_count)
        self.side_width_balance.set(self.settings.side_width_balance)
        self.show_software_controller.set(self.settings.show_software_controller)
        self.audio_input.set(self.settings.audio_input)
        self.audio_gain.set(self.settings.audio_gain)
        self.audio_filter_camera.set(self.settings.audio_filter_camera)
        self.audio_auto_start.set(self.settings.audio_auto_start)
        self.vision_mode.set(self.settings.vision_mode)
        self.record_mode.set(self.settings.record_mode)
        self.record_template_path.set(self.settings.record_template_path)
        self.record_threshold.set(self.settings.record_threshold)
        self.record_interval.set(self.settings.record_interval)
        self.record_release.set(self.settings.record_release)
        self.record_roi.set(self.settings.record_roi)
        self.record_debug.set(self.settings.record_debug)
        self.record_minimum_duration.set(self.settings.record_minimum_duration)
        self.record_variable_command.set(self.settings.record_variable_command)
        self.record_variable_name.set(self.settings.record_variable_name)
        self.record_variable_start.set(self.settings.record_variable_start)
        self.record_variable_stop.set(self.settings.record_variable_stop)
        self.area_capture_roi.set(self.settings.area_capture_roi)
        self.area_capture_output_target.set(self.settings.area_capture_output_target)
        self.area_capture_background.set(self.settings.area_capture_background)
        self.area_capture_active.set(self.settings.area_capture_active)
        self.command_watch_enabled.set(self.settings.command_watch_enabled)
        self.command_watch_command.set(self.settings.command_watch_command)
        self.command_watch_target.set(self.settings.command_watch_target)
        self.command_watch_variables = [name for name in self.settings.command_watch_variables.split(",") if name]
        self.command_watch_list.delete(0, "end")
        for name in self.command_watch_variables:
            self.command_watch_list.insert("end", name)
        try:
            self.record_trigger_rules = json.loads(self.settings.record_trigger_rules)
            self.record_cleanup_rules = json.loads(self.settings.record_cleanup_rules)
        except (TypeError, ValueError):
            self.record_trigger_rules, self.record_cleanup_rules = [], []
        self.configure_recording_rules()
        self.refresh_recording_presets()
        if self.record_template_path.get():
            self.recorder.configure_template(self.record_template_path.get())
        self.apply_panel_assignment()
        self.refresh_presets()
        self.refresh_others_presets()

        # Shortcutボタンに名称とtooltipを設定する
        self.shortcut_1.set(self.shortcut_command_name[1][:8])
        self.shortcut_2.set(self.shortcut_command_name[2][:8])
        self.shortcut_3.set(self.shortcut_command_name[3][:8])
        self.shortcut_4.set(self.shortcut_command_name[4][:8])
        self.shortcut_5.set(self.shortcut_command_name[5][:8])
        self.shortcut_6.set(self.shortcut_command_name[6][:8])
        self.shortcut_7.set(self.shortcut_command_name[7][:8])
        self.shortcut_8.set(self.shortcut_command_name[8][:8])
        self.shortcut_9.set(self.shortcut_command_name[9][:8])
        self.shortcut_10.set(self.shortcut_command_name[10][:8])
        self.shortcut_button_1_tooltip = ToolTip(self.shortcut_button_1, self.shortcut_command_name[1])
        self.shortcut_button_2_tooltip = ToolTip(self.shortcut_button_2, self.shortcut_command_name[2])
        self.shortcut_button_3_tooltip = ToolTip(self.shortcut_button_3, self.shortcut_command_name[3])
        self.shortcut_button_4_tooltip = ToolTip(self.shortcut_button_4, self.shortcut_command_name[4])
        self.shortcut_button_5_tooltip = ToolTip(self.shortcut_button_5, self.shortcut_command_name[5])
        self.shortcut_button_6_tooltip = ToolTip(self.shortcut_button_6, self.shortcut_command_name[6])
        self.shortcut_button_7_tooltip = ToolTip(self.shortcut_button_7, self.shortcut_command_name[7])
        self.shortcut_button_8_tooltip = ToolTip(self.shortcut_button_8, self.shortcut_command_name[8])
        self.shortcut_button_9_tooltip = ToolTip(self.shortcut_button_9, self.shortcut_command_name[9])
        self.shortcut_button_10_tooltip = ToolTip(self.shortcut_button_10, self.shortcut_command_name[10])

        # self.shortcut_button_1["text"] = self.settings.command_name_1
        # 各コンボボックスを現在の設定値に合わせて表示
        self.fps_cb.current(self.fps_cb["values"].index(self.fps.get()))
        self.show_size_cb.current(self.show_size_cb["values"].index(self.show_size.get()))

        # 類似度の表示機能を反映する
        self.mode_change_show_value()

        # ガイドの表示機能を反映する
        self.mode_change_show_guide()

        # 標準出力をログにリダイレクト
        self.switchStdoutDestination()

        # Notificationの設定を反映する
        self.mode_change_notification()

        # ダイアログのOK/NGのボタンの位置を設定する
        self.change_buttons_position()

        if platform.system() == "Windows" or platform.system() == "Darwin":
            try:
                self.locateCameraCmbbox()
                self.camera_id_entry.config(state="disable")
            except Exception as e:
                # Locate an entry instead whenever dll is not imported successfully
                self.camera_name_fromDLL.set(
                    "An error occurred when displaying the camera name in the Win/Mac environment."
                )
                self._logger.warning("An error occurred when displaying the camera name in the Win/Mac environment.")
                self._logger.warning(e)
                self.camera_name_cb.config(state="disable")
                self.camera_id_entry.config(state="normal")
            try:
                self.locateDeviceCmbbox()
                self.set_init_device_name()
            except Exception as e:
                self._logger.warning("An error occurred when checking serial device list.")
                self._logger.warning(e)
        elif platform.system() == "Linux":
            self.camera_name_fromDLL.set("Linux environment. So that cannot show Camera name.")
            self.camera_name_cb.config(state="disable")
            self.camera_id_entry.config(state="normal")
        else:
            self.camera_name_fromDLL.set("Unknown environment. Cannot show Camera name.")
            self.camera_name_cb.config(state="disable")
            self.camera_id_entry.config(state="normal")
        # open up a camera
        self.camera = Camera(self.fps.get())
        self.openCamera()
        # activate serial communication
        try:
            self.locateDeviceCmbbox()
            self.set_init_device_name()
        except Exception:
            self.serial_device_name_label.destroy()
            self.serial_device_name_cb.destroy()
            self.scan_device_button.destroy()
            self.com_port_entry["state"] = "normal"

        if platform.system() == "Windows" or platform.system() == "Darwin":
            pass
        else:
            self.com_port_entry["state"] = "normal"

        self.ser = Sender.Sender(self.is_show_serial)
        self.activateSerial()
        self.activateKeyboard()
        self.preview = CaptureArea(
            self.camera,
            self.fps.get(),
            self.serial_data_format_name.get(),
            self.is_show_realtime,
            #    self.ser,
            KeyPress(self.ser),
            self.camera_lf,
            *list(map(int, self.show_size.get().split("x"))),
        )
        self.preview.config(cursor="crosshair")
        self.preview.grid(column="0", columnspan="7", row="2", padx="5", pady="5", sticky=tk.NSEW)
        self.preview.setTouchscreenArea(
            self.touchscreen_start_x, self.touchscreen_start_y, self.touchscreen_end_x, self.touchscreen_end_y
        )
        self.preview.set_region_listener(self.receive_output_region)
        self.preview.set_frame_listener(self.analyse_live_frame)
        self.preview.set_record_listener(self.process_recording_frame)
        self.root.after(1000, self.preview_area_capture)
        # Audio devices have now been enumerated and the GUI is ready.  Use
        # an idle callback so an unavailable device never delays startup.
        self.root.after(700, self.start_audio_on_launch)
        self.loadCommands()

        # キャンバスに自動化スクリプトからアクセスできるようにする。
        Command.canvas = self.preview
        Command.output = self.show_output

        self.show_size_tmp = self.show_size_cb["values"].index(self.show_size_cb.get())
        self.root.bind("<Key-F5>", self.ReloadCommandWithF5)
        self._logger.debug("Bind F5 key to reload commands")
        self.root.bind("<Key-F6>", self.StartCommandWithF6)
        self._logger.debug("Bind F6 key to execute commands")
        self.root.bind("<Key-Escape>", self.StopCommandWithEsc)
        self._logger.debug("Bind Escape key to stop commands")

        # self.keys_software_controller = UnitCommand
        self.keys_software_controller = KeyPress(self.ser)

        self.softcon_zl_button.bind("<Button-1>", lambda event, arg=Button.ZL: self.hold(event, arg))
        self.softcon_l_button.bind("<Button-1>", lambda event, arg=Button.L: self.hold(event, arg))
        self.softcon_minus_button.bind("<Button-1>", lambda event, arg=Button.MINUS: self.hold(event, arg))
        self.softcon_l_click_button.bind("<Button-1>", lambda event, arg=Button.LCLICK: self.hold(event, arg))
        self.softcon_up_button.bind("<Button-1>", lambda event, arg=Hat.TOP: self.hold(event, arg))
        self.softcon_left_button.bind("<Button-1>", lambda event, arg=Hat.LEFT: self.hold(event, arg))
        self.softcon_right_button.bind("<Button-1>", lambda event, arg=Hat.RIGHT: self.hold(event, arg))
        self.softcon_down_button.bind("<Button-1>", lambda event, arg=Hat.BTM: self.hold(event, arg))
        self.softcon_capture_button.bind("<Button-1>", lambda event, arg=Button.CAPTURE: self.hold(event, arg))
        self.softcon_zr_button.bind("<Button-1>", lambda event, arg=Button.ZR: self.hold(event, arg))
        self.softcon_r_button.bind("<Button-1>", lambda event, arg=Button.R: self.hold(event, arg))
        self.softcon_plus_button.bind("<Button-1>", lambda event, arg=Button.PLUS: self.hold(event, arg))
        self.softcon_r_click_button.bind("<Button-1>", lambda event, arg=Button.R: self.hold(event, arg))
        self.softcon_x_button.bind("<Button-1>", lambda event, arg=Button.X: self.hold(event, arg))
        self.softcon_y_button.bind("<Button-1>", lambda event, arg=Button.Y: self.hold(event, arg))
        self.softcon_a_button.bind("<Button-1>", lambda event, arg=Button.A: self.hold(event, arg))
        self.softcon_b_button.bind("<Button-1>", lambda event, arg=Button.B: self.hold(event, arg))
        self.softcon_home_button.bind("<Button-1>", lambda event, arg=Button.HOME: self.hold(event, arg))

        self.softcon_zl_button.bind("<ButtonRelease-1>", lambda event, arg=Button.ZL: self.holdEnd(event, arg))
        self.softcon_l_button.bind("<ButtonRelease-1>", lambda event, arg=Button.L: self.holdEnd(event, arg))
        self.softcon_minus_button.bind("<ButtonRelease-1>", lambda event, arg=Button.MINUS: self.holdEnd(event, arg))
        self.softcon_l_click_button.bind("<ButtonRelease-1>", lambda event, arg=Button.LCLICK: self.holdEnd(event, arg))
        self.softcon_up_button.bind("<ButtonRelease-1>", lambda event, arg=Hat.TOP: self.holdEnd(event, arg))
        self.softcon_left_button.bind("<ButtonRelease-1>", lambda event, arg=Hat.LEFT: self.holdEnd(event, arg))
        self.softcon_right_button.bind("<ButtonRelease-1>", lambda event, arg=Hat.RIGHT: self.holdEnd(event, arg))
        self.softcon_down_button.bind("<ButtonRelease-1>", lambda event, arg=Hat.BTM: self.holdEnd(event, arg))
        self.softcon_capture_button.bind(
            "<ButtonRelease-1>", lambda event, arg=Button.CAPTURE: self.holdEnd(event, arg)
        )
        self.softcon_zr_button.bind("<ButtonRelease-1>", lambda event, arg=Button.ZR: self.holdEnd(event, arg))
        self.softcon_r_button.bind("<ButtonRelease-1>", lambda event, arg=Button.R: self.holdEnd(event, arg))
        self.softcon_plus_button.bind("<ButtonRelease-1>", lambda event, arg=Button.PLUS: self.holdEnd(event, arg))
        self.softcon_r_click_button.bind("<ButtonRelease-1>", lambda event, arg=Button.R: self.holdEnd(event, arg))
        self.softcon_x_button.bind("<ButtonRelease-1>", lambda event, arg=Button.X: self.holdEnd(event, arg))
        self.softcon_y_button.bind("<ButtonRelease-1>", lambda event, arg=Button.Y: self.holdEnd(event, arg))
        self.softcon_a_button.bind("<ButtonRelease-1>", lambda event, arg=Button.A: self.holdEnd(event, arg))
        self.softcon_b_button.bind("<ButtonRelease-1>", lambda event, arg=Button.B: self.holdEnd(event, arg))
        self.softcon_home_button.bind("<ButtonRelease-1>", lambda event, arg=Button.HOME: self.holdEnd(event, arg))

        self.softcon_zl_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Button.ZL: self.holdEndSkip(event, arg)
        )
        self.softcon_l_button.bind("<Shift-ButtonRelease-1>", lambda event, arg=Button.L: self.holdEndSkip(event, arg))
        self.softcon_minus_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Button.MINUS: self.holdEndSkip(event, arg)
        )
        self.softcon_l_click_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Button.LCLICK: self.holdEndSkip(event, arg)
        )
        self.softcon_up_button.bind("<Shift-ButtonRelease-1>", lambda event, arg=Hat.TOP: self.holdEndSkip(event, arg))
        self.softcon_left_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Hat.LEFT: self.holdEndSkip(event, arg)
        )
        self.softcon_right_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Hat.RIGHT: self.holdEndSkip(event, arg)
        )
        self.softcon_down_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Hat.BTM: self.holdEndSkip(event, arg)
        )
        self.softcon_capture_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Button.CAPTURE: self.holdEndSkip(event, arg)
        )
        self.softcon_zr_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Button.ZR: self.holdEndSkip(event, arg)
        )
        self.softcon_r_button.bind("<Shift-ButtonRelease-1>", lambda event, arg=Button.R: self.holdEndSkip(event, arg))
        self.softcon_plus_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Button.PLUS: self.holdEndSkip(event, arg)
        )
        self.softcon_r_click_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Button.R: self.holdEndSkip(event, arg)
        )
        self.softcon_x_button.bind("<Shift-ButtonRelease-1>", lambda event, arg=Button.X: self.holdEndSkip(event, arg))
        self.softcon_y_button.bind("<Shift-ButtonRelease-1>", lambda event, arg=Button.Y: self.holdEndSkip(event, arg))
        self.softcon_a_button.bind("<Shift-ButtonRelease-1>", lambda event, arg=Button.A: self.holdEndSkip(event, arg))
        self.softcon_b_button.bind("<Shift-ButtonRelease-1>", lambda event, arg=Button.B: self.holdEndSkip(event, arg))
        self.softcon_home_button.bind(
            "<Shift-ButtonRelease-1>", lambda event, arg=Button.HOME: self.holdEndSkip(event, arg)
        )

        # Main widget
        self.mainwindow = self.main_frame

        self.root.protocol("WM_DELETE_WINDOW", self.exit)
        self.preview.startCapture()
        self.root.after(500, self.poll_command_watch)
        self.set_serial_data_format()

        # Output画面/Software-Controllerを再配置する
        self.replace_right_frame_widget()

        self.menu = PokeController_Menubar(self)
        self.root.config(menu=self.menu)

        # logging.debug(f'python version: {sys.version}')

    def openCamera(self):
        self.camera.openCamera(self.camera_id.get())

    def assignCamera(self, event):
        if platform.system() != "Linux":
            self.camera_name_fromDLL.set(self.camera_dic[self.camera_id.get()])

    def locateCameraCmbbox(self):
        if platform.system() == "Windows":
            try:
                import clr

                clr.AddReference(r"..\DirectShowLib\DirectShowLib-2005")
                from DirectShowLib import DsDevice, FilterCategory  # type: ignore

                # Get names of detected camera devices
                captureDevices = DsDevice.GetDevicesOfCat(FilterCategory.VideoInputDevice)
                self.camera_dic = {
                    cam_id: device.Name + " (" + device.DevicePath + ")" for cam_id, device in enumerate(captureDevices)
                }
            except Exception:
                import device as dv

                captureDevices = dv.getDeviceList()
                self.camera_dic = {cam_id: device[0] for cam_id, device in enumerate(captureDevices)}

            self.camera_dic[str(max(list(self.camera_dic.keys())) + 1)] = "Disable"
            self.camera_name_cb["values"] = ["No." + str(k) + ": " + v for k, v in self.camera_dic.items()]
            self._logger.debug(f"Camera list: {[device for device in self.camera_dic.values()]}")
            dev_num = len(self.camera_dic)
        elif platform.system() == "Darwin":
            cmd = 'system_profiler SPCameraDataType | grep "^    [^ ]" | sed "s/    //" | sed "s/://" '
            res = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
            # 出力結果の加工
            ret = res.stdout.decode("utf-8")
            cam_list = list(filter(lambda a: a != "", ret.split("\n")))
            self.camera_dic = {cam_id: camera_name for cam_id, camera_name in enumerate(cam_list)}
            dev_num = len(self.camera_name_cb["values"])
            self.camera_dic[str(max(list(self.camera_dic.keys())) + 1)] = "Disable"
            self.camera_name_cb["values"] = ["No." + str(k) + ": " + v for k, v in self.camera_dic.items()]
        else:
            return False
        if self.camera_id.get() > dev_num - 1:
            print("Inappropriate camera ID! -> set to 0")
            self._logger.debug("Inappropriate camera ID! -> set to 0")
            self.camera_id.set(0)
            if dev_num == 0:
                print("No camera devices can be found.")
                self._logger.debug("No camera devices can be found.")

        #
        self.camera_id_entry.bind("<KeyRelease>", self.assignCamera)
        self.camera_name_cb.current(self.camera_id.get())

    def locateDeviceCmbbox(self):
        # ポート情報取得
        devices_description_list = []
        devices_list = list(list_ports.comports())
        for d in devices_list:
            devices_description_list.append(d.description)
        self.serial_devices = sorted(devices_description_list, key=lambda s: int(re.search(r"COM(\d+)", s).groups()[0]))
        self.serial_device_name_cb["values"] = self.serial_devices

    def saveCapture(self):
        self.camera.saveCapture()

    def _area_capture_rect(self, image):
        try:
            x, y, width, height = map(int, self.area_capture_roi.get().split(","))
        except ValueError:
            raise ValueError("ROI must be x,y,width,height")
        frame_height, frame_width = image.shape[:2]
        if width <= 0 or height <= 0:
            return 0, 0, frame_width, frame_height
        x, y = max(0, x), max(0, y)
        width, height = min(width, frame_width - x), min(height, frame_height - y)
        if width <= 0 or height <= 0:
            raise ValueError("ROI is outside the camera image")
        return x, y, width, height

    def area_capture_roi_changed(self, *_):
        """Typed ROI edits behave the same as a Shift-drag selection."""
        if self.area_capture_active.get() and hasattr(self, "camera") and getattr(self.camera, "image_bgr", None) is not None:
            self.root.after_idle(self.preview_area_capture)

    def toggle_area_capture_active(self):
        if self.area_capture_active.get():
            self.area_capture_status.set("Area Capture preview: active")
            self.preview_area_capture()
            return
        if hasattr(self, "preview"):
            self.preview.deleteImageRect("AreaCaptureROI")
        slot = self._area_capture_preview_slot()
        if slot in self.area_capture_inline:
            self.area_capture_inline[slot][0].pack_forget()
        self.area_capture_status.set("Area Capture preview: inactive")

    def save_area_capture(self):
        image = getattr(self.camera, "image_bgr", None)
        if image is None:
            tkmsg.showwarning("Area Capture", "Start the camera before capturing an area.")
            return
        try:
            x, y, width, height = self._area_capture_rect(image)
        except ValueError as error:
            tkmsg.showwarning("Area Capture", str(error))
            return
        directory = "Captures_Area"
        os.makedirs(directory, exist_ok=True)
        filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f") + ".png"
        path = os.path.join(directory, filename)
        if cv2.imwrite(path, image[y:y + height, x:x + width]):
            self.area_capture_status.set("Saved: " + path)
            print("Area capture succeeded: " + path)
        else:
            self.area_capture_status.set("Capture failed")

    def open_area_capture_dir(self):
        directory = "Captures_Area"
        os.makedirs(directory, exist_ok=True)
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", os.path.abspath(directory)])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", directory])

    def choose_area_capture_background(self):
        from tkinter import colorchooser
        _, color = colorchooser.askcolor(color=self.area_capture_background.get(), parent=self.root)
        if color:
            self.area_capture_background.set(color)

    def apply_area_capture_background(self, *_):
        color = self.area_capture_background.get()
        for _, canvas in self.area_capture_inline.values():
            try:
                canvas.configure(background=color)
            except tk.TclError:
                pass

    def select_area_capture_preview(self, *event):
        """An Area Capture preview owns its panel, so its text log is disabled."""
        slot = self.area_capture_output_target.get().split(" ", 1)[0]
        if slot not in self.panel_slots:
            return
        if self.panel_slots[slot].get().startswith("Log:"):
            if not tkmsg.askyesno("Area Capture preview", "Assign this panel to Area Capture?\nText log output for this panel will be disabled."):
                self.area_capture_output_target.set("")
                return
            self.panel_slots[slot].set("Image")
            self.apply_panel_assignment()
        elif self.panel_slots[slot].get() != "Image":
            self.panel_slots[slot].set("Image")
            self.apply_panel_assignment()
        self.preview_area_capture()

    def preview_area_capture(self):
        if not self.area_capture_active.get():
            return None
        self.area_capture_status.set("Area Capture preview: active")
        image = getattr(self.camera, "image_bgr", None)
        if image is None:
            return None
        try:
            x, y, width, height = self._area_capture_rect(image)
        except ValueError:
            return None
        if hasattr(self, "preview"):
            self.preview.deleteImageRect("AreaCaptureROI")
            self.preview.ImgRect(x, y, x + width, y + height, "red", "AreaCaptureROI", 0, flag=False)
        crop = image[y:y + height, x:x + width].copy()
        slot = self.area_capture_output_target.get().split(" ", 1)[0]
        if slot in self.panel_widgets:
            self.display_area_capture_inline(slot, crop)
        return crop

    def _ensure_area_capture_inline(self, slot):
        if slot in self.area_capture_inline:
            return self.area_capture_inline[slot]
        panel, _, _ = self.panel_widgets[slot]
        holder = ttk.Frame(panel)
        canvas = tk.Canvas(holder, background=self.area_capture_background.get(), highlightthickness=0)
        y_scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        x_scroll = ttk.Scrollbar(holder, orient="horizontal", command=canvas.xview)
        canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        canvas.grid(column=0, row=0, sticky="nsew")
        y_scroll.grid(column=1, row=0, sticky="ns")
        x_scroll.grid(column=0, row=1, sticky="ew")
        controls = ttk.Frame(holder)
        controls.grid(column=0, columnspan=2, row=2, pady=(3, 0), sticky="ew")
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)

        def scroll(event):
            canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

        def zoom(event):
            current = self.area_capture_inline_zoom.get(slot, 1.0)
            self.area_capture_inline_zoom[slot] = max(0.25, min(8.0, current * (1.25 if event.delta > 0 else 0.8)))
            self.preview_area_capture()

        def button_zoom(factor):
            current = self.area_capture_inline_zoom.get(slot, 1.0)
            self.area_capture_inline_zoom[slot] = max(0.25, min(8.0, current * factor))
            self.preview_area_capture()

        def button_resize(edge, direction):
            self.resize_area_capture(edge, direction)

        canvas.bind("<MouseWheel>", scroll)
        canvas.bind("<Control-MouseWheel>", zoom)
        ttk.Button(controls, text="−", width=3, command=lambda: button_zoom(0.8)).pack(side="left", padx=2)
        ttk.Button(controls, text="+", width=3, command=lambda: button_zoom(1.25)).pack(side="left", padx=2)
        ttk.Label(controls, text="Left edge").pack(side="left", padx=(10, 2))
        ttk.Button(controls, text="<", width=3, command=lambda: button_resize("left", -1)).pack(side="left", padx=1)
        ttk.Button(controls, text=">", width=3, command=lambda: button_resize("left", 1)).pack(side="left", padx=1)
        ttk.Label(controls, text="Right edge").pack(side="left", padx=(6, 2))
        ttk.Button(controls, text="<", width=3, command=lambda: button_resize("right", -1)).pack(side="left", padx=1)
        ttk.Button(controls, text=">", width=3, command=lambda: button_resize("right", 1)).pack(side="left", padx=1)
        ttk.Label(controls, text="Top edge").pack(side="left", padx=(6, 2))
        ttk.Button(controls, text="^", width=3, command=lambda: button_resize("top", -1)).pack(side="left", padx=1)
        ttk.Button(controls, text="v", width=3, command=lambda: button_resize("top", 1)).pack(side="left", padx=1)
        ttk.Label(controls, text="Bottom edge").pack(side="left", padx=(6, 2))
        ttk.Button(controls, text="^", width=3, command=lambda: button_resize("bottom", -1)).pack(side="left", padx=1)
        ttk.Button(controls, text="v", width=3, command=lambda: button_resize("bottom", 1)).pack(side="left", padx=1)
        self.area_capture_inline[slot] = (holder, canvas)
        self.area_capture_inline_zoom[slot] = 1.0
        return holder, canvas

    def display_area_capture_inline(self, slot, image_bgr):
        holder, canvas = self._ensure_area_capture_inline(slot)
        zoom = self.area_capture_inline_zoom.get(slot, 1.0)
        h, w = image_bgr.shape[:2]
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb).resize((max(1, int(w * zoom)), max(1, int(h * zoom))))
        tk_image = ImageTk.PhotoImage(image)
        canvas.delete("area_capture")
        canvas.create_image(0, 0, anchor="nw", image=tk_image, tags="area_capture")
        canvas.image = tk_image
        canvas.configure(scrollregion=(0, 0, image.width, image.height))
        holder.pack(expand=True, fill="both", padx=5, pady=5)

    def move_area_capture(self, dx, dy):
        image = getattr(self.camera, "image_bgr", None)
        if image is None:
            return
        try:
            x, y, width, height = self._area_capture_rect(image)
        except ValueError:
            return
        x = max(0, min(x + dx, image.shape[1] - width))
        y = max(0, min(y + dy, image.shape[0] - height))
        self.area_capture_roi.set("{},{},{},{}".format(x, y, width, height))
        self.preview_area_capture()

    def resize_area_capture(self, edge, direction):
        """Move one ROI edge; the opposite edge stays fixed."""
        image = getattr(self.camera, "image_bgr", None)
        if image is None:
            return
        try:
            x, y, width, height = self._area_capture_rect(image)
        except ValueError:
            return
        amount = self.area_capture_step.get() * direction
        if edge == "left":
            new_x = max(0, min(x + amount, x + width - 1))
            width += x - new_x
            x = new_x
        elif edge == "right":
            width = max(1, min(image.shape[1] - x, width + amount))
        elif edge == "top":
            new_y = max(0, min(y + amount, y + height - 1))
            height += y - new_y
            y = new_y
        elif edge == "bottom":
            height = max(1, min(image.shape[0] - y, height + amount))
        self.area_capture_roi.set("{},{},{},{}".format(x, y, width, height))
        self.preview_area_capture()

    def open_area_capture_editor(self):
        if getattr(self.camera, "image_bgr", None) is None:
            tkmsg.showwarning("Area Capture", "Start the camera before opening the preview.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Area Capture preview / edit")
        slot = self._area_capture_preview_slot()
        zoom = tk.DoubleVar(value=self.area_capture_inline_zoom.get(slot, 1.0))
        canvas = tk.Canvas(dialog, width=640, height=420, background="#303030")
        y_scroll = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        x_scroll = ttk.Scrollbar(dialog, orient="horizontal", command=canvas.xview)
        canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        canvas.grid(column=0, row=1, columnspan=5, sticky="nsew")
        y_scroll.grid(column=5, row=1, sticky="ns")
        x_scroll.grid(column=0, columnspan=5, row=2, sticky="ew")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        def refresh():
            crop = self.preview_area_capture()
            if crop is None:
                return
            h, w = crop.shape[:2]
            scale = zoom.get()
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            picture = Image.fromarray(rgb).resize((max(1, int(w * scale)), max(1, int(h * scale))))
            tk_picture = ImageTk.PhotoImage(picture)
            canvas.delete("preview")
            canvas.create_image(0, 0, anchor="nw", image=tk_picture, tags="preview")
            canvas.image = tk_picture
            canvas.configure(scrollregion=(0, 0, picture.width, picture.height))

        def adjust(dx, dy):
            self.move_area_capture(dx * self.area_capture_step.get(), dy * self.area_capture_step.get())
            refresh()

        def change_zoom(factor):
            zoom.set(max(0.25, min(8.0, zoom.get() * factor)))
            if slot:
                self.area_capture_inline_zoom[slot] = zoom.get()
            self.preview_area_capture()
            refresh()

        ttk.Button(dialog, text="−", command=lambda: change_zoom(0.8)).grid(column=0, row=0, padx=3, pady=4)
        ttk.Label(dialog, textvariable=zoom).grid(column=1, row=0, padx=3)
        ttk.Button(dialog, text="+", command=lambda: change_zoom(1.25)).grid(column=2, row=0, padx=3, pady=4)
        ttk.Button(dialog, text="←", command=lambda: adjust(-1, 0)).grid(column=3, row=0, padx=3)
        ttk.Button(dialog, text="↑", command=lambda: adjust(0, -1)).grid(column=4, row=0, padx=3)
        ttk.Button(dialog, text="↓", command=lambda: adjust(0, 1)).grid(column=3, row=3, padx=3, pady=4)
        ttk.Button(dialog, text="→", command=lambda: adjust(1, 0)).grid(column=4, row=3, padx=3, pady=4)
        refresh()

    def OpenCaptureDir(self):
        directory = "Captures"
        self._logger.debug(f"Open folder: '{directory}'")
        if platform.system() == "Windows":
            subprocess.call(f'explorer "{directory}"')
        elif platform.system() == "Darwin":
            command = f'open "{directory}"'
            subprocess.run(command, shell=True)

    def sendWinNotfication(self):
        global flag_import_plyer
        if flag_import_plyer:
            notification.notify(
                title=f"{Constant.NAME} ver.{Constant.VERSION} (profile:{self.profile})",
                message="Notification Test",
                timeout=5,
            )
        else:
            print('"plyer" is not installed.')

    def sendLineImage(self):
        def sendMessage(src):
            Line = Line_Notify()
            Line.send_message("---Manual---", src, "token")

        src = self.camera.readFrame()
        thread = threading.Thread(target=sendMessage, args=(src,))
        thread.start()

    def sendDiscordImage(self):
        def sendMessage(src):
            Discord = Discord_Notify()
            Discord.send_message(notification_message="---Manual---", image=src)

        src = self.camera.readFrame()
        thread = threading.Thread(target=sendMessage, args=(src,))
        thread.start()

    def OpenCommandDir(self):
        selected_tab = self.command_nb.tab(self.command_nb.select(), "text")
        if selected_tab == "Mcu Command":
            directory = os.path.join("Commands", "McuCommands")
        elif selected_tab == "Python Sample Command":
            directory = os.path.join(dirname(dirname(abspath(__file__))), "DevStudio", "SampleCommands")
        else:
            directory = os.path.join("Commands", "PythonCommands")
        self._logger.debug(f"Open folder: '{directory}'")
        if platform.system() == "Windows":
            subprocess.call(f'explorer "{directory}"')
        elif platform.system() == "Darwin":
            command = f'open "{directory}"'
            subprocess.run(command, shell=True)

    def _update_others_scrollregion(self, event=None):
        self.others_canvas.configure(scrollregion=self.others_canvas.bbox("all"))

    def _resize_others_content(self, event):
        self.others_canvas.itemconfigure(self.others_canvas_window, width=max(1, event.width))

    def _scroll_others_with_wheel(self, event):
        canvas = getattr(self, "others_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
        if not (canvas.winfo_rootx() <= x < canvas.winfo_rootx() + canvas.winfo_width() and
                canvas.winfo_rooty() <= y < canvas.winfo_rooty() + canvas.winfo_height()):
            return
        canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _update_input_set_scrollregion(self, event=None):
        canvas = getattr(self, "input_set_canvas", None)
        if canvas is not None and canvas.winfo_exists():
            canvas.configure(scrollregion=canvas.bbox("all"))

    def _resize_input_set_content(self, event):
        self.input_set_canvas.itemconfigure(self.input_set_canvas_window, width=max(1, event.width))

    def _scroll_input_set_with_wheel(self, event):
        canvas = getattr(self, "input_set_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
        if not (canvas.winfo_rootx() <= x < canvas.winfo_rootx() + canvas.winfo_width() and
                canvas.winfo_rooty() <= y < canvas.winfo_rooty() + canvas.winfo_height()):
            return
        canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def refresh_command_watch_commands(self):
        if not hasattr(self, "command_watch_command_cb"):
            return
        values = list(getattr(self, "py_cb_all", [])) + list(getattr(self, "sample_py_cb_all", []))
        self.command_watch_command_cb.configure(values=values)
        if values and self.command_watch_command.get() not in values:
            self.command_watch_command.set(values[0])
        if hasattr(self, "record_variable_command_cb"):
            self.record_variable_command_cb.configure(values=values)
            if values and self.record_variable_command.get() not in values:
                self.record_variable_command.set(values[0])

    def open_image_match_debug(self):
        """Inspect a command's declared images without starting the command."""
        existing = getattr(self, "image_match_debug_dialog", None)
        if existing is not None and existing.winfo_exists():
            existing.focus_force()
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Image match debug")
        dialog.transient(self.root)
        self.image_match_debug_dialog = dialog
        self.image_match_debug_active = False
        self.image_match_debug_templates = {}
        self.image_match_debug_command = tk.StringVar(value=self.py_cb.get() if hasattr(self, "py_cb") else "")
        self.image_match_debug_output = tk.StringVar(value="Output#2")
        self.image_match_debug_status = tk.StringVar(value="Select a command that implements get_detection_targets().")
        ttk.Label(dialog, text="Command:").grid(column=0, row=0, padx=6, pady=5, sticky="w")
        ttk.Combobox(dialog, state="readonly", width=48, textvariable=self.image_match_debug_command,
                     values=list(getattr(self, "py_cb_all", [])) + list(getattr(self, "sample_py_cb_all", []))).grid(column=1, columnspan=2, row=0, padx=6, pady=5, sticky="ew")
        ttk.Label(dialog, text="Log output:").grid(column=0, row=1, padx=6, pady=5, sticky="w")
        ttk.Combobox(dialog, state="readonly", width=14, textvariable=self.image_match_debug_output,
                     values=("Output#1", "Output#2")).grid(column=1, row=1, padx=6, pady=5, sticky="w")
        self.image_match_debug_button_popup = ttk.Button(dialog, text="Start monitoring", command=self.toggle_image_match_debug)
        self.image_match_debug_button_popup.grid(column=2, row=1, padx=6, pady=5)
        ttk.Label(dialog, textvariable=self.image_match_debug_status).grid(column=0, columnspan=3, row=2, padx=6, pady=(0, 6), sticky="w")
        dialog.protocol("WM_DELETE_WINDOW", self.close_image_match_debug)

    def close_image_match_debug(self):
        self.image_match_debug_active = False
        dialog = getattr(self, "image_match_debug_dialog", None)
        if dialog is not None and dialog.winfo_exists():
            dialog.destroy()

    def toggle_image_match_debug(self):
        self.image_match_debug_active = not self.image_match_debug_active
        if self.image_match_debug_active:
            self.image_match_debug_button_popup.configure(text="Stop monitoring")
            self.poll_image_match_debug()
        else:
            self.image_match_debug_button_popup.configure(text="Start monitoring")

    def poll_image_match_debug(self):
        dialog = getattr(self, "image_match_debug_dialog", None)
        if not getattr(self, "image_match_debug_active", False) or dialog is None or not dialog.winfo_exists():
            return
        try:
            selected = self.image_match_debug_command.get()
            command_class = next((item for item in list(getattr(self, "py_classes", [])) + list(getattr(self, "sample_py_classes", [])) if item.NAME == selected), None)
            if command_class is None:
                self.image_match_debug_status.set("Command was not found. Reload Commands and select it again.")
            else:
                targets = command_class.get_detection_targets()
                frame = getattr(self.camera, "image_bgr", None)
                if frame is None:
                    self.image_match_debug_status.set("Waiting for a camera frame.")
                elif not targets:
                    self.image_match_debug_status.set("This command has no declared image targets.")
                else:
                    rows = ["[Image match debug] " + selected]
                    for target in targets:
                        name = str(target.get("name", os.path.basename(target.get("path", "target"))))
                        path = target.get("path", "")
                        image = self.image_match_debug_templates.get(path)
                        if image is None and path:
                            image = cv2.imread(path, cv2.IMREAD_COLOR)
                            self.image_match_debug_templates[path] = image
                        if image is None:
                            rows.append("{}: template missing ({})".format(name, path))
                            continue
                        x, y, width, height = target.get("roi", (0, 0, 0, 0))
                        height_frame, width_frame = frame.shape[:2]
                        reference_width, reference_height = target.get("reference_resolution", (0, 0))
                        reference_width, reference_height = int(reference_width or 0), int(reference_height or 0)
                        scale_x = float(width_frame) / reference_width if reference_width else 1.0
                        scale_y = float(height_frame) / reference_height if reference_height else 1.0
                        x, y = max(0, int(round(int(x) * scale_x))), max(0, int(round(int(y) * scale_y)))
                        width = int(round(int(width) * scale_x)) if int(width) else (width_frame - x)
                        height = int(round(int(height) * scale_y)) if int(height) else (height_frame - y)
                        region = frame[y:min(height_frame, y + height), x:min(width_frame, x + width)]
                        if region.size == 0:
                            rows.append("{}: ROI is outside the camera frame".format(name))
                            continue
                        scaled_image = image
                        if reference_width or reference_height:
                            scaled_image = cv2.resize(image, (max(1, int(round(image.shape[1] * scale_x))),
                                                              max(1, int(round(image.shape[0] * scale_y)))))
                        if target.get("grayscale", False):
                            region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                            scaled_image = cv2.cvtColor(scaled_image, cv2.COLOR_BGR2GRAY)
                        if region.shape[0] < scaled_image.shape[0] or region.shape[1] < scaled_image.shape[1]:
                            rows.append("{}: ROI is smaller than template".format(name))
                            continue
                        _, score, _, _ = cv2.minMaxLoc(cv2.matchTemplate(region, scaled_image, cv2.TM_CCOEFF_NORMED))
                        threshold = float(target.get("threshold", 0.8))
                        rows.append("{}: {:.1f}% / {:.1f}% {}".format(
                            name, score * 100, threshold * 100, "MATCH" if score >= threshold else "NO MATCH"))
                    self.show_output(self.image_match_debug_output.get(), text="\n".join(rows))
                    self.image_match_debug_status.set("Monitoring {} target(s) every 0.5 s.".format(len(targets)))
        except Exception as error:
            self.image_match_debug_status.set("Image debug error: " + str(error))
        self.root.after(500, self.poll_image_match_debug)

    def add_command_watch_variable(self):
        name = self.command_watch_variable.get().strip()
        if name and name not in self.command_watch_variables:
            self.command_watch_variables.append(name)
            self.command_watch_list.insert("end", name)
            self.command_watch_variable.set("")
            self.reset_command_watch()

    def remove_command_watch_variable(self):
        selected = self.command_watch_list.curselection()
        if selected:
            index = selected[0]
            del self.command_watch_variables[index]
            self.command_watch_list.delete(index)
            self.reset_command_watch()

    def reset_command_watch(self):
        if hasattr(self, "command_watch_last_values"):
            self.command_watch_last_values = {}

    def poll_command_watch(self):
        """Publish only changed public variables; never block the UI/command thread."""
        try:
            if self.command_watch_enabled.get() and self.command_watch_variables:
                command = getattr(self, "cur_command", None)
                expected = self.command_watch_command.get()
                if command is None or getattr(command, "NAME", "") != expected:
                    self.command_watch_status.set("Waiting for selected command to run.")
                else:
                    values = {}
                    for name in self.command_watch_variables:
                        if hasattr(command, name):
                            try:
                                values[name] = repr(getattr(command, name))
                            except Exception:
                                values[name] = "<unreadable>"
                        else:
                            values[name] = "<not set>"
                    if values != self.command_watch_last_values:
                        self.command_watch_last_values = values
                        message = "[Command Watch] " + expected + "\n" + "\n".join(
                            "{} = {}".format(name, value) for name, value in values.items()) + "\n"
                        self.show_output(self.command_watch_target.get(), text=message)
                    self.command_watch_status.set("Watching {} variable(s).".format(len(values)))
        finally:
            try:
                self.root.after(500, self.poll_command_watch)
            except tk.TclError:
                pass

    def open_dev_studio(self):
        """Launch the dependency-free PokeCon code search/merge helper."""
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        studio = os.path.join(project_dir, "DevStudio", "PokeConDevStudio.py")
        if not os.path.isfile(studio):
            tkmsg.showwarning("PokeCon Dev Studio", "DevStudio/PokeConDevStudio.py が見つかりません。")
            return
        try:
            # Do not let Dev Studio's initial code indexing share PokeCon's
            # process/console.  On Windows it is a detached child process, so
            # the main capture/controller UI returns immediately.
            options = {"cwd": os.path.dirname(studio), "close_fds": True}
            if platform.system() == "Windows":
                options["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) |
                                             getattr(subprocess, "DETACHED_PROCESS", 0x00000008))
            subprocess.Popen([sys.executable, studio, project_dir], **options)
            self.show_output("Analysis", text="PokeCon Dev Studio started in the background.")
        except OSError as error:
            tkmsg.showerror("PokeCon Dev Studio", "起動できませんでした。\n" + str(error))

    def set_init_device_name(self):
        for d in self.serial_devices:
            if int(self.com_port.get()) == int(re.search(r"COM(\d+)", d).groups()[0]):
                self.serial_device_name.set(d)
                break

    def set_cameraid(self, event=None):
        keys = [k for k, v in self.camera_dic.items() if "No." + str(k) + ": " + v == self.camera_name_cb.get()]
        if keys:
            ret = keys[0]
        else:
            ret = None
        self.camera_id.set(ret)
        if hasattr(self, "audio_filter_camera") and self.audio_filter_camera.get():
            self.update_audio_input_list()

    def set_device(self, event=None):
        self.com_port.set(int(re.search(r"COM(\d+)", self.serial_device_name.get()).groups()[0]))

    def set_serial_data_format(self, event=None):
        KeyPress.serial_data_format_name = self.serial_data_format_name.get()
        self.keys_software_controller.init_hat()
        self.preview.changeRightMouseMode(self.serial_data_format_name.get())

        if self.serial_data_format_name.get() == "3DS Controller":
            print("ボーレートを強制的に115200に変更します。")
            self.baud_rate.set("115200")
        else:
            print("ボーレートを強制的に9600に変更します。")
            self.baud_rate.set("9600")
        self.activateSerial()

    def applyFps(self, event=None):
        print("changed FPS to: " + self.fps.get() + " [fps]")
        self.preview.setFps(self.fps.get())

    def applyBaudRate(self, event=None):
        pass

    def applyWindowSize(self, event=None):
        width, height = map(int, self.show_size.get().split("x"))
        self.preview.setShowsize(height, width)
        self.changeAreaSize()

        if self.show_size_tmp != self.show_size_cb["values"].index(self.show_size_cb.get()):
            ret = tkmsg.askokcancel("確認", "この画面サイズに変更しますか？")
        else:
            return

        if ret:
            self.show_size_tmp = self.show_size_cb["values"].index(self.show_size_cb.get())
        else:
            self.show_size_cb.current(self.show_size_tmp)
            width_bef, height_bef = map(int, self.show_size.get().split("x"))
            self.preview.setShowsize(height_bef, width_bef)
            # self.show_size_tmp = self.show_size_cb['values'].index(self.show_size_cb.get())

        self.changeAreaSize()

    def activateSerial(self):
        if self.ser.isOpened():
            print("Port is already opened and being closed.")
            self.ser.closeSerial()
            self.keyPress = None
            self.activateSerial()
        else:
            if self.ser.openSerial(self.com_port.get(), self.com_port_name.get(), self.baud_rate.get()):
                print("COM Port " + str(self.com_port.get()) + " connected successfully")
                self._logger.debug("COM Port " + str(self.com_port.get()) + " connected successfully")
                self.keyPress = KeyPress(self.ser)
                self.settings.com_port.set(self.com_port.get())
                self.settings.baud_rate.set(self.baud_rate.get())
                self.settings.save()

    def inactivateSerial(self):
        if self.ser.isOpened():
            print("Port is already opened and being closed.")
            self.ser.closeSerial()
            self.keyPress = None

    def activateKeyboard(self):
        if self.is_use_keyboard.get():
            # enable Keyboard as controller
            if self.keyboard is None:
                self.keyboard = SwitchKeyboardController(self.keyPress)
                self.keyboard.listen()

            # bind focus
            if platform.system() != "Linux":
                self.root.bind("<FocusIn>", self.onFocusInController)
                self.root.bind("<FocusOut>", self.onFocusOutController)

        else:
            # stop listening to keyboard events
            if self.keyboard is not None:
                self.keyboard.stop()
                self.keyboard = None

            if platform.system() != "Linux":
                self.root.bind("<FocusIn>", lambda _: None)
                self.root.bind("<FocusOut>", lambda _: None)

    def onFocusInController(self, event):
        # enable Keyboard as controller
        if event.widget == self.root and self.keyboard is None:
            self.keyboard = SwitchKeyboardController(self.keyPress)
            self.keyboard.listen()

    def onFocusOutController(self, event):
        # stop listening to keyboard events
        if event.widget == self.root and self.keyboard is not None:
            self.keyboard.stop()
            self.keyboard = None

    def createControllerWindow(self):
        if self.controller is not None:
            self.controller.focus_force()
            return

        window = ControllerGUI(self.root, self.ser)
        window.protocol("WM_DELETE_WINDOW", self.closingController)
        self.controller = window

    def activate_Left_stick_mouse(self):
        self.preview.ApplyLStickMouse()

    def activate_Right_stick_mouse(self):
        self.preview.ApplyRStickMouse()

    def run_ProController(self):
        if self.procon is not None:
            self.procon = None
        self.procon = ProController()
        self.procon.controller_loop(self.ser, self.flag_record, self.ControllerLogDir)

    def mode_change_show_value(self):
        Command.isSimilarity = self.is_show_value.get()

    def mode_change_show_guide(self):
        Command.isGuide = self.is_show_guide.get()

    def mode_change_show_image(self):
        Command.isImage = self.is_show_image.get()

    def mode_change_notification(self, *event):
        Command.isWinNotStart = self.is_win_notification_start.get()
        Command.isWinNotEnd = self.is_win_notification_end.get()
        Command.isLineNotStart = self.is_line_notification_start.get()
        Command.isLineNotEnd = self.is_line_notification_end.get()
        Command.isDiscordNotStart = self.is_discord_notification_start.get()
        Command.isDiscordNotEnd = self.is_discord_notification_end.get()

    def change_buttons_position(self, *event):
        Command.pos_dialogue_buttons = self.pos_dialogue_buttons.get()

    def mode_change_Pro_Controller(self):
        if self.is_use_Pro_Controller.get():  # Proconでの操作を有効化する。
            try:
                self.closingController()
            except Exception:
                pass
            ProController.flag_procon = True
            self.flag_record = self.is_record_Pro_Controller.get()
            self.ControllerLogDir = "Controller_Log"
            self.record_pro_controller_checkbox["state"] = "disabled"
            thread1 = threading.Thread(target=self.run_ProController)
            thread1.start()
            self.controller_nb.tab(tab_id=0, state="disabled")
            self.controller_nb.tab(tab_id=1, state="disabled")
            self.controller_nb.tab(tab_id=3, state="disabled")
            self.controller_nb.tab(tab_id=4, state="disabled")
            self.start_top_button["state"] = "disabled"
            self.simplecon_top_button["state"] = "disabled"

        else:  # Proconでの操作を無効化する。
            ProController.flag_procon = False
            self.record_pro_controller_checkbox["state"] = "normal"
            self.controller_nb.tab(tab_id=0, state="normal")
            self.controller_nb.tab(tab_id=1, state="normal")
            self.controller_nb.tab(tab_id=3, state="normal")
            self.controller_nb.tab(tab_id=4, state="normal")
            self.start_top_button["state"] = "normal"
            self.simplecon_top_button["state"] = "normal"

    def record_Pro_Controller(self):
        self.flag_record = self.is_record_Pro_Controller.get()

    # def createGetFromHomeWindow(self):
    #     if self.poke_treeview is not None:
    #         self.poke_treeview.focus_force()
    #         return
    #
    #     window2 = GetFromHomeGUI(self.root, self.settings.season, self.settings.is_SingleBattle)
    #     window2.protocol("WM_DELETE_WINDOW", self.closingGetFromHome)
    #     self.poke_treeview = window2

    def loadCommands(self):
        # PythonCommands
        self.py_loader = CommandLoader(
            util.ospath("Commands/PythonCommands"), PythonCommandBase.PythonCommand
        )  # コマンドの読み込み
        self.py_classes = self.py_loader.load()
        self.py_tags = []
        for c in self.py_classes:
            self.py_tags.extend(c.TAGS)
        self.py_tags = set(self.py_tags)
        self.py_tags_values = sorted([s for s in self.py_tags if s[0] != "@"]) + sorted(
            [s for s in self.py_tags if s[0] == "@"]
        )  # ディレクトリのタグは後半にまとめる
        self.command_filter_py_cb["values"] = ["-"] + self.py_tags_values

        # PythonSampleCommands authored in DevStudio and kept separate from
        # normal Commands/PythonCommands.
        sample_commands_path = os.path.join(dirname(dirname(abspath(__file__))), "DevStudio", "SampleCommands")
        self.sample_py_loader = FileCommandLoader(
            sample_commands_path, PythonSampleCommand.PythonSampleCommand)
        self.sample_py_classes = self.sample_py_loader.load()
        self.sample_py_tags = set(tag for command_class in self.sample_py_classes for tag in getattr(command_class, "TAGS", []))
        self.sample_py_tags_values = sorted([tag for tag in self.sample_py_tags if not tag.startswith("@")] ) + sorted(
            [tag for tag in self.sample_py_tags if tag.startswith("@")] )
        self.command_filter_sample_py_cb["values"] = ["-"] + self.sample_py_tags_values

        # McuCommands
        self.mcu_loader = CommandLoader(
            util.ospath("Commands/McuCommands"), McuCommandBase.McuCommand
        )  # コマンドの読み込み
        self.mcu_classes = self.mcu_loader.load()
        self.mcu_tags = []
        for c in self.mcu_classes:
            self.mcu_tags.extend(c.TAGS)
        self.mcu_tags = set(self.mcu_tags)
        self.mcu_tags_values = sorted([s for s in self.mcu_tags if s[0] != "@"]) + sorted(
            [s for s in self.mcu_tags if s[0] == "@"]
        )  # ディレクトリのタグは後半にまとめる
        self.command_filter_mcu_cb["values"] = ["-"] + self.mcu_tags_values

        self.setCommandItems()
        self.assignCommand()
        self.refresh_command_watch_commands()

    def setCommandItems(self):
        # PythonCommands
        self.py_cb_all = [c.NAME for c in self.py_classes]
        if self.command_filter_py_cb.get() == "-":
            self.py_cb["values"] = self.py_cb_all
        else:
            self.py_cb["values"] = [c.NAME for c in self.py_classes if self.command_filter_py_cb.get() in c.TAGS]
        if self.py_cb_all: self.py_cb.current(0)

        # PythonSampleCommands
        self.sample_py_cb_all = [c.NAME for c in self.sample_py_classes]
        if self.command_filter_sample_py_cb.get() == "-":
            self.sample_py_cb["values"] = self.sample_py_cb_all
        else:
            self.sample_py_cb["values"] = [c.NAME for c in self.sample_py_classes if self.command_filter_sample_py_cb.get() in c.TAGS]
        if self.sample_py_cb["values"]: self.sample_py_cb.current(0)

        # McuCommands
        self.mcu_cb_all = [c.NAME for c in self.mcu_classes]
        if self.command_filter_mcu_cb.get() == "-":
            self.mcu_cb["values"] = self.mcu_cb_all
        else:
            self.mcu_cb["values"] = [c.NAME for c in self.mcu_classes if self.command_filter_mcu_cb.get() in c.TAGS]
        if self.mcu_cb_all: self.mcu_cb.current(0)

    def assignShortcutButton(self):
        self.assignCommand()
        if self.set_shortcut_num.get() == "(select)":
            print("not select num.")
        else:
            num = int(self.set_shortcut_num.get())
            self.shortcut_command_name[num] = self.cur_command.NAME

            selected_tab = self.command_nb.tab(self.command_nb.select(), "text")
            if selected_tab == "Python Command":
                self.shortcut_command_class[num] = "Python"
            elif selected_tab == "Python Sample Command":
                self.shortcut_command_class[num] = "Sample"
            elif selected_tab == "Mcu Command":
                self.shortcut_command_class[num] = "Mcu"
            if num == 1:
                self.shortcut_1.set(self.shortcut_command_name[num][:8])
                self.shortcut_button_1_tooltip.text = self.shortcut_command_name[num]
            elif num == 2:
                self.shortcut_2.set(self.shortcut_command_name[num][:8])
                self.shortcut_button_2_tooltip.text = self.shortcut_command_name[num]
            elif num == 3:
                self.shortcut_3.set(self.shortcut_command_name[num][:8])
                self.shortcut_button_3_tooltip.text = self.shortcut_command_name[num]
            elif num == 4:
                self.shortcut_4.set(self.shortcut_command_name[num][:8])
                self.shortcut_button_4_tooltip.text = self.shortcut_command_name[num]
            elif num == 5:
                self.shortcut_5.set(self.shortcut_command_name[num][:8])
                self.shortcut_button_5_tooltip.text = self.shortcut_command_name[num]
            elif num == 6:
                self.shortcut_6.set(self.shortcut_command_name[num][:8])
                self.shortcut_button_6_tooltip.text = self.shortcut_command_name[num]
            elif num == 7:
                self.shortcut_7.set(self.shortcut_command_name[num][:8])
                self.shortcut_button_7_tooltip.text = self.shortcut_command_name[num]
            elif num == 8:
                self.shortcut_8.set(self.shortcut_command_name[num][:8])
                self.shortcut_button_8_tooltip.text = self.shortcut_command_name[num]
            elif num == 9:
                self.shortcut_9.set(self.shortcut_command_name[num][:8])
                self.shortcut_button_9_tooltip.text = self.shortcut_command_name[num]
            elif num == 10:
                self.shortcut_10.set(self.shortcut_command_name[num][:8])
                self.shortcut_button_10_tooltip.text = self.shortcut_command_name[num]

    def assignCommand(self):
        # 選択されているコマンド名を取得する
        mcu_i = [i for i, name in enumerate([c.NAME for c in self.mcu_classes]) if name == self.mcu_cb.get()]
        self.mcu_cur_command = self.mcu_classes[mcu_i[0]]()  # MCUコマンドについて

        # pythonコマンドは画像認識を使うかどうかで分岐している
        py_i = [i for i, name in enumerate([c.NAME for c in self.py_classes]) if name == self.py_cb.get()]
        cmd_class = self.py_classes[py_i[0]]
        if issubclass(cmd_class, PythonCommandBase.ImageProcPythonCommand):
            try:  # 画像認識の際に認識位置を表示する引数追加。互換性のため従来のはexceptに。
                self.py_cur_command = cmd_class(self.camera, self.preview)
            except TypeError:
                self.py_cur_command = cmd_class(self.camera)
            except Exception:
                self.py_cur_command = cmd_class(self.camera)

        else:
            self.py_cur_command = cmd_class()

        sample_i = [i for i, name in enumerate([c.NAME for c in self.sample_py_classes]) if name == self.sample_py_cb.get()]
        self.sample_py_cur_command = self.sample_py_classes[sample_i[0]]() if sample_i else None

        selected_tab = self.command_nb.tab(self.command_nb.select(), "text")
        if selected_tab == "Python Command":
            self.cur_command = self.py_cur_command
        elif selected_tab == "Python Sample Command":
            self.cur_command = self.sample_py_cur_command
        elif selected_tab == "Mcu Command":
            self.cur_command = self.mcu_cur_command

    def assignShortcutCommand(self, num):
        commandtype = self.shortcut_command_class[num]
        commandname = self.shortcut_command_name[num]
        commandindex = -1
        if commandtype in ["Python", "PYTHON", "python", "Py", "PY", "py"]:
            # ループを回してショートカットに割り当てられているpy_classのindexを探索する
            for i, name in enumerate(self.py_cb["values"]):
                if name == commandname:
                    commandindex = i
                    break

            # cur_commnadにショートカットのコマンドを割り当てる。
            if commandindex == -1:
                print("shortcut Python command name error.")
                return False
            else:
                # pythonコマンドは画像認識を使うかどうかで分岐している
                cmd_class = self.py_classes[commandindex]
                if issubclass(cmd_class, PythonCommandBase.ImageProcPythonCommand):
                    try:  # 画像認識の際に認識位置を表示する引数追加。互換性のため従来のはexceptに。
                        self.py_cur_command = cmd_class(self.camera, self.preview)
                    except TypeError:
                        self.py_cur_command = cmd_class(self.camera)
                    except Exception:
                        self.py_cur_command = cmd_class(self.camera)
                else:
                    self.py_cur_command = cmd_class()
                self.cur_command = self.py_cur_command
            return True
        elif commandtype in ["Sample", "SAMPLE", "sample"]:
            for command_class in self.sample_py_classes:
                if command_class.NAME == commandname:
                    self.sample_py_cur_command = command_class()
                    self.cur_command = self.sample_py_cur_command
                    return True
            print("shortcut Python sample command name error.")
            return False
        elif commandtype in ["Mcu", "MCU", "mcu"]:
            # ループを回してショートカットに割り当てられているmcu_classのindexを探索する
            for i, name in enumerate(self.mcu_cb["values"]):
                if name == commandname:
                    commandindex = i
                    break
            # cur_commnadにショートカットのコマンドを割り当てる。
            if commandindex == -1:
                print("shortcut Mcu command name error.")
                return False
            else:
                self.mcu_cur_command = self.mcu_classes[commandindex]()  # MCUコマンドについて
            self.cur_command = self.mcu_cur_command
            return True
        elif commandtype == "None":
            print(f"shortcut command ({num}) is not assigned.")
            return False
        else:
            print("shortcut command type error.")
            return False

    def controllButtons(self, event):
        note = event.widget
        if note.tab(note.select(), "text") == "Shortcut":
            self.shortcut_set_button["state"] = "disabled"
            self.py_cb["values"] = self.py_cb_all
            self.sample_py_cb["values"] = self.sample_py_cb_all
            self.mcu_cb["values"] = self.mcu_cb_all
        else:
            self.shortcut_set_button["state"] = "normal"
            self.applyFilterPy()
            self.applyFilterSamplePy()
            self.applyFilterMcu()
        self._update_command_start_state()

    def _update_command_start_state(self):
        """Re-evaluate Start after reload, tab changes and filtering."""
        if not hasattr(self, "start_button") or self.start_button["text"] != "Start":
            return
        selected_tab = self.command_nb.tab(self.command_nb.select(), "text")
        command_boxes = {
            "Python Command": self.py_cb,
            "Python Sample Command": self.sample_py_cb,
            "Mcu Command": self.mcu_cb,
        }
        command_box = command_boxes.get(selected_tab)
        enabled = command_box is not None and bool(command_box["values"]) and bool(command_box.get())
        state = "normal" if enabled else "disabled"
        self.start_button["state"] = state
        self.start_top_button["state"] = state

    def reloadCommands(self):
        # 表示しているタブを読み取って、どのコマンドを表示しているか取得、リロード後もそれが選択されるようにする
        oldval_mcu = self.mcu_cb.get()
        oldval_py = self.py_cb.get()
        oldval_sample_py = self.sample_py_cb.get()

        self.py_classes = self.py_loader.reload()
        self.sample_py_classes = self.sample_py_loader.reload()
        self.mcu_classes = self.mcu_loader.reload()

        self.py_tags = []
        for c in self.py_classes:
            self.py_tags.extend(c.TAGS)
        self.py_tags = set(self.py_tags)
        self.py_tags_values = sorted([s for s in self.py_tags if s[0] != "@"]) + sorted(
            [s for s in self.py_tags if s[0] == "@"]
        )

        self.sample_py_tags = set(tag for command_class in self.sample_py_classes for tag in getattr(command_class, "TAGS", []))
        self.sample_py_tags_values = sorted([tag for tag in self.sample_py_tags if not tag.startswith("@")] ) + sorted(
            [tag for tag in self.sample_py_tags if tag.startswith("@")] )

        self.mcu_tags = []
        for c in self.mcu_classes:
            self.mcu_tags.extend(c.TAGS)
        self.mcu_tags = set(self.mcu_tags)
        self.mcu_tags_values = sorted([s for s in self.mcu_tags if s[0] != "@"]) + sorted(
            [s for s in self.mcu_tags if s[0] == "@"]
        )

        self.command_filter_py_cb["values"] = ["-"] + self.py_tags_values
        self.command_filter_sample_py_cb["values"] = ["-"] + self.sample_py_tags_values
        self.command_filter_mcu_cb["values"] = ["-"] + self.mcu_tags_values

        # Restore the command selecting state if possible
        self.setCommandItems()
        if oldval_mcu in self.mcu_cb["values"]:
            self.mcu_cb.set(oldval_mcu)
        if oldval_py in self.py_cb["values"]:
            self.py_cb.set(oldval_py)
        if oldval_sample_py in self.sample_py_cb["values"]:
            self.sample_py_cb.set(oldval_sample_py)
        self.assignCommand()
        self._update_command_start_state()
        print("Finished reloading command modules.")
        self._logger.info("Reloaded commands.")

    def applyFilterPy(self, event=None):
        if self.command_filter_py_cb.get() == "-":
            self.py_cb["values"] = self.py_cb_all
        else:
            self.py_cb["values"] = [c.NAME for c in self.py_classes if self.command_filter_py_cb.get() in c.TAGS]
            self.py_cb.current(0)
        self._update_command_start_state()

    def applyFilterMcu(self, event=None):
        if self.command_filter_mcu_cb.get() == "-":
            self.mcu_cb["values"] = self.mcu_cb_all
        else:
            self.mcu_cb["values"] = [c.NAME for c in self.mcu_classes if self.command_filter_mcu_cb.get() in c.TAGS]
            self.mcu_cb.current(0)
        self._update_command_start_state()

    def applyFilterSamplePy(self, event=None):
        if self.command_filter_sample_py_cb.get() == "-":
            self.sample_py_cb["values"] = self.sample_py_cb_all
        else:
            self.sample_py_cb["values"] = [c.NAME for c in self.sample_py_classes if self.command_filter_sample_py_cb.get() in c.TAGS]
        if self.sample_py_cb["values"]: self.sample_py_cb.current(0)
        self._update_command_start_state()

    def pausePlay(self, *event):
        Command.isPause = True
        self.pause_button["text"] = "Restart"
        self.pause_button["command"] = self.restartPlay

    def restartPlay(self, *event):
        Command.isPause = False
        self.pause_button["text"] = "Pause"
        self.pause_button["command"] = self.pausePlay

    def startPlay(self, *event):
        self.is_use_Pro_Controller.set(False)
        self.mode_change_Pro_Controller()
        # set and init selected command
        self.assignCommand()
        if self.cur_command is None:
            print("No commands have been assigned yet.")
            self._logger.info("No commands have been assigned yet.")
            return

        print(self.start_button["text"] + " " + self.cur_command.NAME)
        Command.cur_command_name = self.cur_command.NAME
        self._logger.info(self.start_button["text"] + " " + self.cur_command.NAME)
        self.cur_command.start(self.ser, self.stopPlayPost)

        self.start_button["text"] = "Stop"
        self.start_top_button["text"] = "Stop"
        self.start_button["command"] = self.stopPlay
        self.start_top_button["command"] = self.stopPlay
        self.reload_command_button["state"] = "disabled"
        self.shortcut_button_1["state"] = "disabled"
        self.shortcut_button_2["state"] = "disabled"
        self.shortcut_button_3["state"] = "disabled"
        self.shortcut_button_4["state"] = "disabled"
        self.shortcut_button_5["state"] = "disabled"
        self.shortcut_button_6["state"] = "disabled"
        self.shortcut_button_7["state"] = "disabled"
        self.shortcut_button_8["state"] = "disabled"
        self.shortcut_button_9["state"] = "disabled"
        self.shortcut_button_10["state"] = "disabled"
        self.pause_button["state"] = "normal"
        self.force_stop_button["state"] = "normal"

    def startShortcutPlay(self, *event, num=0):
        if self.cur_command is None:
            print("No commands have been assigned yet.")
            self._logger.info("No commands have been assigned yet.")

        self.is_use_Pro_Controller.set(False)
        self.mode_change_Pro_Controller()
        # set and init selected command
        flag = self.assignShortcutCommand(num)
        if flag:
            print(self.start_button["text"] + " " + self.cur_command.NAME)
            self._logger.info(self.start_button["text"] + " " + self.cur_command.NAME)
            Command.cur_command_name = self.cur_command.NAME
            self.cur_command.start(self.ser, self.stopPlayPost)

            self.start_button["text"] = "Stop"
            self.start_top_button["text"] = "Stop"
            self.start_button["command"] = self.stopPlay
            self.start_top_button["command"] = self.stopPlay
            self.start_button["state"] = "normal"
            self.start_top_button["state"] = "normal"
            self.reload_command_button["state"] = "disabled"
            self.shortcut_button_1["state"] = "disabled"
            self.shortcut_button_2["state"] = "disabled"
            self.shortcut_button_3["state"] = "disabled"
            self.shortcut_button_4["state"] = "disabled"
            self.shortcut_button_5["state"] = "disabled"
            self.shortcut_button_6["state"] = "disabled"
            self.shortcut_button_7["state"] = "disabled"
            self.shortcut_button_8["state"] = "disabled"
            self.shortcut_button_9["state"] = "disabled"
            self.shortcut_button_10["state"] = "disabled"
            self.pause_button["state"] = "normal"
            self.force_stop_button["state"] = "normal"
        else:
            pass

    def force_stop_play(self):
        """Immediately request cancellation for a misbehaving Python command.

        Python cannot safely kill an arbitrary worker thread.  Generated Dev
        Studio commands call ``checkIfAlive`` in their loops, so setting
        ``alive`` false ends them at the next safe checkpoint while keys and
        communications are also released here.
        """
        command = self.cur_command
        if command is None:
            return
        if not tkmsg.askyesno("Force stop", "実行中コマンドへ強制停止要求を送りますか？"):
            return
        Command.isPause = False
        try:
            command.alive = False
            if hasattr(command, "socket0"):
                command.socket0.alive = False
            if hasattr(command, "mqtt0"):
                command.mqtt0.alive = False
            keys = getattr(command, "keys", None)
            if keys is not None:
                keys.end()
            command.end(self.ser)
        except Exception as error:
            self._logger.warning("Force stop request failed: %s", error)
        self.force_stop_button["state"] = "disabled"
        self.pause_button["state"] = "disabled"
        self.show_output("Analysis", text="Force-stop requested. The command exits at its next checkIfAlive() checkpoint.")

    def stopPlay(self):
        print(self.start_button["text"] + " " + self.cur_command.NAME)
        self._logger.info(self.start_button["text"] + " " + self.cur_command.NAME)
        self.start_button["state"] = "disabled"
        self.start_top_button["state"] = "disabled"

        Command.isPause = False
        self.pause_button["text"] = "Pause"
        self.pause_button["command"] = self.pausePlay
        self.pause_button["state"] = "disable"
        self.force_stop_button["state"] = "disabled"

        self.cur_command.end(self.ser)

    def stopPlayPost(self):
        self.start_button["text"] = "Start"
        self.force_stop_button["state"] = "disabled"
        self.start_top_button["text"] = "Start"
        self.start_button["command"] = self.startPlay
        self.start_top_button["command"] = self.startPlay
        if self.command_nb.tab(self.command_nb.select(), "text") == "Shortcut":
            self.start_button["state"] = "disable"
            self.start_top_button["state"] = "disable"
        else:
            self.start_button["state"] = "normal"
            self.start_top_button["state"] = "normal"
        self.reload_command_button["state"] = "normal"
        self.shortcut_button_1["state"] = "normal"
        self.shortcut_button_2["state"] = "normal"
        self.shortcut_button_3["state"] = "normal"
        self.shortcut_button_4["state"] = "normal"
        self.shortcut_button_5["state"] = "normal"
        self.shortcut_button_6["state"] = "normal"
        self.shortcut_button_7["state"] = "normal"
        self.shortcut_button_8["state"] = "normal"
        self.shortcut_button_9["state"] = "normal"
        self.shortcut_button_10["state"] = "normal"

    def run(self):
        self._logger.debug("Start Poke-Controller")
        self.mainwindow.mainloop()

    def exit(self):
        """Avoid destroying the window while the background MP4 encoder runs."""
        if getattr(self, "_exit_waiting", False):
            return

        # In Template mode the Start button arms monitoring.  Disarm it before
        # closing so that a camera callback cannot begin another segment.
        if getattr(self, "record_armed", False):
            self.record_armed = False
            if hasattr(self, "record_button"):
                self.record_button.configure(text="Start recording")
            self.show_output("Analysis", text="Template recording monitoring stopped before closing.")

        # This starts final encoding in a background thread when there is an
        # active clip; it intentionally does not wait for ffmpeg here.
        if getattr(self.recorder, "active", False):
            self.recorder.stop()
            if hasattr(self, "record_button"):
                self.record_button.configure(text="Start recording")

        if getattr(self.recorder, "is_finalizing", False):
            if tkmsg.askyesno(
                "MP4 conversion in progress",
                "MP4ファイルを作成中です。\n変換終了後にPoke Controllerを閉じますか？\n\n"
                "「いいえ」を選ぶと、ツールは開いたままになります。",
            ):
                self._exit_waiting = True
                self.show_output("Analysis", text="MP4 conversion in progress. The tool will close when it finishes.")
                self._wait_for_recording_finalization()
            return
        self._exit_now()

    def _wait_for_recording_finalization(self):
        if getattr(self.recorder, "is_finalizing", False):
            self.root.after(250, self._wait_for_recording_finalization)
            return
        self._exit_waiting = False
        # The user already confirmed closing in the MP4 conversion dialog.
        # Do not ask the generic exit question a second time after ffmpeg ends.
        self._exit_now(confirm=False)

    def _exit_now(self, confirm=True):
        # 一度proconのスレッドを落とす
        self.flag_procon = False
        self.record_pro_controller_checkbox["state"] = "normal"
        self.is_use_Pro_Controller.set(False)

        ret = not confirm or tkmsg.askyesno("確認", "Poke Controllerを終了しますか？")
        if ret:
            if self.ser.isOpened():
                self.ser.closeSerial()
                print("Serial disconnected")
                # self._logger.info("Serial disconnected")

            # stop listening to keyboard events
            if self.keyboard is not None:
                self.keyboard.stop()
                self.keyboard = None

            # save settings
            self.settings.is_show_realtime.set(self.is_show_realtime.get())
            self.settings.is_show_value.set(self.is_show_value.get())
            self.settings.is_show_guide.set(self.is_show_guide.get())
            self.settings.is_show_serial.set(self.is_show_serial.get())
            self.settings.is_use_keyboard.set(self.is_use_keyboard.get())
            self.settings.fps.set(self.fps.get())
            self.settings.show_size.set(self.show_size.get())
            self.settings.com_port.set(self.com_port.get())
            self.settings.baud_rate.set(self.baud_rate.get())
            self.settings.camera_id.set(self.camera_id.get())
            self.settings.serial_data_format_name.set(self.serial_data_format_name.get())
            self.settings.touchscreen_start_x = self.preview.touchscreen_start_x
            self.settings.touchscreen_start_y = self.preview.touchscreen_start_y
            self.settings.touchscreen_end_x = self.preview.touchscreen_end_x
            self.settings.touchscreen_end_y = self.preview.touchscreen_end_y
            self.settings.command_class_dict["1"] = self.shortcut_command_class[1]
            self.settings.command_name_dict["1"].set(self.shortcut_command_name[1])
            self.settings.command_class_dict["2"] = self.shortcut_command_class[2]
            self.settings.command_name_dict["2"].set(self.shortcut_command_name[2])
            self.settings.command_class_dict["3"] = self.shortcut_command_class[3]
            self.settings.command_name_dict["3"].set(self.shortcut_command_name[3])
            self.settings.command_class_dict["4"] = self.shortcut_command_class[4]
            self.settings.command_name_dict["4"].set(self.shortcut_command_name[4])
            self.settings.command_class_dict["5"] = self.shortcut_command_class[5]
            self.settings.command_name_dict["5"].set(self.shortcut_command_name[5])
            self.settings.command_class_dict["6"] = self.shortcut_command_class[6]
            self.settings.command_name_dict["6"].set(self.shortcut_command_name[6])
            self.settings.command_class_dict["7"] = self.shortcut_command_class[7]
            self.settings.command_name_dict["7"].set(self.shortcut_command_name[7])
            self.settings.command_class_dict["8"] = self.shortcut_command_class[8]
            self.settings.command_name_dict["8"].set(self.shortcut_command_name[8])
            self.settings.command_class_dict["9"] = self.shortcut_command_class[9]
            self.settings.command_name_dict["9"].set(self.shortcut_command_name[9])
            self.settings.command_class_dict["10"] = self.shortcut_command_class[10]
            self.settings.command_name_dict["10"].set(self.shortcut_command_name[10])
            self.settings.is_win_notification_start.set(self.is_win_notification_start.get())
            self.settings.is_win_notification_end.set(self.is_win_notification_end.get())
            self.settings.is_line_notification_start.set(self.is_line_notification_start.get())
            self.settings.is_line_notification_end.set(self.is_line_notification_end.get())
            self.settings.is_discord_notification_start.set(self.is_discord_notification_start.get())
            self.settings.is_discord_notification_end.set(self.is_discord_notification_end.get())
            self.settings.area_size = self.area_size.get()
            self.settings.stdout_destination = self.stdout_destination.get()
            self.settings.right_frame_widget_mode = self.right_frame_widget_mode.get()
            self.settings.pos_software_controller = self.pos_software_controller.get()
            self.settings.pos_dialogue_buttons = self.pos_dialogue_buttons.get()
            self.settings.panel_left_top = self.panel_slots["left_top"].get()
            self.settings.panel_left_bottom = self.panel_slots["left_bottom"].get()
            self.settings.panel_right_top = self.panel_slots["right_top"].get()
            self.settings.panel_right_bottom = self.panel_slots["right_bottom"].get()
            self.settings.panel_ratio = self.panel_ratio.get()
            self.settings.right_panel_ratio = self.right_panel_ratio.get()
            self.settings.panel_layout = self.panel_layout.get()
            self.settings.panel_sides = self.panel_sides.get()
            self.settings.left_panel_count = self.left_panel_count.get()
            self.settings.right_panel_count = self.right_panel_count.get()
            self.settings.side_width_balance = self.side_width_balance.get()
            self.settings.show_software_controller = self.show_software_controller.get()
            self.settings.audio_input = self.audio_input.get()
            self.settings.audio_gain = self.audio_gain.get()
            self.settings.audio_filter_camera = self.audio_filter_camera.get()
            self.settings.audio_auto_start = self.audio_auto_start.get()
            self.settings.vision_mode = self.vision_mode.get()
            self.settings.record_mode = self.record_mode.get()
            self.settings.record_template_path = self.record_template_path.get()
            self.settings.record_threshold = self.record_threshold.get()
            self.settings.record_interval = self.record_interval.get()
            self.settings.record_release = self.record_release.get()
            self.settings.record_roi = self.record_roi.get()
            self.settings.record_debug = self.record_debug.get()
            self.settings.record_trigger_rules = json.dumps(self.record_trigger_rules)
            self.settings.record_cleanup_rules = json.dumps(self.record_cleanup_rules)
            self.settings.record_minimum_duration = self.record_minimum_duration.get()
            self.settings.record_variable_command = self.record_variable_command.get()
            self.settings.record_variable_name = self.record_variable_name.get()
            self.settings.record_variable_start = self.record_variable_start.get()
            self.settings.record_variable_stop = self.record_variable_stop.get()
            self.settings.area_capture_roi = self.area_capture_roi.get()
            self.settings.area_capture_output_target = self.area_capture_output_target.get()
            self.settings.area_capture_background = self.area_capture_background.get()
            self.settings.area_capture_active = self.area_capture_active.get()
            self.settings.command_watch_enabled = self.command_watch_enabled.get()
            self.settings.command_watch_command = self.command_watch_command.get()
            self.settings.command_watch_target = self.command_watch_target.get()
            self.settings.command_watch_variables = ",".join(self.command_watch_variables)

            self.settings.save()

            self.stop_audio_monitor()
            self.recorder.stop()
            self.camera.destroy()
            cv2.destroyAllWindows()
            self._logger.debug("Stop Poke Controller")
            self.root.destroy()

    def closingController(self):
        self.controller.destroy()
        self.controller = None

    # def closingGetFromHome(self):
    #     self.poke_treeview.destroy()
    #     self.poke_treeview = None

    def loadSettings(self):
        self.settings = Settings.GuiSettings()
        self.settings.load()

    def ReloadCommandWithF5(self, *event):
        self.reloadCommands()

    def StartCommandWithF6(self, *event):
        if self.start_button["text"] == "Stop":
            print("Command is now working!")
            self._logger.debug("Command is now working!")
        elif self.start_button["text"] == "Start":
            self.startPlay()

    def StopCommandWithEsc(self, *event):
        if self.start_button["text"] == "Stop":
            self.stopPlay()

    def clearTextArea1(self):
        self.text_area_1.config(state="normal")
        self.text_area_1.delete("1.0", "end")
        self.text_area_1.config(state="disable")

    def clearTextArea2(self):
        self.text_area_2.config(state="normal")
        self.text_area_2.delete("1.0", "end")
        self.text_area_2.config(state="disable")

    def clearOutputs(self):
        self.clearTextArea1()
        self.clearTextArea2()

    def _configured_log_choices(self):
        slots = {name: value.get() for name, value in self.panel_slots.items()}
        choices = []
        for output, number in (("Log: Output#1", "1"), ("Log: Output#2", "2")):
            slot = next((name for name, value in slots.items() if value == output), None)
            if slot:
                choices.append((number, "Output#{} ({})".format(number, slot.replace("_", " "))))
        return choices

    def refresh_log_controls(self):
        if not hasattr(self, "stdout_log_target_cb"):
            return
        choices = self._configured_log_choices()
        labels = [label for _, label in choices]
        self.stdout_log_target_cb.configure(values=labels)
        self.clear_log_target_cb.configure(values=labels)
        if hasattr(self, "area_capture_output_cb"):
            area_choices = ["{} ({})".format(slot, value.get()) for slot, value in self.panel_slots.items()]
            self.area_capture_output_cb.configure(values=area_choices)
            if self.area_capture_output_target.get() not in area_choices:
                legacy_target = self.area_capture_output_target.get()
                logical = "Log: " + legacy_target if legacy_target.startswith("Output#") else ""
                migrated = next(("{} ({})".format(slot, value.get()) for slot, value in self.panel_slots.items()
                                 if value.get() == logical), "")
                self.area_capture_output_target.set(migrated)
        selected = next((label for number, label in choices if number == self.stdout_destination.get()), labels[0] if labels else "")
        if choices and not any(number == self.stdout_destination.get() for number, _ in choices):
            self.stdout_destination.set(choices[0][0])
        self.stdout_log_target.set(selected)
        if not self.clear_log_target.get() or self.clear_log_target.get() not in labels:
            self.clear_log_target.set(selected)

    def select_stdout_log_target(self, *event):
        chosen = self.stdout_log_target.get()
        if chosen.startswith("Output#1"):
            self.stdout_destination.set("1")
        elif chosen.startswith("Output#2"):
            self.stdout_destination.set("2")
        self.switchStdoutDestination()

    def clear_selected_log(self):
        chosen = self.clear_log_target.get()
        if chosen.startswith("Output#1"):
            self.clearTextArea1()
        elif chosen.startswith("Output#2"):
            self.clearTextArea2()

    def _area_capture_preview_slot(self):
        if not hasattr(self, "area_capture_output_target"):
            return ""
        return self.area_capture_output_target.get().split(" ", 1)[0]

    def open_side_panel_settings(self):
        """Keep the detailed side settings reachable on compact windows."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Side panel settings")
        dialog.transient(self.root)
        layout = ttk.Labelframe(dialog, text="Visible sides and panel count")
        layout.grid(column=0, row=0, padx=8, pady=6, sticky="ew")
        ttk.Label(layout, text="Display").grid(column=0, row=0, padx=5, pady=4, sticky="w")
        side_cb = ttk.Combobox(layout, state="readonly", width=20, textvariable=self.panel_sides,
                               values=("Both sides", "Left side only", "Right side only", "Both sides hidden"))
        side_cb.grid(column=1, row=0, padx=5, pady=4)
        side_cb.bind("<<ComboboxSelected>>", self.apply_panel_assignment)
        ttk.Label(layout, text="Left panels").grid(column=0, row=1, padx=5, pady=4, sticky="w")
        left_count_cb = ttk.Combobox(layout, state="readonly", width=5, textvariable=self.left_panel_count, values=("1", "2"))
        left_count_cb.grid(column=1, row=1, padx=5, pady=4, sticky="w")
        left_count_cb.bind("<<ComboboxSelected>>", self.apply_panel_assignment)
        ttk.Label(layout, text="Right panels").grid(column=2, row=1, padx=5, pady=4, sticky="w")
        right_count_cb = ttk.Combobox(layout, state="readonly", width=5, textvariable=self.right_panel_count, values=("1", "2"))
        right_count_cb.grid(column=3, row=1, padx=5, pady=4, sticky="w")
        right_count_cb.bind("<<ComboboxSelected>>", self.apply_panel_assignment)
        ttk.Checkbutton(layout, text="Show software controller", variable=self.show_software_controller,
                        command=self.apply_panel_assignment).grid(column=0, columnspan=2, row=2, padx=5, pady=4, sticky="w")
        ttk.Radiobutton(layout, text="Controller TOP", variable=self.pos_software_controller, value="1",
                        command=self.apply_panel_assignment).grid(column=2, row=2, padx=5, pady=4)
        ttk.Radiobutton(layout, text="BOTTOM", variable=self.pos_software_controller, value="2",
                        command=self.apply_panel_assignment).grid(column=3, row=2, padx=5, pady=4)

        assignments = ttk.Labelframe(dialog, text="Content assigned to each panel")
        assignments.grid(column=0, row=1, padx=8, pady=6, sticky="ew")
        panel_values = ("Disabled", "Log: Output#1", "Log: Output#2", "Image", "HTML", "Analysis")
        for row, (slot, label) in enumerate((("left_top", "Left / Top"), ("left_bottom", "Left / Bottom"),
                                             ("right_top", "Right / Top"), ("right_bottom", "Right / Bottom"))):
            ttk.Label(assignments, text=label).grid(column=0, row=row, padx=5, pady=3, sticky="w")
            combo = ttk.Combobox(assignments, state="readonly", width=18, values=panel_values,
                                 textvariable=self.panel_slots[slot])
            combo.grid(column=1, row=row, padx=5, pady=3)
            combo.bind("<<ComboboxSelected>>", self.apply_panel_assignment)
        ttk.Button(dialog, text="Close", command=dialog.destroy).grid(column=0, row=2, padx=8, pady=(0, 8), sticky="e")

    def update_size_adjuster_controls(self, show_left, show_right):
        self.size_adjuster_label.grid_forget()
        self.size_adjuster_scale.grid_forget()
        self.panel_split_label.grid_forget()
        self.panel_split_scale.grid_forget()
        self.right_panel_split_label.grid_forget()
        self.right_panel_split_scale.grid_forget()
        row = 0
        split_row = 0
        if show_left and show_right:
            self.size_adjuster_label.configure(text="Left / right width")
            self.size_adjuster_label.grid(column=0, row=row, padx=5, pady=(2, 0), sticky="w")
            self.size_adjuster_scale.grid(column=0, row=row + 1, padx=5, pady=(0, 2), sticky="ew")
            row += 2
        if show_left and self.left_panel_count.get() == "2":
            self.panel_split_label.configure(text="Left: top / bottom split")
            self.panel_split_label.grid(column=0, row=split_row, padx=5, pady=(2, 0), sticky="w")
            self.panel_split_scale.grid(column=0, row=split_row + 1, padx=5, pady=(0, 2), sticky="ew")
            split_row += 2
        if show_right and self.right_panel_count.get() == "2":
            self.right_panel_split_label.grid(column=0, row=split_row, padx=5, pady=(2, 0), sticky="w")
            self.right_panel_split_scale.grid(column=0, row=split_row + 1, padx=5, pady=(0, 4), sticky="ew")
            split_row += 2
        if split_row:
            self.panel_split_adjuster_lf.grid()
        else:
            self.panel_split_adjuster_lf.grid_remove()

    def receive_output_region(self, image_bgr, rect):
        """Display the persistent red selection in the currently selected output."""
        if hasattr(self, "area_capture_roi"):
            self.area_capture_roi.set("{},{},{},{}".format(*rect))
            self.area_capture_status.set("Selected ROI: {},{},{},{}".format(*rect))
        self.preview_area_capture()
        print(f"Output crop: x={rect[0]}, y={rect[1]}, w={rect[2]}, h={rect[3]}")

    def apply_panel_assignment(self, *event):
        """Reflect assignment in titles and expose it to command scripts.

        Output#1 and Output#2 remain the two existing result areas; the slot
        settings describe where each result belongs in the four-panel layout.
        """
        slots = {name: value.get() for name, value in self.panel_slots.items()}
        output_1_slot = next((name for name, value in slots.items() if value == "Log: Output#1"), "unassigned")
        output_2_slot = next((name for name, value in slots.items() if value == "Log: Output#2"), "unassigned")
        self.text_scroll_1.configure(text=f"Output#1 ({output_1_slot})")
        self.text_scroll_2.configure(text=f"Output#2 ({output_2_slot})")
        if output_1_slot != "unassigned":
            self.text_area_1 = self.panel_widgets[output_1_slot][2]
        else:
            self.text_area_1 = self.base_text_areas[0]
        if output_2_slot != "unassigned":
            self.text_area_2 = self.panel_widgets[output_2_slot][2]
        else:
            self.text_area_2 = self.base_text_areas[1]
        self.softcon_frame.pack_forget()
        sides = self.panel_sides.get()
        show_left = sides in ("Both sides", "Left side only")
        show_right = sides in ("Both sides", "Right side only")
        # The controller lives inside the right output container, but it is a
        # separate option from the side log panels.  Keep that container
        # visible as a host whenever the controller itself is enabled.
        show_controller = self.show_software_controller.get()
        show_right_host = show_right or show_controller
        self.update_size_adjuster_controls(show_left, show_right)
        self.left_output_area_f.grid_forget()
        self.output_area_f.grid_forget()
        if show_left:
            self.left_output_area_f.grid(column=0, padx="5", pady="5", row=0, rowspan=2, sticky="nsew")
        if show_right_host:
            self.output_area_f.grid(column=2, padx="5", pady="5", row=0, rowspan=2, sticky="nsew")
        # A single visible side is allowed to consume the freed space.
        if show_left and show_right:
            self.main_frame.columnconfigure(0, weight=max(1, self.side_width_balance.get()))
            self.main_frame.columnconfigure(2, weight=max(1, 100 - self.side_width_balance.get()))
        else:
            self.main_frame.columnconfigure(0, weight=2 if show_left else 0)
            self.main_frame.columnconfigure(2, weight=2 if show_right_host else 0)
        for panel, _, _ in self.panel_widgets.values():
            panel.pack_forget()
            panel.pack_propagate(True)
        def pack_side(slot_names, split_ratio):
            if len(slot_names) == 1:
                self.panel_widgets[slot_names[0]][0].pack(expand=True, fill="both", side="top")
                return
            total_height = max(240, int(getattr(getattr(self, "preview", None), "show_height", 360)))
            top_height = int(total_height * split_ratio.get() / 100)
            for name, height in zip(slot_names, (top_height, total_height - top_height)):
                panel = self.panel_widgets[name][0]
                panel.configure(height=max(40, height))
                panel.pack_propagate(False)
                panel.pack(expand=False, fill="both", side="top")
        if show_left:
            pack_side(("left_top",) if self.left_panel_count.get() == "1" else ("left_top", "left_bottom"),
                      self.panel_ratio)
        if show_controller and self.pos_software_controller.get() == "1":
            self.softcon_frame.pack(expand=False, fill="x", padx=0, pady=0, side="top")
        if show_right:
            pack_side(("right_top",) if self.right_panel_count.get() == "1" else ("right_top", "right_bottom"),
                      self.right_panel_ratio)
        if show_controller and self.pos_software_controller.get() == "2":
            self.softcon_frame.pack(expand=False, fill="x", padx=0, pady=0, side="bottom")
        # Rebind the stdout proxy after a log destination is moved.
        if hasattr(self, "stdout_destination"):
            self.refresh_log_controls()
            self.switchStdoutDestination(silent=True)
        for slot, (_, image_label, text_widget) in self.panel_widgets.items():
            content = slots[slot]
            # Rebuild panel contents so an Area Capture destination contains
            # only the image, never the old text log below it.
            text_widget.pack_forget()
            if slot in self.area_capture_inline:
                self.area_capture_inline[slot][0].pack_forget()
            for scrollbar in (getattr(self, "yscroll_1", None), getattr(self, "yscroll_2", None)):
                if scrollbar is not None and scrollbar.master == image_label.master:
                    scrollbar.pack_forget()
            image_label.pack_forget()
            is_area_preview = slot == self._area_capture_preview_slot()
            if content.startswith("Log:"):
                image_label.pack(fill="x", padx=5, pady=(5, 0))
                if image_label.master == self.text_scroll_1:
                    self.yscroll_1.pack(side="right", fill="y", padx=(0, 5), pady=5)
                elif image_label.master == self.text_scroll_2:
                    self.yscroll_2.pack(side="right", fill="y", padx=(0, 5), pady=5)
                text_widget.pack(expand=True, fill="both", padx=(5, 0), pady=5)
            else:
                if is_area_preview:
                    self._ensure_area_capture_inline(slot)[0].pack(expand=True, fill="both", padx=5, pady=5)
                else:
                    image_label.pack(expand=True, fill="both", padx=5, pady=5)
            if content == "Disabled":
                image_label.configure(text="Disabled", image="")
            elif content in ("Image", "HTML", "Analysis"):
                if is_area_preview:
                    image_label.configure(text="")
                    image_label.unbind("<Button-1>")
                else:
                    image_label.configure(text=content, image="")
                    image_label.unbind("<Button-1>")

    def show_output(self, panel, text=None, image=None, html_path=None):
        """Public UI API used by Command.show_output()."""
        if panel in self.panel_slots:
            _, image_label, text_area = self.panel_widgets[panel]
            if image is not None:
                if panel == self._area_capture_preview_slot():
                    self.display_area_capture_inline(panel, image)
                else:
                    self.display_output_image(image_label, image)
            if text is not None:
                text_area.configure(state="normal")
                text_area.delete("1.0", "end")
                text_area.insert("end", str(text))
                text_area.configure(state="disabled")
            if html_path:
                webbrowser.open(Path(html_path).resolve().as_uri())
            return
        if panel == "Analysis":
            panel = "Output#2"
        if panel == "Log: Output#1":
            panel = "Output#1"
        if panel == "Log: Output#2":
            panel = "Output#2"
        if panel == "Disabled":
            return
        logical_value = "Log: " + panel
        assigned_slot = next((name for name, value in self.panel_slots.items() if value.get() == logical_value), None)
        if assigned_slot:
            _, image_label, text_area = self.panel_widgets[assigned_slot]
        else:
            image_label = self.output_image_1 if panel == "Output#1" else self.output_image_2
            text_area = self.text_area_1 if panel == "Output#1" else self.text_area_2
        if image is not None:
            self.display_output_image(image_label, image)
        if text is not None:
            text_area.configure(state="normal")
            text_area.delete("1.0", "end")
            text_area.insert("end", str(text))
            text_area.configure(state="disabled")
        if html_path:
            webbrowser.open(Path(html_path).resolve().as_uri())

    def display_output_image(self, target, image_bgr):
        if image_bgr is None or image_bgr.size == 0:
            return
        h, w = image_bgr.shape[:2]
        scale = min(300 / max(w, 1), 180 / max(h, 1), 1.0)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(image_rgb).resize((max(1, int(w * scale)), max(1, int(h * scale))))
        tk_image = ImageTk.PhotoImage(image)
        target.configure(image=tk_image, text="")
        target.image = tk_image  # prevent Tk from garbage-collecting the image

    def change_vision_mode(self, event=None):
        self.vision.set_mode(self.vision_mode.get())
        print(f"Vision mode: {self.vision_mode.get()}")

    def reload_vision_rules(self):
        self.vision.reload_rules()
        self.vision_mode_cb.configure(values=list(self.vision.modes.keys()))
        if self.vision_mode.get() not in self.vision.modes:
            self.vision_mode.set("default")
        self.change_vision_mode()

    def analyse_live_frame(self, frame):
        try:
            result = self.vision.analyse(frame)
            text = result.to_json()
            if text != self._last_vision_text:
                self._last_vision_text = text
                self.text_area_2.configure(state="normal")
                self.text_area_2.delete("1.0", "end")
                self.text_area_2.insert("end", text)
                self.text_area_2.configure(state="disabled")
        except Exception as error:
            self._logger.warning(f"Live analysis error: {error}")

    def _build_input_set_tab(self):
        """Build the left-most Camera/Audio and Recording combination tab."""
        self.input_set_f = ttk.Frame(self.controller_nb)
        self.controller_nb.insert(0, self.input_set_f, padding="5", sticky="nsew", text="InputSet")
        self.input_set_canvas = tk.Canvas(self.input_set_f, highlightthickness=0, borderwidth=0)
        self.input_set_scrollbar = ttk.Scrollbar(
            self.input_set_f, orient="vertical", command=self.input_set_canvas.yview)
        self.input_set_canvas.configure(yscrollcommand=self.input_set_scrollbar.set)
        self.input_set_canvas.pack(side="left", fill="both", expand=True)
        self.input_set_scrollbar.pack(side="right", fill="y")
        self.input_set_content = ttk.Frame(self.input_set_canvas)
        self.input_set_canvas_window = self.input_set_canvas.create_window(
            (0, 0), window=self.input_set_content, anchor="nw")
        self.input_set_content.bind("<Configure>", self._update_input_set_scrollregion)
        self.input_set_canvas.bind("<Configure>", self._resize_input_set_content)
        self.root.bind_all("<MouseWheel>", self._scroll_input_set_with_wheel, add="+")

        input_box = ttk.Labelframe(self.input_set_content, text="Camera・Audio 入力セット")
        input_box.pack(fill="x", padx=6, pady=6)
        ttk.Label(input_box, text="入力セット名:").grid(column=0, row=0, padx=5, pady=5, sticky="w")
        self.input_set_name = tk.StringVar()
        self.input_set_cb = ttk.Combobox(input_box, textvariable=self.input_set_name, width=34)
        self.input_set_cb.grid(column=1, row=0, padx=5, pady=5, sticky="ew")
        ttk.Button(input_box, text="呼び出し", command=self.load_input_set).grid(column=2, row=0, padx=2, pady=5)
        ttk.Button(input_box, text="新規登録", command=lambda: self.save_input_set(False)).grid(column=3, row=0, padx=2, pady=5)
        ttk.Button(input_box, text="変更保存", command=lambda: self.save_input_set(True)).grid(column=4, row=0, padx=2, pady=5)
        ttk.Button(input_box, text="削除", command=self.delete_input_set).grid(column=5, row=0, padx=2, pady=5)
        self.input_set_include_audio = tk.BooleanVar(value=True)
        ttk.Checkbutton(input_box, text="Audio設定を含める", variable=self.input_set_include_audio).grid(
            column=0, columnspan=2, row=1, padx=5, pady=(0, 4), sticky="w")
        ttk.Label(input_box, text="SerialのDevice Nameが設定済みの場合は自動的に含めます。").grid(
            column=2, columnspan=4, row=1, padx=5, pady=(0, 4), sticky="w")
        self.input_set_summary = tk.StringVar(value="CameraタブとAudioタブの現在値を登録します。")
        ttk.Label(input_box, textvariable=self.input_set_summary, anchor="w").grid(
            column=0, columnspan=6, row=2, padx=5, pady=(0, 5), sticky="ew")
        input_box.columnconfigure(1, weight=1)

        combined_box = ttk.Labelframe(self.input_set_content, text="InputSet・Recording 組み合わせセット")
        combined_box.pack(fill="x", padx=6, pady=6)
        ttk.Label(combined_box, text="組み合わせ名:").grid(column=0, row=0, padx=5, pady=5, sticky="w")
        self.input_recording_set_name = tk.StringVar()
        self.input_recording_set_cb = ttk.Combobox(combined_box, textvariable=self.input_recording_set_name, width=34)
        self.input_recording_set_cb.grid(column=1, row=0, padx=5, pady=5, sticky="ew")
        ttk.Label(combined_box, text="InputSet:").grid(column=0, row=1, padx=5, pady=5, sticky="w")
        self.input_recording_input_name = tk.StringVar()
        self.input_recording_input_cb = ttk.Combobox(
            combined_box, textvariable=self.input_recording_input_name, state="readonly", width=34)
        self.input_recording_input_cb.grid(column=1, row=1, padx=5, pady=5, sticky="ew")
        ttk.Label(combined_box, text="Recordingセット:").grid(column=0, row=2, padx=5, pady=5, sticky="w")
        self.input_recording_record_name = tk.StringVar()
        self.input_recording_record_cb = ttk.Combobox(
            combined_box, textvariable=self.input_recording_record_name, state="readonly", width=34)
        self.input_recording_record_cb.grid(column=1, row=2, padx=5, pady=5, sticky="ew")
        actions = ttk.Frame(combined_box)
        actions.grid(column=2, columnspan=4, row=0, rowspan=3, padx=4, pady=4, sticky="ns")
        ttk.Button(actions, text="呼び出し", command=self.load_input_recording_set).pack(fill="x", pady=1)
        ttk.Button(actions, text="新規登録", command=lambda: self.save_input_recording_set(False)).pack(fill="x", pady=1)
        ttk.Button(actions, text="変更保存", command=lambda: self.save_input_recording_set(True)).pack(fill="x", pady=1)
        ttk.Button(actions, text="削除", command=self.delete_input_recording_set).pack(fill="x", pady=1)
        self.input_recording_summary = tk.StringVar(value="登録済みInputSetとRecordingセットを組み合わせます。")
        ttk.Label(combined_box, textvariable=self.input_recording_summary, anchor="w").grid(
            column=0, columnspan=6, row=3, padx=5, pady=(0, 5), sticky="ew")
        combined_box.columnconfigure(1, weight=1)
        self.input_set_cb.bind("<<ComboboxSelected>>", self._show_input_set_summary)
        self.input_recording_set_cb.bind("<<ComboboxSelected>>", self._select_input_recording_set)
        self.refresh_input_sets()

    def _input_sets_path(self):
        return os.path.join(os.path.dirname(Settings.GuiSettings.SETTING_PATH), "input_sets.json")

    def _read_input_sets(self):
        try:
            with open(self._input_sets_path(), "r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                return {"schema_version": 1, "input_sets": {}, "combined_sets": {}}
            data.setdefault("schema_version", 1)
            data.setdefault("input_sets", {})
            data.setdefault("combined_sets", {})
            return data
        except (OSError, ValueError):
            return {"schema_version": 1, "input_sets": {}, "combined_sets": {}}

    def _write_input_sets(self, data):
        path = self._input_sets_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary, path)

    @staticmethod
    def _usb_identity(value):
        value = str(value or "")
        vid = re.search(r"(?i)vid[_:-]?([0-9a-f]{4})", value)
        pid = re.search(r"(?i)pid[_:-]?([0-9a-f]{4})", value)
        return (vid.group(1).upper() if vid else "", pid.group(1).upper() if pid else "")

    def _current_camera_data(self):
        camera_id = self.camera_id.get()
        devices = self.camera_dic or {}
        value = devices.get(camera_id, devices.get(str(camera_id), self.camera_name_fromDLL.get()))
        vid, pid = self._usb_identity(value)
        display_name = str(value or "")
        device_path = ""
        if display_name.endswith(")") and " (" in display_name:
            possible_name, possible_path = display_name.rsplit(" (", 1)
            possible_path = possible_path[:-1]
            if "vid_" in possible_path.lower() or "pid_" in possible_path.lower() or possible_path.startswith("@"):
                display_name, device_path = possible_name, possible_path
        return {
            "camera_id": camera_id,
            "display_name": display_name,
            "device_value": str(value or ""),
            "device_path": device_path,
            "vid": vid,
            "pid": pid,
            "fps": self.fps.get(),
            "show_size": self.show_size.get(),
        }

    def _current_input_set_data(self):
        include_audio = self.input_set_include_audio.get()
        return {
            "camera": self._current_camera_data(),
            "audio": {
                "enabled": include_audio,
                "device_name": self.audio_input.get() if include_audio else "",
                "normalized_name": self._normalize_audio_device_name(self.audio_input.get()) if include_audio else "",
                "gain": self.audio_gain.get(),
                "filter_camera": self.audio_filter_camera.get(),
                "auto_start": self.audio_auto_start.get(),
            },
            "serial": self._current_serial_data(),
        }

    def _current_serial_data(self):
        selected = self.serial_device_name.get().strip() if hasattr(self, "serial_device_name") else ""
        if not selected or selected.startswith("("):
            return {"enabled": False}
        current_port = "COM{}".format(self.com_port.get())
        matched = None
        for port in list_ports.comports():
            if port.description == selected or str(port.device).casefold() == current_port.casefold():
                matched = port
                break
        return {
            "enabled": True,
            "device_name": selected,
            "port": str(getattr(matched, "device", current_port)),
            "description": str(getattr(matched, "description", selected)),
            "vid": getattr(matched, "vid", None),
            "pid": getattr(matched, "pid", None),
            "serial_number": str(getattr(matched, "serial_number", "") or ""),
        }

    def refresh_input_sets(self):
        if not hasattr(self, "input_set_cb"):
            return
        data = self._read_input_sets()
        input_names = sorted(data["input_sets"])
        combined_names = sorted(data["combined_sets"])
        self.input_set_cb.configure(values=input_names)
        self.input_recording_set_cb.configure(values=combined_names)
        self.input_recording_input_cb.configure(values=input_names)
        self.input_recording_record_cb.configure(values=sorted(self._read_recording_presets()))

    def save_input_set(self, update=False):
        name = self.input_set_name.get().strip()
        if not name:
            tkmsg.showwarning("InputSet", "入力セット名を入力してください。")
            return
        data = self._read_input_sets()
        exists = name in data["input_sets"]
        if update and not exists:
            tkmsg.showwarning("InputSet", "変更する登録済みInputSetを選択してください。")
            return
        if not update and exists:
            tkmsg.showwarning("InputSet", "同名のInputSetが登録済みです。変更保存を使用してください。")
            return
        data["input_sets"][name] = self._current_input_set_data()
        self._write_input_sets(data)
        self.refresh_input_sets()
        self._show_input_set_summary()

    def delete_input_set(self):
        name = self.input_set_name.get().strip()
        data = self._read_input_sets()
        if name not in data["input_sets"]:
            tkmsg.showwarning("InputSet", "削除する登録済みInputSetを選択してください。")
            return
        used = [set_name for set_name, item in data["combined_sets"].items() if item.get("input_set") == name]
        detail = "\n使用中の組み合わせ: " + ", ".join(used) if used else ""
        if not tkmsg.askyesno("InputSet", "InputSet「{}」を削除しますか？{}".format(name, detail)):
            return
        del data["input_sets"][name]
        for set_name in used:
            del data["combined_sets"][set_name]
        self._write_input_sets(data)
        self.input_set_name.set("")
        self.refresh_input_sets()

    def _resolve_camera_id(self, saved):
        devices = [(key, str(value)) for key, value in (self.camera_dic or {}).items() if value != "Disable"]
        saved_value = saved.get("device_value", "")
        saved_path = saved.get("device_path", "")
        for key, value in devices:
            if saved_value and value.casefold() == saved_value.casefold():
                return int(key)
            if saved_path and saved_path.casefold() in value.casefold():
                return int(key)
        vid, pid = saved.get("vid", ""), saved.get("pid", "")
        if vid and pid:
            matches = [key for key, value in devices if self._usb_identity(value) == (vid, pid)]
            if len(matches) == 1:
                return int(matches[0])
            if len(matches) > 1:
                return self._choose_camera_candidate(saved, matches, "VID/PIDが同じカメラが複数見つかりました。")
        display_name = saved.get("display_name", "")
        matches = [key for key, value in devices if display_name and display_name.casefold() in value.casefold()]
        if len(matches) == 1:
            return int(matches[0])
        if len(matches) > 1:
            return self._choose_camera_candidate(saved, matches, "同じ名前のカメラが複数見つかりました。")
        fallback = saved.get("camera_id")
        if any(str(key) == str(fallback) for key, _ in devices):
            return int(fallback)
        return None

    def _choose_camera_candidate(self, saved, candidate_ids, reason):
        """Let the user preview ambiguous cameras before committing a match."""
        original_id = self.camera_id.get()
        devices = self.camera_dic or {}
        candidates = [(int(camera_id), str(devices.get(camera_id, devices.get(str(camera_id), ""))))
                      for camera_id in candidate_ids]
        result = {"camera_id": None, "preview_id": None}

        dialog = tk.Toplevel(self.root)
        dialog.title("InputSet カメラの確認")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(True, False)
        ttk.Label(dialog, text=reason).grid(column=0, columnspan=3, row=0, padx=10, pady=(10, 3), sticky="w")
        ttk.Label(dialog, text="候補を切り替えてメイン画面の映像を確認し、正しいカメラを決定してください。").grid(
            column=0, columnspan=3, row=1, padx=10, pady=(0, 8), sticky="w")
        ttk.Label(dialog, text="登録時: {} / VID:{} PID:{}".format(
            saved.get("display_name", ""), saved.get("vid", "-"), saved.get("pid", "-"))).grid(
                column=0, columnspan=3, row=2, padx=10, pady=(0, 8), sticky="w")
        selected = tk.StringVar()
        labels = ["Camera ID {}: {}".format(camera_id, value) for camera_id, value in candidates]
        combo = ttk.Combobox(dialog, textvariable=selected, values=labels, state="readonly", width=90)
        combo.grid(column=0, columnspan=3, row=3, padx=10, pady=5, sticky="ew")
        if labels:
            selected.set(labels[0])

        status = tk.StringVar(value="まだテスト切替していません。")
        ttk.Label(dialog, textvariable=status).grid(column=0, columnspan=3, row=4, padx=10, pady=5, sticky="w")

        def selected_camera_id():
            try:
                return candidates[labels.index(selected.get())][0]
            except (ValueError, IndexError):
                return None

        def preview_candidate():
            camera_id = selected_camera_id()
            if camera_id is None:
                return
            self.camera_id.set(camera_id)
            self.camera_name_fromDLL.set(devices.get(camera_id, devices.get(str(camera_id), "")))
            self.camera_name_cb.current(camera_id)
            if hasattr(self, "camera"):
                self.openCamera()
            result["preview_id"] = camera_id
            status.set("Camera ID {}へ切り替えました。メイン画面の映像を確認してください。".format(camera_id))

        def accept_candidate():
            camera_id = selected_camera_id()
            if camera_id is None:
                return
            if result["preview_id"] != camera_id:
                tkmsg.showwarning("InputSet カメラの確認", "決定前に、選択したカメラへ「テスト切替」して映像を確認してください。", parent=dialog)
                return
            result["camera_id"] = camera_id
            dialog.destroy()

        def cancel_candidate():
            if result["preview_id"] is not None and any(str(key) == str(original_id) for key in devices):
                self.camera_id.set(original_id)
                self.camera_name_fromDLL.set(devices.get(original_id, devices.get(str(original_id), "")))
                self.camera_name_cb.current(original_id)
                if hasattr(self, "camera"):
                    self.openCamera()
            dialog.destroy()

        ttk.Button(dialog, text="テスト切替", command=preview_candidate).grid(column=0, row=5, padx=10, pady=10, sticky="ew")
        ttk.Button(dialog, text="このカメラに決定", command=accept_candidate).grid(column=1, row=5, padx=4, pady=10, sticky="ew")
        ttk.Button(dialog, text="キャンセル", command=cancel_candidate).grid(column=2, row=5, padx=10, pady=10, sticky="ew")
        dialog.protocol("WM_DELETE_WINDOW", cancel_candidate)
        dialog.columnconfigure(0, weight=1)
        dialog.columnconfigure(1, weight=1)
        dialog.columnconfigure(2, weight=1)
        dialog.wait_window()
        return result["camera_id"]

    @staticmethod
    def _normalize_audio_device_name(value):
        """Remove PortAudio/Windows enumeration numbers from a device name."""
        value = re.sub(r"^\s*\d+\s*:\s*", "", str(value or ""))
        # Windows may rename a reconnected device from "(USB...)" to
        # "(2- USB...)".  That instance counter is not part of its identity.
        value = re.sub(r"\(\s*\d+\s*-\s*", "(", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value.casefold()

    def _resolve_audio_name(self, saved_name, saved_normalized=""):
        inputs = list(getattr(self, "all_audio_inputs", []))
        for value in inputs:
            if value.casefold() == str(saved_name).casefold():
                return value
        normalized = saved_normalized or self._normalize_audio_device_name(saved_name)
        matches = [value for value in inputs if normalized and
                   self._normalize_audio_device_name(value) == normalized]
        if matches:
            return matches[0]
        matches = [value for value in inputs if normalized and
                   (normalized in self._normalize_audio_device_name(value) or
                    self._normalize_audio_device_name(value) in normalized)]
        return matches[0] if matches else None

    def _apply_serial_input_set(self, saved):
        if not saved.get("enabled", bool(saved.get("device_name"))):
            return
        ports = list(list_ports.comports())
        serial_number = str(saved.get("serial_number", "") or "").casefold()
        vid, pid = saved.get("vid"), saved.get("pid")
        matches = [port for port in ports if serial_number and
                   str(getattr(port, "serial_number", "") or "").casefold() == serial_number and
                   (vid is None or getattr(port, "vid", None) == vid) and
                   (pid is None or getattr(port, "pid", None) == pid)]
        if not matches and vid is not None and pid is not None:
            matches = [port for port in ports if getattr(port, "vid", None) == vid and
                       getattr(port, "pid", None) == pid]
        if not matches:
            saved_description = str(saved.get("description", saved.get("device_name", ""))).casefold()
            matches = [port for port in ports if str(getattr(port, "description", "")).casefold() == saved_description]
        if not matches:
            saved_port = str(saved.get("port", "")).casefold()
            matches = [port for port in ports if str(getattr(port, "device", "")).casefold() == saved_port]
        if not matches:
            tkmsg.showwarning("InputSet", "登録したSerial Device Nameを検出できませんでした。Serialタブで選択し直してください。")
            return
        port = matches[0]
        description = str(getattr(port, "description", saved.get("device_name", "")))
        device = str(getattr(port, "device", saved.get("port", "")))
        self.locateDeviceCmbbox()
        self.serial_device_name.set(description)
        match = re.search(r"(?i)COM(\d+)", device + " " + description)
        if match:
            self.com_port.set(int(match.group(1)))

    def _apply_input_set_data(self, item):
        camera = item.get("camera", {})
        audio = item.get("audio", {})
        serial = item.get("serial", {})
        self.locateCameraCmbbox()
        camera_id = self._resolve_camera_id(camera)
        if camera_id is None:
            tkmsg.showwarning("InputSet", "登録したカメラを検出できませんでした。Cameraタブで選択し直してください。")
        else:
            self.camera_id.set(camera_id)
            self.camera_name_cb.current(camera_id)
            self.camera_name_fromDLL.set((self.camera_dic or {}).get(camera_id, (self.camera_dic or {}).get(str(camera_id), "")))
            self.fps.set(str(camera.get("fps", self.fps.get())))
            self.show_size.set(camera.get("show_size", self.show_size.get()))
            if hasattr(self, "camera"):
                self.camera.fps = int(self.fps.get())
                self.openCamera()
        audio_enabled = audio.get("enabled", bool(audio.get("device_name")))
        self.input_set_include_audio.set(audio_enabled)
        if audio_enabled:
            self.audio_filter_camera.set(audio.get("filter_camera", False))
            self.audio_auto_start.set(audio.get("auto_start", False))
            self.audio_gain.set(audio.get("gain", 100))
            self.refresh_audio_devices()
            audio_name = self._resolve_audio_name(
                audio.get("device_name", ""), audio.get("normalized_name", ""))
            if audio_name:
                self.audio_input.set(audio_name)
            elif audio.get("device_name"):
                tkmsg.showwarning("InputSet", "登録した音声デバイスを検出できませんでした。Audioタブで選択し直してください。")
        else:
            self.audio_input.set("")
            self.audio_auto_start.set(False)
        self._apply_serial_input_set(serial)

    def load_input_set(self):
        name = self.input_set_name.get().strip()
        item = self._read_input_sets()["input_sets"].get(name)
        if not item:
            tkmsg.showwarning("InputSet", "呼び出す登録済みInputSetを選択してください。")
            return
        self._apply_input_set_data(item)
        self._show_input_set_summary()

    def _show_input_set_summary(self, event=None):
        item = self._read_input_sets()["input_sets"].get(self.input_set_name.get().strip())
        if not item:
            self.input_set_summary.set("CameraタブとAudioタブの現在値を登録します。")
            return
        camera, audio, serial = item.get("camera", {}), item.get("audio", {}), item.get("serial", {})
        audio_enabled = audio.get("enabled", bool(audio.get("device_name")))
        self.input_set_include_audio.set(audio_enabled)
        identity = "VID:{} PID:{}".format(camera.get("vid", "-"), camera.get("pid", "-"))
        audio_text = "{} / Gain: {}%".format(audio.get("device_name", ""), audio.get("gain", 100)) \
            if audio_enabled else "設定なし"
        serial_text = serial.get("device_name", "設定なし") if serial.get("enabled", bool(serial.get("device_name"))) else "設定なし"
        self.input_set_summary.set("Camera: {} ({}) / Audio: {} / Serial: {}".format(
            camera.get("display_name", ""), identity, audio_text, serial_text))

    def save_input_recording_set(self, update=False):
        name = self.input_recording_set_name.get().strip()
        input_name = self.input_recording_input_name.get().strip()
        recording_name = self.input_recording_record_name.get().strip()
        data = self._read_input_sets()
        if not name or input_name not in data["input_sets"] or recording_name not in self._read_recording_presets():
            tkmsg.showwarning("組み合わせセット", "組み合わせ名、登録済みInputSet、Recordingセットを選択してください。")
            return
        exists = name in data["combined_sets"]
        if update and not exists:
            tkmsg.showwarning("組み合わせセット", "変更する登録済み組み合わせセットを選択してください。")
            return
        if not update and exists:
            tkmsg.showwarning("組み合わせセット", "同名の組み合わせセットが登録済みです。変更保存を使用してください。")
            return
        data["combined_sets"][name] = {"input_set": input_name, "recording_set": recording_name}
        self._write_input_sets(data)
        self.refresh_input_sets()
        self._select_input_recording_set()

    def _select_input_recording_set(self, event=None):
        item = self._read_input_sets()["combined_sets"].get(self.input_recording_set_name.get().strip())
        if not item:
            return
        self.input_recording_input_name.set(item.get("input_set", ""))
        self.input_recording_record_name.set(item.get("recording_set", ""))
        self.input_recording_summary.set("InputSet: {} / Recording: {}".format(
            item.get("input_set", ""), item.get("recording_set", "")))

    def load_input_recording_set(self):
        item = self._read_input_sets()["combined_sets"].get(self.input_recording_set_name.get().strip())
        if not item:
            tkmsg.showwarning("組み合わせセット", "呼び出す登録済み組み合わせセットを選択してください。")
            return
        input_item = self._read_input_sets()["input_sets"].get(item.get("input_set"))
        if not input_item:
            tkmsg.showerror("組み合わせセット", "参照しているInputSetがありません。")
            return
        self._apply_input_set_data(input_item)
        self.recording_preset_name.set(item.get("recording_set", ""))
        self.load_recording_preset()
        self._select_input_recording_set()

    def delete_input_recording_set(self):
        name = self.input_recording_set_name.get().strip()
        data = self._read_input_sets()
        if name not in data["combined_sets"]:
            tkmsg.showwarning("組み合わせセット", "削除する登録済み組み合わせセットを選択してください。")
            return
        if not tkmsg.askyesno("組み合わせセット", "組み合わせセット「{}」を削除しますか？".format(name)):
            return
        del data["combined_sets"][name]
        self._write_input_sets(data)
        self.input_recording_set_name.set("")
        self.refresh_input_sets()

    def refresh_audio_devices(self):
        self.all_audio_inputs = AudioMonitor.devices("input")
        self.update_audio_input_list()

    def _show_full_audio_device_name(self, *_):
        self.audio_device_full_name.set(self.audio_input.get())

    def update_audio_input_list(self):
        """Optionally limit Audio In to devices similar to the selected camera."""
        import re

        camera_name = self.camera_name_cb.get().lower()
        tokens = [word for word in re.split(r"[^a-z0-9]+", camera_name) if len(word) >= 3]
        inputs = getattr(self, "all_audio_inputs", [])
        if self.audio_filter_camera.get() and tokens:
            inputs = [name for name in inputs if any(token in name.lower() for token in tokens)]
        self.audio_input_cb.configure(values=inputs)
        if inputs and self.audio_input.get() not in inputs:
            self.audio_input.set(inputs[0])
        elif not inputs:
            self.audio_input.set("")

    def match_camera_audio(self):
        """Select the audio device whose name best matches the camera name."""
        import re

        camera_name = self.camera_name_cb.get().lower()
        # USB model words are more useful than generic words such as 'video'.
        tokens = [word for word in re.split(r"[^a-z0-9]+", camera_name) if len(word) >= 3]
        candidates = list(self.audio_input_cb.cget("values"))
        best = max(candidates, key=lambda name: sum(token in name.lower() for token in tokens), default=None)
        if best and any(token in best.lower() for token in tokens):
            self.audio_input.set(best)
        else:
            tkmsg.showinfo("Capture audio", "カメラ名に一致する音声デバイスを見つけられませんでした。Audio Inから選択してください。")

    def start_audio_monitor(self):
        try:
            self.audio_monitor.start(self.audio_input.get(), gain_percent=self.audio_gain.get())
            self.audio_start_button.configure(text="Audio running")
        except Exception as error:
            tkmsg.showerror("Capture audio", "音声デバイスを開始できません。sounddevice をインストールし、キャプチャーデバイスを選択してください。\n\n" + str(error))

    def start_audio_on_launch(self):
        """Automatic start should never show a modal error during launch."""
        if not self.audio_auto_start.get() or not self.audio_input.get():
            return
        try:
            self.audio_monitor.start(self.audio_input.get(), gain_percent=self.audio_gain.get())
            self.audio_start_button.configure(text="Audio running")
        except Exception as error:
            print("[AUDIO] Automatic start failed: " + str(error))

    def stop_audio_monitor(self):
        self.audio_monitor.stop()
        self.audio_start_button.configure(text="Start audio")

    def choose_record_template(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Recording trigger template", filetypes=[("Image", "*.png;*.jpg;*.jpeg;*.bmp")])
        if path:
            self.record_template_path.set(path)
            self.recorder.configure_template(path)

    def configure_recording_rules(self):
        """Apply saved multi-image AND rules and post-recording discard rules."""
        valid_trigger = [rule for rule in self.record_trigger_rules if rule.get("path")]
        self.recorder.configure_trigger_rules(valid_trigger)
        self.recorder.configure_cleanup_rules(self.record_cleanup_rules, self.record_minimum_duration.get())

    def _recording_presets_path(self):
        return os.path.join(os.path.dirname(Settings.GuiSettings.SETTING_PATH), "recording_presets.json")

    def _read_recording_presets(self):
        path = self._recording_presets_path()
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_recording_presets(self, data):
        path = self._recording_presets_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def refresh_recording_presets(self):
        if hasattr(self, "recording_preset_cb"):
            self.recording_preset_cb.configure(values=sorted(self._read_recording_presets().keys()))
        if hasattr(self, "input_recording_record_cb"):
            self.refresh_input_sets()

    def _recording_preset_data(self):
        return {
            "mode": self.record_mode.get(),
            "template_path": self.record_template_path.get(),
            "threshold": self.record_threshold.get(),
            "interval": self.record_interval.get(),
            "release_seconds": self.record_release.get(),
            "roi": self.record_roi.get(),
            "debug": self.record_debug.get(),
            "trigger_rules": self.record_trigger_rules,
            "cleanup_rules": self.record_cleanup_rules,
            "minimum_duration": self.record_minimum_duration.get(),
            "variable_command": self.record_variable_command.get(),
            "variable_name": self.record_variable_name.get(),
            "variable_start": self.record_variable_start.get(),
            "variable_stop": self.record_variable_stop.get(),
            "output_mode": self.record_output_mode.get(),
            "output_logs": self.record_output_logs.get(),
            "output_guide": self.record_output_guide.get(),
            "output_value": self.record_output_value.get(),
        }

    def save_recording_preset(self):
        name = self.recording_preset_name.get().strip()
        if not name:
            tkmsg.showwarning("Recording set", "Enter a set name.")
            return
        data = self._read_recording_presets()
        data[name] = self._recording_preset_data()
        self._write_recording_presets(data)
        self.refresh_recording_presets()

    def load_recording_preset(self):
        name = self.recording_preset_name.get().strip()
        data = self._read_recording_presets().get(name)
        if not data:
            tkmsg.showwarning("Recording set", "Select a saved recording set.")
            return
        self.record_mode.set(data.get("mode", "Manual"))
        self.record_template_path.set(data.get("template_path", ""))
        self.record_threshold.set(data.get("threshold", 0.9))
        self.record_interval.set(data.get("interval", 0.5))
        self.record_release.set(data.get("release_seconds", 1.0))
        self.record_roi.set(data.get("roi", "0,0,0,0"))
        self.record_debug.set(data.get("debug", False))
        self.record_trigger_rules = data.get("trigger_rules", [])
        self.record_cleanup_rules = data.get("cleanup_rules", [])
        self.record_minimum_duration.set(data.get("minimum_duration", 0))
        self.record_variable_command.set(data.get("variable_command", ""))
        self.record_variable_name.set(data.get("variable_name", "current_step"))
        self.record_variable_start.set(data.get("variable_start", ""))
        self.record_variable_stop.set(data.get("variable_stop", ""))
        self.record_output_mode.set(data.get("output_mode", "Video only"))
        self.record_output_logs.set(data.get("output_logs", "Output#1"))
        self.record_output_guide.set(data.get("output_guide", False))
        self.record_output_value.set(data.get("output_value", False))
        self.configure_recording_rules()
        if not self.record_trigger_rules:
            self.recorder.configure_template(self.record_template_path.get())
        self.toggle_record_debug()

    def delete_recording_preset(self):
        name = self.recording_preset_name.get().strip()
        data = self._read_recording_presets()
        if name not in data:
            tkmsg.showwarning("Recording set", "Select a saved recording set.")
            return
        if tkmsg.askyesno("Recording set", "Delete recording set '" + name + "'?"):
            del data[name]
            self._write_recording_presets(data)
            self.recording_preset_name.set("")
            self.refresh_recording_presets()

    def open_recording_rules(self):
        """Edit multi-image start (AND) and discard rules in a small popup."""
        from tkinter import filedialog

        dialog = tk.Toplevel(self.root)
        dialog.title("Recording image rules")
        dialog.transient(self.root)
        trigger_rows = [
            {"path": tk.StringVar(value=item.get("path", "")), "threshold": tk.DoubleVar(value=item.get("threshold", 0.9))}
            for item in self.record_trigger_rules
        ] or [{"path": tk.StringVar(value=self.record_template_path.get()), "threshold": tk.DoubleVar(value=self.record_threshold.get())}]
        cleanup_rows = [
            {"path": tk.StringVar(value=item.get("path", "")), "threshold": tk.DoubleVar(value=item.get("threshold", 0.9)),
             "minimum_percent": tk.DoubleVar(value=item.get("minimum_percent", 100.0))}
            for item in self.record_cleanup_rules
        ]
        trigger_frame = ttk.Labelframe(dialog, text="Start images — ALL images must match (AND)")
        cleanup_frame = ttk.Labelframe(dialog, text="Discard a completed recording when an image is present")
        trigger_frame.grid(column=0, row=0, padx=8, pady=6, sticky="ew")
        cleanup_frame.grid(column=0, row=1, padx=8, pady=6, sticky="ew")

        def pick(target):
            path = filedialog.askopenfilename(title="Choose image", filetypes=[("Image", "*.png;*.jpg;*.jpeg;*.bmp")])
            if path:
                target.set(path)

        def render_trigger():
            for child in trigger_frame.winfo_children():
                child.destroy()
            ttk.Label(trigger_frame, text="Image").grid(column=0, row=0, padx=3)
            ttk.Label(trigger_frame, text="Threshold").grid(column=3, row=0, padx=3)
            for row, item in enumerate(trigger_rows, 1):
                ttk.Entry(trigger_frame, textvariable=item["path"], width=52).grid(column=0, row=row, padx=3, pady=2)
                ttk.Button(trigger_frame, text="...", width=3, command=lambda value=item["path"]: pick(value)).grid(column=1, row=row)
                ttk.Spinbox(trigger_frame, from_=0.1, to=1.0, increment=0.05, textvariable=item["threshold"], width=6).grid(column=3, row=row)
                ttk.Button(trigger_frame, text="-", width=3, command=lambda index=row - 1: (trigger_rows.pop(index), render_trigger())).grid(column=4, row=row)
            ttk.Button(trigger_frame, text="+ Add start image", command=lambda: (trigger_rows.append({"path": tk.StringVar(), "threshold": tk.DoubleVar(value=0.9)}), render_trigger())).grid(column=0, row=len(trigger_rows) + 1, padx=3, pady=3, sticky="w")

        def render_cleanup():
            for child in cleanup_frame.winfo_children():
                child.destroy()
            ttk.Label(cleanup_frame, text="Image").grid(column=0, row=0, padx=3)
            ttk.Label(cleanup_frame, text="Match threshold").grid(column=3, row=0, padx=3)
            ttk.Label(cleanup_frame, text="Discard if present >= %").grid(column=4, row=0, padx=3)
            for row, item in enumerate(cleanup_rows, 1):
                ttk.Entry(cleanup_frame, textvariable=item["path"], width=52).grid(column=0, row=row, padx=3, pady=2)
                ttk.Button(cleanup_frame, text="...", width=3, command=lambda value=item["path"]: pick(value)).grid(column=1, row=row)
                ttk.Spinbox(cleanup_frame, from_=0.1, to=1.0, increment=0.05, textvariable=item["threshold"], width=6).grid(column=3, row=row)
                ttk.Spinbox(cleanup_frame, from_=0, to=100, increment=1, textvariable=item["minimum_percent"], width=6).grid(column=4, row=row)
                ttk.Button(cleanup_frame, text="-", width=3, command=lambda index=row - 1: (cleanup_rows.pop(index), render_cleanup())).grid(column=5, row=row)
            ttk.Button(cleanup_frame, text="+ Add discard image", command=lambda: (cleanup_rows.append({"path": tk.StringVar(), "threshold": tk.DoubleVar(value=0.9), "minimum_percent": tk.DoubleVar(value=100.0)}), render_cleanup())).grid(column=0, row=len(cleanup_rows) + 1, padx=3, pady=3, sticky="w")

        def save_rules():
            self.record_trigger_rules = [{"path": item["path"].get(), "threshold": item["threshold"].get()} for item in trigger_rows if item["path"].get()]
            self.record_cleanup_rules = [
                {"path": item["path"].get(), "threshold": item["threshold"].get(), "minimum_percent": item["minimum_percent"].get()}
                for item in cleanup_rows if item["path"].get()
            ]
            self.configure_recording_rules()
            dialog.destroy()

        render_trigger()
        render_cleanup()
        ttk.Label(dialog, text="Discard recordings shorter than (s):").grid(column=0, row=2, padx=8, pady=(4, 0), sticky="w")
        ttk.Spinbox(dialog, from_=0, to=3600, increment=1, textvariable=self.record_minimum_duration, width=8).grid(column=0, row=3, padx=8, sticky="w")
        ttk.Button(dialog, text="Save rules", command=save_rules).grid(column=0, row=4, padx=8, pady=8, sticky="e")

    def _recording_roi(self):
        try:
            values = tuple(map(int, self.record_roi.get().split(",")))
            return values if len(values) == 4 else (0, 0, 0, 0)
        except ValueError:
            return 0, 0, 0, 0

    def toggle_record_debug(self):
        if self.record_debug.get():
            self.record_debug_status.set("Debug: checking template in the ROI...")
            return
        self.record_debug_status.set("Debug: disabled")
        if hasattr(self, "preview"):
            self.preview.deleteImageRect("RecordingDebugROI")
            self.preview.deleteImageText("RecordingDebugText")

    def update_recording_debug(self, frame):
        """Show the template search area and the most recent match result."""
        if not self.record_debug.get():
            return
        x, y, width, height = self.recorder.last_roi
        if width <= 0 or height <= 0:
            height, width = frame.shape[:2]
            x, y = 0, 0
        score = self.recorder.last_score
        threshold = self.record_threshold.get()
        if score is None:
            text = "ROI: {}  score: n/a (template is larger than ROI or unavailable)".format((x, y, width, height))
            color = "orange"
        else:
            matched = score >= threshold
            text = "ROI: {}  score: {:.3f} / threshold: {:.3f}  {}".format(
                (x, y, width, height), score, threshold, "MATCH" if matched else "NO MATCH"
            )
            color = "lime" if matched else "red"
        self.record_debug_status.set("Debug: " + text)
        self.preview.deleteImageRect("RecordingDebugROI")
        self.preview.deleteImageText("RecordingDebugText")
        self.preview.ImgRect(x, y, x + width, y + height, color, "RecordingDebugROI", 0, flag=False)
        self.preview.ImgText(x, max(18, y + 20), text, "RecordingDebugText", 0, color=color, flag=False)

    def toggle_recording(self):
        self.configure_recording_rules()
        if self.record_mode.get() == "Variable":
            if self.record_armed:
                self.record_armed = False
                if self.recorder.active:
                    self.recorder.stop()
                self.record_button.configure(text="Start recording")
                self.record_variable_status.set("Variable segments: stopped")
                return
            if not self.record_variable_command.get() or not self.record_variable_name.get().strip() or not self.record_variable_start.get().strip() or not self.record_variable_stop.get().strip():
                tkmsg.showwarning("Recording", "Select a command and enter variable, start value, and stop value.")
                return
            self.record_armed = True
            self.record_button.configure(text="Stop monitoring")
            self.record_variable_status.set("Armed: waiting for {} == {}".format(self.record_variable_name.get(), self.record_variable_start.get()))
            return
        if self.record_mode.get() == "Template":
            if self.record_armed:
                self.record_armed = False
                if self.recorder.active:
                    self.recorder.stop()
                self.record_button.configure(text="Start recording")
                return
            if not self.record_trigger_rules and not self.record_template_path.get():
                tkmsg.showwarning("Recording", "Choose a template image before arming template recording.")
                return
            if not self.record_trigger_rules:
                self.recorder.configure_template(self.record_template_path.get())
            expected_rules = len(self.record_trigger_rules) if self.record_trigger_rules else 1
            configured_rules = len(self.recorder.trigger_rules) if self.record_trigger_rules else (1 if self.recorder.template is not None else 0)
            if configured_rules != expected_rules:
                tkmsg.showwarning("Recording", "The template image could not be read.")
                return
            self.record_armed = True
            self.recorder.last_check = 0.0
            self.record_button.configure(text="Stop monitoring")
            self.show_output("Analysis", text="Template recording armed: waiting for score >= threshold.")
            return
        if self.recorder.active:
            self.recorder.stop()
            self.record_button.configure(text="Start recording")
            self.show_output("Analysis", text="録画を停止しました。MP4はバックグラウンドで結合中です。")
            return
        frame = getattr(self.camera, "image_bgr", None)
        if frame is None:
            tkmsg.showwarning("Recording", "カメラ映像を開始してから録画してください。")
            return
        self.recorder.start(frame, self.fps.get(), self.audio_input.get(), self.audio_gain.get())
        self.record_button.configure(text="Stop recording")

    def open_recording_output_layout(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Recording output layout")
        dialog.transient(self.root)
        ttk.Radiobutton(dialog, text="Video only (existing recording sets)", value="Video only", variable=self.record_output_mode).grid(column=0, columnspan=2, row=0, padx=8, pady=5, sticky="w")
        ttk.Radiobutton(dialog, text="Video + log panel", value="Video + logs", variable=self.record_output_mode).grid(column=0, columnspan=2, row=1, padx=8, pady=3, sticky="w")
        ttk.Label(dialog, text="Log panel:").grid(column=0, row=2, padx=8, pady=4, sticky="w")
        ttk.Combobox(dialog, state="readonly", width=18, textvariable=self.record_output_logs, values=("Output#1", "Output#2", "Output#1 + Output#2")).grid(column=1, row=2, padx=8, pady=4, sticky="w")
        ttk.Checkbutton(dialog, text="Include Show Guide overlay", variable=self.record_output_guide).grid(column=0, columnspan=2, row=3, padx=8, pady=3, sticky="w")
        ttk.Checkbutton(dialog, text="Include Show Value overlay", variable=self.record_output_value).grid(column=0, columnspan=2, row=4, padx=8, pady=3, sticky="w")
        ttk.Button(dialog, text="Close", command=dialog.destroy).grid(column=1, row=5, padx=8, pady=8, sticky="e")

    def recording_output_frame(self, frame):
        if self.record_output_mode.get() == "Video only":
            return frame
        lines = []
        selected = self.record_output_logs.get()
        if "Output#1" in selected:
            lines.append("[Output#1]")
            lines.extend(self.text_area_1.get("1.0", "end-1c").splitlines()[-18:])
        if "Output#2" in selected:
            lines.append("[Output#2]")
            lines.extend(self.text_area_2.get("1.0", "end-1c").splitlines()[-18:])
        if self.record_output_guide.get() and self.is_show_guide.get():
            lines.insert(0, "[Show Guide enabled]")
        if self.record_output_value.get() and self.is_show_value.get():
            lines.insert(0, "[Show Value enabled]")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        panel_width = min(420, max(180, width // 3))
        # Keep the original frame size so template-triggered recording may
        # start before the next composed frame arrives.
        canvas = Image.new("RGB", (width, height), "#202020")
        video_width = max(1, width - panel_width)
        canvas.paste(Image.fromarray(rgb).resize((video_width, height)), (0, 0))
        draw = ImageDraw.Draw(canvas)
        y = 10
        for line in lines:
            draw.text((video_width + 10, y), str(line)[:max(12, panel_width // 7)], fill="white")
            y += 18
            if y >= height - 18:
                break
        return cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR)

    def process_recording_frame(self, frame):
        record_frame = self.recording_output_frame(frame)
        if self.record_mode.get() == "Manual":
            self.recorder.add_frame(record_frame)
            return
        if self.record_mode.get() == "Variable":
            if not self.record_armed:
                return
            command = getattr(self, "cur_command", None)
            if command is None or getattr(command, "NAME", "") != self.record_variable_command.get():
                self.record_variable_status.set("Waiting for selected command to run.")
                return
            name = self.record_variable_name.get().strip()
            value = str(getattr(command, name, "<not set>"))
            if not self.recorder.active and value == self.record_variable_start.get():
                self.recorder.start(record_frame, self.fps.get(), self.audio_input.get(), self.audio_gain.get())
                self.record_variable_status.set("Recording: {} == {}".format(name, value))
            if self.recorder.active:
                self.recorder.add_frame(record_frame)
                if value == self.record_variable_stop.get():
                    self.recorder.stop()
                    self.record_variable_status.set("Segment completed: {} == {}. Waiting for next start.".format(name, value))
            return
        if not self.record_armed and not self.record_debug.get():
            return
        if not self.record_trigger_rules and self.recorder.template_path != self.record_template_path.get():
            self.recorder.configure_template(self.record_template_path.get())
        result = self.recorder.process_detection(
            frame, self.fps.get(), self.audio_input.get(), self.audio_gain.get(), self.record_threshold.get(), self._recording_roi(),
            self.record_interval.get(), self.record_release.get(), allow_start=self.record_armed,
        )
        self.update_recording_debug(frame)
        # A detected segment must receive every camera frame, not merely the
        # low-frequency frames that are used for template matching.
        if self.recorder.active:
            self.recorder.add_frame(record_frame)
        if result is not None:
            # Stay armed after one segment finishes so the next matching
            # appearance becomes the next timestamped recording.
            self.root.after(0, lambda: self.record_button.configure(text="Stop monitoring"))
        elif self.recorder.active:
            self.root.after(0, lambda: self.record_button.configure(text="Stop recording"))

    def _sync_settings_for_preset(self):
        """Copy every UI setting owned by the added tabs into GuiSettings."""
        self.settings.camera_id.set(self.camera_id.get())
        self.settings.com_port.set(self.com_port.get())
        self.settings.com_port_name.set(self.com_port_name.get())
        self.settings.baud_rate.set(self.baud_rate.get())
        self.settings.fps.set(self.fps.get())
        self.settings.show_size.set(self.show_size.get())
        self.settings.is_show_realtime.set(self.is_show_realtime.get())
        self.settings.is_show_value.set(self.is_show_value.get())
        self.settings.is_show_guide.set(self.is_show_guide.get())
        self.settings.is_show_serial.set(self.is_show_serial.get())
        self.settings.is_use_keyboard.set(self.is_use_keyboard.get())
        self.settings.serial_data_format_name.set(self.serial_data_format_name.get())
        self.settings.area_size = self.area_size.get()
        self.settings.stdout_destination = self.stdout_destination.get()
        self.settings.right_frame_widget_mode = self.right_frame_widget_mode.get()
        self.settings.pos_software_controller = self.pos_software_controller.get()
        self.settings.pos_dialogue_buttons = self.pos_dialogue_buttons.get()
        self.settings.panel_left_top = self.panel_slots["left_top"].get()
        self.settings.panel_left_bottom = self.panel_slots["left_bottom"].get()
        self.settings.panel_right_top = self.panel_slots["right_top"].get()
        self.settings.panel_right_bottom = self.panel_slots["right_bottom"].get()
        self.settings.panel_ratio = self.panel_ratio.get()
        self.settings.right_panel_ratio = self.right_panel_ratio.get()
        self.settings.panel_layout = self.panel_layout.get()
        self.settings.panel_sides = self.panel_sides.get()
        self.settings.left_panel_count = self.left_panel_count.get()
        self.settings.right_panel_count = self.right_panel_count.get()
        self.settings.side_width_balance = self.side_width_balance.get()
        self.settings.show_software_controller = self.show_software_controller.get()
        self.settings.audio_input = self.audio_input.get()
        self.settings.audio_gain = self.audio_gain.get()
        self.settings.audio_filter_camera = self.audio_filter_camera.get()
        self.settings.audio_auto_start = self.audio_auto_start.get()
        self.settings.vision_mode = self.vision_mode.get()
        self.settings.record_mode = self.record_mode.get()
        self.settings.record_template_path = self.record_template_path.get()
        self.settings.record_threshold = self.record_threshold.get()
        self.settings.record_interval = self.record_interval.get()
        self.settings.record_release = self.record_release.get()
        self.settings.record_roi = self.record_roi.get()
        self.settings.record_debug = self.record_debug.get()
        self.settings.record_trigger_rules = json.dumps(self.record_trigger_rules)
        self.settings.record_cleanup_rules = json.dumps(self.record_cleanup_rules)
        self.settings.record_minimum_duration = self.record_minimum_duration.get()
        self.settings.record_variable_command = self.record_variable_command.get()
        self.settings.record_variable_name = self.record_variable_name.get()
        self.settings.record_variable_start = self.record_variable_start.get()
        self.settings.record_variable_stop = self.record_variable_stop.get()
        self.settings.area_capture_roi = self.area_capture_roi.get()
        self.settings.area_capture_output_target = self.area_capture_output_target.get()
        self.settings.area_capture_background = self.area_capture_background.get()
        self.settings.area_capture_active = self.area_capture_active.get()
        self.settings.command_watch_enabled = self.command_watch_enabled.get()
        self.settings.command_watch_command = self.command_watch_command.get()
        self.settings.command_watch_target = self.command_watch_target.get()
        self.settings.command_watch_variables = ",".join(self.command_watch_variables)

    def _preset_dir(self):
        return os.path.join(os.path.dirname(Settings.GuiSettings.SETTING_PATH), "presets")

    def _others_presets_path(self):
        return os.path.join(os.path.dirname(Settings.GuiSettings.SETTING_PATH), "others_presets.json")

    def _read_others_presets(self):
        try:
            with open(self._others_presets_path(), "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_others_presets(self, data):
        os.makedirs(os.path.dirname(self._others_presets_path()), exist_ok=True)
        with open(self._others_presets_path(), "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def refresh_others_presets(self):
        if hasattr(self, "others_preset_cb"):
            self.others_preset_cb.configure(values=sorted(self._read_others_presets().keys()))

    def _others_preset_data(self):
        return {
            "stdout_destination": self.stdout_destination.get(),
            "clear_log_target": self.clear_log_target.get(),
            "pos_software_controller": self.pos_software_controller.get(),
            "pos_dialogue_buttons": self.pos_dialogue_buttons.get(),
            "left_top": self.panel_slots["left_top"].get(),
            "left_bottom": self.panel_slots["left_bottom"].get(),
            "right_top": self.panel_slots["right_top"].get(),
            "right_bottom": self.panel_slots["right_bottom"].get(),
            "panel_sides": self.panel_sides.get(),
            "left_panel_count": self.left_panel_count.get(),
            "right_panel_count": self.right_panel_count.get(),
            "side_width_balance": self.side_width_balance.get(),
            "left_panel_ratio": self.panel_ratio.get(),
            "right_panel_ratio": self.right_panel_ratio.get(),
            "show_software_controller": self.show_software_controller.get(),
        }

    def save_others_preset(self):
        name = self.others_preset_name.get().strip()
        if not name:
            tkmsg.showwarning("Others setting set", "保存セット名を入力してください。")
            return
        presets = self._read_others_presets()
        presets[name] = self._others_preset_data()
        self._write_others_presets(presets)
        self.refresh_others_presets()

    def load_others_preset(self):
        name = self.others_preset_name.get().strip()
        data = self._read_others_presets().get(name)
        if not data:
            tkmsg.showwarning("Others setting set", "読み出す保存セットを選択してください。")
            return
        self.stdout_destination.set(str(data.get("stdout_destination", self.stdout_destination.get())))
        self.pos_software_controller.set(str(data.get("pos_software_controller", self.pos_software_controller.get())))
        self.pos_dialogue_buttons.set(str(data.get("pos_dialogue_buttons", self.pos_dialogue_buttons.get())))
        for key, slot in (("left_top", "left_top"), ("left_bottom", "left_bottom"),
                          ("right_top", "right_top"), ("right_bottom", "right_bottom")):
            self.panel_slots[slot].set(data.get(key, self.panel_slots[slot].get()))
        self.panel_sides.set(data.get("panel_sides", self.panel_sides.get()))
        self.left_panel_count.set(str(data.get("left_panel_count", self.left_panel_count.get())))
        self.right_panel_count.set(str(data.get("right_panel_count", self.right_panel_count.get())))
        self.side_width_balance.set(int(data.get("side_width_balance", self.side_width_balance.get())))
        self.panel_ratio.set(int(data.get("left_panel_ratio", self.panel_ratio.get())))
        self.right_panel_ratio.set(int(data.get("right_panel_ratio", self.right_panel_ratio.get())))
        self.show_software_controller.set(bool(data.get("show_software_controller", self.show_software_controller.get())))
        self.clear_log_target.set(data.get("clear_log_target", self.clear_log_target.get()))
        self.apply_panel_assignment()
        self.refresh_log_controls()

    def delete_others_preset(self):
        name = self.others_preset_name.get().strip()
        presets = self._read_others_presets()
        if name not in presets:
            tkmsg.showwarning("Others setting set", "削除する保存セットを選択してください。")
            return
        if tkmsg.askyesno("Others setting set", "保存セット '" + name + "' を削除しますか？"):
            del presets[name]
            self._write_others_presets(presets)
            self.others_preset_name.set("")
            self.refresh_others_presets()

    def _preset_path(self, name):
        safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", name.strip())
        return os.path.join(self._preset_dir(), safe_name + ".ini") if safe_name else None

    def refresh_presets(self):
        os.makedirs(self._preset_dir(), exist_ok=True)
        names = [os.path.splitext(entry)[0] for entry in os.listdir(self._preset_dir()) if entry.endswith(".ini")]
        self.preset_cb.configure(values=sorted(names))

    def save_preset(self):
        path = self._preset_path(self.preset_name.get())
        if path is None:
            tkmsg.showwarning("Presets", "保存セット名を入力してください。")
            return
        self._sync_settings_for_preset()
        self.settings.save(path)
        self.refresh_presets()
        tkmsg.showinfo("Presets", "全タブの設定を保存しました。")

    def load_preset(self):
        path = self._preset_path(self.preset_name.get())
        if path is None or not os.path.isfile(path):
            tkmsg.showwarning("Presets", "読み出す保存セットを選択してください。")
            return
        if tkmsg.askyesno("Presets", "現在の設定をこの保存セットで置き換え、PokeConを再起動しますか？"):
            shutil.copyfile(path, Settings.GuiSettings.SETTING_PATH)
            tkmsg.showinfo("Presets", "読み出しました。PokeConを再起動してください。")

    def delete_preset(self):
        path = self._preset_path(self.preset_name.get())
        if path is None or not os.path.isfile(path):
            tkmsg.showwarning("Presets", "削除する保存セットを選択してください。")
            return
        if tkmsg.askyesno("Presets", f"保存セット '{self.preset_name.get()}' を削除しますか？"):
            os.remove(path)
            self.preset_name.set("")
            self.refresh_presets()

    def open_html_output(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Open HTML for Output#2", filetypes=[("HTML", "*.html;*.htm")])
        if not path:
            return
        with open(path, encoding="utf-8", errors="replace") as html_file:
            source = html_file.read()
        self.text_area_2.configure(state="normal")
        self.text_area_2.delete("1.0", "end")
        self.text_area_2.insert("end", source)
        self.text_area_2.configure(state="disabled")
        # Tk itself has no secure HTML renderer.  The system browser gives full
        # HTML/CSS/JS rendering while Output#2 keeps the source/result visible.
        webbrowser.open(Path(path).resolve().as_uri())

    def changeAreaSize(self, *event):
        _, height = map(int, self.show_size.get().split("x"))
        max_size = 0.075 * height
        mode = self.right_frame_widget_mode.get()
        flag = False
        if mode == "ALL (default)":
            max_size = max_size - 1
        elif mode == "Output#1 + Output#2":
            max_size = max_size + 15
        elif "+" in mode and "Controller" in mode:
            max_size = max_size + 3
            flag = True
        else:
            pass
        adjust_size = max_size - 8
        if flag:
            text_area_1_size = max_size
            text_area_2_size = max_size
        else:
            text_area_1_size = int(round((float(self.area_size.get()) / 100.0) * adjust_size) + 4)
            text_area_2_size = max_size - text_area_1_size
        self.text_area_1.config(height=text_area_1_size)
        self.text_area_2.config(height=text_area_2_size)

    def switchStdoutDestination(self, silent=False):
        val = self.stdout_destination.get()
        if val == "1":
            sys.stdout = StdoutRedirector(self.text_area_1)
            if not silent:
                print("standard output destination is switched.")
            Command.stdout_destination = val
            self.text_scroll_1.configure(text="Output#1 (Stdout)")
            self.text_scroll_2.configure(text="Output#2")
        elif val == "2":
            sys.stdout = StdoutRedirector(self.text_area_2)
            if not silent:
                print("standard output destination is switched.")
            Command.stdout_destination = val
            self.text_scroll_1.configure(text="Output#1")
            self.text_scroll_2.configure(text="Output#2 (Stdout)")

    def replace_right_frame_widget(self, *event):
        # Replaced by the explicit side-panel assignment in Others.
        if hasattr(self, "panel_sides"):
            self.apply_panel_assignment()
            return
        try:
            self.text_scroll_1.pack_forget()
        except Exception:
            pass
        try:
            self.text_scroll_2.pack_forget()
        except Exception:
            pass
        try:
            self.softcon_frame.pack_forget()
        except Exception:
            pass

        mode = self.right_frame_widget_mode.get()

        if self.pos_software_controller.get() == "1" and (mode == "ALL (default)" or "Controller" in mode):
            self.softcon_frame.pack(expand="true", fill="both", padx="0", pady="0", side="top")
            self.softcon_frame.grid_anchor("center")

        if mode == "ALL (default)" or "#1" in mode:
            self.text_scroll_1.pack(expand="true", fill="both", padx="0", pady="0", side="top")
        if mode == "ALL (default)" or "#2" in mode:
            self.text_scroll_2.pack(expand="true", fill="both", padx="0", pady="0", side="top")

        if self.pos_software_controller.get() == "2" and (mode == "ALL (default)" or "Controller" in mode):
            self.softcon_frame.pack(expand="true", fill="both", padx="0", pady="0", side="top")
            self.softcon_frame.grid_anchor("center")

        self.changeAreaSize()

    def hold(self, event, buttons: Button | Hat | Stick | Direction):
        """
        ボタンを押す。
        """
        if event.widget["bg"] != "#FFD800":
            self.keys_software_controller.hold(buttons)

    def holdEnd(self, event, buttons: Button | Hat | Stick | Direction):
        """
        ボタンを押しっぱなしにする/解除する
        """
        event.widget["bg"] = "#343434"
        event.widget["fg"] = "#FFFFFF"
        self.keys_software_controller.holdEnd(buttons)

    def holdEndSkip(self, event, buttons: Button | Hat | Stick | Direction):
        """
        なにもしない
        """
        event.widget["bg"] = "#FFD800"
        event.widget["fg"] = "#343434"

    def holdForceEnd(self):
        """
        hold状態を強制的に解除する
        (holdを示す色も変える)
        """
        self.keys_software_controller.neutral()
        self.softcon_zl_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_l_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_minus_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_l_click_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_up_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_left_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_right_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_down_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_capture_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_zr_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_r_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_plus_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_r_click_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_x_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_y_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_a_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_b_button.configure(bg="#343434", fg="#FFFFFF")
        self.softcon_home_button.configure(bg="#343434", fg="#FFFFFF")


# ToolTipのクラスは以下のサイトを参考に作成
# https://www.ishikawasekkei.com/index.php/2020/05/17/python-tkinter-gui-programing-tooltip/


class ToolTip:
    def __init__(self, widget, text="default tooltip"):
        self.widget = widget
        self.text = text
        self.widget.bind("<Motion>", self.moveCursor)
        self.widget.bind("<Leave>", self.leaveCursor)
        self.id = None
        self.tw = None

    def moveCursor(self, event):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)
        if not self.tw:
            id = self.id
            self.id = None
            if id:
                self.widget.after_cancel(id)
            self.id = self.widget.after(300, self.createTooltip)

    def leaveCursor(self, event):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)
        self.id = self.widget.after(300, self.destroyTooltip)

    def createTooltip(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)
        x, y = self.widget.winfo_pointerxy()
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.geometry(f"+{x + 15}+{y - 35}")
        label = tk.Label(self.tw, text=self.text, background="#98FB98", relief="solid", borderwidth=0.5, justify="left")
        label.pack(ipadx=10)

    def destroyTooltip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()


class StdoutRedirector(object):
    """
    標準出力をtextウィジェットにリダイレクトするクラス
    重いので止めました →# update_idletasks()で出力のたびに随時更新(従来はfor loopのときなどにまとめて出力されることがあった)
    """

    def __init__(self, text_widget):
        self.text_space = text_widget

    def write(self, string):
        self.text_space.configure(state="normal")
        self.text_space.insert("end", string)
        self.text_space.see("end")
        # self.text_space.update_idletasks()
        self.text_space.configure(state="disabled")

    def flush(self):
        pass


if __name__ == "__main__":
    import tkinter as tk

    parser = argparse.ArgumentParser(description="Switch/GC automation support software using Python")
    parser.add_argument("--profile", "-p", help="profile", type=str, default="default")
    args = parser.parse_args()

    logger = PokeConLogger.root_logger()
    # logger.info('The root logger is created.')

    if not flag_import_plyer:
        tkmsg.showwarning(
            "Warning",
            '"plyer" is not installed. Some notification functions are not available. We recommend installing with "pip install plyer".',
        )

    root = tk.Tk()
    app = PokeControllerApp(root, args.profile)
    app.run()
