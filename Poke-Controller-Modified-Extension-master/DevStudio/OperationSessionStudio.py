#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-screen DevStudio workspace for controller-operation authoring sessions."""
from __future__ import print_function

import ast
import bisect
import datetime
import json
import os
import re
import shutil
import threading
import time
import tokenize
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import cv2
except ImportError:  # The rest of DevStudio remains usable without video support.
    cv2 = None
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

from OperationSessionModel import (GENERATION_TARGET_PORTABLE,
                                   GENERATION_TARGET_SWITCH,
                                   STICK_MODE_EIGHT_WAY, STICK_MODE_EXACT,
                                   atomic_json,
                                   generate_intermediate, load_inputs,
                                   load_mappings, load_session,
                                   operation_video_sources, pending_lines,
                                   pending_neighbor, replace_generated_region,
                                   save_mappings, source_class_names, unified_diff)
from OperationDebugCommand import (create_debug_command_package,
                                   build_debug_draft_mappings,
                                   debug_output_paths,
                                   deploy_debug_command as deploy_debug_command_file,
                                   intermediate_revisions,
                                   save_intermediate_revision)
from OperationVisionSample import (analyse_operation_video,
                                   generate_vision_sample,
                                   vision_output_paths)


KIND_LABELS = {
    "Stepとして作成": "step",
    "関数として作成": "function",
    "直接処理として残す": "raw",
    "反映不要": "ignore",
}
KIND_NAMES = {value: key for key, value in KIND_LABELS.items()}
GENERATION_TARGET_LABELS = {
    "Switchのみ": GENERATION_TARGET_SWITCH,
    "Switch＋Steam/PS4流用": GENERATION_TARGET_PORTABLE,
}
GENERATION_TARGET_NAMES = {value: key for key, value in GENERATION_TARGET_LABELS.items()}
STICK_MODE_LABELS = {
    "記録角度を保持（既定）": STICK_MODE_EXACT,
    "8方向へ変換": STICK_MODE_EIGHT_WAY,
}
STICK_MODE_NAMES = {value: key for key, value in STICK_MODE_LABELS.items()}


def _read_source(path):
    with tokenize.open(path) as stream:
        return stream.read()


def _write_text_atomic(path, text):
    temporary = path + ".tmp-" + uuid.uuid4().hex
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    os.replace(temporary, path)


