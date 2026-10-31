# V5.3 State

Letzter Stand: 2026-10-31 01:32 CET
Abgeschlossen: Block 2 (commit 8354f46a69d36c0c012e0c5ec03c46d20f9049c2, Tests: 41 OK)
In Arbeit: Keine uncommittierten Implementierungsänderungen.
Als nächstes: Block 3, Schritt 1 (Drag & Drop Import), nicht in diesem Block-2-Anlauf begonnen.
Letzte Testausgabe (Kurzfassung): Ran 41 tests in 136.135s — OK

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
- Blocks 3–8 not started. No mobile/hosting/effect work added here.
- Block 5 clarification remains: preserve pitch with atempo and test preserved
  tone frequency rather than doubling/halving pitch.
- Existing uncommitted AGENTS.md naming note predates this task; preserved
  separately, excluded from these commits.
