# V5.3 State

Letzter Stand: 2026-11-02 21:01 CET
Abgeschlossen: Block 4a (commit 36fa044b06b41dbe4a536ae0610b5fe571b6a656, Tests: 51 OK)
In Arbeit: Keine Implementierungsänderungen; Block 4b als nächster Micro-Block autorisiert.
Als nächstes: Block 4b, Root-Cause-Analyse und zurückgestellte Disable-Sync-Assertion.
Letzte Testausgabe (Kurzfassung): Ran 51 tests in 175.168s — OK; Browser 4a PASS, Disable-Sync explizit ausstehend.

## Block 4a completed

Feature commit: 36fa044b06b41dbe4a536ae0610b5fe571b6a656.
Pending: UI disable-sync after trim, assertion specified in block 4b.

The saved candidate was restored. Only the two positive Progressive Melt disabled
assertions after short trim / redo were explicitly deferred by the user; every
other duration, preview, reset, history, tooltip, audio, hash and decode assertion
was retained. Full-length enabled status after Undo also remains tested.

Completed: non-destructive per-entry frame markers; source/look/range caches;
look-free trim/geometry pass followed by MPEG4 q4/g10000/bf0/sc_threshold0/m4v;
strict one-I/remaining-P checks; sample-exact 2000-sample PCM frame blocks; hard
render audio/video invariant; Trim dialog and real selection preview; reset;
history; project download/reload and cold-server SHA256 relink of independently
trimmed duplicate entries. Source files remain unchanged.

Trim validation in Handler.do_POST follows authorization and precedes the busy
gate: invalid parameters return 400, valid busy processing requests return 409.

Actual results:

```text
Baseline: Ran 41 tests in 140.852s — OK
Final:    Ran 51 tests in 175.168s — OK
```

