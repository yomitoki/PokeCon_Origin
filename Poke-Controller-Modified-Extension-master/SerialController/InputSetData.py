"""Schema helpers for complete, per-InputSet GUI snapshots."""

from __future__ import annotations

import copy


SCHEMA_VERSION = 7


COMMAND_INPUT_SET_VARIABLES = frozenset((
    "show_python_samples", "command_filter_py_name",
    "command_filter_sample_py_name", "command_filter_mcu_name",
    "image_match_debug_command", "image_match_debug_output",
    "command_watch_enabled", "command_watch_command", "command_watch_target",
    "step_debug_skip_confirm",
    "operation_capture_output_dir", "operation_capture_include_audio",
    "operation_capture_auto_controller", "operation_gamepad_profile_name",
    "operation_capture_last_session",
))


def input_set_commands_enabled(item, legacy_default=True):
    """Return the explicit per-InputSet Commands usage flag.

    Old InputSets did not have this choice.  They keep their former behaviour
    until the user saves them with the new checkbox, avoiding silent loss of
    existing command/debug drafts.
    """
    if not isinstance(item, dict):
        return bool(legacy_default)
    commands = item.get("commands")
    if isinstance(commands, dict) and isinstance(commands.get("enabled"), bool):
        return commands["enabled"]
    return bool(legacy_default)


def strip_commands_from_snapshot(snapshot):
    """Copy an all-tab snapshot while removing Commands/debug ownership."""
    result = copy.deepcopy(snapshot) if isinstance(snapshot, dict) else {}
    result["commands_enabled"] = False
    for key in ("command_selection", "shortcuts", "commands_assist",
                "command_watch_variables", "controller_recordings",
                "operation_capture"):
        result.pop(key, None)
    values = result.get("values")
    if isinstance(values, dict):
        for name in COMMAND_INPUT_SET_VARIABLES:
            values.pop(name, None)
    quick = result.get("quick_actions")
    if isinstance(quick, dict):
        for side in ("left", "right"):
            config = quick.get(side)
            if not isinstance(config, dict):
                continue
            config["items"] = [
                action_id for action_id in config.get("items", [])
                if not str(action_id).startswith(("commands.", "watch."))
            ]
    return result


# Persist user choices only. Status text, active recording state, dialog
# fields and discovered hardware labels are excluded. Manual Control's
# explicitly selected enabled/permission state belongs to each InputSet.
INPUT_SET_VARIABLES = (
    # Camera / display
    "is_show_realtime", "is_show_value", "is_show_guide", "is_show_serial",
    "fps", "show_size", "video_source", "window_capture_mode",
    "last_active_preview_full_fps", "camera_feature_limited",
    # Multi-instance resource control
    "resource_control_enabled", "resource_cpu_target", "resource_main_tool",
    # Audio
    "audio_input", "audio_gain", "audio_filter_camera", "audio_auto_start",
    "audio_monitor_mode", "audio_auto_level", "audio_target_dbfs",
    "audio_max_auto_gain", "audio_limiter_ceiling_dbfs",
    # Serial / Manual Control
    "serial_data_format_name", "is_use_keyboard",
    "is_use_left_stick_mouse", "is_use_right_stick_mouse",
    "pc_gamepad", "is_record_Pro_Controller", "is_use_Pro_Controller",
    "pc_gamepad_input_enabled",
    # Analysis
    "vision_mode", "image_assist_enabled", "image_assist_output",
    "image_assist_game_tag", "image_assist_console_tag", "image_assist_filter_mode",
    "image_assist_max_candidates", "analysis_rules_enabled",
    "image_detection_monitor_search", "image_detection_monitor_target",
    "image_detection_monitor_variant", "image_detection_monitor_enabled",
    "image_detection_monitor_interval", "image_detection_monitor_output",
    "image_detection_monitor_output_tag", "image_detection_monitor_value_timeout",
    "object_detection_roi", "object_detection_threshold", "object_detection_scale_variation",
    # Recording
    "record_mode", "record_output_dir", "record_template_path", "record_threshold",
    "record_interval", "record_release", "record_roi", "record_debug",
    "record_minimum_duration", "record_min_free_gb", "record_max_disk_usage_percent",
    "record_output_mode", "record_output_logs", "record_output_guide",
    "record_output_value", "record_output_detection",
    "record_monitor_chunk_seconds", "record_monitor_keep_steps",
    "record_monitor_loop_cycles", "record_monitor_long_seconds",
    "record_monitor_failure_tail_seconds",
    "record_monitor_auto_arm", "record_monitor_confirm_delete_on_stop",
    # Long-form PC-controller + video authoring session
    "operation_capture_output_dir", "operation_capture_include_audio",
    "operation_capture_auto_controller", "operation_gamepad_profile_name",
    "operation_capture_last_session",
    # Area Capture
    "area_capture_roi", "area_capture_output_target", "area_capture_step",
    "area_capture_background", "area_capture_active", "area_capture_detection_scope",
    "area_capture_detection_output", "area_capture_detection_roi",
    "area_capture_detection_threshold", "area_capture_detection_gray",
    "area_capture_match_color", "area_capture_no_match_color",
    # Commands / Command Watch
    "show_python_samples", "command_filter_py_name", "command_filter_sample_py_name",
    "command_filter_mcu_name", "image_match_debug_command", "image_match_debug_output",
    "command_watch_enabled", "command_watch_command", "command_watch_target",
    "step_debug_skip_confirm",
    # Notification
    "is_win_notification_start", "is_win_notification_end",
    "is_line_notification_start", "is_line_notification_end",
    "is_discord_notification_start", "is_discord_notification_end",
    # Other / output layout
    "stdout_destination", "right_frame_widget_mode", "panel_layout", "panel_sides",
    "left_panel_count", "right_panel_count", "side_width_balance",
    "panel_ratio", "right_panel_ratio", "area_size", "show_software_controller",
    "pos_software_controller", "pos_dialogue_buttons",
)


