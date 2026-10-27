# Minimal local editor

The existing Classic Mosh and Frame Melt engine now powers one complete local
workflow: import → arrange → configure boundaries → assemble → preview → download.
The repository previously had no frontend or h4ngelic CSS. This adds a deliberately
simple interface with a subtle neutral gradient; exact h4ngelic styling is deferred
as requested. The separate h4ngelic website has not been changed.

## Run on an Apple Silicon Mac

Requires Python 3.10+ and FFmpeg/FFprobe with `mpeg4` and `libx264`. No npm build,
pip packages, GPU, FFglitch or cloud credentials are required to run the editor.
With native Homebrew installed:

```sh
brew install ffmpeg python
# For a fresh local checkout; the existing engine branches remain intact:
git clone --branch editor-workflow https://github.com/h333ndrik/h4moshlab.git h4moshlab-editor
cd h4moshlab-editor
python3 tools/server.py --port 8765
```

In a second **local Mac** terminal:

```sh
open http://127.0.0.1:8765
```

This is a local application, not a hosted website or a cloud preview link. Keep
the first terminal open. Ctrl+C stops the server and removes its temporary session
files. On Linux use the same Python command and open the local address in a browser.
The cloud run was validated on Linux/Chromium; Mac/Safari has not been tested.

## Workflow

1. Import up to 12 videos (each at most 128 MiB and 120 seconds). Imports are
   processed sequentially into browser-playable H.264 previews; HEVC/MOV originals
   do not need native browser codec support. Actual upload progress is followed by
   an indeterminate preparation phase.
2. Select a clip to preview it. Drag cards to reorder or use the keyboard-accessible
   arrow buttons. Remove a clip with ×; its temporary server files are released.
3. Select a connector between clips. Choose Cut, Classic Mosh, Frame Melt or Motion Loop.
   Duration is quantized to 1/24 second, with numeric feedback, up to six seconds
   and the incoming clip's available P-frame count. Melt exposes only the verified
   repetition count, 2–12. Motion Loop repeats a selectable short prediction group.
   Optional Choose motion controls let you see and select the donor movement.
   Connector labels use separate name/time lines and fit their contents, including
   at 200% zoom; existing fonts and background are retained.
   [Details and comparison](MOTION_LOOP.md). Cut hides effect-only controls. No shader or fake mode.
4. Assemble the preview. The server creates and fully decodes an actual MP4 before
   declaring it ready. Status shows assembly stages, encoding progress from FFmpeg's
   output timestamps, and final decode validation. Playback and seeking use native
   video controls and HTTP byte ranges. Active cards follow assembled playback.
5. Preview a transition from its dialog to play the corresponding region of that
   same assembled film. An unchanged sequence reuses the existing render. Clip/order
   or transition changes invalidate it and hide the stale download link.
6. Export MP4 renders the current sequence if necessary, then downloads exactly the
   same bytes as its assembled preview. Failures show an error and reenable retry.

Timeline order/settings survive page refresh in this browser tab. Imported clips
and a running/completed render reconnect to the same live server session. This is
not permanent project saving: restarting the server discards that session. The
browser does not create persistent object URLs or keep removed video elements.

## Real sequence processing

`tools/sequence.py` reuses the shared normalization and P-frame operation from
`mosh.py`/`effects.py`. The original CLI calls retain their original six-second
behavior and regression coverage. The editor normalizes **entire clips**, up to
120 seconds, instead of silently taking only six seconds.

For each effect boundary, the incoming I-VOP is omitted and the selected B P-VOP
payloads are appended unchanged to the preceding clip's final reference. Classic
uses sequential P-VOPs; Melt repeats each P-VOP against the evolving reference.
At the configured effect duration, the remaining incoming clip is re-encoded with
a fresh I-frame to restore its normal image. Passthrough frame synchronization
avoids inserting a duplicate frame during this restoration. Normal cuts retain
all source VOPs and reset with the incoming I-VOP. One consistent normalization
configuration is used throughout; intermediate internal timestamps are replaced
by the explicit 24fps decoding cadence.

