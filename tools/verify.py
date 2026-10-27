#!/usr/bin/env python3
"""Check the rendered proof against an aligned cut and any global linear blend."""
import json
from pathlib import Path
import subprocess
from mosh import WIDTH, HEIGHT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
report = json.loads((OUT / 'verification.json').read_text())
boundary = report['boundary_frame_zero_based']
b_frames = report['normalized']['b_frames'] - 1
indices = [boundary + round((b_frames-1)*fraction) for fraction in (0, 0.08, 0.25, 0.5, 0.92)]

def frame(path, index):
    return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'select=eq(n\\,{index})', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])

last = frame(OUT / 'test-mosh.mp4', boundary-1)
metrics = []
for index in indices:
    m = frame(OUT / 'test-mosh.mp4', index)
    b = frame(OUT / 'test-cut.mp4', index+1)  # B I-frame was removed from mosh
    assert len(m) == len(b) == len(last) == WIDTH*HEIGHT*3
    delta = [y-x for x,y in zip(last,b)]
    denom = sum(d*d for d in delta)
    alpha = max(0, min(1, sum((v-a)*d for v,a,d in zip(m,last,delta))/denom)) if denom else 0
    cut_mae = sum(abs(x-y) for x,y in zip(m,b))/len(m)
    blend_mae = sum(abs(v-(a+alpha*d)) for v,a,d in zip(m,last,delta))/len(m)
    assert cut_mae > 1 and blend_mae > 1
    metrics.append({'frame': index, 'cut_mean_absolute_error_8bit': cut_mae,
                    'best_global_blend_alpha': alpha, 'best_global_blend_mean_absolute_error_8bit': blend_mae})
for name, shift in [('mosh', 0), ('cut', 1)]:
    selected = [boundary-1] + [i+shift for i in indices]
    expression = '+'.join(f'eq(n,{i})' for i in selected)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(OUT/f'test-{name}.mp4'),
                    '-vf', f"select='{expression}',tile=6x1", '-frames:v', '1', str(OUT/f'{name}-frames.png')], check=True)
for source, data in report['sources'].items():
    frames = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_frames', '-show_entries', 'frame=pict_type,key_frame', '-of', 'json', source]))['frames']
    data['frame_count'] = len(frames)
    data['picture_type_counts'] = {t: sum(f['pict_type']==t for f in frames) for t in ('I','P','B')}
    data['keyframe_indices'] = [i for i,f in enumerate(frames) if f['key_frame']]
report['rendered_frame_comparisons'] = metrics
report['full_decode_exit_code'] = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(OUT/'test-mosh.mp4'), '-f', 'null', '-'], check=True).returncode
(OUT/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(metrics, indent=2))
