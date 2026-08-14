# PokeCon Portable Package Tool

GitHubに保存されていないローカルデータを、容量上限付きの複数ファイルへ固め、別PCの同じ相対位置へ検証付きで復元するツールです。指定したCommandsと画像・設定だけを、他の人へ渡す用途にも使えます。

## いちばん簡単な使い方（GUI）

`PortablePackageTool`フォルダにある`Start-PokeConBackupGUI.cmd`をダブルクリックしてください。

バックアップ作成は次の順です。

1. `保存内容`を選びます。通常は`軽量移行（おすすめ・録画なし）`です。
2. `バックアップ保存先`を選びます。
3. `① 容量だけ確認`を押し、想定した容量か確認します。
4. `② バックアップ作成`を押します。

別PCへ戻すときはGUIの`復元`タブを開き、バックアップフォルダと復元先PokeConフォルダを選びます。先に`① 破損確認`、成功後に`② 復元開始`を押してください。

保存内容の違いは次のとおりです。

- `軽量移行`: Commands、画像、設定を保存。録画とコマンド記録は除外
- `コマンド記録を保持`: 通常録画は除外し、CommandsRecordingを保存
- `完全保存`: 録画を含むGit管理外データを全保存
- `指定Commandsを個別配布`: 選択したCommandと必要な画像・設定だけを保存

## できること

- Gitの未追跡・ignore対象だけを抽出（Git管理済みソースはGitHubから取得）
- 1ファイルあたりの上限を指定して複数ZIPへ分割
- 上限より大きい単一ファイルはgzip分割し、復元時に自動結合
- 全ファイル／全分割片のSHA-256検証
- 復元先のパストラバーサル防止
- 既存ファイルのバックアップ、停止、スキップ、置換を選択
- 指定Commandと同じフォルダの設定、コード内で参照するリソースを同梱
- 画像検出コマンドは、動的参照の取りこぼしを避けるため既定で`SerialController/Template`全体を同梱

作成ツールはPython標準ライブラリだけを使用します。出来上がったパッケージの復元にはWindows PowerShellだけあればよく、Pythonや7-Zipは不要です。

## 1. まず容量だけ確認

PowerShellで`PortablePackageTool`へ移動して実行します。

```powershell
.\Create-PokeConPackage.cmd local --profile migration --dry-run
```

`migration`は、再生成可能な仮想環境・キャッシュ・ログと、非常に大きい録画系フォルダを除外します。Commands、Template、profiles、settingsなどは対象になります。

通常録画は不要でもコマンド記録を残したい場合は、次を使います。

```powershell
.\Create-PokeConPackage.cmd local --profile command-recordings --dry-run
```

`command-recordings`は`SerialController/CommandsRecording`を保持し、`SerialController/Recordings`を除外します。コマンド記録から操作を再現できる場合の中間プロファイルです。ただし、除外した通常録画の映像そのものは復元できません。

録画を含め、Git管理外を全て対象にする確認は次です。

```powershell
.\Create-PokeConPackage.cmd local --profile complete --dry-run
```

## 2. PC移送用パッケージを作成

次は最大1024 MiBで分割し、指定フォルダへ作成する例です。

```powershell
.\Create-PokeConPackage.cmd local `
  --profile migration `
  --max-volume-mib 1024 `
  --output 'E:\PokeConBackup\local_migration'
```

コマンド記録だけ必要なら`--profile command-recordings`、通常録画を含む全てが必要なら`--profile complete`へ変更します。ただしMP4等は既に圧縮済みなので、ZIP化しても容量はほとんど減りません。現在の環境では`Recordings`と`CommandsRecording`だけで約353GBあります。

## 3. 指定Commandを個別に固める

PythonCommandsからの相対パスで指定できます。

```powershell
.\Create-PokeConPackage.cmd command `
  --command 'ZA\ZA_story\ZA_story.py' `
  --output 'E:\PokeConShare\ZA_story'
```

フォルダ単位も指定できます。

```powershell
.\Create-PokeConPackage.cmd command --command 'ZA\ZA_story' --dry-run
```

既定の`--asset-mode safe`は、画像を使うコマンドにTemplate全体を付けて安全側にします。容量を最小にしたい場合は`--asset-mode minimal`で静的に検出できた画像だけにできます。作成前に必ず`--dry-run`を実行し、「見つからなかった参照」を確認してください。

複数コマンドを別々に渡す場合は、コマンドごとにこの処理を実行して、それぞれ別の`--output`を指定します。

## 4. 別PCへ反映

先にGitHubから同じプロジェクトを取得し、その`Poke-Controller-Modified-Extension-master`を`TargetRoot`へ指定します。パッケージ内の`Install-PokeConPackage.cmd`または次のコマンドを使います。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Restore-PokeConPackage.ps1 `
  -TargetRoot 'D:\tools\PokeCon_Origin\Poke-Controller-Modified-Extension-master' `
  -Overwrite Backup
```

`Backup`（既定）は既存ファイルを`*.pre_restore_日時`へ退避してから反映します。その他は次の通りです。

- `Fail`: 既存ファイルを見つけた時点で停止
- `Skip`: 既存ファイルを変更せずスキップ
- `Replace`: 既存ファイルをバックアップせず置換

反映せず、輸送中の破損だけを調べるには次を実行します。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Restore-PokeConPackage.ps1 -TargetRoot 'D:\dummy' -VerifyOnly
```

復元先には`.pokecon-package-restore-日時.log`が残ります。

## 注意

- パッケージ作成中に元ファイルを書き換えないでください。
- 完成後、輸送前に`-VerifyOnly`を一度実行してください。
- `complete`は数百GBになる可能性があります。出力ドライブの空き容量を先に確認してください。
- パッケージにはトークン、通知先、個人設定などが含まれる場合があります。他人へ渡す用途では`local`ではなく`command`を使い、ドライラン結果を確認してください。
