import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_nevolium_user
from .config import settings
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Artifact, Project, Task, WorkflowExecution
from .schemas import NewsBriefCreate, NewsBriefRead, NewsBriefRunResponse
from .workflows import run_task

router = APIRouter()


def _news_project_id(subject: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"nevolium:project:news:subject:{subject}")


async def _ensure_news_project(session: AsyncSession, subject: str) -> Project:
    normalized_subject = subject.strip()
    if not normalized_subject:
        raise HTTPException(status_code=409, detail="News request has no owner")

    project_id = _news_project_id(normalized_subject)
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_subject == normalized_subject,
        )
    )
    if project is not None:
        return project

    correlation_id = uuid.uuid4()
    inserted_id = await session.scalar(
        pg_insert(Project)
        .values(
            id=project_id,
            owner_subject=normalized_subject,
            name="Nevolium News",
            status="active",
            summary="Per-user system workspace for sourced news briefings and market-impact intelligence.",
            parent_id=None,
        )
        .on_conflict_do_nothing(index_elements=[Project.id])
        .returning(Project.id)
    )
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_subject == normalized_subject,
        )
    )
    if project is None:
        raise RuntimeError("Nevolium News workspace could not be initialized for this owner")

    if inserted_id is not None:
        await enqueue_domain_event(
            session,
            event_type="project.created",
            aggregate_type="project",
            aggregate_id=project.id,
            correlation_id=correlation_id,
            payload={"project_id": str(project.id), "name": project.name, "status": project.status},
        )
        await append_audit(
            session,
            actor_type="system",
            actor_id="news-intelligence",
            action="project.create",
            resource_type="project",
            resource_id=str(project.id),
            authority_level=0,
            correlation_id=correlation_id,
            request_json={
                "reason": "initialize owner-scoped News Intelligence workspace",
                "subject": normalized_subject,
            },
        )
    return project


def _task_title(body: NewsBriefCreate) -> str:
    prefix = "Market brief" if body.mode == "market_impact" else "News brief"
    return f"{prefix} — {body.query}"[:320]


async def _get_news_task(
    task_id: uuid.UUID,
    session: AsyncSession,
    *,
    requester_subject: str,
) -> Task:
    task = await session.scalar(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(
            Task.id == task_id,
            Project.owner_subject == requester_subject,
            Task.owner_type == "user",
            Task.owner_ref == requester_subject,
        )
    )
    task_input = task.input if task is not None else {}
    if (
        task is None
        or (task_input or {}).get("capability") != "news.brief"
        or str((task_input or {}).get("requester_subject") or "") != requester_subject
    ):
        raise HTTPException(status_code=404, detail="News brief not found")
    return task


async def _get_news_artifact(task: Task, session: AsyncSession) -> Artifact | None:
    """Return only an Artifact whose canonical task, project and execution bindings all agree."""

    return await session.scalar(
        select(Artifact)
        .join(WorkflowExecution, WorkflowExecution.id == Artifact.workflow_execution_id)
        .where(
            Artifact.task_id == task.id,
            Artifact.project_id == task.project_id,
            Artifact.kind == "news-brief",
            WorkflowExecution.task_id == task.id,
            WorkflowExecution.workflow_id == f"nevolium-task-{task.id}",
        )
        .order_by(Artifact.created_at.desc())
        .limit(1)
    )


def _response_from_execution(
    task: Task, execution: WorkflowExecution, body: NewsBriefCreate
) -> NewsBriefRunResponse:
    return NewsBriefRunResponse(
        task_id=task.id,
        workflow_execution_id=execution.id,
        workflow_id=execution.workflow_id,
        status=execution.status,
        query=body.query,
        mode=body.mode,
        output=body.output,
    )


