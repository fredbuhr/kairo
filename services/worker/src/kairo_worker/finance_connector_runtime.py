from __future__ import annotations

from typing import Any

import httpx
from temporalio import activity

from .config import settings


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


@activity.defn(name="perform_finance_rotki_sync")
async def perform_finance_rotki_sync(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute one read-only Rotki synchronization through KAIRO Core.

    Core owns the SecretReference/OpenBao access and the normalized Finance snapshot mutation. The
    Worker only supplies the durable Task/Workflow identity, so Rotki credentials never enter the
    Temporal payload/history or the general-purpose Worker process.
    """
    task_input = payload.get("task_input") or {}
    connector_id = str(task_input.get("finance_connector_id") or "")
    task_id = str(payload.get("task_id") or "")
    workflow_execution_id = str(payload.get("workflow_execution_id") or "")
    if not connector_id or not task_id or not workflow_execution_id:
        raise RuntimeError(
            "finance.sync.rotki requires connector, task and workflow execution identity"
        )

    async with httpx.AsyncClient(timeout=240.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/finance-connectors/{connector_id}/sync",
            headers=_headers(),
            json={
                "task_id": task_id,
                "workflow_execution_id": workflow_execution_id,
            },
        )
    if response.status_code >= 400:
        try:
            body = response.json()
            detail = body.get("detail") if isinstance(body, dict) else None
        except ValueError:
            detail = None
        raise RuntimeError(
            f"KAIRO Rotki connector sync failed with HTTP {response.status_code}: "
            f"{detail or response.text[:500]}"
        )
    result = response.json()
    if not isinstance(result, dict):
        raise RuntimeError("KAIRO Rotki connector sync returned an invalid result")
    return result
