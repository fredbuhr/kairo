#!/usr/bin/env python3
"""Fail fast if internal services regress to unauthenticated public Task start routes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(source: str, needle: str, label: str) -> None:
    if needle not in source:
        raise AssertionError(f"Missing {label}: {needle!r}")


def forbid(source: str, needle: str, label: str) -> None:
    if needle in source:
        raise AssertionError(f"Forbidden {label}: {needle!r}")


def main() -> None:
    workflows = text("services/core/src/kairo_core/workflows.py")
    memory_events = text("services/worker/src/kairo_worker/memory_events.py")

    require(
        workflows,
        '"/internal/v1/tasks/{task_id}/run"',
        "internal canonical Task start route",
    )
    require(
        workflows,
        "dependencies=[Depends(require_internal_token)]",
        "internal-token dependency",
    )
    require(
        workflows,
        '@router.post("/v1/tasks/{task_id}/run", response_model=TaskRunResponse)',
        "public authenticated Task start surface",
    )

    require(
        memory_events,
        "}/internal/v1/tasks/{task_id}/run",
        "memory projector internal Task start",
    )
    require(
        memory_events,
        "headers=self._headers()",
        "memory projector internal token header",
    )
    forbid(
        memory_events,
        "}/v1/tasks/{task_id}/run",
        "memory projector public Task start",
    )

    print("KAIRO internal Task start trust-boundary contract passed")


if __name__ == "__main__":
    main()
