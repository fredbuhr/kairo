#!/usr/bin/env python3
"""Minimal Temporal Worker used by the autonomous Research end-to-end proof."""

from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from kairo_worker.activities import begin_execution, complete_execution, fail_execution
from kairo_worker.config import settings
from kairo_worker.policy_activities import check_policy_gate
from kairo_worker.research_agent import perform_autonomous_research
from kairo_worker.tool_runtime import fail_tool_invocation, perform_tool_invocation
from kairo_worker.workflows import TaskExecutionWorkflow


async def main() -> None:
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[TaskExecutionWorkflow],
        activities=[
            begin_execution,
            check_policy_gate,
            perform_autonomous_research,
            perform_tool_invocation,
            fail_tool_invocation,
            complete_execution,
            fail_execution,
        ],
    )
    print(
        f"research E2E worker listening on {settings.temporal_address}/{settings.temporal_task_queue}",
        flush=True,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
