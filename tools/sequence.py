"""Full-clip sequencing built on the verified MPEG-4 I/P operations."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

from effects import EFFECTS, prediction_plan
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
    preview = directory/'preview.mp4'
    run('ffmpeg', '-v', 'error', '-y', '-r', FPS, '-i', normalized, '-an',
        '-c:v', 'libx264', '-threads', '2', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', preview)
    run('ffmpeg', '-v', 'error', '-y', '-i', preview, '-frames:v', '1', directory/'thumb.jpg')
    return {'source': str(source), 'normalized': str(normalized), 'preview': str(preview),
            'frames': len(packets), 'duration': len(packets)/FPS, 'sha256': digest(Path(source))}


def ending_mode(transition):
    default = 'flow' if transition.get('effect') in ('frame-melt', 'motion-loop') else 'reset'
    ending = transition.get('ending', default)
    if ending not in ('flow', 'reset'):
        raise ValueError('Choose flow or reset for the effect ending.')
    return ending


def render(clips, transitions, directory, progress=lambda stage, fraction: None):
    if not 1 <= len(clips) <= 12 or len(transitions) != len(clips)-1:
        raise ValueError('Use 1–12 clips with one transition per boundary.')
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
            prediction_plan(clip['frames'], effect, round(duration*FPS), repeat, transition.get('motion_start', 0), transition.get('loop_frames'))
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
                                                 transition.get('motion_start', 0), transition.get('loop_frames'))
                tail = [packets[index] for index in indices]
                boundaries.append({'frame': expected, 'effect': transition['effect'], 'duration': count/FPS,
                                   'motion_start': config['motion_start'], 'parameters': config, 'ending': ending,
                                   'reset_frame': expected+count if ending == 'reset' and count+1 < len(packets) else None,
                                   'release_b_vop_indices': list(range(count+1, len(packets))) if ending == 'flow' else [],
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
    run('ffmpeg', '-v', 'error', '-xerror', '-r', FPS, '-i', stream, '-f', 'null', '-')
    output = directory/'sequence.mp4'
    command = ['ffmpeg', '-v', 'error', '-nostdin', '-y', '-r', str(FPS), '-i', str(stream),
               '-an', '-c:v', 'libx264', '-threads', '2', '-crf', '18', '-pix_fmt', 'yuv420p',
               '-movflags', '+faststart', '-progress', 'pipe:1', str(output)]
    with (directory/'encode.log').open('w+') as log:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log, text=True) as process:
            for line in process.stdout:
                if line.startswith('out_time_us='):
                    try:
                        fraction = min(.95, .35+.6*int(line.split('=')[1])/(expected/FPS*1e6))
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
    if any(digest(Path(c['source'])) != c['sha256'] for c in clips):
        raise RuntimeError('An input changed during rendering.')
    report = {'frames': expected, 'duration': expected/FPS, 'boundaries': boundaries,
              'source_sha256': [c['sha256'] for c in clips], 'full_decode': 'passed',
              'size': f'{WIDTH}x{HEIGHT}', 'fps': FPS, 'audio': False}
    (directory/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    progress('Ready', 1)
    return report
