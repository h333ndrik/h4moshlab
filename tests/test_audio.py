"""Real AAC export, exact PCM timeline, source offsets and silent gaps."""
from array import array
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from mosh import digest, probe, run
from sequence import prepare, render

RATE = 48000


def pcm(path):
    with wave.open(str(path), 'rb') as source:
        return source.readframes(source.getnframes())


def rms(data, start, end):
    samples = array('h', data)[round(start*RATE)*2:round(end*RATE)*2]
    return math.sqrt(sum(v*v for v in samples)/len(samples))


def amplitude(samples, offset, frequency):
    segment = samples[round(offset*RATE):round(offset*RATE)+2400]
    real = sum(v*math.cos(2*math.pi*frequency*i/RATE) for i,v in enumerate(segment))
    imag = sum(v*math.sin(2*math.pi*frequency*i/RATE) for i,v in enumerate(segment))
    return math.hypot(real, imag)/len(segment)


class AudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.clips = []
        for i,(frequency,duration) in enumerate(((440,1.5),(None,1),(880,2))):
            source = cls.root/f'source-{i}.mov'
            args = ['ffmpeg','-v','error','-y','-f','lavfi','-i',f'testsrc2=size=160x120:rate=24:duration={duration}']
            if frequency:
                args += ['-f','lavfi','-i',f'sine=frequency={frequency}:sample_rate=44100:duration={duration}', '-c:a','pcm_s16le']
            args += ['-c:v','libx264','-threads','2',str(source)]
            run(*args)
            cls.clips.append(prepare(source, cls.root/f'clip-{i}'))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_mixed_sequence_has_exact_silence_and_mosh_frame_trim(self):
        result = render(self.clips, [{'effect':'cut'}, {'effect':'motion-loop','duration':.5,'loop_frames':4}], self.root/'mixed')
        expected = pcm(self.clips[0]['audio']) + bytes(24*2000*4) + pcm(self.clips[2]['audio'])[2000*4:]
        self.assertEqual(pcm(self.root/'mixed/sequence.wav'), expected)
        self.assertTrue(result['audio'])
        self.assertEqual(result['frames'],107)
        self.assertEqual(result['audio_samples'],107*2000)
        streams = probe(self.root/'mixed/sequence.mp4')['streams']
        video = next(s for s in streams if s['codec_type']=='video')
        audio = next(s for s in streams if s['codec_type']=='audio')
        self.assertEqual((audio['codec_name'],int(audio['sample_rate']),audio['channels']), ('aac',48000,2))
        self.assertAlmostEqual(float(audio['duration']),float(video['duration']),places=3)
        decoded = subprocess.check_output(['ffmpeg','-v','error','-xerror','-i',str(self.root/'mixed/sequence.mp4'),'-map','0:a:0','-ac','1','-ar','48000','-f','s16le','-'])
        samples=array('h',decoded)
        self.assertGreater(amplitude(samples,.4,440),10*amplitude(samples,.4,880))
        self.assertLess(max(abs(v) for v in samples[round(1.7*RATE):round(2.2*RATE)]),5)
        self.assertGreater(amplitude(samples,3,880),10*amplitude(samples,3,440))

    def test_reordering_reorders_sound_and_previews_include_audio(self):
        clips=[self.clips[2],self.clips[0]]
        result=render(clips,[{'effect':'cut'}],self.root/'reordered')
        self.assertEqual(pcm(self.root/'reordered/sequence.wav'),pcm(clips[0]['audio'])+pcm(clips[1]['audio']))
        self.assertEqual(result['audio_samples'],84*2000)
        for clip in clips:
            self.assertTrue(any(s['codec_type']=='audio' for s in probe(clip['preview'])['streams']))
        self.assertIsNone(self.clips[1]['audio'])
        self.assertFalse(any(s['codec_type']=='audio' for s in probe(self.clips[1]['preview'])['streams']))

    def test_source_audio_start_and_short_track_are_padded(self):
        source=self.root/'delayed.mov'
        run('ffmpeg','-v','error','-y','-f','lavfi','-i','color=size=160x120:rate=24:duration=2',
            '-itsoffset','0.25','-f','lavfi','-i','sine=frequency=660:sample_rate=48000:duration=1.2',
            '-c:v','libx264','-threads','2','-c:a','pcm_s16le',source)
        clip=prepare(source,self.root/'delayed')
        self.assertEqual(clip['frames'],48)
        data=pcm(clip['audio'])
        self.assertEqual(len(data),48*2000*4)
        self.assertLess(rms(data,0,.2),1)
        self.assertGreater(rms(data,.35,.55),100)
        self.assertLess(rms(data,1.6,1.9),1)

    def test_audio_is_aligned_to_first_video_frame_not_container_start(self):
        source=self.root/'video-offset.mov'
        run('ffmpeg','-v','error','-y','-itsoffset','0.5','-f','lavfi','-i','color=size=160x120:rate=24:duration=1',
            '-f','lavfi','-i','sine=frequency=660:sample_rate=48000:duration=0.5',
            '-af','adelay=750','-c:v','libx264','-threads','2','-c:a','pcm_s16le',source)
        clip=prepare(source,self.root/'video-offset')
        self.assertEqual(clip['frames'],24)
        data=pcm(clip['audio'])
        self.assertLess(rms(data,0,.2),1)
        self.assertGreater(rms(data,.35,.55),100)

    def test_trim_copies_exact_pcm_blocks_and_keeps_export_aligned(self):
        original=self.clips[2]
        trimmed=prepare(original['source'],self.root/'trimmed-audio',start_frame=7,end_frame=31,base=original)
        expected=pcm(original['audio'])[7*2000*4:31*2000*4]
        self.assertEqual(pcm(trimmed['audio']),expected)
        self.assertEqual((trimmed['frames'],trimmed['source_frames']), (24,48))
        direct=prepare(original['source'],self.root/'trimmed-direct',start_frame=7,end_frame=31)
        self.assertEqual(pcm(direct['audio']),expected)
        result=render([self.clips[0],trimmed],[{'effect':'classic-mosh','duration':.5}],self.root/'trimmed-export')
        self.assertEqual(result['frames'],59)
        self.assertEqual(result['audio_samples'],59*2000)
        self.assertEqual(pcm(self.root/'trimmed-export/sequence.wav'),pcm(self.clips[0]['audio'])+expected[2000*4:])
        self.assertEqual(result['full_decode'],'passed')
        self.assertEqual(result['source_sha256'],[self.clips[0]['sha256'],original['sha256']])

    def test_speed_preserves_pitch_frames_and_sample_budget(self):
        original=self.clips[0]
        fast=prepare(original['source'],self.root/'speed-fast',speed=2,base=original)
        slow=prepare(original['source'],self.root/'speed-slow',speed=.5,base=original)
        self.assertEqual((fast['frames'],slow['frames']),(18,72))
        self.assertEqual((len(pcm(fast['audio'])),len(pcm(slow['audio']))),(18*2000*4,72*2000*4))
        source_rms=rms(pcm(original['audio']),.1,.4)
        self.assertAlmostEqual(rms(pcm(fast['audio']),.1,.4)/source_rms,1,delta=.15)
        self.assertAlmostEqual(rms(pcm(slow['audio']),.5,1.5)/source_rms,1,delta=.15)
        for clip,duration,offset in ((fast,.75,.1),(slow,3,1.0)):
            result=render([clip],[],self.root/f"speed-{clip['speed']:g}-export")
            self.assertEqual(result['frames'],clip['frames'])
            self.assertEqual(result['audio_samples'],clip['frames']*2000)
            self.assertEqual(result['full_decode'],'passed')
            decoded=subprocess.check_output(['ffmpeg','-v','error','-xerror','-i',str(self.root/f"speed-{clip['speed']:g}-export/sequence.mp4"),
                '-map','0:a:0','-ac','1','-ar','48000','-f','s16le','-'])
            samples=array('h',decoded)
            self.assertGreater(amplitude(samples,offset,440),10*amplitude(samples,offset,880))
            self.assertGreater(amplitude(samples,offset,440),10*amplitude(samples,offset,220))
            self.assertAlmostEqual(len(samples)/RATE,duration,delta=.002)
        self.assertEqual(digest(Path(original['source'])),original['sha256'])

    def test_audio_follow_remaps_motion_loop_and_false_stays_byte_identical(self):
        first,second=self.clips[0],self.clips[2]
        block=2000*4
        base={'effect':'motion-loop','duration':.5,'loop_frames':4}
        followed=render([first,second],[{**base,'audio_follow':True}],self.root/'audio-follow-loop')
        self.assertTrue(followed['boundaries'][0]['audio_follow'])
        self.assertEqual(followed['audio_samples'],followed['frames']*2000)
        self.assertEqual(followed['full_decode'],'passed')
        donors=followed['boundaries'][0]['b_vop_indices'];count=len(donors)
        donor_audio=pcm(second['audio'])
        expected=b''.join(donor_audio[index*block:(index+1)*block] for index in donors)+donor_audio[(count+1)*block:]
        output=pcm(self.root/'audio-follow-loop/sequence.wav');offset=first['frames']*block
        self.assertEqual(output[offset:offset+len(expected)],expected)
        self.assertEqual(len(output),followed['frames']*block)
        off=render([first,second],[{**base,'audio_follow':False}],self.root/'audio-follow-off')
        absent=render([first,second],[base],self.root/'audio-follow-absent')
        self.assertEqual(off['audio_samples'],followed['audio_samples'])
        self.assertEqual(absent['audio_samples'],followed['audio_samples'])
        self.assertEqual((self.root/'audio-follow-off/sequence.wav').read_bytes(),(self.root/'audio-follow-absent/sequence.wav').read_bytes())
        self.assertEqual((self.root/'audio-follow-off/sequence.m4v').read_bytes(),(self.root/'audio-follow-absent/sequence.m4v').read_bytes())
        self.assertFalse(off['boundaries'][0]['audio_follow'])
        self.assertEqual(off['full_decode'],'passed');self.assertEqual(absent['full_decode'],'passed')

    def test_audio_follow_reset_zero_silent_and_validation(self):
        first,second,silent=self.clips[0],self.clips[2],self.clips[1]
        block=2000*4
        reset=render([first,second],[{'effect':'reset-pulse','duration':.5,'loop_frames':4,'repeat':4,'audio_follow':True}],self.root/'audio-follow-reset')
        self.assertEqual(reset['full_decode'],'passed');self.assertEqual(reset['audio_samples'],reset['frames']*2000)
        donors=reset['boundaries'][0]['b_vop_indices'];zero_positions=[i for i,index in enumerate(donors) if index==0]
        self.assertTrue(zero_positions)
        donor_audio=pcm(second['audio']);output=pcm(self.root/'audio-follow-reset/sequence.wav');offset=first['frames']*block
        for position in zero_positions:
            self.assertEqual(output[offset+position*block:offset+(position+1)*block],donor_audio[:block])
        mixed=render([first,second,silent],[{'effect':'motion-loop','duration':.5,'loop_frames':4,'audio_follow':True},{'effect':'cut'}],self.root/'audio-follow-mixed-report')
        self.assertEqual([boundary['audio_follow'] for boundary in mixed['boundaries']],[True,False])
        self.assertEqual(mixed['full_decode'],'passed')
        silent_base={'effect':'motion-loop','duration':.5,'loop_frames':4}
        silent_on=render([first,silent],[{**silent_base,'audio_follow':True}],self.root/'audio-follow-silent-on')
        silent_off=render([first,silent],[{**silent_base,'audio_follow':False}],self.root/'audio-follow-silent-off')
        self.assertEqual(silent_on['full_decode'],'passed');self.assertEqual(silent_off['full_decode'],'passed')
        self.assertEqual(silent_on['audio_samples'],silent_on['frames']*2000)
        self.assertEqual(pcm(self.root/'audio-follow-silent-on/sequence.wav'),pcm(self.root/'audio-follow-silent-off/sequence.wav'))
        with self.assertRaises(ValueError):
            render([first,second],[{**silent_base,'audio_follow':'yes'}],self.root/'audio-follow-invalid')
        with self.assertRaises(ValueError):
            render([first,second],[{'effect':'frame-melt','duration':.5,'audio_follow':True}],self.root/'audio-follow-unsupported')

    def test_two_frame_trim_preserves_sample_invariant(self):
        original=self.clips[2]
        clip=prepare(original['source'],self.root/'audio-two-frames',start_frame=7,end_frame=9,base=original)
        self.assertEqual(pcm(clip['audio']),pcm(original['audio'])[7*2000*4:9*2000*4])
        result=render([clip],[],self.root/'audio-two-export')
        self.assertEqual(result['frames'],2);self.assertEqual(result['audio_samples'],4000)
        self.assertEqual(result['full_decode'],'passed')

if __name__=='__main__':
    unittest.main()
