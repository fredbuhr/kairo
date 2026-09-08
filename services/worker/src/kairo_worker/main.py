import asyncio

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
from .semantic_router import perform_semantic_route
from .tool_runtime import fail_tool_invocation, perform_tool_invocation
from .workflows import FoundationWorkflow, TaskExecutionWorkflow


async def serve() -> None:
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[TaskExecutionWorkflow, FoundationWorkflow],
        activities=[
            begin_execution,
            check_policy_gate,
            perform_foundation_work,
            perform_news_brief,
            perform_semantic_route,
            perform_autonomous_research,
            perform_memory_projection,
            perform_document_ingestion,
            perform_tool_invocation,
            fail_tool_invocation,
            complete_execution,
            fail_execution,
        ],
    )
    memory_events = MemoryProjectionEventConsumer()
    memory_consumer_task = asyncio.create_task(
        memory_events.run(), name="kairo-memory-projection-events"
    )
    try:
        await worker.run()
    finally:
        await memory_events.stop()
        memory_consumer_task.cancel()
        await asyncio.gather(memory_consumer_task, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(serve())