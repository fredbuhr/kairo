from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_nevolium_user
from .db import get_session
from .models import Artifact, Task, WorkflowExecution

router = APIRouter()

Confidence = Literal["low", "medium", "high", "unknown"]
EvidenceSourceType = Literal["tool", "document", "memory", "unknown"]


class ResearchClaimRead(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence = "unknown"


class ResearchSynthesisRead(BaseModel):
    answer: str
    claims: list[ResearchClaimRead] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class ResearchEvidenceRead(BaseModel):
    evidence_id: str
    source_type: EvidenceSourceType = "unknown"
    source: str = "unknown"
    authority: str = "unknown"
    slot: int | None = None
    tool_key: str | None = None
    invocation_id: uuid.UUID | None = None
    title: str | None = None
    excerpt: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class ResearchToolInvocationRead(BaseModel):
    slot: int
    tool_key: str
    invocation_id: uuid.UUID
    input: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class ResearchRunRead(BaseModel):
    task_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    execution_status: str | None = None
    query: str
    answer: str | None = None
    synthesis: ResearchSynthesisRead | None = None
    evidence: list[ResearchEvidenceRead] = Field(default_factory=list)
    context_pack: dict[str, Any] = Field(default_factory=dict)
    tool_invocations: list[ResearchToolInvocationRead] = Field(default_factory=list)
    tool_call_count: int = 0
    planner_model_alias: str | None = None
    synthesis_model_alias: str | None = None
    model_budget_usd: Decimal | None = None
    artifact_id: uuid.UUID | None = None
    workflow_execution_id: uuid.UUID | None = None
    workflow_id: str | None = None
    correlation_id: uuid.UUID | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    artifact_created_at: datetime | None = None


def _research_input(task: Task) -> dict[str, Any]:
    value = task.input or {}
    if str(value.get("capability") or "") != "research.autonomous":
        raise HTTPException(status_code=409, detail="Task is not an autonomous research task")
    return value


def _require_research_owner(task_input: dict[str, Any], principal: Principal) -> None:
    requester_subject = str(task_input.get("requester_subject") or "").strip()
    if not requester_subject or requester_subject != principal.subject:
        # Missing and foreign ownership deliberately have the same surface.
        raise HTTPException(status_code=404, detail="Research run not found")


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _slot(value: Any, fallback: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return fallback


def _tool_invocations(content: dict[str, Any]) -> list[ResearchToolInvocationRead]:
    raw = content.get("tool_results")
    if not isinstance(raw, list):
        return []

    rows: list[ResearchToolInvocationRead] = []
    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        invocation_id = _uuid_or_none(item.get("invocation_id"))
        if invocation_id is None:
            continue
        rationale = str(item.get("rationale") or "").strip() or None
        rows.append(
            ResearchToolInvocationRead(
                slot=_slot(item.get("slot"), position),
                tool_key=str(item.get("tool_key") or "unknown"),
                invocation_id=invocation_id,
                input=item.get("input") if isinstance(item.get("input"), dict) else {},
                rationale=rationale,
                result=item.get("result") if isinstance(item.get("result"), dict) else {},
            )
        )
    return rows


def _source_type(value: Any, *, invocation_id: uuid.UUID | None) -> EvidenceSourceType:
    candidate = str(value or "").strip()
    if candidate in {"tool", "document", "memory"}:
        return candidate  # type: ignore[return-value]
    return "tool" if invocation_id is not None else "unknown"


def _evidence(
    content: dict[str, Any], tool_invocations: list[ResearchToolInvocationRead]
) -> list[ResearchEvidenceRead]:
    rows: list[ResearchEvidenceRead] = []
    raw = content.get("evidence")
    if isinstance(raw, list):
        for position, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            evidence_id = str(item.get("evidence_id") or "").strip()
            if not evidence_id:
                continue
            invocation_id = _uuid_or_none(item.get("invocation_id"))
            source_type = _source_type(item.get("source_type"), invocation_id=invocation_id)
            if source_type == "tool" and invocation_id is None:
                continue
            raw_slot = item.get("slot")
            slot = _slot(raw_slot, position) if raw_slot is not None else None
            title = str(item.get("title") or "").strip() or None
            excerpt = str(item.get("excerpt") or "").strip() or None
            provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
            rows.append(
                ResearchEvidenceRead(
                    evidence_id=evidence_id,
                    source_type=source_type,
                    source=str(item.get("source") or item.get("tool_key") or "unknown"),
                    authority=str(item.get("authority") or "unknown"),
                    slot=slot,
                    tool_key=(str(item.get("tool_key") or "") or None),
                    invocation_id=invocation_id,
                    title=title,
                    excerpt=excerpt,
                    provenance=provenance,
                )
            )
        if rows:
            return rows

    # Backward compatibility with the first research artifacts, which preserved canonical tool
    # invocations but did not yet include a typed multi-source evidence index.
    for item in tool_invocations:
        rows.append(
            ResearchEvidenceRead(
                evidence_id=f"E{item.slot + 1}",
                source_type="tool",
                source=item.tool_key,
                authority="policy-bound-read-tool",
                slot=item.slot,
                tool_key=item.tool_key,
                invocation_id=item.invocation_id,
            )
        )
    return rows


def _confidence(value: Any) -> Confidence:
    candidate = str(value or "unknown")
    return candidate if candidate in {"low", "medium", "high", "unknown"} else "unknown"  # type: ignore[return-value]


def _synthesis(content: dict[str, Any]) -> ResearchSynthesisRead | None:
    raw = content.get("synthesis")
    if not isinstance(raw, dict):
        return None
    answer = str(raw.get("answer") or "").strip()
    if not answer:
        return None

    claims: list[ResearchClaimRead] = []
    raw_claims = raw.get("claims")
    if isinstance(raw_claims, list):
        for item in raw_claims:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            raw_evidence_ids = item.get("evidence_ids")
            evidence_ids = (
                [str(value) for value in raw_evidence_ids if str(value).strip()]
                if isinstance(raw_evidence_ids, list)
                else []
            )
            claims.append(
                ResearchClaimRead(
                    text=text,
                    evidence_ids=evidence_ids,
                    confidence=_confidence(item.get("confidence")),
                )
            )

    raw_uncertainties = raw.get("uncertainties")
    uncertainties = (
        [str(value) for value in raw_uncertainties if str(value).strip()]
        if isinstance(raw_uncertainties, list)
        else []
    )
    return ResearchSynthesisRead(answer=answer, claims=claims, uncertainties=uncertainties)


def _tool_call_count(content: dict[str, Any], fallback: int) -> int:
    try:
        return max(0, int(content.get("tool_call_count", fallback)))
    except (TypeError, ValueError):
        return fallback


@router.get("/v1/research/runs/{task_id}", response_model=ResearchRunRead)
async def get_research_run(
    task_id: uuid.UUID,
    principal: Principal = Depends(require_nevolium_user),
    session: AsyncSession = Depends(get_session),
) -> ResearchRunRead:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    task_input = _research_input(task)
    _require_research_owner(task_input, principal)

    execution = await session.scalar(
        select(WorkflowExecution)
        .where(WorkflowExecution.task_id == task.id)
        .order_by(WorkflowExecution.created_at.desc())
        .limit(1)
    )
    artifact = await session.scalar(
        select(Artifact)
        .where(Artifact.task_id == task.id, Artifact.kind == "autonomous-research")
        .order_by(Artifact.created_at.desc())
        .limit(1)
    )

    content = artifact.content if artifact is not None and isinstance(artifact.content, dict) else {}
    tool_invocations = _tool_invocations(content)
    synthesis = _synthesis(content)
    answer = str(content.get("answer") or "").strip() or (synthesis.answer if synthesis else None)

    return ResearchRunRead(
        task_id=task.id,
        project_id=task.project_id,
        status=task.status,
        execution_status=execution.status if execution else None,
        query=str(task_input.get("query") or ""),
        answer=answer,
        synthesis=synthesis,
        evidence=_evidence(content, tool_invocations),
        context_pack=(content.get("context_pack") if isinstance(content.get("context_pack"), dict) else {}),
        tool_invocations=tool_invocations,
        tool_call_count=_tool_call_count(content, len(tool_invocations)),
        planner_model_alias=str(
            content.get("planner_model_alias") or task_input.get("model_alias") or ""
        )
        or None,
        synthesis_model_alias=str(content.get("synthesis_model_alias") or "") or None,
        model_budget_usd=Decimal(task.budget_usd) if task.budget_usd is not None else None,
        artifact_id=artifact.id if artifact else None,
        workflow_execution_id=execution.id if execution else None,
        workflow_id=execution.workflow_id if execution else None,
        correlation_id=execution.correlation_id if execution else None,
        error=execution.last_error if execution else None,
        created_at=task.created_at,
        completed_at=task.completed_at,
        artifact_created_at=artifact.created_at if artifact else None,
    )
