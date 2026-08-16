# PokeCon Codex引き継ぎ・実機確認メモ

最終更新: 2026-08-16

このファイルは、同じFPS・Commands安定動作要件をCodexと何度も確認し直さないための引き継ぎです。
FPS、複数PokeCon、Commands画像検知、録画終了、画面停止に関する変更前に必ず読んでください。

- DevStudioのサンプル関数チェックで新旧を判定する際、巨大な実ソース`.py`と`.pyfrag`のファイル更新日時を比較してはならない。サンプル登録・同期時に保存した関数単位の共通ハッシュを基準にし、同期後に片側だけ変化した場合のみ`ソース関数が新しい`／`サンプル関数が新しい`と表示する。旧登録で関数履歴がない差分、または同期後に両側が変化した差分は推測せず`判定不能`と表示する。

## ユーザーが確定した表示FPS要件

1. `表示60FPS維持`をチェックしたPokeConは、Google Chromeなど別アプリが前面でも60FPSを維持する。
2. このチェックはPC全体で1つだけが実効所有者になれる。
3. 起動時に別の所有者がいる場合は、既存の確認ポップアップを維持する。ポップアップを削除・自動承認しない。
4. チェック所有者がいない場合、最後に起動したPokeConは、Googleなどが前面でも設定FPSを維持する。
5. 別の60FPS所有者がいる場合でも、最後に起動した通常PokeConを5FPSには落とさず、少なくとも30FPSで待機させる。
6. 古い通常PokeConを省負荷化してよいのは、別のPokeConが起動している場合だけ。PokeConが1つだけなら、別アプリへ移動したことを理由に5FPSへ落とさない。
7. PokeConが開いたまま録画停止後の動画作成・結合をしている間は、表示FPSを下げない。
8. `録画保存待ち`とは、PokeConの×ボタンを押し、最後の動画作成完了を待ってから終了する状態を指す。この終了待ち中だけFPS制限を許可する。
9. 別PokeConが前面になったことだけを理由に、チェック済み所有者の60FPSを解除しない。
10. メイン／60FPS所有者、最終起動PokeCon、確認再生所有者、Commands実行中などの指定は、表示FPS・CPU優先度・音声所有権だけを決める。指定されたPokeConを`lift`、`focus_force`、`SetForegroundWindow`、`topmost`、再表示などで自動的に前面へ移動してはならない。複数PokeConの重なり順と操作対象はユーザーが選んだ状態を維持する。
11. PokeCon内のダイアログは、ユーザーがそのPokeConで明示的に開いた時だけ当該PokeCon内で前面にしてよい。ダイアログの定期更新、終了、InputSet／メイン所有権の更新によって親PokeConを別PokeConより上へ戻さない。システム全体の`topmost`は使用しない。

`Google`という表現は通常、Google/Chromeを映像入力にする意味ではなく、Googleなど別アプリを前面にしてPokeConが背面になった状態を指す。

## 手動操作のアクティブPokeCon要件

1. WindowsでPokeConを選択した場合、そのPokeConをキーボードおよびPCゲームパッドからSwitchへ送る手動入力の所有者にする。共有レジストリの非同期書込みを待たず、現在のWindows前面PIDを優先する。
2. その後Google/ChromeなどPokeCon以外のアプリを前面にしても、最後に選択したPokeConを入力所有者として保持する。別のPokeConを選択した時だけ所有者を切り替える。
3. 切替は遅くとも3秒以内とする。現在の共有所有権監視は0.5秒周期、キーボード側の補助確認は0.2秒周期である。
4. 非所有PokeConはグローバルキーボードlistenerとPCゲームパッドのSwitch転送を停止し、複数PokeConへ同時送信しない。ゲームパッド接続スレッド自体は待機させてよい。
5. 所有権切替時は旧キーボード入力の押下状態を解放する。PCゲームパッドは転送再開前に既存のニュートラル確認を通す。
6. 入力所有権は操作先だけを決める。PokeConを`lift`、`focus_force`、`SetForegroundWindow`、`topmost`などで自動的に前面へ移動してはならない。

## メイン表示・録画MP4の最優先確定仕様（Codex必読）

今後Codexが表示、録画、音声、FPS、MP4変換のいずれかを変更する際は、最初にこの節を参照する。音声だけ、映像だけ、AVIだけを個別に成功扱いにせず、次の条件を同時に満たすこと。

1. FPS設定が60のメインPokeConは、入力実測と表示実測を約59～60fpsで維持する。録画中・MP4作成中・Chromeなど別アプリが前面の間も、確定済み複数PokeCon規則の範囲で60fps表示を維持する。
2. メインPokeConの`確認再生する`音声は、その画面に実際に表示された映像とずれないこと。映像と音声の開始位置だけでなく、録画時間の経過に伴うドリフトも発生させない。
3. FPS設定が60の録画AVIと最終MP4は、どちらも公称CFR **60/1（60.000fps）** とする。壁時計の計測揺れから算出した59.99、60.005などでMP4の公称fpsを上書きしない。
4. AVI/MP4の映像内容は、PokeConが実際に表示したフレームを提示時刻順に保持する。60fpsのヘッダーだけを作り、未処理の表示フレームを「最新1枚」で上書きして動きを欠落させることを禁止する。
   - 1280x720@60の中間AVIは、実機で書き込みが約32fpsに留まり停止時に未処理フレームを残したMJPEGを使わない。`mp4v`（不可なら`XVID`）のMPEG-4 Part 2 AVIを使い、順序付き60fpsを書き込み速度不足で滞留させない。最終MP4は`libx264 -preset veryfast -crf 18`で再エンコードする。
5. 最終MP4の音声は、PokeConの確認再生で実際にスピーカーへ渡した補正後PCMと提示時刻を使用する。録画ごとの提示時刻から自動整列し、333ms、933msなどの固定offsetを通常録画設定へ保存しない。
6. `recording_timing.json`では、正常な60fps録画について`container_fps=60.0`、`corrected_fps=60.0`、`coalesced_presentation_frames=0`を確認する。`wall_clock_frame_rate`は診断専用であり、AVI/MP4の公称fpsへ再利用しない。
   - `video.intermediate_codec`が`mp4v`または`XVID`で、停止時の順序付きキューが短時間で全量排出され、停止エラーがないことも確認する。
