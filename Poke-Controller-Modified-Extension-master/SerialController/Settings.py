#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import configparser
import os
import tkinter as tk
from logging import getLogger  # , DEBUG, NullHandler

from AudioLevelControl import sanitize_audio_level_settings


class GuiSettings:
    SETTING_PATH = os.path.join(os.path.dirname(__file__), "profiles", "default", "settings.ini")

    def __init__(self):
        self._logger = getLogger(__name__)
        self.setting = configparser.ConfigParser()
        self.setting.optionxform = str
        # print("isExistConfig =", os.path.exists(self.SETTING_PATH))

        if not os.path.exists(self.SETTING_PATH):
            self._logger.debug("Setting file does not exists.")
            self.generate()
            self.load()
            self._logger.debug("Settings file has been generated.")
        else:
            self._logger.debug("Setting file exists.")
            self.load()
            self._logger.debug("Settings file has been loaded.")

        # default
        self.camera_id = tk.IntVar(value=self.setting["General Setting"].getint("camera_id"))
        self.video_source = self.setting.get("General Setting", "video_source", fallback="Capture device")
        self.window_capture_mode = self.setting.get(
            "General Setting", "window_capture_mode", fallback="client")
        self.window_title = self.setting.get("General Setting", "window_title", fallback="")
        self.window_process = self.setting.get("General Setting", "window_process", fallback="")
        self.com_port = tk.IntVar(value=self.setting["General Setting"].getint("com_port"))
        self.com_port_name = tk.StringVar(value=self.setting["General Setting"].get("com_port_name"))
        self.baud_rate = tk.IntVar(value=self.setting["General Setting"].getint("baud_rate"))
        self.fps = tk.StringVar(value=self.setting["General Setting"]["fps"])
        self.show_size = tk.StringVar(value=self.setting["General Setting"].get("show_size"))
        self.last_active_preview_full_fps = self.setting.getboolean(
            "General Setting", "last_active_preview_full_fps", fallback=False)
        self.resource_control_enabled = self.setting.getboolean(
            "Resource Control", "enabled", fallback=True)
        self.resource_cpu_target = self.setting.getint(
            "Resource Control", "cpu_target", fallback=90)
        self.resource_main_tool = self.setting.getboolean(
            "Resource Control", "main_tool", fallback=False)
        self.is_show_realtime = tk.BooleanVar(value=self.setting["General Setting"].getboolean("is_show_realtime"))
        self.is_show_value = tk.BooleanVar(value=self.setting["General Setting"].getboolean("is_show_value"))
        self.is_show_guide = tk.BooleanVar(value=self.setting["General Setting"].getboolean("is_show_guide"))
        self.is_show_serial = tk.BooleanVar(value=self.setting["General Setting"].getboolean("is_show_serial"))
        self.is_use_keyboard = tk.BooleanVar(value=self.setting["General Setting"].getboolean("is_use_keyboard"))
        try:
            self.serial_data_format_name = tk.StringVar(
                value=self.setting["General Setting"]["serial_data_format_name"]
            )
        except Exception:
            self.serial_data_format_name = tk.StringVar(value="Default")
        try:
            self.touchscreen_start_x = int(self.setting["General Setting"]["touchscreen_start_x"])
        except Exception:
            self.touchscreen_start_x = 1
        try:
            self.touchscreen_start_y = int(self.setting["General Setting"]["touchscreen_start_y"])
        except Exception:
            self.touchscreen_start_y = 1
        try:
            self.touchscreen_end_x = int(self.setting["General Setting"]["touchscreen_end_x"])
        except Exception:
            self.touchscreen_end_x = 320
        try:
            self.touchscreen_end_y = int(self.setting["General Setting"]["touchscreen_end_y"])
        except Exception:
            self.touchscreen_end_y = 240
        # Pokemon Home用の設定
        self.season = tk.StringVar(value=self.setting["Pokemon Home"].get("Season"))
        self.is_SingleBattle = tk.StringVar(value=self.setting["Pokemon Home"].get("Single or Double"))
        # Shortcut用の設定
        self.command_class_dict = {}
        self.command_name_dict = {}
        for i in range(1, 11):  # Update直後のError回避策
            try:
                self.command_class_dict[str(i)] = self.setting["Shortcut"][f"command_class_{i}"]
                self.command_name_dict[str(i)] = tk.StringVar(value=self.setting["Shortcut"][f"command_name_{i}"])
            except Exception:
                self.command_class_dict[str(i)] = "None"
                self.command_name_dict[str(i)] = tk.StringVar(value="(empty)")
        # Notification用の設定
        try:
            self.is_win_notification_start = tk.BooleanVar(
                value=self.setting["Notification"].getboolean("is_win_notification_start")
            )
        except Exception:
            self.is_win_notification_start = tk.BooleanVar(value=False)
        try:
            self.is_win_notification_end = tk.BooleanVar(
                value=self.setting["Notification"].getboolean("is_win_notification_end")
            )
        except Exception:
            self.is_win_notification_end = tk.BooleanVar(value=False)
        try:
            self.is_line_notification_start = tk.BooleanVar(
                value=self.setting["Notification"].getboolean("is_line_notification_start")
            )
        except Exception:
            self.is_line_notification_start = tk.BooleanVar(value=False)
        try:
            self.is_line_notification_end = tk.BooleanVar(
                value=self.setting["Notification"].getboolean("is_line_notification_end")
            )
        except Exception:
            self.is_line_notification_end = tk.BooleanVar(value=False)
        try:
            self.is_discord_notification_start = tk.BooleanVar(
                value=self.setting["Notification"].getboolean("is_discord_notification_start")
            )
        except Exception:
            self.is_discord_notification_start = tk.BooleanVar(value=False)
        try:
            self.is_discord_notification_end = tk.BooleanVar(
                value=self.setting["Notification"].getboolean("is_discord_notification_end")
            )
        except Exception:
            self.is_discord_notification_end = tk.BooleanVar(value=False)
        # Output Area用の設定
        self.area_size = self.setting["Output"]["area_size"]
        self.stdout_destination = self.setting["Output"]["stdout_destination"]
        try:
            self.right_frame_widget_mode = self.setting["Output"]["widget_mode"]
        except Exception:
            self.right_frame_widget_mode = "ALL (default)"
        try:
            self.pos_software_controller = self.setting["Output"]["software_controller_position"]
        except Exception:
            self.pos_software_controller = "2"
        try:
            self.pos_dialogue_buttons = self.setting["Output"]["dialogue_buttons_position"]
        except Exception:
            self.pos_dialogue_buttons = "2"
        self.panel_left_top = self.setting["Output"].get("panel_left_top", "Log: Output#3")
        self.panel_left_bottom = self.setting["Output"].get("panel_left_bottom", "Log: Output#4")
        self.panel_right_top = self.setting["Output"].get("panel_right_top", "Log: Output#1")
        self.panel_right_bottom = self.setting["Output"].get("panel_right_bottom", "Log: Output#2")
        self.panel_ratio = self.setting["Output"].get("panel_ratio", "50")
        # Keep the old ratio as the left-side value for backward-compatible
        # profiles.  Each side can now have its own top/bottom split.
        self.right_panel_ratio = self.setting["Output"].get("right_panel_ratio", self.panel_ratio)
        self.panel_layout = self.setting["Output"].get("panel_layout", "Four panels (left/right, top/bottom)")
        self.panel_sides = self.setting["Output"].get("panel_sides", "Both sides")
        self.left_panel_count = self.setting["Output"].get("left_panel_count", "2")
        self.right_panel_count = self.setting["Output"].get("right_panel_count", "2")
        self.side_width_balance = self.setting["Output"].get("side_width_balance", "50")
        self.show_software_controller = self.setting["Output"].getboolean("show_software_controller", True)
        self.audio_input = self.setting.get("Audio", "input_device", fallback="")
        self.audio_gain = self.setting.get("Audio", "gain", fallback="100")
        self.audio_filter_camera = self.setting.getboolean("Audio", "filter_camera", fallback=False)
        self.audio_auto_start = self.setting.getboolean("Audio", "auto_start", fallback=False)
        self.audio_auto_level = self.setting.getboolean(
            "Audio", "auto_level", fallback=False)
        self.audio_target_dbfs = self.setting.getfloat(
            "Audio", "target_dbfs", fallback=-6.0)
        self.audio_max_auto_gain = self.setting.getint(
            "Audio", "max_auto_gain", fallback=800)
        self.audio_limiter_ceiling_dbfs = self.setting.getfloat(
            "Audio", "limiter_ceiling_dbfs", fallback=-1.0)
        safe_audio = sanitize_audio_level_settings(
            self.audio_gain, self.audio_target_dbfs,
            self.audio_max_auto_gain, self.audio_limiter_ceiling_dbfs)
        self.audio_gain = str(safe_audio["gain_percent"])
        self.audio_target_dbfs = safe_audio["target_dbfs"]
        self.audio_max_auto_gain = safe_audio["max_auto_gain_percent"]
        self.audio_limiter_ceiling_dbfs = safe_audio[
            "limiter_ceiling_dbfs"]
        self.vision_mode = self.setting.get("Analysis", "vision_mode", fallback="default")
        self.image_assist_enabled = self.setting.getboolean("Analysis", "image_assist_enabled", fallback=False)
        self.image_assist_output = self.setting.get("Analysis", "image_assist_output", fallback="Output#2")
        self.image_assist_game_tag = self.setting.get("Analysis", "image_assist_game_tag", fallback="すべて")
        self.image_assist_console_tag = self.setting.get("Analysis", "image_assist_console_tag", fallback="すべて")
        self.image_assist_filter_mode = self.setting.get("Analysis", "image_assist_filter_mode", fallback="AND")
        self.image_assist_max_candidates = self.setting.get("Analysis", "image_assist_max_candidates", fallback="10")
        self.analysis_rules_enabled = self.setting.getboolean(
            "Analysis", "rules_enabled", fallback=True)
        self.analysis_rules = self.setting.get("Analysis", "rules", fallback="[]")
        self.pc_gamepad_input_enabled = self.setting.getboolean(
            "Analysis", "pc_gamepad_input_enabled", fallback=False)
        self.record_mode = self.setting.get("Recording", "mode", fallback="Manual")
        self.record_output_dir = self.setting.get("Recording", "output_dir", fallback="")
        self.record_template_path = self.setting.get("Recording", "template_path", fallback="")
        self.record_threshold = self.setting.get("Recording", "threshold", fallback="0.9")
        self.record_interval = self.setting.get("Recording", "interval", fallback="0.5")
        self.record_release = self.setting.get("Recording", "release_seconds", fallback="1.0")
        self.record_roi = self.setting.get("Recording", "roi", fallback="0,0,0,0")
        self.record_debug = self.setting.getboolean("Recording", "debug", fallback=False)
        self.record_trigger_rules = self.setting.get("Recording", "trigger_rules", fallback="[]")
        self.record_cleanup_rules = self.setting.get("Recording", "cleanup_rules", fallback="[]")
        self.record_minimum_duration = self.setting.get("Recording", "minimum_duration", fallback="0")
        self.record_min_free_gb = self.setting.getfloat("Recording", "min_free_gb", fallback=5.0)
        self.record_max_disk_usage_percent = self.setting.getfloat(
            "Recording", "max_disk_usage_percent", fallback=95.0)
        self.record_variable_command = self.setting.get("Recording", "variable_command", fallback="")
        self.record_variable_name = self.setting.get("Recording", "variable_name", fallback="current_step")
        self.record_variable_start = self.setting.get("Recording", "variable_start", fallback="")
        self.record_variable_stop = self.setting.get("Recording", "variable_stop", fallback="")
        self.record_variable_rules = self.setting.get("Recording", "variable_rules", fallback="[]")
        self.operation_capture_output_dir = self.setting.get(
            "Operation Capture", "output_dir", fallback="")
        self.operation_capture_include_audio = self.setting.getboolean(
            "Operation Capture", "include_audio", fallback=True)
        self.operation_capture_auto_controller = self.setting.getboolean(
            "Operation Capture", "auto_controller", fallback=True)
        self.operation_capture_gamepad_profile = self.setting.get(
            "Operation Capture", "gamepad_profile", fallback="")
        self.operation_capture_last_session = self.setting.get(
            "Operation Capture", "last_session", fallback="")
        self.area_capture_roi = self.setting.get("Area Capture", "roi", fallback="0,0,0,0")
        self.area_capture_output_target = self.setting.get("Area Capture", "output_target", fallback="Output#1")
        self.area_capture_background = self.setting.get("Area Capture", "background", fallback="#ffffff")
        self.area_capture_active = self.setting.getboolean("Area Capture", "active", fallback=True)
        self.area_capture_detection_scope = self.setting.get(
            "Area Capture", "detection_scope", fallback="取得範囲内")
        self.area_capture_detection_output = self.setting.get(
            "Area Capture", "detection_output", fallback="Output#2")
        self.area_capture_detection_roi = self.setting.get(
            "Area Capture", "detection_roi", fallback="0,0,0,0")
        self.area_capture_detection_threshold = self.setting.get(
            "Area Capture", "detection_threshold", fallback="0.85")
        self.area_capture_detection_gray = self.setting.getboolean(
            "Area Capture", "detection_gray", fallback=True)
        self.area_capture_match_color = self.setting.get(
            "Area Capture", "match_color", fallback="#00c853")
        self.area_capture_no_match_color = self.setting.get(
            "Area Capture", "no_match_color", fallback="#ff9800")
        self.command_watch_enabled = self.setting.getboolean("Command Watch", "enabled", fallback=False)
        self.command_watch_command = self.setting.get("Command Watch", "command", fallback="")
        self.command_watch_target = self.setting.get("Command Watch", "target", fallback="Output#1")
        self.command_watch_variables = self.setting.get("Command Watch", "variables", fallback="")
        self.commands_assist_enabled = self.setting.getboolean("Commands Assist", "enabled", fallback=False)
        self.commands_assist_recovery_command = self.setting.get(
            "Commands Assist", "recovery_command", fallback="")
        self.commands_assist_rules = self.setting.get("Commands Assist", "rules", fallback="[]")

    def load(self):
        if os.path.isfile(self.SETTING_PATH):
            self.setting.read(self.SETTING_PATH, encoding="utf-8")

    def generate(self):
        # logger.info('Create Default setting file.')
        # default
        self.setting["General Setting"] = {
            "camera_id": 0,
            "video_source": "Capture device",
            "window_capture_mode": "client",
            "window_title": "",
            "window_process": "",
            "com_port": 0,
            "com_port_name": "",
            "baud_rate": 9600,
            "fps": 45,
            "show_size": "640x360",
            "last_active_preview_full_fps": False,
            "is_show_realtime": True,
            "is_show_value": False,
            "is_show_guide": False,
            "is_show_serial": False,
            "is_use_keyboard": True,
            "serial_data_format_name": "Default",
            "touchscreen_start_x": 1,
            "touchscreen_start_y": 1,
            "touchscreen_end_x": 320,
            "touchscreen_end_y": 240,
        }
        # pokemon home用の設定
        self.setting["Pokemon Home"] = {
            "Season": 1,
            "Single or Double": "シングル",
        }
        # keyconfig
        self.setting["KeyMap-Button"] = {
            "Button.Y": "y",
            "Button.B": "b",
            "Button.X": "x",
            "Button.A": "a",
            "Button.L": "l",
            "Button.R": "r",
            "Button.ZL": "k",
            "Button.ZR": "e",
            "Button.MINUS": "m",
            "Button.PLUS": "p",
            "Button.LCLICK": "q",
            "Button.RCLICK": "w",
            "Button.HOME": "h",
            "Button.CAPTURE": "c",
        }
        self.setting["KeyMap-Direction"] = {
            "Direction.UP": "Key.up",
            "Direction.RIGHT": "Key.right",
            "Direction.DOWN": "Key.down",
            "Direction.LEFT": "Key.left",
            "Direction.UP_RIGHT": "20001",
            "Direction.DOWN_RIGHT": "20002",
            "Direction.DOWN_LEFT": "20010",
            "Direction.UP_LEFT": "20011",
        }
        self.setting["KeyMap-Hat"] = {
            "Hat.TOP": "10000",
            "Hat.TOP_RIGHT": "10001",
            "Hat.RIGHT": "10010",
            "Hat.BTM_RIGHT": "10011",
            "Hat.BTM": "10100",
            "Hat.BTM_LEFT": "10101",
            "Hat.LEFT": "10110",
            "Hat.TOP_LEFT": "10111",
            "Hat.CENTER": "11000",
        }
        self.setting["Shortcut"] = {
            "command_class_1": "None",
            "command_name_1": "(empty)",
            "command_class_2": "None",
            "command_name_2": "(empty)",
            "command_class_3": "None",
            "command_name_3": "(empty)",
            "command_class_4": "None",
            "command_name_4": "(empty)",
            "command_class_5": "None",
            "command_name_5": "(empty)",
            "command_class_6": "None",
            "command_name_6": "(empty)",
            "command_class_7": "None",
            "command_name_7": "(empty)",
            "command_class_8": "None",
            "command_name_8": "(empty)",
            "command_class_9": "None",
            "command_name_9": "(empty)",
            "command_class_10": "None",
            "command_name_10": "(empty)",
        }
        self.setting["Notification"] = {
            "is_win_notification_start": False,
            "is_win_notification_end": False,
            "is_line_notification_start": False,
            "is_line_notification_end": False,
            "is_discord_notification_start": False,
            "is_discord_notification_end": False,
        }
        self.setting["Output"] = {
            "area_size": "20",
            "stdout_destination": "1",
            "widget_mode": "ALL (default)",
            "software_controller_position": "2",
            "dialogue_buttons_position": "2",
            "panel_left_top": "Log: Output#3",
            "panel_left_bottom": "Log: Output#4",
            "panel_right_top": "Log: Output#1",
            "panel_right_bottom": "Log: Output#2",
            "panel_ratio": "50",
            "right_panel_ratio": "50",
            "panel_layout": "Four panels (left/right, top/bottom)",
            "panel_sides": "Both sides",
            "left_panel_count": "2",
            "right_panel_count": "2",
            "side_width_balance": "50",
            "show_software_controller": True,
        }
        self.setting["Audio"] = {
            "input_device": "", "gain": "100", "filter_camera": False,
            "auto_start": False, "auto_level": False,
            "target_dbfs": "-6.0", "max_auto_gain": "800",
            "limiter_ceiling_dbfs": "-1.0",
        }
        self.setting["Resource Control"] = {
            "enabled": True, "cpu_target": 90, "main_tool": False,
        }
        self.setting["Analysis"] = {
            "vision_mode": "default",
            "image_assist_enabled": False,
            "image_assist_output": "Output#2",
            "image_assist_game_tag": "すべて",
            "image_assist_console_tag": "すべて",
            "image_assist_filter_mode": "AND",
            "image_assist_max_candidates": "10",
            "rules_enabled": True,
            "rules": "[]",
            "pc_gamepad_input_enabled": False,
        }
        self.setting["Recording"] = {
            "mode": "Manual", "output_dir": "", "template_path": "", "threshold": "0.9",
            "interval": "0.5", "release_seconds": "1.0", "roi": "0,0,0,0", "debug": False,
            "trigger_rules": "[]", "cleanup_rules": "[]", "minimum_duration": "0",
            "min_free_gb": "5.0", "max_disk_usage_percent": "95.0",
            "variable_command": "", "variable_name": "current_step",
            "variable_start": "", "variable_stop": "", "variable_rules": "[]",
        }
        self.setting["Operation Capture"] = {
            "output_dir": "", "include_audio": True,
            "auto_controller": True, "gamepad_profile": "", "last_session": "",
        }
        self.setting["Area Capture"] = {
            "roi": "0,0,0,0", "output_target": "Output#1", "background": "#ffffff", "active": True,
            "detection_scope": "取得範囲内", "detection_output": "Output#2",
            "detection_roi": "0,0,0,0",
            "detection_threshold": "0.85", "detection_gray": True,
            "match_color": "#00c853", "no_match_color": "#ff9800",
        }
        self.setting["Command Watch"] = {"enabled": False, "command": "", "target": "Output#1", "variables": ""}
        self.setting["Commands Assist"] = {"enabled": False, "recovery_command": "", "rules": "[]"}
        with open(self.SETTING_PATH, "w", encoding="utf-8") as file:
            self.setting.write(file)
        os.chmod(path=self.SETTING_PATH, mode=0o777)

    def save(self, path=None):
        # Some preparations are needed because tkinter related objects are not serializable.

        self.setting["General Setting"] = {
            "camera_id": self.camera_id.get(),
            "video_source": self.video_source,
            "window_capture_mode": self.window_capture_mode,
            "window_title": self.window_title,
            "window_process": self.window_process,
            "com_port": self.com_port.get(),
            "com_port_name": self.com_port_name.get(),
            "baud_rate": self.baud_rate.get(),
            "fps": self.fps.get(),
            "show_size": self.show_size.get(),
            "last_active_preview_full_fps": self.last_active_preview_full_fps,
            "is_show_realtime": self.is_show_realtime.get(),
            "is_show_value": self.is_show_value.get(),
            "is_show_guide": self.is_show_guide.get(),
            "is_show_serial": self.is_show_serial.get(),
            "is_use_keyboard": self.is_use_keyboard.get(),
            "serial_data_format_name": self.serial_data_format_name.get(),
            "touchscreen_start_x": self.touchscreen_start_x,
            "touchscreen_start_y": self.touchscreen_start_y,
            "touchscreen_end_x": self.touchscreen_end_x,
            "touchscreen_end_y": self.touchscreen_end_y,
        }
        # pokemon home用の設定
        self.setting["Pokemon Home"] = {
            "Season": self.season.get(),
            "Single or Double": self.is_SingleBattle.get(),
        }

        # ショートカット用の設定
        self.setting["Shortcut"] = {
            "command_class_1": self.command_class_dict["1"],
            "command_name_1": self.command_name_dict["1"].get(),
            "command_class_2": self.command_class_dict["2"],
            "command_name_2": self.command_name_dict["2"].get(),
            "command_class_3": self.command_class_dict["3"],
            "command_name_3": self.command_name_dict["3"].get(),
            "command_class_4": self.command_class_dict["4"],
            "command_name_4": self.command_name_dict["4"].get(),
            "command_class_5": self.command_class_dict["5"],
            "command_name_5": self.command_name_dict["5"].get(),
            "command_class_6": self.command_class_dict["6"],
            "command_name_6": self.command_name_dict["6"].get(),
            "command_class_7": self.command_class_dict["7"],
            "command_name_7": self.command_name_dict["7"].get(),
            "command_class_8": self.command_class_dict["8"],
            "command_name_8": self.command_name_dict["8"].get(),
            "command_class_9": self.command_class_dict["9"],
            "command_name_9": self.command_name_dict["9"].get(),
            "command_class_10": self.command_class_dict["10"],
            "command_name_10": self.command_name_dict["10"].get(),
        }

        self.setting["Notification"] = {
            "is_win_notification_start": self.is_win_notification_start.get(),
            "is_win_notification_end": self.is_win_notification_end.get(),
            "is_line_notification_start": self.is_line_notification_start.get(),
            "is_line_notification_end": self.is_line_notification_end.get(),
            "is_discord_notification_start": self.is_discord_notification_start.get(),
            "is_discord_notification_end": self.is_discord_notification_end.get(),
        }

        self.setting["Output"] = {
            "area_size": self.area_size,
            "stdout_destination": self.stdout_destination,
            "widget_mode": self.right_frame_widget_mode,
            "software_controller_position": self.pos_software_controller,
            "dialogue_buttons_position": self.pos_dialogue_buttons,
            "panel_left_top": self.panel_left_top,
            "panel_left_bottom": self.panel_left_bottom,
            "panel_right_top": self.panel_right_top,
            "panel_right_bottom": self.panel_right_bottom,
            "panel_ratio": self.panel_ratio,
            "right_panel_ratio": self.right_panel_ratio,
            "panel_layout": self.panel_layout,
            "panel_sides": self.panel_sides,
            "left_panel_count": self.left_panel_count,
            "right_panel_count": self.right_panel_count,
            "side_width_balance": self.side_width_balance,
            "show_software_controller": self.show_software_controller,
        }
        self.setting["Audio"] = {
            "input_device": self.audio_input,
            "gain": self.audio_gain,
            "filter_camera": self.audio_filter_camera,
            "auto_start": self.audio_auto_start,
            "auto_level": self.audio_auto_level,
            "target_dbfs": self.audio_target_dbfs,
            "max_auto_gain": self.audio_max_auto_gain,
            "limiter_ceiling_dbfs": self.audio_limiter_ceiling_dbfs,
        }
        self.setting["Resource Control"] = {
            "enabled": self.resource_control_enabled,
            "cpu_target": self.resource_cpu_target,
            "main_tool": self.resource_main_tool,
        }
        self.setting["Analysis"] = {
            "vision_mode": self.vision_mode,
            "image_assist_enabled": self.image_assist_enabled,
            "image_assist_output": self.image_assist_output,
            "image_assist_game_tag": self.image_assist_game_tag,
            "image_assist_console_tag": self.image_assist_console_tag,
            "image_assist_filter_mode": self.image_assist_filter_mode,
            "image_assist_max_candidates": self.image_assist_max_candidates,
            "rules_enabled": self.analysis_rules_enabled,
            "rules": str(self.analysis_rules).replace("%", "%%"),
            "pc_gamepad_input_enabled": self.pc_gamepad_input_enabled,
        }
        self.setting["Recording"] = {
            "mode": self.record_mode,
            "output_dir": self.record_output_dir,
            "template_path": self.record_template_path,
            "threshold": self.record_threshold,
            "interval": self.record_interval,
            "release_seconds": self.record_release,
            "roi": self.record_roi,
            "debug": self.record_debug,
            "trigger_rules": self.record_trigger_rules,
            "cleanup_rules": self.record_cleanup_rules,
            "minimum_duration": self.record_minimum_duration,
            "min_free_gb": self.record_min_free_gb,
            "max_disk_usage_percent": self.record_max_disk_usage_percent,
            "variable_command": self.record_variable_command,
            "variable_name": self.record_variable_name,
            "variable_start": self.record_variable_start,
            "variable_stop": self.record_variable_stop,
            "variable_rules": self.record_variable_rules,
        }
        self.setting["Operation Capture"] = {
            "output_dir": self.operation_capture_output_dir,
            "include_audio": self.operation_capture_include_audio,
            "auto_controller": self.operation_capture_auto_controller,
            "gamepad_profile": self.operation_capture_gamepad_profile,
            "last_session": self.operation_capture_last_session,
        }
        self.setting["Area Capture"] = {
            "roi": self.area_capture_roi, "output_target": self.area_capture_output_target,
            "background": self.area_capture_background, "active": self.area_capture_active,
            "detection_scope": self.area_capture_detection_scope,
            "detection_output": self.area_capture_detection_output,
            "detection_roi": self.area_capture_detection_roi,
            "detection_threshold": self.area_capture_detection_threshold,
            "detection_gray": self.area_capture_detection_gray,
            "match_color": self.area_capture_match_color,
            "no_match_color": self.area_capture_no_match_color,
        }
        self.setting["Command Watch"] = {"enabled": self.command_watch_enabled, "command": self.command_watch_command,
                                         "target": self.command_watch_target, "variables": self.command_watch_variables}
        self.setting["Commands Assist"] = {
            "enabled": self.commands_assist_enabled,
            "recovery_command": self.commands_assist_recovery_command,
            "rules": self.commands_assist_rules,
        }

        target_path = path or self.SETTING_PATH
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as file:
            self.setting.write(file)
        os.chmod(path=target_path, mode=0o777)
        self._logger.debug("Settings file has been saved.")
