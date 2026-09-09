from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .automation_models import AutomationDefinition, AutomationInvocation
from .autonomy_models import ApprovalRequest, ModelUsageRecord
from .calendar_models import CalendarSource, ExternalCalendarEvent
from .command_models import CommandRecord, Conversation, ConversationMessage
from .db import get_session
from .document_models import Document, DocumentChunk, DocumentVersion
from .finance_models import (
    FinanceAccount,
    FinanceConnector,
    FinancePosition,
    FinanceSource,
    FinanceTransactionProposal,
)
from .memory_models import MemoryProjectionRecord
from .models import (
    Artifact,
    Asset,
    AuditRecord,
    DeviceRegistration,
    OutboxEvent,
    Project,
    RelationshipRecord,
    SecretReference,
    Task,
    WorkflowExecution,
)
from .tool_models import ToolInvocation

router = APIRouter(prefix="/v1/account", tags=["account-lifecycle"])

_TERMINAL_TASK_STATUSES = {"completed", "done", "failed", "cancelled", "archived"}
_TERMINAL_WORKFLOW_STATUSES = {"completed", "failed", "cancelled"}
_TERMINAL_INVOCATION_STATUSES = {"completed", "failed", "cancelled"}


class ObjectStorageInventory(BaseModel):
    tracked_objects: int = 0
    tracked_bytes: int = 0
    boundary: Literal["seaweedfs_assets"] = "seaweedfs_assets"


class DerivedProjectionInventory(BaseModel):
    memory_projection_records: int = 0
    projectors: list[str] = Field(default_factory=lambda: ["mem0", "graphiti"])
    canonical: Literal[False] = False
    purge_adapter_available: bool = True
    latest_canonical_message_at: datetime | None = None
    latest_completed_purge_cutoff_at: datetime | None = None
    purge_current: bool = False


class EvidenceInventory(BaseModel):
    subject_owned_audit_records: int = 0
    shared_audit_actor_references: int = 0
    subject_owned_outbox_events: int = 0
    unpublished_subject_outbox_events: int = 0
    data_subject_addressable: bool = True
    retention_action_available: bool = True


class RetentionBoundaryRead(BaseModel):
    key: str
    state: Literal["canonical", "derived", "shared_retention", "external"]
    detail: str


class AccountDataInventoryRead(BaseModel):
    generated_at: datetime
    canonical_counts: dict[str, int]
    canonical_rows_total: int
    object_storage: ObjectStorageInventory
    derived_projections: DerivedProjectionInventory
    evidence: EvidenceInventory
    boundaries: list[RetentionBoundaryRead]


class AccountExportManifestRead(BaseModel):
    schema_version: Literal["kairo.account-export-manifest.v1"] = "kairo.account-export-manifest.v1"
    generated_at: datetime
    status: Literal["manifest_only"] = "manifest_only"
    inventory: AccountDataInventoryRead
    includes: list[str]
    excludes: list[str]
    bundle_export_available: bool = False


class ErasureBlockerRead(BaseModel):
    code: str
    scope: Literal["canonical", "complete"]
    count: int | None = None
    resolvable_by_user: bool = False
    detail: str


class AccountErasurePreflightRead(BaseModel):
    generated_at: datetime
    canonical_delete_ready: bool
    complete_erasure_ready: bool
    blockers: list[ErasureBlockerRead]
    inventory: AccountDataInventoryRead
    destructive_endpoint_available: bool = False


async def _scalar_int(session: AsyncSession, statement) -> int:
    value = await session.scalar(statement)
    return int(value or 0)


def _parse_iso_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


async def _derived_projection_state(
    session: AsyncSession,
    subject: str,
    *,
    memory_projection_count: int,
) -> DerivedProjectionInventory:
    latest_message_at = await session.scalar(
        select(func.max(ConversationMessage.created_at))
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.subject_ref == subject)
    )
    latest_purge_task = await session.scalar(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(
            Project.keycloak_subject == subject,
            Task.input["capability"].astext == "memory.purge",
            Task.status.in_(["completed", "done"]),
        )
        .order_by(Task.completed_at.desc().nullslast(), Task.updated_at.desc())
        .limit(1)
    )
    purge_cutoff = (
        _parse_iso_datetime((latest_purge_task.input or {}).get("purge_cutoff_at"))
        if latest_purge_task is not None
        else None
    )
    purge_current = latest_message_at is None or (
        purge_cutoff is not None
        and purge_cutoff >= latest_message_at
        and memory_projection_count == 0
    )
    return DerivedProjectionInventory(
        memory_projection_records=memory_projection_count,
        latest_canonical_message_at=latest_message_at,
        latest_completed_purge_cutoff_at=purge_cutoff,
        purge_current=purge_current,
    )


