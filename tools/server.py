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
import traceback
import threading
from urllib.parse import parse_qs, unquote, urlsplit
import uuid

from sequence import prepare, render
import lan

ROOT = Path(__file__).resolve().parents[1]
MAX_UPLOAD = 128*1024*1024


def processing_error(exc):
    if isinstance(exc, FileNotFoundError) and Path(str(exc.filename)).name in ('ffmpeg', 'ffprobe'):
        return ('FFmpeg/FFprobe was not found. On a Mac run: brew install ffmpeg '
                '(includes ffprobe), then restart this server from that terminal.')
    return 'Video processing failed. Copy the detailed error from the server terminal so the cause can be diagnosed.'


class App:
    def __init__(self, root, lan_address=None):
        self.root = Path(root)
        self.lan_address = lan_address
        self.lan_key = lan.access_key() if lan_address else None
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
            traceback.print_exc()
            with self.lock:
                self.jobs[job_id].update(status='error', error=str(exc) if isinstance(exc, ValueError) else processing_error(exc))
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
            if app.lan_address:
                valid.add(f'{app.lan_address}:{self.server.server_port}')
            origin = self.headers.get('Origin')
            return host in valid and (not origin or origin in {f'http://{h}' for h in valid})

        def do_POST(self):
            if not self.allowed():
                return self.send_json(403, {'error': 'Local same-origin requests only.'})
            if not lan.authorized(self.headers, self.client_address, app.lan_key):
                return self.send_json(401, {'error': 'Open the phone link from the Mac first.'})
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
            except Exception as exc:
                traceback.print_exc()
                code = 503 if isinstance(exc, FileNotFoundError) else 422
                self.send_json(code, {'error': processing_error(exc)})
            finally:
                if owned:
                    app.busy.release()

        def do_DELETE(self):
            if not self.allowed():
                return self.send_json(403, {'error': 'Local same-origin requests only.'})
            if not lan.authorized(self.headers, self.client_address, app.lan_key):
                return self.send_json(401, {'error': 'Open the phone link from the Mac first.'})
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
            parsed = urlsplit(self.path)
            path = parsed.path
            pairing = parse_qs(parsed.query).get('pair', [])
            if path == '/' and pairing:
                if len(pairing) != 1 or not lan.matches(pairing[0], app.lan_key):
                    return self.send_json(401, {'error': 'This phone link is invalid or expired. Copy the current link from the Mac.'})
                self.send_response(303)
                self.send_header('Set-Cookie', lan.cookie(app.lan_key))
                self.send_header('Location', '/')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if not lan.authorized(self.headers, self.client_address, app.lan_key):
                return self.send_json(401, {'error': 'Open the phone link from the Mac first.'})
            if path == '/api/connection':
                url = f'http://{app.lan_address}:{self.server.server_port}/?pair={app.lan_key}' if app.lan_address and lan.loopback(self.client_address) else None
                return self.send_json(200, {'phone_url': url})
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
            static = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css', '/cursor.js': 'cursor.js', '/h4-cursor.svg': 'h4-cursor.svg'}
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
    parser.add_argument('--lan', action='store_true', help='Allow paired phones on the same trusted Wi-Fi')
    parser.add_argument('--lan-address', help='Optional private Mac IPv4 if automatic Wi-Fi detection chooses another interface')
    args = parser.parse_args()
    if args.lan_address and not args.lan:
        parser.error('--lan-address requires --lan')
    address = (args.lan_address or lan.discover_address()) if args.lan else None
    if args.lan and (not address or not lan.private_address(address)):
        parser.error('No private Wi-Fi IPv4 found. Join your Wi-Fi or provide --lan-address with the Mac private IPv4.')
    missing = [name for name in ('ffmpeg', 'ffprobe') if not shutil.which(name)]
    if missing:
        parser.exit(2, 'Missing: ' + ', '.join(missing) + '. On a Mac run: brew install ffmpeg (includes ffprobe), then restart this server from that terminal.\n')
    (ROOT/'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='editor-', dir=ROOT/'work') as directory:
        app = App(directory, address)
        server = ThreadingHTTPServer(('0.0.0.0' if args.lan else '127.0.0.1', args.port), handler_for(app))
        print(f'Local editor listening on port {args.port}; Ctrl+C to stop. Session files are temporary.', flush=True)
        if address:
            print(f'Phone link (same Wi-Fi): http://{address}:{args.port}/?pair={app.lan_key}', flush=True)
            print('Use the complete link once to pair the phone. It expires when this server stops.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            app.pool.shutdown(wait=True)

if __name__ == '__main__':
    main()
