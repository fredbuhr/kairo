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
PROOF = b'Nevolium original D04 recovery fixture, no private user data'
BASE = ['docker','compose','--env-file','.env','-f','compose.yaml','-f','compose.qualification-recovery.yaml']
OPS = BASE + ['-f','compose.ops.yaml','--profile','ops']


def cmd(args, **kwargs):
    return subprocess.run(args, check=True, timeout=300, **kwargs)


def sql(statement):
    return cmd(BASE + ['exec','-T','postgres','psql','-U','nevolium','-d','nevolium','-At','-v','ON_ERROR_STOP=1','-c',statement],
               capture_output=True, text=True).stdout.strip()


def bao(client, method, path, *, token=None, data=None, expected=(200,204)):
    response = client.request(method, 'http://127.0.0.1:8200/v1/'+path,
                              headers={'X-Vault-Token':token} if token else {}, json=data)
    assert response.status_code in expected, (method, path, response.status_code)
    return response.json() if response.content else {}


def wait_stores():
    state={}
    with httpx.Client(timeout=4, trust_env=False) as client:
        for _ in range(90):
            try:
                state['postgres']=sql('SELECT 1')=='1'
            except subprocess.CalledProcessError:
                state['postgres']=False
            for name,url in [('filer','http://127.0.0.1:8888/'),('openbao','http://127.0.0.1:8200/v1/sys/seal-status')]:
                try:
                    state[name]=client.get(url).status_code==200
                except httpx.HTTPError:
                    state[name]=False
            if all(state.values()):
                return
            time.sleep(2)
    print(json.dumps({'startup_ready':state}),flush=True)
    # Startup is before initialization: no tokens exist to leak in these diagnostic logs.
    cmd(BASE+['logs','--no-color','--tail=80','openbao','seaweedfs','postgres'])
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


def filer_readback(client):
    # An HTTP-ready filer can precede restored volume registration with the master.
    # Require the original bytes, before backup as well as after restoration.
    deadline = time.monotonic() + 45
    attempts = []
    while time.monotonic() < deadline:
        try:
            response = client.get('http://127.0.0.1:8888/d04/proof.txt', timeout=4)
            state = {'status': response.status_code, 'bytes': len(response.content),
                     'sha256': hashlib.sha256(response.content).hexdigest()}
            attempts.append(state)
            if response.status_code == 200 and response.content == PROOF:
                return {'attempts': len(attempts), 'observed_statuses': sorted({
                    row['status'] for row in attempts if 'status' in row}), **state}
        except httpx.HTTPError as exc:
            attempts.append({'error_class': type(exc).__name__})
        time.sleep(1)
    print(json.dumps({'filer_readback_attempts': attempts}), flush=True)
    cmd(BASE + ['logs', '--no-color', '--tail=100', 'seaweedfs'])
    raise AssertionError('Original filer object unavailable within 45 seconds')


def volume_json(action, data=None):
    # Test-only recovery material is itself inside the encrypted snapshot; never uploaded in clear.
    path='/restore/openbao/d04-fixture-recovery.json'
    args = OPS + ['run','--rm','-T','--entrypoint','sh','volume-restore','-ec']
    if action == 'write':
        cmd(args+[f'umask 077; cat > {path}'], input=json.dumps(data), text=True, capture_output=True)
    else:
        return json.loads(cmd(args+[f'cat {path}'], capture_output=True, text=True).stdout)


