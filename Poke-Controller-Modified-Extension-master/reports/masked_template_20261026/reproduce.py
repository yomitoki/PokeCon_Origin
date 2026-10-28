r"""Reproduce saved-frame mask comparison; no devices or game inputs.

From repository root:
  .venv314\Scripts\python.exe -B reports/masked_template_20261026/reproduce.py
Optional: --audit-zip D:/Recording/Switch_No3.zip (692 archived step snapshots).
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "SerialController"))
from Commands.PythonCommands.LocalFunction.MaskedTemplate import (
    bright_mask, masked_template_scores, read_image)


def match(frame, template, mask, crop, gray):
    x1, y1, x2, y2 = crop
    source = frame[y1:y2, x1:x2]
    if gray:
        source = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    plain = cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)
    result = masked_template_scores(source, template, mask)
    _, score, _, loc = cv2.minMaxLoc(result)
    return {"rectangle": cv2.minMaxLoc(plain)[1], "masked": score,
            "position": [loc[0] + x1, loc[1] + y1]}


def save_png(path, data):
    path.write_bytes(cv2.imencode(".png", data)[1].tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-zip", type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    frames = {}
    for row in manifest:
        path = HERE / row["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Evidence changed: " + str(path))
        frames[row["index"]] = read_image(path)
    generated = HERE / "generated"
    generated.mkdir(exist_ok=True)
    name_template = frames[456][375:402, 610:716].copy()
    name_mask = bright_mask(name_template, threshold=200, border=2)
    eye_template = read_image(HERE / "evidence/eye_template.png")
    eye_mask = bright_mask(eye_template, threshold=205, border=2)
    for stem, template, mask in (("pikachu", name_template, name_mask),
                                 ("eye", eye_template, eye_mask)):
        save_png(generated / (stem + "_template.png"), template)
        save_png(generated / (stem + "_mask.png"), mask)
        preview = template.copy()
        excluded = mask == 0
        preview[excluded] = np.uint8(preview[excluded] * .4 + np.array([65, 65, 230]) * .6)
        save_png(generated / (stem + "_overlay.png"), preview)
    samples = []
    for row in manifest:
        frame = frames[row["index"]]
        samples.append(dict(row, name=match(frame, name_template, name_mask, [250, 210, 930, 500], True),
                            eye=match(frame, eye_template, eye_mask, [400, 50, 900, 120], False)))

    # Controlled counterexample. The reference is a binary geometric glyph,
    # not an actual Pokemon name. The raw NCC trap is reproducible exactly.
    glyph = np.full((32, 50), 30, np.uint8)
    glyph[5:27, 8:13] = 255
    glyph[5:10, 8:35] = 255
    glyph[15:20, 8:31] = 255
    core = bright_mask(glyph, 255, 0)
    halo = bright_mask(glyph, 255, 2)
    white = np.full((40, 70), 255, np.uint8)
    trap = cv2.matchTemplate(white, glyph, cv2.TM_CCORR_NORMED, mask=core)
    white_scores = masked_template_scores(white, glyph, halo)
    result = {
        "opencv": cv2.__version__, "samples": samples,
        "synthetic_white_surface": {"core_only_raw_NCC": float(trap.max()),
                                    "halo_masked_ZNCC": float(white_scores.max()),
                                    "note": "-2 means invalid/no match, not a probability"},
        "name_training_index": 456, "name_independent_positive_index": 454,
        "name_positive_count_excluding_training": 1,
        "eye_positive_count": 13, "eye_negative_or_obscured_count": 3,
        "limitations": ["Step snapshots, not continuous video or live input",
                        "No Mareep/Scatterbug lock-on name positives in selected 16 snapshots",
                        "No measured false-positive/miss rate for unseen captures",
                        "No default Story/GET behavior changed"],
    }
    (HERE / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.audit_zip:
        audit = json.loads((HERE / "audit_manifest.json").read_text(encoding="utf-8"))
        rows, hits = [], []
        with zipfile.ZipFile(args.audit_zip) as archive:
            for row in audit:
                frame = cv2.imdecode(np.frombuffer(archive.read(row["member"]), np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError("Cannot decode: " + row["member"])
                scores = match(frame, name_template, name_mask, [250, 210, 930, 500], True)
                item = dict(row, **scores)
                rows.append(item)
                if scores["masked"] >= .7 or scores["rectangle"] >= .7:
                    hits.append(item)
        (HERE / "name_audit.json").write_text(json.dumps(
            {"frames": len(rows), "hits": hits, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    font_path = Path("C:/Windows/Fonts/meiryo.ttc")
    font = ImageFont.truetype(str(font_path), 18) if font_path.exists() else ImageFont.load_default()
    title_font = ImageFont.truetype(str(font_path), 26) if font_path.exists() else font
    canvas = Image.new("RGB", (1320, 770), "#f4f5f7")
    draw = ImageDraw.Draw(canvas)
    draw.text((28, 18), "比較マスクの検証 — 白は比較、黒は無視", font=title_font, fill="#15243a")
    for col, (label, suffix) in enumerate((("元の矩形テンプレート", "template"),
                                         ("比較マスク（白＝比較）", "mask"),
                                         ("元画像に重ねる（赤＝無視）", "overlay"))):
        x = 28 + col * 432
        draw.text((x, 75), label, font=font, fill="#15243a")
        pic = Image.open(generated / ("pikachu_" + suffix + ".png")).convert("RGB")
        pic = pic.resize((424, 108), Image.Resampling.NEAREST)
        canvas.paste(pic, (x, 110))
    for col, idx in enumerate((456, 454)):
        x = 28 + col * 650
        frame = frames[idx]
        pic = Image.fromarray(cv2.cvtColor(frame[280:440, 510:790], cv2.COLOR_BGR2RGB))
        pic = pic.resize((560, 320))
        canvas.paste(pic, (x, 275))
        row = next(x for x in samples if x["index"] == idx)
        label = "参照画像を切り出したフレーム" if idx == 456 else "別フレームで検証（背景・位置・Lvが異なる）"
        draw.text((x, 242), label, font=font, fill="#15243a")
        draw.text((x, 606), "四角全体 {:.3f} → マスク {:.3f}".format(
            row["name"]["rectangle"], row["name"]["masked"]), font=title_font, fill="#125a48")
    draw.text((28, 657), "上部の目マーカー：大きい矩形 0.367–0.466 → マスク 0.837–0.878（陽性13枚）", font=font, fill="#15243a")
    draw.text((28, 691), "注意：名称の独立した正例は1枚。実機・GET条件への適用は未検証。", font=font, fill="#5a4220")
    draw.text((28, 723), "出典：既存ZIPの1280×720保存画像。原画像のSHA256・取得時刻はmanifest.json。", font=font, fill="#536170")
    canvas.save(HERE / "comparison.png")
    print("Saved", HERE / "results.json")
    print("Independent Pikachu positive:", next(x["name"] for x in samples if x["index"] == 454))
    print("White-surface counterexample:", result["synthetic_white_surface"])


if __name__ == "__main__":
    main()
