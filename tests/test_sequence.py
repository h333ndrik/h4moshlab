"""Full sequence regression, including >6s input and reference restoration."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from sequence import prepare, render
from mosh import digest, probe, run, vops
from server import App, handler_for
from http.server import ThreadingHTTPServer
from http.client import HTTPConnection
import json
import subprocess
import threading
import time


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
                       {'effect': 'frame-melt', 'duration': .5, 'repeat': 3, 'ending': 'reset'}]
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

    def test_motion_loop_selected_range_and_clean_restoration(self):
        result = render(self.clips[:2], [{'effect': 'motion-loop', 'duration': .5,
                         'loop_frames': 4, 'motion_start': .25, 'ending': 'reset'}], self.root/'loop')
        _, actual = vops(self.root/'loop/sequence.m4v')
        _, donor = vops(Path(self.clips[1]['normalized']))
        self.assertEqual(actual[174:186], [donor[7+i%4] for i in range(12)])
        self.assertEqual(result['frames'], 221)
        self.assertEqual(result['boundaries'][0]['motion_start'], .25)
        self.assertEqual(actual[186][4] >> 6, 0)

    def test_loop_and_melt_flow_without_an_injected_iframe(self):
        _, donor = vops(Path(self.clips[1]['normalized']))
        for effect in ('motion-loop', 'frame-melt'):
            transition = {'effect': effect, 'duration': .5, 'loop_frames': 4,
                          'repeat': 3, 'motion_start': .25}
            result = render(self.clips[:2], [transition], self.root/f'flow-{effect}')
            _, actual = vops(self.root/f'flow-{effect}/sequence.m4v')
            self.assertEqual(actual[186:], donor[13:])
            self.assertEqual([i for i,p in enumerate(actual) if p[4] >> 6 == 0], [0])
            self.assertEqual(result['frames'], 221)
            self.assertEqual(result['boundaries'][0]['ending'], 'flow')
            self.assertIsNone(result['boundaries'][0]['reset_frame'])
            self.assertEqual(result['boundaries'][0]['release_b_vop_indices'], list(range(13,48)))
            self.assertEqual(result['full_decode'], 'passed')

    def test_flow_followed_by_cut_resets_only_at_the_cut(self):
        result = render(self.clips, [{'effect': 'motion-loop', 'duration': .5, 'loop_frames': 4},
                                   {'effect': 'cut'}], self.root/'flow-cut')
        _, actual = vops(self.root/'flow-cut/sequence.m4v')
        self.assertEqual([i for i,p in enumerate(actual) if p[4] >> 6 == 0], [0,221])
        self.assertEqual(result['frames'], 257)

    def test_invalid_transition_does_not_render(self):
        for transitions in ([{'effect': 'motion-transfer', 'duration': .5}],
                            [{'effect': 'classic-mosh', 'duration': 3}],
                            [{'effect': 'frame-melt', 'duration': .5, 'repeat': 1}],
                            [{'effect': 'motion-loop', 'duration': .5, 'loop_frames': 4, 'ending': 'fade'}], []):
            with self.assertRaises(ValueError):
                render(self.clips[:2], transitions, self.root/'invalid')
        self.assertFalse((self.root/'invalid').exists())

    def test_duplicate_source_http_render_restore_and_timeline_limit(self):
        app=App(self.root/'duplicate-api');app.root.mkdir()
        identifier='a'*32
        app.clips[identifier]={**self.clips[1], 'id':identifier, 'name':'same.mp4'}
        app.views[(identifier,'original')]=dict(app.clips[identifier])
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(app))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(path,body=None):
            connection=HTTPConnection('127.0.0.1',server.server_port)
            connection.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,{'Content-Type':'application/json'})
            response=connection.getresponse();status=response.status;data=json.loads(response.read());connection.close()
            return status,data
        try:
            self.assertEqual(request('/api/sequence/restore',{'clips':[identifier]*2,'looks':['original','negative-bw']})[0],200)
            self.assertEqual(len(app.clips),1)
            self.assertEqual(request('/api/sequence/restore',{'clips':[identifier]*13})[0],400)
            self.assertEqual(request('/api/jobs',{'clips':[identifier]*13,'transitions':[{'effect':'cut'}]*12})[0],400)
            status,job=request('/api/jobs',{'clips':[identifier]*2,'looks':['original','negative-bw'],'transitions':[{'effect':'classic-mosh','duration':.5}]})
            self.assertEqual(status,202)
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                _,result=request('/api/jobs/'+job['id'])
                if result['status']!='processing':break
                time.sleep(.02)
            self.assertEqual(result['status'],'ready',result)
            self.assertEqual(result['result']['frames'],95)
            self.assertEqual(result['result']['full_decode'],'passed')
            self.assertEqual(result['result']['source_sha256'],[self.clips[1]['sha256']]*2)
            self.assertEqual(len(app.clips),1)
            self.assertEqual(digest(Path(self.clips[1]['source'])),self.clips[1]['sha256'])
            # The maximum counts timeline entries, not source files.
            status,job=request('/api/jobs',{'clips':[identifier]*12,'transitions':[{'effect':'cut'}]*11})
            self.assertEqual(status,202)
        finally:
            server.shutdown();server.server_close();thread.join();app.pool.shutdown(wait=True)

    def test_duplicate_project_refs_and_legacy_hash_matching(self):
        script="""
const assert=require('node:assert/strict');
const {validateProject,matchProject}=require('./web/editor-tools.js');
const hash='a'.repeat(64),clip={name:'renamed.mov',sha256:hash,frames:48};
const project={format:'h4-mosh-project',version:1,sound:true,clips:[{...clip,source_ref:0},{...clip,source_ref:0}],transitions:[{effect:'classic-mosh',duration:.5}]};
const saved=validateProject(JSON.parse(JSON.stringify(project)));
assert.deepEqual(saved.clips.map(c=>c.source_ref),[0,0]);
assert.deepEqual(matchProject(saved,[{id:'one',sha256:hash}]).map(c=>c.id),['one','one']);
assert.deepEqual(matchProject(saved,[{id:'wrong',sha256:'b'.repeat(64)}]),[null,null]);
const legacy=validateProject({...project,clips:[clip,clip]});
assert.equal(matchProject(legacy,[{id:'one',sha256:hash}])[1],null);
assert.throws(()=>validateProject({...project,clips:[{...clip,source_ref:1},clip]}));
const ordered=validateProject({...project,order:['c'.repeat(32),'c'.repeat(32)],clips:[clip,clip]});
assert.deepEqual(ordered.order,['c'.repeat(32),'c'.repeat(32)]);
assert.deepEqual(matchProject(ordered,[{id:'one',sha256:hash}]).map(c=>c.id),['one','one']);
assert.throws(()=>validateProject({...project,order:['c'.repeat(32)]}));

"""
        subprocess.run(['node','-e',script],cwd=Path(__file__).resolve().parents[1],check=True)

if __name__ == '__main__':
    unittest.main()
