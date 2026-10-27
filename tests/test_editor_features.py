"""Real preset renders, tempo validation and pixel-level per-clip look checks."""
from pathlib import Path
import array
import json
import math
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from editor_options import PRESETS,preset_settings,tempo_frames,validate_tempo,validate_project_settings
from mosh import digest,run,probe,vops
from effects import prediction_plan
from sequence import prepare,render

class EditorFeaturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        for name,pattern in [('a','testsrc2'),('b','testsrc')]:
            run('ffmpeg','-v','error','-y','-f','lavfi','-i',f'{pattern}=size=160x120:rate=24','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','4','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac',cls.root/f'{name}.mp4')
        cls.clips=[prepare(cls.root/f'{n}.mp4',cls.root/n) for n in ('a','b')]
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_all_21_presets_render_and_decode(self):
        for effect in PRESETS:
            plans=[]
            for index in range(3):
                config=preset_settings(effect,index,self.clips[1]['frames'])
                result=render(self.clips,[config],self.root/f'preset-{effect}-{index}')
                self.assertEqual(result['full_decode'],'passed')
                self.assertTrue(result['audio'])
                self.assertEqual(result['source_sha256'],[c['sha256'] for c in self.clips])
                plans.append((result['boundaries'][0]['duration'],result['boundaries'][0]['b_vop_indices']))
            self.assertEqual(len(set(json.dumps(p) for p in plans)),3)
        with self.assertRaises(ValueError):preset_settings('reset-pulse',0,3)

    def test_manual_bpm_rounding_and_periodic_effects(self):
        for effect in ('motion-loop','motion-stutter','reset-pulse'):
            for bpm in (60,120,137,240):
                count=tempo_frames(effect,bpm,1)
                self.assertEqual(count,math.floor(24*60/bpm+.5))
                transition={'effect':effect,'duration':2,'loop_frames':count,'tempo':{'bpm':bpm,'beats':1}}
                validate_tempo(transition)
            result=render(self.clips,[{'effect':effect,'duration':2,'loop_frames':12,'tempo':{'bpm':120,'beats':1}}],self.root/f'bpm-{effect}')
            self.assertEqual(result['boundaries'][0]['tempo']['bpm'],120)
            if effect=='reset-pulse':self.assertEqual(result['boundaries'][0]['reference_reset_offsets'],[11,23,35,47])
        indices,_=prediction_plan(160,'reset-pulse',144,repeat=4,loop_frames=11,tempo={'bpm':137,'beats':1})
        resets=[i for i,value in enumerate(indices) if value==0]
        for beat,offset in enumerate(resets,1):self.assertLessEqual(abs((offset+1)-beat*24*60/137),.5)
        self.assertEqual(resets[:4],[10,20,31,41])
        for args in [('loop-release',120,1),('motion-loop',0,1),('motion-loop',float('nan'),1),('reset-pulse',40,4),('reset-pulse',240,.25)]:
            with self.assertRaises(ValueError):tempo_frames(*args)
        with self.assertRaises(ValueError):validate_tempo({'effect':'reset-pulse','loop_frames':8,'tempo':{'bpm':120,'beats':1}})

    def test_clip_looks_pixels_audio_and_sources(self):
        original=self.root/'a.mp4';before=digest(original);clips={}
        for look in ('original','black-white','negative-bw','negative-color'):
            clip=prepare(original,self.root/f'look-{look}',look=look);clips[look]=clip
            self.assertEqual(clip['sha256'],before)
            self.assertEqual(clip['frames'],self.clips[0]['frames'])
            self.assertEqual(digest(Path(clip['audio'])),digest(Path(self.clips[0]['audio'])))
        def pixels(clip):
            return subprocess.check_output(['ffmpeg','-v','error','-r','24','-i',clip['normalized'],'-frames:v','1','-vf','crop=600:440:20:20','-f','rawvideo','-pix_fmt','rgb24','-'])
        rgb={k:pixels(v) for k,v in clips.items()}
        for name in ('black-white','negative-bw'):
            data=rgb[name]
            difference=sum(abs(data[i]-data[i+1])+abs(data[i+1]-data[i+2]) for i in range(0,len(data),3))/(len(data)/3)
            self.assertLess(difference,2)
        self.assertNotEqual(rgb['original'],rgb['negative-color'])
        self.assertAlmostEqual((sum(rgb['original'])+sum(rgb['negative-color']))/len(rgb['original']),255,delta=12)
        normal=sum(rgb['black-white'])/len(rgb['black-white']);negative=sum(rgb['negative-bw'])/len(rgb['negative-bw'])
        self.assertAlmostEqual(normal+negative,255,delta=12)
        report=render([clips['negative-color'],clips['negative-bw']],[{'effect':'frame-melt','duration':1,'smooth':True}],self.root/'look-export')
        self.assertEqual(report['full_decode'],'passed');self.assertTrue(report['audio'])
        self.assertEqual(digest(original),before)
        with self.assertRaises(ValueError):prepare(original,self.root/'bad-look',look='shader')
