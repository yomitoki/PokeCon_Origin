# Dev Studio implementation status

This file is the source of truth for the sample-library work.  Do not mark an
item complete until the code path has been exercised or a focused verification
has been recorded.

## Sample library

| Requirement | Status | Implementation / verification |
| --- | --- | --- |
| Sample function metadata (imports, class variables, body) | Complete | `SampleLibrary.py` + `PokeConDevStudio.py`; composition and conflict-reviewed merge smoke-tested. |
| Save folder selection and folder creation | Complete | Folder is constrained under `DevTemplates/Fragments`; GUI construction and catalog round-trip verified. |
| Sample-list member add/remove with selection retained | Complete | Refresh accepts list/member selection and restores both after atomic JSON writes. |
| Tag filter for sample functions | Complete | Exact metadata filtering plus searchable existing-tag dropdown and scrollable add/remove selection UI implemented. |
| Folder hierarchy filter for sample functions | Complete | Expandable checkbox tree supports multiple folders; selecting a parent includes all descendants. |
| Sample-list tags and tag filter | Complete | Schema v2 stores list tags; existing list tags feed the searchable dropdown and scrollable add/remove selection UI. |
| Add another sample list as a member | Complete | Explicit `fragment`/`list` members, recursive flattening, deduplication, and cycle rejection implemented. |
| Open selected fragment in Sample functions for editing | Complete | Double-click loads metadata, imports, variables, requirements, folder and body into the form. |
| Right-side list content/source preview | Complete | Read-only preview uses the exact sample-program shell generator, including class, `do()`, metadata and refresh markers, without writing a file. |
| Separate sample-program authoring tab | Complete | Editable shell creation, refresh with preserved user regions, and nested save/load under `DevStudio/SampleCommands` added. |
| PythonSampleCommand loader | Complete | PokeCon Commands UI has a dedicated Python Sample Command tab backed by recursive `DevStudio/SampleCommands` load/reload and the normal start/stop path. |

## Rules

- Remove the incorrect `generate_sample_command` feature before adding the
  preview and sample-program authoring workflow.
- Sample list data must be versioned JSON with explicit member types.
- Apply/merge must show conflicts before modifying a source file.

## Verification record (2026-08-01)

