from __future__ import annotations

from sqlalchemy.dialects import postgresql

from kairo_core.research_context import (
    MAX_GRAPHITI_CONVERSATION_GROUPS,
    build_graphiti_scope_statement,
    router as research_context_router,
)


def main() -> None:
    statement = build_graphiti_scope_statement(requester_subject="user-a")
    compiled = statement.compile(dialect=postgresql.dialect())
    rendered = str(compiled).lower()
    params = {str(value) for value in compiled.params.values()}

    assert "conversations.subject_ref" in rendered, rendered
    assert "conversations.updated_at" in rendered, rendered
    assert "user-a" in params, compiled.params
    assert str(MAX_GRAPHITI_CONVERSATION_GROUPS + 1) in params, compiled.params

    paths = {getattr(route, "path", "") for route in research_context_router.routes}
    assert "/internal/v1/research/tasks/{task_id}/derived-memory-scope" in paths, paths

    print(
        "PASS: Core derives Mem0/Graphiti Research scope only from requester-owned canonical "
        "conversations, bounds the Graphiti group list and registers the scope endpoint on the "
        "dedicated internal Research Context router"
    )


if __name__ == "__main__":
    main()
