from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from .owned_process import run_owned_process
from .config import settings
from .work_capacity import current_work_lease, run_admitted

# Core admits at most four heavy activities globally; this local guard protects parser memory.
_document_slots = asyncio.Semaphore(settings.kairo_document_max_concurrent)
DOCUMENT_ACTIVITY_SECONDS = 540  # Below the existing ten-minute Temporal activity deadline.


def _heartbeat(value: dict[str, Any]) -> None:
    if activity.in_activity():
        activity.heartbeat(value)


async def _keep_alive(version_id: str) -> None:
    while True:
        _heartbeat({"stage": "ingesting", "document_version_id": version_id})
        await asyncio.sleep(5)


async def _run_parser(source_path: Path, media_type: str) -> dict[str, Any]:
    result_path = source_path.parent / "parsed.json"
    # The parser needs model/cache paths, not Core tokens, database passwords or API keys.
    allowed = {"PATH", "PYTHONPATH", "HOME", "LANG", "LC_ALL", "HF_HOME",
               "HF_HUB_CACHE", "TRANSFORMERS_CACHE", "DOCLING_ARTIFACTS_PATH", "CUDA_VISIBLE_DEVICES"}
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                        "TMPDIR": str(source_path.parent)})
    try:
        returncode = await run_owned_process(
            sys.executable, "-m", "kairo_worker.document_parser", str(source_path), str(result_path),
            media_type, str(settings.kairo_document_max_text_chars), environment=environment,
            timeout=settings.kairo_document_parse_timeout_seconds,
        )
    except TimeoutError as exc:
        raise ApplicationError("Document parser exceeded configured time limit", non_retryable=True) from exc
    if returncode != 0:
        raise ApplicationError(f"Document parser exited with code {returncode}", non_retryable=True)
    # JSON escaping can expand one source character to six bytes. Bound before materialization.
    if not result_path.is_file() or result_path.stat().st_size > settings.kairo_document_max_text_chars * 6 + 65536:
        raise ApplicationError("Document parser result is missing or exceeds configured limit", non_retryable=True)
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ApplicationError("Document parser produced invalid output", non_retryable=True) from exc
    if not isinstance(result, dict):
        raise ApplicationError("Document parser produced invalid output", non_retryable=True)
    if result.get("error"):
        raise ApplicationError(str(result["error"]), non_retryable=not result.get("retryable", False))
    return result


async def _download_source(source: dict[str, Any], path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as client:
        async with client.stream("GET", str(source["download_url"])) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > settings.kairo_document_max_source_bytes:
                raise ApplicationError("Document source exceeds configured byte limit", non_retryable=True)
            with path.open("wb") as handle:
                async for piece in response.aiter_bytes(chunk_size=65536):
                    size += len(piece)
                    if size > settings.kairo_document_max_source_bytes:
                        raise ApplicationError("Document source exceeds configured byte limit", non_retryable=True)
                    digest.update(piece)
                    handle.write(piece)
    actual = digest.hexdigest()
    expected = str(source.get("source_sha256") or "")
    if expected and actual != expected:
        raise ApplicationError("Source asset digest does not match canonical metadata", non_retryable=True)
    return actual, size


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


async def _fetch_source(version_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/documents/versions/{version_id}/source",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def _report_complete(version_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/documents/versions/{version_id}/complete",
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def _ingest(version_id: str) -> dict[str, Any]:
    source = await _fetch_source(version_id)
    _heartbeat({"stage": "source-resolved", "document_version_id": version_id})
    suffix = Path(str(source.get("filename") or "document.bin")).suffix
    # Source metadata cannot choose a directory or an unbounded filename.
    suffix = suffix if suffix and len(suffix) <= 16 else ".bin"
    with tempfile.TemporaryDirectory(prefix="kairo-document-") as directory:
        path = Path(directory) / ("source" + suffix)
        actual_sha256, source_size = await _download_source(source, path)
        parsed = await _run_parser(path, str(source.get("media_type") or ""))

    chunks = parsed["chunks"]
    parser, parser_version = parsed["parser"], parsed["parser_version"]
    _heartbeat({"stage": "parsed", "chunk_count": len(chunks)})

    report = await _report_complete(
        version_id,
        {
            "parser": parser,
            "parser_version": parser_version,
            "source_sha256": actual_sha256,
            "chunks": chunks,
            "metadata": {
                **parsed["metadata"],
                "source_media_type": source.get("media_type"),
                "source_size_bytes": source_size,
                "chunking": {"strategy": "paragraph-pack", "max_chars": 4000},
                "work_lease_token": current_work_lease.get(),
            },
        },
    )
    return {
        "kind": "document-ingestion",
        "title": f"Document ingestion — {source.get('title') or version_id}",
        "content": {
            "document_id": source["document_id"],
            "document_version_id": version_id,
            "generation": source["generation"],
            "parser": parser,
            "parser_version": parser_version,
            "chunk_count": report["chunk_count"],
            "source_sha256": actual_sha256,
        },
    }


@activity.defn
async def perform_document_ingestion(payload: dict[str, Any]) -> dict[str, Any]:
    return await run_admitted(payload, lambda: _perform_document_ingestion(payload))


async def _perform_document_ingestion(payload: dict[str, Any]) -> dict[str, Any]:
    version_id = str((payload.get("task_input") or {}).get("document_version_id") or "")
    if not version_id:
        raise ApplicationError("document.ingest task is missing document_version_id", non_retryable=True)
    heartbeat = asyncio.create_task(_keep_alive(version_id), name="document-ingestion-heartbeat")
    try:
        async with asyncio.timeout(DOCUMENT_ACTIVITY_SECONDS):
            # Acquire before download: queued documents do not retain source bytes/files/models.
            async with _document_slots:
                return await _ingest(version_id)
    except TimeoutError as exc:
        raise ApplicationError("Document ingestion exceeded bounded processing window", non_retryable=True) from exc
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)
