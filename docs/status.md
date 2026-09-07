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
- OpenClaw plugin validation against the pinned development release.

The Gateway-Cron background path has dedicated tests for successful one-shot scheduling, unavailable Gateway Cron, and missing scheduler IDs.

## Proven live locally

An isolated Ubuntu 24.04 / WSL2 runtime has demonstrated:

- Node 22.22.3 and pinned OpenClaw 2026.9.2;
- KAIRO plugin installation from a security-scanned packed archive;
- plugin activation with the full stable `kairo_*` catalog;
- an isolated runtime workspace and KAIRO data directory outside Git;
- a real OpenAI API model call through the local OpenClaw Gateway;
- durable creation of project `ZTIKIX` through `kairo_project_create`;
- retrieval of the same project on a later agent turn;
- durable idea capture under the correct project;
- preservation of the tentative idea as `type: idea` with `epistemic_status: hypothesis`;
- human-readable Markdown persistence without accidental decision/knowledge promotion.

This constitutes live evidence for the core AT-01 / AT-02 path and the runtime/storage/tool boundary.

## Live background-wake proof: current state

The first real call to `kairo_background_schedule` intentionally failed closed:

- KAIRO created the durable Job first;
- OpenClaw returned no scheduler handle from the bundled-only session-workflow helper;
- KAIRO marked the Job `failed` with the concrete scheduler reason;
- Gateway logs confirmed Cron itself was healthy but no KAIRO Cron job had been added.

That observed failure drove the current Gateway-service Cron adapter. The next mandatory live proof is therefore:

1. install the corrected packed KAIRO plugin and restart the local Gateway;
2. schedule a harmless A2 KAIRO background job a few minutes ahead;
3. confirm the Job is `queued` and stores the real OpenClaw Cron ID/tag;
4. close the client while leaving the Gateway running;
5. confirm the future turn wakes and moves the Job through `running` to `completed` or an explicit `failed` state;
6. verify any research source/claim is stored with provenance and epistemic status;
7. repeat around a controlled Gateway restart.

Do not claim AT-04 complete until both normal closed-client wake and controlled-restart behavior are demonstrated.

## Acceptance-test assessment

- **AT-01 Durable idea capture:** implemented and live-proven for the current local runtime.
- **AT-02 Epistemic status:** implemented and live-proven for tentative idea capture.
- **AT-03 Critic mode:** not implemented.
- **AT-04 Autonomous overnight job:** Job ledger implemented; live wake/restart proof still pending.
- **AT-05 Permission boundary:** A0-A2 background restriction exists; approval-request primitive is not implemented.
- **AT-06 “I don't know”:** policy exists, deterministic acceptance proof still pending.
- **AT-07 Model routing/accounting:** not implemented; a single OpenAI model works live, but routing and per-run accounting do not.
- **AT-08 Multi-project isolation:** filesystem/domain isolation is tested; broader runtime brand/context isolation still needs acceptance proof.
- **AT-09 Portfolio drill-down:** not implemented.
- **AT-10 Human-readable export:** implemented for current durable domain records.
- **AT-11 Health visibility:** OpenClaw health exists; KAIRO-specific health/backup/job summary is not implemented.
- **AT-12 Cross-device state:** not implemented.

## Explicitly unfinished

Highest-priority V0 work after the live background wake succeeds:

1. controlled-restart/stale-job reconciliation;
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

Do not implement the Cockpit or add unrelated infrastructure before the corrected background-wake path is proven live. After that, implement the smallest capability required by the next failing acceptance test.
