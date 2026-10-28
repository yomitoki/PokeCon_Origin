# ZA_Story：文字を含む検知画像の全使用箇所

対象はZIPに保存されたZA_story.py。行番号リンクは同梱した録画時ソースを指す。画像はZIP内の参照名に対応するローカルPNGの控えであり、ZIPにPNGそのものは含まれない。
「関数の記録あり」はその関数が録画のステップ／スタックに出現した意味で、各ifの成立やその文字画像の一致を証明しない。
同じ画像が複数の状態で使われるため、画像枚数と使用行数は異なる。画像の英字・数字・漢字片・ボタン記号も後半に含む。

## 2_select_tutorial.png

- 分類：選択肢・再挑戦／日本語の単語・文章
- 主な表示：再挑戦する／アドバイス
- 画像：[Template/ZA_Story/Common/2_select_tutorial.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/2_select_tutorial.png>)
- 検知キー：`POKEMON_ZA_2_SELECT_TUTORIAL`
- 対応時の論点：選択肢の内容を識別する文字。枠やカーソルだけで意味を置き換えない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_field_post_attack_roll_if_needed:3055](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3055>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:12895](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12895>) | `image_check` | あり |
| [ZA_mega_evolution_battle:13042](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13042>) | `image_check` | あり |
| [image_check_confirmation:40210](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:40210>) | `default_or_condition` | あり |


## 3_select_select.png

- 分類：選択肢・再挑戦／日本語の単語・文章
- 主な表示：選んで再挑戦／選ばず再挑戦／もどる
- 画像：[Template/ZA_Story/Common/3_select_select.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/3_select_select.png>)
- 検知キー：`POKEMON_ZA_3_SELECT_SELECT`
- 対応時の論点：選択肢の内容を識別する文字。枠やカーソルだけで意味を置き換えない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_field_post_attack_roll_if_needed:3056](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3056>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:12910](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12910>) | `image_check` | あり |
| [ZA_mega_evolution_battle:13068](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13068>) | `image_check` | あり |
| [image_check_confirmation:40212](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:40212>) | `default_or_condition` | あり |


## 3_select_tutorial.png

- 分類：選択肢・再挑戦／日本語の単語・文章
- 主な表示：再挑戦する／準備して再挑戦／あきらめる
- 画像：[Template/ZA_Story/Common/3_select_tutorial.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/3_select_tutorial.png>)
- 検知キー：`POKEMON_ZA_3_SELECT_TUTORIAL`
- 対応時の論点：選択肢の内容を識別する文字。枠やカーソルだけで意味を置き換えない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_field_post_attack_roll_if_needed:3057](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3057>) | `default_or_condition` | あり |
| [ZA_mega_mode5_event_attack_blocked:3916](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3916>) | `next` | あり |
| [ZA_mega_mode5_defeat_candidate_picture:6428](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6428>) | `next` | あり |
| [ZA_mega_last_battle_tutorial_confirmed:6847](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6847>) | `ZA_mega_mode5_defeat_select_check` | 見つからず |
| [ZA_mega_mode5_a_attack_ready:7773](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7773>) | `next` | あり |
| [ZA_mega_mode5_field_w_up_retry:7937](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7937>) | `default_or_condition` | 見つからず |
| [ZA_mega_evolution_battle:12879](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12879>) | `ZA_mega_mode5_defeat_select_check` | あり |
| [ZA_mega_evolution_battle:12998](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12998>) | `ZA_mega_mode5_defeat_select_confirmed` | あり |
| [ZA_mega_evolution_battle:13009](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13009>) | `ZA_mega_mode5_set_start_flag` | あり |
| [image_check_confirmation:40213](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:40213>) | `default_or_condition` | あり |


## C+.png

- 分類：ボタン・略字・記号／ボタン記号・略字
- 主な表示：C+
- 画像：[Template/ZA_Story/Common/C+.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/C+.png>)
- 検知キー：`POKEMON_ZA_C+`, `POKEMON_ZA_C+_LOW`
- 対応時の論点：日本語の単語ではないが、文字状の要素。単語一覧の主件数とは分ける。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_skill_attack_ready:7827](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7827>) | `image_check` | あり |
| [ZA_mega_mode5_skill_attack_ready:7828](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7828>) | `image_check` | あり |
| [ZA_mega_attack_ready:7850](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7850>) | `image_check` | あり |
| [ZA_mega_attack_ready:7851](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7851>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12136](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12136>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12137](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12137>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12199](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12199>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12205](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12205>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12211](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12211>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12232](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12232>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12239](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12239>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12245](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12245>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12296](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12296>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12302](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12302>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12308](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12308>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12336](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12336>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12342](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12342>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12348](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12348>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12572](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12572>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12574](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12574>) | `image_check` | あり |
| [ZA_battle_Cp_loop:13293](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13293>) | `image_check` | あり |
| [ZA_battle_Cp_loop:13294](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13294>) | `image_check` | あり |
| [ZA_battle_Cp_loop_move:13478](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13478>) | `image_check` | あり |
| [cplus_ready:13478](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13478>) | `image_check` | あり |
| [ZA_battle_Cp_loop_move:13479](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13479>) | `image_check` | あり |
| [cplus_ready:13479](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13479>) | `image_check` | あり |
| [ZA_infi_attack_ready:31942](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31942>) | `image_check` | あり |
| [ZA_infi_attack_ready:31943](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31943>) | `image_check` | あり |


## C+_white.png

- 分類：ボタン・略字・記号／ボタン記号・略字
- 主な表示：C+
- 画像：[Template/ZA_Story/Common/C+_white.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/C+_white.png>)
- 検知キー：`POKEMON_ZA_C+`, `POKEMON_ZA_C+_LOW`
- 対応時の論点：日本語の単語ではないが、文字状の要素。単語一覧の主件数とは分ける。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_skill_attack_ready:7827](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7827>) | `image_check` | あり |
| [ZA_mega_mode5_skill_attack_ready:7828](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7828>) | `image_check` | あり |
| [ZA_mega_attack_ready:7850](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7850>) | `image_check` | あり |
| [ZA_mega_attack_ready:7851](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7851>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12136](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12136>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12137](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12137>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12199](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12199>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12205](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12205>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12211](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12211>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12232](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12232>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12239](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12239>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12245](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12245>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12296](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12296>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12302](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12302>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12308](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12308>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12336](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12336>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12342](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12342>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12348](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12348>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12572](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12572>) | `image_check` | あり |
| [ZA_mega_evolution_battle:12574](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12574>) | `image_check` | あり |
| [ZA_battle_Cp_loop:13293](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13293>) | `image_check` | あり |
| [ZA_battle_Cp_loop:13294](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13294>) | `image_check` | あり |
| [ZA_battle_Cp_loop_move:13478](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13478>) | `image_check` | あり |
| [cplus_ready:13478](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13478>) | `image_check` | あり |
| [ZA_battle_Cp_loop_move:13479](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13479>) | `image_check` | あり |
| [cplus_ready:13479](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13479>) | `image_check` | あり |
| [ZA_infi_attack_ready:31942](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31942>) | `image_check` | あり |
| [ZA_infi_attack_ready:31943](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31943>) | `image_check` | あり |


## POKEMON_ZA_MISSION_COMPLETE_C.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：MISSION COMPLETEの文字片 C
- 画像：[Template/ZA_Story/Common/POKEMON_ZA_MISSION_COMPLETE_C.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_C.png>)
- 検知キー：`POKEMON_ZA_MISSION_COMPLETE`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_story_Template_battle_before_active_level:15770](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15770>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function_active_level:16065](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16065>) | `image_check` | あり |
| [ZA_story_Template_battle_after_active_level:16178](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16178>) | `image_check` | 見つからず |
| [_ZA_story_battle_before_safe_renda_once:16272](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16272>) | `image_check` | あり |
| [_ZA_story_battle_before_safe_renda_once:16273](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16273>) | `default_or_condition` | あり |
| [ZA_story_Template_Comment_Out:16795](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16795>) | `image_check` | あり |
| [ZA_story_Template_Comment_Out:16887](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16887>) | `image_check` | あり |
| [ZA_story_Template_Comment_Out:16940](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16940>) | `image_check` | あり |
| [_2_story_absol_move18:22994](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22994>) | `ZA_story_Template_battle_function_renda_route` | あり |
| [_8_story_story_last_32:29329](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29329>) | `image_check` | あり |


## POKEMON_ZA_MISSION_COMPLETE_M.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：MISSION COMPLETEの文字片 M
- 画像：[Template/ZA_Story/Common/POKEMON_ZA_MISSION_COMPLETE_M.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_M.png>)
- 検知キー：`POKEMON_ZA_MISSION_COMPLETE`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_story_Template_battle_before_active_level:15770](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15770>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function_active_level:16065](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16065>) | `image_check` | あり |
| [ZA_story_Template_battle_after_active_level:16178](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16178>) | `image_check` | 見つからず |
| [_ZA_story_battle_before_safe_renda_once:16272](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16272>) | `image_check` | あり |
| [_ZA_story_battle_before_safe_renda_once:16273](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16273>) | `default_or_condition` | あり |
| [ZA_story_Template_Comment_Out:16795](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16795>) | `image_check` | あり |
| [ZA_story_Template_Comment_Out:16887](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16887>) | `image_check` | あり |
| [ZA_story_Template_Comment_Out:16940](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16940>) | `image_check` | あり |
| [_2_story_absol_move18:22994](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22994>) | `ZA_story_Template_battle_function_renda_route` | あり |
| [_8_story_story_last_32:29329](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29329>) | `image_check` | あり |


## POKEMON_ZA_MISSION_COMPLETE_P.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：MISSION COMPLETEの文字片 P
- 画像：[Template/ZA_Story/Common/POKEMON_ZA_MISSION_COMPLETE_P.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_P.png>)
- 検知キー：`POKEMON_ZA_MISSION_COMPLETE`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_story_Template_battle_before_active_level:15770](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15770>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function_active_level:16065](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16065>) | `image_check` | あり |
| [ZA_story_Template_battle_after_active_level:16178](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16178>) | `image_check` | 見つからず |
| [_ZA_story_battle_before_safe_renda_once:16272](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16272>) | `image_check` | あり |
| [_ZA_story_battle_before_safe_renda_once:16273](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16273>) | `default_or_condition` | あり |
| [ZA_story_Template_Comment_Out:16795](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16795>) | `image_check` | あり |
| [ZA_story_Template_Comment_Out:16887](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16887>) | `image_check` | あり |
| [ZA_story_Template_Comment_Out:16940](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16940>) | `image_check` | あり |
| [_2_story_absol_move18:22994](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22994>) | `ZA_story_Template_battle_function_renda_route` | あり |
| [_8_story_story_last_32:29329](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29329>) | `image_check` | あり |


## POKEMON_ZA_MISSION_COMPLETE_T.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：MISSION COMPLETEの文字片 T
- 画像：[Template/ZA_Story/Common/POKEMON_ZA_MISSION_COMPLETE_T.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/POKEMON_ZA_MISSION_COMPLETE_T.png>)
- 検知キー：`POKEMON_ZA_MISSION_COMPLETE`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_story_Template_battle_before_active_level:15770](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15770>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function_active_level:16065](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16065>) | `image_check` | あり |
| [ZA_story_Template_battle_after_active_level:16178](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16178>) | `image_check` | 見つからず |
| [_ZA_story_battle_before_safe_renda_once:16272](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16272>) | `image_check` | あり |
| [_ZA_story_battle_before_safe_renda_once:16273](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16273>) | `default_or_condition` | あり |
| [ZA_story_Template_Comment_Out:16795](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16795>) | `image_check` | あり |
| [ZA_story_Template_Comment_Out:16887](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16887>) | `image_check` | あり |
| [ZA_story_Template_Comment_Out:16940](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16940>) | `image_check` | あり |
| [_2_story_absol_move18:22994](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22994>) | `ZA_story_Template_battle_function_renda_route` | あり |
| [_8_story_story_last_32:29329](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29329>) | `image_check` | あり |


