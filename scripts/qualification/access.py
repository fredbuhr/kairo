"""Bounded, read-only checks of the public Nevolium API and ingress; no deployment."""
import asyncio
import json
import ssl
import time
from urllib.parse import urlsplit


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
READ_PATHS = ('/v1/projects?limit=20', '/v1/today?limit=20', '/v1/work-capacity')
PROTECTED_PATHS = ('/internal/v1/work-capacity/acquire', '/docs', '/redoc',
                   '/openapi.json', '/health/trust')


class ProbeFailure(Exception):
    """Only fixed diagnostic codes, never response bodies, URLs or credentials."""

    def __init__(self, reason, status=None):
        super().__init__(reason)
        self.status = status


def origin(value):
    url = urlsplit(value)
    if not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise ValueError('Provide a bare Core origin without credentials')
    if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in {'127.0.0.1', 'localhost', '::1'}):
        raise ValueError('Target must use HTTPS, or HTTP on loopback')
    return url


def tls_context(ca_file=None):
    # Never offer verify=False. A private CA must be explicitly provided by the operator.
    return ssl.create_default_context(cafile=str(ca_file) if ca_file else None)


def valid_payload(path, payload):
    if path.startswith('/v1/projects?'):
        return isinstance(payload, list) and all(
            isinstance(row, dict) and isinstance(row.get('id'), str) and isinstance(row.get('name'), str)
            for row in payload)
    if path.startswith('/v1/today?'):
        return (isinstance(payload, dict) and isinstance(payload.get('day'), str)
                and isinstance(payload.get('timezone'), str)
                and isinstance(payload.get('next_cursors'), dict)
                and all(isinstance(payload.get(key), list) for key in
                        ('overdue', 'in_progress', 'due_today', 'planned', 'completed_today', 'backlog')))
    if path == '/v1/work-capacity':
        return isinstance(payload, dict) and all(
            type(payload.get(key)) is int and payload[key] >= 0
            for key in ('waiting', 'active', 'concurrency_limit', 'pending_limit'))
    return False


async def checked_get(client, path, token=None, *, denied=None):
    headers = {'Accept': 'application/json', 'Accept-Encoding': 'identity'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    # HTTPX's socket timeout alone does not bound a peer that drips bytes forever.
    async with asyncio.timeout(10):
        async with client.stream('GET', path, headers=headers) as response:
            status = response.status_code
            if denied is not None:
                if status not in denied:
                    raise ProbeFailure('denial-status-mismatch', status)
                return {'http_status': status}
            if status != 200:
                raise ProbeFailure('api-status-mismatch', status)
            if response.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                raise ProbeFailure('api-json-required')
            if response.headers.get('content-encoding', 'identity').lower() != 'identity':
                raise ProbeFailure('encoded-response-refused')
            length = response.headers.get('content-length')
            if length:
                if not length.isdecimal() or int(length) > MAX_RESPONSE_BYTES:
                    raise ProbeFailure('response-size-limit')
            body = bytearray()
            async for chunk in response.aiter_raw(chunk_size=65536):
                if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise ProbeFailure('response-size-limit')
                body.extend(chunk)
            try:
                payload = json.loads(body)
            except (ValueError, RecursionError):
                raise ProbeFailure('api-json-invalid') from None
            if not valid_payload(path, payload):
                raise ProbeFailure('api-shape-mismatch')
            return {'http_status': status, 'response_bytes': len(body), 'nevolium_shape_valid': True}


async def preflight(client, evidence, token):
    probes = [('anonymous-projects-denied', '/v1/projects?limit=1', None, {401, 403}),
              ('invalid-token-denied', '/v1/projects?limit=1', 'd04-invalid-token', {401, 403})]
    probes += [('authenticated-' + name, path, token, None) for name, path in (
        ('projects', '/v1/projects?limit=1'), ('today', '/v1/today?limit=1'),
        ('capacity', '/v1/work-capacity'))]
    probes += [('ingress-denied-' + str(index), path, token, {403, 404})
               for index, path in enumerate(PROTECTED_PATHS, 1)]
    evidence.data['preflight'] = {'status': 'running', 'authenticated_tokens_tested': 1,
                                 'request_limit': len(probes), 'protected_get_paths': list(PROTECTED_PATHS)}
    for name, path, access_token, denied in probes:
        row = {'id': name, 'status': 'running', 'threshold_seconds': 10}
        evidence.data['cases'].append(row)
        evidence.save()
        started = time.monotonic()
        try:
            row['details'] = await checked_get(client, path, access_token, denied=denied)
            row['status'] = 'passed'
        except Exception as exc:
            row.update(status='failed', error_class=type(exc).__name__)
            if isinstance(exc, ProbeFailure):
                row['reason'] = str(exc)
                if exc.status is not None:
                    row['http_status'] = exc.status
            evidence.data['preflight']['status'] = 'failed'
            raise
        finally:
            row['elapsed_seconds'] = round(time.monotonic() - started, 3)
            evidence.save()
    evidence.data['anonymous_access_rejected'] = True
    evidence.data['preflight']['status'] = 'passed'
    evidence.save()
