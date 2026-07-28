"""Small, dependency-free building blocks for live screen based automation.

The module deliberately does not send controller input.  It produces data only,
so a command author can decide which key (if any) is safe to press.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


@dataclass
class ScreenResult:
    mode: str
    template_found: bool = False
    template_score: float = 0.0
    template_position: Optional[Tuple[int, int]] = None
    hp_percent: Optional[float] = None
    hp_colors: Dict[str, str] = None
    text: Dict[str, str] = None

    def __post_init__(self):
        self.hp_colors = self.hp_colors or {}
        self.text = self.text or {}

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class VisionAutomation:
    """Template/HP-bar analyser with named modes and JSON rules.

    A rule file is intentionally simple and can be edited without changing
    Python code.  See ``Samples/vision_rules.json``.
    """

    def __init__(self, rules_path: str = "vision_rules.json"):
        self.rules_path = Path(rules_path)
        self.modes: Dict[str, dict] = {}
        self.current_mode = "default"
        self.reload_rules()

    def reload_rules(self):
        if self.rules_path.is_file():
            with self.rules_path.open(encoding="utf-8") as fp:
                self.modes = json.load(fp).get("modes", {})
        if "default" not in self.modes:
            self.modes["default"] = {}

    def set_mode(self, name: str):
        if name not in self.modes:
            raise ValueError(f"Unknown vision mode: {name}")
        self.current_mode = name

    def analyse(self, frame: np.ndarray) -> ScreenResult:
        rule = self.modes.get(self.current_mode, {})
        result = ScreenResult(mode=self.current_mode)
        template = rule.get("template")
        if template:
            image = cv2.imread(str(self.rules_path.parent / template), cv2.IMREAD_COLOR)
            if image is not None:
                match = cv2.matchTemplate(frame, image, cv2.TM_CCOEFF_NORMED)
                _, score, _, point = cv2.minMaxLoc(match)
                result.template_score = float(score)
                result.template_found = score >= float(rule.get("template_threshold", 0.9))
                if result.template_found:
                    result.template_position = tuple(map(int, point))

        # Legacy hp_region is [x, y, width, height].
        region = rule.get("hp_region")
        if region and len(region) == 4:
            x, y, width, height = map(int, region)
            roi = frame[y : y + height, x : x + width]
            if roi.size:
                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, np.array([0, 80, 60]), np.array([90, 255, 255]))
                result.hp_percent = round(100 * cv2.countNonZero(mask) / mask.size, 1)
        for hp_rule in rule.get("hp_regions", []):
            x, y, width, height = map(int, hp_rule["rect"])
            roi = frame[y : y + height, x : x + width]
            if roi.size:
                result.hp_colors[hp_rule.get("name", "hp")] = self._hp_color(roi)
        for text_rule in rule.get("ocr_regions", []):
            value = self._ocr(frame, text_rule)
            if value is not None:
                result.text[text_rule.get("name", "text")] = value
        return result

    @staticmethod
    def _hp_color(roi: np.ndarray) -> str:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        red = cv2.inRange(hsv, np.array([0, 90, 70]), np.array([10, 255, 255]))
        red |= cv2.inRange(hsv, np.array([170, 90, 70]), np.array([180, 255, 255]))
        white = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 55, 255]))
        return "red" if cv2.countNonZero(red) > cv2.countNonZero(white) else "white"

    @staticmethod
    def _ocr(frame: np.ndarray, rule: dict) -> Optional[str]:
        try:
            import pytesseract
        except ImportError:
            return "[pytesseract is not installed]"
        x, y, width, height = map(int, rule["rect"])
        roi = frame[y : y + height, x : x + width]
        if not roi.size:
            return None
        scale = float(rule.get("scale", 3))
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        config = "--psm " + str(rule.get("psm", 7))
        if rule.get("whitelist"):
            config += " -c tessedit_char_whitelist=" + rule["whitelist"]
        return pytesseract.image_to_string(binary, config=config).strip()
