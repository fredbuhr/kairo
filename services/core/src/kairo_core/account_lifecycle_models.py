from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
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
