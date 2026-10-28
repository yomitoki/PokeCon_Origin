# ZA_Story：Aマーク以外の文字依存と代用状況

**最新の残件は別一覧へ再整理しました**：[補足モードの未対応判定・前回画像付き一覧](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_checks.html>)／[画像付きMarkdown版](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/remaining_checks.md>)。主対象33画像／30登録判定、マップ44件、初戦再挑戦2画像、英字等20画像、既存別経路5画像。以下は初回調査と追補の履歴です。

**2026-10-24追補**：メニュー位置、MEGA再戦の順番・再開HP、アブソル／最終戦のHUD・HPによる代用を追加した。各項目の「追補」が最新で、枚数・参照行・その後の説明は初回の調査記録。再戦関連8画像は収集除外、メニューは補足一致でも収集、代用できたボス名は収集しない。道具・冷凍ビーム・BOXは従来判定のまま。詳細は[補足モードの仕様・動画確認・検証](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/image_collection_mode.md>)。

初回確認時点：2026-10-24 14:47 JST。ZIP内の旧版一覧を、現行ZA_storyの登録表・呼出条件・直接画像照合と照合した。画像は現行テンプレートの複製で、全画面写真ではなく実際に判定へ使う切り抜き。

**初回調査の主対象は46枚**（日本語43枚・漢字片2枚・HP文字片1枚）。A操作表示6枚とA単体画像は除外した。件数は単語数・関数数ではなく、重複を除く画像ファイル数。

| 分類 | 枚数 | 主な対象 |
| --- | ---: | --- |
| 選択肢・再挑戦 | 8 | 再挑戦／アドバイス／HPひきつぎ |
| メニュー・技・道具 | 7 | つよさをみる／覚えているわざ／けいけんアメS |
| マップの種類・共通操作 | 7 | 地下水道／移動スポット／移動禁止文 |
| 敗北・降参・報酬 | 7 | 目の前がまっくら／降参する／残念でしたね |
| 開始・序盤イベント | 5 | これで始める／駅の会話／勝負をしかけてきた |
| ボス戦の名前・技・予告 | 8 | ボス名／コアパニッシャー／力を溜めている |
| 第3章の進行状態 | 2 | 作戦会議前／依頼3件の解決 |
| 昼夜表示 | 2 | 日中側・夜側の漢字片 |

**別枠**：マップ移動先44件はPIC候補が登録済みだが、日本語場所名とのANDが残る。英字・略字20枚は全言語で共通かの追加確認。既存の代用・別経路がある6枚は主対象から外し、条件と制約を末尾に記した。

**収集機能の注意**：再挑戦・HP引き継ぎの直接照合5枚は通常の画像登録を通らないため、現行の画像取得モードではその照合時の自動保存対象外。その他の主対象41枚は登録画像。これは初回調査時の状態である。追補後の保存対象は下記と追加資料を参照。

「代用あり」はコード上の別経路が存在する意味で、他言語の実機確認済みという意味ではない。通常の会話枠・FIELD復帰・タイムアウトがあるだけでは、文言の意味の代用として数えていない。

[検索・拡大できる画像一覧（HTML）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_word_checks.html>)

## 初回調査の主対象（追補の代用状況を併記）

### 選択肢・再挑戦

#### N001　再挑戦する／アドバイス

![再挑戦する／アドバイス](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/2_select_tutorial.png)

**現在の状態**：追補：補足モードのMEGA敗北後は、黒背景・選択画面の順番／行数／位置と再開HPで代用。再戦関連の画像収集は除外する。通常モードと、序盤などMEGA共通処理以外の参照は従来どおり。

**初回調査時の状態**：選択枠・行数の検知はあるが、選択肢の意味を文字なしで決める代用は未設定。

枠の数や選択色だけで再挑戦／HP引き継ぎ／あきらめるを同一扱いにしない。

画像：`2_select_tutorial.png`（182×110）

検知キー：`POKEMON_ZA_2_SELECT_TUTORIAL`

使用箇所：[ZA_mega_field_post_attack_roll_if_needed](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:6416>) / [_ZA_story_battle_debug_hold_for_defeat](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20209>) / [_ZA_story_battle_debug_hold_for_defeat](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20261>) ほか4参照。全参照はHTML・監査JSONに収録。

#### N002　選んで再挑戦／選ばず再挑戦／もどる

![選んで再挑戦／選ばず再挑戦／もどる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/3_select_select.png)

**現在の状態**：追補：補足モードのMEGA敗北後は、黒背景・選択画面の順番／行数／位置と再開HPで代用。再戦関連の画像収集は除外する。通常モードと、序盤などMEGA共通処理以外の参照は従来どおり。

**初回調査時の状態**：割込み用の文字画像。通常モードには汎用SELECTの補助guardもあるが、この画像の置換設定はない。

使用先は攻撃後ローリングの割込み確認。OR先のZA_mega_choice_input_guardは通常モードで非文字の2_SELECT／3_SELECTを使う一方、最終戦では別の敗北確認へ分岐するため、全モード共通の代用とは数えない。

画像：`3_select_select.png`（121×145）

検知キー：`POKEMON_ZA_3_SELECT_SELECT`

使用箇所：[ZA_mega_field_post_attack_roll_if_needed](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:6417>) / [image_check_confirmation](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:46473>)

#### N003　再挑戦する／準備して再挑戦／あきらめる

![再挑戦する／準備して再挑戦／あきらめる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/3_select_tutorial.png)

**現在の状態**：追補：補足モードのMEGA敗北後は、黒背景・選択画面の順番／行数／位置と再開HPで代用。再戦関連の画像収集は除外する。通常モードと、序盤などMEGA共通処理以外の参照は従来どおり。

**初回調査時の状態**：選択枠・行数の検知はあるが、選択肢の意味を文字なしで決める代用は未設定。

枠の数や選択色だけで再挑戦／HP引き継ぎ／あきらめるを同一扱いにしない。

画像：`3_select_tutorial.png`（175×145）

検知キー：`POKEMON_ZA_3_SELECT_TUTORIAL`

使用箇所：[ZA_mega_field_post_attack_roll_if_needed](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:6418>) / [ZA_mega_mode5_event_attack_blocked](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7299>) / [ZA_mega_mode5_defeat_candidate_picture](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:9836>) ほか9参照。全参照はHTML・監査JSONに収録。

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/3_select_tutorial.jpg>)

#### N004　HPひきつぎ（選択中）

![HPひきつぎ（選択中）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/mega_retry_hp_carryover_label_selected.png)

**現在の状態**：追補：補足モードのMEGA敗北後は、黒背景・選択画面の順番／行数／位置と再開HPで代用。再戦関連の画像収集は除外する。通常モードと、序盤などMEGA共通処理以外の参照は従来どおり。

**初回調査時の状態**：直接照合。質問／HP引き継ぎの意味を判別する非文字代用は未設定。

通常の画像登録を通らずcv2で照合するため、現行の画像取得モードではこの照合時の自動保存対象外。枠の幾何判定だけでは種類を決めない。

画像：`mega_retry_hp_carryover_label_selected.png`（121×30）

検知キー：`ZA_mega_retry_menu_kind / mega_retry_hp_carryover_label_selected.png`

使用箇所：[ZA_mega_retry_menu_kind](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:10997>)

#### N005　HPひきつぎ（未選択）

![HPひきつぎ（未選択）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/mega_retry_hp_carryover_label_unselected.png)

**現在の状態**：追補：補足モードのMEGA敗北後は、黒背景・選択画面の順番／行数／位置と再開HPで代用。再戦関連の画像収集は除外する。通常モードと、序盤などMEGA共通処理以外の参照は従来どおり。

**初回調査時の状態**：直接照合。質問／HP引き継ぎの意味を判別する非文字代用は未設定。

通常の画像登録を通らずcv2で照合するため、現行の画像取得モードではこの照合時の自動保存対象外。枠の幾何判定だけでは種類を決めない。

画像：`mega_retry_hp_carryover_label_unselected.png`（121×30）

検知キー：`ZA_mega_retry_menu_kind / mega_retry_hp_carryover_label_unselected.png`

使用箇所：[ZA_mega_retry_menu_kind](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:10996>)

#### N006　を選びますか？

![を選びますか？](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/mega_retry_hp_question_choice_suffix.png)

**現在の状態**：追補：補足モードのMEGA敗北後は、黒背景・選択画面の順番／行数／位置と再開HPで代用。再戦関連の画像収集は除外する。通常モードと、序盤などMEGA共通処理以外の参照は従来どおり。

