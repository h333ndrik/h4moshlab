# Original sound in the editor

The editor now includes source audio in single-clip previews, assembled playback
and MP4 export. No extra package, audio upload, or separate audio file is required.
The native player volume/mute controls work normally. Re-import clips after
updating/restarting the server so their new audio caches/previews are prepared.

## Timeline behavior

- Original audio follows the clip order and original timeline, including after
  clips are reordered or removed. Motion-source selection, Melt repetition and
  Loop repetition affect the picture only. They do not repeat/stretch the audio.
- Normal cuts retain the entire normalized clip's audio.
- A mosh boundary removes B's first video frame. At 24fps, the audio likewise
  drops its first 2,000 samples at 48kHz (1/24s), preventing cumulative A/V drift.
- First/last audio samples are aligned to the first source video frame. A source
  track that starts late gets leading silence; early audio is trimmed. Short
  tracks are padded and long ones trimmed to the exact normalized video duration.
- In mixed sequences, clips without sound contribute exactly the required silence.
  If all clips are silent, the output remains video-only.

The first audio track is decoded to a private PCM cache, converted to 48kHz stereo,
then encoded as AAC at 192kbps in MP4. This preserves audio content, not compressed
source bytes or original channel layout. The picture remains 640×480 at 24fps.
No `-shortest` cutoff is used; audio must not drop video frames or leave an extra tail.

## Implementation and verification

`tools/clip_audio.py` aligns and caches PCM audio using FFmpeg, then streams the
clip PCM segments into a sample-exact soundtrack with Python's standard `wave`
module. `sequence.py` uses the same cached sound for proxy playback and final
exports, explicitly maps H.264 video and AAC audio, and validates audio presence
and duration in addition to full output decoding. Video normalization now resets
source timestamps before frame-rate conversion so nonzero video starts are aligned.

Verification JSON includes `audio`, `audio_samples` and `audio_sample_rate`.
Private original sound and PCM caches stay under ignored `work/editor-*`; no real
source audio is added to Git. Existing committed demonstration movies and the
standalone pair-proof CLI are historical/silent; newly rendered editor sequences
carry audio when available.

```sh
python3 -m unittest discover -s tests -v
```

Four audio integration tests cover tone clips at different input sample rates,
a silent clip, reordered sound, exact sample concatenation/frame trimming, AAC
stream format and timing, actual exported tone frequencies/silence, delayed and
short audio, and video that starts later than the container audio. Existing codec
regressions continue to run. The browser test checks actual audio decoding and
AAC export with the two supplied MOVs plus a silent synthetic clip. Mac/Safari
execution is not independently verified in this cloud environment.

## Possible future sound effects

Audio effects are not implemented yet. A synchronized stutter/short loop would be
an accessible first option; granular freeze or spectral smearing would require
more DSP work. These are audio-processing effects, not video-style I/P-frame
manipulation. Controlled AAC/MP3 bitstream corruption would be a separate,
experimental codec project with less predictable musical results.
