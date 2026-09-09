from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    event as sa_event,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import OutboxEvent


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class CapabilityRecord(Base):
    """Canonical metadata for a KAIRO-owned capability contract.

    The implementation can change behind this record, but callers route to the stable key rather
    than to a tool, model provider or specialist engine.
    """

    __tablename__ = "capabilities"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    authority_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cost_class: Mapped[str] = mapped_column(String(64), nullable=False, default="none")
    runtime: Mapped[str] = mapped_column(String(80), nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = uuid_pk()
    subject_ref: Mapped[str | None] = mapped_column(String(240))
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="fr-FR")
    title: Mapped[str | None] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_conversations_subject_status", "subject_ref", "status"),)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_conversation_messages_conversation_created", "conversation_id", "created_at"),
    )


@sa_event.listens_for(ConversationMessage, "after_insert")
def _enqueue_memory_projection_event(_mapper, connection, target: ConversationMessage) -> None:
    """Insert the memory event in the same transaction as the canonical message.

    The event intentionally carries only stable references. Workers must fetch the canonical
    message from Core, so the JetStream event log never becomes a second copy of conversation
    content. This listener bypasses the async event helper, therefore it resolves the owning
    Conversation subject explicitly before inserting the Outbox row.
    """

    owner_subject = connection.execute(
        select(Conversation.subject_ref).where(Conversation.id == target.conversation_id)
    ).scalar_one_or_none()
    connection.execute(
        OutboxEvent.__table__.insert().values(
            id=uuid.uuid4(),
            keycloak_subject=owner_subject,
            subject="kairo.domain.conversation.message.created",
            event_type="conversation.message.created",
            aggregate_type="conversation_message",
            aggregate_id=target.id,
            correlation_id=uuid.uuid4(),
            payload={
                "message_id": str(target.id),
                "conversation_id": str(target.conversation_id),
                "role": target.role,
                "projection_generation": 1,
            },
            attempts=0,
        )
    )


class CommandRecord(Base):
    __tablename__ = "commands"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    capability_key: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("capabilities.key", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="routing")
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    route_reason: Mapped[str | None] = mapped_column(String(240))
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL")
    )
    workflow_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflow_executions.id", ondelete="SET NULL")
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_commands_conversation_created", "conversation_id", "created_at"),
        Index("ix_commands_capability_status", "capability_key", "status"),
        Index("ix_commands_task", "task_id"),
        Index("ix_commands_correlation", "correlation_id"),
    )