OUTPUT_LAYOUT_VARIABLES = frozenset((
    "side_width_balance", "panel_ratio", "right_panel_ratio",
))


RESOURCE_INPUT_SET_DEFAULTS = {
    "resource_control_enabled": True,
    "resource_cpu_target": 90,
    "resource_main_tool": False,
}


def snapshot_values_with_defaults(snapshot):
    """Return stored tab values without inheriting another InputSet's state.

    Resource control was added after complete InputSet snapshots existed.  A
    missing Resource key must therefore use a safe per-set default instead of
    leaving the previously loaded InputSet's Tk variable unchanged.
    """
    values = snapshot.get("values", {}) if isinstance(snapshot, dict) else {}
    result = copy.deepcopy(values) if isinstance(values, dict) else {}
    for name, value in RESOURCE_INPUT_SET_DEFAULTS.items():
        result.setdefault(name, value)
    # A legacy InputSet must not inherit the previously loaded InputSet's
    # feature-limited Camera mode.
    result.setdefault("camera_feature_limited", False)
    return result


def has_complete_snapshot(input_set):
    return isinstance(input_set, dict) and isinstance(input_set.get("all_tabs"), dict)


def legacy_combined_snapshot(input_set, combined_set):
    """Use old combined settings only when the referenced InputSet is legacy."""
    if has_complete_snapshot(input_set) or not isinstance(combined_set, dict):
        return {}
    snapshot = combined_set.get("all_tabs")
    return snapshot if isinstance(snapshot, dict) else {}


def sync_step_debug_rules(data, input_set_name, rules):
    """Mirror saved Step-debug drafts into both schema-3 storage locations."""
    if not isinstance(data, dict) or not input_set_name:
        return False
    item = data.get("input_sets", {}).get(input_set_name)
    if not isinstance(item, dict):
        return False
    if not input_set_commands_enabled(item):
        return False
    saved = copy.deepcopy(list(rules or []))
    item.setdefault("commands_assist", {})["step_debug_rules"] = saved
    # Do not create all_tabs on a legacy InputSet: its presence is the schema-3
    # discriminator.  Newly saved schema-3 sets already own this dictionary.
    if isinstance(item.get("all_tabs"), dict):
        item["all_tabs"].setdefault(
            "commands_assist", {})["step_debug_rules"] = copy.deepcopy(saved)
    return True


