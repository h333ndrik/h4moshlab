"""Real render, source payload preservation and timeline-aligned release."""
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from effects import prediction_plan
from sequence import prepare, render
from mosh import vops, run


class LoopReleaseTests(unittest.TestCase):
    def test_release_invariants_and_invalid_settings(self):
        for count in (12, 24, 60, 144):
            indices, _ = prediction_plan(160, 'loop-release', count, loop_frames=8)
            self.assertEqual(len(indices), count)
            self.assertLess(len(set(indices)), count)
            self.assertEqual(indices[-count//2:], list(range(count-count//2+1, count+1)))
        for kwargs in ({'motion_start': .5},):
            with self.assertRaises(ValueError):
                prediction_plan(160, 'loop-release', 60, **kwargs)
        with self.assertRaises(ValueError):
            prediction_plan(160, 'loop-release', 8)

    def test_complete_sequence_payloads_audio_and_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, source in [('a', 'testsrc2=size=160x120:rate=24'), ('b', 'testsrc=size=160x120:rate=24')]:
                run('ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', source, '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '4', '-c:v', 'libx264', '-threads', '2', '-pix_fmt', 'yuv420p', '-c:a', 'aac', root/f'{name}.mp4')
            clips = [prepare(root/f'{name}.mp4', root/name) for name in ('a', 'b')]
            render(clips, [{'effect':'loop-release','duration':2.5,'loop_frames':8}], root/'render')
            _, av = vops(Path(clips[0]['normalized']))
            _, bv = vops(Path(clips[1]['normalized']))
            _, actual = vops(root/'render/sequence.m4v')
            indices, _ = prediction_plan(len(bv), 'loop-release', 60, loop_frames=8)
            self.assertEqual(actual, av + [bv[i] for i in indices] + bv[61:])
            self.assertEqual([p[4] >> 6 for p in actual].count(0), 1)
            normal = av + bv[1:]
            self.assertNotEqual(actual, normal)
            subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(root/'render/sequence.mp4'),'-f','null','-'], check=True)
