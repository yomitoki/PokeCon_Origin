#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operation-recording gamepad profiles and live teaching UI."""
from __future__ import annotations

import json
import os
import queue
import threading
import uuid

import tkinter as tk
import tkinter.messagebox as tkmsg
import tkinter.simpledialog as simpledialog
import tkinter.ttk as ttk


SCHEMA_VERSION = 1
CONTROL_ORDER = (
    "ZL", "L", "MINUS", "LCLICK", "DPAD_UP", "DPAD_LEFT",
    "DPAD_RIGHT", "DPAD_DOWN", "CAPTURE", "ZR", "R", "PLUS",
    "RCLICK", "X", "Y", "A", "B", "HOME",
)
CONTROL_LABELS = {
    "DPAD_UP": "十字 上", "DPAD_LEFT": "十字 左",
    "DPAD_RIGHT": "十字 右", "DPAD_DOWN": "十字 下",
    "LCLICK": "L Stick押込", "RCLICK": "R Stick押込",
}
DEFAULT_MAPPING = {
    "A": "button:0", "B": "button:1", "X": "button:2", "Y": "button:3",
    "MINUS": "button:4", "HOME": "", "PLUS": "button:6",
    "LCLICK": "button:7", "RCLICK": "button:8", "L": "button:9",
    "R": "button:10", "DPAD_UP": "dpad:up", "DPAD_DOWN": "dpad:down",
    "DPAD_LEFT": "dpad:left", "DPAD_RIGHT": "dpad:right",
    "CAPTURE": "button:15", "ZL": "axis:4+", "ZR": "axis:5+",
}
DPAD_ALIASES = {
    "button:11": "dpad:up", "button:12": "dpad:down",
    "button:13": "dpad:left", "button:14": "dpad:right",
    "hat:up": "dpad:up", "hat:down": "dpad:down",
    "hat:left": "dpad:left", "hat:right": "dpad:right",
}


def normalize_gamepad_mapping(mapping):
    source = mapping if isinstance(mapping, dict) else {}
    return {control: str(source.get(control, "") or "").strip()
            for control in CONTROL_ORDER}


def controls_for_token(mapping, token):
    token = str(token or "")
    alias = DPAD_ALIASES.get(token, token)
    return {control for control, source in normalize_gamepad_mapping(mapping).items()
            if source and (source == token or source == alias)}


def gamepad_axis_token(index, value, baseline=0.0, threshold=0.5):
    """Return a teachable token for either direction of any analog axis."""
    delta = float(value) - float(baseline)
    if delta >= float(threshold):
        return "axis:{}+".format(int(index))
    if delta <= -float(threshold):
        return "axis:{}-".format(int(index))
    return ""


def opposite_axis_tokens(first, second):
    first, second = str(first or ""), str(second or "")
    return (first.startswith("axis:") and second.startswith("axis:")
            and first[:-1] == second[:-1] and first[-1:] != second[-1:])


