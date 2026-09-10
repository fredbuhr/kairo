from __future__ import annotations

import asyncio
from typing import Any

import httpx
from temporalio import activity

from .config import settings
from .research_memory_context import read_research_derived_memory_context

MAX_CONTEXT_PACK_DOCUMENTS = 6
MAX_CONTEXT_PACK_DERIVED = 6
MAX_CONTEXT_PACK_ITEMS = MAX_CONTEXT_PACK_DOCUMENTS + MAX_CONTEXT_PACK_DERIVED
MAX_CONTEXT_PACK_CHARS = 20_000


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def _bounded_excerpt(value: Any, remaining: int) -> str:
    text = str(value or "").strip()
    limit = max(0, remaining)
    if len(text) <= limit:
        return text
    if limit <= 1:
        return "" if limit == 0 else "…"
    return text[: limit - 1] + "…"


def _document_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("items") if isinstance(payload.get("items"), list) else []
    items: list[dict[str, Any]] = []
    for row in raw[:MAX_CONTEXT_PACK_DOCUMENTS]:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("context_id") or "").strip()
        excerpt = str(row.get("excerpt") or "").strip()
        if not evidence_id or not excerpt:
            continue
        items.append(
            {
                "evidence_id": evidence_id,
                "source_type": "document",
                "source": "postgresql-document-chunks",
                "authority": "canonical",
                "title": str(row.get("title") or "") or None,
                "excerpt": excerpt,
                "rank": float(row.get("rank") or 0.0),
                "provenance": {
                    "document_id": row.get("document_id"),
                    "document_project_id": row.get("document_project_id"),
                    "document_version_id": row.get("document_version_id"),
                    "chunk_id": row.get("chunk_id"),
                    "generation": row.get("generation"),
                    "ordinal": row.get("ordinal"),
                    "content_sha256": row.get("content_sha256"),
                },
            }
        )
    return items


def _derived_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("items") if isinstance(payload.get("items"), list) else []
    candidates: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("context_id") or "").strip()
        excerpt = str(row.get("excerpt") or "").strip()
        source = str(row.get("source") or "").strip()
        if not evidence_id or not excerpt or source not in {"mem0", "graphiti"}:
            continue
        candidates.append(
            {
                "evidence_id": evidence_id,
                "source_type": "memory",
                "source": source,
                "authority": "derived",
                "title": None,
                "excerpt": excerpt,
                "rank": float(row.get("rank") or 0.0),
                "provenance": {
                    "projection_key": row.get("projection_key"),
                    "canonical_message_id": row.get("canonical_message_id"),
                    "canonical_conversation_id": row.get("canonical_conversation_id"),
                },
            }
        )

    candidates.sort(key=lambda item: (-float(item["rank"]), item["evidence_id"]))
    items: list[dict[str, Any]] = []
    seen_messages: set[str] = set()
    for item in candidates:
        message_id = str(item["provenance"].get("canonical_message_id") or "").strip()
        if message_id and message_id in seen_messages:
            continue
        if message_id:
            seen_messages.add(message_id)
        items.append(item)
        if len(items) >= MAX_CONTEXT_PACK_DERIVED:
            break
    return items


def build_research_context_pack(
    *,
    document_context: dict[str, Any] | None,
    derived_context: dict[str, Any] | None,
) -> dict[str, Any]:
    documents = _document_items(document_context or {})
    derived = _derived_items(derived_context or {})
    selected = [*documents, *derived][:MAX_CONTEXT_PACK_ITEMS]

    bounded: list[dict[str, Any]] = []
    remaining = MAX_CONTEXT_PACK_CHARS
    for item in selected:
        excerpt = _bounded_excerpt(item["excerpt"], remaining)
        if not excerpt:
            break
        copy = {**item, "excerpt": excerpt}
        bounded.append(copy)
        remaining -= len(excerpt)
        if remaining <= 0:
            break

    document_reason = (document_context or {}).get("reason")
    derived_sources = (derived_context or {}).get("sources")
    return {
        "items": bounded,
        "sources": {
            "documents": {
                "status": "ok" if document_context is not None else "unavailable",
                "count": len(documents),
                "reason": document_reason,
            },
            "mem0": (
                dict(derived_sources.get("mem0") or {})
                if isinstance(derived_sources, dict)
                else {"status": "unavailable"}
            ),
            "graphiti": (
                dict(derived_sources.get("graphiti") or {})
                if isinstance(derived_sources, dict)
                else {"status": "unavailable"}
            ),
        },
        "item_count": len(bounded),
        "character_count": sum(len(item["excerpt"]) for item in bounded),
        "max_character_count": MAX_CONTEXT_PACK_CHARS,
    }


