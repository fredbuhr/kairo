from __future__ import annotations

from typing import Any

import httpx
from mcp import Client
from temporalio import activity

from .config import settings

TOOL_CHECKPOINT_KIND = "kairo.tool-call"
TOOL_CHECKPOINT_VERSION = 1


class ToolCallOutcomeUnknown(RuntimeError):
    """A non-retryable external tool may already have executed, so replay must fail closed."""


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def _read_checkpoint() -> dict[str, Any] | None:
    if not activity.in_activity():
        return None
    for detail in reversed(tuple(activity.info().heartbeat_details)):
        if isinstance(detail, dict) and detail.get("kind") == TOOL_CHECKPOINT_KIND:
            return dict(detail)
    return None


def _heartbeat(stage: str, invocation_id: str, result: dict[str, Any] | None = None) -> None:
    if not activity.in_activity():
        return
    payload: dict[str, Any] = {
        "kind": TOOL_CHECKPOINT_KIND,
        "version": TOOL_CHECKPOINT_VERSION,
        "stage": stage,
        "invocation_id": invocation_id,
    }
    if result is not None:
        payload["result"] = result
    activity.heartbeat(payload)


async def _get_context(invocation_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/tool-invocations/{invocation_id}/context",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def _start(invocation_id: str, workflow_execution_id: str) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/tool-invocations/{invocation_id}/start",
            headers=_headers(),
            params={"workflow_execution_id": workflow_execution_id},
        )
        response.raise_for_status()


async def _complete(invocation_id: str, result: dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/tool-invocations/{invocation_id}/complete",
            headers=_headers(),
            json={"result": result},
        )
        response.raise_for_status()


def _result_payload(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        dumped = result.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    if isinstance(result, dict):
        return result
    return {"value": str(result)}


@activity.defn(name="perform_tool_invocation")
async def perform_tool_invocation(payload: dict[str, Any]) -> dict[str, Any]:
    task_input = payload.get("task_input") or {}
    invocation_id = str(task_input.get("tool_invocation_id") or "")
    workflow_execution_id = str(payload.get("workflow_execution_id") or "")
    if not invocation_id or not workflow_execution_id:
        raise RuntimeError("tool.invoke requires tool_invocation_id and workflow_execution_id")

    context = await _get_context(invocation_id)
    if context.get("status") == "completed":
        result = context.get("result") if isinstance(context.get("result"), dict) else {}
        return {"tool_invocation_id": invocation_id, "result": result, "replayed": True}

    checkpoint = _read_checkpoint() or {}
    if checkpoint.get("invocation_id") == invocation_id:
        stage = str(checkpoint.get("stage") or "")
        checkpoint_result = checkpoint.get("result")
        if stage in {"result", "accounted"} and isinstance(checkpoint_result, dict):
            await _complete(invocation_id, checkpoint_result)
            _heartbeat("accounted", invocation_id, checkpoint_result)
            return {
                "tool_invocation_id": invocation_id,
                "result": checkpoint_result,
                "replayed": True,
            }
        if stage == "pre_call" and context.get("retry_policy") == "no_retry":
            raise ToolCallOutcomeUnknown(
                "Previous MCP tool attempt crossed the pre-call checkpoint; outcome is unknown and policy forbids replay"
            )

    await _start(invocation_id, workflow_execution_id)
    _heartbeat("pre_call", invocation_id)

    endpoint = str(context.get("endpoint_url") or "")
    remote_name = str(context.get("remote_name") or "")
    arguments = context.get("input") if isinstance(context.get("input"), dict) else {}
    if not endpoint or not remote_name:
        raise RuntimeError("Tool registry context is missing endpoint or remote tool name")

    async with Client(endpoint) as client:
        result = await client.call_tool(remote_name, arguments)
    result_payload = _result_payload(result)
    if bool(result_payload.get("isError") or result_payload.get("is_error")):
        raise RuntimeError(f"MCP tool returned an error: {result_payload}")

    _heartbeat("result", invocation_id, result_payload)
    await _complete(invocation_id, result_payload)
    _heartbeat("accounted", invocation_id, result_payload)
    return {"tool_invocation_id": invocation_id, "result": result_payload, "replayed": False}
