"""Two distinct CI hosts: encrypted Restic, actual SQL/JetStream/filer/OpenBao readback.

Only original disposable fixture data. Public CI test password is not an operator key-management
recipe. Never run this destructive proof against an existing deployment.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
import nats

from common import Evidence

ROOT = Path(__file__).resolve().parents[2]
PROOF = b'KAIRO original D04 recovery fixture, no private user data'
BASE = ['docker','compose','--env-file','.env','-f','compose.yaml','-f','compose.qualification-recovery.yaml']
OPS = BASE + ['-f','compose.ops.yaml','--profile','ops']


def cmd(args, **kwargs):
    return subprocess.run(args, check=True, timeout=300, **kwargs)


def sql(statement):
    return cmd(BASE + ['exec','-T','postgres','psql','-U','kairo','-d','kairo','-At','-v','ON_ERROR_STOP=1','-c',statement],
               capture_output=True, text=True).stdout.strip()


def bao(client, method, path, *, token=None, data=None, expected=(200,204)):
    response = client.request(method, 'http://127.0.0.1:8200/v1/'+path,
                              headers={'X-Vault-Token':token} if token else {}, json=data)
    assert response.status_code in expected, (method, path, response.status_code)
    return response.json() if response.content else {}


def wait_stores():
    with httpx.Client(timeout=4, trust_env=False) as client:
        for _ in range(90):
            try:
                if sql('SELECT 1') == '1' and client.get('http://127.0.0.1:8888/').status_code == 200 and client.get('http://127.0.0.1:8200/v1/sys/seal-status').status_code == 200:
                    return
            except (subprocess.CalledProcessError, httpx.HTTPError):
                pass
            time.sleep(2)
    raise TimeoutError('Recovery stores startup')


async def jetstream(write):
    client = await nats.connect('nats://127.0.0.1:4222')
    try:
        js = client.jetstream()
        if write:
            await js.add_stream(name='D04_PROOF', subjects=['d04.proof'])
            await js.publish('d04.proof', PROOF)
        message = await js.get_msg('D04_PROOF', seq=1)
        assert message.data == PROOF
    finally:
        await client.close()


def volume_json(action, data=None):
    # Test-only recovery material is itself inside the encrypted snapshot; never uploaded in clear.
    path='/restore/openbao/d04-fixture-recovery.json'
    args = OPS + ['run','--rm','-T','--entrypoint','sh','volume-restore','-ec']
    if action == 'write':
        cmd(args+[f'umask 077; cat > {path}'], input=json.dumps(data), text=True, capture_output=True)
    else:
        return json.loads(cmd(args+[f'cat {path}'], capture_output=True, text=True).stdout)


def seed_and_policy():
    sql('CREATE TABLE kairo_d04_probe (value text NOT NULL); INSERT INTO kairo_d04_probe VALUES (\'d04-canonical-sql\')')
    asyncio.run(jetstream(True))
    with httpx.Client(timeout=10, trust_env=False) as client:
        client.post('http://127.0.0.1:8888/d04/proof.txt', files={'file':('proof.txt',PROOF)}).raise_for_status()
        keys=bao(client,'PUT','sys/init',data={'secret_shares':1,'secret_threshold':1})
        root=keys['root_token']; unseal=keys['keys_base64'][0]
        bao(client,'PUT','sys/unseal',data={'key':unseal})
        bao(client,'POST','sys/mounts/secret',token=root,data={'type':'kv','options':{'version':'2'}})
        bao(client,'POST','secret/data/kairo/d04-proof',token=root,data={'data':{'value':PROOF.decode()}})
        bao(client,'POST','secret/data/outside-kairo',token=root,data={'data':{'value':'outside-fixture'}})
        policy=(ROOT/'infrastructure/openbao/policies/kairo-core-read.hcl').read_text()
        bao(client,'PUT','sys/policies/acl/kairo-core',token=root,data={'policy':policy})
        token=bao(client,'POST','auth/token/create',token=root,data={'policies':['kairo-core'],'no_default_policy':True,'ttl':'1h'})['auth']['client_token']
        assert bao(client,'GET','secret/data/kairo/d04-proof',token=token)['data']['data']['value']==PROOF.decode()
        for method,path,data in [('GET','secret/data/outside-kairo',None),('POST','secret/data/kairo/d04-proof',{'data':{'value':'deny'}}),
                                  ('LIST','secret/metadata/kairo',None),('PUT','sys/policies/acl/forbidden',{'policy':'path "*" { capabilities=["sudo"] }'})]:
            bao(client,method,path,token=token,data=data,expected=(403,))
        volume_json('write',{'unseal':unseal,'workload_token':token})
    return {'sql':True,'jetstream_message':True,'filer_object':True,'openbao_file_backend':True,
            'workload_read_only':True,'forbidden_openbao_operations':4}


def readback():
    assert sql('SELECT value FROM kairo_d04_probe')=='d04-canonical-sql'
    asyncio.run(jetstream(False))
    keys=volume_json('read')
    with httpx.Client(timeout=10, trust_env=False) as client:
        assert client.get('http://127.0.0.1:8888/d04/proof.txt').content==PROOF
        bao(client,'PUT','sys/unseal',data={'key':keys['unseal']})
        assert bao(client,'GET','secret/data/kairo/d04-proof',token=keys['workload_token'])['data']['data']['value']==PROOF.decode()
    return {'sql_row':True,'jetstream_seq_1':True,'filer_sha256':hashlib.sha256(PROOF).hexdigest(),
            'openbao_unsealed_and_workload_read':True}


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('COMPOSE_PROJECT_NAME')!='kairo-d04-recovery':
        raise SystemExit('Requires the isolated D04 CI recovery project')
    action=sys.argv[1]
    assert action in {'backup','restore'}
    host=hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()
    evidence=Evidence('off-host-'+action, '.kairo-qualification/evidence/recovery-'+action+'.json')
    evidence.data['host_boot_fingerprint']=host;evidence.save()
    os.environ['KAIRO_COMPOSE_ENV_FILE']='.env'
    os.environ['KAIRO_COMPOSE_OVERLAY']='compose.qualification-recovery.yaml'
    os.environ['KAIRO_CONFIRM_RESTORE']='YES'
    if action=='backup':
        cmd(BASE+['up','-d','postgres','nats','seaweedfs','openbao']);wait_stores()
        evidence.case('seed-real-durable-state-and-openbao-policy',90,seed_and_policy)
        evidence.case('quiesced-encrypted-restic-backup',300,lambda: (cmd(['bash','scripts/ops/backup.sh']) and {}))
        snapshots=json.loads(cmd(OPS+['run','--rm','-T','restic','snapshots','--json'],capture_output=True,text=True).stdout)
        Path('.kairo-qualification/transfer.json').write_text(json.dumps({'source_host':host,'snapshot':snapshots[-1]['id'],
           'commit':evidence.data['commit']}))
    else:
        transfer=json.loads(Path('.kairo-qualification/transfer.json').read_text())
        assert transfer['source_host']!=host and transfer['commit']==evidence.data['commit']
        # No source volumes are present on this fresh host; check all encrypted packs before restore.
        evidence.case('off-host-restic-full-check',300,lambda: (cmd(OPS+['run','--rm','restic','check','--read-data']) and {}))
        evidence.case('off-host-volume-restore',300,lambda: (cmd(['bash','scripts/ops/restore.sh',transfer['snapshot']]) and {}))
        cmd(BASE+['up','-d','postgres','nats','seaweedfs','openbao']);wait_stores()
        evidence.case('off-host-real-service-readback',90,readback)


if __name__=='__main__':
    main()