def context_pack_model_records(context_pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Render the minimal evidence-shaped Context Pack supplied to planning/synthesis models."""

    records: list[dict[str, Any]] = []
    for item in context_pack.get("items") or []:
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "evidence_id": item.get("evidence_id"),
                "source_type": item.get("source_type"),
                "source": item.get("source"),
                "authority": item.get("authority"),
                "title": item.get("title"),
                "result_excerpt": item.get("excerpt"),
                "provenance": item.get("provenance") if isinstance(item.get("provenance"), dict) else {},
            }
        )
    return records


def context_pack_public_summary(context_pack: dict[str, Any]) -> dict[str, Any]:
    """Expose useful source health without persisting backend exception messages into Artifacts."""

    raw_sources = context_pack.get("sources") if isinstance(context_pack.get("sources"), dict) else {}
    sources: dict[str, dict[str, Any]] = {}
    for name in ("documents", "mem0", "graphiti"):
        raw = raw_sources.get(name) if isinstance(raw_sources.get(name), dict) else {}
        summary: dict[str, Any] = {"status": str(raw.get("status") or "unknown")}
        if raw.get("count") is not None:
            try:
                summary["count"] = max(0, int(raw["count"]))
            except (TypeError, ValueError):
                pass
        reason = str(raw.get("reason") or "").strip()
        if reason:
            summary["reason"] = reason[:200]
        sources[name] = summary

    def _non_negative_int(value: Any, fallback: int = 0) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return fallback

    return {
        "sources": sources,
        "item_count": _non_negative_int(context_pack.get("item_count")),
        "character_count": _non_negative_int(context_pack.get("character_count")),
        "max_character_count": _non_negative_int(
            context_pack.get("max_character_count"), MAX_CONTEXT_PACK_CHARS
        ),
    }


async def load_research_context_pack(
    *, task_id: str, client: httpx.AsyncClient
) -> dict[str, Any]:
    """Load canonical documents and derived memory independently; context failure never grants authority."""

    async def load_documents() -> dict[str, Any] | None:
        try:
            response = await client.get(
                f"{settings.kairo_core_url.rstrip('/')}/internal/v1/research/tasks/{task_id}/document-context",
                headers=_headers(),
                params={"limit": MAX_CONTEXT_PACK_DOCUMENTS},
            )
            response.raise_for_status()
            return response.json()
        except Exception:  # noqa: BLE001 - context enrichment is best-effort
            return None

    async def load_derived() -> dict[str, Any] | None:
        try:
            return await read_research_derived_memory_context(task_id=task_id, client=client)
        except Exception:  # noqa: BLE001 - derived stores are non-authoritative and best-effort
            return None

    document_context, derived_context = await asyncio.gather(load_documents(), load_derived())
    return build_research_context_pack(
        document_context=document_context,
        derived_context=derived_context,
    )


@activity.defn(name="prepare_research_context_pack")
async def prepare_research_context_pack(payload: dict[str, Any]) -> dict[str, Any]:
    """Create one bounded context snapshot that Temporal records before Research model work begins."""

    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("Research context preparation requires task_id")
    async with httpx.AsyncClient(timeout=20.0) as client:
        return await load_research_context_pack(task_id=task_id, client=client)
