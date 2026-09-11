"""Runner regressions with a fixture HTTP server; not real-engine or capacity evidence."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    failures=False
    requests=0
    paths=set()
    lock=threading.Lock()

    def do_GET(self):
        with self.lock:
            type(self).requests+=1
            self.paths.add(self.path)
        status=429 if self.failures else 200
        self.send_response(status);self.send_header('Content-Length','2');self.end_headers()
        self.wfile.write(b'{}')

    def log_message(self,*_args):
        pass


class Server(ThreadingHTTPServer):
    request_queue_size=128
    daemon_threads=True


class Contract(unittest.TestCase):
    def exercise(self,failures):
        Handler.failures=failures;Handler.requests=0;Handler.paths=set()
        server=Server(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)
                fake='fixture.'+base64.urlsafe_b64encode(b'{"sub":"fixture-owner"}').decode().rstrip('=')+'.not-a-real-signature'
                (path/'tokens.json').write_text(json.dumps([fake]))
                result=subprocess.run([sys.executable,str(Path(__file__).with_name('target.py')),'load',
                    '--core',f'http://127.0.0.1:{server.server_port}','--tokens-file',str(path/'tokens.json'),
                    '--output',str(path/'result.json'),'--p95-seconds','10'],capture_output=True,text=True,timeout=120)
                report=json.loads((path/'result.json').read_text())
                self.assertNotIn(fake,result.stdout+result.stderr+json.dumps(report))
                self.assertEqual(report['authenticated_subject_count'],1)
                self.assertEqual(report['d04_gate'],'incomplete')
                self.assertEqual(Handler.paths,{'/v1/projects?limit=20','/v1/today','/v1/work-capacity'})
                return result,report
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3)

    def test_virtual_clients_are_not_invented_users(self):
        result,report=self.exercise(False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual([r['virtual_clients'] for r in report['cases']],[1,10,100,1000])
        self.assertEqual(Handler.requests,3333)
        self.assertTrue(all(r['authenticated_subjects_used']==1 and r['status']=='passed' for r in report['cases']))

    def test_pressure_failure_stops_before_next_stage(self):
        result,report=self.exercise(True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(Handler.requests,3)
        self.assertEqual(len(report['cases']),1)
        self.assertEqual(report['cases'][0]['status'],'failed')


if __name__=='__main__':
    unittest.main()
