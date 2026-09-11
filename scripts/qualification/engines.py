"""Exercise the actual locked Docling/Mem0/Graphiti adapters, never stub them.

Prepare is explicitly online; run must execute inside a read-only container on an internal
Docker network with only PostgreSQL/Neo4j. No credentials or source content enter the report.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import uuid

from common import Evidence, sha256, versions


def prepare(root):
    from docling.utils.model_downloader import download_models
    from fastembed import TextEmbedding
    from kairo_worker.memory_projection import MEM0_EMBEDDING_MODEL
    from kairo_worker.model_assets import inventory
    if (root / 'manifest.json').exists():
        raise ValueError('Use a new bundle for each explicit preparation')
    download_models(output_dir=root / 'docling', with_code_formula=False,
                    with_picture_classifier=False)
    model = TextEmbedding(model_name=MEM0_EMBEDDING_MODEL, cache_dir=str(root / 'fastembed'), threads=1)
    vector = next(iter(model.embed(['KAIRO qualification locale'])))
    assert len(vector) == 384
    revisions = set()
    for path in root.rglob('*.metadata'):
        revision = path.read_text().splitlines()[0]
        if re.fullmatch(r'[0-9a-f]{40}', revision):
            revisions.add((path.relative_to(root).as_posix().split('/.cache/')[0], revision))
    for path in root.rglob('snapshots'):
        for snapshot in path.iterdir():
            if snapshot.is_dir() and re.fullmatch(r'[0-9a-f]{40}', snapshot.name):
                revisions.add((path.parent.relative_to(root).as_posix(), snapshot.name))
    if not revisions:
        raise ValueError('No upstream model revision metadata was recorded')
    source = {'packages': versions(['docling', 'mem0ai', 'graphiti-core', 'fastembed']),
              'embedding_model': MEM0_EMBEDDING_MODEL,
              'selection': 'Docling locked defaults: layout/table/rapidocr; FastEmbed multilingual 384',
              'upstream_revisions': [{'bundle_path': path, 'commit': revision} for path, revision in sorted(revisions)],
              'other_assets': 'RapidOCR downloads selected by locked Docling/RapidOCR; exact file SHA-256 inventory is authoritative'}
    (root / 'manifest.json').write_text(json.dumps({'version': 1, 'sources': [source],
                                                   'files': inventory(root)}, indent=2))
    print('Explicit model preparation complete; execution proof still required', flush=True)


def make_pdf(path):
    # Original fixture with a real PDF text layer, no external document or renderer dependency.
    text = b'BT /F1 16 Tf 50 750 Td (KAIRO REAL PDF QUALIFICATION) Tj 0 -30 Td (The project deadline is 17 October 2026.) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length ' + str(len(text)).encode() + b' >>\nstream\n' + text + b'\nendstream']
    data = bytearray(b'%PDF-1.4\n'); offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data)); data.extend(f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(data)
    data.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        data.extend(f'{offset:010d} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    path.write_bytes(data)


def run(root, output):
    from kairo_worker.model_assets import verify_manifest
    from kairo_worker import memory_projection as memory
    evidence = Evidence('real-document-memory', output)
    evidence.data['versions'] = versions(['docling', 'docling-core', 'mem0ai', 'graphiti-core', 'fastembed', 'onnxruntime'])
    evidence.data['model_manifest_sha256'] = sha256(root / 'manifest.json')
    evidence.data['model_sources'] = json.loads((root / 'manifest.json').read_text())['sources']
    evidence.save()

    def boundaries():
        verify_manifest(root / 'manifest.json')
        assert os.environ.get('HF_HUB_OFFLINE') == '1'
        for host in ['1.1.1.1', '8.8.8.8']:
            try:
                with socket.create_connection((host, 443), timeout=2):
                    pass
            except OSError:
                continue
            raise AssertionError('Offline network proof requires denied public connections')
        try:
            (root / 'must-not-write').write_text('deny')
        except OSError:
            pass
        else:
            raise AssertionError('Model assets must be read only')
        return {'public_ip_probes_denied': 2, 'assets_read_only': True}
    evidence.case('offline-readonly-boundary', 15, boundaries)

    def pdf():
        from kairo_worker.document_ingestion import _run_parser
        from kairo_worker.config import settings
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proof.pdf'; make_pdf(path)
            # Same bounded child path as the Worker, not a simplified direct converter.
            result = asyncio.run(_run_parser(path, 'application/pdf'))
            assert result['parser'] == 'docling' and result['parser_version']
            text = ' '.join(c['text'] for c in result['chunks'])
            assert 'KAIRO REAL PDF QUALIFICATION' in text and '17 October 2026' in text
            return {'parser': result['parser'], 'chunks': len(result['chunks']),
                    'fixture_sha256': sha256(path), 'parse_timeout_seconds': settings.kairo_document_parse_timeout_seconds}
    evidence.case('pdf-docling-owned-child', 210, pdf)

    source = {'message_id': str(uuid.uuid4()), 'conversation_id': str(uuid.uuid4()),
              'subject_ref': 'd04:' + str(uuid.uuid4()), 'role': 'user',
              'content': 'Le projet Kairo doit conserver une memoire locale verifiable.',
              'source_version': 1, 'created_at': datetime.now(timezone.utc).isoformat()}

    def projection():
        reports = asyncio.run(memory._run_projection(source, 'real'))
        assert all(r['status'] == 'projected' for r in reports), [(r['projector'], r.get('error')) for r in reports]
        assert {r['metadata']['backend'] for r in reports} == {'mem0-pgvector', 'graphiti-neo4j'}
        again = asyncio.run(memory._run_projection(source, 'real'))
        assert all(r['status'] == 'projected' for r in again)
        assert [r['projection_key'] for r in reports] == [r['projection_key'] for r in again]
        assert again[0]['metadata']['reused'] is True
        return {'projectors': [r['projector'] for r in reports], 'replay_keys_unchanged': True,
                'generative_extraction': False}
    evidence.case('real-memory-owned-child-and-replay', 240, projection)

    def isolation():
        instance = memory._get_mem0_instance()
        own = instance.search(source['content'], filters={'user_id': memory._memory_scope(source)}, top_k=5)
        other = instance.search(source['content'], filters={'user_id': 'subject:d04:other'}, top_k=5)
        assert own['results'] and not other['results']
        from neo4j import GraphDatabase
        from kairo_worker.config import settings
        with GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)) as driver:
            rows, _, _ = driver.execute_query('MATCH (e:Episodic {uuid: $id}) RETURN e.content AS content, e.group_id AS scope', id=source['message_id'])
            assert len(rows) == 1 and source['content'] in rows[0]['content']
            assert rows[0]['scope'] == 'conversation:' + source['conversation_id']
        return {'semantic_search': True, 'other_scope_empty': True, 'graph_episode_count': 1}
    evidence.case('real-vector-search-and-graph-readback', 120, isolation)

    def missing_assets():
        # A new empty cache with Internet denied must fail, not fall back to mock embeddings.
        import subprocess
        with tempfile.TemporaryDirectory() as empty:
            env = dict(os.environ, FASTEMBED_CACHE_PATH=empty)
            code = 'from kairo_worker.memory_projection import _get_mem0_instance; _get_mem0_instance()'
            process = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, timeout=40)
            assert process.returncode != 0
        return {'missing_cache_rejected': True}
    evidence.case('missing-model-fails-closed', 45, missing_assets)
    evidence.case('model-bundle-unchanged', 30, lambda: verify_manifest(root / 'manifest.json'))
    evidence.finish()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--output', default='/evidence/engines.json')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.models)
    else:
        run(args.models, args.output)
