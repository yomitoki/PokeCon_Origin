# PokeCon Dev Studio

`python PokeConDevStudio.py` で起動できます。PokeCon の **Others** タブからも起動できます。
Windowsでは `StartDevStudio.cmd` または `PokeConDevStudio.pyw` をダブルクリックして直接起動できます。

Pythonファイルの全文検索、関数・クラス検索、タグ付きコードの複数選択・マージ、出力の保存に対応しています。

## 開発機能

- ファイルツリーからの編集・上書き保存／別名保存／新規ファイル
- 行番号、Pythonの簡易キーワード・文字列・コメント色分け
- エディタ内の検索・置換、指定行への移動
- Python構文チェック
- 保存済みPythonファイルの実行、停止、標準出力・エラー表示
- `Ctrl+S` で保存、`F5` で実行

## PokeConコマンド生成

メニューバーの **Commands > New PokeCon Python Command...** から作成します。

- Pythonファイル名、PokeConに表示する名前（`NAME`）、クラス名を指定
- 既存タグをプルダウンから選択、または新規タグを追加
- タグを順に追加すると、`Commands/PythonCommands/tag1/tag2/tag3/` に生成
- `Loop`、`Step`、`One shot` の雛形を選択
- Stepは「章 / 詳細処理」を追加した順に実行するコードを生成

生成後はPokeCon本体で **Commands > Reload Commands** を押します。各生成ファイルには実行対象のクラスを一つだけ置くため、Python Commandの一覧へ二重登録されません。

実行中の変数はPokeCon本体の **Command Watch** タブから監視できます。対象コマンド、出力先、変数名を選び、値が変化した時だけログへ出力します。

実行は選択中のPythonファイルを、そのファイルのフォルダをカレントディレクトリとして起動します。PokeCon本体を実行しているPythonと同じPythonを利用するため、実行対象は内容を確認した上で使用してください。

再利用したい関数またはクラスの直前に、次のようにタグを置きます。

```python
# @pokedev: recording audio utility
def helper():
    pass
```

任意の断片は次の形式で扱えます。

```python
# @pokedev-begin: gui output
# ... code ...
# @pokedev-end
```

マージ結果は雛形です。依存する import、重複する関数名、既存クラスとの接続は保存前に確認してください。
