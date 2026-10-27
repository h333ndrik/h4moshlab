"""Full sequence regression, including >6s input and reference restoration."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from sequence import prepare, render
from mosh import digest, probe, run, vops


class SequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.clips = []
        for i, duration in enumerate((7.25, 2, 1.5)):
            source = cls.root/f'source-{i}.mp4'
            run('ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                f'testsrc2=size=320x240:rate=24:duration={duration}', '-vf', f'hue=h={i*70}',
                '-c:v', 'libx264', '-threads', '2', source)
            cls.clips.append(prepare(source, cls.root/f'clip-{i}'))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_multiple_real_transitions_and_restoration(self):
        transitions = [{'effect': 'classic-mosh', 'duration': .5},
                       {'effect': 'frame-melt', 'duration': .5, 'repeat': 3}]
        progress = []
        result = render(self.clips, transitions, self.root/'effects', lambda stage, p: progress.append(p))
        self.assertEqual(self.clips[0]['frames'], 174)  # Full clip, not Phase 1's six-second cap.
        self.assertEqual(result['size'], '640x480')
        video = probe(self.root/'effects/sequence.mp4')['streams'][0]
        self.assertEqual((video['width'], video['height']), (640, 480))
        self.assertEqual(result['frames'], 174+47+35)
        self.assertEqual([b['frame'] for b in result['boundaries']], [174, 221])
        _, actual = vops(self.root/'effects/sequence.m4v')
        _, b = vops(Path(self.clips[1]['normalized']))
        _, c = vops(Path(self.clips[2]['normalized']))
        self.assertEqual(actual[174:186], b[1:13])
        self.assertEqual(actual[221:233], [c[1+i//3] for i in range(12)])
        self.assertEqual([i for i,p in enumerate(actual) if p[4] >> 6 == 0], [0, 186, 233])
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(progress[-1], 1)
        for clip in self.clips:
            self.assertEqual(digest(Path(clip['source'])), clip['sha256'])

    def test_cut_reordering_and_single_clip(self):
        ordered = list(reversed(self.clips))
        result = render(ordered, [{'effect': 'cut'}, {'effect': 'cut'}], self.root/'cuts')
        _, actual = vops(self.root/'cuts/sequence.m4v')
        expected = []
        for clip in ordered:
            expected += vops(Path(clip['normalized']))[1]
        self.assertEqual(actual, expected)
        self.assertEqual(result['frames'], 258)
        single = render([self.clips[1]], [], self.root/'single')
        self.assertEqual(single['frames'], 48)

    def test_invalid_transition_does_not_render(self):
        for transitions in ([{'effect': 'motion-transfer', 'duration': .5}],
                            [{'effect': 'classic-mosh', 'duration': 3}],
                            [{'effect': 'frame-melt', 'duration': .5, 'repeat': 1}], []):
            with self.assertRaises(ValueError):
                render(self.clips[:2], transitions, self.root/'invalid')
        self.assertFalse((self.root/'invalid').exists())

if __name__ == '__main__':
    unittest.main()