**初回調査時の状態**：直接照合。質問／HP引き継ぎの意味を判別する非文字代用は未設定。

通常の画像登録を通らずcv2で照合するため、現行の画像取得モードではこの照合時の自動保存対象外。枠の幾何判定だけでは種類を決めない。

画像：`mega_retry_hp_question_choice_suffix.png`（196×48）

検知キー：`ZA_mega_retry_menu_kind / mega_retry_hp_question_choice_suffix.png`

使用箇所：[ZA_mega_retry_menu_kind](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:10995>)

#### N007　HP…（質問の先頭部分）

![HP…（質問の先頭部分）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/mega_retry_hp_question_hp_prefix.png)

**現在の状態**：追補：補足モードのMEGA敗北後は、黒背景・選択画面の順番／行数／位置と再開HPで代用。再戦関連の画像収集は除外する。通常モードと、序盤などMEGA共通処理以外の参照は従来どおり。

**初回調査時の状態**：直接照合。質問／HP引き継ぎの意味を判別する非文字代用は未設定。

通常の画像登録を通らずcv2で照合するため、現行の画像取得モードではこの照合時の自動保存対象外。枠の幾何判定だけでは種類を決めない。

画像：`mega_retry_hp_question_hp_prefix.png`（50×31）

検知キー：`ZA_mega_retry_menu_kind / mega_retry_hp_question_hp_prefix.png`

使用箇所：[ZA_mega_retry_menu_kind](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:10994>)

#### N008　このまま…

![このまま…](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/mega_retry_retry_question_prefix.png)

**現在の状態**：追補：補足モードのMEGA敗北後は、黒背景・選択画面の順番／行数／位置と再開HPで代用。再戦関連の画像収集は除外する。通常モードと、序盤などMEGA共通処理以外の参照は従来どおり。

**初回調査時の状態**：直接照合。質問／HP引き継ぎの意味を判別する非文字代用は未設定。

通常の画像登録を通らずcv2で照合するため、現行の画像取得モードではこの照合時の自動保存対象外。枠の幾何判定だけでは種類を決めない。

画像：`mega_retry_retry_question_prefix.png`（117×33）

検知キー：`ZA_mega_retry_menu_kind / mega_retry_retry_question_prefix.png`

使用箇所：[ZA_mega_retry_menu_kind](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:10993>)

### メニュー・技・道具

#### N009　つよさをみる／回復する／使えるわざを選ぶ

![つよさをみる／回復する／使えるわざを選ぶ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/X_menu/pokemon_menu.png)

**現在の状態**：追補：補足モードで選択位置・枠・カーソルによる代用を追加。画像取得ONなら同じフレームの全画面と日本語ROIを保存する。進化を先に済ませる既存の順序が前提。

**初回調査時の状態**：項目名・技名・道具名を含む画像で判定。アイコン部分だけの採用設定はない。

小アイコンが写っていても、現在は文字を含むPNG全体を比較する。

画像：`pokemon_menu.png`（185×157）

検知キー：`POKEMON_ZA_POKEMON_MENU_X_MENU_W`

使用箇所：[_1_story_out_hotel_z_33](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:24145>) / [ZA_common_skill_change_start_check](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35501>) / [ZA_common_skill_change_start_check](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35502>) ほか7参照。全参照はHTML・監査JSONに収録。

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/pokemon_menu.jpg>)

#### N010　つよさをみる／回復する／使えるわざを選ぶ（選択位置違い）

![つよさをみる／回復する／使えるわざを選ぶ（選択位置違い）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/X_menu/pokemon_menu_select_skill.png)

**現在の状態**：追補：補足モードで選択位置・枠・カーソルによる代用を追加。画像取得ONなら同じフレームの全画面と日本語ROIを保存する。進化を先に済ませる既存の順序が前提。

**初回調査時の状態**：項目名・技名・道具名を含む画像で判定。アイコン部分だけの採用設定はない。

小アイコンが写っていても、現在は文字を含むPNG全体を比較する。

画像：`pokemon_menu_select_skill.png`（187×157）

検知キー：`POKEMON_ZA_POKEMON_MENU_X_MENU_W_SELECT_SKILL`

使用箇所：[ZA_common_skill_change_start_check](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35503>) / [ZA_common_skill_change_start_check](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35504>) / [ZA_common_skill_change_skill_window_open](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35565>) ほか2参照。全参照はHTML・監査JSONに収録。

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/pokemon_menu_select_skill.jpg>)

#### N011　覚えているわざ

![覚えているわざ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/X_menu/skillpage.png)

**現在の状態**：追補：補足モードで選択位置・枠・カーソルによる代用を追加。画像取得ONなら同じフレームの全画面と日本語ROIを保存する。進化を先に済ませる既存の順序が前提。

**初回調査時の状態**：項目名・技名・道具名を含む画像で判定。アイコン部分だけの採用設定はない。

小アイコンが写っていても、現在は文字を含むPNG全体を比較する。

画像：`skillpage.png`（118×19）

検知キー：`POKEMON_ZA_SKILL_PAGE_WINDOW`

使用箇所：[ZA_common_skill_change_start_check](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35505>) / [ZA_common_skill_change_start_check](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35506>) / [ZA_common_skill_change_skill_window_chtarget1](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35587>) ほか4参照。全参照はHTML・監査JSONに収録。

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/skillpage.jpg>)

#### N012　けいけんアメS

![けいけんアメS](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/ame_s.png)

**現在の状態**：項目名・技名・道具名を含む画像で判定。アイコン部分だけの採用設定はない。

小アイコンが写っていても、現在は文字を含むPNG全体を比較する。

画像：`ame_s.png`（179×22）

検知キー：`POKEMON_ZA_AME_S`

使用箇所：[_2_story_ame1](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28635>) / [_2_story_ame2](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28642>)

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/ame_s.jpg>)

#### N013　移動する／つよさをみる／使えるわざを選ぶ／もちものを持たせる／ニックネーム／マーキング／やめる

![移動する／つよさをみる／使えるわざを選ぶ／もちものを持たせる／ニックネーム／マーキング／やめる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/boxmenu.png)

**現在の状態**：追補：BOXは代用を採用しない。枠だけの試案がフィールド等3枚に誤一致したため、従来判定と画像収集を維持する。

**初回調査時の状態**：項目名・技名・道具名を含む画像で判定。アイコン部分だけの採用設定はない。

小アイコンが写っていても、現在は文字を含むPNG全体を比較する。

画像：`boxmenu.png`（176×296）

検知キー：`POKEMON_ZA_BOX_MENU`

使用箇所：[_2_story_absol_move4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28032>) / [ZA_common_box_change_box_target1_select](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35862>)

#### N014　れいとうビーム

![れいとうビーム](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_4_e_lank/reibi_skill.png)

**現在の状態**：項目名・技名・道具名を含む画像で判定。アイコン部分だけの採用設定はない。

小アイコンが写っていても、現在は文字を含むPNG全体を比較する。

画像：`reibi_skill.png`（189×43）

検知キー：`POKEMON_ZA_REIBI_SKILL`

使用箇所：[_4_story_shiro_32](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:30361>)

#### N015　おいしいみず

![おいしいみず](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_6_c_lank/water_icon.png)

**現在の状態**：項目名・技名・道具名を含む画像で判定。アイコン部分だけの採用設定はない。

小アイコンが写っていても、現在は文字を含むPNG全体を比較する。

画像：`water_icon.png`（164×36）

検知キー：`POKEMON_ZA_WATER_ICON`

使用箇所：[_6_story_yukari_48](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:32980>)

### マップの種類・共通操作

#### N016　フラダリラボ

![フラダリラボ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/furadari_map.png)

**現在の状態**：マップ種別・タブ名・確認／移動禁止の内容を文字で区別。代用未設定。

地図の移動先PICを使う案とは別の判定。

画像：`furadari_map.png`（189×29）

検知キー：`POKEMON_ZA_FURADARI_MAP`

使用箇所：[ZA_story_furadari_lab_entrance_goto](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:17535>) / [ZA_story_furadari_lab_entrance_goto](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:17541>) / [ZA_story_furadari_lab_entrance_goto](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:17653>) ほか5参照。全参照はHTML・監査JSONに収録。

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/furadari_map.jpg>)

#### N017　この場所に移動しますか？

![この場所に移動しますか？](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/move_comment.png)

**現在の状態**：マップ種別・タブ名・確認／移動禁止の内容を文字で区別。代用未設定。

地図の移動先PICを使う案とは別の判定。

