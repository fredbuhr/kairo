from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import uuid_pk


class FinanceSource(Base):
    __tablename__ = "finance_sources"

    id: Mapped[uuid.UUID] = uuid_pk()
    keycloak_subject: Mapped[str] = mapped_column(String(240), nullable=False)
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="portfolio")
    external_account_ref: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="connected")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("keycloak_subject", "key", name="uq_finance_source_subject_key"),
        UniqueConstraint(
            "keycloak_subject",
            "provider",
            "external_account_ref",
            name="uq_finance_source_subject_account",
        ),
        Index("ix_finance_sources_subject_status", "keycloak_subject", "status"),
    )


class FinanceAccount(Base):
    __tablename__ = "finance_accounts"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("finance_sources.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(320), nullable=False)
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    account_type: Mapped[str] = mapped_column(String(64), nullable=False)
    network: Mapped[str | None] = mapped_column(String(120))
    public_address: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_finance_account_source_external"),
        Index("ix_finance_accounts_source_type", "source_id", "account_type"),
    )


class FinancePosition(Base):
    __tablename__ = "finance_positions"

    id: Mapped[uuid.UUID] = uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("finance_accounts.id", ondelete="CASCADE"), nullable=False
    )
    asset_key: Mapped[str] = mapped_column(String(240), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str | None] = mapped_column(String(240))
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False, default="crypto")
    quantity: Mapped[Decimal] = mapped_column(Numeric(40, 18), nullable=False)
    unit_price_usd: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    value_usd: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)
    cost_basis_usd: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    unrealized_pnl_usd: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("account_id", "asset_key", name="uq_finance_position_account_asset"),
        Index("ix_finance_positions_account_value", "account_id", "value_usd"),
        Index("ix_finance_positions_asset", "asset_key"),
    )


class FinanceTransactionProposal(Base):
    __tablename__ = "finance_transaction_proposals"

    id: Mapped[uuid.UUID] = uuid_pk()
    keycloak_subject: Mapped[str] = mapped_column(String(240), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL")
    )
    from_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("finance_accounts.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="crypto_transfer")
    network: Mapped[str] = mapped_column(String(120), nullable=False)
    asset_key: Mapped[str] = mapped_column(String(240), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(40, 18), nullable=False)
    destination: Mapped[str] = mapped_column(String(512), nullable=False)
    memo: Mapped[str | None] = mapped_column(Text)
    estimated_fee_asset: Mapped[str | None] = mapped_column(String(240))
    estimated_fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(40, 18))
    simulation_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_finance_proposals_subject_status", "keycloak_subject", "status", "created_at"),
        Index("ix_finance_proposals_account", "from_account_id", "created_at"),
    )