## SELECT.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：SELECTの先頭S
- 画像：[Template/ZA_Story/Common/SELECT.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/SELECT.png>)
- 検知キー：`POKEMON_ZA_SELECT`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_battle_coCp_noloop:13246](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13246>) | `image_check` | あり |
| [ZA_battle_Cp_loop:13367](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13367>) | `image_check` | あり |
| [ZA_battle_Cp_loop_move:13497](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13497>) | `image_check` | あり |
| [ZA_bench_map_open:31424](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31424>) | `image_check` | あり |
| [ZA_infi_guarded_ladder_climb:31953](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31953>) | `image_check` | あり |
| [ZA_infi_stalled_ladder_recovery:31986](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31986>) | `image_check` | あり |
| [ZA_battle_move_test:32230](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32230>) | `image_check` | あり |
| [ZA_battle_move_test:32337](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32337>) | `image_check` | あり |
| [ZA_battle_move_test:32477](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32477>) | `image_check` | あり |
| [ZA_battle_move_test:32529](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32529>) | `image_check` | あり |
| [ZA_battle_move_test:32763](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32763>) | `image_check` | あり |
| [ZA_battle_move_test:32821](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32821>) | `image_check` | あり |
| [ZA_battle_move_test:32855](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32855>) | `image_check` | あり |
| [ZA_battle_move_test:32884](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32884>) | `image_check` | あり |
| [ZA_battle_move_test:32950](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32950>) | `image_check` | あり |
| [ZA_battle_move_test:32985](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32985>) | `image_check` | あり |
| [ZA_battle_lockon_test:33103](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33103>) | `image_check` | あり |
| [ZA_battle_lockon_test:33144](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33144>) | `image_check` | あり |
| [ZA_battle_lockon_test:33182](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33182>) | `image_check` | あり |
| [ZA_battle_lockon_test:33234](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33234>) | `image_check` | あり |
| [ZA_battle_lockon_test:33269](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33269>) | `image_check` | あり |


## POKEMON_ZA_REWORD.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：REWARD
- 画像：[Template/ZA_Story/Common/X_menu/POKEMON_ZA_REWORD.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/X_menu/POKEMON_ZA_REWORD.png>)
- 検知キー：`POKEMON_ZA_REWORD`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_event_attack_blocked:3905](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3905>) | `next` | あり |
| [ZA_battle_reword_recovery:13116](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13116>) | `image_check` | あり |


## POKEMON_ZA_X_MENU_EVO_MENU.png

- 分類：メニュー・技・道具／日本語の単語・文章
- 主な表示：進化する／つよさをみる／回復する
- 画像：[Template/ZA_Story/Common/X_menu/POKEMON_ZA_X_MENU_EVO_MENU.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/X_menu/POKEMON_ZA_X_MENU_EVO_MENU.png>)
- 検知キー：`POKEMON_ZA_X_MENU_EVO_MENU`
- 対応時の論点：メニュー内容・技名・道具名を含む。道具や技の小アイコンは他項目との区別を別途確認する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_common_evolution_exec:30248](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30248>) | `image_check` | あり |
| [evolution_confirm_visible:30248](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30248>) | `image_check` | あり |
| [ZA_common_evolution_loop:30322](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30322>) | `image_check` | あり |


## pokemon_menu.png

- 分類：メニュー・技・道具／日本語の単語・文章
- 主な表示：つよさをみる／回復する／使えるわざを選ぶ
- 画像：[Template/ZA_Story/Common/X_menu/pokemon_menu.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/X_menu/pokemon_menu.png>)
- 検知キー：`POKEMON_ZA_POKEMON_MENU_X_MENU_W`
- 対応時の論点：メニュー内容・技名・道具名を含む。道具や技の小アイコンは他項目との区別を別途確認する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_1_story_out_hotel_z_33:19013](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:19013>) | `image_check` | あり |
| [ZA_common_skill_change_start_check:29730](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29730>) | `image_check` | あり |
| [ZA_common_skill_change_pokemon_select:29780](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29780>) | `image_check` | あり |
| [ZA_common_skill_change_skill_window_open:29790](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29790>) | `image_check` | あり |
| [ZA_common_box_change_box_open:30056](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30056>) | `image_check` | あり |
| [ZA_common_item_give_window_open:30171](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30171>) | `image_check` | あり |
| [ZA_common_evolution_exec:30256](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30256>) | `image_check` | あり |
| [close_target_visible:30256](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30256>) | `image_check` | 見つからず |
| [ZA_common_evolution_loop:30321](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30321>) | `image_check` | あり |
| [ZA_common_item_use_window_open:30378](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30378>) | `image_check` | あり |


## pokemon_menu_select_skill.png

- 分類：メニュー・技・道具／日本語の単語・文章
- 主な表示：つよさをみる／回復する／使えるわざを選ぶ（選択位置違い）
- 画像：[Template/ZA_Story/Common/X_menu/pokemon_menu_select_skill.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/X_menu/pokemon_menu_select_skill.png>)
- 検知キー：`POKEMON_ZA_POKEMON_MENU_X_MENU_W_SELECT_SKILL`
- 対応時の論点：メニュー内容・技名・道具名を含む。道具や技の小アイコンは他項目との区別を別途確認する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_common_skill_change_start_check:29732](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29732>) | `image_check` | あり |
| [ZA_common_skill_change_skill_window_open:29794](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29794>) | `image_check` | あり |
| [ZA_common_evolution_exec:30255](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30255>) | `image_check` | あり |
| [close_target_visible:30255](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30255>) | `image_check` | 見つからず |
| [ZA_common_evolution_loop:30320](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30320>) | `image_check` | あり |


## skillpage.png

- 分類：メニュー・技・道具／日本語の単語・文章
- 主な表示：覚えているわざ
- 画像：[Template/ZA_Story/Common/X_menu/skillpage.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/X_menu/skillpage.png>)
- 検知キー：`POKEMON_ZA_SKILL_PAGE_WINDOW`
- 対応時の論点：メニュー内容・技名・道具名を含む。道具や技の小アイコンは他項目との区別を別途確認する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_common_skill_change_start_check:29734](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29734>) | `image_check` | あり |
| [ZA_common_skill_change_skill_window_chtarget1:29816](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29816>) | `image_check` | あり |
| [ZA_common_skill_change_skill_window_chtarget1:29857](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29857>) | `image_check` | あり |
| [ZA_common_skill_change_skill_window_chtarget2:29946](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29946>) | `image_check` | あり |
| [ZA_common_evolution_exec:30253](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30253>) | `image_check` | あり |
| [close_target_visible:30253](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30253>) | `image_check` | 見つからず |
| [ZA_common_evolution_loop:30318](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30318>) | `image_check` | あり |


## x_menu_window.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：MENU
- 画像：[Template/ZA_Story/Common/X_menu/x_menu_window.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/X_menu/x_menu_window.png>)
- 検知キー：`POKEMON_ZA_X_MENU_OPEN`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_event_attack_blocked:3904](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3904>) | `next` | あり |
| [ZA_mega_mode5_x_menu_b_recovery:6494](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6494>) | `image_check` | あり |
| [ZA_mega_mode5_x_menu_b_recovery:6511](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6511>) | `image_check` | あり |
| [ZA_mega_mode5_x_menu_b_recovery:6517](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6517>) | `image_check` | あり |
| [ZA_mega_mode5_field_w_up_retry:7929](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7929>) | `image_check` | 見つからず |
| [ZA_mega_mode5_field_w_up_retry:7970](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7970>) | `image_check` | 見つからず |
| [ZA_mega_mode5_field_w_up_retry:7984](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7984>) | `image_check` | 見つからず |
| [ZA_battle_missing_field_recovery:13145](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13145>) | `image_check` | あり |
| [ZA_battle_missing_field_recovery:13188](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13188>) | `image_check` | あり |
| [ZA_story_Template_battle_function:15253](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15253>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function:15279](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15279>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_after:15506](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15506>) | `default_or_condition` | 見つからず |
| [ZA_story_Template_battle_before_active_level:15716](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15716>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function_active_level:15891](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15891>) | `image_check` | あり |
| [ZA_story_Template_battle_after_active_level:16194](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16194>) | `image_check` | 見つからず |
| [_ZA_story_battle_before_safe_renda_once:16283](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16283>) | `image_check` | あり |
| [_1_story_out_hotel_z_33:19002](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:19002>) | `image_check` | あり |
| [_2_story_restaurant_dohutsu_loop:23170](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23170>) | `image_check` | あり |
| [_8_story_story_last_32:29331](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29331>) | `image_check` | あり |
| [ZA_common_skill_change_start_check:29724](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29724>) | `image_check` | あり |
| [ZA_common_skill_change_start_check:29754](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29754>) | `image_check` | あり |
| [ZA_common_skill_change_pokemon_select:29770](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29770>) | `image_check` | あり |
| [ZA_common_skill_change_skill_window_open:29789](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29789>) | `image_check` | あり |
| [ZA_common_box_change_box_open:30046](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30046>) | `image_check` | あり |
| [ZA_common_item_give_window_open:30170](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30170>) | `image_check` | あり |
| [ZA_common_evolution_exec:30290](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30290>) | `image_check` | あり |
| [ZA_common_evolution_loop:30317](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30317>) | `image_check` | あり |
| [ZA_common_item_use_window_open:30370](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30370>) | `image_check` | あり |


## ZA_RESEARCH_A.png

- 分類：フィールドの操作表示／日本語の単語・文章
- 主な表示：A 調べる
- 画像：[Template/ZA_Story/Common/ZA_RESEARCH_A.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/ZA_RESEARCH_A.png>)
- 検知キー：`ZA_STORY_COMMON_ZA_RESEARCH_A`
- 対応時の論点：Aボタン単体は複数の操作で共通。文字を除去すると操作の意味を区別できるかを別途検証する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_7_story_guri_95:28544](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28544>) | `image_check` | あり |
| [_7_story_guri_98:28570](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28570>) | `image_check` | 見つからず |
| [_7_story_guri_102:28603](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28603>) | `image_check` | あり |
| [_7_story_guri_106:28643](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28643>) | `image_check` | あり |
| [_7_story_guri_106:28647](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28647>) | `image_check` | あり |
| [_7_story_guri_109:28678](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28678>) | `image_check` | あり |
| [_7_story_guri_109:28682](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28682>) | `image_check` | あり |


## ame_s.png

- 分類：メニュー・技・道具／日本語の単語・文章
- 主な表示：けいけんアメS
- 画像：[Template/ZA_Story/Common/ame_s.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/ame_s.png>)
- 検知キー：`POKEMON_ZA_AME_S`
- 対応時の論点：メニュー内容・技名・道具名を含む。道具や技の小アイコンは他項目との区別を別途確認する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_ame1:23254](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23254>) | `ZA_common_item_use_function` | あり |
| [_2_story_ame2:23261](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23261>) | `ZA_common_item_use_function` | あり |


## battle_active_level.png