def sync_commands_assist_rules(data, input_set_name, rules):
    """Continuously save runtime/function replacement mappings."""
    if not isinstance(data, dict) or not input_set_name:
        return False
    item = data.get("input_sets", {}).get(input_set_name)
    if not isinstance(item, dict):
        return False
    if not input_set_commands_enabled(item):
        return False
    saved = copy.deepcopy(list(rules or []))
    item.setdefault("commands_assist", {})["rules"] = saved
    if isinstance(item.get("all_tabs"), dict):
        item["all_tabs"].setdefault("commands_assist", {})["rules"] = copy.deepcopy(saved)
    return True


def sync_quick_actions(data, input_set_name, snapshot):
    """Continuously save quick-action placement into the loaded InputSet."""
    if not isinstance(data, dict) or not input_set_name or not isinstance(snapshot, dict):
        return False
    item = data.get("input_sets", {}).get(input_set_name)
    if not isinstance(item, dict):
        return False
    saved = copy.deepcopy(snapshot)
    if not input_set_commands_enabled(item):
        wrapper = strip_commands_from_snapshot({"quick_actions": saved})
        saved = wrapper.get("quick_actions", saved)
    if isinstance(item.get("all_tabs"), dict):
        item["all_tabs"]["quick_actions"] = saved
    else:
        # Preserve the legacy/new-format discriminator exactly as the Step
        # debug sync does. Legacy loading already supports this top-level key.
        item["quick_actions"] = saved
    return True


def sync_output_layout(data, input_set_name, values):
    """Continuously save the log-boundary sliders into the loaded InputSet."""
    if not isinstance(data, dict) or not input_set_name or not isinstance(values, dict):
        return False
    item = data.get("input_sets", {}).get(input_set_name)
    if not isinstance(item, dict) or not isinstance(item.get("all_tabs"), dict):
        return False
    saved_values = item["all_tabs"].setdefault("values", {})
    if not isinstance(saved_values, dict):
        return False
    for name in OUTPUT_LAYOUT_VARIABLES:
        if name in values:
            saved_values[name] = copy.deepcopy(values[name])
    return True


def sync_command_start_overrides(data, input_set_name, overrides, favorites=None):
    """Save Commands run ranges/favorites separately from Step-debug rules."""
    if not isinstance(data, dict) or not input_set_name or not isinstance(overrides, dict):
        return False
    item = data.get("input_sets", {}).get(input_set_name)
    if not isinstance(item, dict):
        return False
    if not input_set_commands_enabled(item):
        return False
    saved = copy.deepcopy(overrides)
    item.setdefault("commands_assist", {})["start_overrides"] = saved
    if isinstance(item.get("all_tabs"), dict):
        item["all_tabs"].setdefault("commands_assist", {})["start_overrides"] = copy.deepcopy(saved)
    if isinstance(favorites, dict):
        saved_favorites = copy.deepcopy(favorites)
        item.setdefault("commands_assist", {})["run_favorites"] = saved_favorites
        if isinstance(item.get("all_tabs"), dict):
            item["all_tabs"].setdefault(
                "commands_assist", {})["run_favorites"] = copy.deepcopy(
                    saved_favorites)
    return True


def sync_command_recovery_scripts(data, input_set_name, favorites,
                                  auto_open=True):
    """Continuously save recovery snippets into the active Commands InputSet."""
    if (not isinstance(data, dict) or not input_set_name
            or not isinstance(favorites, list)):
        return False
    item = data.get("input_sets", {}).get(input_set_name)
    if not isinstance(item, dict) or not input_set_commands_enabled(item):
        return False
    saved = copy.deepcopy(favorites)
    top = item.setdefault("commands_assist", {})
    top["recovery_scripts"] = saved
    top["recovery_auto_open"] = bool(auto_open)
    if isinstance(item.get("all_tabs"), dict):
        tab = item["all_tabs"].setdefault("commands_assist", {})
        tab["recovery_scripts"] = copy.deepcopy(saved)
        tab["recovery_auto_open"] = bool(auto_open)
    return True
