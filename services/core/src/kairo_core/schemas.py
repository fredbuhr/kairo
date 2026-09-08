import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    status: str = Field(default="active", max_length=32)
    summary: str | None = None
    parent_id: uuid.UUID | None = None


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=320)
    description: str | None = None
    owner_type: str = Field(default="user", max_length=32)
    owner_ref: str | None = None
    authority_ceiling: int = Field(default=1, ge=0, le=5)
    budget_usd: Decimal | None = Field(default=None, ge=0)
    input: dict[str, Any] = Field(default_factory=dict)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    status: str
    owner_type: str
    owner_ref: str | None
    authority_ceiling: int
    budget_usd: Decimal | None
    input: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RelationshipCreate(BaseModel):
    source_type: str = Field(min_length=1, max_length=64)
    source_id: uuid.UUID
    relation_type: str = Field(min_length=1, max_length=96)
    target_type: str = Field(min_length=1, max_length=64)
    target_id: uuid.UUID
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    relation_type: str
    target_type: str
    target_id: uuid.UUID
    metadata_json: dict[str, Any]
    created_at: datetime


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    workflow_execution_id: uuid.UUID | None
    kind: str
    title: str
    content: dict[str, Any]
    created_at: datetime


class TaskRunResponse(BaseModel):
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID
    workflow_id: str
    status: str
    already_started: bool = False


class NewsBriefCreate(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    mode: Literal["general", "local", "market_impact"] = "general"
    location: str | None = Field(default=None, max_length=160)
    language: str = Field(default="fr", min_length=2, max_length=16)
    time_range: Literal["day", "week", "month"] = "day"
    max_sources: int = Field(default=10, ge=3, le=20)
    output: Literal["text", "audio", "both"] = "text"
    voice: str = Field(default="ff_siwis", min_length=2, max_length=120)


class NewsBriefRunResponse(BaseModel):
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID
    workflow_id: str
    status: str
    query: str
    mode: str
    output: str


class NewsBriefRead(BaseModel):
    task_id: uuid.UUID
    status: str
    query: str
    mode: str
    output: str
    voice: str
    artifact: ArtifactRead | None = None
    audio_available: bool = False


class AssistantCommandCreate(BaseModel):
    text: str = Field(min_length=2, max_length=1000)
    locale: str = Field(default="fr-FR", min_length=2, max_length=24)
    output: Literal["auto", "text", "audio", "both"] = "auto"


class AssistantCommandResponse(BaseModel):
    capability: str
    confidence: float = Field(ge=0, le=1)
    parameters: dict[str, Any]
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID
    workflow_id: str
    status: str


class InternalStartResponse(BaseModel):
    task_id: uuid.UUID
    task_title: str
    task_input: dict[str, Any]
    execution_status: str


class InternalCompleteRequest(BaseModel):
    kind: str = Field(default="task-result", max_length=80)
    title: str = Field(min_length=1, max_length=320)
    content: dict[str, Any] = Field(default_factory=dict)


class InternalCompleteResponse(BaseModel):
    execution_status: str
    artifact: ArtifactRead


class InternalFailRequest(BaseModel):
    error: str = Field(min_length=1, max_length=4000)


class SystemReadiness(BaseModel):
    status: str
    checks: dict[str, bool]


class OutboxStats(BaseModel):
    pending: int
    published: int
    relay_connected: bool
