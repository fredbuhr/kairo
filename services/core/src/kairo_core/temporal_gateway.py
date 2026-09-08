import asyncio
from typing import Any

from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from .config import settings


class TemporalGateway:
    def __init__(self) -> None:
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    async def client(self) -> Client:
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is None:
                self._client = await Client.connect(
                    settings.temporal_address,
                    namespace=settings.temporal_namespace,
                )
        return self._client

    async def health(self) -> bool:
        client = await self.client()
        return await client.service_client.check_health()

    async def start_task_workflow(
        self, *, workflow_id: str, payload: dict[str, Any]
    ) -> tuple[bool, str | None]:
        client = await self.client()
        try:
            handle = await client.start_workflow(
                "TaskExecutionWorkflow",
                payload,
                id=workflow_id,
                task_queue=settings.temporal_task_queue,
            )
            return False, getattr(handle, "first_execution_run_id", None)
        except WorkflowAlreadyStartedError as exc:
            return True, exc.run_id

    async def signal_task_workflow(
        self, *, workflow_id: str, signal: str, payload: dict[str, Any]
    ) -> None:
        client = await self.client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(signal, payload)


temporal_gateway = TemporalGateway()