7. 音声の正常条件は、映像`presentation_mode=preview_presented`、音声`source_mode=pokecon_presented_output`、`tap_point=speaker_output_callback`、音声callback/queue/gap欠落0とする。初回提示差は通常1フレーム（60fpsでは約16.7ms）以内を目安とし、最後は短い操作音を含むMP4の実聴でずれがないことを確認する。
8. 完了判定には、変更後PokeConの完全再起動、メイン画面の入力/表示実測、AVIとMP4のfps・全フレーム復号、`recording_timing.json`、MP4実聴をすべて含める。音声が合っていても映像が荒い／カクつく、または映像が60fpsでも音声がずれる場合は未完了とする。

## 現在の実装

- `SerialController/Window.py`
  - 機械全体で一意のメイン/60FPS所有権をアクティブウィンドウ登録で調停する。
  - 最後に起動したPokeConと、別のメイン所有者の有無を追跡する。
  - 確認再生のスピーカー出力も同じ一意の実効メイン（明示的なメイン所有者、所有者がいなければ最後に起動したPokeCon）だけに許可する。非メインは確認再生の希望状態を保持したまま待機し、メインになった時に自動開始する。録音のみの直接入力は止めない。確認再生PCMを共有中の録画がある状態でメインが切り替わった場合は、MP4音声を途中で切らず旧出力を録画終了まで維持し、新メインはその出力解放まで待機する。同時に2つのPokeConからスピーカー出力しない。
  - 通常の録画finalizeではFPS権限を外さず、×ボタンによる終了フローだけをsuspend扱いにする。
  - メイン画面上部へ要求FPS、入力実測FPS、表示実測FPSを表示する。
  - メイン／最終起動／確認再生所有権の監視は、ウィンドウのZ順やWindowsフォーカスを変更しない。監視ループから前面化APIを呼ばない。
- `SerialController/PokeConDialogue.py`
  - ダイアログはシステム全体の`topmost`を使用しない。作成時に当該PokeConプロセスがWindowsの前面である場合だけ`transient`で親へ結び付ける。Commandsなどが背面で自動表示したダイアログを閉じても、親PokeConを別PokeConより上へ戻さない。
  - InputSet選択と機器重複確認も同じ前面判定を使う。InputSet選択の無条件`focus_force()`は禁止する。
- `SerialController/GuiAssets.py`
  - WindowsではCanvas HWNDへGDIで直接描画する。
  - Switch2などの機能制限版がフルレート対象の場合、カメラの新規フレーム通知を専用GDI描画スレッドが直接受ける。表示をTk callbackの混雑から分離する。
  - Tkの4ms高精度ポーリングは録画など、メインスレッド側で全入力フレームを処理する必要がある場合だけ使う。通常の機能制限版表示には使わない。
  - 専用描画は機能制限版だけに限定する。通常版、範囲指定、解析などTk重ね描画が必要な場合は従来の互換描画へ戻す。
  - 入力フレームと同じsequenceを重複描画しない。
  - GDI直接描画とCommandsの枠表示用Tk互換描画を切り替える際、前回の互換描画で非同期変換したフレームを破棄する。GDI面を消す前にその時点の最新CameraフレームでTk画像を更新し、黒面や前回Commands停止時の画像を露出させない。強く省負荷化されたPokeConでは、低頻度の描画時だけ現在フレームを同期変換し、1描画周期前の古い変換結果を表示しない。
  - Camera/Window切替で共有フレームが一時的に`None`になる間は、表示だけ最後の正常フレームを最大3秒保持する。録画・解析へ古いフレームは渡さない。表示サイズ変更時も現在の正常フレームを新サイズへ直接再描画し、途中に`No Image`を挟まない。3秒を超えて入力がない場合は通常どおり全面`No Image`へ戻す。
- `SerialController/Camera.py`
  - カメラ読取は別スレッド。正常にブロックする60FPS DirectShow読取の後へ余計な短時間waitを追加しない。
  - 入力実測FPSを計測する。
  - WindowsのUSBキャプチャは1280x720→設定FPS→`MJPG`の順で交渉する。2026-08-15の実機DirectShow調査では、接続中の`USB2 Video`は1280x720 YUY2が最大20FPS、MJPEGが最大60.0002FPSだった。実機で3種類の設定順を比較し、MJPGを最後に設定した場合だけ`MJPG`・実測59.1FPS、修正後`Camera`クラスでは実測59.553FPS・正常終了を確認した。
  - ログの`Camera mode requested=... negotiated=... MJPG`と画面上の入力実測FPSを両方確認する。プロパティ上60でも実測20なら成功扱いにしない。
  - DirectShowのopen/reconfigure/release全体を再入可能ロックで直列化する。Camera Name切替とApply inputが重なった際、接続設定中のcaptureを別スレッドがreleaseして`0xC0000409`（終了コード`-1073740791`）になった実例がある。解放前にはreader終了を最大0.5秒待つ。
  - `Camera.openCamera()`はライフサイクルロック内で確定した成功可否を返し、呼出側は直後に別途`isOpened()`を呼ばない。次の同一Camera反映が間に入ると、一時的な解放を失敗と誤認して「Camera Nameの映像を開けませんでした」を表示するため。2026-08-15 08:31のログでは全接続がMJPG/60で成功していたが、この競合で誤ポップアップが出た。
  - 正常フレームの最終受信時刻を追跡し、通常60FPS入力では約0.25秒以上新しいフレームが届かなければ`readFrame()`は`None`を返す。停止したUSB入力の最終画像をライブ映像として無期限に再利用しない。表示だけの最大3秒保持とは独立しており、録画とCommands画像検知は古いフレームを処理しない。
  - `Commands/PythonCommandBase.py`の単体・複数テンプレート検知、逆向き画像検知、保存・通知と`LocalFunction/ImageDetection.py`は必ずfreshness判定済みの`readFrame()`を使う。入力停止中の画像検知は不一致／待機となり、新規フレーム受信後に自動復帰する。
  - 画像検知時に0.25秒のfreshness判定を一時的に超えても、`readFreshFrame()`が最大0.75秒だけ新規フレームを待つ。短いDirectShow/Windowsスケジューラ揺れでは誤エラーにせず、完全停止時はキャッシュ済み最終画像を渡さない。