- 分類：ボタン・略字・記号／ボタン記号・略字
- 主な表示：Lv
- 画像：[Template/ZA_Story/Common/battle_active_level.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/battle_active_level.png>)
- 検知キー：`POKEMON_ZA_BATTLE_ACTIVE_LEVEL`
- 対応時の論点：日本語の単語ではないが、文字状の要素。単語一覧の主件数とは分ける。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_defeat_ui_clear:6372](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6372>) | `any` | あり |
| [ZA_mega_mode5_indefinite_field_wait_update:6719](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6719>) | `image_check` | あり |
| [ZA_mega_normal_choice_black_background_state:7606](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7606>) | `any` | あり |
| [ZA_battle_missing_field_recovery:13160](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13160>) | `image_check` | あり |
| [ZA_story_furadari_black_comment_recovery_step:14300](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14300>) | `next` | あり |
| [guri_battle_picture:14300](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14300>) | `next` | あり |
| [ZA_story_event_entry_recovery_step:14886](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14886>) | `default_or_condition` | あり |
| [observed_image_check:14886](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14886>) | `default_or_condition` | あり |
| [ZA_story_Template_battle_after:15520](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15520>) | `image_check` | 見つからず |
| [_ZA_story_guri_select_defeat_observe:15661](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15661>) | `next` | 見つからず |
| [ZA_story_Template_battle_before_active_level:15707](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15707>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function_active_level:15869](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15869>) | `image_check` | あり |
| [ZA_story_Template_battle_after_active_level:16172](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16172>) | `image_check` | 見つからず |
| [_ZA_story_battle_before_safe_renda_once:16245](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16245>) | `image_check` | あり |
| [_ZA_story_battle_before_safe_renda_once:16246](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16246>) | `default_or_condition` | あり |
| [_ZA_story_battle_after_safe_renda:16627](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16627>) | `default_or_condition` | あり |
| [_8_story_story_last_15:29047](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29047>) | `image_check` | あり |
| [_8_story_story_last_22:29111](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29111>) | `image_check` | あり |
| [_8_story_story_last_28:29238](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29238>) | `image_check` | あり |
| [_8_story_story_last_32:29317](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29317>) | `image_check` | あり |
| [_8_story_story_last_40:29460](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29460>) | `image_check` | あり |
| [_8_story_story_last_40_1:29467](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29467>) | `image_check` | 見つからず |
| [image_check_confirmation:40225](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:40225>) | `image_check` | あり |


## boxmenu.png

- 分類：メニュー・技・道具／日本語の単語・文章
- 主な表示：移動する／つよさをみる／使えるわざを選ぶ／もちものを持たせる／ニックネーム／マーキング／やめる
- 画像：[Template/ZA_Story/Common/boxmenu.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/boxmenu.png>)
- 検知キー：`POKEMON_ZA_BOX_MENU`
- 対応時の論点：メニュー内容・技名・道具名を含む。道具や技の小アイコンは他項目との区別を別途確認する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_absol_move4:22671](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22671>) | `image_check` | あり |
| [ZA_common_box_change_box_target1_select:30091](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30091>) | `image_check` | あり |


## boxwindow.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：BOX
- 画像：[Template/ZA_Story/Common/boxwindow.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/boxwindow.png>)
- 検知キー：`POKEMON_ZA_BOX_WINDOW`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_absol_move4:22669](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22669>) | `image_check` | あり |
| [ZA_common_box_change_box_target1:30064](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30064>) | `image_check` | あり |
| [ZA_common_box_change_box_target1_select:30089](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30089>) | `image_check` | あり |
| [ZA_common_box_change_box_target2:30103](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30103>) | `image_check` | あり |
| [ZA_common_box_change_window_close:30128](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30128>) | `image_check` | あり |


## chatmarker.png

- 分類：フィールドの操作表示／日本語の単語・文章
- 主な表示：A 話しかける
- 画像：[Template/ZA_Story/Common/chatmarker.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/chatmarker.png>)
- 検知キー：`POKEMON_ZA_CHAT_MARKER`
- 対応時の論点：Aボタン単体は複数の操作で共通。文字を除去すると操作の意味を区別できるかを別途検証する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_story_Template_battle_function:15332](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15332>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function:15365](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15365>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function:15387](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15387>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function:15406](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15406>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_after:15495](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15495>) | `default_or_condition` | 見つからず |
| [ZA_story_Template_battle_before_active_level:15775](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15775>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_before_active_level:15788](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15788>) | `image_check` | 見つからず |
| [ZA_story_Template_battle_function_active_level:16049](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16049>) | `image_check` | あり |
| [ZA_story_Template_battle_after_active_level:16209](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16209>) | `image_check` | 見つからず |
| [_ZA_story_battle_before_safe_renda_once:16276](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16276>) | `image_check` | あり |
| [_ZA_story_battle_before_safe_renda_once:16277](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16277>) | `default_or_condition` | あり |
| [ZA_story_Template_battle_before_renda_route:16474](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16474>) | `image_check` | あり |
| [ZA_story_Template_battle_before_renda_route:16516](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16516>) | `image_check` | あり |
| [ZA_story_Template_battle_before_renda_route:16529](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16529>) | `image_check` | あり |
| [_1_story_bag_chase_end:17884](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17884>) | `ZA_renda_button` | あり |
| [_1_story_farst_pokemon_select:17965](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17965>) | `image_check` | あり |
| [_1_story_farst_pokemon_select:17982](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17982>) | `image_check` | あり |
| [_1_story_out_hotel_z_6:18306](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:18306>) | `image_check` | あり |
| [_5_story_karasuba_62:26097](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26097>) | `image_check` | あり |
| [_5_story_karasuba_121:26804](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26804>) | `image_check` | 見つからず |
| [_5_story_karasuba_121:26810](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26810>) | `image_check` | 見つからず |
| [_5_story_karasuba_121:26816](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26816>) | `image_check` | 見つからず |
| [_6_story_yukari_22:27070](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27070>) | `image_check` | あり |
| [_6_story_yukari_22:27078](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27078>) | `image_check` | あり |
| [_6_story_yukari_22:27085](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27085>) | `image_check` | あり |
| [_8_story_story_last_32:29323](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29323>) | `image_check` | あり |


## evolution_2_select.png

- 分類：選択肢・再挑戦／日本語の単語・文章
- 主な表示：そのまま見守る／やめる
- 画像：[Template/ZA_Story/Common/evolution_2_select.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/evolution_2_select.png>)
- 検知キー：`POKEMON_ZA_EVOLUTION_CONFIRM`
- 対応時の論点：選択肢の内容を識別する文字。枠やカーソルだけで意味を置き換えない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_common_evolution_exec:30247](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30247>) | `image_check` | あり |
| [evolution_confirm_visible:30247](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30247>) | `image_check` | あり |


## fin.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：FIN
- 画像：[Template/ZA_Story/Common/fin.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/fin.png>)
- 検知キー：`POKEMON_ZA_FIN`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_8_story_story_last_51:29582](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29582>) | `ZA_renda_button` | あり |


## furadari_eyes_dark_comment.png

- 分類：敗北・降参・報酬／日本語の単語・文章
- 主な表示：目の前がまっくらになった！
- 画像：[Template/ZA_Story/Common/furadari_eyes_dark_comment.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/furadari_eyes_dark_comment.png>)
- 検知キー：`POKEMON_ZA_FURADARI_EYES_DARK_COMMENT`
- 対応時の論点：会話枠や下向き矢印の有無だけでは敗北・降参・報酬の意味を区別できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_ZA_furadari_eyes_dark_comment_visible:13859](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13859>) | `image_check` | 見つからず |
| [ZA_story_furadari_black_comment_recovery_step:14076](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14076>) | `image_check` | あり |
| [eyes_dark_is_visible:14076](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14076>) | `image_check` | 見つからず |


## furadari_map.png

- 分類：マップの種類・共通操作／日本語の単語・文章
- 主な表示：フラダリラボ
- 画像：[Template/ZA_Story/Common/furadari_map.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/furadari_map.png>)
- 検知キー：`POKEMON_ZA_FURADARI_MAP`
- 対応時の論点：移動先の写真とは別の文字依存。成功確認と移動禁止警告は別条件のまま識別が必要。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_story_furadari_lab_entrance_goto:13904](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13904>) | `image_check` | あり |
| [ZA_story_furadari_lab_entrance_goto:13910](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13910>) | `ZA_Common_goto` | あり |
| [ZA_story_furadari_lab_entrance_goto:14022](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14022>) | `image_check` | あり |
| [ZA_story_furadari_lab_entrance_goto:14028](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14028>) | `ZA_Common_goto` | あり |
| [ZA_story_furadari_black_comment_recovery_step:14603](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14603>) | `image_check` | あり |
| [ZA_story_furadari_black_comment_recovery_step:14609](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14609>) | `ZA_Common_goto` | あり |
| [ZA_Common_goto_jump:30671](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30671>) | `default_or_condition` | あり |
| [ZA_Common_furadari_map_dark_recovery:30746](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30746>) | `default_or_condition` | 見つからず |


## hashigomarker.png

- 分類：フィールドの操作表示／日本語の単語・文章
- 主な表示：A のぼる
- 画像：[Template/ZA_Story/Common/hashigomarker.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/hashigomarker.png>)
- 検知キー：`POKEMON_ZA_HASHIGO_ICON`
- 対応時の論点：Aボタン単体は複数の操作で共通。文字を除去すると操作の意味を区別できるかを別途検証する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_1_story_out_hotel_z_4:18277](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:18277>) | `image_check` | あり |


## inmarker.png

- 分類：フィールドの操作表示／日本語の単語・文章
- 主な表示：A はいる
- 画像：[Template/ZA_Story/Common/inmarker.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/inmarker.png>)
- 検知キー：`POKEMON_ZA_IN_MARKER`
- 対応時の論点：Aボタン単体は複数の操作で共通。文字を除去すると操作の意味を区別できるかを別途検証する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_1_story_hote_z_move2:18092](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:18092>) | `image_check` | 見つからず |
| [_1_story_out_hotel_z_45:19240](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:19240>) | `image_check` | あり |
| [_1_story_out_hotel_z_46:19279](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:19279>) | `image_check` | あり |


## investigate_marker.png

- 分類：フィールドの操作表示／日本語の単語・文章
- 主な表示：A 調べる（暗い表示）
- 画像：[Template/ZA_Story/Common/investigate_marker.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/investigate_marker.png>)
- 検知キー：`POKEMON_ZA_INVESTIGATE_MARKER`
- 対応時の論点：Aボタン単体は複数の操作で共通。文字を除去すると操作の意味を区別できるかを別途検証する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_5_story_karasuba_46_recovery:25895](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25895>) | `image_check` | 見つからず |


## itemwindow.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：ITEM
- 画像：[Template/ZA_Story/Common/itemwindow.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/itemwindow.png>)
- 検知キー：`POKEMON_ZA_ITEM_WINDOW`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_6_story_yukari_47:27293](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27293>) | `ZA_story_Template_Comment_Out` | あり |
| [_6_story_yukari_48:27306](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27306>) | `image_check` | あり |
| [_6_story_yukari_49:27357](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27357>) | `ZA_story_Template_Comment_Out` | あり |
| [_8_story_story_last_49:29534](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29534>) | `ZA_renda_button` | あり |
| [_8_story_story_last_50:29548](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29548>) | `default_or_condition` | あり |
| [ZA_common_item_give_target_side:30182](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30182>) | `image_check` | あり |
| [ZA_common_item_give_target_high:30193](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30193>) | `image_check` | あり |


