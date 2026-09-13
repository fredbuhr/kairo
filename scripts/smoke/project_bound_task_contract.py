from __future__ import annotations

from sqlalchemy.dialects import postgresql

from nevolium_core.auth import Principal, require_nevolium_user
from nevolium_core.config import settings
from nevolium_core.main import app
from nevolium_core.project_access import owned_tasks_statement
from nevolium_core.research import router as research_router


def _principal(subject: str) -> Principal:
    return Principal(subject=subject, username=None, email=None, roles=frozenset({"nevolium-user"}), claims={})


def _dependency_calls(route) -> set:
    return {dependency.call for dependency in route.dependant.dependencies}


def main() -> None:
    original_auth = settings.nevolium_auth_enabled
    try:
        settings.nevolium_auth_enabled = True
        compiled = owned_tasks_statement(_principal("alice")).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
        rendered = str(compiled).lower()
        assert "join projects" in rendered, rendered
        assert "projects.owner_subject" in rendered and "alice" in rendered, rendered
        assert "is null" not in rendered, rendered
    finally:
        settings.nevolium_auth_enabled = original_auth

    task_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) in {"/v1/tasks", "/v1/tasks/{task_id}"}
    ]
    methods = {(route.path, tuple(sorted(route.methods or set()))) for route in task_routes}
    assert ("/v1/tasks", ("GET",)) in methods, methods
    assert ("/v1/tasks", ("POST",)) in methods, methods
    assert ("/v1/tasks/{task_id}", ("GET",)) in methods, methods
    for route in task_routes:
        assert require_nevolium_user in _dependency_calls(route), (route.path, route.methods)

    research_create = next(
        route
        for route in research_router.routes
        if getattr(route, "path", None) == "/v1/research/runs" and "POST" in (route.methods or set())
    )
    assert require_nevolium_user in _dependency_calls(research_create), _dependency_calls(research_create)

    print(
        "PASS: public Task collection/item APIs require user identity, Task listing is Project-owner scoped, "
        "and Research launch remains authenticated for owned-Project enforcement"
    )


if __name__ == "__main__":
    main()
