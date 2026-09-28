# PokeCon YouTube限定公開アーカイブ

Recording タブ上部の「録画動画の保存先」で「YouTubeへアップロード」を選ぶと、通常録画と Commands 監視録画を YouTube の通常動画として逐次アップロードします。ライブ配信は使用しません。PCへ動画を残す場合は「PCへ保存」を選び、保存フォルダと容量監視は「PC保存設定」タブ、チャンネルや分割時間は「YouTubeアップロード設定」タブで設定します。この選択はInputSetへ保存されます。

## 初回設定

1. Google Cloud でプロジェクトを作成し、YouTube Data API v3 を有効にします。
2. OAuth 同意画面と「デスクトップ アプリ」用 OAuth client を作成し、client JSON をダウンロードします。
3. PokeCon の Recording →「チャンネル認証・既定設定…」→「OAuth JSONを読込して認証…」を開きます。
4. ブラウザーでアップロード先の YouTube アカウントを認証します。
5. 通常はその設定を既定にします。別チャンネルへ保存する InputSet だけ、Recording のチャンネル欄で設定名を選びます。

OAuth の client secret と refresh token は InputSet には入りません。`profiles/<profile>/youtube_channels.json` に、現在の Windows ユーザーだけが復号できる DPAPI 暗号文として保存されます。

## Commandsへアップロードする映像

「Commands映像」は InputSet ごとに次の3種類から選べます。選択は次の Commands 録画チャンクから反映され、YouTubeへ送る保存確定動画にも引き継がれます。

- 「画像検知枠＋ログ（既存録画）」: Camera映像へ検知枠を描き、選択中のOutputログを右側へ合成します。
- 「ゲーム映像のみ」: 検知枠やログを合成せず、PokeConへ入力されたゲーム映像だけを保存します。
- 「PokeCon画面全体」: メインのPokeConウィンドウ全体をWindows Graphics Captureで別取得し、縦横比を維持したまま動画へ収めます。ダイアログなど別ウィンドウは対象外です。

アップロード用に3本を同時生成する設定ではありません。選んだ1種類をCommandsの保存動画として作成し、その動画をアップロードするため、不要なローカル容量を増やしません。通常録画の「Output layout」は変更しません。「PokeCon画面全体」を選んだ場合だけ第2のネイティブウィンドウ取得を起動し、ゲーム入力とプレビューの取得経路は切り替えません。

## 保存と削除

- 公開設定は `unlisted`（限定公開）固定です。URLを知っている第三者は閲覧・再共有できます。
- 複数の PokeCon は同じ永続キューを共有し、同時に複数本を送らず1本ずつ処理します。
- 既定は120分ごとに通常動画へ分割します。容量を小さく抑えたい場合は10～30分を指定できます。12時間以上のライブアーカイブ制約には依存しません。
- YouTubeモードのCommands監視録画は、停止を待たず、設定した分割時間に達するたびバックグラウンドでMP4を確定してアップロードキューへ入れます。30秒の内部チャンクを1本ずつアップロードすることはありません。
- MP4の確定と永続キュー登録が成功した後、結合元の短い内部チャンクを削除します。Stop時は最後の分割時間未満の端数だけを保存確認後に確定します。
- YouTube APIで動画処理完了を確認するまではローカル動画を削除しません。処理完了後は動画・音声を自動削除します。
- 完了後に削除するのは `recording.mp4`、`recording.avi`、WAV、一時分割動画だけです。`youtube_remote.json`、`command_monitor.json`、`steps.jsonl`、JPEG、ログ、ソーススナップショットは残ります。
- アップロード中に PokeCon を閉じても、別プロセスのワーカーが継続します。PC終了や通信断の後は、次回 PokeCon 起動時に永続キューから再開します。
- 通信速度が録画速度より遅い場合やYouTube側が処理中の場合、安全のため未送信動画は削除しないので、その分だけ一時容量は増えます。

## Commands と DevStudio

InputSet で「共通3関数の全呼び出し元を索引化」を ON にすると、次の共通関数だけを選択トレースします。

- `ZA_story_Template_battle_before_renda_route`
- `ZA_story_Template_battle_function_renda_route`
- `ZA_story_Template_battle_after_renda_route`

実行時スタックから呼び出し元を取得するため、`_4_story_shiro_35`～`37`に限定されません。同じ共通関数を使う全 Step 関数が `common_function_index.json` へ記録されます。OFF の InputSet では、この追加トレースを有効にしません。

DevStudio の Commands録画タブでは「共通関数の呼び出し元…」から、グループ → 共通関数 → 呼び出し元 → 発生時刻を選べます。「YouTubeでこの時刻を開く」は、長時間録画が複数動画になった場合も該当パートの相対時刻へ変換します。

## API上の注意

- YouTube Data API のアップロードには API クォータが必要です。短いチャンクを個別送信しないのは、この消費を抑えるためでもあります。
- 新規・未監査 API プロジェクトでは、YouTube側の制限によりアップロード動画が private 固定になる場合があります。限定公開で運用するには Google の監査が必要になることがあります。
- 動画説明はサイズ制限があるため、主な Step と共通関数時刻だけを載せます。完全な履歴はローカル索引が正本です。
- Codexへ解析を依頼する場合は、録画フォルダの `command_monitor.json`、`steps.jsonl`、`common_function_index.json`、JPEG、ソーススナップショットを渡すのが確実です。`youtube_remote.json` には時刻付きURLの解決情報があります。
