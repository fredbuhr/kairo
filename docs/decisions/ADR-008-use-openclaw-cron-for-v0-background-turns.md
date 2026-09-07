# ADR-008 — Use OpenClaw Cron for V0 background work

## Status

Accepted for V0 runtime wake proof; amended after the first live external-plugin test on 2026-09-07.

## Context

KAIRO must continue approved work after every phone/browser client is closed. Rebuilding a scheduler, queue, wake-up service, and session-resumption layer inside KAIRO would add substantial infrastructure before the core usage pattern is proven.

OpenClaw already owns a persistent Cron subsystem capable of creating future agent turns bound to sessions. This is sufficient to test the most important runtime property: the server can wake an agent later without an active client.

The initial KAIRO adapter used `api.session.workflow.scheduleSessionTurn(...)`. Unit tests passed, but the first live installed-plugin proof exposed an important OpenClaw 2026.9.2 constraint: the host implementation returns no scheduler handle for a non-bundled plugin origin. KAIRO therefore persisted the attempted Job as `failed`, which was the correct fail-closed behavior, but no Cron job was created.

OpenClaw 2026.9.2 also exposes Gateway-owned Cron access to long-lived plugin services through `ctx.getCron()`. That service surface supports scheduler `list`, `add`, `update`, and `remove` operations and is available to a loaded external plugin running inside the Gateway.

## Decision

Continue using **OpenClaw Cron** for the first KAIRO background-work capability, but integrate through a Gateway-hosted KAIRO plugin service rather than the bundled-only session-workflow helper.

The KAIRO plugin uses an advanced `definePluginEntry` runtime entry which:

- preserves the existing stable `kairo_*` tool catalog;
- registers a small Gateway service with `api.registerService(...)`;
- obtains the current Cron capability from `ctx.getCron()` only while that service is active;
- creates one-shot Cron `agentTurn` jobs bound to the originating session;
- records the returned Cron job ID in the KAIRO-owned Job ledger;
- fails closed if the Gateway Cron service is absent or does not return a scheduler ID;
- removes the Cron job on best-effort compensation if KAIRO cannot finish linking the durable scheduler state.

The KAIRO tool remains intentionally narrower than the underlying OpenClaw Cron API:

- V0 exposes only one-shot absolute schedules;
- timestamps must include an explicit UTC offset or `Z`;
- scheduled work is limited to authority A0-A2;
- A3+ publishing, messaging, financial, destructive, or external-system changes are forbidden by the scheduled-turn contract;
- the project must already exist in KAIRO before background work is scheduled;
- the future turn is instructed to preserve epistemic status and use KAIRO source/knowledge tools for durable research findings;
- one-shot jobs request deletion after execution;
- result announcement can be disabled, but defaults to the originating session route.

No CLI subprocess, custom queue, scheduler bypass, or OpenClaw fork is introduced.

## Compatibility note

OpenClaw's plugin SDK is experimental and KAIRO pins OpenClaw 2026.9.2 for this adapter. In that release, the public Gateway-service Cron create type is narrower than the runtime Cron normalizer used by OpenClaw's own session-turn scheduler. KAIRO keeps the necessary compatibility cast inside one adapter boundary and tests the actual one-shot `at` + `agentTurn` shape. This boundary must be revalidated before upgrading OpenClaw.

## Important limitation

This decision proves **runtime wake-up**, not the complete KAIRO autonomous-job model.

KAIRO already owns a first-class Job record linking user/task intent, authority ceiling, requested budget, scheduler state, execution lifecycle, and outcome. The following remain incomplete:

- actual provider/model/token/cost accounting on each job;
- hard model-spend enforcement;
- automatic stale queued/running Job reconciliation after crashes;
- richer produced-artefact and approval linkage.

An LLM budget mentioned in natural language remains advisory until KAIRO's accounting/router layer enforces it technically.

## Consequences

### Positive

- validates background execution without introducing Redis, Celery, n8n, or a custom scheduler;
- uses the Gateway-owned scheduler lifecycle already designed to survive closed clients;
- keeps KAIRO focused on domain state, policy, and auditability;
- preserves a future path to recurring standing orders;
- the live failure is now represented by a regression test instead of an architectural assumption.

### Negative

- KAIRO is temporarily dependent on OpenClaw Cron semantics for wake-up;
- the external-plugin integration uses an experimental SDK surface and must remain version-pinned/tested;
- scheduler state and KAIRO domain state are not transactionally linked;
- completion/failure reconciliation is still incomplete;
- hard per-job model-spend enforcement remains pending.

## Revisit when

- the live background-wake and controlled-restart proofs are complete;
- KAIRO needs schedules independent of OpenClaw sessions;
- a future runtime replaces OpenClaw;
- Cron lifecycle limitations prevent reliable execution or reconciliation.
