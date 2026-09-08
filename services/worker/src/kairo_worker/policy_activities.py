from __future__ import annotations

from typing import Any

import httpx
from temporalio import activity

from .config import settings


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


@activity.defn
async def check_policy_gate(payload: dict[str, Any]) -> dict[str, Any]:
    """Ask KAIRO Core for authority and budget before a side-effecting activity.

    The signed capability token deliberately stays inside this activity process and is not returned
    into Temporal workflow history. Tool adapters can consume it transiently in the same activity.
    """

    request = {
        "task_id": payload["task_id"],
        "workflow_execution_id": payload.get("workflow_execution_id"),
        "action": payload["action"],
        "resource_type": payload.get("resource_type", "capability"),
        "resource_id": payload.get("resource_id"),
        "authority_level": int(payload.get("authority_level", 1)),
        "estimated_cost_usd": str(payload.get("estimated_cost_usd", "0")),
        "scope": payload.get("scope") or {},
        "reason": payload.get("reason") or "Temporal activity requires KAIRO policy authorization",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url}/internal/v1/policy/authorize",
            headers=_headers(),
            json=request,
        )
        response.raise_for_status()
        decision = response.json()

    # Capability tokens are intentionally not serialized into Temporal history.
    decision.pop("policy_token", None)
    return decision
