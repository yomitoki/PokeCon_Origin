#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preflight checks for DevStudio's registered image-detection library."""
from __future__ import annotations

import os
import struct
import importlib.util


def resolve_template_path(template_path, template_root):
    value = str(template_path or "").strip()
    if not value:
        return ""
    if os.path.isabs(value):
        return os.path.abspath(value)
    return os.path.abspath(os.path.join(os.path.dirname(template_root), value))


def _jpeg_size(data):
    if not data.startswith(b"\xff\xd8"):
        return None
    position = 2
    start_of_frame = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) \
        | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in (0x01, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            break
        length = struct.unpack(">H", data[position:position + 2])[0]
        if length < 2 or position + length > len(data):
            break
        if marker in start_of_frame and length >= 8:
            height, width = struct.unpack(">HH", data[position + 3:position + 7])
            channels = data[position + 7]
            return int(width), int(height), int(channels), False, "JPEG"
        position += length
    return None


def _image_metadata(path):
    """Read dimensions without requiring OpenCV/Pillow in standalone DevStudio."""
    try:
        with open(path, "rb") as stream:
            data = stream.read()
    except OSError:
        return None
    if len(data) >= 26 and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        color_type = data[25]
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type, 0)
        return int(width), int(height), channels, color_type in (4, 6), "PNG"
    jpeg = _jpeg_size(data)
    if jpeg:
        return jpeg
    if len(data) >= 30 and data.startswith(b"BM"):
        width = struct.unpack("<i", data[18:22])[0]
        height = abs(struct.unpack("<i", data[22:26])[0])
        bits = struct.unpack("<H", data[28:30])[0]
        channels = 4 if bits == 32 else (3 if bits == 24 else 1)
        return abs(int(width)), int(height), channels, bits == 32, "BMP"
    return None


