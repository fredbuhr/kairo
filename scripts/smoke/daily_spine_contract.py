#!/usr/bin/env python3
"""Static/domain proof that Today, Projects and future Gantt share canonical Task planning state."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
import uuid

from pydantic import ValidationError

from kairo_core.models import Task
from kairo_core.planning import _planning_window, router
from kairo_core.schemas import TaskCreate

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    columns = set(Task.__table__.columns.keys())
    required = {"priority", "planned_start_at", "planned_end_at", "due_at"}
    missing = required - columns
    assert not missing, f"Task planning columns missing: {sorted(missing)}"

    constraint_names = {constraint.name for constraint in Task.__table__.constraints}
    assert "ck_tasks_priority_range" in constraint_names, constraint_names
    assert "ck_tasks_planned_window" in constraint_names, constraint_names

    route_contract = {
        (route.path, method)
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    assert ("/v1/tasks/{task_id}", "PATCH") in route_contract, route_contract
    assert ("/v1/today", "GET") in route_contract, route_contract

    # Public creation rejects ambiguous planning timestamps rather than guessing a timezone.
    try:
        TaskCreate(
            project_id=uuid.uuid4(),
            title="naive date must fail",
            due_at=datetime(2026, 9, 11, 9, 0),
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("TaskCreate accepted a timezone-naive due_at")

    try:
        TaskCreate(
            project_id=uuid.uuid4(),
            title="end without start must fail",
            planned_end_at=datetime(2026, 9, 11, 10, 0, tzinfo=UTC),
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("TaskCreate accepted planned_end_at without planned_start_at")

    # A local calendar day is not assumed to be 24h: Paris spring DST day is 23h in UTC.
    local_day, _zone, local_start, local_end = _planning_window(date(2026, 3, 29), "Europe/Paris")
    assert local_day == date(2026, 3, 29)
    duration = local_end.astimezone(UTC) - local_start.astimezone(UTC)
    assert duration.total_seconds() == 23 * 60 * 60, duration

    migration = (ROOT / "services/core/migrations/versions/0012_task_planning.py").read_text(
        encoding="utf-8"
    )
    assert 'revision = "0012_task_planning"' in migration
    assert 'down_revision = "0011_tool_invocation_ownership"' in migration

    app = (ROOT / "apps/web/src/App.tsx").read_text(encoding="utf-8")
    today = (ROOT / "apps/web/src/TodayWorkspace.tsx").read_text(encoding="utf-8")
    assert "import TodayWorkspace from './TodayWorkspace'" in app
    assert "key: 'today'" in app and "id: 'today-workspace'" in app
    assert "<TodayWorkspace apiUrl={API_URL} />" in app
    assert "/v1/today?day=" in today
    assert "method: 'PATCH'" in today
    assert "Statut piloté par Temporal" in today

    print(
        "PASS: canonical Task planning fields, timezone-aware Today contracts and the dockable "
        "Today workspace share one Daily Spine"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
