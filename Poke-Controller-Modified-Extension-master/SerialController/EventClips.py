"""Extract event highlights from finalized, AV-corrected recordings."""
import copy
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import threading

import cv2
import numpy as np

from ImageDetectionMonitor import crop_search_region, match_variant


# Include the encoding policy in cache identities. Older CRF-18 exports are
# useful playback copies, but must not stand in for template-source clips.
CLIP_EXPORT_VERSION = 2


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_rule(rule):
    rule = copy.deepcopy(rule)
    stages = rule.get("stages", [])
    if not 1 <= len(stages) <= 2:
        raise ValueError("条件グループは1〜2個必要です。")
    for stage in stages:
        if stage.get("operator", "AND") not in ("AND", "OR"):
            raise ValueError("条件の組み合わせはANDかORです。")
        if not 1 <= len(stage.get("targets", [])) <= 32:
            raise ValueError("各グループに画像条件を1〜32個指定してください。")
        stage["stable_seconds"] = _number(stage.get("stable_seconds", 0), 0, 60)
        for target in stage["targets"]:
            if not isinstance(target.get("expected", True), bool):
                raise ValueError("画像条件の一致／不一致を指定してください。")
            if target.get("operator", "OR") not in ("AND", "OR", "AT_LEAST_2", "AT_LEAST_3", "AT_LEAST_4") or not target.get("variants"):
                raise ValueError("登録画像のパターンがありません。")
            for variant in target["variants"]:
                variant["threshold"] = _number(variant.get("threshold", .85), 0, 1)
                if not variant.get("template_path"):
                    raise ValueError("テンプレート画像を指定してください。")
    for name, default, minimum, maximum in (
            ("within_seconds", 30, .01, 3600), ("pre_seconds", 5, 0, 300),
            ("post_seconds", 5, .01, 300), ("interval_seconds", .1, 0, 10),
            ("cooldown_seconds", 5, 0, 3600), ("max_total_gb", 10, .001, 100000)):
        rule[name] = _number(rule.get(name, default), minimum, maximum)
    return rule


def za_field_hard_targets(library):
    """The current ZA non-battle HARD predicate on one recorded frame.

    This does not execute Commands or claim the runtime's repeated fresh-frame
    checks. Sampled stability is configured separately by the clip rule.
    """
    groups = (
        ("ZA HARD: FIELD（前／後）", True,
         ("POKEMON_ZA_FIELD_W", "POKEMON_ZA_FIELD_BACK_W")),
        ("ZA HARD: 手持ち／FIELD確認", True,
         ("POKEMON_ZA_MERIP_ICON_GET5", "POKEMON_ZA_BATTLE", "POKEMON_ZA_WANINOKO_ICON",
          "POKEMON_ZA_ODAIRU_ICON", "POKEMON_ZA_ABSOL_ICON", "POKEMON_ZA_DEAD")),
        ("ZA HARD: 戦闘ボール／Escape", False,
         ("POKEMON_ZA_BATTLE_BALL_CHECK", "POKEMON_ZA_ESCAPE")),
    )
    targets = []
    for label, expected, names in groups:
        variants = []
        for name in names:
            target = library.get("targets", {}).get(name, {})
            if not target.get("variants") or target.get("operator", "OR") != "OR":
                raise ValueError("ZA HARDに必要なOR登録画像を確認できません: " + name)
            variants.extend(copy.deepcopy(target["variants"]))
        targets.append({"name": label, "operator": "OR", "expected": expected,
                        "variants": variants, "source_targets": list(names)})
    return targets


def _number(value, minimum, maximum):
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError("数値は{}〜{}の範囲で指定してください。".format(minimum, maximum))
    return number


def snapshot_rule(rule, base_directory):
    rule = validate_rule(rule)
    for stage in rule["stages"]:
        for target in stage["targets"]:
            for variant in target["variants"]:
                path = Path(variant["template_path"])
                if not path.is_absolute():
                    path = Path(base_directory) / path
                variant["template_path"] = str(path.resolve(strict=True))
                variant["sha256"] = sha256(path)
    return rule


