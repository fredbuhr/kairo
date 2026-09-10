from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import UniqueConstraint

from kairo_core.ui_layouts import MAX_WORKSPACE_LAYOUT_BYTES, _validate_layout_size, router
from kairo_core.ui_models import WorkspaceLayout


def main() -> None:
    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in WorkspaceLayout.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("subject_ref", "workspace_key") in unique_sets, unique_sets

    _validate_layout_size({"grid": {"panels": ["command", "news", "research"]}})
    try:
        _validate_layout_size({"oversized": "x" * (MAX_WORKSPACE_LAYOUT_BYTES + 1)})
    except HTTPException as exc:
        assert exc.status_code == 413, exc
    else:
        raise AssertionError("Oversized workspace layout was accepted")

    methods_by_path = {
        route.path: set(route.methods or set())
        for route in router.routes
        if getattr(route, "path", None)
    }
    path = "/v1/ui/workspaces/{workspace_key}/layout"
    assert path in methods_by_path, methods_by_path
    assert {"GET", "PUT"}.issubset(methods_by_path[path]), methods_by_path[path]

    print(
        "PASS: workspace layouts are owner-keyed, size-bounded and exposed through the canonical UI API"
    )


if __name__ == "__main__":
    main()
