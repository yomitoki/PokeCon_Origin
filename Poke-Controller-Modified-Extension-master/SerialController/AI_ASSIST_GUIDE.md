# AIアシストと契約内のCodex連携

Commands右側にあった入力・画像保存・同Step再試験の操作を「AIアシスト」へ移動しました。Commandsは開始位置と登録操作を中心にした幅の小さい配置です。本体変更の反映には一度完全再起動が必要ですが、その後の操作コマンド追加・変更には再起動やF5 Reloadは不要です。

## Codexの設定

1. Codex CLIをChatGPT契約でログインします。既存のCLIログインを再利用します。未設定ならターミナルで `codex login` を実行します。APIキーは設定しません。
2. AIアシストで「接続・残量確認」を押し、取得されたモデルと対応する思考量を選びます。
3. 「残り %以上」は **残りの利用枠** です。既定は20%。取得されたすべての枠・時間窓の最小残量で判断します。未取得・期限切れ・利用上限到達時は依頼を保留します。
4. 無操作時間（既定120秒）、暗転継続時間（10秒）、暗さ（24）、再依頼間隔（600秒）、Git差分条件を選び「設定保存」を押します。
5. 「監視を有効」で報告保存、「条件成立時に自動で修正依頼」も有効にすると条件を再確認してCodex CLIへ渡します。どちらも初期状態はOFFです。

このPCでは既存のCodex CLIでChatGPT認証・残量・モデル一覧を読み取れることを確認済みです。CLIのパスが自動検出できない場合だけ `codex.exe` の絶対パスを入力してください。`--ignore-user-config` に対応したCLIを使います。個人設定によるモデルプロバイダー切替を避け、ChatGPT認証とOpenAIプロバイダーを指定します。

APIの従量課金は使用しません。契約には利用上限があり、既存クレジット・追加利用を有効にしている場合はアカウント側でOFFにしてください。PokeConはクレジットを購入せず、上限リセットも実行しません。依頼開始後の消費量を事前に保証するものではありません。

## 監視と報告

- Commandsの実行中だけ、コントローラー入力がない時間と暗い映像の継続をANDで判定します。手動のpriority入力も無操作時間をリセットします。
- Cameraのfreshness判定済みフレームを1秒ごとに縮小サンプルで調べます。平均輝度と90%以上の暗い画素を必要とします。入力欠測・3秒超のサンプル間隔は暗転継続をリセットします。映像だけの黒帯や一瞬の暗転を即座に障害扱いしません。
- 保存先は `SerialController/AiAssist/profiles/<InputSet識別子>/reports/`。`incident.json`、`screen.png`、`request.txt` に実行位置・直近ログ・対象ソースのSHA・Git情報をまとめます。無操作と暗転は不具合の候補であり、原因確定ではありません。
- 「対象Commandsがコミット済みと同じ」は、追跡済み・HEADに存在するソースを対象に、staged／unstagedの差分を確認します。未追跡・ignoreされたCommandsは通しません。「リポジトリ全体に差分なし」は他の未追跡ファイルも対象です。「差分条件なし」も選べます。
- 依頼直前に認証・残量・モデル／思考量・Git条件を再確認します。報告後に対象ソースが変わった場合、InputSetや対象実行が変わった場合、同じ報告が依頼済みの場合は送信しません。同じ異常が続く間は重複報告しません。
- 報告を作るだけでも利用できます。「現在の報告を作成」→「この報告を修正依頼」で手動依頼できます。「依頼文をコピー」でCLIへ貼り付ける使い方も可能です。
- CLIは作業フォルダーへの書込みを許可して修正を依頼します。`cli.log` が実行ログ、`result.txt` が回答です。既存差分の保持、commit／push禁止、PokeConのStop・Reload・再起動・ゲーム入力禁止を依頼文に含めます。修正後の実行コードへの反映・実機確認は別途必要です。

## Claude Code

Claude Codeも契約アカウントでログインし、`claude -p` で非対話実行できます。ただしこの実装では、同等の公式な事前残量取得と残量条件を検証できていないため、Claude Codeへの自動送信は行いません。「依頼文をコピー」して契約ログイン済みのClaude Codeへ渡してください。このPCではClaude Code CLI自体は検出されませんでした。

## 操作コマンドを再起動せず登録する

「専用フォルダーから自動登録を有効にする」をONにします。フォルダーの絶対パスがタブ内に表示されます。AIはこのフォルダーへ次の形式のJSONを保存できます。Codexへの依頼文にも、有効な場合だけ登録先と形式を含めます。

```json
{
  "id": "press_b_once",
  "name": "Bを1回押す",
  "code": "press(Button.B, duration=0.1, wait=0.3)"
}
```

最大100件。入力用関数 `press` / `press_rep` / `hold` / `release` / `release_all` / `stick` / `wait` / `log` / `image_check` / `check_cancelled` と `Button` / `Hat` / `Stick` / `Direction` が利用できます。import、任意の属性呼出し、while、元CommandsやOSの終了操作は登録時に拒否します。JSONの書込み途中や構文エラーは実行候補に入りません。

一覧は1秒間隔で更新されます。自動登録はゲーム入力を伴いません。プルダウンで選択して「実行」、または番号1～10へ割り当て、Commandsの番号ボタンから呼び出します。番号は従来のPython Commands Shortcutと別枠です。実行中Commandsは既存の復旧処理で一時停止し、操作終了後も停止を保持します。「この操作が一時停止したCommandsを再開」で明示再開できます。「操作だけ停止」は元Commandsを終了しません。

実行直前にもファイルを検査します。選択中の操作が更新途中・削除済みなら実行を止め、別の操作に置き換えて実行しません。InputSet切替直後は対象を確認してから再度操作してください。

## 公式資料

- [Codexの認証](https://learn.chatgpt.com/docs/auth)
- [Codex非対話実行](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Codex App Serverの利用枠・モデル取得](https://learn.chatgpt.com/docs/app-server)
- [Claude Codeの認証](https://code.claude.com/docs/en/authentication)
- [Claude Code非対話実行](https://code.claude.com/docs/en/headless)
- [Claude Codeのモデル・思考量](https://code.claude.com/docs/en/model-config)
