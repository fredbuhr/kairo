# ADR-013 — Temporal owns durable workflow execution

**Status:** Accepted

## Decision

Temporal replaces the V0 runtime scheduler/job-recovery mechanism for long-running and autonomous KAIRO work.

KAIRO stores intent, authority, budgets, approvals, user-visible execution correlation and results; Temporal owns workflow/activity replay and durable execution mechanics.

## Rationale

The V0 crash experiments proved that replay, unknown activity results and idempotency are core platform concerns. Temporal provides these primitives without KAIRO implementing another workflow engine.
