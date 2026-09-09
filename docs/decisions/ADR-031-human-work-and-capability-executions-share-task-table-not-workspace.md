# ADR-031 — Human work and capability executions share Task storage, not workspace semantics

Status: accepted
Date: 2026-09-09

## Context

KAIRO deliberately makes durable system actions first-class canonical Tasks. News, Research, semantic routing, document ingestion and MCP tool invocations therefore use the same `tasks` table that also stores work a person intends to do.

This is useful for durability, audit, budgets and a unified graph, but a literal UI projection of every Task into the human Tasks/Today/Gantt views creates noise and incorrect semantics. A document-ingestion execution is not a human to-do merely because both records are durable Tasks.

## Decision

The canonical Task table remains shared, but product workspaces distinguish intent by the KAIRO capability marker already present in Task input.

- A Task whose canonical `input` contains a string `capability` is a **capability execution Task**.
- A Task without that marker is **human/operational work** for the current Tasks/Today/Gantt surface.

This is a product projection boundary, not a second database model.

### Human work surface

`GET /v1/planning/tasks`, `GET /v1/today` and the Task planning mutation operate only on human work Tasks. Attempts to use the human planning endpoint on a capability execution Task fail with `409` rather than silently modifying runtime execution semantics.

### Agents surface

`GET /v1/operations/agents` projects capability execution Tasks together with their canonical WorkflowExecution, pending approval count and canonical model spend where available.

The Agents workspace is therefore the operational home for durable KAIRO work. It may show News, Research, routing, ingestion and MCP tool calls without adding them to the user's Today list.

Pending ApprovalRequest rows remain canonical approval objects. The Agents workspace uses the existing approve/deny endpoints rather than creating frontend-only approval state.

### Shared world

Both kinds of Task remain visible to the graph when relevant. Cross-view navigation uses the same Task id. The distinction only determines which operational workspace is appropriate.

## Consequences

- Today/Gantt remain calm and human-oriented while Temporal executions remain fully canonical.
- Agent activity, spend, approval waits and failures gain a dedicated operational view.
- The graph can still connect human work, agent executions, artifacts, approvals and workflows because no storage split was introduced.
- Future scheduled automations that intentionally represent user work must declare their semantics explicitly rather than relying on UI heuristics.
- A richer typed Task-kind column may be introduced later if capability markers become insufficient; until then, the existing canonical capability contract is the fail-closed discriminator.
