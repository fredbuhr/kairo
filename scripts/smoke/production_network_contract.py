"""Disposable CI production Core/SQL/Web proof, including actual Docker network denials."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[2]


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('This destructive disposable-stack proof is CI-only')
    env={}
    for line in (ROOT/'.env.production.example').read_text().splitlines():
        if line and not line.startswith('#') and '=' in line:
            key,value=line.split('=',1)
            env[key]=secrets.token_hex(32) if 'CHANGE_ME' in value else value
    env.update(KAIRO_API_PORT='14800',KAIRO_WEB_PORT='15173',KEYCLOAK_PROXY_TRUSTED_ADDRESSES='127.0.0.1/32')
    with tempfile.NamedTemporaryFile(mode='w',suffix='.env') as file:
        file.write('\n'.join(k+'='+v for k,v in env.items()));file.flush()
        compose=['docker','compose','-p','kairo-d03-proof','--env-file',file.name,'-f','compose.yaml','-f','compose.production.yaml']
        def redact(value):
            for secret in env.values():
                if len(secret) >= 24: value=value.replace(secret,'[redacted]')
            return value
        def run(*args):
            result=subprocess.run([*compose,*args],cwd=ROOT,capture_output=True,text=True)
            if result.returncode:
                print(redact(result.stderr[-6000:]))
                raise AssertionError('production stack command failed: '+args[0])
            return result.stdout.strip()
        try:
            run('up','-d','--wait','postgres')
            run('run','--rm','--build','kairo-db-provision')
            run('run','--rm','--build','kairo-migrate')
            run('up','-d','--no-deps','--build','kairo-core','kairo-web')
            for _ in range(45):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:14800/health/live',timeout=2) as response:
                        assert json.load(response)['environment']=='production'
                    break
                except (OSError,ValueError): time.sleep(1)
            else: raise AssertionError('production Core did not start with restricted SQL identity')
            with urllib.request.urlopen('http://127.0.0.1:15173/',timeout=3) as response: assert response.status==200
            try: urllib.request.urlopen('http://127.0.0.1:14800/v1/projects',timeout=3)
            except urllib.error.HTTPError as exc: assert exc.code==401
            else: raise AssertionError('production Core admitted an unauthenticated user')
            pg_id=run('ps','-q','postgres')
            inspected=json.loads(subprocess.check_output(['docker','inspect',pg_id],text=True))
            address=inspected[0]['NetworkSettings']['Networks']['kairo-d03-proof_canonical']['IPAddress']
            run('exec','-T','kairo-core','python','-c','import socket; socket.create_connection(("'+address+'",5432),timeout=3).close()')
            # Check both name lookup and direct numeric-IP access, not only Compose declarations.
            script='''const net=require('node:net');async function denied(host){await new Promise((resolve,reject)=>{const s=net.connect({host,port:5432});s.setTimeout(1500);s.on('connect',()=>{s.destroy();reject(Error('network isolation failed'))});s.on('error',resolve);s.on('timeout',()=>{s.destroy();resolve()})})};(async()=>{await denied('postgres');await denied(process.argv[1])})().catch(()=>process.exit(1))'''
            run('exec','-T','kairo-web','node','-e',script,address)
            core_id=run('ps','-q','kairo-core')
            run('stop','kairo-core')
            state=json.loads(subprocess.check_output(['docker','inspect',core_id],text=True))[0]['State']
            assert state['ExitCode']==0 and not state['OOMKilled'], 'Core did not stop cleanly'
            print('PASS: production provisioning/migration, Core restricted startup/authentication, static Web, real network allow/deny and clean shutdown')
        except Exception:
            result=subprocess.run([*compose,'logs','--no-color','--tail','90','kairo-core'],cwd=ROOT,capture_output=True,text=True)
            print(redact(result.stdout))
            raise
        finally:
            run('down','-v','--remove-orphans')


if __name__=='__main__': main()
