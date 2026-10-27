"""Integration regressions: actual encoders, VOPs, reference decoding, legacy CLI."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from effects import process, prediction_plan
from compare import compare, frame
from mosh import digest, vops


def decode(path):
    return subprocess.check_output(['ffmpeg', '-v', 'error', '-xerror', '-r', '24',
        '-i', str(path), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])


class EngineRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        shutil.copytree(ROOT/'tools', cls.root/'tools', ignore=shutil.ignore_patterns('__pycache__'))
        # Exercise both original Phase 1 commands in an isolated clone of the tools.
        subprocess.run([sys.executable, str(cls.root/'tools/mosh.py'), '--synthetic'], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, str(cls.root/'tools/verify.py')], check=True, stdout=subprocess.DEVNULL)
        cls.a, cls.b = [cls.root/f'samples/clip-{label}.mp4' for label in ('a','b')]
        cls.hashes = [digest(cls.a), digest(cls.b)]
        cls.results = {}
        for effect in ('classic-mosh', 'frame-melt'):
            output = cls.root/'output'/f'{effect}.mp4'
            cls.results[effect] = process(effect, cls.a, cls.b, 2.5, output)
        cls.raw = {name: decode(cls.root/'output'/f'{name}.evidence/effect.m4v') for name in cls.results}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_classic_matches_legacy_prediction_bytes(self):
        header, legacy = vops(self.root/'work/mosh.m4v')
        new_header, new = vops(self.root/'output/classic-mosh.evidence/effect.m4v')
        self.assertEqual(new_header, header)
        self.assertEqual(new, legacy[:144+60])
        self.assertEqual(self.results['classic-mosh']['b_vop_indices'], list(range(1,61)))

    def test_frame_melt_repeats_compressed_predictions(self):
        _, bv = vops(self.root/'output/frame-melt.evidence/b.m4v')
        _, actual = vops(self.root/'output/frame-melt.evidence/effect.m4v')
        self.assertEqual(actual[144:], [bv[1+i//4] for i in range(60)])
        # Replaying a compressed P-frame is not holding a decoded frame.
        size = 640*480*3
        frames = [self.raw['frame-melt'][(144+i)*size:(145+i)*size] for i in range(4)]
        self.assertEqual(len(set(frames)), 4)

    def test_output_frames_and_visual_distinction(self):
        for result in self.results.values():
            self.assertEqual((result['probe']['streams'][0]['width'], result['probe']['streams'][0]['height']), (640, 480))
            self.assertEqual(result['output_frames'], 204)
            self.assertEqual(int(result['probe']['streams'][0]['nb_frames']), 204)
        size = 640*480*3
        classic, melt = [self.raw[k] for k in ('classic-mosh','frame-melt')]
        self.assertEqual(classic[:144*size], melt[:144*size])
        self.assertEqual(len(classic), 204*size)
        self.assertEqual(len(melt), 204*size)
        # Frame 180 is 1.5s into the transition; detect a material pixel difference.
        left, right = [data[180*size:181*size] for data in (classic,melt)]
        error = sum(abs(a-b) for a,b in zip(left,right))/size
        self.assertGreater(error, 2)

    def test_melt_supported_parameter_endpoints(self):
        for repeat in (2, 12):
            result = process('frame-melt', self.a, self.b, 0.5,
                             self.root/f'repeat-{repeat}.mp4', {'repeat': repeat})
            self.assertEqual(result['b_vop_indices'], [1+i//repeat for i in range(12)])
            self.assertEqual(result['output_frames'], 156)

    def test_motion_loop_replays_group_and_visually_differs(self):
        output = self.root/'loop.mp4'
        result = process('motion-loop', self.a, self.b, 2.5, output,
                         {'motion_start': .5, 'loop_frames': 8})
        _, donor = vops(self.root/'loop.evidence/b.m4v')
        _, actual = vops(self.root/'loop.evidence/effect.m4v')
        self.assertEqual(actual[144:], [donor[13+i%8] for i in range(60)])
        self.assertEqual(result['b_vop_indices'], [13+i%8 for i in range(60)])
        self.assertEqual(result['output_frames'], 204)
        self.assertEqual(result['parameters'], {'motion_start': .5, 'loop_frames': 8})
        self.assertNotEqual(frame(output, 144), frame(output, 152))
        selected = frame(output, 180)
        size = 640*480*3
        for effect in ('classic-mosh', 'frame-melt'):
            reference = self.raw[effect][180*size:181*size]
            error = sum(abs(a-b) for a,b in zip(selected,reference))/size
            self.assertGreater(error, 2, effect)

    def test_selected_motion_range_preserves_prediction_payloads(self):
        for effect in ('classic-mosh', 'frame-melt'):
            output = self.root/f'selected-{effect}.mp4'
            result = process(effect, self.a, self.b, .5, output, {'motion_start': .5})
            expected = [13+(i//4 if effect == 'frame-melt' else i) for i in range(12)]
            self.assertEqual(result['b_vop_indices'], expected)

    def test_loop_window_parameter_endpoints(self):
        for length in (2,48):
            result = process('motion-loop', self.a, self.b, 2.5,
                             self.root/f'loop-{length}.mp4', {'loop_frames': length})
            self.assertEqual(result['b_vop_indices'], [1+i%length for i in range(60)])

    def test_invalid_motion_windows(self):
        for kwargs in ({'motion_start': -1}, {'motion_start': float('nan')},
                       {'motion_start': 6}, {'loop_frames': 1}, {'loop_frames': 49},
                       {'loop_frames': 60}, {'motion_start': 5.8, 'loop_frames': 8}):
            with self.assertRaises(ValueError):
                prediction_plan(144, 'motion-loop', 60, **kwargs)
        with self.assertRaises(ValueError):
            prediction_plan(144, 'classic-mosh', 60, motion_start=4)
        with self.assertRaises(ValueError):
            prediction_plan(3, 'motion-loop', 2)

    def test_original_files_preserved(self):
        self.assertEqual([digest(self.a), digest(self.b)], self.hashes)

    def test_reject_unverified_effects_and_fake_parameters(self):
        for effect, params in [('motion-transfer', {}), ('classic-mosh', {'repeat': 4}), ('frame-melt', {'repeat': 1})]:
            with self.assertRaises(ValueError):
                process(effect, self.a, self.b, 2.5, self.root/'bad.mp4', params)
        with self.assertRaises(ValueError):
            process('classic-mosh', self.a, self.b, 10, self.root/'bad.mp4')
        with self.assertRaises(ValueError):
            process('classic-mosh', self.a, self.b, 1, self.a)
        with self.assertRaises(ValueError):
            process('classic-mosh', self.a, self.b, 6, self.root/'bad.mp4')
        with self.assertRaises(ValueError):
            compare(self.root/'comparison.mp4', self.b, 1, self.root)

if __name__ == '__main__':
    unittest.main()
