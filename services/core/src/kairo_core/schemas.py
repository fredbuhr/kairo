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


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    bucket: str
    object_key: str
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class DeviceRegistrationCreate(BaseModel):
    device_key: str = Field(min_length=1, max_length=240)
    name: str = Field(min_length=1, max_length=240)
    platform: str = Field(min_length=1, max_length=80)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    public_key: str | None = Field(default=None, max_length=16000)


class DeviceRegistrationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    platform: str | None = Field(default=None, min_length=1, max_length=80)
    capabilities: dict[str, Any] | None = None
    public_key: str | None = Field(default=None, max_length=16000)


class DeviceRegistrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    keycloak_subject: str
    device_key: str
    name: str
    platform: str
    capabilities: dict[str, Any]
    public_key: str | None
    last_seen_at: datetime | None
    created_at: datetime


class SecretReferenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    # Authenticated deployments generate a subject-scoped OpenBao path server-side. The optional
    # field remains only for isolated auth-disabled fixtures that pre-provision deterministic paths.
    provider_path: str | None = Field(
        default=None,
        min_length=1,
        max_length=1024,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_./-]*$",
    )
    purpose: str = Field(min_length=1, max_length=320)


class SecretReferenceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    purpose: str | None = Field(default=None, min_length=1, max_length=320)


class SecretReferenceProvision(BaseModel):
    values: dict[str, str] = Field(min_length=1, max_length=32)


class SecretReferenceRead(BaseModel):
    """Public vault-handle metadata; the deployment-owned OpenBao path stays inside Core."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    purpose: str
    created_at: datetime
    updated_at: datetime


class SecretReferenceStatusRead(BaseModel):
    reference_id: uuid.UUID
    provider: Literal["openbao"] = "openbao"
    exists: bool
    keys: list[str] = Field(default_factory=list)
    version: int | None = None


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


class AssistantCommandCreate(BaseModel):
    text: str = Field(min_length=2, max_length=4000)
    conversation_id: uuid.UUID | None = None
    locale: str = Field(default="fr-FR", min_length=2, max_length=16)
    output: Literal["auto", "text", "audio", "both"] = "auto"


class SemanticRouteInput(BaseModel):
    command_id: uuid.UUID
    text: str = Field(min_length=2, max_length=4000)
    locale: str = Field(default="fr-FR", min_length=2, max_length=16)
    requested_output: Literal["auto", "text", "audio", "both"] = "auto"
    routable_capabilities: list[dict[str, Any]] = Field(min_length=1)


class SemanticRouteProposal(BaseModel):
    outcome: Literal["route", "unsupported"]
    capability: str | None = Field(default=None, max_length=120)
    confidence: float = Field(ge=0, le=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=1000)


class SemanticRouteApplyResponse(BaseModel):
    command_id: uuid.UUID
    status: str
    capability: str | None = None
    task_id: uuid.UUID | None = None
    workflow_execution_id: uuid.UUID | None = None
    workflow_id: str | None = None


class AssistantCommandResponse(BaseModel):
    command_id: uuid.UUID
    conversation_id: uuid.UUID
    status: str
    routing: Literal["deterministic", "semantic"]
    capability: str | None = None
    confidence: float | None = None
    route_reason: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    task_id: uuid.UUID | None = None
    workflow_execution_id: uuid.UUID | None = None
    workflow_id: str | None = None
    routing_task_id: uuid.UUID | None = None
    routing_workflow_execution_id: uuid.UUID | None = None
    routing_workflow_id: str | None = None


class CapabilityContractRead(BaseModel):
    key: str
    version: int
    title: str
    description: str
    authority_level: int
    cost_class: str
    runtime: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    metadata: dict[str, Any]
    enabled: bool


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_ref: str | None
    locale: str
    title: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ConversationMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    metadata_json: dict[str, Any]
    created_at: datetime


class CommandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    capability_key: str | None
    status: str
    confidence: Decimal | None
    route_reason: str | None
    parameters_json: dict[str, Any]
    result_json: dict[str, Any]
    task_id: uuid.UUID | None
    workflow_execution_id: uuid.UUID | None
    correlation_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
