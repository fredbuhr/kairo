from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .capabilities import (
    get_capability,
    is_routable_capability,
    list_capabilities,
    list_routable_capabilities,
    synchronize_capabilities,
)
from .command_models import CommandRecord, Conversation, ConversationMessage
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import Project, Task
from .news import start_news_brief
from .ownership import DEVELOPMENT_SUBJECT, ensure_system_project
from .research import ResearchCommandInput, ResearchRunCreate, start_research_run
from .schemas import (
    AssistantCommandCreate,
    AssistantCommandResponse,
    CapabilityContractRead,
    CommandRead,
    ConversationMessageRead,
    ConversationRead,
    NewsBriefCreate,
    SemanticRouteApplyResponse,
    SemanticRouteInput,
    SemanticRouteProposal,
)
from .security import require_internal_token
from .workflows import reconcile_command_task_projection, run_task

router = APIRouter()

ASSISTANT_PROJECT_ID = uuid.UUID("91d51873-3aa5-4fbc-a6df-cf474239682f")
SEMANTIC_ROUTE_BUDGET_USD = Decimal("0.02")
SEMANTIC_ROUTE_CONFIDENCE_FLOOR = 0.80
RESEARCH_COMMAND_MODEL_BUDGET_USD = Decimal("0.02")
RESEARCH_COMMAND_MODEL_ALIAS = "local-fast"

