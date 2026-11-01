"""Embedded Step picker. No modal dialogs, constructors or controller I/O."""
import copy
import queue
import threading
import tkinter as tk
from tkinter import ttk

from CommandRunOptions import apply_command_run_options


CURRENT = "現在のStep（開始時に確定）"
FIRST = "先頭から"
DEFAULT = "Commands既定"
FRESH = "タイトル→はじめから実行"


def location_choices(locations, current=None, radius=3, all_steps=False):
    """Keep current neighbours in the same public state table/Step sequence."""
    locations = list(locations)
    if all_steps or not current:
        return locations
    group = [item for item in locations if item.get("variable") == current.get("variable")]
    index = next((n for n, item in enumerate(group) if item.get("id") == current.get("id")), None)
    return group[max(0, index - radius):index + radius + 1] if index is not None else locations


def observed_location(command, locations):
    if command is None:
        return None
    worker = getattr(command, "thread", None)
    if not getattr(command, "alive", False) and getattr(worker, "ident", None) is None:
        return None
    vision = getattr(command, "_vision_current_state", None)
    if vision:
        found = next((item for item in locations if item.get("value") == vision), None)
        if found:
            return found
    from CommandMonitorRecording import runtime_state_snapshot, relevant_state_path
    path = relevant_state_path(runtime_state_snapshot(command))
    return next((item for value in reversed(path) for item in locations
                 if str(item.get("value")) == value), None)


PANEL_PLACES = (("tab", "Commandsタブに表示（AI操作向け）"),
                ("dialog", "Startを押した時に表示（従来のPokeCon）"))


