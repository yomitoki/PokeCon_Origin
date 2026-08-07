"""Low-rate, independently configurable screen-analysis rules."""
from __future__ import annotations

import os
import re
import threading
import time

import cv2
import numpy as np


ANALYSIS_TYPES = {
    "hp_bar": "HPバー（%）",
    "number_ocr": "数値OCR",
    "text_ocr": "文字OCR",
    "image_match": "画像一致",
    "state": "範囲状態",
}

CONDITION_TYPES = {
    "always": "常時",
    "image": "画像一致時",
    "step": "Step値一致時",
}


def parse_roi(value, frame_shape):
    """Return a clipped x/y/w/h ROI; zero width/height means full frame."""
    frame_height, frame_width = frame_shape[:2]
    try:
        x, y, width, height = [int(part.strip()) for part in str(value).split(",")]
    except (TypeError, ValueError):
        return 0, 0, frame_width, frame_height
    if width <= 0 or height <= 0:
        return 0, 0, frame_width, frame_height
    x, y = max(0, x), max(0, y)
    width = min(width, frame_width - x)
    height = min(height, frame_height - y)
    if width <= 0 or height <= 0:
        return 0, 0, frame_width, frame_height
    return x, y, width, height


class AnalysisRuleEngine:
    def __init__(self, result_callback):
        self.result_callback = result_callback
        self.busy = False
        self.last_runs = {}
        self.template_cache = {}
        self.previous_regions = {}
        self.lock = threading.Lock()

    def reset(self):
        with self.lock:
            self.last_runs.clear()
            self.previous_regions.clear()

    def submit(self, frame, rules, context=None, force=False):
        if frame is None or self.busy:
            return False
        now = time.monotonic()
        due = []
        for rule in rules:
            if not rule.get("enabled", True):
                continue
            rule_id = str(rule.get("id", ""))
            try:
                interval = max(0.25, float(rule.get("interval", 1.0)))
            except (TypeError, ValueError):
                interval = 1.0
            if force or now - self.last_runs.get(rule_id, 0.0) >= interval:
                due.append(dict(rule))
                self.last_runs[rule_id] = now
        if not due:
            return False
        self.busy = True
        threading.Thread(
            target=self._worker,
            args=(frame.copy(), due, dict(context or {})),
            daemon=True,
            name="AnalysisRules",
        ).start()
        return True

    def _worker(self, frame, rules, context):
        results = []
        try:
            for rule in rules:
                try:
                    results.append(self._analyse_rule(frame, rule, context))
                except Exception as error:
                    results.append({"id": str(rule.get("id", "")),
                                    "name": str(rule.get("name", "解析エラー")),
                                    "passed": False, "summary": "解析失敗: " + str(error),
                                    "rect": parse_roi(rule.get("roi", "0,0,0,0"), frame.shape),
                                    "type": rule.get("type", "error")})
        finally:
            self.busy = False
        self.result_callback(results)

    def _load_template(self, path, grayscale=True):
        path = os.path.abspath(str(path or ""))
        if not os.path.isfile(path):
            return None
        try:
            state = (path, os.path.getmtime(path), bool(grayscale))
        except OSError:
            return None
        cached = self.template_cache.get(state)
        if cached is not None:
            return cached
        image = cv2.imread(path, cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR)
        if image is not None:
            self.template_cache = {key: value for key, value in self.template_cache.items()
                                   if key[0] != path}
            self.template_cache[state] = image
        return image

    def _condition(self, frame, rule, context):
        kind = rule.get("condition_type", "always")
        if kind == "step":
            expected = str(rule.get("condition_value", ""))
            actual = str(context.get("values", {}).get(rule.get("condition_variable", ""), ""))
            command_scope = str(rule.get("condition_command", "すべて"))
            command_name = str(context.get("command_name", ""))
            scope_ok = command_scope in ("", "すべて", "All commands", "*") or command_scope == command_name
            return scope_ok and actual == expected, "Step {} = {}".format(actual, expected)
        if kind == "image":
            rect = parse_roi(rule.get("condition_roi", "0,0,0,0"), frame.shape)
            x, y, width, height = rect
            source = frame[y:y + height, x:x + width]
            grayscale = bool(rule.get("condition_gray", True))
            if grayscale:
                source = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
            template = self._load_template(rule.get("condition_template", ""), grayscale)
            if template is None or source.shape[0] < template.shape[0] or source.shape[1] < template.shape[1]:
                return False, "条件画像なし／ROIより大きい"
            response = cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)
            _, score, _, _ = cv2.minMaxLoc(response)
            threshold = float(rule.get("condition_threshold", 0.85))
            return score >= threshold, "条件画像 {:.3f}/{:.3f}".format(score, threshold)
        return True, "常時"

    def _analyse_rule(self, frame, rule, context):
        name = str(rule.get("name") or ANALYSIS_TYPES.get(rule.get("type"), "解析"))
        rect = parse_roi(rule.get("roi", "0,0,0,0"), frame.shape)
        passed, condition_summary = self._condition(frame, rule, context)
        base = {"id": str(rule.get("id", "")), "name": name, "type": rule.get("type", "state"),
                "rect": rect, "passed": passed, "condition": condition_summary}
        if not passed:
            base.update(value=None, summary="実行条件待ち: " + condition_summary)
            return base
        x, y, width, height = rect
        roi = frame[y:y + height, x:x + width]
        if roi.size == 0:
            base.update(value=None, summary="ROIが映像範囲外です")
            return base
        analysis_type = rule.get("type", "state")
        try:
            if analysis_type == "image_match":
                value, summary = self._image_match(roi, rule)
            elif analysis_type in ("number_ocr", "text_ocr"):
                value, summary = self._ocr(roi, rule, numeric=analysis_type == "number_ocr")
            elif analysis_type == "hp_bar":
                value, summary = self._hp_bar(roi, rule)
            else:
                value, summary = self._state(roi, rule)
        except Exception as error:
            value, summary = None, "解析失敗: " + str(error)
        base.update(value=value, summary=summary)
        return base

    def _image_match(self, roi, rule):
        grayscale = bool(rule.get("grayscale", True))
        source = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if grayscale else roi
        template = self._load_template(rule.get("template_path", ""), grayscale)
        if template is None:
            return None, "比較画像が設定されていません"
        if source.shape[0] < template.shape[0] or source.shape[1] < template.shape[1]:
            return None, "比較画像がROIより大きいです"
        response = cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(response)
        threshold = float(rule.get("threshold", 0.85))
        return bool(score >= threshold), "{} {:.3f}/{:.3f} at {},{}".format(
            "一致" if score >= threshold else "不一致", score, threshold, location[0], location[1])

    @staticmethod
    def _ocr(roi, rule, numeric=False):
        try:
            import pytesseract
        except ImportError:
            return None, "pytesseractがインストールされていません"
        scale = max(1.0, float(rule.get("ocr_scale", 3.0)))
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        if bool(rule.get("ocr_invert", False)):
            gray = cv2.bitwise_not(gray)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        config = "--psm {}".format(int(rule.get("ocr_psm", 7)))
        whitelist = str(rule.get("ocr_whitelist", ""))
        if numeric and not whitelist:
            whitelist = "0123456789/%."
        if whitelist:
            config += " -c tessedit_char_whitelist=" + whitelist
        language = str(rule.get("ocr_language", "jpn+eng") or "jpn+eng")
        text = pytesseract.image_to_string(binary, config=config, lang=language).strip()
        if numeric:
            values = re.findall(r"\d+(?:\.\d+)?", text)
            value = values[0] if len(values) == 1 else values
            return value, "数値: {}（OCR: {}）".format(value if values else "未検出", text)
        return text, "文字: " + (text or "未検出")

    @staticmethod
    def _hp_bar(roi, rule):
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        color = str(rule.get("hp_color", "auto"))
        if color == "green":
            mask = cv2.inRange(hsv, np.array([35, 55, 45]), np.array([95, 255, 255]))
        elif color == "red":
            mask = cv2.inRange(hsv, np.array([0, 70, 55]), np.array([12, 255, 255]))
            mask |= cv2.inRange(hsv, np.array([168, 70, 55]), np.array([180, 255, 255]))
        elif color == "white":
            mask = cv2.inRange(hsv, np.array([0, 0, 145]), np.array([180, 80, 255]))
        else:
            mask = cv2.inRange(hsv, np.array([0, 55, 45]), np.array([180, 255, 255]))
        kernel_width = max(1, roi.shape[1] // 80)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((1, kernel_width), np.uint8))
        filled_columns = np.mean(mask > 0, axis=0) >= float(rule.get("hp_column_fill", 0.18))
        indices = np.flatnonzero(filled_columns)
        percent = 0.0 if not indices.size else 100.0 * (int(indices[-1]) + 1) / max(1, roi.shape[1])
        percent = round(max(0.0, min(100.0, percent)), 1)
        return percent, "HP {:.1f}%".format(percent)

    def _state(self, roi, rule):
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        small = cv2.resize(gray, (32, 18), interpolation=cv2.INTER_AREA)
        rule_id = str(rule.get("id", ""))
        previous = self.previous_regions.get(rule_id)
        change = 0.0 if previous is None else float(np.mean(cv2.absdiff(small, previous))) / 255.0 * 100.0
        self.previous_regions[rule_id] = small
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        edges = cv2.Canny(gray, 55, 150)
        edge_percent = cv2.countNonZero(edges) / float(max(1, edges.size)) * 100.0
        hue = float(np.median(hsv[:, :, 0]))
        saturation = float(np.mean(hsv[:, :, 1]))
        if saturation < 35:
            dominant_color = "無彩色"
        elif hue < 10 or hue >= 170:
            dominant_color = "赤"
        elif hue < 25:
            dominant_color = "橙"
        elif hue < 38:
            dominant_color = "黄"
        elif hue < 85:
            dominant_color = "緑"
        elif hue < 130:
            dominant_color = "青"
        elif hue < 160:
            dominant_color = "紫"
        else:
            dominant_color = "赤紫"
        if brightness < 45:
            label = "暗い"
        elif brightness > 205:
            label = "明るい"
        elif change >= float(rule.get("state_change_threshold", 8.0)):
            label = "変化中"
        elif saturation < 35:
            label = "低彩度"
        else:
            label = "安定"
        value = {"state": label, "brightness": round(brightness, 1), "contrast": round(contrast, 1),
                 "edge_percent": round(edge_percent, 1), "change_percent": round(change, 1),
                 "hue": round(hue, 1), "dominant_color": dominant_color}
        return value, "{} / 色 {} / 明るさ {:.0f} / 差 {:.1f}% / 輪郭 {:.1f}%".format(
            label, dominant_color, brightness, change, edge_percent)
