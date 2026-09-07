# Development runbook — first live KAIRO/OpenClaw proof

## Purpose

The repository now has unit/integration coverage for KAIRO Core, the OpenClaw tool adapter, bounded future-turn scheduling, and the KAIRO-owned Job ledger.

The next meaningful proof is **not more architecture**. It is to run the pinned OpenClaw runtime, load the real KAIRO plugin, use a real model provider, close the client, and verify that a future server-side turn wakes and updates durable KAIRO state.

This runbook is intentionally for an isolated local development runtime. Production/VPS hardening comes after the behavior is proven.

## Safety rules

- Do not put API keys in this repository.
- Do not use the Git checkout as `KAIRO_DATA_DIR` or as the live OpenClaw workspace.
- Keep the Gateway on localhost for this proof; do not expose the OpenClaw administrative surface publicly.
- Use a small test budget and harmless A0-A2 research/internal work only.
- Do not configure social publishing, trading, financial actions, or destructive external tools for this test.

## 1. Prerequisites

OpenClaw's current supported development runtime includes Node 22.22.3+; KAIRO CI uses Node 22.22.3. Git and npm are also required.

From the KAIRO repository root, verify:

```bash
node --version
git --version
npm --version
```

## 2. Create an isolated runtime environment

From the KAIRO repository root:

```bash
source scripts/dev/openclaw-env.sh
```

The helper deliberately places runtime state under `$HOME/.kairo-dev` by default and exports:

- `OPENCLAW_HOME`
- `OPENCLAW_STATE_DIR`
- `OPENCLAW_CONFIG_PATH`
- `OPENCLAW_WORKSPACE_DIR`
- `KAIRO_DATA_DIR`

These locations are outside Git.

## 3. Build and validate the pinned OpenClaw plugin

KAIRO pins OpenClaw `2026.9.2` as the adapter's development dependency.

```bash
cd plugins/openclaw-kairo-tools
npm install --no-audit --no-fund
npm run plugin:build
npm test
npm run plugin:validate
```

All commands must pass before continuing.

For the rest of this runbook, from this directory:

```bash
export OPENCLAW_BIN="$PWD/node_modules/.bin/openclaw"
"$OPENCLAW_BIN" --version
```

Confirm the expected pinned version before touching runtime state.

## 4. Create the OpenClaw baseline

OpenClaw documents `setup --baseline` for creating config/workspace state without running the full onboarding wizard.

```bash
"$OPENCLAW_BIN" setup --baseline
```

Point the default agent at the isolated KAIRO workspace:

```bash
"$OPENCLAW_BIN" config set agents.defaults.workspace "$OPENCLAW_WORKSPACE_DIR"
```

Copy KAIRO's versioned workspace defaults into the live workspace from the repository root:

```bash
cd ../..
cp config/openclaw/workspace-template/AGENTS.md "$OPENCLAW_WORKSPACE_DIR/AGENTS.md"
cp config/openclaw/workspace-template/SOUL.md "$OPENCLAW_WORKSPACE_DIR/SOUL.md"
cp config/openclaw/workspace-template/IDENTITY.md "$OPENCLAW_WORKSPACE_DIR/IDENTITY.md"
cp config/openclaw/workspace-template/USER.template.md "$OPENCLAW_WORKSPACE_DIR/USER.md"
```

`USER.md` is now runtime-private. Edit that live file for test-user preferences if needed; do not copy the personalized version back into Git.

## 5. Install and configure KAIRO Tools

Return to the plugin directory and install the already-built local package through OpenClaw's plugin manager:

```bash
cd plugins/openclaw-kairo-tools
"$OPENCLAW_BIN" plugins install "$PWD" --accept-capabilities
```

Configure the runtime-private KAIRO data path:

```bash
"$OPENCLAW_BIN" config set plugins.entries.kairo-tools.config.dataDir "$KAIRO_DATA_DIR"
"$OPENCLAW_BIN" config validate
```

Inspect the plugin before starting the Gateway:

```bash
"$OPENCLAW_BIN" plugins inspect kairo-tools --runtime --json
```

The tool catalog should include the `kairo_*` tools generated in `openclaw.plugin.json`.

## 6. Configure one real model provider

Use OpenClaw's supported model-auth/configuration flow rather than writing credentials into repository files:

```bash
"$OPENCLAW_BIN" configure
```

For the first proof, one provider is enough. OpenAI + Anthropic routing is a later KAIRO capability; the goal here is to prove the runtime/tool/storage path with minimal variables.

After provider configuration, never commit the resulting OpenClaw auth/state files.

## 7. Start the local Gateway

OpenClaw's local Gateway defaults around port `18789`. For this proof, keep it local:

```bash
"$OPENCLAW_BIN" gateway --port 18789 --verbose
```

In a second terminal, source the same environment helper and use the same local OpenClaw binary, then verify:

```bash
source scripts/dev/openclaw-env.sh
cd plugins/openclaw-kairo-tools
export OPENCLAW_BIN="$PWD/node_modules/.bin/openclaw"
"$OPENCLAW_BIN" health
"$OPENCLAW_BIN" gateway status --require-rpc
```

Do not continue if the health/RPC checks are not healthy.

## 8. Live proof A — durable idea capture

Through the local OpenClaw conversation surface, ask KAIRO to:

1. create project `ZTIKIX`;
2. capture a clearly tentative idea under ZTIKIX;
3. list the ideas;
4. retrieve the new idea.

Then start a **new session** and retrieve it again.

Expected durable state under `$KAIRO_DATA_DIR`:

```text
projects/
  ztikix/
    project.md
    ideas/
      idea_<uuid>.md
```

Verify the Markdown is readable by a human and the tentative statement did not become a decision or fact.

## 9. Live proof B — background wake with durable Job state

Schedule a harmless future task a few minutes ahead, for example:

> For ZTIKIX, in five minutes perform a small public research check, save one genuine source if useful, preserve uncertainty, and return a concise result. Authority A2 only.

KAIRO should return both:

- a KAIRO `job_*` ID;
- an OpenClaw scheduler ID/tag.

Before the scheduled time, inspect the job. It should be `queued` and should retain the scheduler linkage.

Now close the browser/client. **Leave the Gateway process running.**

After the scheduled time, reconnect and verify:

- the future turn actually ran without an open client;
- the Job moved through `running` to `completed` or an explicit `failed` state;
- any saved source is a separate `Source` object;
- any saved conclusion has an explicit epistemic status;
- no A3+ external action occurred;
- the job remains readable from `$KAIRO_DATA_DIR/projects/ztikix/jobs/`.

## 10. Controlled restart proof

The full V0 acceptance criterion also requires safe recovery around runtime restarts.

Do **not** claim this test complete yet merely because a normal scheduled turn works.

The next controlled test is:

1. schedule a future KAIRO job;
2. stop/restart the Gateway before its due time;
3. confirm OpenClaw Cron still owns/reloads the schedule;
4. confirm KAIRO Job state is not lost;
5. confirm the future turn either completes or leaves an explicit state that the reconciler can diagnose.

This test will inform the stale-job reconciliation code rather than assuming its design up front.

## 11. What this runbook does not prove

Even after both live proofs succeed, these remain unfinished:

- hard per-job model-spend enforcement;
- actual provider/token/cost accounting on the Job;
- automatic stale-job reconciliation after crashes;
- production backups/restore;
- remote authentication and HTTPS;
- cross-device PWA;
- model routing;
- social/crypto/voice integrations.

That is intentional. The next code should respond to failures observed in the live proof rather than anticipate every possible infrastructure need.
