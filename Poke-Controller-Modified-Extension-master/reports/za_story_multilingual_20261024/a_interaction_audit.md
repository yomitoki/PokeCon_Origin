# ZA_Story 移動後のA入力・L調整・入口確認

追補：[移動後A確認・動画・補完残件の最新版](movement_a_checks.html)。固定移動後Aを通常モードでも確認し、補完ONでは対応するA成功18件の場所確認を代用しました。残件はマップ26件・その他59画像です。**以下は今回の対応前の履歴です。「A未追加」「マップ44件が未代用」等は当時の状態を記録しています。**

## 追加対応：17番・美術館・ド・フツーのL、カフェと道場のA省略

ユーザーの動画確認を受けて、17番、美術館の入館、美術館の館内から戻る操作、レストラン・ド・フツーの4関数で、最後の方向移動と既存の待機の後にLを1回追加した。Lはduration=0.15、wait=0.5、interval=0.1で、その後に既存のAを押す。方向入力の角度・秒数は変えていない。

美術館の館内から戻るAは退出操作として残し、「A でる」の表示も想定するコメントを付けた。今回の4関数にA表示の判定は追加していない。14番・19番の最大3秒の入場チェックは既存どおり。

カフェ・アルティメットとジャスティス会道場は、移動後のAをコメントアウトした。カフェは通過による登録が目的であること、道場はAを使わず次の登録確認へ進むことをコードに記載。既存のマップ登録確認と、未登録時の再移動は維持している。

| 対象 | 変更後の処理 | 対象関数 |
| --- | --- | --- |
| ワイルドゾーン17 | 最後の0度・2秒 → 既存待機 → L → A | `_6_story_mapping_3` |
| 美術館・入館 | 最後の270度・5秒 → 既存待機 → L → A | `_2_story_mapping_80` |
| 美術館・館内から戻る | 270度・1秒 → 既存待機 → L → 退出A | `_2_story_mapping_81_0` |
| レストラン・ド・フツー | 最後の280度・3秒 → 既存待機 → L → A | `_2_story_mapping_99` |
| カフェ・アルティメット | 340度・19秒 → 既存待機 → 登録確認87（A省略） | `_2_story_mapping_86` |
| ジャスティス会道場 | 最後の310度・8秒 → 既存待機 → 登録確認103（A省略） | `_2_story_mapping_102` |

Origin・stock・保存ZIP・clean DevStudio documentの対象6関数だけを同期した。Python 3.7構文解析・compile、対象外関数のAST、方向移動・既存画像チェック、ZIPの対象外427memberを確認済み。必須全体テストは「Ran 869 tests in 780.709s / FAILED (failures=19, errors=8, skipped=1)」。直前の戦闘復旧変更後の診断一覧と比較し、追加0件・解消0件。全体成功ではない。実ゲームでの表示・登録成功は未確認で、PokeConへの停止・Reload・実機入力は行っていない。

[今回の検証結果](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/.codex_tmp/za_mapping_l_alignment_20261024/verification_result.json>) ／ [今回の差分](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/.codex_tmp/za_mapping_l_alignment_20261024/source_changes.patch>) ／ [同期検査結果](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/.codex_tmp/za_mapping_l_alignment_20261024/mirror_sync.json>)

## 19番：入場確認を必須化し、退出の速度を維持

19番の固定移動後は、既存のL入力のあとに「A はいる」を最大3秒確認し、検出できた場合だけ最初のAを押す。未検出ならAを送らず、Common状態とマップカーソルを初期化して`7_STORY_MAPPING_5`の時間変更・移動元からやり直す。

入場後の270度・1秒の移動と、その後のAは退出操作である。ユーザーから、ゾーン内ではマップ移動できず、すぐ退出しないと出られなくなる可能性があるとの説明があった。動画でも入場直後の発見表示を確認したため、**退出時には画像取得・待機を追加していない**。既存の入場Aのwait=2.0、退出方向移動のduration=1.0・wait=0.5、退出Aのrepeat=3・wait=1.0を維持した。

`POKEMON_ZA_OUT_MARKER`（「A でる」）の任意チェックは、退出Aの直前にコメントアウトして用意した。有効化する場合も、未検出をゲームリセットへ直結させず、既存の`7_STORY_MAPPING_8`の戦闘・登録確認へ進む形としている。現在はこのコメント部分を実行しない。

