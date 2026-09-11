"""Production settings/JWT/ops/model inventory and effective Compose rejection proofs."""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from kairo_core import auth, security
from kairo_core.config import Settings as CoreSettings
from kairo_worker.config import Settings as WorkerSettings
from kairo_worker.model_assets import inventory, verify_manifest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('production_check', ROOT / 'scripts/ops/production.py')
production = importlib.util.module_from_spec(spec)
spec.loader.exec_module(production)


def core_values():
    return dict(kairo_env='production', kairo_auth_enabled=True,
                kairo_internal_token='a'*64, kairo_policy_signing_key='b'*64,
                openbao_token='c'*64, kairo_operations_token='d'*64,
                database_url='postgresql+asyncpg://kairo_app:'+('e'*64)+'@postgres/kairo',
                keycloak_issuer='https://auth.example.org/realms/kairo',
                kairo_cors_origins='https://kairo.example.org')


class Deployment(unittest.TestCase):
    def test_settings_fail_closed(self):
        CoreSettings(_env_file=None, **core_values())
        for change in [dict(kairo_env='prod'), dict(kairo_auth_enabled=False),
                       dict(kairo_internal_token='CHANGE_ME_LONG_RANDOM_INTERNAL_TOKEN'),
                       dict(kairo_policy_signing_key='a'*64), dict(kairo_cors_origins='*'),
                       dict(keycloak_issuer='http://auth.example.org/realms/kairo'),
                       dict(database_url='postgresql+asyncpg://postgres:secret@db/kairo')]:
            with self.subTest(change=list(change)), self.assertRaises(ValidationError):
                CoreSettings(_env_file=None, **{**core_values(), **change})
        values = dict(kairo_env='production', kairo_internal_token='a'*64,
                      litellm_master_key='b'*64, mem0_database_url='postgresql://mem0_app:'+('c'*64)+'@postgres/mem0',
                      kairo_memory_projector_mode='real')
        WorkerSettings(**values)
        for change in [dict(kairo_env='prod'),dict(kairo_memory_projector_mode='auto'),dict(kairo_memory_projector_mode='stub'),dict(mem0_database_url=''),dict(kairo_internal_token='development-only-change-me')]:
            with self.subTest(change=list(change)), self.assertRaises(ValidationError):
                WorkerSettings(**{**values,**change})

    def test_signed_access_tokens(self):
        key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        base = dict(sub='owner-1',iss=auth.settings.keycloak_issuer,aud=auth.settings.keycloak_audience,
                    azp=auth.settings.keycloak_client_id,typ='Bearer',iat=int(time.time()),exp=int(time.time())+300,
                    realm_access={'roles':['kairo-user']})
        with patch.object(auth._jwks_client,'get_signing_key_from_jwt',return_value=type('Key',(),{'key':key.public_key()})()):
            def decode(values): return auth._decode_token(jwt.encode(values,key,algorithm='RS256'))
            self.assertEqual(decode(base).subject,'owner-1')
            for claim in ('aud','azp','typ','sub','iss','exp','iat'):
                values={k:v for k,v in base.items() if k!=claim}
                with self.subTest(missing=claim), self.assertRaises(jwt.PyJWTError): decode(values)
            for change in [dict(aud='elsewhere'),dict(azp='elsewhere'),dict(typ='ID'),dict(sub=''),dict(exp=1),dict(realm_access=[]),dict(realm_access={'roles':'kairo-admin'})]:
                with self.subTest(change=change), self.assertRaises(jwt.PyJWTError): decode({**base,**change})

    def test_worker_cannot_use_operations_token(self):
        with patch.object(security,'settings',CoreSettings(_env_file=None,**core_values())):
            asyncio.run(security.require_operations_token('d'*64))
            with self.assertRaises(Exception): asyncio.run(security.require_operations_token('a'*64))
            with self.assertRaises(Exception): asyncio.run(security.require_internal_token('d'*64))

    def test_model_changes_require_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'weights').write_bytes(b'bounded fixture, not a real model')
            path=root/'manifest.json';path.write_text(json.dumps(dict(version=1,sources=['fixture revision 1'],files=inventory(root))))
            verify_manifest(path)
            (root/'weights').write_bytes(b'changed')
            with self.assertRaises(ValueError): verify_manifest(path)

    def test_effective_compose(self):
        # Generated throwaway credentials; never start this synthetic production configuration.
        text=(ROOT/'.env.production.example').read_text()
        lines=[]
        for line in text.splitlines():
            if line and not line.startswith('#') and '=' in line:
                key,value=line.split('=',1)
                if 'CHANGE_ME' in value: value=secrets.token_hex(32)
                if key=='KEYCLOAK_PROXY_TRUSTED_ADDRESSES': value='127.0.0.1/32'
                line=key+'='+value
            lines.append(line)
        with tempfile.NamedTemporaryFile(mode='w',suffix='.env') as env:
            env.write('\n'.join(lines));env.flush()
            base=['docker','compose','--env-file',env.name,'-f','compose.yaml','-f','compose.production.yaml']
            def config(extra):
                result=subprocess.run([*base,*extra,'config','--format','json'],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,'Compose rendering failed; possible credentials withheld')
                return json.loads(result.stdout)
            valid=config([])
            self.assertEqual(production.validate(valid),[])
            self.assertNotIn('kairo-realtime',valid['services'])
            self.assertNotIn('activepieces',valid['services'])
            for name in ['postgres','nats','temporal','seaweedfs','openbao']:
                self.assertFalse(valid['services'][name].get('ports'))
            with_tools=config(['-f','compose.web-mcp.yaml','-f','compose.web-mcp.production.yaml','--profile','search','--profile','ai'])
            self.assertEqual(production.validate(with_tools),[])
            self.assertEqual(set(with_tools['services']['kairo-web-mcp']['networks']),{'search','egress'})
            self.assertNotIn('KAIRO_INTERNAL_TOKEN',with_tools['services']['kairo-web-mcp']['environment'])
            bad=config(['-f','compose.test-noauth.yaml'])
            self.assertTrue(production.validate(bad))
            for extra in [['-f','compose.override.yaml'],['--profile','collaboration-experimental'],['--profile','home']]:
                self.assertTrue(production.validate(config(extra)),extra)
            bad=copy.deepcopy(valid);bad['services']['kairo-core']['environment']['DATABASE_URL']='postgresql://postgres:secret@db/kairo'
            self.assertTrue(production.validate(bad))


if __name__=='__main__': unittest.main(verbosity=2)