def seed_and_policy():
    sql('CREATE TABLE nevolium_d04_probe (value text NOT NULL); INSERT INTO nevolium_d04_probe VALUES (\'d04-canonical-sql\')')
    asyncio.run(jetstream(True))
    with httpx.Client(timeout=10, trust_env=False) as client:
        client.post('http://127.0.0.1:8888/d04/proof.txt', files={'file':('proof.txt',PROOF)}).raise_for_status()
        filer = filer_readback(client)
        cmd(BASE + ['exec', '-T', 'seaweedfs', 'test', '-d', '/data/filerldb2'])
        keys=bao(client,'PUT','sys/init',data={'secret_shares':1,'secret_threshold':1})
        root=keys['root_token']; unseal=keys['keys_base64'][0]
        bao(client,'PUT','sys/unseal',data={'key':unseal})
        bao(client,'POST','sys/mounts/secret',token=root,data={'type':'kv','options':{'version':'2'}})
        bao(client,'POST','secret/data/nevolium/d04-proof',token=root,data={'data':{'value':PROOF.decode()}})
        bao(client,'POST','secret/data/outside-nevolium',token=root,data={'data':{'value':'outside-fixture'}})
        policy=(ROOT/'infrastructure/openbao/policies/nevolium-core-read.hcl').read_text()
        bao(client,'PUT','sys/policies/acl/nevolium-core',token=root,data={'policy':policy})
        token=bao(client,'POST','auth/token/create',token=root,data={
            'policies':['nevolium-core'],'no_default_policy':True,'no_parent':True,'period':'24h'
        })['auth']['client_token']
        allowed=bao(client,'POST','sys/capabilities-self',token=token,
                    data={'path':'secret/data/nevolium/d04-proof'})
        denied=bao(client,'POST','sys/capabilities-self',token=token,
                   data={'path':'secret/data/outside-nevolium'})
        assert set(allowed['capabilities'])=={'read'}
        assert set(denied['capabilities'])=={'deny'}
        assert bao(client,'GET','secret/data/nevolium/d04-proof',token=token)['data']['data']['value']==PROOF.decode()
        renewed=bao(client,'POST','auth/token/renew-self',token=token,data={})
        assert renewed['auth']['renewable'] is True
        for method,path,data in [('GET','secret/data/outside-nevolium',None),('POST','secret/data/nevolium/d04-proof',{'data':{'value':'deny'}}),
                                  ('LIST','secret/metadata/nevolium',None),('PUT','sys/policies/acl/forbidden',{'policy':'path "*" { capabilities=["sudo"] }'})]:
            bao(client,method,path,token=token,data=data,expected=(403,))
        volume_json('write',{'unseal':unseal,'workload_token':token})
    return {'sql':True,'jetstream_message':True,'filer_object':filer,'filer_metadata_in_durable_volume':True,'openbao_file_backend':True,
            'workload_read_only':True,'workload_self_introspection':True,
            'workload_self_renewal':True,'forbidden_openbao_operations':4}


def readback():
    assert sql('SELECT value FROM nevolium_d04_probe')=='d04-canonical-sql'
    asyncio.run(jetstream(False))
    keys=volume_json('read')
    with httpx.Client(timeout=10, trust_env=False) as client:
        filer = filer_readback(client)
        bao(client,'PUT','sys/unseal',data={'key':keys['unseal']})
        assert bao(client,'GET','secret/data/nevolium/d04-proof',token=keys['workload_token'])['data']['data']['value']==PROOF.decode()
    return {'sql_row':True,'jetstream_seq_1':True,'filer_sha256':hashlib.sha256(PROOF).hexdigest(),
            'filer_object':filer,
            'openbao_unsealed_and_workload_read':True}


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('COMPOSE_PROJECT_NAME')!='nevolium-d04-recovery':
        raise SystemExit('Requires the isolated D04 CI recovery project')
    action=sys.argv[1]
    assert action in {'backup','restore'}
    host=hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()
    evidence=Evidence('off-host-'+action, '.nevolium-qualification/evidence/recovery-'+action+'.json')
    evidence.data['host_boot_fingerprint']=host;evidence.save()
    os.environ['NEVOLIUM_COMPOSE_ENV_FILE']='.env'
    os.environ['NEVOLIUM_COMPOSE_OVERLAY']='compose.qualification-recovery.yaml'
    os.environ['NEVOLIUM_CONFIRM_RESTORE']='YES'
    # Create bind-mount roots as the operator before Docker can create root-owned paths.
    Path('.nevolium-backup-staging').mkdir(exist_ok=True)
    if action=='backup':
        cmd(BASE+['up','-d','postgres','nats','seaweedfs','openbao']);wait_stores()
        evidence.case('seed-real-durable-state-and-openbao-policy',90,seed_and_policy)
        evidence.case('quiesced-encrypted-restic-backup',300,lambda: (cmd(['bash','scripts/ops/backup.sh']) and {}))
        snapshots=json.loads(cmd(OPS+['run','--rm','-T','restic','snapshots','--json'],capture_output=True,text=True).stdout)
        Path('.nevolium-qualification/transfer.json').write_text(json.dumps({'source_host':host,'snapshot':snapshots[-1]['id'],
           'commit':evidence.data['commit']}))
    else:
        transfer=json.loads(Path('.nevolium-qualification/transfer.json').read_text())
        assert transfer['source_host']!=host and transfer['commit']==evidence.data['commit']
        # No source volumes are present on this fresh host; check all encrypted packs before restore.
        evidence.case('off-host-restic-full-check',300,lambda: (cmd(OPS+['run','--rm','restic','check','--read-data']) and {}))
        evidence.case('off-host-volume-restore',300,lambda: (cmd(['bash','scripts/ops/restore.sh',transfer['snapshot']]) and {}))
        cmd(BASE+['up','-d','postgres','nats','seaweedfs','openbao']);wait_stores()
        evidence.case('off-host-real-service-readback',90,readback)
    evidence.finish()


if __name__=='__main__':
    main()