class OperationGamepadProfileStore:
    def __init__(self, path):
        self.path = os.path.abspath(path)

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as stream:
                value = json.load(stream)
        except (OSError, ValueError):
            value = {}
        profiles = value.get("profiles", {}) if isinstance(value, dict) else {}
        normalized = {}
        if isinstance(profiles, dict):
            for name, item in profiles.items():
                if str(name).strip():
                    mapping = item.get("mapping", item) if isinstance(item, dict) else {}
                    normalized[str(name).strip()] = {
                        "mapping": normalize_gamepad_mapping(mapping)}
        if not normalized:
            normalized = {"Default": {"mapping": normalize_gamepad_mapping(DEFAULT_MAPPING)}}
        selected = str(value.get("selected", "") if isinstance(value, dict) else "")
        if selected not in normalized:
            selected = sorted(normalized, key=str.casefold)[0]
        return {"schema_version": SCHEMA_VERSION, "selected": selected,
                "profiles": normalized}

    def save(self, value):
        profiles = {}
        for name, item in (value.get("profiles", {}) or {}).items():
            name = str(name).strip()
            if name:
                mapping = item.get("mapping", item) if isinstance(item, dict) else {}
                profiles[name] = {"mapping": normalize_gamepad_mapping(mapping)}
        if not profiles:
            profiles["Default"] = {"mapping": normalize_gamepad_mapping(DEFAULT_MAPPING)}
        selected = str(value.get("selected", "") or "")
        if selected not in profiles:
            selected = sorted(profiles, key=str.casefold)[0]
        payload = {"schema_version": SCHEMA_VERSION, "selected": selected,
                   "profiles": profiles}
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        temporary = self.path + ".tmp-" + uuid.uuid4().hex
        try:
            with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary, self.path)
        finally:
            try:
                if os.path.exists(temporary):
                    os.remove(temporary)
            except OSError:
                pass
        return payload

    def select(self, name):
        value = self.load()
        if name in value["profiles"]:
            value["selected"] = name
        return self.save(value)


class GamepadTeachMonitor:
    """Read raw gamepad controls without forwarding anything to Serial."""
    def __init__(self, joystick_index, callback):
        self.joystick_index = max(0, int(joystick_index))
        self.callback = callback
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread is not None:
            return
        self.thread = threading.Thread(target=self._run, daemon=True,
                                       name="GamepadMappingMonitor")
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self):
        import pygame
        try:
            pygame.init()
            if pygame.joystick.get_count() <= self.joystick_index:
                return
            joystick = pygame.joystick.Joystick(self.joystick_index)
            joystick.init()
            instance_id = int(joystick.get_instance_id()) \
                if hasattr(joystick, "get_instance_id") else None
            # SDL/XInput axes can initially report 0 and settle at -1 for an
            # untouched trigger. Pump briefly before freezing the rest values.
            warmup_clock = pygame.time.Clock()
            baselines = {}
            for _sample in range(24):
                pygame.event.pump()
                baselines = {index: float(joystick.get_axis(index))
                             for index in range(joystick.get_numaxes())}
                warmup_clock.tick(120)
            button_states = {index: bool(joystick.get_button(index))
                             for index in range(joystick.get_numbuttons())}
            hat_states = {index: tuple(joystick.get_hat(index))
                          for index in range(joystick.get_numhats())}
            active_axes = {}
            suppressed_axes = {}
            clock = pygame.time.Clock()
            while not self.stop_event.is_set():
                for event in pygame.event.get():
                    if (hasattr(event, "instance_id") and instance_id is not None
                            and int(event.instance_id) != instance_id):
                        continue
                    if (not hasattr(event, "instance_id") and hasattr(event, "joy")
                            and int(event.joy) != self.joystick_index):
                        continue
                    if event.type == pygame.JOYAXISMOTION:
                        index = int(event.axis)
                        previous = active_axes.get(index, "")
                        current = gamepad_axis_token(
                            index, event.value, baselines.get(index, 0.0))
                        if previous and previous != current:
                            self.callback(previous, False)
                            if opposite_axis_tokens(previous, current):
                                suppressed_axes[index] = current
                        if not current:
                            suppressed_axes.pop(index, None)
                        elif (index in suppressed_axes
                              and current != suppressed_axes[index]):
                            suppressed_axes.pop(index, None)
                        if current == suppressed_axes.get(index):
                            current = ""
                        if current and current != previous:
                            self.callback(current, True)
                        if current:
                            active_axes[index] = current
                        else:
                            active_axes.pop(index, None)
                for index in range(joystick.get_numbuttons()):
                    current = bool(joystick.get_button(index))
                    previous = button_states.get(index, current)
                    if current != previous:
                        self.callback("button:{}".format(index), current)
                    button_states[index] = current
                for index in range(joystick.get_numhats()):
                    previous_xy = hat_states.get(index, (0, 0))
                    current_xy = tuple(joystick.get_hat(index))
                    previous = set()
                    current = set()
                    for x, y, target in (
                            (previous_xy[0], previous_xy[1], previous),
                            (current_xy[0], current_xy[1], current)):
                        if y > 0: target.add("hat:up")
                        if y < 0: target.add("hat:down")
                        if x > 0: target.add("hat:right")
                        if x < 0: target.add("hat:left")
                    for token in previous - current:
                        self.callback(token, False)
                    for token in current - previous:
                        self.callback(token, True)
                    hat_states[index] = current_xy
                clock.tick(120)
        finally:
            try:
                pygame.quit()
            except Exception:
                pass


