#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, TYPE_CHECKING

import pygame
import numpy as np
import datetime
import time
from logging import getLogger, DEBUG, NullHandler

if TYPE_CHECKING:
    from Commands.Sender import Sender


class ProController:
    flag_procon = False
    ACTIVITY_NOTIFICATION_IDLE_SECONDS = 10 * 60

    def __init__(self, joystick_index=0, input_enabled_event=None, activity_callback=None,
                 state_callback=None):
        self.joystick_index = max(0, int(joystick_index))
        self.input_enabled_event = input_enabled_event
        self.activity_callback = activity_callback
        self.state_callback = state_callback
        self.last_activity_at = None
        self.joystick_instance_id = None
        self.axis_dict = {
            0: "L-X",
            1: "L-Y",
            2: "R-X",
            3: "R-Y",
            4: "ZL",
            5: "ZR",
        }

        self.button_dict = {
            0: "A",
            1: "B",
            2: "X",
            3: "Y",
            4: "MINUS",
            5: "HOME",
            6: "PLUS",
            7: "LSTICK",
            8: "RSTICK",
            9: "L",
            10: "R",
            11: "UP",
            12: "DOWN",
            13: "LEFT",
            14: "RIGHT",
            15: "CAPTURE",
        }

        self.button_dict_shift = {
            0: 4,
            1: 3,
            2: 5,
            3: 2,
            4: 10,
            # The physical Guide/Home button is reserved by Steam on Windows.
            # Do not forward it to Switch; Steam may also handle it globally.
            6: 11,
            7: 12,
            8: 13,
            9: 6,
            10: 7,
            11: 0,
            12: 2,
            13: 3,
            14: 1,
            15: 15,
        }

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

        def axis(index):
            return joystick.get_axis(index) if index < axis_count else 0.0

        def axis_from_neutral(index):
            value = float(axis(index)) - float(self.axis_baseline.get(index, 0.0))
            return max(-1.0, min(1.0, value))

        # Lstickの位置を確認する。
        if np.sqrt(axis_from_neutral(0) ** 2 + axis_from_neutral(1) ** 2) < 0.35:
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
        if np.sqrt(axis_from_neutral(2) ** 2 + axis_from_neutral(3) ** 2) < 0.35:
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
                if axis_index < 4:
                    if abs(event.dict["value"]) < 0.3:
                        pass
                    else:
                        pass
                elif axis_index in (4, 5):
                    self.flag_print = True
                    baseline = self.trigger_baseline.get(axis_index, event.dict["value"])
                    if abs(float(event.dict["value"]) - baseline) >= 0.5:
                        self.bits_16 = self.bits_16 | (1 << (axis_index + 4))
                    else:
                        self.bits_16 = self.bits_16 & ~(1 << (axis_index + 4))
            elif event.type == pygame.JOYBUTTONDOWN:
                button = int(event.dict["button"])
                shift = self.button_dict_shift.get(button)
                if shift is None:
                    self._logger.debug("Ignore unmapped gamepad button: %s", button)
                    continue
                self.flag_print = True
                if button <= 10 or button == 15:
                    self.bits_16 = self.bits_16 | (1 << shift)
                else:
                    self.hat_status = self.hat_status | (1 << shift)
            elif event.type == pygame.JOYBUTTONUP:
                button = int(event.dict["button"])
                shift = self.button_dict_shift.get(button)
                if shift is None:
                    continue
                self.flag_print = True
                if button <= 10 or button == 15:
                    self.bits_16 = self.bits_16 & ~(1 << shift)
                else:
                    self.hat_status = self.hat_status & ~(1 << shift)
            elif event.type == pygame.JOYHATMOTION:
                x, y = event.value
                self.hat_status = ((1 if y > 0 else 0) | (4 if y < 0 else 0)
                                   | (2 if x > 0 else 0) | (8 if x < 0 else 0))
                self.flag_print = True

    def send_message(self, ser: Sender, flag_record: bool):
        # 送信するバイナリデータ生成
        self.message = "0x%04x %01d" % (self.bits_16, self.hat_dict[self.hat_status]) + self.stick_bits

        # コマンドが異なる場合のみ送る
        sent = False
        if self.flag_print and self.old_message != self.message:
            self.time0 = datetime.datetime.today()
            ser.writeRow_wo_perf_counter(self.message, is_show=False)
            sent = True

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

    def suspend_input(self, ser: Sender, flag_record: bool):
        """Release Switch controls once, then discard input while permission is off."""
        self.bits_16 = 0
        self.hat_status = 0
        self.stick_status_old = [128, 128, 128, 128]
        self.stick_status_new = [128, 128, 128, 128]
        self.stick_bits = " 80 80 80 80"
        self.message = "0x0003 8 80 80 80 80"
        self.time0 = datetime.datetime.today()
        ser.writeRow_wo_perf_counter(self.message, is_show=False)
        if flag_record:
            self.record_message(False)
        self.old_message = self.message
        self.flag_print = False
        self.awaiting_neutral = True
        self.neutral_poll_count = 0

    def joystick_is_neutral(self, joystick: pygame.Joystick):
        """Require a stable neutral pad before forwarding a newly enabled input."""
        for index in range(min(4, joystick.get_numaxes())):
            baseline = float(self.axis_baseline.get(index, 0.0))
            if abs(float(joystick.get_axis(index)) - baseline) >= 0.3:
                return False
        # Unmapped Guide/vendor buttons can be reported as permanently held by
        # Steam virtual devices. They must not block the safety gate forever.
        for index in self.button_dict_shift:
            if index < joystick.get_numbuttons() and joystick.get_button(index):
                return False
        for index in range(joystick.get_numhats()):
            if joystick.get_hat(index) != (0, 0):
                return False
        return True

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
        ser.writeRow_wo_perf_counter(self.message, is_show=False)
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
        self.trigger_baseline = {
            index: float(joystick.get_axis(index))
            for index in (4, 5) if index < joystick.get_numaxes()
        }
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
                        if self.joystick_is_neutral(joystick):
                            self.neutral_poll_count += 1
                            if self.neutral_poll_count >= 3:
                                self.awaiting_neutral = False
                                pygame.event.clear()
                                self.report_state("ready")
                        else:
                            self.neutral_poll_count = 0
                        previously_enabled = enabled
                        clock.tick(120)
                        continue
                    # L/R-Stick and button/hat input are evaluated only while
                    # Camera > Display Settings grants explicit permission.
                    self.joystick_move_detection(joystick)
                    self.event_check(events)
                    if self.send_message(ser, flag_record):
                        self.report_activity()
                elif previously_enabled:
                    # Release any held Switch input exactly once when permission
                    # is revoked, preventing a stuck button or stick direction.
                    self.suspend_input(ser, flag_record)
                    self.report_state("disabled")
                previously_enabled = enabled
                # Avoid consuming a CPU core while retaining responsive input.
                clock.tick(120)
                # print("4")
        except Exception as error:
            self._logger.warning("PC gamepad bridge stopped: %s", error)
        finally:
            # 終了処理
            self.end_sequence(ser, flag_record)
        pygame.quit()
        self._logger.info("Inactivate Pro Controller")
        print("*****Inactivate Pro Controller*****")
