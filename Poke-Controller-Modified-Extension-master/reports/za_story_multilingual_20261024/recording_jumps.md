# 録画のジャンプと結合時の音声同期の点検

14番と17番付近のジャンプは、**録画の分割切替中に未記録時間が生じ、結合時に前後が直接つながることが主因と考えられる**。ZIPの操作記録・結合元の実尺情報・現行コードの処理順が一致する。音声付きの結合処理にも、後続区間の音が早まる条件と、通常録画の同期補正を通らない問題がある。

今回は処理の点検と人工データによる再現確認。録画・音声・アップロードの本体コード、設定、キュー、既存録画は変更していない。先行して依頼されたZA StoryのL追加4か所とA省略2か所は別途反映済み。

## 動画が飛ぶ位置と分割境界

| 対象 | 動画上の境界 | 操作記録の実時間差 | 動画上の時間差 | 差し引きの欠落推定 |
| --- | --- | --- | --- | --- |
| [14番](https://www.youtube.com/watch?v=u3_WGptNscg&t=2133s) | 35:37.916667、71区間目の末尾 | 7.117秒 | 0.084587秒 | 約7.03秒 |
| [17番](https://www.youtube.com/watch?v=DHVY6rsajPM&t=4517s) | 1:15:19.366667、150区間目の末尾 | 8.384秒 | 0.204526秒 | 約8.18秒 |

両動画とも結合元は240区間で、全区間60fps。14番側は434,490フレームで7,241.5秒、17番側は434,212フレームで7,236.866667秒。元区間の実尺合計と保存尺情報が一致する。`loop_compaction.applied`は双方Falseで、今回の境界は長いループを意図的に省略したものではない。

全239境界のうち、実時間と動画時間の差が1秒を超える境界は、14番側206件、17番側174件。差の中央値はそれぞれ約4.43秒・3.25秒で、対象場面だけの現象ではない。これは記録時刻からの推定であり、各フレームの欠落量を直接測った値ではない。

ZIP内の`youtube_remote.json`は双方とも動画1本・`part=1`・`processing_status=processed`。現在の[アップロード用分割処理](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/YouTubeArchive.py:1664>)も、1本なら元MP4をそのまま渡す。今回の境界がアップロード用の分割位置だったことを示す記録はない。

ZIPには当時の元AVI/WAV/MP4が含まれないため、当時の全フレームを結合前後で直接比較した結果ではない。参照動画はZIP内のリンクだけを使用した。

## 現行処理で空白が生じる経路

1. [分割切替](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Window.py:25690>)で、前の区間を停止する。
2. [停止処理](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Window.py:21198>)が記録情報の保存と映像・音声の終了処理を行う。停止中は通常の録画フレーム投入が抑止される。
3. [終了後のコールバック](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Window.py:21120>)から次の区間を準備する。
4. [準備完了後の時刻](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Window.py:20870>)を新しい録画の開始時刻にする。準備中の映像を新しい区間へ遡って保存する処理はない。
5. [結合処理](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/CommandRecordingMerge.py:553>)は保存された区間を順に連結する。通常の切替中の未記録時間は補填しない。

現在の実尺検査は各区間内の尺と完成MP4の総尺を照合するため、区間と区間の間の空白は検出対象になっていない。次区間の準備中も前区間の録画を継続し、映像と音声を同じ提示時刻で切り替えることが修正候補となる。フレームレートを変更して空白分を伸ばしても、未記録のゲーム動作は復元できない。

## 実際の結合関数とFFmpegによる再現確認

カメラやゲームを使わず、通し番号を持つ60fps・2秒の人工動画を2本作成し、現行の結合関数でMP4化した。4ケースとも240フレームが元の順序で残り、映像は4秒だった。区間の開始記録には意図的に5秒の空白を与えたが、出力は4秒で、その空白への警告はなかった。

| 音声の条件 | 結合後の観測 |
| --- | --- |
| 両区間とも2秒、各区間の0.5秒で音 | 0.5秒と2.5秒で音。区間境界の位置は一致 |
| 前区間のWAVだけ1秒、後区間は2秒 | 後区間の音が1.5秒に出現。本来の2.5秒より1秒早い |
| 後区間のWAVがない | 結合MP4全体に音声トラックがない |
| 提示時計の補正情報がある | 結合は未補正WAVを使用。通常録画で呼ぶ補正関数は呼ばない |

[結合時の音声処理](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/CommandRecordingMerge.py:527>)は、全区間のWAVがある場合だけ音声を結合し、連結全体の末尾へ`apad`を適用する。途中で短い音声があっても、その区間の末尾には補填しないため、後続の音が前へずれる。WAVが1本でもなければ`-an`で全体を無音にする。

[通常録画のMP4作成](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/SerialController/Recording.py:1988>)は`write_presentation_aligned_audio`を使うが、結合側は元WAVを直接連結する。提示時計に沿う補正、区間ごとの映像・音声の尺合わせ、音声がない区間だけの無音補填を、結合側にも適用する必要がある。固定オフセットや音量調整で代用しない。

上記は人工データで成立した既存の問題で、対象のYouTube動画で同じ音声ずれが起きたと実聴確認した結果ではない。通常の音声補正関数を使った短い人工音の比較も保存したが、同期精度や実聴品質の合否判定には使用していない。

## 変更の範囲と確認記録

録画関連8ファイルは点検前後のSHA-256が一致。稼働PokeConの停止・再起動、実機入力、音声デバイスの操作、既存動画の再作成・再アップロードは行っていない。既存のアップロードを止める変更も加えていない。

今回見つかった録画切替・音声結合の問題は未修正。修正後の実機確認では、分割境界を跨ぐ映像と操作音に加え、入力／表示FPSを確認する必要がある。今回の人工データ確認だけで実機の同期改善を保証することはできない。

- [人工動画の再現結果と本体ソースのhash](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/.codex_tmp/recording_jump_audit_20261024/probe_results.json>)
- [ZIP内の全分割境界の集計](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/.codex_tmp/recording_jump_audit_20261024/zip_boundary_results.json>)
- [先行したL追加とA省略の検証結果](<C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/.codex_tmp/za_mapping_l_alignment_20261024/verification_result.json>)：全体869件は19 failures／8 errors／1 skip、直前基準との差分0。
