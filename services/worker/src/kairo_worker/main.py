import asyncio
import signal
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

from .activities import begin_execution, complete_execution, fail_execution, perform_foundation_work
from .config import settings
from .document_ingestion import perform_document_ingestion
from .memory_events import MemoryProjectionEventConsumer
from .memory_projection import perform_memory_projection
from .news_activity import perform_news_brief
from .policy_activities import check_policy_gate
from .research_agent import perform_autonomous_research
from .research_context_pack import prepare_research_context_pack
from .semantic_router import perform_semantic_route
from .tool_runtime import fail_tool_invocation, perform_tool_invocation
from .workflows import FoundationWorkflow, TaskExecutionWorkflow


async def serve() -> None:
    if settings.kairo_env == "production":
        from .model_assets import verify_production_assets
        await asyncio.to_thread(verify_production_assets)
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        max_concurrent_activities=settings.kairo_worker_max_concurrent_activities,
        max_concurrent_workflow_tasks=settings.kairo_worker_max_concurrent_workflow_tasks,
        workflows=[TaskExecutionWorkflow, FoundationWorkflow],
        activities=[
            begin_execution,
            check_policy_gate,
            perform_foundation_work,
            perform_news_brief,
            perform_semantic_route,
            prepare_research_context_pack,
            perform_autonomous_research,
            perform_memory_projection,
            perform_document_ingestion,
            perform_tool_invocation,
            fail_tool_invocation,
            complete_execution,
            fail_execution,
        ],
        graceful_shutdown_timeout=timedelta(seconds=20),
        # Research model-call checkpoints are replay-critical. Keep heartbeat coalescing bounded so
        # an abrupt Worker death cannot leave an already-accounted model result only in process
        # memory for the SDK's much longer default throttle interval.
        max_heartbeat_throttle_interval=timedelta(seconds=1),
        default_heartbeat_throttle_interval=timedelta(seconds=1),
    )
    memory_events = MemoryProjectionEventConsumer()
    memory_consumer_task = asyncio.create_task(
        memory_events.run(), name="kairo-memory-projection-events"
    )
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stopped.set)
    async with worker:
        try:
            await stopped.wait()
        finally:
            await memory_events.stop()
            memory_consumer_task.cancel()
            await asyncio.gather(memory_consumer_task, return_exceptions=True)
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.remove_signal_handler(signum)


if __name__ == "__main__":
    asyncio.run(serve())
