from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .db import get_session
from .models import Artifact, Task, WorkflowExecution

router = APIRouter()


class ResearchClaimRead(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: str = "unknown"


class ResearchSynthesisRead(BaseModel):
    answer: str
    claims: list[ResearchClaimRead] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class ResearchEvidenceRead(BaseModel):
    evidence_id: str
    slot: int
    tool_key: str
    invocation_id: str


class ResearchRunRead(BaseModel):
    task_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    execution_status: str | None = None
    query: str
    answer: str | None = None
    synthesis: ResearchSynthesisRead | None = None
    evidence: list[ResearchEvidenceRead] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
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


def _tool_results(content: dict[str, Any]) -> list[dict[str, Any]]:
    raw = content.get("tool_results")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _evidence(content: dict[str, Any], tool_results: list[dict[str, Any]]) -> list[ResearchEvidenceRead]:
    rows: list[ResearchEvidenceRead] = []
    raw = content.get("evidence")
    if isinstance(raw, list):
        for position, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            try:
                slot = int(item.get("slot", position))
            except (TypeError, ValueError):
                slot = position
            rows.append(
                ResearchEvidenceRead(
                    evidence_id=str(item.get("evidence_id") or f"E{slot + 1}"),
                    slot=slot,
                    tool_key=str(item.get("tool_key") or "unknown"),
                    invocation_id=str(item.get("invocation_id") or ""),
                )
            )
        if rows:
            return rows

    # Backward compatibility with the first research artifact, which preserved tool results but did
    # not yet include an explicit evidence index.
    for position, item in enumerate(tool_results):
        try:
            slot = int(item.get("slot", position))
        except (TypeError, ValueError):
            slot = position
        rows.append(
            ResearchEvidenceRead(
                evidence_id=f"E{slot + 1}",
                slot=slot,
                tool_key=str(item.get("tool_key") or "unknown"),
                invocation_id=str(item.get("invocation_id") or ""),
            )
        )
    return rows


def _synthesis(content: dict[str, Any]) -> ResearchSynthesisRead | None:
    raw = content.get("synthesis")
    if not isinstance(raw, dict) or not str(raw.get("answer") or "").strip():
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
            evidence_ids = item.get("evidence_ids")
            claims.append(
                ResearchClaimRead(
                    text=text,
                    evidence_ids=[str(value) for value in evidence_ids]
                    if isinstance(evidence_ids, list)
                    else [],
                    confidence=str(item.get("confidence") or "unknown"),
                )
            )

    raw_uncertainties = raw.get("uncertainties")
    uncertainties = (
        [str(value) for value in raw_uncertainties]
        if isinstance(raw_uncertainties, list)
        else []
    )
    return ResearchSynthesisRead(
        answer=str(raw["answer"]), claims=claims, uncertainties=uncertainties
    )


@router.get("/v1/research/runs/{task_id}", response_model=ResearchRunRead)
async def get_research_run(
    task_id: uuid.UUID,
    _: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> ResearchRunRead:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Research task not found")
    task_input = _research_input(task)

    execution = await session.scalar(
        select(WorkflowExecution)
        .where(WorkflowExecution.task_id == task.id)
        .order_by(WorkflowExecution.created_at.desc())
    )
    artifact = await session.scalar(
        select(Artifact)
        .where(Artifact.task_id == task.id, Artifact.kind == "autonomous-research")
        .order_by(Artifact.created_at.desc())
    )

    content = artifact.content if artifact is not None and isinstance(artifact.content, dict) else {}
    tool_results = _tool_results(content)
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
        evidence=_evidence(content, tool_results),
        tool_results=tool_results,
        tool_call_count=int(content.get("tool_call_count") or len(tool_results)),
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
