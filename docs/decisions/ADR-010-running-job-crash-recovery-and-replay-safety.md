# ADR-010 — Preserve runtime recovery and require replay-safe autonomous steps

## Status

Accepted for V0 based on live OpenClaw 2026.9.2 crash-recovery characterization.

## Context

ADR-009 established a KAIRO-owned durable Job ledger while OpenClaw owns runtime scheduling and execution. It correctly identified that a future-turn crash can leave a KAIRO Job in `queued` or `running` without a final transition, but the recovery behavior of a real abrupt runtime crash had not yet been characterized.

A live local proof deliberately killed the OpenClaw Gateway with `SIGKILL` while a harmless A2 KAIRO Job was already `running` and executing `sleep 90`.

The observed behavior was:

1. `kairo_job_start` had persisted the Job as `running` before the crash;
2. the abrupt process death left that durable state unchanged, with no false completion or failure;
3. after restart, OpenClaw recorded the interrupted Cron run as `cron: job interrupted by gateway restart`;
4. OpenClaw resumed the interrupted agent turn and explicitly treated the interrupted/missing tool result as unknown;
5. the harmless `sleep 90` step was replayed and then completed successfully;
6. the resumed turn called `kairo_job_complete`, making the KAIRO Job terminal;
7. a later one-shot Cron retry attempted to start the same KAIRO Job, but the ledger rejected `completed -> running`;
8. the retry inspected the already-completed Job instead of repeating the substantive work, and the one-shot scheduler was subsequently cleaned up.

A separate live proof also showed that Cron delivery failure can coexist with a successfully completed KAIRO Job. Scheduler execution/delivery state is therefore not identical to KAIRO work state.

## Decision

### 1. Do not blanket-fail `running` Jobs on Gateway restart

KAIRO must not mark every `running` Job failed merely because OpenClaw restarted or because a previous runtime process disappeared.

On the pinned V0 runtime, OpenClaw can legitimately resume an interrupted agent turn. A blanket transition to `failed` would race with or invalidate that native recovery path.

Queued-job reconciliation remains conservative and separate: future `queued` Jobs whose scheduler disappears after OpenClaw Cron reconciliation may be failed under the existing PR #12 rules.

### 2. Keep the KAIRO Job ledger authoritative for KAIRO lifecycle

KAIRO completion/failure is determined by the durable KAIRO Job lifecycle, not by Cron delivery status alone.

A delivery-only error must not overwrite an already-correct KAIRO terminal state.

Likewise, an interrupted or missing tool result after a crash must be treated as **unknown**, never inferred as successful.

### 3. Treat crash replay as an idempotence problem

The unresolved safety risk is not simply a stale `running` marker. It is replay of a step whose prior outcome cannot be determined after abrupt failure.

Before KAIRO expands autonomous work to non-idempotent internal mutations, those steps must have a replay-safe contract. The smallest acceptable V0 mechanism may use one or more of:

- stable operation/idempotency keys;
- durable step checkpoints written before/after mutation boundaries;
- deterministic lookup of whether an operation already took effect;
- tool-specific deduplication where the underlying system supports it.

The exact mechanism is intentionally not fixed by this ADR. It must be chosen by the smallest next acceptance-driven implementation.

### 4. Do not add an automatic retry engine inside KAIRO

OpenClaw remains the execution runtime and scheduler. KAIRO should not duplicate its retry/session machinery.

KAIRO's responsibility is to make its durable domain transitions and autonomous mutations safe to observe and replay, while preserving an inspectable audit trail.

## Consequences

### Positive

- native OpenClaw interrupted-turn recovery remains usable;
- KAIRO avoids falsely failing work that can still complete safely;
- completed Jobs remain protected from later retry re-entry by lifecycle validation;
- the crash-safety problem is narrowed to the actual side-effect boundary instead of adding broad scheduler machinery;
- the KAIRO/OpenClaw ownership boundary remains intact.

### Negative

- a `running` Job can legitimately remain non-terminal for some time after a crash/restart while runtime recovery settles;
- KAIRO cannot yet safely claim crash-safe replay for arbitrary non-idempotent mutations;
- richer health/debugging will eventually need to expose interrupted/recovering work without pretending to know an unknown outcome.

## Next work

1. define the minimum replay/idempotence/checkpoint contract for KAIRO autonomous steps;
2. add tests around duplicate/replayed operations before enabling non-idempotent autonomous mutations;
3. then implement provider/model/token/tool/cost attribution and hard budget enforcement for KAIRO Jobs;
4. keep crash/recovery behavior covered by live proofs when the pinned OpenClaw runtime changes.