class EventSequence:
    """AND/OR stages, sampled stability, bounded THEN, and edge rearming."""
    def __init__(self, rule):
        self.rule = rule
        self.stage = 0
        self.since = None
        self.started = None
        self.latched = False
        self.cooldown_until = -1.0

    def update(self, now, matches):
        if self.latched:
            if not matches[0] and now >= self.cooldown_until:
                self.latched = False
            return None
        if self.started is not None and now - self.started > self.rule["within_seconds"]:
            self.stage, self.since, self.started = 0, None, None
        if not matches[self.stage]:
            self.since = None
            return None
        if self.since is None:
            self.since = now
        if now - self.since + 1e-8 < self.rule["stages"][self.stage]["stable_seconds"]:
            return None
        if self.started is None:
            self.started = now
        if self.stage + 1 < len(self.rule["stages"]):
            self.stage += 1
            self.since = None
            return None  # THEN must use a later observation.
        event = {"started_seconds": self.started, "confirmed_seconds": now}
        self.stage, self.since, self.started = 0, None, None
        self.latched = True
        self.cooldown_until = now + self.rule["cooldown_seconds"]
        return event


class EventMatcher:
    def __init__(self, rule):
        self.rule = validate_rule(rule)
        self.templates = {}
        for stage in self.rule["stages"]:
            for target in stage["targets"]:
                for variant in target["variants"]:
                    path = variant["template_path"]
                    if variant.get("sha256") and sha256(path) != variant["sha256"]:
                        raise ValueError("設定保存後に画像が変更されています: " + path)
                    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if image is None:
                        raise ValueError("画像を読み込めません: " + path)
                    cropped, _ = crop_search_region(image, variant.get("template_crop", []))
                    compared = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY) if variant.get("use_gray", True) else cropped
                    variation = np.std(compared, axis=(0, 1))
                    if float(np.max(variation)) < .01:
                        raise ValueError("単色の画像は一致条件に使用できません: " + path)
                    if variant.get("exclude_regions"):
                        raise ValueError("除外範囲付きの画像条件は未対応です。検知範囲を絞った画像を登録してください: " + path)
                    self.templates[path] = image

    def matches(self, frame):
        stages = []
        for stage in self.rule["stages"]:
            targets = []
            for target in stage["targets"]:
                variants = []
                for variant in target["variants"]:
                    source, offset = crop_search_region(frame, variant.get("crop", []))
                    template, _ = crop_search_region(self.templates[variant["template_path"]], variant.get("template_crop", []))
                    variants.append(match_variant(source, template,
                                                  variant, offset)["matched"])
                operator = target.get("operator", "OR")
                matched = (sum(variants) >= int(operator.rsplit("_", 1)[1])
                           if operator.startswith("AT_LEAST_") else
                           (all if operator == "AND" else any)(variants))
                targets.append(matched if target.get("expected", True) else not matched)
            stages.append((all if stage.get("operator", "AND") == "AND" else any)(targets))
        return stages


def event_intervals(events, rule, duration):
    intervals = []
    for event in events:
        start = max(0.0, event["confirmed_seconds"] - rule["pre_seconds"])
        end = min(duration, event["confirmed_seconds"] + rule["post_seconds"])
        if intervals and start <= intervals[-1][1]:
            intervals[-1][1] = max(intervals[-1][1], end)
        else:
            intervals.append([start, end])
    return intervals


def _run_ffmpeg(arguments, cancel):
    executable = shutil.which("ffmpeg")
    if not executable:
        import imageio_ffmpeg
        executable = imageio_ffmpeg.get_ffmpeg_exe()
    import tempfile
    with tempfile.TemporaryFile() as errors:
        options = {"stdout": subprocess.DEVNULL, "stderr": errors}
        if os.name == "nt":
            options["creationflags"] = 0x08000000 | 0x00000040
        process = subprocess.Popen([executable, "-v", "error"] + arguments, **options)
        while process.poll() is None:
            if cancel.wait(.1):
                process.terminate()
                process.wait()
                raise RuntimeError("クリップ作成を中止しました。元動画は保持しています。")
        if process.returncode:
            errors.seek(0)
            raise RuntimeError(errors.read().decode("utf-8", errors="replace")[-3000:])


