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
    {"id": "commands.debug_capture", "tab": "Commands", "label": "画像＋判定保存", "kind": "button",
     "command": "capture_command_debug_evidence"},
    {"id": "commands.debug_retest", "tab": "Commands", "label": "同Step再試験", "kind": "button",
     "command": "retest_current_command_step"},
    {"id": "commands.debug_stop", "tab": "Commands", "label": "調整入力を中断", "kind": "button",
     "command": "stop_command_debug_tools"},
    {"id": "commands.debug_restart", "tab": "Commands", "label": "このPokeConを再起動（許可時のみ）", "kind": "button",
     "command": "restart_pokecon_same_settings"},
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
    {"id": "output.discord", "tab": "Other", "label": "Discord", "kind": "button",
     "widget": "discord_button"},
    {"id": "output.html", "tab": "Other", "label": "Open HTML", "kind": "button",
     "widget": "html_button"},
    {"id": "camera.keep_preview_fps", "tab": "Camera", "label": "表示60FPS維持（1つだけ）", "kind": "check",
     "widget": "keep_preview_fps_checkbox", "variable": "last_active_preview_full_fps",
     "command": "_resource_main_changed"},
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


# This is a fixed proxy group, not a rewrite of the user's saved quick items.
# Keeping original widget targets also retains Start/Stop state and safety
# checks owned by the existing callbacks.
MAIN_PANEL_ACTION_IDS = (
    "commands.start_stop", "commands.controller", "output.clear",
    "camera.capture", "camera.open_capture", "output.discord", "output.html",
    "camera.keep_preview_fps",
)


def normalize_main_panel_controls(value):
    """A missing/invalid old snapshot must not opt into the compact layout."""
    return value is True


def main_panel_controls_layout(enabled, feature_limited, show_right, right_position):
    """Return layout decisions without changing the saved side preferences."""
    enabled = normalize_main_panel_controls(enabled)
    right_position = normalize_position(right_position)
    return {
        "show_header": not feature_limited and not enabled,
        "show_fixed_actions": enabled and not feature_limited,
        "show_right_host": bool(show_right or enabled),
        "right_quick_position": "上" if enabled else normalize_position(right_position),
        "show_right_user_actions": bool(show_right and right_position != "非表示"),
    }


def compact_log_height_budget(preview_height, tool_height, enabled):
    """Fit compact right-side tools/logs beside, not below, the preview.

    The ordinary layout retains its historical budget. Only the compact
    right column subtracts fixed tools; user ratios are applied afterwards.
    """
    total = max(240, int(preview_height))
    if not normalize_main_panel_controls(enabled):
        return total
    return max(80, total - max(0, int(tool_height)))


def compact_log_panel_heights(height_budget, ratio):
    """Keep two logs within their budget without changing the saved ratio."""
    total = max(80, int(height_budget))
    top = max(40, min(total - 40, int(total * float(ratio) / 100)))
    return top, total - top


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
