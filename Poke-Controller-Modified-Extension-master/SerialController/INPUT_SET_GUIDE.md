# InputSetの保存範囲

InputSetは、接続機器だけでなくPokeCon画面の各タブ設定をまとめて保存します。クイックアクションもInputSetごとの設定です。

## 保存手順

1. Camera、Audio、Recording、Commands、Analysis、Otherなどを使用したい状態にします。
2. クイックアクションの配置と登録内容を設定します。
3. Commandsを実行するInputSetだけ、`Commandsを使用する`をONにします。
4. InputSetタブで名前を入力します。
5. 新しい名前なら「新規登録」、同じInputSetを更新するなら「変更保存」を押します。

別の名前で新規登録した場合、元のInputSetは変更されません。

登録済みInputSetを呼び出した後は、Stepデバッグの停止地点、置換コード、PC操作記録置換、試験ON/OFF、本反映履歴を変更するたびに、そのInputSetへ自動保存します。Stepデバッグ置換案のために毎回「変更保存」を押す必要はありません。

クイックアクションも、設定画面で「反映して閉じる」を押すと、現在呼び出しているInputSetへ自動保存します。未登録の新しいInputSet名を入力中は、直前のInputSetを上書きせず、「新規登録」するまで作業中の設定として保持します。

## 保存される主な内容

- Camera、Audio、Serialのデバイス識別情報と表示設定
- Recordingの開始条件、破棄条件、保存先、容量制限、録画表示設定
- `Commands監視録画`の分割秒数、直近Step数、ループ保持周数、同一Step保持秒数、自動開始
- Commandsの選択、フィルター、10個のショートカット
- Commandsごとの開始Step設定（変更なし／状態変数／開始Step）
- CommandsAssist、Stepデバッグ、関数置換、コントローラー記録
- Image Detectionの検索、登録画像、パターン、連続監視、測定間隔
- Analysis、Area Capture、Object Detectionの解析設定とルール
- Command Watch、通知設定
- 左右ログの割り当て、上下比率、Software Controller位置
- クイックアクションの左右位置、登録項目、並び順

`Commandsを使用する`がOFFの場合は、選択Commands、Commandsフィルター、ショートカット、Command Watch、開始Step、Stepデバッグ、関数置換、コントローラー置換記録、Commands系クイックアクションを保存しません。読込時にも以前のInputSetのデバッグ設定を引き継がず、Commands関連を無効化します。

ONの場合は、Commandsタブの種類（Python／Sample／MCU）と各プルダウンで選択したCommandsを保存し、次回読込時に同じCommandsを選択します。

登録済みInputSetから実際にCommandsをStartした場合は、`Commandsを使用する`を自動的にONとして扱い、その時に実行したCommands選択を直ちにInputSetへ更新します。

`Video input`に`Window (Steam/game)`を保存したInputSetは、読込時にCamera Name／Camera IDを開かず、保存したゲームウィンドウを直接開きます。対象ウィンドウが見つからない場合もキャプチャーデバイスへ自動切替しないため、他のツールが使用しているカメラを奪いません。

Window入力はWindows Graphics Captureを使用し、選択したゲームウィンドウの描画面だけを取得します。ゲームの前に別の画面を重ねても、その画面はPokeConの映像へ入りません。初回接続時にゲームが最小化されていると映像を開始できないゲームがあるため、その場合はいったんゲームを最小化解除してから`Apply input`を押してください。接続後に一時的にフレームが届かなくなった場合は、真っ黒な画像へ置き換えず最後に取得できたゲーム映像を保持します。

Cameraタブの`Window range`では、`ゲーム画面のみ（タイトルバーなし）`と`ウィンドウ全体（タイトルバーあり）`を切り替えられます。この範囲はメイン表示だけでなく、画像解析・キャプチャー・録画にも共通で使用され、InputSetごとに保存されます。Windowsの画面下部にあるタスクバーはどちらのモードにも入りません。

## 保存しない安全項目

PCゲームパッドからSwitchへ入力する許可と、ゲームパッド転送の実行状態は保存しません。InputSetを読み込んだだけでPCコントローラー操作が許可されないよう、毎回OFFになります。

旧形式のInputSetも読み込めます。旧形式を「変更保存」すると、全タブ保存に対応した新形式へ更新されます。
旧形式ではStepデバッグ設定だけを安全に追記し、空の全タブ設定を作って新形式と誤判定しないようにします。
