# Project preferences to carry forward

## Future design work: branded H4 cursor

When planning the next UI/design refinement, proactively remind the user of this
requested feature. Keep it deferred until that design work is requested.

- Use the branded H4 mouse cursor.
- At rest, rotate it approximately 15 degrees to the left (-15deg).
- When hovering over an enabled clickable element, rotate it approximately
  15 degrees to the right (+15deg).
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
- The custom H4 cursor above remains a future enhancement, not part of the current
  implemented layout. Proactively mention it when the next design pass is planned.
