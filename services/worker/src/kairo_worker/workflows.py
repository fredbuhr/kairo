from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from .activities import (
        begin_execution,
        complete_execution,
        fail_execution,
        perform_foundation_work,
        perform_news_brief,
    )
    from .policy_activities import check_policy_gate

ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=10,
)


@workflow.defn
class TaskExecutionWorkflow:
    def __init__(self) -> None:
        self._approval_decisions: dict[str, str] = {}

    @workflow.signal
    async def approval_decision(self, payload: dict[str, Any]) -> None:
        approval_id = str(payload.get("approval_request_id") or "")
        decision = str(payload.get("decision") or "")
        if approval_id and decision in {"approved", "denied"}:
            self._approval_decisions[approval_id] = decision

    async def _await_policy(self, gate_payload: dict[str, Any]) -> None:
        decision = await workflow.execute_activity(
            check_policy_gate,
            gate_payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=ACTIVITY_RETRY,
        )
        if decision.get("allowed"):
            return
        if not decision.get("approval_required"):
            raise ApplicationError(
                f"KAIRO policy denied activity: {decision.get('reason', 'denied')}",
                non_retryable=True,
            )

        approval_id = str(decision["approval_request_id"])
        await workflow.wait_condition(lambda: approval_id in self._approval_decisions)
        if self._approval_decisions[approval_id] != "approved":
            raise ApplicationError("KAIRO approval was denied", non_retryable=True)

        # Re-check immediately before execution. This catches budget changes, expiry and revocation-like
        # state changes rather than trusting a stale approval signal.
        resumed = await workflow.execute_activity(
            check_policy_gate,
            gate_payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=ACTIVITY_RETRY,
        )
        if not resumed.get("allowed"):
            raise ApplicationError(
                f"KAIRO policy no longer authorizes activity: {resumed.get('reason', 'denied')}",
                non_retryable=True,
            )

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
            "workflow_execution_id": payload.get("workflow_execution_id"),
            "correlation_id": payload.get("correlation_id"),
            "task_title": started["task_title"],
            "task_input": started["task_input"],
        }
        task_input = started.get("task_input") or {}
        capability = str(task_input.get("capability") or "foundation")
        authority_level = int(task_input.get("authority_level") or 1)
        estimated_cost_usd = str(task_input.get("estimated_cost_usd") or "0")
        gate_payload = {
            "task_id": payload["task_id"],
            "workflow_execution_id": payload.get("workflow_execution_id"),
            "action": capability,
            "resource_type": "capability",
            "resource_id": capability,
            "authority_level": authority_level,
            "estimated_cost_usd": estimated_cost_usd,
            "scope": task_input.get("policy_scope") or {"capability": capability},
            "reason": task_input.get("approval_reason")
            or f"KAIRO workflow requests authority level {authority_level} for {capability}",
        }

        try:
            await self._await_policy(gate_payload)
            if capability == "news.brief":
                result = await workflow.execute_activity(
                    perform_news_brief,
                    work_payload,
                    start_to_close_timeout=timedelta(minutes=3),
                    heartbeat_timeout=timedelta(seconds=120),
                    retry_policy=ACTIVITY_RETRY,
                )
            else:
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
