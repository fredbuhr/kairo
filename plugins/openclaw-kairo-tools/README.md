# KAIRO OpenClaw Tools

This package is the runtime adapter between OpenClaw and KAIRO Core.

The model never writes KAIRO Markdown files directly. Durable writes go through `@kairo/core`, which owns validation, IDs, project isolation, provenance fields, and storage rules.

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

Bounded background execution:

- `kairo_background_schedule`

## Why this boundary matters

```text
model
  -> OpenClaw
    -> KAIRO tool
      -> KAIRO Core
        -> durable Markdown store
```

OpenClaw may be replaced in the future without changing the KAIRO domain data contract.

For background execution the V0 path is:

```text
current OpenClaw session
  -> kairo_background_schedule
    -> OpenClaw session.workflow.scheduleSessionTurn
      -> Cron-owned future agent turn
        -> KAIRO tools + ordinary OpenClaw research tools
```

This proves that work can be scheduled server-side without keeping a browser or phone client open. It is not yet the complete KAIRO autonomous-job model.

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

The scheduler currently uses OpenClaw's Cron-backed `scheduleSessionTurn` API and can announce the result back to the originating session route.

### Known V0 limitation

KAIRO does **not** yet persist a first-class KAIRO `Job` linked to the OpenClaw scheduler handle, and the requested model-spend budget is not yet a hard technical ceiling. Those are required before claiming the full autonomous-job acceptance test is complete.

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

### Future background turn

1. In an active OpenClaw session, ask KAIRO to schedule bounded research for a future absolute time.
2. Confirm OpenClaw returns a Cron scheduler handle.
3. Close all clients.
4. At the scheduled time, the server should start the future agent turn.
5. The turn may research, save sources/claims through KAIRO tools, and announce a completion report.
6. Confirm no A3+ external action was performed.

The second flow is a runtime wake proof, not yet the full AT-04 durable-job proof.