変更箇所：[_7_story_mapping_7](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:33430>)。

- [1:37:50から：19番の入口と退出の一連の動作](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5870s)
- [1:37:54：「A はいる」](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5874s)
- [1:37:57：「A でる」と発見表示](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5877s)

これらはZIPに記録された旧版の動作であり、今回の入口チェックを実機で動かした録画ではない。

## 14番：最後の移動後にLを追加

14番の入口処理を、**最後の移動 → Lを1回 →「A はいる」を最大3秒確認 → A入力 → 既存のマップ登録確認**へ変更した。表示が確認できなければAを送らず、`5_STORY_MAPPING_1`の時間変更・移動元からやり直す。ゲームリセットは追加していない。

変更箇所は[_5_story_mapping_3](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:30944>)。移動の角度・秒数は維持している。最後の移動は実コードでは85度・0.3秒で、その直前が0度・2.5秒。Lはこの85度の微調整も終わった位置に追加した。

Aは1回ずつ最大3回。最初のAで入口表示が消えた場合は残りを送らず、`5_STORY_MAPPING_4`へ進めて登録結果を確認する。入場後にA表示が無いことを、復帰の理由にはしない。

## 14番の参照動画

参照元は `D:/Recording/Switch_No3.zip` 内の `youtube_remote.json`。14番は次の同じ動画の区間になる。