## last_battle_charge.png

- 分類：ボス戦の名前・技・予告／日本語の単語・文章
- 主な表示：力を溜めている……（予告片）
- 画像：[Template/ZA_Story/Common/last_battle_charge.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/last_battle_charge.png>)
- 検知キー：`POKEMON_ZA_LAST_BATTLE_CHARGE`
- 対応時の論点：相手名・技名・攻撃予告を判別。背景色や通常HPバーだけへの置換は意味を失う。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_no_attack_watchdog:3775](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3775>) | `default_or_condition` | あり |
| [ZA_mega_mode5_no_attack_watchdog:3776](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3776>) | `image_check` | あり |
| [ZA_mega_mode5_no_attack_watchdog:3804](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3804>) | `image_check` | あり |
| [ZA_mega_mode5_no_attack_watchdog:3860](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3860>) | `image_check` | あり |
| [ZA_mega_last_battle_charge_update:7181](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7181>) | `image_check` | 見つからず |
| [ZA_mega_last_battle_charge_update:7219](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7219>) | `image_check` | 見つからず |
| [ZA_mega_last_battle_charge_update:7252](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7252>) | `image_check` | 見つからず |
| [ZA_mega_last_battle_charge_update:7345](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7345>) | `ZA_mega_mode5_trace` | 見つからず |
| [ZA_mega_mode5_testmode1_side_transition_update:8941](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:8941>) | `image_check` | 見つからず |


## last_battle_move_core_enforcer.png

- 分類：ボス戦の名前・技・予告／日本語の単語・文章
- 主な表示：コアパニッシャー…
- 画像：[Template/ZA_Story/Common/last_battle_move_core_enforcer.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/last_battle_move_core_enforcer.png>)
- 検知キー：`POKEMON_ZA_LAST_BATTLE_MOVE_UI`
- 対応時の論点：相手名・技名・攻撃予告を判別。背景色や通常HPバーだけへの置換は意味を失う。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_renda_button:3273](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3273>) | `default_or_condition` | あり |
| [ZA_mega_mode5_event_attack_picture:3945](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3945>) | `default_or_condition` | あり |
| [ZA_mega_mode5_indefinite_field_wait_update:6738](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6738>) | `default_or_condition` | あり |
| [ZA_mega_mode5_indefinite_field_wait_update:6822](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6822>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:10821](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:10821>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:11036](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11036>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:11415](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11415>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:12980](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12980>) | `default_or_condition` | あり |


## last_battle_move_lands_wrath.png

- 分類：ボス戦の名前・技・予告／日本語の単語・文章
- 主な表示：グランドフォース
- 画像：[Template/ZA_Story/Common/last_battle_move_lands_wrath.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/last_battle_move_lands_wrath.png>)
- 検知キー：`POKEMON_ZA_LAST_BATTLE_MOVE_UI`
- 対応時の論点：相手名・技名・攻撃予告を判別。背景色や通常HPバーだけへの置換は意味を失う。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_renda_button:3273](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3273>) | `default_or_condition` | あり |
| [ZA_mega_mode5_event_attack_picture:3945](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3945>) | `default_or_condition` | あり |
| [ZA_mega_mode5_indefinite_field_wait_update:6738](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6738>) | `default_or_condition` | あり |
| [ZA_mega_mode5_indefinite_field_wait_update:6822](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6822>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:10821](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:10821>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:11036](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11036>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:11415](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11415>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:12980](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12980>) | `default_or_condition` | あり |


## last_battle_move_thousand_arrows.png

- 分類：ボス戦の名前・技・予告／日本語の単語・文章
- 主な表示：サウザンアロー
- 画像：[Template/ZA_Story/Common/last_battle_move_thousand_arrows.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/last_battle_move_thousand_arrows.png>)
- 検知キー：`POKEMON_ZA_LAST_BATTLE_MOVE_UI`
- 対応時の論点：相手名・技名・攻撃予告を判別。背景色や通常HPバーだけへの置換は意味を失う。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_renda_button:3273](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3273>) | `default_or_condition` | あり |
| [ZA_mega_mode5_event_attack_picture:3945](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3945>) | `default_or_condition` | あり |
| [ZA_mega_mode5_indefinite_field_wait_update:6738](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6738>) | `default_or_condition` | あり |
| [ZA_mega_mode5_indefinite_field_wait_update:6822](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6822>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:10821](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:10821>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:11036](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11036>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:11415](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11415>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:12980](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12980>) | `default_or_condition` | あり |


## last_battle_move_thousand_waves.png

- 分類：ボス戦の名前・技・予告／日本語の単語・文章
- 主な表示：サウザンウェーブ
- 画像：[Template/ZA_Story/Common/last_battle_move_thousand_waves.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/last_battle_move_thousand_waves.png>)
- 検知キー：`POKEMON_ZA_LAST_BATTLE_MOVE_UI`
- 対応時の論点：相手名・技名・攻撃予告を判別。背景色や通常HPバーだけへの置換は意味を失う。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_renda_button:3273](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3273>) | `default_or_condition` | あり |
| [ZA_mega_mode5_event_attack_picture:3945](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3945>) | `default_or_condition` | あり |
| [ZA_mega_mode5_indefinite_field_wait_update:6738](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6738>) | `default_or_condition` | あり |
| [ZA_mega_mode5_indefinite_field_wait_update:6822](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6822>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:10821](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:10821>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:11036](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11036>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:11415](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11415>) | `default_or_condition` | あり |
| [ZA_mega_evolution_battle:12980](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:12980>) | `default_or_condition` | あり |


## last_battle_strong_light.png

- 分類：ボス戦の名前・技・予告／日本語の単語・文章
- 主な表示：強い光を放…（予告片）
- 画像：[Template/ZA_Story/Common/last_battle_strong_light.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/last_battle_strong_light.png>)
- 検知キー：`POKEMON_ZA_LAST_BATTLE_STRONG_LIGHT`
- 対応時の論点：相手名・技名・攻撃予告を判別。背景色や通常HPバーだけへの置換は意味を失う。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_no_attack_watchdog:3777](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3777>) | `default_or_condition` | あり |
| [ZA_mega_mode5_no_attack_watchdog:3778](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3778>) | `image_check` | あり |
| [ZA_mega_mode5_no_attack_watchdog:3806](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3806>) | `image_check` | あり |
| [ZA_mega_mode5_no_attack_watchdog:3862](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3862>) | `image_check` | あり |
| [ZA_mega_last_battle_charge_update:7185](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7185>) | `image_check` | 見つからず |
| [ZA_mega_last_battle_charge_update:7221](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7221>) | `image_check` | 見つからず |
| [ZA_mega_last_battle_charge_update:7258](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7258>) | `image_check` | 見つからず |
| [ZA_mega_last_battle_charge_update:7386](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:7386>) | `image_check` | 見つからず |
| [ZA_mega_mode5_testmode1_side_transition_update:8943](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:8943>) | `image_check` | 見つからず |


## map2.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：MAP
- 画像：[Template/ZA_Story/Common/map2.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/map2.png>)
- 検知キー：`POKEMON_ZA_MAP`, `POKEMON_ZA_MAP2`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_story_furadari_lab_entrance_goto:13906](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13906>) | `image_check` | あり |
| [ZA_story_furadari_lab_entrance_goto:14024](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14024>) | `image_check` | あり |
| [ZA_story_furadari_black_comment_recovery_step:14605](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:14605>) | `image_check` | あり |
| [_1_story_third_battle_end:18249](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:18249>) | `image_check` | あり |
| [_1_story_out_hotel_z_54:19342](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:19342>) | `image_check` | あり |
| [_2_story_tower_36:19979](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:19979>) | `image_check` | あり |
| [ZA_Common_map_open:30477](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30477>) | `image_check` | あり |
| [ZA_Common_map_open:30479](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30479>) | `image_check` | あり |
| [ZA_Common_goto_select1:30496](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30496>) | `image_check` | あり |
| [ZA_Common_goto_select1:30558](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30558>) | `image_check` | あり |
| [ZA_Common_goto_select1:30565](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30565>) | `image_check` | あり |
| [ZA_Common_goto_select1:30568](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30568>) | `image_check` | あり |
| [ZA_Common_goto_select2:30582](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30582>) | `image_check` | あり |
| [ZA_Common_event_marker_check:31090](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31090>) | `image_check` | 見つからず |
| [ZA_bench_map_open:31403](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31403>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter1:31466](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31466>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter1:31487](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31487>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter1:31490](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31490>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter2:31496](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31496>) | `image_check` | あり |
| [ZA_goto_quasar1:31637](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31637>) | `image_check` | あり |
| [ZA_goto_quasar1:31651](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31651>) | `image_check` | あり |
| [ZA_goto_quasar1:31654](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31654>) | `image_check` | あり |
| [ZA_goto_quasar2:31660](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31660>) | `image_check` | あり |
| [ZA_battle_map_open:31743](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31743>) | `image_check` | あり |
| [ZA_battle_goto_battle_zone1:31772](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31772>) | `image_check` | あり |
| [ZA_battle_goto_battle_zone1:31789](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31789>) | `image_check` | あり |
| [ZA_battle_goto_battle_zone1:31792](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31792>) | `image_check` | あり |
| [ZA_battle_goto_battle_zone2:31798](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31798>) | `image_check` | あり |


## morning.png

