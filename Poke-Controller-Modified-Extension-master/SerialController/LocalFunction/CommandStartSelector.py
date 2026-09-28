#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portable ZA Story start-Step selector for the stock 0.1.9 host.

The enhanced PokeCon window owns its Commands run-settings dialog.  Stock
0.1.9 has no equivalent hook, so ``ZA_story`` can call this module from its
``start`` method, before ``PythonCommand.start`` creates the worker thread.

This module deliberately knows only the ZA Story state layout.  It does not
import the enhanced host's ``Window``, ``CommandRunOptions`` or
``CommandStartOverride`` modules, allowing the copied ``LocalFunction`` folder
to run unchanged on stock 0.1.9.
"""

from __future__ import annotations

import sys
import threading


PORTABLE_START_APPLY = "apply"
PORTABLE_START_DEFAULT = "default"
PORTABLE_START_CANCEL = "cancel"


# A Story child state has to be paired with the MAIN state that dispatches it.
# Keep this explicit: source inspection can choose the wrong parent when a
# helper state table is referenced by several Story functions.
_STORY_PARENT_BINDINGS = {
    "STATE_1_STORY_FUNCTION": (
        "_1_story_current_state_init", "MAIN_1_Z_LANK"),
    "STATE_2_STORY_FUNCTION": (
        "_2_story_current_state_init", "MAIN_2_Y_V_LANK"),
    "STATE_3_STORY_FUNCTION": (
        "_3_story_current_state_init", "MAIN_3_F_LANK"),
    "STATE_4_STORY_FUNCTION": (
        "_4_story_current_state_init", "MAIN_4_E_LANK"),
    "STATE_5_STORY_FUNCTION": (
        "_5_story_current_state_init", "MAIN_5_D_LANK"),
    "STATE_6_STORY_FUNCTION": (
        "_6_story_current_state_init", "MAIN_6_C_LANK"),
    "STATE_7_STORY_FUNCTION": (
        "_7_story_current_state_init", "MAIN_7_B_LANK"),
    "STATE_8_STORY_FUNCTION": (
        "_8_story_current_state_init", "MAIN_8_STORY_LAST"),
}


def portable_selector_required():
    """Return whether the running host needs the command-owned selector.

    ``Window.py`` is normally executed as ``__main__``.  Looking only for a
    module named ``Window`` can therefore import a second copy of the GUI and
    cause circular imports.  Inspect already loaded modules only.
    """

    host_classes = []
    for module_name in ("__main__", "Window"):
        module = sys.modules.get(module_name)
        app_class = getattr(module, "PokeControllerApp", None)
        if app_class is not None and app_class not in host_classes:
            host_classes.append(app_class)
    return not any(
        callable(getattr(app_class, "_prompt_command_run_settings", None))
        for app_class in host_classes
    )


def discover_story_locations(command):
    """Return selectable MAIN and chapter Story states in execution order.

    Common helper, ZA_INFI internal, bench, battle and quasar state tables are
    intentionally excluded.  They do not have an unambiguous standalone Story
    parent and selecting one directly can corrupt the dispatch dictionary.
    """

    locations = []
    labels = getattr(command, "COMMAND_STEP_LABELS", {})
    descriptions = getattr(command, "COMMAND_STEP_DESCRIPTIONS", {})
    if not isinstance(labels, dict):
        labels = {}
    if not isinstance(descriptions, dict):
        descriptions = {}
    table_names = ["STATE_MAIN_FUNCTION"] + [
        "STATE_{}_STORY_FUNCTION".format(chapter)
        for chapter in range(1, 9)
    ]
    for table_name in table_names:
        table = getattr(command, table_name, None)
        if not isinstance(table, dict):
            continue
        group = "MAIN" if table_name == "STATE_MAIN_FUNCTION" else (
            table_name[len("STATE_"):-len("_FUNCTION")])
        for order, state in enumerate(table):
            if not isinstance(state, str):
                continue
            locations.append({
                "id": "{}:{}".format(table_name, state),
                "variable": table_name,
                "state": state,
                "value": state,
                "label": str(labels.get(state, state)),
                "description": str(descriptions.get(state, "")),
                "group": group,
                "order": order,
            })
    return locations


def apply_story_start(command, variable, state):
    """Apply a selected ZA Story state to a freshly constructed command.

    Returns a compact assignment list for logging and tests.  The command is
    always routed through ``MAIN_STATE_INIT`` so the existing ZA initialization
    path copies the selected chapter's ``*_current_state_init`` value into its
    active state.
    """

    variable = str(variable or "").strip()
    state = str(state or "").strip()
    table = getattr(command, variable, None)
    if not isinstance(table, dict):
        raise ValueError(
            "状態変数「{}」がZA_storyにありません。".format(variable))
    if state not in table:
        raise ValueError(
            "Step「{}」が{}にありません。".format(state, variable))
    if variable != "STATE_MAIN_FUNCTION" and variable not in _STORY_PARENT_BINDINGS:
        raise ValueError(
            "単独開始できないZA内部Stateです: {}".format(variable))
    if not hasattr(command, "main_current_state_init"):
        raise AttributeError("ZA_storyにmain_current_state_initがありません。")

    assignments = []
    if hasattr(command, "main_current_state"):
        command.main_current_state = "MAIN_STATE_INIT"
        assignments.append({
            "attribute": "main_current_state",
            "value": "MAIN_STATE_INIT",
        })

    if variable == "STATE_MAIN_FUNCTION":
        # MAIN_STATE_INIT with itself as its requested return value never
        # advances.  Treat selecting it as the normal story entry instead.
        main_init = "" if state == "MAIN_STATE_INIT" else state
        command.main_current_state_init = main_init
        assignments.append({
            "attribute": "main_current_state_init",
            "value": main_init,
        })
        return assignments

    child_init_attribute, parent_state = _STORY_PARENT_BINDINGS[variable]
    if not hasattr(command, child_init_attribute):
        raise AttributeError(
            "ZA_storyに{}がありません。".format(child_init_attribute))
    main_table = getattr(command, "STATE_MAIN_FUNCTION", None)
    if not isinstance(main_table, dict) or parent_state not in main_table:
        raise ValueError(
            "親Step「{}」がSTATE_MAIN_FUNCTIONにありません。".format(
                parent_state))

    setattr(command, child_init_attribute, state)
    command.main_current_state_init = parent_state
    assignments.extend((
        {"attribute": child_init_attribute, "value": state},
        {"attribute": "main_current_state_init", "value": parent_state},
    ))
    return assignments


def _dialog_parent(command):
    gui = getattr(command, "gui", None)
    if gui is None:
        return None
    try:
        parent = gui.winfo_toplevel()
        if not bool(parent.winfo_exists()):
            return None
        return parent
    except Exception:
        return None


def show_portable_start_dialog(command):
    """Show the stock-host ZA Step selector and return the chosen action.

    The caller must invoke this before it calls ``super().start``.  If no Tk
    GUI is available, or this is accidentally called outside the GUI thread,
    the function safely returns ``"cancel"`` and leaves the command intact.
    Selecting a Step applies it before returning ``"apply"``.
    """

    if not portable_selector_required():
        return PORTABLE_START_DEFAULT
    if threading.current_thread() is not threading.main_thread():
        print(
            "[ZA_PORTABLE_START] GUIスレッド外のため開始を中止します。")
        return PORTABLE_START_CANCEL

    parent = _dialog_parent(command)
    if parent is None:
        print(
            "[ZA_PORTABLE_START] GUI親画面を取得できないため開始を中止します。")
        return PORTABLE_START_CANCEL
    locations = discover_story_locations(command)
    if not locations:
        print(
            "[ZA_PORTABLE_START] Story Stepがないため開始を中止します。")
        return PORTABLE_START_CANCEL

    dialog = None
    try:
        import tkinter as tk
        from tkinter import messagebox
        from tkinter import ttk

        result = {"action": PORTABLE_START_CANCEL}
        dialog = tk.Toplevel(parent)
        dialog.title("ZA_story - Step実行設定")
        dialog.geometry("860x280")
        dialog.minsize(720, 250)
        dialog.transient(parent)

        search = tk.StringVar(value="")
        group = tk.StringVar(value="すべて")
        selected = tk.StringVar(value="")
        status = tk.StringVar(value="")
        visible_locations = []

        groups = ["すべて"]
        for item in locations:
            item_group = item["group"]
            if item_group not in groups:
                groups.append(item_group)

        ttk.Label(
            dialog,
            text="Startが押されました。実行を開始するStepを選択してください。",
            foreground="#174a7e",
        ).pack(anchor="w", padx=12, pady=(12, 6))

        filter_frame = ttk.Labelframe(dialog, text="検索・章フィルター")
        filter_frame.pack(fill="x", padx=12, pady=5)
        ttk.Label(filter_frame, text="文字検索:").grid(
            column=0, row=0, padx=5, pady=6, sticky="e")
        search_entry = ttk.Entry(filter_frame, textvariable=search)
        search_entry.grid(column=1, row=0, padx=5, pady=6, sticky="ew")
        ttk.Label(filter_frame, text="章:").grid(
            column=2, row=0, padx=5, pady=6, sticky="e")
        group_combo = ttk.Combobox(
            filter_frame, state="readonly", textvariable=group,
            values=groups, width=22)
        group_combo.grid(column=3, row=0, padx=5, pady=6, sticky="ew")
        ttk.Label(filter_frame, textvariable=status).grid(
            column=4, row=0, padx=7, pady=6, sticky="w")
        filter_frame.columnconfigure(1, weight=1)

        selection_frame = ttk.Labelframe(dialog, text="開始Step")
        selection_frame.pack(fill="x", padx=12, pady=5)
        step_combo = ttk.Combobox(
            selection_frame, state="readonly", textvariable=selected,
            width=88)
        step_combo.pack(fill="x", expand=True, padx=7, pady=8)

        def display(item):
            if item["label"] == item["state"]:
                return "{}  [{}]".format(item["state"], item["group"])
            return "{}  ({})  [{}]".format(
                item["label"], item["state"], item["group"])

        def refresh_filter(*_args):
            del visible_locations[:]
            needle = search.get().strip().casefold()
            selected_group = group.get()
            for item in locations:
                if (selected_group != "すべて"
                        and item["group"] != selected_group):
                    continue
                haystack = "{} {} {} {} {}".format(
                    item["label"], item["state"], item["description"],
                    item["variable"], item["group"])
                if needle and needle not in haystack.casefold():
                    continue
                visible_locations.append(item)
            values = [display(item) for item in visible_locations]
            step_combo.configure(
                values=values, state="readonly" if values else "disabled")
            if selected.get() not in values:
                # MAIN_0_START is a safer initial selection than the dispatcher
                # state MAIN_STATE_INIT.  Fall back to the first visible row.
                preferred = next(
                    (display(item) for item in visible_locations
                     if item["state"] == "MAIN_0_START"), "")
                selected.set(preferred or (values[0] if values else ""))
            status.set("{} / {}件".format(len(values), len(locations)))

        def close(action):
            result["action"] = action
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.destroy()

        def start_selected():
            chosen = next(
                (item for item in visible_locations
                 if display(item) == selected.get()), None)
            if chosen is None:
                messagebox.showwarning(
                    "ZA_story Step実行設定",
                    "開始Stepを選択してください。", parent=dialog)
                return
            try:
                assignments = apply_story_start(
                    command, chosen["variable"], chosen["state"])
            except (AttributeError, TypeError, ValueError) as error:
                messagebox.showerror(
                    "ZA_story Step実行設定",
                    "開始位置を設定できませんでした。\n{}".format(error),
                    parent=dialog)
                return
            print(
                "[ZA_PORTABLE_START] {} :: {} / {}".format(
                    chosen["variable"], chosen["state"], assignments))
            close(PORTABLE_START_APPLY)

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=12, pady=(8, 12))
        ttk.Button(
            buttons, text="開始をやめる",
            command=lambda: close(PORTABLE_START_CANCEL)).pack(
                side="right", padx=4)
        ttk.Button(
            buttons, text="Commands既定で開始",
            command=lambda: close(PORTABLE_START_DEFAULT)).pack(
                side="right", padx=4)
        ttk.Button(
            buttons, text="選択Stepから開始",
            command=start_selected).pack(side="right", padx=4)

        search.trace_add("write", refresh_filter)
        group_combo.bind("<<ComboboxSelected>>", refresh_filter)
        dialog.protocol(
            "WM_DELETE_WINDOW", lambda: close(PORTABLE_START_CANCEL))
        refresh_filter()
        dialog.update_idletasks()
        dialog.grab_set()
        dialog.lift()
        search_entry.focus_set()
        parent.wait_window(dialog)
        return result["action"]
    except Exception as error:
        if dialog is not None:
            try:
                dialog.destroy()
            except Exception:
                pass
        # Wrong-Step execution is more harmful than declining a Start when a
        # stock installation is headless or has a non-Tk preview.
        print(
            "[ZA_PORTABLE_START] 選択画面を表示できないため"
            "開始を中止します: {}".format(error))
        return PORTABLE_START_CANCEL


__all__ = [
    "PORTABLE_START_APPLY",
    "PORTABLE_START_DEFAULT",
    "PORTABLE_START_CANCEL",
    "portable_selector_required",
    "show_portable_start_dialog",
    "apply_story_start",
    "discover_story_locations",
]
