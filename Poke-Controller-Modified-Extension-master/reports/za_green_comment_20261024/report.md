# 緑コメント送りの検知改善（2026-10-24）

緑の↓が上下する際に、背景・吹き出しの縁を含む従来画像の一致度が0.86～0.89へ落ち、閾値0.90を下回っていた。メガアブソル戦だけでなく、ランクアップ受付と終盤の通常会話でも同じ現象を確認した。

`POKEMON_ZA_TEXT_GREEN_COMMENT`へ、緑の↓付近28×21pxだけをカラー照合するORパターンを追加した。閾値は0.90のまま。元の画像ファイルは変更せず、`template_crop=[57,15,85,36]`を使う。画面内の探索範囲は`[900,610,1000,700]`。確認した矢印位置は左上X=943、Y=642～651で、上下動をこの範囲内で吸収する。

元の全面パターンも残した。文字の表示途中・↓がまだ出ていない緑コメントや、選択肢を伴う緑コメントを従来どおり処理できる。追加の待機、連続確認、ボタン回数・間隔、メガ戦の敗北判定・再戦選択処理は変更していない。

## 録画での比較

|資料|確認画像数|従来の一致|変更後の一致|回復した取りこぼし|追加誤検知|
|---|---:|---:|---:|---:|---:|
|`D:/Recording/Switch_No3.zip`の未加工Step画像|13,173|33|45|12（メガ9、通常3）|0|
|10月24日保存の別録画2本の未加工Step画像|970|13|21|8（メガ7、通常1）|0|
|合計|14,143|46|66|20|0|

↓が表示されていると目視確認できた40枚では、従来の20枚から40枚へ改善した。変更後に一致した画像は全件目視確認した。拒否した全画像を会話有無でラベル付けした検査ではないため、全場面の検出率100%を意味しない。動画の全フレームを走査した結果でもない。

ZIP側のカラー矢印一致度は、緑コメントの最低0.927188、拒否画像の最大0.844237。白黒の矢印だけでは黒コメントの白い↓も0.97前後になったため、カラーを必須にした。また、従来の大きな画像の閾値だけを0.85へ下げると、白い会話枠6枚が誤一致することを確認した。

|録画の例|従来一致度|追加のカラー矢印一致度|
|---|---:|---:|
|[メガ戦のアドバイス（1:04:59）](https://www.youtube.com/watch?v=LoAXbwyjmG0&t=3899s)|0.859|0.935|
|[ランクアップ受付（1:00:15）](https://www.youtube.com/watch?v=DHVY6rsajPM&t=3615s)|0.861|0.937|
|[終盤の会話（1:20:17）](https://www.youtube.com/watch?v=l_MzEJK1KeM&t=4817s)|0.860|0.942|
|[10月24日のメガ戦（46:43）](https://www.youtube.com/watch?v=wEU-G6oQ04E&t=2803s)|0.863|0.940|

数値は各時刻付近の未加工Step JPGを再照合したもの。ブラウザーでもメガ戦、ランクアップ受付、10月24日のメガ戦の該当する前後を確認した。YouTube上の縮小表示から数値を算出したものではない。

## 反映・検証

- Origin、stock、既存`ZA_story.zip`、未編集状態のDevStudio保存documentに同じ2パターンを同期した。
- DevStudio用の`image_detection_profiles.json`も更新。他の画像登録・リスト、ソースAST、ZIPの対象外427メンバー・順序・metadata、他のdocument・metadataは保持した。PNG・カメラ・FPS・録画・音声の実装変更はない。
- 未加工録画25枚をfixtureとして追加。実`image_check`→実`detect_image`で、メガ・通常の取りこぼし、文字表示途中、選択肢付き緑コメント、黒コメント、白い↓、白い会話枠、戦闘演出を確認した。fresh入力の欠落・復帰、stockの`readFrame`、`nocheckflag=0`も検査した。
- 専用11件＋既存緑コメント復帰9件＝20件成功。stockの実helperでも新パターンの一致を確認。4配置のソースは実Python 3.7でcompile成功。
- 必須の全体回帰テストは869件／1166.341秒で、既知の19 failures／8 errors／1 skipが残った。直前基準との失敗・エラー診断名の追加0、解消0。全体成功ではない。検査前後のソースhash一致と、同期した5ファイルの変更後hashを再確認した。詳細は[検証結果](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_green_comment_20261024/verification_result.json)と[全体テストの診断比較](C:/PokeCon/PokeCon_Origin/Poke-Controller-Modified-Extension-master/reports/za_green_comment_20261024/automation_features_result.json)。

ユーザーの「PokeConでの確認は今は不要、動画のみ」の指定により、PokeConのStop・Reload・再起動、実カメラ取得、ゲーム入力による確認は行っていない。起動中Commandsへの反映と実機での送り速度・FPSは未確認。保存した変更は、後日Commandsを停止してF5 Reloadした時点から使われる。

証跡は`.codex_tmp/green_comment_20261024/`の`audit_summary.json`、`frame_scores.json`、`color_scores.json`、`holdout_scores.json`、`mirror_sync.json`、`targeted_tests.log`。目視照合用は`green_01.jpg`、`old_only_01.jpg`、`old_only_02.jpg`、`holdout_01.jpg`。変更前の退避は`.codex_backups/green_comment_20261024_143354/`。
