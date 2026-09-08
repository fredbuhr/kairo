import asyncio
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

from .config import settings


@activity.defn
async def foundation_ping(payload: dict) -> dict:
    """First deterministic activity used to prove the permanent Temporal boundary."""
    return {"ok": True, "payload": payload, "engine": "temporal"}


@workflow.defn
class FoundationWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        return await workflow.execute_activity(
            foundation_ping,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
        )


async def serve() -> None:
    client = await Client.connect(settings.temporal_address)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[FoundationWorkflow],
        activities=[foundation_ping],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(serve())