async def _evidence_inventory(session: AsyncSession, subject: str) -> EvidenceInventory:
    subject_owned_audit = await _scalar_int(
        session,
        select(func.count())
        .select_from(AuditRecord)
        .where(AuditRecord.keycloak_subject == subject),
    )
    shared_actor_refs = await _scalar_int(
        session,
        select(func.count())
        .select_from(AuditRecord)
        .where(
            AuditRecord.actor_type == "user",
            AuditRecord.actor_id == subject,
            or_(
                AuditRecord.keycloak_subject.is_(None),
                AuditRecord.keycloak_subject != subject,
            ),
        ),
    )
    subject_outbox = await _scalar_int(
        session,
        select(func.count())
        .select_from(OutboxEvent)
        .where(OutboxEvent.keycloak_subject == subject),
    )
    unpublished_subject_outbox = await _scalar_int(
        session,
        select(func.count())
        .select_from(OutboxEvent)
        .where(
            OutboxEvent.keycloak_subject == subject,
            OutboxEvent.published_at.is_(None),
        ),
    )
    return EvidenceInventory(
        subject_owned_audit_records=subject_owned_audit,
        shared_audit_actor_references=shared_actor_refs,
        subject_owned_outbox_events=subject_outbox,
        unpublished_subject_outbox_events=unpublished_subject_outbox,
        retention_action_available=True,
    )


