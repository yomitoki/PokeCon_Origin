# 追加機能のローカルサンプル

PokeConを起動後、Commands タブから次のサンプルを読み込めます。

- `OutputPanelsSample.py` — Others タブで設定した表示枠へログ・画像・HTMLを送ります。
- `VisionAnalysisSample.py` — `battle` モードのHPバー色判定と指定領域OCRを実行します。

`VisionAnalysisSample.py` を使う前に、`../Samples/vision_rules.json` の `rect` を利用するゲーム画面に合わせて変更してください。OCRには `pytesseract` と Tesseract OCR 本体が必要です。

Pythonコマンド内からは次のように送れます。

```python
self.show_output("Output#1", text="ログ")
self.show_output("left_top", image=image_bgr)
self.show_output("right_bottom", html_path=r"C:\work\result.html")
```
