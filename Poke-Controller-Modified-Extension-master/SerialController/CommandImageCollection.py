"""Native Commands-start-only supplemental checks and multilingual captures.

The portable command/selector has no settings for this feature. A new native
start dialog explicitly arms one command instance; no option is persisted in
InputSets, favorites, command source, or the image detection library.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import logging
import math
from pathlib import Path
import queue
import re
import sys
import threading
import time
import uuid

try:
    from .CommandSupplementalChecks import (MENU_REFERENCES, BOSS_REFERENCES, HOTEL_REFERENCES, RETRY_TEXT_REFERENCES,
                                             PositionChecks, RetryByPosition)
    from .CommandSupplementalIcons import ICON_REFERENCES, IconChecks, choice_rows
except ImportError:
    from CommandSupplementalChecks import (MENU_REFERENCES, BOSS_REFERENCES, HOTEL_REFERENCES, RETRY_TEXT_REFERENCES,
                                           PositionChecks, RetryByPosition)
    from CommandSupplementalIcons import ICON_REFERENCES, IconChecks, choice_rows


LOGGER = logging.getLogger(__name__)
SESSION_ATTRIBUTE = "_native_image_collection"
# Both the target name AND the shipped Japanese reference must agree. Do not
# replace arbitrary detections or add checks around arbitrary A button input.
A_REFERENCES = {
    "POKEMON_ZA_OTHER_A_MARKER": "other_a_marker.png",
    "POKEMON_ZA_IN_MARKER": "inmarker.png",
    "POKEMON_ZA_OUT_MARKER": "outmarker.png",
    "POKEMON_ZA_CHAT_MARKER": "chatmarker.png",
    "POKEMON_ZA_HASHIGO_ICON": "hashigomarker.png",
    "POKEMON_ZA_INVESTIGATE_MARKER": "investigate_marker.png",
    "ZA_STORY_COMMON_ZA_RESEARCH_A": "ZA_RESEARCH_A.png",
}
A_THRESHOLD = 0.90
# Exclude the bottom menu legend. Also retain the original check's narrower
# crop, so a glyph elsewhere on screen cannot authorize that check.
FIELD_CROP = (200, 120, 1080, 620)
MAX_SAMPLES = 2000
SAMPLES_PER_CHECK = 3
CAPTURE_INTERVAL = 2.0


@dataclass(frozen=True)
class CollectionOptions:
    collect: bool = False
    supplemental: bool = False
    language: str = ""


def _safe_name(value, limit):
    return re.sub(r"[^\w.-]+", "_", str(value), flags=re.UNICODE).strip("._")[:limit] or "command"


def _bounds(crop, shape):
    height, width = shape[:2]
    if not crop or not any(crop):
        return (0, 0, width, height)
    x1, y1, x2, y2 = map(int, crop)
    result = (max(0, x1), max(0, y1),
              width if x2 <= 0 else min(width, x2),
              height if y2 <= 0 else min(height, y2))
    if result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError("画像収集の検知範囲が画面外です。")
    return result


def _region(frame, bounds):
    x1, y1, x2, y2 = bounds
    return frame[y1:y2, x1:x2]


def _reference_name(path):
    return str(path).replace("\\", "/").rsplit("/", 1)[-1]


def _context(command):
    states = {name: value for name, value in vars(command).items()
              if (name == "current_state" or name.endswith("_current_state"))
              and isinstance(value, (str, int, bool))}
    caller = {}
    frame = sys._getframe(1)
    try:
        for _ in range(16):
            if frame is None:
                break
            name = frame.f_code.co_name
            if (frame.f_locals.get("self") is command and name not in
                    {"_image_check_target", "image_check", "image_check_confirmation"}):
                caller = {"file": frame.f_code.co_filename,
                          "function": name, "line": frame.f_lineno}
                break
            frame = frame.f_back
    finally:
        del frame
    return states, caller


class CommandImageCollection:
    """One frozen run configuration; match on caller, write on bounded worker."""

    def __init__(self, serial_root, command_name, options):
        self.options = options
        self.serial_root = Path(serial_root).resolve()
        self.command_name = str(command_name)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.directory = (self.serial_root / "Captures" / "Multilingual" /
                          (stamp + "_" + uuid.uuid4().hex[:6] + "_" +
                           _safe_name(command_name, 24)))
        self._queue = queue.Queue(maxsize=4)
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._worker = None
        self._seen = {}
        self._capture_failed = False
        self._warned = set()
        self.stats = {"queued": 0, "saved": 0, "queue_full": 0,
                      "limited": 0, "a_skipped": 0, "retry_skipped": 0,
                      "boss_skipped": 0, "write_errors": 0}
        self._positions = PositionChecks(self.serial_root)
        self._icons = IconChecks(self._positions)
        self._retry = RetryByPosition(self._positions)
        self._retry_capture_guard = False
        self._glyphs = []
        self._glyph_error = None
        if options.supplemental:
            self._load_glyphs()

    def reset_retry(self):
        # Start a new boss without discarding what this command run learned.
        # Closing/rearming the native Start dialog creates a fresh session.
        self._retry.reset(keep_strategy=True)
        self._icons.scenes.reset_final_warning()

    def final_warning_observation(self, command, reader):
        """Refresh the opt-in final-warning window from one fresh frame."""
        if not self.options.supplemental:
            return None
        return self._icons.scenes.final_warning(reader(command), command)

    def final_warning_deadline(self, command, reader):
        observation = self.final_warning_observation(command, reader)
        if observation is None or not observation['valid']:
            return None
        return observation['deadline']

    def choice_observation(self, command, reader, kind):
        """Read one fresh frame; this helper never sends a button."""
        frame = reader(command)
        if frame is None or frame.shape != (720, 1280, 3):
            return None
        if kind == "map":
            return self._icons.map_menu(frame)
        if kind in ("filter", "box"):
            menu = self._icons.scenes.menu(frame, kind)
            if menu is None and kind == "box" and self._icons.scenes.box_closed(frame):
                return {"rows": 0, "selected": 0}
            return menu
        return choice_rows(frame)

    def map_warning_observation(self, command, reader):
        frame = reader(command)
        return self._icons.match("POKEMON_ZA_MOVE_COMMENT_BATTLE", frame, command)["matched"]

    def retry_menu_step(self, command, directions, reader, button_a):
        self._retry_capture_guard = True
        try:
            return self._retry.step(command, reader, directions, button_a)
        finally:
            self._retry_capture_guard = False

    def _load_glyphs(self):
        import cv2
        import numpy as np

        # The dark examine prompt has a different A raster. These crops
        # contain the A glyph only, never the Japanese action text.
        definitions = [
            ("Template/ZA_Story_PIC/Common/other_a_marker.png", None, .80),
            ("Template/ZA_Story_PIC/ZA_infi/doorA.png", None, A_THRESHOLD),
            ("Template/ZA_Story_PIC/Common/investigate_marker.png", (6, 0, 21, 14), A_THRESHOLD),
        ]
        glyphs = []
        for relative, crop, threshold in definitions:
            if relative.endswith('/other_a_marker.png') and not (self.serial_root / relative).is_file():
                # Older portable template sets retain their existing A glyphs.
                continue
            data = (self.serial_root / relative).read_bytes()
            raster = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
            if raster is None:
                raise ValueError("補足A画像を読めません: " + relative)
            if crop:
                raster = _region(raster, crop)
            if raster.size == 0 or float(raster.std()) < 1.0:
                raise ValueError("補足A画像に有効な図柄がありません: " + relative)
            glyphs.append((raster.copy(), {
                "template_path": relative, "template_crop": crop,
                "threshold": threshold,
                "template_sha256": hashlib.sha256(data).hexdigest(),
            }))
        self._glyphs = glyphs

    def _warn_once(self, key, message):
        if key not in self._warned:
            self._warned.add(key)
            LOGGER.warning("[Commands画像収集] %s", message)

    def _supplemental_match(self, frame, crop, exclusions):
        import cv2

        result = {"matched": False, "score": 0.0, "threshold": A_THRESHOLD,
                  "position": (0, 0), "template_size": (15, 14)}
        if frame.shape[:2] != (720, 1280):
            result["error"] = "補足Aチェックは1280x720入力が対象です。"
            self._warn_once("resolution", result["error"])
            return result
        original = _bounds(crop, frame.shape)
        bounds = (max(original[0], FIELD_CROP[0]), max(original[1], FIELD_CROP[1]),
                  min(original[2], FIELD_CROP[2]), min(original[3], FIELD_CROP[3]))
        result["search_crop"] = bounds
        if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            result["error"] = "日本語の検知範囲とフィールドのA探索範囲が重なりません。"
            return result
        source = cv2.cvtColor(_region(frame, bounds), cv2.COLOR_BGR2GRAY)
        best = -2.0
        for glyph, reference in self._glyphs:
            height, width = glyph.shape
            if source.shape[0] < height or source.shape[1] < width:
                continue
            scores = cv2.matchTemplate(source, glyph, cv2.TM_CCOEFF_NORMED)
            for x1, y1, x2, y2 in exclusions or []:
                left, top = max(0, x1 - bounds[0] - width + 1), max(0, y1 - bounds[1] - height + 1)
                right, bottom = min(scores.shape[1], x2 - bounds[0]), min(scores.shape[0], y2 - bounds[1])
                if left < right and top < bottom:
                    scores[top:bottom, left:right] = -2.0
            _, score, _, position = cv2.minMaxLoc(scores)
            threshold = reference.get("threshold", A_THRESHOLD)
            # A qualifying canonical Other_A must not be discarded in favour
            # of a higher-scoring small glyph that fails its own threshold.
            if math.isfinite(score) and (score - threshold) > best:
                best = score - threshold
                result.update(reference)
                result.update(score=float(score), matched=score >= threshold,
                              position=(position[0] + bounds[0], position[1] + bounds[1]),
                              template_size=(width, height))
        return result

    def process(self, command, frame, detail, template_path, crop, template_crop):
        """Use opt-in alternatives and retain Japanese ROI from the same frame."""
        if self._closed.is_set():
            return detail
        japanese = dict(detail)
        supplemental = None
        reference = A_REFERENCES.get(str(detail["name"]))
        if ((self.options.supplemental or self.options.collect)
                and reference == _reference_name(template_path)):
            try:
                # Collection alone also probes A to omit images that no
                # longer need a language-specific template. It keeps the
                # original operation verdict unless supplemental is enabled.
                if self._glyph_error:
                    raise ValueError(self._glyph_error)
                if not self._glyphs:
                    try:
                        self._load_glyphs()
                    except Exception as error:
                        self._glyph_error = str(error)
                        raise
                supplemental = self._supplemental_match(
                    frame, crop, detail.get("excluded_regions"))
            except Exception as error:
                # An enabled replacement must not silently fall back to text.
                supplemental = {"matched": False, "score": 0.0,
                                "threshold": A_THRESHOLD, "error": str(error)}
                self._warn_once("match", "補足Aチェック失敗: " + str(error))
            if self.options.supplemental:
                detail = dict(detail)
                detail.update({key: supplemental[key] for key in
                               ("matched", "score", "threshold", "position", "template_size")
                               if key in supplemental})
                detail.update(match_source="supplemental_A", japanese=japanese,
                              supplemental=supplemental)
        position_reference = MENU_REFERENCES.get(str(detail["name"]))
        if (self.options.supplemental and position_reference is not None
                and position_reference == _reference_name(template_path)):
            supplemental = self._positions.match(str(detail["name"]), frame)
            detail = dict(detail)
            detail.update({key: supplemental[key] for key in
                           ("matched", "score", "threshold", "position", "template_size", "match_source")})
            detail.update(japanese=japanese, supplemental=supplemental)
        icon_reference = ICON_REFERENCES.get(str(detail["name"]))
        if (self.options.supplemental and icon_reference is not None
                and _reference_name(template_path) in (icon_reference if isinstance(icon_reference, tuple) else (icon_reference,))):
            try:
                supplemental = self._icons.match(str(detail["name"]), frame, command)
            except Exception as error:
                supplemental = {"matched": False, "score": 0.0, "error": str(error),
                                "match_source": "supplemental_icon"}
                self._warn_once("icon:" + str(detail["name"]), "補足アイコンチェック失敗: " + str(error))
            detail = dict(detail)
            detail.update({key: supplemental[key] for key in
                           ("matched", "score", "threshold", "position", "template_size", "match_source")
                           if key in supplemental})
            detail.update(japanese=japanese, supplemental=supplemental)
        hotel_reference = HOTEL_REFERENCES.get(str(detail["name"]))
        if (self.options.supplemental and hotel_reference is not None
                and hotel_reference == _reference_name(template_path)):
            try:
                supplemental = self._positions.hotel_icon(
                    frame, detail.get("excluded_regions"))
            except Exception as error:
                supplemental = {"matched": False, "score": 0.0, "error": str(error),
                                "match_source": "supplemental_hotel_icon"}
                self._warn_once("hotel", "ホテル入口の補足チェック失敗: " + str(error))
            detail = dict(detail)
            detail.update({key: supplemental[key] for key in
                           ("matched", "score", "threshold", "position", "template_size", "match_source")
                           if key in supplemental})
            detail.update(japanese=japanese, supplemental=supplemental)
        boss_reference = BOSS_REFERENCES.get(str(detail["name"]))
        boss_match = False
        if ((self.options.supplemental or self.options.collect)
                and boss_reference is not None
                and boss_reference == _reference_name(template_path)):
            supplemental = self._positions.boss(str(detail["name"]), frame,
                last_battle=bool(getattr(command, "_za_mega_last_battle_mode", False)))
            boss_match = supplemental["matched"]
            if self.options.supplemental:
                detail = dict(detail)
                detail.update({key: supplemental[key] for key in
                               ("matched", "score", "threshold", "position", "template_size", "match_source")})
                detail.update(japanese=japanese, supplemental=supplemental)
        # Some existing targets already use the language-independent doorA
        # glyph directly. Those also need no translated capture assets.
        original_a_only = (japanese["matched"] and
                           str(template_path).replace("\\", "/").endswith("ZA_infi/doorA.png"))
        retry_excluded = (_reference_name(template_path) in RETRY_TEXT_REFERENCES
                          or self._retry_capture_guard or self._retry.active)
        a_match = (reference is not None and reference == _reference_name(template_path)
                   and supplemental and supplemental["matched"])
        if self.options.collect and retry_excluded:
            self.stats["retry_skipped"] += 1
        elif self.options.collect and (original_a_only or a_match):
            self.stats["a_skipped"] += 1
        elif self.options.collect and boss_match:
            self.stats["boss_skipped"] += 1
        elif self.options.collect and (japanese["matched"] or detail["matched"]):
            try:
                self._enqueue(command, frame, japanese, supplemental, detail,
                              template_path, crop, template_crop)
            except Exception as error:
                # Disk/capture errors cannot alter the selected match result.
                self._warn_once("capture", "画像収集を保存できません: " + str(error))
        return detail

    def _enqueue(self, command, frame, japanese, supplemental, effective,
                 template_path, crop, template_crop):
        states, caller = _context(command)
        bounds = _bounds(crop, frame.shape)
        key = json.dumps([japanese["name"], str(template_path), bounds, template_crop,
                          japanese.get("excluded_regions"), states, caller,
                          japanese["matched"], bool(supplemental and supplemental["matched"])],
                         sort_keys=True, ensure_ascii=False)
        now = time.monotonic()
        with self._lock:
            if self._closed.is_set() or self._capture_failed:
                return
            count, previous = self._seen.get(key, (0, -float("inf")))
            if (count >= SAMPLES_PER_CHECK or now - previous < CAPTURE_INTERVAL
                    or self.stats["queued"] >= MAX_SAMPLES):
                self.stats["limited"] += 1
                return
            if self._queue.full():
                self.stats["queue_full"] += 1
                return
            index = self.stats["queued"] + 1
            metadata = {
                "schema_version": 1, "sample": index,
                "command": self.command_name, "language": self.options.language,
                "target": japanese["name"], "captured_at": datetime.now().astimezone().isoformat(),
                "frame_size": [int(frame.shape[1]), int(frame.shape[0])],
                "japanese_template_path": str(template_path),
                "japanese_template_crop": template_crop,
                "japanese_search_crop": bounds, "states": states, "caller": caller,
                "japanese": japanese, "supplemental": supplemental,
                "effective_matched": bool(effective["matched"]),
                "match_source": effective.get("match_source", "japanese"),
                "scope": "template_variant_before_target_confirmation",
                "note": ("位置判定の一致フレーム。項目名の意味は確認していません。"
                         if effective.get("match_source") == "supplemental_position" else
                         "ホテル接近時の入口アイコン。入館完了やホテルの場所名は確認していません。"
                         if effective.get("match_source") == "supplemental_hotel_icon" else
                         "A図柄の一致だけでは、入る・出る・話すや移動成功を区別できません。"),
            }
            self._queue.put_nowait((frame.copy(), metadata))
            self._seen[key] = (count + 1, now)
            self.stats["queued"] = index
            if self._worker is None:
                self._worker = threading.Thread(target=self._write_loop,
                                                name="CommandImageCollection", daemon=True)
                self._worker.start()

    @staticmethod
    def _write_png(path, image):
        import cv2
        encoded, data = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        if not encoded:
            raise OSError("PNG保存に失敗しました: " + str(path))
        path.write_bytes(data.tobytes())

    def _save_sample(self, frame, metadata):
        folder = self.directory / ("{:06d}_{}".format(
            metadata["sample"], _safe_name(metadata["target"], 48)))
        folder.mkdir()
        self._write_png(folder / "full.png", frame)
        self._write_png(folder / "japanese_roi.png", _region(frame, metadata["japanese_search_crop"]))
        files = {"full": "full.png", "japanese_roi": "japanese_roi.png"}
        item = metadata["japanese"]
        if item["matched"]:
            x, y = item["position"]
            width, height = item["template_size"]
            self._write_png(folder / "japanese_match.png", _region(frame, (x, y, x + width, y + height)))
            files["japanese"] = "japanese_match.png"
        metadata["files"] = files
        # Metadata is the completion marker. Incomplete writes have no marker.
        (folder / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), "utf-8")
        with (self.directory / "manifest.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"folder": folder.name, **metadata}, ensure_ascii=False) + "\n")

    def _write_session(self, complete):
        document = {"schema_version": 1, "command": self.command_name,
                    "options": {"collect": self.options.collect,
                                "supplemental": self.options.supplemental,
                                "language": self.options.language},
                    "closed": complete, "stats": dict(self.stats),
                    "limits": {"samples": MAX_SAMPLES, "per_check": SAMPLES_PER_CHECK,
                               "interval_seconds": CAPTURE_INTERVAL, "queue": 4}}
        pending = self.directory / "session.json.tmp"
        pending.write_text(json.dumps(document, ensure_ascii=False, indent=2), "utf-8")
        pending.replace(self.directory / "session.json")

    def _write_loop(self):
        try:
            self.directory.mkdir(parents=True, exist_ok=False)
            self._write_session(False)
            LOGGER.warning("[Commands画像収集] 保存先: %s", self.directory)
            while not self._closed.is_set() or not self._queue.empty():
                try:
                    frame, metadata = self._queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                try:
                    self._save_sample(frame, metadata)
                    self.stats["saved"] += 1
                finally:
                    self._queue.task_done()
            self._write_session(True)
            LOGGER.warning("[Commands画像収集] 完了: %s / %s", self.directory, self.stats)
        except Exception as error:
            with self._lock:
                self._capture_failed = True
                self.stats["write_errors"] += 1
            self._warn_once("write", "保存失敗（画像判定は継続）: " + str(error))
            while True:
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    break
            try:
                self._write_session(False)
            except OSError:
                pass

    def close(self):
        """Stop accepting frames, drain pending PNGs without blocking Tk/input."""
        with self._lock:
            self._closed.set()

    def wait_closed(self, timeout=5.0):
        """Offline verification helper; the live command never waits on disk."""
        worker = self._worker
        if worker is not None:
            worker.join(timeout)
            return not worker.is_alive()
        return True


def arm_native_image_collection(command, serial_root, options):
    """Called only by the native Start dialog's explicit Start buttons."""
    previous = getattr(command, SESSION_ATTRIBUTE, None)
    if previous is not None:
        previous.close()
    session = (CommandImageCollection(serial_root, getattr(command, "NAME", "Commands"), options)
               if options.collect or options.supplemental else None)
    setattr(command, SESSION_ATTRIBUTE, session)
    return session


