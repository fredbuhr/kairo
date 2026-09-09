from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .db import get_session
from .graph import graph_search
from .graph_schemas import (
    GraphEntityRef,
    GraphUIDirectiveRead,
    GraphUIDirectiveResolveRead,
    GraphUIDirectiveResolveRequest,
)


router = APIRouter(prefix="/v1/graph/directives", tags=["graph"])

_ISOLATE_PATTERN = re.compile(
    r"^\s*(?:isole(?:[- ]moi)?|montre\s+uniquement|affiche\s+uniquement|isolate)\s+(.+?)\s*[?!.]*$",
    flags=re.IGNORECASE,
)
_FOCUS_PATTERN = re.compile(
    r"^\s*(?:montre(?:[- ]moi)?|affiche|ouvre|va\s+[àa]|focus(?:se)?\s+sur|zoome\s+sur|show\s+me|open)\s+(.+?)\s*[?!.]*$",
    flags=re.IGNORECASE,
)
_TYPE_PREFIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(?:(?:le|un)\s+)?(?:projet|project)\s+(.+)$", re.IGNORECASE), "project"),
    (re.compile(r"^(?:(?:la|une)\s+)?t[âa]che\s+(.+)$", re.IGNORECASE), "task"),
    (re.compile(r"^(?:(?:le|un)\s+)?document\s+(.+)$", re.IGNORECASE), "document"),
    (re.compile(r"^(?:(?:la|une)\s+)?conversation\s+(.+)$", re.IGNORECASE), "conversation"),
    (re.compile(r"^(?:(?:l['’]|une?\s+))?approbation\s+(.+)$", re.IGNORECASE), "approval"),
    (re.compile(r"^(?:(?:le|un)\s+)?(?:fichier|file)\s+(.+)$", re.IGNORECASE), "asset"),
    (re.compile(r"^(?:(?:l['’]|un\s+))?(?:artefact|artifact)\s+(.+)$", re.IGNORECASE), "artifact"),
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold().strip()


def _typed_query(value: str) -> tuple[str, str | None]:
    query = value.strip(" \t\r\n'\"“”‘’")
    for pattern, entity_type in _TYPE_PREFIXES:
        matched = pattern.match(query)
        if matched:
            stripped = matched.group(1).strip(" \t\r\n'\"“”‘’")
            if len(stripped) >= 2:
                return stripped, entity_type
    return query, None


def _parse_navigation(text: str) -> tuple[str, str, str | None] | None:
    isolated = _ISOLATE_PATTERN.match(text)
    if isolated:
        query, entity_type = _typed_query(isolated.group(1))
        return ("isolate_entity", query, entity_type) if len(query) >= 2 else None

    focused = _FOCUS_PATTERN.match(text)
    if focused:
        query, entity_type = _typed_query(focused.group(1))
        return ("focus_entity", query, entity_type) if len(query) >= 2 else None
    return None


@router.post("/resolve", response_model=GraphUIDirectiveResolveRead)
async def resolve_graph_ui_directive(
    body: GraphUIDirectiveResolveRequest,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> GraphUIDirectiveResolveRead:
    parsed = _parse_navigation(body.text)
    if parsed is None:
        return GraphUIDirectiveResolveRead(outcome="not_navigation")

    kind, query, entity_type = parsed
    search = await graph_search(q=query, limit=12, principal=principal, session=session)
    candidates = [
        node for node in search.nodes if entity_type is None or node.entity_type == entity_type
    ]
    if not candidates:
        return GraphUIDirectiveResolveRead(outcome="not_found", query=query)

    normalized_query = _normalize(query)
    exact = [node for node in candidates if _normalize(node.label) == normalized_query]
    if len(exact) == 1:
        chosen = exact[0]
    elif len(candidates) == 1:
        chosen = candidates[0]
    else:
        return GraphUIDirectiveResolveRead(
            outcome="ambiguous",
            query=query,
            candidates=candidates[:6],
        )

    return GraphUIDirectiveResolveRead(
        outcome="directive",
        query=query,
        directive=GraphUIDirectiveRead(
            kind=kind,
            entity=GraphEntityRef(entity_type=chosen.entity_type, entity_id=chosen.id),
            label=chosen.label,
            depth=1,
            reason=(
                "deterministic.ui.isolate"
                if kind == "isolate_entity"
                else "deterministic.ui.focus"
            ),
        ),
    )
