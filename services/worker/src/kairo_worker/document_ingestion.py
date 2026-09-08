from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import os
import tempfile
from typing import Any

import httpx
from temporalio import activity

from .config import settings


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def _chunk_text(text: str, *, max_chars: int = 4000) -> list[dict[str, Any]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append({"text": "\n\n".join(current), "metadata": {"kind": "text"}})
                current = []
                current_len = 0
            for offset in range(0, len(paragraph), max_chars):
                piece = paragraph[offset : offset + max_chars].strip()
                if piece:
                    chunks.append({"text": piece, "metadata": {"kind": "text", "split": True}})
            continue
        extra = len(paragraph) + (2 if current else 0)
        if current and current_len + extra > max_chars:
            chunks.append({"text": "\n\n".join(current), "metadata": {"kind": "text"}})
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += extra
    if current:
        chunks.append({"text": "\n\n".join(current), "metadata": {"kind": "text"}})
    return chunks


def _plain_text_fallback(content: bytes, media_type: str | None) -> tuple[str, str, str | None, dict[str, Any]]:
    allowed = {
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "application/json",
        "text/csv",
        "text/html",
    }
    if (media_type or "").split(";", 1)[0].lower() not in allowed:
        raise RuntimeError("Docling is unavailable and this media type has no deterministic fallback parser")
    return content.decode("utf-8", errors="replace"), "text-fallback", None, {"docling_available": False}


def _parse_with_docling(content: bytes, filename: str | None) -> tuple[str, str, str | None, dict[str, Any]]:
    from docling.document_converter import DocumentConverter

    suffix = os.path.splitext(filename or "document.bin")[1] or ".bin"
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(content)
            temp_path = handle.name
        result = DocumentConverter().convert(temp_path)
        text = result.document.export_to_markdown()
        try:
            version = importlib.metadata.version("docling")
        except importlib.metadata.PackageNotFoundError:
            version = None
        return text, "docling", version, {"docling_available": True, "export": "markdown"}
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


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


@activity.defn
async def perform_document_ingestion(payload: dict[str, Any]) -> dict[str, Any]:
    task_input = payload.get("task_input") or {}
    version_id = str(task_input.get("document_version_id") or "")
    if not version_id:
        raise RuntimeError("document.ingest task is missing document_version_id")

    source = await _fetch_source(version_id)
    activity.heartbeat({"stage": "source-resolved", "document_version_id": version_id})
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as client:
        response = await client.get(str(source["download_url"]))
        response.raise_for_status()
        content = response.content

    actual_sha256 = hashlib.sha256(content).hexdigest()
    expected_sha256 = str(source.get("source_sha256") or "")
    if expected_sha256 and actual_sha256 != expected_sha256:
        raise RuntimeError("Source asset digest does not match canonical metadata")

    media_type = source.get("media_type")
    if importlib.util.find_spec("docling") is not None:
        text, parser, parser_version, parser_metadata = _parse_with_docling(
            content, source.get("filename")
        )
    else:
        text, parser, parser_version, parser_metadata = _plain_text_fallback(content, media_type)

    chunks = _chunk_text(text)
    if not chunks:
        raise RuntimeError("Document parser produced no textual chunks")
    activity.heartbeat({"stage": "parsed", "chunk_count": len(chunks)})

    report = await _report_complete(
        version_id,
        {
            "parser": parser,
            "parser_version": parser_version,
            "source_sha256": actual_sha256,
            "chunks": chunks,
            "metadata": {
                **parser_metadata,
                "source_media_type": media_type,
                "source_size_bytes": len(content),
                "chunking": {"strategy": "paragraph-pack", "max_chars": 4000},
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