class OperationSessionWorkspace(ttk.Frame):
    """Controller inputs, video and generated source in one ordered workspace."""

    def __init__(self, parent, initial_session="", code_root_provider=None,
                 open_image_callback=None, open_source_callback=None):
        ttk.Frame.__init__(self, parent)
        self.code_root_provider = code_root_provider or (lambda: os.getcwd())
        self.open_image_callback = open_image_callback
        self.open_source_callback = open_source_callback
        self.session_dir = ""
        self.session = {}
        self.inputs = []
        self.input_by_line = {}
        self.input_times = []
        self._input_page = 0
        self._filtered_inputs = []
        self._mapping_index = {}
        self._pending_count = 0
        self.mappings = []
        self.mapping_by_iid = {}
        self.video_capture = None
        self.video_sources = {}
        self.video_source_origins = {}
        self.video_source_ranges = {}
        self.video_time_origin = 0.0
        self.video_fps = 30.0
        self.video_duration = 0.0
        self.current_time = 0.0
        self.current_frame = None
        self.playing = False
        self._play_job = None
        self._play_wall = 0.0
        self._play_origin = 0.0
        self._selection_from_video = False
        self._last_highlight_line = 0
        self._video_photo = None
        self._nearby_photos = []
        self._mapping_edit_id = None
        self._mapping_edit_range = None
        self._vision_generation_running = False
        self._latest_intermediate_revision = ""
        self._build()
        if initial_session:
            self.after_idle(lambda: self.load_session_dir(initial_session))

    def _build(self):
        self.session_path = tk.StringVar()
        self.session_summary = tk.StringVar(value="操作セッションを選択してください。")
        self.status = tk.StringVar(value="① セッション読込から開始します。")
        self.input_search = tk.StringVar()
        self.input_page_text = tk.StringVar(value="0件")
        self.input_jump_line = tk.StringVar()
        self.mapping_kind = tk.StringVar(value="Stepとして作成")
        self.mapping_step = tk.StringVar(value="RECORDED_STEP")
        self.mapping_next_step = tk.StringVar()
        self.mapping_function = tk.StringVar(value="recorded_function")
        self.mapping_call_step = tk.StringVar()
        self.mapping_notes = tk.StringVar()
        self.mapping_start_line = tk.StringVar()
        self.mapping_end_line = tk.StringVar()
        self.video_choice = tk.StringVar()
        self.video_time_text = tk.StringVar(value="00:00.000 / 00:00.000")
        self.video_sync = tk.DoubleVar(value=0.0)
        self.source_path = tk.StringVar()
        self.source_class = tk.StringVar()
        self.mapping_progress = tk.StringVar(value="未割当 0 / 全0行")
        self.generation_target = tk.StringVar(value="Switchのみ")
        self.stick_angle_mode = tk.StringVar(value="記録角度を保持（既定）")
        self.debug_command_path = tk.StringVar(value="")

        guide = ttk.Label(
            self,
            text=("このタブだけでCommands化まで進めます。 "
                  "①記録読込 → ②入力と映像を確認 → ③範囲をStep/関数へ割当 → "
                  "④中間生成 → ⑤差分確認 → ⑥ソース反映／画像検知"),
            foreground="#174a7e", justify="left", wraplength=1450)
        guide.pack(fill="x", padx=8, pady=(7, 2))

        opener = ttk.Frame(self)
        opener.pack(fill="x", padx=8, pady=(2, 5))
        ttk.Label(opener, text="① 操作セッション:").pack(side="left")
        ttk.Entry(opener, textvariable=self.session_path).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(opener, text="選択...", command=self.choose_session).pack(side="left")
        ttk.Button(opener, text="読込", command=self.load_typed_session).pack(side="left", padx=3)
        ttk.Button(opener, text="フォルダを開く", command=self.open_session_folder).pack(side="left")
        ttk.Label(self, textvariable=self.session_summary, anchor="w").pack(
            fill="x", padx=10, pady=(0, 4))

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=7, pady=(0, 4))
        code_panel, input_panel, video_panel = ttk.Frame(panes), ttk.Frame(panes), ttk.Frame(panes)
        panes.add(code_panel, weight=3)
        panes.add(input_panel, weight=4)
        panes.add(video_panel, weight=4)
        self.panes = panes

        self._build_code_panel(code_panel)
        self._build_input_panel(input_panel)
        self._build_video_panel(video_panel)
        ttk.Label(self, textvariable=self.status, anchor="w").pack(
            fill="x", padx=9, pady=(0, 6))

    def _text_page(self, notebook, title):
        page = ttk.Frame(notebook)
        notebook.add(page, text=title)
        text = tk.Text(page, wrap="none", undo=True, font=("Consolas", 9),
                       background="#171717", foreground="#e5e5e5",
                       insertbackground="white")
        sy = ttk.Scrollbar(page, orient="vertical", command=text.yview)
        sx = ttk.Scrollbar(page, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        text.grid(column=0, row=0, sticky="nsew")
        sy.grid(column=1, row=0, sticky="ns")
        sx.grid(column=0, row=1, sticky="ew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        return text

    def _build_code_panel(self, parent):
        ttk.Label(parent, text="④〜⑥ 中間／最終ソース", foreground="#174a7e").pack(
            anchor="w", padx=4)
        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=3, pady=3)
        ttk.Button(actions, text="④ 中間コード生成", command=self.generate_code).pack(side="left")
        self.vision_sample_button = ttk.Button(
            actions, text="動画解析＋デバッグCommands生成",
            command=self.generate_video_vision_sample)
        self.vision_sample_button.pack(side="left", padx=3)
        ttk.Button(actions, text="デバッグ編集", command=self.open_debug_command).pack(
            side="left", padx=2)
        ttk.Button(actions, text="Commandsへ配置", command=self.deploy_debug_command).pack(
            side="left", padx=2)
        ttk.Button(actions, text="⑤ 差分更新", command=self.refresh_final_preview).pack(
            side="left")
        ttk.Button(actions, text="⑥ ソースへ反映", command=self.apply_to_source).pack(side="left")

        generation = ttk.Labelframe(parent, text="中間コードの入力対象")
        generation.pack(fill="x", padx=3, pady=(0, 4))
        settings = ttk.Frame(generation)
        settings.pack(side="left", padx=4, pady=3)
        ttk.Label(settings, text="入力対象:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            settings, textvariable=self.generation_target, state="readonly",
            values=tuple(GENERATION_TARGET_LABELS), width=25).grid(
                row=0, column=1, padx=(3, 0), pady=(0, 2))
        ttk.Label(settings, text="スティック角度:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            settings, textvariable=self.stick_angle_mode, state="readonly",
            values=tuple(STICK_MODE_LABELS), width=25).grid(
                row=1, column=1, padx=(3, 0))
        self.generation_target.trace_add(
            "write", lambda *_args: self._generation_target_changed())
        self.stick_angle_mode.trace_add(
            "write", lambda *_args: self._generation_target_changed())
        ttk.Label(
            generation,
            text=("既定は記録した角度と倒し量を保持します。8方向では倒し量を保ち、角度だけを45度単位へ変換。"
                  "流用対応では Steam_Switch_Game_Input サンプルを使用します。キー割当は生成後も変更可能。"
                  "画像検知は最初は共通名を使い、後からSwitch／Steam／PS4別に上書きできます。"),
            foreground="#555555", wraplength=520, justify="left").pack(
                side="left", fill="x", expand=True, padx=3, pady=3)

        source = ttk.Labelframe(parent, text="最終ソース（先に選択。元ファイルはバックアップされます）")
        source.pack(fill="x", padx=3, pady=(0, 4))
        ttk.Entry(source, textvariable=self.source_path).grid(
            column=0, columnspan=3, row=0, padx=3, pady=3, sticky="ew")
        ttk.Button(source, text="選択...", command=self.choose_source).grid(column=3, row=0, padx=2)
        ttk.Button(source, text="エディタで開く", command=self.open_source_in_editor).grid(
            column=4, row=0, padx=2)
        ttk.Label(source, text="反映先クラス:").grid(column=0, row=1, padx=3, sticky="w")
        self.source_class_combo = ttk.Combobox(
            source, textvariable=self.source_class, state="readonly", width=28)
        self.source_class_combo.grid(column=1, columnspan=4, row=1, padx=3, pady=3, sticky="ew")
        source.columnconfigure(2, weight=1)

        self.code_tabs = ttk.Notebook(parent)
        self.code_tabs.pack(fill="both", expand=True, padx=3)
        self.intermediate_text = self._text_page(self.code_tabs, "中間ファイル")
        self.final_text = self._text_page(self.code_tabs, "反映後プレビュー")
        self.diff_text = self._text_page(self.code_tabs, "差分")
        self.vision_sample_text = self._text_page(
            self.code_tabs, "動画判断・疑似サンプル")
        self.intermediate_history_diff_text = self._text_page(
            self.code_tabs, "中間履歴差分")
        self.diff_text.tag_configure("add", foreground="#85d996")
        self.diff_text.tag_configure("delete", foreground="#ff8585")
        self.intermediate_history_diff_text.tag_configure("add", foreground="#85d996")
        self.intermediate_history_diff_text.tag_configure("delete", foreground="#ff8585")

        history_actions = ttk.Frame(parent)
        history_actions.pack(fill="x", padx=3, pady=(2, 0))
        ttk.Button(history_actions, text="前回の中間コードと比較",
                   command=self.compare_intermediate_revisions).pack(side="left")
        ttk.Button(history_actions, text="中間履歴フォルダを開く",
                   command=self.open_intermediate_history).pack(side="left", padx=3)
        ttk.Label(history_actions, textvariable=self.debug_command_path,
                  foreground="#555555").pack(side="left", fill="x", expand=True, padx=5)

    def _build_input_panel(self, parent):
        header = ttk.Frame(parent)
        header.pack(fill="x", padx=3)
        ttk.Label(header, text="② 入力記録", foreground="#174a7e").pack(side="left")
        ttk.Label(header, textvariable=self.mapping_progress).pack(side="right")
        search = ttk.Entry(parent, textvariable=self.input_search)
        search.pack(fill="x", padx=3, pady=3)
        self.input_search.trace_add("write", lambda *_args: self._input_filter_changed())

        pages = ttk.Frame(parent)
        pages.pack(fill="x", padx=3, pady=(0, 3))
        ttk.Button(pages, text="◀ 前500件",
                   command=lambda: self.change_input_page(-1)).pack(side="left")
        ttk.Button(pages, text="次500件 ▶",
                   command=lambda: self.change_input_page(1)).pack(side="left", padx=3)
        ttk.Label(pages, textvariable=self.input_page_text).pack(side="left", padx=5)
        ttk.Button(pages, text="行へ", command=self.jump_to_input_line).pack(side="right")
        ttk.Entry(pages, textvariable=self.input_jump_line, width=8).pack(
            side="right", padx=3)
        ttk.Label(pages, text="入力行:").pack(side="right")

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=3)
        self.input_tree = ttk.Treeview(
            tree_frame, columns=("line", "time", "segment", "input", "mapping"),
            show="headings", selectmode="extended", height=11)
        for column, label, width in (
                ("line", "行", 48), ("time", "秒", 72), ("segment", "区間", 42),
                ("input", "入力", 240), ("mapping", "割当", 120)):
            self.input_tree.heading(column, text=label)
            self.input_tree.column(column, width=width,
                                   stretch=column in ("input", "mapping"))
        sy = ttk.Scrollbar(tree_frame, orient="vertical", command=self.input_tree.yview)
        sx = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.input_tree.xview)
        self.input_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.input_tree.grid(column=0, row=0, sticky="nsew")
        sy.grid(column=1, row=0, sticky="ns")
        sx.grid(column=0, row=1, sticky="ew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.input_tree.bind("<<TreeviewSelect>>", self.on_input_selected)

        pending = ttk.Frame(parent)
        pending.pack(fill="x", padx=3, pady=3)
        ttk.Button(pending, text="← 前の未割当", command=lambda: self.select_pending(False)).pack(
            side="left")
        ttk.Button(pending, text="次の未割当 →", command=lambda: self.select_pending(True)).pack(
            side="left", padx=3)
        ttk.Button(pending, text="選択をCommandsから除外",
                   command=self.exclude_selected_inputs).pack(side="left", padx=3)
        ttk.Button(pending, text="選択行の映像へ", command=self.seek_selected_input).pack(side="right")

        form = ttk.Labelframe(parent, text="③ 選択した連続行を割り当て（後から編集・削除可）")
        form.pack(fill="x", padx=3, pady=3)
        ttk.Label(form, text="種類:").grid(column=0, row=0, padx=3, pady=2, sticky="w")
        ttk.Combobox(form, textvariable=self.mapping_kind, state="readonly",
                     values=tuple(KIND_LABELS), width=21).grid(
                         column=1, row=0, padx=3, pady=2, sticky="ew")
        ttk.Label(form, text="Step名:").grid(column=0, row=1, padx=3, pady=2, sticky="w")
        ttk.Entry(form, textvariable=self.mapping_step).grid(
            column=1, row=1, padx=3, pady=2, sticky="ew")
        ttk.Label(form, text="次Step:").grid(column=2, row=1, padx=3, pady=2, sticky="w")
        ttk.Entry(form, textvariable=self.mapping_next_step, width=18).grid(
            column=3, row=1, padx=3, pady=2, sticky="ew")
        ttk.Label(form, text="関数名:").grid(column=0, row=2, padx=3, pady=2, sticky="w")
        ttk.Entry(form, textvariable=self.mapping_function).grid(
            column=1, row=2, padx=3, pady=2, sticky="ew")
        ttk.Label(form, text="呼出元Step:").grid(column=2, row=2, padx=3, pady=2, sticky="w")
        ttk.Entry(form, textvariable=self.mapping_call_step, width=18).grid(
            column=3, row=2, padx=3, pady=2, sticky="ew")
        ttk.Label(form, text="メモ:").grid(column=0, row=3, padx=3, pady=2, sticky="w")
        ttk.Entry(form, textvariable=self.mapping_notes).grid(
            column=1, columnspan=3, row=3, padx=3, pady=2, sticky="ew")
        ttk.Label(form, text="行範囲:").grid(column=0, row=4, padx=3, pady=2, sticky="w")
        range_box = ttk.Frame(form)
        range_box.grid(column=1, columnspan=3, row=4, padx=3, pady=2, sticky="ew")
        ttk.Entry(range_box, textvariable=self.mapping_start_line, width=8).pack(side="left")
        ttk.Label(range_box, text=" ～ ").pack(side="left")
        ttk.Entry(range_box, textvariable=self.mapping_end_line, width=8).pack(side="left")
        ttk.Button(range_box, text="現在の選択から設定",
                   command=self.use_selected_mapping_range).pack(side="left", padx=5)
        ttk.Label(range_box, text="ページをまたぐ範囲は数値で指定できます。",
                  foreground="#555555").pack(side="left")
        buttons = ttk.Frame(form)
        buttons.grid(column=0, columnspan=4, row=5, sticky="ew", padx=2, pady=3)
        self.mapping_save_button = ttk.Button(
            buttons, text="＋ 選択範囲を登録", command=self.save_mapping)
        self.mapping_save_button.pack(side="left")
        ttk.Button(buttons, text="編集解除", command=self.clear_mapping_form).pack(
            side="left", padx=3)
        ttk.Button(buttons, text="選択した割当を削除", command=self.delete_mapping).pack(
            side="right")
        for column in (1, 3):
            form.columnconfigure(column, weight=1)

        mapping_frame = ttk.Frame(parent)
        mapping_frame.pack(fill="both", expand=False, padx=3, pady=(0, 3))
        self.mapping_tree = ttk.Treeview(
            mapping_frame, columns=("range", "kind", "name", "notes"),
            show="headings", selectmode="browse", height=5)
        for column, label, width in (("range", "行範囲", 90), ("kind", "種類", 90),
                                     ("name", "Step/関数", 150), ("notes", "メモ", 150)):
            self.mapping_tree.heading(column, text=label)
            self.mapping_tree.column(column, width=width, stretch=column in ("name", "notes"))
        sy = ttk.Scrollbar(mapping_frame, orient="vertical", command=self.mapping_tree.yview)
        self.mapping_tree.configure(yscrollcommand=sy.set)
        self.mapping_tree.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")
        self.mapping_tree.bind("<<TreeviewSelect>>", self.edit_selected_mapping)

    def _build_video_panel(self, parent):
        header = ttk.Frame(parent)
        header.pack(fill="x", padx=3)
        ttk.Label(header, text="② 映像同期／⑥ 画像検知", foreground="#174a7e").pack(side="left")
        self.video_combo = ttk.Combobox(
            header, textvariable=self.video_choice, state="readonly", width=23)
        self.video_combo.pack(side="right")
        self.video_combo.bind("<<ComboboxSelected>>", lambda _event: self.open_selected_video())

        self.video_label = tk.Label(parent, text="映像を読み込むとここに表示されます。",
                                    background="black", foreground="white")
        self.video_label.pack(fill="both", expand=True, padx=3, pady=4)
        self.video_slider = ttk.Scale(parent, from_=0.0, to=1.0, command=self.on_video_slider)
        self.video_slider.pack(fill="x", padx=5)
        ttk.Label(parent, textvariable=self.video_time_text, anchor="center").pack(fill="x")
        controls = ttk.Frame(parent)
        controls.pack(fill="x", padx=3, pady=3)
        for label, amount in (("-1秒", -1.0), ("-0.1", -0.1)):
            ttk.Button(controls, text=label, command=lambda value=amount: self.nudge_video(value)).pack(
                side="left", padx=1)
        self.play_button = ttk.Button(controls, text="▶ 再生", command=self.toggle_play)
        self.play_button.pack(side="left", padx=4)
        for label, amount in (("+0.1", 0.1), ("+1秒", 1.0)):
            ttk.Button(controls, text=label, command=lambda value=amount: self.nudge_video(value)).pack(
                side="left", padx=1)
        ttk.Button(controls, text="近辺5枚を更新", command=self.update_nearby_frames).pack(
            side="right")

        sync = ttk.Frame(parent)
        sync.pack(fill="x", padx=3, pady=(0, 3))
        ttk.Label(sync, text="入力⇔映像 補正秒:").pack(side="left")
        ttk.Spinbox(sync, from_=-30.0, to=30.0, increment=0.01,
                    textvariable=self.video_sync, width=8).pack(side="left", padx=3)
        ttk.Button(sync, text="同期補正を保存", command=self.save_video_sync).pack(side="left")
        ttk.Button(sync, text="現在フレームから画像検知", command=self.open_frame_capture).pack(
            side="right")
        ttk.Label(
            parent,
            text=("画像は初期状態ではSwitch／Steam／PS4共通として保存します。"
                  "流用対応コードではgame_image_profilesで機種別画像へ後から変更できます。"),
            foreground="#555555", wraplength=520, justify="left").pack(
                fill="x", padx=5, pady=(0, 2))

        nearby = ttk.Labelframe(parent, text="現在位置の近辺（クリックで移動）")
        nearby.pack(fill="x", padx=3, pady=3)
        self.nearby_labels = []
        for index in range(5):
            label = tk.Label(nearby, text="-", background="#111", foreground="white",
                             width=18, height=5)
            label.pack(side="left", fill="both", expand=True, padx=1, pady=2)
            self.nearby_labels.append(label)

    def choose_session(self):
        path = filedialog.askdirectory(parent=self, title="操作セッションフォルダを選択",
                                       initialdir=self.session_path.get() or self.code_root_provider())
        if path:
            self.session_path.set(path)
            self.load_session_dir(path)

    def load_typed_session(self):
        self.load_session_dir(self.session_path.get())

    def load_session_dir(self, path):
        path = os.path.abspath(str(path or ""))
        try:
            session = load_session(path)
            inputs = load_inputs(path)
            mappings = load_mappings(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("操作記録→Commands", str(error), parent=self)
            return False
        self.stop_video()
        self.close_video()
        self.session_dir = path
        self.session_path.set(path)
        self.session = session
        self.inputs = inputs
        self.input_by_line = {int(item.get("line", 0)): item for item in inputs}
        self.input_times = [float(item.get("time", 0.0)) for item in inputs]
        self.mappings = mappings
        self._input_page = 0
        self._rebuild_mapping_index()
        self.video_sync.set(float(session.get("video_sync_offset", 0.0)))
        generation = session.get("generation", {})
        saved_target = generation.get("input_target", GENERATION_TARGET_SWITCH) \
            if isinstance(generation, dict) else GENERATION_TARGET_SWITCH
        saved_stick_mode = generation.get("stick_angle_mode", STICK_MODE_EXACT) \
            if isinstance(generation, dict) else STICK_MODE_EXACT
        self.generation_target.set(GENERATION_TARGET_NAMES.get(
            saved_target, "Switchのみ"))
        self.stick_angle_mode.set(STICK_MODE_NAMES.get(
            saved_stick_mode, "記録角度を保持（既定）"))
        self.source_path.set(str(session.get("final_source", "") or ""))
        debug_paths = debug_output_paths(path)
        self.debug_command_path.set(
            debug_paths["working"] if os.path.isfile(debug_paths["working"]) else "")
        revisions = intermediate_revisions(path)
        self._latest_intermediate_revision = revisions[-1] if revisions else ""
        input_configuration = session.get("input_configuration", {})
        gamepad_profile = str(input_configuration.get("gamepad_profile", "")) \
            if isinstance(input_configuration, dict) else ""
        self.session_summary.set(
            "状態: {} / 有効時間 {:.1f}秒 / 入力 {}行 / 区間 {} / InputSet: {} / ゲームパッド設定: {}".format(
                session.get("status", ""), float(session.get("active_duration", 0.0)),
                len(inputs), len(session.get("segments", [])), session.get("input_set", ""),
                gamepad_profile or "なし"))
        self.refresh_input_tree()
        self.refresh_mapping_tree()
        self.generate_code(select_tab=False)
        self.load_video_vision_sample()
        self.refresh_video_sources()
        if self.source_path.get() and os.path.isfile(self.source_path.get()):
            self.load_source_classes()
            self.refresh_final_preview(select_tab=False)
        self.status.set("読込完了。入力行を選ぶと同じ時刻の映像へ移動します。")
        if session.get("status") == "paused":
            self.status.set(
                "一時停止中のセッションです。区間動画の確認・割り当て・中間コード生成を行えます。")
        return True

    def open_session_folder(self):
        if not self.session_dir or not os.path.isdir(self.session_dir):
            return
        try:
            os.startfile(self.session_dir)
        except (AttributeError, OSError):
            pass

    def _mappings_for_line(self, line):
        return self._mapping_index.get(int(line), ())

    def _rebuild_mapping_index(self):
        """Build the range lookup once instead of scanning every mapping per row."""
        self._mapping_index = {}
        if self.input_by_line:
            minimum = min(self.input_by_line)
            maximum = max(self.input_by_line)
            for mapping in self.mappings:
                start = max(minimum, int(mapping.get("start_line", minimum)))
                end = min(maximum, int(mapping.get("end_line", maximum)))
                for line in range(start, end + 1):
                    if line in self.input_by_line:
                        self._mapping_index.setdefault(line, []).append(mapping)
        self._pending_count = sum(
            1 for line in self.input_by_line if line not in self._mapping_index)

    def _input_filter_changed(self):
        self._input_page = 0
        self.refresh_input_tree()

    def refresh_input_tree(self):
        if not hasattr(self, "input_tree"):
            return
        selected_lines = self.selected_input_lines()
        self.input_tree.delete(*self.input_tree.get_children())
        needle = self.input_search.get().strip().lower()
        filtered = []
        for item in self.inputs:
            line = int(item.get("line", 0))
            text = "{} {} {}".format(line, item.get("summary", ""), item.get("message", ""))
            mappings = self._mappings_for_line(line)
            mapping_text = "未割当"
            if mappings:
                mapping_text = " + ".join(
                    KIND_NAMES.get(mapping.get("kind"), mapping.get("kind", ""))
                    for mapping in mappings)
            if needle and needle not in text.lower() and needle not in mapping_text.lower():
                continue
            filtered.append((item, mapping_text))
        self._filtered_inputs = filtered
        page_count = max(1, (len(filtered) + 499) // 500)
        self._input_page = min(max(0, self._input_page), page_count - 1)
        start = self._input_page * 500
        visible = filtered[start:start + 500]
        for item, mapping_text in visible:
            line = int(item.get("line", 0))
            iid = "input-{}".format(line)
            self.input_tree.insert("", "end", iid=iid, values=(
                line, "{:.3f}".format(float(item.get("time", 0.0))),
                item.get("segment", ""), item.get("summary", item.get("message", "")),
                mapping_text))
            if line in selected_lines:
                self.input_tree.selection_add(iid)
        first = start + 1 if visible else 0
        finish = start + len(visible)
        self.input_page_text.set("{}～{} / {}件（{}/{}ページ）".format(
            first, finish, len(filtered), self._input_page + 1, page_count))
        self.mapping_progress.set(
            "未割当 {} / 全{}行（一覧は最大500件ずつ表示）".format(
                self._pending_count, len(self.inputs)))

    def change_input_page(self, amount):
        page_count = max(1, (len(self._filtered_inputs) + 499) // 500)
        self._input_page = min(
            max(0, self._input_page + int(amount)), page_count - 1)
        self.refresh_input_tree()

    def jump_to_input_line(self):
        try:
            line = int(self.input_jump_line.get())
        except (TypeError, ValueError):
            return
        self._select_input_line(line, seek=True)

    def selected_input_lines(self):
        result = []
        if not hasattr(self, "input_tree"):
            return result
        for iid in self.input_tree.selection():
            if iid.startswith("input-"):
                try:
                    result.append(int(iid.split("-", 1)[1]))
                except ValueError:
                    pass
        return sorted(result)

    def on_input_selected(self, _event=None):
        if self._selection_from_video:
            return
        self.seek_selected_input()

    def seek_selected_input(self):
        lines = self.selected_input_lines()
        if not lines:
            return
        item = self.input_by_line.get(lines[0])
        if item:
            global_video_time = (
                float(item.get("time", 0.0)) + float(self.video_sync.get()))
            self._select_video_for_session_time(global_video_time)
            self.seek_video(global_video_time - self.video_time_origin)

    def _select_video_for_session_time(self, session_time):
        """Switch to the paused segment containing a global input time."""
        if len(self.video_sources) <= 1:
            return
        value = float(session_time)
        for label, (start, end) in self.video_source_ranges.items():
            if start <= value <= end + 0.001:
                if self.video_choice.get() != label:
                    self.video_choice.set(label)
                    self.open_selected_video()
                return

    def select_pending(self, forward):
        selected = self.selected_input_lines()
        current = (selected[-1] if forward else selected[0]) if selected else 0
        line = pending_neighbor(self.inputs, self.mappings, current, forward=forward)
        if line is None:
            self.status.set("未割当の入力はありません。")
            return
        self._select_input_line(line, seek=True)

    def _select_input_line(self, line, seek=False):
        iid = "input-{}".format(int(line))
        if not self.input_tree.exists(iid):
            position = next(
                (index for index, (item, _mapping) in enumerate(self._filtered_inputs)
                 if int(item.get("line", 0)) == int(line)), -1)
            if position >= 0:
                self._input_page = position // 500
                self.refresh_input_tree()
        if not self.input_tree.exists(iid):
            return
        self._selection_from_video = not seek
        try:
            self.input_tree.selection_set(iid)
            self.input_tree.see(iid)
        finally:
            self._selection_from_video = False
        if seek:
            self.seek_selected_input()

    def _selected_mapping(self):
        selected = self.mapping_tree.selection()
        return self.mapping_by_iid.get(selected[0]) if selected else None

    def refresh_mapping_tree(self):
        self.mapping_tree.delete(*self.mapping_tree.get_children())
        self.mapping_by_iid = {}
        for index, item in enumerate(self.mappings):
            iid = "mapping-{}".format(index)
            self.mapping_by_iid[iid] = item
            name = item.get("step_name") if item.get("kind") == "step" else item.get("function_name")
            self.mapping_tree.insert("", "end", iid=iid, values=(
                "{}〜{}".format(item["start_line"], item["end_line"]),
                KIND_NAMES.get(item.get("kind"), item.get("kind", "")), name or "-",
                item.get("notes", "")))

    def edit_selected_mapping(self, _event=None):
        item = self._selected_mapping()
        if not item:
            return
        self._mapping_edit_id = item.get("id")
        self._mapping_edit_range = (int(item["start_line"]), int(item["end_line"]))
        self.mapping_kind.set(KIND_NAMES.get(item.get("kind"), "直接処理として残す"))
        self.mapping_step.set(item.get("step_name", ""))
        self.mapping_next_step.set(item.get("next_step", ""))
        self.mapping_function.set(item.get("function_name", ""))
        self.mapping_call_step.set(item.get("call_from_step", ""))
        self.mapping_notes.set(item.get("notes", ""))
        self.mapping_start_line.set(str(item["start_line"]))
        self.mapping_end_line.set(str(item["end_line"]))
        self.mapping_save_button.configure(text="選択した割当を更新")
        iids = ["input-{}".format(line) for line in
                range(int(item["start_line"]), int(item["end_line"]) + 1)
                if self.input_tree.exists("input-{}".format(line))]
        if iids:
            self.input_tree.selection_set(iids)
            self.input_tree.see(iids[0])

    def clear_mapping_form(self):
        self._mapping_edit_id = None
        self._mapping_edit_range = None
        self.mapping_start_line.set("")
        self.mapping_end_line.set("")
        self.mapping_save_button.configure(text="＋ 選択範囲を登録")
        self.mapping_tree.selection_remove(self.mapping_tree.selection())

    def use_selected_mapping_range(self):
        lines = self.selected_input_lines()
        if lines:
            self.mapping_start_line.set(str(lines[0]))
            self.mapping_end_line.set(str(lines[-1]))

    def exclude_selected_inputs(self):
        """Register selected contiguous input rows as intentionally ignored."""
        lines = self.selected_input_lines()
        if not lines:
            messagebox.showinfo(
                "Commandsから除外", "除外する入力行を選択してください。", parent=self)
            return
        if lines != list(range(lines[0], lines[-1] + 1)):
            messagebox.showwarning(
                "Commandsから除外",
                "除外する行は連続して選択してください。離れた範囲は分けて登録できます。",
                parent=self)
            return
        # Always create a new ignore mapping.  A mapping selected in the lower
        # list must not be silently converted or moved by this shortcut.
        self.clear_mapping_form()
        self.mapping_kind.set(KIND_NAMES["ignore"])
        self.mapping_step.set("")
        self.mapping_next_step.set("")
        self.mapping_function.set("")
        self.mapping_call_step.set("")
        self.mapping_notes.set("Commands生成から除外")
        self.mapping_start_line.set(str(lines[0]))
        self.mapping_end_line.set(str(lines[-1]))
        self.save_mapping()

    def save_mapping(self):
        lines = self.selected_input_lines()
        start_text = self.mapping_start_line.get().strip()
        end_text = self.mapping_end_line.get().strip()
        if start_text or end_text:
            try:
                start_line = int(start_text)
                end_line = int(end_text)
                if start_line > end_line:
                    start_line, end_line = end_line, start_line
                if start_line not in self.input_by_line or end_line not in self.input_by_line:
                    raise ValueError
                lines = list(range(start_line, end_line + 1))
            except (TypeError, ValueError):
                messagebox.showwarning(
                    "割当", "存在する入力行の開始番号と終了番号を指定してください。", parent=self)
                return
        if not self.session_dir or not lines:
            messagebox.showinfo("割当", "入力記録の連続した行を選択してください。", parent=self)
            return
        if lines != list(range(lines[0], lines[-1] + 1)):
            messagebox.showwarning("割当", "飛び飛びではなく連続した行を選択してください。", parent=self)
            return
        kind = KIND_LABELS.get(self.mapping_kind.get(), "raw")
        if kind == "step" and not self.mapping_step.get().strip():
            messagebox.showwarning("割当", "Step名を入力してください。", parent=self)
            return
        if kind == "function" and not self.mapping_function.get().strip():
            messagebox.showwarning("割当", "関数名を入力してください。", parent=self)
            return
        item = {
            "id": self._mapping_edit_id or uuid.uuid4().hex,
            "start_line": lines[0], "end_line": lines[-1], "kind": kind,
            "step_name": self.mapping_step.get().strip(),
            "next_step": self.mapping_next_step.get().strip(),
            "function_name": self.mapping_function.get().strip(),
            "call_from_step": self.mapping_call_step.get().strip(),
            "notes": self.mapping_notes.get().strip(),
        }
        if kind == "function" and not item["call_from_step"]:
            parent_step = next((old for old in self.mappings
                                if old.get("kind") == "step"
                                and int(old["start_line"]) <= lines[0]
                                and int(old["end_line"]) >= lines[-1]), None)
            if parent_step:
                item["call_from_step"] = parent_step.get("step_name", "")
                self.mapping_call_step.set(item["call_from_step"])

        def permitted_nested(old):
            old_start, old_end = int(old["start_line"]), int(old["end_line"])
            if old.get("kind") == "step" and kind in ("function", "ignore"):
                parent_matches = (kind == "ignore" or not item["call_from_step"]
                                  or item["call_from_step"] == old.get("step_name", ""))
                return old_start <= lines[0] and old_end >= lines[-1] and parent_matches
            if kind == "step" and old.get("kind") in ("function", "ignore"):
                parent_matches = (old.get("kind") == "ignore"
                                  or old.get("call_from_step", "") == item["step_name"])
                return lines[0] <= old_start and lines[-1] >= old_end and parent_matches
            return False

        overlaps = [old for old in self.mappings if old.get("id") != self._mapping_edit_id
                    and not (int(old["end_line"]) < lines[0]
                            or int(old["start_line"]) > lines[-1])
                    and not permitted_nested(old)]
        if overlaps and not messagebox.askyesno(
                "割当範囲の重複", "重なる既存割当を削除して登録しますか？", parent=self):
            return
        self.mappings = [old for old in self.mappings
                         if old.get("id") != self._mapping_edit_id and old not in overlaps]
        self.mappings.append(item)
        self.mappings = save_mappings(self.session_dir, self.mappings)
        self._rebuild_mapping_index()
        self.clear_mapping_form()
        self.refresh_mapping_tree()
        self.refresh_input_tree()
        self.generate_code(select_tab=False)
        self.status.set("割当をmappings.jsonへ保存しました。閉じても残ります。")

    def delete_mapping(self):
        item = self._selected_mapping()
        if not item:
            return
        if not messagebox.askyesno("割当を削除", "選択した割当だけ削除しますか？", parent=self):
            return
        self.mappings = save_mappings(
            self.session_dir, [old for old in self.mappings if old.get("id") != item.get("id")])
        self._rebuild_mapping_index()
        self.clear_mapping_form()
        self.refresh_mapping_tree()
        self.refresh_input_tree()
        self.generate_code(select_tab=False)

    def generate_code(self, select_tab=True, preserve_revision=None):
        if not self.session:
            return ""
        if preserve_revision is None:
            # UI button presses preserve a comparison revision.  Automatic
            # refreshes caused by mapping/target edits update only current.py.
            preserve_revision = bool(select_tab)
        target_mode = GENERATION_TARGET_LABELS.get(
            self.generation_target.get(), GENERATION_TARGET_SWITCH)
        stick_mode = STICK_MODE_LABELS.get(
            self.stick_angle_mode.get(), STICK_MODE_EXACT)
        generation = self.session.setdefault("generation", {})
        generation_changed = (
            generation.get("input_target") != target_mode
            or generation.get("stick_angle_mode") != stick_mode
            or generation.get("image_mode") !=
            "shared_logical_name_with_platform_overrides")
        generation["input_target"] = target_mode
        generation["stick_angle_mode"] = stick_mode
        generation["image_mode"] = "shared_logical_name_with_platform_overrides"
        if generation_changed and self.session_dir:
            atomic_json(os.path.join(self.session_dir, "session.json"), self.session)
        generated = generate_intermediate(
            self.session, self.inputs, self.mappings,
            generation_target=target_mode, stick_mode=stick_mode)
        self.intermediate_text.delete("1.0", "end")
        self.intermediate_text.insert("1.0", generated)
        target = os.path.join(self.session_dir, "source", "intermediate.py")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        _write_text_atomic(target, generated)
        if preserve_revision:
            self._latest_intermediate_revision = save_intermediate_revision(
                self.session_dir, generated,
                generation_target=target_mode + "_" + stick_mode)
            revisions = intermediate_revisions(self.session_dir)
            generation["intermediate_history"] = revisions
            generation["latest_intermediate_revision"] = \
                self._latest_intermediate_revision
            generation["isolated_from_final_source"] = True
            atomic_json(os.path.join(self.session_dir, "session.json"), self.session)
        if select_tab:
            self.code_tabs.select(0)
        self.status.set(
            "中間ファイルを保存しました{}: {}".format(
                "（比較用履歴も保存）" if preserve_revision else "", target))
        return generated

    def compare_intermediate_revisions(self):
        revisions = intermediate_revisions(self.session_dir) if self.session_dir else []
        if len(revisions) < 2:
            messagebox.showinfo(
                "中間履歴差分",
                "［④ 中間コード生成］を2回以上実行すると前回との差分を確認できます。",
                parent=self)
            return ""
        previous, current = revisions[-2], revisions[-1]
        try:
            before = _read_source(previous)
            after = _read_source(current)
        except OSError as error:
            messagebox.showerror("中間履歴差分", str(error), parent=self)
            return ""
        diff = unified_diff(before, after, previous, current)
        viewer = self.intermediate_history_diff_text
        viewer.delete("1.0", "end")
        viewer.insert("1.0", diff or "差分はありません。\n")
        for number, line in enumerate((diff or "").splitlines(), 1):
            if line.startswith("+") and not line.startswith("+++"):
                viewer.tag_add("add", "{}.0".format(number), "{}.end".format(number))
            elif line.startswith("-") and not line.startswith("---"):
                viewer.tag_add("delete", "{}.0".format(number), "{}.end".format(number))
        self.code_tabs.select(viewer.master)
        self.status.set("直近2回の中間コードを比較しています。")
        return diff

    def open_intermediate_history(self):
        if not self.session_dir:
            return
        folder = debug_output_paths(self.session_dir)["intermediate_history"]
        os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)
        except (AttributeError, OSError):
            pass

    def open_debug_command(self):
        path = debug_output_paths(self.session_dir)["working"] if self.session_dir else ""
        if not path or not os.path.isfile(path):
            messagebox.showinfo(
                "デバッグCommands", "先に［動画解析＋デバッグCommands生成］を実行してください。",
                parent=self)
            return
        self.debug_command_path.set(path)
        if self.open_source_callback:
            self.open_source_callback(path)

    def deploy_debug_command(self):
        if not self.session_dir or not self.session:
            return
        paths = debug_output_paths(self.session_dir)
        working = paths["working"]
        if not os.path.isfile(working):
            messagebox.showinfo(
                "Commandsへ配置", "先にデバッグCommandsを生成してください。", parent=self)
            return
        try:
            target = deploy_debug_command_file(
                working, self.code_root_provider(),
                self.session.get("session_id", "operation"),
                backup_dir=os.path.join(paths["root"], "deployed_history"))
        except (OSError, SyntaxError, ValueError) as error:
            messagebox.showerror("Commandsへ配置", str(error), parent=self)
            return
        generation = self.session.setdefault("generation", {})
        generation["debug_command_deployed"] = {
            "path": target,
            "deployed_at": datetime.datetime.now().astimezone().isoformat(),
            "debug_only": True,
            "final_source_unchanged": True,
        }
        atomic_json(os.path.join(self.session_dir, "session.json"), self.session)
        self.status.set("デバッグCommandsを配置しました。PokeConでCommandsを再読込してください: " + target)
        messagebox.showinfo(
            "Commandsへ配置",
            "デバッグ専用フォルダへ配置しました。\nPokeConのCommandsを再読込して、"
            "[DEBUG]で始まるコマンドを選択してください。\n\n" + target,
            parent=self)

    def load_video_vision_sample(self):
        """Load the optional sample without running video analysis on session open."""
        self.vision_sample_text.delete("1.0", "end")
        if not self.session_dir:
            return ""
        path = vision_output_paths(self.session_dir)["source"]
        try:
            with open(path, "r", encoding="utf-8") as stream:
                source = stream.read()
        except OSError:
            source = (
                "動画判断サンプルはまだ生成されていません。\n\n"
                "［動画判断サンプル］を押すと、Step終端付近の映像から\n"
                "画面遷移の判定に使えそうな領域を自動抽出します。\n"
                "通常の中間コードやソース反映には自動で混ざりません。\n")
        self.vision_sample_text.insert("1.0", source)
        return source

    def _vision_video_path(self):
        outputs = self.session.get("outputs", {}) if self.session else {}
        clean = outputs.get("clean_video", "") if isinstance(outputs, dict) else ""
        if clean and os.path.isfile(clean):
            return os.path.abspath(clean)
        selected = self.video_sources.get(self.video_choice.get(), "")
        if selected and os.path.isfile(selected):
            return os.path.abspath(selected)
        return ""

    def generate_video_vision_sample(self):
        if self._vision_generation_running:
            return
        if not self.session_dir or not self.session:
            messagebox.showinfo(
                "動画判断サンプル", "先に操作セッションを読み込んでください。", parent=self)
            return
        video_path = self._vision_video_path()
        if not video_path:
            messagebox.showinfo(
                "動画判断サンプル",
                "解析できる映像がありません。PokeConで［完了・結合］してください。",
                parent=self)
            return
        manual_steps = any(item.get("kind") == "step" for item in self.mappings)
        if manual_steps:
            # This explicit debug generation keeps an immutable intermediate
            # revision. Mapping auto-refreshes do not create noisy revisions.
            debug_mappings = [dict(item) for item in self.mappings]
            intermediate_source = self.generate_code(
                select_tab=False, preserve_revision=True)
            intermediate_revision = self._latest_intermediate_revision
            debug_inputs = [dict(item) for item in self.inputs]
        else:
            # With a long paused recording, use roughly one minute around the
            # currently displayed video position.  These draft Steps live only
            # in debug_command and can never enter the final apply path.
            session_time = (float(self.current_time) + float(self.video_time_origin)
                            - float(self.video_sync.get()))
            debug_mappings = build_debug_draft_mappings(
                self.inputs, center_time=session_time)
            debug_inputs = [
                dict(item) for item in self.inputs
                if any(int(mapping["start_line"]) <= int(item.get("line", 0))
                       <= int(mapping["end_line"]) for mapping in debug_mappings)
            ]
            target_mode = GENERATION_TARGET_LABELS.get(
                self.generation_target.get(), GENERATION_TARGET_SWITCH)
            stick_mode = STICK_MODE_LABELS.get(
                self.stick_angle_mode.get(), STICK_MODE_EXACT)
            intermediate_source = generate_intermediate(
                self.session, debug_inputs, debug_mappings,
                generation_target=target_mode, stick_mode=stick_mode)
            intermediate_revision = save_intermediate_revision(
                self.session_dir, intermediate_source,
                generation_target=target_mode + "_" + stick_mode + "_auto_debug")
            self._latest_intermediate_revision = intermediate_revision
            self.status.set(
                "未割当のため、現在の動画位置付近からデバッグ専用の仮Stepを作成しています。")
        if not debug_mappings:
            messagebox.showinfo(
                "デバッグCommands", "デバッグ用に利用できる入力行がありません。", parent=self)
            return
        self._vision_generation_running = True
        self.vision_sample_button.configure(state="disabled")
        self.status.set("動画から画面判断候補を抽出しています...")
        session_dir = self.session_dir
        session = dict(self.session)
        inputs = debug_inputs
        mappings = [dict(item) for item in debug_mappings]
        sync_offset = float(self.video_sync.get()) - self.video_time_origin

        def worker():
            try:
                metadata = analyse_operation_video(
                    session_dir, session, inputs, mappings, video_path,
                    video_sync_offset=sync_offset)
                source = generate_vision_sample(session_dir, session, metadata)
                source_path = vision_output_paths(session_dir)["source"]
                _write_text_atomic(source_path, source)
                debug_manifest = create_debug_command_package(
                    session_dir, session, intermediate_source, source,
                    metadata, mappings,
                    intermediate_revision=intermediate_revision)
            except Exception as error:  # Report codec/OpenCV/file failures in the UI.
                try:
                    self.after(0, lambda value=str(error):
                               self._finish_video_vision_sample(error=value))
                except tk.TclError:
                    pass
                return
            try:
                self.after(0, lambda: self._finish_video_vision_sample(
                    source=source, metadata=metadata, source_path=source_path,
                    debug_manifest=debug_manifest))
            except tk.TclError:
                pass

        threading.Thread(target=worker, name="OperationVisionSample", daemon=True).start()

    def _finish_video_vision_sample(self, source="", metadata=None,
                                    source_path="", error="",
                                    debug_manifest=None):
        self._vision_generation_running = False
        self.vision_sample_button.configure(state="normal")
        if error:
            self.status.set("動画判断サンプルを生成できませんでした: " + error)
            messagebox.showerror("動画判断サンプル", error, parent=self)
            return
        self.vision_sample_text.delete("1.0", "end")
        self.vision_sample_text.insert("1.0", source)
        generation = self.session.setdefault("generation", {})
        generation["vision_sample"] = {
            "source": source_path,
            "metadata": vision_output_paths(self.session_dir)["metadata"],
            "candidate_count": int((metadata or {}).get("candidate_count", 0)),
            "generated_at": datetime.datetime.now().astimezone().isoformat(),
            "separate_from_intermediate": True,
        }
        if debug_manifest:
            generation["debug_command"] = dict(debug_manifest)
            self.debug_command_path.set(debug_manifest.get("working", ""))
        atomic_json(os.path.join(self.session_dir, "session.json"), self.session)
        self.code_tabs.select(self.vision_sample_text.master)
        count = generation["vision_sample"]["candidate_count"]
        self.status.set(
            "動画判断とデバッグCommandsを保存しました（候補 {}件・要レビュー）: {}".format(
                count, (debug_manifest or {}).get("working", source_path)))

    def _generation_target_changed(self):
        if not self.session_dir or not self.session:
            return
        target_mode = GENERATION_TARGET_LABELS.get(
            self.generation_target.get(), GENERATION_TARGET_SWITCH)
        stick_mode = STICK_MODE_LABELS.get(
            self.stick_angle_mode.get(), STICK_MODE_EXACT)
        generation = self.session.setdefault("generation", {})
        if (generation.get("input_target") == target_mode
                and generation.get("stick_angle_mode") == stick_mode
                and generation.get("image_mode") ==
                "shared_logical_name_with_platform_overrides"):
            return
        generation["input_target"] = target_mode
        generation["stick_angle_mode"] = stick_mode
        generation["image_mode"] = "shared_logical_name_with_platform_overrides"
        atomic_json(os.path.join(self.session_dir, "session.json"), self.session)
        self.generate_code(select_tab=False)

    def choose_source(self):
        path = filedialog.askopenfilename(
            parent=self, title="反映先Commandsソースを選択",
            initialdir=self.source_path.get() or self.code_root_provider(),
            filetypes=(("Python", "*.py"), ("すべて", "*.*")))
        if path:
            self.source_path.set(os.path.abspath(path))
            self.load_source_classes()
            self.refresh_final_preview()

    def load_source_classes(self):
        path = self.source_path.get().strip()
        try:
            names = source_class_names(_read_source(path))
        except OSError:
            names = []
        self.source_class_combo.configure(values=names)
        if self.source_class.get() not in names:
            self.source_class.set(names[0] if names else "")

    def refresh_final_preview(self, select_tab=True):
        path = self.source_path.get().strip()
        if not path or not os.path.isfile(path) or not self.session:
            if select_tab:
                messagebox.showinfo("差分", "最終ソースを選択してください。", parent=self)
            return None
        try:
            original = _read_source(path)
            generated = self.intermediate_text.get("1.0", "end-1c") or self.generate_code(False)
            updated = replace_generated_region(
                original, generated, self.session.get("session_id", "operation"),
                class_name=self.source_class.get().strip() or None)
            ast.parse(updated)
        except (OSError, ValueError, SyntaxError) as error:
            messagebox.showerror("差分生成", str(error), parent=self)
            return None
        self.final_text.delete("1.0", "end")
        self.final_text.insert("1.0", updated)
        diff = unified_diff(original, updated, path, path + " (操作記録反映後)")
        self.diff_text.delete("1.0", "end")
        self.diff_text.insert("1.0", diff or "差分はありません。\n")
        for number, line in enumerate((diff or "").splitlines(), 1):
            if line.startswith("+") and not line.startswith("+++"):
                self.diff_text.tag_add("add", "{}.0".format(number), "{}.end".format(number))
            elif line.startswith("-") and not line.startswith("---"):
                self.diff_text.tag_add("delete", "{}.0".format(number), "{}.end".format(number))
        if select_tab:
            self.code_tabs.select(2)
        return updated

    def apply_to_source(self):
        path = self.source_path.get().strip()
        updated = self.refresh_final_preview(select_tab=True)
        if updated is None:
            return
        if pending_lines(self.inputs, self.mappings):
            messagebox.showwarning(
                "未割当あり", "未割当入力が残っています。すべて割当または［反映不要］にしてください。",
                parent=self)
            return
        if not messagebox.askyesno(
                "最終ソースへ反映", "表示中の差分をソースへ反映しますか？\n"
                "操作セッション内へ日時付きバックアップを作成します。", parent=self):
            return
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(self.session_dir, "source", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup = os.path.join(
            backup_dir, os.path.basename(path) + ".operation-" + stamp + ".bak")
        try:
            shutil.copy2(path, backup)
            _write_text_atomic(path, updated)
            self.session["final_source"] = os.path.abspath(path)
            self.session["source_backup"] = backup
            atomic_json(os.path.join(self.session_dir, "session.json"), self.session)
        except OSError as error:
            messagebox.showerror("ソース反映", str(error), parent=self)
            return
        self.status.set("ソースへ反映しました。バックアップ: " + backup)
        messagebox.showinfo("ソース反映", "反映しました。\nバックアップ:\n" + backup, parent=self)

    def open_source_in_editor(self):
        path = self.source_path.get().strip()
        if path and self.open_source_callback:
            self.open_source_callback(path)

    def refresh_video_sources(self):
        sources = operation_video_sources(self.session)
        self.video_sources = {item["label"]: item["path"] for item in sources}
        self.video_source_origins = {
            item["label"]: float(item.get("timeline_start", 0.0))
            for item in sources
        }
        self.video_source_ranges = {
            item["label"]: (
                float(item.get("timeline_start", 0.0)),
                float(item.get("timeline_start", 0.0))
                + float(item.get("duration", 0.0)))
            for item in sources
        }
        labels = list(self.video_sources)
        self.video_combo.configure(values=labels)
        self.video_choice.set(labels[0] if labels else "")
        if labels:
            self.open_selected_video()
        else:
            self.video_label.configure(
                text="再生できる区間がまだありません。PokeConで一時停止してから再読込してください。",
                image="")

    def close_video(self):
        capture, self.video_capture = self.video_capture, None
        if capture is not None:
            capture.release()

    def open_selected_video(self):
        if cv2 is None or Image is None:
            self.status.set("OpenCVまたはPillowがないため映像を表示できません。")
            return
        path = self.video_sources.get(self.video_choice.get(), "")
        self.video_time_origin = float(
            self.video_source_origins.get(self.video_choice.get(), 0.0))
        self.stop_video()
        self.close_video()
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            self.status.set("映像を開けません: " + path)
            return
        self.video_capture = capture
        self.video_fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        self.video_duration = frames / max(1.0, self.video_fps)
        self.video_slider.configure(to=max(0.001, self.video_duration))
        self.seek_video(min(self.current_time, self.video_duration), update_nearby=True)

    @staticmethod
    def _clock(value):
        value = max(0.0, float(value))
        minutes = int(value // 60)
        return "{:02d}:{:06.3f}".format(minutes, value - minutes * 60)

    def _update_time_text(self):
        self.video_time_text.set("{} / {}".format(
            self._clock(self.current_time), self._clock(self.video_duration)))

    def on_video_slider(self, value):
        if self.playing:
            return
        try:
            target = float(value)
        except (TypeError, ValueError):
            return
        self.current_time = target
        self._update_time_text()
        if hasattr(self, "_slider_seek_job"):
            try:
                self.after_cancel(self._slider_seek_job)
            except tk.TclError:
                pass
        self._slider_seek_job = self.after(100, lambda: self.seek_video(target))

    def seek_video(self, target, update_nearby=False):
        if self.video_capture is None:
            return
        self.stop_video()
        target = min(max(0.0, float(target)), max(0.0, self.video_duration))
        self.video_capture.set(cv2.CAP_PROP_POS_MSEC, target * 1000.0)
        ok, frame = self.video_capture.read()
        if not ok:
            return
        self.current_time = target
        self.current_frame = frame
        self.video_slider.set(target)
        self._show_frame(frame)
        self._update_time_text()
        self.highlight_input_at_time(target)
        if update_nearby:
            self.update_nearby_frames()

    def _show_frame(self, frame):
        if Image is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        width = max(320, self.video_label.winfo_width() - 8)
        height = max(180, self.video_label.winfo_height() - 8)
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        self._video_photo = ImageTk.PhotoImage(image)
        self.video_label.configure(image=self._video_photo, text="")

    def nudge_video(self, amount):
        self.seek_video(self.current_time + float(amount), update_nearby=True)

    def toggle_play(self):
        if self.playing:
            self.stop_video()
            return
        if self.video_capture is None:
            return
        self.playing = True
        self.play_button.configure(text="Ⅱ 一時停止")
        self._play_wall = time.monotonic()
        self._play_origin = self.current_time
        self.video_capture.set(cv2.CAP_PROP_POS_MSEC, self.current_time * 1000.0)
        self._play_tick()

    def _play_tick(self):
        if not self.playing or self.video_capture is None:
            return
        target = self._play_origin + (time.monotonic() - self._play_wall)
        if target >= self.video_duration:
            self.seek_video(self.video_duration)
            return
        # Decode sequentially during normal playback.  Random-seeking an MP4
        # for every displayed frame is expensive and made other DevStudio tabs
        # sluggish.  Correct only meaningful drift against wall time.
        decoded_at = float(self.video_capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
        if abs(decoded_at - target) > 0.15:
            self.video_capture.set(cv2.CAP_PROP_POS_MSEC, target * 1000.0)
        else:
            for _index in range(max(0, int(round(self.video_fps / 30.0)) - 1)):
                self.video_capture.grab()
        ok, frame = self.video_capture.read()
        if not ok:
            self.stop_video()
            return
        self.current_time = target
        self.current_frame = frame
        self.video_slider.set(target)
        self._show_frame(frame)
        self._update_time_text()
        self.highlight_input_at_time(target)
        self._play_job = self.after(33, self._play_tick)

    def stop_video(self):
        self.playing = False
        self.play_button.configure(text="▶ 再生")
        if self._play_job is not None:
            try:
                self.after_cancel(self._play_job)
            except tk.TclError:
                pass
            self._play_job = None

    def highlight_input_at_time(self, video_time):
        if not self.input_times:
            return
        input_time = (float(video_time) + self.video_time_origin
                      - float(self.video_sync.get()))
        index = bisect.bisect_right(self.input_times, input_time) - 1
        if index < 0:
            return
        line = int(self.inputs[index].get("line", 0))
        if line != self._last_highlight_line:
            self._last_highlight_line = line
            self._select_input_line(line, seek=False)

    def update_nearby_frames(self):
        path = self.video_sources.get(self.video_choice.get(), "")
        if not path or cv2 is None or Image is None:
            return
        offsets = (-1.0, -0.5, 0.0, 0.5, 1.0)
        capture = cv2.VideoCapture(path)
        photos = []
        for label, offset in zip(self.nearby_labels, offsets):
            target = min(max(0.0, self.current_time + offset), self.video_duration)
            capture.set(cv2.CAP_PROP_POS_MSEC, target * 1000.0)
            ok, frame = capture.read()
            if not ok:
                label.configure(image="", text="取得不可")
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            image.thumbnail((160, 90), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            photos.append(photo)
            label.configure(image=photo, text=self._clock(target), compound="top")
            label.bind("<Button-1>", lambda _event, value=target: self.seek_video(value))
        capture.release()
        self._nearby_photos = photos

    def save_video_sync(self):
        if not self.session_dir:
            return
        self.session["video_sync_offset"] = float(self.video_sync.get())
        atomic_json(os.path.join(self.session_dir, "session.json"), self.session)
        self.status.set("入力と映像の同期補正を保存しました。")

    def open_frame_capture(self):
        if self.current_frame is None or Image is None:
            messagebox.showinfo("画像検知", "先に映像の対象フレームを表示してください。", parent=self)
            return
        FrameCaptureDialog(
            self, self.current_frame.copy(), self.session_dir, self.session,
            self.current_time + self.video_time_origin,
            self._captured_image_ready)

    def _captured_image_ready(self, path, crop, name, open_library):
        self.status.set("1280x720元映像から画像を保存しました: " + path)
        if open_library and self.open_image_callback:
            self.open_image_callback(path, crop, name)

    def destroy(self):
        self.stop_video()
        self.close_video()
        ttk.Frame.destroy(self)


class FrameCaptureDialog(tk.Toplevel):
    """Select an exact 1280x720 ROI and hand it to DevStudio image detection."""

    def __init__(self, parent, frame, session_dir, session, video_time, callback):
        tk.Toplevel.__init__(self, parent)
        self.title("現在フレームから画像検知を作成")
        self.transient(parent.winfo_toplevel())
        self.frame = frame
        self.session_dir = session_dir
        self.session = session
        self.video_time = float(video_time)
        self.callback = callback
        self.name = tk.StringVar(value="OPERATION_{}".format(int(self.video_time * 1000)))
        self.coords = tk.StringVar()
        self.start = None
        self.rectangle = None
        self.scale = min(960.0 / frame.shape[1], 540.0 / frame.shape[0])
        width, height = int(frame.shape[1] * self.scale), int(frame.shape[0] * self.scale)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb).resize((width, height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        ttk.Label(self, text=("ドラッグで検知対象だけを四角く囲みます。座標は元の1280x720基準で保存され、"
                             "Area Captureと同じ範囲を画像検知へ渡します。"),
                  foreground="#174a7e", wraplength=940).pack(fill="x", padx=8, pady=6)
        form = ttk.Frame(self)
        form.pack(fill="x", padx=8)
        ttk.Label(form, text="検知名:").pack(side="left")
        ttk.Entry(form, textvariable=self.name, width=34).pack(side="left", padx=3)
        ttk.Label(form, textvariable=self.coords).pack(side="right")
        self.canvas = tk.Canvas(self, width=width, height=height, highlightthickness=0)
        self.canvas.pack(padx=8, pady=6)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.bind("<ButtonPress-1>", self.begin_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        # A visible initial ROI makes the workflow understandable immediately;
        # the user can drag anywhere to replace it.
        self.set_rectangle(width * 0.25, height * 0.25, width * 0.75, height * 0.75)
        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(actions, text="画像だけ保存", command=lambda: self.save(False)).pack(side="left")
        ttk.Button(actions, text="保存して画像検知タブで調整", command=lambda: self.save(True)).pack(
            side="left", padx=4)
        ttk.Button(actions, text="閉じる", command=self.destroy).pack(side="right")

    def begin_drag(self, event):
        self.start = (event.x, event.y)

    def drag(self, event):
        if self.start:
            self.set_rectangle(self.start[0], self.start[1], event.x, event.y)

    def end_drag(self, event):
        self.drag(event)
        self.start = None

    def set_rectangle(self, x1, y1, x2, y2):
        width, height = self.frame.shape[1], self.frame.shape[0]
        max_x, max_y = width * self.scale, height * self.scale
        x1, x2 = sorted((max(0, min(max_x, x1)), max(0, min(max_x, x2))))
        y1, y2 = sorted((max(0, min(max_y, y1)), max(0, min(max_y, y2))))
        self.selection = (int(x1 / self.scale), int(y1 / self.scale),
                          int(x2 / self.scale), int(y2 / self.scale))
        if self.rectangle is None:
            self.rectangle = self.canvas.create_rectangle(
                x1, y1, x2, y2, outline="#00ffff", width=3)
        else:
            self.canvas.coords(self.rectangle, x1, y1, x2, y2)
        self.coords.set("元映像範囲: {},{},{},{}".format(*self.selection))

    def save(self, open_library):
        x1, y1, x2, y2 = self.selection
        if x2 - x1 < 2 or y2 - y1 < 2:
            messagebox.showwarning("画像検知", "2px以上の範囲を囲んでください。", parent=self)
            return
        name = re.sub(r"[^0-9A-Za-z_.-]+", "_", self.name.get().strip()).strip("._")
        if not name:
            messagebox.showwarning("画像検知", "検知名を入力してください。", parent=self)
            return
        session_id = str(self.session.get("session_id", "operation"))
        template_root = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "SerialController", "Template",
            "OperationCaptures", session_id))
        os.makedirs(template_root, exist_ok=True)
        path = os.path.join(template_root, name + ".png")
        if os.path.exists(path) and not messagebox.askyesno(
                "画像を更新", "同名画像を更新しますか？", parent=self):
            return
        crop_image = self.frame[y1:y2, x1:x2]
        if not cv2.imwrite(path, crop_image):
            messagebox.showerror("画像検知", "画像を保存できませんでした。", parent=self)
            return
        metadata = {
            "schema_version": 2, "session_id": session_id, "video_time": self.video_time,
            "source_frame_size": [int(self.frame.shape[1]), int(self.frame.shape[0])],
            "crop": [x1, y1, x2, y2], "template_path": path, "name": name,
            # All platforms intentionally share the captured image initially.
            # A later editor can replace just one entry without renaming the
            # logical detection used by generated Commands code.
            "logical_name": name,
            "platform_templates": {
                "switch": path, "steam": path, "ps4": path,
            },
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        captures = os.path.join(self.session_dir, "captures")
        os.makedirs(captures, exist_ok=True)
        atomic_json(os.path.join(captures, name + ".json"), metadata)
        self.callback(path, [x1, y1, x2, y2], name, open_library)
        self.destroy()
