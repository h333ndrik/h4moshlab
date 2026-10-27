#!/usr/bin/env python3
"""Compare four real prediction schedules using identical clips and original audio."""
import argparse
import json
from pathlib import Path
from mosh import run
from sequence import prepare, render


def compare_dynamic(a,b,directory,duration=2,repeat=6,loop_frames=8):
    directory=Path(directory).resolve()
    if any(directory==Path(p).resolve() or directory in Path(p).resolve().parents for p in (a,b)):
        raise ValueError('Sources must be outside the output directory.')
    clips=[prepare(Path(source).resolve(),directory/name) for source,name in ((a,'a'),(b,'b'))]
    modes=['frame-melt','progressive-melt','motion-loop','motion-stutter']
    reports={}
    for effect in modes:
        reports[effect]=render(clips,[{'effect':effect,'duration':duration,'repeat':repeat,'loop_frames':loop_frames,'ending':'flow'}],directory/effect)
    inputs=[]
    for effect in modes: inputs.extend(['-i',directory/effect/'sequence.mp4'])
    run('ffmpeg','-v','error','-y',*inputs,'-filter_complex','[0:v][1:v][2:v][3:v]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[v]','-map','[v]','-map','0:a?','-c:v','libx264','-threads','2','-crf','18','-c:a','aac','-movflags','+faststart',directory/'comparison.mp4')
    run('ffmpeg','-v','error','-xerror','-i',directory/'comparison.mp4','-f','null','-')
    boundary=reports[modes[0]]['boundaries'][0]['frame']
    for label,index in [('during',boundary+round(duration*12)),('exit',boundary+round(duration*24))]:
        run('ffmpeg','-v','error','-y','-i',directory/'comparison.mp4','-vf',f'select=eq(n\\,{index})','-frames:v','1',directory/f'{label}.png')
    result={'layout':{'top-left':'Frame Melt','top-right':'Progressive Melt','bottom-left':'Motion Loop','bottom-right':'Motion Stutter'},'reports':reports,'original_audio_not_moshed':True}
    (directory/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a',required=True)
    parser.add_argument('--b',required=True)
    parser.add_argument('--output-dir',default='output/dynamic-effects')
    parser.add_argument('--duration',type=float,default=2)
    parser.add_argument('--repeat',type=int,default=6)
    parser.add_argument('--loop-frames',type=int,default=8)
    args=parser.parse_args()
    result=compare_dynamic(args.a,args.b,args.output_dir,args.duration,args.repeat,args.loop_frames)
    print(json.dumps({'layout':result['layout'],'full_decode':'passed','output':str(Path(args.output_dir)/'comparison.mp4')}))
