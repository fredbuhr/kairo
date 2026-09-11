import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .command_models import CommandRecord
from .db import get_session
from .document_models import Document, DocumentVersion
from .events import append_audit, enqueue_domain_event
from .models import Artifact, Task, WorkflowExecution
from .project_access import get_owned_task
from .schemas import (
    ArtifactRead,
    InternalCompleteRequest,
    InternalCompleteResponse,
    InternalFailRequest,
    InternalStartResponse,
    TaskRunResponse,
)
from .security import require_internal_token
from .temporal_gateway import temporal_gateway

router = APIRouter()


def _workflow_id(task_id: uuid.UUID) -> str:
    return f"kairo-task-{task_id}"


async def _lock_execution(session: AsyncSession, workflow_id: str) -> WorkflowExecution | None:
    """Reload and lock the execution so stale request state cannot overwrite Worker progress."""

    return await session.scalar(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def _propagate_semantic_route_failure(
    session: AsyncSession,
    *,
    task: Task,
    execution: WorkflowExecution,
    error: str,
) -> None:
    """Make a failed semantic routing Task terminal in the canonical Command state too.

    The routing Task is an implementation detail of the Command Kernel. If it reaches a terminal
    failure before Core accepts or rejects a semantic proposal, clients must not poll `routing`
    forever. A Command that has already been accepted/unsupported is deliberately left untouched:
    a late infrastructure failure cannot revoke an authoritative route that Core already applied.
    """

    task_input = task.input or {}
    if str(task_input.get("capability") or "") != "assistant.route.semantic":
        return

    raw_command_id = task_input.get("command_id")
    if raw_command_id is None:
        return
    try:
        command_id = uuid.UUID(str(raw_command_id))
    except (TypeError, ValueError):
        return

    command = await session.scalar(
        select(CommandRecord).where(CommandRecord.id == command_id).with_for_update()
    )
    if command is None or command.status != "routing":
        return

    command.status = "failed"
    command.route_reason = "semantic.execution-failed"
    command.result_json = {
        **(command.result_json or {}),
        "semantic_error": error[:4000],
        "routing_status": "failed",
        "routing_task_id": str(task.id),
        "routing_workflow_execution_id": str(execution.id),
        "routing_workflow_id": execution.workflow_id,
    }
    await enqueue_domain_event(
        session,
        event_type="command.failed",
        aggregate_type="command",
        aggregate_id=command.id,
        correlation_id=command.correlation_id,
        payload={
            "command_id": str(command.id),
            "route_reason": command.route_reason,
            "routing_task_id": str(task.id),
            "workflow_execution_id": str(execution.id),
        },
    )
    await append_audit(
        session,
        actor_type="worker",
        actor_id=execution.workflow_id,
        action="command.semantic_route.fail",
        resource_type="command",
        resource_id=str(command.id),
        authority_level=1,
        correlation_id=command.correlation_id,
        idempotency_key=f"command:{command.id}:semantic-route-fail",
        result_json={"error": error[:4000], "routing_task_id": str(task.id)},
    )


async def _propagate_document_ingestion_failure(
    session: AsyncSession,
    *,
    task: Task,
    execution: WorkflowExecution,
    error: str,
) -> None:
    """Project a terminal document Task failure onto its canonical parse generation.

    Worker activity attempts are intentionally not allowed to mark a DocumentVersion terminal:
    Temporal may still retry them. This hook only runs from the canonical workflow failure path,
    after the activity retry policy has been exhausted or policy has terminally denied execution.
    """

    task_input = task.input or {}
    if str(task_input.get("capability") or "") != "document.ingest":
        return

    raw_version_id = task_input.get("document_version_id")
    if raw_version_id is None:
        return
    try:
        version_id = uuid.UUID(str(raw_version_id))
    except (TypeError, ValueError):
        return

    version = await session.scalar(
        select(DocumentVersion).where(DocumentVersion.id == version_id).with_for_update()
    )
    if version is None or version.status == "completed":
        return

    transitioned = version.status != "failed"
    version.status = "failed"
    version.last_error = error[:4000]
    version.completed_at = version.completed_at or datetime.now(UTC)

    document = await session.scalar(
        select(Document).where(Document.id == version.document_id).with_for_update()
    )
    if document is not None:
        latest_generation = int(
            await session.scalar(
                select(func.max(DocumentVersion.generation)).where(
                    DocumentVersion.document_id == document.id
                )
            )
            or version.generation
        )
        if version.generation == latest_generation:
            document.status = "failed"

    if not transitioned:
        return

    await enqueue_domain_event(
        session,
        event_type="document.ingestion.failed",
        aggregate_type="document_version",
        aggregate_id=version.id,
        correlation_id=execution.correlation_id,
        payload={
            "document_id": str(version.document_id),
            "document_version_id": str(version.id),
            "generation": version.generation,
            "task_id": str(task.id),
            "workflow_execution_id": str(execution.id),
            "error": error[:4000],
        },
    )
    await append_audit(
        session,
        actor_type="worker",
        actor_id=execution.workflow_id,
        action="document.ingest.fail",
        resource_type="document_version",
        resource_id=str(version.id),
        authority_level=1,
        correlation_id=execution.correlation_id,
        idempotency_key=f"document-version:{version.id}:ingestion-fail",
        result_json={"error": error[:4000], "task_id": str(task.id)},
    )


async def run_task(
    task_id: uuid.UUID,
    session: AsyncSession,
    *,
    actor_id: str | None = None,
) -> TaskRunResponse:
    """Start or resume one canonical Task.

    This function is intentionally transport-agnostic so internal Core modules can schedule their
    own already-authorized Tasks. The public HTTP wrapper below performs requester ownership checks.
    """

    task = await session.get(Task, task_id, with_for_update=True)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="Completed task cannot be started again")

    workflow_id = _workflow_id(task.id)
    execution = await session.scalar(
        select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
    )
    if execution is None:
        correlation_id = uuid.uuid4()
        execution = WorkflowExecution(
            task_id=task.id,
            workflow_id=workflow_id,
            status="pending_start",
            correlation_id=correlation_id,
        )
        session.add(execution)
        task.status = "queued"
        await session.flush()
        await enqueue_domain_event(
            session,
            event_type="execution.requested",
            aggregate_type="workflow_execution",
            aggregate_id=execution.id,
            correlation_id=correlation_id,
            payload={
                "execution_id": str(execution.id),
                "workflow_id": workflow_id,
                "task_id": str(task.id),
            },
        )
        await append_audit(
            session,
            actor_type="user",
            actor_id=actor_id,
            action="task.run.request",
            resource_type="task",
            resource_id=str(task.id),
            authority_level=min(task.authority_ceiling, 1),
            correlation_id=correlation_id,
        )
        await session.commit()
        await session.refresh(execution)
    else:
        correlation_id = execution.correlation_id
        await session.commit()

    payload = {
        "task_id": str(task.id),
        "workflow_id": workflow_id,
        "workflow_execution_id": str(execution.id),
        "correlation_id": str(correlation_id),
    }
    try:
        already_started, run_id = await temporal_gateway.start_task_workflow(
            workflow_id=workflow_id, payload=payload
        )
    except Exception as exc:
        locked_execution = await _lock_execution(session, workflow_id)
        if locked_execution is None:
            raise HTTPException(status_code=404, detail="Workflow execution not found") from exc

        if locked_execution.status in {"running", "completed"}:
            await session.commit()
            return TaskRunResponse(
                task_id=task.id,
                workflow_execution_id=locked_execution.id,
                workflow_id=workflow_id,
                status=locked_execution.status,
                already_started=True,
            )

        locked_execution.status = "start_unknown"
        locked_execution.last_error = str(exc)[:4000]
        await enqueue_domain_event(
            session,
            event_type="execution.start_unknown",
            aggregate_type="workflow_execution",
            aggregate_id=locked_execution.id,
            correlation_id=correlation_id,
            payload={
                "execution_id": str(locked_execution.id),
                "workflow_id": workflow_id,
                "task_id": str(task.id),
                "reason": "Temporal start result is unknown; retry with the same workflow ID",
            },
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Temporal start outcome is unknown; retrying is safe",
                "workflow_id": workflow_id,
            },
        ) from exc

    locked_execution = await _lock_execution(session, workflow_id)
    if locked_execution is None:
        raise HTTPException(status_code=404, detail="Workflow execution not found")
    if locked_execution.status in {"pending_start", "start_unknown"}:
        locked_execution.status = "queued"
    locked_execution.run_id = run_id or locked_execution.run_id
    locked_execution.last_error = None
    await enqueue_domain_event(
        session,
        event_type="execution.accepted",
        aggregate_type="workflow_execution",
        aggregate_id=locked_execution.id,
        correlation_id=correlation_id,
        payload={
            "execution_id": str(locked_execution.id),
            "workflow_id": workflow_id,
            "task_id": str(task.id),
            "already_started": already_started,
            "observed_status": locked_execution.status,
        },
    )
    await session.commit()
    return TaskRunResponse(
        task_id=task.id,
        workflow_execution_id=locked_execution.id,
        workflow_id=workflow_id,
        status=locked_execution.status,
        already_started=already_started,
    )