- [35:09から：14番への徒歩移動開始](https://www.youtube.com/watch?v=u3_WGptNscg&t=2109s)
- [35:33から：入口付近とA入力](https://www.youtube.com/watch?v=u3_WGptNscg&t=2133s)
- 操作記録上の移動状態は2109.246〜2138.360秒。2137.917秒の保存画像はA連打処理中で、入口付近の緑の柱が大きく映り、A表示を確認できない。動画でも今回の観察では入力直前のA表示を確定できなかったため、「元動画で常にAが見える」とは判断していない。

今回のL追加は、この入口で向きと視点をそろえてから確認するためのユーザー指定の変更。**L追加後の14番入口の実機映像は未確認**で、保存済みの他施設の「A はいる」を使った検出試験とは区別する。

## A表示を確認しない固定移動の箇所

Originの変更前のマップ登録用固定移動では22関数・23か所のA呼出しがあり、A表示を入力前の条件にしていなかった。うち11関数がワイルドゾーン向け。開始時のFIELDや手持ちアイコンの確認と、A入力後のマップ登録確認は存在する。

14番と19番の2関数に入口チェックを追加した。その後、カフェ・アルティメットとジャスティス会道場の2関数はAをコメントアウトした。残る18関数のA表示チェックは未追加で、うち4関数は今回Lだけを追加している。以下の復帰先は、主に既存のマップ登録不成立時の戻り先であり、全てにA未検出からの復帰が実装済みという意味ではない。

| 目的地または経路 | 固定移動の関数 | 現行の入力前確認・Aの扱い | 既存のやり直し先 | ZIP操作記録の移動区間 |
| --- | --- | --- | --- | --- |
| ワイルドゾーン4 | [_2_story_mapping_2](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25334>) | A表示の確認なし | `2_STORY_MAPPING_1` | [1:38:18〜1:39:07](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=5898s)<br>[1:39:29〜1:40:18](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=5969s) |
| ローリングドリーマー | [_2_story_mapping_8](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25443>) | A表示の確認なし | `2_STORY_MAPPING_7` | [1:41:22〜1:41:43](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6082s) |
| ワイルドゾーン2 | [_2_story_mapping_38](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:25994>) | A表示の確認なし | `2_STORY_MAPPING_37` | [1:53:14〜1:53:40](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6794s) |
| ワイルドゾーン5 | [_2_story_mapping_41](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26054>) | A表示の確認なし | `2_STORY_MAPPING_40` | [1:54:06〜1:54:27](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6846s) |
| ワイルドゾーン6 | [_2_story_mapping_44](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26104>) | A表示の確認なし | `2_STORY_MAPPING_43` | [1:54:53〜1:55:35](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6893s) |
| レストラン二流 | [_2_story_mapping_77](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26699>) | A表示の確認なし | `2_STORY_MAPPING_76` | [4:41〜5:58](https://www.youtube.com/watch?v=BLM81UP9V5I&t=281s) |
| ミアレ美術館への移動 | [_2_story_mapping_80](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26753>) | L追加、A表示の判定は未追加 | `2_STORY_MAPPING_79` | [6:36〜7:08](https://www.youtube.com/watch?v=BLM81UP9V5I&t=396s) |
| ミアレ美術館の追加操作 | [_2_story_mapping_81_0](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26767>) | L追加、退出Aを維持（A でるも想定） | `2_STORY_MAPPING_79` | [7:08〜7:19](https://www.youtube.com/watch?v=BLM81UP9V5I&t=428s) |
| ホテル・シュールリッシュ | [_2_story_mapping_83](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26819>) | A表示の確認なし | `2_STORY_MAPPING_82` | [7:37〜8:16](https://www.youtube.com/watch?v=BLM81UP9V5I&t=457s) |
| カフェ・アルティメット | [_2_story_mapping_86](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26871>) | Aをコメントアウト、登録確認へ | `2_STORY_MAPPING_85` | [8:33〜9:00](https://www.youtube.com/watch?v=BLM81UP9V5I&t=513s) |
| カフェ・バタイユへの経路 | [_2_story_mapping_92](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:26974>) | A表示の確認なし | `2_STORY_MAPPING_91` | [10:08〜10:56](https://www.youtube.com/watch?v=BLM81UP9V5I&t=608s) |
| ラシーヌ工務店 | [_2_story_mapping_96](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27037>) | A表示の確認なし | `2_STORY_MAPPING_95` | [11:29〜12:10](https://www.youtube.com/watch?v=BLM81UP9V5I&t=689s) |
| レストラン・ド・フツー | [_2_story_mapping_99](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27091>) | L追加、A表示の判定は未追加 | `2_STORY_MAPPING_98` | [12:27〜13:12](https://www.youtube.com/watch?v=BLM81UP9V5I&t=747s) |
| ジャスティス会道場 | [_2_story_mapping_102](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27151>) | Aをコメントアウト、登録確認へ | `2_STORY_MAPPING_101` | [13:45〜15:02](https://www.youtube.com/watch?v=BLM81UP9V5I&t=825s) |
| レストラン・エクストリーム | [_2_story_mapping_105](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:27215>) | A表示の確認なし | `2_STORY_MAPPING_104` | [15:25〜16:21](https://www.youtube.com/watch?v=BLM81UP9V5I&t=925s) |
| ワイルドゾーン8 | [_2_story_mapping_112](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28103>) | A表示の確認なし | `2_STORY_MAPPING_110` | [45:43〜46:44](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2743s) |
| ワイルドゾーン9 | [_2_story_mapping_114_1](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28168>) | A表示の確認なし | `2_STORY_MAPPING_114_0` | [48:22〜48:42](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2902s) |
| ワイルドゾーン10 | [_2_story_mapping_116_1](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:28231>) | A表示の確認なし | `2_STORY_MAPPING_116_0` | [49:09〜49:39](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2949s) |
| ワイルドゾーン14 | [_5_story_mapping_3](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:30944>) | L後「A はいる」を最大3秒 | `5_STORY_MAPPING_1` | [35:09〜35:38](https://www.youtube.com/watch?v=u3_WGptNscg&t=2109s) |
| ワイルドゾーン17 | [_6_story_mapping_3](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:32530>) | L追加、A表示の判定は未追加 | `6_STORY_MAPPING_1` | [1:14:58〜1:15:19](https://www.youtube.com/watch?v=DHVY6rsajPM&t=4498s) |
| ワイルドゾーン18 | [_7_story_mapping_3](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:33372>) | A表示の確認なし | `7_STORY_MAPPING_1` | [1:34:48〜1:35:24](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5688s) |
| ワイルドゾーン19 | [_7_story_mapping_7](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:33430>) | 入場は「A はいる」を最大3秒。退出チェックはコメントアウト | `7_STORY_MAPPING_5` | [1:37:07〜1:37:59](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5827s) |

上表の区間リンクは操作ログの状態遷移から特定したもの。映像上の表示確認結果は次の表に分けて示す。美術館は2段階の処理があるため2関数として数える。`_2_story_mapping_92`は追加移動の93を経て94で登録確認を行う。

## 固定移動22関数の動画上のA表示

対象は方向移動後のAであり、コメント送り、メニュー操作、EVENT方向へ接近しながら繰り返すAは含めない。ZIP内リンクの該当区間をブラウザーで停止・コマ送りして観察した。下表の秒数はプレーヤーに表示された時刻で、操作ログのイベント時刻と完全に一致するとは限らない。

「未確認」は今回見た画面でA表示を確認できなかったという意味であり、全フレームで表示されないことや検知不能を証明したものではない。「確認」も、同じ画像検知閾値で全条件・全言語に安定することを意味しない。

| 対象 | 動画の確認位置 | 観察結果 |
| --- | --- | --- |
| ゾーン4・初回 | [1:39:05](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=5945s) | 柱に寄った位置でA表示を未確認。その後、同経路の再移動が記録されている。 |
| ゾーン4・再移動 | [1:40:17](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6017s) | 「A はいる」を確認。初回の位置ずれをAチェックで拾う意義がある。 |
| ローリングドリーマー | [1:41:41](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6101s) | ZIPの未加工保存画像でも「A はいる」を確認。 |
| ゾーン2 | [1:53:39](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6819s) | 横からの視点で「A はいる」を確認。 |
| ゾーン5 | [1:54:25](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6865s) | 「A はいる」を確認。 |
| ゾーン6 | [1:55:33](https://www.youtube.com/watch?v=22Lc8za8OfQ&t=6933s) | 「A はいる」を確認。 |
| レストラン二流 | [5:55](https://www.youtube.com/watch?v=BLM81UP9V5I&t=355s) | 「A はいる」を確認。 |
| 美術館・入館 | [7:07](https://www.youtube.com/watch?v=BLM81UP9V5I&t=427s) | 柱・壁の近くでキャラクターが映らず、A表示を未確認。視点調整の検討候補。 |
| 美術館・館内から戻る追加操作 | [7:18〜7:19](https://www.youtube.com/watch?v=BLM81UP9V5I&t=438s) | 館内画面でA表示を未確認。7:24ではロード画面。移動で始まる画面切替とAの必要性を区別して確認する必要がある。 |
| ホテル・シュールリッシュ | [8:15](https://www.youtube.com/watch?v=BLM81UP9V5I&t=495s) | 最後の位置調整後に「A はいる」を確認。 |
| カフェ・アルティメット | [8:57〜8:59](https://www.youtube.com/watch?v=BLM81UP9V5I&t=537s) | A表示を未確認。8:57には既に移動スポット登録表示が見えるため、A未表示だけで登録失敗としない。 |
| カフェ・バタイユへの経路 | [10:55](https://www.youtube.com/watch?v=BLM81UP9V5I&t=655s) | 途中のゾーン入口で「A はいる」を確認。カフェへの会話Aではない。 |
| ラシーヌ工務店 | [12:08](https://www.youtube.com/watch?v=BLM81UP9V5I&t=728s) | 扉の前にA表示を確認。明るい背景で文字のコントラストは低い。 |
| レストラン・ド・フツー | [13:10](https://www.youtube.com/watch?v=BLM81UP9V5I&t=790s) | 移動終点でキャラクター・入口が映らず、A表示を未確認。視点調整の検討候補。 |
| ジャスティス会道場 | [15:00](https://www.youtube.com/watch?v=BLM81UP9V5I&t=900s) | 広場内の到着位置でA表示を未確認。入口操作と同じA必須条件にしてよいかは追加検証が必要。 |
| レストラン・エクストリーム | [16:20](https://www.youtube.com/watch?v=BLM81UP9V5I&t=980s) | 「A はいる」を確認。 |
| ゾーン8 | [46:42](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2802s) | 「A はいる」を確認。 |
| ゾーン9 | [48:41](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2921s) | 「A はいる」を確認。 |
| ゾーン10 | [49:37](https://www.youtube.com/watch?v=Tivo8Fsbbdg&t=2977s) | 横からの視点で「A はいる」を確認。 |
| ゾーン14 | [35:33〜35:38](https://www.youtube.com/watch?v=u3_WGptNscg&t=2133s) | 追跡調査で、録画切替時に実時間に対し約7.0秒の欠落を確認。最後の0度・85度の移動部分が記録に残らず、次の記録はA処理中。視点だけが原因とは判断できない。L追加後の実機確認は未実施。 |
| ゾーン17 | [1:15:17〜1:15:20](https://www.youtube.com/watch?v=DHVY6rsajPM&t=4517s) | 追跡調査で、録画切替時に実時間に対し約8.2秒の欠落を確認。最後の0度移動とAの記録が抜け、次は登録確認状態。A直前に入口を向いていたか、動画だけでは判断できない。 |
| ゾーン18 | [1:35:22](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5722s) | 「A はいる」と、その後の通過を確認。 |
| ゾーン19 | [1:37:54](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5874s) ／ [1:37:57](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5877s) | 最初は「A はいる」、入場後の方向移動では「A でる」を確認。後段を再入場チェックにしない。 |

22関数中15関数では関連するA表示を確認し、7関数（14・17、美術館2関数、アルティメット、ド・フツー、道場）は上記の観察範囲では未確認。4番を2回分に分けたため、表は23行。マップ登録以外のホテル内移動・ベンチ・ラボなどを含む全A呼出しを映像確認したものではない。

[追加確認の保存画面一覧とhash](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/data/a_interaction/followup_screenshot_manifest.json>) ／ [19番「A はいる」](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/a_interaction/youtube_zone19_before_first_a.png>) ／ [19番「A でる」](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/a_interaction/youtube_zone19_between_a.png>) ／ [17番の観察画面](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/a_interaction/youtube_zone17_transition_edge.png>)

## 方向入力を含めた再確認と、14・17番の録画欠落

録画版の上記7関数はすべて、コード上は方向移動を行ってからAを押す。入口画像の座標などを使って「入口へ向き直す」専用処理はなく、最後の移動で決まる向きのままAを押す構成だった。方向入力が存在することだけでは、その向きが入口方向と一致していたとは断定できない。現在は冒頭のとおりL追加・A省略を反映しており、以下の入力列・実行時刻は録画版の記録である。

角度はPokeConの左スティック入力の定義で、0度=右、90度=上、180度=左、270度=下。`Stick.LEFT`は左スティックの指定であり、左方向という意味ではない。ゲーム世界の東西南北とも区別する。

| 対象・動画 | 録画版のAに至る最後の方向入力（終盤を抜粋） | 現行のL・A変更 | 記録から確認できた範囲 |
| --- | --- | --- | --- |
| [17番：1:15:10から](https://www.youtube.com/watch?v=DHVY6rsajPM&t=4510s) | 上90度・7.5秒 → **右0度・2秒** → A | 録画版なし／現行L追加済み | 最後の右入力はコード上あり。録画・実行行の記録は上入力中から次の登録確認状態へ飛んでいる。 |
| [美術館・入館：6:58から](https://www.youtube.com/watch?v=BLM81UP9V5I&t=418s) | 左やや下185度・18秒 → **下270度・5秒** → A | 録画版なし／現行L追加済み | 最後の下入力とAの実行中の行を両方確認。A処理はログの7:08.12〜7:08.45付近。 |
| [美術館・館内から戻る：7:13から](https://www.youtube.com/watch?v=BLM81UP9V5I&t=433s) | **下270度・1秒** → A | 録画版なし／現行L追加済み | 下入力とAの記録あり。A処理はログの7:18.95〜7:19.07付近。 |
| [アルティメット：8:51から](https://www.youtube.com/watch?v=BLM81UP9V5I&t=531s) | **右下340度・19秒** → A | Lなし／現行Aコメントアウト | 方向入力とAの記録あり。A処理はログの9:00.23〜9:00.78付近。入口へ向き直す追加入力はない。 |
| [ド・フツー：13:04から](https://www.youtube.com/watch?v=BLM81UP9V5I&t=784s) | 右やや上10度・2.5秒 → **下寄りの右下280度・3秒** → A | 録画版なし／現行L追加済み | 最後の280度入力とAの記録あり。A処理はログの13:11.65〜13:12.21付近。 |
| [ジャスティス会道場：14:50から](https://www.youtube.com/watch?v=BLM81UP9V5I&t=890s) | 上やや右75度・5秒 → **右下310度・8秒** → A | Lなし／現行Aコメントアウト | 最後の310度入力とAの記録あり。A処理はログの15:01.70〜15:01.91付近。入口へ向き直す追加入力はない。 |
| [14番：35:29から](https://www.youtube.com/watch?v=u3_WGptNscg&t=2129s) | 右0度・2.5秒 → **上やや右85度・0.3秒** → A | 録画版なし／現行は追加済み | この最後の2入力はコード上あり。記録は95度移動中からA処理中へ飛んでいる。現行は85度入力後にLと入口確認を追加済み。 |

録画版では14番以外の6関数は、最後の方向入力解除後に設定上合計1.5秒（pressのwait=0.5秒＋明示wait=1.0秒）待ってからA。14番の録画版は最後の85度入力後に0.5秒待ってA。表の実行時刻は、サンプリングされた実行中の行の時刻であり、物理ボタンを押し始めた正確な時刻ではない。

録画の不連続はZIPの`steps.jsonl`の実時刻と動画時刻を比較して確認した。

| 対象 | 録画切替前後の動画時刻 | 実時刻の経過 | 動画時刻の経過 | 差 |
| --- | --- | --- | --- | --- |
| 17番 | 1:15:19.162 → 1:15:19.367 | 8.384秒 | 0.205秒 | **約8.179秒** |
| 14番 | 35:37.832 → 35:37.917 | 7.117秒 | 0.085秒 | **約7.032秒** |

17番では切替前が90度・7.5秒移動の実行中、切替後が`6_STORY_MAPPING_4`。14番では切替前が95度・7.5秒移動中、切替後がA3回の実行中。したがって、この2件について前回示した「視点調整の候補」は仮説であり、最終移動時の向きやA表示を録画から直接確認できたという意味ではない。Lだけで足りるか、方向を合わせてからLが必要かは、この欠けた動画だけでは確定できない。

比較用の4番は、途中でL → 170度・16秒 → 80度・5秒 → A。最後の移動後のLはない。初回と再移動は同じ方向入力なので、位置ずれと視点の両方を分けて見る必要がある。

[方向入力と録画欠落の集計](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/data/a_interaction/direction_before_a_summary.json>) ／ [ZIPの実行行記録の抜粋](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/data/a_interaction/direction_before_a_log_evidence.json>)。今回の再確認でゲーム処理の変更や実機入力は行っていない。

マップ登録以外にも、ホテル内の固定移動後のA（例：[_1_story_hote_z_move3](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23225>)、[_1_story_hote_z_move5](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23253>)）、[ZA_Benchi](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:36787>)のA12回、[ZA_quasar_move_entrance](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:39320>)のA30回などがある。いずれもAの表示そのものを直前条件にしていないが、室内アイコン・FIELDや後続の会話・朝夜判定といった別の条件がある。ベンチ自体の失敗対策を、同じベンチ処理へ無制限に戻す構成にはしない。

既存の入口チェックの例は[_1_story_hote_z_move2](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23212>)の「A はいる」、[_1_story_farst_battle_zone_move3](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:23175>)の「A でる」、[ZA_quasar_move_door](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:39309>)のA図柄。14番では指定どおり「A はいる」の登録画像を使用し、探索範囲・閾値は変更していない。

## A図柄だけの広範囲検知で分かること

18番の動画では[1:35:22](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5722s)に「A はいる」、[1:35:24](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5724s)にゲートの通過演出、[1:35:26](https://www.youtube.com/watch?v=ugB3vep1qMI&t=5726s)に内側へ移った場面を確認した。A表示を入力前の条件にすることと、操作後に入場したことを確認することは、別の段階として扱える。

[18番のA表示](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/a_interaction/youtube_zone18_prompt.png>) ／ [通過演出](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/a_interaction/youtube_zone18_after_a.png>) ／ [通過後](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/evidence/a_interaction/youtube_zone18_entered.png>)

既存の `ZA_infi/doorA.png` は日本語を含まない15×14pxのA図柄で、保存された1280×720の画像へ照合した結果は次のとおり。値は正答率ではなく画像の類似度。

| 画面 | 文字を除いたA図柄の一致度 | 意味 |
| --- | --- | --- |
| レストラン入口「A はいる」 | 0.978335 | 入口操作の候補を検知できる |
| ラシーヌ付近のNPC「A 話しかける」 | 0.966045 | Aだけでは入口と会話を区別できない |
| ラボの「A 調べる」 | 0.959452 | 他の操作にも共通する図柄 |
| マップ下端の操作案内のAの一例 | 0.915490 | 画面全体を無条件に探すと操作案内も拾う |

探索範囲を仮に `(200,120)〜(1080,620)` にした場合、今回のマップ画面85入力サンプルでは0.85以上の一致が0件、全画面では75件だった。同じ場面の重複も含むため、誤検知率の評価ではない。NPCのAはこの範囲にも入る。フィールド状態の確認、メニュー等の除外、入口周辺の状況、入力後の変化を組み合わせる必要がある。

この広範囲・A図柄だけの判定は調査結果であり、14番・19番へ実装したのはユーザー指定の「A はいる」全文字画像のチェック。元のPNGはZIPに含まれないため、対応するローカル登録画像とZIPの未加工JPGを使って照合した。

## 復帰を追加する場合の扱い

固定移動を終えた状態だけでA表示の待機を開始し、入力前に表示が確認できなければ、その経路の既知の移動元へ戻す。時間帯をそろえる必要がある経路では既存の時間変更を経由する。14番・18番・19番・10番の既存復帰先にはこの経路がある。

A入力後は表示消失だけで失敗とせず、通過演出や移動後の状態を待ってから登録・到着結果を確認する。A表示が有るだけでは「目的のゾーン」を選べたことまでは確定できないため、多言語版で番号の画像が使えない場合も、Aの確認だけを目的地識別の代わりにはできない。

**EVENT方向へ接近しながらAを試す処理には、今回のA未表示による復帰を適用しない。** 例として[ZA_story_Template_battle_before_active_level](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:20430>)、[ZA_story_Template_battle_before_renda_route](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:21182>)、移動中の攻撃にAを使う[ZA_MOVE_ACTION](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Commands/PythonCommands/ZA/ZA_story/ZA_story.py:6174>)がある。現在の探索・戦闘の判定を維持し、Aが出ないことだけでゲームリセットしない。

## 変更と検証の範囲

19番の追加変更では専用7件と14番の既存9件、計16件が9.087秒で成功。遅れて出る入口表示、3秒未検出、期限後の画像取得、停止、FIELD不在、未加工の保存画像をfresh取得する実matcherを確認した。入場後に画像取得しないことと、入場Aから退出Aまでの入力間隔が変わらないことも検査した。

19番の即時検出時は、変更前ソースと変更後ソースを偽入力・偽時計で実行し、全方向移動・ボタン・入力時刻・終了時刻が一致した。Originの変更関数は19番の1関数のみで、14番・EVENT系・他関数のASTは不変。stock・既存ZA_story.zip・clean DevStudio保存documentも19番だけ同期し、ZIPの対象外427memberとmetadataを維持した。

19番変更後の必須全体チェックは869件／949.457秒でFAILED（19 failures・8 errors・1 skip）。14番変更時の診断名との差分は追加・解消とも0。全体成功とは扱わない。[19番の変更検証結果](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/.codex_tmp/za_zone19_entry_guard_20261024/verification_result.json>)。実機入力・Reloadは行っていない。

以下は14番変更時の検証記録。

専用9テストで、Lと移動とAの順序、2.9秒後の表示、3秒の未検出、期限後に完了する画像取得、表示消失後の残りA停止、最大3回、FIELD不在、ユーザー停止、保存画像をfresh取得する実matcherを確認した。保存画像は他施設の入口・NPCの会話・14番の演出中の画面であり、L追加後の14番を再録画したものではない。

Origin・stock・保存用ZA_story.zip・clean DevStudio保存documentの14番関数を同期した。新しい共通のA入力制限は追加せず、他の関数のAST、移動の角度・秒数、ZIP内の対象外427ファイルとmetadataを維持した。

必須の全体チェック869件は337.711秒で終了し、19 failures・8 errors・1 skip。直前の数字判定対応時と比べて診断の追加・解消は0で、全体成功ではない。[14番の変更検証結果](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/.codex_tmp/za_zone14_entry_guard_20261024/verification_result.json>)に記録した。稼働中PokeConへの停止・Reload・再起動・実機入力は行っていない。ユーザーがCommandsを停止した後にF5 Reloadする際に反映する。

[移動関数とZIP時刻の全データ](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/data/a_interaction/mapping_routes_with_times.json>) ／ [A図柄の試験値と画像hash](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_story_multilingual_20261024/data/a_interaction/a_icon_probe.json>)
