# Gentler repetition movement

Frame Melt, Progressive Melt and Motion Stutter now offer **Repetition movement**:
**Gentler · smaller motion jumps** or **Original cadence** in the existing
transition dialog. Newly selecting one of these modes enables Gentler. Saved
settings without the new parameter and direct API calls retain original behavior.
Classic Mosh, Motion Loop and Loop Release keep their existing algorithms.

## What changes

Previously, repeated predictions could be followed by a donor index far ahead of
the last one. For example, in the tested two-second Frame Melt with six repeats,
the effect used donor 8 immediately before the suffix started at 49: a 41-frame
jump. Gentler distributes catch-up before the exit and bounds forward steps to
at most two donor frames. The final quarter uses consecutive predictions aligned
with the incoming timeline, so the following suffix has no donor-position jump.

The operation still uses original compressed MPEG-4 Part 2 P-VOP payloads.
No interpolation, crossfade, shader or decoded-frame freeze is used. Repeated
P-frames continue modifying the evolving reference. There is no new I-frame when
Continue motion is selected. Restore clear image still deliberately resets it.

## Exact scheduling

For a plan with N predictions, the uninterrupted tail begins at
`R = N - max(1, floor(N/4))`. In zero-based output slot i before R, choose the
original requested donor position clamped between:

- lower bound: `max(previous, 0, R - 2*(R-i))`
- upper bound: `previous + 2`

At and after R, use donor position i. The first normalized P-VOP corresponds to
zero-based position 0. This preserves repeats early where feasible, limits
per-step movement and rejoins the original donor timeline before the effect ends.

This is a change in motion cadence, not a continuous reduction of accumulated
codec distortion. At most one donor frame can still be skipped per output step.
Motion can speed up while catching up, some early repeat groups are shortened,
and existing corruption or source cuts can still produce jumps. Smaller donor
steps are a structural improvement, not a perceptual smoothness guarantee.

## Audio, duration and limits

- Full sequence frame counts, clip boundaries and original audio are unchanged.
  PCM audio hashes match between original and Gentler renders on tested sources.
- The selected source movement can still differ from the source audio during the
  effect, as with all video-moshing modes. This does not guarantee lip sync of
  transformed imagery. It adds no drift to later clip boundaries.
- Gentler requires motion_start=0 and sufficient source frames for the full effect
  duration. The source-start control is intentionally disabled in that setting.
  Original Frame Melt retains its independent movement-source selection.
- Existing repeat/pulse controls remain functional, but catch-up can shorten
  requested repetitions. Tiny transitions may have little room for repetition.
- No new runtime dependencies; original files remain unchanged.

## Reproduce

Python 3.9+, FFmpeg/FFprobe. On Apple Silicon: `brew install ffmpeg`.

```sh
python3 tools/compare_smooth.py --a samples/clip-a.mp4 --b samples/clip-b.mp4 --effect frame-melt --duration 2 --repeat 6 --output-dir output/smooth-comparison
python3 tools/effects.py --effect frame-melt --a samples/clip-a.mp4 --b samples/clip-b.mp4 --duration 2 --repeat 6 --smooth --output output/smooth-melt.mp4
python3 -m unittest discover -s tests -v
```

The sequence comparison has original cadence on the left and Gentler on the
right. It includes the full suffix, original audio if present, raw m4v evidence,
JSON donor indices/hashes, and four exit-frame pairs. --effect also supports
progressive-melt and motion-stutter. Use --loop-frames for the latter.

The common effect and sequence APIs accept boolean `smooth` (default false).
The standalone pair API ends at the effect; use the full sequence comparison to
inspect its exit. Unsupported effect/parameter combinations are rejected by the
pair API. Private comparison footage/audio stays ignored and is not published.
