# ZA_Story 補足モードの未対応判定（2026-10-24 17:16 JST）

追補：[移動後A確認・動画・補完残件の最新版](movement_a_checks.html)。固定移動後Aを通常モードでも確認し、補完ONでは対応するA成功18件の場所確認を代用しました。残件はマップ26件・その他59画像です。**以下は今回の対応前の履歴です。「A未追加」「マップ44件が未代用」等は当時の状態を記録しています。**

**追補:** 以下は17:16時点の一覧です。その後のホテルZ専用の補完探索範囲拡張・8番／18番のプレビュー競合比較と、その他の代用案の画像・動画確認は、[補完案の確認と反映](supplemental_proposals.html)にまとめています。

現行コードで再整理した。**未対応の主対象は33画像・30種類の登録判定**。画像数と操作箇所数は同じではない。

[画像付き一覧を開く](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_checks.html>)

| 区分 | 画像数 | 状況 |
| --- | ---: | --- |
| 未対応の主対象 | 33 | 道具・BOX・冷凍ビーム、マップ共通操作、敗北文、序盤、最終戦の技・予告、第3章目的文、昼夜 |
| マップの場所名条件 | 44 | 日本語場所名 AND PICが残る。10・18番の数字詳細も日本語名を省略しない |
| MEGA以外の再挑戦 | 2 | 初戦の2／3択は別処理。しかも収集除外 |
| 英字・略字 | 20 | MENU・Lv・MAP等。他言語でも字形が同じか未確認 |
| 既存の別経路 | 5 | 進化確認、捕獲、初戦HUD、ホテル入口など。文字分岐や適用条件が残る |

A関連6画像、Xメニュー等4登録、MEGA再戦の8画像、ボス名2画像の代用は実装済み。MEGA再戦と同じ画像を使う初戦2画像は上記の部分対応に含む。

全画面はZIPの既存保存画像。今回、現行の範囲・閾値で再照合したもので、実行時の判定瞬間そのものとは限らない。単一画像の一致はAND・追加確認・Step完了を意味しない。閾値未満や目視で目的表示を確認できない候補は、成功画像に数えない。

未対応の文字判定は、日本語画像が不一致だと画像取得モードでも保存されない。コード・設定・元画像の変更、実ゲーム操作、新規カメラ取得は行っていない。

## 未対応33画像の内訳

| 分類 | 画像数 |
| --- | ---: |
| メニュー・技・道具 | 4 |
| マップの種類・共通操作 | 7 |
| 敗北・降参・報酬 | 7 |
| 開始・序盤イベント | 5 |
| ボス戦の名前・技・予告 | 6 |
| 第3章の進行状態 | 2 |
| 昼夜表示 | 2 |

## 各判定の画像・使用箇所

### N035 力を溜めている……（予告片）

**区分**：未対応の主対象。最終戦の溜め予告。移動の抑止、遮蔽物・緑床への移動や回避のタイミングに使う。

補足モードでも元の文字画像の判定を維持。代用は未実装。 ボス名代用とは別の操作条件。

![力を溜めている……（予告片）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_charge.png)

**判定部分**：POKEMON_ZA_LAST_BATTLE_CHARGE / 探索 [840, 170, 1275, 360] / 閾値 0.78 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N035](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N035_frame.jpg)

![同じ保存画面の検知範囲 N035](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N035_roi.png)

