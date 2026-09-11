import asyncio
import json
import logging
from datetime import timedelta
import uuid

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import DiscardPolicy
from nats.js.errors import NotFoundError
from sqlalchemy import delete, func, or_, select, update

from .config import settings
from .db import SessionFactory
from .models import OutboxEvent, Task
from .work_capacity import WorkAdmission

logger = logging.getLogger(__name__)


async def prune_technical_history() -> dict[str, int]:
    """Bound each cleanup transaction; canonical and unpublished data are never retention targets."""
    removed = {}
    async with SessionFactory() as session, session.begin():
        cutoff = func.clock_timestamp() - timedelta(days=settings.outbox_retention_days)
        old_events = select(OutboxEvent.id).where(OutboxEvent.published_at < cutoff).order_by(
            OutboxEvent.published_at, OutboxEvent.id,
        ).limit(settings.maintenance_batch_size).with_for_update(skip_locked=True)
        removed["published_events"] = (await session.execute(delete(OutboxEvent).where(
            OutboxEvent.id.in_(old_events),
        ))).rowcount
        terminal_tasks = select(Task.id).where(Task.status.in_({"completed", "failed"}))
        old_work = select(WorkAdmission.task_id).where(
            WorkAdmission.status == "finished", WorkAdmission.updated_at < cutoff,
            WorkAdmission.task_id.in_(terminal_tasks),
        ).order_by(WorkAdmission.updated_at, WorkAdmission.task_id).limit(settings.maintenance_batch_size).with_for_update(skip_locked=True)
        removed["finished_admissions"] = (await session.execute(delete(WorkAdmission).where(
            WorkAdmission.task_id.in_(old_work),
        ))).rowcount
    return removed


class OutboxRelay:
    """At-least-once relay with short claims: no PostgreSQL connection is held during NATS I/O."""
    def __init__(self) -> None:
        self._nc: NATS | None = None
        self._js: JetStreamContext | None = None
        self._stopping = asyncio.Event()
        self._next_maintenance = 0.0

    @property
    def connected(self) -> bool:
        return bool(self._nc and self._nc.is_connected)

    async def _connect(self) -> None:
        if self.connected and self._js:
            return
        self._nc = await nats.connect(settings.nats_url, name="kairo-core-outbox",
                                      reconnect_time_wait=1, max_reconnect_attempts=-1)
        js = self._nc.jetstream()
        limits = dict(max_age=settings.nats_domain_max_age_seconds,
                      max_bytes=settings.nats_domain_max_bytes, max_msgs=100000, discard=DiscardPolicy.NEW)
        try:
            info = await js.stream_info(settings.nats_domain_stream)
        except NotFoundError:
            await js.add_stream(name=settings.nats_domain_stream, subjects=["kairo.domain.>"], **limits)
        else:
            config = info.config
            for key, value in limits.items():
                setattr(config, key, value)
            await js.update_stream(config=config)
        self._js = js

    async def _claim_batch(self) -> tuple[uuid.UUID, list[dict]]:
        token = uuid.uuid4()
        async with SessionFactory() as session, session.begin():
            now = await session.scalar(select(func.clock_timestamp()))
            rows = list((await session.execute(select(OutboxEvent).where(
                OutboxEvent.published_at.is_(None),
                or_(OutboxEvent.claim_until.is_(None), OutboxEvent.claim_until <= now),
            ).order_by(OutboxEvent.created_at, OutboxEvent.id).limit(settings.outbox_batch_size)
              .with_for_update(skip_locked=True))).scalars())
            events = []
            for row in rows:
                row.claim_token, row.claim_until = token, now + timedelta(seconds=60)
                row.attempts += 1
                events.append({"id": row.id, "subject": row.subject, "payload": row.payload,
                               "event_type": row.event_type, "correlation_id": row.correlation_id})
        return token, events

    async def _publish_batch(self) -> int:
        if not self._js:
            return 0
        token, events = await self._claim_batch()
        published = 0
        for event in events:
            error = None
            try:
                async with asyncio.timeout(2):
                    await self._js.publish(event["subject"],
                        json.dumps(event["payload"], separators=(",", ":"), default=str).encode(),
                        headers={"Nats-Msg-Id": str(event["id"]), "Kairo-Event-Type": event["event_type"],
                                 "Kairo-Correlation-Id": str(event["correlation_id"])}, timeout=2,
                    )
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"[:2000]
                logger.warning("Outbox publication failed for %s: %s", event["id"], type(exc).__name__)
            async with SessionFactory() as session, session.begin():
                values = {"last_error": error, "claim_token": None,
                          "claim_until": func.clock_timestamp() + timedelta(seconds=5) if error else None}
                if not error:
                    values["published_at"] = func.clock_timestamp()
                acknowledged = await session.scalar(update(OutboxEvent).where(
                    OutboxEvent.id == event["id"], OutboxEvent.claim_token == token,
                    OutboxEvent.published_at.is_(None),
                ).values(**values).returning(OutboxEvent.id))
                published += int(not error and acknowledged is not None)
        return published

    async def run(self) -> None:
        while not self._stopping.is_set():
            try:
                clock = asyncio.get_running_loop().time()
                if clock >= self._next_maintenance:
                    await prune_technical_history()  # Also progresses while NATS is unavailable.
                    self._next_maintenance = clock + 60
                await self._connect()
                published = await self._publish_batch()
                delay = 0 if published else settings.outbox_poll_interval_seconds
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outbox relay iteration failed")
                if self._nc and not self._nc.is_closed and not self._js:
                    await self._nc.close()
                delay = settings.outbox_retry_interval_seconds
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=delay)
            except TimeoutError:
                pass

    async def stop(self) -> None:
        self._stopping.set()
        if self._nc and not self._nc.is_closed:
            await self._nc.drain()
