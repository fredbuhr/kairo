#!/usr/bin/env python3
"""Fail fast if Outbox/JetStream retention reconciliation loses its transport receipt boundary."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(source: str, needle: str, label: str) -> None:
    if needle not in source:
        raise AssertionError(f"Missing {label}: {needle!r}")


def main() -> None:
    models = text("services/core/src/kairo_core/models.py")
    migration = text("services/core/migrations/versions/0020_outbox_jetstream_receipts.py")
    outbox = text("services/core/src/kairo_core/outbox.py")
    worker_config = text("services/worker/src/kairo_worker/config.py")
    core_config = text("services/core/src/kairo_core/config.py")
    memory_events = text("services/worker/src/kairo_worker/memory_events.py")
    env = text(".env.example")

    require(models, "jetstream_stream: Mapped[str | None]", "Outbox JetStream stream receipt")
    require(models, "jetstream_sequence: Mapped[int | None]", "Outbox JetStream sequence receipt")
    require(models, 'name="uq_outbox_jetstream_receipt"', "unique transport receipt")

    require(migration, 'revision = "0020_outbox_jetstream_receipts"', "migration revision")
    require(migration, 'sa.Column("jetstream_stream"', "stream migration")
    require(migration, 'sa.Column("jetstream_sequence"', "sequence migration")
    require(migration, "Historical", "historical receipt limitation documentation")

    require(outbox, 'headers={"Nats-Msg-Id": str(event.id)}', "Outbox UUID JetStream dedupe header")
    require(outbox, "event.jetstream_stream = str(ack.stream)", "PubAck stream persistence")
    require(outbox, "event.jetstream_sequence = int(ack.seq)", "PubAck sequence persistence")
    require(outbox, "event.published_at = datetime.now(UTC)", "publish completion marker")

    for config_source, label in ((worker_config, "Worker"), (core_config, "Core")):
        require(
            config_source,
            "nats_domain_retention_seconds: int = 7 * 24 * 60 * 60",
            f"{label} bounded retention default",
        )
    require(env, "NATS_DOMAIN_RETENTION_SECONDS=604800", "deployment retention environment")

    require(memory_events, "max_age=max_age", "new stream max-age")
    require(memory_events, "config.max_age = max_age", "existing stream max-age reconciliation")
    require(memory_events, "await self._js.update_stream(config=config)", "existing stream update")

    print("KAIRO Outbox/JetStream bounded-retention receipt contract passed")


if __name__ == "__main__":
    main()