ZIP保存画面の再照合一致 0.9408／閾値0.78。[1:05:45 の動画](https://www.youtube.com/watch?v=XLLw1yJGVCg&t=3945s)。

**使用箇所**：[ZA_mega_mode5_no_attack_watchdog:7158](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7158>) / [ZA_mega_mode5_no_attack_watchdog:7159](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7159>) / [ZA_mega_mode5_no_attack_watchdog:7187](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7187>) / [ZA_mega_mode5_no_attack_watchdog:7243](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7243>) / [ZA_mega_last_battle_charge_update:10593](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10593>)

### N036 コアパニッシャー…

**区分**：未対応の主対象。最終イベントの技操作画面を確認する。4技のうち1つ以上の文字画像が一致するOR判定。

補足モードでも元の文字画像の判定を維持。代用は未実装。 ボス名代用とは別の操作条件。

![コアパニッシャー…](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_move_core_enforcer.png)

**判定部分**：POKEMON_ZA_LAST_BATTLE_MOVE_UI / 探索 [900, 450, 1220, 545] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

[前回ブラウザーで4技表示を確認した動画 1:02:28。下の保存JPGがこの時刻の画像という意味ではない。](https://www.youtube.com/watch?v=XLLw1yJGVCg&t=3748s)

**使用箇所**：[ZA_renda_button:6652](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:6652>) / [ZA_mega_mode5_event_attack_picture:7328](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7328>) / [ZA_mega_mode5_indefinite_field_wait_update:10150](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10150>) / [ZA_mega_mode5_indefinite_field_wait_update:10234](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10234>) / [ZA_mega_evolution_battle:14560](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:14560>)

### N037 グランドフォース

**区分**：未対応の主対象。最終イベントの技操作画面を確認する。N036・N038・N039と同じOR判定の候補。

補足モードでも元の文字画像の判定を維持。代用は未実装。 ボス名代用とは別の操作条件。

![グランドフォース](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_move_lands_wrath.png)

**判定部分**：POKEMON_ZA_LAST_BATTLE_MOVE_UI / 探索 [890, 615, 1210, 720] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

[前回ブラウザーで4技表示を確認した動画 1:02:28。下の保存JPGがこの時刻の画像という意味ではない。](https://www.youtube.com/watch?v=XLLw1yJGVCg&t=3748s)

**使用箇所**：[ZA_renda_button:6652](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:6652>) / [ZA_mega_mode5_event_attack_picture:7328](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7328>) / [ZA_mega_mode5_indefinite_field_wait_update:10150](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10150>) / [ZA_mega_mode5_indefinite_field_wait_update:10234](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10234>) / [ZA_mega_evolution_battle:14560](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:14560>)

### N038 サウザンアロー

**区分**：未対応の主対象。最終イベントの技操作画面を確認する。N036・N037・N039と同じOR判定の候補。

補足モードでも元の文字画像の判定を維持。代用は未実装。 ボス名代用とは別の操作条件。

![サウザンアロー](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_move_thousand_arrows.png)

**判定部分**：POKEMON_ZA_LAST_BATTLE_MOVE_UI / 探索 [760, 525, 1050, 635] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

[前回ブラウザーで4技表示を確認した動画 1:02:28。下の保存JPGがこの時刻の画像という意味ではない。](https://www.youtube.com/watch?v=XLLw1yJGVCg&t=3748s)

**使用箇所**：[ZA_renda_button:6652](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:6652>) / [ZA_mega_mode5_event_attack_picture:7328](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7328>) / [ZA_mega_mode5_indefinite_field_wait_update:10150](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10150>) / [ZA_mega_mode5_indefinite_field_wait_update:10234](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10234>) / [ZA_mega_evolution_battle:14560](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:14560>)

### N039 サウザンウェーブ

**区分**：未対応の主対象。最終イベントの技操作画面を確認する。N036〜N038と同じOR判定の候補。

補足モードでも元の文字画像の判定を維持。代用は未実装。 ボス名代用とは別の操作条件。

![サウザンウェーブ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_move_thousand_waves.png)

**判定部分**：POKEMON_ZA_LAST_BATTLE_MOVE_UI / 探索 [1030, 525, 1280, 635] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

[前回ブラウザーで4技表示を確認した動画 1:02:28。下の保存JPGがこの時刻の画像という意味ではない。](https://www.youtube.com/watch?v=XLLw1yJGVCg&t=3748s)

**使用箇所**：[ZA_renda_button:6652](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:6652>) / [ZA_mega_mode5_event_attack_picture:7328](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7328>) / [ZA_mega_mode5_indefinite_field_wait_update:10150](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10150>) / [ZA_mega_mode5_indefinite_field_wait_update:10234](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10234>) / [ZA_mega_evolution_battle:14560](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:14560>)

### N040 強い光を放…（予告片）

**区分**：未対応の主対象。最終戦の強い光の予告。溜め状態の解除・攻撃前移動の抑止時間などに使う。

補足モードでも元の文字画像の判定を維持。代用は未実装。 ボス名代用とは別の操作条件。

![強い光を放…（予告片）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_strong_light.png)

**判定部分**：POKEMON_ZA_LAST_BATTLE_STRONG_LIGHT / 探索 [840, 170, 1275, 360] / 閾値 0.78 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N040](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N040_frame.jpg)

![同じ保存画面の検知範囲 N040](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N040_roi.png)

ZIP保存画面の再照合一致 0.9045／閾値0.78。[1:08:46 の動画](https://www.youtube.com/watch?v=XLLw1yJGVCg&t=4126s)。

**使用箇所**：[ZA_mega_mode5_no_attack_watchdog:7160](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7160>) / [ZA_mega_mode5_no_attack_watchdog:7161](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7161>) / [ZA_mega_mode5_no_attack_watchdog:7189](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7189>) / [ZA_mega_mode5_no_attack_watchdog:7245](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7245>) / [ZA_mega_last_battle_charge_update:10597](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10597>)

### N012 けいけんアメS

**区分**：未対応の主対象。けいけんアメSを特定し、使用する数・対象へ進む。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![けいけんアメS](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/ame_s.png)

**判定部分**：POKEMON_ZA_AME_S / 探索 [20, 40, 850, 700] / 閾値 0.95 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N012](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N012_frame.jpg)

![同じ保存画面の検知範囲 N012](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N012_roi.png)

ZIP保存画面の再照合一致 0.9873／閾値0.95。[1:57:10 の動画](https://www.youtube.com/watch?v=S7keWU7QF4Q&t=7030s)。

**使用箇所**：[_2_story_ame1:28646](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28646>) / [_2_story_ame2:28653](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28653>)

### N013 移動する／つよさをみる／使えるわざを選ぶ／もちものを持たせる／ニックネーム／マーキング／やめる

**区分**：未対応の主対象。BOX内の黒い操作メニューが開いたことを確認する。

補足モードでも元の文字画像の判定を維持。代用は未実装。 枠だけの試案はフィールド等3枚で誤一致したため不採用。

![移動する／つよさをみる／使えるわざを選ぶ／もちものを持たせる／ニックネーム／マーキング／やめる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/boxmenu.png)

**判定部分**：POKEMON_ZA_BOX_MENU / 探索 [20, 40, 850, 700] / 閾値 0.88 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_2_story_absol_move4:28043](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28043>) / [ZA_common_box_change_box_target1_select:35873](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:35873>)

### N014 れいとうビーム

**区分**：未対応の主対象。シロ編の技変更で、技一覧の「れいとうビーム」を特定する。技画面自体の位置代用とは別。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![れいとうビーム](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_4_e_lank/reibi_skill.png)

**判定部分**：POKEMON_ZA_REIBI_SKILL / 探索 [40, 200, 320, 550] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N014](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N014_frame.jpg)

![同じ保存画面の検知範囲 N014](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N014_roi.png)

ZIP保存画面の再照合一致 0.9892／閾値0.80。[59:46 の動画](https://www.youtube.com/watch?v=RKTDE46FHBM&t=3586s)。

**使用箇所**：[_4_story_shiro_32:30372](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:30372>)

### N015 おいしいみず

**区分**：未対応の主対象。ユカリ編で道具「おいしいみず」を特定する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![おいしいみず](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_6_c_lank/water_icon.png)

**判定部分**：POKEMON_ZA_WATER_ICON / 探索 [50, 50, 600, 680] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_6_story_yukari_48:32991](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:32991>)

### N016 フラダリラボ

**区分**：未対応の主対象。フラダリラボ内の専用地図を識別し、入口移動・復帰を分岐する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![フラダリラボ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/furadari_map.png)

**判定部分**：POKEMON_ZA_FURADARI_MAP / 探索 [20, 0, 300, 70] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N016](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N016_frame.jpg)

![同じ保存画面の検知範囲 N016](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N016_roi.png)

ZIP保存画面の再照合一致 0.9869／閾値0.85。[39:29 の動画](https://www.youtube.com/watch?v=l_MzEJK1KeM&t=2369s)。

**使用箇所**：[ZA_story_furadari_lab_entrance_goto:17546](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17546>) / [ZA_story_furadari_lab_entrance_goto:17552](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17552>) / [ZA_story_furadari_lab_entrance_goto:17664](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17664>) / [ZA_story_furadari_lab_entrance_goto:17670](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17670>) / [ZA_story_furadari_black_comment_recovery_step:18261](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:18261>)

### N017 この場所に移動しますか？

**区分**：未対応の主対象。マップの「この場所に移動しますか？」を確認して移動を確定する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![この場所に移動しますか？](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/move_comment.png)

**判定部分**：POKEMON_ZA_MOVE_COMMENT / 探索 [290, 550, 1000, 690] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N017](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N017_frame.jpg)

![同じ保存画面の検知範囲 N017](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N017_roi.png)

ZIP保存画面の再照合一致 0.9889／閾値0.85。[24:07 の動画](https://www.youtube.com/watch?v=tf8nqOSIsW0&t=1447s)。

**使用箇所**：[ZA_Common_goto_jump:36507](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36507>) / [ZA_Common_goto_jump:36515](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36515>) / [ZA_Common_battle_return:37196](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37196>) / [ZA_bench_goto_pokecenter2:37508](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37508>) / [ZA_bench_goto_pokecenter2:37518](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37518>)

### N018 移動スポット

**区分**：未対応の主対象。マップの移動スポット一覧タブにいることを確認する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![移動スポット](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/movespot_tab.png)

**判定部分**：POKEMON_ZA_MOVESPOT_TAB / 探索 [30, 120, 220, 250] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N018](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N018_frame.jpg)

![同じ保存画面の検知範囲 N018](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N018_roi.png)

ZIP保存画面の再照合一致 0.9865／閾値0.85。[6:32 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=392s)。

**使用箇所**：[ZA_Common_goto_select1:36280](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36280>) / [ZA_Common_goto_select2:36365](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36365>) / [ZA_bench_goto_pokecenter1:37472](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37472>) / [ZA_bench_goto_pokecenter2:37501](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37501>) / [ZA_goto_quasar1:37642](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37642>)

### N019 すべて／施設／ポケモンセンター／カフェ／ゾーン／やめる

**区分**：未対応の主対象。マップの種類フィルターの黒い選択メニューを確認する。Xメニューの位置代用の対象ではない。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![すべて／施設／ポケモンセンター／カフェ／ゾーン／やめる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/select_all.png)

**判定部分**：POKEMON_ZA_SELECT_ALL / 探索 [20, 270, 280, 595] / 閾値 0.75 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N019](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N019_frame.jpg)

![同じ保存画面の検知範囲 N019](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N019_roi.png)

ZIP保存画面の再照合一致 0.9527／閾値0.75。[1:53:50 の動画](https://www.youtube.com/watch?v=snVCacRDGNY&t=6830s)。

**使用箇所**：[ZA_Common_goto_select1:36288](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36288>) / [ZA_Common_goto_select1:36300](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36300>) / [ZA_Common_goto_select1:36320](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36320>) / [ZA_bench_goto_pokecenter1:37476](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37476>) / [ZA_goto_quasar1:37645](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37645>)

### N020 地下水道

**区分**：未対応の主対象。地下水道の専用マップを識別する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![地下水道](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/underground_sewer_map.png)

**判定部分**：POKEMON_ZA_UG_SEWER_MAP / 探索 [20, 0, 250, 70] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N020](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N020_frame.jpg)

![同じ保存画面の検知範囲 N020](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N020_roi.png)

ZIP保存画面の再照合一致 0.9837／閾値0.85。[37:22 の動画](https://www.youtube.com/watch?v=DHVY6rsajPM&t=2242s)。

**使用箇所**：[_5_story_karasuba_69:31919](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:31919>) / [_5_story_karasuba_96:32327](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:32327>)

### N021 ポケモンにみつかっているため 移動できない！

**区分**：未対応の主対象。ポケモンに見つかってマップ移動できない状態を判別する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![ポケモンにみつかっているため 移動できない！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/POKEMON_ZA_MOVE_COMMENT_BATTLE2.png)

**判定部分**：POKEMON_ZA_MOVE_COMMENT_BATTLE2 / 探索 [353, 587, 744, 665] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N021](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N021_frame.jpg)

![同じ保存画面の検知範囲 N021](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N021_roi.png)

ZIP保存画面の再照合一致 0.9943／閾値0.80。[1:29:14 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=5354s)。

**使用箇所**：[_2_story_tower_38:25231](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25231>) / [_2_story_tower_40:25282](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25282>) / [_4_story_shiro_32_0:30364](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:30364>)

### N022 戦闘しているので 移動できない！

**区分**：未対応の主対象。戦闘中のためマップ移動できない状態を判別し、戦闘復帰などへ分岐する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![戦闘しているので 移動できない！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/move_comment_battle.png)

**判定部分**：POKEMON_ZA_MOVE_COMMENT_BATTLE / 探索 [290, 550, 1000, 690] / 閾値 0.75 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_Common_goto_jump:36483](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36483>) / [ZA_Common_goto_jump:36490](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36490>) / [ZA_Common_battle_return:37195](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37195>) / [ZA_bench_goto_pokecenter1:37465](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37465>) / [ZA_bench_goto_pokecenter2:37512](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37512>)

### N023 目の前がまっくらになった！

