import asyncio
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import __version__
from .approval_signals import router as approval_signals_router
from .assistant import router as assistant_router
from .assets import router as assets_router
from .autonomy import router as autonomy_router
from .components import load_component_registry
from .config import settings
from .db import get_session, ping_database
from .documents import router as documents_router
from .events import append_audit, enqueue_domain_event
from .graph import router as graph_router
from .graph_activity import router as graph_activity_router
from .memory import router as memory_router
from .models import OutboxEvent, Project, RelationshipRecord, Task
from .news import router as news_router
from .openbao import openbao_client
from .outbox import OutboxRelay
from .research import router as research_router
from .resources import router as resources_router
from .schemas import (
    OutboxStats,
    ProjectCreate,
    ProjectRead,
    RelationshipCreate,
    RelationshipRead,
    SystemReadiness,
    TaskCreate,
    TaskRead,
)
from .temporal_gateway import temporal_gateway
from .tools import router as tools_router
from .workflows import router as workflow_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    relay = OutboxRelay()
    relay_task = asyncio.create_task(relay.run(), name="kairo-outbox-relay")
    app.state.outbox_relay = relay
    try:
        yield
    finally:
        await relay.stop()
        relay_task.cancel()
        await asyncio.gather(relay_task, return_exceptions=True)


app = FastAPI(title="KAIRO Core", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.kairo_cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(workflow_router)
app.include_router(memory_router)
app.include_router(documents_router)
app.include_router(graph_router)
app.include_router(graph_activity_router)
app.include_router(tools_router)
app.include_router(research_router)
app.include_router(news_router)
app.include_router(assistant_router)
app.include_router(resources_router)
app.include_router(assets_router)
app.include_router(autonomy_router)
app.include_router(approval_signals_router)


@app.get("/health/live")
async def liveness() -> dict[str, str]:
    return {
        "service": "kairo-core",
        "status": "ok",
        "version": __version__,
        "environment": settings.kairo_env,
    }


@app.get("/health")
async def health_alias() -> dict[str, str]:
    return await liveness()


async def _seaweed_ready() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.seaweed_filer_endpoint.rstrip('/')}/")
        return response.status_code < 500
    except Exception:
        return False


async def _temporal_ready() -> bool:
    try:
        return await temporal_gateway.health()
    except Exception:
        return False


async def _keycloak_ready() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(settings.keycloak_jwks_url)
        if response.status_code != 200:
            return False
        payload = response.json()
        return isinstance(payload.get("keys"), list) and bool(payload["keys"])
    except Exception:
        return False


@app.get("/health/ready", response_model=SystemReadiness)
async def readiness(request: Request) -> SystemReadiness:
    relay: OutboxRelay = request.app.state.outbox_relay
    postgres_ok, temporal_ok, seaweed_ok = await asyncio.gather(
        ping_database(), _temporal_ready(), _seaweed_ready(), return_exceptions=True
    )
    checks = {
        "postgres": postgres_ok is True,
        "nats": relay.connected,
        "temporal": temporal_ok is True,
        "seaweedfs": seaweed_ok is True,
    }
    if not all(checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not-ready", "checks": checks},
        )
    return SystemReadiness(status="ready", checks=checks)


@app.get("/health/trust", response_model=SystemReadiness)
async def trust_readiness() -> SystemReadiness:
    keycloak_ok, openbao_ok, seaweed_ok = await asyncio.gather(
        _keycloak_ready(), openbao_client.health(), _seaweed_ready(), return_exceptions=True
    )
    checks = {
        "keycloak": keycloak_ok is True,
        "openbao": openbao_ok is True,
        "seaweedfs": seaweed_ok is True,
    }
    if not all(checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "trust-boundary-not-ready", "checks": checks},
        )
    return SystemReadiness(status="ready", checks=checks)


@app.get("/v1/system/components")
async def components() -> dict:
    return load_component_registry()


