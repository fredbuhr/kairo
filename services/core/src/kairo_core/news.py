import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .config import settings
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Artifact, Project, Task, WorkflowExecution
from .ownership import DEVELOPMENT_SUBJECT, ensure_system_project, owned_task
from .schemas import NewsBriefCreate, NewsBriefRead, NewsBriefRunResponse
from .workflows import run_task

router = APIRouter()

NEWS_PROJECT_ID = uuid.UUID("b8d9cccf-257b-4b48-b58e-4fe63a4398b2")


async def _ensure_news_project(session: AsyncSession, subject: str) -> Project:
    project, created = await ensure_system_project(
        session,
        subject=subject,
        key="news",
        name="KAIRO News",
        summary="Per-user system workspace for sourced news briefings and market-impact intelligence.",
        legacy_development_id=NEWS_PROJECT_ID,
    )
    if created:
        correlation_id = uuid.uuid4()
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
            request_json={"reason": "initialize owner-scoped News Intelligence workspace", "subject": subject},
        )
    return project


def _task_title(body: NewsBriefCreate) -> str:
    prefix = "Market brief" if body.mode == "market_impact" else "News brief"
    return f"{prefix} — {body.query}"[:320]


async def _get_news_task(task_id: uuid.UUID, session: AsyncSession, subject: str) -> Task:
    task = await owned_task(session, task_id, subject)
    if not task or (task.input or {}).get("capability") != "news.brief":
        raise HTTPException(status_code=404, detail="News brief not found")
    return task


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
    actor_type: str = "user",
    actor_id: str | None = None,
    owner_subject: str | None = None,
    correlation_id: uuid.UUID | None = None,
    command_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
) -> NewsBriefRunResponse:
    """Start the canonical News capability independently of the invoking transport.

    A caller may provide a deterministic ``task_id``. This makes a semantic-routing handoff replay-safe:
    if the Worker retries after Core already created or started the final task, the same canonical task
    and WorkflowExecution are reused rather than creating a duplicate News request.
    """

    subject = owner_subject or actor_id or DEVELOPMENT_SUBJECT
    project = await _ensure_news_project(session, subject)
    correlation_id = correlation_id or uuid.uuid4()
    requested_task_id = task_id

    if requested_task_id is not None:
        existing = await owned_task(session, requested_task_id, subject)
        if existing is None and await session.get(Task, requested_task_id) is not None:
            raise HTTPException(status_code=409, detail="Deterministic task ID is already in use")
        if existing is not None:
            existing_input = existing.input or {}
            if existing_input.get("capability") != "news.brief":
                raise HTTPException(status_code=409, detail="Deterministic task ID is already in use")
            if command_id is not None and existing_input.get("command_id") != str(command_id):
                raise HTTPException(status_code=409, detail="News task is bound to another command")
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
    if command_id is not None:
        task_input["command_id"] = str(command_id)

    task = Task(
        id=requested_task_id or uuid.uuid4(),
        project_id=project.id,
        title=_task_title(body),
        description="Sourced news briefing generated by KAIRO News Intelligence.",
        status="todo",
        owner_type=actor_type,
        owner_ref=actor_id,
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
        actor_id=actor_id,
        action="news.brief.request",
        resource_type="task",
        resource_id=str(task.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            **body.model_dump(mode="json"),
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
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> NewsBriefRunResponse:
    return await start_news_brief(
        body,
        session,
        actor_type="user",
        actor_id=principal.subject,
        owner_subject=principal.subject,
    )


@router.get("/v1/news/briefs/{task_id}", response_model=NewsBriefRead)
async def get_news_brief(
    task_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> NewsBriefRead:
    task = await _get_news_task(task_id, session, principal.subject)
    artifact = await session.scalar(
        select(Artifact)
        .where(Artifact.task_id == task.id, Artifact.kind == "news-brief")
        .order_by(Artifact.created_at.desc())
        .limit(1)
    )
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
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    task = await _get_news_task(task_id, session, principal.subject)
    artifact = await session.scalar(
        select(Artifact)
        .where(Artifact.task_id == task.id, Artifact.kind == "news-brief")
        .order_by(Artifact.created_at.desc())
        .limit(1)
    )
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
            detail="Local TTS service is unavailable. Start KAIRO with the voice profile enabled.",
        ) from exc

    return Response(
        content=response.content,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="kairo-news-{task.id}.mp3"'},
    )