**区分**：未対応の主対象。「目の前がまっくら」の敗北確認。フラダリラボの復帰と共通LOSEのOR候補に使う。MEGA再戦の選択順とは別。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![目の前がまっくらになった！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/furadari_eyes_dark_comment.png)

**判定部分**：POKEMON_ZA_FURADARI_EYES_DARK_COMMENT / 探索 [300, 590, 760, 690] / 閾値 0.85 / OR / POKEMON_ZA_LOSE / 探索 [300, 590, 760, 690] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N023](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N023_frame.jpg)

![同じ保存画面の検知範囲 N023](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N023_roi.png)

ZIP保存画面の再照合一致 0.9962／閾値0.85。[48:13 の動画](https://www.youtube.com/watch?v=l_MzEJK1KeM&t=2893s)。

**使用箇所**：[_ZA_furadari_eyes_dark_comment_visible:17501](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17501>) / [ZA_story_furadari_black_comment_recovery_step.eyes_dark_is_visible:17718](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17718>) / [_ZA_story_battle_debug_hold_for_defeat:20204](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20204>) / [_ZA_story_battle_debug_hold_for_defeat:20205](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20205>) / [_ZA_story_battle_debug_hold_for_defeat:20219](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20219>)

### N024 賞金メダルを半分わたして 降参しますか？

**区分**：未対応の主対象。降参する前の賞金メダルの説明を確認する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![賞金メダルを半分わたして 降参しますか？](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/escapecomment1.png)

**判定部分**：POKEMON_ZA_ESCAPE_COMMENT1 / 探索 [290, 550, 1000, 690] / 閾値 0.75 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_battle_move_test:38193](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38193>) / [ZA_battle_move_test:38804](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38804>) / [ZA_battle_move_test:38935](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38935>)

### N025 次は勝てるように ポケモンや使える技を確認しましょう

**区分**：未対応の主対象。降参後の案内を確認して処理を進める。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![次は勝てるように ポケモンや使える技を確認しましょう](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/escapecomment2.png)

**判定部分**：POKEMON_ZA_ESCAPE_COMMENT2 / 探索 [290, 550, 1000, 690] / 閾値 0.75 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_battle_move_test:38195](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38195>) / [ZA_battle_move_test:38806](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38806>) / [ZA_battle_move_test:38937](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38937>)

### N026 降参する／続ける

**区分**：未対応の主対象。降参する／続けるの選択を確認する。MEGA再挑戦の選択位置の対象ではない。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![降参する／続ける](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/escapecommentselect.png)

**判定部分**：POKEMON_ZA_ESCAPE_SELECT / 探索 [900, 400, 1200, 550] / 閾値 0.75 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_battle_move_test:38191](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38191>) / [ZA_battle_move_test:38802](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38802>) / [ZA_battle_move_test:38933](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38933>)

### N027 戦えるポケモンがいなくなった……

**区分**：未対応の主対象。戦えるポケモンがいなくなったことを確認する。もう1つの敗北文と同じLOSE判定のOR候補。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![戦えるポケモンがいなくなった……](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/lose.png)

**判定部分**：POKEMON_ZA_LOSE / 探索 [290, 550, 1000, 690] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_ZA_story_battle_debug_hold_for_defeat:20204](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20204>) / [_ZA_story_battle_debug_hold_for_defeat:20205](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20205>) / [_ZA_story_battle_debug_hold_for_defeat:20219](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20219>) / [_ZA_story_battle_debug_hold_for_defeat:20258](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20258>) / [_ZA_story_battle_debug_hold_for_defeat:20259](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20259>)

### N028 チャレンジチケットを手に入れたら

**区分**：未対応の主対象。クエーサー戦等の終了・チャレンジチケットの案内を識別する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![チャレンジチケットを手に入れたら](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/reword_end.png)

**判定部分**：POKEMON_ZA_REWORD_END / 探索 [200, 500, 1080, 720] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_mega_mode5_event_attack_blocked:7289](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7289>) / [ZA_battle_move_test:38380](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38380>) / [ZA_battle_move_test:38397](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38397>) / [ZA_battle_move_test:38416](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38416>) / [ZA_battle_move_test:38433](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38433>)

### N029 残念でしたね……

**区分**：未対応の主対象。報酬／敗北後の「残念でしたね」を識別する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![残念でしたね……](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/reword_lose.png)

**判定部分**：POKEMON_ZA_REWORD_LOSE / 探索 [200, 500, 1080, 720] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_mega_mode5_event_attack_blocked:7290](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7290>) / [ZA_battle_move_test:38387](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38387>) / [ZA_battle_move_test:38404](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38404>) / [ZA_battle_move_test:38423](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38423>) / [ZA_battle_move_test:38440](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38440>)

### N030 これで始める！

**区分**：未対応の主対象。ゲーム開始時の「これで始める！」の選択状態を確認する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![これで始める！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_0_Start/startbutton_select.png)

**判定部分**：POKEMON_ZA_STARTBTN_SELECT / 探索 [120, 520, 500, 610] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N030](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N030_frame.jpg)

![同じ保存画面の検知範囲 N030](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N030_roi.png)

ZIP保存画面の再照合一致 0.9926／閾値0.80。[0:00 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=0s)。

**使用箇所**：[main_0_start:22705](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22705>) / [main_0_start:22706](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22706>) / [main_0_start:22711](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22711>)

### N031 勝負をしかけてきた！

**区分**：未対応の主対象。初戦敗北後の「勝負をしかけてきた！」を確認して再開状態を判断する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![勝負をしかけてきた！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/farst_battle_retry_start.png)

**判定部分**：POKEMON_ZA_FARST_BATTLE_RETRY_START / 探索 [345, 640, 680, 700] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_ZA_story_battle_debug_hold_for_defeat:20225](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20225>) / [_ZA_story_battle_debug_hold_for_defeat:20226](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20226>) / [_1_story_farst_battle:23041](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23041>)

### N032 ポケモンの勉…／いつかは博士…（切り抜かれた会話片）

**区分**：未対応の主対象。序盤の白い会話片を見つけ、移動・イベント探索の処理を分岐する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![ポケモンの勉…／いつかは博士…（切り抜かれた会話片）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/out_hotel_z23_field_white_comment.png)

**判定部分**：POKEMON_ZA_OUT_HOTEL_Z23_FIELD_WHITE_COMMENT / 探索 [350, 100, 950, 350] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_markerdir:22213](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22213>)

### N033 ミアレシティだ！

**区分**：未対応の主対象。駅を出た直後の会話で序盤の進行位置を確認する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![ミアレシティだ！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/station_field.png)

**判定部分**：POKEMON_ZA_TEXT_TRAIN_OUT_COMMENT / 探索 [1020, 120, 1210, 190] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_1_story_start_check:22845](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22845>) / [_1_story_staition_out:22865](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22865>) / [_1_story_staition_out:22866](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22866>) / [_1_story_staition_out:22870](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22870>)

### N034 ん？ なんか騒ぎが…（会話片）

**区分**：未対応の主対象。駅前の騒ぎの会話を確認し、駅前移動・追跡の進行を判別する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![ん？ なんか騒ぎが…（会話片）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/station_leave_comment.png)

**判定部分**：POKEMON_ZA_TEXT_STATION_LEAVE_COMMENT / 探索 [950, 130, 1150, 230] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N034](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N034_frame.jpg)

![同じ保存画面の検知範囲 N034](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N034_roi.png)

ZIP保存画面の再照合一致 0.9783／閾値0.80。[3:52 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=232s)。

**使用箇所**：[_1_story_staition_front:22880](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22880>) / [_1_story_staition_front:22881](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22881>) / [_1_story_staition_front:22885](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22885>) / [_1_story_staition_leave_move:22895](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22895>) / [_1_story_staition_leave_move:22896](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22896>)

### N043 暴走メガシンカの依頼を 3件すべて解決する

**区分**：未対応の主対象。第3章で会議後／依頼3件解決の段階を、画面左上の目的文で確認する。

補足モードでも元の文字画像の判定を維持。代用は未実装。 FIELD表示と3秒安定の条件もあるが、目的文の区別を省いてはいない。

![暴走メガシンカの依頼を 3件すべて解決する](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/chapter3_mega2_post_meeting_task.png)

**判定部分**：POKEMON_ZA_MEGA2_POST_MEETING_TASK / 探索 [45, 65, 430, 150] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_ZA_story_mega2_phase_selector:29860](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:29860>)

### N044 エムゼット団の 作戦会議をはじめる

**区分**：未対応の主対象。第3章で会議前の段階を、画面左上の目的文で確認する。

補足モードでも元の文字画像の判定を維持。代用は未実装。 FIELD表示と3秒安定の条件もあるが、目的文の区別を省いてはいない。

![エムゼット団の 作戦会議をはじめる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/chapter3_mega2_pre_meeting_task.png)

