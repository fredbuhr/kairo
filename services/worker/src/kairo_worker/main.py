import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from .activities import (
    begin_execution,
    complete_execution,
    fail_execution,
    perform_foundation_work,
    perform_news_brief,
)
from .config import settings
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
            perform_foundation_work,
            perform_news_brief,
            complete_execution,
            fail_execution,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(serve())
