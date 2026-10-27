# Simple editing tools after Blueprint 1

The light layout, H4 cursor, one Export MP4 action and 640x480/24fps processing
remain. The immutable tag h4-moshlab-blueprint-1 is the previous restore point.

## Undo and redo

Use the two arrows beside Project in the Sequence row, or Command/Ctrl Z and
Command/Ctrl Shift Z (Ctrl Y also works). Reorder, imports, removal, clip looks,
transition edits, presets, tempo, sound and opening a project can be undone.
A slider gesture is one action. Playback and source selection do not create
history actions. Native text/number fields retain their own text-edit shortcuts.

History retains up to 40 actions in the current tab. Reloading the page restores
the sequence settings but clears undo history. Removed clips are retained in the
temporary server session so undo can recover them; they are deleted when the
server session ends. Active sequences still have at most 12 clips, with at most
24 uploaded source files retained per session including undo media. At that limit,
save the project, restart and relink its originals to free the temporary cache.
This is a local/same-Wi-Fi editor, not an isolated multi-user hosted service.

## Starting points

Each real effect has Subtle, Dragging and Intense starting points in the existing
transition dialog. They set actual duration, repetition/group length and movement
settings; they are not extra algorithms. All 21 combinations are rendered and
fully decoded in tests. Results depend on the input footage; these names are not
a claim that pixel distortion increases monotonically on every source.

Settings fit the incoming clip; unsupported effects on very short clips remain
disabled. Manual changes switch the selector back to Custom. Presets and their
exact parameters are saved with projects and can be undone.

## Match music tempo

Expand Match music tempo for Motion Loop, Motion Stutter or Reset Pulse. Enter
40–240 BPM, choose a beat interval, then Apply tempo. If needed, effect duration
is extended enough to fit a cycle. Unrepresentable/too-long intervals produce a
message instead of silently clamping the tempo. The source clip and the 2-second
maximum movement interval still constrain the choice.

Every beat boundary is rounded separately to the 24fps grid. For example, 137 BPM
uses alternating frame intervals rather than repeating a rounded 11-frame period
and accumulating drift. The engine validates tempo metadata, reports actual donor
indices/reset offsets and retains this timing through export. The visible loop
length is the nominal rounded interval; adjacent musical cycles may differ by
one frame.

Timing starts with the effect. This is manual cadence matching, not automatic
music analysis, detection of the first downbeat, global beat-grid alignment,
audio time stretching or a music-file importer. Video-source audio continues
unchanged when Sound on is selected. Motion Stutter with Gentler intentionally
releases its rhythm at the effect ending. Loop Release has changing group lengths,
so it intentionally does not expose a fake fixed-BPM option.

## Save and reopen a project

Project → Save project downloads a small .h4mosh JSON file with sequence order,
source names/SHA256 hashes, clip looks, transitions, presets, tempo and sound.
**It does not contain the video files. Keep your originals.**

Project → Open project restores immediately if the originals are already in the
session. Otherwise a small dialog asks you to select them. Original files are
verified by hash; renamed files can be relinked, changed files cannot silently
substitute for the originals. Missing/wrong files leave the current edit intact.
You can open on another Mac with the original media and the same engine version.

Project input is size limited, schema checked, and its transition settings are
validated before replacing the sequence. A project file cannot execute code or
select arbitrary server file paths. Temporary output/job URLs and session tokens
are not written to the project file. Project loading itself is one undo action.

## Clip appearance

Each clip card has a compact selector:

- Original
- Black & white
- B&W negative
- Color negative

These are ordinary FFmpeg image-processing filters applied to temporary working
copies **before** genuine codec datamoshing. They are not additional datamoshing
modes. Frame count, duration and original audio remain unchanged. B&W negative
inverts video luma while keeping neutral chroma; Color negative inverts RGB.
Black padding stays black. Looks apply to thumbnails, source preview, short
transition preview and full export, and are included in undo/projects. Original
files are never modified. Prepared variants are cached per source/look during
the session; changing a look invalidates old complete renders and uses separate
transition-preview cache entries.

## Dependencies and verification

No new runtime dependencies: Python 3.9+, FFmpeg and FFprobe. On Apple Silicon,
`brew install ffmpeg`, then use the documented existing server command.

```sh
python3 -m unittest discover -s tests -v
node tests/editor_tools_test.js
```

Optional development browser checks require Playwright/Chromium. Start two fresh
servers for the project restart/relink scenario:

```sh
python3 tools/server.py --port 8801
# In a second terminal:
python3 tools/server.py --port 8802
# In a third terminal:
H4_EDITOR_TEST_URL=http://127.0.0.1:8801 H4_EDITOR_COLD_URL=http://127.0.0.1:8802 python3 tests/browser_editor_workflow.py
```

The browser test accepts two video paths as positional arguments and checks real
imports, history, BPM/preset rendering, grade undo, project download, original
relink on the second server, complete export and narrow layout. Integration tests
also verify all 21 presets, per-beat rounding drift, grayscale/inverted pixels,
unchanged source/audio hashes and archive/restore validation. Private source
videos, saved test projects and render artifacts remain ignored.