**判定部分**：POKEMON_ZA_MEGA2_PRE_MEETING_TASK / 探索 [45, 65, 430, 150] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_ZA_story_mega2_phase_selector:29859](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:29859>)

### N045 朝側：バトルゾーン「終了」の文字片

**区分**：未対応の主対象。バトルゾーン終了時の「終了」の文字片で、朝側への時間変更を確認する。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![朝側：バトルゾーン「終了」の文字片](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/morning.png)

**判定部分**：POKEMON_ZA_MORNING / 探索 [540, 155, 740, 350] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N045](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N045_frame.jpg)

![同じ保存画面の検知範囲 N045](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N045_roi.png)

ZIP保存画面の再照合一致 0.9378／閾値0.85。[31:39 の動画](https://www.youtube.com/watch?v=mjX0QjBRpuA&t=1899s)。

**使用箇所**：[ZA_story_furadari_lab_entrance_goto:17583](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17583>) / [_ZA_story_event_entry_pending_recovery_step:19325](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:19325>) / [ZA_story_Template_battle_after:19959](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:19959>) / [_ZA_story_battle_after_safe_renda:21510](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21510>) / [ZA_story_Template_Comment_Out:21828](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21828>)

### N046 夜側：切替表示の漢字片

**区分**：未対応の主対象。夜側へ時間変更した時の大型表示の漢字片を確認する（ピンク背景）。

補足モードでも元の文字画像の判定を維持。代用は未実装。

![夜側：切替表示の漢字片](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/night.png)

**判定部分**：POKEMON_ZA_NIGHT / 探索 [430, 350, 850, 520] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_ZA_story_event_entry_pending_recovery_step:19326](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:19326>) / [ZA_story_Template_battle_after:19960](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:19960>) / [_ZA_story_battle_after_safe_renda:21511](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21511>) / [ZA_story_Template_Comment_Out:21829](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21829>) / [_1_story_farst_battle_lose:23120](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23120>)

### N047 10番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「10番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。 10・18番の番号詳細比較は実装済みだが、場所名ANDは残る。

![10番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE10_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE10 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N047](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N047_frame.jpg)

![同じ保存画面の検知範囲 N047](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N047_roi.png)

ZIP保存画面の再照合一致 0.9900／閾値0.90。[49:45 の動画](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2985s)。

**使用箇所**：[_2_story_mapping_117:28258](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28258>) / [_2_story_mapping_117:28259](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28259>) / [_2_story_mapping_117:28268](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28268>)

### N048 14番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「14番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。

![14番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE14_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE14 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N048](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N048_frame.jpg)

![同じ保存画面の検知範囲 N048](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N048_roi.png)

ZIP保存画面の再照合一致 0.9896／閾値0.90。[35:46 の動画](https://www.youtube.com/watch?v=u3_WGptNscg&t=2146s)。

**使用箇所**：[_5_story_mapping_4:31000](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:31000>) / [_5_story_mapping_4:31001](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:31001>) / [_5_story_mapping_4:31010](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:31010>)

### N049 15番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「15番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。

![15番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE15_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE15 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N049](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N049_frame.jpg)

![同じ保存画面の検知範囲 N049](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N049_roi.png)

ZIP保存画面の再照合一致 0.9895／閾値0.90。[36:15 の動画](https://www.youtube.com/watch?v=u3_WGptNscg&t=2175s)。

**使用箇所**：[_5_story_mapping_6:31041](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:31041>) / [_5_story_mapping_6:31042](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:31042>) / [_5_story_mapping_6:31055](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:31055>)

### N050 17番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「17番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。

![17番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE17_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE17 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N050](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N050_frame.jpg)

![同じ保存画面の検知範囲 N050](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N050_roi.png)

ZIP保存画面の再照合一致 0.9889／閾値0.90。[1:15:27 の動画](https://www.youtube.com/watch?v=DHVY6rsajPM&t=4527s)。

**使用箇所**：[_6_story_mapping_4:32559](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:32559>) / [_6_story_mapping_4:32560](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:32560>) / [_6_story_mapping_4:32569](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:32569>)

### N051 18番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「18番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。 10・18番の番号詳細比較は実装済みだが、場所名ANDは残る。

![18番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE18_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE18 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N051](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N051_frame.jpg)

![同じ保存画面の検知範囲 N051](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N051_roi.png)

ZIP保存画面の再照合一致 0.9893／閾値0.90。[1:35:30 の動画](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5730s)。

**使用箇所**：[_7_story_mapping_4:33395](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:33395>) / [_7_story_mapping_4:33396](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:33396>) / [_7_story_mapping_4:33405](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:33405>)

### N052 19番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「19番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。

![19番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE19_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE19 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N052](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N052_frame.jpg)

![同じ保存画面の検知範囲 N052](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N052_roi.png)

ZIP保存画面の再照合一致 0.9892／閾値0.90。[1:38:06 の動画](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5886s)。

**使用箇所**：[_7_story_mapping_8:33491](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:33491>) / [_7_story_mapping_8:33492](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:33492>) / [_7_story_mapping_8:33504](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:33504>)

### N053 2番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「2番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。

![2番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE2_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE2 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N053](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N053_frame.jpg)

![同じ保存画面の検知範囲 N053](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N053_roi.png)

ZIP保存画面の再照合一致 0.9889／閾値0.90。[1:53:47 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6827s)。

**使用箇所**：[_2_story_mapping_39:26017](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26017>) / [_2_story_mapping_39:26018](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26018>) / [_2_story_mapping_39:26027](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26027>)

### N054 4番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「4番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。

![4番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE4_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE4 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N054](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N054_frame.jpg)

![同じ保存画面の検知範囲 N054](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N054_roi.png)

ZIP保存画面の再照合一致 0.9430／閾値0.90。[1:40:25 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6025s)。

**使用箇所**：[_2_story_mapping_3:25365](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25365>) / [_2_story_mapping_3:25366](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25366>) / [_2_story_mapping_3:25375](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25375>)

### N055 5番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「5番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。

![5番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE5_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE5 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N055](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N055_frame.jpg)

![同じ保存画面の検知範囲 N055](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N055_roi.png)

ZIP保存画面の再照合一致 0.9889／閾値0.90。[1:54:33 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6873s)。

**使用箇所**：[_2_story_mapping_42:26077](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26077>) / [_2_story_mapping_42:26078](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26078>) / [_2_story_mapping_42:26087](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26087>)

### N056 6番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「6番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。

![6番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE6_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE6 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N056](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N056_frame.jpg)

![同じ保存画面の検知範囲 N056](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N056_roi.png)

ZIP保存画面の再照合一致 0.9892／閾値0.90。[1:55:42 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6942s)。

**使用箇所**：[_2_story_mapping_45:26131](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26131>) / [_2_story_mapping_45:26132](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26132>) / [_2_story_mapping_45:26141](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26141>)

### N057 8番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「8番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。 前回の最高点候補は「18番」の途中から「8番」に一致した画像。8番選択の証拠には採用しない。単独の場所名検知と移動先の成立は区別する。

![8番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE8_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE8 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_2_story_mapping_113:28132](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28132>) / [_2_story_mapping_113:28133](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28133>) / [_2_story_mapping_113:28142](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28142>)

### N058 9番ワイルドゾーン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「9番ワイルドゾーン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。 PICにもWILD ZONEと番号が含まれる。

![9番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE9_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE9 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N058](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N058_frame.jpg)

![同じ保存画面の検知範囲 N058](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N058_roi.png)

ZIP保存画面の再照合一致 0.9888／閾値0.90。[48:48 の動画](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2928s)。

**使用箇所**：[_2_story_mapping_115:28195](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28195>) / [_2_story_mapping_115:28196](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28196>) / [_2_story_mapping_115:28205](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28205>)

### N059 ミアレ美術館

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ミアレ美術館」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ミアレ美術館](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/art_museum_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_ART_MUSEUM / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N059](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N059_frame.jpg)

![同じ保存画面の検知範囲 N059](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N059_roi.png)

ZIP保存画面の再照合一致 0.9876／閾値0.90。[7:31 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=451s)。

**使用箇所**：[_2_story_mapping_81:26792](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26792>) / [_2_story_mapping_81:26793](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26793>) / [_2_story_mapping_81:26802](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26802>)

### N060 ブルー広場

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ブルー広場」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ブルー広場](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/bule_square_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_BLUE_SQUARE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N060](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N060_frame.jpg)

![同じ保存画面の検知範囲 N060](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N060_roi.png)

ZIP保存画面の再照合一致 0.9879／閾値0.90。[1:59:31 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=7171s)。

**使用箇所**：[_2_story_mapping_60:26405](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26405>) / [_2_story_mapping_60:26406](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26406>) / [_2_story_mapping_60:26415](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26415>) / [_2_story_mapping_63:26462](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26462>)

### N061 カフェ・アラモード

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・アラモード」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・アラモード](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_alamode_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_ALAMODE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N061](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N061_frame.jpg)