画像：`move_comment.png`（325×44）

検知キー：`POKEMON_ZA_MOVE_COMMENT`

使用箇所：[ZA_Common_goto_jump](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36496>) / [ZA_Common_goto_jump](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36504>) / [ZA_Common_battle_return](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:37185>) ほか6参照。全参照はHTML・監査JSONに収録。

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/move_comment.jpg>)

#### N018　移動スポット

![移動スポット](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/movespot_tab.png)

**現在の状態**：マップ種別・タブ名・確認／移動禁止の内容を文字で区別。代用未設定。

地図の移動先PICを使う案とは別の判定。

画像：`movespot_tab.png`（148×31）

検知キー：`POKEMON_ZA_MOVESPOT_TAB`

使用箇所：[ZA_Common_goto_select1](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36269>) / [ZA_Common_goto_select2](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36354>) / [ZA_bench_goto_pokecenter1](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:37461>) ほか5参照。全参照はHTML・監査JSONに収録。

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/movespot_tab.jpg>)

#### N019　すべて／施設／ポケモンセンター／カフェ／ゾーン／やめる

![すべて／施設／ポケモンセンター／カフェ／ゾーン／やめる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/select_all.png)

**現在の状態**：マップ種別・タブ名・確認／移動禁止の内容を文字で区別。代用未設定。

地図の移動先PICを使う案とは別の判定。

画像：`select_all.png`（206×311）

検知キー：`POKEMON_ZA_SELECT_ALL`

使用箇所：[ZA_Common_goto_select1](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36277>) / [ZA_Common_goto_select1](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36289>) / [ZA_Common_goto_select1](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36309>) ほか3参照。全参照はHTML・監査JSONに収録。

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/select_all.jpg>)

#### N020　地下水道

![地下水道](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/underground_sewer_map.png)

**現在の状態**：マップ種別・タブ名・確認／移動禁止の内容を文字で区別。代用未設定。

地図の移動先PICを使う案とは別の判定。

画像：`underground_sewer_map.png`（164×27）

検知キー：`POKEMON_ZA_UG_SEWER_MAP`

使用箇所：[_5_story_karasuba_69](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:31908>) / [_5_story_karasuba_96](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:32316>)

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/underground_sewer_map.jpg>)

#### N021　ポケモンにみつかっているため 移動できない！

![ポケモンにみつかっているため 移動できない！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/POKEMON_ZA_MOVE_COMMENT_BATTLE2.png)

**現在の状態**：マップ種別・タブ名・確認／移動禁止の内容を文字で区別。代用未設定。

地図の移動先PICを使う案とは別の判定。

画像：`POKEMON_ZA_MOVE_COMMENT_BATTLE2.png`（381×68）

検知キー：`POKEMON_ZA_MOVE_COMMENT_BATTLE2`

使用箇所：[_2_story_tower_38](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25220>) / [_2_story_tower_40](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25271>) / [_4_story_shiro_32_0](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:30353>)

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/POKEMON_ZA_MOVE_COMMENT_BATTLE2.jpg>)

#### N022　戦闘しているので 移動できない！

![戦闘しているので 移動できない！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/move_comment_battle.png)

**現在の状態**：マップ種別・タブ名・確認／移動禁止の内容を文字で区別。代用未設定。

地図の移動先PICを使う案とは別の判定。

画像：`move_comment_battle.png`（219×88）

検知キー：`POKEMON_ZA_MOVE_COMMENT_BATTLE`

使用箇所：[ZA_Common_goto_jump](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36472>) / [ZA_Common_goto_jump](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36479>) / [ZA_Common_battle_return](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:37184>) ほか3参照。全参照はHTML・監査JSONに収録。

### 敗北・降参・報酬

#### N023　目の前がまっくらになった！

![目の前がまっくらになった！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/furadari_eyes_dark_comment.png)

**現在の状態**：特定の敗北・降参・報酬文言を使う。内容を識別する非文字の代用は未設定。

FIELD復帰などの後段処理があっても、降参への同意や敗北の意味の代用にはならない。

画像：`furadari_eyes_dark_comment.png`（360×50）

検知キー：`POKEMON_ZA_FURADARI_EYES_DARK_COMMENT` / `POKEMON_ZA_LOSE`

使用箇所：[_ZA_furadari_eyes_dark_comment_visible](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:17490>) / [ZA_story_furadari_black_comment_recovery_step.eyes_dark_is_visible](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:17707>) / [_ZA_story_battle_debug_hold_for_defeat](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20193>) ほか14参照。全参照はHTML・監査JSONに収録。

#### N024　賞金メダルを半分わたして 降参しますか？

![賞金メダルを半分わたして 降参しますか？](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/escapecomment1.png)

**現在の状態**：特定の敗北・降参・報酬文言を使う。内容を識別する非文字の代用は未設定。

FIELD復帰などの後段処理があっても、降参への同意や敗北の意味の代用にはならない。

画像：`escapecomment1.png`（649×128）

検知キー：`POKEMON_ZA_ESCAPE_COMMENT1`

使用箇所：[ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38182>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38793>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38924>)

#### N025　次は勝てるように ポケモンや使える技を確認しましょう

![次は勝てるように ポケモンや使える技を確認しましょう](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/escapecomment2.png)

**現在の状態**：特定の敗北・降参・報酬文言を使う。内容を識別する非文字の代用は未設定。

FIELD復帰などの後段処理があっても、降参への同意や敗北の意味の代用にはならない。

画像：`escapecomment2.png`（608×125）

検知キー：`POKEMON_ZA_ESCAPE_COMMENT2`

使用箇所：[ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38184>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38795>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38926>)

#### N026　降参する／続ける

![降参する／続ける](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/escapecommentselect.png)

**現在の状態**：特定の敗北・降参・報酬文言を使う。内容を識別する非文字の代用は未設定。

FIELD復帰などの後段処理があっても、降参への同意や敗北の意味の代用にはならない。

画像：`escapecommentselect.png`（182×116）

検知キー：`POKEMON_ZA_ESCAPE_SELECT`

使用箇所：[ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38180>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38791>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38922>)

#### N027　戦えるポケモンがいなくなった……

![戦えるポケモンがいなくなった……](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/lose.png)

**現在の状態**：特定の敗北・降参・報酬文言を使う。内容を識別する非文字の代用は未設定。

FIELD復帰などの後段処理があっても、降参への同意や敗北の意味の代用にはならない。

画像：`lose.png`（445×49）

検知キー：`POKEMON_ZA_LOSE`

使用箇所：[_ZA_story_battle_debug_hold_for_defeat](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20193>) / [_ZA_story_battle_debug_hold_for_defeat](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20194>) / [_ZA_story_battle_debug_hold_for_defeat](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20208>) ほか11参照。全参照はHTML・監査JSONに収録。

#### N028　チャレンジチケットを手に入れたら

![チャレンジチケットを手に入れたら](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/reword_end.png)

**現在の状態**：特定の敗北・降参・報酬文言を使う。内容を識別する非文字の代用は未設定。

FIELD復帰などの後段処理があっても、降参への同意や敗北の意味の代用にはならない。

画像：`reword_end.png`（630×58）

検知キー：`POKEMON_ZA_REWORD_END`

使用箇所：[ZA_mega_mode5_event_attack_blocked](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7289>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38369>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38386>) ほか7参照。全参照はHTML・監査JSONに収録。

#### N029　残念でしたね……

![残念でしたね……](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/reword_lose.png)

**現在の状態**：特定の敗北・降参・報酬文言を使う。内容を識別する非文字の代用は未設定。

FIELD復帰などの後段処理があっても、降参への同意や敗北の意味の代用にはならない。

画像：`reword_lose.png`（242×51）

検知キー：`POKEMON_ZA_REWORD_LOSE`

使用箇所：[ZA_mega_mode5_event_attack_blocked](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7290>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38376>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38393>) ほか7参照。全参照はHTML・監査JSONに収録。

### 開始・序盤イベント

#### N030　これで始める！

![これで始める！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_0_Start/startbutton_select.png)

**現在の状態**：開始・特定会話・初戦再開の表示を使う。該当内容の非文字代用は未設定。

汎用会話枠・矢印とは別に、表示内容を特定する文字チェックが残る。

画像：`startbutton_select.png`（251×76）

検知キー：`POKEMON_ZA_STARTBTN_SELECT`

使用箇所：[main_0_start](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22694>) / [main_0_start](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22695>) / [main_0_start](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22700>)

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/startbutton_select.jpg>)

#### N031　勝負をしかけてきた！