async def start_news_brief(
    body: NewsBriefCreate,
    session: AsyncSession,
    *,
    requester_subject: str | None = None,
    actor_type: str = "user",
    actor_id: str | None = None,
    correlation_id: uuid.UUID | None = None,
    command_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
) -> NewsBriefRunResponse:
    """Start the canonical News capability independently of the invoking transport.

    News state is always bound to a concrete requester subject. A caller may provide a deterministic
    ``task_id``. This makes a semantic-routing handoff replay-safe: if the Worker retries after Core
    already created or started the final task, the same owner-bound canonical task and
    WorkflowExecution are reused rather than creating a duplicate News request.
    """

    subject = str(requester_subject or actor_id or "").strip()
    if not subject:
        raise HTTPException(status_code=409, detail="News request has no owner")

    project = await _ensure_news_project(session, subject)
    correlation_id = correlation_id or uuid.uuid4()
    requested_task_id = task_id

    if requested_task_id is not None:
        existing = await session.get(Task, requested_task_id)
        if existing is not None:
            existing_input = existing.input or {}
            if existing_input.get("capability") != "news.brief":
                raise HTTPException(status_code=409, detail="Deterministic task ID is already in use")
            if existing.project_id != project.id:
                raise HTTPException(status_code=409, detail="News task is bound to another project")
            if existing.owner_type != "user" or existing.owner_ref != subject:
                raise HTTPException(status_code=409, detail="News task is bound to another requester")
            if str(existing_input.get("requester_subject") or "") != subject:
                raise HTTPException(status_code=409, detail="News task is bound to another requester")
            if command_id is not None and existing_input.get("command_id") != str(command_id):
                raise HTTPException(status_code=409, detail="News task is bound to another command")

            expected = body.model_dump(mode="json")
            actual = {key: existing_input.get(key) for key in expected}
            if actual != expected:
                raise HTTPException(
                    status_code=409,
                    detail="Deterministic News task cannot be rebound to different execution parameters",
                )

            execution = await session.scalar(
                select(WorkflowExecution).where(WorkflowExecution.task_id == existing.id)
            )
            if execution is not None:
                return _response_from_execution(existing, execution, body)
            run = await run_task(existing.id, session)
            return NewsBriefRunResponse(
                task_id=existing.id,
                workflow_execution_id=run.workflow_execution_id,
                workflow_id=run.workflow_id,
                status=run.status,
                query=body.query,
                mode=body.mode,
                output=body.output,
            )

    task_input = body.model_dump(mode="json")
    task_input["capability"] = "news.brief"
    task_input["requester_subject"] = subject
    if command_id is not None:
        task_input["command_id"] = str(command_id)

    task = Task(
        id=requested_task_id or uuid.uuid4(),
        project_id=project.id,
        title=_task_title(body),
        description="Sourced news briefing generated by Nevolium News Intelligence.",
        status="todo",
        owner_type="user",
        owner_ref=subject,
        authority_ceiling=1,
        input=task_input,
    )
    session.add(task)
    await session.flush()
    event_payload = {
        "task_id": str(task.id),
        "query": body.query,
        "mode": body.mode,
        "time_range": body.time_range,
    }
    if command_id is not None:
        event_payload["command_id"] = str(command_id)
    await enqueue_domain_event(
        session,
        event_type="news.brief.requested",
        aggregate_type="task",
        aggregate_id=task.id,
        correlation_id=correlation_id,
        payload=event_payload,
    )
    await append_audit(
        session,
        actor_type=actor_type,
        actor_id=actor_id or subject,
        action="news.brief.request",
        resource_type="task",
        resource_id=str(task.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            **body.model_dump(mode="json"),
            "requester_subject": subject,
            **({"command_id": str(command_id)} if command_id is not None else {}),
        },
    )
    await session.commit()

    execution = await run_task(task.id, session)
    return NewsBriefRunResponse(
        task_id=task.id,
        workflow_execution_id=execution.workflow_execution_id,
        workflow_id=execution.workflow_id,
        status=execution.status,
        query=body.query,
        mode=body.mode,
        output=body.output,
    )


@router.post(
    "/v1/news/briefs",
    response_model=NewsBriefRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_news_brief(
    body: NewsBriefCreate,
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
) -> NewsBriefRunResponse:
    return await start_news_brief(
        body,
        session,
        requester_subject=principal.subject,
        actor_type="user",
        actor_id=principal.subject,
    )


@router.get("/v1/news/briefs/{task_id}", response_model=NewsBriefRead)
async def get_news_brief(
    task_id: uuid.UUID,
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
) -> NewsBriefRead:
    task = await _get_news_task(task_id, session, requester_subject=principal.subject)
    artifact = await _get_news_artifact(task, session)
    task_input = task.input or {}
    return NewsBriefRead(
        task_id=task.id,
        status=task.status,
        query=str(task_input.get("query") or task.title),
        mode=str(task_input.get("mode") or "general"),
        output=str(task_input.get("output") or "text"),
        voice=str(task_input.get("voice") or settings.kokoro_default_voice),
        artifact=artifact,
        audio_available=artifact is not None,
    )


@router.get("/v1/news/briefs/{task_id}/audio")
async def news_brief_audio(
    task_id: uuid.UUID,
    voice: str | None = None,
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    task = await _get_news_task(task_id, session, requester_subject=principal.subject)
    artifact = await _get_news_artifact(task, session)
    if not artifact:
        raise HTTPException(status_code=409, detail="News brief is not completed yet")

    spoken_summary = str(
        artifact.content.get("spoken_summary") or artifact.content.get("summary") or ""
    ).strip()
    if not spoken_summary:
        raise HTTPException(status_code=422, detail="News brief has no text to synthesize")

    selected_voice = (voice or str((task.input or {}).get("voice") or settings.kokoro_default_voice))[:120]
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.kokoro_tts_url.rstrip('/')}/v1/audio/speech",
                json={
                    "model": "kokoro",
                    "voice": selected_voice,
                    "input": spoken_summary[:12000],
                    "response_format": "mp3",
                    "speed": 1.0,
                },
            )
            response.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local TTS service is unavailable. Start Nevolium with the voice profile enabled.",
        ) from exc

    return Response(
        content=response.content,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="nevolium-news-{task.id}.mp3"'},
    )