- 分類：昼夜表示／漢字の文字片
- 主な表示：昼夜表示の漢字片
- 画像：[Template/ZA_Story/Common/morning.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/morning.png>)
- 検知キー：`POKEMON_ZA_MORNING`
- 対応時の論点：日中・夜の表示を大きな漢字の一部で検知。太陽・月アイコンの代用は別検証。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_story_furadari_lab_entrance_goto:13941](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13941>) | `ZA_Common_change_time_set` | あり |
| [_ZA_story_event_entry_pending_recovery_step:15123](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15123>) | `default_or_condition` | あり |
| [ZA_story_Template_battle_after:15502](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15502>) | `default_or_condition` | 見つからず |
| [_ZA_story_battle_after_safe_renda:16594](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16594>) | `default_or_condition` | あり |
| [ZA_story_Template_Comment_Out:16857](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16857>) | `ZA_renda_button` | あり |
| [_2_story_y_lank_move0:22344](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22344>) | `ZA_Common_change_time_set` | あり |
| [_2_story_absol_move3:22655](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22655>) | `image_check` | あり |
| [_2_story_mapping_110:22727](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22727>) | `ZA_Common_change_time_set` | あり |
| [_2_story_mapping_114_0:22788](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22788>) | `ZA_Common_change_time_set` | あり |
| [_2_story_mapping_116_0:22847](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22847>) | `ZA_Common_change_time_set` | 見つからず |
| [_2_story_mega_move1:23500](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23500>) | `ZA_Common_change_time_set` | あり |
| [_2_story_mega_move7:23551](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23551>) | `ZA_Common_change_time_set` | あり |
| [_2_story_mega_move17:23631](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23631>) | `ZA_Common_change_time_set` | あり |
| [_3_story_canari_2_recovery1:23736](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23736>) | `ZA_Common_change_time_set` | あり |
| [_3_story_mega_move3:24111](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:24111>) | `ZA_Common_change_time_set` | あり |
| [_3_story_mega_move13:24207](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:24207>) | `ZA_Common_change_time_set` | あり |
| [_3_story_mega_move19:24263](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:24263>) | `ZA_Common_change_time_set` | あり |
| [_4_story_shiro_2:24397](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:24397>) | `ZA_Common_change_time_set` | あり |
| [_4_story_shiro_21:24570](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:24570>) | `ZA_Common_change_time_set` | あり |
| [_4_story_shiro_38:24774](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:24774>) | `ZA_Common_change_time_set` | あり |
| [_4_story_shiro_83:25262](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25262>) | `ZA_Common_change_time_set` | あり |
| [_5_story_mapping_1:25308](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25308>) | `ZA_Common_change_time_set` | あり |
| [_5_story_karasuba_1:25423](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25423>) | `ZA_Common_change_time_set` | あり |
| [_5_story_karasuba_15:25510](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25510>) | `ZA_Common_change_time_set` | あり |
| [_5_story_karasuba_21:25559](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25559>) | `ZA_Common_change_time_set` | あり |
| [_5_story_karasuba_27:25618](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25618>) | `ZA_Common_change_time_set` | あり |
| [_5_story_karasuba_34:25681](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25681>) | `ZA_Common_change_time_set` | あり |
| [_5_story_karasuba_63:26106](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26106>) | `ZA_Common_change_time_set` | あり |
| [_6_story_mapping_1:26851](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26851>) | `ZA_Common_change_time_set` | あり |
| [_6_story_yukari_1:26922](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26922>) | `ZA_Common_change_time_set` | あり |
| [_6_story_yukari_11:26987](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26987>) | `ZA_Common_change_time_set` | あり |
| [_6_story_yukari_17:27030](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27030>) | `ZA_Common_change_time_set` | あり |
| [_6_story_yukari_23:27097](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27097>) | `ZA_Common_change_time_set` | あり |
| [_6_story_yukari_29:27144](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27144>) | `ZA_Common_change_time_set` | あり |
| [_6_story_yukari_35:27194](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27194>) | `ZA_Common_change_time_set` | あり |
| [_6_story_yukari_42:27257](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27257>) | `ZA_Common_change_time_set` | あり |
| [_6_story_yukari_55:27487](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27487>) | `ZA_Common_change_time_set` | あり |
| [_6_story_yukari_61:27521](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27521>) | `ZA_Common_change_time_set` | あり |
| [_7_story_mapping_1:27687](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27687>) | `ZA_Common_change_time_set` | あり |
| [_7_story_mapping_5:27741](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27741>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_1:27812](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27812>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_8:27869](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27869>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_14:27915](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27915>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_20:27959](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27959>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_37:28058](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28058>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_47:28175](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28175>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_51:28204](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28204>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_55:28251](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28251>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_63:28295](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28295>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_71:28351](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28351>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_75:28379](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28379>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_129:28831](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28831>) | `ZA_Common_change_time_set` | あり |
| [_7_story_guri_136:28881](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:28881>) | `ZA_Common_change_time_set` | あり |
| [ZA_common_evolution_exec:30263](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30263>) | `image_check` | あり |
| [other_a_target_visible:30263](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30263>) | `image_check` | あり |
| [ZA_Common_check_time:31028](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31028>) | `default_or_condition` | あり |
| [ZA_Common_check_time:31038](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31038>) | `default_or_condition` | あり |
| [_ZA_story_mapping_goto_recovery_context:31183](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31183>) | `default_or_condition` | 見つからず |
| [ZA_bench_map_open:31405](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31405>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter1:31481](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31481>) | `image_check` | あり |
| [ZA_bench_check_time:31577](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31577>) | `image_check` | あり |
| [ZA_battle_map_open:31709](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31709>) | `image_check` | あり |
| [ZA_battle_move_test:32312](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32312>) | `image_check` | あり |
| [ZA_battle_move_test:32456](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32456>) | `image_check` | あり |


## move_comment.png

- 分類：マップの種類・共通操作／日本語の単語・文章
- 主な表示：この場所に移動しますか？
- 画像：[Template/ZA_Story/Common/move_comment.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/move_comment.png>)
- 検知キー：`POKEMON_ZA_MOVE_COMMENT`
- 対応時の論点：移動先の写真とは別の文字依存。成功確認と移動禁止警告は別条件のまま識別が必要。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_Common_goto_jump:30705](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30705>) | `image_check` | あり |
| [ZA_Common_goto_jump:30718](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30718>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter2:31504](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31504>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter2:31514](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31514>) | `image_check` | あり |
| [ZA_goto_quasar2:31669](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31669>) | `image_check` | あり |
| [ZA_goto_quasar2:31674](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31674>) | `image_check` | あり |
| [ZA_battle_goto_battle_zone2:31841](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31841>) | `image_check` | あり |
| [ZA_battle_goto_battle_zone2:31856](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31856>) | `image_check` | あり |


## movespot_tab.png

- 分類：マップの種類・共通操作／日本語の単語・文章
- 主な表示：移動スポット
- 画像：[Template/ZA_Story/Common/movespot_tab.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/movespot_tab.png>)
- 検知キー：`POKEMON_ZA_MOVESPOT_TAB`
- 対応時の論点：移動先の写真とは別の文字依存。成功確認と移動禁止警告は別条件のまま識別が必要。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_Common_goto_select1:30498](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30498>) | `image_check` | あり |
| [ZA_Common_goto_select2:30583](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30583>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter1:31468](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31468>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter2:31497](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31497>) | `image_check` | あり |
| [ZA_goto_quasar1:31638](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31638>) | `image_check` | あり |
| [ZA_goto_quasar2:31661](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31661>) | `image_check` | あり |
| [ZA_battle_goto_battle_zone1:31773](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31773>) | `image_check` | あり |
| [ZA_battle_goto_battle_zone2:31799](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31799>) | `image_check` | あり |


## night.png

- 分類：昼夜表示／漢字の文字片
- 主な表示：昼夜表示の漢字片
- 画像：[Template/ZA_Story/Common/night.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/night.png>)
- 検知キー：`POKEMON_ZA_NIGHT`
- 対応時の論点：日中・夜の表示を大きな漢字の一部で検知。太陽・月アイコンの代用は別検証。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_ZA_story_event_entry_pending_recovery_step:15124](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15124>) | `default_or_condition` | あり |
| [ZA_story_Template_battle_after:15503](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:15503>) | `default_or_condition` | 見つからず |
| [_ZA_story_battle_after_safe_renda:16595](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16595>) | `default_or_condition` | あり |
| [ZA_story_Template_Comment_Out:16858](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16858>) | `ZA_renda_button` | あり |
| [_2_story_tower_84:22323](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22323>) | `ZA_Common_change_time_set` | あり |
| [_3_story_canari_11:23822](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23822>) | `ZA_Common_change_time_set` | あり |
| [_3_story_canari_33:23993](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23993>) | `ZA_Common_change_time_set` | あり |
| [_5_story_karasuba_99:26672](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26672>) | `ZA_Common_change_time_set` | あり |
| [_5_story_karasuba_111:26734](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26734>) | `ZA_Common_change_time_set` | あり |
| [ZA_common_evolution_exec:30264](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30264>) | `image_check` | あり |
| [other_a_target_visible:30264](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30264>) | `image_check` | あり |
| [ZA_Common_check_time:31044](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31044>) | `default_or_condition` | あり |
| [ZA_Common_check_time:31055](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31055>) | `default_or_condition` | あり |
| [ZA_bench_map_open:31407](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31407>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter1:31483](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31483>) | `image_check` | あり |
| [ZA_bench_check_time:31601](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31601>) | `image_check` | あり |


## outmarker.png

- 分類：フィールドの操作表示／日本語の単語・文章
- 主な表示：A でる
- 画像：[Template/ZA_Story/Common/outmarker.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/outmarker.png>)
- 検知キー：`POKEMON_ZA_OUT_MARKER`
- 対応時の論点：Aボタン単体は複数の操作で共通。文字を除去すると操作の意味を区別できるかを別途検証する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_1_story_farst_battle_zone_move3:18056](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:18056>) | `image_check` | 見つからず |
| [_1_story_out_hotel_z_21:18886](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:18886>) | `image_check` | あり |
| [_1_story_out_hotel_z_21:18897](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:18897>) | `image_check` | あり |
| [_1_story_out_hotel_z_21:18909](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:18909>) | `image_check` | あり |
| [_1_story_out_hotel_z_40:19184](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:19184>) | `image_check` | あり |


## select_all.png

- 分類：マップの種類・共通操作／日本語の単語・文章
- 主な表示：すべて／施設／ポケモンセンター／カフェ／ゾーン／やめる
- 画像：[Template/ZA_Story/Common/select_all.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/select_all.png>)
- 検知キー：`POKEMON_ZA_SELECT_ALL`
- 対応時の論点：移動先の写真とは別の文字依存。成功確認と移動禁止警告は別条件のまま識別が必要。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_Common_goto_select1:30506](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30506>) | `image_check` | あり |
| [ZA_Common_goto_select1:30518](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30518>) | `image_check` | あり |
| [ZA_Common_goto_select1:30538](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30538>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter1:31472](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31472>) | `image_check` | あり |
| [ZA_goto_quasar1:31641](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31641>) | `image_check` | あり |
| [ZA_battle_goto_battle_zone1:31776](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31776>) | `image_check` | あり |


## underground_sewer_map.png

- 分類：マップの種類・共通操作／日本語の単語・文章
- 主な表示：地下水道
- 画像：[Template/ZA_Story/Common/underground_sewer_map.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/underground_sewer_map.png>)
- 検知キー：`POKEMON_ZA_UG_SEWER_MAP`
- 対応時の論点：移動先の写真とは別の文字依存。成功確認と移動禁止警告は別条件のまま識別が必要。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_5_story_karasuba_69:26245](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26245>) | `ZA_Common_goto` | あり |
| [_5_story_karasuba_96:26651](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26651>) | `ZA_Common_goto` | あり |


## z-a_royale.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：Z-A ROYALE
- 画像：[Template/ZA_Story/Common/z-a_royale.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/Common/z-a_royale.png>)
- 検知キー：`POKEMON_ZA_ZA_ROYALE`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_story_Template_Comment_Out:16850](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16850>) | `ZA_renda_button` | あり |
| [ZA_story_Template_Comment_Out:16950](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:16950>) | `image_check` | あり |
| [_2_story_mega_move23:23677](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23677>) | `image_check` | あり |
| [ZA_common_evolution_exec:30295](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30295>) | `image_check` | あり |
| [ZA_common_item_use_window_close:30442](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30442>) | `ZA_renda_button` | 見つからず |


## W_ZONE10_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 10
- 画像：[Template/ZA_Story/MovePoint/W_ZONE10_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE10_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE10`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_117:22880](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22880>) | `image_check` | あり |
| [_2_story_mapping_117:22888](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22888>) | `ZA_Common_mappic_check` | あり |


## W_ZONE10_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：10番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE10_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE10_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE10`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_117:22878](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22878>) | `image_check` | あり |
| [_2_story_mapping_117:22888](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22888>) | `ZA_Common_mappic_check` | あり |


## W_ZONE14_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 14
- 画像：[Template/ZA_Story/MovePoint/W_ZONE14_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE14_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE14`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_5_story_mapping_4:25340](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25340>) | `image_check` | あり |
| [_5_story_mapping_4:25348](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25348>) | `ZA_Common_mappic_check` | あり |


## W_ZONE14_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：14番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE14_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE14_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE14`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_5_story_mapping_4:25338](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25338>) | `image_check` | あり |
| [_5_story_mapping_4:25348](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25348>) | `ZA_Common_mappic_check` | あり |


