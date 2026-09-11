"""D04 target inventory and bounded read-only load; no model calls or deployment."""
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import time
from urllib.parse import urlsplit

from common import Evidence, hardware


def inventory(output):
    result = {'schema':1, 'lot':'D04', 'hardware':hardware(),
              'tools':{name: bool(shutil.which(name)) for name in ('docker','nvidia-smi','restic','uv')},
              'free_disk_bytes':shutil.disk_usage(Path.cwd()).free,
              'target_config_present':Path('.env.production').is_file(),
              'model_manifest_present':Path(os.environ.get('KAIRO_MODEL_ASSETS_PATH','model-assets'),'manifest.json').is_file(),
              'target_and_off_host_restore_validated':False}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


def subject(token):
    # Counting subjects only; the target Core must verify signatures/claims on every request.
    payload=token.split('.')[1]
    return json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))['sub']


async def load(args):
    import httpx
    url=urlsplit(args.core)
    if url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('Provide a bare Core origin without credentials')
    if url.scheme!='https' and not (url.scheme=='http' and url.hostname in {'127.0.0.1','localhost','::1'}):
        raise ValueError('Target must use HTTPS, or HTTP on loopback')
    tokens=json.loads(args.tokens_file.read_text())
    if not isinstance(tokens,list) or not tokens or not all(isinstance(t,str) and 0<len(t)<16384 for t in tokens):
        raise ValueError('Token file must be a nonempty JSON array of access tokens')
    subjects={subject(token) for token in tokens}
    evidence=Evidence('target-read-load',args.output)
    evidence.data.update(authenticated_subject_count=len(subjects),
        hardware_role='load-generator; record the server inventory separately',
        workload='three read-only requests per virtual client; no AI calls',
        concurrency=args.concurrency, thresholds={'p95_seconds':args.p95_seconds,'max_errors':0},
        target_origin_sha256=hashlib.sha256(args.core.encode()).hexdigest())
    evidence.save()
    semaphore=asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(base_url=args.core,timeout=10,trust_env=False,follow_redirects=False) as client:
        # A development/noauth deployment cannot yield an authenticated capacity proof.
        anonymous=await client.get('/v1/projects?limit=1')
        if anonymous.status_code not in {401,403}:
            evidence.data['cases'].append({'id':'anonymous-access-rejected','status':'failed'})
            evidence.save()
            raise SystemExit('Target accepts anonymous access; authenticated load refused')
        evidence.data['anonymous_access_rejected']=True;evidence.save()
        for count in (1,10,100,1000):
            latencies=[];errors=0;started=time.monotonic()
            row={'id':f'read-load-{count}', 'virtual_clients':count, 'status':'running'}
            evidence.data['cases'].append(row);evidence.save()
            async def virtual_client(index):
                nonlocal errors
                async with semaphore:
                    for path in ('/v1/projects?limit=20','/v1/today','/v1/work-capacity'):
                        before=time.monotonic()
                        try:
                            response=await client.get(path,headers={'Authorization':'Bearer '+tokens[index%len(tokens)]})
                            if response.status_code!=200:
                                errors+=1
                        except httpx.HTTPError:
                            errors+=1
                        latencies.append(time.monotonic()-before)
            try:
                async with asyncio.timeout(args.stage_timeout):
                    await asyncio.gather(*(virtual_client(i) for i in range(count)))
            except TimeoutError:
                row.update(status='failed', error_class='TimeoutError', completed_requests=len(latencies),
                           elapsed_seconds=round(time.monotonic()-started,3))
                evidence.save()
                raise SystemExit('Read-load stage timed out; partial results preserved') from None
            latencies.sort();p95=latencies[min(len(latencies)-1,int(len(latencies)*0.95))]
            row.update({'requests':len(latencies),
                 'authenticated_subjects_used':len({subject(tokens[i%len(tokens)]) for i in range(count)}),
                 'elapsed_seconds':round(time.monotonic()-started,3), 'p50_seconds':round(statistics.median(latencies),3),
                 'p95_seconds':round(p95,3),'errors':errors,'status':'passed' if errors==0 and p95<=args.p95_seconds else 'failed'})
            evidence.save();print(json.dumps(row))
            if row['status']!='passed':
                raise SystemExit('Read-load threshold exceeded; stop before higher pressure')
    evidence.finish()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['inventory','load'])
    parser.add_argument('--output',default='.kairo-qualification/evidence/target.json')
    parser.add_argument('--core')
    parser.add_argument('--tokens-file',type=Path)
    parser.add_argument('--concurrency',type=int,default=20,choices=range(1,65))
    parser.add_argument('--p95-seconds',type=float,default=2)
    parser.add_argument('--stage-timeout',type=float,default=180)
    args=parser.parse_args()
    if args.action=='inventory':
        inventory(args.output)
    else:
        if not args.core or not args.tokens_file or not 0<args.p95_seconds<=30 or not 0<args.stage_timeout<=600:
            parser.error('load requires --core, --tokens-file and positive bounded thresholds')
        asyncio.run(load(args))
