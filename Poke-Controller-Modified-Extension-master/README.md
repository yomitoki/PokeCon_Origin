# Poke-Controller Modified Extension

[moi_poke](https://github.com/Moi-poke)氏が開発した[Poke-Controller Modified](https://github.com/Moi-poke/Poke-Controller-Modified)をベースに機能を追加したゲーム機自動化支援ソフトウェアです。

[Poke-Controller Modified](https://github.com/Moi-poke/Poke-Controller-Modified)からUIを一新、並列起動や対応ゲーム機の種類を増やしています。(ver. 0.1.6時点ではSwitch/3DS/DS/GCに対応。)

また、Modified版に対する後方互換性保持をMUSTとして開発をしています。
2025/3/31時点では、[Poke-Controller Modified](https://github.com/Moi-poke/Poke-Controller-Modified)で動作する自動化のスクリプト(後述)はすべて動作する(はず)です。

![カイリューかわいい](https://github.com/futo030/Poke-Controller-Modified-Extension/blob/image/pokecon_modified_extension_image_20250402.png)


## 更新履歴

[Github - 更新履歴](https://github.com/futo030/Poke-Controller-Modified-Extension/blob/master/changelog.txt)

ZA Storyの多言語向け判定は、[補完対応と残件（画像・動画付き）](reports/za_story_multilingual_20261024/remaining_checks_current.html)へ整理しています。本PokeConのCommands開始時だけ設定でき、毎回デフォルトOFFです。非文字図柄、選択行、最終戦の敵アイコンによる継続回避、初戦再開のワニノコ図柄、駅の「？」を使います。第3章の通常会議経路は、補完ONで目的表示やコメント数の判断を省き、会話処理後の非戦闘FIELDで次へ進みます。リセット後の会議前／後の分岐とZ_23のNPC回避は非文字代用が残っています。40項目59画像のうち実装33項目、残件2項目（第3章は一部対応）、保留5項目。多言語実機での通し実行は未確認です。

移動Aの通常モード修正は[復旧先・初回ResetDebug・未確定一覧](reports/za_story_multilingual_20261024/movement_a_reset_debug.html)を参照してください。固定到着点は最大3秒ずつA表示を確認し、失敗が12秒以上続けば登録した復旧先へ戻します。通常失敗と初回確認で177 Stepの復旧先を共用し、別途4つの共通処理内での戻しを維持。初回確認はResetDebug有効時のみ20秒待機し、同じ経路の完了履歴を共有します。復旧先未確定は13 Step。Z_40等の途中探索は待機なし、19番の即時退出は既存の速度を維持します。

A復旧・初回確認の追加後は、関連130テストと177経路を両モードで模擬実行する2テストが成功。必須全体はRan 878 tests in 609.605s / FAILED (failures=19, errors=8, skipped=1)で、直前の全体検査から診断名の追加0件です。全体成功や実機リセット／ロードの確認済みとは扱いません。既存の補完native変更の反映には本体再起動が必要ですが、今回その再起動やゲーム操作は実施していません。

## Origin：表示サイズ・2画面・条件クリップ

本体を完全に終了して再起動すると反映されます。CommandsのF5 Reloadだけでは反映されません。

### 表示サイズと取得解像度

Cameraタブの「表示をウィンドウに合わせる（取得解像度は固定）」で、縦横比を保ってプレビューだけを拡大・縮小します。Show Sizeを手動で選ぶと自動調整はOFFになります。録画・通常スクリーンショットはカメラの取得解像度を使い、範囲選択は表示座標から実際の取得画像の座標に変換します。リサイズ途中の選択枠は解除されるので、必要な範囲を選び直してください。

### 1つのPokeConで2画面

Main Panelの「2画面」を押し、副画面で保存済みInputSetを選んで「接続」します。それぞれ別のカメラ・Serial・録音入力を使います。他の画面で使用中の機器、識別情報が合わない機器への接続は停止します。

- 主画面・副画面でCommandsを個別に選択し、Start／Stop／Pauseできます。副画面の手動操作は副画面のControllerを使います。通常のキーボード操作は主画面が対象です。
- 副画面は表示15fps、録画中は表示・保存30fpsを上限とし、カメラ入力は60fpsを要求します。実際のFPSは機器・処理負荷に依存します。主画面の既存の優先設定は維持します。
- 「両方スクショ」で取得解像度の画像を2枚保存します。主画面のRecordingをManualにして「両方録画開始」「両方録画停止」でまとめて操作できます。
- 副画面の動画は通常録画先の `secondary` フォルダーへローカル保存します。副画面ではスピーカー再生を増やさず、InputSetで選んだ入力音声を録音します。MP4作成が終わるまで終了処理が待機することがあります。
- 画像・出力・Pause・Serial形式・テンプレートパスを画面ごとに分離しています。副画面のCommands実行中は全体のF5 Reloadを止めます。任意のユーザースクリプトが独自に使うグローバル変数や同名の保存ファイルまでは分離しません。

### 条件部分を別の保存先へ残す

Main Panelの「条件クリップ」で設定します。**全体動画は従来の設定どおりYouTubeへアップロードし、条件クリップは指定した別フォルダー／別ドライブへローカル保存します。** クリップを自動でYouTubeへ送る設定ではありません。

1. ①へ指定画面の登録画像またはPNGを追加します。必要なら②へFIELD／HARD判定に使う画像を追加し、AND／OR、継続秒、①→②の制限秒を指定します。「一致／不一致」で、表示されないことも条件にできます。登録画像の閾値・探索範囲・パターンのAND／OR・指定個数以上の一致を引き継ぎます。空のグループで「ZA HARD」を押すと、FIELD前／後のいずれか、手持ち／FIELD確認のいずれか、戦闘ボール／Escapeの不在をANDで追加します。これは2026-10-23の非戦闘HARDを同一フレーム上で確認する画像条件で、実機の連続fresh frame確認は実行しません。必要な安定時間は「継続秒」で指定します。
2. 成立前・成立後の秒数を指定します。基準は②の成立時刻（②が空なら①）です。前後はそれぞれ最大300秒で、重なる区間は1本にまとめます。
3. 「条件クリップ専用保存先」と「保存先上限GB」を指定します。容量はその保存先以下のMP4の合計です。上限に達した区間は保存を見送り、既存のクリップは削除しません。通常録画のセッションフォルダー内は、アップロード後の削除に巻き込まれないよう指定できません。
4. 自動保存を有効にして「設定を適用・保存」を押します。以後のアップロード予約から反映されます。InputSet／録画セットにも残したい場合は、そのセットを明示的に保存してください。予約済み動画には予約時の条件が使われます。

自動解析は全体動画の完成後、アップロード前に実行します。ライブで別の録画を重ねる方式ではありません。アップロードしない録画や副画面の動画は「完成動画を選んで解析・保存」からMP4を指定できます。解析は中止でき、元動画は変更しません。別ドライブへアクセスできない等でクリップ保存に失敗しても全体動画のアップロードは続け、再試行用に元動画を保持します。

解析間隔0は全フレーム、それ以外は指定間隔に近いフレーム間隔で確認します。標本の間だけに出る短い表示は検出できないため、短い演出は間隔を狭くしてください。条件クリップの音声は、Originの音声同期補正を終えた完成MP4から映像と同じ区間を切り出します。判定結果・元動画・保存区間は保存先内の `events.json` に残ります。

**Windowsに残す条件クリップは、画像検知へ登録する画像の元として使えます。** アップロード前のローカル完成MP4から、元の解像度・FPS・色形式を保った可逆圧縮の映像を保存します。全体動画がアップロード後に削除されても、残したクリップだけから元解像度のフレームを読み出せます。必要な範囲をそのフレームからPNGで切り出して登録すると、探索範囲にも同じ元解像度の座標を使えます。元の録画に既にある圧縮や、異なる画面・描画条件による検知差までは解消しません。

可逆圧縮は以前の条件クリップより容量が増えるため、前後秒数と保存先上限GBで調整してください。既存クリップは保持し、この変更以後の新規作成分から適用します。旧方式で作成済みのクリップを新方式のキャッシュとして流用せず、元動画から再解析した場合は別の出力として保存します。元動画・通常アップロードの画質設定は変えません。

2026-10-23の検証では、別プロファイルの実カメラ2台で表示サイズ変更、1280×720の2枚保存、主60fps／副30fpsのMP4保存を確認しました。入力はおおむね60fpsでしたが、表示60fpsの安定は未達です。実機音声の最終的な同期確認と、通常プロファイルでの独立Commandsの通し実行は未確認です。


## Poke-Controller とは?

Poke-Controllerの概要は[KawaSwitch](https://github.com/KawaSwitch)氏が開発した[Poke-Controller](https://github.com/KawaSwitch/Poke-Controller)および[moi_poke](https://github.com/Moi-poke)氏が開発した[Poke-Controller Modified](https://github.com/Moi-poke/Poke-Controller-Modified)を参照してください。


## Poke-Controller Modifiedとの差分について

[Poke-Controller Modified](https://github.com/Moi-poke/Poke-Controller-Modified)に対し、以下の機能追加および仕様変更を実施しています。
- 使用時における便利機能の追加
  - 2つ目のログ画面を追加(常時表示しておきたい情報の表示を想定)
  - 更新確認機能を追加
  - シリアルデバイスをコンボボックスで設定する機能を追加
  - スクリプトのFilter機能を追加
  - スクリプトのショートカット割り当て機能を追加
  - スクリプトの一時停止機能を追加
  - ログ画面クリア機能を追加
  - ログ画面の上書き用関数を追加
  - メインウィンドウに埋め込まれたソフトウェアコントローラーを追加(表示ON/OFF可能)
  - スクリプト一時停止機能を追加
  - ToolTip表示機能を追加
- スクリプト開発に役立つ機能の追加
  - 画像認識時の類似度を自動化スクリプトの記載によらず出力できる機能を追加(ON/OFF可能)
  - 画像認識時の探索範囲および認識結果をGUI上に表示する機能を追加(ON/OFF可能)
  - 画面キャプチャ機能を拡張
    - キャプチャしている画面部分を'Ctrl+Alt+左クリック'しながらドラッグした範囲をキャプチャすることが可能\
      このとき、名前をつけて保存のダイアログボックスが出て、任意の名前をつけることが可能
- スクリプト開発者への問い合わせ時に必要な情報の表示する機能の追加
  - ライブラリのversion情報の表示機能の追加
  - 問い合わせ用テンプレート文章作成アシスタント機能の追加
- 並列起動への対応
  - ProfileによるPokeCon側の設定複数保持機能を追加
  - 同一名称のキャプチャデバイスが接続された場合に対応できるよう仕様を変更
- 3DS自動化基板への対応([Qingpi](https://qiita.com/u1f992/items/09617ae326288a0df703)/3DS Controller)
  - 送信するシリアルデータのフォーマットを3種(Poke-Controller向け/Qingpi向け/3DS Controller向け)から選択する機能を追加
  - PokeConの画面上でタッチスクリーンを操作する機能を追加([Qingpi](https://qiita.com/u1f992/items/09617ae326288a0df703)のみ)
- ゲームパッドによる操作への対応
  - Pro-Controllerによる操作機能を追加(ver.0.1.5時点ではPro-Controllerのみ対応。)
  - 操作時のログを取得する機能を追加(再生可能)
- MQTTおよびSocket通信関連への対応
  - 関連する関数を追加
- 画像認識関連の関数の拡張
  - 画像の2値化に対応
  - 引数および関数を追加
- ダイアログ関数の拡張
  - ウィジェットの複数列表示(改行)機能を追加
  - 前回の入力の保持や呼び出しが可能なダイアログ関数を追加
- 通知機能の拡充
  - WindowsのNotificationによる通知機能を追加
  - ~~Discord Webhookを用いた通知機能を追加~~(同様の機能が[Poke-Controller Modified](https://github.com/Moi-poke/Poke-Controller-Modified)に実装済み)
  - プログラムの開始および終了時に通知する機能を追加(ON/OFF可能)
- UI刷新(設定画面のタブ化およびログ画面を2画面化)
  - ログ画面の2画面化に伴う機能の追加(サイズや標準出力先など)
  - レイアウトカスタマイズ機能の追加


## 推奨環境

- OS
  - Windows10/11
  - (一応Mac/Linuxでも動作するはずですが未確認です。issueおよびPRには対応します。)
- Python
  - 3.12以上(従来の3.7はサポートが終了しているためサポート対象外とします。)


## 開発環境

Python 3.12.2


## Installation

必要なライブラリは[Github - requirements](https://github.com/futo030/Poke-Controller-Modified-Extension/blob/master/requirements.txt)を参照してください。


## Wiki

現在作成を検討しております。
3DSの自動化については[こちら](https://draco-meteor.hatenablog.com/entry/20240514)の記事を参照ください。


## 謝辞

[Poke-Controller](https://github.com/KawaSwitch/Poke-Controller)の開発者である[KawaSwitch](https://github.com/KawaSwitch)氏、[Poke-Controller Modified](https://github.com/Moi-poke/Poke-Controller-Modified)の開発者である[moi_poke](https://github.com/Moi-poke)氏にそれぞれ感謝申し上げます。

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tr>
    <td align="center"><a href="https://github.com/KawaSwitch"><img src="https://avatars3.githubusercontent.com/u/41296626?v=4" width="100px;" alt=""/><br /><sub><b>KawaSwitch</b></sub></a><br /><a href="https://github.com/KawaSwitch/Poke-Controller/commits?author=KawaSwitch" title="Code">💻</a> <a href="#maintenance-KawaSwitch" title="Maintenance">🚧</a> <a href="https://github.com/KawaSwitch/Poke-Controller/commits?author=KawaSwitch" title="Documentation">📖</a> <a href="#question-KawaSwitch" title="Answering Questions">💬</a></td>
    <td align="center"><a href="https://github.com/Moi-poke"><img src="https://avatars1.githubusercontent.com/u/59233665?v=4" width="100px;" alt=""/><br /><sub><b>Moi-poke</b></sub></a><br /><a href="https://github.com/KawaSwitch/Poke-Controller/commits?author=Moi-poke" title="Code">💻</a> <a href="#question-Moi-poke" title="Answering Questions">💬</a></td>
  </tr>
</table>

<!-- markdownlint-enable -->
<!-- prettier-ignore-end -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

## 貢献

このプロジェクトは, [all-contributors](https://github.com/all-contributors/all-contributors)仕様に準拠しています. どんな貢献も歓迎します。


## ライセンス

本プロジェクトはMITライセンスです。
詳細は [Github - LISENCE](https://github.com/futo030/Poke-Controller-Modified-Extension/blob/master/LICENSE) を参照ください。
※今後変更の可能性があります。

また, 本プロジェクトではLGPLライセンスのDirectShowLib-2005.dllを同梱し使用しています。
[About DirectShowLib](http://directshownet.sourceforge.net/)

<!-- ZA_A_REMAINING_20261025_START -->
### 2026-10-25: ZA Storyの連戦Aチェックと復旧先

YUKARI_64/68/72/76/80/84/88/92の移動後A表示チェックを一時無効にしました。A入力と連戦処理は維持し、連戦終了後のDOOR往復は別の残件です。

前回の復旧未確定13か所は10追加・2一時除外・1未確定。共通のポケモン回復10か所にもgotoからのやり直しを追加しました。[動画・画像付きの復旧先と未対応一覧](reports/za_story_multilingual_20261024/movement_a_reset_debug.html)を参照してください。稼働中Commandsへ反映するには停止後のF5 Reloadが必要です。実機でのロード確認は未実施です。
<!-- ZA_A_REMAINING_20261025_END -->
