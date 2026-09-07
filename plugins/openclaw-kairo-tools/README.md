# KAIRO OpenClaw Tools

This package is the runtime adapter between OpenClaw and KAIRO Core.

The model never writes KAIRO Markdown files directly. Durable writes go through `@kairo/core`, which owns validation, IDs, project isolation, provenance fields, storage rules, and the KAIRO-owned autonomous-job ledger.

## Current V0 tool surface

Projects and ideas:

- `kairo_project_create`
- `kairo_project_list`
- `kairo_project_get`
- `kairo_idea_capture`
- `kairo_idea_list`
- `kairo_idea_get`

Research memory:

- `kairo_source_capture`
- `kairo_source_get`
- `kairo_knowledge_capture`
- `kairo_knowledge_get`

Durable job state:

- `kairo_job_list`
- `kairo_job_get`
- `kairo_job_start`
- `kairo_job_complete`
- `kairo_job_fail`

Bounded background execution:

- `kairo_background_schedule`

## Why this boundary matters

```text
model
  -> OpenClaw
    -> KAIRO tool
      -> KAIRO Core
        -> durable Markdown / job ledger
```

OpenClaw may be replaced in the future without changing the KAIRO domain data contract or losing KAIRO's execution history.

For background execution the V0 path is:

```text
current OpenClaw session
  -> kairo_background_schedule
    -> create KAIRO Job (scheduling)
    -> OpenClaw session.workflow.scheduleSessionTurn
    -> link scheduler handle (queued)
      -> Cron-owned future agent turn
        -> kairo_job_start (running)
        -> KAIRO tools + ordinary OpenClaw research tools
        -> kairo_job_complete / kairo_job_fail
```

This separates **KAIRO-owned audit state** from **OpenClaw-owned wake-up/runtime state**.

## Runtime configuration

The plugin requires one setting: an **absolute** runtime-private data path.

Example OpenClaw configuration fragment:

```json5
{
  plugins: {
    entries: {
      "kairo-tools": {
        enabled: true,
        config: {
          dataDir: "/var/lib/kairo/data"
        }
      }
    }
  }
}
```

Do not point `dataDir` inside the Git repository for a real deployment.

## Background-work safety in V0

`kairo_background_schedule` deliberately accepts only authority ceilings **A0, A1, or A2**.

A scheduled turn is explicitly instructed not to:

- publish content;
- send messages;
- purchase anything;
- trade or move financial assets;
- delete external data;
- modify external systems.

If the work requires more authority, the future turn must stop and report the limitation.

The scheduler uses OpenClaw's Cron-backed `scheduleSessionTurn` API and can announce the result back to the originating session route.

Before scheduling, KAIRO creates a durable `Job`. A successful OpenClaw scheduler handle is attached to that job. Scheduling errors are recorded as failed KAIRO jobs. If scheduler creation succeeds but KAIRO cannot link the handle, the adapter attempts best-effort unscheduling by tag.

### Known V0 limitations

The job ledger is now durable, but two important gaps remain before AT-04 is complete:

1. **Hard model-cost enforcement:** a requested budget is recorded with `budget_enforced: false`; the future model router/accounting layer must enforce and record actual spend.
2. **Crash/restart reconciliation:** a future agent turn is instructed to mark the job running/completed/failed, but a process crash can still leave a stale queued/running record. A health reconciler must detect this condition against OpenClaw scheduler/task state.

KAIRO must not describe an advisory budget as guaranteed or a stale job as successfully completed.

## Research-memory rules

Background research can persist two different things:

- a `Source` — evidence/locator such as a URL, document, or dataset;
- a `KnowledgeClaim` — one discrete claim with an explicit epistemic state.

A source is not itself a fact, and a knowledge claim marked `hypothesis` or `deduction` must not silently become `fact`.

## Development

Requirements follow OpenClaw's current tool-plugin contract:

- supported Node 22+ runtime;
- OpenClaw pinned for development/validation;
- TypeScript ESM output;
- generated `openclaw.plugin.json` manifest.

From this directory:

```bash
npm install
npm run plugin:build
npm test
npm run plugin:validate
```

The build step uses OpenClaw's supported `defineToolPlugin` API and manifest generator.

## Manual vertical slices

### Durable idea capture

1. Ask KAIRO to create a project named `ZTIKIX`.
2. Ask KAIRO to record a tentative idea in ZTIKIX.
3. Confirm the idea is stored as an `idea`, not a `decision` or `fact`.
4. Start a new OpenClaw session.
5. Ask KAIRO to list/retrieve the idea.
6. Confirm the original idea and provenance remain available from the same server-side KAIRO store.

### Future background job

1. In an active OpenClaw session, ask KAIRO to schedule bounded research for a future absolute time.
2. Confirm KAIRO returns both a `job_*` ID and an OpenClaw scheduler ID.
3. Close all clients.
4. At the scheduled time, the server should start the future agent turn and mark the KAIRO job running.
5. The turn may research, save sources/claims through KAIRO tools, and mark the job completed/failed.
6. Reconnect and confirm the job record, evidence, findings, and outcome are durable.
7. Confirm no A3+ external action was performed.

This is close to the full AT-04 path, but the crash reconciler and hard budget enforcement are still explicit exit requirements.
