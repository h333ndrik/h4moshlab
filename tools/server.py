#!/usr/bin/env python3
"""Local editor server: Python stdlib, FFmpeg, no build step. Bind loopback only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import shutil
import tempfile
import threading
from urllib.parse import unquote, urlsplit
import uuid

from sequence import prepare, render

ROOT = Path(__file__).resolve().parents[1]
MAX_UPLOAD = 128*1024*1024


class App:
    def __init__(self, root):
        self.root = Path(root)
        self.clips = {}
        self.jobs = {}
        self.lock = threading.Lock()
        self.busy = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=1)

    def work(self, job_id, clips, transitions):
        def progress(stage, fraction):
            with self.lock:
                self.jobs[job_id].update(stage=stage, progress=fraction)
        try:
            result = render(clips, transitions, self.root/job_id, progress)
            with self.lock:
                self.jobs[job_id].update(status='ready', result=result, url=f'/media/job/{job_id}')
        except Exception as exc:
            with self.lock:
                self.jobs[job_id].update(status='error', error=str(exc))
        finally:
            self.busy.release()


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(120)

        def log_message(self, fmt, *args):
            pass

        def send_json(self, code, data):
            payload = json.dumps(data).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)

        def allowed(self):
            host = self.headers.get('Host', '')
            valid = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            origin = self.headers.get('Origin')
            return host in valid and (not origin or origin in {f'http://{h}' for h in valid})

        def do_POST(self):
            if not self.allowed():
                return self.send_json(403, {'error': 'Local same-origin requests only.'})
            if not app.busy.acquire(blocking=False):
                return self.send_json(409, {'error': 'Processing is already running.'})
            owned = True
            try:
                length = int(self.headers.get('Content-Length', 0))
                if self.path == '/api/clips':
                    if not 0 < length <= MAX_UPLOAD:
                        return self.send_json(413, {'error': 'Choose a video smaller than 128 MiB.'})
                    if len(app.clips) >= 12:
                        raise ValueError('Maximum 12 clips. Remove one first.')
                    clip_id = uuid.uuid4().hex
                    directory = app.root/clip_id
                    directory.mkdir()
                    source = directory/'source'
                    try:
                        with source.open('wb') as target:
                            remaining = length
                            while remaining:
                                chunk = self.rfile.read(min(1024*1024, remaining))
                                if not chunk:
                                    raise ValueError('Incomplete upload.')
                                target.write(chunk)
                                remaining -= len(chunk)
                        clip = prepare(source, directory)
                        clip.update(id=clip_id, name=unquote(self.headers.get('X-Filename', 'video'))[:180])
                        with app.lock:
                            app.clips[clip_id] = clip
                    except Exception:
                        shutil.rmtree(directory, ignore_errors=True)
                        raise
                    return self.send_json(201, {k: clip[k] for k in ('id','name','frames','duration')} |
                                          {'preview': f'/media/clip/{clip_id}', 'thumbnail': f'/media/thumb/{clip_id}'})
                if self.path != '/api/jobs':
                    return self.send_json(404, {'error': 'Unknown endpoint.'})
                if not 0 < length <= 16384:
                    raise ValueError('Invalid sequence request.')
                body = json.loads(self.rfile.read(length))
                ids, transitions = body['clips'], body['transitions']
                if not isinstance(ids, list) or not 1 <= len(ids) <= 12 or len(ids) != len(set(ids)):
                    raise ValueError('Choose 1–12 distinct clips.')
                if not isinstance(transitions, list) or len(transitions) != len(ids)-1 or not all(isinstance(t, dict) for t in transitions):
                    raise ValueError('One transition setting is needed per boundary.')
                clips = [dict(app.clips[i]) for i in ids]
                job_id = uuid.uuid4().hex
                with app.lock:
                    app.jobs[job_id] = {'id': job_id, 'status': 'processing', 'stage': 'Preparing sequence', 'progress': 0}
                app.pool.submit(app.work, job_id, clips, transitions)
                owned = False
                self.send_json(202, {'id': job_id})
            except (ValueError, KeyError, TypeError) as exc:
                self.send_json(400, {'error': str(exc)})
            except Exception:
                self.send_json(422, {'error': 'Video processing failed. Check the format and try another file.'})
            finally:
                if owned:
                    app.busy.release()

        def do_DELETE(self):
            if not self.allowed():
                return self.send_json(403, {'error': 'Local same-origin requests only.'})
            if not app.busy.acquire(blocking=False):
                return self.send_json(409, {'error': 'Wait until processing finishes.'})
            try:
                clip_id = self.path.removeprefix('/api/clips/') if self.path.startswith('/api/clips/') else ''
                with app.lock:
                    clip = app.clips.pop(clip_id, None)
                if not clip:
                    return self.send_json(404, {'error': 'Unknown clip.'})
                shutil.rmtree(Path(clip['source']).parent)
                self.send_json(200, {'removed': clip_id})
            finally:
                app.busy.release()

        def do_GET(self):
            if not self.allowed():
                return self.send_json(403, {'error': 'Local requests only.'})
            path = urlsplit(self.path).path
            if path == '/api/clips':
                with app.lock:
                    clips = [{k:c[k] for k in ('id', 'name', 'frames', 'duration')} |
                             {'preview': f'/media/clip/{c["id"]}', 'thumbnail': f'/media/thumb/{c["id"]}'}
                             for c in app.clips.values()]
                return self.send_json(200, {'clips': clips})
            if path.startswith('/api/jobs/'):
                with app.lock:
                    result = dict(app.jobs.get(path.rsplit('/', 1)[1], {}))
                return self.send_json(200 if result else 404, result or {'error': 'Unknown job.'})
            if path.startswith('/media/'):
                parts = path.split('/')
                file = None
                if len(parts) == 4:
                    kind, identifier = parts[2:]
                    if kind in ('clip', 'thumb') and identifier in app.clips:
                        file = Path(app.clips[identifier]['preview'])
                        if kind == 'thumb':
                            file = file.parent/'thumb.jpg'
                    if kind == 'job' and app.jobs.get(identifier, {}).get('status') == 'ready':
                        file = app.root/identifier/'sequence.mp4'
                if file:
                    return self.send_file(file, download='download' in urlsplit(self.path).query)
            static = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
            if path in static:
                return self.send_file(ROOT/'web'/static[path])
            self.send_json(404, {'error': 'Not found.'})

        def send_file(self, file, download=False):
            size = file.stat().st_size
            start, end, status = 0, size-1, 200
            requested = self.headers.get('Range')
            if requested:
                match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
                try:
                    if not match or not any(match.groups()):
                        raise ValueError()
                    left, right = match.groups()
                    if left:
                        start = int(left)
                        end = min(int(right), end) if right else end
                    else:
                        start = max(0, size-int(right))
                    if not 0 <= start <= end < size:
                        raise ValueError()
                    status = 206
                except ValueError:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
            self.send_response(status)
            self.send_header('Content-Type', mimetypes.guess_type(file)[0] or 'application/octet-stream')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(end-start+1))
            self.send_header('Cache-Control', 'no-store')
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="h4-mosh-lab.mp4"')
            self.end_headers()
            try:
                with file.open('rb') as source:
                    source.seek(start)
                    remaining = end-start+1
                    while remaining:
                        chunk = source.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    (ROOT/'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='editor-', dir=ROOT/'work') as directory:
        app = App(directory)
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(app))
        print(f'Local editor listening on port {args.port}; Ctrl+C to stop. Session files are temporary.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            app.pool.shutdown(wait=True)

if __name__ == '__main__':
    main()
