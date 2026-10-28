"""A second, lightweight capture/Commands pane in the existing Tk process."""
import copy
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

from Camera import Camera
from CaptureGeometry import capture_frame_size, fit_preview_size
from Commands.PythonCommandBase import ImageProcPythonCommand
from Commands.Sender import Sender
from Commands.Keys import KeyPress, normalize_serial_data_format_name
from GuiAssets import CaptureArea, ControllerGUI
from InputSetRuntimeRegistry import canonical_device_key
from Recording import CaptureRecorder
from WindowsAudioIdentity import usb_connection_token


def resolve_companion_camera(saved, devices):
    """Never use a stale numeric ID when a saved physical identity is absent."""
    identity = str(saved.get("device_path") or saved.get("device_value") or "").casefold()
    if identity:
        matches = [int(key) for key, value in devices.items()
                   if identity == str(value).casefold() or identity in str(value).casefold()]
        if not matches:
            token = saved.get("usb_connection_token") or usb_connection_token(identity)
            vid, pid = str(saved.get("vid", "")).casefold(), str(saved.get("pid", "")).casefold()
            if token and vid and pid:
                matches = [int(key) for key, value in devices.items()
                           if usb_connection_token(value) == token
                           and "vid_" + vid in str(value).casefold()
                           and "pid_" + pid in str(value).casefold()]
        if len(matches) != 1:
            raise ValueError("副画面の保存済みカメラを一意に確認できません。InputSetを更新してください。")
        return matches[0]
    raise ValueError("副画面には機器識別情報を保存したInputSetが必要です。")


def bind_companion_command(command, camera, preview, output, text_output):
    # Instance attributes isolate the old class defaults. Main Commands can
    # pause/stop or change their output widgets without affecting this pane.
    command.camera = camera
    command.gui = preview
    command.canvas = preview
    command.output = output
    command.text_output = text_output
    command.image_detection_event = lambda *args, **kwargs: None
    command.isPause = False
    command.isGuide = False
    command.isSimilarity = False
    command.isImage = False
    command.cur_command_name = command.NAME
    command.template_path_name = "./Template/"
    for key in ("isWinNotStart", "isWinNotEnd", "isLineNotStart", "isLineNotEnd",
                "isDiscordNotStart", "isDiscordNotEnd"):
        setattr(command, key, False)
    return command


