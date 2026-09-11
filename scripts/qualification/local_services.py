"""Real local LiteLLM/Ollama/Core accounting and SearXNG adapters; no paid model path."""
import asyncio
from decimal import Decimal
import os
import subprocess
import time
import uuid

import httpx

from common import Evidence
from nevolium_worker.config import settings
from nevolium_worker.model_gateway import chat_completion, ModelCheckpointLedger, ModelCallOutcomeUnknown

CORE = 'http://127.0.0.1:8000'
OLLAMA = 'http://127.0.0.1:11434'
MODEL = 'qwen2.5:0.5b'


def compose(*args):
    subprocess.run(['docker', 'compose', '-f', 'compose.yaml', '-f', 'compose.test-noauth.yaml',
                    *args], check=True, timeout=180)


def run():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('This destructive stop/restart fixture runs only in isolated CI; use the D04 target protocol elsewhere')
    evidence = Evidence('real-local-services', '.nevolium-qualification/evidence/local-services.json')
    settings.nevolium_core_url = CORE
    settings.nevolium_internal_token = 'd04-internal-fixture-token'
    settings.litellm_url = 'http://127.0.0.1:4000'
    settings.litellm_master_key = 'd04-local-fixture-no-provider-key'
    settings.nevolium_model_max_output_tokens = 48
    settings.searxng_url = 'http://127.0.0.1:8082'
    with httpx.Client(timeout=10, trust_env=False) as client:
        for _ in range(90):
            try:
                if client.get(CORE + '/health/live').status_code == 200 and client.get(settings.litellm_url+'/health/liveliness').status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(2)
        else:
            raise TimeoutError('Local service startup')
        catalog = client.get(OLLAMA+'/api/tags').json()['models']
        model = next(item for item in catalog if item['name'] == MODEL)
        assert len(model['digest']) == 64
        evidence.data['model'] = {key: model[key] for key in ('name', 'digest', 'size', 'details')}
        evidence.data['ollama_version'] = client.get(OLLAMA+'/api/version').json()['version']
        evidence.save()
        project = client.post(CORE+'/v1/projects', json={'name': 'D04 local model qualification'})
        project.raise_for_status()
        task = client.post(CORE+'/v1/tasks', json={'project_id':project.json()['id'],
            'title':'D04 real local inference', 'authority_ceiling':1, 'budget_usd':'1.00', 'input':{}})
        task.raise_for_status()
        task_id = task.json()['id']
    ledger = ModelCheckpointLedger()
    key = str(uuid.uuid4())
    params = dict(task_id=task_id, workflow_execution_id=None, correlation_id=None,
                  model_alias='local-fast', messages=[{'role':'user','content':'Say hello in French in one short sentence.'}],
                  idempotency_key=key, checkpoint_ledger=ledger, estimated_cost_usd=Decimal('0.001'),
                  timeout_seconds=110, temperature=0)

    def inference():
        result = asyncio.run(chat_completion(**params))
        assert result.content.strip() and result.usage.completion_tokens > 0
        assert ledger.checkpoint_for(key)['stage'] == 'accounted'
        return {'prompt_tokens':result.usage.prompt_tokens, 'completion_tokens':result.usage.completion_tokens,
                'reported_cost_usd':str(result.usage.cost_usd), 'cost_reported':result.usage.cost_reported,
                'canonical_accounting':True, 'model_alias':'local-fast'}
    evidence.case('gateway-local-inference-and-accounting', 115, inference)

    def replay_without_engine():
        compose('stop', 'ollama')
        result = asyncio.run(chat_completion(**params))
        assert result.raw.get('replayed_from_temporal_checkpoint') is True
        new = dict(params, idempotency_key=str(uuid.uuid4()), timeout_seconds=15)
        try:
            asyncio.run(chat_completion(**new))
        except (httpx.HTTPError, TimeoutError):
            pass
        else:
            raise AssertionError('Unavailable local model unexpectedly returned a completion')
        try:
            asyncio.run(chat_completion(**new))
        except ModelCallOutcomeUnknown:
            pass
        else:
            raise AssertionError('Uncertain dispatch must not be retried blindly')
        compose('up', '-d', 'ollama')
        return {'known_result_replayed_without_engine':True, 'unknown_outcome_replay_refused':True}
    evidence.case('engine-loss-known-replay-and-unknown-outcome', 90, replay_without_engine)
    evidence.case('local-engine-restart', 115, lambda: inference_after_restart(params))

    def search():
        from nevolium_worker.activities import _search_searxng, _public_sources
        sources = asyncio.run(_search_searxng(query='PostgreSQL documentation', language='en',
            time_range='year', max_sources=3, mode='general'))
        public = _public_sources(sources)
        assert public and all(item.get('url','').startswith(('https://','http://')) for item in public)
        return {'source_count':len(public), 'adapter':'Nevolium SearXNG', 'live_external_search':True}
    evidence.case('searxng-live-worker-search', 65, search)
    evidence.finish()


def inference_after_restart(params):
    result = asyncio.run(chat_completion(**dict(params, idempotency_key=str(uuid.uuid4()))))
    assert result.content and result.usage.completion_tokens > 0
    return {'completion_tokens':result.usage.completion_tokens}


if __name__ == '__main__':
    run()