- `SerialController/WindowsAudioIdentity.py` / InputSet
  - Camera IDやAudio一覧先頭のPortAudio番号、Windows表示名の`(2- ...)`番号は物理機器の識別子として使わない。
  - Cameraは保存済みPnPパスを優先し、DirectShow列挙部だけが変わった場合はVID/PIDとUSB接続トークンで追従する。
  - AudioはWindows録音端末GUID、デバイスinstance/interface path、USB接続位置をInputSetへ保存する。同型Audioが複数ある場合も、GUIDまたは同じキャプチャカードの映像interfaceと共通のUSB位置で選ぶ。
  - 保存した安定識別子の端末が不在なら、同名の別機器へ自動接続しない。安定識別子を持たない旧InputSetだけ、旧完全名と現在解決したCameraのUSB位置から一意に補完する。
  - 2026-08-15に既存`Switch2`と`Switch_No1`へ録音端末GUIDを補完済み。`PS4_main`は保存時の端末が現在不在で一意なGUIDを確定できないため、再接続時にCameraの現在USB位置で解決する。
- `SerialController/ResourceControl.py`
  - 実効60FPS対象だけWindowsタイマー精度を1msにし、プロセスをABOVE_NORMAL優先度にする。
- `SerialController/UiResponsiveness.py`
  - メイン所有者、最後に起動したPokeCon、通常PokeConの優先度を分ける。

## Commands画像検知の安定動作仕様（必須）

Commandsや登録画像検知を変更する際は、次の条件を同時に守る。FPS改善、No Image対策、カメラ切替、機能制限版の変更によって、この条件を崩さないこと。

1. 画像検知の取得元はCamera readerが最後に受信した**新しい実入力フレーム**とする。GUIが見た目のため最大3秒保持している最終描画や`image_bgr`の古いキャッシュへフォールバックしない。
2. 通常60FPS入力では、最終受信から約0.25秒以内のフレームだけを即時利用する。0.25秒を超えた場合もUSB切断と即断せず、Commands側は`readFreshFrame(timeout=0.75)`で最大0.75秒だけ新規フレームを待つ。
3. 待機中に新規フレームが来れば、その場で自動復帰して検知を続行する。短いDirectShow/Windowsスケジューラ揺れを不一致・コマンド終了・エラーポップアップとして扱わない。
4. 0.75秒待っても新規フレームがなければ、停止した入力の最終画像で一致判定しない。標準`PythonCommandBase`は不一致／待機、`LocalFunction/ImageDetection.py`は取得不能を明示する。復帰後はPokeCon再起動なしで検知を再開できること。
5. 一時停止中の同一エラーを高速で連続表示しない。標準Commandsの警告ログは停止区間につき原則1回とし、復帰もログに残す。
6. カメラ入力は1280x720・設定FPS・MJPGで交渉し、Commands実行中もreaderをTk処理や画像照合から分離する。プロパティ上の60FPSではなく、画面の`入力xx.x fps`が約59～60であることを基準にする。
7. Camera Name変更、Apply input、再読込、終了がCommandsと重なっても、open/reconfigure/releaseをライフサイクルロックで直列化する。切替途中のcaptureを別スレッドからreleaseしない。
8. Commands実行や画像検知を理由に、単独PokeConまたは表示60FPS所有者を低FPS化しない。別PokeConがある場合の省負荷規則は「ユーザーが確定した表示FPS要件」に従う。
9. Switch2 InputSetは通常、Commands・解析・範囲指定を無効にした機能制限版とする。Commandsを必要とする場合は通常版／Tk互換描画への変更が必要だとポップアップで案内し、無断で機能制限を解除しない。
10. 画像検知の枠表示などTk重ね描画が必要な間だけ互換描画を使う。互換描画へ切り替えてもCamera readerと録画入力を止めず、終了後は適切な描画経路へ戻す。
11. `POKEMON_ZA_TEXT_WHITE_COMMENT`は、2026-08-15の実機確認で3回連続確認でストーリー進行が止まったため、最初の画像照合1回の結果をそのまま返す。3回連続確認は行わない。下矢印の上下アニメーションは`white_comment.png`と`white_comment2.png`を同じORターゲットとして1回の照合内で吸収する。
12. 新しいImageProc Commandsの最初の画像検知は、Commands開始前にCameraへ残っていたフレームを使わず、開始後にsequenceが進んだ最初のfresh frameを最大0.75秒待つ。停止直前の画像を次回実行の最初の一致として再利用しない。
13. Show Valueの複数検知結果は、各検知名・パターンの最新一致度が高い順に表示する。同点だけ既存順を維持する。閾値以上で「一致」したブロックは濃い緑文字と薄い緑背景で区別し、不一致は通常色のままにする。

変更後の確認はunit testだけで完了扱いにしない。対象PokeConを完全再起動し、入力実測FPSが安定してから、同じ画像検知を最低30秒連続実行する。その間にPokeCon前面、Chromeなど別アプリ前面、枠表示あり、Camera入力切替後の復帰を確認する。出力に一時的な「新しい映像を取得できません」が出た場合は、発生時刻の`SerialController/log/log_*.log`でCamera open/reconfigure/終了と照合する。