class CompanionPane:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.camera = Camera(60)
        self.sender = Sender(False, if_print=False)
        self.recorder = CaptureRecorder()
        self.recorder.durable_finalization = True
        self.command = None
        self.controllers = []
        self.connected = False
        self.busy = False
        self.closing = False
        self.events = queue.Queue()
        self.device_keys = {}
        self.settings = {}
        self.audio_name = ""
        self.disk_check_at = 0.0
        self.frame = ttk.LabelFrame(app.camera_lf, text="副画面（最大2画面）")
        self.frame.grid(row=2, column=4, columnspan=3, sticky="n", padx=4)
        self.frame.is_use_left_stick_mouse = tk.BooleanVar(master=self.root, value=False)
        self.frame.is_use_right_stick_mouse = tk.BooleanVar(master=self.root, value=False)
        self.show = tk.BooleanVar(master=self.root, value=True)
        self.name = tk.StringVar(master=self.root)
        self.status = tk.StringVar(master=self.root, value="InputSetを選択して接続")
        self.command_name = tk.StringVar(master=self.root)
        row = ttk.Frame(self.frame)
        row.pack(fill="x")
        self.inputs = ttk.Combobox(row, state="readonly", textvariable=self.name,
                                  values=tuple(app._read_input_sets().get("input_sets", {})), width=22)
        self.inputs.pack(side="left", fill="x", expand=True)
        self.connect_button = ttk.Button(row, text="接続", command=self.connect)
        self.connect_button.pack(side="left")
        ttk.Button(row, text="閉じる", command=self.close).pack(side="left")
        self.preview = CaptureArea(self.camera, 60, "Default", self.show,
                                   KeyPress(self.sender, priority=True), self.frame, 480, 270)
        self.preview.pack()
        self.preview.set_render_priority_provider(lambda: (False, False, False))
        self.preview.set_resource_multiplier_provider(lambda: 1.0)
        self.preview.set_capture_work_provider(lambda: self.recorder.active)
        self.preview.set_presentation_listener(self.presented)
        self.commands = ttk.Combobox(self.frame, textvariable=self.command_name,
                                     state="readonly", width=50)
        self.commands.pack(fill="x", pady=3)
        buttons = ttk.Frame(self.frame)
        buttons.pack(fill="x")
        self.start_button = ttk.Button(buttons, text="Start", command=self.start_command)
        self.start_button.pack(side="left")
        ttk.Button(buttons, text="Stop", command=self.stop_command).pack(side="left")
        ttk.Button(buttons, text="Pause/再開", command=self.pause_command).pack(side="left")
        ttk.Button(buttons, text="Controller", command=self.controller).pack(side="left")
        buttons2 = ttk.Frame(self.frame)
        buttons2.pack(fill="x")
        self.record_button = ttk.Button(buttons2, text="副画面録画", command=self.toggle_recording)
        self.record_button.pack(side="left")
        ttk.Button(buttons2, text="両方スクショ", command=self.capture_both).pack(side="left")
        ttk.Button(buttons2, text="両方録画開始", command=self.record_both).pack(side="left")
        ttk.Button(buttons2, text="両方録画停止", command=self.stop_both).pack(side="left")
        ttk.Label(self.frame, text="主画面を優先。副画面は表示15fps／録画30fps。").pack(anchor="w")
        self.fps_status = tk.StringVar(master=self.root)
        ttk.Label(self.frame, textvariable=self.fps_status).pack(anchor="w")
        ttk.Label(self.frame, text="副画面の操作は上のCommands／Controllerから。", wraplength=470).pack(anchor="w")
        ttk.Label(self.frame, textvariable=self.status, wraplength=470).pack(anchor="w")
        self.log = tk.Text(self.frame, height=3, width=55, state="disabled")
        self.log.pack(fill="x")
        app.preview.grid_configure(columnspan=3, sticky="n")
        self.refresh_commands()
        self.preview.startCapture()
        self.poll_id = self.root.after(250, self.poll)

    def fit(self, primary_size):
        size = fit_preview_size(capture_frame_size(self.camera),
                                (primary_size[0], max(90, primary_size[1] - 180)))
        if size != tuple(self.preview.show_size):
            self.preview.setShowsize(size[1], size[0])

    def refresh_commands(self):
        classes = list(self.app.py_classes) + list(self.app.sample_py_classes)
        self.classes = {cls.NAME: cls for cls in classes}
        self.commands.configure(values=tuple(self.classes))

    def connect(self):
        if self.busy or self.connected or self.closing:
            return
        try:
            saved = copy.deepcopy(self.app._read_input_sets()["input_sets"][self.name.get()])
            camera = saved.get("camera", {})
            if camera.get("source_type", "Capture device") != "Capture device":
                raise ValueError("副画面はキャプチャ機器のInputSetを選択してください。")
            camera_id = resolve_companion_camera(camera, self.app.camera_dic or {})
            camera_key = self.app._camera_usage_key(camera_id=camera_id, source_type="Capture device")
            serial = saved.get("serial", {})
            port = str(serial.get("port", "")) if serial.get("enabled", False) else ""
            serial_key = canonical_device_key("serial", port) if port else ""
            for kind, key in (("camera", camera_key), ("serial", serial_key)):
                own = self.app._camera_usage_key() if kind == "camera" else self.app._serial_usage_key()
                if key and (key == own or self.app._device_conflicts(kind, key)):
                    raise ValueError("副画面の{}は他の画面で使用中です。".format(kind))
            if port:
                from serial.tools import list_ports
                matches = [p for p in list_ports.comports() if p.device.casefold() == port.casefold()]
                if len(matches) != 1:
                    raise ValueError("副画面のシリアル接続が見つかりません: " + port)
                for key in ("vid", "pid", "serial_number"):
                    if serial.get(key) not in (None, "") and serial[key] != getattr(matches[0], key):
                        raise ValueError("副画面のシリアル機器識別情報が一致しません。")
            self.settings = saved
            audio = saved.get("audio", {})
            self.audio_name = (self.app._resolve_audio_name(
                audio.get("device_name", ""), audio.get("normalized_name", ""), audio,
                camera.get("device_path", "")) or "") if audio.get("enabled", True) else ""
            if audio.get("enabled", True) and audio.get("device_name") and not self.audio_name:
                raise ValueError("副画面の保存済み音声入力を確認できません。InputSetを更新してください。")
            audio_key = self.app._audio_usage_key(self.audio_name) if self.audio_name else ""
            if audio_key and (audio_key == self.app._audio_usage_key()
                              or self.app._device_conflicts("audio", audio_key)):
                raise ValueError("副画面の音声入力は他の画面で使用中です。")
            self.sender.serial_data_format_name = normalize_serial_data_format_name(serial.get("data_format", "Default"))
            self.device_keys = {"camera": camera_key, "serial": serial_key, "audio": audio_key}
            for kind, key in self.device_keys.items():
                self.app._publish_device_usage(kind + "_secondary", key, self.name.get())
            self.busy = True
            self.connect_button.configure(state="disabled")
            self.inputs.configure(state="disabled")
            self.status.set("副画面を接続しています")
            def open_devices():
                try:
                    if not self.camera.openCamera(camera_id):
                        raise RuntimeError("副画面の映像を開けませんでした。")
                    if port and not self.sender.openSerial(0, port, int(serial.get("baud_rate", 9600))):
                        raise RuntimeError("副画面のシリアルを開けませんでした。")
                    self.events.put(("connected", None))
                except Exception as error:
                    self.camera.destroy()
                    if self.sender.ser is not None:
                        self.sender.closeSerial()
                    self.events.put(("connect_error", str(error)))
            threading.Thread(target=open_devices, daemon=True, name="CompanionConnect").start()
        except Exception as error:
            self.status.set(str(error))

    def start_command(self):
        if self.busy or self.closing or self.command_running():
            return
        if not self.connected or not self.sender.isOpened():
            self.status.set("副画面の映像とSerialを接続してください。")
            return
        self.refresh_commands()
        cls = self.classes.get(self.command_name.get())
        if cls is None:
            self.status.set("副画面のCommandsを選択してください。")
            return
        try:
            if issubclass(cls, ImageProcPythonCommand):
                import inspect
                signature = inspect.signature(cls)
                try:
                    signature.bind(self.camera, self.preview)
                except TypeError:
                    command = cls(self.camera)
                else:
                    command = cls(self.camera, self.preview)
            else:
                command = cls()
            bind_companion_command(command, self.camera, self.preview,
                                   self.output, self.text_output)
            self.command = command
            command.start(self.sender, lambda: self.events.put(("command_done", command)))
            self.status.set("副画面Commands実行中: " + command.NAME)
        except Exception as error:
            self.status.set("副画面Commands開始失敗: " + str(error))

    def command_running(self):
        worker = getattr(self.command, "thread", None)
        return worker is not None and worker.is_alive()

    def stop_command(self):
        if self.command_running():
            self.command.isPause = False
            self.command.pause_requested = False
            self.command.end(self.sender)

    def pause_command(self):
        if self.command_running():
            self.command.isPause = not self.command.isPause

    def controller(self):
        if self.connected and self.sender.isOpened() and not self.closing:
            self.controllers.append(ControllerGUI(self.root, self.sender))

    def output(self, panel, text=None, image=None, html_path=None):
        if text is not None:
            self.events.put(("log", str(text)))

    def text_output(self, panel, mode, text):
        self.events.put(("log", text))

    def presented(self, frame, sequence, presented_at):
        if self.recorder.active:
            self.recorder.add_frame(frame, presented_at=presented_at,
                                    presentation_mode="preview_presented")

    def toggle_recording(self):
        if self.busy or self.closing:
            return
        if self.recorder.active:
            self.busy = True
            self.status.set("副画面録画を保存しています")
            def stop_recording():
                try:
                    self.recorder.stop()
                    self.events.put(("record_stopped", None))
                except Exception as error:
                    self.events.put(("record_error", str(error)))
            threading.Thread(target=stop_recording, daemon=True, name="CompanionRecordStop").start()
            return
        frame = self.camera.readFrame()
        if frame is None:
            self.status.set("副画面の新しい映像がありません。")
            return
        # Use the same timestamped recorder and pitch-preserving AV correction
        # as Origin. A second pane never competes for speaker ownership.
        audio = self.settings.get("audio", {})
        self.recorder.output_dir = os.path.join(
            self.app.record_output_dir.get().strip() or "Recordings", "secondary")
        import shutil
        parent = os.path.abspath(self.recorder.output_dir)
        while not os.path.isdir(parent):
            parent = os.path.dirname(parent)
        usage = shutil.disk_usage(parent)
        if (usage.free < max(1.0, float(self.app.record_min_free_gb.get())) * 1024 ** 3
                or usage.used / usage.total * 100 >= float(self.app.record_max_disk_usage_percent.get())):
            self.status.set("副画面録画の保存先の空き容量が不足しています。")
            return
        try:
            self.recorder.start(frame, 30, self.audio_name, audio.get("gain", 100),
                                audio_level_options={
                                    "auto_level": audio.get("auto_level", False),
                                    "target_dbfs": audio.get("target_dbfs", -6),
                                    "max_auto_gain_percent": audio.get("max_auto_gain_percent", 200),
                                    "limiter_ceiling_dbfs": audio.get("limiter_ceiling_dbfs", -1)},
                                async_audio_start=True)
            self.record_button.configure(text="副画面録画停止")
            self.status.set("副画面録画中: " + self.recorder.session_dir)
        except Exception as error:
            self.status.set("副画面録画開始失敗: " + str(error))

    def record_both(self):
        if self.app.record_mode.get() != "Manual":
            self.status.set("主画面のRecordingをManualにしてから両方録画を開始してください。")
            return
        if not self.recorder.active:
            self.toggle_recording()
        if self.recorder.active and not self.app.recorder.active:
            self.app.toggle_recording()

    def capture_both(self):
        frames = (self.app.camera.readFrame(), self.camera.readFrame())
        if any(frame is None for frame in frames):
            self.status.set("両方の新しい映像が必要です。")
            return
        import datetime
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.app.camera.saveCapture(filename=stamp + "_main", img=frames[0])
        self.camera.capture_dir = self.app.camera.capture_dir
        self.camera.saveCapture(filename=stamp + "_secondary", img=frames[1])
        self.status.set("両方の取得解像度でスクリーンショットを保存しました。")

    def stop_both(self):
        if self.recorder.active and not self.busy:
            self.toggle_recording()
        if self.app.recorder.active:
            self.app.toggle_recording()

    def poll(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "connected":
                self.connected = True
                self.busy = False
                self.status.set("副画面接続済み: " + self.name.get())
            elif kind == "connect_error":
                self.busy = False
                for key in self.device_keys:
                    self.app._publish_device_usage(key + "_secondary", "", "")
                self.device_keys = {}
                self.inputs.configure(state="readonly")
                self.connect_button.configure(state="normal")
                self.status.set(value)
            elif kind == "log":
                self.log.configure(state="normal")
                self.log.insert("end", value + "\n")
                if int(self.log.index("end-1c").split(".")[0]) > 100:
                    self.log.delete("1.0", "50.0")
                self.log.see("end")
                self.log.configure(state="disabled")
            elif kind == "command_done":
                if value is self.command:
                    self.status.set("副画面Commands終了")
            elif kind in ("record_stopped", "record_error"):
                self.busy = False
                self.record_button.configure(text="副画面録画")
                self.status.set(value or "副画面AVI保存済み・MP4作成中")
                if kind == "record_error":
                    self.closing = False
        # A small preview target bounds rendering cost while the Camera reader
        # remains at 60 for fresh Commands image checks.
        desired = 30 if self.recorder.active else 15
        if self.preview._requested_fps != desired:
            self.preview.setFps(desired)
        self.preview.set_render_priority_provider(lambda: (True, False, False))
        self.fps_status.set("入力 {:.1f}fps / 表示 {:.1f}fps / 取得 {}×{}".format(
            self.camera.measuredFps(), self.preview.measuredPreviewFps(), *capture_frame_size(self.camera)))
        now = time.monotonic()
        if self.recorder.active and not self.busy and now >= self.disk_check_at:
            self.disk_check_at = now + 5
            import shutil
            try:
                usage = shutil.disk_usage(self.recorder.output_dir)
                if (usage.free < max(1.0, float(self.app.record_min_free_gb.get())) * 1024 ** 3
                        or usage.used / usage.total * 100 >= float(self.app.record_max_disk_usage_percent.get())):
                    self.toggle_recording()
                    self.status.set("保存先の容量上限に達したため副画面録画を終了しています。")
            except OSError as error:
                self.toggle_recording()
                self.status.set("保存先を確認できないため副画面録画を終了しています: " + str(error))
        if self.recorder.active and self.recorder.audio_start_error:
            self.status.set("副画面録画中・音声入力エラー: " + self.recorder.audio_start_error)
        if self.closing and not self.busy and not self.command_running() and not self.recorder.active:
            if not self.recorder.is_finalizing:
                self.finish_close()
                return
        self.poll_id = self.root.after(250, self.poll)

    def close(self):
        if self.closing:
            return
        if self.busy:
            self.status.set("接続／保存の完了を待ってから閉じてください。")
            return
        self.stop_command()
        if self.recorder.active:
            self.toggle_recording()
        self.closing = True
        self.status.set("副画面のCommands停止・録画保存を待っています")

    def finish_close(self):
        for controller in self.controllers:
            try:
                controller.window.destroy()
            except tk.TclError:
                pass
        self.preview.destroy()
        self.camera.destroy()
        if self.sender.ser is not None:
            self.sender.closeSerial()
        self.recorder.retire_finalize_worker()
        for kind in self.device_keys:
            self.app._publish_device_usage(kind + "_secondary", "", "")
        self.frame.destroy()
        self.app.companion_pane = None
        self.app.preview.grid_configure(columnspan=7, sticky=tk.NSEW)
        self.app.preview_sizing.schedule()


def open_companion(app):
    if getattr(app, "companion_pane", None) is None:
        app.companion_pane = CompanionPane(app)
        app.preview_sizing.enabled.set(True)
        app.preview_sizing.schedule()