async def _inventory(session: AsyncSession, subject: str) -> AccountDataInventoryRead:
    project_filter = Project.keycloak_subject == subject

    project_count = await _scalar_int(
        session,
        select(func.count()).select_from(Project).where(project_filter),
    )
    task_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(Task)
        .join(Project, Project.id == Task.project_id)
        .where(project_filter),
    )
    workflow_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(WorkflowExecution)
        .join(Task, Task.id == WorkflowExecution.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(project_filter),
    )
    artifact_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(Artifact)
        .join(Project, Project.id == Artifact.project_id)
        .where(project_filter),
    )
    relationship_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(RelationshipRecord)
        .where(RelationshipRecord.keycloak_subject == subject),
    )
    approval_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(ApprovalRequest)
        .join(Task, Task.id == ApprovalRequest.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(project_filter),
    )
    model_usage_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(ModelUsageRecord)
        .join(Task, Task.id == ModelUsageRecord.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(project_filter),
    )

    asset_count = await _scalar_int(
        session,
        select(func.count()).select_from(Asset).where(Asset.keycloak_subject == subject),
    )
    asset_bytes = await _scalar_int(
        session,
        select(func.coalesce(func.sum(Asset.size_bytes), 0)).where(Asset.keycloak_subject == subject),
    )
    document_count = await _scalar_int(
        session,
        select(func.count()).select_from(Document).where(Document.keycloak_subject == subject),
    )
    document_version_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(DocumentVersion)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(Document.keycloak_subject == subject),
    )
    document_chunk_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(DocumentChunk)
        .join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(Document.keycloak_subject == subject),
    )

    conversation_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.subject_ref == subject),
    )
    message_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(ConversationMessage)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.subject_ref == subject),
    )
    command_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(CommandRecord)
        .join(Conversation, Conversation.id == CommandRecord.conversation_id)
        .where(Conversation.subject_ref == subject),
    )
    owned_message_ids = (
        select(ConversationMessage.id)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.subject_ref == subject)
    )
    memory_projection_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(MemoryProjectionRecord)
        .where(
            MemoryProjectionRecord.source_type == "conversation_message",
            MemoryProjectionRecord.source_id.in_(owned_message_ids),
        ),
    )
    derived_projection_state = await _derived_projection_state(
        session,
        subject,
        memory_projection_count=memory_projection_count,
    )

    device_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(DeviceRegistration)
        .where(DeviceRegistration.keycloak_subject == subject),
    )
    secret_reference_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(SecretReference)
        .where(SecretReference.keycloak_subject == subject),
    )

    calendar_source_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(CalendarSource)
        .where(CalendarSource.keycloak_subject == subject),
    )
    calendar_event_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(ExternalCalendarEvent)
        .join(CalendarSource, CalendarSource.id == ExternalCalendarEvent.source_id)
        .where(CalendarSource.keycloak_subject == subject),
    )

    finance_source_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(FinanceSource)
        .where(FinanceSource.keycloak_subject == subject),
    )
    finance_account_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(FinanceAccount)
        .join(FinanceSource, FinanceSource.id == FinanceAccount.source_id)
        .where(FinanceSource.keycloak_subject == subject),
    )
    finance_position_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(FinancePosition)
        .join(FinanceAccount, FinanceAccount.id == FinancePosition.account_id)
        .join(FinanceSource, FinanceSource.id == FinanceAccount.source_id)
        .where(FinanceSource.keycloak_subject == subject),
    )
    finance_proposal_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(FinanceTransactionProposal)
        .where(FinanceTransactionProposal.keycloak_subject == subject),
    )
    finance_connector_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(FinanceConnector)
        .where(FinanceConnector.keycloak_subject == subject),
    )

    automation_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(AutomationDefinition)
        .where(AutomationDefinition.keycloak_subject == subject),
    )
    automation_invocation_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(AutomationInvocation)
        .join(AutomationDefinition, AutomationDefinition.id == AutomationInvocation.automation_id)
        .where(AutomationDefinition.keycloak_subject == subject),
    )
    tool_invocation_count = await _scalar_int(
        session,
        select(func.count())
        .select_from(ToolInvocation)
        .where(ToolInvocation.keycloak_subject == subject),
    )

    counts = {
        "projects": project_count,
        "tasks": task_count,
        "workflow_executions": workflow_count,
        "artifacts": artifact_count,
        "relationships": relationship_count,
        "approval_requests": approval_count,
        "model_usage_records": model_usage_count,
        "assets": asset_count,
        "documents": document_count,
        "document_versions": document_version_count,
        "document_chunks": document_chunk_count,
        "conversations": conversation_count,
        "conversation_messages": message_count,
        "commands": command_count,
        "devices": device_count,
        "secret_references": secret_reference_count,
        "calendar_sources": calendar_source_count,
        "external_calendar_events": calendar_event_count,
        "finance_sources": finance_source_count,
        "finance_accounts": finance_account_count,
        "finance_positions": finance_position_count,
        "finance_transaction_proposals": finance_proposal_count,
        "finance_connectors": finance_connector_count,
        "automation_definitions": automation_count,
        "automation_invocations": automation_invocation_count,
        "tool_invocations": tool_invocation_count,
    }

    return AccountDataInventoryRead(
        generated_at=datetime.now(UTC),
        canonical_counts=counts,
        canonical_rows_total=sum(counts.values()),
        object_storage=ObjectStorageInventory(
            tracked_objects=asset_count,
            tracked_bytes=asset_bytes,
        ),
        derived_projections=derived_projection_state,
        evidence=await _evidence_inventory(session, subject),
        boundaries=[
            RetentionBoundaryRead(
                key="audit_outbox",
                state="shared_retention",
                detail=(
                    "Subject-owned Audit evidence can be irreversibly minimized and published Outbox "
                    "transport state can be deleted after exact JetStream receipt deletion or verified "
                    "max-age expiry. Shared administrative actor references are redacted separately."
                ),
            ),
            RetentionBoundaryRead(
                key="mem0_graphiti",
                state="derived",
                detail=(
                    "Mem0/Graphiti are rebuildable projections. A subject-scoped purge adapter is "
                    "available; a purge is current only when its completed cutoff covers the latest "
                    "canonical conversation message."
                ),
            ),
            RetentionBoundaryRead(
                key="keycloak_identity",
                state="external",
                detail="Deleting KAIRO data does not currently delete the Keycloak identity.",
            ),
            RetentionBoundaryRead(
                key="encrypted_backups",
                state="shared_retention",
                detail=(
                    "Historical encrypted backups require a documented expiry/restore policy; "
                    "they cannot support surgical subject deletion in place."
                ),
            ),
        ],
    )


