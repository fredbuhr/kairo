from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .autonomy_models import ApprovalRequest
from .db import get_session
from .models import WorkflowExecution
from .temporal_gateway import temporal_gateway

router = APIRouter()


class ApprovalResumeResponse(BaseModel):
    approval_request_id: uuid.UUID
    workflow_id: str
    decision: str
    signaled: bool


@router.post(
    "/v1/approval-requests/{approval_id}/resume",
    response_model=ApprovalResumeResponse,
)
async def resume_approved_workflow(
    approval_id: uuid.UUID,
    _: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> ApprovalResumeResponse:
    approval = await session.get(ApprovalRequest, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status not in {"approved", "denied"}:
        raise HTTPException(status_code=409, detail="Approval request has no final decision")
    if not approval.workflow_execution_id:
        raise HTTPException(status_code=409, detail="Approval request is not bound to a workflow")

    execution = await session.get(WorkflowExecution, approval.workflow_execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Workflow execution not found")

    try:
        await temporal_gateway.signal_task_workflow(
            workflow_id=execution.workflow_id,
            signal="approval_decision",
            payload={
                "approval_request_id": str(approval.id),
                "decision": approval.status,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Approval is recorded but Temporal could not be signaled; retry this resume endpoint",
        ) from exc

    return ApprovalResumeResponse(
        approval_request_id=approval.id,
        workflow_id=execution.workflow_id,
        decision=approval.status,
        signaled=True,
    )
