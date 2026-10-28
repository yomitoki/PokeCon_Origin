"""Configure local highlights independently of the normal recording/upload."""
import copy
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from EventClips import snapshot_rule, export_event_clips, za_field_hard_targets
from ImageDetectionMonitor import load_detection_library


class EventClipWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("条件クリップ — 全体動画のアップロードとは別に保存")
        self.window.geometry("900x640")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.closed = False
        self.library = load_detection_library(app._image_detection_monitor_profile_path())
        saved = copy.deepcopy(getattr(app, "event_clip_rule", {}) or {})
        self.enabled = tk.BooleanVar(value=saved.get("enabled", False))
        ttk.Checkbutton(self.window, text="全体動画のYouTubeアップロード前に、条件部分をローカル保存する",
                        variable=self.enabled).pack(anchor="w", padx=12, pady=8)
        ttk.Label(self.window, text="完成MP4の補正済み音声を使います。FIELD／HARDチェックは登録画像をANDで組み合わせて設定できます。\n"
                  "ZA HARDは同じフレームの画像条件です。実機での連続確認は実行しません。継続秒は別途指定できます。\n"
                  "解析間隔の間にしか出ない短い表示は検出できません。0秒なら全フレームを確認します。",
                  wraplength=860).pack(anchor="w", padx=12)
        self.groups = []
        groups = ttk.Frame(self.window)
        groups.pack(fill="both", expand=True, padx=10, pady=8)
        for index in range(2):
            frame = ttk.LabelFrame(groups, text=("① 最初の条件" if index == 0 else "② その後の条件（空なら①のみ）"))
            frame.pack(side="left", fill="both", expand=True, padx=3)
            stage = (saved.get("stages", []) + [{}, {}])[index]
            operator = tk.StringVar(value=stage.get("operator", "AND"))
            stable = tk.StringVar(value=str(stage.get("stable_seconds", 0)))
            row = ttk.Frame(frame)
            row.pack(fill="x")
            ttk.Combobox(row, textvariable=operator, values=("AND", "OR"), state="readonly", width=6).pack(side="left")
            ttk.Label(row, text="継続秒:").pack(side="left")
            ttk.Entry(row, textvariable=stable, width=7).pack(side="left")
            target = tk.StringVar()
            chooser = ttk.Combobox(frame, textvariable=target, values=tuple(sorted(self.library["targets"])), width=44)
            chooser.pack(fill="x")
            choices = tk.Listbox(frame, height=7, exportselection=False)
            scrollbar = ttk.Scrollbar(frame, orient="vertical", command=choices.yview)
            choices.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")
            choices.pack(fill="both", expand=True)
            group = {"operator": operator, "stable": stable, "target": target,
                     "list": choices, "targets": copy.deepcopy(stage.get("targets", []))}
            self.groups.append(group)
            buttons = ttk.Frame(frame)
            buttons.pack(fill="x")
            ttk.Button(buttons, text="登録画像を追加", command=lambda g=group: self.add_target(g)).pack(side="left")
            ttk.Button(buttons, text="PNG追加", command=lambda g=group: self.add_png(g)).pack(side="left")
            ttk.Button(buttons, text="一致／不一致", command=lambda g=group: self.invert(g)).pack(side="left")
            ttk.Button(buttons, text="削除", command=lambda g=group: self.remove(g)).pack(side="left")
            ttk.Button(buttons, text="ZA HARD", command=lambda g=group: self.add_hard(g)).pack(side="left")
            self.refresh(group)
        options = ttk.Frame(self.window)
        options.pack(fill="x", padx=12)
        self.values = {}
        for index, (key, label, default) in enumerate((
                ("within_seconds", "①→②の制限秒", 30), ("pre_seconds", "成立前の秒数", 5),
                ("post_seconds", "成立後の秒数", 5), ("interval_seconds", "解析間隔秒", .1),
                ("cooldown_seconds", "再検出間隔秒", 5), ("max_total_gb", "保存先上限GB", 10))):
            value = tk.StringVar(value=str(saved.get(key, default)))
            self.values[key] = value
            ttk.Label(options, text=label).grid(row=index // 3, column=(index % 3) * 2, padx=4, pady=5)
            ttk.Entry(options, textvariable=value, width=9).grid(row=index // 3, column=(index % 3) * 2 + 1)
        self.output_dir = tk.StringVar(value=saved.get("output_dir", ""))
        row = ttk.Frame(self.window)
        row.pack(fill="x", padx=12, pady=8)
        ttk.Label(row, text="条件クリップ専用保存先:").pack(side="left")
        ttk.Entry(row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="参照…", command=self.choose_directory).pack(side="left")
        ttk.Label(self.window, text="画像検知の登録元に使えるよう、元の解像度・画素を保つ可逆圧縮で保存します（容量は増えます）。\n"
                  "保存上限に達した場合は既存クリップを残して新規保存を停止します。全体動画は通常どおりアップロードします。",
                  wraplength=860).pack(anchor="w", padx=12)
        row = ttk.Frame(self.window)
        row.pack(fill="x", padx=12, pady=8)
        ttk.Button(row, text="設定を適用・保存", command=self.save).pack(side="left")
        ttk.Button(row, text="完成動画を選んで解析・保存", command=self.export).pack(side="left", padx=8)
        ttk.Button(row, text="解析を中止", command=self.cancel.set).pack(side="left")
        self.status = tk.StringVar(value="前後秒数は②（②なしなら①）の成立時刻が基準です。重なる区間は1本にまとめます。")
        ttk.Label(self.window, textvariable=self.status, wraplength=860).pack(anchor="w", padx=12, pady=5)
        self.poll_id = self.window.after(200, self.poll)

    def refresh(self, group):
        group["list"].delete(0, "end")
        for target in group["targets"]:
            prefix = "一致: " if target.get("expected", True) else "不一致: "
            group["list"].insert("end", prefix + target.get("name", "画像") + " (" + target.get("operator", "OR") + ")")

    def invert(self, group):
        for index in group["list"].curselection():
            target = group["targets"][index]
            target["expected"] = not target.get("expected", True)
        self.refresh(group)

    def add_hard(self, group):
        if group["targets"]:
            self.status.set("ZA HARDは空の条件グループへ追加してください。既存の条件は残しています。")
            return
        try:
            group["targets"] = za_field_hard_targets(self.library)
            group["operator"].set("AND")
            self.refresh(group)
            self.status.set("ZA非戦闘HARDの画像組み合わせを追加しました。継続秒と前後秒数も設定できます。")
        except ValueError as error:
            self.status.set(str(error))

    def add_target(self, group):
        name = group["target"].get()
        target = self.library["targets"].get(name)
        if target:
            target = copy.deepcopy(target)
            target["name"] = name
            group["targets"].append(target)
            self.refresh(group)

    def add_png(self, group):
        path = filedialog.askopenfilename(parent=self.window, filetypes=[("画像", "*.png *.jpg *.jpeg")])
        if path:
            group["targets"].append({"name": os.path.basename(path), "operator": "OR", "variants": [
                {"template_path": path, "threshold": .9, "use_gray": False, "crop": []}]})
            self.refresh(group)

    def remove(self, group):
        for index in reversed(group["list"].curselection()):
            group["targets"].pop(index)
        self.refresh(group)

    def choose_directory(self):
        path = filedialog.askdirectory(parent=self.window)
        if path:
            self.output_dir.set(path)

    def rule(self, validate_images=True):
        output = self.output_dir.get().strip()
        if not output and validate_images:
            raise ValueError("条件クリップ専用の保存先を指定してください。")
        stages = [{"operator": group["operator"].get(), "stable_seconds": float(group["stable"].get()),
                   "targets": copy.deepcopy(group["targets"])} for group in self.groups]
        if not stages[1]["targets"]:
            stages.pop()
        rule = {key: float(value.get()) for key, value in self.values.items()}
        rule.update({"enabled": self.enabled.get(), "output_dir": os.path.abspath(output) if output else "", "stages": stages})
        return snapshot_rule(rule, os.path.dirname(__file__)) if validate_images else rule

    def save(self):
        try:
            # Disabling automatic exports must work even if an image/drive
            # was removed. Manual exports still validate the complete rule.
            rule = self.rule(validate_images=self.enabled.get())
            self.app.settings.save_event_clip_rule(json.dumps(rule, ensure_ascii=False))
            self.app.event_clip_rule = rule
            # Same live setting is included in _recording_preset_data for
            # InputSet/recording sets; explicit set-save retains its semantics.
            self.status.set("設定保存済み。次のアップロード予約から反映します。InputSet／録画セットの保存にも含まれます。")
        except Exception as error:
            self.status.set(str(error))

    def export(self):
        if self.worker is not None and self.worker.is_alive():
            return
        try:
            rule = self.rule()
        except Exception as error:
            self.status.set(str(error))
            return
        path = filedialog.askopenfilename(parent=self.window, filetypes=[("完成動画", "*.mp4")])
        if not path:
            return
        self.cancel.clear()
        def work():
            try:
                from Recording import set_current_thread_below_normal
                set_current_thread_below_normal()
                result = export_event_clips(path, rule, cancel=self.cancel, progress=self.events.put)
                self.events.put("完了: {}本保存 / 容量上限で{}区間見送り / {}".format(
                    len(result["clips"]), len(result.get("skipped_capacity", [])), result.get("manifest", rule["output_dir"])))
            except Exception as error:
                self.events.put("解析・保存を完了できませんでした: " + str(error))
        self.worker = threading.Thread(target=work, daemon=True, name="EventClipExport")
        self.worker.start()

    def poll(self):
        while not self.events.empty():
            self.status.set(self.events.get_nowait())
        if not self.closed:
            self.poll_id = self.window.after(200, self.poll)

    def close(self):
        if self.closed:
            return
        self.cancel.set()
        if self.worker is not None and self.worker.is_alive():
            self.status.set("解析を中止しています。保存処理の終了を待っています。")
            self.window.after(100, self.close)
            return
        self.closed = True
        self.window.after_cancel(self.poll_id)
        self.window.destroy()
        self.app.event_clip_window = None


def open_event_clips(app):
    if getattr(app, "event_clip_window", None) is None:
        app.event_clip_window = EventClipWindow(app)