@app.get("/v1/system/architecture")
async def architecture() -> dict[str, object]:
    return {
        "canonical_state": "postgresql",
        "canonical_objects": "seaweedfs-filer",
        "durable_execution": "temporal",
        "event_bus": "nats-jetstream",
        "event_delivery": "transactional-outbox-at-least-once",
        "identity": "keycloak-jwt-jwks",
        "secret_values": "openbao",
        "conversation_state": "postgresql",
        "canonical_documents": "postgresql-document-version-chunks",
        "document_parser": "docling",
        "capability_registry": "kairo-core",
        "tool_registry": "kairo-core-postgresql",
        "tool_transport": "mcp-streamable-http",
        "tool_policy": "deny-by-default-explicit-enable",
        "autonomous_research": "pydanticai-planner-policy-bound-mcp-child-tasks",
        "command_routing": "deterministic-first-semantic-later",
        "spatial_graph_projection": "kairo-core-canonical-read-model",
        "spatial_graph_activity": "kairo-core-sanitized-sse-from-canonical-outbox",
        "derived_context_graph": "graphiti-neo4j",
        "derived_memory": "mem0",
        "model_gateway": "litellm",
        "news_discovery": "searxng",
        "news_speech": "kokoro-fastapi",
        "policy_default": "deny",
        "policy_authority": "kairo-core-signed-capability-token",
        "model_budget_ledger": "postgresql",
    }


@app.get("/v1/system/outbox", response_model=OutboxStats)
async def outbox_stats(
    request: Request, session: AsyncSession = Depends(get_session)
) -> OutboxStats:
    pending = await session.scalar(
        select(func.count()).select_from(OutboxEvent).where(OutboxEvent.published_at.is_(None))
    )
    published = await session.scalar(
        select(func.count()).select_from(OutboxEvent).where(OutboxEvent.published_at.is_not(None))
    )
    relay: OutboxRelay = request.app.state.outbox_relay
    return OutboxStats(
        pending=int(pending or 0), published=int(published or 0), relay_connected=relay.connected
    )


@app.post("/v1/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate, session: AsyncSession = Depends(get_session)
) -> Project:
    correlation_id = uuid.uuid4()
    if body.parent_id and not await session.get(Project, body.parent_id):
        raise HTTPException(status_code=404, detail="Parent project not found")
    project = Project(**body.model_dump())
    session.add(project)
    await session.flush()
    await enqueue_domain_event(
        session,
        event_type="project.created",
        aggregate_type="project",
        aggregate_id=project.id,
        correlation_id=correlation_id,
        payload={"project_id": str(project.id), "name": project.name},
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=None,
        action="project.create",
        resource_type="project",
        resource_id=str(project.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(project)
    return project


@app.get("/v1/projects", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[Project]:
    rows = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return list(rows.scalars())


@app.post("/v1/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, session: AsyncSession = Depends(get_session)) -> Task:
    if not await session.get(Project, body.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    correlation_id = uuid.uuid4()
    task = Task(**body.model_dump())
    session.add(task)
    await session.flush()
    await enqueue_domain_event(
        session,
        event_type="task.created",
        aggregate_type="task",
        aggregate_id=task.id,
        correlation_id=correlation_id,
        payload={"task_id": str(task.id), "project_id": str(task.project_id), "title": task.title},
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=None,
        action="task.create",
        resource_type="task",
        resource_id=str(task.id),
        authority_level=min(task.authority_ceiling, 1),
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(task)
    return task


@app.get("/v1/tasks", response_model=list[TaskRead])
async def list_tasks(session: AsyncSession = Depends(get_session)) -> list[Task]:
    rows = await session.execute(select(Task).order_by(Task.created_at.desc()))
    return list(rows.scalars())


@app.get("/v1/tasks/{task_id}", response_model=TaskRead)
async def get_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Task:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/v1/relationships", response_model=RelationshipRead, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    body: RelationshipCreate, session: AsyncSession = Depends(get_session)
) -> RelationshipRecord:
    correlation_id = uuid.uuid4()
    relationship = RelationshipRecord(
        source_type=body.source_type,
        source_id=body.source_id,
        relation_type=body.relation_type,
        target_type=body.target_type,
        target_id=body.target_id,
        metadata_json=body.metadata,
    )
    session.add(relationship)
    await session.flush()
    await enqueue_domain_event(
        session,
        event_type="relationship.created",
        aggregate_type="relationship",
        aggregate_id=relationship.id,
        correlation_id=correlation_id,
        payload={
            "relationship_id": str(relationship.id),
            "source_type": relationship.source_type,
            "source_id": str(relationship.source_id),
            "relation_type": relationship.relation_type,
            "target_type": relationship.target_type,
            "target_id": str(relationship.target_id),
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=None,
        action="relationship.create",
        resource_type="relationship",
        resource_id=str(relationship.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(relationship)
    return relationship