@router.get("/data-inventory", response_model=AccountDataInventoryRead)
async def account_data_inventory(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> AccountDataInventoryRead:
    return await _inventory(session, principal.subject)


@router.get("/export/manifest", response_model=AccountExportManifestRead)
async def account_export_manifest(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> AccountExportManifestRead:
    inventory = await _inventory(session, principal.subject)
    return AccountExportManifestRead(
        generated_at=datetime.now(UTC),
        inventory=inventory,
        includes=[
            "subject-scoped canonical record inventory",
            "tracked SeaweedFS Asset object count and bytes",
            "rebuildable memory projection ledger count and purge freshness",
            "subject-addressable audit/outbox evidence counts (not raw retained payloads)",
            "retention-boundary declarations",
        ],
        excludes=[
            "secret values (write-only OpenBao material is never exported)",
            "shared deployment MCP server endpoint topology",
            "Mem0/Graphiti derived payloads",
            "raw Audit/Outbox evidence (retention minimizes/removes it rather than exporting it)",
            "Keycloak credentials/tokens",
        ],
    )


@router.get("/erasure/preflight", response_model=AccountErasurePreflightRead)
async def account_erasure_preflight(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> AccountErasurePreflightRead:
    inventory = await _inventory(session, principal.subject)
    project_filter = Project.keycloak_subject == principal.subject

    active_tasks = await _scalar_int(
        session,
        select(func.count())
        .select_from(Task)
        .join(Project, Project.id == Task.project_id)
        .where(project_filter, ~Task.status.in_(_TERMINAL_TASK_STATUSES)),
    )
    active_workflows = await _scalar_int(
        session,
        select(func.count())
        .select_from(WorkflowExecution)
        .join(Task, Task.id == WorkflowExecution.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(project_filter, ~WorkflowExecution.status.in_(_TERMINAL_WORKFLOW_STATUSES)),
    )
    pending_approvals = await _scalar_int(
        session,
        select(func.count())
        .select_from(ApprovalRequest)
        .join(Task, Task.id == ApprovalRequest.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(project_filter, ApprovalRequest.status == "pending"),
    )
    active_automations = await _scalar_int(
        session,
        select(func.count())
        .select_from(AutomationInvocation)
        .join(AutomationDefinition, AutomationDefinition.id == AutomationInvocation.automation_id)
        .where(
            AutomationDefinition.keycloak_subject == principal.subject,
            ~AutomationInvocation.status.in_(_TERMINAL_INVOCATION_STATUSES),
        ),
    )
    active_tool_invocations = await _scalar_int(
        session,
        select(func.count())
        .select_from(ToolInvocation)
        .where(
            ToolInvocation.keycloak_subject == principal.subject,
            ~ToolInvocation.status.in_(_TERMINAL_INVOCATION_STATUSES),
        ),
    )

    blockers: list[ErasureBlockerRead] = []
    for code, count, detail in (
        (
            "active_tasks",
            active_tasks,
            "Canonical work is still active; finish/cancel it before destructive deletion.",
        ),
        (
            "active_workflows",
            active_workflows,
            "Temporal-backed workflow executions are still non-terminal.",
        ),
        (
            "pending_approvals",
            pending_approvals,
            "Pending approval decisions still exist for this account.",
        ),
        (
            "active_automation_invocations",
            active_automations,
            "Automation side-effect executions are still non-terminal.",
        ),
        (
            "active_tool_invocations",
            active_tool_invocations,
            "MCP tool executions are still non-terminal.",
        ),
    ):
        if count:
            blockers.append(
                ErasureBlockerRead(
                    code=code,
                    scope="canonical",
                    count=count,
                    resolvable_by_user=True,
                    detail=detail,
                )
            )

    secret_count = inventory.canonical_counts.get("secret_references", 0)
    if secret_count:
        blockers.append(
            ErasureBlockerRead(
                code="secret_references_remaining",
                scope="complete",
                count=secret_count,
                resolvable_by_user=True,
                detail=(
                    "Personal SecretReferences remain. Their OpenBao values must be explicitly "
                    "destroyed before complete erasure."
                ),
            )
        )

    if not inventory.derived_projections.purge_current:
        blockers.append(
            ErasureBlockerRead(
                code="derived_projection_purge_required",
                scope="complete",
                count=inventory.derived_projections.memory_projection_records,
                resolvable_by_user=True,
                detail=(
                    "Mem0/Graphiti derived memory must be purged after the latest canonical "
                    "conversation message. Canonical conversations are preserved by this action."
                ),
            )
        )

    evidence_count = (
        inventory.evidence.subject_owned_audit_records
        + inventory.evidence.shared_audit_actor_references
        + inventory.evidence.subject_owned_outbox_events
    )
    if evidence_count:
        blockers.append(
            ErasureBlockerRead(
                code="audit_outbox_retention_required",
                scope="complete",
                count=evidence_count,
                resolvable_by_user=inventory.evidence.retention_action_available,
                detail=(
                    "Apply the explicit account evidence retention action: published Outbox transport "
                    "copies are deleted/reconciled first, then subject-owned Audit rows are minimized "
                    "and shared administrative actor references are redacted."
                ),
            )
        )

    blockers.extend(
        [
            ErasureBlockerRead(
                code="keycloak_identity_deletion_not_implemented",
                scope="complete",
                detail="KAIRO Core does not currently delete the external Keycloak identity.",
            ),
            ErasureBlockerRead(
                code="backup_retention_policy_not_verified",
                scope="complete",
                detail=(
                    "Encrypted backup expiry and restore-after-erasure semantics are not yet "
                    "formally verified."
                ),
            ),
        ]
    )

    canonical_ready = not any(blocker.scope == "canonical" for blocker in blockers)
    complete_ready = canonical_ready and not blockers
    return AccountErasurePreflightRead(
        generated_at=datetime.now(UTC),
        canonical_delete_ready=canonical_ready,
        complete_erasure_ready=complete_ready,
        blockers=blockers,
        inventory=inventory,
    )
