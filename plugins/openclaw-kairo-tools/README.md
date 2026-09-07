# KAIRO OpenClaw Tools

This package is the runtime adapter between OpenClaw and KAIRO Core.

The model never writes KAIRO Markdown files directly. Durable writes go through `@kairo/core`, which owns validation, IDs, project isolation, provenance fields, storage rules, replay-safety checkpoints, and the KAIRO-owned autonomous-job ledger.

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
- `kairo_job_step_begin`
- `kairo_job_step_complete`
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
    -> KAIRO Gateway service -> OpenClaw Cron
    -> link Cron scheduler ID/tag (queued)
      -> Cron-owned future agentTurn
        -> kairo_job_start (running)
        -> pure reads / replay-safe computation
        -> kairo_job_step_begin before replay-sensitive mutation
        -> guarded mutation
        -> kairo_job_step_complete after confirmed success
        -> kairo_job_complete / kairo_job_fail
```

This separates **KAIRO-owned audit/replay state** from **OpenClaw-owned wake-up/runtime state**.

The runtime package uses an advanced `definePluginEntry` wrapper to register the Gateway service while preserving the stable tool declarations and generated metadata from the existing `defineToolPlugin` tool contract.

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

The installed plugin does not call OpenClaw's bundled-only `scheduleSessionTurn` host helper directly. OpenClaw 2026.9.2 returns no handle from that helper for an external plugin origin. Instead, KAIRO registers a Gateway-hosted service, obtains the active scheduler through `ctx.getCron()`, and creates a one-shot Cron `agentTurn` bound to the originating session.

Before scheduling, KAIRO creates a durable `Job`. A successful OpenClaw Cron ID is attached to that job. Scheduling errors are recorded as failed KAIRO jobs. If scheduler creation succeeds but KAIRO cannot link the scheduler state, the adapter attempts best-effort compensation by removing the newly created Cron job.

### Replay-safety checkpoints

A real `SIGKILL` proof on OpenClaw 2026.9.2 showed that an interrupted agent turn may resume after Gateway restart and that a tool result interrupted by the crash is treated as **unknown**. A harmless `sleep 90` step was replayed during that proof. KAIRO therefore does not blanket-fail every `running` Job on restart.

For a replay-sensitive internal mutation, the scheduled turn must use a stable two-phase checkpoint:

1. call `kairo_job_step_begin` immediately before the mutation;
2. if it returns `started`, perform the mutation;
3. after confirmed success, call `kairo_job_step_complete` with the same `stepKey`;
4. if a retry receives `already_completed`, skip the mutation;
5. if a retry receives `already_started`, the prior mutation outcome is unknown — verify deterministically if possible, otherwise stop/fail explicitly rather than repeating the mutation blindly.

`kairo_job_complete` rejects completion while any execution checkpoint remains `started`. Pure reads and replay-safe deterministic computation do not need checkpoints.

These checkpoints make uncertainty durable and visible. They do **not** prove that an arbitrary external side effect is idempotent; tool-specific deduplication or deterministic effect verification is still required before KAIRO can safely broaden autonomous mutation scope.

### Known V0 limitations

The durable wake/restart/crash path is now characterized, but important gaps remain before the full AT-04 contract is complete:

1. **Hard model-cost enforcement:** a requested budget is recorded with `budget_enforced: false`; the future model router/accounting layer must enforce and record actual spend.
2. **KAIRO-owned usage accounting:** provider/model/token/tool/cost metadata is not yet persisted on the KAIRO Job, even though OpenClaw run history exposes some usage data.
3. **Replay-safe side effects:** generic KAIRO checkpoints expose unknown outcomes and prevent blind replay, but each non-idempotent tool/mutation still needs a deterministic or provider-supported deduplication contract.
4. **Morning result surface:** there is no dedicated KAIRO morning-brief/result aggregation surface yet.

Queued-job reconciliation is implemented after OpenClaw `cron_reconciled` for future queued Jobs whose linked scheduler disappeared. `running` Jobs are deliberately left to native interrupted-turn recovery rather than blanket-failed.

KAIRO must not describe an advisory budget as guaranteed, an unknown mutation as successful, or a delivery-only Cron error as a KAIRO work failure.

## Research-memory rules

Background research can persist two different things:

- a `Source` — evidence/locator such as a URL, document, or dataset;
- a `KnowledgeClaim` — one discrete claim with an explicit epistemic state.

A source is not itself a fact, and a knowledge claim marked `hypothesis` or `deduction` must not silently become `fact`.

## Development

Requirements follow the pinned OpenClaw plugin contracts:

- Node 22.22.3+ runtime;
- OpenClaw 2026.9.2 pinned for development/validation;
- TypeScript ESM output;
- generated `openclaw.plugin.json` manifest;
- packed runtime archive for local installed-plugin testing.

From this directory:

```bash
npm install
npm run plugin:build
npm test
npm run plugin:validate
npm run plugin:pack
```

`plugin:build` generates metadata from `dist/entry.js`. The entry preserves the tool-plugin metadata used by OpenClaw's manifest generator while adding the Gateway service needed for external-plugin Cron access.

## Manual vertical slices

### Durable idea capture

1. Ask KAIRO to create a project named `ZTIKIX`.
2. Ask KAIRO to record a tentative idea in ZTIKIX.
3. Confirm the idea is stored as an `idea`, not a `decision` or `fact`.
4. Start a later OpenClaw turn/session.
5. Ask KAIRO to list/retrieve the idea.
6. Confirm the original idea and provenance remain available from the same server-side KAIRO store.

This path has been demonstrated on the isolated local runtime.

### Future background job

1. In an active OpenClaw session, ask KAIRO to schedule bounded internal/research work for a future absolute time.
2. Confirm KAIRO returns both a `job_*` ID and a real OpenClaw Cron scheduler ID/tag.
3. Confirm the durable Job is `queued` before closing the client.
4. Close all clients while leaving the Gateway process running.
5. At the scheduled time, the server should start the future agent turn and mark the KAIRO Job running.
6. Before any replay-sensitive KAIRO mutation, confirm the turn begins a stable execution checkpoint and completes that checkpoint only after confirmed success.
7. Reconnect and confirm the Job record, checkpoints, evidence, findings, and outcome are durable.
8. Confirm no A3+ external action was performed.
9. Repeat with a controlled Gateway restart before the due time.

The closed-client, controlled-restart, and harmless abrupt-crash runtime paths have been demonstrated. The next live checkpoint proof should verify that a deliberately unresolved `started` execution checkpoint survives restart and prevents blind replay/job completion.
