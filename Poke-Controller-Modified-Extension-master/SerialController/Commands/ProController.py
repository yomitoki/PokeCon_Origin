#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, TYPE_CHECKING

import pygame
import datetime
import math
import time
import threading
from logging import getLogger, DEBUG, NullHandler

from OperationGamepadMap import (DEFAULT_MAPPING, controls_for_token,
                                 gamepad_axis_token,
                                 normalize_gamepad_mapping,
                                 opposite_axis_tokens)

if TYPE_CHECKING:
    from Commands.Sender import Sender


class ProController:
    flag_procon = False
    ACTIVITY_NOTIFICATION_IDLE_SECONDS = 10 * 60
    # State-change packets are cheap.  Polling at 240 Hz keeps the controller
    # side below one display frame of latency without sending duplicate serial
    # traffic or involving Tk's event loop.
    POLL_HZ = 240

    CONTROL_BITS = {
        "Y": 2, "B": 3, "A": 4, "X": 5, "L": 6, "R": 7,
        "ZL": 8, "ZR": 9, "MINUS": 10, "PLUS": 11,
        "LCLICK": 12, "RCLICK": 13, "HOME": 14, "CAPTURE": 15,
    }
    DPAD_BITS = {"DPAD_UP": 1, "DPAD_RIGHT": 2,
                  "DPAD_DOWN": 4, "DPAD_LEFT": 8}

    def __init__(self, joystick_index=0, input_enabled_event=None, activity_callback=None,
                 state_callback=None, input_callback=None, control_mapping=None,
                 physical_input_callback=None):
        self.joystick_index = max(0, int(joystick_index))
        self.input_enabled_event = input_enabled_event
        self.activity_callback = activity_callback
        self.state_callback = state_callback
        self.input_callback = input_callback
        self.physical_input_callback = physical_input_callback
        self._mapping_lock = threading.RLock()
        self.control_mapping = normalize_gamepad_mapping(
            control_mapping if control_mapping is not None else DEFAULT_MAPPING)
        self._active_axis_tokens = {}
        self._axis_suppressed_tokens = {}
        self._preview_axis_tokens = {}
        self._preview_axis_suppressed_tokens = {}
        self._polled_button_states = {}
        self._polled_hat_states = {}
        self._neutral_blocker_state = ""
        self._axis_rebaseline_pending = True
        self.last_activity_at = None
        self.joystick_instance_id = None
        self.hat_dict = {
            0: 8,  # center
            1: 0,  # up
            2: 2,  # right
            3: 1,  # up-right
            4: 4,  # down
            5: 8,  # ありえないのでcenterにする
            6: 3,  # down-right
            7: 8,  # ありえないのでcenterにする
            8: 6,  # left
            9: 7,  # up-left
            10: 8,  # ありえないのでcenterにする
            11: 8,  # ありえないのでcenterにする
            12: 5,  # down-left
            13: 8,  # ありえないのでcenterにする
            14: 8,  # ありえないのでcenterにする
            15: 8,  # ありえないのでcenterにする
        }

        self.bits_16 = 0
        self.hat_status = 0
        self.stick_status_old = [128, 128, 128, 128]
        self.stick_status_new = [128, 128, 128, 128]
        self.trigger_baseline = {}
        self.axis_baseline = {}
        self.awaiting_neutral = True
        self.neutral_poll_count = 0
        self.flag_print = False
        self.filename = ""

        self._logger = getLogger(__name__)
        self._logger.addHandler(NullHandler())
        self._logger.setLevel(DEBUG)
        self._logger.propagate = True

    def set_control_mapping(self, mapping):
        """Replace the physical-button map without restarting the bridge."""
        with self._mapping_lock:
            self.control_mapping = normalize_gamepad_mapping(mapping)
            self.bits_16 &= 3
            self.hat_status = 0
            self._active_axis_tokens.clear()
            self._axis_suppressed_tokens.clear()
            self._preview_axis_tokens.clear()
            self._preview_axis_suppressed_tokens.clear()
            self.flag_print = True
            self._axis_rebaseline_pending = True

    def mapped_axis_indices(self):
        indices = set()
        with self._mapping_lock:
            sources = tuple(self.control_mapping.values())
        for source in sources:
            if source.startswith("axis:"):
                try:
                    indices.add(int(source.split(":", 1)[1][:-1]))
                except (ValueError, IndexError):
                    pass
        return indices

    def stabilize_mapped_axis_baselines(self, joystick):
        """Learn trigger rest values after SDL has finished initializing them."""
        for index in self.mapped_axis_indices():
            if index < joystick.get_numaxes():
                self.axis_baseline[index] = float(joystick.get_axis(index))
        self._axis_rebaseline_pending = False

    def report_physical_input(self, token, pressed):
        if self.physical_input_callback is None:
            return
        try:
            self.physical_input_callback(str(token), bool(pressed))
        except Exception as error:
            self._logger.debug("Physical input callback failed: %s", error)

    def _apply_physical(self, token, pressed):
        with self._mapping_lock:
            controls = controls_for_token(self.control_mapping, token)
        for control in controls:
            if control in self.CONTROL_BITS:
                mask = 1 << self.CONTROL_BITS[control]
                if pressed:
                    self.bits_16 |= mask
                else:
                    self.bits_16 &= ~mask
            elif control in self.DPAD_BITS:
                mask = self.DPAD_BITS[control]
                if pressed:
                    self.hat_status |= mask
                else:
                    self.hat_status &= ~mask
        if controls:
            self.flag_print = True
        self.report_physical_input(token, pressed)

    def poll_digital_states(self, joystick, forward=False, report=True):
        """Poll buttons/hats so mapping preview cannot lose short SDL events."""
        for index in range(joystick.get_numbuttons()):
            current = bool(joystick.get_button(index))
            if index not in self._polled_button_states:
                self._polled_button_states[index] = current
                continue
            previous = self._polled_button_states[index]
            if current != previous:
                token = "button:{}".format(index)
                if forward:
                    self._apply_physical(token, current)
                elif report:
                    self.report_physical_input(token, current)
                self._polled_button_states[index] = current

        for index in range(joystick.get_numhats()):
            x, y = joystick.get_hat(index)
            current = set()
            if y > 0: current.add("hat:up")
            if y < 0: current.add("hat:down")
            if x > 0: current.add("hat:right")
            if x < 0: current.add("hat:left")
            if index not in self._polled_hat_states:
                self._polled_hat_states[index] = current
                continue
            previous = self._polled_hat_states[index]
            for token in previous - current:
                if forward:
                    self._apply_physical(token, False)
                elif report:
                    self.report_physical_input(token, False)
            for token in current - previous:
                if forward:
                    self._apply_physical(token, True)
                elif report:
                    self.report_physical_input(token, True)
            self._polled_hat_states[index] = current

    def physical_token_is_mapped(self, token):
        with self._mapping_lock:
            return bool(controls_for_token(self.control_mapping, token))

    @staticmethod
    def _axis_transition(index, current, active, suppressed, callback,
                         allow_opposite=None):
        previous = active.get(index, "")
        if previous and previous != current:
            callback(previous, False)
            if (opposite_axis_tokens(previous, current)
                    and not (allow_opposite is not None and allow_opposite(current))):
                suppressed[index] = current
        if not current:
            suppressed.pop(index, None)
        elif index in suppressed and current != suppressed[index]:
            suppressed.pop(index, None)
        if current == suppressed.get(index):
            current = ""
        if current and current != previous:
            callback(current, True)
        if current:
            active[index] = current
        else:
            active.pop(index, None)

    @staticmethod
    def devices():
        """Return connected PC gamepads."""
        names = []
        try:
            pygame.joystick.init()
            for index in range(pygame.joystick.get_count()):
                joystick = pygame.joystick.Joystick(index)
                names.append("{}: {}".format(index, joystick.get_name()))
        except Exception:
            names = []
        return names

    # stickの出力を0-255の範囲に補正する。
    def map_axis(self, val: float):
        val = round(val, 3)
        in_min = -1
        in_max = 1
        out_min = 0
        out_max = 255
        return int((val - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

    def joystick_move_detection(self, joystick: pygame.Joystick):
        axis_count = joystick.get_numaxes()
        mapped_button_axes = self.mapped_axis_indices()

        def axis(index):
            return joystick.get_axis(index) if index < axis_count else 0.0

        def axis_from_neutral(index):
            # A trigger can be reported on an axis that another controller uses
            # for a stick. Once taught as a button, do not also move that stick.
            if index in mapped_button_axes:
                return 0.0
            value = float(axis(index)) - float(self.axis_baseline.get(index, 0.0))
            return max(-1.0, min(1.0, value))

        # Lstickの位置を確認する。
        if math.hypot(axis_from_neutral(0), axis_from_neutral(1)) < 0.35:
            self.stick_status_new[0] = 128
            self.stick_status_new[1] = 128
        else:
            self.stick_status_new[0] = self.map_axis(axis_from_neutral(0))
            self.stick_status_new[1] = self.map_axis(axis_from_neutral(1))
        # 古い位置と比較して異なるならビットを立てる
        if (
            self.stick_status_new[0] == self.stick_status_old[0]
            and self.stick_status_new[1] == self.stick_status_old[1]
        ):
            self.bits_16 = self.bits_16 & ~(2)
        else:
            self.flag_print = True
            self.bits_16 = self.bits_16 | 2

        # Rstickの位置を確認する。
        if math.hypot(axis_from_neutral(2), axis_from_neutral(3)) < 0.35:
            self.stick_status_new[2] = 128
            self.stick_status_new[3] = 128
        else:
            self.stick_status_new[2] = self.map_axis(axis_from_neutral(2))
            self.stick_status_new[3] = self.map_axis(axis_from_neutral(3))
        # 古い位置と比較して異なるならビットを立てる
        if (
            self.stick_status_new[2] == self.stick_status_old[2]
            and self.stick_status_new[3] == self.stick_status_old[3]
        ):
            self.bits_16 = self.bits_16 & ~(1)
        else:
            self.flag_print = True
            self.bits_16 = self.bits_16 | 1

        if self.bits_16 & 3 == 1:
            self.stick_bits = " %02x %02x" % (self.stick_status_new[2], self.stick_status_new[3])
        elif self.bits_16 & 3 == 2:
            self.stick_bits = " %02x %02x" % (self.stick_status_new[0], self.stick_status_new[1])
        elif self.bits_16 & 3 == 3:
            self.stick_bits = " %02x %02x %02x %02x" % (
                self.stick_status_new[0],
                self.stick_status_new[1],
                self.stick_status_new[2],
                self.stick_status_new[3],
            )
        else:
            self.stick_bits = ""

        # deep copy
        self.stick_status_old[0] = self.stick_status_new[0]
        self.stick_status_old[1] = self.stick_status_new[1]
        self.stick_status_old[2] = self.stick_status_new[2]
        self.stick_status_old[3] = self.stick_status_new[3]

    def event_check(self, events: List[pygame.Event]):
        for i, event in enumerate(events):
            if (hasattr(event, "instance_id") and self.joystick_instance_id is not None
                    and int(event.instance_id) != self.joystick_instance_id):
                continue
            if (not hasattr(event, "instance_id") and hasattr(event, "joy")
                    and int(event.joy) != self.joystick_index):
                continue
            if event.type == pygame.JOYAXISMOTION:
                axis_index = int(event.dict["axis"])
                current = gamepad_axis_token(
                    axis_index, event.dict["value"],
                    self.axis_baseline.get(axis_index, 0.0))
                self._axis_transition(
                    axis_index, current, self._active_axis_tokens,
                    self._axis_suppressed_tokens, self._apply_physical,
                    allow_opposite=self.physical_token_is_mapped)

    def report_only_events(self, events: List[pygame.Event]):
        """Publish raw presses for the mapping screen while Serial input is off."""
        for event in events:
            if (hasattr(event, "instance_id") and self.joystick_instance_id is not None
                    and int(event.instance_id) != self.joystick_instance_id):
                continue
            if (not hasattr(event, "instance_id") and hasattr(event, "joy")
                    and int(event.joy) != self.joystick_index):
                continue
            if event.type == pygame.JOYAXISMOTION:
                index = int(event.dict["axis"])
                current = gamepad_axis_token(
                    index, event.dict["value"], self.axis_baseline.get(index, 0.0))
                self._axis_transition(
                    index, current, self._preview_axis_tokens,
                    self._preview_axis_suppressed_tokens,
                    self.report_physical_input,
                    allow_opposite=self.physical_token_is_mapped)

    def send_message(self, ser: Sender, flag_record: bool):
        # 送信するバイナリデータ生成
        self.message = "0x%04x %01d" % (self.bits_16, self.hat_dict[self.hat_status]) + self.stick_bits

        # コマンドが異なる場合のみ送る
        sent = False
        if self.flag_print and self.old_message != self.message:
            self.time0 = datetime.datetime.today()
            # PC gamepad packets are manual input and must not queue behind a
            # Commands/software-controller override.
            ser.writeRow_wo_perf_counter(self.message, is_show=False, priority=True)
            sent = True
            self.report_input(self.message)

            # 記録モードになっている場合のみ
            if flag_record:
                self.record_message(False)

        # コマンドが異なることの検知のために保存
        self.old_message = self.message
        return sent

    def input_is_enabled(self):
        return self.input_enabled_event is None or self.input_enabled_event.is_set()

    def report_activity(self):
        now = time.monotonic()
        should_notify = (
            self.last_activity_at is None
            or now - self.last_activity_at >= self.ACTIVITY_NOTIFICATION_IDLE_SECONDS
        )
        self.last_activity_at = now
        if should_notify and self.activity_callback is not None:
            self.activity_callback()

    def report_state(self, state):
        if self.state_callback is not None:
            self.state_callback(state)

    def report_input(self, message):
        if self.input_callback is None:
            return
        try:
            self.input_callback(str(message), time.monotonic())
        except Exception as error:
            # Capturing authoring metadata must never interrupt live control.
            self._logger.warning("PC gamepad input callback failed: %s", error)

    def suspend_input(self, ser: Sender, flag_record: bool):
        """Release Switch controls once, then discard input while permission is off."""
        self.bits_16 = 0
        self.hat_status = 0
        self.stick_status_old = [128, 128, 128, 128]
        self.stick_status_new = [128, 128, 128, 128]
        self.stick_bits = " 80 80 80 80"
        self.message = "0x0003 8 80 80 80 80"
        self.time0 = datetime.datetime.today()
        ser.writeRow_wo_perf_counter(self.message, is_show=False, priority=True)
        self.report_input(self.message)
        if flag_record:
            self.record_message(False)
        self.old_message = self.message
        self.flag_print = False
        self.awaiting_neutral = True
        self.neutral_poll_count = 0

    def joystick_is_neutral(self, joystick: pygame.Joystick):
        """Require a stable neutral pad before forwarding a newly enabled input."""
        return not self.joystick_neutral_blocker(joystick)

    def joystick_neutral_blocker(self, joystick: pygame.Joystick):
        """Return the physical input that is preventing the safety gate."""
        # Axes explicitly taught as buttons/triggers are calibrated separately
        # and never block the neutral safety gate. Their +/- direction is used
        # only when the operation profile maps that token to a Switch control.
        mapped_button_axes = self.mapped_axis_indices()
        mapped_axes = set(range(min(4, joystick.get_numaxes()))) - mapped_button_axes
        for index in mapped_axes:
            if index >= joystick.get_numaxes():
                continue
            baseline = float(self.axis_baseline.get(index, 0.0))
            if abs(float(joystick.get_axis(index)) - baseline) >= 0.3:
                return "axis:{}".format(index)
        # Buttons and hats are event-driven. Their startup events are cleared
        # before entering ready state, so a driver-reported held button cannot
        # be forwarded and must not keep the whole controller disabled. Once
        # released and pressed again, a fresh event is handled normally.
        return ""

    def record_message(self, flag_force_write: bool):
        # バイナリデータを追加する。
        message_log = str(self.time0) + "," + self.message + "\n"
        self.controller_log.append(message_log)

        # バイナリデータが100個たまった or 強制書き込み時
        if len(self.controller_log) == 100 or flag_force_write:
            self.f.writelines(self.controller_log)
            self.controller_log = []

    def end_sequence(self, ser: Sender, flag_record: bool):
        self.message = "0x0003 8 80 80 80 80"
        ser.writeRow_wo_perf_counter(self.message, is_show=False, priority=True)
        self.report_input(self.message)
        if flag_record:
            self.record_message(True)
            self.f.close()
            self._logger.info(f"{self.filename} is closed.")
            print(f"{self.filename} is closed.")

    def controller_loop(self, ser: Sender, flag_record: bool, ControllerLogDir: str):
        self._logger.info("Activate Pro Controller")
        print("*****Activate Pro Controller*****")
        # pygame初期化
        pygame.init()
        if pygame.joystick.get_count() <= self.joystick_index:
            raise RuntimeError("選択したPCゲームパッドが見つかりません。")
        joystick = pygame.joystick.Joystick(self.joystick_index)
        joystick.init()
        if hasattr(joystick, "get_instance_id"):
            self.joystick_instance_id = int(joystick.get_instance_id())
        self.axis_baseline = {
            index: float(joystick.get_axis(index))
            for index in range(joystick.get_numaxes())
        }
        self.poll_digital_states(joystick, forward=False, report=False)
        self._logger.info("PC gamepad selected: index=%s instance=%s name=%s axes=%s buttons=%s hats=%s",
                          self.joystick_index, self.joystick_instance_id, joystick.get_name(),
                          joystick.get_numaxes(), joystick.get_numbuttons(), joystick.get_numhats())
        clock = pygame.time.Clock()

        if flag_record:
            start_time = datetime.datetime.today().strftime("%Y%m%d%H%M%S")
            self.filename = ControllerLogDir + "/controller_log_" + start_time + ".txt"
            self.f = open(self.filename, "w", encoding="UTF-8")
            self._logger.info(f"{self.filename} is opened.")
            print(f"{self.filename} is opened.")
            self.controller_log = []

        self.old_message = ""
        previously_enabled = self.input_is_enabled()
        self.report_state("waiting_neutral" if previously_enabled else "disabled")
        try:
            while self.flag_procon:
                # イベント取得
                events = pygame.event.get()
                enabled = self.input_is_enabled()
                if enabled:
                    if not previously_enabled:
                        self.awaiting_neutral = True
                        self.neutral_poll_count = 0
                        pygame.event.clear()
                        self.report_state("waiting_neutral")
                    if self.awaiting_neutral:
                        # SDL/XInput trigger axes often start at 0 and settle at
                        # -1 after the first event pump. Relearn only axes that
                        # are mapped as buttons while Serial output is gated.
                        self.stabilize_mapped_axis_baselines(joystick)
                        # Treat whatever the driver reports at startup as the
                        # non-forwarded baseline. Fresh changes after ready are
                        # polled and delivered even if SDL events were cleared.
                        self.poll_digital_states(joystick, forward=False, report=False)
                        blocker = self.joystick_neutral_blocker(joystick)
                        if not blocker:
                            self.neutral_poll_count += 1
                            if self.neutral_poll_count >= 3:
                                self.awaiting_neutral = False
                                pygame.event.clear()
                                self._neutral_blocker_state = ""
                                self.report_state("ready")
                        else:
                            self.neutral_poll_count = 0
                            if blocker != self._neutral_blocker_state:
                                self._neutral_blocker_state = blocker
                                self.report_state("waiting_neutral:" + blocker)
                        previously_enabled = enabled
                        clock.tick(self.POLL_HZ)
                        continue
                    if self._axis_rebaseline_pending:
                        self.stabilize_mapped_axis_baselines(joystick)
                    # L/R-Stick and button/hat input are evaluated only while
                    # Camera > Display Settings grants explicit permission.
                    self.joystick_move_detection(joystick)
                    self.event_check(events)
                    self.poll_digital_states(joystick, forward=True, report=True)
                    if self.send_message(ser, flag_record):
                        self.report_activity()
                else:
                    self.report_only_events(events)
                    self.poll_digital_states(joystick, forward=False, report=True)
                if not enabled and previously_enabled:
                    # Release any held Switch input exactly once when permission
                    # is revoked, preventing a stuck button or stick direction.
                    self.suspend_input(ser, flag_record)
                    self.report_state("disabled")
                previously_enabled = enabled
                # Avoid consuming a CPU core while retaining responsive input.
                clock.tick(self.POLL_HZ)
                # print("4")
        except Exception as error:
            self._logger.warning("PC gamepad bridge stopped: %s", error)
        finally:
            # 終了処理
            self.end_sequence(ser, flag_record)
        pygame.quit()
        self._logger.info("Inactivate Pro Controller")
        print("*****Inactivate Pro Controller*****")
