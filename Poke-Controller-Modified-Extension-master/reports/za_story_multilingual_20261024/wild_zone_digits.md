# ワイルドゾーン10・18：数字部分による詳細比較

2026-10-24。参照はSwitch_No3.zipの保存画像とZIPに記載された動画リンク。

## 結果と反映内容

**数字部分に絞ると、10番と18番の一致率の差は約0.015から約0.068へ広がった。** 既存のカード全体のチェック後に、数字だけを同じ範囲で比較する処理を10番・18番へ追加した。

| 実際の画面 | 全体比較の正解／競合 | 全体の差 | 数字比較の正解／競合 | 数字の差 |
| --- | --- | --- | --- | --- |
| 10番 | 0.993871／0.977905 | 0.015966 | 0.991026／0.922379 | **0.068647** |
| 18番 | 0.993668／0.978844 | 0.014824 | 0.991215／0.923287 | **0.067928** |

ここでの値は正規化相関の類似度で、正答確率ではない。上表は各番号の代表画像。

## 採用する条件

1. 既存のPIC全体チェックが成立する。
2. 新しい入力フレームを取得し、その同じフレームでPIC全体も再確認する。最初の判定から画面が切り替わった場合に古い一致を使わない。
3. カード内の数字部分について、10と18の両テンプレートを**同じ43×43pxの範囲**で比較する。
4. 指定番号の数字が **0.90以上**、かつ相手番号より **0.03以上高い**場合だけ一致とする。差が足りなければ、どちらにも確定しない。

元PNGの余白の違いを補正し、数字の切り抜きを39×39pxに揃えた。10は元PNG内 `(169,4)-(208,43)`、18は `(168,0)-(207,39)`。画面側はカード位置に追従して前後左右2pxだけ探索する。元PNGの書き換え・新しい判定画像の配布は不要。

適用する検知キーは `POKEMON_ZA_MOVEPOINT_PIC_W_ZONE10` と `POKEMON_ZA_MOVEPOINT_PIC_W_ZONE18` の2つ。場所名など、マップ移動の既存条件は維持している。この変更だけで移動処理全体が多言語対応になったとは扱わない。

[実装：ZA_wild_zone_number_detail_check](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:46221>) ／ [今回のZA_story変更差分](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/data/wild_zone_source_changes.patch>)

## 保存画像での検証

前回のマップ候補1,773枚を、10・18のカード全体で粗い事前絞り込みなしに走査。どちらかが元の閾値0.9を超えた7枚を目視し、以下の番号を確認した。10・18は各2枚で全て正解し、15番2枚・19番1枚は詳細比較で除外できた。

| 実際の番号 | 10の数字との一致率 | 18の数字との一致率 | 最終結果 | ZIP内の参照時刻 |
| --- | --- | --- | --- | --- |
| 10番 | 0.991026 | 0.922379 | 10番 | [Tivo8Fsbbdg 49:42](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2982s) |
| 10番 | 0.991026 | 0.922379 | 10番 | [Tivo8Fsbbdg 49:45](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2985s) |
| 15番 | 0.791483 | 0.808072 | 10・18とも不一致 | [u3_WGptNscg 36:11](https://www.youtube.com/watch?v=u3_WGptNscg&t=2171s) |
| 15番 | 0.791483 | 0.808072 | 10・18とも不一致 | [u3_WGptNscg 36:15](https://www.youtube.com/watch?v=u3_WGptNscg&t=2175s) |
| 18番 | 0.923287 | 0.991215 | 18番 | [ugB3vep1qMI 95:27](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5727s) |
| 18番 | 0.923287 | 0.991215 | 18番 | [ugB3vep1qMI 95:30](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5730s) |
| 19番 | 0.716400 | 0.742471 | 10・18とも不一致 | [ugB3vep1qMI 98:06](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5886s) |

[7枚の確認画像](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/wild_zone_digit_candidates.jpg>) ／ [照合値・ZIP内メンバー名・原画像SHA-256](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/data/wild_zone_digit_probe.json>)

追加で、変更後の実際の `image_check` → 確認フック → 数字比較を使い、前回の代表40画面（写真28・番号カード12）へ2候補ずつ計80判定を実施。10番・18番だけがそれぞれの候補として一致し、他38画面は両方とも不一致になった。

13件の専用テストが成功。実保存画像の正負例、判定間の10→18／空画面／入力欠落、数字欠落、数字だけでカードがない画面、曖昧な数字、競合PNG欠落、生成サンプルで片側だけ登録された場合、stockのreadFrame API、既存SELECT確認処理を検査した。ノイズ±3・軽いぼかし・JPEG品質90/70の人工変化でも正しい番号だけが成立した。人工変化は実録画の追加事例とは区別する。

[80判定の実行結果](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/data/wild_zone_real_chain_replay.json>) ／ [専用テストログ](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/data/wild_zone_targeted_tests.log>) ／ [テストコード](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/tests/test_za_wild_zone_digits.py>)

必須全体テスト：869件、548.372秒、`FAILED (failures=19, errors=8, skipped=1)`。前回記録との診断名比較：追加0件、解消0件。全体成功とは扱わない。

## 右下の白い領域・？／アイコン部分

今回は追加条件にしていない。数字部分だけで差が広がり、上記の正負例と人工変化でも区別できたため、ユーザー指定の「すでに安定しそうであれば不要」に沿って数字の比較を採用した。右下領域の識別力や状態変化に対する安定性を比較検証済みとするものではない。

## 反映先と確認の限界

OriginのZA_story、stockのZA_story、既存ZA_story.zip、cleanなDevStudio保存documentへ対象2関数だけを同期。再利用用ZA_InfiImageCheckHelpers断片とmetadata、4つの依存グループにも追加関数を含めた。元PNG・他関数・ZIPの対象外427エントリを保持し、変更前を `.codex_backups` に退避した。

確認は保存済み画像と偽Camera入力によるオフライン試験。稼働中PokeConのStart／Stop／Reload／再起動、実カメラ取得、ゲーム入力は行っていない。起動中Commandsへの反映は、ユーザーがCommands停止後にF5 Reloadする際に行う。実機での移動通し・他言語版・描画条件全般での安定性は未確認。
