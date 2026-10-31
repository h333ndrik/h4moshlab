# V5.3 State

Letzter Stand: 2026-10-31 20:03 CET
Abgeschlossen: Block 3 (commit cb893482d564c80b7d7fdc72eed78b73515f830d, Tests: 41 OK)
In Arbeit: Keine uncommittierten Implementierungsänderungen.
Als nächstes: Block 4, Schritt 1 (framegenauer Clip-Trimmer), noch nicht begonnen.
Letzte Testausgabe (Kurzfassung): Ran 41 tests in 142.674s — OK

## Block 3 completed

Code/test commit: cb893482d564c80b7d7fdc72eed78b73515f830d.
Only web/app.js, web/index.html and tests/browser_smoke.py changed.
This follow-up commit updates V5_STATE.md only. PROJECT_PROGRESS.md and
NEXT_SESSION.md remain untouched; their documentation updates belong to Block 8.
The separate Documents request was explicitly cancelled by the user.

### Behavior

- File-picker and main/viewer/#empty file drops share importFiles(), retaining
  limits, original source handling, progress/error feedback and one undo action
  per import. Busy drops are ignored. Clip cards remain reorder/duplicate targets
  and do not import files. Internal text drags are not treated as file imports.
- Space toggles the visible preview. Left/right seek by 1/24 second;
  Shift+left/right seek by one second, clamped to the media duration.
- In an open transition dialog, shortcuts address the visible #motion-preview.
  Closed/hidden motion details, an unrelated modal, missing metadata/source,
  focused input/select/textarea/contenteditable controls and Ctrl/Meta/Alt
  combinations are excluded. Existing history/duplicate shortcuts are preserved.
- preventDefault is used only for playback actions the handler actually handles.
- The empty-view hint mentions dropping a video. No new controls or layout/CSS
  changes; all HTML IDs, heading, tab title, cursor/visit and export remain.

### Actual verification

Baseline: Ran 41 tests in 136.777s — OK.
Final: Ran 41 tests in 142.674s — OK.

