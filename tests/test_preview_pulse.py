"""Real I-VOP pulses, cropped context fidelity, release limits and unchanged audio."""
from pathlib import Path
import array
import math
import subprocess
import sys
import tempfile
import unittest
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from effects import prediction_plan, process
from sequence import prepare, render
from mosh import run, vops, digest, probe
from compare import frame

class PreviewPulseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        for name,pattern in [('a','testsrc2'),('b','testsrc')]:
            run('ffmpeg','-v','error','-y','-f','lavfi','-i',f'{pattern}=size=160x120:rate=24','-f','lavfi','-i',f'sine=frequency={440 if name == "a" else 880}:sample_rate=48000','-t','4','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac',cls.root/f'{name}.mp4')
        cls.clips=[prepare(cls.root/f'{n}.mp4',cls.root/n) for n in ('a','b')]
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_reset_pulses_are_real_clear_references_then_distort(self):
        output=self.root/'pulse.mp4'
        result=process('reset-pulse',self.root/'a.mp4',self.root/'b.mp4',2,output,{'loop_frames':12,'repeat':4})
        self.assertEqual(result['reference_reset_offsets'],[11,23,35,47])
        _,bv=vops(self.root/'pulse.evidence/b.m4v')
        _,actual=vops(self.root/'pulse.evidence/effect.m4v')
        boundary=result['boundary_frame']
        self.assertEqual(actual[boundary:],[bv[i] for i in result['b_vop_indices']])
        # Decode to raw pixels, bypassing H264 delivery losses, and compare I-frame.
        raw=subprocess.check_output(['ffmpeg','-v','error','-r','24','-i',str(self.root/'pulse.evidence/effect.m4v'),'-f','rawvideo','-pix_fmt','rgb24','-'])
        braw=subprocess.check_output(['ffmpeg','-v','error','-r','24','-i',str(self.root/'pulse.evidence/b.m4v'),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
        size=640*480*3
        reset=boundary+11
        self.assertEqual(raw[reset*size:(reset+1)*size],braw)
        repeated=[raw[(reset+i)*size:(reset+i+1)*size] for i in (1,2,3)]
        self.assertEqual(len(set(repeated)),3)
        self.assertNotEqual(repeated[0],braw)
        for params in ({'loop_frames':3},{'loop_frames':48},{'repeat':1},{'motion_start':.5}):
            with self.assertRaises(ValueError): prediction_plan(96,'reset-pulse',48,**params)

    def test_preview_has_same_prediction_context_audio_and_shorter_encode(self):
        # Preview the SECOND boundary, with preceding Mosh influencing its reference.
        clips=self.clips+[self.clips[0]]
        transitions=[{'effect':'frame-melt','duration':1,'repeat':4}, {'effect':'reset-pulse','duration':1,'loop_frames':8}]
        full=render(clips,transitions,self.root/'full')
        short=render(clips,transitions,self.root/'short',preview_boundary=1)
        self.assertEqual(short['frames'],60)  # .75s + 1s effect + .75s
        self.assertLess(short['frames'],full['frames'])
        self.assertEqual(short['boundaries'][0]['frame'],18)
        self.assertEqual(short['preview']['boundary_index'],1)
        self.assertEqual(short['audio_samples'],short['frames']*2000)
        self.assertEqual(short['full_decode'],'passed')
        self.assertEqual((self.root/'full/sequence.m4v').read_bytes(),(self.root/'short/sequence.m4v').read_bytes())
        # PCM is the exact same source timeline; final encode trims to preview range.
        self.assertEqual(digest(self.root/'full/sequence.wav'),digest(self.root/'short/sequence.wav'))
        start=short['preview']['start_frame']
        fullrgb=frame(self.root/'full/sequence.mp4',start+18)
        shortrgb=frame(self.root/'short/sequence.mp4',18)
        difference=sum(abs(a-b) for a,b in zip(fullrgb,shortrgb))/len(fullrgb)
        pcm=array.array('f',subprocess.check_output(['ffmpeg','-v','error','-i',str(self.root/'short/sequence.mp4'),'-map','0:a:0','-ac','1','-ar','48000','-f','f32le','-']))
        for time,frequency in ((.1,880),(1.1,440)):
            samples=pcm[round(time*48000):round((time+.1)*48000)]
            def energy(hz):
                return abs(sum(v*complex(math.cos(2*math.pi*hz*i/48000),math.sin(2*math.pi*hz*i/48000)) for i,v in enumerate(samples)))
            self.assertGreater(energy(frequency),energy(440 if frequency==880 else 880)*5)
        self.assertLess(difference,4)  # independently encoded H264, same actual imagery
        for bad in (-1,2,True):
            with self.assertRaises(ValueError): render(clips,transitions,self.root/'bad',preview_boundary=bad)

    def test_release_parameter_changes_tail_without_timing_change(self):
        for seconds in (.25,.75):
            indices,config=prediction_plan(96,'frame-melt',48,repeat=6,smooth=True,release_duration=seconds)
            n=round(seconds*24)
            self.assertEqual(indices[-n:],list(range(49-n,49)))
            self.assertEqual(config['release_duration'],seconds)
            self.assertTrue(all(0<=b-a<=2 for a,b in zip(indices,indices[1:])))
        short,_=prediction_plan(96,'frame-melt',48,repeat=6,smooth=True,release_duration=.25)
        long,_=prediction_plan(96,'frame-melt',48,repeat=6,smooth=True,release_duration=.75)
        self.assertNotEqual(short,long)
        for seconds in (-1,0,1.1,float('nan')):
            with self.assertRaises(ValueError):prediction_plan(96,'frame-melt',48,smooth=True,release_duration=seconds)
        with self.assertRaises(ValueError):prediction_plan(96,'frame-melt',48,release_duration=.25)

    def test_sound_off_removes_audio_in_export_and_short_preview(self):
        transitions=[{'effect':'reset-pulse','duration':1,'loop_frames':8}]
        on=render(self.clips,transitions,self.root/'sound-on')
        off=render(self.clips,transitions,self.root/'sound-off',include_audio=False)
        short=render(self.clips,transitions,self.root/'sound-off-short',preview_boundary=0,include_audio=False)
        self.assertTrue(on['audio'])
        self.assertFalse(off['audio'])
        self.assertFalse(short['audio'])
        self.assertEqual(off['audio_samples'],0)
        self.assertEqual(on['frames'],off['frames'])
        self.assertEqual(digest(self.root/'sound-on/sequence.m4v'),digest(self.root/'sound-off/sequence.m4v'))
        for folder in ('sound-off','sound-off-short'):
            self.assertFalse(any(s['codec_type']=='audio' for s in probe(self.root/folder/'sequence.mp4')['streams']))
        with self.assertRaises(ValueError):render(self.clips,transitions,self.root/'bad-audio',include_audio='false')