def _optional_image_statistics(path):
    """Return pixel statistics only when PokeCon's OpenCV runtime is available."""
    if importlib.util.find_spec("numpy") is None or importlib.util.find_spec("cv2") is None:
        return None
    try:
        import cv2
        import numpy as np
        encoded = np.fromfile(path, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
        if image is None or image.size == 0:
            return None
        if image.ndim == 3:
            gray = cv2.cvtColor(
                image, cv2.COLOR_BGRA2GRAY if image.shape[2] == 4
                else cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        alpha_nonzero = None
        if image.ndim == 3 and image.shape[2] == 4:
            alpha_nonzero = bool(np.any(image[:, :, 3]))
        return {"contrast": float(np.std(gray)), "alpha_nonzero": alpha_nonzero}
    except (ImportError, OSError, ValueError):
        return None


def _crop_values(value):
    if value in (None, ""):
        return [0, 0, 0, 0]
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("検知範囲は x1,y1,x2,y2 の4整数で指定します。")
    try:
        return [int(part) for part in value]
    except (TypeError, ValueError):
        raise ValueError("検知範囲に整数以外が含まれています。")


def suggested_crop(crop, template_size, frame_size):
    """Expand a valid cropped region just enough to contain the template."""
    x1, y1, x2, y2 = _crop_values(crop)
    template_width, template_height = [int(value) for value in template_size]
    frame_width, frame_height = [int(value) for value in frame_size]
    if not any((x1, y1, x2, y2)):
        if template_width <= frame_width and template_height <= frame_height:
            return [0, 0, 0, 0]
        raise ValueError("テンプレートが基準画面より大きいため、範囲の拡張では修正できません。")
    if min(x1, y1, x2, y2) < 0 or x2 <= x1 or y2 <= y1:
        raise ValueError("座標自体が不正なため、画像検知編集画面で範囲を指定し直してください。")
    if x1 >= frame_width or y1 >= frame_height:
        raise ValueError("範囲の開始位置が基準画面外です。")
    required_x2 = max(x2, x1 + template_width)
    required_y2 = max(y2, y1 + template_height)
    if required_x2 > frame_width or required_y2 > frame_height:
        raise ValueError("現在位置のままでは基準画面内に拡張できません。範囲開始位置か画像を調整してください。")
    return [x1, y1, required_x2, required_y2]


def _result(name, index, status, codes, summary, details, fixes, **extra):
    row = {
        "name": str(name), "index": index, "status": status,
        "codes": list(codes), "summary": str(summary),
        "details": list(details), "fixes": list(fixes),
    }
    row.update(extra)
    return row


def inspect_variant(name, index, variant, template_root, frame_size=(1280, 720)):
    errors, warnings, fixes = [], [], []
    codes = []
    warning_codes = []
    ignored_warning_codes = []
    ignored_details = []
    configured_ignored = {
        str(value) for value in variant.get("health_ignored_warnings", [])}
    frame_width, frame_height = [int(value) for value in frame_size]
    raw_path = str(variant.get("template_path", "") or "")
    path = resolve_template_path(raw_path, template_root)
    metadata = None
    image_size = None
    crop_size = None
    crop = variant.get("crop", [0, 0, 0, 0])
    repairable = False

    if not raw_path:
        errors.append("テンプレート画像が指定されていません。")
        codes.append("empty_path")
        fixes.append("画像検知編集画面でテンプレート画像を選択してください。")
    elif not os.path.isfile(path):
        errors.append("テンプレート画像ファイルがありません: " + path)
        codes.append("missing_file")
        fixes.append("移動した画像を選び直すか、登録からこのパターンを外してください。")
    else:
        metadata = _image_metadata(path)
        if metadata is None:
            errors.append("画像をデコードできません。破損または未対応形式です: " + path)
            codes.append("unreadable_image")
            fixes.append("PNGまたはJPEGで保存し直してから画像を選び直してください。")
        else:
            image_width, image_height, channels, has_alpha, _format = metadata
            image_size = (image_width, image_height)
            if image_width < 2 or image_height < 2:
                errors.append("テンプレート画像が小さすぎます: {}x{}".format(image_width, image_height))
                codes.append("tiny_image")
                fixes.append("2x2より大きく、判定特徴を含む範囲を切り出してください。")
            if channels not in (1, 3, 4):
                errors.append("未対応のチャンネル数です: {}".format(channels))
                codes.append("invalid_channels")
                fixes.append("グレースケール、RGB、RGBAのPNG/JPEGへ変換してください。")
            statistics = _optional_image_statistics(path)
            optional_warnings = []
            if has_alpha and statistics and statistics.get("alpha_nonzero") is False:
                optional_warnings.append((
                    "transparent_image",
                    "画像が完全に透明です。実行時には透明度が無視され、黒画像として読まれます。",
                    "透明部分を除いて切り出すか、背景を含むRGB画像へ変換してください。"))
            if statistics and statistics.get("contrast", 100.0) < 2.0:
                optional_warnings.append((
                    "low_contrast",
                    "画像内の明暗差がほとんどなく、テンプレート一致が不安定です。",
                    "文字画面の色判定用ならこの警告を除外できます。通常画像なら輪郭や模様を含めてください。"))
            for warning_code, message, fix in optional_warnings:
                if warning_code in configured_ignored:
                    ignored_warning_codes.append(warning_code)
                    ignored_details.append(message)
                else:
                    warning_codes.append(warning_code)
                    warnings.append(message)
                    codes.append(warning_code)
                    fixes.append(fix)

    try:
        threshold = float(variant.get("threshold", 0.8))
        if not 0.0 <= threshold <= 1.0:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("閾値が0～1の範囲ではありません。")
        codes.append("invalid_threshold")
        fixes.append("閾値を0.00～1.00に設定してください（開始目安は0.80）。")

    try:
        crop = _crop_values(crop)
        if min(crop) < 0:
            raise ValueError("検知範囲に負数があります。")
        if any(crop):
            x1, y1, x2, y2 = crop
            if x2 <= x1 or y2 <= y1:
                raise ValueError("検知範囲の終点は開始点より右下にしてください。")
            crop_size = (x2 - x1, y2 - y1)
            if x2 > frame_width or y2 > frame_height:
                errors.append("検知範囲が基準画面{}x{}の外へ出ています。".format(frame_width, frame_height))
                codes.append("crop_outside_frame")
                fixes.append("基準画面サイズを実際の入力に合わせるか、x2/y2を画面内へ戻してください。")
        else:
            crop_size = (frame_width, frame_height)
    except ValueError as error:
        errors.append(str(error))
        codes.append("invalid_crop")
        fixes.append("範囲を x1,y1,x2,y2 で指定し直してください。0,0,0,0は画面全体です。")
        crop_size = None

    if image_size and crop_size:
        if image_size[0] > crop_size[0] or image_size[1] > crop_size[1]:
            errors.append("検知範囲{}x{}よりテンプレート画像{}x{}が大きいため例外になります。".format(
                crop_size[0], crop_size[1], image_size[0], image_size[1]))
            codes.append("template_larger_than_crop")
            fixes.append("検知範囲を画像以上に広げるか、特徴を残してテンプレートを小さく切り出してください。")
            try:
                repairable = suggested_crop(crop, image_size, frame_size) != crop
            except ValueError:
                repairable = False

    status = "エラー" if errors else ("警告" if warnings else (
        "除外" if ignored_details else "正常"))
    details = errors + warnings
    if status == "除外":
        details = ignored_details
    return _result(
        name, index, status, codes,
        details[0] if details else "画像と検知設定に問題は見つかりませんでした。",
        details, list(dict.fromkeys(fixes)), path=path, raw_path=raw_path,
        image_size=image_size, crop=crop, crop_size=crop_size,
        frame_size=(frame_width, frame_height), repairable=repairable,
        warning_codes=warning_codes,
        ignored_warning_codes=ignored_warning_codes,
    )


def _inspect_library_structure(data):
    rows = []
    targets, lists = data.get("targets", {}), data.get("lists", {})
    for name, target in targets.items():
        if not target.get("variants"):
            rows.append(_result(
                name, None, "エラー", ["no_variants"],
                "画像パターンが1件も登録されていません。",
                ["画像パターンが1件も登録されていません。"],
                ["画像検知編集画面で画像を追加するか、空の検知名を削除してください。"],
                path="", image_size=None, crop=None, crop_size=None,
                frame_size=None, repairable=False))

    def visit(name, stack):
        if name in stack:
            raise ValueError("循環: " + " -> ".join(stack + [name]))
        if name not in lists:
            raise ValueError("存在しないフォルダー: " + name)
        for member in lists[name].get("members", []):
            member_type, member_id = member.get("type"), str(member.get("id", ""))
            if member_type == "target" and member_id not in targets:
                raise ValueError("存在しない画像検知: " + member_id)
            if member_type == "list":
                visit(member_id, stack + [name])

    for name in lists:
        try:
            visit(name, [])
        except ValueError as error:
            rows.append(_result(
                "フォルダー: " + name, None, "エラー", ["invalid_list"], str(error),
                [str(error)], ["画像検知ワークスペースで参照先を外すか、正しい登録を追加してください。"],
                path="", image_size=None, crop=None, crop_size=None,
                frame_size=None, repairable=False))
    return rows


def audit_image_library(data, template_root, frame_size=(1280, 720)):
    frame_width, frame_height = [int(value) for value in frame_size]
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("基準画面サイズは1以上の幅・高さを指定してください。")
    rows = []
    for name in sorted(data.get("targets", {}), key=str.casefold):
        variants = data["targets"][name].get("variants", [])
        for index, variant in enumerate(variants):
            rows.append(inspect_variant(
                name, index, variant, template_root, (frame_width, frame_height)))
    rows.extend(_inspect_library_structure(data))
    return rows
