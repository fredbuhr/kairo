from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from .command_models import CapabilityRecord
from .schemas import (
    NewsBriefCreate,
    NewsBriefRunResponse,
    SemanticRouteInput,
    SemanticRouteProposal,
    TaskRunResponse,
)


class ResearchRoutingInput(BaseModel):
    """Semantic routing intent only; Core injects all execution-authority fields."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=4000)
    max_tool_calls: int = Field(default=3, ge=1, le=8)


@dataclass(frozen=True)
class CapabilitySpec:
    key: str
    version: int
    title: str
    description: str
    authority_level: int
    cost_class: str
    runtime: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    metadata: dict[str, Any]

    def public_contract(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "authority_level": self.authority_level,
            "cost_class": self.cost_class,
            "runtime": self.runtime,
            "input_schema": self.input_model.model_json_schema(),
            "output_schema": self.output_model.model_json_schema(),
            "metadata": self.metadata,
            "enabled": True,
        }


NEWS_BRIEF = CapabilitySpec(
    key="news.brief",
    version=1,
    title="News Intelligence briefing",
    description=(
        "Create a sourced current-news briefing through Nevolium's durable News Intelligence workflow."
    ),
    authority_level=1,
    cost_class="metered-model",
    runtime="temporal",
    input_model=NewsBriefCreate,
    output_model=NewsBriefRunResponse,
    metadata={
        "domain": "news",
        "side_effects": "canonical-artifact",
        "model_gateway": "litellm",
        "durable": True,
        "routable": True,
        "internal": False,
    },
)

SEMANTIC_ROUTE = CapabilitySpec(
    key="assistant.route.semantic",
    version=1,
    title="Semantic capability routing",
    description=(
        "Propose one registered Nevolium capability for an ambiguous conversational command. "
        "This capability can propose a route but cannot execute specialist tools directly."
    ),
    authority_level=1,
    cost_class="metered-model",
    runtime="temporal",
    input_model=SemanticRouteInput,
    output_model=SemanticRouteProposal,
    metadata={
        "domain": "assistant",
        "side_effects": "route-proposal-only",
        "model_gateway": "litellm",
        "agent_framework": "pydantic-ai",
        "durable": True,
        "routable": False,
        "internal": True,
    },
)

AUTONOMOUS_RESEARCH = CapabilitySpec(
    key="research.autonomous",
    version=2,
    title="Autonomous read-only research",
    description=(
        "Research a question through explicitly enabled read-only A1 MCP tools. "
        "The route may choose the question and bounded tool-call depth only; Core owns project, "
        "model, budget and tool authority."
    ),
    authority_level=1,
    cost_class="metered-model-and-tools",
    runtime="temporal",
    input_model=ResearchRoutingInput,
    output_model=TaskRunResponse,
    metadata={
        "domain": "research",
        "side_effects": "read-only-child-tool-tasks",
        "model_gateway": "litellm",
        "agent_framework": "pydantic-ai",
        "tool_transport": "mcp",
        "tool_risk_ceiling": "read",
        "core_injected_execution_fields": [
            "project_id",
            "allowed_tool_keys",
            "model_alias",
            "estimated_model_cost_usd",
        ],
        "durable": True,
        "routable": True,
        "internal": False,
    },
)

CAPABILITIES: dict[str, CapabilitySpec] = {
    NEWS_BRIEF.key: NEWS_BRIEF,
    SEMANTIC_ROUTE.key: SEMANTIC_ROUTE,
    AUTONOMOUS_RESEARCH.key: AUTONOMOUS_RESEARCH,
}


def get_capability(key: str) -> CapabilitySpec | None:
    return CAPABILITIES.get(key)


def list_capabilities() -> list[CapabilitySpec]:
    return [CAPABILITIES[key] for key in sorted(CAPABILITIES)]


def list_routable_capabilities() -> list[CapabilitySpec]:
    return [spec for spec in list_capabilities() if spec.metadata.get("routable") is True]


def is_routable_capability(key: str) -> bool:
    spec = get_capability(key)
    return spec is not None and spec.metadata.get("routable") is True


async def synchronize_capabilities(session: AsyncSession) -> None:
    """Project the code-owned capability contracts into canonical PostgreSQL metadata.

    The stable capability key is Nevolium-owned. Specialist engines remain replaceable behind it.
    This synchronization never grants authority; it only keeps inspectable contract metadata current.
    """

    for spec in list_capabilities():
        input_schema = spec.input_model.model_json_schema()
        output_schema = spec.output_model.model_json_schema()
        record = await session.get(CapabilityRecord, spec.key)
        if record is None:
            session.add(
                CapabilityRecord(
                    key=spec.key,
                    version=spec.version,
                    title=spec.title,
                    description=spec.description,
                    authority_level=spec.authority_level,
                    cost_class=spec.cost_class,
                    runtime=spec.runtime,
                    input_schema=input_schema,
                    output_schema=output_schema,
                    metadata_json=spec.metadata,
                    enabled=True,
                )
            )
            continue

        record.version = spec.version
        record.title = spec.title
        record.description = spec.description
        record.authority_level = spec.authority_level
        record.cost_class = spec.cost_class
        record.runtime = spec.runtime
        record.input_schema = input_schema
        record.output_schema = output_schema
        record.metadata_json = spec.metadata
        record.enabled = True
