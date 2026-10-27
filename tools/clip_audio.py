"""Sample-aligned original audio for video previews and full sequences."""
from pathlib import Path
import math
import wave

from mosh import run

SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2


def prepare_audio(source, metadata, frames, directory, fps):
    if not any(s['codec_type'] == 'audio' for s in metadata['streams']):
        return None
    video = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
    start = float(video.get('start_time', metadata['format'].get('start_time', 0)))
    if not math.isfinite(start):
        raise ValueError('Invalid video start timestamp.')
    samples = frames*SAMPLE_RATE//fps
    path = Path(directory)/'audio.wav'
    # Keep source timestamps through decoding, align to the first video frame,
    # fill late audio with silence, and pad/trim to exactly the video frame count.
    filters = (f'atrim=start={start}:end={start+frames/fps},asetpts=PTS-({start})/TB,'
               f'aresample={SAMPLE_RATE}:async=1:first_pts=0,apad,'
               f'atrim=end_sample={samples},asetpts=N/SR/TB')
    run('ffmpeg', '-v', 'error', '-nostdin', '-y', '-copyts', '-i', source,
        '-map', '0:a:0', '-vn', '-af', filters, '-ac', CHANNELS, '-ar', SAMPLE_RATE,
        '-c:a', 'pcm_s16le', path)
    with wave.open(str(path), 'rb') as audio:
        if audio.getnframes() != samples:
            raise RuntimeError('Prepared audio length does not match video.')
    return str(path)


def assemble_audio(clips, transitions, directory, fps):
    if not any(c.get('audio') for c in clips):
        return None, 0
    if SAMPLE_RATE % fps:
        raise ValueError('Audio requires an integer number of samples per frame.')
    samples_per_frame = SAMPLE_RATE//fps
    destination = Path(directory)/'sequence.wav'
    expected = 0
    with wave.open(str(destination), 'wb') as target:
        target.setnchannels(CHANNELS)
        target.setsampwidth(SAMPLE_WIDTH)
        target.setframerate(SAMPLE_RATE)
        for index, clip in enumerate(clips):
            skip = int(index > 0 and transitions[index-1]['effect'] != 'cut')
            count = (clip['frames']-skip)*samples_per_frame
            expected += count
            if clip.get('audio'):
                with wave.open(clip['audio'], 'rb') as source:
                    if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE):
                        raise RuntimeError('Unexpected audio cache format; re-import the clip.')
                    source.setpos(skip*samples_per_frame)
                    remaining = count
                    while remaining:
                        data = source.readframes(min(16384, remaining))
                        if not data:
                            raise RuntimeError('Incomplete audio cache; re-import the clip.')
                        target.writeframesraw(data)
                        remaining -= len(data)//(CHANNELS*SAMPLE_WIDTH)
            else:
                remaining = count
                while remaining:
                    chunk = min(16384, remaining)
                    target.writeframesraw(bytes(chunk*CHANNELS*SAMPLE_WIDTH))
                    remaining -= chunk
    with wave.open(str(destination), 'rb') as audio:
        if audio.getnframes() != expected:
            raise RuntimeError('Assembled audio sample count mismatch.')
    return str(destination), expected


def encoding_args(audio):
    if not audio:
        return ['-map', '0:v:0', '-an']
    return ['-i', str(audio), '-map', '0:v:0', '-map', '1:a:0',
            '-c:a', 'aac', '-b:a', '192k', '-ar', str(SAMPLE_RATE), '-ac', str(CHANNELS)]
