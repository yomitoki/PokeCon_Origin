# CommandsのStep実行設定

Stepを搭載したCommandsでStartを押すと、そのCommandsが公開した開始場所・終了場所をPokeConのポップアップに表示します。Commandsタブへの常設設定や独立した開始Step設定ではありません。Stepデバッグの停止地点・一時置換とは別の設定です。

## 設定手順

1. CommandsタブでStep対応Commandsを選び、Startを押します。
2. 表示されたポップアップで開始場所と、必要なら終了場所を選びます。
3. 候補が多い場合は、文字検索または状態グループで絞り込みます。
4. 同じ画面でデバッグ項目、セーブ削除ユーザー番号、失敗時再実行を指定します。
5. 「この設定で開始」を押します。

「Commands既定で開始」を押すと、保存した実行範囲だけを解除してCommands本来の開始位置で開始します。ポップアップを閉じた場合はCommandsを開始しません。

## お気に入り

現在選択している開始・終了・詳細設定は、Commandsごとに最大10件まで登録できます。

- 「新規登録」: 名前を付けて現在の設定を追加します。
- 「呼出」: 選択したお気に入りを現在の実行設定へ反映します。
- 「上書き変更」: 選択したお気に入りを現在の設定で更新します。
- 「削除」: 選択したお気に入りだけを削除します。

お気に入りと現在の実行設定はInputSetごとに保存されます。

開始・終了候補は次の形式から自動検出されます。

- ZA_Storyなどの`STATE_*_FUNCTION`
- DevStudio生成StepやStepサンプルの`STEP_LABELS`／`STEP_KEYS`
- FRLG形式の`cb_restart_flag`（番号と「開始～終了」の説明）
- Commandsが明示した`COMMAND_RUN_LOCATIONS`

終了場所は、その場所の処理を完了して次へ遷移した時点で停止します。FRLG形式ではCommands本来のストップ番号へ設定します。

ZA_Storyでは、選んだStepだけでなく、外側の `main_current_state_init` も自動設定します。Pythonソースは変更しません。
Start後は、Commandsタブの同じ行が `現在Step` 表示に切り替わります。ここに選択したStepが出ていれば、initは反映済みです。次のStep名に変われば、選択Stepの処理は完了しています。

## 変更しない場合

Start後のポップアップには次の3つの操作があります。

- 「この設定で開始」: 画面で選んだ開始・終了・デバッグ設定を反映します。
- 「Commands既定で開始」: 実行範囲設定を解除し、Commands本来のinitで開始します。
- 「キャンセル」: Commandsを開始しません。

設定自体が不要になった場合はStart後のポップアップで「Commands既定で開始」を押します。対象Commandsの実行範囲がInputSetからも削除されます。お気に入りは個別に削除するまで残ります。

## 注意

- Stepを変更しても、ゲーム内の座標、会話、所持品、進行フラグは変更されません。
- ゲーム画面を選択Stepの開始状態に合わせてからStartしてください。
- Step名は必ずしも移動処理を表しません。画像が一致するまで待つStepや、会話を送るStepでは、スティックが動かず停止しているように見えることがあります。
- 例: `1_STORY_OUT_HOTEL_Z_73` は会話・画面条件の処理です。フィールド上の移動処理を再開したい場合は、ゲーム状態を確認したうえで次の `1_STORY_OUT_HOTEL_Z_74` を選びます。
- 「Start時にゲーム画面の状態確認を表示する」をONにしておくことを推奨します。
- 既存の `*_current_state_init` があるCommandsではinitへ設定します。initがないCommandsでは、生成したCommandsインスタンスの現在Stepだけを変更します。

## Commands側で説明・デバッグ・セーブ削除を登録する

自動検出だけで不足する場合はCommandsクラスに次を定義できます。

```python
COMMAND_RUN_LOCATIONS = [
    {
        "id": "chapter_1",
        "label": "第1章",
        "description": "自室から最初の町まで",
        "mode": "state",
        "variable": "STATE_MAIN_FUNCTION",
        "value": "MAIN_CHAPTER_1",
    },
]

# この宣言があるCommandsだけ、Start後にStep実行ポップアップを表示します。
COMMAND_RUN_SETTINGS = True

COMMAND_DEBUG_OPTIONS = [
    {"attribute": "DEBUG", "label": "画像保存デバッグ", "default": False},
]

COMMAND_SAVE_RECOVERY = {
    "method": "delete_save_for_user",
    "user_attribute": "save_delete_user_number",
    "max_retries": 1,
}

def delete_save_for_user(self, user_number):
    # ゲーム／機種に合った安全なセーブ削除操作を実装する
    ...
```

セーブ削除はゲームや機種で操作が異なるため、PokeCon共通処理が推測して削除することはありません。明示した削除関数がないCommandsでは失敗再実行を選択できません。削除関数で例外が発生した場合も再実行せず停止します。