![同じ保存画面の検知範囲 N061](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N061_roi.png)

ZIP保存画面の再照合一致 0.9910／閾値0.90。[1:56:21 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6981s)。

**使用箇所**：[_2_story_mapping_48:26179](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26179>) / [_2_story_mapping_48:26180](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26180>) / [_2_story_mapping_48:26189](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26189>)

### N062 カフェ・バタイユ

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・バタイユ」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・バタイユ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_bataille_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_BATAILLE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N062](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N062_frame.jpg)

![同じ保存画面の検知範囲 N062](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N062_roi.png)

ZIP保存画面の再照合一致 0.9902／閾値0.90。[11:12 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=672s)。

**使用箇所**：[_2_story_mapping_94:27010](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27010>) / [_2_story_mapping_94:27011](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27011>) / [_2_story_mapping_94:27020](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27020>)

### N063 カフェ・カンコドール

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・カンコドール」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・カンコドール](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_cancodor_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_CANCODOR / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N063](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N063_frame.jpg)

![同じ保存画面の検知範囲 N063](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N063_roi.png)

ZIP保存画面の再照合一致 0.9913／閾値0.90。[4:22 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=262s)。

**使用箇所**：[_2_story_mapping_75:26672](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26672>) / [_2_story_mapping_75:26673](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26673>) / [_2_story_mapping_75:26682](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26682>)

### N064 カフェ・かわいがり

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・かわいがり」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・かわいがり](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_cute_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_CUTE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N064](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N064_frame.jpg)

![同じ保存画面の検知範囲 N064](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N064_roi.png)

ZIP保存画面の再照合一致 0.9902／閾値0.90。[17:29 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=1049s)。

**使用箇所**：[_2_story_mapping_109:27296](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27296>) / [_2_story_mapping_109:27297](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27297>) / [_2_story_mapping_109:27306](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27306>)

### N065 カフェ・フォーカス

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・フォーカス」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・フォーカス](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_focus_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_FOCUS / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N065](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N065_frame.jpg)

![同じ保存画面の検知範囲 N065](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N065_roi.png)

ZIP保存画面の再照合一致 0.9699／閾値0.90。[1:37 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=97s)。

**使用箇所**：[_2_story_mapping_66:26520](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26520>) / [_2_story_mapping_66:26521](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26521>) / [_2_story_mapping_66:26530](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26530>)

### N066 カフェ・おとこまえ

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・おとこまえ」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・おとこまえ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_man_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_MAN / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N066](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N066_frame.jpg)

![同じ保存画面の検知範囲 N066](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N066_roi.png)

ZIP保存画面の再照合一致 0.9905／閾値0.90。[1:43:16 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6196s)。

**使用箇所**：[_2_story_mapping_12:25520](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25520>) / [_2_story_mapping_12:25521](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25521>) / [_2_story_mapping_12:25530](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25530>)

### N067 ヌーヴォカフェ2号店

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ヌーヴォカフェ2号店」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ヌーヴォカフェ2号店](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_nuvo2_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_NUVO2 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N067](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N067_frame.jpg)

![同じ保存画面の検知範囲 N067](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N067_roi.png)

ZIP保存画面の再照合一致 0.9886／閾値0.90。[1:58:55 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=7135s)。

**使用箇所**：[_2_story_mapping_57:26356](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26356>) / [_2_story_mapping_57:26357](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26357>) / [_2_story_mapping_57:26366](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26366>)

### N068 ヌーヴォカフェ3号店

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ヌーヴォカフェ3号店」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ヌーヴォカフェ3号店](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_nuvo3_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_NUVO3 / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N068](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N068_frame.jpg)

![同じ保存画面の検知範囲 N068](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N068_roi.png)

ZIP保存画面の再照合一致 0.9884／閾値0.90。[3:16 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=196s)。

**使用箇所**：[_2_story_mapping_72:26622](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26622>) / [_2_story_mapping_72:26623](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26623>) / [_2_story_mapping_72:26632](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26632>)

### N069 カフェ・パルトネール

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・パルトネール」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・パルトネール](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_partenaire_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_PARTENAIRE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N069](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N069_frame.jpg)

![同じ保存画面の検知範囲 N069](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N069_roi.png)

ZIP保存画面の再照合一致 0.9904／閾値0.90。[9:48 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=588s)。

**使用箇所**：[_2_story_mapping_90:26947](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26947>) / [_2_story_mapping_90:26948](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26948>) / [_2_story_mapping_90:26957](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26957>)

### N070 カフェ・リテイク

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・リテイク」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・リテイク](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_retake_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_RETAKE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N070](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N070_frame.jpg)

![同じ保存画面の検知範囲 N070](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N070_roi.png)

ZIP保存画面の再照合一致 0.9905／閾値0.90。[1:52:12 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6732s)。

**使用箇所**：[_2_story_mapping_33:25908](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25908>) / [_2_story_mapping_33:25909](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25909>) / [_2_story_mapping_33:25918](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25918>)

### N071 カフェ・スラローム

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・スラローム」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・スラローム](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_slalom_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_SLALOM / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N071](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N071_frame.jpg)

![同じ保存画面の検知範囲 N071](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N071_roi.png)

ZIP保存画面の再照合一致 0.9902／閾値0.90。[2:28 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=148s)。

**使用箇所**：[_2_story_mapping_69:26573](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26573>) / [_2_story_mapping_69:26574](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26574>) / [_2_story_mapping_69:26583](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26583>)

### N072 カフェ・ソレイユ

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・ソレイユ」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・ソレイユ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_soleil_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_SOLEIL / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N072](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N072_frame.jpg)

![同じ保存画面の検知範囲 N072](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N072_roi.png)

ZIP保存画面の再照合一致 0.9910／閾値0.90。[0:27 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=27s)。

**使用箇所**：[_2_story_mapping_63:26461](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26461>) / [_2_story_mapping_63:26471](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26471>)

### N073 カフェ・トウトウ

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・トウトウ」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・トウトウ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_toto_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_TOTO / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N073](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N073_frame.jpg)

![同じ保存画面の検知範囲 N073](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N073_roi.png)

ZIP保存画面の再照合一致 0.9906／閾値0.90。[1:57:04 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=7024s)。

**使用箇所**：[_2_story_mapping_51:26227](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26227>) / [_2_story_mapping_51:26228](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26228>) / [_2_story_mapping_51:26237](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26237>)

### N074 カフェ・ツイスター

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・ツイスター」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・ツイスター](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_twister_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_TWISTER / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N074](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N074_frame.jpg)

![同じ保存画面の検知範囲 N074](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N074_roi.png)

ZIP保存画面の再照合一致 0.9918／閾値0.90。[9:15 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=555s)。

**使用箇所**：[_2_story_mapping_54:26290](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26290>) / [_2_story_mapping_54:26291](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26291>) / [_2_story_mapping_54:26300](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26300>)

### N075 カフェ・アルティメット

**区分**：マップの場所名条件が残る。マップ一覧の場所名「カフェ・アルティメット」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![カフェ・アルティメット](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_ult_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_CAFE_ULT / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N075](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N075_frame.jpg)

![同じ保存画面の検知範囲 N075](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N075_roi.png)

ZIP保存画面の再照合一致 0.9907／閾値0.90。[9:03 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=543s)。

**使用箇所**：[_2_story_mapping_87:26896](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26896>) / [_2_story_mapping_87:26897](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26897>) / [_2_story_mapping_87:26906](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26906>)

### N076 ホテル シュールリッシュ

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ホテル シュールリッシュ」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ホテル シュールリッシュ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/hotel_surrealish_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_HOTEL_SURREALISH / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N076](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N076_frame.jpg)

![同じ保存画面の検知範囲 N076](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N076_roi.png)

ZIP保存画面の再照合一致 0.9901／閾値0.90。[8:28 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=508s)。

**使用箇所**：[_2_story_mapping_84:26844](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26844>) / [_2_story_mapping_84:26845](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26845>) / [_2_story_mapping_84:26854](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26854>)

### N077 ジャスティスの会道場

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ジャスティスの会道場」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ジャスティスの会道場](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/justice_dojo_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_JUSTICE_DOJO / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N077](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N077_frame.jpg)

![同じ保存画面の検知範囲 N077](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N077_roi.png)

ZIP保存画面の再照合一致 0.9889／閾値0.90。[15:04 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=904s)。

**使用箇所**：[_2_story_mapping_103:27188](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27188>) / [_2_story_mapping_103:27189](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27189>) / [_2_story_mapping_103:27198](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27198>)

### N078 ポケモンセンター：ブルー

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ポケモンセンター：ブルー」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ポケモンセンター：ブルー](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_blue_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_BLUE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N078](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N078_frame.jpg)

![同じ保存画面の検知範囲 N078](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N078_roi.png)

