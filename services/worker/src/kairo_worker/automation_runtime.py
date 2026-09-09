from __future__ import annotations

import hashlib
from typing import Any

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from .config import settings

AUTOMATION_CHECKPOINT_KIND = "kairo.automation-call"
AUTOMATION_CHECKPOINT_VERSION = 1


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def _heartbeat(stage: str, invocation_id: str) -> None:
    if not activity.in_activity():
        return
    activity.heartbeat(
        {
            "kind": AUTOMATION_CHECKPOINT_KIND,
            "version": AUTOMATION_CHECKPOINT_VERSION,
            "stage": stage,
            "invocation_id": invocation_id,
        }
    )


async def _get_context(invocation_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/automation-invocations/{invocation_id}/context",
            headers=_headers(),
        )
        if response.status_code >= 400:
            raise ApplicationError(
                f"automation-pre-call: Core context returned {response.status_code}",
                non_retryable=True,
            )
        return response.json()


async def _start(invocation_id: str, workflow_execution_id: str) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/automation-invocations/{invocation_id}/start",
            headers=_headers(),
            json={"workflow_execution_id": workflow_execution_id},
        )
        if response.status_code >= 400:
            raise ApplicationError(
                f"automation-pre-call: Core start returned {response.status_code}",
                non_retryable=True,
            )


async def _complete(invocation_id: str, response_status: int, result: dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/automation-invocations/{invocation_id}/complete",
            headers=_headers(),
            json={"response_status": response_status, "result": result},
        )
        if response.status_code >= 400:
            raise ApplicationError(
                f"automation-post-call: Core completion accounting returned {response.status_code}",
                non_retryable=True,
            )


async def _fail(invocation_id: str, error: str, *, outcome_ambiguous: bool) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/automation-invocations/{invocation_id}/fail",
            headers=_headers(),
            json={
                "error": error[:4000],
                "outcome_ambiguous": outcome_ambiguous,
            },
        )
        response.raise_for_status()


@activity.defn(name="fail_automation_invocation")
async def fail_automation_invocation(payload: dict[str, Any]) -> dict[str, Any]:
    task_input = payload.get("task_input") or {}
    invocation_id = str(task_input.get("automation_invocation_id") or "")
    if not invocation_id:
        raise RuntimeError("automation.invoke failure propagation requires automation_invocation_id")
    error = str(payload.get("error") or "automation invocation failed")
    outcome_ambiguous = bool(payload.get("outcome_ambiguous"))
    await _fail(invocation_id, error, outcome_ambiguous=outcome_ambiguous)
    return {
        "automation_invocation_id": invocation_id,
        "status": "failed",
        "outcome_ambiguous": outcome_ambiguous,
    }


@activity.defn(name="perform_automation_invocation")
async def perform_automation_invocation(payload: dict[str, Any]) -> dict[str, Any]:
    task_input = payload.get("task_input") or {}
    invocation_id = str(task_input.get("automation_invocation_id") or "")
    workflow_execution_id = str(payload.get("workflow_execution_id") or "")
    if not invocation_id or not workflow_execution_id:
        raise ApplicationError(
            "automation-pre-call: automation.invoke requires invocation and workflow execution ids",
            non_retryable=True,
        )

    context = await _get_context(invocation_id)
    if str(context.get("engine") or "") != "activepieces_webhook":
        raise ApplicationError("automation-pre-call: unsupported automation engine", non_retryable=True)

    await _start(invocation_id, workflow_execution_id)

    # Resolve authorization + secret again immediately before the external boundary. Disabling the
    # automation after Task creation therefore fails closed rather than using a stale webhook path.
    context = await _get_context(invocation_id)
    endpoint_url = str(context.get("endpoint_url") or "")
    input_payload = context.get("input") if isinstance(context.get("input"), dict) else {}
    timeout_seconds = int(context.get("timeout_seconds") or 60)
    correlation_id = str(context.get("correlation_id") or "")
    if not endpoint_url:
        raise ApplicationError("automation-pre-call: webhook endpoint is missing", non_retryable=True)

    # A webhook call may trigger irreversible work. There is deliberately no automatic Temporal
    # retry after this checkpoint. If the worker loses the response, KAIRO records an ambiguous
    # outcome and requires an explicit user decision before a new invocation is created.
    _heartbeat("pre_call", invocation_id)
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(float(timeout_seconds)),
            follow_redirects=False,
        ) as client:
            response = await client.post(
                endpoint_url,
                json=input_payload,
                headers={
                    "Accept": "application/json",
                    "X-Kairo-Automation-Invocation": invocation_id,
                    "X-Kairo-Correlation-Id": correlation_id,
                },
            )
    except httpx.RequestError as exc:
        raise ApplicationError(
            f"automation-post-call: webhook outcome is unknown: {type(exc).__name__}",
            non_retryable=True,
        ) from exc

    body = response.content
    result = {
        "response_content_type": response.headers.get("content-type"),
        "response_size_bytes": len(body),
        "response_sha256": hashlib.sha256(body).hexdigest(),
    }
    _heartbeat("response", invocation_id)

    if not 200 <= response.status_code < 300:
        raise ApplicationError(
            f"automation-post-call: webhook returned HTTP {response.status_code}",
            non_retryable=True,
        )

    await _complete(invocation_id, response.status_code, result)
    _heartbeat("accounted", invocation_id)
    return {
        "automation_invocation_id": invocation_id,
        "response_status": response.status_code,
        **result,
    }
