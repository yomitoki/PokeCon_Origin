#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-modal offline UI for comparing two retained Commands runs."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import cv2
except ImportError:
    cv2 = None
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

from CommandRecordingModel import (load_command_recording,
                                   load_command_timeline,
                                   resolve_event_source)
from CommandRunComparison import (align_step_visits, apply_function_restore,
                                  compare_frames, discover_recording_folders,
                                  load_visit_frame, prepare_function_restore,
                                  step_visits, unified_function_diff)


STATUS_TEXT = {
    "match": "一致",
    "mismatch": "Step不一致",
    "baseline_only": "今回は未到達",
    "current_only": "今回だけ（再試行候補）",
}


def _clock(value):
    value = max(0.0, float(value or 0.0))
    minutes = int(value // 60)
    return "{:02d}:{:06.3f}".format(minutes, value - minutes * 60)


def _visit_text(visit):
    if not visit:
        return "-"
    suffix = " [同Step {}回目]".format(visit["occurrence"]) \
        if int(visit.get("occurrence", 1)) > 1 else ""
    return str(visit.get("step", "")) + suffix


class CommandRunComparisonWindow(tk.Toplevel):
    """Compare saved evidence only; never import or execute a Commands class."""

    def __init__(self, parent, current_folder="", seek_callback=None):
        tk.Toplevel.__init__(self, parent)
        self.title("Commands 過去実行との差分")
        self.geometry("1480x900")
        self.minsize(1050, 650)
        self.current_folder = os.path.abspath(str(current_folder or ""))
        self.seek_callback = seek_callback
        self.rows = []
        self.row_by_iid = {}
        self.current_metadata = {}
        self.baseline_metadata = {}
        self.baseline_folder = ""
        self._generation = 0
        self._selection_generation = 0
        self._photos = []
        self._restore_context = None
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self.update_context(current_folder)

    def _build(self):
        self.current_value = tk.StringVar()
        self.baseline_value = tk.StringVar()
        self.summary = tk.StringVar(value="比較する過去録画を選択してください。")
        self.status = tk.StringVar(
            value="Stepの再通過を別回として保持し、進行位置のずれを比較します。")
        self.frame_status = tk.StringVar(value="差分行を選ぶとStep開始画面を比較します。")

        guide = ttk.Label(
            self,
            text=("基準（以前ここまで進めた録画）と今回録画を比較します。"
                  " 同じStepへ戻った場合も通過回ごとに残します。新しい録画は画像検知表示前の生画像、"
                  "旧録画は動画フレームを使用します。"),
            foreground="#174a7e", justify="left", wraplength=1400)
        guide.pack(fill="x", padx=9, pady=(8, 4))

        chooser = ttk.Labelframe(self, text="比較するCommands録画")
        chooser.pack(fill="x", padx=8, pady=4)
        ttk.Label(chooser, text="今回:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(chooser, textvariable=self.current_value, state="readonly").grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=4, pady=3)
        ttk.Label(chooser, text="基準:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        self.baseline_combo = ttk.Combobox(
            chooser, textvariable=self.baseline_value, state="normal")
        self.baseline_combo.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(chooser, text="選択…", command=self.choose_baseline).grid(
            row=1, column=2, padx=3)
        self.compare_button = ttk.Button(
            chooser, text="Step差分を比較", command=self.compare_runs)
        self.compare_button.grid(row=1, column=3, padx=4)
        chooser.columnconfigure(1, weight=1)
        ttk.Label(self, textvariable=self.summary, anchor="w").pack(
            fill="x", padx=10, pady=(0, 4))

        split = ttk.Panedwindow(self, orient="vertical")
        split.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        top = ttk.Frame(split)
        bottom = ttk.Notebook(split)
        split.add(top, weight=4)
        split.add(bottom, weight=5)
        self._build_alignment(top)
        frame_page = ttk.Frame(bottom)
        code_page = ttk.Frame(bottom)
        bottom.add(frame_page, text="Step開始画面")
        bottom.add(code_page, text="記録時コード差分・復元")
        self._build_frames(frame_page)
        self._build_code(code_page)
        ttk.Label(self, textvariable=self.status, anchor="w").pack(
            fill="x", padx=9, pady=(0, 6))

    def _build_alignment(self, parent):
        columns = ("status", "baseline_no", "baseline_time", "baseline_step",
                   "current_no", "current_time", "current_step")
        self.tree = ttk.Treeview(
            parent, columns=columns, show="headings", selectmode="browse", height=12)
        specs = (
            ("status", "判定", 145), ("baseline_no", "基準#", 65),
            ("baseline_time", "基準時刻", 85), ("baseline_step", "基準Step", 390),
            ("current_no", "今回#", 65), ("current_time", "今回時刻", 85),
            ("current_step", "今回Step", 390),
        )
        for name, label, width in specs:
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, stretch=name.endswith("step"))
        sy = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        sx = ttk.Scrollbar(parent, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        self.tree.tag_configure("baseline_only", background="#ffe0b2")
        self.tree.tag_configure("current_only", background="#e1f5fe")
        self.tree.tag_configure("mismatch", background="#ffcdd2")
        self.tree.bind("<<TreeviewSelect>>", self.on_row_selected)

    def _build_frames(self, parent):
        ttk.Label(parent, textvariable=self.frame_status, anchor="w", wraplength=1370).pack(
            fill="x", padx=5, pady=4)
        panels = ttk.Frame(parent)
        panels.pack(fill="both", expand=True, padx=4, pady=2)
        self.frame_labels = []
        for index, title in enumerate(("基準Step開始", "今回Step開始", "画面差分（ヒートマップ）")):
            holder = ttk.Labelframe(panels, text=title)
            holder.grid(row=0, column=index, sticky="nsew", padx=3)
            label = tk.Label(holder, text="未選択", background="black", foreground="white")
            label.pack(fill="both", expand=True)
            self.frame_labels.append(label)
            panels.columnconfigure(index, weight=1)
        panels.rowconfigure(0, weight=1)
        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=5, pady=3)
        ttk.Button(actions, text="今回録画をこの時刻へ移動",
                   command=self.seek_current).pack(side="left")

    def _build_code(self, parent):
        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=4, pady=3)
        ttk.Label(
            actions,
            text="上段: 基準録画↔今回録画 / 下段: 基準録画↔現在の実ソース",
            foreground="#174a7e").pack(side="left")
        self.restore_button = ttk.Button(
            actions, text="基準録画の関数へ戻す…",
            command=self.restore_function, state="disabled")
        self.restore_button.pack(side="right")
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.code_text = tk.Text(
            holder, wrap="none", font=("Consolas", 9),
            background="#171717", foreground="#e5e5e5", insertbackground="white")
        sy = ttk.Scrollbar(holder, orient="vertical", command=self.code_text.yview)
        sx = ttk.Scrollbar(holder, orient="horizontal", command=self.code_text.xview)
        self.code_text.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.code_text.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        self.code_text.configure(state="disabled")

    def update_context(self, current_folder):
        current = os.path.abspath(str(current_folder or self.current_folder or ""))
        self.current_folder = current
        self.current_value.set(current)
        candidates = discover_recording_folders(current)
        self.baseline_combo.configure(values=candidates)
        if candidates and not self.baseline_value.get():
            self.baseline_value.set(candidates[0])

    def choose_baseline(self):
        path = filedialog.askdirectory(
            parent=self, title="基準にする過去のCommands録画を選択",
            initialdir=os.path.dirname(self.current_folder) or os.getcwd())
        if path:
            self.baseline_value.set(os.path.abspath(path))

    def compare_runs(self):
        baseline = os.path.abspath(str(self.baseline_value.get() or ""))
        current = os.path.abspath(str(self.current_folder or ""))
        if not os.path.isfile(os.path.join(baseline, "command_monitor.json")):
            messagebox.showwarning("Commands実行比較", "基準録画を選択してください。", parent=self)
            return
        if not os.path.isfile(os.path.join(current, "command_monitor.json")):
            messagebox.showwarning("Commands実行比較", "今回録画を読み込めません。", parent=self)
            return
        if os.path.normcase(baseline) == os.path.normcase(current):
            messagebox.showwarning("Commands実行比較", "異なる2つの録画を選択してください。", parent=self)
            return
        self._generation += 1
        generation = self._generation
        self.compare_button.configure(state="disabled")
        self.status.set("2つのStep履歴をバックグラウンドで位置合わせしています...")

        def worker():
            try:
                base_metadata = load_command_recording(baseline)
                current_metadata = load_command_recording(current)
                base_command = str(base_metadata.get("command", "") or "")
                current_command = str(current_metadata.get("command", "") or "")
                if base_command and current_command and base_command != current_command:
                    raise ValueError(
                        "異なるCommandsの録画です: {} / {}".format(
                            base_command, current_command))
                base_events = load_command_timeline(baseline)
                current_events = load_command_timeline(current)
                rows, summary = align_step_visits(
                    step_visits(base_events), step_visits(current_events))
                result = (base_metadata, current_metadata, rows, summary)
                error = ""
            except Exception as caught:
                result, error = None, str(caught)
            try:
                self.after(0, lambda: self._finish_compare(
                    generation, baseline, current, result, error))
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True,
                         name="CommandRunStepAlignment").start()

    def _finish_compare(self, generation, baseline, current, result, error):
        if generation != self._generation:
            return
        self.compare_button.configure(state="normal")
        if error or result is None:
            self.status.set("比較失敗: " + (error or "不明なエラー"))
            return
        self.baseline_folder, self.current_folder = baseline, current
        self.baseline_metadata, self.current_metadata, self.rows, summary = result
        self.tree.delete(*self.tree.get_children())
        self.row_by_iid = {}
        divergence = summary["first_divergence"]
        divergence_text = "なし" if divergence is None else str(divergence + 1) + "行目"
        self.summary.set(
            "基準 {}通過 / 今回 {}通過 / 一致 {} / 今回未到達 {} / 今回のみ {} / Step不一致 {} / 最初の差分 {}".format(
                summary["baseline_visits"], summary["current_visits"],
                summary["matched"], summary["not_reached"],
                summary["extra_or_retry"], summary["mismatch"], divergence_text))
        if summary["regressed"]:
            self.status.set("以前の到達位置より手前で終わった可能性があります。差分行を選んで画面とコードを確認してください。")
        else:
            self.status.set("位置合わせ完了。差分行を選んでStep開始画面と記録時コードを確認してください。")
        self._populate_rows(generation, 0)

    def _populate_rows(self, generation, start):
        if generation != self._generation:
            return
        end = min(len(self.rows), start + 200)
        for index in range(start, end):
            row = self.rows[index]
            left, right = row.get("baseline"), row.get("current")
            iid = "comparison-{}".format(index)
            self.row_by_iid[iid] = row
            self.tree.insert("", "end", iid=iid, tags=(row["status"],), values=(
                STATUS_TEXT.get(row["status"], row["status"]),
                int(left["visit_index"]) + 1 if left else "-",
                _clock(left["video_time"]) if left else "-", _visit_text(left),
                int(right["visit_index"]) + 1 if right else "-",
                _clock(right["video_time"]) if right else "-", _visit_text(right)))
        if end < len(self.rows):
            self.after(1, lambda: self._populate_rows(generation, end))
        elif self.rows:
            first = next((i for i, row in enumerate(self.rows)
                          if row["status"] != "match"), 0)
            iid = "comparison-{}".format(first)
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.see(iid)

    def on_row_selected(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        row = self.row_by_iid.get(selected[0])
        if not row:
            return
        self._selection_generation += 1
        generation = self._selection_generation
        self._restore_context = None
        self.restore_button.configure(state="disabled")
        self.frame_status.set("Step開始画像とコード差分をバックグラウンドで読み込んでいます...")
        self._set_code("比較中...")

        def worker():
            try:
                payload = self._selected_row_payload(row)
                error = ""
            except Exception as caught:
                payload, error = None, str(caught)
            try:
                self.after(0, lambda: self._finish_row_load(
                    generation, row, payload, error))
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True,
                         name="CommandRunSelectedDifference").start()

    def _selected_row_payload(self, row):
        left, right = row.get("baseline"), row.get("current")

        def legacy_frame_visit(visit, metadata):
            if not visit:
                return visit
            adjusted = dict(visit)
            adjusted["video_time"] = max(
                0.0, float(visit.get("video_time", 0.0) or 0.0)
                + float(metadata.get("video_sync_offset", 0.0) or 0.0))
            return adjusted

        left_image = load_visit_frame(
            self.baseline_folder,
            legacy_frame_visit(left, self.baseline_metadata)) if left else {
            "frame": None, "kind": "missing", "warning": "基準側Stepなし", "path": ""}
        right_image = load_visit_frame(
            self.current_folder,
            legacy_frame_visit(right, self.current_metadata)) if right else {
            "frame": None, "kind": "missing", "warning": "今回側は未到達", "path": ""}
        frame_diff = compare_frames(left_image["frame"], right_image["frame"])

        left_event = left.get("event", {}) if left else {}
        right_event = right.get("event", {}) if right else {}
        left_source, left_location = resolve_event_source(
            self.baseline_folder, self.baseline_metadata, left_event) if left else ("", {})
        right_source, right_location = resolve_event_source(
            self.current_folder, self.current_metadata, right_event) if right else ("", {})
        left_function = str(left_location.get("function", "") or "")
        right_function = str(right_location.get("function", "") or "")
        target = str((right_location if right else left_location).get("file", "") or "")
        function = right_function if right_function else left_function
        sections = []
        if left_source and right_source and left_function and right_function:
            if left_function == right_function:
                difference = unified_function_diff(
                    left_source, left_function, right_source, right_function)
                sections.append("===== 基準録画 ↔ 今回録画 =====\n" + difference["text"])
            else:
                sections.append(
                    "===== 基準録画 ↔ 今回録画 =====\n関数が異なります: {} ↔ {}".format(
                        left_function, right_function))
        else:
            sections.append("===== 基準録画 ↔ 今回録画 =====\n片方のStep/記録時ソースがありません。")
        restore = None
        if left_source and left_function and target and os.path.isfile(target):
            if not right_function or right_function == left_function:
                live_diff = unified_function_diff(
                    left_source, left_function, target, left_function)
                sections.append("===== 基準録画 ↔ 現在の実ソース =====\n" + live_diff["text"])
                restore = {
                    "baseline_source": left_source, "target_source": target,
                    "function": left_function,
                }
        return {
            "left_image": left_image, "right_image": right_image,
            "frame_diff": frame_diff, "code": "\n\n".join(sections),
            "restore": restore,
        }

    def _finish_row_load(self, generation, row, payload, error):
        if generation != self._selection_generation:
            return
        if error or payload is None:
            self.frame_status.set("比較失敗: " + (error or "不明なエラー"))
            self._set_code("比較失敗: " + (error or "不明なエラー"))
            return
        similarity = payload["frame_diff"].get("similarity")
        similarity_text = "比較不可" if similarity is None else "類似度 {:.2%}".format(similarity)
        warnings = [item.get("warning", "") for item in
                    (payload["left_image"], payload["right_image"]) if item.get("warning")]
        self.frame_status.set(similarity_text + (" / " + " / ".join(warnings) if warnings else
                                                 " / 生のStep開始画像を比較"))
        frames = (
            payload["left_image"].get("frame"),
            payload["right_image"].get("frame"),
            payload["frame_diff"].get("difference"),
        )
        self._show_frames(frames)
        self._set_code(payload["code"])
        self._restore_context = payload.get("restore")
        self.restore_button.configure(
            state="normal" if self._restore_context else "disabled")

    def _show_frames(self, frames):
        self._photos = []
        for label, frame in zip(self.frame_labels, frames):
            if frame is None or Image is None or ImageTk is None or cv2 is None:
                label.configure(image="", text="画像なし")
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            image.thumbnail((450, 300), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self._photos.append(photo)
            label.configure(image=photo, text="")

    def _set_code(self, text):
        self.code_text.configure(state="normal")
        self.code_text.delete("1.0", "end")
        self.code_text.insert("1.0", str(text or ""))
        self.code_text.configure(state="disabled")

    def seek_current(self):
        selected = self.tree.selection()
        row = self.row_by_iid.get(selected[0]) if selected else None
        visit = row.get("current") if row else None
        if visit and callable(self.seek_callback):
            self.seek_callback(float(visit.get("video_time", 0.0) or 0.0))

    def restore_function(self):
        context = dict(self._restore_context or {})
        if not context:
            return
        self.restore_button.configure(state="disabled")
        self.status.set("復元内容を検証しています（まだ実ソースは変更していません）...")

        def worker():
            try:
                plan = prepare_function_restore(
                    context["baseline_source"], context["target_source"],
                    context["function"])
                error = ""
            except Exception as caught:
                plan, error = None, str(caught)
            try:
                self.after(0, lambda: self._confirm_restore(plan, error))
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True,
                         name="CommandFunctionRestorePrepare").start()

    def _confirm_restore(self, plan, error):
        self.restore_button.configure(state="normal" if self._restore_context else "disabled")
        if error or plan is None:
            messagebox.showerror("Commands関数の復元", error or "復元内容を作成できません。", parent=self)
            self.status.set("復元準備に失敗しました。")
            return
        if not plan["different"]:
            messagebox.showinfo("Commands関数の復元", "現在の実ソースは基準録画の関数と同じです。", parent=self)
            self.status.set("実ソースの変更はありません。")
            return
        backup_dir = os.path.join(
            os.path.dirname(plan["target_source_path"]), ".pokecon-command-backups")
        confirmed = messagebox.askyesno(
            "Commands関数の復元",
            "現在の実ソースの関数を、基準録画時の内容へ戻しますか？\n\n"
            "関数: {function}\n実ソース: {target}\n\n"
            "変更前ファイルは次のフォルダへ必ずバックアップします:\n{backup}\n\n"
            "確認後に実ソースが変わっていた場合は自動的に中止します。".format(
                function=plan["function_name"], target=plan["target_source_path"],
                backup=backup_dir), parent=self)
        if not confirmed:
            self.status.set("関数の復元を取り消しました。実ソースは変更していません。")
            return
        try:
            result = apply_function_restore(plan)
        except Exception as caught:
            messagebox.showerror("Commands関数の復元", str(caught), parent=self)
            self.status.set("関数の復元に失敗しました。")
            return
        self.status.set("関数を復元しました。バックアップ: " + result.get("backup", ""))
        messagebox.showinfo(
            "Commands関数の復元",
            "関数を復元しました。\n\nバックアップ:\n" + result.get("backup", ""),
            parent=self)

    def close(self):
        self._generation += 1
        self._selection_generation += 1
        self.destroy()
