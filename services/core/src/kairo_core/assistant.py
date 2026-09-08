import unicodedata
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .news import create_news_brief
from .schemas import (
    AssistantCommandCreate,
    AssistantCommandResponse,
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
)
_MARKET_IMPACT_TERMS = (
    "impact",
    "impacter",
    "influencer",
    "bouger",
    "risque",
    "risquent",
    "affecter",
)
_LOCAL_TERMS = (
    "actualite locale",
    "actualites locales",
    "nouvelles locales",
    "ville de",
    "ma ville",
    "localement",
)
_AUDIO_TERMS = (
    "a voix haute",
    "audio",
    "oralement",
    "resume-moi oralement",
    "lis-moi",
    "lire le resume",
    "lecture audio",
)


@dataclass(frozen=True)
class CommandRoute:
    capability: str
    confidence: float
    news_mode: Literal["general", "local", "market_impact"]
    time_range: Literal["day", "week", "month"]
    output: Literal["text", "audio", "both"]


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def route_command(body: AssistantCommandCreate) -> CommandRoute | None:
    """Route high-confidence intents without spending a model call.

    This deterministic front door is intentionally conservative. A later agentic router can handle
    ambiguous commands, but known KAIRO capabilities should remain fast, cheap and testable.
    """

    text = _normalize(body.text)
    has_news = any(term in text for term in _NEWS_TERMS)
    has_market = any(term in text for term in _MARKET_TERMS)
    asks_market_impact = has_market and any(term in text for term in _MARKET_IMPACT_TERMS)

    # Market-impact questions are news intents even when the user omits the literal word "news".
    if not has_news and not asks_market_impact:
        return None

    if asks_market_impact or (has_news and has_market):
        news_mode: Literal["general", "local", "market_impact"] = "market_impact"
        confidence = 0.99
    elif any(term in text for term in _LOCAL_TERMS):
        news_mode = "local"
        confidence = 0.98
    else:
        news_mode = "general"
        confidence = 0.97

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

    return CommandRoute(
        capability="news.brief",
        confidence=confidence,
        news_mode=news_mode,
        time_range=time_range,
        output=output,
    )


@router.post("/v1/assistant/commands", response_model=AssistantCommandResponse)
async def assistant_command(
    body: AssistantCommandCreate,
    session: AsyncSession = Depends(get_session),
) -> AssistantCommandResponse:
    route = route_command(body)
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "No deterministic KAIRO capability matched this command yet",
                "text": body.text,
            },
        )

    language = body.locale.split("-", 1)[0].lower() or "fr"
    news_request = NewsBriefCreate(
        query=body.text,
        mode=route.news_mode,
        language=language,
        time_range=route.time_range,
        max_sources=10,
        output=route.output,
    )
    execution = await create_news_brief(news_request, session)
    return AssistantCommandResponse(
        capability=route.capability,
        confidence=route.confidence,
        parameters=news_request.model_dump(mode="json"),
        task_id=execution.task_id,
        workflow_execution_id=execution.workflow_execution_id,
        workflow_id=execution.workflow_id,
        status=execution.status,
    )
