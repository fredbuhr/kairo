from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import nats
from fastapi import APIRouter, Depends, HTTPException, status
from nats.js.errors import NotFoundError
from pydantic import BaseModel
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .automation_models import AutomationDefinition, AutomationInvocation
from .autonomy_models import ApprovalRequest
from .config import settings
from .db import get_session
from .models import AuditRecord, OutboxEvent, Project, Task, WorkflowExecution
from .outbox import DOMAIN_SUBJECT
from .tool_models import ToolInvocation

router = APIRouter(prefix="/v1/account/evidence", tags=["account-lifecycle"])

_TERMINAL_TASK_STATUSES = {"completed", "done", "failed", "cancelled", "archived"}
_TERMINAL_WORKFLOW_STATUSES = {"completed", "failed", "cancelled"}
_TERMINAL_INVOCATION_STATUSES = {"completed", "failed", "cancelled"}
_RETENTION_BATCH_LIMIT = 250
_TRANSPORT_EXPIRY_GRACE_SECONDS = 300
_REDACTED = "[erased-user]"


class EvidenceRetentionBlockerRead(BaseModel):
    code: str
    count: int | None = None
    detail: str


class EvidenceRetentionPlanRead(BaseModel):
    generated_at: datetime
    mode: Literal["minimize_audit_delete_outbox"] = "minimize_audit_delete_outbox"
    subject_owned_audit_records: int
    shared_audit_actor_references: int
    subject_owned_outbox_events: int
    unpublished_subject_outbox_events: int
    mapped_published_outbox_events: int
    unmapped_published_outbox_events: int
    partial_receipt_outbox_events: int
    historical_unmapped_safe_after: datetime | None = None
    batch_limit: int = _RETENTION_BATCH_LIMIT
    request_ready: bool
    blockers: list[EvidenceRetentionBlockerRead]


class EvidenceRetentionApplyRequest(BaseModel):
    confirmation: Literal["MINIMIZE_ACCOUNT_EVIDENCE"]


class EvidenceRetentionApplyRead(BaseModel):
    status: Literal["partial", "complete"]
    outbox_rows_removed: int
    jetstream_messages_deleted: int
    jetstream_messages_already_absent: int
    historical_transport_expiry_accepted: int
    audit_rows_minimized: int
    shared_actor_references_redacted: int
    remaining_subject_outbox_events: int
    remaining_subject_audit_records: int
    remaining_shared_actor_references: int


async def _count(session: AsyncSession, statement) -> int:
    return int(await session.scalar(statement) or 0)


