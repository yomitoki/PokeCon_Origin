# PokeCon Python runtime selection

`ExecutePokeConModified-Extension.bat` をダブルクリックすると、PokeConを起動する前にPythonを選択できます。

- `Python 3.14（Commands互換／GILあり）`: PokeCon本体と、従来3.7／3.12で動作していたCommandsを3.14で実行します。現在の推奨です。
- `Python 3.14t（GILなし対応状況）`: GILが実際に無効か、Commandsの構文と対応依存を確認する診断画面を開きます。現在はPokeCon本体を起動しません。
- `Python 3.12`: PokeCon専用の `.venv312` を使います。
- `Python 3.7（互換モード）`: 従来環境との互換性を確認するときだけ使います。
- `前回の選択で起動`: 前回選んだ環境をもう一度使います。
- `キャンセル`: PokeConを起動せずに閉じます。

選択内容はローカルファイル `.pokecon-python-version` に保存されます。選択画面は毎回表示されるため、次回起動時に別のPythonへ変更できます。

## 仮想環境をBATから作成・修復する

`.venv312`、`.venv314`、`.venv314t`はPC固有の大きなフォルダなので、Gitへはコミットしません。
代わりに次のファイルをコミットしておけば、別PCや新しいクローンでも同じ環境を復元できます。

- `.gitignore`（`.venv*`とローカルの選択状態を除外）
- `SetupPokeConPythonEnvironments.bat`
- `SetupPokeConPythonEnvironments.ps1`
- `requirements-py312.lock.txt`
- `requirements-py314.lock.txt`
- `requirements-py314t-core.lock.txt`

通常は`SetupPokeConPythonEnvironments.bat`をダブルクリックし、環境を選んで「作成・修復を開始」を押します。
既存環境が正常なら削除せず、固定requirementsに従って不足・不整合だけを修復します。

完全に作り直す必要がある場合だけ「既存環境を削除して最初から作り直す」をチェックします。
削除対象は選択した`.venv`フォルダだけで、InputSet、録画、Commands、PokeConソースは削除しません。

コマンドから状態だけ確認する場合は次を使用します。

```bat
SetupPokeConPythonEnvironments.bat -Runtime all -CheckOnly
```

## Python 3.12環境

- Python本体: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`
- PokeCon専用環境: `.venv312\Scripts\python.exe`
- 固定依存関係: `requirements-py312.lock.txt`

環境を作り直す場合は、プロジェクトのルートで次を実行します。

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv312
& ".\.venv312\Scripts\python.exe" -m pip install -r requirements-py312.lock.txt
```

Python 3.7とPython 3.12は別の場所にインストールされ、ライブラリも共有しません。

旧カメラ列挙用の `windows-capture-device-list` はPython 3.12用公開パッケージが正常に読み込めないため、3.12環境からは除外しています。PokeConが通常使用する `pythonnet + DirectShowLib` のカメラ列挙経路を使用します。

## Python 3.14環境

- 通常版Python: `%LOCALAPPDATA%\Programs\Python\Python314\python.exe`
- free-threaded版: `%LOCALAPPDATA%\Programs\Python\Python314\python3.14t.exe`
- PokeCon互換環境: `.venv314\Scripts\python.exe`
- GILなしコア環境: `.venv314t\Scripts\python.exe`
- 互換環境の固定依存: `requirements-py314.lock.txt`
- GILなしコア固定依存: `requirements-py314t-core.lock.txt`

Python 3.14互換モードでは、Python 3.14用ホイールがない従来の `pygame` を、同じ `import pygame` APIを提供する `pygame-ce` に置き換えています。

### GILなしモードの現在の制限

Python 3.14tを導入すればGIL無効の診断環境を作成できます。ただしPokeCon本体は起動時にOpenCV、pygame、pythonnetを読み込みます。現在の公式Windowsパッケージでは次の問題があります。

- `opencv-python`: 安全な公式cp314tホイールがなく、非公式ビルドにはクラッシュ報告があります。
- `pygame`: 読み込むとGILを再有効化します。
- `pythonnet`: free-threaded環境で初期化できません。

このため、ランチャーの3.14t項目は対応状況を確認する診断画面として実装しています。GILを強制無効化して未対応C拡張を読み込む危険な起動は行いません。PokeCon本体と既存Commandsは `Python 3.14（Commands互換／GILあり）` を使用します。

## コマンドからの確認

画面を開かずに選択状態だけ確認する場合は次を使用します。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\PokeConRuntimeLauncher.ps1 -Runtime 312 -CheckOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\PokeConRuntimeLauncher.ps1 -Runtime 37 -CheckOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\PokeConRuntimeLauncher.ps1 -Runtime 314 -CheckOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\PokeConRuntimeLauncher.ps1 -Runtime 314t -CheckOnly
```