_NEWS_TERMS = (
    "actualite",
    "actualites",
    "journal",
    "journaux",
    "news",
    "nouvelle",
    "nouvelles",
    "presse",
    "headline",
    "headlines",
)
_MARKET_TERMS = (
    "bourse",
    "marche",
    "marches",
    "action",
    "actions",
    "cac 40",
    "cac40",
    "nasdaq",
    "s&p",
    "sp500",
    "portefeuille",
    "crypto",
    "bitcoin",
    "ethereum",
    "inflation",
    "taux",
    "banque centrale",
    "bce",
    "fed",
    "stock market",
    "stocks",
    "markets",
)
_MARKET_IMPACT_TERMS = (
    "impact",
    "impacter",
    "influencer",
    "bouger",
    "risque",
    "risquent",
    "affecter",
    "affect",
    "move",
    "moving",
)
_LOCAL_TERMS = (
    "actualite locale",
    "actualites locales",
    "nouvelles locales",
    "ville de",
    "ville d'",
    "ville d’",
    "ma ville",
    "localement",
    "local news",
)
_AUDIO_TERMS = (
    "a voix haute",
    "audio",
    "oralement",
    "resume-moi oralement",
    "lis-moi",
    "lire le resume",
    "lecture audio",
    "read it to me",
    "read me",
    "speak",
)
_RESEARCH_TERMS = (
    "fais une recherche",
    "faire une recherche",
    "recherche approfondie",
    "recherche detaillee",
    "analyse approfondie",
    "enquete sur",
    "cherche et compare",
    "cherche puis compare",
    "recoupe les sources",
    "recouper les sources",
    "research this",
    "deep dive",
    "investigate",
)
_DEEP_RESEARCH_TERMS = (
    "recherche approfondie",
    "recherche detaillee",
    "analyse approfondie",
    "recoupe les sources",
    "recouper les sources",
    "deep dive",
)
_CITY_PATTERN = re.compile(
    r"\bville\s+d(?:e|['’])\s+([^?!,.;:]{2,80})",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class CommandRoute:
    capability: str
    confidence: float
    route_reason: str
    parameters: dict[str, object]


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def _extract_location(value: str) -> str | None:
    match = _CITY_PATTERN.search(value)
    if match is None:
        return None
    location = re.sub(r"\s+", " ", match.group(1)).strip(" -'’")
    return location[:160] or None


def route_command(body: AssistantCommandCreate) -> CommandRoute | None:
    """Route known high-confidence intents without spending a model call."""

    text = _normalize(body.text)
    has_news = any(term in text for term in _NEWS_TERMS)
    has_market = any(term in text for term in _MARKET_TERMS)
    asks_market_impact = has_market and any(term in text for term in _MARKET_IMPACT_TERMS)
    asks_research = any(term in text for term in _RESEARCH_TERMS)

    # Explicit news/market commands retain priority. A phrase such as "recherche les news" must not
    # silently switch from the sourced News capability to the generic MCP research planner.
    if asks_research and not has_news and not asks_market_impact:
        max_tool_calls = 5 if any(term in text for term in _DEEP_RESEARCH_TERMS) else 3
        request = ResearchCommandInput(query=body.text, max_tool_calls=max_tool_calls)
        return CommandRoute(
            capability="research.autonomous",
            confidence=0.98,
            route_reason="deterministic.research",
            parameters=request.model_dump(mode="json"),
        )

    if not has_news and not asks_market_impact:
        return None

    location = _extract_location(body.text)
    if asks_market_impact or (has_news and has_market):
        news_mode: Literal["general", "local", "market_impact"] = "market_impact"
        confidence = 0.99
        route_reason = "deterministic.market-impact"
        location = None
    elif location is not None or any(term in text for term in _LOCAL_TERMS):
        news_mode = "local"
        confidence = 0.98
        route_reason = "deterministic.local-news"
    else:
        news_mode = "general"
        confidence = 0.97
        route_reason = "deterministic.news"

    if "semaine" in text or "week" in text:
        time_range: Literal["day", "week", "month"] = "week"
    elif "mois" in text or "month" in text:
        time_range = "month"
    else:
        time_range = "day"

    if body.output == "auto":
        output: Literal["text", "audio", "both"] = (
            "both" if any(term in text for term in _AUDIO_TERMS) else "text"
        )
    else:
        output = body.output

    language = body.locale.split("-", 1)[0].lower() or "fr"
    news_request = NewsBriefCreate(
        query=body.text,
        mode=news_mode,
        location=location,
        language=language,
        time_range=time_range,
        max_sources=10,
        output=output,
    )
    return CommandRoute(
        capability="news.brief",
        confidence=confidence,
        route_reason=route_reason,
        parameters=news_request.model_dump(mode="json"),
    )


async def _conversation_for_command(
    body: AssistantCommandCreate,
    session: AsyncSession,
    subject: str,
) -> Conversation:
    if body.conversation_id is not None:
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.id == body.conversation_id,
                Conversation.subject_ref == subject,
            )
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.status != "active":
            raise HTTPException(status_code=409, detail="Conversation is not active")
        return conversation

    title = re.sub(r"\s+", " ", body.text).strip()[:120]
    conversation = Conversation(
        subject_ref=subject,
        locale=body.locale,
        title=title or None,
        status="active",
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def _ensure_assistant_project(session: AsyncSession, subject: str) -> Project:
    project, created = await ensure_system_project(
        session,
        subject=subject,
        key="assistant",
        name="KAIRO Assistant",
        summary="Per-user system workspace for durable command routing and assistant orchestration.",
        legacy_development_id=ASSISTANT_PROJECT_ID,
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
            actor_id="command-kernel",
            action="project.create",
            resource_type="project",
            resource_id=str(project.id),
            authority_level=0,
            correlation_id=correlation_id,
            request_json={"reason": "initialize owner-scoped assistant routing workspace", "subject": subject},
        )
    return project


def _routable_contracts() -> list[dict[str, object]]:
    return [
        {
            "key": spec.key,
            "version": spec.version,
            "title": spec.title,
            "description": spec.description,
            "input_schema": spec.input_model.model_json_schema(),
        }
        for spec in list_routable_capabilities()
    ]


async def _start_semantic_route(
    command: CommandRecord,
    body: AssistantCommandCreate,
    conversation: Conversation,
    session: AsyncSession,
) -> AssistantCommandResponse:
    subject = conversation.subject_ref or DEVELOPMENT_SUBJECT
    project = await _ensure_assistant_project(session, subject)
    route_input = SemanticRouteInput(
        command_id=command.id,
        text=body.text,
        locale=body.locale,
        requested_output=body.output,
        routable_capabilities=_routable_contracts(),
    )
    routing_task_id = uuid.uuid5(uuid.NAMESPACE_URL, f"kairo:semantic-route:{command.id}:v1")
    task = await session.get(Task, routing_task_id)
    if task is None:
        task = Task(
            id=routing_task_id,
            project_id=project.id,
            title=f"Route command — {body.text}"[:320],
            description="PydanticAI semantic proposal constrained to registered KAIRO capabilities.",
            status="todo",
            owner_type="system",
            owner_ref="command-kernel",
            authority_ceiling=1,
            budget_usd=SEMANTIC_ROUTE_BUDGET_USD,
            input={
                "capability": "assistant.route.semantic",
                **route_input.model_dump(mode="json"),
            },
        )
        session.add(task)
        await session.flush()
        await enqueue_domain_event(
            session,
            event_type="command.semantic_route.requested",
            aggregate_type="command",
            aggregate_id=command.id,
            correlation_id=command.correlation_id,
            payload={
                "command_id": str(command.id),
                "routing_task_id": str(task.id),
                "routable_capabilities": [item["key"] for item in route_input.routable_capabilities],
            },
        )
        await append_audit(
            session,
            actor_type="system",
            actor_id="command-kernel",
            action="command.semantic_route.request",
            resource_type="command",
            resource_id=str(command.id),
            authority_level=1,
            correlation_id=command.correlation_id,
            request_json={
                "routing_task_id": str(task.id),
                "budget_usd": str(SEMANTIC_ROUTE_BUDGET_USD),
            },
        )
    command.status = "routing"
    command.route_reason = "semantic.pending"
    command.result_json = {"routing_task_id": str(routing_task_id)}
    await session.commit()

    execution = await run_task(routing_task_id, session)
    command = await session.get(CommandRecord, command.id)
    if command is not None:
        command.result_json = {
            **(command.result_json or {}),
            "routing_workflow_execution_id": str(execution.workflow_execution_id),
            "routing_workflow_id": execution.workflow_id,
            "routing_status": execution.status,
        }
        await session.commit()

    return AssistantCommandResponse(
        command_id=route_input.command_id,
        conversation_id=conversation.id,
        status="routing",
        routing="semantic",
        route_reason="semantic.pending",
        routing_task_id=routing_task_id,
        routing_workflow_execution_id=execution.workflow_execution_id,
        routing_workflow_id=execution.workflow_id,
    )


async def _mark_semantic_unsupported(
    command: CommandRecord,
    proposal: SemanticRouteProposal,
    reason: str,
    session: AsyncSession,
) -> SemanticRouteApplyResponse:
    if command.status == "unsupported":
        return SemanticRouteApplyResponse(command_id=command.id, status="unsupported")
    command.status = "unsupported"
    command.capability_key = None
    command.confidence = Decimal(str(proposal.confidence))
    command.route_reason = reason
    command.parameters_json = proposal.parameters
    command.result_json = {
        **(command.result_json or {}),
        "semantic_rationale": proposal.rationale,
        "semantic_outcome": proposal.outcome,
    }
    await enqueue_domain_event(
        session,
        event_type="command.unsupported",
        aggregate_type="command",
        aggregate_id=command.id,
        correlation_id=command.correlation_id,
        payload={"command_id": str(command.id), "route_reason": reason},
    )
    await append_audit(
        session,
        actor_type="worker",
        actor_id="semantic-router",
        action="command.semantic_route.unsupported",
        resource_type="command",
        resource_id=str(command.id),
        authority_level=1,
        correlation_id=command.correlation_id,
        idempotency_key=f"command:{command.id}:semantic-unsupported",
        result_json={"reason": reason, "confidence": proposal.confidence},
    )
    await session.commit()
    return SemanticRouteApplyResponse(command_id=command.id, status="unsupported")


async def _execute_route(
    command: CommandRecord,
    conversation: Conversation,
    route: CommandRoute,
    session: AsyncSession,
    *,
    semantic: bool,
) -> tuple[str, uuid.UUID, uuid.UUID, str]:
    capability = get_capability(route.capability)
    if capability is None or not is_routable_capability(route.capability):
        raise HTTPException(status_code=422, detail="Capability is not routable")

    deterministic_task_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"kairo:command:{command.id}:{capability.key}:v{capability.version}",
    )

    if capability.key == "news.brief":
        news_request = NewsBriefCreate.model_validate(route.parameters)
        execution = await start_news_brief(
            news_request,
            session,
            actor_type="user",
            actor_id=conversation.subject_ref,
            correlation_id=command.correlation_id,
            command_id=command.id,
            task_id=deterministic_task_id if semantic else None,
        )
    elif capability.key == "research.autonomous":
        routed = ResearchCommandInput.model_validate(route.parameters)
        project = await _ensure_assistant_project(
            session, conversation.subject_ref or DEVELOPMENT_SUBJECT
        )
        research_request = ResearchRunCreate(
            project_id=project.id,
            query=routed.query,
            max_tool_calls=routed.max_tool_calls,
            allowed_tool_keys=[],
            model_alias=RESEARCH_COMMAND_MODEL_ALIAS,
            estimated_model_cost_usd=RESEARCH_COMMAND_MODEL_BUDGET_USD,
        )
        execution = await start_research_run(
            research_request,
            session,
            actor_type="worker" if semantic else "user",
            actor_id="semantic-router" if semantic else conversation.subject_ref,
            correlation_id=command.correlation_id,
            command_id=command.id,
            task_id=deterministic_task_id,
        )
    else:
        raise HTTPException(status_code=501, detail="Capability adapter is not implemented")

    command = await session.get(CommandRecord, command.id)
    if command is None:
        raise HTTPException(status_code=404, detail="Command disappeared during routing")
    command.capability_key = capability.key
    command.confidence = Decimal(str(route.confidence))
    command.route_reason = route.route_reason
    # Persist only the route-owned contract. Core-injected project/model/budget/tool-policy fields live
    # on the final Task and are never represented as if they were model/user routing parameters.
    command.parameters_json = route.parameters
    command.status = "accepted"
    command.task_id = execution.task_id
    command.workflow_execution_id = execution.workflow_execution_id
    command.result_json = {
        **(command.result_json or {}),
        "workflow_id": execution.workflow_id,
        "status": execution.status,
    }

    # A very fast Worker can finish after Temporal start but before the Command binding above is
    # committed. The completion endpoint cannot safely project an assistant result until task_id is
    # authoritative. Reconcile now; if the Task is still non-terminal this is a no-op and the normal
    # Worker completion/failure path will project later.
    await reconcile_command_task_projection(
        session,
        command_id=command.id,
        task_id=execution.task_id,
    )

    await enqueue_domain_event(
        session,
        event_type="command.routed",
        aggregate_type="command",
        aggregate_id=command.id,
        correlation_id=command.correlation_id,
        payload={
            "command_id": str(command.id),
            "conversation_id": str(conversation.id),
            "capability": capability.key,
            "confidence": route.confidence,
            "routing": "semantic" if semantic else "deterministic",
            "task_id": str(execution.task_id),
            "workflow_execution_id": str(execution.workflow_execution_id),
        },
    )
    await append_audit(
        session,
        actor_type="worker" if semantic else "user",
        actor_id="semantic-router" if semantic else conversation.subject_ref,
        action="command.route",
        resource_type="command",
        resource_id=str(command.id),
        authority_level=capability.authority_level,
        correlation_id=command.correlation_id,
        idempotency_key=(f"command:{command.id}:semantic-route" if semantic else None),
        result_json={
            "capability": capability.key,
            "confidence": route.confidence,
            "route_reason": route.route_reason,
            "task_id": str(execution.task_id),
        },
    )
    await session.commit()
    return capability.key, execution.task_id, execution.workflow_execution_id, execution.workflow_id


