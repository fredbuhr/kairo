# Development runbook — first live KAIRO/OpenClaw proof

## Purpose

The repository has unit/integration coverage for KAIRO Core, the OpenClaw tool adapter, the KAIRO-owned Job ledger, secure packed-plugin installation, and the Gateway-Cron background scheduling path.

The local live proof has demonstrated the real model → OpenClaw → KAIRO tool → durable Markdown path for project and tentative-idea capture, plus a corrected future server-side turn that wakes without an active client and survives a controlled Gateway restart.

This runbook records how to reproduce those proofs in an isolated local development runtime. Production/VPS hardening comes after the behavior is proven.

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

## 5. Pack, install, and configure KAIRO Tools

OpenClaw 2026.9.2 scans plugin dependency boundaries. Installing the development checkout directly is rejected because npm represents the local `@kairo/core` dependency as a symlink outside the plugin root.

Use KAIRO's pack script. It builds the advanced runtime entry and creates a self-contained archive whose installed `@kairo/core` is a real package copy rather than an external symlink:

```bash
cd plugins/openclaw-kairo-tools
npm run plugin:pack
PKG=$(ls -1t kairo-openclaw-tools-*.tgz | head -1)
tar -tzf "$PKG" | grep 'node_modules/@kairo/core'
tar -xOf "$PKG" package/package.json | grep -A3 '"dependencies"'
```

Before continuing, verify:

- real files exist under `package/node_modules/@kairo/core/`;
- the packed `package.json` uses a normal version such as `"@kairo/core": "0.1.0"`, not `file:../../packages/kairo-core`;
- `package/dist/entry.js` and `package/openclaw.plugin.json` are present.

For a first install of this reviewed local archive:

```bash
"$OPENCLAW_BIN" plugins install "$PWD/$PKG" --accept-capabilities
```

If `kairo-tools` is already installed from an earlier local archive, intentionally replace that managed install with the newly reviewed archive:

```bash
"$OPENCLAW_BIN" plugins install "$PWD/$PKG" --force --accept-capabilities
```

In OpenClaw 2026.9.2, `--force` confirms/replaces an already installed arbitrary local source; it does **not** bypass install policy or the code safety scan.

Configure the runtime-private KAIRO data path and enable the plugin:

```bash
"$OPENCLAW_BIN" config set plugins.entries.kairo-tools.config.dataDir "$KAIRO_DATA_DIR"
"$OPENCLAW_BIN" plugins enable kairo-tools
"$OPENCLAW_BIN" config validate
```

Inspect the plugin before starting the Gateway:

```bash
"$OPENCLAW_BIN" plugins inspect kairo-tools --runtime --json
```

The runtime source must resolve to the packed advanced entry (`dist/entry.js`), the plugin must be loaded/enabled, the `kairo-tools-cron` service must be registered, and the tool catalog must still include all stable `kairo_*` tools.

## 6. Configure one real model provider

Use OpenClaw's supported model-auth/configuration flow rather than writing credentials into repository files:

```bash
"$OPENCLAW_BIN" configure
```

For the first proof, one provider is enough. OpenAI + Anthropic routing is a later KAIRO capability; the goal here is to prove the runtime/tool/storage path with minimal variables.

After provider configuration, never commit the resulting OpenClaw auth/state files.

## 7. Start the local Gateway

Keep the Gateway local:

```bash
"$OPENCLAW_BIN" gateway --port 18789 --verbose
```

In a second terminal, source the same environment helper and use the same local OpenClaw binary, then verify:

```bash
cd ~/kairo
source scripts/dev/openclaw-env.sh
export OPENCLAW_BIN="$HOME/kairo/plugins/openclaw-kairo-tools/node_modules/.bin/openclaw"
"$OPENCLAW_BIN" health
```

The Gateway process must remain running for the normal closed-client wake proof.

## 8. Live proof A — durable idea capture

This path has already been demonstrated in the first local proof. To repeat it from a clean data directory, ask KAIRO to:

1. create project `ZTIKIX`;
2. capture a clearly tentative idea under ZTIKIX;
3. list the ideas;
4. retrieve the new idea;
5. retrieve it again on a later agent turn without recreating it.

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

This path has been demonstrated successfully with the Gateway-Cron adapter. To reproduce it, schedule a harmless future task a few minutes ahead, for example:

> For ZTIKIX, in five minutes re-read the existing tentative sticker idea, produce a concise internal summary, preserve uncertainty, take no external action, and complete the KAIRO Job. Authority A2 only.

KAIRO must return both:

- a KAIRO `job_*` ID;
- a real OpenClaw Cron scheduler ID/tag.

**Stop immediately if the scheduler ID is missing.** Do not wait and do not treat a KAIRO Job alone as evidence that background work was scheduled.

Before the scheduled time, inspect the Job Markdown. It must be `queued` and retain the scheduler linkage.

Also verify the Gateway log contains a corresponding `cron: job added` event with the same scheduler ID. This is important because the first live attempt exposed a bundled-only OpenClaw helper that returned no handle and created no Cron job.

Now close the browser/client. **Leave the Gateway process running.**

After the scheduled time, reconnect and verify:

- the future turn actually ran without an open client;
- the Job moved through `running` to `completed` or an explicit `failed` state;
- any saved source is a separate `Source` object;
- any saved conclusion has an explicit epistemic status;
- no A3+ external action occurred;
- the Job remains readable from `$KAIRO_DATA_DIR/projects/ztikix/jobs/`.

For a one-shot success, also run:

```bash
"$OPENCLAW_BIN" cron list
```

and confirm the completed scheduler ID is no longer present.

The first corrected live proof completed successfully and the one-shot scheduler was removed after execution.

## 10. Controlled restart proof

This path has also been demonstrated successfully. To reproduce it:

1. schedule a new future KAIRO Job several minutes ahead;
2. confirm the Job is `queued` and linked to a real Cron ID;
3. stop the Gateway before its due time and confirm the listening port is free;
4. restart the Gateway using the same isolated runtime environment;
5. run `openclaw health` to confirm the restarted Gateway is healthy;
6. run `openclaw cron list` and confirm the **same scheduler ID** is still present before the due time;
7. confirm the KAIRO Job is still `queued` with the same scheduler linkage;
8. leave the restarted Gateway running and wait past the due time;
9. verify the future turn moves the Job through `running` to `completed` or an explicit `failed` state.

The live controlled-restart proof preserved the exact same scheduler ID across Gateway stop/restart and the future turn completed successfully with durable KAIRO Job state intact.

This proves controlled restart recovery for queued one-shot work. It does **not** yet prove automatic reconciliation for unclean crashes, jobs interrupted while already `running`, or scheduler/runtime divergence.

## 11. What this runbook does not prove

Even after both background proofs succeed, these remain unfinished:

- hard per-job model-spend enforcement;
- actual provider/token/cost accounting on the Job;
- automatic stale queued/running Job reconciliation after unclean crashes or interrupted runs;
- production backups/restore;
- remote authentication and HTTPS;
- cross-device PWA;
- model routing;
- Critic mode and approval-request workflow;
- social/crypto/voice integrations.

That is intentional. The next code should respond to failures observed in live use rather than anticipate every possible infrastructure need.