async def _active_work_blockers(session: AsyncSession, subject: str) -> list[EvidenceRetentionBlockerRead]:
    project_filter = Project.keycloak_subject == subject
    active_tasks = await _count(
        session,
        select(func.count())
        .select_from(Task)
        .join(Project, Project.id == Task.project_id)
        .where(project_filter, ~Task.status.in_(_TERMINAL_TASK_STATUSES)),
    )
    active_workflows = await _count(
        session,
        select(func.count())
        .select_from(WorkflowExecution)
        .join(Task, Task.id == WorkflowExecution.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(project_filter, ~WorkflowExecution.status.in_(_TERMINAL_WORKFLOW_STATUSES)),
    )
    pending_approvals = await _count(
        session,
        select(func.count())
        .select_from(ApprovalRequest)
        .join(Task, Task.id == ApprovalRequest.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(project_filter, ApprovalRequest.status == "pending"),
    )
    active_automations = await _count(
        session,
        select(func.count())
        .select_from(AutomationInvocation)
        .join(AutomationDefinition, AutomationDefinition.id == AutomationInvocation.automation_id)
        .where(
            AutomationDefinition.keycloak_subject == subject,
            ~AutomationInvocation.status.in_(_TERMINAL_INVOCATION_STATUSES),
        ),
    )
    active_tools = await _count(
        session,
        select(func.count())
        .select_from(ToolInvocation)
        .where(
            ToolInvocation.keycloak_subject == subject,
            ~ToolInvocation.status.in_(_TERMINAL_INVOCATION_STATUSES),
        ),
    )

    blockers: list[EvidenceRetentionBlockerRead] = []
    for code, count, detail in (
        ("active_tasks", active_tasks, "Canonical Tasks are still non-terminal."),
        ("active_workflows", active_workflows, "Temporal WorkflowExecutions are still non-terminal."),
        ("pending_approvals", pending_approvals, "Pending ApprovalRequests still exist."),
        (
            "active_automation_invocations",
            active_automations,
            "Automation side-effect reconciliation is still active.",
        ),
        ("active_tool_invocations", active_tools, "MCP ToolInvocations are still non-terminal."),
    ):
        if count:
            blockers.append(EvidenceRetentionBlockerRead(code=code, count=count, detail=detail))
    return blockers


async def _plan(session: AsyncSession, subject: str) -> EvidenceRetentionPlanRead:
    subject_audit = await _count(
        session,
        select(func.count()).select_from(AuditRecord).where(AuditRecord.keycloak_subject == subject),
    )
    shared_actor = await _count(
        session,
        select(func.count())
        .select_from(AuditRecord)
        .where(
            AuditRecord.actor_type == "user",
            AuditRecord.actor_id == subject,
            or_(AuditRecord.keycloak_subject.is_(None), AuditRecord.keycloak_subject != subject),
        ),
    )
    outbox_total = await _count(
        session,
        select(func.count()).select_from(OutboxEvent).where(OutboxEvent.keycloak_subject == subject),
    )
    unpublished = await _count(
        session,
        select(func.count())
        .select_from(OutboxEvent)
        .where(OutboxEvent.keycloak_subject == subject, OutboxEvent.published_at.is_(None)),
    )
    mapped = await _count(
        session,
        select(func.count())
        .select_from(OutboxEvent)
        .where(
            OutboxEvent.keycloak_subject == subject,
            OutboxEvent.published_at.is_not(None),
            OutboxEvent.jetstream_stream.is_not(None),
            OutboxEvent.jetstream_sequence.is_not(None),
        ),
    )
    partial = await _count(
        session,
        select(func.count())
        .select_from(OutboxEvent)
        .where(
            OutboxEvent.keycloak_subject == subject,
            OutboxEvent.published_at.is_not(None),
            or_(
                (OutboxEvent.jetstream_stream.is_(None) & OutboxEvent.jetstream_sequence.is_not(None)),
                (OutboxEvent.jetstream_stream.is_not(None) & OutboxEvent.jetstream_sequence.is_(None)),
            ),
        ),
    )
    unmapped = await _count(
        session,
        select(func.count())
        .select_from(OutboxEvent)
        .where(
            OutboxEvent.keycloak_subject == subject,
            OutboxEvent.published_at.is_not(None),
            OutboxEvent.jetstream_stream.is_(None),
            OutboxEvent.jetstream_sequence.is_(None),
        ),
    )
    latest_unmapped_published = await session.scalar(
        select(func.max(OutboxEvent.published_at)).where(
            OutboxEvent.keycloak_subject == subject,
            OutboxEvent.published_at.is_not(None),
            OutboxEvent.jetstream_stream.is_(None),
            OutboxEvent.jetstream_sequence.is_(None),
        )
    )
    safe_after = None
    if latest_unmapped_published is not None:
        safe_after = latest_unmapped_published + timedelta(
            seconds=max(60, settings.nats_domain_retention_seconds) + _TRANSPORT_EXPIRY_GRACE_SECONDS
        )

    blockers = await _active_work_blockers(session, subject)
    if unpublished:
        blockers.append(
            EvidenceRetentionBlockerRead(
                code="unpublished_outbox",
                count=unpublished,
                detail="Outbox events must be published before transport copies can be reconciled.",
            )
        )
    if partial:
        blockers.append(
            EvidenceRetentionBlockerRead(
                code="partial_jetstream_receipt",
                count=partial,
                detail="Outbox rows contain incomplete stream/sequence receipts and require operator repair.",
            )
        )
    now = datetime.now(UTC)
    if safe_after is not None and safe_after > now:
        blockers.append(
            EvidenceRetentionBlockerRead(
                code="historical_transport_retention_window",
                count=unmapped,
                detail=(
                    "Historical published events without exact JetStream receipts must age past the "
                    "configured max-age plus the retention safety grace before PostgreSQL evidence can be removed."
                ),
            )
        )

    return EvidenceRetentionPlanRead(
        generated_at=now,
        subject_owned_audit_records=subject_audit,
        shared_audit_actor_references=shared_actor,
        subject_owned_outbox_events=outbox_total,
        unpublished_subject_outbox_events=unpublished,
        mapped_published_outbox_events=mapped,
        unmapped_published_outbox_events=unmapped,
        partial_receipt_outbox_events=partial,
        historical_unmapped_safe_after=safe_after,
        request_ready=not blockers,
        blockers=blockers,
    )


def _redact_subject_json(value: Any, subject: str) -> Any:
    if isinstance(value, dict):
        return {str(key): _redact_subject_json(child, subject) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact_subject_json(child, subject) for child in value]
    if isinstance(value, str):
        return value.replace(subject, _REDACTED)
    return value


async def _assert_stream_contract():
    """Return a connected (nc, js, stream_exists) tuple for privacy reconciliation.

    The retention action does not silently broaden or repair NATS policy. Core/Worker bootstrap already
    converges the stream. Here we verify the declared max-age/subject contract before treating time as
    proof that a historical unreceipted transport copy must have expired.
    """

    try:
        nc = await nats.connect(
            settings.nats_url,
            name="kairo-core-account-evidence-retention",
            connect_timeout=3,
            max_reconnect_attempts=1,
        )
        js = nc.jetstream()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NATS is unavailable; account evidence retention cannot verify transport state",
        ) from exc

    try:
        try:
            info = await js.stream_info(settings.nats_domain_stream)
        except NotFoundError:
            return nc, js, False
        config = info.config
        expected_age = float(max(60, settings.nats_domain_retention_seconds))
        actual_age = float(config.max_age or 0)
        if list(config.subjects or []) != [DOMAIN_SUBJECT] or actual_age <= 0 or actual_age > expected_age:
            raise HTTPException(
                status_code=409,
                detail=(
                    "KAIRO domain stream retention does not match the declared bounded contract; "
                    "reconcile the stream before account evidence retention"
                ),
            )
        return nc, js, True
    except Exception:
        await nc.close()
        raise


@router.get("/retention", response_model=EvidenceRetentionPlanRead)
async def evidence_retention_plan(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> EvidenceRetentionPlanRead:
    return await _plan(session, principal.subject)


@router.post("/retention/apply", response_model=EvidenceRetentionApplyRead)
async def apply_evidence_retention(
    _: EvidenceRetentionApplyRequest,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> EvidenceRetentionApplyRead:
    """Minimize subject-owned Audit evidence and clear published Outbox transport state.

    This is an erasure-preparation primitive, not account deletion. It is deliberately idempotent and
    may be repeated. Any later user-world activity creates fresh evidence and makes account preflight
    require this stage again.
    """

    plan = await _plan(session, principal.subject)
    if not plan.request_ready:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Account evidence retention is not ready",
                "blockers": [blocker.model_dump(mode="json") for blocker in plan.blockers],
            },
        )

    rows = list(
        (
            await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.keycloak_subject == principal.subject)
                .order_by(OutboxEvent.created_at, OutboxEvent.id)
                .limit(_RETENTION_BATCH_LIMIT)
            )
        ).scalars()
    )

    deleted_messages = 0
    absent_messages = 0
    expired_historical = 0
    if rows:
        nc, js, stream_exists = await _assert_stream_contract()
        try:
            now = datetime.now(UTC)
            expiry_cutoff = now - timedelta(
                seconds=max(60, settings.nats_domain_retention_seconds)
                + _TRANSPORT_EXPIRY_GRACE_SECONDS
            )
            for row in rows:
                if row.published_at is None:
                    raise HTTPException(status_code=409, detail="Subject Outbox still contains unpublished events")
                has_stream = row.jetstream_stream is not None
                has_seq = row.jetstream_sequence is not None
                if has_stream != has_seq:
                    raise HTTPException(status_code=409, detail="Outbox JetStream receipt is incomplete")

                if has_stream and has_seq:
                    if row.jetstream_stream != settings.nats_domain_stream:
                        raise HTTPException(
                            status_code=409,
                            detail="Outbox receipt points at an unexpected JetStream stream",
                        )
                    if not stream_exists:
                        absent_messages += 1
                        continue
                    try:
                        removed = await js.delete_msg(
                            str(row.jetstream_stream),
                            int(row.jetstream_sequence),
                        )
                    except NotFoundError:
                        absent_messages += 1
                    else:
                        if removed:
                            deleted_messages += 1
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="JetStream did not confirm message deletion",
                            )
                    continue

                if not stream_exists:
                    expired_historical += 1
                    continue
                published_at = row.published_at
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=UTC)
                if published_at > expiry_cutoff:
                    raise HTTPException(
                        status_code=409,
                        detail="Historical Outbox transport retention window has not elapsed",
                    )
                expired_historical += 1
        finally:
            if not nc.is_closed:
                await nc.drain()

        row_ids = [row.id for row in rows]
        result = await session.execute(
            delete(OutboxEvent).where(
                OutboxEvent.keycloak_subject == principal.subject,
                OutboxEvent.id.in_(row_ids),
            )
        )
        outbox_removed = int(result.rowcount or 0)
    else:
        outbox_removed = 0

    remaining_outbox = await _count(
        session,
        select(func.count()).select_from(OutboxEvent).where(OutboxEvent.keycloak_subject == principal.subject),
    )

    audit_minimized = 0
    shared_redacted = 0
    if remaining_outbox == 0:
        subject_audit_rows = list(
            (
                await session.execute(
                    select(AuditRecord).where(AuditRecord.keycloak_subject == principal.subject)
                )
            ).scalars()
        )
        shared_actor_rows = list(
            (
                await session.execute(
                    select(AuditRecord).where(
                        AuditRecord.actor_type == "user",
                        AuditRecord.actor_id == principal.subject,
                        or_(
                            AuditRecord.keycloak_subject.is_(None),
                            AuditRecord.keycloak_subject != principal.subject,
                        ),
                    )
                )
            ).scalars()
        )

        for record in subject_audit_rows:
            record.keycloak_subject = None
            record.actor_id = None
            record.resource_id = "erased"
            record.correlation_id = uuid.uuid4()
            record.idempotency_key = None
            record.request_json = {}
            record.result_json = {"retention": "minimized"}
            audit_minimized += 1

        for record in shared_actor_rows:
            record.actor_id = None
            record.resource_id = record.resource_id.replace(principal.subject, _REDACTED)
            record.idempotency_key = None
            record.request_json = _redact_subject_json(record.request_json or {}, principal.subject)
            record.result_json = _redact_subject_json(record.result_json or {}, principal.subject)
            shared_redacted += 1

        # Preserve a deployment-neutral receipt of the destructive evidence operation. It has no
        # subject/actor identifier and therefore does not recreate the personal evidence just erased.
        session.add(
            AuditRecord(
                keycloak_subject=None,
                actor_type="system",
                actor_id=None,
                action="account.evidence.retention.apply",
                resource_type="account_retention",
                resource_id=str(uuid.uuid4()),
                authority_level=1,
                correlation_id=uuid.uuid4(),
                request_json={},
                result_json={
                    "outbox_rows_removed": outbox_removed,
                    "audit_rows_minimized": audit_minimized,
                    "shared_actor_references_redacted": shared_redacted,
                    "status": "complete",
                },
            )
        )

    await session.commit()

    remaining_audit = await _count(
        session,
        select(func.count()).select_from(AuditRecord).where(AuditRecord.keycloak_subject == principal.subject),
    )
    remaining_shared = await _count(
        session,
        select(func.count())
        .select_from(AuditRecord)
        .where(
            AuditRecord.actor_type == "user",
            AuditRecord.actor_id == principal.subject,
            or_(AuditRecord.keycloak_subject.is_(None), AuditRecord.keycloak_subject != principal.subject),
        ),
    )
    complete = remaining_outbox == 0 and remaining_audit == 0 and remaining_shared == 0
    return EvidenceRetentionApplyRead(
        status="complete" if complete else "partial",
        outbox_rows_removed=outbox_removed,
        jetstream_messages_deleted=deleted_messages,
        jetstream_messages_already_absent=absent_messages,
        historical_transport_expiry_accepted=expired_historical,
        audit_rows_minimized=audit_minimized,
        shared_actor_references_redacted=shared_redacted,
        remaining_subject_outbox_events=remaining_outbox,
        remaining_subject_audit_records=remaining_audit,
        remaining_shared_actor_references=remaining_shared,
    )
