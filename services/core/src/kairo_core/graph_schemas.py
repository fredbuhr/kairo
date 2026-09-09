from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


GraphProjectionMode = Literal["home", "neighborhood"]
GraphEdgeProvenance = Literal["canonical_relationship", "canonical_fk"]
GraphUIDirectiveKind = Literal["focus_entity", "isolate_entity"]
GraphUIDirectiveOutcome = Literal["directive", "not_navigation", "ambiguous", "not_found"]


class GraphEntityRef(BaseModel):
    entity_type: str = Field(min_length=1, max_length=64)
    entity_id: uuid.UUID

    @property
    def key(self) -> str:
        return f"{self.entity_type}:{self.entity_id}"


class GraphNodeRead(BaseModel):
    id: uuid.UUID
    entity_type: str
    label: str
    subtitle: str | None = None
    project_id: uuid.UUID | None = None
    status: str | None = None
    importance: float = Field(ge=0, le=1)
    activity: float = Field(ge=0, le=1)
    recency: float = Field(ge=0, le=1)
    relationship_count: int = Field(default=0, ge=0)
    cluster_hint: str | None = None
    lod: int = Field(default=2, ge=0, le=3)
    provenance: Literal["canonical"] = "canonical"
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None

    @property
    def key(self) -> str:
        return f"{self.entity_type}:{self.id}"


class GraphEdgeRead(BaseModel):
    id: str
    source: GraphEntityRef
    target: GraphEntityRef
    relation: str
    directed: bool = True
    strength: float = Field(default=0.6, ge=0, le=1)
    provenance: GraphEdgeProvenance
    explanation: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphProjectionContext(BaseModel):
    mode: GraphProjectionMode
    focus: GraphEntityRef | None = None
    depth: int = Field(default=0, ge=0, le=3)
    requested_limit: int = Field(ge=1, le=200)


class GraphProjectionRead(BaseModel):
    context: GraphProjectionContext
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]
    truncated: bool = False
    generated_at: datetime


class GraphSearchRead(BaseModel):
    query: str
    nodes: list[GraphNodeRead]


class GraphActivityEventRead(BaseModel):
    id: uuid.UUID
    event_type: str = Field(min_length=1, max_length=160)
    entity: GraphEntityRef
    related: list[GraphEntityRef] = Field(default_factory=list)
    correlation_id: uuid.UUID
    occurred_at: datetime


class GraphUIDirectiveResolveRequest(BaseModel):
    text: str = Field(min_length=2, max_length=1000)


class GraphUIDirectiveRead(BaseModel):
    kind: GraphUIDirectiveKind
    entity: GraphEntityRef
    label: str = Field(min_length=1, max_length=320)
    depth: int = Field(default=1, ge=1, le=2)
    reason: str = Field(min_length=1, max_length=160)


class GraphUIDirectiveResolveRead(BaseModel):
    outcome: GraphUIDirectiveOutcome
    query: str = ""
    directive: GraphUIDirectiveRead | None = None
    candidates: list[GraphNodeRead] = Field(default_factory=list)
