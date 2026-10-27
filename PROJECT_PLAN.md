# Implementation plan — completed

Authorized scope: continue beyond immutable h4-moshlab-blueprint-1 with the
simplest practical UX. Preserve light layout, one export button and 640x480.

- [x] Undo/redo for edits, reorder, imports, removals and sound; coalesced sliders.
- [x] Three validated presets per existing effect (21 real renders).
- [x] Save/load lightweight project files with source hashes; relink originals.
- [x] Manual BPM for Motion Loop/Stutter/Reset Pulse, rounded per beat at 24fps.
- [x] User-added per-video Original/B&W/B&W-negative/Color-negative looks.
- [x] Integration/browser checks, documentation and visual/touch review.
- [ ] Commit/publish editor-workflow; verify remote and unchanged Blueprint tag.

Project files store edit decisions, not original videos. Removed media is retained
only temporarily for undo. No automatic beat detection, native app, public hosting,
image import, quality selector or unrelated redesign belongs to this plan.
