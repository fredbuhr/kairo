from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from .config import settings
from .memory_projection import _get_mem0_instance

MAX_DERIVED_CONTEXT_ITEMS_PER_SOURCE = 6
MAX_DERIVED_CONTEXT_EXCERPT_CHARS = 1_500
GRAPHITI_SCAN_LIMIT = 24

GraphitiSearch = Callable[[str, list[str], int], Awaitable[list[dict[str, Any]]]]
Mem0Search = Callable[[str, str, int], list[dict[str, Any]]]

GRAPHITI_EPISODE_QUERY = """
MATCH (e:Episodic)
WHERE e.group_id IN $group_ids
WITH e, [term IN $terms WHERE toLower(coalesce(e.content, '')) CONTAINS term] AS matched_terms
WITH e, size(matched_terms) AS score
WHERE score > 0
RETURN e.uuid AS uuid,
       e.group_id AS group_id,
       e.content AS content,
       e.created_at AS created_at,
       score
ORDER BY score DESC, e.created_at DESC
LIMIT $limit
""".strip()


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def _excerpt(value: Any, limit: int = MAX_DERIVED_CONTEXT_EXCERPT_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for match in re.finditer(r"[\wÀ-ÖØ-öø-ÿ]{3,}", query.lower(), flags=re.UNICODE):
        value = match.group(0)
        if value not in terms:
            terms.append(value)
        if len(terms) >= 8:
            break
    return terms


def _uuid_from_group_id(group_id: str) -> str | None:
    prefix = "conversation:"
    if not group_id.startswith(prefix):
        return None
    value = group_id.removeprefix(prefix).strip()
    return value or None


def normalize_mem0_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for position, row in enumerate(results[:MAX_DERIVED_CONTEXT_ITEMS_PER_SOURCE], start=1):
        memory = _excerpt(row.get("memory"))
        if not memory:
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        try:
            score = max(0.0, min(1.0, float(row.get("score") or 0.0)))
        except (TypeError, ValueError):
            score = 0.0
        items.append(
            {
                "context_id": f"M{position}",
                "source": "mem0",
                "excerpt": memory,
                "rank": score,
                "projection_key": str(row.get("id") or "") or None,
                "canonical_message_id": (
                    str(metadata.get("kairo_message_id"))
                    if metadata.get("kairo_message_id")
                    else None
                ),
                "canonical_conversation_id": (
                    str(metadata.get("kairo_conversation_id"))
                    if metadata.get("kairo_conversation_id")
                    else None
                ),
            }
        )
    return items


def normalize_graphiti_results(results: list[dict[str, Any]], *, term_count: int) -> list[dict[str, Any]]:
    divisor = max(1, term_count)
    items: list[dict[str, Any]] = []
    for position, row in enumerate(results[:MAX_DERIVED_CONTEXT_ITEMS_PER_SOURCE], start=1):
        excerpt = _excerpt(row.get("content"))
        if not excerpt:
            continue
        try:
            matches = max(0, int(row.get("score") or 0))
        except (TypeError, ValueError):
            matches = 0
        group_id = str(row.get("group_id") or "")
        items.append(
            {
                "context_id": f"G{position}",
                "source": "graphiti",
                "excerpt": excerpt,
                "rank": min(1.0, matches / divisor),
                "projection_key": str(row.get("uuid") or "") or None,
                "canonical_message_id": str(row.get("uuid") or "") or None,
                "canonical_conversation_id": _uuid_from_group_id(group_id),
            }
        )
    return items


def _mem0_search_sync(query: str, mem0_user_id: str, limit: int) -> list[dict[str, Any]]:
    memory = _get_mem0_instance()
    payload = memory.search(
        query,
        filters={"user_id": mem0_user_id},
        top_k=max(1, min(MAX_DERIVED_CONTEXT_ITEMS_PER_SOURCE, limit)),
        threshold=0.1,
    )
    raw = payload.get("results") if isinstance(payload, dict) else []
    return [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


async def _graphiti_search(query: str, group_ids: list[str], limit: int) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    if not terms or not group_ids:
        return []

    from graphiti_core.driver.neo4j_driver import Neo4jDriver

    driver = Neo4jDriver(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    try:
        records, _, _ = await driver.execute_query(
            GRAPHITI_EPISODE_QUERY,
            group_ids=group_ids,
            terms=terms,
            limit=max(GRAPHITI_SCAN_LIMIT, limit),
            routing_="r",
        )
        return [dict(record) for record in records]
    finally:
        await driver.close()


async def collect_derived_memory_context(
    *,
    query: str,
    mem0_user_id: str | None,
    graphiti_group_ids: list[str],
    limit_per_source: int = MAX_DERIVED_CONTEXT_ITEMS_PER_SOURCE,
    mem0_search: Mem0Search | None = None,
    graphiti_search: GraphitiSearch | None = None,
) -> dict[str, Any]:
    """Read rebuildable derived stores independently and never make either store authoritative."""

    limit = max(1, min(MAX_DERIVED_CONTEXT_ITEMS_PER_SOURCE, int(limit_per_source)))
    terms = _query_terms(query)
    items: list[dict[str, Any]] = []
    sources: dict[str, dict[str, Any]] = {}

    async def read_mem0() -> None:
        if not mem0_user_id:
            sources["mem0"] = {"status": "skipped", "reason": "owner_scope_unavailable"}
            return
        try:
            reader = mem0_search or _mem0_search_sync
            raw = await asyncio.to_thread(reader, query, mem0_user_id, limit)
            normalized = normalize_mem0_results(raw)
            items.extend(normalized)
            sources["mem0"] = {"status": "ok", "count": len(normalized)}
        except Exception as exc:  # noqa: BLE001 - derived context is best-effort by design
            sources["mem0"] = {
                "status": "unavailable",
                "error": f"{type(exc).__name__}: {exc}"[:500],
            }

    async def read_graphiti() -> None:
        if not graphiti_group_ids:
            sources["graphiti"] = {"status": "skipped", "reason": "no_owned_conversation_groups"}
            return
        try:
            reader = graphiti_search or _graphiti_search
            raw = await reader(query, graphiti_group_ids, limit)
            normalized = normalize_graphiti_results(raw, term_count=len(terms))
            items.extend(normalized)
            sources["graphiti"] = {"status": "ok", "count": len(normalized)}
        except Exception as exc:  # noqa: BLE001 - derived context is best-effort by design
            sources["graphiti"] = {
                "status": "unavailable",
                "error": f"{type(exc).__name__}: {exc}"[:500],
            }

    await asyncio.gather(read_mem0(), read_graphiti())
    items.sort(key=lambda item: (-float(item.get("rank") or 0), str(item.get("context_id") or "")))
    return {
        "items": items,
        "sources": sources,
        "derived": True,
        "authoritative": False,
    }


async def read_research_derived_memory_context(
    *, task_id: str, client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """Fetch Core-owned scope, then read derived stores only within that exact scope."""

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=15.0)
    try:
        response = await http.get(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/research/tasks/{task_id}/derived-memory-scope",
            headers=_headers(),
        )
        response.raise_for_status()
        scope = response.json()
    finally:
        if owns_client:
            await http.aclose()

    query = str(scope.get("query") or "").strip()
    if not query:
        return {
            "items": [],
            "sources": {},
            "derived": True,
            "authoritative": False,
            "reason": "query_unavailable",
        }

    result = await collect_derived_memory_context(
        query=query,
        mem0_user_id=(str(scope.get("mem0_user_id")) if scope.get("mem0_user_id") else None),
        graphiti_group_ids=[
            str(value) for value in scope.get("graphiti_group_ids") or [] if str(value)
        ],
    )
    result["scope"] = {
        "requester_subject": scope.get("requester_subject"),
        "graphiti_groups_truncated": bool(scope.get("graphiti_groups_truncated")),
    }
    return result
