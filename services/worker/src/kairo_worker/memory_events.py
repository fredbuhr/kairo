from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext

from .config import settings

logger = logging.getLogger(__name__)

MEMORY_EVENT_SUBJECT = "kairo.domain.conversation.message.created"
MEMORY_CONSUMER_DURABLE = "kairo-memory-projector-v1"
DOMAIN_SUBJECT = "kairo.domain.>"
DOMAIN_MAX_MESSAGES = 100_000


class MemoryProjectionEventConsumer:
    """Durably turn canonical conversation events into deterministic Temporal Tasks.

    JetStream delivery is at-least-once. Core owns idempotency through deterministic memory Task
    IDs and source/projector projection rows, so duplicate event delivery cannot create duplicate
    canonical work.

    This consumer also reconciles the shared KAIRO domain stream before subscribing. The stream is
    transport/replay state, not canonical history, so its retention must stay explicitly time-bounded
    for account-lifecycle guarantees.
    """

    def __init__(self) -> None:
        self._nc: NATS | None = None
        self._js: JetStreamContext | None = None
        self._stopping = asyncio.Event()

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"X-Kairo-Internal-Token": settings.kairo_internal_token}

    async def _ensure_domain_stream(self) -> None:
        if self._js is None:
            raise RuntimeError("JetStream is not connected")

        max_age = float(max(60, settings.nats_domain_retention_seconds))
        try:
            info = await self._js.stream_info(settings.nats_domain_stream)
        except Exception:
            await self._js.add_stream(
                name=settings.nats_domain_stream,
                subjects=[DOMAIN_SUBJECT],
                max_msgs=DOMAIN_MAX_MESSAGES,
                max_age=max_age,
            )
            return

        config = info.config
        changed = False
        if list(config.subjects or []) != [DOMAIN_SUBJECT]:
            config.subjects = [DOMAIN_SUBJECT]
            changed = True
        if int(config.max_msgs or 0) != DOMAIN_MAX_MESSAGES:
            config.max_msgs = DOMAIN_MAX_MESSAGES
            changed = True
        if float(config.max_age or 0) != max_age:
            config.max_age = max_age
            changed = True
        if changed:
            await self._js.update_stream(config=config)

    async def _ensure_projection(self, message_id: str, generation: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{settings.kairo_core_url.rstrip('/')}/internal/v1/memory/"
                f"projections/conversation-messages/{message_id}/ensure",
                headers=self._headers(),
                json={"generation": generation},
            )
            response.raise_for_status()
            return response.json()

    async def _run_task(self, task_id: str) -> None:
        """Start a Core-created deterministic Task through the Worker-only trust boundary.

        Public `/v1/tasks/.../run` requires a user bearer token and must never be used as an internal
        service backdoor. The Worker authenticates with the existing internal service token instead.
        """
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{settings.kairo_core_url.rstrip('/')}/internal/v1/tasks/{task_id}/run",
                headers=self._headers(),
            )
            if response.status_code == 409:
                # Core returns 409 only when the deterministic Task is already completed.
                return
            response.raise_for_status()

    async def _handle_message(self, message) -> None:
        try:
            payload = json.loads(message.data.decode("utf-8"))
            message_id = str(payload.get("message_id") or "")
            if not message_id:
                raise ValueError("conversation.message.created event has no message_id")
            generation = max(1, int(payload.get("projection_generation") or 1))
            ensured = await self._ensure_projection(message_id, generation)
            if ensured.get("should_run") and ensured.get("task_id"):
                await self._run_task(str(ensured["task_id"]))
            await message.ack()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to hand off conversation message to memory projection")
            try:
                await message.nak()
            except Exception:
                logger.exception("Failed to NAK memory projection event")

    async def _connect_and_subscribe(self) -> None:
        self._nc = await nats.connect(
            settings.nats_url,
            name="kairo-worker-memory-projector",
            reconnect_time_wait=1,
            max_reconnect_attempts=-1,
        )
        self._js = self._nc.jetstream()
        await self._ensure_domain_stream()
        await self._js.subscribe(
            MEMORY_EVENT_SUBJECT,
            durable=MEMORY_CONSUMER_DURABLE,
            stream=settings.nats_domain_stream,
            manual_ack=True,
            cb=self._handle_message,
        )

    async def run(self) -> None:
        while not self._stopping.is_set():
            try:
                await self._connect_and_subscribe()
                await self._stopping.wait()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Memory projection consumer is waiting for JetStream")
                if self._nc and not self._nc.is_closed:
                    await self._nc.close()
                self._nc = None
                self._js = None
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=2.0)
                except TimeoutError:
                    pass

    async def stop(self) -> None:
        self._stopping.set()
        if self._nc and not self._nc.is_closed:
            await self._nc.drain()
