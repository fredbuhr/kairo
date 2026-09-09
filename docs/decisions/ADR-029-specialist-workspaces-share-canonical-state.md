# ADR-029 — Specialist workspaces share canonical KAIRO state

Status: accepted
Date: 2026-09-09

## Context

KAIRO's permanent Test Interface v1 combines a spatial Home/KAIRO Brain with specialist operational views such as Projects, Tasks/Today, Knowledge, Calendar, Gantt, Agents and Finance.

A specialist view is often easier to use as a list, form, table or timeline than as a 3D graph. That convenience creates a risk: each workspace could start owning its own local project/task/document state and become a second product model that must later be reconciled with the mycelium.

That would violate the core KAIRO rule that PostgreSQL-owned domain entities are canonical and that alternative views are projections over the same world.

## Decision

Specialist workspaces are views and controls over KAIRO-owned canonical APIs. They do not own parallel authoritative state.

The permanent shell remains shared:

- primary navigation;
- universal search;
- KAIRO command dock and assistant;
- common product identity and accessibility rules.

The central surface may switch from the spatial renderer to a specialist workspace, but this is not a second application.

### Canonical synchronization

When a workspace creates or mutates an entity that is represented in the spatial graph:

1. the mutation is performed through KAIRO Core;
2. the workspace invalidates/refetches its own operational read model;
3. the shared graph projection is invalidated/refreshed;
4. live canonical Outbox activity remains the normal cross-view update mechanism.

Projects and Tasks therefore mutate canonical `/v1/projects` / `/v1/tasks` state and invalidate the same `kairo-graph` query family. Task planning extends the canonical Task itself with explicit priority, planned start/end and due timestamps; the Today view is a deterministic read model over those fields rather than a frontend ranking heuristic.

Knowledge follows the same rule at the document boundary. A user import becomes a canonical Asset, then a stable Document, then immutable DocumentVersion / DocumentChunk projections. Retrieval reads the newest completed canonical generation and never stores a separate frontend library or silently treats a stale generation as current knowledge.

### Cross-view navigation

If a specialist workspace displays a canonical entity that exists in the graph contract, it should expose a direct path to that same entity in KAIRO Brain/Home focus. The workspace must pass the canonical `entity_type` + `entity_id`; it must not create an independent visual identity.

Projects, Tasks and Documents already follow this rule in Test Interface v1.

### Progressive capability depth

An operational workspace may launch with a deliberately narrow but real slice — for example create/read/filter/explore — while richer update/lifecycle actions are still being implemented. Missing capabilities are shown as unavailable rather than simulated with frontend-only data.

Progressive depth must not be confused with fabricated behavior. For example, Today only shows a task because a real due date, planned interval or explicit high priority exists. If no such fact exists, KAIRO shows that the day is unplanned instead of inventing urgency.

## Consequences

- Projects, Tasks/Today and Knowledge can evolve independently as interfaces while remaining synchronized representations of the same KAIRO world.
- The mycelium and operational workspaces never require reconciliation between competing domain models.
- Calendar and Gantt can build directly on explicit Task planning timestamps rather than creating temporary schedule objects.
- Future Agents, Automations and Finance areas must follow the same contract.
- Tauri/Desktop can reuse the same web application and workspace boundaries.
- Frontend state remains interaction state; canonical domain state remains in KAIRO Core.
