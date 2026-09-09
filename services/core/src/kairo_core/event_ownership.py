from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .automation_models import AutomationDefinition, AutomationInvocation
from .autonomy_models import ApprovalRequest, ModelUsageRecord
from .calendar_models import CalendarSource, ExternalCalendarEvent
from .command_models import CommandRecord, Conversation, ConversationMessage
from .document_models import Document, DocumentChunk, DocumentVersion
from .finance_models import (
    FinanceAccount,
    FinanceConnector,
    FinancePosition,
    FinanceSource,
    FinanceTransactionProposal,
)
from .models import (
    Artifact,
    Asset,
    DeviceRegistration,
    Project,
    RelationshipRecord,
    SecretReference,
    Task,
    WorkflowExecution,
)
from .tool_models import ToolInvocation

# These records describe installation-wide policy/transport state. A user may be the actor who
# changed them, but that does not make the shared record part of that user's erasable world.
_SHARED_CONTROL_PLANE = {
    "capability",
    "capability_record",
    "tool_server",
    "tool_definition",
    "system",
    "component",
    "architecture",
    "outbox",
}


def normalize_resource_type(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(".", "_").replace(" ", "_")
    aliases = {
        "workflow": "workflow_execution",
        "execution": "workflow_execution",
        "approval": "approval_request",
        "automation_definition": "automation",
        "finance_transaction": "finance_transaction_proposal",
        "secret_reference": "secret_reference",
    }
    return aliases.get(normalized, normalized)


def _uuid(value: uuid.UUID | str) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


async def resolve_data_subject(
    session: AsyncSession,
    resource_type: str,
    resource_id: uuid.UUID | str,
) -> str | None:
    """Resolve the authenticated data owner for a canonical user-world resource.

    The result is intentionally *not* the audit actor. Shared deployment control-plane records remain
    unowned even when an administrator changed them. This lets account lifecycle distinguish
    user-world data from retained security/administrative evidence.
    """

    kind = normalize_resource_type(resource_type)
    if kind in _SHARED_CONTROL_PLANE:
        return None
    entity_id = _uuid(resource_id)
    if entity_id is None:
        return None

    if kind == "project":
        return await session.scalar(select(Project.keycloak_subject).where(Project.id == entity_id))

    if kind == "task":
        return await session.scalar(
            select(Project.keycloak_subject)
            .join(Task, Task.project_id == Project.id)
            .where(Task.id == entity_id)
        )

    if kind == "workflow_execution":
        return await session.scalar(
            select(Project.keycloak_subject)
            .join(Task, Task.project_id == Project.id)
            .join(WorkflowExecution, WorkflowExecution.task_id == Task.id)
            .where(WorkflowExecution.id == entity_id)
        )

    if kind == "artifact":
        return await session.scalar(
            select(Project.keycloak_subject)
            .join(Artifact, Artifact.project_id == Project.id)
            .where(Artifact.id == entity_id)
        )

    if kind == "relationship":
        return await session.scalar(
            select(RelationshipRecord.keycloak_subject).where(RelationshipRecord.id == entity_id)
        )

    if kind == "asset":
        return await session.scalar(select(Asset.keycloak_subject).where(Asset.id == entity_id))

    if kind == "device":
        return await session.scalar(
            select(DeviceRegistration.keycloak_subject).where(DeviceRegistration.id == entity_id)
        )

    if kind == "secret_reference":
        return await session.scalar(
            select(SecretReference.keycloak_subject).where(SecretReference.id == entity_id)
        )

    if kind == "conversation":
        return await session.scalar(select(Conversation.subject_ref).where(Conversation.id == entity_id))

    if kind == "conversation_message":
        return await session.scalar(
            select(Conversation.subject_ref)
            .join(ConversationMessage, ConversationMessage.conversation_id == Conversation.id)
            .where(ConversationMessage.id == entity_id)
        )

    if kind == "command":
        return await session.scalar(
            select(Conversation.subject_ref)
            .join(CommandRecord, CommandRecord.conversation_id == Conversation.id)
            .where(CommandRecord.id == entity_id)
        )

    if kind == "approval_request":
        return await session.scalar(
            select(Project.keycloak_subject)
            .join(Task, Task.project_id == Project.id)
            .join(ApprovalRequest, ApprovalRequest.task_id == Task.id)
            .where(ApprovalRequest.id == entity_id)
        )

    if kind == "model_usage_record":
        return await session.scalar(
            select(Project.keycloak_subject)
            .join(Task, Task.project_id == Project.id)
            .join(ModelUsageRecord, ModelUsageRecord.task_id == Task.id)
            .where(ModelUsageRecord.id == entity_id)
        )

    if kind == "document":
        return await session.scalar(select(Document.keycloak_subject).where(Document.id == entity_id))

    if kind == "document_version":
        return await session.scalar(
            select(Document.keycloak_subject)
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .where(DocumentVersion.id == entity_id)
        )

    if kind == "document_chunk":
        return await session.scalar(
            select(Document.keycloak_subject)
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .join(DocumentChunk, DocumentChunk.document_version_id == DocumentVersion.id)
            .where(DocumentChunk.id == entity_id)
        )

    if kind == "calendar_source":
        return await session.scalar(
            select(CalendarSource.keycloak_subject).where(CalendarSource.id == entity_id)
        )

    if kind == "external_calendar_event":
        return await session.scalar(
            select(CalendarSource.keycloak_subject)
            .join(ExternalCalendarEvent, ExternalCalendarEvent.source_id == CalendarSource.id)
            .where(ExternalCalendarEvent.id == entity_id)
        )

    if kind == "automation":
        return await session.scalar(
            select(AutomationDefinition.keycloak_subject).where(AutomationDefinition.id == entity_id)
        )

    if kind == "automation_invocation":
        return await session.scalar(
            select(AutomationDefinition.keycloak_subject)
            .join(AutomationInvocation, AutomationInvocation.automation_id == AutomationDefinition.id)
            .where(AutomationInvocation.id == entity_id)
        )

    if kind == "finance_source":
        return await session.scalar(select(FinanceSource.keycloak_subject).where(FinanceSource.id == entity_id))

    if kind == "finance_account":
        return await session.scalar(
            select(FinanceSource.keycloak_subject)
            .join(FinanceAccount, FinanceAccount.source_id == FinanceSource.id)
            .where(FinanceAccount.id == entity_id)
        )

    if kind == "finance_position":
        return await session.scalar(
            select(FinanceSource.keycloak_subject)
            .join(FinanceAccount, FinanceAccount.source_id == FinanceSource.id)
            .join(FinancePosition, FinancePosition.account_id == FinanceAccount.id)
            .where(FinancePosition.id == entity_id)
        )

    if kind == "finance_transaction_proposal":
        return await session.scalar(
            select(FinanceTransactionProposal.keycloak_subject).where(
                FinanceTransactionProposal.id == entity_id
            )
        )

    if kind == "finance_connector":
        return await session.scalar(
            select(FinanceConnector.keycloak_subject).where(FinanceConnector.id == entity_id)
        )

    if kind == "tool_invocation":
        return await session.scalar(
            select(ToolInvocation.keycloak_subject).where(ToolInvocation.id == entity_id)
        )

    return None