- `SerialController/Recording.py` / `AudioMonitor.py`
  - 録画AVIのCFRフレーム位置は、非同期録画合成が完了した時刻ではなく、`presented_at`（Tk/GDIで実際に表示した時刻）から決める。合成が遅れて届いても、その遅延を映像内容の時刻へ加えない。次の提示フレームまで直前の表示フレームを必要数だけ反復し、録画停止時刻まで自動でフラッシュする。
  - 表示成功通知からAVIまでの受け渡しは順序付きキューとし、合成待ち・MJPEG書込み待ちのどちらでも「最新1枚」で未処理フレームを上書きしない。`Video only`は重い合成を経由せず表示フレームを直接AVIキューへ渡す。録画停止時は、停止操作より前に表示済みの全フレームをキューから排出してからAVIを閉じる。
  - `recording_timing.json`の映像`timeline_mode=preview_presentation_timestamped_cfr`を新方式の正常条件とする。`compositor_delivery_delay_average_ms`／`max_ms`は診断値であり、その値を固定音声オフセットとして保存しない。
  - 同JSONの`coalesced_presentation_frames`は正常時0でなければならない。`presentation_queue_max_depth`／`compositor_queue_max_depth`は一時的な処理遅れの診断値であり、深さが増えても表示済みフレームを破棄して0へ戻さない。
  - AVIと最終MP4の公称fpsは録画開始時の設定CFRをそのまま使う。`frames / elapsed`は`wall_clock_frame_rate`へ診断値として残すだけで、ffmpegの`-r`へ渡さない。FPS設定60ならAVI/MP4とも`60/1`とする。
  - Audioタブの`確認再生する`が動作中で、録画Audio Inが同じ物理入力の場合、別の入力ストリームを開かず、確認再生と同じGain・自動補正・Limiter・リサンプル後PCMを録画へ分岐する。分岐点は**スピーカー出力callback**とし、PokeConが実際に確認再生へ渡したPCMを録画する。
  - 確認再生を使用していない場合、または選択入力が異なる場合だけ、低遅延WASAPI優先の直接録音へフォールバックする。
  - `recording_timing.json`の正常な共有経路は、映像が`presentation_mode=preview_presented`、音声が`source_mode=pokecon_presented_output`かつ`tap_point=speaker_output_callback`。`direct_input`は確認再生を共有できない場合の直接録音、旧`pokecon_processed_input`／`pre_playback_buffer`／`pokecon_confirmation_playback`は現在の正常条件にしない。
  - 映像はCamera取得callbackではなく、TkまたはGDIへの描画が成功したフレームを録画へ渡す。表示通知が0.5秒以上来ない異常時だけ`capture_fallback`を使い、`recording_timing.json`へ明示する。
  - 音声の最初の位置はPortAudioの`outputBufferDacTime`を単調時計へ写像し、録画開始から実際のスピーカー提示予定時刻までを初期整列する。通常のcallback揺れを固定ミリ秒補正へ置き換えない。
  - Windows既定出力がMMEでも、同名のWASAPIスピーカーを優先する。2026-08-15実機では既定MME device 10が44.1kHz/90ms、同じRealtekスピーカーのWASAPI device 26が48kHz/3msだった。入力streamより出力streamを先に開始し、開始時の音声backlogを作らない。
  - USB入力96kHzからWASAPI出力48kHzへの変換は、callbackごとの独立`np.interp`ではなく状態を保持する低域通過FIRで2:1変換する。一部の高周波効果音だけに出るalias/境界ノイズを避け、通常音量とLimiter設定は維持する。
  - 96→48kHzのFIRは127tap Kaiser・約20kHz通過端を使い、48kHz Nyquistを超えるUSB入力成分が可聴帯域へ折り返して断続的なジリジリ音にならないようにする。フィルター状態はcallback間で継続し、ブロック境界でリセットしない。
  - 入力機器とスピーカーの独立クロック差は、FIFOが増えた時にcallbackブロックを丸ごと捨てて補正しない。soft目標の上下に出力1 callback分のヒステリシスを設け、その範囲を外れた時だけ1frame少なく／多く消費し、その1frameをブロック全体へ補間して連続波形を維持する。入力・出力callbackの開始位相でFIFOが目標付近を往復するだけの時に、毎callbackで+1/-1補正を交互に反転させない。FIFOが空になる直前まで補正を待つことは禁止し、緊急上限でのみ正確な超過量を除いて次の出力を短くcrossfadeする。
  - 確認再生の起動直後は、通常のsoft FIFO目標（低遅延WASAPIでは80ms）まで準備してから音を出す。入力の短い断片だけを再生して残りをfade付き無音にすることを禁止し、この待機はstartup silenceとしてruntime underflowと分離して記録する。これは固定A/V offsetではなく、入力・出力callbackの開始位相差とWindowsの短いスケジューリング停止を吸収する再生バッファである。緊急上限は通常250msとし、soft目標付近の通常揺れを強制trimしない。
  - `level_info()`と`recording_timing.json`へ入出力driver status、software underflow、緊急overflow trim、緩やかなclock補正frame数を残す。正常時はdriver status、録画開始後underflow、緊急overflow trimが0。clock補正の少数frameは欠落ではなく独立クロック追従の診断値とする。
  - 正常なPortAudioパケットは連続PCMとして書き、時刻の揺れをパケット欠落と誤認して無音を挿入しない。キュー欠落または入力overflowを確認した場合だけ無音補完する。
  - MMEの31文字で切れたデバイス名から同じ物理入力の完全名を照合し、WASAPI、DirectSound、MMEの順で低遅延入力を試す。
  - Audio Gainの100%は入力原音の1.0倍であり、Windows側の入力音量を100へ変更する意味ではない。2026-08-15に使用中の`(4- USB Digital Audio)`を3秒実測したところpeak 0.06445（-23.82 dBFS）、平均RMS -39.4 dBFSで、入力自体が小さかった。Switch2 InputSetは400%（4倍、実測ピーク換算約-11.8 dBFS）へ補正済み。UIは`Gain (100%=原音)`と表示する。確認再生中の録画は増幅後の同一PCMを使う。
  - `AudioLevelControl.py`の入力ピーク自動補正をAudioタブから操作できる。Switch2は有効、目標-6 dBFS、手動400%後の自動最大200%、Limiter上限-1 dBFS。-60 dBFS未満の無音では追従を止め、ゲイン低下は速く・回復は遅くして効果音と無音によるポンピングを抑える。
  - 2026-08-15の実USB入力で再測定し、raw peak -23.69 dBFSから補正後-5.70 dBFS、自動倍率1.999、Limiter動作0/300ブロックを確認した。Audioタブには入力/出力peak、自動倍率、Limiter動作を0.5秒ごとに表示する。
  - AudioタブはGain・自動補正前のUSB原音について、現在peak、開始／リセット後の最大peak、0 dBFS近傍へ達した原音CLIPブロック数を表示する。`最大値リセット`で観測区間だけをリセットし、音量は変えない。原音CLIPが増える場合は入力機器側、原音CLIPが0でLimiter回数だけ増える場合はPokeCon後段増幅側を疑う。
  - Limiterは上限超過サンプルを個別にhard clipせず、該当PCMブロック全体を同じ比率で減衰する。最大振幅を守りながら波形比を保持し、旧hard clip由来の音割れを避ける。
  - Audioタブには短い通常確認用の`5秒おまかせ`と、不定期な大音量まで含める`30秒精密調整`がある。Gain前の原音について最大peak、測定全体のRMS、原音CLIP回数を測り、手動Gain 100%のまま`目標dBFS・Limiter・自動最大倍率`をすべて算出してAudioを再開始する。目標とLimiterの間には最低3 dBの余裕を確保する。
  - 調整値には無音を除いた有音ブロックの中央値RMS、95パーセンタイル基準peak、99パーセンタイル大音量peakを使う。大音量peakが基準peakを繰り返し大きく上回る場合も、通常音の目標と自動最大倍率は下げず、Limiter上限だけへ最大2 dBの大音量保護を追加する。一部の効果音だけを抑え、全体音量を維持する。30秒内の無音割合や一度だけの突出peakで調整のたびに音量が下がらないようにし、0.5 dB/25%刻みへ丸めて同等の測定結果を同じ設定へ安定させる。絶対最大peakと原音CLIP回数は安全警告用として別に保持する。
  - 自動補正は直近約0.5秒のpeakを保持して現在音量へ連続追従する。Limiterは必要時に即時保護し、解除は約0.25秒かけて戻すため、ブロックごとの急な音量変化を抑える。保存値が範囲外または目標とLimiterが近すぎる場合は起動・適用時に安全値へ自動修復する。実際に`settings.ini`が目標+40 dBFS / Limiter-20 dBFSとなり、毎ブロック抑制する矛盾状態が発生したため追加した。
  - 自動Gain/Limiterの安全な増減はPCMブロック内で線形補間し、callback境界の小さなクリックを抑える。現在gainでは上限を超える突然の大音量だけは、波形保護を優先して即時減衰する。
  - 実測-23.8 dBFSでは自動最大は800%となるため、旧Switch2の手動400%×自動最大200%と総最大倍率は同じ。Switch2 InputSetの保存値も手動100%・自動最大800%へ更新済み。原音CLIPを検出した場合は、PokeCon前段のSwitch/キャプチャ機器/Windows入力を下げる警告を出す。
  - 確認再生中の録画は補正後PCMを共有する。確認再生なしのUSB直接録音でも同じ自動補正をWAV書込前に適用し、`recording_timing.json`の`audio.level_control`へ最終状態を残す。
  - 録画ごとに`recording_timing.json`を残し、実デバイス/API、遅延、音声欠落、補正FPSを後から確認できるようにする。

