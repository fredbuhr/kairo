# KAIRO implementation status

Last updated: 2026-09-07

This document describes what exists in code and what has been demonstrated live. It is intentionally stricter than the long-term roadmap.

## Implemented and versioned

### Product / architecture

- vision, non-goals, and portability principles;
- OpenClaw selected as V0 execution runtime without forking it;
- KAIRO Core remains runtime/provider independent;
- human-readable Markdown-first durable knowledge;
- authority model A0-A5;
- explicit epistemic states;
- V0 acceptance tests and staged roadmap.

### KAIRO Core

Durable project-scoped domain state currently includes:

- Projects and parent relationships;
- Ideas;
- Decisions;
- Tasks with owner/authority/budget fields;
- KnowledgeClaims with epistemic status/confidence/source IDs;
- Sources;
- KAIRO Jobs with lifecycle state and scheduler linkage.

Storage is a filesystem/Markdown V0 adapter with stable IDs and atomic writes. No database has been selected yet.

### OpenClaw adapter

The validated `kairo-tools` plugin exposes tools for:

- project create/list/get;
- idea capture/list/get;
- source capture/get;
- knowledge-claim capture/get;
- job list/get/start/complete/fail;
- bounded future background scheduling.

Background scheduling:

- creates a durable KAIRO Job before external scheduling;
- links the OpenClaw scheduler ID/tag to the KAIRO Job;
- records scheduler failure durably;
- limits V0 background authority to A0-A2;
- instructs the future turn to use explicit Job lifecycle calls;
- supports an advisory requested model budget but does not hard-enforce it yet;
- uses a Gateway-hosted plugin service and OpenClaw Cron access through `ctx.getCron()` for installed-plugin scheduling.

The earlier direct use of `api.session.workflow.scheduleSessionTurn(...)` was removed as the live proof showed that OpenClaw 2026.9.2 only returns a scheduler handle through that helper for bundled plugin origin.

### Automated validation

GitHub Actions validates:

- KAIRO Core tests on Node 22;
- OpenClaw plugin TypeScript build;
- generated plugin metadata consistency;
- adapter/core integration tests;
- OpenClaw plugin validation against the pinned development release;
- packed runtime archive contents, including the advanced entry and bundled KAIRO Core copy.

The Gateway-Cron background path has dedicated tests for successful one-shot scheduling, unavailable Gateway Cron, and missing scheduler IDs.

## Proven live locally

An isolated Ubuntu 24.04 / WSL2 runtime has demonstrated:

- Node 22.22.3 and pinned OpenClaw 2026.9.2;
- KAIRO plugin installation from a reviewed packed archive;
- plugin activation with the full stable `kairo_*` catalog;
- an isolated runtime workspace and KAIRO data directory outside Git;
- a real OpenAI API model call through the local OpenClaw Gateway;
- durable creation of project `ZTIKIX` through `kairo_project_create`;
- retrieval of the same project on a later agent turn;
- durable idea capture under the correct project;
- preservation of the tentative idea as `type: idea` with `epistemic_status: hypothesis`;
- human-readable Markdown persistence without accidental decision/knowledge promotion;
- a real future A2 KAIRO Job queued with an OpenClaw Cron scheduler ID;
- execution of that Job after the initiating client disconnected while the Gateway remained running;
- explicit Job lifecycle transition from `queued` to `running` to `completed`;
- one-shot Cron cleanup after completion;
- survival of a second queued Job across a controlled Gateway stop/restart;
- reload of the exact same scheduler ID after Gateway restart;
- successful post-restart wake and completion of that Job with durable Markdown state intact.

This constitutes live evidence for the core AT-01 / AT-02 path, the runtime/storage/tool boundary, and the AT-04 autonomous background/restart path.

## Live background-wake proof

The first real call to `kairo_background_schedule` intentionally failed closed:

- KAIRO created the durable Job first;
- OpenClaw returned no scheduler handle from the bundled-only session-workflow helper;
- KAIRO marked the Job `failed` with the concrete scheduler reason;
- Gateway logs confirmed Cron itself was healthy but no KAIRO Cron job had been added.

That observed failure drove the Gateway-service Cron adapter now merged on `main`.

The corrected path was then demonstrated live with a harmless A2 ZTIKIX job:

1. KAIRO created the Job first and persisted it as `queued`;
2. OpenClaw Cron returned a real scheduler ID and tag, both stored durably on the Job;
3. Gateway logs showed the matching `cron: job added` event;
4. the initiating client disconnected while the Gateway remained running;
5. the future turn woke at the scheduled time, called `kairo_job_start`, performed the bounded internal work, and called `kairo_job_complete`;
6. the Job persisted `started_at`, `completed_at`, and a concise completion summary;
7. the one-shot scheduler disappeared from `openclaw cron list` after execution.

A separate controlled-restart proof then demonstrated:

1. a new future KAIRO Job was queued with a distinct real Cron scheduler ID;
2. the Gateway was stopped before the due time;
3. after restart, `openclaw cron list` showed the same scheduler ID still present and idle;
4. at the due time, the future turn woke and completed successfully;
5. the KAIRO Job retained the same scheduler linkage and durable lifecycle state throughout.

The live proof therefore establishes the intended V0 property: closing the client does not stop approved background work, and queued work survives a controlled OpenClaw Gateway restart.

## Acceptance-test assessment

- **AT-01 Durable idea capture:** implemented and live-proven for the current local runtime.
- **AT-02 Epistemic status:** implemented and live-proven for tentative idea capture.
- **AT-03 Critic mode:** not implemented.
- **AT-04 Autonomous overnight job:** implemented and live-proven for closed-client execution plus controlled Gateway restart recovery.
- **AT-05 Permission boundary:** A0-A2 background restriction exists; approval-request primitive is not implemented.
- **AT-06 “I don't know”:** policy exists, deterministic acceptance proof still pending.
- **AT-07 Model routing/accounting:** not implemented; a single OpenAI model works live, but routing and per-run accounting do not.
- **AT-08 Multi-project isolation:** filesystem/domain isolation is tested; broader runtime brand/context isolation still needs acceptance proof.
- **AT-09 Portfolio drill-down:** not implemented.
- **AT-10 Human-readable export:** implemented for current durable domain records.
- **AT-11 Health visibility:** OpenClaw health exists; KAIRO-specific health/backup/job summary is not implemented.
- **AT-12 Cross-device state:** not implemented.

## Explicitly unfinished

Highest-priority V0 work after the AT-04 live proof:

1. stale queued/running Job reconciliation for unclean crashes and interrupted runs;
2. provider/model/token/cost attribution and hard budget enforcement;
3. Critic mode with linked recommendation/provenance;
4. approval-request primitive for authority escalation;
5. portfolio graph/navigation API;
6. KAIRO health + tested backup/restore;
7. minimal cross-device surface required by the V0 exit scenario.

Still intentionally deferred:

- full Cockpit/PWA and mindmap visualization;
- voice input;
- production VPS deployment/auth/HTTPS;
- social publishing;
- CoinMarketCap/crypto module;
- optional local inference.

## Current engineering rule

AT-04 is now live-proven. Continue capability-first: implement the smallest capability required by the next failing acceptance test, and let observed runtime failures drive reconciliation and infrastructure work rather than adding speculative machinery.
