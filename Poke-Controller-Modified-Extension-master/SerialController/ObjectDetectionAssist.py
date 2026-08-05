"""Interactive, low-impact object detection assistant.

The window intentionally owns no camera.  ``camera_getter`` must return the
latest BGR ndarray (or ``None``).  Expensive OpenCV work is serialized on one
worker so opening this assistant does not stall Tk's event loop.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk


class ObjectDetectionAssistWindow:
    """Toplevel used to prepare and exercise multi-view object templates."""

    PREVIEW_SIZE = (720, 405)
    DETECT_INTERVAL_MS = 500

    def __init__(self, parent, frame_getter, initial_search_roi=None, on_close=None,
                 title="物体検知アシスト"):
        self.parent = parent
        self.camera_getter = frame_getter
        self.on_close = on_close
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("1080x760")
        self.window.minsize(900, 650)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        roi = initial_search_roi if initial_search_roi and len(initial_search_roi) == 4 else (0, 0, 0, 0)
        self.roi_var = tk.StringVar(value=",".join(str(int(v)) for v in roi))
        self.threshold_var = tk.DoubleVar(value=0.78)
        self.scale_variation_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="最初に指定範囲の静止画を取得してください。")
        self.recommendation_var = tk.StringVar(
            value="推奨: 物体全体が入り、背景が少ない範囲を選択してください。向きごとのサンプル追加が有効です。")
        self.stats_var = tk.StringVar(value="現在: --  最小: --  最大: --  平均: --  一致率: --  連続一致: 0")
        self.detect_button_text = tk.StringVar(value="動作確認を開始")

        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="object-assist")
        self._lock = threading.Lock()
        self._job_pending = False
        self._generation = 0
        self._closed = False
        self._detecting = False
        self._after_id = None

        self.still_roi = None
        self.still_origin = (0, 0)
        self.candidate_mask = None
        self.selection = None
        self.samples = []
        self._photo = None
        self._display_scale = 1.0
        self._display_offset = (0, 0)
        self._drag_start = None
        self._selection_item = None
        self._latest_live = None
        self._latest_box = None
        self._latest_matched = False
        self._reset_stats()

        self._build_ui()
        self._render_still()

    def _build_ui(self):
        top = ttk.Frame(self.window, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="検索範囲 x,y,w,h:").pack(side="left")
        ttk.Entry(top, textvariable=self.roi_var, width=22).pack(side="left", padx=(4, 8))
        ttk.Button(top, text="指定範囲を静止画取得", command=self.capture_still).pack(side="left")
        ttk.Label(top, text="閾値:").pack(side="left", padx=(18, 3))
        ttk.Spinbox(top, from_=0.10, to=1.00, increment=0.01,
                    textvariable=self.threshold_var, width=6).pack(side="left")
        ttk.Checkbutton(
            top, text="大きさ変化 ±15%", variable=self.scale_variation_var,
        ).pack(side="left", padx=(10, 3))
        ttk.Button(top, textvariable=self.detect_button_text,
                   command=self.toggle_detection).pack(side="right")

        body = ttk.Panedwindow(self.window, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8)
        preview_frame = ttk.LabelFrame(body, text="対象の確認（ドラッグして物体を囲む）")
        side = ttk.LabelFrame(body, text="複数方向サンプル")
        body.add(preview_frame, weight=4)
        body.add(side, weight=1)

        self.canvas = tk.Canvas(preview_frame, width=self.PREVIEW_SIZE[0],
                                height=self.PREVIEW_SIZE[1], background="#202020",
                                highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self.canvas.bind("<Configure>", lambda _event: self._render_current())

        self.sample_list = tk.Listbox(side, height=14, exportselection=False)
        self.sample_list.pack(fill="both", expand=True, padx=5, pady=5)
        sample_buttons = ttk.Frame(side)
        sample_buttons.pack(fill="x", padx=5)
        ttk.Button(sample_buttons, text="候補を追加", command=self.add_sample).pack(side="left", fill="x", expand=True)
        ttk.Button(sample_buttons, text="選択を削除", command=self.remove_sample).pack(side="left", fill="x", expand=True, padx=(4, 0))
        session_buttons = ttk.Frame(side)
        session_buttons.pack(fill="x", padx=5, pady=(5, 0))
        ttk.Button(session_buttons, text="セッション保存", command=self.save_session).pack(side="left", fill="x", expand=True)
        ttk.Button(session_buttons, text="セッション読込", command=self.load_session).pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Label(side, text="OR判定: どれか1つが閾値以上なら一致",
                  wraplength=230, foreground="#555555").pack(fill="x", padx=6, pady=8)

        info = ttk.Frame(self.window, padding=(8, 5, 8, 8))
        info.pack(fill="x")
        ttk.Label(info, textvariable=self.recommendation_var, wraplength=1030,
                  foreground="#176b2c").pack(anchor="w")
        ttk.Separator(info).pack(fill="x", pady=5)
        ttk.Label(info, textvariable=self.stats_var, font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(info, textvariable=self.status_var, wraplength=1030).pack(anchor="w", pady=(3, 0))

    def _parse_roi(self, frame, roi_text=None):
        height, width = frame.shape[:2]
        try:
            values = [int(part.strip()) for part in (self.roi_var.get() if roi_text is None else roi_text).split(",")]
            if len(values) != 4:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("検索範囲は x,y,w,h の4整数で入力してください。")
        x, y, w, h = values
        if w <= 0 or h <= 0:
            return 0, 0, width, height
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = max(1, min(w, width - x))
        h = max(1, min(h, height - y))
        return x, y, w, h

    def _get_frame(self):
        frame = self.camera_getter()
        if frame is None or not isinstance(frame, np.ndarray) or frame.ndim < 2:
            raise RuntimeError("カメラ画像を取得できません。")
        return frame.copy()

    def _submit(self, generation, operation, callback):
        with self._lock:
            if self._closed or self._job_pending:
                return False
            self._job_pending = True
        future = self._executor.submit(operation)

        def completed(done):
            try:
                result, error = done.result(), None
            except Exception as exc:  # report on the Tk thread
                result, error = None, exc
            if not self._closed:
                try:
                    self.window.after(0, self._finish_job, generation, callback, result, error)
                except tk.TclError:
                    pass

        future.add_done_callback(completed)
        return True

    def _finish_job(self, generation, callback, result, error):
        with self._lock:
            self._job_pending = False
        if self._closed or generation != self._generation:
            return
        callback(result, error)

    def capture_still(self):
        self.stop_detection()
        generation = self._generation
        roi_text = self.roi_var.get()
        self.status_var.set("静止画を取得しています…")

        def operation():
            frame = self._get_frame()
            x, y, w, h = self._parse_roi(frame, roi_text)
            return frame[y:y + h, x:x + w].copy(), (x, y)

        if not self._submit(generation, operation, self._captured):
            # A stopped detection may still be finishing in the sole worker.
            # Retry without ever creating a second concurrent OpenCV job.
            self.status_var.set("直前の検知処理の終了を待っています…")
            self.window.after(100, self.capture_still)

    def _captured(self, result, error):
        if error:
            self.status_var.set(str(error))
            return
        self.still_roi, self.still_origin = result
        self.candidate_mask = None
        self.selection = None
        self.status_var.set("静止画を保持しました。検知したい物体をドラッグで囲んでください。")
        self._render_still()

    def _canvas_to_image(self, event):
        if self.still_roi is None:
            return None
        ox, oy = self._display_offset
        x = int((event.x - ox) / self._display_scale)
        y = int((event.y - oy) / self._display_scale)
        h, w = self.still_roi.shape[:2]
        return max(0, min(x, w - 1)), max(0, min(y, h - 1))

    def _on_drag_start(self, event):
        point = self._canvas_to_image(event)
        if point is None or self._detecting:
            return
        self._drag_start = point

    def _on_drag_move(self, event):
        if self._drag_start is None:
            return
        point = self._canvas_to_image(event)
        if point is None:
            return
        self.selection = self._normal_rect(self._drag_start, point)
        self._render_still()

    def _on_drag_end(self, event):
        if self._drag_start is None:
            return
        point = self._canvas_to_image(event)
        start, self._drag_start = self._drag_start, None
        rect = self._normal_rect(start, point)
        if rect[2] < 6 or rect[3] < 6:
            self.status_var.set("物体をもう少し大きく囲んでください。")
            return
        self.selection = rect
        self._segment_selection(rect)

    @staticmethod
    def _normal_rect(first, second):
        x1, x2 = sorted((first[0], second[0]))
        y1, y2 = sorted((first[1], second[1]))
        return x1, y1, max(1, x2 - x1 + 1), max(1, y2 - y1 + 1)

    def _segment_selection(self, rect):
        generation = self._generation
        image = self.still_roi.copy()
        self.status_var.set("前景候補を抽出しています…")

        def operation():
            h, w = image.shape[:2]
            x, y, rw, rh = rect
            # GrabCut needs a background margin.  A user rectangle touching an
            # edge is moved one pixel inward without changing the saved bbox.
            gx, gy = max(1, x), max(1, y)
            gr = min(rw, w - gx - 1)
            gh = min(rh, h - gy - 1)
            if gr < 3 or gh < 3:
                raise ValueError("画像端から少し内側を選択してください。")
            labels = np.zeros((h, w), np.uint8)
            bg_model = np.zeros((1, 65), np.float64)
            fg_model = np.zeros((1, 65), np.float64)
            cv2.grabCut(image, labels, (gx, gy, gr, gh), bg_model, fg_model,
                        4, cv2.GC_INIT_WITH_RECT)
            return np.where((labels == cv2.GC_FGD) | (labels == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

        self._submit(generation, operation, self._segmented)

    def _segmented(self, mask, error):
        if error:
            self.candidate_mask = None
            self.status_var.set("前景抽出に失敗しました: {}".format(error))
            self._render_still()
            return
        self.candidate_mask = mask
        x, y, w, h = self.selection
        ratio = float(np.count_nonzero(mask[y:y + h, x:x + w])) / float(w * h)
        if ratio < .12:
            advice = "前景が少なすぎます。物体の内側を中心に、背景を減らして囲み直してください。"
        elif ratio > .88:
            advice = "背景も前景に含まれた可能性があります。対象の外周に近づけて囲み直してください。"
        else:
            advice = "緑色が目的の物体を覆っていれば候補を追加してください。"
        self.recommendation_var.set("推奨: {} 向きが変わる物体は正面・側面・背面を追加します。".format(advice))
        self.status_var.set("緑色の部分が検知対象として正しいか確認してください。")
        self._render_still()

    def add_sample(self):
        if self.still_roi is None or self.selection is None:
            messagebox.showwarning("物体検知アシスト", "先に静止画上で物体を選択してください。", parent=self.window)
            return
        x, y, w, h = self.selection
        image = self.still_roi[y:y + h, x:x + w].copy()
        if self.candidate_mask is None:
            mask = np.full((h, w), 255, np.uint8)
        else:
            mask = self.candidate_mask[y:y + h, x:x + w].copy()
            if np.count_nonzero(mask) < max(12, int(mask.size * .05)):
                mask[:] = 255
        self.samples.append({"image": image, "mask": mask})
        self.sample_list.insert("end", "サンプル {}  ({} x {})".format(len(self.samples), w, h))
        self.sample_list.selection_clear(0, "end")
        self.sample_list.selection_set("end")
        self.status_var.set("サンプルを追加しました。別方向も静止画取得して追加できます。")
        count = len(self.samples)
        self.recommendation_var.set(
            "推奨: {}方向を登録済み。3D物体は3方向以上をOR判定すると向きの変化に強くなります。".format(count))

    def remove_sample(self):
        selection = self.sample_list.curselection()
        if not selection:
            return
        index = selection[0]
        del self.samples[index]
        self.sample_list.delete(index)
        # Renumber because list indices are meaningful during editing.
        for pos in range(self.sample_list.size()):
            sample = self.samples[pos]["image"]
            self.sample_list.delete(pos)
            self.sample_list.insert(pos, "サンプル {}  ({} x {})".format(pos + 1, sample.shape[1], sample.shape[0]))
        self.status_var.set("サンプルを削除しました。")

    @staticmethod
    def _session_root():
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Template", "ObjectAssist")
        os.makedirs(root, exist_ok=True)
        return root

    def save_session(self):
        if not self.samples:
            messagebox.showwarning("物体検知アシスト", "保存するサンプルがありません。", parent=self.window)
            return
        default_name = "object_{}".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        name = simpledialog.askstring("セッション保存", "物体・セッション名:",
                                      initialvalue=default_name, parent=self.window)
        if not name:
            return
        safe_name = re.sub(r"[^0-9A-Za-z_\-\u3040-\u30ff\u3400-\u9fff]+", "_", name).strip("_")
        if not safe_name:
            safe_name = default_name
        folder = os.path.join(self._session_root(), safe_name)
        os.makedirs(folder, exist_ok=True)
        records = []
        try:
            for index, sample in enumerate(self.samples, 1):
                image_name = "sample_{:02d}.png".format(index)
                mask_name = "sample_{:02d}_mask.png".format(index)
                if not cv2.imwrite(os.path.join(folder, image_name), sample["image"]):
                    raise IOError("画像を書き込めません: {}".format(image_name))
                if not cv2.imwrite(os.path.join(folder, mask_name), sample["mask"]):
                    raise IOError("マスクを書き込めません: {}".format(mask_name))
                records.append({"image": image_name, "mask": mask_name})
            metadata = {
                "format": 1,
                "name": name,
                "search_roi": self.roi_var.get(),
                "threshold": float(self.threshold_var.get()),
                "scale_variation": bool(self.scale_variation_var.get()),
                "samples": records,
            }
            json_path = os.path.join(folder, "session.json")
            with open(json_path, "w", encoding="utf-8") as stream:
                json.dump(metadata, stream, ensure_ascii=False, indent=2)
            self.status_var.set("セッションを保存しました: {}".format(json_path))
        except (OSError, ValueError, cv2.error) as exc:
            messagebox.showerror("セッション保存", str(exc), parent=self.window)

    def load_session(self):
        json_path = filedialog.askopenfilename(
            title="物体検知セッションを選択", initialdir=self._session_root(),
            filetypes=(("Object Assist session", "session.json"), ("JSON", "*.json")),
            parent=self.window)
        if not json_path:
            return
        try:
            with open(json_path, "r", encoding="utf-8") as stream:
                metadata = json.load(stream)
            folder = os.path.dirname(json_path)
            loaded = []
            for record in metadata.get("samples", []):
                image = cv2.imread(os.path.join(folder, record["image"]), cv2.IMREAD_COLOR)
                mask = cv2.imread(os.path.join(folder, record["mask"]), cv2.IMREAD_GRAYSCALE)
                if image is None or mask is None or image.shape[:2] != mask.shape[:2]:
                    raise ValueError("サンプル画像またはマスクが不正です。")
                loaded.append({"image": image, "mask": mask})
            if not loaded:
                raise ValueError("セッションにサンプルがありません。")
            self.stop_detection()
            self.samples = loaded
            self.sample_list.delete(0, "end")
            for index, sample in enumerate(self.samples, 1):
                image = sample["image"]
                self.sample_list.insert("end", "サンプル {}  ({} x {})".format(index, image.shape[1], image.shape[0]))
            self.roi_var.set(str(metadata.get("search_roi", "0,0,0,0")))
            self.threshold_var.set(float(metadata.get("threshold", .78)))
            self.scale_variation_var.set(bool(metadata.get("scale_variation", True)))
            self.recommendation_var.set(
                "推奨: {}方向を読込みました。動作確認で向きが変わっても連続一致するか確認してください。".format(len(loaded)))
            self.status_var.set("セッションを読み込みました: {}".format(json_path))
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("セッション読込", str(exc), parent=self.window)

    def toggle_detection(self):
        if self._detecting:
            self.stop_detection()
        else:
            self.start_detection()

    def start_detection(self):
        if not self.samples:
            messagebox.showwarning("物体検知アシスト", "検知に使うサンプルを1つ以上追加してください。", parent=self.window)
            return
        try:
            threshold = float(self.threshold_var.get())
            if not 0.0 <= threshold <= 1.0:
                raise ValueError
        except (TypeError, ValueError, tk.TclError):
            messagebox.showwarning("物体検知アシスト", "閾値は0～1で指定してください。", parent=self.window)
            return
        self._generation += 1
        self._detecting = True
        self._reset_stats()
        self.detect_button_text.set("動作確認を終了")
        self.status_var.set("複数サンプルのOR判定を継続中です。緑枠=一致、赤枠=閾値未満。")
        self._schedule_tick(0)

    def stop_detection(self):
        if self._after_id is not None:
            try:
                self.window.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if self._detecting:
            self._generation += 1  # discard completion from the previous run
        self._detecting = False
        self.detect_button_text.set("動作確認を開始")
        self._render_still()

    def _schedule_tick(self, delay=None):
        if self._closed or not self._detecting:
            return
        self._after_id = self.window.after(
            self.DETECT_INTERVAL_MS if delay is None else delay, self._detection_tick)

    def _detection_tick(self):
        self._after_id = None
        if not self._detecting:
            return
        generation = self._generation
        samples = [(item["image"].copy(), item["mask"].copy()) for item in self.samples]
        threshold = float(self.threshold_var.get())
        scale_variation = bool(self.scale_variation_var.get())
        roi_text = self.roi_var.get()

        def operation():
            frame = self._get_frame()
            x0, y0, rw, rh = self._parse_roi(frame, roi_text)
            source_full = frame[y0:y0 + rh, x0:x0 + rw]
            # Limit the analysis resolution so several directional samples do
            # not take CPU away from the live camera preview.
            analysis_scale = min(1.0, 480.0 / max(1, rw), 270.0 / max(1, rh))
            if analysis_scale < 1.0:
                source = cv2.resize(
                    source_full,
                    (max(1, int(rw * analysis_scale)), max(1, int(rh * analysis_scale))),
                    interpolation=cv2.INTER_AREA,
                )
            else:
                source = source_full
            best_score, best_box = -1.0, None
            for template, mask in samples:
                source_th, source_tw = template.shape[:2]
                factors = (0.85, 1.0, 1.15) if scale_variation else (1.0,)
                for factor in factors:
                    tw = max(3, int(source_tw * analysis_scale * factor))
                    th = max(3, int(source_th * analysis_scale * factor))
                    if th > source.shape[0] or tw > source.shape[1]:
                        continue
                    interpolation = cv2.INTER_AREA if factor * analysis_scale < 1.0 else cv2.INTER_LINEAR
                    reduced = cv2.resize(template, (tw, th), interpolation=interpolation)
                    reduced_mask = cv2.resize(mask, (tw, th), interpolation=cv2.INTER_NEAREST)
                    match_mask = (cv2.merge((reduced_mask, reduced_mask, reduced_mask))
                                  if reduced.ndim == 3 else reduced_mask)
                    try:
                        result = cv2.matchTemplate(
                            source, reduced, cv2.TM_CCORR_NORMED, mask=match_mask)
                    except cv2.error:
                        result = cv2.matchTemplate(source, reduced, cv2.TM_CCOEFF_NORMED)
                    result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
                    _, score, _, location = cv2.minMaxLoc(result)
                    if score > best_score:
                        best_score = float(score)
                        best_box = (
                            x0 + int(location[0] / analysis_scale),
                            y0 + int(location[1] / analysis_scale),
                            max(1, int(tw / analysis_scale)),
                            max(1, int(th / analysis_scale)),
                        )
            return frame, best_score, best_box, best_score >= threshold

        if not self._submit(generation, operation, self._detected):
            self._schedule_tick()

    def _detected(self, result, error):
        if error:
            self.status_var.set("検知処理エラー: {}".format(error))
            self.stop_detection()
            return
        frame, score, box, matched = result
        self._latest_live = frame
        self._latest_box = box
        self._latest_matched = matched
        self._update_stats(score, matched)
        self._render_live()
        self._schedule_tick()

    def _reset_stats(self):
        self._score_count = 0
        self._score_total = 0.0
        self._score_minimum = 1.0
        self._score_maximum = 0.0
        self._match_count = 0
        self._consecutive = 0
        self.stats_var.set("現在: --  最小: --  最大: --  平均: --  一致率: --  連続一致: 0")

    def _update_stats(self, score, matched):
        if score < 0:
            score = 0.0
        self._score_count += 1
        self._score_total += score
        self._score_minimum = min(self._score_minimum, score)
        self._score_maximum = max(self._score_maximum, score)
        if matched:
            self._match_count += 1
            self._consecutive += 1
        else:
            self._consecutive = 0
        average = self._score_total / self._score_count
        rate = 100.0 * self._match_count / self._score_count
        self.stats_var.set(
            "現在: {:.3f}  最小: {:.3f}  最大: {:.3f}  平均: {:.3f}  "
            "一致率: {:.1f}% ({}/{})  連続一致: {}".format(
                score, self._score_minimum, self._score_maximum, average,
                rate, self._match_count, self._score_count, self._consecutive))

    def _render_current(self):
        if self._detecting and self._latest_live is not None:
            self._render_live()
        else:
            self._render_still()

    def _render_still(self):
        if not hasattr(self, "canvas"):
            return
        if self.still_roi is None:
            self.canvas.delete("all")
            self.canvas.create_text(max(1, self.canvas.winfo_width()) // 2,
                                    max(1, self.canvas.winfo_height()) // 2,
                                    text="静止画はまだ取得されていません", fill="#dddddd")
            return
        display = self.still_roi.copy()
        if self.candidate_mask is not None:
            green = np.zeros_like(display)
            green[:, :, 1] = 255
            foreground = self.candidate_mask > 0
            display[foreground] = cv2.addWeighted(display, .55, green, .45, 0)[foreground]
        self._show_image(display)
        if self.selection:
            self._draw_scaled_box(self.selection, "#ffcc00", width=2)

    def _render_live(self):
        if self._latest_live is None:
            return
        display = self._latest_live.copy()
        if self._latest_box:
            x, y, w, h = self._latest_box
            colour = (40, 220, 40) if self._latest_matched else (40, 40, 230)
            cv2.rectangle(display, (x, y), (x + w, y + h), colour, 3)
            cv2.putText(display, "MATCH" if self._latest_matched else "NO MATCH",
                        (x, max(20, y - 7)), cv2.FONT_HERSHEY_SIMPLEX, .65, colour, 2, cv2.LINE_AA)
        self._show_image(display)

    def _show_image(self, bgr):
        canvas_w = max(2, self.canvas.winfo_width())
        canvas_h = max(2, self.canvas.winfo_height())
        h, w = bgr.shape[:2]
        scale = min(canvas_w / float(w), canvas_h / float(h))
        out_w, out_h = max(1, int(w * scale)), max(1, int(h * scale))
        resized = cv2.resize(bgr, (out_w, out_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        self._photo = ImageTk.PhotoImage(Image.fromarray(rgb))
        ox, oy = (canvas_w - out_w) // 2, (canvas_h - out_h) // 2
        self._display_scale, self._display_offset = scale, (ox, oy)
        self.canvas.delete("all")
        self.canvas.create_image(ox, oy, anchor="nw", image=self._photo)

    def _draw_scaled_box(self, box, colour, width=2):
        x, y, w, h = box
        ox, oy = self._display_offset
        scale = self._display_scale
        self.canvas.create_rectangle(ox + x * scale, oy + y * scale,
                                     ox + (x + w) * scale, oy + (y + h) * scale,
                                     outline=colour, width=width)

    def close(self):
        if self._closed:
            return
        self.stop_detection()
        self._closed = True
        self._generation += 1
        # Running OpenCV is allowed to finish; waiting here would freeze Tk.
        self._executor.shutdown(wait=False)
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass


# Short alias for callers that name dialogs after their feature.
ObjectDetectionAssist = ObjectDetectionAssistWindow
