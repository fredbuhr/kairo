# ADR-009 — Keep a KAIRO-owned durable job ledger

## Status

Accepted for V0.

## Context

OpenClaw owns the scheduler and runtime session/task state used to wake future agent turns. KAIRO, however, must remain able to explain what work it was asked to do, what authority was granted, whether the work ran, and what result it produced even if the execution runtime is upgraded or replaced.

Relying only on OpenClaw scheduler/session state would make KAIRO's audit history runtime-specific. Conversely, rebuilding OpenClaw's task/scheduler subsystem inside KAIRO would duplicate infrastructure prematurely.

## Decision

Add a small KAIRO-owned `Job` ledger stored beside the rest of the project domain state.

A KAIRO Job records, at minimum:

- stable KAIRO job ID;
- project;
- title and original instructions;
- lifecycle state;
- authority ceiling;
- requested schedule;
- source session where available;
- advisory requested model budget where supplied;
- external scheduler ID/tag/kind after scheduling;
- timestamps for queue/start/completion/failure/cancellation;
- completion summary or failure reason.

The V0 lifecycle is:

```text
scheduling -> queued -> running -> completed
     |          |          |
     +----------+----------+-> failed
     |
     +-> cancelled
```

Invalid transitions are rejected explicitly.

The OpenClaw scheduling adapter must create the KAIRO Job **before** requesting external scheduling. On successful scheduling it links the OpenClaw scheduler handle to the job. If scheduling fails, the durable job is marked failed. If scheduling succeeds but subsequent KAIRO linkage fails, the adapter attempts best-effort unscheduling by tag.

The future scheduled turn is instructed to mark the job running and then completed/failed through KAIRO tools.

## Budget semantics

A `requested_budget` may be recorded now, but V0 sets `budget_enforced: false` until the model router/accounting layer can enforce spend technically. KAIRO must not present an advisory budget as a hard guarantee.

## Consequences

### Positive

- KAIRO gains a runtime-independent audit trail for autonomous work;
- scheduler failures are visible as durable domain state;
- the future Cockpit can display queued/running/completed/failed work without reading OpenClaw internals;
- authority intent and requested budgets are preserved;
- migration to a different runtime remains possible.

### Negative

- scheduler state and KAIRO state are not transactionally atomic;
- future-turn crashes can leave a job queued/running without a final transition;
- completion currently depends on the future agent following the job lifecycle instructions;
- actual model/tool cost is not yet recorded on the job.

## Next work

Add runtime lifecycle reconciliation/health checks that can identify stale queued/running jobs and compare them with the OpenClaw scheduler/task state. Add model usage accounting before claiming hard budget enforcement.