@router.get("/v1/capabilities", response_model=list[CapabilityContractRead])
async def capability_contracts() -> list[CapabilityContractRead]:
    return [CapabilityContractRead(**spec.public_contract()) for spec in list_capabilities()]


@router.post(
    "/v1/assistant/commands",
    response_model=AssistantCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def assistant_command(
    body: AssistantCommandCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> AssistantCommandResponse:
    await synchronize_capabilities(session)
    conversation = await _conversation_for_command(body, session, principal.subject)
    correlation_id = uuid.uuid4()

    message = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        content=body.text,
        metadata_json={"locale": body.locale, "requested_output": body.output},
    )
    session.add(message)
    await session.flush()

    route = route_command(body)
    command = CommandRecord(
        conversation_id=conversation.id,
        message_id=message.id,
        status="routing",
        correlation_id=correlation_id,
    )
    session.add(command)
    await session.flush()

    if route is None:
        return await _start_semantic_route(command, body, conversation, session)

    capability_key, task_id, execution_id, workflow_id = await _execute_route(
        command, conversation, route, session, semantic=False
    )
    return AssistantCommandResponse(
        command_id=command.id,
        conversation_id=conversation.id,
        status="accepted",
        routing="deterministic",
        capability=capability_key,
        confidence=route.confidence,
        route_reason=route.route_reason,
        parameters=route.parameters,
        task_id=task_id,
        workflow_execution_id=execution_id,
        workflow_id=workflow_id,
    )


@router.post(
    "/internal/v1/assistant/commands/{command_id}/semantic-route",
    response_model=SemanticRouteApplyResponse,
    dependencies=[Depends(require_internal_token)],
)
async def apply_semantic_route(
    command_id: uuid.UUID,
    proposal: SemanticRouteProposal,
    session: AsyncSession = Depends(get_session),
) -> SemanticRouteApplyResponse:
    command = await session.scalar(
        select(CommandRecord).where(CommandRecord.id == command_id).with_for_update()
    )
    if command is None:
        raise HTTPException(status_code=404, detail="Command not found")
    if command.status == "accepted" and command.task_id is not None:
        return SemanticRouteApplyResponse(
            command_id=command.id,
            status="accepted",
            capability=command.capability_key,
            task_id=command.task_id,
            workflow_execution_id=command.workflow_execution_id,
            workflow_id=str((command.result_json or {}).get("workflow_id") or "") or None,
        )
    if command.status == "unsupported":
        return SemanticRouteApplyResponse(command_id=command.id, status="unsupported")
    if command.status != "routing":
        raise HTTPException(status_code=409, detail="Command is not awaiting semantic routing")

    if proposal.outcome != "route":
        return await _mark_semantic_unsupported(command, proposal, "semantic.unsupported", session)
    if proposal.confidence < SEMANTIC_ROUTE_CONFIDENCE_FLOOR:
        return await _mark_semantic_unsupported(command, proposal, "semantic.low-confidence", session)
    if proposal.capability is None or not is_routable_capability(proposal.capability):
        return await _mark_semantic_unsupported(command, proposal, "semantic.invalid-capability", session)

    capability = get_capability(proposal.capability)
    assert capability is not None
    try:
        validated = capability.input_model.model_validate(proposal.parameters)
    except ValidationError:
        return await _mark_semantic_unsupported(command, proposal, "semantic.invalid-parameters", session)

    conversation = await session.get(Conversation, command.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    route = CommandRoute(
        capability=proposal.capability,
        confidence=proposal.confidence,
        route_reason="semantic.model",
        parameters=validated.model_dump(mode="json"),
    )
    capability_key, task_id, execution_id, workflow_id = await _execute_route(
        command, conversation, route, session, semantic=True
    )
    return SemanticRouteApplyResponse(
        command_id=command.id,
        status="accepted",
        capability=capability_key,
        task_id=task_id,
        workflow_execution_id=execution_id,
        workflow_id=workflow_id,
    )


@router.get("/v1/conversations/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> Conversation:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.subject_ref == principal.subject,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get(
    "/v1/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessageRead],
)
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[ConversationMessage]:
    conversation = await session.scalar(
        select(Conversation.id).where(
            Conversation.id == conversation_id,
            Conversation.subject_ref == principal.subject,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at, ConversationMessage.id)
    )
    return list(result.scalars())


@router.get("/v1/commands/{command_id}", response_model=CommandRead)
async def get_command(
    command_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> CommandRecord:
    command = await session.scalar(
        select(CommandRecord)
        .join(Conversation, Conversation.id == CommandRecord.conversation_id)
        .where(
            CommandRecord.id == command_id,
            Conversation.subject_ref == principal.subject,
        )
    )
    if command is None:
        raise HTTPException(status_code=404, detail="Command not found")
    return command
