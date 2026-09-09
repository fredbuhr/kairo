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

DOMAIN_SUBJECT = "kairo.domain.>"
DOMAIN_MAX_MESSAGES = 100_000


class OutboxRelay:
    """At-least-once PostgreSQL -> NATS JetStream relay.

    The domain mutation and outbox row share one DB transaction. Publication happens later.
    If KAIRO crashes after JetStream acknowledges but before PostgreSQL records published_at,
    the same event is replayed with the same Nats-Msg-Id so JetStream can deduplicate it.

    A successful PubAck is persisted on the Outbox row as stream/sequence transport evidence before
    the surrounding PostgreSQL transaction commits. This lets account-retention reconciliation map a
    canonical Outbox event to the exact JetStream message when the receipt is available.

    Core also reconciles the shared domain stream before publishing. The Worker performs the same
    convergence before subscribing, so bounded retention does not depend on service start order.
    """

    def __init__(self) -> None:
        self._nc: NATS | None = None
        self._js: JetStreamContext | None = None
        self._stopping = asyncio.Event()

    @property
    def connected(self) -> bool:
        return bool(self._nc and self._nc.is_connected)

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
        await self._ensure_domain_stream()

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
                        ack = await self._js.publish(
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

                    # Persist the exact transport receipt before marking the canonical delivery row
                    # complete. If the DB commit is lost, the next retry reuses Nats-Msg-Id and lets
                    # JetStream deduplicate the same Outbox UUID rather than creating an intentional
                    # second transport copy.
                    event.jetstream_stream = str(ack.stream)
                    event.jetstream_sequence = int(ack.seq)
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