## W_ZONE15_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 15
- 画像：[Template/ZA_Story/MovePoint/W_ZONE15_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE15_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE15`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_5_story_mapping_6:25377](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25377>) | `image_check` | あり |
| [_5_story_mapping_6:25389](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25389>) | `ZA_Common_mappic_check` | あり |


## W_ZONE15_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：15番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE15_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE15_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE15`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_5_story_mapping_6:25375](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25375>) | `image_check` | あり |
| [_5_story_mapping_6:25389](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:25389>) | `ZA_Common_mappic_check` | あり |


## W_ZONE17_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 17
- 画像：[Template/ZA_Story/MovePoint/W_ZONE17_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE17_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE17`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_6_story_mapping_4:26883](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26883>) | `image_check` | あり |
| [_6_story_mapping_4:26891](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26891>) | `ZA_Common_mappic_check` | あり |


## W_ZONE17_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：17番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE17_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE17_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE17`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_6_story_mapping_4:26881](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26881>) | `image_check` | あり |
| [_6_story_mapping_4:26891](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26891>) | `ZA_Common_mappic_check` | あり |


## W_ZONE18_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 18
- 画像：[Template/ZA_Story/MovePoint/W_ZONE18_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE18_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE18`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_7_story_mapping_4:27715](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27715>) | `image_check` | あり |
| [_7_story_mapping_4:27723](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27723>) | `ZA_Common_mappic_check` | あり |


## W_ZONE18_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：18番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE18_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE18_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE18`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_7_story_mapping_4:27713](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27713>) | `image_check` | あり |
| [_7_story_mapping_4:27723](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27723>) | `ZA_Common_mappic_check` | あり |


## W_ZONE19_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 19
- 画像：[Template/ZA_Story/MovePoint/W_ZONE19_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE19_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE19`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_7_story_mapping_8:27782](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27782>) | `image_check` | あり |
| [_7_story_mapping_8:27793](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27793>) | `ZA_Common_mappic_check` | あり |


## W_ZONE19_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：19番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE19_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE19_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE19`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_7_story_mapping_8:27780](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27780>) | `image_check` | あり |
| [_7_story_mapping_8:27793](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27793>) | `ZA_Common_mappic_check` | あり |


## W_ZONE2_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 2
- 画像：[Template/ZA_Story/MovePoint/W_ZONE2_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE2_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE2`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_39:20765](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20765>) | `image_check` | あり |
| [_2_story_mapping_39:20773](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20773>) | `ZA_Common_mappic_check` | あり |


## W_ZONE2_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：2番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE2_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE2_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE2`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_39:20763](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20763>) | `image_check` | あり |
| [_2_story_mapping_39:20773](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20773>) | `ZA_Common_mappic_check` | あり |


## W_ZONE4_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 4
- 画像：[Template/ZA_Story/MovePoint/W_ZONE4_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE4_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE4`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_3:20161](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20161>) | `image_check` | あり |
| [_2_story_mapping_3:20169](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20169>) | `ZA_Common_mappic_check` | あり |


## W_ZONE4_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：4番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE4_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE4_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE4`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_3:20159](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20159>) | `image_check` | あり |
| [_2_story_mapping_3:20169](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20169>) | `ZA_Common_mappic_check` | あり |


## W_ZONE5_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 5
- 画像：[Template/ZA_Story/MovePoint/W_ZONE5_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE5_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE5`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_42:20821](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20821>) | `image_check` | あり |
| [_2_story_mapping_42:20829](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20829>) | `ZA_Common_mappic_check` | あり |


## W_ZONE5_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：5番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE5_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE5_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE5`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_42:20819](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20819>) | `image_check` | あり |
| [_2_story_mapping_42:20829](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20829>) | `ZA_Common_mappic_check` | あり |


## W_ZONE6_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 6
- 画像：[Template/ZA_Story/MovePoint/W_ZONE6_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE6_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE6`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_45:20871](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20871>) | `image_check` | あり |
| [_2_story_mapping_45:20879](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20879>) | `ZA_Common_mappic_check` | あり |


## W_ZONE6_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：6番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE6_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE6_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE6`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_45:20869](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20869>) | `image_check` | あり |
| [_2_story_mapping_45:20879](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20879>) | `ZA_Common_mappic_check` | あり |


## W_ZONE8_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 8
- 画像：[Template/ZA_Story/MovePoint/W_ZONE8_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE8_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE8`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_113:22762](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22762>) | `image_check` | あり |
| [_2_story_mapping_113:22770](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22770>) | `ZA_Common_mappic_check` | あり |


## W_ZONE8_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：8番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE8_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE8_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE8`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_113:22760](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22760>) | `image_check` | あり |
| [_2_story_mapping_113:22770](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22770>) | `ZA_Common_mappic_check` | あり |


## W_ZONE9_pic.png

- 分類：ワイルドゾーンの番号カード／英字・数字の文字判定
- 主な表示：WILD ZONE 9
- 画像：[Template/ZA_Story/MovePoint/W_ZONE9_pic.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE9_pic.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_PIC_W_ZONE9`
- 対応時の論点：picという名前だが景観写真ではなく英字＋番号。数字だけを使う場合も文字・番号の判定が残る。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_115:22821](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22821>) | `image_check` | あり |
| [_2_story_mapping_115:22829](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22829>) | `ZA_Common_mappic_check` | あり |


## W_ZONE9_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：9番ワイルドゾーン
- 画像：[Template/ZA_Story/MovePoint/W_ZONE9_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/W_ZONE9_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_W_ZONE9`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_115:22819](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22819>) | `image_check` | あり |
| [_2_story_mapping_115:22829](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22829>) | `ZA_Common_mappic_check` | あり |


## art_museum_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ミアレ美術館
- 画像：[Template/ZA_Story/MovePoint/art_museum_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/art_museum_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_ART_MUSEUM`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_81:21477](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21477>) | `image_check` | あり |
| [_2_story_mapping_81:21487](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21487>) | `ZA_Common_mappic_check` | あり |


## bule_square_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ブルー広場
- 画像：[Template/ZA_Story/MovePoint/bule_square_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/bule_square_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_BLUE_SQUARE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_60:21123](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21123>) | `image_check` | あり |
| [_2_story_mapping_60:21133](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21133>) | `ZA_Common_mappic_check` | あり |


## cafe_alamode_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・アラモード
- 画像：[Template/ZA_Story/MovePoint/cafe_alamode_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_alamode_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_ALAMODE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_48:20913](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20913>) | `image_check` | あり |
| [_2_story_mapping_48:20923](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20923>) | `ZA_Common_mappic_check` | あり |


## cafe_bataille_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・バタイユ
- 画像：[Template/ZA_Story/MovePoint/cafe_bataille_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_bataille_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_BATAILLE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_94:21677](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21677>) | `image_check` | あり |
| [_2_story_mapping_94:21687](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21687>) | `ZA_Common_mappic_check` | あり |


## cafe_cancodor_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・カンコドール
- 画像：[Template/ZA_Story/MovePoint/cafe_cancodor_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_cancodor_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_CANCODOR`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_75:21370](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21370>) | `image_check` | あり |
| [_2_story_mapping_75:21380](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21380>) | `ZA_Common_mappic_check` | あり |


## cafe_cute_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・かわいがり
- 画像：[Template/ZA_Story/MovePoint/cafe_cute_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_cute_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_CUTE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_109:21939](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21939>) | `image_check` | あり |
| [_2_story_mapping_109:21949](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21949>) | `ZA_Common_mappic_check` | あり |


## cafe_focus_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・フォーカス
- 画像：[Template/ZA_Story/MovePoint/cafe_focus_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_focus_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_FOCUS`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_66:21230](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21230>) | `image_check` | あり |
| [_2_story_mapping_66:21240](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21240>) | `ZA_Common_mappic_check` | あり |


## cafe_man_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・おとこまえ
- 画像：[Template/ZA_Story/MovePoint/cafe_man_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_man_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_MAN`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_12:20302](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20302>) | `image_check` | あり |
| [_2_story_mapping_12:20312](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20312>) | `ZA_Common_mappic_check` | あり |


## cafe_nuvo2_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ヌーヴォカフェ2号店
- 画像：[Template/ZA_Story/MovePoint/cafe_nuvo2_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_nuvo2_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_NUVO2`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_57:21078](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21078>) | `image_check` | あり |
| [_2_story_mapping_57:21088](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21088>) | `ZA_Common_mappic_check` | あり |


## cafe_nuvo3_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ヌーヴォカフェ3号店
- 画像：[Template/ZA_Story/MovePoint/cafe_nuvo3_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_nuvo3_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_NUVO3`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_72:21324](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21324>) | `image_check` | あり |
| [_2_story_mapping_72:21334](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21334>) | `ZA_Common_mappic_check` | あり |


## cafe_partenaire_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・パルトネール
- 画像：[Template/ZA_Story/MovePoint/cafe_partenaire_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_partenaire_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_PARTENAIRE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_90:21618](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21618>) | `image_check` | あり |
| [_2_story_mapping_90:21628](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21628>) | `ZA_Common_mappic_check` | あり |


## cafe_retake_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・リテイク
- 画像：[Template/ZA_Story/MovePoint/cafe_retake_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_retake_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_RETAKE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_33:20662](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20662>) | `image_check` | あり |
| [_2_story_mapping_33:20672](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20672>) | `ZA_Common_mappic_check` | あり |


## cafe_slalom_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・スラローム
- 画像：[Template/ZA_Story/MovePoint/cafe_slalom_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_slalom_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_SLALOM`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_69:21279](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21279>) | `image_check` | あり |
| [_2_story_mapping_69:21289](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21289>) | `ZA_Common_mappic_check` | あり |


## cafe_soleil_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・ソレイユ
- 画像：[Template/ZA_Story/MovePoint/cafe_soleil_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_soleil_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_SOLEIL`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_63:21175](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21175>) | `image_check` | あり |
| [_2_story_mapping_63:21185](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21185>) | `ZA_Common_mappic_check` | あり |


## cafe_toto_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・トウトウ
- 画像：[Template/ZA_Story/MovePoint/cafe_toto_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_toto_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_TOTO`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_51:20957](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20957>) | `image_check` | あり |
| [_2_story_mapping_51:20967](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20967>) | `ZA_Common_mappic_check` | あり |


## cafe_twister_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・ツイスター
- 画像：[Template/ZA_Story/MovePoint/cafe_twister_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_twister_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_TWISTER`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_54:21016](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21016>) | `image_check` | あり |
| [_2_story_mapping_54:21026](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21026>) | `ZA_Common_mappic_check` | あり |


## cafe_ult_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：カフェ・アルティメット
- 画像：[Template/ZA_Story/MovePoint/cafe_ult_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/cafe_ult_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_CAFE_ULT`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_87:21571](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21571>) | `image_check` | あり |
| [_2_story_mapping_87:21581](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21581>) | `ZA_Common_mappic_check` | あり |


## hotel_surrealish_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ホテル シュールリッシュ
- 画像：[Template/ZA_Story/MovePoint/hotel_surrealish_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/hotel_surrealish_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_HOTEL_SURREALISH`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_84:21525](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21525>) | `image_check` | あり |
| [_2_story_mapping_84:21535](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21535>) | `ZA_Common_mappic_check` | あり |