class OperationGamepadMapDialog:
    PREVIEW_IID = "__input_preview__"
    SELECTED_COLOR = "#ffd54f"
    ARMED_COLOR = "#ff9800"
    PRESSED_COLOR = "#43d17a"
    BOTH_COLOR = "#35c6d8"
    NORMAL_COLOR = "#343434"

    def __init__(self, parent, store, joystick_index=0, use_monitor=True,
                 on_saved=None):
        self.store = store
        self.on_saved = on_saved
        self.data = store.load()
        self.mapping = {}
        self.active_control = None
        self.capture_armed = False
        self.last_detected_token = ""
        self.pressed_controls = set()
        self.canvas_items = {}
        # Some SDL drivers emit axis noise at a very high rate.  If Tk is
        # covered or paused, keep the teaching dialog from retaining an
        # unbounded history of obsolete light-up events.
        self.event_queue = queue.Queue(maxsize=512)
        self.monitor = GamepadTeachMonitor(joystick_index, self.queue_physical_input) \
            if use_monitor else None
        self.window = tk.Toplevel(parent)
        self.window.title("操作記録用 PCゲームパッド割り当て")
        self.window.geometry("940x700")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        bar = ttk.Frame(self.window)
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(bar, text="プロファイル:").pack(side="left")
        self.profile_name = tk.StringVar(value=self.data["selected"])
        self.profile_combo = ttk.Combobox(
            bar, state="readonly", width=28, textvariable=self.profile_name,
            values=sorted(self.data["profiles"], key=str.casefold))
        self.profile_combo.pack(side="left", padx=5)
        self.profile_combo.bind("<<ComboboxSelected>>", self._load_selected)
        ttk.Button(bar, text="新規", command=self._new_profile).pack(side="left", padx=2)
        ttk.Button(bar, text="保存", command=self._save_profile).pack(side="left", padx=2)
        ttk.Button(bar, text="削除", command=self._delete_profile).pack(side="left", padx=2)
        ttk.Button(bar, text="初期割り当てに戻す",
                   command=self._reset_mapping).pack(side="left", padx=(10, 2))
        ttk.Label(self.window, text=(
            "一覧の［入力確認（変更なし）］では割り当てを変えずに点灯確認できます。"
            " 黄色=選択中、橙=変更待ち、緑=実際に押下中、水色=選択＋押下です。"),
            foreground="#174a7e").pack(fill="x", padx=12, pady=4)
        self.status = tk.StringVar(
            value="押下確認中です。割り当てを変更する場合はSwitch側のボタンを選択してください。")
        ttk.Label(self.window, textvariable=self.status, foreground="#9a4e00").pack(
            fill="x", padx=12, pady=(0, 5))
        assignment_bar = ttk.Frame(self.window)
        assignment_bar.pack(fill="x", padx=10, pady=(0, 5))
        self.assign_detected_text = tk.StringVar(value="検出入力を選択先へ登録")
        self.assign_detected_button = ttk.Button(
            assignment_bar, textvariable=self.assign_detected_text,
            command=self._assign_last_detected, state="disabled")
        self.assign_detected_button.pack(side="left", padx=(0, 6))
        ttk.Button(assignment_bar, text="次に押す入力を割り当て",
                   command=self._arm_selected).pack(side="left", padx=(0, 6))
        ttk.Button(assignment_bar, text="選択入力を解除",
                   command=self._clear_active).pack(side="left")

        body = ttk.Frame(self.window)
        body.pack(fill="both", expand=True, padx=10, pady=5)
        self.tree = ttk.Treeview(body, columns=("control", "physical"),
                                 show="headings", height=20, selectmode="browse")
        self.tree.heading("control", text="Switch操作")
        self.tree.heading("physical", text="PCゲームパッド入力")
        self.tree.column("control", width=145)
        self.tree.column("physical", width=170)
        self.tree.grid(row=0, column=0, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._tree_selected)
        self.canvas = tk.Canvas(body, width=590, height=470, bg="#f4f6f8",
                                highlightthickness=1, highlightbackground="#b0bec5")
        self.canvas.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._draw_controller()
        buttons = ttk.Frame(self.window)
        buttons.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(buttons, text="閉じる", command=self.close).pack(side="right")
        self._load_selected()
        if self.monitor is not None:
            self.monitor.start()
        self.window.after(30, self._drain_events)
        self.window.grab_set()

    def _draw_controller(self):
        c = self.canvas
        c.create_rectangle(35, 70, 285, 420, fill="#95e8f4", outline="#24869a", width=3)
        c.create_rectangle(305, 70, 555, 420, fill="#ff8b91", outline="#a8323c", width=3)
        positions = {
            "ZL": (70, 45), "L": (155, 80), "MINUS": (245, 125),
            "LCLICK": (155, 175), "DPAD_UP": (155, 245),
            "DPAD_LEFT": (110, 290), "DPAD_RIGHT": (200, 290),
            "DPAD_DOWN": (155, 335), "CAPTURE": (245, 385),
            "ZR": (520, 45), "R": (435, 80), "PLUS": (345, 125),
            "RCLICK": (435, 250), "X": (465, 155), "Y": (420, 200),
            "A": (510, 200), "B": (465, 245), "HOME": (345, 385),
        }
        for control, (x, y) in positions.items():
            radius = 25 if control not in ("ZL", "ZR", "L", "R") else 28
            shape = c.create_oval(x-radius, y-radius, x+radius, y+radius,
                                  fill=self.NORMAL_COLOR, outline="white", width=2,
                                  tags=("control:" + control,))
            label = c.create_text(x, y, text=control.replace("DPAD_", ""),
                                  fill="white", font=("Segoe UI", 9, "bold"),
                                  tags=("control:" + control,))
            self.canvas_items[control] = (shape, label)
            c.tag_bind("control:" + control, "<Button-1>",
                       lambda _event, name=control: self._select_control(name))

    def queue_physical_input(self, token, pressed):
        item = (str(token), bool(pressed))
        try:
            self.event_queue.put_nowait(item)
        except queue.Full:
            try:
                self.event_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.event_queue.put_nowait(item)
            except queue.Full:
                pass

    def handle_physical_input(self, token, pressed):
        token = str(token)
        taught = False
        if pressed:
            self._remember_detected(token)
        if pressed and self.active_control and self.capture_armed:
            self._assign_token_to_active(token)
            self.capture_armed = False
            taught = True
            self.status.set("{} ← {}。保存すると反映します。".format(
                CONTROL_LABELS.get(self.active_control, self.active_control), token))
        affected = controls_for_token(self.mapping, token)
        if pressed:
            self.pressed_controls.update(affected)
            if not taught:
                labels = [CONTROL_LABELS.get(name, name) for name in CONTROL_ORDER
                          if name in affected]
                self.status.set("検出: {}{}".format(
                    token, " → " + " / ".join(labels) if labels else "（未割り当て）"))
        else:
            self.pressed_controls.difference_update(affected)
        self._paint_controls()

    def _drain_events(self):
        if not self.window.winfo_exists():
            return
        try:
            while True:
                token, pressed = self.event_queue.get_nowait()
                self.handle_physical_input(token, pressed)
        except queue.Empty:
            pass
        self.window.after(30, self._drain_events)

    def _load_selected(self, _event=None):
        item = self.data["profiles"].get(self.profile_name.get(), {})
        self.mapping = normalize_gamepad_mapping(item.get("mapping", {}))
        self.pressed_controls.clear()
        self.active_control = None
        self.capture_armed = False
        self.last_detected_token = ""
        self.assign_detected_text.set("検出入力を選択先へ登録")
        self._refresh_tree()
        self.tree.selection_set(self.PREVIEW_IID)
        self._paint_controls()
        self._update_assignment_actions()
        self.status.set(
            "入力確認モードです。実機入力を押して点灯と検出番号を確認できます。")

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree.insert("", "end", iid=self.PREVIEW_IID,
                         values=("入力確認（変更なし）", "—"))
        for control in CONTROL_ORDER:
            self.tree.insert("", "end", iid=control,
                             values=(CONTROL_LABELS.get(control, control),
                                     self.mapping.get(control, "")))

    def _update_tree_values(self):
        for control in CONTROL_ORDER:
            if self.tree.exists(control):
                self.tree.item(control, values=(
                    CONTROL_LABELS.get(control, control), self.mapping.get(control, "")))

    def _tree_selected(self, _event=None):
        selected = self.tree.selection()
        if selected:
            if selected[0] == self.PREVIEW_IID:
                self._select_preview_mode(select_tree=False)
            else:
                self._select_control(selected[0], select_tree=False)

    def _select_preview_mode(self, select_tree=True):
        self.active_control = None
        self.capture_armed = False
        if select_tree and self.tree.exists(self.PREVIEW_IID):
            self.tree.selection_set(self.PREVIEW_IID)
            self.tree.see(self.PREVIEW_IID)
        self._paint_controls()
        self._update_assignment_actions()
        self.status.set("入力確認モードです。割り当ては変更されません。")

    def _select_control(self, control, select_tree=True):
        if control not in CONTROL_ORDER:
            return
        self.active_control = control
        self.capture_armed = False
        if select_tree and self.tree.exists(control):
            self.tree.selection_set(control)
            self.tree.see(control)
        self._paint_controls()
        self._update_assignment_actions()
        if self.last_detected_token:
            self.status.set("{}を選択中。上部のボタンで検出済みの{}を登録できます。".format(
                CONTROL_LABELS.get(control, control), self.last_detected_token))
        else:
            self.status.set("{}を選択中。入力確認後、検出した入力を上部ボタンで登録できます。".format(
                CONTROL_LABELS.get(control, control)))

    def _arm_selected(self):
        if self.active_control not in CONTROL_ORDER:
            self.status.set("先にSwitch側の変更対象を選択してください。")
            return
        self.capture_armed = True
        self._paint_controls()
        self.status.set("{}の変更待ちです。割り当てる物理ボタンを1回押してください。".format(
            CONTROL_LABELS.get(self.active_control, self.active_control)))

    def _remember_detected(self, token):
        self.last_detected_token = str(token)
        self.assign_detected_text.set(
            "検出した {} を選択先へ登録".format(self.last_detected_token))
        self._update_assignment_actions()

    def _update_assignment_actions(self):
        enabled = (self.active_control in CONTROL_ORDER and bool(self.last_detected_token))
        self.assign_detected_button.configure(state="normal" if enabled else "disabled")

    def _assign_token_to_active(self, token):
        if self.active_control not in CONTROL_ORDER or not token:
            return False
        for control in CONTROL_ORDER:
            if control != self.active_control and self.mapping.get(control) == token:
                self.mapping[control] = ""
        self.mapping[self.active_control] = str(token)
        self._update_tree_values()
        return True

    def _assign_last_detected(self):
        if not self._assign_token_to_active(self.last_detected_token):
            self.status.set("Switch側の登録先を選び、実機入力を1回押してください。")
            return
        self.capture_armed = False
        self._paint_controls()
        self.status.set("{} ← {}。保存すると反映します。".format(
            CONTROL_LABELS.get(self.active_control, self.active_control),
            self.last_detected_token))

    def _paint_controls(self):
        for name, (shape, label) in self.canvas_items.items():
            selected = name == self.active_control
            pressed = name in self.pressed_controls
            color = self.BOTH_COLOR if selected and pressed else \
                self.ARMED_COLOR if selected and self.capture_armed else \
                self.PRESSED_COLOR if pressed else self.SELECTED_COLOR if selected else self.NORMAL_COLOR
            self.canvas.itemconfigure(shape, fill=color,
                                      outline="#ff8f00" if selected else "white",
                                      width=4 if selected else 2)
            self.canvas.itemconfigure(label, fill="#202020" if selected or pressed else "white")

    def _clear_active(self):
        if self.active_control not in CONTROL_ORDER:
            return
        self.mapping[self.active_control] = ""
        self.capture_armed = False
        self._update_tree_values()
        self._paint_controls()

    def _reset_mapping(self):
        self.mapping = normalize_gamepad_mapping(DEFAULT_MAPPING)
        self.active_control = None
        self.capture_armed = False
        self.last_detected_token = ""
        self.pressed_controls.clear()
        self._update_tree_values()
        if self.tree.exists(self.PREVIEW_IID):
            self.tree.selection_set(self.PREVIEW_IID)
        self.assign_detected_text.set("検出入力を選択先へ登録")
        self._update_assignment_actions()
        self._paint_controls()
        self.status.set("初期割り当てへ戻しました。保存すると反映します。")

    def _new_profile(self):
        name = str(simpledialog.askstring("ゲームパッド設定", "新しいプロファイル名:",
                                          parent=self.window) or "").strip()
        if not name:
            return
        if name in self.data["profiles"]:
            tkmsg.showwarning("ゲームパッド設定", "同名のプロファイルがあります。",
                              parent=self.window)
            return
        self.data["profiles"][name] = {
            "mapping": normalize_gamepad_mapping(DEFAULT_MAPPING)}
        self.profile_combo.configure(values=sorted(self.data["profiles"], key=str.casefold))
        self.profile_name.set(name)
        self._load_selected()

    def _save_profile(self):
        name = self.profile_name.get().strip()
        self.data["profiles"][name] = {"mapping": normalize_gamepad_mapping(self.mapping)}
        self.data["selected"] = name
        self.data = self.store.save(self.data)
        if self.on_saved is not None:
            self.on_saved(name, dict(self.mapping))
        self.status.set("{}をPokeConへ保存し、選択プロファイルにしました。".format(name))

    def _delete_profile(self):
        name = self.profile_name.get().strip()
        if len(self.data["profiles"]) <= 1:
            tkmsg.showwarning("ゲームパッド設定", "最後のプロファイルは削除できません。",
                              parent=self.window)
            return
        if not tkmsg.askyesno("ゲームパッド設定", "{}を削除しますか？".format(name),
                              parent=self.window):
            return
        self.data["profiles"].pop(name, None)
        self.data["selected"] = sorted(self.data["profiles"], key=str.casefold)[0]
        self.data = self.store.save(self.data)
        self.profile_combo.configure(values=sorted(self.data["profiles"], key=str.casefold))
        self.profile_name.set(self.data["selected"])
        self._load_selected()
        if self.on_saved is not None:
            selected = self.data["selected"]
            self.on_saved(selected, dict(self.data["profiles"][selected]["mapping"]))

    def close(self):
        if self.monitor is not None:
            self.monitor.stop()
        if self.window.winfo_exists():
            self.window.destroy()