- Direct `compile(...)` validation passed for the Dev Studio UI and all new modules.
- Headless library smoke test passed: legacy migration, schema v2 atomic save, metadata tag/folder catalog, nested-list resolution, preview merge, and program-loader validation.
- Tk GUI construction smoke test passed with four workspace tabs and the sample-program controls present.
- The full PokeCon base import additionally requires the existing optional `numpy`/OpenCV runtime; the new subclass contract was therefore checked in isolation.
- `git diff --check` passed.
- Function tags and list tags use the shared `TagPicker`; GUI checks cover narrowed dropdown values plus add/remove behavior.
- Function-candidate tags use a partial-match searchable readonly dropdown; folder filtering uses an expandable multi-select tree with ancestor scope.
- The complete right-side sample-list editor is vertically scrollable at minimum window size; its inner width follows pane resizing while nested lists keep their own scrollbars.
- Sample-program refresh replaces ID/hash-tracked generated fragments while preserving `POKECON_USER_DO` and `POKECON_USER_METHODS`; an updated-fragment GUI smoke test passed.
- Sample source save/load is constrained to `DevStudio/SampleCommands` and supports nested folders; a nested round-trip smoke test passed.
- Sample-program editor shows synchronized line numbers, supports gutter drag selection, highlights syntax-error lines, maps Tab to four spaces, and preserves indentation on newline.
- Registered fragments can be edited in place without changing their IDs, or deleted with usage confirmation and automatic removal from every sample list; entry buttons exist in the function tab, list members/candidates, and combined preview header.
- Sample-list member and function-candidate rows open the selected fragment directly in function edit mode by Change, double-click, or Enter.
- The PokeCon main window loads nested `DevStudio/SampleCommands` separately from normal Python commands, exposes filter/select/reload/start controls, and includes sample commands in Command Watch.
- The compact PokeCon `Others` tab is hosted in a width-following vertical scroll canvas so all settings remain reachable when the notebook height is limited.
- The PokeCon notebook now inserts `InputSet` at index 0. Profile-local `input_sets.json` stores Camera/Audio sets and named InputSet/Recording-preset combinations with create, update, delete and load actions. Camera restore resolves exact DirectShow device path first, then VID/PID, display name and saved camera index.
- Ambiguous VID/PID or camera-name matches open a modal candidate chooser. Each candidate must be test-switched and visually checked in the main preview before it can be committed; cancelling restores the prior camera. Input sets and their dependent combination sets remain explicitly deletable for device replacement.
- The InputSet tab is hosted in a width-following vertical scroll canvas with pointer-scoped mouse-wheel handling, keeping the combined-set controls reachable at compact notebook heights.
- Audio InputSet restore ignores the volatile PortAudio list prefix (`2:`) and Windows reconnect instance counter (`(3- USB...)`). New sets persist both the display name and normalized identity, while old sets are normalized on load for backward compatibility.
- Confirming close during MP4 finalization now exits immediately after conversion without showing the generic exit confirmation a second time; ordinary window close still uses the normal confirmation.
- InputSet can explicitly omit Audio via `Audio設定を含める`; loading such a set clears Audio without a missing-device warning. A configured Serial Device Name is saved automatically with COM, VID/PID and serial number and restored in stable-identity-first order.
- Command Start state is re-evaluated after Reload, command-tab changes and every filter update. A command added after an initially empty load now selects the first result and enables both Start buttons; empty/filtered-out tabs remain disabled.
- Fragment composition now dedents pasted class-method source before applying class indentation, preventing helpers from becoming local functions inside `do()`. The existing `etc_sendCommand` fragment/generated sample was repaired, and command exceptions are mirrored to the original console stderr when GUI output redirection is active.
- Sample-function metadata/UI now supports per-run initializer code. Generated commands expose `initialize_sample()`, call it only after Start at the beginning of `do()`, preserve a `POKECON_USER_INIT` region on refresh, and keep class constants separate from per-run `self.*` state.
- Added the `Steam_Switch_Game_Input` sample list. Its per-run initializer selects Steam/Switch and a game-profile array; `game_input()` maps controller-style names to up to five simultaneous keyboard keys for Steam/PS4-style targets or uses standard PokeCon `Button`/`Hat` input for Switch.
- Added a full Image Detection workspace backed by `Template/image_detection_profiles.json`. A detection name can retain multiple matching variants, Template folder names become searchable tags, and nested detection lists resolve with cycle checks.
- Image-detection lists generate or update a marked `image_check()` block in either Source Edit or Sample Program. Sample-function refresh preserves that block and its LocalFunction import; generated sample commands now receive Camera/preview without changing the original PythonCommand base API.
- `SerialController/LocalFunction/ImageDetection.py` provides portable score-returning matching, bounded similarity history, average/min/max and missing-interval summaries, graph rendering, and camera+graph+log composite frames for future recording integration.
- Source Edit > Apply Sample List now contains a scrollable hierarchical image-detection picker. Template folders, individual targets and nested detection lists can be filtered, staged as required items, flattened/deduplicated and applied to the currently edited source.
- The Image Detection workspace displays saved targets under their Template folder hierarchy and can import literal `IMAGE_DETECTION_TARGETS` from Source Edit or Sample Program into the editable catalog. Re-applying generated code preserves the final `POKECON_IMAGE_CHECK_USER` exception block.
- Generated command source imports only matching/history helpers; graph rendering and recording composition remain opt-in functions on the local PokeCon side and are never injected into distributed command source.
- The configured Python 3.7 user environment was repaired with `numpy==1.21.6`; unrestricted verification imported NumPy 1.21.6 and OpenCV 5.0.0, then passed a real synthetic template match plus graph/composite-frame smoke test.
- The legacy Source Edit > Image detection side panel now bridges directly to the registered detection catalog. Its current fields can be saved as a standalone target (with an automatically created single-target list), and a folder-hierarchy browser can add/remove registered variants from the current source debug targets, apply them to `image_check`, or explicitly delete the registration itself.
- Selecting a source image-target row now enters an explicit `変更モード: <name>` state and loads its values; double-click uses the same path. Source removal and library deletion are separate operations to prevent accidental loss of reusable registrations.
- Registered image targets and image-detection folders now store editable descriptions. Descriptions participate in the Image Detection and Apply Sample List searches and are emitted into generated source as `IMAGE_DETECTION_DESCRIPTIONS` for later source-to-catalog editing.
- Each image-detection target has an explicit `AND`/`OR` operator. A single `image_check("target name")` evaluates every image registered under that argument and combines the results with the target operator. Nested lists are organizational folders only and retain cycle checks.
# Pokemon ZA story migration (2026-08-01)

- `ZA_story.py` の画像検知243件を `POKEMON_ZA_*` 名へ移行し、既存の閾値・ROI・カラー設定を画像検知ライブラリへ登録した。
- 登録画像のタグはすべて `Pokemon_ZA` とし、Template配下のフォルダ単位セットと `POKEMON_ZA_ALL` を作成した。
- 画像以外の特殊判定6件を `POKEMON_ZA_*` 名へ変更し、`image_check_exception()` の例外対応領域へ移した。
- DevStudioのStep階層に `STATE_*_FUNCTION` の非破壊読み取り、対象メソッド移動、状態追加・変更・削除とソース反映を追加した。追加状態のメソッドが未定義なら編集用マーカー付きスタブも生成する。
- ZA_storyの再利用可能処理106関数を依存グループ別に抽出し、定義・内部呼び出し・状態辞書・単純初期値を `ZA_` 名前空間で登録した。
- `Pokemon_ZA_MovementAndEvent`、`Pokemon_ZA_Common`、`Pokemon_ZA_BattleAndRoyale`、`Pokemon_ZA_AllReusable` の依存リストを登録した。
- ZA_story内の到達不能な旧監視処理、旧画像検知2関数、`_legacy_Benchi` を削除した。FIELD6判定、ウィンドウ取得のself不足、共通処理の重複名も修正済み。
