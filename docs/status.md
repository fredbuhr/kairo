# KAIRO implementation status

Last updated: 2026-09-08

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
- uses a Gateway-hosted plugin service and OpenClaw Cron access through `ctx.getCron()` for installed-plugin scheduling;
- reconciles future `queued` KAIRO Jobs after OpenClaw Cron reconciliation when their scheduler ID has disappeared, while deliberately leaving `running` Jobs unchanged.

The earlier direct use of `api.session.workflow.scheduleSessionTurn(...)` was removed as the live proof showed that OpenClaw 2026.9.2 only returns a scheduler handle through that helper for bundled plugin origin.

### Automated validation

GitHub Actions validates:

- KAIRO Core tests on Node 22;
- OpenClaw plugin TypeScript build;
- generated plugin metadata consistency;
- adapter/core integration tests;
- OpenClaw plugin validation against the pinned development release;
- packed runtime archive contents, including the advanced entry and bundled KAIRO Core copy.

The Gateway-Cron background path has dedicated tests for successful one-shot scheduling, unavailable Gateway Cron, missing scheduler IDs, and queued-job reconciliation after `cron_reconciled`.

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
- successful post-restart wake and completion of that Job with durable Markdown state intact;
- conservative failure of a future `queued` KAIRO Job when its linked scheduler is missing after Cron reconciliation;
- abrupt `SIGKILL` of the Gateway while a KAIRO Job was already `running`, leaving the durable Job in `running` with no false terminal transition;
- OpenClaw 2026.9.2 recording that interrupted Cron run as `cron: job interrupted by gateway restart` after restart;
- OpenClaw resuming the interrupted agent turn with the missing/interrupted tool result treated as unknown;
- replay of the harmless unknown `sleep 90` step, successful KAIRO completion, a later Cron retry being blocked from re-entering the completed Job, and final one-shot scheduler cleanup.

This constitutes live evidence for the core AT-01 / AT-02 path, the runtime/storage/tool boundary, and the core autonomous execution/restart portion of AT-04.

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

## Abrupt crash / running-job characterization

A separate harmless A2 proof deliberately killed the Gateway with `SIGKILL` while the scheduled turn was already executing `sleep 90`.

Observed behavior on pinned OpenClaw 2026.9.2:

1. `kairo_job_start` had already persisted the KAIRO Job as `running`;
2. the Gateway was killed while the local command was active;
3. the KAIRO Job remained durably `running` after the abrupt process death, with no fabricated completion/failure;
4. after Gateway restart, OpenClaw recorded the original Cron run as interrupted by the restart;
5. OpenClaw resumed the interrupted turn and explicitly treated the missing tool result as unknown;
6. the harmless `sleep 90` step was replayed and completed with exit code 0;
7. `kairo_job_complete` then persisted the Job as `completed`;
8. OpenClaw later retried the one-shot Cron job, but `kairo_job_start` rejected `completed -> running`;
9. the retry inspected the durable Job, did not repeat the work, and the one-shot scheduler was ultimately cleaned up.

This proof changes the crash-recovery design assumption. KAIRO must **not** automatically mark every `running` Job failed merely because the Gateway restarted. OpenClaw can legitimately resume an interrupted turn. The unresolved risk is narrower: a side-effecting step whose tool outcome is unknown may be replayed. KAIRO therefore needs idempotence/checkpoint semantics before autonomous work is allowed to perform non-idempotent internal mutations that cannot safely be retried.

Cron delivery status is also not authoritative for KAIRO work outcome: a Cron run can report a delivery error even when the KAIRO Job itself completed correctly. KAIRO's durable lifecycle remains authoritative for KAIRO completion/failure.

## Acceptance-test assessment

- **AT-01 Durable idea capture:** implemented and live-proven for the current local runtime.
- **AT-02 Epistemic status:** implemented and live-proven for tentative idea capture.
- **AT-03 Critic mode:** not implemented.
- **AT-04 Autonomous overnight job:** core autonomous execution, closed-client wake, controlled restart, and abrupt-crash recovery behavior are live-proven. The full acceptance contract is still incomplete because KAIRO does not yet record provider/model/token/cost/tool accounting, enforce a hard spend ceiling, or expose a dedicated morning-brief/result surface.
- **AT-05 Permission boundary:** A0-A2 background restriction exists; approval-request primitive is not implemented.
- **AT-06 “I don't know”:** policy exists, deterministic acceptance proof still pending.
- **AT-07 Model routing/accounting:** not implemented; a single OpenAI model works live, and OpenClaw run history exposes usage metadata, but KAIRO does not yet persist routing/accounting as its own domain state.
- **AT-08 Multi-project isolation:** filesystem/domain isolation is tested; broader runtime brand/context isolation still needs acceptance proof.
- **AT-09 Portfolio drill-down:** not implemented.
- **AT-10 Human-readable export:** implemented for current durable domain records.
- **AT-11 Health visibility:** OpenClaw health exists; KAIRO-specific health/backup/job summary is not implemented.
- **AT-12 Cross-device state:** not implemented.

## Current development sequence

Highest-priority V0 work after the live autonomy proofs:

1. define and implement the minimum replay/idempotence/checkpoint contract required for crash-safe autonomous steps;
2. provider/model/token/tool/cost attribution on KAIRO Jobs plus hard budget enforcement;
3. Critic mode with linked recommendation/provenance and deterministic “I don't know” acceptance proof;
4. approval-request primitive for authority escalation;
5. portfolio graph/navigation API plus minimal cross-device web surface;
6. KAIRO health + tested backup/restore;
7. repeat the full V0 exit scenario end-to-end.

Still intentionally deferred:

- full Cockpit/PWA and mindmap visualization;
- voice input;
- production VPS deployment/auth/HTTPS;
- social publishing;
- CoinMarketCap/crypto module;
- optional local inference.

## Current engineering rules

- Continue capability-first: implement the smallest capability required by the next failing acceptance test.
- Treat the KAIRO Job ledger as the authoritative KAIRO work lifecycle; do not infer KAIRO failure from delivery-only Cron errors.
- Preserve OpenClaw's native interrupted-turn recovery; do not auto-fail every `running` Job on Gateway restart.
- Treat missing/interrupted tool results after a crash as unknown, never as success.
- Require replay-safe/idempotent semantics before expanding autonomous work to non-idempotent mutations.
- Let observed runtime failures drive reconciliation and infrastructure work rather than adding speculative machinery.
