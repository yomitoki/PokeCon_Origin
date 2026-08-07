"""Definitions and persistence helpers for the log-side quick action bars."""

from __future__ import annotations

import json


POSITIONS = ("上", "下", "非表示")


# Targets are resolved lazily by Window.PokeControllerApp.  This keeps the
# registry independent from tkinter and makes saved action IDs stable even if
# the original tab layout changes.
ACTION_DEFINITIONS = (
    {"id": "commands.start_stop", "tab": "Commands", "label": "開始／停止", "kind": "button",
     "widget": "start_top_button"},
    {"id": "commands.pause_resume", "tab": "Commands", "label": "一時停止／再開", "kind": "button",
     "widget": "pause_button"},
    {"id": "commands.force_stop", "tab": "Commands", "label": "強制停止", "kind": "button",
     "widget": "force_stop_button"},
    {"id": "commands.reload", "tab": "Commands", "label": "Commands再読込", "kind": "button",
     "widget": "reload_command_button"},
    {"id": "commands.controller", "tab": "Commands", "label": "コントローラー", "kind": "button",
     "widget": "simplecon_top_button"},
    {"id": "commands.step_debug", "tab": "CommandsAssist", "label": "Stepデバッグ", "kind": "button",
     "command": "open_step_debug_assist"},
    {"id": "commands.assist_enabled", "tab": "CommandsAssist", "label": "処理アシスト", "kind": "check",
     "variable": "commands_assist_enabled", "command": "_reset_commands_assist_monitor"},
    {"id": "camera.capture", "tab": "Camera", "label": "画面保存", "kind": "button",
     "widget": "capture_button"},
    {"id": "camera.open_capture", "tab": "Camera", "label": "保存フォルダ", "kind": "button",
     "widget": "open_capture_button"},
    {"id": "camera.reload", "tab": "Camera", "label": "カメラ再読込", "kind": "button",
     "widget": "reload_button"},
    {"id": "camera.realtime", "tab": "Camera", "label": "リアルタイム表示", "kind": "check",
     "variable": "is_show_realtime"},
    {"id": "camera.show_value", "tab": "Camera", "label": "数値表示", "kind": "check",
     "variable": "is_show_value", "command": "mode_change_show_value"},
    {"id": "camera.show_guide", "tab": "Camera", "label": "ガイド表示", "kind": "check",
     "variable": "is_show_guide", "command": "mode_change_show_guide"},
    {"id": "recording.toggle", "tab": "Recording", "label": "録画開始／停止", "kind": "button",
     "widget": "record_button", "textvariable": "record_button_text"},
    {"id": "audio.start", "tab": "Audio", "label": "音声開始", "kind": "button",
     "widget": "audio_start_button"},
    {"id": "audio.stop", "tab": "Audio", "label": "音声停止", "kind": "button",
     "command": "stop_audio_monitor"},
    {"id": "analysis.image_assist", "tab": "Analysis", "label": "画像解析アシスト", "kind": "check",
     "variable": "image_assist_enabled", "command": "toggle_image_analysis_assist"},
    {"id": "analysis.rules_enabled", "tab": "Analysis", "label": "解析ルール有効", "kind": "check",
     "variable": "analysis_rules_enabled"},
    {"id": "analysis.settings", "tab": "Analysis", "label": "画像解析設定", "kind": "button",
     "command": "open_image_analysis_assist_settings"},
    {"id": "area.capture", "tab": "Area Capture", "label": "範囲を保存", "kind": "button",
     "command": "save_area_capture"},
    {"id": "area.preview", "tab": "Area Capture", "label": "範囲編集", "kind": "button",
     "command": "open_area_capture_editor"},
    {"id": "area.active", "tab": "Area Capture", "label": "範囲プレビュー", "kind": "check",
     "variable": "area_capture_active", "command": "toggle_area_capture_active"},
    {"id": "inputset.load", "tab": "InputSet", "label": "選択InputSet読込", "kind": "button",
     "command": "load_input_set"},
    {"id": "output.clear", "tab": "Other", "label": "全ログ消去", "kind": "button",
     "widget": "clear_top_button"},
    {"id": "output.software_controller", "tab": "Other", "label": "ソフトコントローラー", "kind": "check",
     "variable": "show_software_controller", "command": "apply_panel_assignment"},
    {"id": "watch.enabled", "tab": "Command Watch", "label": "変数監視", "kind": "check",
     "variable": "command_watch_enabled", "command": "reset_command_watch"},
    {"id": "notification.windows_start", "tab": "Notification", "label": "開始通知", "kind": "check",
     "variable": "is_win_notification_start", "command": "mode_change_notification"},
    {"id": "notification.windows_end", "tab": "Notification", "label": "終了通知", "kind": "check",
     "variable": "is_win_notification_end", "command": "mode_change_notification"},
)


ACTION_BY_ID = {item["id"]: item for item in ACTION_DEFINITIONS}


def normalize_position(value, default="上"):
    return value if value in POSITIONS else default


def normalize_action_ids(value):
    """Return unique, known IDs from a list or its JSON representation."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            value = []
    if not isinstance(value, (list, tuple)):
        return []
    result = []
    for action_id in value:
        if action_id in ACTION_BY_ID and action_id not in result:
            result.append(action_id)
    return result


def encode_action_ids(value):
    return json.dumps(normalize_action_ids(value), ensure_ascii=False)
