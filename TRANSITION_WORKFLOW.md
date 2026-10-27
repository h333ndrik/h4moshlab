# Reset Pulse and focused transition controls

The existing light layout, H4 cursor, original audio and full-sequence actions
remain. New controls live in the transition dialog and its expandable sections.
No image import, hosting or additional runtime dependencies were added.

## Reset Pulse (video only)

At each reset interval, copy the incoming video's **first I-VOP** into the
compressed sequence. This clears the reference to the incoming first frame.
Repeat subsequent P-VOPs to distort that reference again. This deliberately
returns to the same first frame, not a different clear frame from the current
source time. Original audio continues along the existing sequence timeline.

The first incoming I-VOP is initially omitted, as in Classic Mosh. For zero-based
output offset j, let k=(j+1) modulo interval. If k=0, select donor VOP 0 (I).
Otherwise select donor VOP `1 + floor((k-1)/repeat)` (P). The raw payloads are
unchanged. The report records actual reference_reset_offsets and donor hashes.
Delivery timestamps are regenerated at a fixed 24fps because repeated I-VOPs
carry their original codec timestamps.

Controls: effect duration (minimum .5s, maximum 6s/source length), reset interval
4–48 frames, shorter than the effect, and repetitions 2–12. Motion start must be
zero. This is intentionally a hard rhythmic effect; Gentler is not exposed for
Reset Pulse. The default ending continues prediction; a final explicit clear
reference reset remains available through the existing ending selector.

```sh
python3 tools/effects.py --effect reset-pulse --a samples/clip-a.mp4 --b samples/clip-b.mp4 --duration 2 --loop-frames 12 --repeat 4 --output output/reset-pulse.mp4
```

This pair tool ends after the effect and is silent, like the existing pair API.
The editor's complete sequence and short previews include original audio.

## Short transition previews

`Preview this transition` now renders only .75s before, the effect, and up to .75s
after the selected boundary. If the full movie is already cached, it reuses that
movie and seeks to the boundary instead. Cuts have zero effect duration.

API: existing POST /api/jobs with clips/transitions plus optional integer
`preview_boundary`. Without this field, processing/export is unchanged. The
result includes preview start/end/source frame positions and its local boundary.
Only the preceding clips and selected incoming clip are needed. Earlier codec
references are retained: the prefix must still be decoded to obtain the correct
image. Only the selected window is H264-encoded; this is not a claim that all
processing is independent of earlier clips or always faster in wall time.

The original source-aligned PCM is trimmed at exact 2000-sample-per-video-frame
boundaries. Validation covers audio duration, expected tones before/after the
boundary and correspondence with the full render. Video timestamps are fixed to
24fps. In the tested real pair, 84 frames were encoded for the preview instead
of 159 for the complete movie.

Short previews have separate cache entries (up to 12 in the browser). They never
replace the full movie's saved job or export resource. Assemble preview and
Export MP4 still process/reuse the entire sequence. Browser refresh restores the
full movie when available; it does not restore temporary A/B preview selection.

## Adjustable release

Gentler Frame Melt, Progressive Melt and Motion Stutter expose a Release slider:
one frame through half the effect duration, default one quarter. This reserves
**at least** that ending for consecutive donor frames. Some original schedules
already contain a longer consecutive tail. Longer release can reduce the time
available for repetitions. Existing duration/audio alignment remains unchanged.

The optional API parameter is `release_duration` in seconds, rounded to 24fps.
It requires `smooth=true` in the common pair API; sequence settings ignore stale
release fields when Gentler is off or the effect does not support it. Omitting
it preserves the previous fixed-quarter Gentler behavior.

## Original/Gentler comparison

Expand Compare movement under the Gentler/release controls and select Preview
original or Preview gentler. Each produces the same short transition window with
one cadence changed; selected transition settings are not modified. Cached
versions can be revisited without another processing job. This compares motion
cadence, not an unaffected cut against a moshed sequence.

## Motion Loop source marks

Under Choose motion, scrub the source video and use Set start here / Set end
here. These set the existing motion_start/loop_frames parameters: no hidden new
algorithm. The source interval is quantized to whole 24fps frames, 2–48 frames
(up to 2s), and must fit the source and be shorter than the effect. The existing
start slider and loop-length control remain available.

## Tests and limitations

Tests exercise raw decoded reset frames equal to the clear source reference,
non-identical subsequent decoded frames from repeated P payloads, exact donor
payloads, release bounds, preview context after a prior Mosh, shortened encoding,
source/audio integrity and tone order, complete decoding, browser A/B caching,
source marks and full export. Use:

```sh
python3 -m unittest discover -s tests -v
H4_EDITOR_TEST_URL=http://127.0.0.1:8765 python3 tests/browser_preview_pulse.py
```

The browser test needs a fresh server and optional development-only Playwright
and Chromium. Runtime remains Python 3.9+, FFmpeg/FFprobe, no new dependencies.
On Apple Silicon: `brew install ffmpeg`, then run the existing server command.

Reference corruption can still jump; Reset Pulse does so intentionally. Decoder
work for a long prefix may dominate a short preview. All private source videos,
audio and render artifacts remain ignored and must not be published implicitly.

## Sound on/off

A small checkbox beside the player switches original sound for both playback and
processing. Off mutes source previews and produces short/full MP4s without an
audio stream. On includes source audio when available. The choice survives a
browser-session reload, invalidates an old full export and is part of short
preview cache keys. No audio-moshing algorithm is implied. API: `audio` boolean
on POST /api/jobs (default true), or include_audio on sequence.render.
