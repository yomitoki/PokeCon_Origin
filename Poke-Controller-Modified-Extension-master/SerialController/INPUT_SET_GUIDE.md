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
- Manual Controlのキーボード／スティックマウス、PCゲームパッド、割り当てプロファイル、有効状態
- Recordingの開始条件、破棄条件、保存先、容量制限、録画表示設定
- `Commands監視録画`の分割秒数、直近Step数、ループ保持周数、同一Step保持秒数、停止後の原因確認映像秒数、自動開始
- Commandsの選択、フィルター、10個のショートカット
- Commandsごとの実行範囲設定（開始場所／終了場所／デバッグ項目／セーブ削除用ユーザー番号／失敗時再実行）
- CommandsAssist、Stepデバッグ、関数置換、コントローラー記録
- Image Detectionの検索、登録画像、パターン、連続監視、測定間隔
- Analysis、Area Capture、Object Detectionの解析設定とルール
- Command Watch、通知設定
- 左右ログの割り当て、左右幅・上下境界スライダー、Software Controller位置
- クイックアクションの左右位置、登録項目、並び順

登録済みInputSetを呼び出している場合、左右幅・上下境界スライダーはドラッグを終えた時点でそのInputSetへ自動保存されます。

`Commandsを使用する`がOFFの場合は、選択Commands、Commandsフィルター、ショートカット、Command Watch、Step実行設定とお気に入り、Stepデバッグ、関数置換、コントローラー置換記録、Commands系クイックアクションを保存しません。読込時にも以前のInputSetのデバッグ設定を引き継がず、Commands関連を無効化します。

ONの場合は、Commandsタブの種類（Python／Sample／MCU）と各プルダウンで選択したCommandsを保存し、次回読込時に同じCommandsを選択します。

登録済みInputSetから実際にCommandsをStartした場合は、`Commandsを使用する`を自動的にONとして扱い、その時に実行したCommands選択を直ちにInputSetへ更新します。

`Video input`に`Window (Steam/game)`を保存したInputSetは、読込時にCamera Name／Camera IDを開かず、保存したゲームウィンドウを直接開きます。対象ウィンドウが見つからない場合もキャプチャーデバイスへ自動切替しないため、他のツールが使用しているカメラを奪いません。

Window入力はWindows Graphics Captureを使用し、選択したゲームウィンドウの描画面だけを取得します。ゲームの前に別の画面を重ねても、その画面はPokeConの映像へ入りません。初回接続時にゲームが最小化されていると映像を開始できないゲームがあるため、その場合はいったんゲームを最小化解除してから`Apply input`を押してください。接続後に一時的にフレームが届かなくなった場合は、真っ黒な画像へ置き換えず最後に取得できたゲーム映像を保持します。

Cameraタブの`Window range`では、`ゲーム画面のみ（タイトルバーなし）`と`ウィンドウ全体（タイトルバーあり）`を切り替えられます。この範囲はメイン表示だけでなく、画像解析・キャプチャー・録画にも共通で使用され、InputSetごとに保存されます。Windowsの画面下部にあるタスクバーはどちらのモードにも入りません。

## 複数PokeConでの機器重複

Camera、Window映像、Serial、Audioのプルダウンを開くと、ほかのPokeConが現在使用している項目に`[使用中: PID ...]`を表示します。使用中の機器を開く、またはInputSetから反映する場合は確認画面が出ます。

- `それでも反映`: ほかのPokeConで使用中でも反映します。
- `反映しない`: その機器は反映せず、未設定にします。

起動時InputSetの選択画面では、`Camera・Serial・Audioを未設定で反映`を選べます。この場合も、Commands、Recording、画面配置などほかのInputSet設定は反映されます。機器だけを後から各タブで選択してください。

使用情報は実行中プロセスのCamera開始、Serial接続、Audio監視・録画に合わせて更新します。PokeConが正常終了した場合は直ちに解除され、異常終了した情報も次回確認時にプロセス状態を検査して除去されます。

## Manual Controlの復元

Manual Controlの設定はInputSetごとに保存します。キーボード、左右スティックマウス、選択PCゲームパッド、記録設定、割り当てプロファイル、PCゲームパッド→Switchの有効状態を復元します。保存したゲームパッドが見つからない場合は、機器名をInputSetに残したまま転送を停止し、再接続後に再読込できるようにします。

旧形式のInputSetも読み込めます。旧形式を「変更保存」すると、全タブ保存に対応した新形式へ更新されます。
旧形式ではStepデバッグ設定だけを安全に追記し、空の全タブ設定を作って新形式と誤判定しないようにします。
## Resource tab / multiple PokeCon instances

Each complete InputSet stores the Resource-tab choices: cooperative CPU
control on/off, the total-PC CPU target (for example 80% or 90%), and whether
the InputSet requests the unique main-tool role. When the target is exceeded,
background preview conversion and optional image-monitor polling are reduced.
Commands execution, recording, recent tab/key activity, and Software-Controller
input are protected and keep their normal cadence.

`このInputSetをメインツールにする`がOFFのPokeConは、最後に開いた／操作した
順番では優遇されません。実際にバックグラウンドなら、すべて同じ省負荷判定を
受けます。前面表示中のプレビューと、Commands実行・録画・Software-Controller
操作中の処理だけは必要な範囲で一時保護されます。

The main-tool role is coordinated through the machine-wide live-window
registry and can belong to only one running PokeCon. If a startup InputSet asks
for a role already owned by another PokeCon, the user can open it as a normal
tool or cancel opening that InputSet. The CPU target is cooperative and cannot
stop unrelated applications from consuming CPU.

Resource機能追加前のInputSetにResource設定がない場合は、直前に開いていた
InputSetのメイン設定を引き継がず、`CPU制御ON / 目標90% / 通常ツール`として
読み込みます。InputSet一覧で選択したときの概要にも、保存済みのResource役割と
CPU目標が表示されます。