def build_native_image_collection_controls(parent, command, serial_root):
    """Return an arm callback; every opening starts OFF, including favorites."""
    import tkinter as tk
    from tkinter import ttk

    box = ttk.Labelframe(parent, text="多言語版の画像収集（今回の実行のみ）")
    box.pack(fill="x", padx=10, pady=5)
    collect = tk.BooleanVar(master=box, value=False)
    supplemental = tk.BooleanVar(master=box, value=False)
    language = tk.StringVar(master=box, value="")
    targets = getattr(command, "IMAGE_DETECTION_TARGETS", None) or {}
    registered = bool(targets)
    a_registered = any(name in targets for name in (*A_REFERENCES, *MENU_REFERENCES, *BOSS_REFERENCES, *ICON_REFERENCES))
    state = "normal" if registered else "disabled"
    ttk.Checkbutton(box, text="補足画像でのチェック有効モード（A・アイコン・選択位置・再戦HP）",
                    variable=supplemental, state="normal" if a_registered else "disabled").pack(
                        anchor="w", padx=7, pady=2)
    row = ttk.Frame(box)
    row.pack(fill="x", padx=7, pady=2)
    ttk.Checkbutton(row, text="一致時の画像取得（A・再戦・代用できたボス名を除外）",
                    variable=collect, state=state).pack(side="left")
    ttk.Label(row, text="ゲーム言語（記録用）:").pack(side="left", padx=(12, 3))
    ttk.Entry(row, textvariable=language, width=14, state=state).pack(side="left")
    ttk.Label(box, text=(
        "対象: 入口A、メニュー・マップ等のアイコン、選択位置、再戦、アブソル／最終戦名。道具は選択中の行だけで確認します。\n"
        "注意: 進化を済ませてから技変更へ進む順序が前提です。進化可能なまま途中開始すると項目位置が変わる場合があります。\n"
        "通常はFIELD＋戦闘アイコン＋ボスHP、最終イベントはHP表示で確認。メニューは補足一致でも画像保存。次回は両方OFFです。"
        if registered else "登録型 image_check を使用するCommandsが対象です。"),
        foreground="#555555", justify="left", wraplength=930).pack(anchor="w", padx=7, pady=(2, 5))

    def activate():
        return arm_native_image_collection(command, serial_root, CollectionOptions(
            collect=bool(registered and collect.get()),
            supplemental=bool(a_registered and supplemental.get()),
            language=str(language.get()).strip()[:80]))

    return activate