![勝負をしかけてきた！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/farst_battle_retry_start.png)

**現在の状態**：開始・特定会話・初戦再開の表示を使う。該当内容の非文字代用は未設定。

汎用会話枠・矢印とは別に、表示内容を特定する文字チェックが残る。

画像：`farst_battle_retry_start.png`（270×43）

検知キー：`POKEMON_ZA_FARST_BATTLE_RETRY_START`

使用箇所：[_ZA_story_battle_debug_hold_for_defeat](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20214>) / [_ZA_story_battle_debug_hold_for_defeat](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20215>) / [_1_story_farst_battle](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:23030>)

#### N032　ポケモンの勉…／いつかは博士…（切り抜かれた会話片）

![ポケモンの勉…／いつかは博士…（切り抜かれた会話片）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/out_hotel_z23_field_white_comment.png)

**現在の状態**：開始・特定会話・初戦再開の表示を使う。該当内容の非文字代用は未設定。

汎用会話枠・矢印とは別に、表示内容を特定する文字チェックが残る。

画像：`out_hotel_z23_field_white_comment.png`（120×80）

検知キー：`POKEMON_ZA_OUT_HOTEL_Z23_FIELD_WHITE_COMMENT`

使用箇所：[ZA_markerdir](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22202>)

#### N033　ミアレシティだ！

![ミアレシティだ！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/station_field.png)

**現在の状態**：開始・特定会話・初戦再開の表示を使う。該当内容の非文字代用は未設定。

汎用会話枠・矢印とは別に、表示内容を特定する文字チェックが残る。

画像：`station_field.png`（138×41）

検知キー：`POKEMON_ZA_TEXT_TRAIN_OUT_COMMENT`

使用箇所：[_1_story_start_check](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22834>) / [_1_story_staition_out](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22854>) / [_1_story_staition_out](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22855>) ほか1参照。全参照はHTML・監査JSONに収録。

#### N034　ん？ なんか騒ぎが…（会話片）

![ん？ なんか騒ぎが…（会話片）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/station_leave_comment.png)

**現在の状態**：開始・特定会話・初戦再開の表示を使う。該当内容の非文字代用は未設定。

汎用会話枠・矢印とは別に、表示内容を特定する文字チェックが残る。

画像：`station_leave_comment.png`（106×47）

検知キー：`POKEMON_ZA_TEXT_STATION_LEAVE_COMMENT`

使用箇所：[_1_story_staition_front](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22869>) / [_1_story_staition_front](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22870>) / [_1_story_staition_front](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22874>) ほか5参照。全参照はHTML・監査JSONに収録。

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/station_leave_comment.jpg>)

### ボス戦の名前・技・予告

#### N035　力を溜めている……（予告片）

![力を溜めている……（予告片）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_charge.png)

**現在の状態**：ボス名・技表示・攻撃予告の文字を使用。該当検知を置き換える設定はない。

別の戦闘状態や回避経路があっても、この表示の同定とは別。

画像：`last_battle_charge.png`（155×24）

検知キー：`POKEMON_ZA_LAST_BATTLE_CHARGE`

使用箇所：[ZA_mega_mode5_no_attack_watchdog](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7158>) / [ZA_mega_mode5_no_attack_watchdog](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7159>) / [ZA_mega_mode5_no_attack_watchdog](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7187>) ほか6参照。全参照はHTML・監査JSONに収録。

#### N036　コアパニッシャー…

![コアパニッシャー…](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_move_core_enforcer.png)

**現在の状態**：ボス名・技表示・攻撃予告の文字を使用。該当検知を置き換える設定はない。

別の戦闘状態や回避経路があっても、この表示の同定とは別。

画像：`last_battle_move_core_enforcer.png`（177×23）

検知キー：`POKEMON_ZA_LAST_BATTLE_MOVE_UI`

使用箇所：[ZA_renda_button](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:6652>) / [ZA_mega_mode5_event_attack_picture](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7328>) / [ZA_mega_mode5_indefinite_field_wait_update](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:10146>) ほか5参照。全参照はHTML・監査JSONに収録。

#### N037　グランドフォース

![グランドフォース](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_move_lands_wrath.png)

**現在の状態**：ボス名・技表示・攻撃予告の文字を使用。該当検知を置き換える設定はない。

別の戦闘状態や回避経路があっても、この表示の同定とは別。

画像：`last_battle_move_lands_wrath.png`（167×29）

検知キー：`POKEMON_ZA_LAST_BATTLE_MOVE_UI`

使用箇所：[ZA_renda_button](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:6652>) / [ZA_mega_mode5_event_attack_picture](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7328>) / [ZA_mega_mode5_indefinite_field_wait_update](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:10146>) ほか5参照。全参照はHTML・監査JSONに収録。

#### N038　サウザンアロー

![サウザンアロー](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_move_thousand_arrows.png)

**現在の状態**：ボス名・技表示・攻撃予告の文字を使用。該当検知を置き換える設定はない。

別の戦闘状態や回避経路があっても、この表示の同定とは別。

画像：`last_battle_move_thousand_arrows.png`（158×26）

検知キー：`POKEMON_ZA_LAST_BATTLE_MOVE_UI`

使用箇所：[ZA_renda_button](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:6652>) / [ZA_mega_mode5_event_attack_picture](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7328>) / [ZA_mega_mode5_indefinite_field_wait_update](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:10146>) ほか5参照。全参照はHTML・監査JSONに収録。

#### N039　サウザンウェーブ

![サウザンウェーブ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_move_thousand_waves.png)

**現在の状態**：ボス名・技表示・攻撃予告の文字を使用。該当検知を置き換える設定はない。

別の戦闘状態や回避経路があっても、この表示の同定とは別。

画像：`last_battle_move_thousand_waves.png`（164×26）

検知キー：`POKEMON_ZA_LAST_BATTLE_MOVE_UI`

使用箇所：[ZA_renda_button](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:6652>) / [ZA_mega_mode5_event_attack_picture](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7328>) / [ZA_mega_mode5_indefinite_field_wait_update](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:10146>) ほか5参照。全参照はHTML・監査JSONに収録。

#### N040　強い光を放…（予告片）

![強い光を放…（予告片）](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/last_battle_strong_light.png)

**現在の状態**：ボス名・技表示・攻撃予告の文字を使用。該当検知を置き換える設定はない。

別の戦闘状態や回避経路があっても、この表示の同定とは別。

画像：`last_battle_strong_light.png`（97×24）

検知キー：`POKEMON_ZA_LAST_BATTLE_STRONG_LIGHT`

使用箇所：[ZA_mega_mode5_no_attack_watchdog](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7160>) / [ZA_mega_mode5_no_attack_watchdog](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7161>) / [ZA_mega_mode5_no_attack_watchdog](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7189>) ほか6参照。全参照はHTML・監査JSONに収録。

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/last_battle_strong_light.jpg>)

#### N041　暴走メガアブソル

![暴走メガアブソル](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_2_y_lank/mega_absol_battle_name.png)

**現在の状態**：追補：補足モードではFIELD系＋非文字の戦闘アイコン＋上部ボスHPで代用する。代用一致時は名前画像を収集しない。名前による種別の特定はしない。

**初回調査時の状態**：ボス名・技表示・攻撃予告の文字を使用。該当検知を置き換える設定はない。

別の戦闘状態や回避経路があっても、この表示の同定とは別。

画像：`mega_absol_battle_name.png`（238×39）

検知キー：`POKEMON_ZA_MEGA_ABSOL_BATTLE_NAME`

使用箇所：[_2_story_absol_battle](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27988>)

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/mega_absol_battle_name.jpg>)

#### N042　超大暴走アンジュフラエッテ

![超大暴走アンジュフラエッテ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_8_last/last_battle_name.png)

**現在の状態**：追補：補足モードでは通常時はFIELD系＋戦闘アイコン＋ボスHP、最終戦のFIELD不在時はボスHPで代用する。5秒確認と既存の復帰条件を維持し、代用一致時は名前画像を収集しない。

**初回調査時の状態**：ボス名・技表示・攻撃予告の文字を使用。該当検知を置き換える設定はない。

別の戦闘状態や回避経路があっても、この表示の同定とは別。

画像：`last_battle_name.png`（340×38）

検知キー：`POKEMON_ZA_LAST_BATTLE_NAME`

使用箇所：[ZA_mega_mode5_last_name_no_hard_timeout](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7354>) / [ZA_mega_mode5_defeat_event_name_recovery_ready](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:9861>) / [ZA_mega_mode5_event_name_ui_missing_update](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:9979>)

