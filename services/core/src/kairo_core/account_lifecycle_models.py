from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class AccountWriteFreeze(Base):
    """Durable local write barrier for one authenticated KAIRO subject.

    Row existence means public user-originated mutations are frozen. This is intentionally separate
    from Keycloak enabled/disabled state because already-issued bearer tokens may remain valid after a
    provider-side disable. Internal Worker routes keep their own trust boundary so in-flight durable
    work can reach a terminal/reconciled state while new browser mutations are rejected.
    """

    __tablename__ = "account_write_freezes"

    keycloak_subject: Mapped[str] = mapped_column(String(255), primary_key=True)
    operation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, unique=True, default=uuid.uuid4
    )
    reason: Mapped[str] = mapped_column(String(320), nullable=False, default="account_erasure_preparation")
    frozen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_account_write_freezes_frozen_at", "frozen_at"),)


class AccountErasureOperation(Base):
    """Durable preparation ledger for one attempted full-account erasure.

    This table deliberately records preparation and blockers before any irreversible account deletion
    exists. It gives KAIRO one replayable identity for the future state machine instead of letting a
    sequence of browser buttons become the deletion protocol.
    """

    __tablename__ = "account_erasure_operations"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keycloak_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="preparing")
    phase: Mapped[str] = mapped_column(String(64), nullable=False, default="write_freeze")
    freeze_operation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    owns_write_freeze: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocker_snapshot_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    irreversible_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_account_erasure_subject_created", "keycloak_subject", "created_at"),
        Index(
            "uq_account_erasure_active_subject",
            "keycloak_subject",
            unique=True,
            postgresql_where=text("status IN ('preparing', 'ready')"),
        ),
    )
