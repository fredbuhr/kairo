import asyncio
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import __version__
from .approval_signals import router as approval_signals_router
from .assistant import router as assistant_router
from .assets import router as assets_router
from .auth import (
    Principal,
    authenticate_authorization_header,
    principal_is_kairo_user,
    require_kairo_user,
)
from .automations import router as automations_router
from .autonomy import router as autonomy_router
from .calendar_external import router as calendar_external_router
from .components import load_component_registry
from .config import settings
from .db import SessionFactory, get_session, ping_database
from .documents import router as documents_router
from .events import append_audit, enqueue_domain_event
from .finance import router as finance_router
from .finance_connectors import router as finance_connectors_router
from .graph import router as graph_router
from .graph_activity import router as graph_activity_router
from .graph_directives import router as graph_directives_router
from .knowledge import router as knowledge_router
from .memory import router as memory_router
from .models import OutboxEvent, Project, RelationshipRecord, Task
from .news import router as news_router
from .openbao import openbao_client
from .operations import router as operations_router
from .outbox import OutboxRelay
from .ownership import owned_project, owned_task, require_owned_project, require_same_owner_entities
from .planning import router as planning_router
from .project_management import router as project_management_router
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
from .tool_management import router as tool_management_router
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


async def _owned_path_guard(path: str, subject: str) -> str | None:
    """Protect canonical project/task subroutes even if a new handler forgets its local scope check."""

    parts = [part for part in path.split("/") if part]
    if len(parts) < 3 or parts[0] != "v1" or parts[1] not in {"projects", "tasks"}:
        return None
    try:
        entity_id = uuid.UUID(parts[2])
    except ValueError:
        return None

    async with SessionFactory() as session:
        if parts[1] == "projects":
            owned = await owned_project(session, entity_id, subject)
            return None if owned is not None else "Project not found"
        owned = await owned_task(session, entity_id, subject)
        return None if owned is not None else "Task not found"


@app.middleware("http")
async def authenticated_public_api_perimeter(request: Request, call_next):
    """Fail closed for every public `/v1` route, including newly added routers.

    Internal Worker/connector routes live under `/internal/v1` and keep their separate internal-token
    boundary. Health endpoints remain unauthenticated for orchestrator readiness. CORS preflights are
    allowed through to CORSMiddleware without requiring a bearer token.
    """

    if request.method == "OPTIONS" or not request.url.path.startswith("/v1/"):
        return await call_next(request)

    try:
        principal = await authenticate_authorization_header(request.headers.get("authorization"))
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {},
        )

    if not principal_is_kairo_user(principal):
        return JSONResponse(status_code=403, content={"detail": "KAIRO user role required"})

    ownership_error = await _owned_path_guard(request.url.path, principal.subject)
    if ownership_error is not None:
        return JSONResponse(status_code=404, content={"detail": ownership_error})

    request.state.principal = principal
    return await call_next(request)


# Keep CORS outside the auth perimeter so even 401/403 responses carry the browser-visible CORS
# headers for explicitly allowed KAIRO Web/Desktop origins.
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
app.include_router(knowledge_router)
app.include_router(planning_router)
app.include_router(calendar_external_router)
app.include_router(project_management_router)
app.include_router(operations_router)
app.include_router(automations_router)
app.include_router(finance_router)
app.include_router(finance_connectors_router)
app.include_router(graph_router)
app.include_router(graph_activity_router)
app.include_router(graph_directives_router)
app.include_router(tools_router)
app.include_router(tool_management_router)
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
        "public_api_authentication": "fail-closed-v1-bearer-perimeter",
        "domain_ownership": "project-root-keycloak-subject-with-explicit-polymorphic-ownership",
        "secret_values": "openbao",
        "conversation_state": "postgresql",
        "canonical_documents": "postgresql-document-version-chunks",
        "document_parser": "docling",
        "knowledge_retrieval": "kairo-core-latest-canonical-document-chunks",
        "project_lifecycle": "kairo-core-canonical-project-mutation",
        "task_planning": "kairo-core-canonical-priority-schedule-due-fields",
        "today_projection": "kairo-core-explicit-task-planning-read-model",
        "external_calendar": "kairo-core-provenance-preserving-external-source-snapshots",
        "agent_operations": "kairo-core-capability-task-workflow-approval-usage-read-model",
        "automation_registry": "kairo-core-postgresql-activepieces-webhook-boundary",
        "automation_execution": "temporal-no-retry-after-webhook-side-effect-boundary",
        "finance_portfolio": "kairo-core-provenance-preserving-source-account-position-snapshots",
        "finance_connectors": "kairo-core-owned-read-only-provider-control-plane",
        "finance_rotki": "deployment-owned-origin-openbao-credentials-temporal-read-sync",
        "finance_signing": "external-isolated-signer-never-ai-private-key-custody",
        "capability_registry": "kairo-core",
        "tool_registry": "kairo-core-postgresql",
        "tool_transport": "mcp-streamable-http",
        "tool_policy": "deny-by-default-explicit-enable",
        "tool_management": "kairo-core-fail-closed-server-and-tool-policy",
        "autonomous_research": "pydanticai-planner-policy-bound-mcp-child-tasks",
        "command_routing": "deterministic-first-semantic-later",
        "spatial_graph_projection": "kairo-core-canonical-read-model",
        "mind_map_projection": "kairo-graph-shared-canonical-projection-local-layout",
        "spatial_graph_activity": "kairo-core-sanitized-sse-from-canonical-outbox",
        "spatial_ui_directives": "kairo-core-typed-deterministic-navigation",
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
    body: ProjectCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> Project:
    correlation_id = uuid.uuid4()
    if body.parent_id:
        await require_owned_project(session, body.parent_id, principal.subject)
    project = Project(keycloak_subject=principal.subject, **body.model_dump())
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
        actor_id=principal.subject,
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
async def list_projects(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[Project]:
    rows = await session.execute(
        select(Project)
        .where(Project.keycloak_subject == principal.subject)
        .order_by(Project.created_at.desc())
    )
    return list(rows.scalars())


@app.post("/v1/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> Task:
    await require_owned_project(session, body.project_id, principal.subject)
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
        actor_id=principal.subject,
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
async def list_tasks(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    rows = await session.execute(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Project.keycloak_subject == principal.subject)
        .order_by(Task.created_at.desc())
    )
    return list(rows.scalars())


@app.get("/v1/tasks/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> Task:
    task = await owned_task(session, task_id, principal.subject)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/v1/relationships", response_model=RelationshipRead, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    body: RelationshipCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> RelationshipRecord:
    await require_same_owner_entities(
        session,
        source_type=body.source_type,
        source_id=body.source_id,
        target_type=body.target_type,
        target_id=body.target_id,
        subject=principal.subject,
    )
    correlation_id = uuid.uuid4()
    relationship = RelationshipRecord(
        keycloak_subject=principal.subject,
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
        actor_id=principal.subject,
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