class CommandQuickRun(ttk.LabelFrame):
    def __init__(self, parent, app, host=None):
        super().__init__(parent, text="開始位置・その他の操作")
        # host: CommandStartPanelHost。"dialog" の時はこの欄は Start を押した時の画面に入る
        self.host, self._dialog_accepted = host, False
        self.app, self.name, self.locations = app, "", []
        self.options, self.last_location, self.prepared = {}, {}, None
        self._display_current_id = None
        self.profile = None
        self.observed_command, self.observed_profile = None, None
        self.choice = tk.StringVar(self, CURRENT)
        self.scope = tk.StringVar(self, "前後3Step")
        self.search = tk.StringVar(self)
        self.status = tk.StringVar(self, "現在のStepが未取得のときはCommands既定で開始")
        self.end = tk.StringVar(self, "終了指定なし")
        self.debug_vars = {}
        self.retry = tk.BooleanVar(self, False)
        self.retry_count = tk.StringVar(self, "1")
        self.delete_user = tk.StringVar(self, "0")
        self.favorite = tk.StringVar(self)
        self.delete_authorization = None
        self.collect = tk.BooleanVar(self, False)
        self.supplemental = tk.BooleanVar(self, False)
        self.language = tk.StringVar(self)
        # Commands may declare extra start modes (COMMAND_RUN_MODES). Each mode is
        # a tab next to the normal Story start; Start follows the selected tab.
        self.mode = tk.StringVar(self, "")
        self.mode_panels, self.mode_specs = {}, {}
        self.prepared_mode, self.mode_authorization = None, None
        self.mode_bar = ttk.Frame(self)
        self.story_frame = ttk.Frame(self)
        self.story_frame.pack(fill="x")
        row = ttk.Frame(self.story_frame)
        row.pack(fill="x", padx=5, pady=3)
        ttk.Label(row, text="開始").pack(side="left")
        self.start_cb = ttk.Combobox(row, textvariable=self.choice, state="readonly", width=38)
        self.start_cb.pack(side="left", fill="x", expand=True, padx=4)
        self.start_cb.bind("<<ComboboxSelected>>", self.describe)
        scope = ttk.Combobox(row, textvariable=self.scope, state="readonly", width=10,
                             values=("前後3Step", "全Step"))
        scope.pack(side="left", padx=3)
        scope.bind("<<ComboboxSelected>>", lambda *_: self.refresh_choices())
        ttk.Button(row, text="オプション", width=10, command=self.toggle_options).pack(side="left")
        self.option_frame = ttk.Frame(self.story_frame)
        filters = ttk.Frame(self.option_frame)
        filters.pack(fill="x")
        ttk.Label(filters, text="Step検索").pack(side="left")
        ttk.Entry(filters, textvariable=self.search, width=24).pack(side="left", padx=3)
        ttk.Label(filters, text="終了").pack(side="left")
        self.end_cb = ttk.Combobox(filters, textvariable=self.end, state="readonly", width=30)
        self.end_cb.pack(side="left", fill="x", expand=True, padx=3)
        self.debug_frame = ttk.Frame(self.option_frame)
        self.debug_frame.pack(fill="x", pady=2)
        recovery = ttk.Frame(self.option_frame)
        recovery.pack(fill="x", pady=2)
        self.retry_widget = ttk.Checkbutton(recovery, text="失敗時に再実行", variable=self.retry)
        self.retry_widget.pack(side="left")
        ttk.Label(recovery, text="上限回数").pack(side="left")
        ttk.Entry(recovery, textvariable=self.retry_count, width=4).pack(side="left", padx=3)
        ttk.Label(recovery, text="セーブ削除ユーザー番号（0=無効）").pack(side="left")
        self.delete_widget = ttk.Combobox(recovery, textvariable=self.delete_user, width=3,
                                          values=list(range(9)), state="readonly")
        self.delete_widget.pack(side="left", padx=3)
        favorites = ttk.Frame(self.option_frame)
        favorites.pack(fill="x", pady=2)
        ttk.Label(favorites, text="お気に入り名").pack(side="left")
        self.favorite_cb = ttk.Combobox(favorites, textvariable=self.favorite, width=24)
        self.favorite_cb.pack(side="left", padx=3)
        for text, action in (("登録・更新", self.save_favorite), ("呼出", self.load_favorite), ("削除", self.delete_favorite)):
            ttk.Button(favorites, text=text, command=action).pack(side="left", padx=2)
        native = ttk.Frame(self.option_frame)
        native.pack(fill="x", pady=2)
        ttk.Checkbutton(native, text="今回のみ画像収集", variable=self.collect).pack(side="left")
        ttk.Checkbutton(native, text="今回のみ補足画像チェック", variable=self.supplemental).pack(side="left")
        ttk.Label(native, text="言語").pack(side="left")
        ttk.Entry(native, textvariable=self.language, width=12).pack(side="left")
        ttk.Button(self.option_frame, text="オプションをInputSetへ保存", command=self.save_options).pack(anchor="w")
        self.status_label = ttk.Label(self, textvariable=self.status, width=65, wraplength=650)
        self.status_label.pack(fill="x", padx=5, pady=3)
        self.confirmation = ttk.Frame(self)
        self.confirm_text = tk.StringVar(self)
        ttk.Label(self.confirmation, textvariable=self.confirm_text, wraplength=620).pack(fill="x")
        self.confirm_button = ttk.Button(self.confirmation, text="内容を確認して実行")
        self.confirm_button.pack(side="left", padx=4)
        ttk.Button(self.confirmation, text="キャンセル", command=self.confirmation.pack_forget).pack(side="left")
        self.search.trace_add("write", lambda *_: self.refresh_choices())

    def toggle_options(self):
        if self.option_frame.winfo_manager():
            self.option_frame.pack_forget()
        else:
            self.option_frame.pack(fill="x", padx=5, pady=3)

    def reveal(self, box, focus=None):
        """Scroll the Commands page so an embedded prompt is visible.

        These prompts are packed at the bottom of a scrolling page; when they
        were off-screen, Start looked unresponsive while waiting for them.
        """
        try:
            canvas = box.master
            while canvas is not None and not isinstance(canvas, tk.Canvas):
                canvas = canvas.master
            if canvas is not None:
                canvas.update_idletasks()
                content = canvas.nametowidget(canvas.itemcget(canvas.find_all()[0], "window"))
                total = max(1, content.winfo_height())
                # Prefer the action button: a tall preview image can push it out of view.
                target = focus if focus is not None else box
                top = target.winfo_rooty() - content.winfo_rooty() - max(0, canvas.winfo_height() - target.winfo_height() - 8)
                canvas.yview_moveto(max(0.0, min(1.0, top / float(total))))
            if focus is not None:
                focus.focus_set()
        except (tk.TclError, IndexError, KeyError):
            pass

    def _in_dialog(self):
        return self.host is not None and self.host.dialog_mode()

    def _problem(self, text):
        """開始できない理由を表示する（Start時の画面なら画面を出して見せる）。"""
        self.status.set(text)
        if self._in_dialog():
            self.host.show_dialog()
        return False

    def confirm(self, message, action):
        self.confirm_text.set(message)
        def accepted():
            self.confirmation.pack_forget()
            # 確認済みの Start では、Start時の画面を出し直さない
            self._dialog_accepted = True
            if self._in_dialog():
                self.host.hide_dialog()
            action()
        self.confirm_button.configure(command=accepted)
        self.confirmation.pack(fill="x", padx=5, pady=4)
        if self._in_dialog():
            self.host.show_dialog()
        self.after_idle(lambda: self.reveal(self.confirmation, self.confirm_button))

    def refresh(self, force=False):
        name = self.app._selected_command_name()
        profile = str(getattr(self.app, "_active_input_set_name", "") or "")
        if name == self.name and profile == self.profile and not force:
            return
        self.name, self.profile = name, profile
        self.options = self.app._command_run_options(name) if name else {}
        self.locations = list(self.options.get("locations", []))
        self.choice.set(CURRENT)
        self.collect.set(False)
        self.supplemental.set(False)
        saved = self.app.command_start_overrides.get(name, {})
        available = bool(self.options.get("save_recovery", {}).get("available"))
        self.retry.set(bool(available and saved.get("retry_on_failure", False)))
        self.retry_count.set(str(saved.get("max_retries", 1)))
        self.delete_user.set(str(saved.get("save_delete_user_number", 0) if available else 0))
        self.retry_widget.configure(state="normal" if available else "disabled")
        self.delete_widget.configure(state="readonly" if available else "disabled")
        self.refresh_favorites()
        for child in self.debug_frame.winfo_children():
            child.destroy()
        self.debug_vars = {}
        for item in self.options.get("debug_options", []):
            key = item.get("attribute", "")
            if not key:
                continue
            var = tk.BooleanVar(self, saved.get("debug", {}).get(key, item.get("default", False)))
            self.debug_vars[key] = var
            ttk.Checkbutton(self.debug_frame, text=item.get("label", key), variable=var).pack(side="left", padx=3)
        self.end.set(next((self.display(item) for item in self.locations
                           if item.get("id") == (saved.get("end") or {}).get("id")), "終了指定なし"))
        self.refresh_modes()
        self.refresh_choices()

    def refresh_modes(self):
        """Rebuild the tabs for the selected command's COMMAND_RUN_MODES."""
        for widget in list(self.mode_bar.winfo_children()) + list(self.mode_panels.values()):
            widget.destroy()
        self.mode_panels, self.mode_specs = {}, {}
        self.prepared_mode, self.mode_authorization = None, None
        owners = self.app._command_classes(self.name) if self.name else []
        modes = next((getattr(owner, "COMMAND_RUN_MODES", ()) for owner in owners
                      if getattr(owner, "COMMAND_RUN_MODES", ())), ())
        for spec in modes:
            try:
                panel = spec["builder"](self, self)
            except Exception as error:
                self.status.set("開始タブ「{}」を表示できません: {}".format(spec.get("label", ""), error))
                continue
            self.mode_panels[spec["key"]], self.mode_specs[spec["key"]] = panel, spec
        self.mode.set("")
        if self.mode_panels:
            for key, label in [("", "ストーリー")] + [(k, s.get("label", k)) for k, s in self.mode_specs.items()]:
                ttk.Radiobutton(self.mode_bar, text=label, value=key, variable=self.mode,
                                style="Toolbutton", command=self.show_mode).pack(side="left", padx=2)
        self.show_mode()

    def show_mode(self):
        # Re-pack in a fixed order above the status line. Packing relative to
        # a hidden sibling raises "isn't packed" (Reload while a tab was open).
        key = self.mode.get()
        for widget in [self.mode_bar, self.story_frame] + list(self.mode_panels.values()):
            widget.pack_forget()
        if self.mode_panels:
            self.mode_bar.pack(fill="x", padx=5, pady=(3, 0), before=self.status_label)
        if key in self.mode_panels:
            self.mode_panels[key].pack(fill="x", padx=5, pady=3, before=self.status_label)
        else:
            self.story_frame.pack(fill="x", before=self.status_label)

    @staticmethod
    def display(item):
        # IDs avoid ambiguity when two chapters use the same label.
        return "{} [{}]".format(item.get("label", item.get("value", "")), item.get("id", ""))

    def current(self):
        profile = str(getattr(self.app, "_active_input_set_name", "") or "")
        if profile != self.profile:
            self.refresh()
        command = getattr(self.app, "cur_command", None)
        key = (self.profile, self.name)
        if command is self.observed_command and self.observed_profile != self.profile:
            return self.last_location.get(key)
        if getattr(command, "NAME", "") == self.name:
            current = observed_location(command, self.locations)
            if current:
                self.observed_command, self.observed_profile = command, self.profile
                self.last_location[key] = copy.deepcopy(current)
        saved = self.last_location.get(key)
        return next((item for item in self.locations if saved and
                     all(item.get(field) == saved.get(field) for field in ("id", "mode", "variable", "value"))), None)

    def refresh_choices(self):
        current = self.current()
        self._display_current_id = (current or {}).get("id")
        rows = location_choices(self.locations, current, all_steps=self.scope.get() == "全Step")
        term = self.search.get().casefold().strip()
        if term:
            rows = [item for item in self.locations if term in (self.display(item) + str(item.get("description", ""))).casefold()]
        self.mapping = {self.display(item): item for item in self.locations}
        values = [CURRENT, FIRST, DEFAULT] + [self.display(item) for item in rows]
        owners = self.app._command_classes(self.name) if self.name else []
        if any(isinstance(getattr(owner, "POKECON_FRESH_START", None), dict) for owner in owners):
            values.append(FRESH)
        selected = self.choice.get()
        if selected not in values and selected in self.mapping:
            values.append(selected)
        self.start_cb.configure(values=values)
        if selected not in values:
            self.choice.set(CURRENT)
        self.end_cb.configure(values=["終了指定なし"] + list(self.mapping))
        self.describe()

    def describe(self, *_):
        selected = self.choice.get()
        item = self.current() if selected == CURRENT else self.mapping.get(selected)
        if selected == FRESH:
            text = "対応ゲームのみ。データ1のオートセーブ上書きを実行前にこの欄で確認します。"
        elif item:
            text = "開始: {} {}".format(item.get("label", ""), item.get("description", ""))
        else:
            text = "現在位置未取得: Commands既定で開始" if selected == CURRENT else selected
        self.status.set(text)

    def capture_before_start(self):
        self.refresh()
        if self._in_dialog() and not self._dialog_accepted:
            # 従来の PokeCon と同じく、Start を押した時に開始位置・タブを選ぶ画面を出す。
            # 「この内容で開始」で Start をやり直す（CommandStartPanelHost.accept_dialog）
            self.refresh_choices()
            self.host.show_dialog()
            return False
        self._dialog_accepted = False
        key = self.mode.get()
        if key in self.mode_panels:
            return self.capture_mode_before_start(key)
        self.prepared_mode = None
        selected = self.choice.get()
        if selected == FRESH:
            self.app.fresh_start_current_command()
            return False
        location = (self.current() if selected == CURRENT else
                    self.locations[0] if selected == FIRST and self.locations else
                    self.mapping.get(selected))
        try:
            config = self.config(location)
        except ValueError as error:
            return self._problem(str(error))
        authorization = (self.profile, self.name, repr(config))
        if config["save_delete_user_number"] and self.delete_authorization != authorization:
            def confirmed():
                self.delete_authorization = authorization
                self.app.startPlay()
            self.confirm("ユーザー{}のセーブ削除を含む設定で実行します。対象データを確認してください。".format(
                config["save_delete_user_number"]), confirmed)
            return False
        self.prepared = (self.name, copy.deepcopy(location))
        return True

    def capture_mode_before_start(self, key):
        """Start on an extra tab: the panel validates and returns its settings."""
        try:
            values, message = self.mode_panels[key].prepare_start()
        except ValueError as error:
            return self._problem(str(error))
        authorization = (self.profile, self.name, key, repr(values))
        if message and self.mode_authorization != authorization:
            def confirmed():
                self.mode_authorization = authorization
                self.app.startPlay()
            self.confirm(message, confirmed)
            return False
        self.mode_authorization = None
        self.prepared_mode = (self.name, key, copy.deepcopy(values))
        self.prepared = (self.name, None)
        return True

    def config(self, location):
        retries = int(self.retry_count.get())
        user = int(self.delete_user.get())
        if not 1 <= retries <= 100 or not 0 <= user <= 8:
            raise ValueError("再実行上限は1～100、削除ユーザーは0～8で指定してください")
        recovery = bool(self.options.get("save_recovery", {}).get("available"))
        return {"start": copy.deepcopy(location or {}),
                "end": copy.deepcopy(self.mapping.get(self.end.get(), {})),
                "debug": {key: var.get() for key, var in self.debug_vars.items()},
                "confirm": False, "retry_on_failure": bool(recovery and self.retry.get()), "max_retries": retries,
                "save_delete_user_number": user if recovery else 0}

    def save_options(self):
        location = self.current() if self.choice.get() == CURRENT else self.mapping.get(self.choice.get())
        try:
            self.app.command_start_overrides[self.name] = self.config(location)
        except ValueError as error:
            self.status.set(str(error))
            return
        saved = self.app._sync_command_start_overrides_to_active_input_set()
        self.status.set("オプションを保存しました" if saved else "作業中設定へ保存しました。InputSet登録時に保存されます")

    def refresh_favorites(self):
        favorites = getattr(self.app, "command_run_favorites", {})
        self.favorite_cb.configure(values=[item.get("name", "") for item in favorites.get(self.name, [])])

    def save_favorite(self):
        name = self.favorite.get().strip()
        if not name:
            self.status.set("お気に入り名を入力してください")
            return
        favorites = self.app.command_run_favorites.setdefault(self.name, [])
        existing = next((item for item in favorites if item.get("name") == name), None)
        if existing is None and len(favorites) >= 10:
            self.status.set("お気に入りはCommandsごとに最大10件です")
            return
        location = (self.current() if self.choice.get() == CURRENT else
                    self.locations[0] if self.choice.get() == FIRST and self.locations else self.mapping.get(self.choice.get()))
        try:
            config = self.config(location)
        except ValueError as error:
            self.status.set(str(error))
            return
        if existing is None:
            favorites.append({"name": name, "config": config})
        else:
            existing["config"] = config
        self.app._sync_command_start_overrides_to_active_input_set()
        self.refresh_favorites()
        self.status.set("お気に入りを保存しました: " + name)

    def load_favorite(self):
        item = next((item for item in self.app.command_run_favorites.get(self.name, []) if item.get("name") == self.favorite.get()), None)
        if item:
            self.use_config(item.get("config", {}))

    def use_config(self, config):
        self.app.command_start_overrides[self.name] = copy.deepcopy(config)
        self.refresh(force=True)
        start = config.get("start", {})
        selected = next((text for text, row in self.mapping.items() if row.get("id") == start.get("id")), DEFAULT)
        self.choice.set(selected)
        self.refresh_choices()

    def delete_favorite(self):
        items = self.app.command_run_favorites.get(self.name, [])
        name = self.favorite.get()
        self.app.command_run_favorites[self.name] = [item for item in items if item.get("name") != name]
        self.app._sync_command_start_overrides_to_active_input_set()
        self.refresh_favorites()
        self.status.set("お気に入りを削除しました: " + name)

    def prepare(self, command, initial_config=None):
        name = getattr(command, "NAME", "")
        if name != self.name:
            # Numbered legacy command shortcuts must never inherit another command's Step.
            config = copy.deepcopy(self.app.command_start_overrides.get(name, {}))
            config["confirm"] = False
        else:
            location = self.prepared[1] if self.prepared and self.prepared[0] == name else None
            if initial_config is not None:
                config = copy.deepcopy(initial_config)
                config["confirm"] = False
            else:
                try:
                    config = self.config(location)
                except ValueError as error:
                    self.status.set(str(error))
                    return False
        self.prepared = None
        if self.prepared_mode and self.prepared_mode[0] == name:
            # An extra tab starts at the command default and never uses the
            # Story tab's save-delete recovery.
            config["start"], config["end"] = {}, {}
            config["save_delete_user_number"] = 0
        authorization = (self.profile, name, repr(config))
        if config.get("save_delete_user_number") and (
                name != self.name or self.delete_authorization != authorization):
            self.status.set("セーブ削除を含む設定はCommandsタブのStartから内容を確認して開始してください")
            return False
        self.delete_authorization = None
        available = self.locations if name == self.name else self.app._command_run_options(name).get("locations", [])
        if getattr(command, "COMMAND_RUN_SETTINGS", False) and not available:
            self.status.set("開始位置を取得できません。ソースを確認してReloadしてください")
            return False
        self.app.command_start_overrides[name] = config
        return True

    def apply(self, command):
        config = copy.deepcopy(self.app.command_start_overrides.get(getattr(command, "NAME", ""), {}))
        try:
            assignments = apply_command_run_options(command, config)
            from pathlib import Path
            from CommandImageCollection import arm_native_image_collection, CollectionOptions
            arm_native_image_collection(command, str(Path(__file__).resolve().parent),
                CollectionOptions(collect=bool(self.collect.get()),
                                  supplemental=bool(self.supplemental.get()),
                                  language=self.language.get().strip()[:80]))
        except (AttributeError, TypeError, ValueError) as error:
            self.status.set("開始位置を適用できません: " + str(error))
            return False
        finally:
            self.collect.set(False)
            self.supplemental.set(False)
        mode, self.prepared_mode = self.prepared_mode, None
        hook = getattr(command, "apply_command_run_mode", None)
        if callable(hook):
            if mode and mode[0] == getattr(command, "NAME", ""):
                hook(mode[1], copy.deepcopy(mode[2]))
            else:
                hook(None, None)
        start = config.get("start") or {}
        command._command_start_override_context = {
            "variable": start.get("variable", ""), "state": str(start.get("value", "")),
            "assignments": assignments, "start": start, "end": config.get("end") or {}, "end_seen": False}
        return True

    def show_start_preview(self, source_root, context, provider):
        """Show an opt-in Commands reference image inside Commands, with no grab."""
        box = ttk.LabelFrame(self, text="開始画面の確認")
        box.pack(fill="x", padx=5, pady=4)
        if self._in_dialog():
            self.host.show_dialog()
        else:
            self.app.controller_nb.select(self.app.commands_tab)
        done = tk.BooleanVar(self, False)
        status = tk.StringVar(self, "開始画像を読み込み中…")
        state = {"accepted": False, "closed": False, "photo": None, "poll": None}
        messages = queue.Queue()
        command = self.app.cur_command
        binding = self.app._command_debug_binding()
        ttk.Label(box, text="タイトル画面からデータ1を『はじめから』で開始します。既存オートセーブは上書きされます。",
                  wraplength=620).pack(fill="x", padx=4)
        image_label = ttk.Label(box)
        image_label.pack(fill="x", padx=4, pady=3)
        ttk.Label(box, textvariable=status, wraplength=620).pack(fill="x", padx=4)
        actions = ttk.Frame(box)
        actions.pack(fill="x", padx=4, pady=3)

        def finish(accepted=False):
            state["accepted"], state["closed"] = accepted, True
            done.set(True)

        def submit(kind, callback):
            confirm.configure(state="disabled")
            def worker():
                try:
                    messages.put((kind, callback(), None))
                except Exception as error:
                    messages.put((kind, None, str(error)))
            threading.Thread(target=worker, daemon=True, name="EmbeddedCommandPreview").start()

        def accept():
            if self.app.cur_command is not command or binding != self.app._command_debug_binding():
                status.set("入力先／Commandsが変わりました。キャンセルしてやり直してください")
                return
            status.set("開始設定を再確認中…")
            submit("verify", lambda: provider.verify_start_context(source_root, context))

        confirm = ttk.Button(actions, text="確認して実行", command=accept, state="disabled")
        confirm.pack(side="left", padx=3)
        ttk.Button(actions, text="キャンセル", command=finish).pack(side="left")

        self.after_idle(lambda: self.reveal(box))

        def poll():
            if state["closed"]:
                return
            try:
                kind, value, error = messages.get_nowait()
            except queue.Empty:
                state["poll"] = self.after(60, poll)
                return
            if kind == "frame":
                if error:
                    status.set("参考画像を読み込めません: " + error)
                    confirm.configure(text="画像なしで実行", state="normal")
                    self.after_idle(lambda: self.reveal(box, confirm))
                else:
                    from PIL import ImageTk
                    pixels = value.image.copy()
                    pixels.thumbnail((620, 240))
                    state["photo"] = ImageTk.PhotoImage(pixels, master=self)
                    image_label.configure(image=state["photo"])
                    status.set("元録画の参考画像です。現在の入力映像と開始位置を確認してください")
                    confirm.configure(state="normal")
                    self.after_idle(lambda: self.reveal(box, confirm))
            elif error:
                status.set("開始しません: " + error)
                confirm.configure(state="normal")
            elif self.app.cur_command is command and binding == self.app._command_debug_binding():
                finish(True)
                return
            else:
                status.set("入力先／Commandsが変わったため開始しません")
            state["poll"] = self.after(60, poll)

        submit("frame", lambda: provider.read_reference_frame(context["reference"], context["recording"]))
        state["poll"] = self.after(60, poll)
        destroy_binding = self.bind("<Destroy>", lambda event: finish() if event.widget is self else None, add="+")
        try:
            self.wait_variable(done)
            return context if state["accepted"] else None
        finally:
            state["closed"] = True
            try:
                if state["poll"]:
                    self.after_cancel(state["poll"])
                self.unbind("<Destroy>", destroy_binding)
                box.destroy()
                if self._in_dialog():
                    self.host.hide_dialog()
            except tk.TclError:
                pass