@router.post("/v1/tasks/{task_id}/run", response_model=TaskRunResponse)
async def run_owned_task(
    task_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> TaskRunResponse:
    if not await get_owned_task(session, task_id, principal):
        raise HTTPException(status_code=404, detail="Task not found")
    return await run_task(task_id, session, actor_id=principal.subject)


@router.post(
    "/internal/v1/tasks/{task_id}/run",
    response_model=TaskRunResponse,
    dependencies=[Depends(require_internal_token)],
)
async def run_internal_system_task(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TaskRunResponse:
    """Start a system-owned Task from a trusted KAIRO service.

    Internal callers must not use this route to bypass user ownership for ordinary user Tasks.
    Only deterministic/system Tasks such as memory projections are eligible.
    """

    task = await session.get(Task, task_id)
    if task is None or task.owner_type != "system":
        raise HTTPException(status_code=404, detail="Task not found")
    actor_id = str(task.owner_ref or "internal-system")
    return await run_task(task_id, session, actor_id=actor_id)


@router.post(
    "/internal/v1/executions/{workflow_id}/start",
    response_model=InternalStartResponse,
    dependencies=[Depends(require_internal_token)],
)
async def internal_start_execution(
    workflow_id: str, session: AsyncSession = Depends(get_session)
) -> InternalStartResponse:
    execution = await session.scalar(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .with_for_update()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Workflow execution not found")
    task = await session.get(Task, execution.task_id, with_for_update=True)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if execution.status not in {"running", "completed"}:
        now = datetime.now(UTC)
        execution.status = "running"
        execution.started_at = execution.started_at or now
        task.status = "running"
        task.started_at = task.started_at or now
        await enqueue_domain_event(
            session,
            event_type="execution.started",
            aggregate_type="workflow_execution",
            aggregate_id=execution.id,
            correlation_id=execution.correlation_id,
            payload={"execution_id": str(execution.id), "task_id": str(task.id)},
        )
        await append_audit(
            session,
            actor_type="worker",
            actor_id=workflow_id,
            action="task.execution.start",
            resource_type="task",
            resource_id=str(task.id),
            authority_level=min(task.authority_ceiling, 1),
            correlation_id=execution.correlation_id,
            idempotency_key=f"{workflow_id}:start",
        )
        await session.commit()

    return InternalStartResponse(
        task_id=task.id,
        task_title=task.title,
        task_input=task.input,
        execution_status=execution.status,
    )


@router.post(
    "/internal/v1/executions/{workflow_id}/complete",
    response_model=InternalCompleteResponse,
    dependencies=[Depends(require_internal_token)],
)
async def internal_complete_execution(
    workflow_id: str,
    body: InternalCompleteRequest,
    session: AsyncSession = Depends(get_session),
) -> InternalCompleteResponse:
    execution = await session.scalar(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .with_for_update()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Workflow execution not found")
    task = await session.get(Task, execution.task_id, with_for_update=True)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    artifact = await session.scalar(
        select(Artifact).where(Artifact.workflow_execution_id == execution.id)
    )
    if execution.status == "completed" and artifact:
        return InternalCompleteResponse(execution_status="completed", artifact=artifact)

    if artifact is None:
        artifact = Artifact(
            project_id=task.project_id,
            task_id=task.id,
            workflow_execution_id=execution.id,
            kind=body.kind,
            title=body.title,
            content=body.content,
        )
        session.add(artifact)
        await session.flush()
        await enqueue_domain_event(
            session,
            event_type="artifact.created",
            aggregate_type="artifact",
            aggregate_id=artifact.id,
            correlation_id=execution.correlation_id,
            payload={
                "artifact_id": str(artifact.id),
                "task_id": str(task.id),
                "project_id": str(task.project_id),
                "kind": artifact.kind,
            },
        )

    now = datetime.now(UTC)
    execution.status = "completed"
    execution.completed_at = execution.completed_at or now
    execution.last_error = None
    task.status = "completed"
    task.completed_at = task.completed_at or now
    await enqueue_domain_event(
        session,
        event_type="task.completed",
        aggregate_type="task",
        aggregate_id=task.id,
        correlation_id=execution.correlation_id,
        payload={"task_id": str(task.id), "artifact_id": str(artifact.id)},
    )
    await append_audit(
        session,
        actor_type="worker",
        actor_id=workflow_id,
        action="task.execution.complete",
        resource_type="task",
        resource_id=str(task.id),
        authority_level=min(task.authority_ceiling, 1),
        correlation_id=execution.correlation_id,
        idempotency_key=f"{workflow_id}:complete",
        result_json={"artifact_id": str(artifact.id)},
    )
    await session.commit()
    await session.refresh(artifact)
    return InternalCompleteResponse(execution_status="completed", artifact=artifact)


@router.post(
    "/internal/v1/executions/{workflow_id}/fail",
    dependencies=[Depends(require_internal_token)],
)
async def internal_fail_execution(
    workflow_id: str,
    body: InternalFailRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    execution = await session.scalar(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .with_for_update()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Workflow execution not found")
    task = await session.get(Task, execution.task_id, with_for_update=True)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if execution.status != "completed":
        if execution.status != "failed":
            execution.status = "failed"
            execution.last_error = body.error
            task.status = "failed"
            await enqueue_domain_event(
                session,
                event_type="execution.failed",
                aggregate_type="workflow_execution",
                aggregate_id=execution.id,
                correlation_id=execution.correlation_id,
                payload={"execution_id": str(execution.id), "task_id": str(task.id)},
            )
            await append_audit(
                session,
                actor_type="worker",
                actor_id=workflow_id,
                action="task.execution.fail",
                resource_type="task",
                resource_id=str(task.id),
                authority_level=min(task.authority_ceiling, 1),
                correlation_id=execution.correlation_id,
                idempotency_key=f"{workflow_id}:fail",
                result_json={"error": body.error},
            )
        await _propagate_semantic_route_failure(
            session,
            task=task,
            execution=execution,
            error=body.error,
        )
        await _propagate_document_ingestion_failure(
            session,
            task=task,
            execution=execution,
            error=body.error,
        )
        await session.commit()
    return {"status": execution.status}


@router.get("/v1/tasks/{task_id}/artifacts", response_model=list[ArtifactRead])
async def task_artifacts(
    task_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[Artifact]:
    if not await get_owned_task(session, task_id, principal):
        raise HTTPException(status_code=404, detail="Task not found")
    result = await session.execute(
        select(Artifact).where(Artifact.task_id == task_id).order_by(Artifact.created_at)
    )
    return list(result.scalars())
