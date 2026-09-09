# ADR-030 — Explicit Task planning drives Today and Gantt

Status: accepted
Date: 2026-09-09

## Context

KAIRO needs an extremely simple operational Today view and, later, a capable Gantt/calendar view. Building those interfaces before the domain model contains real planning facts would force the frontend to infer urgency, fabricate dates or maintain a second scheduling model.

That would make the interface visually convincing while breaking KAIRO's canonical-state rule.

## Decision

Planning facts live on the canonical `Task` record in PostgreSQL:

- `priority` — explicit integer 0..4, with 2 as the neutral default;
- `planned_start_at` — optional timezone-aware planned start;
- `planned_end_at` — optional timezone-aware planned end;
- `due_at` — optional timezone-aware deadline.

Migration `0008_task_planning_fields` adds those fields and indexes their main operational access paths.

KAIRO Core owns planning mutation through `PATCH /v1/tasks/{task_id}/planning`. The endpoint validates planned intervals, emits a canonical `task.updated` event, audits the change, and keeps lifecycle timestamps coherent when a Task starts, completes or is reopened.

`GET /v1/today` is a deterministic read model. It does not ask a model to rank the user's day. It groups open Tasks from explicit facts, in this precedence order:

1. overdue deadline;
2. deadline in the requested local day;
3. planned interval overlapping the local day;
4. explicit priority 3/4 when the Task has not already appeared in another Today group.

The client supplies its timezone offset only to define the local-day boundary. Canonical timestamps remain timezone-aware.

## Consequences

- An empty Today view is meaningful: it means no canonical planning fact currently places work in Today.
- The UI can expose planning controls without introducing local-only task metadata.
- Gantt can reuse `planned_start_at` / `planned_end_at` instead of maintaining a separate fake schedule.
- Calendar can later project Task intervals alongside external calendar events while preserving provenance.
- KAIRO can eventually suggest planning changes, but suggestions must become explicit Core mutations before Today/Gantt treat them as facts.
- Priority is not an LLM confidence or importance score; it is explicit user/KAIRO-authorized operational state.
