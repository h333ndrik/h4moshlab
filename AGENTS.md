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
