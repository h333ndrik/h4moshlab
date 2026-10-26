#!/usr/bin/env python3
"""Verified MPEG-4 effects API. No web server or optional dependencies."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from mosh import digest, normalize, probe, run, vops

EFFECTS = {
    'classic-mosh': {'parameters': {}, 'method': 'Remove B I-VOP; append B P-VOPs unchanged.'},
    'frame-melt': {'parameters': {'repeat': {'default': 4, 'min': 2, 'max': 12}},
                   'method': 'Remove B I-VOP; repeat compressed B P-VOPs against evolving references.'},
}

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
    repeat = params.get('repeat', 4) if effect == 'frame-melt' else 1
    if effect == 'frame-melt' and (type(repeat) is not int or not 2 <= repeat <= 12):
        raise ValueError('repeat must be an integer from 2 through 12')
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
    indices = [1 + i//repeat for i in range(count)]
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
    result = {'effect': effect, 'parameters': {'repeat': repeat} if repeat > 1 else {},
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
    parser.add_argument('--repeat', type=int, help='frame-melt only: compressed P-VOP repetition count')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    parameters = {} if args.repeat is None else {'repeat': args.repeat}
    result = process(args.effect, args.a, args.b, args.duration, args.output, parameters)
    print(json.dumps({k:result[k] for k in ('effect','output','boundary_frame','output_frames','transition_duration')}))
