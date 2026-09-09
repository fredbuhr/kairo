from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .autonomy_models import ApprovalRequest
from .command_models import Conversation
from .db import get_session
from .document_models import Document
from .graph_schemas import (
    GraphEdgeRead,
    GraphEntityRef,
    GraphNodeRead,
    GraphProjectionContext,
    GraphProjectionRead,
    GraphSearchRead,
)
from .models import Artifact, Asset, Project, RelationshipRecord, Task, WorkflowExecution
from .ownership import entity_belongs_to_subject


router = APIRouter(prefix="/v1/graph", tags=["graph"])

_TYPE_ALIASES = {
    "projects": "project",
    "tasks": "task",
    "documents": "document",
    "conversations": "conversation",
    "approvals": "approval",
    "approval_request": "approval",
    "approval_requests": "approval",
    "artifacts": "artifact",
    "assets": "asset",
    "workflow": "workflow_execution",
    "workflow_execution": "workflow_execution",
    "workflow_executions": "workflow_execution",
}

_BASE_IMPORTANCE = {
    "approval": 0.90,
    "project": 0.82,
    "task": 0.68,
    "document": 0.56,
    "artifact": 0.52,
    "conversation": 0.48,
    "workflow_execution": 0.42,
    "asset": 0.34,
}

_ACTIVE_STATES = {
    "active",
    "in_progress",
    "running",
    "pending",
    "queued",
    "waiting",
    "waiting_approval",
    "blocked",
}


def _normalize_type(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return _TYPE_ALIASES.get(normalized, normalized)


def _entity_key(entity_type: str, entity_id: uuid.UUID) -> str:
    return f"{_normalize_type(entity_type)}:{entity_id}"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _recency_score(value: datetime | None) -> float:
    if value is None:
        return 0.15
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (datetime.now(timezone.utc) - value).total_seconds() / 86400.0)
    return _clamp(math.exp(-age_days / 21.0))


def _activity_score(status: str | None, recency: float) -> float:
    if status and status.lower() in _ACTIVE_STATES:
        return max(recency, 0.72)
    return recency * 0.72


def _initial_importance(entity_type: str, status: str | None, recency: float) -> float:
    score = _BASE_IMPORTANCE.get(entity_type, 0.40)
    if status and status.lower() in {"blocked", "pending", "waiting_approval"}:
        score += 0.10
    return _clamp(score + recency * 0.08)


def _lod_for(importance: float) -> int:
    if importance >= 0.88:
        return 0
    if importance >= 0.70:
        return 1
    if importance >= 0.50:
        return 2
    return 3


def _node(
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    label: str,
    subtitle: str | None,
    project_id: uuid.UUID | None,
    status: str | None,
    updated_at: datetime | None,
    metadata: dict | None = None,
) -> GraphNodeRead:
    entity_type = _normalize_type(entity_type)
    recency = _recency_score(updated_at)
    importance = _initial_importance(entity_type, status, recency)
    cluster_hint = str(project_id) if project_id else (str(entity_id) if entity_type == "project" else None)
    return GraphNodeRead(
        id=entity_id,
        entity_type=entity_type,
        label=label,
        subtitle=subtitle,
        project_id=project_id,
        status=status,
        importance=importance,
        activity=_activity_score(status, recency),
        recency=recency,
        relationship_count=0,
        cluster_hint=cluster_hint,
        lod=_lod_for(importance),
        metadata=metadata or {},
        updated_at=updated_at,
    )


def _node_from_project(row: Project) -> GraphNodeRead:
    return _node(
        entity_type="project",
        entity_id=row.id,
        label=row.name,
        subtitle=row.summary[:160] if row.summary else None,
        project_id=row.id,
        status=row.status,
        updated_at=row.updated_at,
        metadata={"parent_id": str(row.parent_id) if row.parent_id else None},
    )


def _node_from_task(row: Task) -> GraphNodeRead:
    return _node(
        entity_type="task",
        entity_id=row.id,
        label=row.title,
        subtitle=row.description[:160] if row.description else None,
        project_id=row.project_id,
        status=row.status,
        updated_at=row.updated_at,
        metadata={
            "owner_type": row.owner_type,
            "owner_ref": row.owner_ref,
            "authority_ceiling": row.authority_ceiling,
        },
    )


