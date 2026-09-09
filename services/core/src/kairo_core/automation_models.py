from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import uuid_pk


class AutomationDefinition(Base):
    __tablename__ = "automation_definitions"

    id: Mapped[uuid.UUID] = uuid_pk()
    keycloak_subject: Mapped[str] = mapped_column(String(240), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    engine: Mapped[str] = mapped_column(String(64), nullable=False, default="activepieces_webhook")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    authority_level: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    webhook_secret_reference_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("secret_references.id", ondelete="RESTRICT"), nullable=False
    )
    webhook_secret_key: Mapped[str] = mapped_column(String(120), nullable=False, default="path")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("keycloak_subject", "key", name="uq_automation_definition_subject_key"),
        ForeignKeyConstraint(
            ["webhook_secret_reference_id", "keycloak_subject"],
            ["secret_references.id", "secret_references.keycloak_subject"],
            name="fk_automation_definitions_secret_subject",
            ondelete="RESTRICT",
        ),
        Index("ix_automation_definitions_subject_enabled", "keycloak_subject", "enabled"),
        Index("ix_automation_definitions_project", "project_id", "created_at"),
    )


class AutomationInvocation(Base):
    __tablename__ = "automation_invocations"

    id: Mapped[uuid.UUID] = uuid_pk()
    automation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("automation_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    workflow_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflow_executions.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str] = mapped_column(String(240), nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    response_status: Mapped[int | None] = mapped_column(Integer)
    outcome_ambiguous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "automation_id",
            "idempotency_key",
            name="uq_automation_invocation_definition_idempotency",
        ),
        Index("ix_automation_invocations_automation_created", "automation_id", "created_at"),
        Index("ix_automation_invocations_status_created", "status", "created_at"),
        Index("ix_automation_invocations_correlation", "correlation_id"),
    )
