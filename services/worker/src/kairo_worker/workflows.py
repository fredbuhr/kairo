from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import (
        begin_execution,
        complete_execution,
        fail_execution,
        perform_foundation_work,
        perform_news_brief,
    )

ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=10,
)


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
        capability = str((started.get("task_input") or {}).get("capability") or "foundation")
        activity_fn = perform_news_brief if capability == "news.brief" else perform_foundation_work
        try:
            result = await workflow.execute_activity(
                activity_fn,
                work_payload,
                start_to_close_timeout=timedelta(minutes=3),
                heartbeat_timeout=timedelta(seconds=15),
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
