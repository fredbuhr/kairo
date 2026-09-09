# ADR-029 — Specialist workspaces share canonical KAIRO state

Status: accepted
Date: 2026-09-09

## Context

KAIRO's permanent Test Interface v1 combines a spatial Home/KAIRO Brain with specialist operational views such as Projects, Tasks, Knowledge, Calendar, Gantt, Agents and Finance.

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

The first Projects and Tasks workspaces therefore use the existing `/v1/projects` and `/v1/tasks` APIs and invalidate the same `kairo-graph` query family after creation.

### Cross-view navigation

If a specialist workspace displays a canonical entity that exists in the graph contract, it should expose a direct path to that same entity in KAIRO Brain/Home focus. The workspace must pass the canonical `entity_type` + `entity_id`; it must not create an independent visual identity.

### Progressive capability depth

An operational workspace may launch with a deliberately narrow but real slice — for example create/read/filter/explore — while richer update/lifecycle actions are still being implemented. Missing capabilities are shown as unavailable rather than simulated with frontend-only data.

## Consequences

- Projects and Tasks can become useful immediately without waiting for every lifecycle mutation endpoint.
- The mycelium and operational workspaces remain two representations of the same KAIRO world.
- Future Knowledge, Calendar, Gantt, Agents and Finance areas must follow the same contract.
- Tauri/Desktop can reuse the same web application and workspace boundaries.
- Frontend state remains interaction state; canonical domain state remains in KAIRO Core.
