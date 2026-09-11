"""Real JetStream limits and upgrade of an existing durable consumer on disposable CI NATS."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from nats.js.api import ConsumerConfig

from kairo_core.config import settings as core_settings
from kairo_core.outbox import OutboxRelay
from kairo_worker.config import settings as worker_settings
from kairo_worker.memory_events import MEMORY_CONSUMER_DURABLE, MEMORY_EVENT_SUBJECT, MemoryProjectionEventConsumer


async def main():
    assert core_settings.nats_url == "nats://127.0.0.1:4222", "Requires isolated local CI NATS"
    worker_settings.nats_url = core_settings.nats_url
    relay, consumer = OutboxRelay(), MemoryProjectionEventConsumer()
    try:
        await relay._connect()
        connection = relay._nc
        info = await relay._js.stream_info(core_settings.nats_domain_stream)
        assert info.config.max_age == core_settings.nats_domain_max_age_seconds
        assert info.config.max_bytes == core_settings.nats_domain_max_bytes
        assert info.config.max_msgs == 100000 and info.config.discard == "new"
        info.config.max_bytes = 1048576
        await relay._js.update_stream(config=info.config)
        await relay._reconnected()
        await relay._connect()
        assert relay._nc is connection, "Reconciliation opened an extra connection"
        info = await relay._js.stream_info(core_settings.nats_domain_stream)
        assert info.config.max_bytes == core_settings.nats_domain_max_bytes
        await relay._js.add_consumer(core_settings.nats_domain_stream, config=ConsumerConfig(
            durable_name=MEMORY_CONSUMER_DURABLE, filter_subject=MEMORY_EVENT_SUBJECT,
            deliver_subject="_INBOX.d02capacity", ack_wait=120, max_ack_pending=999,
        ))
        await consumer._connect_and_subscribe()
        info = await relay._js.consumer_info(core_settings.nats_domain_stream, MEMORY_CONSUMER_DURABLE)
        assert info.config.max_ack_pending == 32 and info.config.ack_wait == 60
        assert info.config.deliver_subject == "_INBOX.d02capacity"
        # A reconnecting client must not be multiplied on every relay iteration.
        from kairo_core import outbox
        reconnecting = OutboxRelay()
        reconnecting._nc = SimpleNamespace(is_closed=False, is_connected=False)
        with patch.object(outbox.nats, "connect", AsyncMock()) as connect:
            try:
                await reconnecting._connect()
            except ConnectionError:
                pass
            else:
                raise AssertionError("Expected reconnecting state")
            connect.assert_not_awaited()
        print("PASS real stream limits/reconciliation, existing durable upgrade and bounded reconnection")
    finally:
        await consumer.stop()
        await relay.stop()


if __name__ == "__main__":
    asyncio.run(main())