## 録画AV同期の確定仕様（必須）

1. 新規録画の同期基準はCamera/Audioの取得時刻ではなく、**PokeConで実際に見えた映像と、実際に聞こえた確認再生音声**とする。ユーザーがPokeCon上でずれを感じない状態を最終MP4でも再現する。
2. 映像はTk/GDI描画成功後のpresentation listenerから渡す。Cameraのraw callbackは録画開始条件・画像検知・重ね描画状態の更新には使ってよいが、表示通知が正常に続く間は録画映像源にしない。
3. 音声はGain・入力ピーク自動補正・Limiter・リサンプルを終え、スピーカー出力callbackが実際に渡したPCMを使う。最初の提示時刻はPortAudioの`outputBufferDacTime`で動画と同じ単調時計へ合わせる。
4. 正常な新規録画の`recording_timing.json`は、映像`presentation_mode=preview_presented`、音声`source_mode=pokecon_presented_output`、`tap_point=speaker_output_callback`であること。`capture_fallback`になった録画は実表示基準を満たしたと断定しない。
5. 100ms、500msなどの固定補正値を録画・環境の恒常設定として保存しない。必要量が録画ごと・区間ごとにぶれるため、固定値を何度も試す方法を通常の解決策にしない。比較MP4は旧録画の診断用途に限定する。
6. AVI/WAVの総尺一致、完全無音の除去、固定offset比較、unit test成功だけで同期済みと断定しない。変更後PokeConを完全再起動し、画面上で操作音が合っている状態から短い新規録画を作り、MP4を実聴確認する。
7. 音量調整と同期調整を混同しない。通常音量の目標・最大Gainは維持し、不定期な大音量だけLimiterで保護する。Limiter動作を音声時刻の補正に使わない。
8. FPS設定60の最終MP4は公称`60/1`であること。表示時刻から作成済みの60fps CFRタイムラインを、壁時計の`frames / elapsed`値で59.99や60.005へ変更しない。

## Commands監視録画のStop保存・保持仕様（必須）

1. `Commands Stop時に今回の録画を保存確認`がONの場合、明示的なStopまたはForce stop後に「今回の録画を問題確認用として保存するか」を確認する。
2. 確認の`はい`は今回分を1本へ結合して保護保存、`いいえ`は今回の未保護分だけを削除する。保存を選んだ録画は次回起動時の自動整理でも削除しない。
3. 問題録画は、問題Stepより前の異なる15 Stepから保持する。`Step1 → Step2 → Step1 → Step2`は4遷移ではなく2種類のStepとして数える。
4. 問題Stepに入ってからは、停止・暗転・キー無操作の開始地点から最大60秒を原因確認用として保持する。60秒より前にStopした場合はStop時点までを保持する。
5. 自動判定前に明示的なStopを押した場合は、その時点で実行中のStepを問題Stepとして同じ15 Step＋最大60秒の範囲を保存候補にする。
6. `調整停止＋保護`は保存確認を省略し、今回分を保護したまま1本へ結合する。

- `SerialController/RecordingSyncRepair.py` / `PokeCon_録画同期修復.bat`
  - 日付録画フォルダ内へ`sync_repair_日時`を作成し、元AVI/WAV/MP4を上書きせずMP4を再作成する。
  - AVI総フレーム数 ÷ WAV実時間で旧版録画の補正FPSを算出する。
  - 旧タイムスタンプ補正が作った大量の全チャンネル完全無音（1%以上）を検出した場合は、連続音声の比較用修復も行う。

## 2026-08-15 音声遅延の実ファイル調査

