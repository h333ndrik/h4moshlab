#!/usr/bin/env python3
"""Render identical full sequences with Motion Loop versus Loop Release."""
import argparse
import json
from pathlib import Path
from compare import frame
from mosh import run
from sequence import prepare, render


def compare_release(a, b, directory, duration=2.5, loop_frames=8):
    directory = Path(directory).resolve()
    if any(directory == Path(p).resolve() or directory in Path(p).resolve().parents for p in (a, b)):
        raise ValueError('Sources must be outside the output directory.')
    clips = [prepare(Path(source).resolve(), directory/name) for source, name in ((a,'a'), (b,'b'))]
    reports = {}
    for effect in ('motion-loop', 'loop-release'):
        reports[effect] = render(clips, [{'effect':effect, 'duration':duration, 'loop_frames':loop_frames, 'ending':'flow'}], directory/effect)
    paths = [directory/effect/'sequence.mp4' for effect in reports]
    run('ffmpeg','-v','error','-y','-i',paths[0],'-i',paths[1],'-filter_complex','[0:v][1:v]hstack[v]','-map','[v]','-map','0:a?', '-c:v','libx264','-threads','2','-crf','18','-c:a','aac','-movflags','+faststart',directory/'comparison.mp4')
    run('ffmpeg','-v','error','-xerror','-i',directory/'comparison.mp4','-f','null','-')
    boundary = reports['motion-loop']['boundaries'][0]
    end = boundary['frame'] + round(boundary['duration']*24)
    metrics = {}
    for effect, path in zip(reports, paths):
        before, after = frame(path, end-1), frame(path, end)
        metrics[effect] = sum(abs(a-b) for a,b in zip(before,after))/len(before) if before and after else None
    run('ffmpeg','-v','error','-y','-i',directory/'comparison.mp4','-vf',f"select='eq(n,{end-2})+eq(n,{end-1})+eq(n,{end})+eq(n,{end+1})',scale=640:-1,tile=1x4",'-frames:v','1',directory/'exit-frames.png')
    result = {'layout':'left Motion Loop / right Loop Release', 'exit_frame':end, 'exit_rgb_mae':metrics, 'note':'Frame difference is a diagnostic, not a universal perceptual smoothness score.', 'reports':reports}
    (directory/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a', required=True)
    parser.add_argument('--b', required=True)
    parser.add_argument('--output-dir', default='output/loop-release')
    parser.add_argument('--duration', type=float, default=2.5)
    parser.add_argument('--loop-frames', type=int, default=8)
    args = parser.parse_args()
    result = compare_release(args.a,args.b,args.output_dir,args.duration,args.loop_frames)
    print(json.dumps({k:result[k] for k in ('layout','exit_frame','exit_rgb_mae')}))