python3 -m py_compile tools/*.py, node --check web/app.js, frontend syntax and
Node editor-tools checks passed. Full Chromium smoke passed with no JS errors:
trim_preview_duration_reset_undo_redo_full_decode=passed,
ui_disable_sync_after_trim=pending_block_4b; complete ordinary export duration
17.916667s. Trimmed render fully decoded and original hashes checked.

Additional Chromium workflow passed: differently trimmed duplicate instances
(36 and 24 frames) with independent looks, project download, session reload,
cold-server relink from one original, and a 59-frame full-decode render. Desktop
and 390px screenshots inspected. Ignored local evidence: work/v53-block4a-verified/.

Pending 4b assertion (not active in 4a):

```python
assert page.locator('#effect option[value="progressive-melt"]').is_disabled()
```

Precondition: incoming clip trimmed below 13 frames; expected enabled again after
Undo restores full length, disabled again after Redo. Block 4b must establish the
root cause from response metadata, entry mapping and native DOM state before a
fix; 4a does not claim this sync is solved.

Code commit touched only the eleven restored Block-4 implementation/test files;
this follow-up changes only V5_STATE.md. main, Blueprint, prediction algorithms,
cursor/visit, output dimensions and single Export action are preserved. No new
runtime dependency. PROJECT_PROGRESS.md/NEXT_SESSION.md updates remain Block 8.
The pre-existing unrelated AGENTS.md naming note is untouched/uncommitted.

## Historical Block 4 third attempt: HTTP fixed in candidate, UI still failed

Baseline: Ran 41 tests in 147.246s — OK. The saved candidate was reapplied with
only the requested HTTP/availability corrections and required codec configuration.
After the browser assertion failed, no further fixes or tests were started; the
already-running full suite was allowed to finish. All eleven implementation/test
files were then restored to HEAD. No Block-4 feature commit was made.

### HTTP correction — verified in the discarded candidate

Handler.do_POST() calls validate_trims_before_processing() after Host/Origin and
LAN authorization, BEFORE app.busy.acquire(). This synchronous preflight parses
bounded JSON once via read_json(), validates per-entry trim markers through
timeline_trims(), and for POST /api/jobs validates transitions against the
trimmed lengths via validate_project_settings(). ValueErrors return 400 before
any processing/cache work. Valid requests still receive 409 if processing is busy.

The original failing HTTP assertion was NOT changed and now passes. An additional
regression holds the busy lock deliberately: invalid /trim and /api/jobs markers
both return 400, while a valid /api/jobs request returns 409. All cases passed.
This correction is saved in the patch but is NOT in the committed application.

### Availability correction attempted, not verified

The candidate centralizes option availability in updateEffectAvailability(),
using the actual incoming state.clips entry frames (<13 for aligned effects),
and invokes it from openTransition(), updateDialog() after clamping, and controls()
after processing/undo updates. Per-entry metadata replacement remains separate
from other instances of the same source. No existing assertion was relaxed.

Despite those changes, the same original browser assertion still failed:

```text
File "tests/browser_smoke.py", line 152, in <module>
  verify_trim(page)
File "tests/browser_smoke.py", line 81, in verify_trim
  assert page.locator('#effect option[value="progressive-melt"]').is_disabled()
AssertionError
```

Do not infer a root cause from this alone. A future authorized attempt needs to
capture the API response, state.clips incoming frame count, dialogIndex, selected
option and actual disabled property/attribute immediately before the assertion.
The newly appended Undo/Redo option assertions were not reached.

### Exact verification / normalization

```text
Ran 51 tests in 170.771s
OK
```

All original 41 tests, prior invalid-marker HTTP test, new busy-lock validation
regression, 2/3-frame exports for all four looks, exact PCM/audio invariants,
color-range selection, project metadata and source-hash checks passed.

python3 -m py_compile tools/*.py, node --check web/app.js and
node tests/editor_tools_test.js exited 0. Additional frontend syntax checks
passed before execution. The full browser smoke FAILED; Block 4 is not complete.

The candidate uses the required MPEG-4 normalization configuration for trim:
g=10000, bf=0, sc_threshold=0, q=4, codec=mpeg4, format=m4v. The previous
1000000000 threshold was removed. Trim and look remain separate passes, and the
one-initial-I/subsequent-P validation plus render() audio sample check are intact.

Recovery artifacts: work/v53-block4-third-stopped/implementation.patch,
h4-block4-third-baseline.log, h4-block4-third-unit.log and h4-block4-third-smoke.log.
They are ignored/local. The app remains at completed Block 3; source-code diff
against HEAD is empty. main/Blueprint remain unchanged. The pre-existing AGENTS.md
naming note is preserved separately, uncommitted.

## Earlier Block 4 retry: diagnosis completed, implementation stopped

The latest retry was explicitly authorized. It started on the unchanged Block-3
application: Ran 41 tests in 149.868s — OK. After the new failures, all eleven
candidate files were restored to HEAD. No Block-4 code has been committed.
The unrelated AGENTS.md naming note remains untouched and uncommitted.

### Isolated diagnosis before implementation

The exact red/green/blue fixture was recreated and normalized without any trim.
All four looks produced 36 frames, with an unexpected extra I-VOP at frame 24:
I positions [0,24]. Therefore the earlier failure occurred BEFORE trim, even with
Original/no look. It was not caused by an empty short-look filter or a missing
post-look minimum-frame check.

Separately trimming source frames 12–14 or 12–15 BEFORE normalization, followed
by each of Original, Black & white, B&W negative and Color negative, gave:

- 2 frames: [I,P], all four full intermediate decodes exited 0.
- 3 frames: [I,P,P], all four full intermediate decodes exited 0.
- Original synthetic source SHA256 remained unchanged.

Encoder isolation confirmed the cause:

```text
mpeg4 sc_threshold=0:          36 frames, I positions [0,24]
mpeg4 sc_threshold=1000000000: 36 frames, I positions [0]
```

A zero scene threshold does not disable automatic I-VOP insertion at hard cuts.
The rejected candidate used a lossless, look-free trim/geometry pass on the 24fps
grid, then a separate look/MPEG-4 cache pass with automatic scene resets disabled.
The one-initial-I/remaining-P validation remained strict; effect algorithms and
sample-count validation were not weakened.

Diagnostic script and full JSON reports: work/block4-diagnosis/ and copies under
work/v53-block4-retry-stopped/. This diagnosis is also recorded in the state
commit message, as requested.

### Actual failures / HARD STOP

Browser smoke failed first in verify_trim(), line 81:

```text
assert page.locator('#effect option[value="progressive-melt"]').is_disabled()
AssertionError
```

Prior trim preview, duration update, fully decoded trimmed render, Undo/Redo,
Reset and disabled Export assertions had passed. The effect-option assertion
failed; its cause was not established and no test/implementation fix was made
after HARD STOP.

The already-running full suite then completed:

```text
FAIL: test_trim_variants_are_per_entry_and_http_rejects_invalid_markers
  tests/test_sequence.py, line 216
  self.assertEqual(request(endpoint,{'start_frame':start,'end_frame':end})[0],400)
AssertionError: 409 != 400

Ran 50 tests in 175.435s
FAILED (failures=1)
```

The exact reason for the unexpected busy response is not established; do not
change the expected invalid-marker rejection to 409 simply to pass the test.
All 41 existing tests passed unchanged. The newly added two/three-frame tests
for all four looks (including actual MP4 render/full decode), two-frame audio
sample invariant, exact PCM slicing and original color-range regression also
passed. This does not make the complete Block 4 verified.

Preflight Python/Node syntax checks passed. Chained post-suite checks were not
executed because unittest exited 1. No further tests or fixes were started after
the first red browser result. The in-progress unittest was allowed to finish.

### Recovery / committed state

work/v53-block4-retry-stopped/implementation.patch contains the rejected candidate
and unchanged tests. The directory also contains the baseline, full unit/browser
logs, diagnostic script and report.json / thresholds.json. It is ignored/local.

The committed app remains Block 3. git diff HEAD -- tools web tests is empty.
main/Blueprint remain unchanged; no merge into editor-workflow. Only this state
file is committed for the stopped attempt. Blocks 5–8 remain untouched.

## Earlier Block 4 stopped — no feature commit

The committed application remains exactly at completed Block 3. All eleven
uncommitted Block-4 implementation/test files were restored to HEAD after the
failure. The existing unrelated AGENTS.md naming note was preserved separately.
No Block 4 code was committed, and Blocks 5–8 were not started.

### Actual verification

Starting baseline, before implementation:

```text
Ran 41 tests in 151.315s
OK
```

Candidate full suite:

```text
ERROR: test_frame_trim_selects_the_requested_images_and_keeps_original
  (test_sequence.SequenceTests.test_frame_trim_selects_the_requested_images_and_keeps_original)
Traceback (most recent call last):
  File "tests/test_sequence.py", line 175, in test_frame_trim_selects_the_requested_images_and_keeps_original
    clip=prepare(source,self.root/'green-trim',start_frame=12,end_frame=24)
  File "tools/sequence.py", line 39, in prepare
    raise ValueError('Video must normalize to at least two I/P frames.')
ValueError: Video must normalize to at least two I/P frames.

Ran 45 tests in 151.340s
FAILED (errors=1)
```

The new test generated red/green/blue sections and attempted to select frames
12–24. It failed during normalization validation before the trim operation.
The actual offending VOP pattern/cause has not been established. Do not weaken
the existing one-I/remaining-P requirement or adjust the test to hide the error.

Preflight Python compilation and Node syntax checks passed before the suite.
The chained post-suite checks did not run because unittest exited 1.
The new exact PCM trim/export test, per-entry HTTP trim/validation test and
project-metadata test passed in this rejected candidate, but this is NOT a
verified Block 4 implementation. The browser smoke was interrupted after the
unit failure and has no successful result to report.

### Recovery and next diagnosis

Ignored local evidence: work/v53-block4-stopped/implementation.patch,
h4-block4-unit.log, h4-block4-baseline.log and h4-block4-smoke.log.
The patch contains all candidate changes and tests, unchanged after failure.

An additional code-review concern in the discarded candidate (not fixed after
HARD STOP): controls() computes a preview problem from dialogIndex+1 without
first excluding dialogIndex=null. A future retry must inspect this guard before
browser verification; do not claim that browser behavior passed.

The candidate changes touched sequence/clip_audio/server, app/index/style,
editor-actions/editor-tools and sequence/audio/browser tests only. The effect
algorithms were untouched. git diff HEAD -- tools web tests is empty after
rollback. main and Blueprint identities remain the recorded values below.

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