@contextlib.contextmanager
def _export_lock(base, cancel):
    # Serialize scanning/encoding per destination to bound CPU and disk use.
    # Short lock attempts also let a waiting export be cancelled promptly.
    from InputSetRuntimeRegistry import _registry_lock
    with contextlib.ExitStack() as stack:
        while True:
            if cancel.is_set():
                raise RuntimeError("解析を中止しました。")
            try:
                stack.enter_context(_registry_lock(str(base / ".event_clip_capacity"), timeout=.5))
                break
            except TimeoutError:
                continue
        yield


def export_event_clips(media_path, rule, output_dir=None, cancel=None, progress=None):
    cancel = cancel or threading.Event()
    source = Path(media_path).resolve(strict=True)
    base = Path(output_dir or rule.get("output_dir") or source.parent.parent / "EventClips").resolve()
    if base == source.parent or source.parent in base.parents:
        raise ValueError("クリップ保存先は元録画フォルダーの外に指定してください。")
    with _export_lock(base, cancel):
        return _export_event_clips(source, rule, base, cancel, progress)


def _export_event_clips(media_path, rule, output_dir=None, cancel=None, progress=None):
    """Never re-time audio: trim both streams from the corrected final MP4."""
    cancel = cancel or threading.Event()
    rule = validate_rule(rule)
    source = Path(media_path).resolve(strict=True)
    identity = (source.stat().st_size, source.stat().st_mtime_ns)
    base = Path(output_dir or rule.get("output_dir") or source.parent.parent / "EventClips").resolve()
    # Uploaded session directories can be removed by the existing uploader.
    if base == source.parent or source.parent in base.parents:
        raise ValueError("クリップ保存先は元録画フォルダーの外に指定してください。")
    key = hashlib.sha256((str(CLIP_EXPORT_VERSION) + str(source) + repr(identity)
                          + json.dumps(rule, sort_keys=True)).encode()).hexdigest()[:20]
    destination = base / key
    manifest_path = destination / "events.json"
    existing = {}
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        valid = [c for c in saved.get("clips", []) if Path(c["path"]).is_file()
                 and sha256(c["path"]) == c["sha256"]]
        existing = {(c["start_seconds"], c["end_seconds"]): c for c in valid}
        if (saved.get("complete") and len(valid) == len(saved.get("clips", []))
                and not saved.get("skipped_capacity")):
            saved["manifest"] = str(manifest_path)
            return saved
    matcher = EventMatcher(rule)
    sequence = EventSequence(rule)
    capture = cv2.VideoCapture(str(source))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        pixel_format = int(capture.get(cv2.CAP_PROP_CODEC_PIXEL_FORMAT))
        if not capture.isOpened() or not math.isfinite(fps) or fps <= 0 or count <= 0:
            raise ValueError("動画のFPS／長さを読み込めません。完成MP4を選択してください。")
        step = max(1, int(round(fps * rule["interval_seconds"])))
        events, decoded = [], 0
        while capture.grab():
            if cancel.is_set():
                raise RuntimeError("解析を中止しました。")
            index = decoded
            decoded += 1
            if index % step:
                continue
            ok, frame = capture.retrieve()
            if not ok or frame is None:
                raise RuntimeError("動画の復号に失敗しました。解析完了として保存しません。")
            event = sequence.update(index / fps, matcher.matches(frame))
            if event is not None:
                events.append(event)
                if len(events) > 500:
                    raise ValueError("一致が500件を超えました。条件を絞ってください。")
            if progress and index % max(step, int(fps)) < step:
                progress("解析 {:.1f}% / 成立{}件".format(min(100, decoded / count * 100), len(events)))
        if abs(decoded - count) > 1:
            raise RuntimeError("動画の途中で読込が終了しました。元動画を保持します。")
    finally:
        capture.release()
    if identity != (source.stat().st_size, source.stat().st_mtime_ns):
        raise RuntimeError("解析中に元動画が変更されました。")
    destination.mkdir(parents=True, exist_ok=True)
    result = {"complete": False, "export_version": CLIP_EXPORT_VERSION,
              "video_encoding": "h264_lossless", "frame_size": [width, height],
              "source": str(source), "source_size": identity[0],
              "source_mtime_ns": identity[1], "fps": fps, "sample_step_frames": step,
              "sample_interval_seconds": step / fps, "events": events, "rule": rule,
              "clips": [], "skipped_capacity": []}
    for number, (start, end) in enumerate(event_intervals(events, rule, decoded / fps), 1):
        if cancel.is_set():
            raise RuntimeError("解析を中止しました。")
        if (start, end) in existing:
            result["clips"].append(existing[(start, end)])
            continue
        path = destination / ("event_{:03d}.mp4".format(number))
        temporary = destination / ("event_{:03d}.partial.mp4".format(number))
        if progress:
            progress("クリップ{}を作成しています".format(number))
        try:
            used = sum(p.stat().st_size for p in base.rglob("*.mp4") if p.is_file())
            remaining = int(rule["max_total_gb"] * 1024 ** 3) - used
            if remaining < 1024 * 1024:
                result["skipped_capacity"].append([start, end])
                continue
            _run_ffmpeg(["-y", "-threads", "1", "-i", str(source),
                     "-ss", str(start), "-t", str(end - start),
                     "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264",
                     "-threads", "1", "-filter_threads", "1", "-preset", "veryfast",
                     # Preserve decoded source pixels for later image-check
                     # registration. Do not force 4:2:0 or resize the picture.
                     "-crf", "0", "-c:a", "aac",
                     "-brand", "mp42", "-tag:v", "avc1", "-movflags", "+faststart",
                     "-fs", str(remaining), str(temporary)], cancel)
            check = cv2.VideoCapture(str(temporary))
            try:
                rate = float(check.get(cv2.CAP_PROP_FPS))
                length = float(check.get(cv2.CAP_PROP_FRAME_COUNT)) / max(1.0, rate)
                clip_size = (int(check.get(cv2.CAP_PROP_FRAME_WIDTH)),
                             int(check.get(cv2.CAP_PROP_FRAME_HEIGHT)))
                clip_format = int(check.get(cv2.CAP_PROP_CODEC_PIXEL_FORMAT))
            finally:
                check.release()
            if temporary.stat().st_size > remaining or length + 2 / fps < end - start:
                if temporary.stat().st_size < remaining * .9:
                    raise RuntimeError("クリップが指定区間より短く出力されました。元動画を保持します。")
                temporary.unlink()  # Only the partial file created by this export.
                result["skipped_capacity"].append([start, end])
                continue
            if clip_size != (width, height) or not math.isclose(rate, fps, rel_tol=1e-5):
                raise RuntimeError("クリップの解像度／FPSが元動画と一致しません。元動画を保持します。")
            if pixel_format != -1 and clip_format != pixel_format:
                raise RuntimeError("クリップの色形式が元動画と一致しません。元動画を保持します。")
            _run_ffmpeg(["-threads", "1", "-i", str(temporary), "-f", "null", "-"], cancel)
            if not temporary.is_file() or temporary.stat().st_size <= 1024:
                raise RuntimeError("クリップ出力が空です。元動画を保持します。")
            os.replace(str(temporary), str(path))
        finally:
            if temporary.exists():
                temporary.unlink()
        result["clips"].append({"path": str(path), "start_seconds": start,
                                "end_seconds": end, "sha256": sha256(path)})
    if identity != (source.stat().st_size, source.stat().st_mtime_ns):
        raise RuntimeError("クリップ作成中に元動画が変更されました。")
    result["complete"] = True
    result["manifest"] = str(manifest_path)
    temporary_manifest = destination / "events.partial.json"
    temporary_manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(temporary_manifest), str(manifest_path))
    return result
