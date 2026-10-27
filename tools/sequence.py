"""Full-clip sequencing built on the verified MPEG-4 I/P operations."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

from effects import EFFECTS, SMOOTH_EFFECTS, prediction_plan
from clip_audio import SAMPLE_RATE, prepare_audio, assemble_audio, encoding_args
from mosh import WIDTH, HEIGHT, digest, normalize, probe, run, vops

FPS = 24


def prepare(source, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    metadata = probe(source)
    videos = [s for s in metadata['streams'] if s['codec_type'] == 'video']
    duration = float(videos[0].get('duration', metadata['format'].get('duration', 0))) if videos else 0
    if not videos or not math.isfinite(duration) or not 0 < duration <= 120:
        raise ValueError('Use a video between 0 and 120 seconds.')
    normalized = directory/'clip.m4v'
    normalize(source, normalized, max_seconds=None)
    header, packets = vops(normalized)
    if len(packets) < 2 or [p[4] >> 6 for p in packets] != [0]+[1]*(len(packets)-1):
        raise ValueError('Video must normalize to at least two I/P frames.')
    audio = prepare_audio(source, metadata, len(packets), directory, FPS)
    preview = directory/'preview.mp4'
    run('ffmpeg', '-v', 'error', '-y', '-r', FPS, '-i', normalized, *encoding_args(audio),
        '-c:v', 'libx264', '-threads', '2', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', preview)
    run('ffmpeg', '-v', 'error', '-y', '-i', preview, '-frames:v', '1', directory/'thumb.jpg')
    return {'source': str(source), 'normalized': str(normalized), 'preview': str(preview), 'audio': audio,
            'frames': len(packets), 'duration': len(packets)/FPS, 'sha256': digest(Path(source))}


def ending_mode(transition):
    default = 'flow' if transition.get('effect') in ('frame-melt', 'motion-loop', 'loop-release', 'progressive-melt', 'motion-stutter', 'reset-pulse') else 'reset'
    ending = transition.get('ending', default)
    if ending not in ('flow', 'reset'):
        raise ValueError('Choose flow or reset for the effect ending.')
    return ending


def render(clips, transitions, directory, progress=lambda stage, fraction: None, preview_boundary=None, include_audio=True):
    if type(include_audio) is not bool:
        raise ValueError('include_audio must be a boolean.')
    if not 1 <= len(clips) <= 12 or len(transitions) != len(clips)-1:
        raise ValueError('Use 1–12 clips with one transition per boundary.')
    if preview_boundary is not None:
        if type(preview_boundary) is not int or not 0 <= preview_boundary < len(transitions):
            raise ValueError('Choose a valid transition to preview.')
        clips, transitions = clips[:preview_boundary+2], transitions[:preview_boundary+1]
    # Validate the whole request before generating anything.
    for clip, transition in zip(clips[1:], transitions):
        effect = transition.get('effect')
        duration = transition.get('duration')
        repeat = transition.get('repeat', 4)
        if effect not in ('cut', *EFFECTS):
            raise ValueError('Unsupported effect.')
        if effect != 'cut':
            ending_mode(transition)
            if type(duration) not in (int, float) or not math.isfinite(duration) or not 1/FPS <= duration <= min(6, (clip['frames']-1)/FPS):
                raise ValueError('Transition duration exceeds the incoming clip (maximum 6s).')
            prediction_plan(clip['frames'], effect, round(duration*FPS), repeat, transition.get('motion_start', 0), transition.get('loop_frames'), transition.get('smooth', False) if effect in SMOOTH_EFFECTS else False,
                            transition.get('release_duration') if effect in SMOOTH_EFFECTS and transition.get('smooth') else None)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stream = directory/'sequence.m4v'
    expected = 0
    boundaries = []
    with stream.open('wb') as target:
        for i, clip in enumerate(clips):
            header, packets = vops(Path(clip['normalized']))
            if i == 0 or transitions[i-1]['effect'] == 'cut':
                if i:
                    boundaries.append({'frame': expected, 'effect': 'cut', 'duration': 0})
                target.write((header if i == 0 else b'')+b''.join(packets))
                expected += len(packets)
            else:
                transition = transitions[i-1]
                count = round(transition['duration']*FPS)
                ending = ending_mode(transition)
                indices, config = prediction_plan(len(packets), transition['effect'], count, transition.get('repeat', 4),
                                                 transition.get('motion_start', 0), transition.get('loop_frames'),
                                                 transition.get('smooth', False) if transition['effect'] in SMOOTH_EFFECTS else False,
                                                 transition.get('release_duration') if transition['effect'] in SMOOTH_EFFECTS and transition.get('smooth') else None)
                tail = [packets[index] for index in indices]
                boundaries.append({'frame': expected, 'effect': transition['effect'], 'duration': count/FPS,
                                   'motion_start': config['motion_start'], 'parameters': config, 'ending': ending,
                                   'reset_frame': expected+count if ending == 'reset' and count+1 < len(packets) else None,
                                   'release_b_vop_indices': list(range(count+1, len(packets))) if ending == 'flow' else [],
                                   'reference_reset_offsets': [j for j,p in enumerate(tail) if p[4] >> 6 == 0],
                                   'b_vop_indices': indices,
                                   'payload_sha256': [hashlib.sha256(p).hexdigest() for p in tail]})
                target.write(b''.join(tail))
                # Flow keeps the evolving reference: normal P-VOPs continue with
                # no forced I-frame. Reset retains the original clear-image exit.
                start = count+1
                if ending == 'flow':
                    target.write(b''.join(packets[start:]))
                elif start < len(packets):
                    suffix = directory/f'restore-{i}.m4v'
                    run('ffmpeg', '-v', 'error', '-y', '-r', FPS, '-i', clip['normalized'],
                        '-vf', f'trim=start_frame={start},setpts=PTS-STARTPTS', '-an',
                        '-c:v', 'mpeg4', '-threads', '2', '-q:v', '4', '-g', '10000', '-bf', '0',
                        '-sc_threshold', '0', '-fps_mode', 'passthrough', '-f', 'm4v', suffix)
                    sh, sv = vops(suffix)
                    if len(sv) != len(packets)-start or sv[0][4] >> 6 != 0:
                        raise RuntimeError(f'Reference restoration failed: {len(sv)} frames instead of {len(packets)-start}; first type {sv[0][4] >> 6}.')
                    target.write(b''.join(sv))
                expected += len(packets)-1
            progress(f'Assembled clip {i+1}/{len(clips)}', .35*(i+1)/len(clips))
    assembled_frames = expected
    video_trim, audio_trim = [], []
    preview_info = None
    if preview_boundary is not None:
        boundary = boundaries[-1]
        start = max(0, boundary['frame'] - 18)
        end = min(expected, boundary['frame'] + round(boundary['duration']*FPS) + 18)
        expected = end-start
        video_trim = ['-vf', f'trim=start_frame={start}:end_frame={end},setpts=N/({FPS}*TB)', '-frames:v', str(expected)]
        audio_trim = ['-af', f'atrim=start_sample={start*2000}:end_sample={end*2000},asetpts=N/SR/TB']
        preview_info = {'boundary_index': preview_boundary, 'start_frame': start, 'end_frame': end, 'source_frames':assembled_frames}
        boundary = dict(boundary, frame=boundary['frame']-start)
        if boundary.get('reset_frame') is not None:
            boundary['reset_frame'] -= start
        boundaries = [boundary]
    run('ffmpeg', '-v', 'error', '-xerror', '-r', FPS, '-i', stream, *video_trim, '-f', 'null', '-')
    progress('Assembling original audio', .36)
    audio, audio_samples = assemble_audio(clips, transitions, directory, FPS) if include_audio else (None, 0)
    if audio and audio_samples != assembled_frames*SAMPLE_RATE//FPS:
        raise RuntimeError('Audio and video timelines do not match.')
    if audio and preview_info is not None:
        audio_samples = expected * SAMPLE_RATE // FPS
    output = directory/'sequence.mp4'
    fixed_timing = preview_info is not None or any(t['effect']=='reset-pulse' for t in transitions)
    output_video = video_trim[:-2] if preview_info is not None else ['-vf', f'setpts=N/({FPS}*TB)'] if fixed_timing else []
    command = ['ffmpeg', '-v', 'error', '-nostdin', '-y', '-r', str(FPS), '-i', str(stream),
               *encoding_args(audio), *output_video,
               *(audio_trim if audio else []), *(['-t', str(expected/FPS)] if preview_info is not None else []),
               *(['-r', str(FPS), '-fps_mode', 'cfr'] if fixed_timing else []), '-c:v', 'libx264', '-threads', '2', '-crf', '18', '-pix_fmt', 'yuv420p',
               '-movflags', '+faststart', '-progress', 'pipe:1', str(output)]
    with (directory/'encode.log').open('w+') as log:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log, text=True) as process:
            for line in process.stdout:
                if line.startswith('out_time_us='):
                    try:
                        fraction = min(.95, .36+.59*int(line.split('=')[1])/(expected/FPS*1e6))
                        progress('Encoding assembled video', fraction)
                    except ValueError:
                        pass
            if process.wait():
                log.seek(0)
                raise RuntimeError('Encoding failed: '+log.read()[-1500:])
    progress('Checking full output decode', .96)
    run('ffmpeg', '-v', 'error', '-xerror', '-i', output, '-f', 'null', '-')
    metadata = probe(output)
    if int(metadata['streams'][0]['nb_frames']) != expected:
        raise RuntimeError('Output frame count mismatch.')
    video_stream = next(s for s in metadata['streams'] if s['codec_type']=='video')
    if abs(float(video_stream['duration'])-expected/FPS) > .002:
        raise RuntimeError('Encoded video duration does not match frame count.')
    audio_streams = [s for s in metadata['streams'] if s['codec_type'] == 'audio']
    if bool(audio_streams) != bool(audio):
        raise RuntimeError('Output audio stream is missing or unexpected.')
    if audio and abs(float(audio_streams[0]['duration'])-expected/FPS) > .002:
        raise RuntimeError('Encoded audio duration does not match video.')
    if any(digest(Path(c['source'])) != c['sha256'] for c in clips):
        raise RuntimeError('An input changed during rendering.')
    report = {'frames': expected, 'duration': expected/FPS, 'boundaries': boundaries,
              'source_sha256': [c['sha256'] for c in clips], 'full_decode': 'passed',
              'size': f'{WIDTH}x{HEIGHT}', 'fps': FPS, 'audio': bool(audio),
              'audio_samples': audio_samples, 'audio_sample_rate': SAMPLE_RATE if audio else None}
    if preview_info is not None:
        report['preview'] = preview_info
    (directory/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    progress('Ready', 1)
    return report
