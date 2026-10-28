"""Embedded subscription repair requests and reload-free controller actions."""
import hashlib
import inspect
import json
import os
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import ttk
import uuid

from LiveAssistCommands import LiveCommandRegistry
from SubscriptionAgent import (DEFAULT_SETTINGS, EFFORTS, StallDetector, atomic_json,
    git_guard, normalize_settings, probe_codex, request_prompt, resolve_codex, run_request)


class AiAssistPanel(ttk.Frame):
    def __init__(self, parent, app, commands_parent):
        super().__init__(parent)
        self.app = app
        self.base = Path(__file__).resolve().parent / "AiAssist"
        self.workspace = self.base.parent.parent
        self.profile = None
        self.registry = None
        self.settings = dict(DEFAULT_SETTINGS)
        self.detector = StallDetector()
        self.busy = False
        self.cancelled = threading.Event()
        self.revision = 0
        self.latest = None
        self.slots = {}
        self.models = []
        self.request_binding = None
        self.request_activity = None
        self.vars = {}
        self.status = tk.StringVar(self, "Codex CLIにChatGPTでログイン → 接続確認 → モデルを選択 → 設定保存")
        self.operation = tk.StringVar(self)
        self.slot = tk.StringVar(self, "1")
        self.operation_name = tk.StringVar(self)
        self.operation_id = tk.StringVar(self)
        self._build()
        self._build_shortcuts(commands_parent)
        self.app.root.after(1000, self.tick)

    def _build(self):
        box = ttk.LabelFrame(self, text="無操作＋暗転の監視 / Codexへの修正依頼")
        box.pack(fill="x", padx=5, pady=4)
        for key, default in DEFAULT_SETTINGS.items():
            self.vars[key] = (tk.BooleanVar(self, default) if isinstance(default, bool)
                              else tk.StringVar(self, str(default)))
        checks = ttk.Frame(box)
        checks.pack(fill="x")
        for key, title in (("enabled", "監視を有効"), ("auto_send", "条件成立時に自動で修正依頼")):
            ttk.Checkbutton(checks, text=title, variable=self.vars[key], command=self.save).pack(side="left", padx=4)
        timing = ttk.Frame(box)
        timing.pack(fill="x", pady=3)
        for key, label in (("idle_seconds", "無操作 秒"), ("dark_seconds", "暗転 秒"),
                           ("brightness", "暗さ 1～100"), ("remaining_percent", "残り %以上")):
            ttk.Label(timing, text=label).pack(side="left", padx=3)
            ttk.Entry(timing, textvariable=self.vars[key], width=5).pack(side="left")
        agent = ttk.Frame(box)
        agent.pack(fill="x", pady=3)
        ttk.Label(agent, text="モデル").pack(side="left", padx=3)
        self.model_cb = ttk.Combobox(agent, textvariable=self.vars["model"], width=24, state="readonly")
        self.model_cb.pack(side="left", padx=3)
        self.model_cb.bind("<<ComboboxSelected>>", self.model_changed)
        ttk.Label(agent, text="思考量").pack(side="left")
        self.effort_cb = ttk.Combobox(agent, textvariable=self.vars["effort"], values=EFFORTS, width=10, state="readonly")
        self.effort_cb.pack(side="left", padx=3)
        ttk.Button(agent, text="接続・残量確認", command=self.probe).pack(side="left", padx=3)
        advanced = ttk.Frame(box)
        advanced.pack(fill="x", pady=3)
        ttk.Label(advanced, text="差分条件").pack(side="left", padx=3)
        self.clean_labels = {"対象Commandsがコミット済みと同じ": "command",
                             "リポジトリ全体に差分なし": "repository", "差分条件なし": "none"}
        self.clean = tk.StringVar(self, next(iter(self.clean_labels)))
        ttk.Combobox(advanced, textvariable=self.clean, values=list(self.clean_labels),
                     width=31, state="readonly").pack(side="left", padx=3)
        ttk.Label(advanced, text="再依頼間隔 秒").pack(side="left")
        ttk.Entry(advanced, textvariable=self.vars["cooldown_seconds"], width=6).pack(side="left", padx=3)
        cli = ttk.Frame(box)
        cli.pack(fill="x", pady=3)
        ttk.Label(cli, text="codex.exe（空欄で自動検出）").pack(side="left", padx=3)
        ttk.Entry(cli, textvariable=self.vars["cli"], width=32).pack(side="left", fill="x", expand=True, padx=3)
        ttk.Button(cli, text="設定保存", command=self.save).pack(side="left", padx=3)
        actions = ttk.Frame(box)
        actions.pack(fill="x", pady=3)
        for text, callback in (("現在の報告を作成", self.manual_report),
                               ("この報告を修正依頼", self.submit),
                               ("依頼文をコピー", self.copy_request), ("依頼を中止", self.cancel)):
            ttk.Button(actions, text=text, command=callback).pack(side="left", padx=3)
        ttk.Label(box, text="APIキー不要。契約の利用枠を使用。残量不明・差分条件不成立は保留。\n"
                  "追加クレジット／追加利用はアカウント側でOFFにしてください。自動再起動・自動ゲーム再開はしません。\n"
                  "Claude Codeを使う場合は依頼文をコピーして、契約ログイン済みのCLIへ渡せます。",
                  wraplength=690).pack(fill="x", padx=5, pady=3)
        ttk.Label(self, textvariable=self.status, width=85, wraplength=690,
                  foreground="#174a7e").pack(fill="x", padx=5, pady=4)
        operations = ttk.LabelFrame(self, text="AI作成の操作コマンド（再起動不要）")
        operations.pack(fill="x", padx=5, pady=4)
        ttk.Checkbutton(operations, text="専用フォルダーから自動登録を有効にする（実行は手動）",
                        variable=self.vars["allow_registration"], command=self.save).pack(anchor="w", padx=4)
        self.folder = tk.StringVar(self)
        ttk.Entry(operations, textvariable=self.folder, state="readonly").pack(fill="x", padx=4, pady=3)
        row = ttk.Frame(operations)
        row.pack(fill="x", pady=3)
        self.operations_cb = ttk.Combobox(row, textvariable=self.operation, state="readonly", width=32)
        self.operations_cb.pack(side="left", fill="x", expand=True, padx=3)
        self.operations_cb.bind("<<ComboboxSelected>>", self.load_operation)
        ttk.Button(row, text="実行", command=self.execute).pack(side="left", padx=3)
        ttk.Button(row, text="操作だけ停止", command=self.app._stop_command_recovery_script).pack(side="left", padx=3)
        ttk.Combobox(row, textvariable=self.slot, values=list(range(1, 11)), state="readonly", width=3).pack(side="left")
        ttk.Button(row, text="番号に追加", command=self.assign_slot).pack(side="left", padx=3)
        editor = ttk.Frame(operations)
        editor.pack(fill="x", padx=4)
        ttk.Label(editor, text="ID").pack(side="left")
        ttk.Entry(editor, textvariable=self.operation_id, width=18).pack(side="left", padx=3)
        ttk.Label(editor, text="名前").pack(side="left")
        ttk.Entry(editor, textvariable=self.operation_name, width=25).pack(side="left", padx=3)
        ttk.Button(editor, text="登録・更新", command=self.register).pack(side="left", padx=3)
        self.code = tk.Text(operations, height=5, width=65, undo=True)
        self.code.pack(fill="x", padx=4, pady=3)
        self.code.insert("1.0", "# 例: Bを1回\npress(Button.B, duration=0.1, wait=0.3)\n")
        ttk.Label(operations, text="press / press_rep / stick / wait / log / image_check、Button / Hat / Stickが使用可能。\n"
                  "登録しただけでは入力しません。実行中Commandsは既存の復旧処理で一時停止します。",
                  wraplength=670).pack(fill="x", padx=4, pady=3)
        ttk.Button(operations, text="この操作が一時停止したCommandsを再開",
                   command=lambda: self.app.resume_command_after_recovery(wait_for_visual=False)).pack(anchor="w", padx=4, pady=3)

    def _build_shortcuts(self, parent):
        self.shortcut_box = ttk.LabelFrame(parent, text="登録操作")
        self.shortcut_box.grid(row=3, column=0, sticky="ew", padx=5, pady=3)
        row = ttk.Frame(self.shortcut_box)
        row.pack(fill="x", padx=3, pady=2)
        self.quick_cb = ttk.Combobox(row, textvariable=self.operation, state="readonly", width=30)
        self.quick_cb.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="実行", command=self.execute).pack(side="left", padx=3)
        ttk.Button(row, text="AIアシストへ", command=lambda: self.app.controller_nb.select(self.app.ai_assist_tab)).pack(side="left")
        slots = ttk.Frame(self.shortcut_box)
        slots.pack(fill="x", padx=3, pady=2)
        self.slot_buttons = {}
        for number in range(1, 11):
            button = ttk.Button(slots, text=str(number), width=4,
                                command=lambda n=number: self.execute(slot=n))
            button.pack(side="left", padx=2)
            self.slot_buttons[str(number)] = button
        self.slot_hint = tk.StringVar(self)
        ttk.Label(self.shortcut_box, textvariable=self.slot_hint, width=65, wraplength=650).pack(fill="x", padx=4)

    def bind_profile(self):
        profile = str(getattr(self.app, "_active_input_set_name", "") or "未選択")
        if profile == self.profile:
            return
        self.cancelled.set()
        self.revision += 1
        self.profile = profile
        self.profile_dir = self.base / "profiles" / hashlib.sha256(profile.encode("utf-8")).hexdigest()[:20]
        self.registry = LiveCommandRegistry(self.profile_dir / "commands")
        self.folder.set(str(self.registry.directory))
        self.latest, self.slots, self.models = None, {}, []
        try:
            data = json.loads((self.profile_dir / "settings.json").read_text(encoding="utf-8"))
            self.settings = normalize_settings(data.get("settings", {}))
            self.slots = {str(k): str(v) for k, v in data.get("slots", {}).items() if str(k) in map(str, range(1, 11))}
        except (OSError, ValueError, AttributeError, TypeError):
            self.settings = dict(DEFAULT_SETTINGS)
        for key, value in self.settings.items():
            self.vars[key].set(value)
        self.clean.set(next(label for label, value in self.clean_labels.items() if value == self.settings["clean_scope"]))
        self.detector = StallDetector()
        self.refresh_operations()

    def save(self):
        self.bind_profile()
        try:
            raw = {key: var.get() for key, var in self.vars.items()}
            raw["clean_scope"] = self.clean_labels[self.clean.get()]
            settings = normalize_settings(raw)
            if settings["auto_send"] and not settings["model"]:
                raise ValueError("自動依頼には接続確認後にモデルを選択してください")
            if settings != self.settings:
                self.settings = settings
                self.revision += 1
                self.cancelled.set()  # Pending requests must not use superseded settings.
            self.persist()
            self.status.set("設定を保存しました: " + self.profile)
            self.refresh_operations()
            return True
        except (ValueError, OSError, tk.TclError) as error:
            for key in ("enabled", "auto_send", "allow_registration"):
                self.vars[key].set(self.settings[key])
            self.status.set(str(error))
            return False

    def persist(self):
        atomic_json(self.profile_dir / "settings.json", {"profile": self.profile,
                    "settings": self.settings, "slots": self.slots})

    def background(self, task, finish):
        if self.busy:
            self.status.set("現在の処理が完了してから再実行してください")
            return False
        self.busy = True
        revision, profile = self.revision, self.profile
        def worker():
            try:
                result, error = task(), None
            except Exception as exc:
                result, error = None, str(exc)
            def complete():
                self.busy = False
                if profile != self.profile or revision != self.revision:
                    return
                if error:
                    self.status.set(error)
                else:
                    finish(result)
            self.app._gui_action_queue.put(complete)
        threading.Thread(target=worker, daemon=True, name="PokeConAiAssist").start()
        return True

    def probe(self):
        self.bind_profile()
        if self.busy:
            self.status.set("現在の依頼／確認処理が完了してから再実行してください")
            return
        executable = self.vars["cli"].get()
        self.status.set("契約ログイン・残量・モデル一覧を確認中…")
        def done(value):
            self.models = value["models"]
            choices = [item["model"] for item in self.models]
            self.model_cb.configure(values=choices)
            if self.vars["model"].get() not in choices and choices:
                default = next((item["model"] for item in self.models if item.get("isDefault")), choices[0])
                self.vars["model"].set(default)
            self.model_changed()
            self.status.set("ChatGPT契約を確認。各枠の残りの最小値 {:.1f}% / モデル選択後に設定保存".format(value["remaining"]))
        self.background(lambda: probe_codex(resolve_codex(executable), self.workspace), done)

    def model_changed(self, *_):
        model = next((item for item in self.models if item.get("model") == self.vars["model"].get()), {})
        choices = [item["reasoningEffort"] for item in model.get("supportedReasoningEfforts", [])]
        self.effort_cb.configure(values=choices or EFFORTS)
        if choices and self.vars["effort"].get() not in choices:
            self.vars["effort"].set(model.get("defaultReasoningEffort", choices[0]))

    def frame_sample(self):
        camera = getattr(self.app, "camera", None)
        frame = camera.readFrame() if camera is not None else None
        if frame is None or getattr(frame, "size", 0) == 0:
            return None, None, None
        sample = frame[::max(1, frame.shape[0] // 60), ::max(1, frame.shape[1] // 100)]
        import numpy as np
        if sample.ndim == 3:
            gray = sample[:, :, :3].astype(np.float32).mean(axis=2)
        else:
            gray = sample
        return frame, float(gray.mean()), float((gray <= self.settings["brightness"]).mean())

    def snapshot(self, detection):
        command = getattr(self.app, "cur_command", None)
        if command is None:
            raise ValueError("対象Commandsがありません。Commandsを選択・読み込みしてください")
        source = inspect.getsourcefile(type(command))
        if not source:
            raise ValueError("対象Commandsのソースを特定できません")
        quick = getattr(self.app, "command_quick_run", None)
        location = quick.current() if quick is not None else None
        from CommandMonitorRecording import runtime_execution_snapshot
        runtime = runtime_execution_snapshot(command, str(self.workspace))
        log_reader = getattr(self.app, "_record_log_lines", None)
        logs = list(log_reader(80)) if callable(log_reader) else []
        return {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "input_set": self.profile,
                "run_id": [id(command), id(getattr(command, "thread", None))],
                "command": str(getattr(command, "NAME", "")), "source": os.path.abspath(source),
                "workspace": str(self.workspace), "location": location, "runtime": runtime,
                "log_tail": logs,
                "detection": detection, "runtime_paused": bool(getattr(command, "pause_requested", False)),
                "recording_session": str(getattr(self.app, "_command_monitor_session_dir", "")),
                "note": "Stepは観測値。ソースSHAは報告時のディスク上のファイルでありロード済みコードの証明ではありません。"}

    def make_report(self, detection, frame=None, automatic=False):
        try:
            incident = self.snapshot(detection)
        except (ValueError, TypeError) as error:
            self.status.set(str(error))
            return
        settings = dict(self.settings)
        incident["automatic"] = bool(automatic)
        directory = self.profile_dir / "reports" / (time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8])
        registration_dir = str(self.registry.directory) if settings["allow_registration"] else ""
        captured = frame.copy() if frame is not None else None
        self.status.set("不具合候補の報告を保存中…")
        def task():
            directory.mkdir(parents=True, exist_ok=True)
            incident["source_sha256"] = hashlib.sha256(Path(incident["source"]).read_bytes()).hexdigest()
            try:
                incident["git"] = git_guard(self.workspace, incident["source"], settings["clean_scope"])
            except ValueError as error:
                incident["git_block"] = str(error)
            if captured is not None:
                import cv2
                ok, data = cv2.imencode(".png", captured)
                if ok:
                    image_path = directory / "screen.png"
                    image_path.write_bytes(data.tobytes())
                    incident["image"] = str(image_path)
            atomic_json(directory / "incident.json", incident)
            (directory / "request.txt").write_text(request_prompt(incident, registration_dir), encoding="utf-8")
            return incident
        def done(value):
            self.latest = (value, directory)
            self.status.set("報告を保存: " + str(directory) + (" / " + value["git_block"] if value.get("git_block") else ""))
            if automatic and settings["auto_send"]:
                self.submit(save=False)
        self.background(task, done)

    def manual_report(self):
        if self.save():
            frame, brightness, ratio = self.frame_sample()
            self.make_report({"manual": True, "brightness": brightness, "dark_ratio": ratio}, frame)

    def submit(self, save=True):
        if self.busy:
            self.status.set("依頼／確認処理中です")
            return
        if save and not self.save():
            return
        if not self.latest:
            self.status.set("先に報告を作成してください")
            return
        incident, directory = self.latest
        command = getattr(self.app, "cur_command", None)
        binding = [id(command), id(getattr(command, "thread", None))]
        if incident.get("run_id") != binding:
            self.status.set("対象Commandsの実行が変わりました。報告を作り直してください")
            return
        if incident.get("automatic"):
            _frame, brightness, ratio = self.frame_sample()
            if (brightness is None or ratio is None or ratio < .9
                    or brightness > self.settings["brightness"]
                    or time.monotonic() - self.detector.last_input < self.settings["idle_seconds"]
                    or not getattr(command, "alive", False)):
                self.status.set("無操作＋暗転の条件が解消したため、報告保存のみで依頼を保留しました")
                return
        if incident.get("git_block") and self.settings["clean_scope"] != "none":
            self.status.set(incident["git_block"] + "。報告を作り直してください")
            return
        if (directory / "dispatch.json").exists():
            self.status.set("この報告は依頼済みです。cli.log / result.txtを確認してください")
            return
        self.cancelled = threading.Event()
        self.request_binding = binding
        self.request_activity = self.detector.last_input if incident.get("automatic") else None
        token, settings = self.cancelled, dict(self.settings)
        registration_dir = str(self.registry.directory) if settings["allow_registration"] else ""
        self.status.set("残量・差分を再確認してCodexに修正依頼中…")
        self.background(lambda: run_request(settings, incident, directory, registration_dir, token),
                        lambda path: self.status.set("修正依頼が完了: " + path + " / 反映・実機確認は別途必要です"))

    def copy_request(self):
        if not self.require_current_profile():
            return
        if not self.latest:
            self.status.set("先に報告を作成してください")
            return
        self.clipboard_clear()
        self.clipboard_append((self.latest[1] / "request.txt").read_text(encoding="utf-8"))
        self.status.set("依頼文をコピーしました。契約でログイン済みのCodex / Claude Codeへ貼り付けできます")

    def cancel(self):
        self.cancelled.set()
        self.status.set("依頼の停止を要求しました。途中の変更は保存済みの場合があります")

    def refresh_operations(self):
        if self.registry is None:
            return
        values = [item["name"] for item in self.registry.items.values()] if self.settings["allow_registration"] else []
        self.operations_cb.configure(values=values)
        self.quick_cb.configure(values=values)
        if self.operation.get() not in values:
            self.operation.set(values[0] if values else "")
        for slot, button in self.slot_buttons.items():
            item = self.registry.items.get(self.slots.get(slot, ""))
            enabled = bool(item and self.settings["allow_registration"])
            button.configure(state="normal" if enabled else "disabled")
        self.slot_hint.set(" / ".join("{}: {}".format(slot, self.registry.items[key]["name"])
                                      for slot, key in sorted(self.slots.items(), key=lambda pair: int(pair[0]))
                                      if key in self.registry.items))

    def selected_operation(self):
        return next((item for item in self.registry.items.values() if item["name"] == self.operation.get()), None)

    def require_current_profile(self):
        previous = self.profile
        self.bind_profile()
        if previous != self.profile:
            self.status.set("InputSetが変わりました。対象と操作を確認して再実行してください")
            return False
        return True

    def load_operation(self, *_):
        item = self.selected_operation()
        if item:
            self.operation_id.set(item["id"])
            self.operation_name.set(item["name"])
            self.code.delete("1.0", "end")
            self.code.insert("1.0", item["code"])

    def register(self):
        if not self.require_current_profile():
            return
        try:
            self.registry.register(self.operation_id.get().strip(), self.operation_name.get(), self.code.get("1.0", "end-1c"))
            self.refresh_operations()
            self.status.set("登録しました。自動登録を有効にするとプルダウン／番号へ追加できます")
        except (ValueError, OSError, SyntaxError) as error:
            self.status.set(str(error))

    def assign_slot(self):
        if not self.require_current_profile():
            return
        item = self.selected_operation()
        if item:
            self.slots[self.slot.get()] = item["id"]
            self.persist()
            self.refresh_operations()
            self.status.set("番号{}: {}".format(self.slot.get(), item["name"]))

    def execute(self, slot=None):
        if not self.require_current_profile():
            return False
        if not self.settings["allow_registration"]:
            self.status.set("操作コマンド登録を有効にしてください")
            return False
        # Keep the clicked ID even if a hot update removes the selected item.
        # Refreshing the dropdown may select a different default; never run it.
        selected = self.selected_operation()
        key = self.slots.get(str(slot), "") if slot else (selected or {}).get("id", "")
        try:
            self.registry.scan(force=True)  # Revalidate current bytes before every execution.
        except OSError as error:
            self.status.set("操作ファイルを再確認できません: " + str(error))
            return False
        self.refresh_operations()
        item = self.registry.items.get(key)
        if not item:
            self.status.set("登録された操作が見つかりません")
            return False
        self.app._command_recovery_context_command = getattr(self.app, "cur_command", None)
        accepted = self.app._run_command_recovery_script(item["code"], auto_resume=False)
        self.status.set("操作を実行中: " + item["name"] if accepted else "操作を開始できませんでした")
        return accepted

    def tick(self):
        try:
            if getattr(self.app, "_preview_shutdown_mode", False):
                self.cancelled.set()
                return
            self.bind_profile()
            command = getattr(self.app, "cur_command", None)
            if self.request_binding and self.request_binding != [id(command), id(getattr(command, "thread", None))]:
                self.cancelled.set()
                self.request_binding = None
            if self.busy and self.request_activity is not None and self.detector.last_input > self.request_activity:
                self.cancelled.set()
                self.request_activity = None
            quick = getattr(self.app, "command_quick_run", None)
            if quick is not None:
                current = quick.current()
                if (current or {}).get("id") != quick._display_current_id:
                    quick.refresh_choices()
            if self.settings["allow_registration"] and self.registry.scan():
                self.refresh_operations()
                self.status.set("操作一覧を更新しました" + (" / " + self.registry.errors[0] if self.registry.errors else ""))
            command = getattr(self.app, "cur_command", None)
            worker = getattr(command, "thread", None)
            running = bool(worker is not None and worker.is_alive() and getattr(command, "alive", False)
                           and not getattr(command, "pause_requested", False)
                           and not getattr(command, "isPause", False))
            if self.settings["enabled"] and not self.busy:
                frame, brightness, ratio = self.frame_sample()
                incident = self.detector.check((self.profile, id(command), id(worker)), running,
                                               brightness, ratio, self.settings)
                if incident and not self.busy:
                    self.make_report(incident, frame, automatic=True)
        except Exception as error:
            self.status.set("AIアシスト: " + str(error))
        self.app.root.after(1000, self.tick)
