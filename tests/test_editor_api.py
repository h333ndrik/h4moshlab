"""Real local HTTP checks for undo retention, clip looks and validated controls."""
from http.server import ThreadingHTTPServer
from http.client import HTTPConnection
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from server import App,handler_for
from mosh import run

class EditorAPITests(unittest.TestCase):
    def test_archive_restore_looks_and_validation_are_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'original.mp4'
            run('ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=160x120:rate=24','-t','2','-c:v','libx264','-threads','2','-pix_fmt','yuv420p',source)
            app=App(root/'session');app.root.mkdir()
            server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(app));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def request(path,method='GET',data=None,headers=None):
                connection=HTTPConnection('127.0.0.1',server.server_port)
                payload=json.dumps(data).encode() if isinstance(data,dict) else data
                connection.request(method,path,body=payload,headers=headers or {})
                response=connection.getresponse();body=response.read();code=response.status;connection.close()
                return code,json.loads(body)
            try:
                code,clip=request('/api/clips','POST',source.read_bytes(),{'X-Filename':'original.mp4'})
                self.assertEqual(code,201);self.assertEqual(clip['look'],'original');self.assertEqual(len(clip['sha256']),64)
                identifier=clip['id'];original_path=Path(app.clips[identifier]['source'])
                self.assertEqual(request('/api/clips/'+identifier,'DELETE')[0],200)
                self.assertEqual(request('/api/clips')[1]['clips'],[])
                self.assertTrue(original_path.exists())
                self.assertEqual(request('/api/library')[1]['clips'][0]['sha256'],clip['sha256'])
                self.assertEqual(request('/api/sequence/restore','POST',{'clips':[identifier],'looks':{identifier:'negative-bw'}})[0],200)
                self.assertEqual(app.clips[identifier]['look'],'negative-bw')
                # Invalid operations cannot partly replace the active sequence.
                self.assertEqual(request('/api/sequence/restore','POST',{'clips':[identifier,'missing']})[0],400)
                self.assertEqual(list(app.clips),[identifier])
                self.assertEqual(request('/api/clips/'+identifier+'/look','POST',{'look':'fake'})[0],400)
                self.assertEqual(app.clips[identifier]['look'],'negative-bw')
                self.assertEqual(request('/api/clips/'+identifier+'/look','POST',{'look':'original'})[0],200)
                self.assertEqual(request('/api/settings','POST',{'action':'tempo','effect':'reset-pulse','bpm':120,'beats':1})[1]['loop_frames'],12)
                self.assertEqual(request('/api/settings','POST',{'action':'tempo','effect':'classic-mosh','bpm':120,'beats':1})[0],400)
                self.assertEqual(request('/api/settings','POST',{'action':'preset','effect':'frame-melt','preset':0,'frames':48})[0],200)
                self.assertEqual(request('/api/settings','POST',{'action':'validate_project','frames':[48,48],'transitions':[{'effect':'reset-pulse','duration':1,'loop_frames':8,'tempo':{'bpm':120,'beats':1}}]})[0],400)
                self.assertEqual(request('/api/sequence/restore','POST',{'clips':[]},{'Origin':'https://elsewhere.example'})[0],403)
                self.assertEqual(list(app.clips),[identifier])
            finally:
                server.shutdown();server.server_close();thread.join();app.pool.shutdown(wait=True)