def _node_from_document(row: Document) -> GraphNodeRead:
    return _node(
        entity_type="document",
        entity_id=row.id,
        label=row.title,
        subtitle=row.media_type,
        project_id=row.project_id,
        status=row.status,
        updated_at=row.updated_at,
        metadata={"asset_id": str(row.asset_id), "media_type": row.media_type},
    )


def _node_from_conversation(row: Conversation) -> GraphNodeRead:
    label = row.title or "Conversation"
    return _node(
        entity_type="conversation",
        entity_id=row.id,
        label=label,
        subtitle=None,
        project_id=None,
        status=row.status,
        updated_at=row.updated_at,
        metadata={"locale": row.locale},
    )


def _node_from_approval(row: ApprovalRequest) -> GraphNodeRead:
    return _node(
        entity_type="approval",
        entity_id=row.id,
        label=row.action,
        subtitle=row.resource_type,
        project_id=None,
        status=row.status,
        updated_at=row.updated_at,
        metadata={
            "task_id": str(row.task_id),
            "authority_level": row.authority_level,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        },
    )


def _node_from_artifact(row: Artifact) -> GraphNodeRead:
    return _node(
        entity_type="artifact",
        entity_id=row.id,
        label=row.title,
        subtitle=row.kind,
        project_id=row.project_id,
        status=None,
        updated_at=row.created_at,
        metadata={
            "kind": row.kind,
            "task_id": str(row.task_id) if row.task_id else None,
        },
    )


def _node_from_asset(row: Asset) -> GraphNodeRead:
    filename = row.metadata_json.get("filename") if isinstance(row.metadata_json, dict) else None
    if not isinstance(filename, str) or not filename.strip():
        filename = PurePosixPath(row.object_key).name or "Asset"
    return _node(
        entity_type="asset",
        entity_id=row.id,
        label=filename,
        subtitle=row.mime_type,
        project_id=row.project_id,
        status=None,
        updated_at=row.created_at,
        metadata={
            "mime_type": row.mime_type,
            "size_bytes": row.size_bytes,
        },
    )


def _node_from_workflow(row: WorkflowExecution) -> GraphNodeRead:
    return _node(
        entity_type="workflow_execution",
        entity_id=row.id,
        label=row.workflow_id,
        subtitle="Workflow",
        project_id=None,
        status=row.status,
        updated_at=row.updated_at,
        metadata={"task_id": str(row.task_id)},
    )


async def _resolve_entity(
    session: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    subject: str,
) -> GraphNodeRead | None:
    entity_type = _normalize_type(entity_type)
    if not await entity_belongs_to_subject(session, entity_type, entity_id, subject):
        return None
    if entity_type == "project":
        row = await session.get(Project, entity_id)
        return _node_from_project(row) if row else None
    if entity_type == "task":
        row = await session.get(Task, entity_id)
        return _node_from_task(row) if row else None
    if entity_type == "document":
        row = await session.get(Document, entity_id)
        return _node_from_document(row) if row else None
    if entity_type == "conversation":
        row = await session.get(Conversation, entity_id)
        return _node_from_conversation(row) if row else None
    if entity_type == "approval":
        row = await session.get(ApprovalRequest, entity_id)
        return _node_from_approval(row) if row else None
    if entity_type == "artifact":
        row = await session.get(Artifact, entity_id)
        return _node_from_artifact(row) if row else None
    if entity_type == "asset":
        row = await session.get(Asset, entity_id)
        return _node_from_asset(row) if row else None
    if entity_type == "workflow_execution":
        row = await session.get(WorkflowExecution, entity_id)
        return _node_from_workflow(row) if row else None
    return None


