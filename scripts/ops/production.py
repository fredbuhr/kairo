#!/usr/bin/env python3
"""Validate the effective production configuration before explicit activation. Never prints secrets."""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

FORBIDDEN = {'home-assistant', 'openhands', 'livekit', 'nevolium-realtime', 'rotki', 'actual-budget', 'hummingbot', 'headscale', 'activepieces', 'ntfy'}
PASSWORD = re.compile(r'(PASSWORD|SECRET|SIGNING_KEY|INTERNAL_TOKEN|OPERATIONS_TOKEN|MASTER_KEY|OPENBAO_TOKEN|ENCRYPTION_KEY|SALT)$')
OPENBAO_SERVICE_TOKEN = re.compile(r's\.[A-Za-z0-9]{24,}')


def validate(config: dict) -> list[str]:
    errors = []
    services = config['services']
    for name, svc in services.items():
        if name in FORBIDDEN:
            errors.append(f'{name}: integration/production boundary is not implemented')
        env = svc.get('environment', {})
        for key, value in env.items():
            if PASSWORD.search(key) and key not in {'BAO_DEV_ROOT_TOKEN_ID'}:
                value = str(value or '')
                invalid_openbao = key == 'OPENBAO_TOKEN' and not OPENBAO_SERVICE_TOKEN.fullmatch(value)
                invalid_other = key != 'OPENBAO_TOKEN' and (len(value) < 32 or any(
                    x in value.lower() for x in ('change_me','change-me','development','nevolium-dev')
                ))
                if invalid_openbao or invalid_other:
                    errors.append(f'{name}: provision {key}')
        command = svc.get('command') or []
        if isinstance(command, str): command = command.split()
        if any(c in {'start-dev','-dev','--dev'} for c in command):
            errors.append(f'{name}: development command forbidden')
        if svc.get('privileged') or svc.get('network_mode') == 'host':
            errors.append(f'{name}: host privileges forbidden')
        for vol in svc.get('volumes', []):
            if 'docker.sock' in str(vol): errors.append(f'{name}: Docker host socket forbidden')
        for port in svc.get('ports', []):
            if port.get('host_ip') not in {'127.0.0.1','::1'}:
                errors.append(f'{name}: public host port requires an explicit TLS ingress design')
        if not all(svc.get(key) for key in ('cpus','mem_limit','pids_limit','init')):
            errors.append(f'{name}: CPU/RAM/PID/init bounds required')
        if 'nevolium' in svc.get('networks', {}): errors.append(f'{name}: development shared network forbidden')
        if name in {'nevolium-core','nevolium-worker','nevolium-realtime'} and env.get('NEVOLIUM_ENV') != 'production':
            errors.append(f'{name}: production mode required')
    if 'vllm' in services:
        command = services['vllm'].get('command', [])
        if '--revision' not in command or not re.fullmatch(r'[0-9a-f]{40}', command[command.index('--revision')+1]):
            errors.append('vLLM requires an explicit upstream model revision')
    core = services.get('nevolium-core', {}).get('environment', {})
    if core:
        if str(core.get('NEVOLIUM_AUTH_ENABLED')).lower() != 'true': errors.append('Core authentication required')
        db = urlsplit(core.get('DATABASE_URL',''))
        if db.username != 'nevolium_app': errors.append('Core SQL runtime identity must be nevolium_app')
        values = [core.get(k) for k in ('NEVOLIUM_INTERNAL_TOKEN','NEVOLIUM_POLICY_SIGNING_KEY','OPENBAO_TOKEN','NEVOLIUM_OPERATIONS_TOKEN')]
        if len(set(values)) != 4: errors.append('Core workload secrets must be distinct')
    for name, key in [('nevolium-core','KEYCLOAK_ISSUER'), ('keycloak','KC_HOSTNAME')]:
        value = services.get(name,{}).get('environment',{}).get(key)
        if value and (urlsplit(value).scheme != 'https' or '*' in value): errors.append(f'{name}: explicit HTTPS origin required')
    trusted_proxy = str(services.get('keycloak',{}).get('environment',{}).get('KC_PROXY_TRUSTED_ADDRESSES') or '')
    try:
        trusted_network = ipaddress.ip_network(trusted_proxy, strict=False)
        if trusted_network.num_addresses != 1 or not (trusted_network.is_private or trusted_network.is_loopback):
            raise ValueError
    except ValueError:
        errors.append('keycloak: exact private trusted proxy address required')
    webargs = services.get('nevolium-web',{}).get('build',{}).get('args',{})
    for key in ('VITE_NEVOLIUM_API_URL','VITE_KEYCLOAK_URL'):
        if webargs and urlsplit(webargs.get(key,'')).scheme != 'https': errors.append(f'Web: HTTPS {key} required')
    worker = services.get('nevolium-worker',{}).get('environment',{})
    if worker:
        if worker.get('NEVOLIUM_MEMORY_PROJECTOR_MODE') != 'real': errors.append('Worker production memory must be real')
        if urlsplit(worker.get('MEM0_DATABASE_URL','')).username != 'mem0_app': errors.append('Worker must use mem0_app')
        if not worker.get('NEVOLIUM_MODEL_ASSETS_MANIFEST'): errors.append('Worker model bundle required')
    return errors


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['check','up'])
    p.add_argument('--env-file', default='.env.production')
    p.add_argument('--profile', action='append', default=[])
    p.add_argument('--web-mcp', action='store_true')
    p.add_argument(
        '--keycloak-bootstrap',
        action='store_true',
        help='render the explicit one-time Keycloak bootstrap overlay',
    )
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    command = ['docker','compose','--env-file',str(Path(args.env_file).resolve()),'-f','compose.yaml','-f','compose.production.yaml']
    if args.keycloak_bootstrap:
        command += ['-f', 'compose.keycloak-bootstrap.yaml']
    if 'observability' in args.profile:
        command += ['-f','compose.observability.yaml']
    if args.web_mcp:
        command += ['-f','compose.web-mcp.yaml','-f','compose.web-mcp.production.yaml']
        args.profile.append('search')
    for profile in args.profile: command += ['--profile',profile]
    result = subprocess.run([*command,'config','--format','json'],cwd=root,capture_output=True,text=True)
    if result.returncode:
        raise SystemExit('Compose could not render this production topology; configuration output withheld')
    errors = validate(json.loads(result.stdout))
    if errors: raise SystemExit('Production configuration refused:\n- '+'\n- '.join(errors))
    print('Production topology configuration accepted; runtime credentials/assets and D04 engine proofs still apply')
    if args.action == 'up':
        subprocess.run([*command,'up','-d','--build'],cwd=root,check=True)


if __name__ == '__main__': main()
