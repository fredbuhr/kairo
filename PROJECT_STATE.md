# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- Last fully revalidated product/checkpoint parent before repository-cleanup-only commits: `69cf0dd52eea93f7e5b9bf7413cde2cb51c2c8b5`.
- R5a checkpoint before R5b verification: `53508fcb9a600bd45c5ed594925b27f3b0e808a0`.
- The seven workflows triggered on the R2 checkpoint passed, including Foundation and real Research Worker `SIGKILL` replay. News ownership passed on the exact validated PR #73 head where all eight workflows were green.
- `AGENTS.md` and this file are part of the canonical line.
- Rule: always fetch the live `main` head before acting. Recorded SHAs are checkpoints, not permission to ignore newer GitHub state.

## Repository Reset status

- R0 — repository truth: **complete**.
- R1 — recovery protocol: **complete**.
- R2 — validate and promote G51 / PR #73: **complete**.
- R3 — synchronize canonical documentation: **complete**.
- R4 — branch and PR inventory: **complete**.
- R5a — close stale open PRs: **complete**.
- R5b — obvious absorbed/duplicate branch cleanup: **verification complete, deletion blocked by current GitHub connector**.
- Active development branch: **none**.
- Active work pull request: **none**.
- Open pull requests: **0**.

## R5b verification result

Live `main` was re-fetched before comparison. The branch inventory still contains **88 branches** because no branch-ref deletion capability is exposed by the GitHub connector available in this session. Do not claim R5b complete until the approved refs below are actually deleted and the remaining branch set is re-counted.

### Protected refs — never delete in R5b

- `main` — canonical source of truth.
- `feat/kairo-test-interface-v1` — temporary prototype/salvage reservoir only.
- `consolidate/g49-research-durable-stages` — temporary Research design reservoir only.

### Approved absorbed refs — `ahead_by == 0` versus live `main`

#### Block 2 — 10 refs

- `block2/assistant-conversation-ownership`
- `block2/research-context-pack`
- `block2/research-crash-replay`
- `block2/research-derived-memory-context`
- `block2/research-document-context`
- `block2/research-grounded-synthesis`
- `block2/research-heartbeat-recovery`
- `block2/research-result-contract`
- `block2/research-synthesis-checkpoints`
- `block2/research-web-mcp`

#### Block 3 — 19 refs

Every current `block3/*` ref was re-compared against live `main` and returned `ahead_by == 0`:

- `block3/cockpit-extra-panels`
- `block3/cockpit-layout-contract`
- `block3/cockpit-layout-persistence`
- `block3/cockpit-mounted`
- `block3/cockpit-panel-controls`
- `block3/cockpit-shell-component`
- `block3/command-center-generic-polling`
- `block3/command-center-generic-tasks`
- `block3/g51-daily-spine`
- `block3/panel-command-center`
- `block3/panel-command-center-component`
- `block3/panel-news-component`
- `block3/panels-mounted`
- `block3/project-bound-task-access`
- `block3/project-ownership`
- `block3/projects-workspace-minimal`
- `block3/research-workspace-minimal`
- `block3/research-workspace-mounted`
- `block3/task-run-artifact-ownership`

#### Consolidation / stabilization — 4 refs

- `consolidate/g48-ownership`
- `consolidate/g49-research-replay`
- `consolidate/g50-baseline`
- `stabilize/daily-v1`

Each was re-compared with live `main` and returned `ahead_by == 0`.

### Approved exact duplicate refs — 6 refs

The live branch inventory still shows all six refs on the exact same snapshot SHA `51977f987a3edd260b4b3ba2adc4794746fb6598`:

- `feat/kairo-test-interface-v1-backup`
- `feat/kairo-test-interface-v1-draft`
- `feat/kairo-test-interface-v1-finalreview`
- `feat/kairo-test-interface-v1-pr`
- `feat/kairo-test-interface-v1-review`
- `tmp-noop`

The retained `feat/kairo-test-interface-v1` remains on `ed12d503aa500a6e7700e9ac82d823e0e815f33d`, so these six snapshot refs have no independent salvage value.

### Total approved R5b deletion set

- strict ancestors of `main`: **33** refs;
- exact duplicate snapshot refs: **6** refs;
- total refs approved for deletion: **39**.

Starting from the verified 88-branch inventory, a successful R5b deletion should leave **49 branches** before R5c.

## Explicitly deferred to R5c — divergent refs

R5b verification caught several `block2/*` refs that still contain commits exclusive to their old lines. They must **not** be deleted under the `ahead_by == 0` rule and are deferred to R5c salvage/supersession review:

- `block2/context-pack-documents` — divergent, 28 commits ahead at verification;
- `block2/research-crash-recovery` — divergent, 4 commits ahead;
- `block2/research-crash-replay-proof` — divergent, 25 commits ahead;
- `block2/research-e2e-proof` — divergent, 19 commits ahead;
- `block2/web-mcp-bootstrap` — divergent, 14 commits ahead;
- `block2/web-mcp-search` — divergent, 5 commits ahead.

Other V0/OpenClaw/old architecture/feature branches also remain for R5c. Do not infer deletability from branch names alone.

## R5b blocker

The GitHub connector available in this session exposes branch reads, comparisons and ref moves, but **does not expose branch/ref deletion**. Moving an obsolete branch to another commit is not an acceptable substitute for deleting it, so no branch was falsely rewritten or reported as removed.

R5b is therefore not complete yet. The verified deletion set above is ready for a context that has a real branch-delete/ref-delete operation.

## Next action

Perform **the R5b deletion mutation only** before starting R5c:

1. re-fetch live `main`;
2. confirm the three protected refs still exist;
3. delete exactly the 39 approved refs above using a branch/ref deletion-capable GitHub context;
4. verify the repository has 49 branches remaining;
5. verify `main`, `feat/kairo-test-interface-v1`, and `consolidate/g49-research-durable-stages` still exist;
6. update this checkpoint to mark R5b complete;
7. stop.

Do **not** proceed to R5c, R6, Gantt, Calendar, Brain, Finance/Crypto or any other product slice until this deletion mutation is actually complete.

## Repository reset sequence

- R0 — establish repository truth: **complete**
- R1 — add `AGENTS.md` + `PROJECT_STATE.md`: **complete**
- R2 — resolve/promote PR #73: **complete**
- R3 — synchronize current documentation: **complete**
- R4 — inventory branches and PRs: **complete**
- R5a — close stale open PRs: **complete**
- R5b — remove obvious absorbed/duplicate branches: **verified, deletion pending**
- R5c — remove remaining superseded divergent branches after re-check
- R6 — inventory repository files/directories: active / intentional scaffold / historical / duplicate / removable
- R7 — establish a clean tagged baseline with green CI

## Product work after repository reset

The intended next product sequence remains:

1. Gantt + Calendar on the canonical G51 Task planning model;
2. 2D/3D Brain / graph;
3. collaboration and universal search;
4. desktop/voice/presence;
5. specialist Finance/Crypto/Home capabilities behind KAIRO-owned contracts.

If GitHub state moves, reconcile this file before creating or resuming any development branch.
