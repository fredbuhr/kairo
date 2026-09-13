from __future__ import annotations

from sqlalchemy.dialects import postgresql

from nevolium_core.auth import Principal, require_nevolium_user
from nevolium_core.config import settings
from nevolium_core.main import app
from nevolium_core.models import Project
from nevolium_core.project_access import owned_project_clause


def _principal(subject: str) -> Principal:
    return Principal(subject=subject, username=None, email=None, roles=frozenset({"nevolium-user"}), claims={})


def main() -> None:
    owner_column = Project.__table__.c.owner_subject
    assert owner_column.nullable is True
    assert owner_column.type.length == 320
    indexes = {index.name for index in Project.__table__.indexes}
    assert "ix_projects_owner_status" in indexes, indexes

    original_auth = settings.nevolium_auth_enabled
    try:
        settings.nevolium_auth_enabled = True
        authenticated = str(
            owned_project_clause(_principal("alice")).compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        ).lower()
        assert "alice" in authenticated, authenticated
        assert "is null" not in authenticated, authenticated

        settings.nevolium_auth_enabled = False
        local_legacy = str(
            owned_project_clause(_principal("development-user")).compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        ).lower()
        assert "development-user" in local_legacy, local_legacy
        assert "is null" in local_legacy, local_legacy
    finally:
        settings.nevolium_auth_enabled = original_auth

    project_routes = [route for route in app.routes if getattr(route, "path", None) == "/v1/projects"]
    assert len(project_routes) == 2, [(route.path, route.methods) for route in project_routes]
    for route in project_routes:
        dependencies = {dependency.call for dependency in route.dependant.dependencies}
        assert require_nevolium_user in dependencies, (route.methods, dependencies)

    print(
        "PASS: Projects carry canonical owner subjects, authenticated APIs are owner-scoped, "
        "and ownerless legacy projects are visible only in local auth-disabled mode"
    )


if __name__ == "__main__":
    main()
