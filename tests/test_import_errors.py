"""Missing local tools must not masquerade as an unsupported MOV format."""
import contextlib
import errno
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from server import App, handler_for, main


class ImportErrorTests(unittest.TestCase):
    def test_missing_ffprobe_is_actionable_and_releases_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            app = App(directory)
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(app))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}/api/clips'
            try:
                missing = FileNotFoundError(errno.ENOENT, 'No such file', 'ffprobe')
                with patch('server.prepare', side_effect=missing), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(urllib.error.HTTPError) as response:
                        urllib.request.urlopen(urllib.request.Request(url, data=b'mov bytes'))
                    self.assertEqual(response.exception.code, 503)
                    message = json.load(response.exception)['error']
                self.assertIn('brew install ffmpeg', message)
                self.assertIn('ffprobe', message)
                self.assertEqual(app.clips, {})
                self.assertEqual(list(Path(directory).iterdir()), [])
                self.assertTrue(app.busy.acquire(timeout=1))
                app.busy.release()
                # A second request reaches preparation rather than a stuck 409 gate.
                with patch('server.prepare', side_effect=ValueError('Video is too long.')):
                    with self.assertRaises(urllib.error.HTTPError) as response:
                        urllib.request.urlopen(urllib.request.Request(url, data=b'mov bytes'))
                    self.assertEqual(response.exception.code, 400)
                    self.assertIn('too long', json.load(response.exception)['error'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                app.pool.shutdown(wait=True)

    def test_startup_reports_missing_tools_before_binding(self):
        with patch('server.shutil.which', return_value=None), patch('sys.argv', ['server.py']), contextlib.redirect_stderr(io.StringIO()) as log:
            with self.assertRaises(SystemExit) as result:
                main()
        self.assertEqual(result.exception.code, 2)
        self.assertIn('ffmpeg, ffprobe', log.getvalue())
        self.assertIn('brew install ffmpeg', log.getvalue())

if __name__ == '__main__':
    unittest.main()
