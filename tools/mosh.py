#!/usr/bin/env python3
"""One MPEG-4 Part 2 reference-frame substitution; Python stdlib + FFmpeg."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def run(*args):
    subprocess.run([str(a) for a in args], check=True)

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def vops(path):
    data = path.read_bytes()
    marker = b'\x00\x00\x01\xb6'
    offsets = []
    pos = data.find(marker)
    while pos >= 0:
        offsets.append(pos)
        pos = data.find(marker, pos + 4)
    if not offsets:
        raise ValueError('No MPEG-4 VOPs')
    return data[:offsets[0]], [data[a:b] for a, b in zip(offsets, offsets[1:] + [len(data)])]

def normalize(source, destination):
    """Shared, unchanged Phase 1 normalization; never edit the source."""
    run('ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', source, '-t', '6', '-an',
        '-vf', 'scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2,fps=24,setsar=1',
        '-c:v', 'mpeg4', '-threads', '2', '-q:v', '4', '-g', '10000', '-bf', '0', '-sc_threshold', '0',
        '-pix_fmt', 'yuv420p', '-f', 'm4v', destination)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a', type=Path, default=ROOT / 'samples/clip-a.mp4')
    parser.add_argument('--b', type=Path, default=ROOT / 'samples/clip-b.mp4')
    parser.add_argument('--synthetic', action='store_true', help='Generate missing default sample files, never overwrite sources')
    args = parser.parse_args()
    work, output = ROOT / 'work', ROOT / 'output'
    work.mkdir(exist_ok=True)
    output.mkdir(exist_ok=True)
    if args.synthetic:
        for path, source in [(args.a, 'testsrc2=size=320x240:rate=24:duration=6'), (args.b, 'testsrc=size=320x240:rate=24:duration=6')]:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                run('ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'lavfi', '-i', source,
                    '-c:v', 'libx264', '-threads', '2', '-pix_fmt', 'yuv420p', path)
    before = {str(p): digest(p) for p in (args.a, args.b)}
    sources = {str(p): probe(p) for p in (args.a, args.b)}
    for label, source in [('a', args.a), ('b', args.b)]:
        normalize(source, work / f'{label}.m4v')
    header, a = vops(work / 'a.m4v')
    _, b = vops(work / 'b.m4v')
    types = lambda packets: [p[4] >> 6 for p in packets]
    assert types(a) == [0] + [1] * (len(a)-1), types(a)
    assert types(b) == [0] + [1] * (len(b)-1), types(b)
    # Keep A's VOL configuration and all A VOPs. Drop B's I-VOP and
    # configuration prefix, append B's P-VOP bytes without changing a bit.
    mosh = header + b''.join(a + b[1:])
    (work / 'mosh.m4v').write_bytes(mosh)
    (work / 'cut.m4v').write_bytes(header + b''.join(a + b))
    for name in ('mosh', 'cut'):
        run('ffmpeg', '-v', 'error', '-nostdin', '-y', '-fflags', '+genpts', '-r', '24',
            '-i', work / f'{name}.m4v', '-an', '-c:v', 'libx264', '-threads', '2', '-crf', '18',
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', output / f'test-{name}.mp4')
    result = output / 'test-mosh.mp4'
    run('ffmpeg', '-v', 'error', '-xerror', '-i', result, '-f', 'null', '-')
    _, actual = vops(work / 'mosh.m4v')
    assert actual[len(a):] == b[1:], 'B prediction payloads changed'
    assert all(digest(Path(p)) == h for p, h in before.items()), 'Source changed'
    report = {'source_sha256': before, 'sources': sources,
              'normalized': {'codec': 'mpeg4', 'size': '320x240', 'fps': 24, 'a_frames': len(a), 'b_frames': len(b), 'a_vop_types': types(a), 'b_vop_types': types(b)},
              'boundary_frame_zero_based': len(a), 'removed_b_i_vops': 1,
              'b_p_vops_byte_identical': True, 'source_files_unchanged': True,
              'output': probe(result)}
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Created {result}; boundary frame {len(a)}; retained {len(b)-1} byte-identical B P-VOPs')

if __name__ == '__main__':
    main()