def _edge_id(
    provenance: str,
    relation: str,
    source_type: str,
    source_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
) -> str:
    signature = (
        f"kairo:{provenance}:{_normalize_type(source_type)}:{source_id}:"
        f"{relation}:{_normalize_type(target_type)}:{target_id}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, signature))


def _structural_edge(
    source: GraphNodeRead,
    target: GraphNodeRead,
    relation: str,
    *,
    explanation: str,
    strength: float = 0.88,
) -> GraphEdgeRead:
    return GraphEdgeRead(
        id=_edge_id(
            "canonical_fk",
            relation,
            source.entity_type,
            source.id,
            target.entity_type,
            target.id,
        ),
        source=GraphEntityRef(entity_type=source.entity_type, entity_id=source.id),
        target=GraphEntityRef(entity_type=target.entity_type, entity_id=target.id),
        relation=relation,
        directed=True,
        strength=strength,
        provenance="canonical_fk",
        explanation=explanation,
    )


def _relationship_edge(row: RelationshipRecord) -> GraphEdgeRead:
    metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
    raw_strength = metadata.get("strength", 0.62)
    try:
        strength = _clamp(float(raw_strength))
    except (TypeError, ValueError):
        strength = 0.62
    directed = metadata.get("directed", True)
    if not isinstance(directed, bool):
        directed = True
    explanation = metadata.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        explanation = row.relation_type.replace("_", " ")
    return GraphEdgeRead(
        id=str(row.id),
        source=GraphEntityRef(
            entity_type=_normalize_type(row.source_type), entity_id=row.source_id
        ),
        target=GraphEntityRef(
            entity_type=_normalize_type(row.target_type), entity_id=row.target_id
        ),
        relation=row.relation_type,
        directed=directed,
        strength=strength,
        provenance="canonical_relationship",
        explanation=explanation,
        metadata={key: value for key, value in metadata.items() if key not in {"strength", "directed"}},
    )


async def _explicit_edges_for(
    session: AsyncSession,
    nodes: dict[str, GraphNodeRead],
    subject: str,
) -> list[GraphEdgeRead]:
    if not nodes:
        return []
    ids = list({node.id for node in nodes.values()})
    rows = await session.execute(
        select(RelationshipRecord)
        .where(RelationshipRecord.keycloak_subject == subject)
        .where(
            or_(
                RelationshipRecord.source_id.in_(ids),
                RelationshipRecord.target_id.in_(ids),
            )
        )
        .order_by(RelationshipRecord.created_at.desc())
        .limit(2000)
    )
    edges: list[GraphEdgeRead] = []
    for row in rows.scalars():
        edge = _relationship_edge(row)
        if (
            _entity_key(edge.source.entity_type, edge.source.entity_id) in nodes
            and _entity_key(edge.target.entity_type, edge.target.entity_id) in nodes
        ):
            edges.append(edge)
    return edges


def _structural_edges(nodes: dict[str, GraphNodeRead]) -> list[GraphEdgeRead]:
    edges: list[GraphEdgeRead] = []
    for node in nodes.values():
        if node.entity_type == "project":
            parent_id = node.metadata.get("parent_id")
            if parent_id:
                parent_key = _entity_key("project", uuid.UUID(parent_id))
                if parent_key in nodes:
                    edges.append(
                        _structural_edge(
                            node,
                            nodes[parent_key],
                            "part_of",
                            explanation="Project hierarchy",
                            strength=0.92,
                        )
                    )

        if node.project_id and node.entity_type != "project":
            project_key = _entity_key("project", node.project_id)
            if project_key in nodes:
                edges.append(
                    _structural_edge(
                        node,
                        nodes[project_key],
                        "belongs_to",
                        explanation="Canonical project scope",
                        strength=0.94,
                    )
                )

        task_id = node.metadata.get("task_id")
        if task_id:
            task_key = _entity_key("task", uuid.UUID(task_id))
            if task_key in nodes:
                relation = {
                    "approval": "authorizes",
                    "artifact": "produced_by",
                    "workflow_execution": "executes",
                }.get(node.entity_type, "relates_to_task")
                explanation = {
                    "approval": "Approval request for this task",
                    "artifact": "Artifact produced by this task",
                    "workflow_execution": "Workflow execution for this task",
                }.get(node.entity_type, "Canonical task linkage")
                edges.append(
                    _structural_edge(
                        node,
                        nodes[task_key],
                        relation,
                        explanation=explanation,
                        strength=0.90,
                    )
                )

        asset_id = node.metadata.get("asset_id")
        if asset_id:
            asset_key = _entity_key("asset", uuid.UUID(asset_id))
            if asset_key in nodes:
                edges.append(
                    _structural_edge(
                        node,
                        nodes[asset_key],
                        "sourced_from",
                        explanation="Canonical source asset",
                        strength=0.86,
                    )
                )
    return edges


def _merge_edges(*groups: Iterable[GraphEdgeRead]) -> list[GraphEdgeRead]:
    deduped: dict[str, GraphEdgeRead] = {}
    for group in groups:
        for edge in group:
            deduped[edge.id] = edge
    return list(deduped.values())


def _finalize_nodes(nodes: dict[str, GraphNodeRead], edges: list[GraphEdgeRead]) -> None:
    degree: dict[str, int] = {key: 0 for key in nodes}
    for edge in edges:
        source_key = _entity_key(edge.source.entity_type, edge.source.entity_id)
        target_key = _entity_key(edge.target.entity_type, edge.target.entity_id)
        if source_key in degree:
            degree[source_key] += 1
        if target_key in degree:
            degree[target_key] += 1

    for key, node in nodes.items():
        node.relationship_count = degree[key]
        node.importance = _clamp(node.importance + min(degree[key], 8) * 0.018)
        node.lod = _lod_for(node.importance)


async def _ensure_project_anchors(
    session: AsyncSession,
    nodes: dict[str, GraphNodeRead],
    *,
    max_nodes: int,
    subject: str,
) -> None:
    project_ids = {
        node.project_id
        for node in nodes.values()
        if node.project_id is not None and _entity_key("project", node.project_id) not in nodes
    }
    for project_id in project_ids:
        if len(nodes) >= max_nodes:
            break
        project = await session.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.keycloak_subject == subject,
            )
        )
        if project:
            node = _node_from_project(project)
            nodes[node.key] = node