Effects occupy the beginning of an incoming clip; they are not overlap dissolves.
Each mosh boundary drops one source frame (B's initial I-frame), as in Phase 1.
The rest of the clip remains; Melt may visibly jump to normal B when its window
ends because it traverses fewer donor frames. A normal cut drops no frames.
Outputs are silent 640×480/24fps with preserved aspect ratio. Audio and
selectable higher-resolution exports are not implemented. This limitation is displayed in the interface.

Private originals, normalized clips, reference-restoration streams, render logs,
VOP indices/payload hashes and verification JSON live under ignored
`work/editor-*/`. A render snapshots the ordered clip list/settings and blocks
concurrent mutation. Inputs are hash-checked after rendering. Temporary folders are
cleaned on graceful shutdown. A forced process kill can leave ignored directories;
remove only abandoned `work/editor-*` folders after the server has stopped.

The stdlib HTTP server binds loopback only, validates local Host/Origin, rejects
oversized imports, uses generated file IDs, and exposes only known media/static
routes. It is intended for a single local user, not public hosting. There is no
account system, job cancellation or permanent project database.

## Checks

```sh
python3 -m unittest discover -s tests -v
node --check web/app.js  # Optional JS syntax check when Node is available.
```

Sixteen integration tests passed: all six original effect regressions plus full-clip
sequencing, multiple real boundaries, normal-reference restoration, cut reordering,
one-clip exports and invalid requests. The >6s fixture confirms no editor truncation. Missing-tool tests check startup
diagnostics, actionable import errors, cleanup and retry after a failed import.
The sequence test compares actual compressed P-VOP payloads and expected I-frame
locations, checks exact output frame counts, and fully decodes the rendered video.

Optional browser test (development only; requires Playwright and Chromium): start
a **fresh** test server on port 8765, then supply three distinct video filenames:

```sh
python3 tests/browser_smoke.py /path/a.mov /path/b.mov /path/c.mp4
```

The browser test imports real files and covers reordering, contextual sliders,
settings/page reload, assembled playback, seeking, transition preview, byte-identical
preview/download, invalidation, injected server-error recovery, render reconnection,
removal, HTTP byte ranges and local-origin rejection. It checks original upload
hashes, JavaScript errors, and overflow at 1200px/390px widths. Screenshots and the
actual downloaded MP4 are kept in ignored `work/browser-smoke/`.

Validated with the two user-provided MOVs and one synthetic clip: 12.583333-second
three-clip render with two effect boundaries, zero JavaScript errors, complete download decode successful.

## Changed files and next step

- `web/index.html`, `web/style.css`, `web/app.js`: simple responsive editor.
- `tools/server.py`: local upload, media-range, background-job and download API.
- `tools/sequence.py`: full-clip assembly, actual effect boundaries and restoration.
- `tools/mosh.py`, `tools/effects.py`: small shared-helper extensions; existing CLI preserved.
- `tests/test_sequence.py`, `tests/browser_smoke.py`: sequence and real-browser coverage.

Next recommended task: run this flow on the target Apple Silicon Mac/Safari with
real footage, then set the required output resolution/audio behavior before applying
the final h4ngelic design. Motion Loop is verified; Motion Transfer remains unavailable for the reasons in
[PHASE2.md](PHASE2.md); it is not exposed as a working effect.

## Import troubleshooting (including iPhone MOV)

MOV files are accepted and transcoded on the server. An import failure does not
by itself mean MOV is unsupported. In the same local terminal environment, check:

```sh
ffmpeg -version
ffprobe -version
```

If either is missing, install Homebrew's FFmpeg package (`brew install ffmpeg`),
which includes both tools. If Homebrew is installed at `/opt/homebrew` but its
commands are not on PATH, initialize it with `eval "$(/opt/homebrew/bin/brew shellenv)"`.
Restart the Python server from that initialized terminal and retry the import.
The server now checks both tools before starting, rather than accepting an upload
and displaying an incorrect format hint. Runtime missing-tool errors also name
the install command. Other processing failures write their details to the server
terminal; copy that error for diagnosis instead of renaming or modifying originals.
