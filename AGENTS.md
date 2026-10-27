# Project preferences to carry forward

## Future design work: branded H4 cursor

When planning the next UI/design refinement, proactively remind the user of this
requested feature. The user has now requested implementation and supplied the original artwork.

- Use the branded H4 mouse cursor.
- At rest, rotate it 25 degrees to the left (-25deg).
- When hovering over an enabled clickable element, rotate it to the upright position (0deg).
- The angle change signals that the element can be clicked. Do not invent the
  cursor artwork; use the user's H4 cursor asset when implementing this later.

## Current scope

Keep imports video-only. Photo Mosh and image import are deferred at the user's request; do not add them during audio/video work.

## Approved layout baseline

The user explicitly asked to remember the current layout. Preserve it when adding
features; redesign only when the user requests it. Baseline: commit 5580d7d on
editor-workflow. The authoritative files are web/index.html and web/style.css;
demo/editor/desktop.png is the accompanying visual reference.

- Minimal centered page, current Arial/Helvetica sans-serif typography and subtle
  light-gray background gradient. Keep the current fonts and background.
- Header text is exactly "h4 mosh lab", lowercase, with no "/ editor" or tagline.
  Keep the import control at the top right.
- Large preview above a compact horizontal clip timeline. Keep active-clip
  highlighting, thumbnails, reorder arrows and removal controls.
- Transition connectors fit their contents: effect name and duration on separate
  lines, with no overflowing text, including when zoomed.
- Keep contextual transition settings in the existing dialog, with advanced
  motion-source settings expandable rather than permanently cluttering the page.
- Keep "Assemble preview" and "Export MP4" as the main actions. Do not restore the
  duplicate "Download assembled MP4" link or add separate full-sequence/clip tabs.
- Preserve the existing responsive spacing and horizontally scrolling timeline.
- The original H4 cursor is implemented separately in web/cursor.js and
  web/h4-cursor.svg; preserve its small monochrome form and smooth -25/0 rotation.

## Platform direction

The user prefers a mobile web version rather than a native iOS/App Store app.
Preserve the approved visual layout while improving touch/browser usability.
Do not start native iOS development or App Store enrollment without a new request.

Start with iPhone access on the same Wi-Fi as the Mac. An Internet-hosted link
without a running Mac is a long-term goal, not the current deployment scope.

## Current priority and cursor refinement

Prioritize effect improvements and new video-only codec effects before mobile work.
After effect work, implement the original h4ngelic cursor if its asset is available:
black and white, slightly smaller, resting at -25 degrees, smoothly rotating to
0 degrees over enabled clickable controls. Other chat history is unavailable;
ask for the original asset if it cannot be found instead of inventing its shape.

Cursor artwork extracted from the user-supplied h4ngelic-preview (5).html.
Use a 22x33px display size, black fill/white outline. Native pointer remains on
touch devices and video controls; honor reduced-motion preferences.

## Browser tab icon

Use the clean bold lowercase h4 wordmark for the favicon (web/favicon.svg and
32px PNG fallback), dark text on the existing light background. The tab icon is
separate from the ornamental H4 mouse cursor. Keep the approved page layout.

## Effect development priority

Website linking/hosting and mobile remain deferred; focus on verified video
effects. Progressive Melt and Motion Stutter use compressed P-VOP scheduling,
not new motion-vector editing algorithms. See DYNAMIC_EFFECTS.md. Keep honest
limits: minimum 0.5 seconds, motion_start=0, original audio unchanged, and
block-boundary jumps may persist despite a consecutive prediction tail.

Browser tab title: exactly `mosh lab` in lowercase, without h4 (already in
the favicon). The page heading stays `h4 mosh lab`.

Gentler repetition movement is implemented for Frame Melt, Progressive Melt and
Motion Stutter. See SMOOTH_REPETITIONS.md: boolean smooth API parameter, donor
advances bounded to two and final quarter consecutive, unchanged duration/audio.
Keep Original cadence selectable; do not promise universally smooth distortion.

## Current design experiment: dark version

The user explicitly requested a negative/dark version after the light baseline.
Current experiment: near-black background with a subtle neutral gradient,
off-white type, gray video well, charcoal cards/dialog and light primary export.
Keep existing typography, dimensions, structure, cursor and features. This is
a requested visual experiment; do not assume final user approval of this palette.
The prior light layout remains available in Git before this experiment.

## Current approved palette: light again

The user reverted the dark experiment. Use the original white/light background
with its subtle gray gradient, dark text and original light cards/settings.
Keep all effects, cursor angles (-25/0), favicon and layout. The dark screenshot
is historical, not the current design reference.

## Simple transition workflow

Reset Pulse uses the first incoming I-VOP periodically, followed by repeated
P-VOPs; it is a video effect with intentional clear flashes, not a smooth mode.
Keep short previews separate from cached complete movies/exports. Preserve codec
context from earlier transitions. Release is an advanced Gentler control and
Original/Gentler comparison stays expandable. Motion Loop source marks map to
existing start/length parameters. See TRANSITION_WORKFLOW.md.

Sound on/off is a small master checkbox beside the player: original audio in
preview AND export, default on, session-persisted. Off means no exported audio
stream. Keep original media unchanged and do not label this audio moshing.

## Export simplicity and future priorities

The user wants one simple export button with the best practical output quality,
not a quality selector or low/medium/high presets. Preserve the explicitly chosen
640x480 processing resolution unless the user requests a resolution change.
Do not call current lossy delivery lossless or maximum source resolution.
Undo/redo, saved projects, tested effect presets and BPM alignment interest the
user; start with undo/redo and effect presets when implementing the next phase.
These are ideas/priorities, not yet implemented capabilities.

## Permanent save point: h4 moshlab blueprint 1

The user named the current website/application state `h4 moshlab blueprint 1`.
Preserve the immutable Git tag `h4-moshlab-blueprint-1`; never move or overwrite it.
See blueprints/blueprint-1.md for included features, restore instructions and
limits (no private footage or temporary editing sessions in Git). Future changes
continue separately so the user can return to this exact baseline.

BPM alignment to music is now a desired next feature, especially for pulse,
stutter and loop timing. It is not implemented yet. Keep the UI simple and do not
claim automatic beat detection or music synchronization before it is built/tested.

## Current implementation beyond Blueprint 1

Undo/redo, three tested starting points per effect, lightweight .h4mosh project
files, manual BPM timing and per-video looks are implemented; see EDITOR_TOOLS.md.
Keep the UI compact: two history arrows + Project menu; presets in the existing
dialog; BPM expandable for Motion Loop/Stutter/Reset Pulse only. Beat boundaries
are rounded individually to 24fps to avoid accumulating interval-rounding drift.
Do not claim automatic beat detection, absolute downbeat alignment or music import.
Projects store edit decisions and source hashes, not embedded originals. Removed
media is retained locally for undo until session shutdown (24 sources total,
12 active, 40 undo actions per tab); never publish private test projects/media.
Per-clip Original/B&W/B&W-negative/Color-negative are preprocessing filters, not
codec mosh modes. Preserve source files, audio, duration and Blueprint 1 tag.
