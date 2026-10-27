# Progressive Melt and Motion Stutter

Two additional compressed-frame scheduling modes, built on the existing genuine
MPEG-4 Part 2 reference manipulation. They reuse unmodified P-VOP payloads after
omitting the incoming I-VOP. They do not use shaders, decoded-frame freezes,
crossfades or FFglitch motion-vector editing.

## Progressive Melt

A repeated P-frame keeps modifying the evolving decoded reference; this is not a
still-image hold. Unlike Frame Melt's constant repetitions and slow donor
progress, Progressive Melt starts each group at its output-timeline position and
reduces repetitions as the effect progresses. The existing repetition slider
controls the initial maximum, from 2 to 12.

At output position `t`, the repetition count is rounded from
`1 + (initial_repeat - 1) * max(0, 1 - t / (0.75 * duration_frames))²`.
Groups are capped to leave the final quarter uninterrupted. Accumulated
distortion is not faded away: decreasing repetitions changes the motion cadence.

## Motion Stutter

Each pulse repeats its first compressed P-VOP during the first half, then uses
consecutive timeline-aligned P-VOPs during its second half. Pulse length is
4–48 frames (about 0.17–2 seconds) and must be shorter than the effect.
The final quarter uses uninterrupted motion, so the pulse does not stop at the
exit. Unlike Motion Loop, this alternates single-frame prediction bursts and
forward motion rather than replaying one movement window throughout.

## Shared behavior and limits

- Both require at least 0.5 seconds and motion_start=0. The source-start control is
  disabled intentionally. Output remains 640×480, 24 fps.
- Continue motion is the default ending. The last effect VOP and following suffix
  are consecutive donor frames, with no new I-VOP. Restore clear image remains
  available as an intentional hard reference reset.
- These schedules skip some donor movement between groups to retain the original
  overall timeline. Group changes may still jump, especially with camera cuts or
  abrupt source motion. No universal smoothness guarantee is made.
- Original audio follows the source timeline; audio itself is not moshed.
- Classic Mosh, Frame Melt, Motion Loop and Loop Release keep their algorithms.
- Video inputs only; image import and Photo Mosh remain deferred.

## Reproduce comparisons (Mac or Linux)

Python 3.9+, FFmpeg and FFprobe. On Apple Silicon: `brew install ffmpeg`.
No additional application dependencies.

```sh
python3 tools/compare_dynamic.py --a samples/clip-a.mp4 --b samples/clip-b.mp4 --duration 2 --repeat 6 --loop-frames 8 --output-dir output/dynamic-effects
```

Use your own input paths as needed. The ignored output directory contains four
full sequence MP4s, raw MPEG-4 streams, evidence JSONs and comparison.mp4:

| Position | Mode |
| --- | --- |
| Top left | Frame Melt |
| Top right | Progressive Melt |
| Bottom left | Motion Loop |
| Bottom right | Motion Stutter |

`during.png` and `exit.png` contain representative frame grids. The comparison
uses original audio from the first render, not four overlapping audio streams.
Do not publish private source videos/audio or these renders without permission.

The common standalone API `effects.process(...)` accepts `progressive-melt` with
`repeat`, and `motion-stutter` with `loop_frames`. The standalone tool ends at the
effect; use sequence rendering to inspect the complete exit:

```sh
python3 tools/effects.py --effect progressive-melt --a samples/clip-a.mp4 --b samples/clip-b.mp4 --duration 2 --repeat 6 --output output/progressive.mp4
python3 tools/effects.py --effect motion-stutter --a samples/clip-a.mp4 --b samples/clip-b.mp4 --duration 2 --loop-frames 8 --output output/stutter.mp4
python3 -m unittest discover -s tests -v
```

Tests exercise actual encoded payload order, initial I-frame omission, unchanged
source hashes, distinct decoded frames, consecutive exit frames, audio sample
counts, full output decode and existing engine regressions. Optional browser test:
`python3 tests/browser_dynamic.py` against a fresh running server; override its
URL with H4_EDITOR_TEST_URL if necessary.
