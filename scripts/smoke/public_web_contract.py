"""Real HTTP/TLS sockets on an isolated CI loopback alias: DNS pinning and bounded reads.
Run after `sudo ip addr add 93.184.216.34/32 dev lo`; never contacts that public host.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import ipaddress
import os
from pathlib import Path
import socket
import ssl
import tempfile
import unittest
from unittest.mock import patch

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from kairo_worker import public_web as web

ADDRESS='93.184.216.34'


class PublicWeb(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls=[];self.dns_calls=[];self.sni=[]
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'public.example.test')])
        cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(days=1))
              .not_valid_after(datetime.now(timezone.utc)+timedelta(days=1))
              .add_extension(x509.SubjectAlternativeName([x509.DNSName('public.example.test')]),critical=False)
              .sign(key,hashes.SHA256()))
        (root/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (root/'cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server_context.load_cert_chain(root/'cert.pem',root/'key.pem')
        server_context.set_servername_callback(lambda _socket,name,_ctx:self.sni.append(name))
        self.client_context=ssl.create_default_context(cafile=str(root/'cert.pem'))
        self.servers=[await asyncio.start_server(self.serve,ADDRESS,80),await asyncio.start_server(self.serve,ADDRESS,443,ssl=server_context)]
        loop=asyncio.get_running_loop();original=loop.getaddrinfo
        async def resolve(host,port,*args,**kwargs):
            try: ipaddress.ip_address(host)
            except ValueError:
                self.dns_calls.append(host)
                # The attack changes DNS to localhost on a second hostname resolution.
                address=ADDRESS if len(self.dns_calls)==1 else '127.0.0.1'
                return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,port))]
            return await original(host,port,*args,**kwargs)
        self.dns=patch.object(loop,'getaddrinfo',side_effect=resolve);self.dns.start()
        self.context=patch.object(ssl,'create_default_context',return_value=self.client_context);self.context.start()
        self.proxy=patch.dict(os.environ,{'HTTPS_PROXY':'http://127.0.0.1:9','HTTP_PROXY':'http://127.0.0.1:9','ALL_PROXY':'http://127.0.0.1:9'});self.proxy.start()

    async def asyncTearDown(self):
        self.proxy.stop();self.context.stop();self.dns.stop()
        for server in self.servers: server.close();await server.wait_closed()
        self.temp.cleanup()

    async def serve(self,reader,writer):
        try:
            raw=await reader.readuntil(b'\r\n\r\n');self.calls.append(raw)
            path=raw.split(b' ')[1]
            if path==b'/redirect': response=b'HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1/internal\r\nContent-Length: 0\r\n\r\n'
            elif path==b'/gzip': response=b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Encoding: gzip\r\nContent-Length: 0\r\n\r\n'
            elif path==b'/oversize': response=b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n'+b'x'*4096
            elif path==b'/slow':
                await asyncio.sleep(0.3);response=b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n'
            else:
                body=b'<html>Public fixture</html>';response=b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body
            writer.write(response);await writer.drain()
        except (ConnectionError,asyncio.IncompleteReadError): pass
        finally:
            writer.close()
            try: await writer.wait_closed()
            except ConnectionError: pass

    async def test_real_tls_host_sni_and_one_dns(self):
        response=await web.fetch_public_html('https://public.example.test/article?q=kept')
        self.assertEqual(response.status_code,200)
        self.assertEqual(str(response.url),'https://public.example.test/article?q=kept')
        self.assertEqual(self.dns_calls,['public.example.test'])
        self.assertEqual(self.sni,['public.example.test'])
        self.assertIn(b'Host: public.example.test',self.calls[0])
        self.assertNotIn(b'Authorization:',self.calls[0])

    async def test_wrong_tls_hostname_refused(self):
        with self.assertRaises(httpx.ConnectError): await web.fetch_public_html('https://wrong.example.test/')
        self.assertEqual(self.calls,[])

    async def test_private_redirect_refused_before_request(self):
        self.assertIsNone(await web.fetch_public_html('http://public.example.test/redirect'))
        self.assertEqual(len(self.calls),1)

    async def test_unknown_length_and_compression_refused(self):
        with patch.object(web,'MAX_BYTES',1024):
            self.assertIsNone(await web.fetch_public_html(f'http://{ADDRESS}/oversize'))
        self.assertIsNone(await web.fetch_public_html(f'http://{ADDRESS}/gzip'))

    async def test_whole_request_deadline(self):
        with patch.object(web,'MAX_SECONDS',0.05),self.assertRaises(TimeoutError):
            await web.fetch_public_html(f'http://{ADDRESS}/slow')

    async def test_invalid_destinations(self):
        for url in ['http://127.0.0.1/','http://[::1]/','http://[::ffff:127.0.0.1]/','http://[64:ff9b::7f00:1]/','http://224.0.0.1/','http://169.254.169.254/','http://localhost/','http://x.internal/','http://user:password@example.org/','http://example.org:99999/','http://example.org:5432/','file:///etc/passwd','http://example.org\\@127.0.0.1/']:
            with self.subTest(url=url): self.assertIsNone(await web.resolve_public(url))
        loop=asyncio.get_running_loop()
        with patch.object(loop,'getaddrinfo',return_value=[(2,1,6,'',(ADDRESS,80)),(2,1,6,'',('10.0.0.1',80))]):
            self.assertIsNone(await web.resolve_public('http://mixed.example.test/'))
        self.assertEqual(self.calls,[])


if __name__=='__main__': unittest.main(verbosity=2)