### 第3章の進行状態

#### N043　暴走メガシンカの依頼を 3件すべて解決する

![暴走メガシンカの依頼を 3件すべて解決する](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/chapter3_mega2_post_meeting_task.png)

**現在の状態**：会議前／会議後を目的文で分け、FIELDと3秒安定を確認する。文字なしの代用は未設定。

目的アイコンだけでは会議の前後を区別できるとは確認できていない。

画像：`chapter3_mega2_post_meeting_task.png`（323×56）

検知キー：`POKEMON_ZA_MEGA2_POST_MEETING_TASK`

使用箇所：[_ZA_story_mega2_phase_selector](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:29849>)

#### N044　エムゼット団の 作戦会議をはじめる

![エムゼット団の 作戦会議をはじめる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/chapter3_mega2_pre_meeting_task.png)

**現在の状態**：会議前／会議後を目的文で分け、FIELDと3秒安定を確認する。文字なしの代用は未設定。

目的アイコンだけでは会議の前後を区別できるとは確認できていない。

画像：`chapter3_mega2_pre_meeting_task.png`（323×56）

検知キー：`POKEMON_ZA_MEGA2_PRE_MEETING_TASK`

使用箇所：[_ZA_story_mega2_phase_selector](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:29848>)

### 昼夜表示

#### N045　昼夜表示の漢字片

![昼夜表示の漢字片](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/morning.png)

**現在の状態**：日中／夜側の大きな漢字の一部分を照合。色・時刻・アイコンだけの代用は未設定。

文字全体ではないが、言語ごとの字形が変わると影響する。

画像：`morning.png`（60×62）

検知キー：`POKEMON_ZA_MORNING`

使用箇所：[ZA_story_furadari_lab_entrance_goto](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:17572>) / [_ZA_story_event_entry_pending_recovery_step](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:19314>) / [ZA_story_Template_battle_after](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:19948>) ほか62参照。全参照はHTML・監査JSONに収録。

#### N046　昼夜表示の漢字片

![昼夜表示の漢字片](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/night.png)

**現在の状態**：日中／夜側の大きな漢字の一部分を照合。色・時刻・アイコンだけの代用は未設定。

文字全体ではないが、言語ごとの字形が変わると影響する。

画像：`night.png`（157×163）

検知キー：`POKEMON_ZA_NIGHT`

使用箇所：[_ZA_story_event_entry_pending_recovery_step](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:19315>) / [ZA_story_Template_battle_after](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:19949>) / [_ZA_story_battle_after_safe_renda](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:21500>) ほか14参照。全参照はHTML・監査JSONに収録。

## マップ移動先：代用候補はあるが日本語名ANDが残る

#### N047　10番ワイルドゾーン

![10番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE10_target.png)

**現在の状態**：番号詳細あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE10_target.png`（175×21）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE10`

使用箇所：[_2_story_mapping_117](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28247>) / [_2_story_mapping_117](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28248>) / [_2_story_mapping_117](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28257>)

既存のPIC／代用候補：

![W_ZONE10_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE10_pic.png)

#### N048　14番ワイルドゾーン

