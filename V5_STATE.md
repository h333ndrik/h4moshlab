# V5.3 State

Letzter Stand: 2026-10-30 13:19 CET
Abgeschlossen: Block 1 (commit 0b5b055, Tests: 39 OK)
In Arbeit: Keine Implementierungsänderungen. Block 2 nach Browser-Testfehler gestoppt und vollständig zurückgesetzt.
Als nächstes: Block 2, Alt+Drag-Fehler untersuchen, erst nach neuer Freigabe zum Fortsetzen der HARD-STOP-Regel.
Letzte Testausgabe (Kurzfassung): Ran 41 tests in 150.045s — OK (verworfener Block-2-Kandidat); Browser Alt+Drag — FAILED.

## Current committed application

The application is unchanged from 0b5b055. Block 2 was NOT committed.
Blocks 3–8 were NOT started. No failing/partial implementation remains.
Starting baseline: Ran 39 tests in 146.166s — OK.
The 41-test result belongs to the discarded candidate, not the committed tree.
Python compilation and app.js syntax passed for that candidate.

## User clarifications received

- web/editor-actions.js and web/editor-tools.js are additionally authorized
  for Block 2 only, limited to Duplicate/Undo/project serialization.
- Block 5 must preserve pitch with atempo; tests should expect preserved
  tone frequency, not doubled/halved pitch.

## Hard stop evidence

The candidate browser check reached the Alt+Drag step after checking:
Duplicate button, independent look, Copy/Paste, retained destination-local
random_seed/audio_follow, Undo/Redo, session reload, actual project download
and reopen, Ctrl+D and undo. These preceding assertions passed.

Alt+Drag from the first to third card did not duplicate the clip:

```text
/tmp/h4-block2-browser.py, line 41
AssertionError: Locator expected to have text '4 clips'
Actual value: 3 clips
```

Cause not established. Per the explicit V5.3 HARD STOP, no implementation
fix or test adjustment was made after this failure. The rest of the browser
scenario (full UI render, 12-entry UI limit, cold relink) was not reached.
The already-running unittest suite finished with 41 passing tests, including
actual duplicate-source HTTP render/restore/limit and project-ref tests.

## Recovery artifacts (ignored, local only)

work/v53-block2-stopped/ contains implementation.patch, the browser harness,
the failure log and both unittest logs. The patch contains only the six
Block-2 implementation/test files. It is not published or applied.
Do not claim the candidate is verified. A fresh session starts with the
Git log, this file and the baseline unittest suite as required.

## Preserved invariants

- Branch: v5-plan. No merge into editor-workflow.
- main remote: c62b5c5ac2b4de8d7f779476f99ad5aae8464ffe.
- Blueprint tag object: 06d276234ee64dcfa537a44549aba44d23266488.
- Block 1 cursor/visit implementation unchanged.
- Existing uncommitted AGENTS.md naming note predates this task and remains
  untouched/uncommitted.
