#!/usr/bin/env python3
"""Render both verified effects from identical inputs, plus a side-by-side MP4."""
import argparse
import json
from pathlib import Path
import subprocess

from effects import process
from mosh import WIDTH, HEIGHT, run


def frame(path, index):
    return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-vf',
        f'select=eq(n\\,{index})', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])


def compare(a, b, duration, output_dir, repeat=4):
    directory = Path(output_dir).resolve()
    sources = {Path(a).resolve(), Path(b).resolve()}
    generated = [directory/name for name in ('classic-mosh.mp4', 'frame-melt.mp4',
                 'classic-mosh.png', 'frame-melt.png', 'comparison.mp4', 'comparison.json')]
    evidence_dirs = [directory/f'{effect}.evidence' for effect in ('classic-mosh', 'frame-melt')]
    if sources.intersection(generated) or any(d == p or d in p.parents for d in evidence_dirs for p in sources):
        raise ValueError('Comparison outputs cannot overwrite source files')
    directory.mkdir(parents=True, exist_ok=True)
    reports = {}
    for effect in ('classic-mosh', 'frame-melt'):
        reports[effect] = process(effect, a, b, duration, directory/f'{effect}.mp4',
                                 {'repeat': repeat} if effect == 'frame-melt' else {})
    boundary = reports['classic-mosh']['boundary_frame']
    count = reports['classic-mosh']['output_frames']-boundary
    indices = [boundary-1] + sorted(set(boundary+round((count-1)*x) for x in (0, .2, .4, .8)))
    for effect in reports:
        expression = '+'.join(f'eq(n,{i})' for i in indices)
        run('ffmpeg', '-v', 'error', '-y', '-i', directory/f'{effect}.mp4',
            '-vf', f"select='{expression}',tile={len(indices)}x1", '-frames:v', '1', directory/f'{effect}.png')
    index = boundary+count//2
    left, right = [frame(directory/f'{effect}.mp4', index) for effect in reports]
    if len(left) != WIDTH*HEIGHT*3 or len(right) != len(left):
        raise RuntimeError('Missing comparison frame')
    difference = sum(abs(a-b) for a,b in zip(left,right))/len(left)
    if difference <= 2:
        raise RuntimeError('Insufficient visual distinction on this source pair; inspect source motion')
    run('ffmpeg', '-v', 'error', '-y', '-i', directory/'classic-mosh.mp4', '-i', directory/'frame-melt.mp4',
        '-filter_complex', '[0:v][1:v]hstack=inputs=2[v]', '-map', '[v]', '-an', '-c:v', 'libx264',
        '-threads', '2', '-crf', '18', '-movflags', '+faststart', directory/'comparison.mp4')
    run('ffmpeg', '-v', 'error', '-xerror', '-i', directory/'comparison.mp4', '-f', 'null', '-')
    report = {'layout': 'left: classic-mosh; right: frame-melt',
              'comparison_frame': index, 'mean_absolute_rgb_difference_8bit': difference,
              'effects': reports, 'motion-transfer': {'status': 'not implemented',
              'reason': 'ffedit unavailable; FFglitch download/documentation HTTP 403 in this cloud environment'}}
    (directory/'comparison.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Comparison: {directory / "comparison.mp4"}; frame {index} RGB MAE: {difference:.3f}/255')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a', type=Path, required=True)
    parser.add_argument('--b', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=2.5)
    parser.add_argument('--repeat', type=int, default=4)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parents[1]/'output/phase2')
    args = parser.parse_args()
    compare(args.a, args.b, args.duration, args.output_dir, args.repeat)
