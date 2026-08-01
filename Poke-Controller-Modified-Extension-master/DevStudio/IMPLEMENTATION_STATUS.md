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