![14番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE14_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE14_target.png`（178×23）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE14`

使用箇所：[_5_story_mapping_4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:30989>) / [_5_story_mapping_4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:30990>) / [_5_story_mapping_4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:30999>)

既存のPIC／代用候補：

![W_ZONE14_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE14_pic.png)

#### N049　15番ワイルドゾーン

![15番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE15_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE15_target.png`（176×25）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE15`

使用箇所：[_5_story_mapping_6](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:31030>) / [_5_story_mapping_6](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:31031>) / [_5_story_mapping_6](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:31044>)

既存のPIC／代用候補：

![W_ZONE15_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE15_pic.png)

#### N050　17番ワイルドゾーン

![17番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE17_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE17_target.png`（178×20）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE17`

使用箇所：[_6_story_mapping_4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:32548>) / [_6_story_mapping_4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:32549>) / [_6_story_mapping_4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:32558>)

既存のPIC／代用候補：

![W_ZONE17_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE17_pic.png)

#### N051　18番ワイルドゾーン

![18番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE18_target.png)

**現在の状態**：番号詳細あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE18_target.png`（176×21）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE18`

使用箇所：[_7_story_mapping_4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:33384>) / [_7_story_mapping_4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:33385>) / [_7_story_mapping_4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:33394>)

既存のPIC／代用候補：

![W_ZONE18_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE18_pic.png)

#### N052　19番ワイルドゾーン

![19番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE19_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE19_target.png`（185×19）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE19`

使用箇所：[_7_story_mapping_8](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:33480>) / [_7_story_mapping_8](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:33481>) / [_7_story_mapping_8](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:33493>)

既存のPIC／代用候補：

![W_ZONE19_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE19_pic.png)

#### N053　2番ワイルドゾーン

![2番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE2_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE2_target.png`（160×19）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE2`

使用箇所：[_2_story_mapping_39](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26006>) / [_2_story_mapping_39](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26007>) / [_2_story_mapping_39](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26016>)

既存のPIC／代用候補：

![W_ZONE2_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE2_pic.png)

#### N054　4番ワイルドゾーン

![4番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE4_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE4_target.png`（161×23）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE4`

使用箇所：[_2_story_mapping_3](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25354>) / [_2_story_mapping_3](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25355>) / [_2_story_mapping_3](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25364>)

既存のPIC／代用候補：

![W_ZONE4_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE4_pic.png)

#### N055　5番ワイルドゾーン

![5番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE5_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE5_target.png`（162×19）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE5`

使用箇所：[_2_story_mapping_42](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26066>) / [_2_story_mapping_42](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26067>) / [_2_story_mapping_42](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26076>)

既存のPIC／代用候補：

![W_ZONE5_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE5_pic.png)

#### N056　6番ワイルドゾーン

![6番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE6_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE6_target.png`（164×22）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE6`

使用箇所：[_2_story_mapping_45](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26120>) / [_2_story_mapping_45](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26121>) / [_2_story_mapping_45](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26130>)

既存のPIC／代用候補：

![W_ZONE6_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE6_pic.png)

#### N057　8番ワイルドゾーン

![8番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE8_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE8_target.png`（160×20）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE8`

使用箇所：[_2_story_mapping_113](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28121>) / [_2_story_mapping_113](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28122>) / [_2_story_mapping_113](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28131>)

既存のPIC／代用候補：

![W_ZONE8_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE8_pic.png)

#### N058　9番ワイルドゾーン

![9番ワイルドゾーン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE9_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

PICもWILD ZONE＋番号の文字画像。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`W_ZONE9_target.png`（161×21）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE9`

使用箇所：[_2_story_mapping_115](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28184>) / [_2_story_mapping_115](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28185>) / [_2_story_mapping_115](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28194>)

既存のPIC／代用候補：

![W_ZONE9_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/W_ZONE9_pic.png)

#### N059　ミアレ美術館

![ミアレ美術館](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/art_museum_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`art_museum_target.png`（116×23）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_ART_MUSEUM`

使用箇所：[_2_story_mapping_81](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26781>) / [_2_story_mapping_81](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26782>) / [_2_story_mapping_81](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26791>)

既存のPIC／代用候補：

![art_museum_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/art_museum_pic.png)

#### N060　ブルー広場

![ブルー広場](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/bule_square_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`bule_square_target.png`（96×19）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_BLUE_SQUARE`

使用箇所：[_2_story_mapping_60](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26394>) / [_2_story_mapping_60](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26395>) / [_2_story_mapping_60](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26404>) ほか1参照。全参照はHTML・監査JSONに収録。

既存のPIC／代用候補：

![bule_square_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/bule_square_pic.png)

#### N061　カフェ・アラモード

![カフェ・アラモード](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_alamode_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_alamode_target.png`（153×22）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_ALAMODE`

使用箇所：[_2_story_mapping_48](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26168>) / [_2_story_mapping_48](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26169>) / [_2_story_mapping_48](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26178>)

既存のPIC／代用候補：

![cafe_alamode_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_alamode_pic.png)

#### N062　カフェ・バタイユ

![カフェ・バタイユ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_bataille_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_bataille_target.png`（136×22）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_BATAILLE`

使用箇所：[_2_story_mapping_94](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26999>) / [_2_story_mapping_94](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27000>) / [_2_story_mapping_94](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27009>)

既存のPIC／代用候補：

![cafe_bataille_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_bataille_pic.png)

#### N063　カフェ・カンコドール

![カフェ・カンコドール](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_cancodor_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_cancodor_target.png`（169×26）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_CANCODOR`

使用箇所：[_2_story_mapping_75](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26661>) / [_2_story_mapping_75](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26662>) / [_2_story_mapping_75](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26671>)

既存のPIC／代用候補：

![cafe_cancodor_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_cancodor_pic.png)

#### N064　カフェ・かわいがり

![カフェ・かわいがり](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_cute_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_cute_target.png`（160×22）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_CUTE`

使用箇所：[_2_story_mapping_109](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27285>) / [_2_story_mapping_109](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27286>) / [_2_story_mapping_109](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27295>)

既存のPIC／代用候補：

![cafe_cute_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_cute_pic.png)

#### N065　カフェ・フォーカス

![カフェ・フォーカス](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_focus_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_focus_target.png`（150×20）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_FOCUS`

使用箇所：[_2_story_mapping_66](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26509>) / [_2_story_mapping_66](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26510>) / [_2_story_mapping_66](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26519>)

既存のPIC／代用候補：

![cafe_focus_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_focus_pic.png)

#### N066　カフェ・おとこまえ

![カフェ・おとこまえ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_man_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_man_target.png`（161×23）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_MAN`

使用箇所：[_2_story_mapping_12](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25509>) / [_2_story_mapping_12](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25510>) / [_2_story_mapping_12](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25519>)

既存のPIC／代用候補：

![cafe_man_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_man_pic.png)

#### N067　ヌーヴォカフェ2号店

![ヌーヴォカフェ2号店](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_nuvo2_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_nuvo2_target.png`（181×21）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_NUVO2`

使用箇所：[_2_story_mapping_57](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26345>) / [_2_story_mapping_57](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26346>) / [_2_story_mapping_57](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26355>)

既存のPIC／代用候補：

![cafe_nuvo2_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_nuvo2_pic.png)

#### N068　ヌーヴォカフェ3号店

![ヌーヴォカフェ3号店](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_nuvo3_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_nuvo3_target.png`（179×21）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_NUVO3`

使用箇所：[_2_story_mapping_72](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26611>) / [_2_story_mapping_72](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26612>) / [_2_story_mapping_72](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26621>)

既存のPIC／代用候補：

![cafe_nuvo3_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_nuvo3_pic.png)

#### N069　カフェ・パルトネール

![カフェ・パルトネール](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_partenaire_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_partenaire_target.png`（174×22）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_PARTENAIRE`

使用箇所：[_2_story_mapping_90](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26936>) / [_2_story_mapping_90](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26937>) / [_2_story_mapping_90](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26946>)

既存のPIC／代用候補：

![cafe_partenaire_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_partenaire_pic.png)

#### N070　カフェ・リテイク

![カフェ・リテイク](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_retake_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_retake_target.png`（133×25）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_RETAKE`

使用箇所：[_2_story_mapping_33](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25897>) / [_2_story_mapping_33](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25898>) / [_2_story_mapping_33](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25907>)

既存のPIC／代用候補：

![cafe_retake_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_retake_pic.png)

#### N071　カフェ・スラローム

![カフェ・スラローム](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_slalom_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_slalom_target.png`（152×21）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_SLALOM`

使用箇所：[_2_story_mapping_69](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26562>) / [_2_story_mapping_69](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26563>) / [_2_story_mapping_69](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26572>)

既存のPIC／代用候補：

![cafe_slalom_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_slalom_pic.png)

#### N072　カフェ・ソレイユ

![カフェ・ソレイユ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_soleil_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_soleil_target.png`（134×22）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_SOLEIL`

使用箇所：[_2_story_mapping_63](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26450>) / [_2_story_mapping_63](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26460>)

既存のPIC／代用候補：

![cafe_soleil_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_soleil_pic.png)

#### N073　カフェ・トウトウ

![カフェ・トウトウ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_toto_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_toto_target.png`（133×23）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_TOTO`

使用箇所：[_2_story_mapping_51](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26216>) / [_2_story_mapping_51](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26217>) / [_2_story_mapping_51](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26226>)

既存のPIC／代用候補：

![cafe_toto_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_toto_pic.png)

#### N074　カフェ・ツイスター

![カフェ・ツイスター](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_twister_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_twister_target.png`（154×21）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_TWISTER`

使用箇所：[_2_story_mapping_54](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26279>) / [_2_story_mapping_54](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26280>) / [_2_story_mapping_54](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26289>)

既存のPIC／代用候補：

![cafe_twister_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_twister_pic.png)

#### N075　カフェ・アルティメット

![カフェ・アルティメット](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_ult_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`cafe_ult_target.png`（181×21）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_ULT`

使用箇所：[_2_story_mapping_87](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26885>) / [_2_story_mapping_87](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26886>) / [_2_story_mapping_87](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26895>)

既存のPIC／代用候補：

![cafe_ult_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/cafe_ult_pic.png)

#### N076　ホテル シュールリッシュ

![ホテル シュールリッシュ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/hotel_surrealish_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`hotel_surrealish_target.png`（216×22）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_HOTEL_SURREALISH`

使用箇所：[_2_story_mapping_84](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26833>) / [_2_story_mapping_84](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26834>) / [_2_story_mapping_84](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26843>)

既存のPIC／代用候補：

![hotel_surrealish_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/hotel_surrealish_pic.png)

#### N077　ジャスティスの会道場

![ジャスティスの会道場](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/justice_dojo_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`justice_dojo_target.png`（189×22）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_JUSTICE_DOJO`

使用箇所：[_2_story_mapping_103](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27177>) / [_2_story_mapping_103](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27178>) / [_2_story_mapping_103](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27187>)

既存のPIC／代用候補：

![justice_dojo_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/justice_dojo_pic.png)

#### N078　ポケモンセンター：ブルー

![ポケモンセンター：ブルー](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_blue_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`pokecenter_blue_target.png`（226×25）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_BLUE`

使用箇所：[_2_story_mapping_27](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25785>) / [_2_story_mapping_27](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25786>) / [_2_story_mapping_27](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25795>)

既存のPIC／代用候補：

![pokecenter_blue_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_blue_pic.png)

#### N079　ポケモンセンター：イベール

![ポケモンセンター：イベール](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_evel_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`pokecenter_evel_target.png`（244×27）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_EVEL`

使用箇所：[_2_story_mapping_30](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25840>) / [_2_story_mapping_30](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25841>) / [_2_story_mapping_30](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25850>)

既存のPIC／代用候補：

![pokecenter_evel_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_evel_pic.png)

#### N080　ポケモンセンター：ジョーヌ

![ポケモンセンター：ジョーヌ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_jone_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`pokecenter_jone_target.png`（239×19）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_JONE`

使用箇所：[_2_story_mapping_36](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25950>) / [_2_story_mapping_36](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25951>) / [_2_story_mapping_36](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25960>)

既存のPIC／代用候補：

![pokecenter_jone_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_jone_pic.png)

#### N081　ポケモンセンター：プランタン

![ポケモンセンター：プランタン](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_prantan_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`pokecenter_prantan_target.png`（258×24）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_PRANTAN`

使用箇所：[_2_story_mapping_24](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25714>) / [_2_story_mapping_24](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25715>) / [_2_story_mapping_24](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25724>)

既存のPIC／代用候補：

![pokecenter_prantan_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_prantan_pic.png)

#### N082　ポケモンセンター：ローズ広場

![ポケモンセンター：ローズ広場](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_rose_square_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`pokecenter_rose_square_target.png`（263×22）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_ROSE_S`

使用箇所：[_2_story_mapping_18](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25610>) / [_2_story_mapping_18](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25611>) / [_2_story_mapping_18](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25620>)

既存のPIC／代用候補：

![pokecenter_rose_square_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_rose_square_pic.png)

#### N083　ポケモンセンター：ローズ

![ポケモンセンター：ローズ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_rose_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`pokecenter_rose_target.png`（264×20）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_ROSE`

使用箇所：[_2_story_mapping_21](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25663>) / [_2_story_mapping_21](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25664>) / [_2_story_mapping_21](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25673>)

既存のPIC／代用候補：

![pokecenter_rose_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_rose_pic.png)

#### N084　ポケモンセンター：ルージュ

![ポケモンセンター：ルージュ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_rudu_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`pokecenter_rudu_target.png`（239×20）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_RUDU`

使用箇所：[_2_story_mapping_6](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25405>) / [_2_story_mapping_6](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25406>) / [_2_story_mapping_6](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25415>)

既存のPIC／代用候補：

![pokecenter_rudu_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/pokecenter_rudu_pic.png)

#### N085　ラシーヌ工務店

![ラシーヌ工務店](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/racine_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`racine_target.png`（139×28）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_RACINE`

使用箇所：[_2_story_mapping_97](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27053>) / [_2_story_mapping_97](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27054>) / [_2_story_mapping_97](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27063>)

既存のPIC／代用候補：

![racine_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/racine_pic.png)

#### N086　リストランテ ニ・リュー

![リストランテ ニ・リュー](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_2ryu_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`restaurant_2ryu_target.png`（207×21）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_2RYU`

使用箇所：[_2_story_mapping_78](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26715>) / [_2_story_mapping_78](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26716>) / [_2_story_mapping_78](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:26725>)

既存のPIC／代用候補：

![restaurant_2ryu_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_2ryu_pic.png)

#### N087　レストラン・ド・フツー

![レストラン・ド・フツー](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_dohutsu_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`restaurant_dohutsu_target.png`（182×23）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_DOHUTSU`

使用箇所：[_2_story_mapping_100](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27113>) / [_2_story_mapping_100](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27114>) / [_2_story_mapping_100](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27123>)

既存のPIC／代用候補：

![restaurant_dohutsu_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_dohutsu_pic.png)

#### N088　レストラン ローリングドリーマー

![レストラン ローリングドリーマー](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_dream_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`restaurant_dream_target.png`（292×23）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_DREAM`

使用箇所：[_2_story_mapping_9](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25457>) / [_2_story_mapping_9](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25458>) / [_2_story_mapping_9](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25467>)

既存のPIC／代用候補：

![restaurant_dream_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_dream_pic.png)

#### N089　レストラン・ド・キワミ

![レストラン・ド・キワミ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_exterme_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`restaurant_exterme_target.png`（183×22）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_EXTREAME`

使用箇所：[_2_story_mapping_106](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27237>) / [_2_story_mapping_106](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27238>) / [_2_story_mapping_106](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:27247>)

既存のPIC／代用候補：

![restaurant_exterme_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/restaurant_exterme_pic.png)

#### N090　ローズ広場

![ローズ広場](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/rose_square_target.png)

**現在の状態**：PIC候補あり・日本語名ANDを維持

施設・風景のPICが登録済み。ZA_Common_mappic_checkは場所名とPICのAND。日本語名を省く設定にはなっていない。

画像：`rose_square_target.png`（96×21）

検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_ROSE_SQUARE`

使用箇所：[_2_story_mapping_15](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25559>) / [_2_story_mapping_15](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25560>) / [_2_story_mapping_15](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:25569>)

既存のPIC／代用候補：

![rose_square_pic.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/MovePoint/rose_square_pic.png)

## 英字・略字：他言語でも共通か追加確認

#### N091　C+

![C+](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/C+.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。 色違い2枚のORはあるが、どちらもC+の字形を使う。

画像：`C+.png`（27×20）

検知キー：`POKEMON_ZA_C+` / `POKEMON_ZA_C+_LOW`

使用箇所：[ZA_mega_mode5_skill_attack_ready](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:11526>) / [ZA_mega_mode5_skill_attack_ready](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:11527>) / [ZA_mega_attack_ready](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:11549>) ほか25参照。全参照はHTML・監査JSONに収録。

#### N092　C+

![C+](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/C+_white.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。 色違い2枚のORはあるが、どちらもC+の字形を使う。

画像：`C+_white.png`（21×19）

検知キー：`POKEMON_ZA_C+` / `POKEMON_ZA_C+_LOW`

使用箇所：[ZA_mega_mode5_skill_attack_ready](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:11526>) / [ZA_mega_mode5_skill_attack_ready](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:11527>) / [ZA_mega_attack_ready](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:11549>) ほか25参照。全参照はHTML・監査JSONに収録。

#### N093　MISSION COMPLETEの文字片 C

![MISSION COMPLETEの文字片 C](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_C.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。 C/M/P/Tの4片中3片一致（AT_LEAST_3）。英字を使わない判定ではない。

画像：`POKEMON_ZA_MISSION_COMPLETE_C.png`（50×46）

検知キー：`POKEMON_ZA_MISSION_COMPLETE`

使用箇所：[ZA_story_Template_battle_before_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20514>) / [ZA_story_Template_battle_function_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20915>) / [ZA_story_Template_battle_after_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:21061>) ほか8参照。全参照はHTML・監査JSONに収録。

#### N094　MISSION COMPLETEの文字片 M

![MISSION COMPLETEの文字片 M](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_M.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。 C/M/P/Tの4片中3片一致（AT_LEAST_3）。英字を使わない判定ではない。

画像：`POKEMON_ZA_MISSION_COMPLETE_M.png`（63×46）

検知キー：`POKEMON_ZA_MISSION_COMPLETE`

使用箇所：[ZA_story_Template_battle_before_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20514>) / [ZA_story_Template_battle_function_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20915>) / [ZA_story_Template_battle_after_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:21061>) ほか8参照。全参照はHTML・監査JSONに収録。

#### N095　MISSION COMPLETEの文字片 P

![MISSION COMPLETEの文字片 P](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_P.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。 C/M/P/Tの4片中3片一致（AT_LEAST_3）。英字を使わない判定ではない。

画像：`POKEMON_ZA_MISSION_COMPLETE_P.png`（51×46）

検知キー：`POKEMON_ZA_MISSION_COMPLETE`

使用箇所：[ZA_story_Template_battle_before_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20514>) / [ZA_story_Template_battle_function_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20915>) / [ZA_story_Template_battle_after_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:21061>) ほか8参照。全参照はHTML・監査JSONに収録。

#### N096　MISSION COMPLETEの文字片 T

![MISSION COMPLETEの文字片 T](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_T.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。 C/M/P/Tの4片中3片一致（AT_LEAST_3）。英字を使わない判定ではない。

画像：`POKEMON_ZA_MISSION_COMPLETE_T.png`（53×46）

検知キー：`POKEMON_ZA_MISSION_COMPLETE`

使用箇所：[ZA_story_Template_battle_before_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20514>) / [ZA_story_Template_battle_function_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:20915>) / [ZA_story_Template_battle_after_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:21061>) ほか8参照。全参照はHTML・監査JSONに収録。

#### N097　SELECTの先頭S

![SELECTの先頭S](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/SELECT.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`SELECT.png`（46×40）

検知キー：`POKEMON_ZA_SELECT`

使用箇所：[ZA_battle_coCp_noloop](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:16877>) / [ZA_battle_Cp_loop](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:16998>) / [ZA_battle_Cp_loop_move](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:17128>) ほか18参照。全参照はHTML・監査JSONに収録。

#### N098　REWARD

![REWARD](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/X_menu/POKEMON_ZA_REWORD.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`POKEMON_ZA_REWORD.png`（184×24）

検知キー：`POKEMON_ZA_REWORD`

使用箇所：[ZA_mega_mode5_event_attack_blocked](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7288>) / [ZA_battle_reword_recovery](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:16739>)

#### N099　MENU

![MENU](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/X_menu/x_menu_window.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`x_menu_window.png`（328×48）

検知キー：`POKEMON_ZA_X_MENU_OPEN`

使用箇所：[_ZA_gamereset_game_screen](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:5856>) / [_ZA_gamereset_game_screen](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:5870>) / [_ZA_story_shiro_80_reset_debug_ready](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:5878>) ほか35参照。全参照はHTML・監査JSONに収録。

#### N100　Lv

![Lv](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/battle_active_level.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`battle_active_level.png`（20×13）

検知キー：`POKEMON_ZA_BATTLE_ACTIVE_LEVEL`

使用箇所：[_ZA_gamereset_game_screen](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:5871>) / [ZA_mega_mode5_defeat_ui_clear](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:9780>) / [ZA_mega_mode5_indefinite_field_wait_update](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:10127>) ほか26参照。全参照はHTML・監査JSONに収録。

#### N101　BOX

![BOX](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/boxwindow.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`boxwindow.png`（63×18）

検知キー：`POKEMON_ZA_BOX_WINDOW`

使用箇所：[_2_story_absol_move4](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:28030>) / [ZA_common_box_change_box_target1](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35835>) / [ZA_common_box_change_box_target1_select](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35860>) ほか2参照。全参照はHTML・監査JSONに収録。

#### N102　FIN

![FIN](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/fin.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`fin.png`（119×54）

検知キー：`POKEMON_ZA_FIN`

使用箇所：[_8_story_story_last_51](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:35349>)

#### N103　ITEM

![ITEM](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/itemwindow.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`itemwindow.png`（93×19）

検知キー：`POKEMON_ZA_ITEM_WINDOW`

使用箇所：[_6_story_yukari_47](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:32964>) / [_6_story_yukari_48](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:32977>) / [_6_story_yukari_49](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:33028>) ほか4参照。全参照はHTML・監査JSONに収録。

#### N104　MAP

![MAP](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/map2.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`map2.png`（143×29）

検知キー：`POKEMON_ZA_MAP` / `POKEMON_ZA_MAP2`

使用箇所：[ZA_story_furadari_lab_entrance_goto](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:17537>) / [ZA_story_furadari_lab_entrance_goto](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:17655>) / [ZA_story_furadari_black_comment_recovery_step](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:18252>) ほか28参照。全参照はHTML・監査JSONに収録。

#### N105　Z-A ROYALE

![Z-A ROYALE](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/z-a_royale.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`z-a_royale.png`（337×32）

検知キー：`POKEMON_ZA_ZA_ROYALE`

使用箇所：[ZA_story_Template_Comment_Out](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:21810>) / [ZA_story_Template_Comment_Out](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:21915>) / [_2_story_mega_move23](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:29058>) ほか3参照。全参照はHTML・監査JSONに収録。

#### N106　REWARD

![REWARD](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/REWARD.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`REWARD.png`（98×12）

検知キー：`POKEMON_ZA_REWARD_RESULT`

使用箇所：[ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38657>) / [ZA_battle_lockon_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:39082>)

#### N107　Rボタンの一部

![Rボタンの一部](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/R_push.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`R_push.png`（9×24）

検知キー：`POKEMON_ZA_R_push`

使用箇所：[ZA_mega_mode5_event_lockon_bootstrap](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7523>) / [ZA_mega_mode5_event_attack_axby](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:7625>) / [ZA_mega_mode5_rpush_prompt_confirmed](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:9787>) ほか11参照。全参照はHTML・監査JSONに収録。

#### N108　MAX

![MAX](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/chicket_95_118x1122_1268.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`chicket_95_118x1122_1268.png`（146×23）

検知キー：`POKEMON_ZA_CHICKET_MAX_RIGHT`

使用箇所：[ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38440>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38668>)

#### N109　MAX

![MAX](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/ZA_infi/chicket_max.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`chicket_max.png`（166×26）

検知キー：`POKEMON_ZA_CHICKET_MAX`

使用箇所：[ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38668>) / [ZA_battle_move_test](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:38669>)

#### N110　PROFILE

![PROFILE](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_0_Start/Profile.png)

**現在の状態**：英字／略字を含む。非文字への置換設定はない。

日本語版でもこの表記。他言語でも同じ字形・配置かは今回未確認であり、翻訳用画像が必須とは断定しない。

画像：`Profile.png`（177×20）

検知キー：`POKEMON_ZA_PROFILE`

使用箇所：[main_0_start](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22692>) / [main_0_start](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22693>) / [main_0_start](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:22699>)

## 既存の代用・別経路があるため主対象から除外

#### N111　進化する／つよさをみる／回復する

![進化する／つよさをみる／回復する](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/X_menu/POKEMON_ZA_X_MENU_EVO_MENU.png)

**現在の状態**：追補：補足モードで選択位置・枠・カーソルによる代用を追加。画像取得ONなら同じフレームの全画面と日本語ROIを保存する。進化を先に済ませる既存の順序が前提。

**初回調査時の状態**：2_SELECTとのOR・形状差あり

進化実行では2_SELECTとのORがある。進化後の整理処理でも参照されるため、全場面で不要になった画像とは扱わない。

画像：`POKEMON_ZA_X_MENU_EVO_MENU.png`（196×159）

検知キー：`POKEMON_ZA_X_MENU_EVO_MENU`

使用箇所：[ZA_common_evolution_exec.evolution_confirm_visible](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36019>) / [ZA_common_evolution_loop](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36093>)

既存のPIC／代用候補：

![2_select.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/2_select.png)

[ZIPの保存フレームで一致した場面（前回調査）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/POKEMON_ZA_X_MENU_EVO_MENU.jpg>)

#### N112　そのまま見守る／やめる

![そのまま見守る／やめる](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/evolution_2_select.png)

**現在の状態**：2_SELECTとのOR・形状差あり

進化確認はEVOLUTION_CONFIRM／X_MENU_EVO_MENU／2_SELECTのOR。2_SELECTは非文字の枠だが、専用画面との形状差がソースに明記されており、代用の実機確認が必要。

画像：`evolution_2_select.png`（212×120）

検知キー：`POKEMON_ZA_EVOLUTION_CONFIRM`

使用箇所：[ZA_common_evolution_exec.evolution_confirm_visible](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:36018>)

既存のPIC／代用候補：

![2_select.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/2_select.png)

#### N113　やったな！

![やったな！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/2get_success.png)

**現在の状態**：捕獲アイコンで進行可能

OUT_HOTEL_Z_16はヤヤコマ＋ホルビーの手持ちアイコンで次Stepへ進む。「やったな！」不一致時も同じ会話終了処理がある。

画像：`2get_success.png`（125×33）

検知キー：`POKEMON_ZA_TEXT_2_GET_SUCCESS`

使用箇所：[_1_story_out_hotel_z_16](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:23531>)

既存のPIC／代用候補：

![yayakomaicon.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/yayakomaicon.png)

![horubiiicon.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/horubiiicon.png)

#### N114　ZL：狙う／X・A：技を指示

![ZL：狙う／X・A：技を指示](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/farst_battle_field_hud.png)

**現在の状態**：HARD FIELDとのOR

初戦敗北後の戦闘再開はLv表示 AND（HARD FIELD 0 OR このHUD）。日本語HUDを通らない経路はあるが、Lv表示の条件は残る。

画像：`farst_battle_field_hud.png`（129×51）

検知キー：`POKEMON_ZA_FARST_BATTLE_FIELD_HUD`

使用箇所：[_1_story_farst_battle_lose.battle_field_ready](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:23070>)

#### N115　捕獲チャンスだ！ いまのうちに捕まえろ！

![捕獲チャンスだ！ いまのうちに捕まえろ！](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/getchance_comment.png)

**現在の状態**：別経路あり・文字分岐も残る

初回の白Commentを閉じた後はGETCHANCE_ICON4で捕獲可能。文字一致時だけ即座に捕獲する分岐も残るため、文字判定そのものの完全置換ではない。

画像：`getchance_comment.png`（303×91）

検知キー：`POKEMON_ZA_TEXT_2_GETCHANCE`

使用箇所：[_1_story_out_hotel_z_16](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:23527>)

既存のPIC／代用候補：

![getmerker4.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/getmerker4.png)

#### N116　ホテルZ

![ホテルZ](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/_1_z_lank/out_hotel_z45_hotel_z_text.png)

**現在の状態**：入口アイコンとのOR

IN_ICONとホテルZの文字がOR。文字は入口アイコンの一致不足を補うため追加された経緯があり、他言語でアイコンだけが安定するとは未確認。

画像：`out_hotel_z45_hotel_z_text.png`（51×24）

検知キー：`POKEMON_ZA_OUT_HOTEL_Z45_HOTEL_Z_TEXT`

使用箇所：[_1_story_out_hotel_z_45](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py:24426>)

既存のPIC／代用候補：

![in_icon.png](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/non_a_reference_templates/Common/in_icon.png)

## 確認方法・出典

現行ソース SHA256：`6cb92bb3a4d25d8ce968d1e3a32d5c46b6c8f59a8666856df9c186b35e86df37`。登録304対象・322パターン・226画像をASTで読み、関数内の直接PNG参照も確認。旧版と共通の220画像は参照控えとSHA256一致。追加登録6画像のうち4枚が文字入り、2枚は捕獲アイコン。直接照合の新規5枚も追加した。

単純なORに日本語画像が複数ある場合、非文字の代用とは数えない。再挑戦の枠検知、HP引き継ぎの文字照合、マップ名とPICのAND、10・18番の数字詳細の接続を別々に確認した。

画像とソースは一覧作成時点の控え。稼働中プロセスのロード状態・他言語ゲームの実行結果は今回の確認対象外。ゲーム入力・PokeCon停止・Reload・録画／音声処理の変更は行っていない。

[監査データ（画像ごとの全参照と設定）](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/data/non_a_word_checks.json>)

[一覧作成時点のZA_storyソース](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/current_ZA_story_non_a_20261024.py>)
