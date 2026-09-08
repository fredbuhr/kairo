from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .command_models import CapabilityRecord
from .schemas import NewsBriefCreate, NewsBriefRunResponse


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
        "Create a sourced current-news briefing through KAIRO's durable News Intelligence workflow."
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
    },
)

CAPABILITIES: dict[str, CapabilitySpec] = {NEWS_BRIEF.key: NEWS_BRIEF}


def get_capability(key: str) -> CapabilitySpec | None:
    return CAPABILITIES.get(key)


def list_capabilities() -> list[CapabilitySpec]:
    return [CAPABILITIES[key] for key in sorted(CAPABILITIES)]


async def synchronize_capabilities(session: AsyncSession) -> None:
    """Project the code-owned capability contracts into canonical PostgreSQL metadata.

    The stable capability key is KAIRO-owned. Specialist engines remain replaceable behind it.
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
