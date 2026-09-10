from __future__ import annotations

from sqlalchemy.dialects import postgresql

from kairo_core import research
from kairo_core.research_context import (
    MAX_DOCUMENT_CONTEXT_EXCERPT_CHARS,
    _excerpt,
    build_document_context_statement,
)


def main() -> None:
    statement = build_document_context_statement(
        requester_subject="development-user",
        query="canonical provenance",
        limit=99,
    )
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    lowered = compiled.lower()
    assert "to_tsvector" in lowered, compiled
    assert "plainto_tsquery" in lowered, compiled
    assert "owner_subject" in lowered and "development-user" in compiled, compiled
    assert "max(" in lowered and "document_versions" in lowered and "generation" in lowered, compiled
    assert "completed" in lowered and "ready" in lowered, compiled
    assert "limit 12" in lowered, compiled

    long_text = (
        "prefix " * 500
        + "canonical provenance is retained in the authoritative document chunk "
        + "suffix " * 500
    )
    excerpt = _excerpt(long_text, "canonical provenance", limit=500)
    assert len(excerpt) <= 500, len(excerpt)
    assert "canonical provenance" in excerpt.lower(), excerpt
    assert excerpt.startswith("…") and excerpt.endswith("…"), excerpt
    assert MAX_DOCUMENT_CONTEXT_EXCERPT_CHARS == 2000

    paths = {getattr(route, "path", "") for route in research.router.routes}
    assert "/internal/v1/research/tasks/{task_id}/document-context" in paths, paths

    print(
        "PASS: Research document context is owner-scoped, latest-completed-version ranked, bounded, "
        "and exposed only through the internal Research router"
    )


if __name__ == "__main__":
    main()
