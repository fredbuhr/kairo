import asyncio
import json
import logging
from datetime import UTC, datetime

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from sqlalchemy import select

from .config import settings
from .db import SessionFactory
from .models import OutboxEvent

logger = logging.getLogger(__name__)


class OutboxRelay:
    """At-least-once PostgreSQL -> NATS JetStream relay.

    The domain mutation and outbox row share one DB transaction. Publication happens later.
    If KAIRO crashes after JetStream acknowledges but before PostgreSQL records published_at,
    the same event is replayed with the same Nats-Msg-Id so JetStream can deduplicate it.
    """

    def __init__(self) -> None:
        self._nc: NATS | None = None
        self._js: JetStreamContext | None = None
        self._stopping = asyncio.Event()

    @property
    def connected(self) -> bool:
        return bool(self._nc and self._nc.is_connected)

    async def _connect(self) -> None:
        if self.connected:
            return
        self._nc = await nats.connect(
            settings.nats_url,
            name="kairo-core-outbox",
            reconnect_time_wait=1,
            max_reconnect_attempts=-1,
        )
        self._js = self._nc.jetstream()
        try:
            await self._js.stream_info(settings.nats_domain_stream)
        except Exception:
            await self._js.add_stream(
                name=settings.nats_domain_stream,
                subjects=["kairo.domain.>"],
            )

    async def _publish_batch(self) -> int:
        if not self._js:
            return 0
        published = 0
        async with SessionFactory() as session:
            async with session.begin():
                result = await session.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.published_at.is_(None))
                    .order_by(OutboxEvent.created_at)
                    .limit(settings.outbox_batch_size)
                    .with_for_update(skip_locked=True)
                )
                events = list(result.scalars())
                for event in events:
                    event.attempts += 1
                    try:
                        await self._js.publish(
                            event.subject,
                            json.dumps(event.payload, separators=(",", ":"), default=str).encode(),
                            headers={
                                "Nats-Msg-Id": str(event.id),
                                "Kairo-Event-Type": event.event_type,
                                "Kairo-Correlation-Id": str(event.correlation_id),
                            },
                        )
                    except Exception as exc:
                        event.last_error = str(exc)[:2000]
                        logger.exception("Failed to publish outbox event %s", event.id)
                        continue
                    event.last_error = None
                    event.published_at = datetime.now(UTC)
                    published += 1
        return published

    async def run(self) -> None:
        while not self._stopping.is_set():
            try:
                await self._connect()
                published = await self._publish_batch()
                delay = 0 if published else settings.outbox_poll_interval_seconds
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outbox relay iteration failed")
                delay = settings.outbox_retry_interval_seconds
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=delay)
            except TimeoutError:
                pass

    async def stop(self) -> None:
        self._stopping.set()
        if self._nc and not self._nc.is_closed:
            await self._nc.drain()