## justice_dojo_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ジャスティスの会道場
- 画像：[Template/ZA_Story/MovePoint/justice_dojo_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/justice_dojo_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_JUSTICE_DOJO`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_103:21839](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21839>) | `image_check` | あり |
| [_2_story_mapping_103:21849](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21849>) | `ZA_Common_mappic_check` | あり |


## pokecenter_blue_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ポケモンセンター：ブルー
- 画像：[Template/ZA_Story/MovePoint/pokecenter_blue_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/pokecenter_blue_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_BLUE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_27:20558](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20558>) | `image_check` | あり |
| [_2_story_mapping_27:20568](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20568>) | `ZA_Common_mappic_check` | あり |


## pokecenter_evel_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ポケモンセンター：イベール
- 画像：[Template/ZA_Story/MovePoint/pokecenter_evel_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/pokecenter_evel_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_EVEL`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_30:20609](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20609>) | `image_check` | あり |
| [_2_story_mapping_30:20619](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20619>) | `ZA_Common_mappic_check` | あり |


## pokecenter_jone_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ポケモンセンター：ジョーヌ
- 画像：[Template/ZA_Story/MovePoint/pokecenter_jone_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/pokecenter_jone_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_JONE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_36:20711](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20711>) | `image_check` | あり |
| [_2_story_mapping_36:20721](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20721>) | `ZA_Common_mappic_check` | あり |


## pokecenter_prantan_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ポケモンセンター：プランタン
- 画像：[Template/ZA_Story/MovePoint/pokecenter_prantan_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/pokecenter_prantan_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_PRANTAN`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_24:20491](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20491>) | `image_check` | あり |
| [_2_story_mapping_24:20501](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20501>) | `ZA_Common_mappic_check` | あり |


## pokecenter_rose_square_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ポケモンセンター：ローズ広場
- 画像：[Template/ZA_Story/MovePoint/pokecenter_rose_square_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/pokecenter_rose_square_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_ROSE_S`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_18:20395](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20395>) | `image_check` | あり |
| [_2_story_mapping_18:20405](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20405>) | `ZA_Common_mappic_check` | あり |


## pokecenter_rose_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ポケモンセンター：ローズ
- 画像：[Template/ZA_Story/MovePoint/pokecenter_rose_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/pokecenter_rose_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_ROSE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_21:20444](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20444>) | `image_check` | あり |
| [_2_story_mapping_21:20454](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20454>) | `ZA_Common_mappic_check` | あり |


## pokecenter_rudu_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ポケモンセンター：ルージュ
- 画像：[Template/ZA_Story/MovePoint/pokecenter_rudu_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/pokecenter_rudu_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_POKECENTER_RUDU`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_6:20206](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20206>) | `image_check` | あり |
| [_2_story_mapping_6:20216](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20216>) | `ZA_Common_mappic_check` | あり |


## racine_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ラシーヌ工務店
- 画像：[Template/ZA_Story/MovePoint/racine_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/racine_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_RACINE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_97:21727](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21727>) | `image_check` | あり |
| [_2_story_mapping_97:21737](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21737>) | `ZA_Common_mappic_check` | あり |


## restaurant_2ryu_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：リストランテ ニ・リュー
- 画像：[Template/ZA_Story/MovePoint/restaurant_2ryu_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/restaurant_2ryu_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_2RYU`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_78:21420](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21420>) | `image_check` | あり |
| [_2_story_mapping_78:21430](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21430>) | `ZA_Common_mappic_check` | あり |


## restaurant_dohutsu_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：レストラン・ド・フツー
- 画像：[Template/ZA_Story/MovePoint/restaurant_dohutsu_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/restaurant_dohutsu_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_DOHUTSU`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_100:21781](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21781>) | `image_check` | あり |
| [_2_story_mapping_100:21791](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21791>) | `ZA_Common_mappic_check` | あり |


## restaurant_dream_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：レストラン ローリングドリーマー
- 画像：[Template/ZA_Story/MovePoint/restaurant_dream_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/restaurant_dream_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_DREAM`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_9:20254](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20254>) | `image_check` | あり |
| [_2_story_mapping_9:20264](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20264>) | `ZA_Common_mappic_check` | あり |


