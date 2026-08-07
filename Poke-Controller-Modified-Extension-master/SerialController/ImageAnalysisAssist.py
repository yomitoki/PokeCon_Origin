"""Low-rate background template suggestions for the Camera preview."""
from __future__ import annotations

import json
import math
import os
import threading
import time

import cv2


class ImageAnalysisAssist:
    def __init__(self, serial_root, result_callback, interval=2.0, max_candidates=10):
        self.serial_root = serial_root
        self.profile_path = os.path.join(serial_root, "Template", "image_detection_profiles.json")
        self.result_callback = result_callback
        self.interval = float(interval)
        self.max_candidates = max(3, min(20, int(max_candidates)))
        self.enabled = False
        self.busy = False
        self.last_submit = 0.0
        self.entries = None
        self.lock = threading.Lock()
        self.game_tag = ""
        self.console_tag = ""
        self.filter_mode = "AND"

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            self.result_callback([])

    def submit(self, frame):
        now = time.monotonic()
        if not self.enabled or self.busy or now - self.last_submit < self.interval:
            return
        self.last_submit = now
        self.busy = True
        threading.Thread(target=self._worker, args=(frame.copy(),), daemon=True).start()

    @staticmethod
    def _target_tags(target):
        legacy_tags = [str(value).strip() for value in target.get("tags", []) if str(value).strip()]
        game_tags = [str(value).strip() for value in target.get("game_tags", []) if str(value).strip()]
        console_tags = [str(value).strip() for value in target.get("console_tags", []) if str(value).strip()]
        has_explicit_game_tags = bool(game_tags)
        for value in legacy_tags:
            lowered = value.lower()
            if lowered.startswith(("console:", "platform:")):
                console_tags.append(value.split(":", 1)[1].strip())
            elif not has_explicit_game_tags:
                game_tags.append(value)
        if not console_tags and any(value.lower() in ("pokemon_za", "za_story") for value in game_tags):
            console_tags.append("Nintendo Switch")
        return list(dict.fromkeys(game_tags)), list(dict.fromkeys(console_tags))

    def _load_entries(self):
        if self.entries is not None:
            return self.entries
        entries = []
        try:
            with open(self.profile_path, "r", encoding="utf-8") as source:
                targets = json.load(source).get("targets", {})
            for name, target in targets.items():
                game_tags, console_tags = self._target_tags(target)
                for variant in target.get("variants", []):
                    relative = str(variant.get("template_path", "")).replace("/", os.sep)
                    path = relative if os.path.isabs(relative) else os.path.join(self.serial_root, relative)
                    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    if image is None or min(image.shape[:2]) < 4:
                        continue
                    entries.append({
                        "name": name,
                        "description": target.get("description", ""),
                        "threshold": float(variant.get("threshold", 0.8)),
                        "game_tags": game_tags,
                        "console_tags": console_tags,
                        "crop": variant.get("crop"),
                        "image": image,
                    })
        except (OSError, ValueError, TypeError):
            entries = []
        self.entries = entries
        return entries

    def reload(self):
        with self.lock:
            self.entries = None

    def set_filters(self, game_tag="", console_tag="", mode="AND"):
        with self.lock:
            self.game_tag = str(game_tag or "").strip()
            self.console_tag = str(console_tag or "").strip()
            self.filter_mode = "OR" if str(mode).upper() == "OR" else "AND"

    def set_max_candidates(self, value):
        with self.lock:
            self.max_candidates = max(3, min(20, int(value)))

    def filter_options(self):
        game_tags = set()
        console_tags = set()
        try:
            with open(self.profile_path, "r", encoding="utf-8") as source:
                targets = json.load(source).get("targets", {})
            for target in targets.values():
                target_games, target_consoles = self._target_tags(target)
                game_tags.update(target_games)
                console_tags.update(target_consoles)
        except (OSError, ValueError, TypeError):
            pass
        game_tags = sorted(game_tags, key=str.lower)
        console_tags = sorted(console_tags, key=str.lower)
        return game_tags, console_tags

    def _matches_filters(self, entry):
        with self.lock:
            game_tag = self.game_tag
            console_tag = self.console_tag
            mode = self.filter_mode
        checks = []
        if game_tag:
            checks.append(game_tag in entry.get("game_tags", []))
        if console_tag:
            checks.append(console_tag in entry.get("console_tags", []))
        if not checks:
            return True
        return any(checks) if mode == "OR" else all(checks)

    def _worker(self, frame):
        try:
            results = self._analyse(frame)
        except Exception:
            results = []
        finally:
            self.busy = False
        self.result_callback(results)

    def _analyse(self, frame):
        entries = self._load_entries()
        if not entries or frame is None:
            return []
        height, width = frame.shape[:2]
        # 160x90 keeps a 244-template library inexpensive. This is an assist
        # ranking pass, not the production image-detection decision.
        scale = min(1.0, 160.0 / max(1, width), 90.0 / max(1, height))
        small = cv2.resize(frame, (max(1, int(width * scale)), max(1, int(height * scale))),
                           interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        best_by_name = {}
        for entry in entries:
            if not self._matches_filters(entry):
                continue
            template = entry["image"]
            tw = max(2, int(template.shape[1] * scale))
            th = max(2, int(template.shape[0] * scale))
            if tw > gray.shape[1] or th > gray.shape[0]:
                continue
            cache_key = (tw, th)
            if entry.get("cache_key") != cache_key:
                entry["reduced"] = cv2.resize(template, cache_key, interpolation=cv2.INTER_AREA)
                entry["cache_key"] = cache_key
            reduced = entry["reduced"]
            crop = entry.get("crop")
            if isinstance(crop, (list, tuple)) and len(crop) == 4:
                crop_width = max(1.0, float(crop[2]) - float(crop[0]))
                crop_height = max(1.0, float(crop[3]) - float(crop[1]))
                template_width = float(template.shape[1])
                template_height = float(template.shape[0])
                area_ratio = (template_width * template_height) / (crop_width * crop_height)
                # Tiny markers searched across a broad range (PIN_MARKER and
                # similar entries) are useful in explicit commands but too
                # prone to false positives for automatic suggestions.
                if (area_ratio < 0.02
                        and (crop_width / template_width > 6.0
                             or crop_height / template_height > 6.0)):
                    continue
                x1 = max(0, min(gray.shape[1], int(float(crop[0]) * scale)))
                y1 = max(0, min(gray.shape[0], int(float(crop[1]) * scale)))
                x2 = max(x1, min(gray.shape[1], int(float(crop[2]) * scale)))
                y2 = max(y1, min(gray.shape[0], int(float(crop[3]) * scale)))
            else:
                x1, y1, x2, y2 = 0, 0, gray.shape[1], gray.shape[0]
            search = gray[y1:y2, x1:x2]
            if search.shape[1] < tw or search.shape[0] < th:
                continue
            response = cv2.matchTemplate(search, reduced, cv2.TM_CCOEFF_NORMED)
            _, score, _, location = cv2.minMaxLoc(response)
            if not math.isfinite(score):
                continue
            threshold = entry["threshold"]
            # Suggestions may sit below the production threshold, but discard
            # weak correlations so the preview remains useful.
            if score < max(0.45, threshold - 0.25):
                continue
            other_similarity = self._second_match_score(response, location, tw, th)
            # A registered template that matches almost as well elsewhere is
            # not a useful suggestion for choosing a discriminative region.
            if other_similarity >= 0.72 and score - other_similarity < 0.08:
                continue
            x, y = int((location[0] + x1) / scale), int((location[1] + y1) / scale)
            item = {
                "name": entry["name"], "description": entry["description"],
                "score": float(score), "threshold": threshold,
                "kind": "registered",
                "game_tags": entry.get("game_tags", []),
                "console_tags": entry.get("console_tags", []),
                "other_similarity": float(other_similarity),
                "uniqueness": float(max(0.0, min(1.0, score - other_similarity))),
                "rect": (x, y, int(tw / scale), int(th / scale)),
            }
            previous = best_by_name.get(entry["name"])
            if previous is None or item["score"] > previous["score"]:
                best_by_name[entry["name"]] = item
        # Registered detections are supporting hints only. Keep at most three
        # and use every remaining slot for unregistered region proposals.
        registered_limit = min(3, self.max_candidates)
        novel_limit = max(0, self.max_candidates - registered_limit)
        results = sorted(best_by_name.values(), key=lambda item: item["score"], reverse=True)[:registered_limit]
        results.extend(self._propose_novel_regions(gray, scale, width, height, results, novel_limit))
        return results

    @staticmethod
    def _intersection_ratio(first, second):
        ax, ay, aw, ah = first
        bx, by, bw, bh = second
        x1, y1 = max(ax, bx), max(ay, by)
        x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        smaller = max(1, min(aw * ah, bw * bh))
        return intersection / smaller

    @staticmethod
    def _second_match_score(response, location, template_width, template_height):
        """Return the strongest match away from the winning location."""
        if response.size <= 1:
            return -1.0
        remaining = response.copy()
        x, y = location
        # Suppress shifted versions of the same object, but retain genuinely
        # separate occurrences elsewhere in the frame.
        radius_x = max(2, int(template_width * 0.75))
        radius_y = max(2, int(template_height * 0.75))
        x1, x2 = max(0, x - radius_x), min(remaining.shape[1], x + radius_x + 1)
        y1, y2 = max(0, y - radius_y), min(remaining.shape[0], y + radius_y + 1)
        remaining[y1:y2, x1:x2] = -1.0
        _, score, _, _ = cv2.minMaxLoc(remaining)
        return float(score) if math.isfinite(score) else -1.0

    @staticmethod
    def _candidate_quality(gray, edges, rect, scale):
        """Measure how reliably a grayscale template can represent *rect*."""
        x, y, width, height = rect
        sx1 = max(0, min(gray.shape[1] - 1, int(x * scale)))
        sy1 = max(0, min(gray.shape[0] - 1, int(y * scale)))
        sx2 = max(sx1 + 1, min(gray.shape[1], int(math.ceil((x + width) * scale))))
        sy2 = max(sy1 + 1, min(gray.shape[0], int(math.ceil((y + height) * scale))))
        region = gray[sy1:sy2, sx1:sx2]
        edge_region = edges[sy1:sy2, sx1:sx2]
        if region.size < 16 or min(region.shape[:2]) < 3:
            return None
        contrast = float(region.std())
        detail = float(cv2.Laplacian(region, cv2.CV_32F).var())
        edge_density = cv2.countNonZero(edge_region) / float(max(1, edge_region.size))
        contrast_score = min(1.0, contrast / 42.0)
        detail_score = min(1.0, detail / 700.0)
        # Empty areas and near-solid edge carpets are both poor templates.
        edge_score = min(1.0, edge_density / 0.12) * min(1.0, max(0.0, 0.65 - edge_density) / 0.25)
        detectability = 0.38 * contrast_score + 0.37 * detail_score + 0.25 * edge_score
        return {
            "small_rect": (sx1, sy1, sx2 - sx1, sy2 - sy1),
            "contrast": contrast,
            "detail": detail,
            "edge_density": edge_density,
            "detectability": detectability,
        }

    def _other_region_similarity(self, gray, small_rect):
        """Compare a candidate with the rest of the frame, excluding itself."""
        x, y, width, height = small_rect
        template = gray[y:y + height, x:x + width]
        if template.size < 16 or min(template.shape[:2]) < 3 or float(template.std()) < 5.0:
            return 1.0
        if template.shape[0] > gray.shape[0] or template.shape[1] > gray.shape[1]:
            return 1.0
        response = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        return self._second_match_score(response, (x, y), width, height)

    def _propose_novel_regions_legacy(self, gray, scale, width, height, occupied, limit):
        """Find a few object-sized regions on the already downscaled frame."""
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 55, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        joined = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        # Keep fine edge contours as well as joined object contours. The joined
        # pass is useful for normal objects, but can swallow very small icons.
        fine_contours = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
        joined_contours = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
        contours = list(fine_contours) + list(joined_contours)
        # Unregistered suggestions may be as small as one quarter of the
        # previous width/height minimum. At 1280x720 this is about 13x16.
        min_width = max(12, int(width * 0.01))
        min_height = max(16, int(height * 0.02))
        # Broad regions are generally background and are easy to select by
        # eye. Keep automatic proposals below 18% of the full frame.
        max_area = width * height * 0.18
        occupied_rects = [item["rect"] for item in occupied]
        proposals = []
        for contour in contours:
            sx, sy, sw, sh = cv2.boundingRect(contour)
            # Four pixels in the low-resolution analysis frame rejects isolated
            # noise while retaining regions near the new quarter-size limit.
            if sw * sh < max(4, gray.shape[0] * gray.shape[1] * 0.0000625):
                continue
            x, y = int(sx / scale), int(sy / scale)
            box_width, box_height = int(sw / scale), int(sh / scale)
            padding_x, padding_y = int(box_width * 0.25), int(box_height * 0.25)
            x -= padding_x
            y -= padding_y
            box_width += padding_x * 2
            box_height += padding_y * 2
            if box_width < min_width:
                x -= (min_width - box_width) // 2
                box_width = min_width
            if box_height < min_height:
                y -= (min_height - box_height) // 2
                box_height = min_height
            x, y = max(0, x), max(0, y)
            box_width = min(box_width, width - x)
            box_height = min(box_height, height - y)
            rect = (x, y, box_width, box_height)
            if box_width * box_height > max_area or box_width < min_width or box_height < min_height:
                continue
            if any(self._intersection_ratio(rect, other) > 0.65 for other in occupied_rects):
                continue
            edge_density = cv2.countNonZero(edges[sy:sy + sh, sx:sx + sw]) / max(1, sw * sh)
            small_region_confidence = min(1.0, (sw * sh) / 16.0)
            edge_density *= 0.5 + 0.5 * small_region_confidence
            proposals.append({
                "name": "未登録の画像範囲候補",
                "description": "物体全体を含めるため最小範囲を確保した候補",
                "score": float(edge_density),
                "threshold": None,
                "kind": "proposal",
                "game_tags": [],
                "console_tags": [],
                "rect": rect,
            })
            occupied_rects.append(rect)
        proposals.sort(key=lambda item: item["score"], reverse=True)
        proposals = proposals[:limit]

        # Highly detailed game frames can merge into one oversized contour.
        # In that case, fall back to object-sized high-detail windows so an
        # unregistered suggestion still appears without shrinking to a dot.
        if len(proposals) < limit:
            window_width = max(8, int(min_width * scale))
            window_height = max(8, int(min_height * scale))
            step_x = max(4, window_width // 2)
            step_y = max(4, window_height // 2)
            windows = []
            for sy in range(0, max(1, gray.shape[0] - window_height + 1), step_y):
                for sx in range(0, max(1, gray.shape[1] - window_width + 1), step_x):
                    region = gray[sy:sy + window_height, sx:sx + window_width]
                    if region.size == 0:
                        continue
                    detail = float(cv2.Laplacian(region, cv2.CV_32F).var())
                    windows.append((detail, sx, sy))
            windows.sort(reverse=True)
            selected_rects = occupied_rects + [item["rect"] for item in proposals]
            for detail, sx, sy in windows:
                x, y = int(sx / scale), int(sy / scale)
                rect = (x, y, min(min_width, width - x), min(min_height, height - y))
                if rect[2] < min_width or rect[3] < min_height:
                    continue
                if any(self._intersection_ratio(rect, other) > 0.65 for other in selected_rects):
                    continue
                proposals.append({
                    "name": "未登録の画像範囲候補",
                    "description": "物体検知に使える大きさを確保した高詳細領域",
                    "score": detail,
                    "threshold": None,
                    "kind": "proposal",
                    "game_tags": [],
                    "console_tags": [],
                    "rect": rect,
                })
                selected_rects.append(rect)
                if len(proposals) >= limit:
                    break
        return proposals[:limit]

    def _propose_novel_regions(self, gray, scale, width, height, occupied, limit):
        """Find distinctive regions that are reliable as detection templates."""
        if limit <= 0:
            return []
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 55, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        joined = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        fine_contours = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
        joined_contours = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
        contours = list(fine_contours) + list(joined_contours)
        min_width = max(12, int(width * 0.01))
        min_height = max(16, int(height * 0.02))
        max_area = width * height * 0.18
        occupied_rects = [item["rect"] for item in occupied]
        raw_candidates = []

        def add_candidate(rect, source):
            if rect[2] < min_width or rect[3] < min_height or rect[2] * rect[3] > max_area:
                return
            if any(self._intersection_ratio(rect, other) > 0.65 for other in occupied_rects):
                return
            metrics = self._candidate_quality(gray, edges, rect, scale)
            if metrics is None or metrics["contrast"] < 6.0 or metrics["detectability"] < 0.18:
                return
            raw_candidates.append({"rect": rect, "source": source, "metrics": metrics})

        for contour in contours:
            sx, sy, sw, sh = cv2.boundingRect(contour)
            if sw * sh < max(4, gray.shape[0] * gray.shape[1] * 0.0000625):
                continue
            x, y = int(sx / scale), int(sy / scale)
            box_width, box_height = int(sw / scale), int(sh / scale)
            padding_x, padding_y = int(box_width * 0.25), int(box_height * 0.25)
            x -= padding_x
            y -= padding_y
            box_width += padding_x * 2
            box_height += padding_y * 2
            if box_width < min_width:
                x -= (min_width - box_width) // 2
                box_width = min_width
            if box_height < min_height:
                y -= (min_height - box_height) // 2
                box_height = min_height
            x, y = max(0, x), max(0, y)
            box_width = min(box_width, width - x)
            box_height = min(box_height, height - y)
            add_candidate((x, y, box_width, box_height), "contour")

        # A regular window pass covers detailed objects swallowed by a broad
        # joined contour. The window remains large enough to retain structure.
        window_width = max(8, int(gray.shape[1] * 0.06), int(min_width * scale))
        window_height = max(8, int(gray.shape[0] * 0.08), int(min_height * scale))
        step_x, step_y = max(4, window_width // 2), max(4, window_height // 2)
        for sy in range(0, max(1, gray.shape[0] - window_height + 1), step_y):
            for sx in range(0, max(1, gray.shape[1] - window_width + 1), step_x):
                x, y = int(sx / scale), int(sy / scale)
                box_width = min(width - x, max(min_width, int(window_width / scale)))
                box_height = min(height - y, max(min_height, int(window_height / scale)))
                add_candidate((x, y, box_width, box_height), "window")

        raw_candidates.sort(key=lambda item: item["metrics"]["detectability"], reverse=True)
        proposals = []
        selected_rects = list(occupied_rects)
        # Uniqueness matching is more expensive than the local quality pass;
        # evaluate only a bounded set at the 160x90 analysis resolution.
        for candidate in raw_candidates[:max(60, limit * 12)]:
            rect = candidate["rect"]
            if any(self._intersection_ratio(rect, other) > 0.65 for other in selected_rects):
                continue
            metrics = candidate["metrics"]
            other_similarity = self._other_region_similarity(gray, metrics["small_rect"])
            # Repeated icons, text rows, tiles, and shifted copies are excluded.
            if other_similarity >= 0.88:
                continue
            uniqueness = max(0.0, min(1.0, (0.92 - other_similarity) / 0.42))
            score = 0.60 * metrics["detectability"] + 0.40 * uniqueness
            if score < 0.30:
                continue
            proposals.append({
                "name": "未登録の識別候補",
                "description": "画面内で重複が少なく、輪郭・明暗差・細部がある領域",
                "score": float(score),
                "threshold": None,
                "kind": "proposal",
                "game_tags": [],
                "console_tags": [],
                "rect": rect,
                "detectability": float(metrics["detectability"]),
                "other_similarity": float(other_similarity),
                "uniqueness": float(uniqueness),
            })
            selected_rects.append(rect)
            if len(proposals) >= limit:
                break
        return proposals