- 最新`20260815_101015_650719`は映像354.817743秒、WAV354.817732秒、尺差約0.00001秒、callback/queue/gap欠落0であり、総尺ドリフトや欠落だけでは説明できないpresentation基準のずれ。旧共有経路は`Windows WASAPI -> MME`、44.1kHz、再生遅延91.4ms、`pokecon_confirmation_playback`でスピーカーバッファ後を録音していた。WAV最大は-3.002 dBFS、0 dBFS到達サンプル0なので録画後段のdigital clipはない。既存MP4用に`offset_compare_20260815_104106`へ音声100/200/300/500ms前進版を映像stream copyで作成済み。
- ユーザー実聴では同録画の音声500ms前進版でも遅延が残り、必要な補正量は一定でない。映像動き量と音声強度の区間相関も区間ごとに約-3.6～+4.0秒へばらつき、信頼できる固定offsetを特定できなかった。以後、固定補正比較を繰り返して新規録画の解決策とせず、実表示・実再生presentation基準を直す。
- `D:\SSR_pic`の2026-08-14 23:13以降の6録画に、全チャンネル完全無音が一律約4.48～4.60%入っていた。以前4録画はほぼ0%だったため、ゲーム固有の無音ではなく旧タイムスタンプ補正由来と判定した。
- 最新`20260815_113306_532841`は映像312.131950秒、音声312.137604秒（差約5.7ms）、MP4復号音声と元WAVの相関lag 0ms、callback/queue/gap欠落0。ユーザー実聴では約00:45より前だけ操作音が合わず、その後は戻る。Template画像検知そのものは音声へ固定offsetを加えないが、画像検知枠によるGDI/Tk切替で古い表示フレームが露出すると、`preview_presented`を録画源にする現仕様ではその古い映像も録画へ入って音声だけ現在時刻のままになる。2026-08-15に描画切替の古い非同期フレーム破棄・現在フレーム先行反映を追加した。これが00:45までのずれを解消するかは、PokeCon完全再起動後の新規短時間録画で実聴確認が必要。
- 同録画の追加調査で、録画側は`presented_at`を受け取っていた一方、旧`_video_writer_loop`が合成完了後の`latest_frame`を現在のCFR位置へ書いており、提示時刻を実際のフレーム配置に使っていなかったことを確認した。非同期合成の配送遅延が区間ごとに変動すると、固定音声offsetでは再現不能になる。`Recording.py`を提示時刻駆動へ変更し、279件のunit test成功。起動中PokeConには未反映なので、完全再起動後の新規録画・実聴確認までは完了扱いにしない。
- 直近`20260815_010819_064136`は映像315.945秒、WAV315.967秒で総尺は合う一方、WAV内に完全無音14.153秒が分散していた。総尺一致だけで同期良好と判断しないこと。
- 同録画を`sync_repair_20260815_013518`へ修復済み。補正FPS 45.318029、出力315.960秒、WAVとの差0.007秒、全体デコードエラー0。修復用連続WAVの完全無音は0秒。
- ユーザー実聴では上記の連続音声修復後も音声遅延が残った。無音除去・均等伸長だけで解決済みと判断しないこと。
- 固定遅延比較用に同フォルダの`offset_compare_20260815_014442`へ音声を250/500/750/1000ms前進した最終MP4を作成済み。映像は無劣化stream copy、音声だけAAC再作成、4本とも総尺315.98秒・映像音声ストリーム確認済み。
- `RecordingSyncRepair.py --compare-offsets 250,500,750,1000 <MP4>`で同じ比較版を作成できる。`--audio-advance-ms`はAVI/WAVからの最終MP4再作成にも使用可能。
- 無音欠陥のない旧録画`20260814_202103_419520`も`sync_repair_20260815_013755`へ再作成済み。補正FPS 40.299446、尺差0.004秒、全体デコードエラー0。
- 選択Audio 8はMME（既定low latency 90ms）だった。同じ物理入力のWASAPI 36（3ms、48kHz）を検出し、今後は36を優先する。`check_input_settings`成功済み。
- 2026-08-16の`20260816_175911_231289`は開始時は合う一方、ユーザー実聴で後半ほど映像側が遅れ、約2分30秒から違和感が出た。提示時計診断では音声callback PCMがスピーカー提示時計より30秒で0.131秒、60秒で0.337秒、150秒で1.505秒、300秒で3.637秒、終了時4.948秒先行していた。Stop時に不足分237,510 frames（4.948125秒）を末尾無音として一括追加したため総尺だけは一致していたが、録画中の音を連続書込みしたことで音が徐々に先行し、結果として映像遅延に聞こえた。固定offsetでは修復しない。
- 同録画の初回比較版`presentation_rebuild_20260816_184148`は、379個の`presentation_clock_samples`によるPCM直接リサンプルで同期ドリフトは改善したが、ユーザー実聴で音程低下が確認された。この版は同期原因確認用であり、最終確認用に使わない。
- 音程維持版を`presentation_rebuild_20260816_190250`へ再構築済み。5秒前後の77区間をRubber Bandで`pitch_scale=1.0`のまま伸縮し、隣接区間は80ms重ねて連続化した。記録された提示時計への最大近似誤差は35.120ms、`fixed_offset_ms=0`。元WAVと対応区間の周波数分布照合は60/150/240/330/370秒ですべて1.000～1.00025倍で、旧直接リサンプル版の後半0.986倍前後への低下は解消。映像は元MP4からstream copyし、映像stream SHA-256は`0bedf3eddee98c5c15c622b94ab5678b13ce049d8d75adcb9a83bb324711fa01`で再構築前後一致、60fps、全映像・音声デコードエラー0。元ファイルは未変更。
- `Recording.py`の通常MP4 muxは、提示時計ドリフトが20ms以上ある場合に`recording_timing.json`から`recording_presentation_aligned.wav`を作り、その音声を最終MP4へ使う。方式は`piecewise_presentation_clock_pitch_preserving_stretch`、`fixed_offset_ms=0`、Rubber BandがないFFmpegでは音程維持の`atempo`へフォールバックする。開始を一律に前後させない。起動中PokeConには未反映のため、変更後PokeConの完全再起動と新規録画の実聴確認までは完了扱いにしない。
- Windows Media Playerの`0xc00d36c4`対策として、通常録画・提示時計再構築・旧録画修復のMP4は`brand=mp42`、`tag:v=avc1`、`video_track_timescale=60000`で作る。実録画の音程維持版を録画フォルダー直下の`recording_pitch_preserved_windows.mp4`へ映像・音声ともstream copyで再格納し、開始時刻0、6分18.93秒、H.264 High/AVC・AAC-LC、全編デコードエラー0を確認済み。
- `20260816_191004_896692`では初回提示区間が35.369msと通常の半クロスフェード40msより短く、FFmpeg `acrossfade`がエラーコード0のまま0 framesを出力した。旧成功条件が「終了コード0かつファイル存在」だったため、78 bytesの空WAVを使っ261 bytesの開けないMP4を残した。境界ごとにクロスフェードを隣接区間長以下へ縮小し、補正WAVの実フレーム数が`target_frames`と完全一致しなければ成功扱いしないようにした。最終MP4も1,024 bytes以下なら失敗扱いし、誤解を招く空MP4を残さない。
- 同録画は修正後WAV 17,174,611 frames（357.804396秒）と元AVIから録画フォルダー直下の`recording.mp4`へ復旧済み。復旧MP4は83,684,773 bytes、357.80秒、60fps、H.264 High/AVC・AAC-LC、全編デコードエラー0。旧261 bytes版は`recording_failed_261bytes.mp4`へ退避した。ユーザー側の実プレーヤーでの開閉確認は未完了。
- 上記初回復旧版はユーザー実聴で後半の映像が微妙に遅れた。元WAVと補正WAVの実音声指紋を対応時刻ごとに照合したところ、音声が60秒で約163ms、150秒で約489ms、210秒で約646ms先行していた。Rubber Bandが各5秒区間の末尾に約27msのflush tailを出し、その余分を区間ごとに切らず連結したことが原因。各区間に`apad=whole_len=<予定frames>,atrim=end_sample=<予定frames>`を適用し、クロスフェード前に区間長を完全一致させた。
- 上記区間長修正後の実音声指紋残差は30～240秒で約±2ms、270～352秒を含めて最大14.78ms。`20260816_191004_896692\recording.mp4`は音声だけを再結合した83,691,411 bytesの修正版へ置換済みで、357.80秒、60fps、全編デコードエラー0。映像stream SHA-256は置換前後で`79aaf7adf3d10f96b02d44ebeebab96ac622497d8af7028389d4da1acbf5256e`と一致。区間末尾未切断の比較版は`recording_before_segment_length_fix.mp4`へ退避した。ユーザー再実聴は未完了。

