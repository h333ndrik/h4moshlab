# h4 moshlab blueprint 1

Saved on 2026-10-27 at the user's request, before BPM alignment or further
experimentation. Permanent Git tag: `h4-moshlab-blueprint-1`.
Application code baseline: `a4f2186` (this snapshot adds only documentation).

## Restore without overwriting your current project

Download and unpack this exact version into a separate folder:

https://github.com/h333ndrik/h4moshlab/archive/refs/tags/h4-moshlab-blueprint-1.zip

Open Terminal in that folder, then run on your Apple Silicon Mac:

```sh
eval "$(/opt/homebrew/bin/brew shellenv)"
python3 tools/server.py --port 8788
```

Open http://127.0.0.1:8788 on that Mac. If occupied, choose another port in both
the command and URL. Keep Terminal open; stop with Control+C.

For Git users, create a separate restoration branch (commit or stash your local
changes before switching):

```sh
git fetch origin --tags
git switch -c restore-blueprint-1 h4-moshlab-blueprint-1
```

Do not move this tag, force-push it or overwrite current work to restore it.
Future changes stay on editor-workflow; the tag remains this exact snapshot.

## Included state

- Original light background and subtle gray gradient; compact existing layout.
- Page heading `h4 mosh lab`, browser tab `mosh lab`, clean h4 favicon.
- Original monochrome H4 cursor, 22x33px, -25 degrees at rest / 0 on clickable
  controls, smooth rotation; native video/touch fallbacks.
- Multiple clips, reorder/remove, contextual transition settings, assembled
  playback, short transition previews, and one MP4 export button.
- 640x480 at 24fps. Genuine MPEG-4 Part 2 reference/prediction processing and H264
  MP4 delivery. No export quality selector.
- Classic Mosh, Frame Melt, Motion Loop, Loop Release, Progressive Melt,
  Motion Stutter and Reset Pulse; ordinary Cut separately.
- Optional Gentler movement, adjustable minimum release, Original/Gentler preview
  comparison, Motion Loop source start/end marks.
- Original sound on/off for playback and export; choice remembered per session.
- Optional paired access from a phone on the same trusted Wi-Fi with the Mac
  running. This is not a hosted public service.

BPM alignment is the next desired direction, especially matching Reset Pulse,
Motion Stutter and loop timing to music. It is **not implemented in this snapshot**.
Undo/redo, named effect presets and permanent saved projects are also not yet
implemented. Preserve the simple interface when developing those features.

## Validation and snapshot limits

The application baseline passed 35 integration tests and browser checks for
processing/export, short previews, comparisons, source marks and sound toggling.
This save-point operation changes no application code.

This snapshot preserves source code, documentation and tracked reference assets.
It does not include uploaded originals, private renders, temporary server media,
browser session data, installed dependencies or a running server. It is not a
saved editing project and cannot recover an expired temporary session.
