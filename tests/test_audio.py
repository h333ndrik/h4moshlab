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
from mosh import probe, run
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

if __name__=='__main__':
    unittest.main()