## 必須の実機確認手順

コード変更だけ、またはunit testだけで「60FPSを修正済み」と断定しないこと。

1. 変更対象のPokeConを完全に再起動する。Pythonソース変更は起動済みプロセスへ反映されない。
2. 表示上部の`入力xx.x / 表示xx.x fps`が測定値になるまで最低3秒待つ。
3. 次の値を別々に確認する。
   - 入力が約59～60、表示だけ低い: CameraではなくGuiAssets/Tk/GDI側を調査する。
   - 入力自体が低い: DirectShow、USB、Camera reader、デバイス交渉を調査する。
4. 以下の状態をそれぞれ15秒程度確認する。
   - PokeConが前面
   - Google/Chromeが前面でPokeConが背面
   - PokeConが1つだけ
   - 別PokeConを追加起動
   - チェック所有者が別にいる状態の最後に起動した通常PokeCon
   - 録画を停止して動画作成中だが、PokeConは閉じていない状態
5. 期待値:
   - チェック所有者: 表示約60
   - 所有者なしの最後に起動したPokeCon: 表示約60
   - 別所有者ありの最後に起動した通常PokeCon: 表示約30以上、5にしない
   - 古い通常PokeCon: 別PokeConがある場合のみ省負荷化可
6. 問題が残る場合は、ユーザーへ同じ一般質問を繰り返さず、`入力`と`表示`の実測値、発生時の前面アプリ、PokeCon数を基に次の層を修正する。

### 録画終了処理中の固まり防止

- 2026-08-15、メインPokeCon PID 6784だけが一時的にWindowsの「応答なし」となった。Camera接続は正常で、`CaptureRecordingFinalizer`が録画整理中に約1コア、続くffmpegが約2.7コアを使用し、複数PokeCon・ブラウザと合わせてPC全体がほぼ100%になっていた。USB映像停止ではなく録画終了処理によるCPU枯渇だった。
- cleanup画像判定は最大約120フレームだけを評価する場合でも、AVIを先頭から全フレーム復号してはならない。全区間へ均等配置した最大120位置へ直接seekして取得し、フレーム数不明時の逐次読込も120回で打ち切る。
- `CaptureRecordingFinalizer`はWindowsでbelow-normal thread priorityとし、ffmpegもbelow-normal process priority・最大2 encoding threadsで起動する。メインPokeConのabove-normal priorityを子ffmpegへ継承させない。
- 動画作成中もPokeConの入力・表示FPSを下げない。終了処理側を譲歩させ、変更後の完全再起動後に「録画停止して動画作成中」の入力/表示FPSとWindows応答状態を実測する。

### 新規録画の音声同期

1. Audioタブで録画対象入力を選び、`確認再生する`を開始する。PokeCon上で映像・音声が合っていることを確認してから録画する。
2. 録画後の`recording_timing.json`で、映像`presentation_mode`が`preview_presented`、音声`source_mode`が`pokecon_presented_output`、`tap_point`が`speaker_output_callback`、入力/再生APIが可能なら両方`Windows WASAPI`になっていることを確認する。
3. `callback_status_count`、`queue_drop_packets`、`confirmed_gap_silence_frames`がすべて0であることを確認する。
4. これは今後の録画経路の変更であり、既存MP4は自動では変わらない。旧録画は`PokeCon_録画同期修復.bat`を使う。
5. unit testだけで実聴同期済みと断定しない。変更後PokeConを再起動し、短い操作音のある録画を1本作って確認する。
6. その新規録画でも遅れる場合は固定offset版を追加せず、同録画の`first_presentation_offset_ms`、`presentation_frames`、callback/gap情報と実聴位置からpresentation経路を調査する。

## 調査に使う場所

- 実行環境: `.venv314`
- テスト:
  - `.venv314\Scripts\python.exe -m unittest tests.test_automation_features`
- ログ: `SerialController/log/log_*.log`
- 複数PokeCon登録:
  - `%LOCALAPPDATA%\PokeConModifiedExtension\active_windows.json`
- Windowsではvenv launcherと実アプリの2つのPythonプロセスが見える場合がある。実アプリは通常、作業セットとCPU時間が大きい子プロセス。
- カメラの`CAP_PROP_FPS`交渉値だけで60FPSと判断しない。画面上の入力実測値を優先する。
- 複数PokeConのうち指定PokeConが前面へ戻る再発調査では、`active_windows.json`の`main_effective`／PIDと、Windowsの`GetForegroundWindow`、`WS_EX_TOPMOST`、その時刻のダイアログ・Camera再接続・InputSet反映を照合する。2026-08-15 19:51の再発確認では3つのPokeConすべて`WS_EX_TOPMOST=False`で、メイン所有者PID 6784だけが前面だった。このため「常時最前面フラグ」ではなく、前面を取り直した契機を調べる。メイン所有権そのものを前面化理由にしてはならない。
- 2026-08-16 01:45～01:54の再発確認では、PID 20824／10404の2台とも最小化なし、`WS_EX_TOPMOST=False`、メイン要求・実効所有者ともなしだった。PID 10404を01:50:30に後から操作した記録があるにもかかわらず、未操作のPID 20824がZ順で上へ戻っていた。50秒監視中は両PokeConの相対順が常にPID 20824→10404で、可視の子ダイアログは残っていなかった。これは所有権監視や常時最前面ではなく、背面で作られた`transient`ダイアログの終了などが親だけを再浮上させ、そのZ順が残る経路として扱う。対策は「ダイアログ作成前から当該PokeConがWindows前面の場合だけ親へ`transient`接続／`lift`を許可」とし、無条件`focus_force()`を再導入しない。

## 関連する既存要件

