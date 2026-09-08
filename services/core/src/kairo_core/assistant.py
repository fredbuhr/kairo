from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .capabilities import get_capability, list_capabilities, synchronize_capabilities
from .command_models import CommandRecord, Conversation, ConversationMessage
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .news import start_news_brief
from .schemas import (
    AssistantCommandCreate,
    AssistantCommandResponse,
    CapabilityContractRead,
    CommandRead,
    ConversationMessageRead,
    ConversationRead,
    NewsBriefCreate,
)

router = APIRouter()

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
    """Route deterministic high-confidence intents without spending a model call.

    Semantic routing will be added later as a second tier. Known KAIRO intents stay cheap,
    inspectable and regression-testable, and ambiguous commands fail conservatively.
    """

    text = _normalize(body.text)
    has_news = any(term in text for term in _NEWS_TERMS)
    has_market = any(term in text for term in _MARKET_TERMS)
    asks_market_impact = has_market and any(term in text for term in _MARKET_IMPACT_TERMS)

    # A market-impact request is a News Intelligence intent even if the word "news" is omitted.
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
    body: AssistantCommandCreate, session: AsyncSession
) -> Conversation:
    if body.conversation_id is not None:
        conversation = await session.get(Conversation, body.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.status != "active":
            raise HTTPException(status_code=409, detail="Conversation is not active")
        return conversation

    title = re.sub(r"\s+", " ", body.text).strip()[:120]
    conversation = Conversation(locale=body.locale, title=title or None, status="active")
    session.add(conversation)
    await session.flush()
    return conversation


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
    session: AsyncSession = Depends(get_session),
) -> AssistantCommandResponse:
    await synchronize_capabilities(session)
    conversation = await _conversation_for_command(body, session)
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
        command.status = "unsupported"
        command.route_reason = "no_deterministic_capability_match"
        await enqueue_domain_event(
            session,
            event_type="command.unsupported",
            aggregate_type="command",
            aggregate_id=command.id,
            correlation_id=correlation_id,
            payload={
                "command_id": str(command.id),
                "conversation_id": str(conversation.id),
                "text": body.text,
            },
        )
        await append_audit(
            session,
            actor_type="user",
            actor_id=conversation.subject_ref,
            action="command.route.unsupported",
            resource_type="command",
            resource_id=str(command.id),
            authority_level=0,
            correlation_id=correlation_id,
            request_json=body.model_dump(mode="json"),
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "No deterministic KAIRO capability matched this command yet",
                "command_id": str(command.id),
                "conversation_id": str(conversation.id),
            },
        )

    capability = get_capability(route.capability)
    if capability is None:
        # This should be unreachable because the deterministic router only emits registered keys.
        command.status = "failed"
        command.route_reason = "capability_registry_miss"
        await session.commit()
        raise HTTPException(status_code=503, detail="Routed capability is not registered")

    command.capability_key = capability.key
    command.confidence = Decimal(str(route.confidence))
    command.route_reason = route.route_reason
    command.parameters_json = route.parameters
    command.status = "accepted"

    if capability.key != "news.brief":
        command.status = "failed"
        await session.commit()
        raise HTTPException(status_code=501, detail="Capability adapter is not implemented")

    news_request = NewsBriefCreate.model_validate(route.parameters)
    execution = await start_news_brief(
        news_request,
        session,
        actor_type="user",
        actor_id=conversation.subject_ref,
        correlation_id=correlation_id,
        command_id=command.id,
    )

    command.task_id = execution.task_id
    command.workflow_execution_id = execution.workflow_execution_id
    command.result_json = {
        "workflow_id": execution.workflow_id,
        "status": execution.status,
    }
    await enqueue_domain_event(
        session,
        event_type="command.routed",
        aggregate_type="command",
        aggregate_id=command.id,
        correlation_id=correlation_id,
        payload={
            "command_id": str(command.id),
            "conversation_id": str(conversation.id),
            "capability": capability.key,
            "confidence": route.confidence,
            "task_id": str(execution.task_id),
            "workflow_execution_id": str(execution.workflow_execution_id),
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=conversation.subject_ref,
        action="command.route",
        resource_type="command",
        resource_id=str(command.id),
        authority_level=capability.authority_level,
        correlation_id=correlation_id,
        request_json=body.model_dump(mode="json"),
        result_json={
            "capability": capability.key,
            "confidence": route.confidence,
            "route_reason": route.route_reason,
            "task_id": str(execution.task_id),
        },
    )
    await session.commit()

    return AssistantCommandResponse(
        command_id=command.id,
        conversation_id=conversation.id,
        capability=capability.key,
        confidence=route.confidence,
        route_reason=route.route_reason,
        parameters=route.parameters,
        task_id=execution.task_id,
        workflow_execution_id=execution.workflow_execution_id,
        workflow_id=execution.workflow_id,
        status=execution.status,
    )


@router.get("/v1/conversations/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Conversation:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get(
    "/v1/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessageRead],
)
async def get_conversation_messages(
    conversation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[ConversationMessage]:
    if await session.get(Conversation, conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at, ConversationMessage.id)
    )
    return list(result.scalars())


@router.get("/v1/commands/{command_id}", response_model=CommandRead)
async def get_command(
    command_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> CommandRecord:
    command = await session.get(CommandRecord, command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="Command not found")
    return command
