"""Bounded prediction jumps, unchanged audio/timing and real compressed payloads."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from effects import prediction_plan, SMOOTH_EFFECTS, process
from mosh import run, vops, digest
from sequence import prepare, render

class SmoothTests(unittest.TestCase):
    def test_bounded_jumps_and_continuous_tail(self):
        for effect in SMOOTH_EFFECTS:
            for count in (1,12,24,60,144):
                if effect!='frame-melt' and count<12: continue
                for repeat in (2,12):
                    indices,_=prediction_plan(160,effect,count,repeat=repeat,loop_frames=min(8,count-1),smooth=True)
                    self.assertEqual(len(indices),count)
                    self.assertTrue(all(0<=b-a<=2 for a,b in zip(indices,indices[1:])))
                    tail=max(1,count//4)
                    self.assertEqual(indices[-tail:],list(range(count-tail+1,count+1)))
                    original,_=prediction_plan(160,effect,count,repeat=repeat,loop_frames=min(8,count-1))
                    if count>=24:
                        self.assertLessEqual(len(set(indices)),count-1)
                        old=original+[count+1]
                        new=indices+[count+1]
                        self.assertLessEqual(max(b-a for a,b in zip(new,new[1:])),max(b-a for a,b in zip(old,old[1:])))
        for kwargs in ({'smooth':1},{'smooth':True,'motion_start':.5}):
            with self.assertRaises(ValueError): prediction_plan(160,'frame-melt',60,**kwargs)
        with self.assertRaises(ValueError): prediction_plan(160,'classic-mosh',60,smooth=True)

    def test_render_keeps_audio_duration_and_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for label,pattern in [('a','testsrc2'),('b','testsrc')]:
                run('ffmpeg','-v','error','-y','-f','lavfi','-i',f'{pattern}=size=160x120:rate=24','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac',root/f'{label}.mp4')
            clips=[prepare(root/f'{n}.mp4',root/n) for n in ('a','b')]
            _,av=vops(Path(clips[0]['normalized']));_,bv=vops(Path(clips[1]['normalized']))
            audio_hash=None
            for effect in SMOOTH_EFFECTS:
                for smooth in (False,True):
                    dest=root/f'{effect}-{smooth}'
                    result=render(clips,[{'effect':effect,'duration':2,'repeat':6,'loop_frames':8,'smooth':smooth,'ending':'flow'}],dest)
                    indices,_=prediction_plan(len(bv),effect,48,repeat=6,loop_frames=8,smooth=smooth)
                    _,actual=vops(dest/'sequence.m4v')
                    self.assertEqual(actual,av+[bv[i] for i in indices]+bv[49:])
                    self.assertEqual(sum(p[4]>>6==0 for p in actual),1)
                    self.assertEqual(result['frames'],len(av)+len(bv)-1)
                    self.assertEqual(result['audio_samples'],result['frames']*2000)
                    audio_hash=audio_hash or digest(dest/'sequence.wav')
                    self.assertEqual(digest(dest/'sequence.wav'),audio_hash)
                    self.assertEqual(result['full_decode'],'passed')
            evidence=process('frame-melt',root/'a.mp4',root/'b.mp4',2,root/'pair.mp4',{'repeat':6,'smooth':True})
            self.assertTrue(evidence['parameters']['smooth'])
            self.assertTrue(evidence['b_p_vops_byte_identical'])