## restaurant_exterme_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：レストラン・ド・キワミ
- 画像：[Template/ZA_Story/MovePoint/restaurant_exterme_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/restaurant_exterme_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_RESTAURANT_EXTREAME`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_106:21895](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21895>) | `image_check` | あり |
| [_2_story_mapping_106:21905](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:21905>) | `ZA_Common_mappic_check` | あり |


## rose_square_target.png

- 分類：マップ移動先名／日本語の単語・文章
- 主な表示：ローズ広場
- 画像：[Template/ZA_Story/MovePoint/rose_square_target.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/MovePoint/rose_square_target.png>)
- 検知キー：`POKEMON_ZA_MOVEPOINT_TARGET_ROSE_SQUARE`
- 対応時の論点：場所名の判定。写真側だけで代用できるかはマップ検証表を参照。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mapping_15:20348](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20348>) | `image_check` | あり |
| [_2_story_mapping_15:20358](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20358>) | `ZA_Common_mappic_check` | あり |


## POKEMON_ZA_MOVE_COMMENT_BATTLE2.png

- 分類：マップの種類・共通操作／日本語の単語・文章
- 主な表示：ポケモンにみつかっているため 移動できない！
- 画像：[Template/ZA_Story/ZA_infi/POKEMON_ZA_MOVE_COMMENT_BATTLE2.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/POKEMON_ZA_MOVE_COMMENT_BATTLE2.png>)
- 検知キー：`POKEMON_ZA_MOVE_COMMENT_BATTLE2`
- 対応時の論点：移動先の写真とは別の文字依存。成功確認と移動禁止警告は別条件のまま識別が必要。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_tower_38:20027](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20027>) | `image_check` | あり |
| [_2_story_tower_40:20076](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:20076>) | `image_check` | あり |
| [_4_story_shiro_32_0:24731](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:24731>) | `image_check` | あり |


## REWARD.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：REWARD
- 画像：[Template/ZA_Story/ZA_infi/REWARD.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/REWARD.png>)
- 検知キー：`POKEMON_ZA_REWARD_RESULT`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_battle_move_test:32664](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32664>) | `image_check` | あり |
| [ZA_battle_lockon_test:33089](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33089>) | `image_check` | あり |


## R_push.png

- 分類：ボタン・略字・記号／ボタン記号・略字
- 主な表示：Rボタンの一部
- 画像：[Template/ZA_Story/ZA_infi/R_push.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/R_push.png>)
- 検知キー：`POKEMON_ZA_R_push`
- 対応時の論点：日本語の単語ではないが、文字状の要素。単語一覧の主件数とは分ける。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_event_lockon_bootstrap:4140](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:4140>) | `next` | あり |
| [ZA_mega_mode5_event_attack_axby:4242](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:4242>) | `next` | 見つからず |
| [ZA_mega_mode5_rpush_prompt_confirmed:6379](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6379>) | `image_check` | 見つからず |
| [ZA_mega_evolution_battle:11623](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11623>) | `image_check` | あり |
| [ZA_mega_evolution_battle:11841](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11841>) | `image_check` | あり |
| [ZA_mega_evolution_battle:11867](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11867>) | `image_check` | あり |
| [ZA_mega_evolution_battle:11879](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11879>) | `image_check` | あり |
| [ZA_mega_evolution_battle:11888](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:11888>) | `image_check` | あり |
| [ZA_battle_Cp_loop:13372](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13372>) | `image_check` | あり |
| [ZA_battle_Cp_loop_move:13502](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:13502>) | `image_check` | あり |
| [_8_story_story_last_49:29526](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29526>) | `ZA_renda_button` | あり |
| [_8_story_story_last_51:29569](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:29569>) | `image_check` | あり |
| [ZA_battle_lockon_test:33075](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33075>) | `image_check` | あり |
| [image_check_confirmation:40226](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:40226>) | `image_check` | あり |


## chicket_95_118x1122_1268.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：MAX
- 画像：[Template/ZA_Story/ZA_infi/chicket_95_118x1122_1268.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/chicket_95_118x1122_1268.png>)
- 検知キー：`POKEMON_ZA_CHICKET_MAX_RIGHT`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_battle_move_test:32447](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32447>) | `image_check` | あり |
| [ZA_battle_move_test:32675](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32675>) | `image_check` | あり |


## chicket_max.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：MAX
- 画像：[Template/ZA_Story/ZA_infi/chicket_max.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/chicket_max.png>)
- 検知キー：`POKEMON_ZA_CHICKET_MAX`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_battle_move_test:32675](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32675>) | `image_check` | あり |


## doorA.png

- 分類：ボタン・略字・記号／ボタン記号・略字
- 主な表示：A
- 画像：[Template/ZA_Story/ZA_infi/doorA.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/doorA.png>)
- 検知キー：`POKEMON_ZA_DOOR_A`
- 対応時の論点：日本語の単語ではないが、文字状の要素。単語一覧の主件数とは分ける。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_mega_move24_1:23697](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:23697>) | `image_check` | 見つからず |
| [ZA_quasar_move_door:33323](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33323>) | `image_check` | 見つからず |


## escapecomment1.png

- 分類：敗北・降参・報酬／日本語の単語・文章
- 主な表示：賞金メダルを半分わたして 降参しますか？
- 画像：[Template/ZA_Story/ZA_infi/escapecomment1.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/escapecomment1.png>)
- 検知キー：`POKEMON_ZA_ESCAPE_COMMENT1`
- 対応時の論点：会話枠や下向き矢印の有無だけでは敗北・降参・報酬の意味を区別できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_battle_move_test:32189](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32189>) | `image_check` | あり |
| [ZA_battle_move_test:32800](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32800>) | `image_check` | あり |
| [ZA_battle_move_test:32931](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32931>) | `image_check` | あり |


## escapecomment2.png

- 分類：敗北・降参・報酬／日本語の単語・文章
- 主な表示：次は勝てるように ポケモンや使える技を確認しましょう
- 画像：[Template/ZA_Story/ZA_infi/escapecomment2.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/escapecomment2.png>)
- 検知キー：`POKEMON_ZA_ESCAPE_COMMENT2`
- 対応時の論点：会話枠や下向き矢印の有無だけでは敗北・降参・報酬の意味を区別できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_battle_move_test:32191](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32191>) | `image_check` | あり |
| [ZA_battle_move_test:32802](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32802>) | `image_check` | あり |
| [ZA_battle_move_test:32933](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32933>) | `image_check` | あり |


## escapecommentselect.png

- 分類：敗北・降参・報酬／日本語の単語・文章
- 主な表示：降参する／続ける
- 画像：[Template/ZA_Story/ZA_infi/escapecommentselect.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/escapecommentselect.png>)
- 検知キー：`POKEMON_ZA_ESCAPE_SELECT`
- 対応時の論点：会話枠や下向き矢印の有無だけでは敗北・降参・報酬の意味を区別できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_battle_move_test:32187](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32187>) | `image_check` | あり |
| [ZA_battle_move_test:32798](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32798>) | `image_check` | あり |
| [ZA_battle_move_test:32929](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32929>) | `image_check` | あり |


## lose.png

- 分類：敗北・降参・報酬／日本語の単語・文章
- 主な表示：戦えるポケモンがいなくなった……
- 画像：[Template/ZA_Story/ZA_infi/lose.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/lose.png>)
- 検知キー：`POKEMON_ZA_LOSE`
- 対応時の論点：会話枠や下向き矢印の有無だけでは敗北・降参・報酬の意味を区別できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_5_story_karasuba_69_95_black_comment_recovery:26179](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:26179>) | `image_check` | あり |
| [ZA_battle_map_open:31722](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31722>) | `image_check` | あり |
| [ZA_battle_move_test:32364](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32364>) | `image_check` | あり |
| [ZA_battle_move_test:32656](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32656>) | `image_check` | あり |
| [ZA_battle_lockon_test:33094](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33094>) | `image_check` | あり |


## move_comment_battle.png

- 分類：マップの種類・共通操作／日本語の単語・文章
- 主な表示：戦闘しているので 移動できない！
- 画像：[Template/ZA_Story/ZA_infi/move_comment_battle.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/move_comment_battle.png>)
- 検知キー：`POKEMON_ZA_MOVE_COMMENT_BATTLE`
- 対応時の論点：移動先の写真とは別の文字依存。成功確認と移動禁止警告は別条件のまま識別が必要。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_Common_goto_jump:30701](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30701>) | `image_check` | あり |
| [ZA_Common_goto_jump:30711](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:30711>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter1:31461](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31461>) | `image_check` | あり |
| [ZA_bench_goto_pokecenter2:31508](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31508>) | `image_check` | あり |
| [ZA_battle_goto_battle_zone2:31850](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:31850>) | `image_check` | あり |


## reword_end.png

- 分類：敗北・降参・報酬／日本語の単語・文章
- 主な表示：チャレンジチケットを手に入れたら
- 画像：[Template/ZA_Story/ZA_infi/reword_end.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/reword_end.png>)
- 検知キー：`POKEMON_ZA_REWORD_END`
- 対応時の論点：会話枠や下向き矢印の有無だけでは敗北・降参・報酬の意味を区別できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_event_attack_blocked:3906](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3906>) | `next` | あり |
| [ZA_battle_move_test:32376](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32376>) | `image_check` | あり |
| [ZA_battle_move_test:32393](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32393>) | `image_check` | あり |
| [ZA_battle_move_test:32412](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32412>) | `image_check` | あり |
| [ZA_battle_move_test:32429](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32429>) | `image_check` | あり |
| [ZA_battle_move_test:32579](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32579>) | `image_check` | あり |
| [ZA_battle_move_test:32604](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32604>) | `image_check` | あり |
| [ZA_battle_move_test:32697](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32697>) | `image_check` | あり |
| [ZA_battle_move_test:32736](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32736>) | `image_check` | あり |
| [ZA_battle_lockon_test:33099](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33099>) | `image_check` | あり |


## reword_lose.png

- 分類：敗北・降参・報酬／日本語の単語・文章
- 主な表示：残念でしたね……
- 画像：[Template/ZA_Story/ZA_infi/reword_lose.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/ZA_infi/reword_lose.png>)
- 検知キー：`POKEMON_ZA_REWORD_LOSE`
- 対応時の論点：会話枠や下向き矢印の有無だけでは敗北・降参・報酬の意味を区別できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_event_attack_blocked:3907](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3907>) | `next` | あり |
| [ZA_battle_move_test:32383](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32383>) | `image_check` | あり |
| [ZA_battle_move_test:32400](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32400>) | `image_check` | あり |
| [ZA_battle_move_test:32419](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32419>) | `image_check` | あり |
| [ZA_battle_move_test:32436](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32436>) | `image_check` | あり |
| [ZA_battle_move_test:32586](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32586>) | `image_check` | あり |
| [ZA_battle_move_test:32611](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32611>) | `image_check` | あり |
| [ZA_battle_move_test:32704](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32704>) | `image_check` | あり |
| [ZA_battle_move_test:32743](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:32743>) | `image_check` | あり |
| [ZA_battle_lockon_test:33099](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:33099>) | `image_check` | あり |


## Profile.png

- 分類：共通UIの英字・装飾文字／英字・数字の文字判定
- 主な表示：PROFILE
- 画像：[Template/ZA_Story/_0_Start/Profile.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_0_Start/Profile.png>)
- 検知キー：`POKEMON_ZA_PROFILE`
- 対応時の論点：日本語版の画面でも英字。全言語で表記・配置が同じかはZIPの日本語録画だけでは確定できない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [main_0_start:17671](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17671>) | `image_check` | あり |
| [main_0_start:17678](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17678>) | `image_check` | あり |


## startbutton_select.png

- 分類：開始・序盤イベント／日本語の単語・文章
- 主な表示：これで始める！
- 画像：[Template/ZA_Story/_0_Start/startbutton_select.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_0_Start/startbutton_select.png>)
- 検知キー：`POKEMON_ZA_STARTBTN_SELECT`
- 対応時の論点：特定イベントの到達を確認する語句。一般的な会話矢印への置換ではイベントの同定にならない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [main_0_start:17673](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17673>) | `image_check` | あり |
| [main_0_start:17679](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17679>) | `image_check` | あり |


## 2get_success.png

- 分類：開始・序盤イベント／日本語の単語・文章
- 主な表示：やったな！
- 画像：[Template/ZA_Story/_1_z_lank/2get_success.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_1_z_lank/2get_success.png>)
- 検知キー：`POKEMON_ZA_TEXT_2_GET_SUCCESS`
- 対応時の論点：特定イベントの到達を確認する語句。一般的な会話矢印への置換ではイベントの同定にならない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_1_story_out_hotel_z_16:18403](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:18403>) | `image_check` | あり |


## getchance_comment.png

- 分類：開始・序盤イベント／日本語の単語・文章
- 主な表示：捕獲チャンスだ！ いまのうちに捕まえろ！
- 画像：[Template/ZA_Story/_1_z_lank/getchance_comment.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_1_z_lank/getchance_comment.png>)
- 検知キー：`POKEMON_ZA_TEXT_2_GETCHANCE`
- 対応時の論点：特定イベントの到達を確認する語句。一般的な会話矢印への置換ではイベントの同定にならない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_1_story_out_hotel_z_16:18399](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:18399>) | `image_check` | あり |


## out_hotel_z23_field_white_comment.png

- 分類：開始・序盤イベント／日本語の単語・文章
- 主な表示：ポケモンの勉…／いつかは博士…（切り抜かれた会話片）
- 画像：[Template/ZA_Story/_1_z_lank/out_hotel_z23_field_white_comment.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_1_z_lank/out_hotel_z23_field_white_comment.png>)
- 検知キー：`POKEMON_ZA_OUT_HOTEL_Z23_FIELD_WHITE_COMMENT`
- 対応時の論点：特定イベントの到達を確認する語句。一般的な会話矢印への置換ではイベントの同定にならない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_markerdir:17237](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17237>) | `image_check` | あり |


## out_hotel_z45_hotel_z_text.png

- 分類：開始・序盤イベント／日本語の単語・文章
- 主な表示：ホテルZ
- 画像：[Template/ZA_Story/_1_z_lank/out_hotel_z45_hotel_z_text.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_1_z_lank/out_hotel_z45_hotel_z_text.png>)
- 検知キー：`POKEMON_ZA_OUT_HOTEL_Z45_HOTEL_Z_TEXT`
- 対応時の論点：特定イベントの到達を確認する語句。一般的な会話矢印への置換ではイベントの同定にならない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_1_story_out_hotel_z_45:19250](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:19250>) | `image_check` | あり |


## station_field.png

- 分類：開始・序盤イベント／日本語の単語・文章
- 主な表示：ミアレシティだ！
- 画像：[Template/ZA_Story/_1_z_lank/station_field.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_1_z_lank/station_field.png>)
- 検知キー：`POKEMON_ZA_TEXT_TRAIN_OUT_COMMENT`
- 対応時の論点：特定イベントの到達を確認する語句。一般的な会話矢印への置換ではイベントの同定にならない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_1_story_start_check:17813](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17813>) | `image_check` | あり |
| [_1_story_staition_out:17833](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17833>) | `image_check` | あり |
| [_1_story_staition_out:17838](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17838>) | `image_check` | あり |


## station_leave_comment.png

- 分類：開始・序盤イベント／日本語の単語・文章
- 主な表示：ん？ なんか騒ぎが…（会話片）
- 画像：[Template/ZA_Story/_1_z_lank/station_leave_comment.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_1_z_lank/station_leave_comment.png>)
- 検知キー：`POKEMON_ZA_TEXT_STATION_LEAVE_COMMENT`
- 対応時の論点：特定イベントの到達を確認する語句。一般的な会話矢印への置換ではイベントの同定にならない。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_1_story_staition_front:17848](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17848>) | `image_check` | あり |
| [_1_story_staition_front:17853](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17853>) | `ZA_renda_button` | あり |
| [_1_story_staition_leave_move:17863](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17863>) | `image_check` | あり |
| [_1_story_staition_leave_move:17866](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17866>) | `image_check` | あり |
| [_1_story_bag_chase_end:17880](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:17880>) | `image_check` | あり |


## mega_absol_battle_name.png

- 分類：ボス戦の名前・技・予告／日本語の単語・文章
- 主な表示：暴走メガアブソル
- 画像：[Template/ZA_Story/_2_y_lank/mega_absol_battle_name.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_2_y_lank/mega_absol_battle_name.png>)
- 検知キー：`POKEMON_ZA_MEGA_ABSOL_BATTLE_NAME`
- 対応時の論点：相手名・技名・攻撃予告を判別。背景色や通常HPバーだけへの置換は意味を失う。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_2_story_absol_battle:22627](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:22627>) | `ZA_mega_evolution_battle_mode_select` | あり |


## reibi_skill.png

- 分類：メニュー・技・道具／日本語の単語・文章
- 主な表示：れいとうビーム
- 画像：[Template/ZA_Story/_4_e_lank/reibi_skill.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_4_e_lank/reibi_skill.png>)
- 検知キー：`POKEMON_ZA_REIBI_SKILL`
- 対応時の論点：メニュー内容・技名・道具名を含む。道具や技の小アイコンは他項目との区別を別途確認する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_4_story_shiro_32:24739](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:24739>) | `ZA_common_skill_change_function` | 見つからず |


## water_icon.png

- 分類：メニュー・技・道具／日本語の単語・文章
- 主な表示：おいしいみず
- 画像：[Template/ZA_Story/_6_c_lank/water_icon.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_6_c_lank/water_icon.png>)
- 検知キー：`POKEMON_ZA_WATER_ICON`
- 対応時の論点：メニュー内容・技名・道具名を含む。道具や技の小アイコンは他項目との区別を別途確認する。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [_6_story_yukari_48:27309](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:27309>) | `image_check` | あり |


## last_battle_name.png

- 分類：ボス戦の名前・技・予告／日本語の単語・文章
- 主な表示：超大暴走アンジュフラエッテ
- 画像：[Template/ZA_Story/_8_last/last_battle_name.png](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/reference_templates/_8_last/last_battle_name.png>)
- 検知キー：`POKEMON_ZA_LAST_BATTLE_NAME`
- 対応時の論点：相手名・技名・攻撃予告を判別。背景色や通常HPバーだけへの置換は意味を失う。

| 使用関数・行 | 渡し先／判定 | 関数の録画記録 |
| --- | --- | --- |
| [ZA_mega_mode5_last_name_no_hard_timeout:3971](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:3971>) | `image_check` | 見つからず |
| [ZA_mega_mode5_defeat_event_name_recovery_ready:6453](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6453>) | `image_check` | あり |
| [ZA_mega_mode5_event_name_ui_missing_update:6571](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/source/recorded_ZA_story.py:6571>) | `image_check` | 見つからず |

