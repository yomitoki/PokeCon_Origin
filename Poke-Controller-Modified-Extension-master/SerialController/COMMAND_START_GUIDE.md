# Commands 開始Step設定

この設定は、CommandsをStopして再度Startするときに、シナリオを指定Stepから開始する機能です。Stepデバッグの停止地点・一時置換とは別の設定です。

## 設定手順

1. Commandsタブで「開始Step設定」を押します。
2. 対象Commandsを選びます。
3. `STATE_1_STORY_FUNCTION` などの状態変数を選びます。
4. Step名を検索して選び、「このStepから開始」を押します。
5. 通常どおりCommandsをStartします。

ZA_Storyでは、選んだStepだけでなく、外側の `main_current_state_init` も自動設定します。Pythonソースは変更しません。
Start後は、Commandsタブの同じ行が `現在Step` 表示に切り替わります。ここに選択したStepが出ていれば、initは反映済みです。次のStep名に変われば、選択Stepの処理は完了しています。

## 変更しない場合

開始確認には次の3つの操作があります。

- 「設定したStepから開始」: 保存済みの開始Stepを今回の実行へ反映します。
- 「今回だけ設定を無視して通常開始」: 保存済み設定は残し、その1回だけCommands本来のinitで開始します。
- 「開始をやめる」: Commandsを開始しません。

設定自体が不要になった場合は、開始Step設定画面の「init設定を削除」を押します。対象Commandsの設定がInputSetからも削除され、以降はCommands本来のinitから開始します。開始Step設定はCommandsごと、InputSetごとに保存されます。

## 注意

- Stepを変更しても、ゲーム内の座標、会話、所持品、進行フラグは変更されません。
- ゲーム画面を選択Stepの開始状態に合わせてからStartしてください。
- Step名は必ずしも移動処理を表しません。画像が一致するまで待つStepや、会話を送るStepでは、スティックが動かず停止しているように見えることがあります。
- 例: `1_STORY_OUT_HOTEL_Z_73` は会話・画面条件の処理です。フィールド上の移動処理を再開したい場合は、ゲーム状態を確認したうえで次の `1_STORY_OUT_HOTEL_Z_74` を選びます。
- 「Start時にゲーム画面の状態確認を表示する」をONにしておくことを推奨します。
- 既存の `*_current_state_init` があるCommandsではinitへ設定します。initがないCommandsでは、生成したCommandsインスタンスの現在Stepだけを変更します。