ZIP保存画面の再照合一致 0.9908／閾値0.90。[1:05:18 の動画](https://www.youtube.com/watch?v=RKTDE46FHBM&t=3918s)。

**使用箇所**：[_2_story_mapping_27:25796](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25796>) / [_2_story_mapping_27:25797](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25797>) / [_2_story_mapping_27:25806](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25806>)

### N079 ポケモンセンター：イベール

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ポケモンセンター：イベール」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ポケモンセンター：イベール](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_evel_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_EVEL / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N079](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N079_frame.jpg)

![同じ保存画面の検知範囲 N079](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N079_roi.png)

ZIP保存画面の再照合一致 0.9904／閾値0.90。[10:03 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=603s)。

**使用箇所**：[_2_story_mapping_30:25851](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25851>) / [_2_story_mapping_30:25852](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25852>) / [_2_story_mapping_30:25861](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25861>)

### N080 ポケモンセンター：ジョーヌ

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ポケモンセンター：ジョーヌ」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ポケモンセンター：ジョーヌ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_jone_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_JONE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N080](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N080_frame.jpg)

![同じ保存画面の検知範囲 N080](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N080_roi.png)

ZIP保存画面の再照合一致 0.9889／閾値0.90。[1:18:19 の動画](https://www.youtube.com/watch?v=fApUB0nJ5Fc&t=4699s)。

**使用箇所**：[_2_story_mapping_36:25961](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25961>) / [_2_story_mapping_36:25962](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25962>) / [_2_story_mapping_36:25971](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25971>)

### N081 ポケモンセンター：プランタン

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ポケモンセンター：プランタン」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ポケモンセンター：プランタン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_prantan_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_PRANTAN / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N081](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N081_frame.jpg)

![同じ保存画面の検知範囲 N081](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N081_roi.png)

ZIP保存画面の再照合一致 0.9905／閾値0.90。[1:47:16 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6436s)。

**使用箇所**：[_2_story_mapping_24:25725](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25725>) / [_2_story_mapping_24:25726](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25726>) / [_2_story_mapping_24:25735](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25735>)

### N082 ポケモンセンター：ローズ広場

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ポケモンセンター：ローズ広場」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ポケモンセンター：ローズ広場](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_rose_square_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_ROSE_S / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N082](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N082_frame.jpg)

![同じ保存画面の検知範囲 N082](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N082_roi.png)

ZIP保存画面の再照合一致 0.9898／閾値0.90。[1:44:26 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6266s)。

**使用箇所**：[_2_story_mapping_18:25621](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25621>) / [_2_story_mapping_18:25622](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25622>) / [_2_story_mapping_18:25631](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25631>)

### N083 ポケモンセンター：ローズ

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ポケモンセンター：ローズ」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ポケモンセンター：ローズ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_rose_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_ROSE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N083](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N083_frame.jpg)

![同じ保存画面の検知範囲 N083](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N083_roi.png)

ZIP保存画面の再照合一致 0.9902／閾値0.90。[1:45:57 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6357s)。

**使用箇所**：[_2_story_mapping_21:25674](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25674>) / [_2_story_mapping_21:25675](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25675>) / [_2_story_mapping_21:25684](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25684>)

### N084 ポケモンセンター：ルージュ

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ポケモンセンター：ルージュ」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ポケモンセンター：ルージュ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_rudu_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_RUDU / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N084](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N084_frame.jpg)

![同じ保存画面の検知範囲 N084](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N084_roi.png)

ZIP保存画面の再照合一致 0.9899／閾値0.90。[1:41:03 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6063s)。

**使用箇所**：[_2_story_mapping_6:25416](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25416>) / [_2_story_mapping_6:25417](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25417>) / [_2_story_mapping_6:25426](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25426>)

### N085 ラシーヌ工務店

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ラシーヌ工務店」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ラシーヌ工務店](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/racine_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_RACINE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N085](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N085_frame.jpg)

![同じ保存画面の検知範囲 N085](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N085_roi.png)

ZIP保存画面の再照合一致 0.9897／閾値0.90。[12:21 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=741s)。

**使用箇所**：[_2_story_mapping_97:27064](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27064>) / [_2_story_mapping_97:27065](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27065>) / [_2_story_mapping_97:27074](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27074>)

### N086 リストランテ ニ・リュー

**区分**：マップの場所名条件が残る。マップ一覧の場所名「リストランテ ニ・リュー」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![リストランテ ニ・リュー](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_2ryu_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_2RYU / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N086](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N086_frame.jpg)

![同じ保存画面の検知範囲 N086](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N086_roi.png)

ZIP保存画面の再照合一致 0.9898／閾値0.90。[6:10 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=370s)。

**使用箇所**：[_2_story_mapping_78:26726](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26726>) / [_2_story_mapping_78:26727](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26727>) / [_2_story_mapping_78:26736](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26736>)

### N087 レストラン・ド・フツー

**区分**：マップの場所名条件が残る。マップ一覧の場所名「レストラン・ド・フツー」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![レストラン・ド・フツー](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_dohutsu_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_DOHUTSU / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N087](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N087_frame.jpg)

![同じ保存画面の検知範囲 N087](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N087_roi.png)

ZIP保存画面の再照合一致 0.9908／閾値0.90。[13:25 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=805s)。

**使用箇所**：[_2_story_mapping_100:27124](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27124>) / [_2_story_mapping_100:27125](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27125>) / [_2_story_mapping_100:27134](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27134>)

### N088 レストラン ローリングドリーマー

**区分**：マップの場所名条件が残る。マップ一覧の場所名「レストラン ローリングドリーマー」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![レストラン ローリングドリーマー](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_dream_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_DREAM / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N088](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N088_frame.jpg)

![同じ保存画面の検知範囲 N088](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N088_roi.png)

ZIP保存画面の再照合一致 0.9912／閾値0.90。[49:45 の動画](https://www.youtube.com/watch?v=RKTDE46FHBM&t=2985s)。

**使用箇所**：[_2_story_mapping_9:25468](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25468>) / [_2_story_mapping_9:25469](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25469>) / [_2_story_mapping_9:25478](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25478>)

### N089 レストラン・ド・キワミ

**区分**：マップの場所名条件が残る。マップ一覧の場所名「レストラン・ド・キワミ」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![レストラン・ド・キワミ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_exterme_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_EXTREAME / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N089](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N089_frame.jpg)

![同じ保存画面の検知範囲 N089](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N089_roi.png)

ZIP保存画面の再照合一致 0.9900／閾値0.90。[16:34 の動画](https://www.youtube.com/watch?v=BLM81UP9V5I&t=994s)。

**使用箇所**：[_2_story_mapping_106:27248](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27248>) / [_2_story_mapping_106:27249](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27249>) / [_2_story_mapping_106:27258](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27258>)

### N090 ローズ広場

**区分**：マップの場所名条件が残る。マップ一覧の場所名「ローズ広場」と、右側の場所画像を両方確認する。

場所名 AND PICのまま。補足モードで日本語名を省く分岐は未実装。

![ローズ広場](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/rose_square_target.png)

**判定部分**：POKEMON_ZA_MOVEPOINT_TARGET_ROSE_SQUARE / 探索 [0, 100, 450, 600] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N090](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N090_frame.jpg)

![同じ保存画面の検知範囲 N090](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N090_roi.png)

ZIP保存画面の再照合一致 0.9864／閾値0.90。[1:43:59 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6239s)。

**使用箇所**：[_2_story_mapping_15:25570](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25570>) / [_2_story_mapping_15:25571](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25571>) / [_2_story_mapping_15:25580](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25580>)

### N001 再挑戦する／アドバイス

**区分**：MEGA以外の再挑戦が残る。MEGA再戦では順番・行数・再開HPで代用するが、初戦の再挑戦の別処理にも同じ画像が残る。

_1_story_farst_battle／_1_story_farst_battle_loseはnative再戦ハンドラーへ委譲していない。

![再挑戦する／アドバイス](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/2_select_tutorial.png)

**判定部分**：POKEMON_ZA_2_SELECT_TUTORIAL / 探索 [920, 400, 1180, 550] / 閾値 0.75 / OR

**収集**：再戦関連の同名画像として収集除外。初戦側で未対応でも保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_1_story_farst_battle:23038](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23038>) / [_1_story_farst_battle_lose.retry_choice_visible:23092](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23092>)

### N003 再挑戦する／準備して再挑戦／あきらめる

**区分**：MEGA以外の再挑戦が残る。MEGA再戦では順番・行数・再開HPで代用するが、初戦の再挑戦の別処理にも同じ画像が残る。

_1_story_farst_battle／_1_story_farst_battle_loseはnative再戦ハンドラーへ委譲していない。 保存候補の表示は「再挑戦する／HPひきつぎ／アドバイス」で参照画像の下2行と異なるため、一致の証拠には採用しない。

