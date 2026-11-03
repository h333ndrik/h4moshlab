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


def assemble_audio(clips, transitions, directory, fps, donor_indices=None):
    if not any(c.get('audio') for c in clips):
        return None, 0
    if SAMPLE_RATE % fps:
        raise ValueError('Audio requires an integer number of samples per frame.')
    donor_indices = [None for _ in transitions] if donor_indices is None else donor_indices
    if not isinstance(donor_indices,list) or len(donor_indices)!=len(transitions):
        raise ValueError('One audio donor list is needed per transition.')
    samples_per_frame = SAMPLE_RATE//fps
    frame_bytes = samples_per_frame*CHANNELS*SAMPLE_WIDTH
    destination = Path(directory)/'sequence.wav'
    expected = 0
    with wave.open(str(destination), 'wb') as target:
        target.setnchannels(CHANNELS)
        target.setsampwidth(SAMPLE_WIDTH)
        target.setframerate(SAMPLE_RATE)
        for index, clip in enumerate(clips):
            transition = transitions[index-1] if index else None
            skip = int(index > 0 and transition['effect'] != 'cut')
            count = (clip['frames']-skip)*samples_per_frame
            expected += count
            if clip.get('audio'):
                with wave.open(clip['audio'], 'rb') as source:
                    if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE):
                        raise RuntimeError('Unexpected audio cache format; re-import the clip.')
                    follow = bool(transition and transition.get('audio_follow')) and skip
                    if follow:
                        donors = donor_indices[index-1]
                        if not isinstance(donors,list) or len(donors)!=round(transition['duration']*fps):
                            raise RuntimeError('Audio donor indices do not match the transition.')
                        if len(donors) >= clip['frames'] or any(type(i) is not int or not 0 <= i < clip['frames'] for i in donors):
                            raise RuntimeError('Audio donor index is outside the incoming clip.')
                        for donor in donors:
                            source.setpos(donor*samples_per_frame)
                            data = source.readframes(samples_per_frame)
                            if len(data) != frame_bytes:
                                raise RuntimeError('Incomplete audio cache; re-import the clip.')
                            target.writeframesraw(data)
                        # The visual remainder starts after the transition's
                        # count transition frames, at B block count+1.
                        source.setpos((len(donors)+1)*samples_per_frame)
                        remaining = (clip['frames']-1-len(donors))*samples_per_frame
                        while remaining:
                            data = source.readframes(min(16384, remaining))
                            if not data:
                                raise RuntimeError('Incomplete audio cache; re-import the clip.')
                            target.writeframesraw(data)
                            remaining -= len(data)//(CHANNELS*SAMPLE_WIDTH)
                    else:
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
            raise RuntimeError(f'Assembled audio sample count mismatch: {audio.getnframes()} instead of {expected}.')
    return str(destination), expected


def encoding_args(audio):
    if not audio:
        return ['-map', '0:v:0', '-an']
    return ['-i', str(audio), '-map', '0:v:0', '-map', '1:a:0',
            '-c:a', 'aac', '-b:a', '192k', '-ar', str(SAMPLE_RATE), '-ac', str(CHANNELS)]


def atempo_chain(speed):
    """Return an atempo chain whose factors all lie in FFmpeg's 0.5–2.0 range."""
    factors = []
    remaining = float(speed)
    while remaining < .5 - 1e-9:
        factors.append(.5)
        remaining /= .5
    while remaining > 2 + 1e-9:
        factors.append(2.0)
        remaining /= 2
    factors.append(round(remaining, 9))
    return factors


def speed_audio(audio, frames, destination, speed, fps):
    """Retime PCM with pitch-preserving atempo and restore the exact frame budget."""
    if not audio or speed == 1:
        return audio
    target = frames*SAMPLE_RATE//fps
    filters = ','.join(f'atempo={factor:g}' for factor in atempo_chain(speed))
    filters += f',apad,atrim=end_sample={target},asetpts=N/SR/TB'
    run('ffmpeg','-v','error','-nostdin','-y','-i',str(audio),'-vn','-af',filters,
        '-ac',CHANNELS,'-ar',SAMPLE_RATE,'-c:a','pcm_s16le',str(destination))
    with wave.open(str(destination), 'rb') as output:
        if (output.getnchannels(), output.getsampwidth(), output.getframerate()) != (CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE):
            raise RuntimeError('Unexpected sped audio format.')
        if output.getnframes() != target:
            raise RuntimeError('Sped audio length does not match the video.')
    return str(destination)


def trim_audio(audio, start_frame, end_frame, destination, fps):
    """Copy exact aligned PCM blocks; never re-decode or alter the original."""
    if not audio:
        return None
    samples_per_frame = SAMPLE_RATE // fps
    with wave.open(str(audio), 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE):
            raise RuntimeError('Unexpected audio cache format; re-import the clip.')
        if end_frame*samples_per_frame > source.getnframes():
            raise RuntimeError('Incomplete audio cache; re-import the clip.')
        source.setpos(start_frame*samples_per_frame)
        with wave.open(str(destination), 'wb') as target:
            target.setparams((CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
            remaining = (end_frame-start_frame)*samples_per_frame
            while remaining:
                data = source.readframes(min(16384, remaining))
                if not data:
                    raise RuntimeError('Incomplete audio trim.')
                target.writeframesraw(data)
                remaining -= len(data)//(CHANNELS*SAMPLE_WIDTH)
    return str(destination)
