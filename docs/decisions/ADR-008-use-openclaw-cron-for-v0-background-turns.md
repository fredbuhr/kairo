# ADR-008 — Use OpenClaw Cron-backed session turns for V0 background work

## Status

Accepted for V0 runtime wake proof.

## Context

KAIRO must continue approved work after every phone/browser client is closed. Rebuilding a scheduler, queue, wake-up service, and session-resumption layer inside KAIRO would add substantial infrastructure before the core usage pattern is proven.

OpenClaw's plugin API already exposes `api.session.workflow.scheduleSessionTurn(...)`. The host delegates timing to its Cron subsystem and can create a future agent turn bound to the current session. The call supports one-shot absolute times, delayed execution, recurring cron schedules, agent selection, delivery mode, names, tags, and cleanup behavior.

This is sufficient to test the most important runtime property: the server can wake an agent later without an active client.

## Decision

Use OpenClaw's Cron-backed `scheduleSessionTurn` API for the first KAIRO background-work capability.

The KAIRO tool is intentionally narrower than the underlying OpenClaw API:

- V0 exposes only one-shot absolute schedules;
- timestamps must include an explicit UTC offset or `Z`;
- scheduled work is limited to authority A0-A2;
- A3+ publishing, messaging, financial, destructive, or external-system changes are forbidden by the scheduled-turn contract;
- the project must already exist in KAIRO before background work is scheduled;
- the future turn is instructed to preserve epistemic status and use KAIRO source/knowledge tools for durable research findings;
- one-shot jobs request `deleteAfterRun: true`;
- result announcement can be disabled, but defaults to the originating session route.

## Important limitation

This decision proves **runtime wake-up**, not the complete KAIRO autonomous-job model.

V0 still needs a first-class KAIRO `Job` record that can link:

- the user/task intent;
- authority ceiling;
- requested/actual cost;
- OpenClaw scheduler handle/tag;
- start/end/failure state;
- models and tools used;
- produced artefacts;
- approvals and retries.

Likewise, an LLM budget mentioned in natural language is not a hard technical cost ceiling until KAIRO's model router and accounting layer enforce it.

## Consequences

### Positive

- validates background execution without introducing Redis, Celery, n8n, or a custom scheduler;
- uses a host-owned lifecycle already designed to survive closed clients;
- keeps KAIRO focused on domain state, policy, and auditability;
- preserves a future path to recurring standing orders.

### Negative

- KAIRO is temporarily dependent on OpenClaw Cron semantics for wake-up;
- scheduler state and KAIRO domain state are not yet transactionally linked;
- completion/failure reconciliation is still incomplete;
- hard per-job model-spend enforcement remains pending.

## Revisit when

- first-class KAIRO Job persistence is implemented;
- KAIRO needs schedules independent of OpenClaw sessions;
- a future runtime replaces OpenClaw;
- Cron lifecycle limitations prevent reliable execution or reconciliation.
