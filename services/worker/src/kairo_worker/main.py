import asyncio
from datetime import timedelta
from typing import Any

import httpx
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Worker

from .config import settings

ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=10,
)


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


@activity.defn
async def begin_execution(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_id = payload["workflow_id"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url}/internal/v1/executions/{workflow_id}/start",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


@activity.defn
async def perform_foundation_work(payload: dict[str, Any]) -> dict[str, Any]:
    """Replay-safe Block 1 activity used to exercise crash/restart semantics.

    This activity has no external side effect. It heartbeats while delayed so a killed worker is
    detected quickly and Temporal can retry it on the replacement worker.
    """
    task_input = payload.get("task_input") or {}
    delay = max(0.0, min(float(task_input.get("delay_seconds", 0)), 30.0))
    elapsed = 0.0
    while elapsed < delay:
        step = min(1.0, delay - elapsed)
        await asyncio.sleep(step)
        elapsed += step
        activity.heartbeat({"elapsed_seconds": elapsed})

    return {
        "kind": "foundation-result",
        "title": f"Result — {payload['task_title']}",
        "content": {
            "task_id": payload["task_id"],
            "message": "Durable Temporal workflow completed through the KAIRO Core boundary.",
            "input": task_input,
        },
    }


@activity.defn
async def complete_execution(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_id = payload["workflow_id"]
    result = payload["result"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url}/internal/v1/executions/{workflow_id}/complete",
            headers=_headers(),
            json=result,
        )
        response.raise_for_status()
        return response.json()


@activity.defn
async def fail_execution(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_id = payload["workflow_id"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url}/internal/v1/executions/{workflow_id}/fail",
            headers=_headers(),
            json={"error": payload["error"]},
        )
        response.raise_for_status()
        return response.json()


@workflow.defn
class TaskExecutionWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow_id = payload["workflow_id"]
        started = await workflow.execute_activity(
            begin_execution,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=ACTIVITY_RETRY,
        )
        work_payload = {
            "task_id": payload["task_id"],
            "workflow_id": workflow_id,
            "task_title": started["task_title"],
            "task_input": started["task_input"],
        }
        try:
            result = await workflow.execute_activity(
                perform_foundation_work,
                work_payload,
                start_to_close_timeout=timedelta(seconds=60),
                heartbeat_timeout=timedelta(seconds=5),
                retry_policy=ACTIVITY_RETRY,
            )
            completion = await workflow.execute_activity(
                complete_execution,
                {"workflow_id": workflow_id, "result": result},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=ACTIVITY_RETRY,
            )
            return completion
        except Exception as exc:
            await workflow.execute_activity(
                fail_execution,
                {"workflow_id": workflow_id, "error": str(exc)},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=ACTIVITY_RETRY,
            )
            raise


@workflow.defn
class FoundationWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "payload": payload, "engine": "temporal"}


async def serve() -> None:
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[TaskExecutionWorkflow, FoundationWorkflow],
        activities=[begin_execution, perform_foundation_work, complete_execution, fail_execution],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(serve())