![再挑戦する／準備して再挑戦／あきらめる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/3_select_tutorial.png)

**判定部分**：POKEMON_ZA_3_SELECT_TUTORIAL / 探索 [900, 320, 1200, 580] / 閾値 0.75 / OR

**収集**：再戦関連の同名画像として収集除外。初戦側で未対応でも保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_1_story_farst_battle:23039](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23039>) / [_1_story_farst_battle_lose.retry_choice_visible:23093](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23093>)

### N091 C+

**区分**：英字・略字の他言語確認。攻撃できるC+表示を確認する。低閾値版も同じ字形を使う。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![C+](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/C+.png)

**判定部分**：POKEMON_ZA_C+ / 探索 [1000, 565, 1280, 720] / 閾値 0.75 / OR / POKEMON_ZA_C+_LOW / 探索 [1000, 565, 1280, 720] / 閾値 0.6 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N091](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N091_frame.jpg)

![同じ保存画面の検知範囲 N091](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N091_roi.png)

ZIP保存画面の再照合一致 0.9611／閾値0.75。[49:44 の動画](https://www.youtube.com/watch?v=XLLw1yJGVCg&t=2984s)。

**使用箇所**：[ZA_mega_mode5_skill_attack_ready:11534](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:11534>) / [ZA_mega_mode5_skill_attack_ready:11535](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:11535>) / [ZA_mega_attack_ready:11557](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:11557>) / [ZA_mega_attack_ready:11558](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:11558>) / [ZA_mega_evolution_battle:15875](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:15875>)

### N092 C+

**区分**：英字・略字の他言語確認。C+の別色。N091とのOR候補であり、非文字の代用ではない。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![C+](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/C+_white.png)

**判定部分**：POKEMON_ZA_C+ / 探索 [1000, 565, 1280, 720] / 閾値 0.75 / OR / POKEMON_ZA_C+_LOW / 探索 [1000, 565, 1280, 720] / 閾値 0.6 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_mega_mode5_skill_attack_ready:11534](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:11534>) / [ZA_mega_mode5_skill_attack_ready:11535](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:11535>) / [ZA_mega_attack_ready:11557](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:11557>) / [ZA_mega_attack_ready:11558](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:11558>) / [ZA_mega_evolution_battle:15875](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:15875>)

### N093 MISSION COMPLETEの文字片 C

**区分**：英字・略字の他言語確認。MISSION COMPLETEの4文字片中3片以上の一致で完了を確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![MISSION COMPLETEの文字片 C](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_C.png)

**判定部分**：POKEMON_ZA_MISSION_COMPLETE / 探索 [416, 179, 476, 243] / 閾値 0.5 / AT_LEAST_3

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_story_Template_battle_before_active_level:20525](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20525>) / [ZA_story_Template_battle_function_active_level:20926](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20926>) / [ZA_story_Template_battle_after_active_level:21072](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21072>) / [_ZA_story_battle_before_safe_renda_once:21174](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21174>) / [_ZA_story_battle_before_safe_renda_once:21175](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21175>)

### N094 MISSION COMPLETEの文字片 M

**区分**：英字・略字の他言語確認。N093・N095・N096と同じ完了判定の文字片。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![MISSION COMPLETEの文字片 M](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_M.png)

**判定部分**：POKEMON_ZA_MISSION_COMPLETE / 探索 [522, 179, 595, 243] / 閾値 0.5 / AT_LEAST_3

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_story_Template_battle_before_active_level:20525](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20525>) / [ZA_story_Template_battle_function_active_level:20926](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20926>) / [ZA_story_Template_battle_after_active_level:21072](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21072>) / [_ZA_story_battle_before_safe_renda_once:21174](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21174>) / [_ZA_story_battle_before_safe_renda_once:21175](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21175>)

### N095 MISSION COMPLETEの文字片 P

**区分**：英字・略字の他言語確認。N093・N094・N096と同じ完了判定の文字片。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![MISSION COMPLETEの文字片 P](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_P.png)

**判定部分**：POKEMON_ZA_MISSION_COMPLETE / 探索 [589, 179, 650, 243] / 閾値 0.5 / AT_LEAST_3

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_story_Template_battle_before_active_level:20525](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20525>) / [ZA_story_Template_battle_function_active_level:20926](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20926>) / [ZA_story_Template_battle_after_active_level:21072](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21072>) / [_ZA_story_battle_before_safe_renda_once:21174](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21174>) / [_ZA_story_battle_before_safe_renda_once:21175](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21175>)

### N096 MISSION COMPLETEの文字片 T

**区分**：英字・略字の他言語確認。N093〜N095と同じ完了判定の文字片。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![MISSION COMPLETEの文字片 T](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_T.png)

**判定部分**：POKEMON_ZA_MISSION_COMPLETE / 探索 [746, 179, 809, 243] / 閾値 0.5 / AT_LEAST_3

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_story_Template_battle_before_active_level:20525](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20525>) / [ZA_story_Template_battle_function_active_level:20926](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20926>) / [ZA_story_Template_battle_after_active_level:21072](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21072>) / [_ZA_story_battle_before_safe_renda_once:21174](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21174>) / [_ZA_story_battle_before_safe_renda_once:21175](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21175>)

### N097 SELECTの先頭S

**区分**：英字・略字の他言語確認。画面左下のSELECTの文字片で選択画面を確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![SELECTの先頭S](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/SELECT.png)

**判定部分**：POKEMON_ZA_SELECT / 探索 [80, 640, 135, 695] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_battle_coCp_noloop:16888](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:16888>) / [ZA_battle_Cp_loop:17009](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17009>) / [ZA_battle_Cp_loop_move:17139](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17139>) / [ZA_bench_map_open:37428](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37428>) / [ZA_infi_guarded_ladder_climb:37957](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:37957>)

### N098 REWARD

**区分**：英字・略字の他言語確認。報酬画面のREWARD見出しを確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![REWARD](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/X_menu/POKEMON_ZA_REWORD.png)

**判定部分**：POKEMON_ZA_REWORD / 探索 [366, 40, 560, 74] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_mega_mode5_event_attack_blocked:7288](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7288>) / [ZA_battle_reword_recovery:16750](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:16750>)

### N099 MENU

**区分**：英字・略字の他言語確認。Xメニューが開いていることをMENUの文字で確認する。内部の選択位置を代用しても、この入口判定は残る。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![MENU](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/X_menu/x_menu_window.png)

**判定部分**：POKEMON_ZA_X_MENU_OPEN / 探索 [50, 50, 450, 120] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N099](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N099_frame.jpg)

![同じ保存画面の検知範囲 N099](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N099_roi.png)

ZIP保存画面の再照合一致 0.9853／閾値0.85。[39:32 の動画](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2372s)。

**使用箇所**：[_ZA_gamereset_game_screen:5856](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:5856>) / [_ZA_gamereset_game_screen:5870](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:5870>) / [_ZA_story_shiro_80_reset_debug_ready:5878](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:5878>) / [ZA_mega_mode5_event_attack_blocked:7287](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7287>) / [ZA_mega_mode5_x_menu_b_recovery:9906](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:9906>)

### N100 Lv

**区分**：英字・略字の他言語確認。共通戦闘処理でLv表示を確認する。ボス名の代用は、この登録の全使用箇所を置換していない。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![Lv](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/battle_active_level.png)

**判定部分**：POKEMON_ZA_BATTLE_ACTIVE_LEVEL / 探索 [120, 500, 300, 580] / 閾値 0.75 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N100](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N100_frame.jpg)

![同じ保存画面の検知範囲 N100](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N100_roi.png)

ZIP保存画面の再照合一致 0.9710／閾値0.75。[1:45:48 の動画](https://www.youtube.com/watch?v=ugB3vep1qMI&t=6348s)。

**使用箇所**：[_ZA_gamereset_game_screen:5871](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:5871>) / [ZA_mega_mode5_defeat_ui_clear:9784](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:9784>) / [ZA_mega_mode5_indefinite_field_wait_update:10131](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:10131>) / [ZA_mega_retry_menu_step.ui_clear:11211](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:11211>) / [ZA_mega_normal_choice_black_background_state:11313](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:11313>)

### N101 BOX

**区分**：英字・略字の他言語確認。BOX画面の見出しを確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![BOX](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/boxwindow.png)

**判定部分**：POKEMON_ZA_BOX_WINDOW / 探索 [160, 10, 290, 60] / 閾値 0.88 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N101](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N101_frame.jpg)

![同じ保存画面の検知範囲 N101](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N101_roi.png)

ZIP保存画面の再照合一致 0.9778／閾値0.88。[38:59 の動画](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2339s)。

**使用箇所**：[_2_story_absol_move4:28041](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28041>) / [ZA_common_box_change_box_target1:35846](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:35846>) / [ZA_common_box_change_box_target1_select:35871](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:35871>) / [ZA_common_box_change_box_target2:35885](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:35885>) / [ZA_common_box_change_window_close:35910](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:35910>)

