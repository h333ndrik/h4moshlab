"""Exercise pairing over real HTTP with a simulated non-loopback peer."""
from http.server import ThreadingHTTPServer
from http.client import HTTPConnection
from pathlib import Path
import json
import sys
import tempfile
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import lan
from server import App, handler_for


class LanTests(unittest.TestCase):
    def test_private_address_and_expired_cookie(self):
        for value in ('192.168.1.2', '10.0.0.2', '172.16.0.1'):
            self.assertTrue(lan.private_address(value))
        for value in ('127.0.0.1', '0.0.0.0', '8.8.8.8', '::1', 'hostname'):
            self.assertFalse(lan.private_address(value))
        key = lan.access_key()
        headers = {'Cookie': lan.cookie(key)}
        self.assertTrue(lan.authorized(headers, ('192.168.1.9', 1), key))
        self.assertFalse(lan.authorized(headers, ('192.168.1.9', 1), lan.access_key()))
        self.assertTrue(lan.authorized({}, ('127.0.0.1', 1), key))

    def test_http_pairing_and_origin_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            app = App(directory, '192.168.1.2')
            class Remote(handler_for(app)):
                def setup(self):
                    super().setup()
                    self.client_address = ('192.168.1.9', self.client_address[1])
            server = ThreadingHTTPServer(('127.0.0.1', 0), Remote)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def request(path, method='GET', headers=None):
                connection = HTTPConnection('127.0.0.1', server.server_port)
                connection.request(method, path, headers=headers or {})
                response = connection.getresponse()
                result = response.status, dict(response.getheaders()), response.read()
                connection.close()
                return result
            try:
                self.assertEqual(request('/api/clips')[0], 401)
                self.assertEqual(request('/api/clips', 'POST')[0], 401)
                self.assertEqual(request('/?pair=wrong')[0], 401)
                code, headers, _ = request('/?pair=' + app.lan_key)
                self.assertEqual(code, 303)
                self.assertEqual(headers['Location'], '/')
                self.assertIn('HttpOnly', headers['Set-Cookie'])
                self.assertIn('SameSite=Strict', headers['Set-Cookie'])
                cookie = {'Cookie': headers['Set-Cookie'].split(';')[0]}
                self.assertEqual(request('/api/clips', headers=cookie)[0], 200)
                self.assertIsNone(json.loads(request('/api/connection', headers=cookie)[2])['phone_url'])
                self.assertEqual(request('/api/clips', headers={**cookie, 'Host': 'evil.example'})[0], 403)
                self.assertEqual(request('/api/jobs', 'POST', {**cookie, 'Origin': 'https://evil.example'})[0], 403)
                self.assertEqual(request('/api/clips', headers={**cookie, 'Host': f'192.168.1.2:{server.server_port}'})[0], 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                app.pool.shutdown(wait=True)

if __name__ == '__main__':
    unittest.main()