- `ZA_mega_evolution_battle`は`lockon_rclick=1`を既定とする。ZLロックオン中かつ`POKEMON_ZA_C+`で攻撃可能な時にRCLICKを行い、直後3秒間は他の移動判定より`dir1`を優先して相手へ接近しながら既存の攻撃ループを続ける。同じロックオン中は無条件にRCLICKを連打せず、初回または`POKEMON_ZA_R_push`が残っている場合だけ3秒間隔で再試行する。`lockon_rclick=0`では従来の`POKEMON_ZA_R_push`画像判定によるRCLICKだけを使用する。実行元`ZA_story.py`と`ZA_MovementAndEvent.pyfrag`は同じ関数内容を維持する。
- `ZA_markerdir`のEVENT/PIN/SIDE_MARKERは同じ16領域を使い、全パターンの検知閾値を0.8に統一する。上下中央の`CENTER_WIDE_UPPER/DOWNER`はX=600～700とし、`UPPER_LEFT/RIGHT`・`DOWNER_LEFT/RIGHT`は中央帯と50px重ねて境界上でも検知を継続する。重複部は中央のUPPER/DOWNER判定をLEFT/RIGHTより先にして上下動作を優先する。さらに上下領域と中段のY境界、LEFT/RIGHTと左右端のX境界は30px重ねる。特に右下は`DOWNER_RIGHT`をX=650～1210・Y=570～720、右端をX=1180～1280として、X=1180またはY=600をまたぐマーカーが一時不一致になって探索方向と往復しないようにする。上下左右には中央接近帯`*_LEFT_NEAR`（X=450～650）と`*_RIGHT_NEAR`（X=650～850）を追加し、中央を飛び越えないよう0.2倍・duration=0で微調整する。接近帯・中央帯以外のLEFT/RIGHTと左右端は1.0倍・duration=0.03秒で早く回転し、各判定後の再検知待ちは0.1秒とする。右スティック角度はLEFT=180、RIGHT=0、中央下=270、中央上=90、左端=180、右端=0とする。一度でもマーカー領域を検知した後に画像が不一致になった場合、`else`では最後に成功した右スティックの角度・強さ・durationをそのまま再実行し、固定180度へ反転しない。まだ成功履歴がない場合だけ180度・1.0倍・duration=0を初期探索に使う。左上のミニマップ表示X=0～210・Y=0～210は全マーカー検知から除外する。周囲だけを維持するため、`UPPER_LEFT`をX=210～650、左端をY=210～720、`LEFT_WIDE`を下側X=70～680・Y=210～600とマップ右側X=210～680・Y=100～240のOR判定に分割し、境界には30pxの重なりを残す。中段の`CENTER_WIDE`重複部も0.2倍を維持する。DevStudioの画像検知登録と、実行する`ZA_story.py`の管理登録には同じ閾値・領域を反映する。
- Switch2 InputSetは機能制限版。Commands、解析、範囲指定、Tk重ね描画を通常は無効にする。
- Tk重ね描画が必要な録画条件を制限版で使う場合は、通常版への変更が必要だとポップアップで知らせる。
- InputSetなどのプルダウンは意図せずマウスホイールで値を変更しない。
- Windows直接描画から実際に`No Image`へ移る際は、古いGDI画素を全面消去し、現在の表示サイズの代替画像で覆う。通常の入力切替・表示サイズ変更の短い空白では最後の正常フレームを保持し、`No Image`を差し込まない。
- Camera Name選択は映像入力へ実際に反映し、DirectShow接続中にTkを停止させない。
- 固まったPokeConの復旧では、対象InputSetのプロセスだけを終了できる復旧画面/バッチを維持する。
- Dev Studioの項目数が増える一覧・ツリー・複数行編集欄には、見える縦スクロールバーを付ける。長いパスや列を持つ箇所は横スクロールも付け、マウスホイールはポインター下の一覧だけを動かす。画像検知ライブラリだけの個別対応にせず、Explorer、検索、Step、サンプル、差分・選択ダイアログなど同種の項目へ共通適用する。
- Dev Studioの`関数登録`タブは右ペインが低い場合でも、`選択をサンプルへ登録`と登録名確認ボタンを関数一覧の直上へ常時表示する。詳細な改名・登録先・依存処理設定を含むタブ全体にも縦スクロールを付け、一覧の高さによって登録操作が画面外へ隠れないようにする。
- `関数登録`タブの登録済み判定は`.pokesample.json`の代表`name`だけを見ず、各`.pyfrag`内の全関数定義を関数単位で照合する。複数関数サンプル内に同じ処理があれば`登録済み`として親サンプルを開けるようにし、同名で処理差がある場合は`処理差あり`、複数登録は`同名複数`と表示する。依存グループが既存関数を再利用した場合も、その関数の同期ハッシュを親メタデータへ保存する。
- Dev Studioの画像検知ライブラリ一覧は、`Template/Samples`を初期除外し、カンマ・セミコロン・改行区切りで任意のTemplateフォルダーを追加除外できるようにする。除外は一覧表示だけに適用し、登録データを削除しない。選択中パターンの実テンプレート画像を右側へ縦横比を維持して表示し、元画像サイズと絶対パスも確認できるようにする。
- Dev Studioのサンプル関数チェックでプロジェクト直下などサンプルライブラリの親フォルダーが指定された場合は、実際の`SerialController/DevTemplates/Fragments`へ安全に補正して全登録サンプルを比較する。登録元ソースが旧ドライブの絶対パスまたは`SerialController/...`相対パスでも、同じportable pathなら現在のソースとして追従する。再チェックで比較対象0件になった場合は空画面のままにせず警告する。
- Dev Studioのサンプル関数チェックで「サンプル関数 → ソース」または安全な一括反映・関数置換・使用箇所反映を実行した場合、エディタを未保存状態へ変更するだけで完了扱いにしない。反映前バックアップを作り、Python構文を検証して実際の比較元`.py`へ原子的に保存し、保存後内容を再読込してから一致表示へ更新する。ボタンと完了表示は「ソース保存済み」を明示する。直前の一括反映を戻す場合も、保存先が記録されていれば実ソースへ復元保存する。
- Dev Studio上部の共有検索バーは、一致件数が1件以上なら現在位置を`0 / N`のままにしない。入力・再検索・検索対象切替時に、直前の一致位置またはカーソル以降の一致を選択して`1 / N`以上を表示する。検索欄へ入力中は対象エディタへフォーカスを奪わず、`前へ`／`次へ`を押したときだけエディタへ移動する。

## 現在のテスト基準

2026-08-16時点で `tests.test_automation_features` は317件。件数は増減し得るため、件数そのものより全件成功を確認する。