async def _home_candidates(session: AsyncSession, subject: str) -> list[GraphNodeRead]:
    results: list[GraphNodeRead] = []

    project_rows = await session.execute(
        select(Project)
        .where(Project.keycloak_subject == subject, Project.status != "archived")
        .order_by(Project.updated_at.desc())
        .limit(18)
    )
    results.extend(_node_from_project(row) for row in project_rows.scalars())

    task_rows = await session.execute(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(
            Project.keycloak_subject == subject,
            ~Task.status.in_(["completed", "done", "cancelled", "archived"]),
        )
        .order_by(Task.updated_at.desc())
        .limit(32)
    )
    results.extend(_node_from_task(row) for row in task_rows.scalars())

    approval_rows = await session.execute(
        select(ApprovalRequest)
        .join(Task, Task.id == ApprovalRequest.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(
            Project.keycloak_subject == subject,
            ApprovalRequest.status == "pending",
        )
        .order_by(ApprovalRequest.updated_at.desc())
        .limit(10)
    )
    results.extend(_node_from_approval(row) for row in approval_rows.scalars())

    document_rows = await session.execute(
        select(Document)
        .join(Project, Project.id == Document.project_id)
        .where(Project.keycloak_subject == subject)
        .order_by(Document.updated_at.desc())
        .limit(20)
    )
    results.extend(_node_from_document(row) for row in document_rows.scalars())

    conversation_rows = await session.execute(
        select(Conversation)
        .where(Conversation.subject_ref == subject, Conversation.status == "active")
        .order_by(Conversation.updated_at.desc())
        .limit(16)
    )
    results.extend(_node_from_conversation(row) for row in conversation_rows.scalars())

    artifact_rows = await session.execute(
        select(Artifact)
        .join(Project, Project.id == Artifact.project_id)
        .where(Project.keycloak_subject == subject)
        .order_by(Artifact.created_at.desc())
        .limit(14)
    )
    results.extend(_node_from_artifact(row) for row in artifact_rows.scalars())

    return results


async def _structural_neighbors(
    session: AsyncSession,
    node: GraphNodeRead,
    *,
    limit: int,
    subject: str,
) -> list[tuple[GraphNodeRead, GraphEdgeRead]]:
    if limit <= 0:
        return []
    pairs: list[tuple[GraphNodeRead, GraphEdgeRead]] = []

    async def add(neighbor: GraphNodeRead | None, relation: str, explanation: str, strength: float = 0.9):
        if neighbor is None or len(pairs) >= limit:
            return
        pairs.append(
            (
                neighbor,
                _structural_edge(node, neighbor, relation, explanation=explanation, strength=strength),
            )
        )

    if node.entity_type == "project":
        parent_id = node.metadata.get("parent_id")
        if parent_id:
            await add(
                await _resolve_entity(session, "project", uuid.UUID(parent_id), subject),
                "part_of",
                "Project hierarchy",
                0.92,
            )
        rows = await session.execute(
            select(Task)
            .where(Task.project_id == node.id)
            .order_by(Task.updated_at.desc())
            .limit(limit)
        )
        for row in rows.scalars():
            child = _node_from_task(row)
            if len(pairs) < limit:
                pairs.append(
                    (
                        child,
                        _structural_edge(
                            child,
                            node,
                            "belongs_to",
                            explanation="Canonical project scope",
                            strength=0.94,
                        ),
                    )
                )
        if len(pairs) < limit:
            rows = await session.execute(
                select(Document)
                .where(Document.project_id == node.id)
                .order_by(Document.updated_at.desc())
                .limit(limit - len(pairs))
            )
            for row in rows.scalars():
                child = _node_from_document(row)
                if len(pairs) < limit:
                    pairs.append(
                        (
                            child,
                            _structural_edge(
                                child,
                                node,
                                "belongs_to",
                                explanation="Canonical project scope",
                                strength=0.94,
                            ),
                        )
                    )
        if len(pairs) < limit:
            rows = await session.execute(
                select(Project)
                .where(Project.parent_id == node.id, Project.keycloak_subject == subject)
                .order_by(Project.updated_at.desc())
                .limit(limit - len(pairs))
            )
            for row in rows.scalars():
                child = _node_from_project(row)
                if len(pairs) < limit:
                    pairs.append(
                        (
                            child,
                            _structural_edge(
                                child,
                                node,
                                "part_of",
                                explanation="Project hierarchy",
                                strength=0.92,
                            ),
                        )
                    )

    elif node.entity_type == "task":
        if node.project_id:
            await add(
                await _resolve_entity(session, "project", node.project_id, subject),
                "belongs_to",
                "Canonical project scope",
                0.94,
            )
        if len(pairs) < limit:
            rows = await session.execute(
                select(ApprovalRequest)
                .where(ApprovalRequest.task_id == node.id)
                .order_by(ApprovalRequest.updated_at.desc())
                .limit(limit - len(pairs))
            )
            for row in rows.scalars():
                approval = _node_from_approval(row)
                if len(pairs) < limit:
                    pairs.append(
                        (
                            approval,
                            _structural_edge(
                                approval,
                                node,
                                "authorizes",
                                explanation="Approval request for this task",
                                strength=0.90,
                            ),
                        )
                    )
        if len(pairs) < limit:
            rows = await session.execute(
                select(Artifact)
                .where(Artifact.task_id == node.id)
                .order_by(Artifact.created_at.desc())
                .limit(limit - len(pairs))
            )
            for row in rows.scalars():
                artifact = _node_from_artifact(row)
                if len(pairs) < limit:
                    pairs.append(
                        (
                            artifact,
                            _structural_edge(
                                artifact,
                                node,
                                "produced_by",
                                explanation="Artifact produced by this task",
                                strength=0.88,
                            ),
                        )
                    )

    elif node.entity_type == "document":
        if node.project_id:
            await add(
                await _resolve_entity(session, "project", node.project_id, subject),
                "belongs_to",
                "Canonical project scope",
                0.94,
            )
        asset_id = node.metadata.get("asset_id")
        if asset_id:
            await add(
                await _resolve_entity(session, "asset", uuid.UUID(asset_id), subject),
                "sourced_from",
                "Canonical source asset",
                0.86,
            )

    elif node.entity_type == "approval":
        task_id = node.metadata.get("task_id")
        if task_id:
            task = await _resolve_entity(session, "task", uuid.UUID(task_id), subject)
            if task:
                pairs.append(
                    (
                        task,
                        _structural_edge(
                            node,
                            task,
                            "authorizes",
                            explanation="Approval request for this task",
                            strength=0.90,
                        ),
                    )
                )

    elif node.entity_type == "artifact":
        if node.project_id:
            await add(
                await _resolve_entity(session, "project", node.project_id, subject),
                "belongs_to",
                "Canonical project scope",
                0.94,
            )
        task_id = node.metadata.get("task_id")
        if task_id:
            await add(
                await _resolve_entity(session, "task", uuid.UUID(task_id), subject),
                "produced_by",
                "Artifact produced by this task",
                0.88,
            )

    elif node.entity_type == "asset":
        if node.project_id:
            await add(
                await _resolve_entity(session, "project", node.project_id, subject),
                "belongs_to",
                "Canonical project scope",
                0.90,
            )

    elif node.entity_type == "workflow_execution":
        task_id = node.metadata.get("task_id")
        if task_id:
            await add(
                await _resolve_entity(session, "task", uuid.UUID(task_id), subject),
                "executes",
                "Workflow execution for this task",
                0.92,
            )

    return pairs[:limit]


async def _explicit_neighbors(
    session: AsyncSession,
    frontier: list[GraphNodeRead],
    *,
    limit: int,
    subject: str,
) -> list[tuple[GraphNodeRead, GraphEdgeRead]]:
    if not frontier or limit <= 0:
        return []
    frontier_keys = {node.key for node in frontier}
    ids = [node.id for node in frontier]
    rows = await session.execute(
        select(RelationshipRecord)
        .where(RelationshipRecord.keycloak_subject == subject)
        .where(
            or_(
                RelationshipRecord.source_id.in_(ids),
                RelationshipRecord.target_id.in_(ids),
            )
        )
        .order_by(RelationshipRecord.created_at.desc())
        .limit(max(limit * 6, 60))
    )
    pairs: list[tuple[GraphNodeRead, GraphEdgeRead]] = []
    for row in rows.scalars():
        edge = _relationship_edge(row)
        source_key = _entity_key(edge.source.entity_type, edge.source.entity_id)
        target_key = _entity_key(edge.target.entity_type, edge.target.entity_id)
        if source_key in frontier_keys:
            other = edge.target
        elif target_key in frontier_keys:
            other = edge.source
        else:
            continue
        neighbor = await _resolve_entity(session, other.entity_type, other.entity_id, subject)
        if neighbor:
            pairs.append((neighbor, edge))
        if len(pairs) >= limit:
            break
    return pairs


@router.get("/home", response_model=GraphProjectionRead)
async def graph_home(
    max_nodes: int = Query(default=72, ge=12, le=200),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> GraphProjectionRead:
    candidates = await _home_candidates(session, principal.subject)
    candidates.sort(
        key=lambda node: (node.importance + node.activity * 0.30, node.recency),
        reverse=True,
    )

    nodes: dict[str, GraphNodeRead] = {}
    project_candidates = [node for node in candidates if node.entity_type == "project"]
    other_candidates = [node for node in candidates if node.entity_type != "project"]

    for node in project_candidates[: min(18, max(4, max_nodes // 3))]:
        nodes.setdefault(node.key, node)

    reserve_for_anchors = min(8, max_nodes // 6)
    soft_limit = max(len(nodes), max_nodes - reserve_for_anchors)
    for node in other_candidates:
        if len(nodes) >= soft_limit:
            break
        nodes.setdefault(node.key, node)

    await _ensure_project_anchors(
        session,
        nodes,
        max_nodes=max_nodes,
        subject=principal.subject,
    )

    for node in other_candidates:
        if len(nodes) >= max_nodes:
            break
        nodes.setdefault(node.key, node)

    explicit = await _explicit_edges_for(session, nodes, principal.subject)
    structural = _structural_edges(nodes)
    edges = _merge_edges(explicit, structural)
    _finalize_nodes(nodes, edges)

    ordered_nodes = sorted(
        nodes.values(),
        key=lambda node: (node.importance + node.activity * 0.25, node.recency),
        reverse=True,
    )
    return GraphProjectionRead(
        context=GraphProjectionContext(
            mode="home",
            focus=None,
            depth=0,
            requested_limit=max_nodes,
        ),
        nodes=ordered_nodes,
        edges=edges,
        truncated=len(candidates) > max_nodes,
        generated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/neighborhood/{entity_type}/{entity_id}",
    response_model=GraphProjectionRead,
)
async def graph_neighborhood(
    entity_type: str,
    entity_id: uuid.UUID,
    depth: int = Query(default=1, ge=1, le=2),
    max_nodes: int = Query(default=96, ge=8, le=200),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> GraphProjectionRead:
    center = await _resolve_entity(session, entity_type, entity_id, principal.subject)
    if center is None:
        raise HTTPException(status_code=404, detail="Graph entity not found")

    center.importance = 1.0
    center.activity = max(center.activity, 0.80)
    center.lod = 0
    nodes: dict[str, GraphNodeRead] = {center.key: center}
    edge_map: dict[str, GraphEdgeRead] = {}
    frontier = [center]
    truncated = False

    for _level in range(depth):
        remaining = max_nodes - len(nodes)
        if remaining <= 0:
            truncated = True
            break

        discovered: list[tuple[GraphNodeRead, GraphEdgeRead]] = []
        for source in frontier:
            if len(discovered) >= remaining:
                truncated = True
                break
            discovered.extend(
                await _structural_neighbors(
                    session,
                    source,
                    limit=remaining - len(discovered),
                    subject=principal.subject,
                )
            )

        if len(discovered) < remaining:
            discovered.extend(
                await _explicit_neighbors(
                    session,
                    frontier,
                    limit=remaining - len(discovered),
                    subject=principal.subject,
                )
            )

        next_frontier: list[GraphNodeRead] = []
        for neighbor, edge in discovered:
            if not await entity_belongs_to_subject(
                session,
                neighbor.entity_type,
                neighbor.id,
                principal.subject,
            ):
                continue
            edge_map[edge.id] = edge
            if neighbor.key not in nodes:
                if len(nodes) >= max_nodes:
                    truncated = True
                    break
                nodes[neighbor.key] = neighbor
                next_frontier.append(neighbor)

        if not next_frontier:
            break
        frontier = next_frontier

    await _ensure_project_anchors(
        session,
        nodes,
        max_nodes=max_nodes,
        subject=principal.subject,
    )
    explicit = await _explicit_edges_for(session, nodes, principal.subject)
    structural = _structural_edges(nodes)
    edges = _merge_edges(edge_map.values(), explicit, structural)
    _finalize_nodes(nodes, edges)
    center = nodes[center.key]
    center.importance = 1.0
    center.lod = 0

    ordered_nodes = [center] + sorted(
        (node for key, node in nodes.items() if key != center.key),
        key=lambda node: (node.importance + node.activity * 0.25, node.recency),
        reverse=True,
    )
    return GraphProjectionRead(
        context=GraphProjectionContext(
            mode="neighborhood",
            focus=GraphEntityRef(entity_type=center.entity_type, entity_id=center.id),
            depth=depth,
            requested_limit=max_nodes,
        ),
        nodes=ordered_nodes,
        edges=edges,
        truncated=truncated,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/search", response_model=GraphSearchRead)
async def graph_search(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> GraphSearchRead:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Search query is too short")
    pattern = f"%{query}%"
    per_type = min(max(limit, 8), 24)
    nodes: dict[str, GraphNodeRead] = {}

    rows = await session.execute(
        select(Project)
        .where(Project.keycloak_subject == principal.subject, Project.name.ilike(pattern))
        .order_by(Project.updated_at.desc())
        .limit(per_type)
    )
    for row in rows.scalars():
        node = _node_from_project(row)
        nodes[node.key] = node

    rows = await session.execute(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Project.keycloak_subject == principal.subject, Task.title.ilike(pattern))
        .order_by(Task.updated_at.desc())
        .limit(per_type)
    )
    for row in rows.scalars():
        node = _node_from_task(row)
        nodes[node.key] = node

    rows = await session.execute(
        select(Document)
        .join(Project, Project.id == Document.project_id)
        .where(Project.keycloak_subject == principal.subject, Document.title.ilike(pattern))
        .order_by(Document.updated_at.desc())
        .limit(per_type)
    )
    for row in rows.scalars():
        node = _node_from_document(row)
        nodes[node.key] = node

    rows = await session.execute(
        select(Conversation)
        .where(
            Conversation.subject_ref == principal.subject,
            Conversation.title.is_not(None),
            Conversation.title.ilike(pattern),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(per_type)
    )
    for row in rows.scalars():
        node = _node_from_conversation(row)
        nodes[node.key] = node

    rows = await session.execute(
        select(ApprovalRequest)
        .join(Task, Task.id == ApprovalRequest.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(
            Project.keycloak_subject == principal.subject,
            ApprovalRequest.action.ilike(pattern),
        )
        .order_by(ApprovalRequest.updated_at.desc())
        .limit(per_type)
    )
    for row in rows.scalars():
        node = _node_from_approval(row)
        nodes[node.key] = node

    lowered = query.lower()
    ordered = sorted(
        nodes.values(),
        key=lambda node: (
            1 if node.label.lower().startswith(lowered) else 0,
            1 if lowered in node.label.lower() else 0,
            node.importance + node.recency * 0.20,
        ),
        reverse=True,
    )[:limit]
    return GraphSearchRead(query=query, nodes=ordered)