### N102 FIN

**区分**：英字・略字の他言語確認。FIN表示を確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![FIN](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/fin.png)

**判定部分**：POKEMON_ZA_FIN / 探索 [1000, 565, 1280, 720] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_8_story_story_last_51:35360](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:35360>)

### N103 ITEM

**区分**：英字・略字の他言語確認。道具画面のITEM見出しを確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![ITEM](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/itemwindow.png)

**判定部分**：POKEMON_ZA_ITEM_WINDOW / 探索 [80, 30, 230, 65] / 閾値 0.88 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_6_story_yukari_47:32975](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:32975>) / [_6_story_yukari_48:32988](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:32988>) / [_6_story_yukari_49:33039](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:33039>) / [_8_story_story_last_49:35312](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:35312>) / [_8_story_story_last_50:35326](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:35326>)

### N104 MAP

**区分**：英字・略字の他言語確認。地図をMAPの文字で確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![MAP](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/map2.png)

**判定部分**：POKEMON_ZA_MAP / 探索 [20, 0, 200, 70] / 閾値 0.85 / OR / POKEMON_ZA_MAP2 / 探索 [20, 0, 200, 70] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_story_furadari_lab_entrance_goto:17548](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17548>) / [ZA_story_furadari_lab_entrance_goto:17666](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:17666>) / [ZA_story_furadari_black_comment_recovery_step:18263](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:18263>) / [_1_story_third_battle_end:23381](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23381>) / [_1_story_out_hotel_z_54:24541](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:24541>)

### N105 Z-A ROYALE

**区分**：英字・略字の他言語確認。Z-A ROYALEの画面見出しを確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![Z-A ROYALE](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/z-a_royale.png)

**判定部分**：POKEMON_ZA_ZA_ROYALE / 探索 [20, 40, 380, 80] / 閾値 0.88 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_story_Template_Comment_Out:21821](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21821>) / [ZA_story_Template_Comment_Out:21926](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21926>) / [_2_story_mega_move23:29069](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:29069>) / [_2_story_mega_move23:29070](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:29070>) / [ZA_common_evolution_exec:36077](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36077>)

### N106 REWARD

**区分**：英字・略字の他言語確認。別範囲のREWARD文字を確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![REWARD](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/REWARD.png)

**判定部分**：POKEMON_ZA_REWARD_RESULT / 探索 [930, 45, 1030, 60] / 閾値 0.75 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_battle_move_test:38668](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38668>) / [ZA_battle_lockon_test:39093](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:39093>)

### N107 Rボタンの一部

**区分**：英字・略字の他言語確認。Rボタンの表示の一部を確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![Rボタンの一部](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/R_push.png)

**判定部分**：POKEMON_ZA_R_push / 探索 [1000, 565, 1280, 720] / 閾値 0.75 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N107](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N107_frame.jpg)

![同じ保存画面の検知範囲 N107](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N107_roi.png)

ZIP保存画面の再照合一致 0.9302／閾値0.75。[1:04:16 の動画](https://www.youtube.com/watch?v=mjX0QjBRpuA&t=3856s)。

**使用箇所**：[ZA_mega_mode5_event_lockon_bootstrap:7523](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7523>) / [ZA_mega_mode5_event_attack_axby:7625](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:7625>) / [ZA_mega_mode5_rpush_prompt_confirmed:9791](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:9791>) / [ZA_mega_evolution_battle:15362](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:15362>) / [ZA_mega_evolution_battle:15580](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:15580>)

### N108 MAX

**区分**：英字・略字の他言語確認。チケット数のMAX表示を確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![MAX](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/chicket_95_118x1122_1268.png)

**判定部分**：POKEMON_ZA_CHICKET_MAX_RIGHT / 探索 [1122, 95, 1268, 118] / 閾値 0.75 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_battle_move_test:38451](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38451>) / [ZA_battle_move_test:38679](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38679>)

### N109 MAX

**区分**：英字・略字の他言語確認。別範囲のMAX表示を確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![MAX](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/chicket_max.png)

**判定部分**：POKEMON_ZA_CHICKET_MAX / 探索 [700, 600, 1000, 720] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_battle_move_test:38679](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38679>) / [ZA_battle_move_test:38680](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:38680>)

### N110 PROFILE

**区分**：英字・略字の他言語確認。PROFILE画面の見出しを確認する。

非文字への置換は未実装。対象言語でも字形・配置が共通なら画像変更が不要な可能性がある。未検証。

![PROFILE](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_0_Start/Profile.png)

**判定部分**：POKEMON_ZA_PROFILE / 探索 [60, 40, 260, 70] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

![前回保存画面 N110](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N110_frame.jpg)

![同じ保存画面の検知範囲 N110](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_evidence/N110_roi.png)

ZIP保存画面の再照合一致 0.9776／閾値0.80。[0:00 の動画](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=0s)。

**使用箇所**：[main_0_start:22703](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22703>) / [main_0_start:22704](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22704>) / [main_0_start:22710](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:22710>)

### N112 そのまま見守る／やめる

**区分**：既存の別経路あり・要確認。進化確認。非文字2_SELECTとのOR経路はあるが、専用画面との形状差の確認が残る。

2_SELECTとのOR・形状差あり。進化確認はEVOLUTION_CONFIRM／X_MENU_EVO_MENU／2_SELECTのOR。2_SELECTは非文字の枠だが、専用画面との形状差がソースに明記されており、代用の実機確認が必要。

![そのまま見守る／やめる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/evolution_2_select.png)

**判定部分**：POKEMON_ZA_EVOLUTION_CONFIRM / 探索 [880, 380, 1220, 580] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[ZA_common_evolution_exec.evolution_confirm_visible:36029](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36029>)

### N113 やったな！

**区分**：既存の別経路あり・要確認。捕獲2匹の会話終了。手持ちのヤヤコマ＋ホルビーのアイコンで進める別経路がある。

捕獲アイコンで進行可能。OUT_HOTEL_Z_16はヤヤコマ＋ホルビーの手持ちアイコンで次Stepへ進む。「やったな！」不一致時も同じ会話終了処理がある。

![やったな！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/2get_success.png)

**判定部分**：POKEMON_ZA_TEXT_2_GET_SUCCESS / 探索 [300, 555, 1000, 700] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_1_story_out_hotel_z_16:23542](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23542>)

### N114 ZL：狙う／X・A：技を指示

**区分**：既存の別経路あり・要確認。初戦の再開HUD。HARD FIELDとのORはあるが、共通のLv表示条件は残る。

HARD FIELDとのOR。初戦敗北後の戦闘再開はLv表示 AND（HARD FIELD 0 OR このHUD）。日本語HUDを通らない経路はあるが、Lv表示の条件は残る。

![ZL：狙う／X・A：技を指示](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/farst_battle_field_hud.png)

**判定部分**：POKEMON_ZA_FARST_BATTLE_FIELD_HUD / 探索 [565, 610, 730, 690] / 閾値 0.85 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_1_story_farst_battle_lose.battle_field_ready:23081](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23081>)

### N115 捕獲チャンスだ！ いまのうちに捕まえろ！

**区分**：既存の別経路あり・要確認。捕獲チャンスの会話。捕獲アイコンによる別経路はあるが、文字一致で即捕獲する分岐も残る。

別経路あり・文字分岐も残る。初回の白Commentを閉じた後はGETCHANCE_ICON4で捕獲可能。文字一致時だけ即座に捕獲する分岐も残るため、文字判定そのものの完全置換ではない。

![捕獲チャンスだ！ いまのうちに捕まえろ！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/getchance_comment.png)

**判定部分**：POKEMON_ZA_TEXT_2_GETCHANCE / 探索 [300, 555, 1000, 700] / 閾値 0.9 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_1_story_out_hotel_z_16:23538](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23538>)

### N116 ホテルZ

**区分**：既存の別経路あり・要確認。ホテルZ入口。入口アイコンとのORはあるが、文字はアイコン一致不足を補う用途で残る。

入口アイコンとのOR。IN_ICONとホテルZの文字がOR。文字は入口アイコンの一致不足を補うため追加された経緯があり、他言語でアイコンだけが安定するとは未確認。

![ホテルZ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/out_hotel_z45_hotel_z_text.png)

**判定部分**：POKEMON_ZA_OUT_HOTEL_Z45_HOTEL_Z_TEXT / 探索 [250, 250, 500, 450] / 閾値 0.8 / OR

**収集**：画像取得ONでも、日本語画像が一致した時だけ収集。他言語で不一致なら自動保存されない。

一致した全画面は未確認。探索候補は閾値未満または目的表示の確認ができていないため、HTMLの折りたたみ内にのみ掲載。

**使用箇所**：[_1_story_out_hotel_z_45:24437](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:24437>)

