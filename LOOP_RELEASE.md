# Loop Release — codec-level loop exit

Loop Release is a new variation on Motion Loop, using the existing MPEG-4 Part 2
prediction engine. Classic Mosh, Frame Melt and Motion Loop keep their algorithms.
In the transition dialog select **Loop Release**, then **Continue motion**.
The existing loop-length control chooses the maximum repeated group size.

The first half of the transition has room for a group repeated three times and,
if space permits, another group repeated twice. Each block starts at its current
output-timeline position. The remaining half or more uses consecutive source
P-VOPs and ends exactly at the donor index matching the original timeline. The
rest of the incoming clip therefore continues with the next consecutive P-VOP.
No new I-VOP, frame blend, crossfade, shader or motion-vector editing is used.
Repeated P-VOP payloads act on evolving decoded references, not frozen pictures.

This deliberately relocates motion discontinuities to earlier block changes.
It does not continuously fade distortion strength, guarantee a smooth result on
all footage, or implement independent FFglitch motion transfer. Donor frames can
be skipped between blocks. It needs at least 0.5 seconds and motion_start=0 for
this timeline-aligned exit. Original audio follows the original timeline.
Selecting Restore clear image still deliberately inserts a reference reset.

## Reproduce a full comparison

Python 3.9+, FFmpeg and FFprobe; no additional runtime packages. On Apple Silicon:

```sh
brew install ffmpeg
python3 tools/compare_release.py --a samples/clip-a.mp4 --b samples/clip-b.mp4 --output-dir output/loop-release --duration 2.5 --loop-frames 8
```

Use your own source paths as needed. Outputs (ignored by Git):

- `comparison.mp4`: left Motion Loop, right Loop Release, same original audio.
- `exit-frames.png`: four frame pairs around the effect exit.
- `comparison.json`: donor indices, original hashes, full-decode results and
  exit-frame RGB difference. That metric is diagnostic, not a perceptual score.
- Each mode directory also contains `sequence.mp4` and raw `sequence.m4v`.

The standalone API also accepts `loop-release` with `loop_frames`, but ends after
the effect. Use the sequence renderer/comparison above to inspect its exit.

## Validation

26 integration tests passed, including exact VOP payload sequence, no extra I-VOP
in flow mode, final consecutive donor indices, original source preservation,
full decoding, and existing audio/Classic/Loop/Melt regressions. Synthetic exit
RGB MAE was 3.377 for Motion Loop versus 1.885 for Loop Release (8-bit values,
these specific sources only). Representative frames were visually inspected.
Real source comparisons are local artifacts and must not be published without
permission, since they include the user's original audio.