class CommandStartPanelHost(ttk.Frame):
    """Commands タブの「開始位置・その他の操作」の置き場所を切り替える。

    - "tab": Commands タブに常時表示（生成AIの操作では常に見えている方が扱いやすい）
    - "dialog": 従来の PokeCon と同じく Start を押した時に画面を出す
    設定は settings.ini の [Commands Start] panel に保存する。Tk のウィジェットは親を
    変えられないため、切り替え時は欄を作り直す（選択中の Commands の設定は読み直す）。
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.window, self.panel = None, None
        self.place = tk.StringVar(self, "tab")
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="開始位置・その他の操作:").pack(side="left")
        for key, label in PANEL_PLACES:
            ttk.Radiobutton(bar, text=label, value=key, variable=self.place,
                            command=self.switch).pack(side="left", padx=4)
        self._build()

    def dialog_mode(self):
        return self.place.get() == "dialog"

    def apply_saved_mode(self):
        """settings.ini の読込後に呼ぶ（画面を作る時点ではまだ読み込まれていない）。"""
        saved = str(getattr(getattr(self.app, "settings", None), "command_start_panel", "tab") or "tab")
        if saved in dict(PANEL_PLACES) and saved != self.place.get():
            self.place.set(saved)
            self._rebuild()

    def switch(self):
        settings = getattr(self.app, "settings", None)
        if settings is not None:
            settings.command_start_panel = self.place.get()
            try:
                settings.save()
            except Exception:
                pass
        self._rebuild()
        try:
            self.panel.refresh(force=True)
        except Exception:
            pass

    def _rebuild(self):
        old, window = self.panel, self.window
        self.window = None
        self._build()
        for widget in (old, window):
            if widget is not None:
                try:
                    widget.destroy()
                except tk.TclError:
                    pass

    def _build(self):
        if self.dialog_mode():
            window = tk.Toplevel(self)
            window.title("Commands - 開始位置・その他の操作")
            window.withdraw()
            window.protocol("WM_DELETE_WINDOW", self.cancel_dialog)
            ttk.Label(window, text="Startが押されました。開始位置・タブを選んで開始してください。",
                      foreground="#174a7e").pack(anchor="w", padx=10, pady=(8, 2))
            panel = CommandQuickRun(window, self.app, host=self)
            panel.pack(fill="both", expand=True, padx=8, pady=4)
            buttons = ttk.Frame(window)
            buttons.pack(fill="x", padx=8, pady=(0, 8))
            ttk.Button(buttons, text="開始をやめる", command=self.cancel_dialog).pack(side="right", padx=4)
            ttk.Button(buttons, text="この内容で開始", command=self.accept_dialog).pack(side="right", padx=4)
            self.window = window
        else:
            panel = CommandQuickRun(self, self.app, host=self)
            panel.pack(fill="x", pady=(3, 0))
        self.panel = panel
        self.app.command_quick_run = panel

    def show_dialog(self):
        if self.window is None:
            return
        try:
            self.window.transient(self.winfo_toplevel())
            self.window.deiconify()
            self.window.lift()
            self.window.grab_set()
            self.window.focus_set()
        except tk.TclError:
            pass

    def hide_dialog(self):
        if self.window is None:
            return
        try:
            self.window.grab_release()
            self.window.withdraw()
        except tk.TclError:
            pass

    def accept_dialog(self):
        self.panel._dialog_accepted = True
        self.hide_dialog()
        self.app.startPlay()

    def cancel_dialog(self):
        self.panel._dialog_accepted = False
        self.panel.confirmation.pack_forget()
        self.hide_dialog()
        self.panel.status.set("開始をやめました")
