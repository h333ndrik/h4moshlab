#!/usr/bin/env python3
"""Full old/new sequence comparison for gentler compressed-frame repetition."""
import argparse
import json
from pathlib import Path
from effects import SMOOTH_EFFECTS
from mosh import digest, run
from sequence import prepare, render


def compare_smooth(a,b,directory,effect='frame-melt',duration=2,repeat=6,loop_frames=8):
    directory=Path(directory).resolve()
    if any(directory==Path(p).resolve() or directory in Path(p).resolve().parents for p in (a,b)):
        raise ValueError('Sources must be outside output directory.')
    clips=[prepare(Path(source).resolve(),directory/name) for source,name in ((a,'a'),(b,'b'))]
    reports={}
    jumps={}
    for label,smooth in [('original',False),('gentler',True)]:
        reports[label]=render(clips,[{'effect':effect,'duration':duration,'repeat':repeat,'loop_frames':loop_frames,'smooth':smooth,'ending':'flow'}],directory/label)
        boundary=reports[label]['boundaries'][0]
        indices=boundary['b_vop_indices']+boundary['release_b_vop_indices']
        jumps[label]=max(abs(b-a) for a,b in zip(indices,indices[1:]))
    assert reports['original']['frames']==reports['gentler']['frames']
    if reports['original']['audio']:
        assert digest(directory/'original/sequence.wav')==digest(directory/'gentler/sequence.wav')
    run('ffmpeg','-v','error','-y','-i',directory/'original/sequence.mp4','-i',directory/'gentler/sequence.mp4','-filter_complex','[0:v][1:v]hstack[v]','-map','[v]','-map','0:a?','-c:v','libx264','-threads','2','-crf','18','-c:a','aac','-movflags','+faststart',directory/'comparison.mp4')
    run('ffmpeg','-v','error','-xerror','-i',directory/'comparison.mp4','-f','null','-')
    boundary=reports['original']['boundaries'][0]
    end=boundary['frame']+round(boundary['duration']*24)
    run('ffmpeg','-v','error','-y','-i',directory/'comparison.mp4','-vf',f"select='eq(n,{end-2})+eq(n,{end-1})+eq(n,{end})+eq(n,{end+1})',scale=640:-1,tile=1x4",'-frames:v','1',directory/'exit-frames.png')
    result={'effect':effect,'layout':'left Original / right Gentler','max_donor_step':jumps,'audio_pcm_identical':True if reports['original']['audio'] else None,'reports':reports,'note':'Bounded donor steps are a structural improvement, not a guarantee of perceptual smoothness.'}
    (directory/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a',required=True);parser.add_argument('--b',required=True)
    parser.add_argument('--output-dir',default='output/smooth-comparison')
    parser.add_argument('--effect',choices=SMOOTH_EFFECTS,default='frame-melt')
    parser.add_argument('--duration',type=float,default=2)
    parser.add_argument('--repeat',type=int,default=6)
    parser.add_argument('--loop-frames',type=int,default=8)
    args=parser.parse_args()
    result=compare_smooth(args.a,args.b,args.output_dir,args.effect,args.duration,args.repeat,args.loop_frames)
    print(json.dumps({k:result[k] for k in ('effect','layout','max_donor_step','audio_pcm_identical')}))
