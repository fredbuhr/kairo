from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

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


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold().strip()


def _parse_navigation(text: str) -> tuple[str, str] | None:
    isolated = _ISOLATE_PATTERN.match(text)
    if isolated:
        query = isolated.group(1).strip(" \t\r\n'\"“”‘’")
        return ("isolate_entity", query) if len(query) >= 2 else None

    focused = _FOCUS_PATTERN.match(text)
    if focused:
        query = focused.group(1).strip(" \t\r\n'\"“”‘’")
        return ("focus_entity", query) if len(query) >= 2 else None
    return None


@router.post("/resolve", response_model=GraphUIDirectiveResolveRead)
async def resolve_graph_ui_directive(
    body: GraphUIDirectiveResolveRequest,
    session: AsyncSession = Depends(get_session),
) -> GraphUIDirectiveResolveRead:
    parsed = _parse_navigation(body.text)
    if parsed is None:
        return GraphUIDirectiveResolveRead(outcome="not_navigation")

    kind, query = parsed
    search = await graph_search(q=query, limit=8, session=session)
    if not search.nodes:
        return GraphUIDirectiveResolveRead(outcome="not_found", query=query)

    normalized_query = _normalize(query)
    exact = [node for node in search.nodes if _normalize(node.label) == normalized_query]
    if len(exact) == 1:
        chosen = exact[0]
    elif len(search.nodes) == 1:
        chosen = search.nodes[0]
    else:
        return GraphUIDirectiveResolveRead(
            outcome="ambiguous",
            query=query,
            candidates=search.nodes[:6],
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