All exited 0:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py
node --check web/app.js
python3 -m py_compile tests/browser_smoke.py
```

The updated existing browser smoke also exited 0:

```sh
H4_EDITOR_TEST_URL=http://127.0.0.1:8841 python3 tests/browser_smoke.py samples/clip-a.mp4 samples/clip-b.mp4 work/block2-clip-c.mp4
```

The third synthetic fixture is an unchanged copy of samples/clip-a.mp4 under a
separate filename. No private media was used or committed.

Actual smoke output:

```json
{"browser":"chromium","clips":3,"duration":17.916667,"javascript_errors":[],"drop_import_busy_card_exclusion_preview_keys_frame_step_undo_redo":"passed","upload_reorder_settings_reload_render_scrub_transition_preview_download_error_retry_remove_ranges":"passed"}
```

New assertions verify actual File/DataTransfer import through #empty; a second
file drop during a held real upload is ignored; card file drops are excluded;
file-picker import still works; Ctrl+Z/Ctrl+Shift+Z restore imports; Space toggles;
arrow steps equal 1/24s within browser microsecond precision; Shift seeks 1s;
dialog keys affect only the motion preview. All earlier render/export/full-decode,
source-hash, recovery, reordering and narrow-layout assertions remain intact.

Additional Chromium guards passed: successful main-area drop; no interception
without a source, while an input/select/textarea is focused, with modifiers, or
in the project modal; a 13-file drop is rejected by the shared import limit
without uploads, order changes or extra history. No test failed in Block 3.

Ignored local evidence and desktop/390px screenshots:
work/v53-block3-verified/. The extra guard harness/log are stored there as well.

## Block 2 completed

- Server accepts repeated source IDs in jobs and restoration; still 1–12
  timeline entries, at most 24 retained source files, one dict/cache per source.
- Duplicate button, Cmd/Ctrl+D and Alt/Option+Drag use the same history action
  in editor-actions.js. Independent timeline entries share the original source,
  with separate looks and transition settings. Removing one copy keeps its source
  available to the others and undo.
- .h4mosh saves an order array with repeated source IDs. Validation converts
  repeated references into hash-relinkable source references. Old projects and
  the prior candidate source_ref format remain supported.
- Copy/Paste is a deep copy, omits source random_seed/audio_follow, preserves
  those fields at the destination, and disables Paste with an explanatory
  tooltip if the incoming clip violates the duration/motion/window guards.
- Alt is tracked through keydown/keyup; blur clears it. Drop reads this global
  state rather than event.altKey. dragstart also records copy/move in
  application/x-h4-drag-mode. Normal reordering is preserved.

## Diagnosis and regression evidence

The earlier no-drop trace was initially treated as a possible simulation
limitation. Investigation on the unchanged baseline established an actual stale
DOM state: after both import and undo, busy was false while every card still had
`draggable=false`. draw() had run while busy; controls() never restored dragging.
The targeted fix updates card.draggable alongside the existing busy controls.

A second candidate was stopped before the latest retry after its normal-reorder
assertion failed; it was saved and rolled back. The latest retry started again
on the verified 39-test baseline. The exact previously failing reorder assertion
was retained and now passes after undo. No assertion was weakened to hide it.

Native Alt+Drag now passes both from the border and from the default center
with page.keyboard.down('Alt') before the drag. The native trace records
mode=copy. There is no remaining reported simulation limitation for that test.
A drop with altKey=false also duplicates through the key-tracked state.

## Actual verification

Starting baseline:

```text
Ran 39 tests in 130.728s
OK
```

Final suite (python3 -m unittest discover -s tests -v):

```text
Ran 41 tests in 136.135s
OK
```

The reused integration tests exercise an actual duplicate-source HTTP render,
restore and the 12-entry limit, matching source hashes, exact frame count and
full decode. Project tests cover repeated IDs, legacy references, wrong hashes
and malformed order rejection.

All exited 0:

- python3 -m py_compile tools/*.py
- node --check web/app.js
- node --check web/editor-actions.js
- node --check web/editor-tools.js
- node tests/editor_tools_test.js
- git diff --check

Chromium checks passed:

- Mandatory Duplicate button 3 → 4; one shared source, independent entries;
  undo 4 → 3, redo 3 → 4; dragging enabled after import/undo/redo.
- Independent looks/settings, Copy/Paste and destination-local fields,
  clipboard deep copy and short-clip tooltip guard.
- Session reload, downloaded project reopen, cold-server SHA256 relink,
  actual assembled duplicate render, 12 entries and only two retained sources.
- Native Alt+Drag, missing event.altKey, Alt release, blur and normal reorder
  after undo. No JavaScript errors.
- Existing unmodified tests/browser_smoke.py: three clips, duration 17.916667s,
  upload/reorder/settings/reload/render/scrub/transition preview/download/
  error/retry/remove/ranges passed, javascript_errors=[];
  real exported MP4 fully decoded.
- Desktop and 390px screenshots inspected; no page/control overflow. Duplicate
  sits beside Look so the existing coarse-pointer reorder row still fits.

## Changed tracked files

Code/test commit 8354f46 changes only:

- tools/server.py
- web/app.js
- web/index.html
- web/editor-actions.js
- web/editor-tools.js
- tests/test_sequence.py

This separate state commit updates only V5_STATE.md, as required.
Local ignored evidence: work/v53-block2-verified/, work/block2-1200.png,
work/block2-touch390.png and work/block2-default-drag-trace.json.
Recovery patches/logs from unsuccessful attempts remain in the separate ignored
work/v53-block2-stopped/ and work/v53-block2-retry-stopped/ directories.

## Preserved invariants / remaining work

- Branch v5-plan only; no merge into editor-workflow.
- main remote: c62b5c5ac2b4de8d7f779476f99ad5aae8464ffe, unchanged.
- Blueprint tag object: 06d276234ee64dcfa537a44549aba44d23266488, unchanged.
- Block 1 cursor/visit, style.css, 640x480/24fps, one Export button unchanged.
- tools/sequence.py and tools/clip_audio.py unchanged, including the hard
  audio/video sample-count check; audio regressions remain green.
- No new runtime dependencies; private originals remain untouched/ignored.
- Blocks 4–8 not started. No mobile/hosting/effect work added here.
- Block 5 clarification remains: preserve pitch with atempo and test preserved
  tone frequency rather than doubling/halving pitch.
- Existing uncommitted AGENTS.md naming note predates this task; preserved
  separately, excluded from these commits.
