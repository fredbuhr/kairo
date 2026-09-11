"""Real loopback HTTP/TLS checks of the runner; not a Nevolium deployment/capacity proof."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from access import MAX_RESPONSE_BYTES, PROTECTED_PATHS, READ_PATHS

TOKEN = 'fixture.' + base64.urlsafe_b64encode(b'{"sub":"fixture-owner"}').decode().rstrip('=') + '.not-a-real-signature'
TODAY = {'day': '2026-09-11', 'timezone': 'UTC', 'next_cursors': {},
         **{key: [] for key in ('overdue', 'in_progress', 'due_today', 'planned', 'completed_today', 'backlog')}}
CAPACITY = {'waiting': 0, 'active': 0, 'concurrency_limit': 4, 'pending_limit': 32}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    scenario = 'good'
    requests = 0
    paths = set()
    load_started = False
    lock = threading.Lock()

    def reply(self, status, body=b'{}', content_type='application/json', **headers):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            self.serve()
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
            pass

    def serve(self):
        with self.lock:
            type(self).requests += 1
            self.paths.add(self.path)
            if self.path == READ_PATHS[0]:
                type(self).load_started = True
        if self.path in PROTECTED_PATHS:
            self.reply(405 if self.scenario == 'internal-leak' else 404)
            return
        if self.headers.get('Authorization') != 'Bearer ' + TOKEN:
            self.reply(200 if self.scenario == 'anonymous' else 401)
            return
        if self.scenario == 'pressure' and self.load_started:
            self.reply(429)
            return
        if self.scenario == 'html':
            self.reply(200, b'<html>wrong application</html>', 'text/html')
            return
        if self.scenario == 'wrong-shape':
            self.reply(200)
            return
        if self.scenario == 'redirect':
            self.reply(302, Location=f'https://localhost:{self.server.server_port}/credential-sink')
            return
        if self.scenario == 'oversized':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(MAX_RESPONSE_BYTES + 1))
            self.end_headers()
            return
        if self.scenario == 'slow':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', '12')
            self.end_headers()
            for _ in range(12):
                self.wfile.write(b' ')
                self.wfile.flush()
                time.sleep(1)
            return
        payload = [] if self.path.startswith('/v1/projects?') else TODAY if self.path.startswith('/v1/today?') else CAPACITY
        self.reply(200, json.dumps(payload).encode())

    def log_message(self, *_args):
        pass


class Server(ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True


def exercise(server, action, scenario='good', ca_file=None, hostname='localhost'):
    Handler.scenario = scenario
    Handler.requests = 0
    Handler.paths = set()
    Handler.load_started = False
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / 'tokens.json').write_text(json.dumps([TOKEN]))
        scheme = 'https' if isinstance(server.socket, ssl.SSLSocket) else 'http'
        command = [sys.executable, str(Path(__file__).with_name('target.py')), action,
                   '--core', f'{scheme}://{hostname}:{server.server_port}',
                   '--tokens-file', str(path / 'tokens.json'), '--output', str(path / 'result.json'),
                   '--p95-seconds', '10']
        if ca_file:
            command += ['--ca-file', str(ca_file)]
        # These ambient proxies must never receive credentials or prevent loopback access.
        env = dict(os.environ, HTTPS_PROXY='http://127.0.0.1:1', HTTP_PROXY='http://127.0.0.1:1', NO_PROXY='')
        result = subprocess.run(command, capture_output=True, text=True, timeout=120, env=env)
        report = json.loads((path / 'result.json').read_text())
        if TOKEN in result.stdout + result.stderr + json.dumps(report):
            raise AssertionError('Token leaked into runner output')
        return result, report


class Contract(unittest.TestCase):
    def setUp(self):
        self.server = Server(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def test_virtual_clients_are_not_invented_users(self):
        result, report = exercise(self.server, 'load')
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [r for r in report['cases'] if r['id'].startswith('read-load-')]
        self.assertEqual([r['virtual_clients'] for r in rows], [1, 10, 100, 1000])
        self.assertEqual(Handler.requests, 3333 + 10)
        self.assertEqual(report['authenticated_subject_count'], 1)
        self.assertEqual(report['d04_gate'], 'incomplete')
        self.assertTrue(report['anonymous_access_rejected'])
        self.assertFalse(report['transport']['certificate_verification_enabled'])
        self.assertTrue(all(r['authenticated_subjects_used'] == 1 and r['status'] == 'passed' for r in rows))

    def test_pressure_failure_stops_before_next_stage(self):
        result, report = exercise(self.server, 'load', 'pressure')
        self.assertNotEqual(result.returncode, 0)
        rows = [r for r in report['cases'] if r['id'].startswith('read-load-')]
        self.assertEqual(Handler.requests, 3 + 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'failed')
        self.assertEqual(rows[0]['errors'], 3)


class TLSContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.cert = root / 'cert.pem'
        cls.key = root / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(cls.key), '-out', str(cls.cert), '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'],
                       check=True, capture_output=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.server = Server(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert, self.key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    tearDown = Contract.tearDown

    def test_tls_preflight_without_load(self):
        result, report = exercise(self.server, 'preflight', ca_file=self.cert)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Handler.requests, 10)
        self.assertEqual(report['preflight']['status'], 'passed')
        self.assertTrue(report['transport']['certificate_verification_enabled'])
        self.assertEqual(report['transport']['trust_source'], 'operator-ca')

    def test_misrouting_denials_and_size_stop_before_load(self):
        for scenario in ('anonymous', 'html', 'wrong-shape', 'internal-leak', 'redirect', 'oversized'):
            with self.subTest(scenario=scenario):
                result, report = exercise(self.server, 'load', scenario, ca_file=self.cert)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report['preflight']['status'], 'failed')
                self.assertFalse(any(r['id'].startswith('read-load-') for r in report['cases']))
                self.assertNotIn('/credential-sink', Handler.paths)

    def test_untrusted_ca_and_wrong_hostname_are_rejected(self):
        for ca, hostname in ((None, 'localhost'), (self.cert, '127.0.0.1')):
            with self.subTest(hostname=hostname, trusted=bool(ca)):
                result, report = exercise(self.server, 'preflight', ca_file=ca, hostname=hostname)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(Handler.requests, 0)
                self.assertEqual(report['preflight']['status'], 'failed')

    def test_dripping_response_has_a_total_deadline(self):
        result, report = exercise(self.server, 'preflight', 'slow', ca_file=self.cert)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(report['cases'][-1]['error_class'], 'TimeoutError')
        self.assertLess(report['cases'][-1]['elapsed_seconds'], 13)


if __name__ == '__main__':
    unittest.main()
