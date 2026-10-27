"""Actual P-VOP reuse, distinct decoded results, timeline and audio regression."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from effects import prediction_plan, process
from sequence import prepare, render
from mosh import vops, run
from compare import frame

class DynamicEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        for name, source in [('a','testsrc2=size=160x120:rate=24'), ('b','testsrc=size=160x120:rate=24')]:
            run('ffmpeg','-v','error','-y','-f','lavfi','-i',source,'-f','lavfi','-i','sine=frequency=550:sample_rate=48000','-t','3','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac',cls.root/f'{name}.mp4')
        cls.clips = [prepare(cls.root/f'{n}.mp4',cls.root/n) for n in ('a','b')]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_plans_end_in_consecutive_motion_and_validate_parameters(self):
        for effect in ('progressive-melt','motion-stutter'):
            for count in (12,24,60,144):
                for repeat in (2,12):
                    indices, _ = prediction_plan(160,effect,count,repeat=repeat,loop_frames=min(8,count-1))
                    self.assertEqual(len(indices),count)
                    self.assertLess(len(set(indices)),count)
                    n=max(2,count//4)
                    self.assertEqual(indices[-n:],list(range(count-n+1,count+1)))
            for kwargs in ({'motion_start':.5},{'motion_start':float('nan')}):
                with self.assertRaises(ValueError): prediction_plan(160,effect,60,**kwargs)
            with self.assertRaises(ValueError): prediction_plan(160,effect,11)
        with self.assertRaises(ValueError): prediction_plan(160,'motion-stutter',60,loop_frames=2)
        with self.assertRaises(ValueError): prediction_plan(160,'progressive-melt',60,repeat=13)

    def test_actual_sequences_payloads_audio_and_distinct_frames(self):
        hashes = {}
        for effect in ('classic-mosh','frame-melt','motion-loop','progressive-melt','motion-stutter'):
            directory = self.root/effect
            report = render(self.clips,[{'effect':effect,'duration':2,'repeat':6,'loop_frames':8,'ending':'flow'}],directory)
            _, av = vops(Path(self.clips[0]['normalized']))
            _, bv = vops(Path(self.clips[1]['normalized']))
            _, actual = vops(directory/'sequence.m4v')
            indices,_ = prediction_plan(len(bv),effect,48,repeat=6,loop_frames=8)
            self.assertEqual(actual,av+[bv[i] for i in indices]+bv[49:])
            self.assertEqual(sum(p[4]>>6==0 for p in actual),1)
            self.assertTrue(report['audio'])
            self.assertEqual(report['audio_samples'],report['frames']*2000)
            self.assertEqual(report['full_decode'],'passed')
            frames = b''.join(frame(directory/'sequence.mp4',len(av)+i) for i in (1,8,18,32))
            hashes[effect]=hashlib.sha256(frames).hexdigest()
        self.assertEqual(len(set(hashes.values())),len(hashes))

    def test_common_pair_api_and_unsupported_parameters(self):
        for effect, parameters in [('progressive-melt',{'repeat':6}),('motion-stutter',{'loop_frames':8})]:
            report=process(effect,self.root/'a.mp4',self.root/'b.mp4',2,self.root/f'{effect}.mp4',parameters)
            self.assertTrue(report['source_files_unchanged'])
            self.assertTrue(report['b_p_vops_byte_identical'])
        with self.assertRaises(ValueError):
            process('motion-stutter',self.root/'a.mp4',self.root/'b.mp4',2,self.root/'bad.mp4',{'repeat':4})
