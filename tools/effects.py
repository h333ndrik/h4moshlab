#!/usr/bin/env python3
"""Verified MPEG-4 effects API. No web server or optional dependencies."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from mosh import digest, normalize, probe, run, vops

EFFECTS = {
    'progressive-melt': {'parameters': {'motion_start': {'default': 0}, 'repeat': {'default': 4, 'min': 2, 'max': 12}},
                         'method': 'Repeat timeline-anchored P-VOPs with decreasing repetition, then continue consecutive prediction frames.'},
    'motion-stutter': {'parameters': {'motion_start': {'default': 0}, 'loop_frames': {'default': 12, 'min': 4, 'max': 48}},
                       'method': 'Alternate repeated single P-VOP bursts with consecutive motion; finish with an uninterrupted prediction tail.'},
    'classic-mosh': {'parameters': {'motion_start': {'default': 0}}, 'method': 'Remove B I-VOP; append B P-VOPs unchanged.'},
    'frame-melt': {'parameters': {'motion_start': {'default': 0}, 'repeat': {'default': 4, 'min': 2, 'max': 12}},
                   'method': 'Remove B I-VOP; repeat compressed B P-VOPs against evolving references.'},
    'loop-release': {'parameters': {'motion_start': {'default': 0}, 'loop_frames': {'default': 12, 'min': 2, 'max': 48}},
                     'method': 'Repeat motion groups three then two times; finish with timeline-aligned consecutive P-VOPs, without a reference reset.'},
    'motion-loop': {'parameters': {'motion_start': {'default': 0}, 'loop_frames': {'default': 12, 'min': 2, 'max': 48}},
                    'method': 'Replay a selected group of compressed B P-VOPs against evolving references.'},
}


SMOOTH_EFFECTS = ('frame-melt', 'progressive-melt', 'motion-stutter')
for _effect in SMOOTH_EFFECTS:
    EFFECTS[_effect]['parameters']['smooth'] = {'default': False}


def soften_repetitions(positions):
    """Bound donor advances to two; reserve a timeline-aligned consecutive tail.

    Repeating predictions consumes output time. Catch-up is distributed across
    earlier frames instead of jumping at a block boundary. Some donor frames are
    still skipped; this is not interpolation or a perceptual smoothness guarantee.
    """
    count = len(positions)
    release = count - max(1, count // 4)
    result = []
    previous = 0
    for i, desired in enumerate(positions):
        lower = max(0, release - 2 * (release - i))
        value = i if i >= release else min(previous + 2, max(previous, desired, lower))
        result.append(value)
        previous = value
    return result


def prediction_plan(frame_count, effect, count, repeat=4, motion_start=0, loop_frames=None, smooth=False):
    """Validate/select donor VOP indices without decoding or altering their payloads.

    motion_start is seconds from B's first P-VOP, rounded to 24fps. Output duration
    is independent of donor progress. Loop repeats a group, Melt repeats each VOP.
    """
    if effect not in EFFECTS:
        raise ValueError('Unsupported effect')
    if type(count) is not int or not 1 <= count <= frame_count-1:
        raise ValueError('Transition exceeds the incoming clip motion frames.')
    if type(motion_start) not in (int, float) or not math.isfinite(motion_start) or motion_start < 0:
        raise ValueError('motion_start must be a nonnegative finite number of seconds')
    if type(smooth) is not bool or (smooth and effect not in SMOOTH_EFFECTS):
        raise ValueError('smooth must be a boolean and is supported only for repetition effects.')
    offset = round(motion_start*24)
    if smooth and offset != 0:
        raise ValueError('Smooth repetition requires motion_start=0 for a timeline-aligned exit.')
    available = frame_count-1-offset
    if available < 1:
        raise ValueError('Motion start is outside the incoming clip.')
    if effect in ('loop-release', 'progressive-melt', 'motion-stutter') and (offset != 0 or count < 12):
        raise ValueError('This timeline-aligned effect needs at least 0.5 seconds and motion_start=0 for a timeline-aligned exit.')
    config = {'motion_start': offset/24}
    if effect in ('frame-melt', 'progressive-melt'):
        if type(repeat) is not int or not 2 <= repeat <= 12:
            raise ValueError('repeat must be an integer from 2 through 12')
        positions = [i//repeat for i in range(count)]
        if effect == 'progressive-melt':
            positions = []
            while len(positions) < count:
                start = len(positions)
                remaining = max(0, 1 - start / max(1, count * .75))
                repetitions = max(1, round(1 + (repeat - 1) * remaining * remaining))
                release = count - max(2, count // 4)
                repetitions = min(repetitions, release - start) if start < release else 1
                positions.extend([start] * repetitions)
        config['repeat'] = repeat
    elif effect in ('motion-loop', 'loop-release', 'motion-stutter'):
        if loop_frames is None:
            loop_frames = min(12, available, count-1)
        if type(loop_frames) is not int or not 2 <= loop_frames <= 48 or loop_frames >= count:
            raise ValueError('Choose 2–48 loop frames and an effect longer than one loop.')
        if loop_frames > available:
            raise ValueError('The selected motion loop extends beyond the incoming clip.')
        if effect == 'motion-stutter' and loop_frames < 4:
            raise ValueError('Motion Stutter needs 4–48 frames per pulse.')
        positions = [i % loop_frames for i in range(count)]
        if effect == 'motion-stutter':
            release = count - max(2, count // 4)
            positions = [i - i % loop_frames if i < release and i % loop_frames < loop_frames // 2 else i
                         for i in range(count)]
        if effect == 'loop-release':
            # Keep at least half the transition for uninterrupted normal motion.
            # Repeated blocks start at their output-timeline position; this skips
            # donor motion at block boundaries, but rejoins the tail exactly.
            positions = []
            for repetitions in (3, 2):
                length = min(loop_frames, (count // 2 - len(positions)) // repetitions)
                if length < 2:
                    continue
                start = len(positions)
                positions.extend(list(range(start, start + length)) * repetitions)
            positions.extend(range(len(positions), count))
        config['loop_frames'] = loop_frames
    else:
        positions = list(range(count))
    if smooth:
        positions = soften_repetitions(positions)
        config['smooth'] = True
    if max(positions) >= available:
        raise ValueError('Selected motion range is too short; move its start earlier or shorten the effect.')
    return [1+offset+i for i in positions], config


def prediction_tail(packets, effect, count, repeat=4, motion_start=0, loop_frames=None, smooth=False):
    """Shared compressed-domain operation used by CLI and sequence renderer."""
    indices, _ = prediction_plan(len(packets), effect, count, repeat, motion_start, loop_frames, smooth)
    return indices, [packets[i] for i in indices]


def process(effect, a, b, transition_duration, output, parameters=None):
    """Render <=6s of A followed by exactly duration*24 prediction frames.

    Inputs are never changed. Returns an evidence dict; writes MP4 and adjacent
    <stem>.evidence/{a,b,effect}.m4v and verification.json. All paths are local.
    """
    if effect not in EFFECTS:
        raise ValueError(f'Unsupported effect: {effect}; available: {list(EFFECTS)}')
    params = dict(parameters or {})
    if set(params) - set(EFFECTS[effect]['parameters']):
        raise ValueError('Unsupported parameter')
    repeat = params.get('repeat', 4)
    if not math.isfinite(transition_duration) or not 1/24 <= transition_duration <= 6:
        raise ValueError('transition_duration must be between 1/24 and 6 seconds')
    count = round(transition_duration * 24)
    a, b, output = (Path(p).resolve() for p in (a, b, output))
    if output.suffix.lower() != '.mp4' or output in (a, b):
        raise ValueError('Output must be a separate .mp4 file')
    evidence = output.parent / (output.stem + '.evidence')
    if any(p == evidence or evidence in p.parents for p in (a, b)):
        raise ValueError('Input cannot be inside the evidence directory')
    originals = {str(p): digest(p) for p in (a, b)}
    evidence.mkdir(parents=True, exist_ok=True)
    for label, source in [('a', a), ('b', b)]:
        normalize(source, evidence / f'{label}.m4v')
    header, av = vops(evidence / 'a.m4v')
    _, bv = vops(evidence / 'b.m4v')
    for packets in (av, bv):
        if len(packets) < 2 or [p[4] >> 6 for p in packets] != [0] + [1]*(len(packets)-1):
            raise ValueError('Normalization must yield initial I and subsequent P VOPs')
    # Equal output duration across effects. Melt progresses more slowly through B.
    if count > len(bv)-1:
        raise ValueError(f'Transition too long for B: maximum {(len(bv)-1)/24:.6f}s')
    indices, config = prediction_plan(len(bv), effect, count, repeat, params.get('motion_start', 0), params.get('loop_frames'), params.get('smooth', False))
    tail = [bv[i] for i in indices]
    stream = evidence / 'effect.m4v'
    stream.write_bytes(header + b''.join(av + tail))
    # Full manipulated-stream decode is also checked, before delivery encoding.
    run('ffmpeg', '-v', 'error', '-xerror', '-r', '24', '-i', stream, '-f', 'null', '-')
    run('ffmpeg', '-v', 'error', '-nostdin', '-y', '-fflags', '+genpts', '-r', '24', '-i', stream,
        '-an', '-c:v', 'libx264', '-threads', '2', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', output)
    run('ffmpeg', '-v', 'error', '-xerror', '-i', output, '-f', 'null', '-')
    metadata = probe(output)
    if int(metadata['streams'][0]['nb_frames']) != len(av)+count:
        raise RuntimeError('Wrong decoded output frame count')
    _, actual = vops(stream)
    if actual != av+tail:
        raise RuntimeError('Compressed payload verification failed')
    if any(digest(Path(p)) != h for p,h in originals.items()):
        raise RuntimeError('Original source changed')
    result = {'effect': effect, 'parameters': {k:v for k,v in config.items() if k != 'motion_start' or v != 0},
              'requested_transition_duration': transition_duration, 'transition_duration': count/24,
              'boundary_frame': len(av), 'output_frames': len(av)+count,
              'source_sha256': originals, 'source_files_unchanged': True,
              'b_vop_indices': indices, 'b_p_vops_byte_identical': True,
              'b_payload_sha256': [hashlib.sha256(p).hexdigest() for p in tail],
              'full_intermediate_and_output_decode': 'passed', 'output': str(output), 'probe': metadata}
    (evidence/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--effect', choices=EFFECTS, required=True)
    parser.add_argument('--a', type=Path, required=True)
    parser.add_argument('--b', type=Path, required=True)
    parser.add_argument('--duration', type=float, required=True, help='Seconds of effect after A, rounded to 24fps')
    parser.add_argument('--motion-start', type=float, default=0, help='Seconds into B motion (first P-VOP = zero)')
    parser.add_argument('--loop-frames', type=int, help='Loop/Release/Stutter: group or pulse size in frames')
    parser.add_argument('--repeat', type=int, help='Frame/Progressive Melt: initial P-VOP repetition count')
    parser.add_argument('--smooth', action='store_true', help='Gentler Frame/Progressive Melt or Stutter cadence; requires motion-start=0')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    parameters = {'motion_start': args.motion_start}
    if args.smooth:
        parameters['smooth'] = True
    if args.repeat is not None:
        parameters['repeat'] = args.repeat
    if args.loop_frames is not None:
        parameters['loop_frames'] = args.loop_frames
    result = process(args.effect, args.a, args.b, args.duration, args.output, parameters)
    print(json.dumps({k:result[k] for k in ('effect','output','boundary_frame','output_frames','transition_duration')}))
