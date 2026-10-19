"""Export a local, immutable-frame Commands image-detection snapshot.

This module never acquires camera images, runs Commands, or sends input. The
caller is responsible for supplying a fresh frame and its sequence. JSON is
published last as the commit marker for its same-prefix PNG. Publication uses
exclusive hard links: an existing evidence file is never replaced.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import uuid
from collections.abc import Mapping

import cv2
import numpy as np

try:
    from . import ImageDetectionMonitor as _monitor
except ImportError:
    import ImageDetectionMonitor as _monitor


MAX_TARGETS = 128
MAX_VARIANTS_PER_TARGET = 64
MAX_METADATA_ITEMS = 256
MAX_METADATA_DEPTH = 8
MAX_STRING_LENGTH = 8192
_KNOWN_OPTIONS = frozenset(("template_path", "crop", "threshold", "use_gray",
    "template_crop", "min_mean_luma", "anchor_variant", "anchor_offset",
    "anchor_tolerance", "name", "description", "variant", "id"))


def _json_value(value, counts, depth=0):
    """Bound caller metadata without invoking arbitrary repr/item methods."""
    if depth > MAX_METADATA_DEPTH:
        counts["depth_omitted"] += 1
        return None
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        counts["nonfinite_as_null"] += 1
        return None
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            counts["strings_truncated"] += 1
        return value[:MAX_STRING_LENGTH]
    if isinstance(value, Path):
        return _json_value(str(value), counts, depth)
    if isinstance(value, np.generic):
        return _json_value(value.item(), counts, depth)
    if isinstance(value, Mapping):
        result = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_METADATA_ITEMS:
                counts["items_omitted"] += max(1, len(value) - index)
                break
            if not isinstance(key, (str, int, float, bool)):
                counts["items_omitted"] += 1
                continue
            result[str(key)[:MAX_STRING_LENGTH]] = _json_value(item, counts, depth+1)
        return result
    if isinstance(value, (list, tuple)):
        counts["items_omitted"] += max(0, len(value)-MAX_METADATA_ITEMS)
        return [_json_value(item, counts, depth+1) for item in value[:MAX_METADATA_ITEMS]]
    counts["unsupported_values_omitted"] += 1
    return None


def _counts():
    return dict(nonfinite_as_null=0, strings_truncated=0, items_omitted=0,
                depth_omitted=0, unsupported_values_omitted=0)


def _finite(value, label, lower=None, upper=None):
    result = float(value)
    if not math.isfinite(result) or (lower is not None and result < lower) or (upper is not None and result > upper):
        raise ValueError("Invalid " + label)
    return result


def _crop(image, crop, label):
    if crop is not None and crop != []:
        if not isinstance(crop, (list, tuple)) or len(crop) != 4:
            raise ValueError(label + " must be [x1,y1,x2,y2]")
        for value in crop:
            _finite(value, label)
    return _monitor.crop_search_region(image, crop)


def _variant(snapshot, settings, index, serial_root):
    row = dict(index=index, score=None, threshold=None, matched=False,
               position=None, template_size=None, status="error")
    if not isinstance(settings, Mapping):
        row["error"] = "Variant must be a mapping"
        return row
    row["settings"] = dict(settings)
    unsupported = sorted(str(key) for key in settings if key not in _KNOWN_OPTIONS)
    if unsupported:
        row["unsupported_options"] = unsupported
    try:
        threshold = _finite(settings.get("threshold", .8), "threshold", 0., 1.)
        row["threshold"] = threshold
        path = Path(_monitor.resolve_template_path(str(serial_root), settings.get("template_path")))
        row["resolved_template_path"] = str(path.resolve())
        if not settings.get("template_path") or not path.is_file():
            raise ValueError("Template file does not exist")
        template = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if template is None or not template.size:
            raise ValueError("Template could not be decoded")
        row["template_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        template, _ = _crop(template, settings.get("template_crop"), "template_crop")
        search, offset = _crop(snapshot, settings.get("crop"), "crop")
        effective = dict(settings, threshold=threshold)
        detail = _monitor.match_variant(search, template, effective, offset=offset)
        row.update(detail)
        row["score_matched"] = bool(detail["matched"])
        x, y = detail["position"]
        width, height = detail["template_size"]
        patch = snapshot[y:y+height, x:x+width]
        luma = float(np.mean(cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)))
        minimum = _finite(settings.get("min_mean_luma", 0.), "min_mean_luma", 0., 255.)
        row.update(mean_luma=luma, min_mean_luma=minimum, luma_matched=luma >= minimum)
        row["matched"] = bool(detail["matched"] and row["luma_matched"] and not unsupported)
        row["status"] = "unsupported" if unsupported else "ok"
    except Exception as exc:
        # A failed target is evidence too; do not discard the fresh snapshot or
        # skip other variants because one path/setting is invalid.
        row["matched"] = False
        row["status"] = "error"
        row["error"] = "{}: {}".format(type(exc).__name__, str(exc))
    return row


def _anchors(rows, variants):
    for index, settings in enumerate(variants):
        if not isinstance(settings, Mapping) or "anchor_variant" not in settings:
            continue
        row = rows[index]
        try:
            anchor = int(settings["anchor_variant"])
            if anchor < 0 or anchor >= len(rows) or anchor == index:
                raise ValueError("Invalid anchor_variant")
            offset = settings["anchor_offset"]
            tolerance = settings.get("anchor_tolerance", [8, 8])
            if len(offset) != 2 or len(tolerance) != 2:
                raise ValueError("Anchor offsets/tolerances need two values")
            expected = [_finite(v, "anchor_offset") for v in offset]
            allowed = [_finite(v, "anchor_tolerance", 0.) for v in tolerance]
            first, second = rows[anchor]["position"], row["position"]
            if first is None or second is None:
                raise ValueError("Anchor or variant has no detected position")
            delta = [second[axis]-first[axis] for axis in (0, 1)]
            passed = all(abs(delta[axis]-expected[axis]) <= allowed[axis] for axis in (0, 1))
            row["anchor_check"] = dict(anchor_variant=anchor, actual_offset=delta,
                expected_offset=expected, tolerance=allowed, matched=passed)
            row["matched"] = bool(row["matched"] and passed)
        except Exception as exc:
            row.update(matched=False, status="error", error="Anchor: " + str(exc))


def _target(snapshot, name, target, operator, serial_root):
    if isinstance(target, Mapping) and "variants" in target:
        operator = operator or target.get("operator")
        variants = target["variants"]
    elif isinstance(target, Mapping):
        variants = [target]
    else:
        variants = target
    operator = str(operator or "OR").upper()
    result = dict(name=name, operator=operator, matched=False, variants=[])
    if not isinstance(variants, (list, tuple)) or not variants:
        result["error"] = "Target has no variant list"
        return result
    result["variant_count"] = len(variants)
    if len(variants) > MAX_VARIANTS_PER_TARGET:
        result.update(error="Variant limit exceeded; entire target omitted",
                      omitted_variants=len(variants), unsupported=True)
        return result
    rows = [_variant(snapshot, item, index, serial_root) for index, item in enumerate(variants)]
    _anchors(rows, variants)
    result["variants"] = rows
    if operator not in ("AND", "OR"):
        result.update(unsupported=True, error="Unsupported operator: " + operator)
    else:
        result["matched"] = all(row["matched"] for row in rows) if operator == "AND" else any(row["matched"] for row in rows)
    result["failed_variants"] = sum(row["status"] == "error" for row in rows)
    result["unsupported_variants"] = sum(row["status"] == "unsupported" for row in rows)
    return result


def _publish(directory, prefix, image_bytes, json_bytes):
    temporary = []
    published = []
    paths = [directory / (prefix+".png"), directory / (prefix+".json")]
    try:
        for suffix, payload in ((".png.tmp", image_bytes), (".json.tmp", json_bytes)):
            descriptor, name = tempfile.mkstemp(prefix="."+prefix+"_", suffix=suffix, dir=str(directory))
            temporary.append(Path(name))
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        for source, destination in zip(temporary, paths):
            os.link(str(source), str(destination))
            published.append(destination)
    except Exception:
        for path in published:
            path.unlink()
        raise
    finally:
        for path in temporary:
            path.unlink()
    return paths


def save_debug_evidence(directory, frame, sequence, targets, operators, metadata,
                        target_names=None, serial_root=None):
    """Save one caller-supplied fresh BGR frame and all selected variant results.

    Returns ``{'image_path': str, 'json_path': str}``. Missing/invalid frames
    raise ValueError, with no camera/cache fallback. At most MAX_TARGETS are
    evaluated; omissions and unsupported matching options are explicit in JSON.
    """
    if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or not frame.size:
        raise ValueError("A fresh, nonempty uint8 BGR frame is required")
    if not isinstance(targets, Mapping) or not isinstance(operators, Mapping):
        raise ValueError("targets and operators must be mappings")
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be a mapping")
    snapshot = np.array(frame, copy=True, order="C")
    snapshot.setflags(write=False)
    observed = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    # Bind source position/input context now, not after potentially expensive
    # template matching while the caller's command may keep advancing.
    safe_counts = _counts()
    safe_metadata = _json_value(metadata, safe_counts)
    serial_root = Path(serial_root) if serial_root is not None else Path(__file__).resolve().parent
    names = list(targets) if target_names is None else ([target_names] if isinstance(target_names, str) else list(target_names))
    names = list(dict.fromkeys(names))
    selected, omitted = names[:MAX_TARGETS], names[MAX_TARGETS:]
    results = [_target(snapshot, str(name), targets.get(name), operators.get(name), serial_root) for name in selected]
    ok, encoded = cv2.imencode(".png", snapshot)
    if not ok:
        raise RuntimeError("Could not encode evidence PNG")
    image_bytes = encoded.tobytes()
    height, width = snapshot.shape[:2]
    document = dict(schema_version=1, observed_utc=observed,
        frame=dict(sequence=_json_value(sequence, safe_counts), width=width, height=height,
            channels=3, dtype="uint8", color_order="BGR", byte_count=int(snapshot.nbytes),
            sha256=hashlib.sha256(snapshot.tobytes()).hexdigest(),
            hash_encoding="contiguous BGR uint8 pixel bytes; no header"),
        image=dict(sha256=hashlib.sha256(image_bytes).hexdigest(), byte_count=len(image_bytes), format="PNG"),
        metadata=safe_metadata, metadata_sanitization=safe_counts,
        context={key: safe_metadata.get(key) for key in ("command_version", "source_sha256", "source_position", "input_binding")},
        freshness="Caller supplied; backend never acquires or falls back to another frame",
        targets=results, selection=dict(requested_count=len(names), evaluated_count=len(results),
            omitted_count=len(omitted), omitted_names=[str(name) for name in omitted[:MAX_TARGETS]],
            omitted_names_truncated=len(omitted)>MAX_TARGETS, max_targets=MAX_TARGETS,
            max_variants_per_target=MAX_VARIANTS_PER_TARGET))
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    for _ in range(8):
        prefix = "command_debug_" + observed.replace("-", "").replace(":", "").replace(".", "_") + "_" + uuid.uuid4().hex
        document["image"]["file"] = prefix+".png"
        # Sanitise result settings too: invalid NaN thresholds/options must
        # remain a failed diagnostic row, never non-standard JSON literals.
        safe = _json_value(document, _counts())
        json_bytes = (json.dumps(safe, ensure_ascii=False, indent=2, allow_nan=False)+"\n").encode("utf-8")
        try:
            image_path, json_path = _publish(output, prefix, image_bytes, json_bytes)
            return dict(image_path=str(image_path.resolve()), json_path=str(json_path.resolve()))
        except FileExistsError:
            continue
    raise FileExistsError("Could not allocate unique debug evidence paths")
