# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- Last fully revalidated product/checkpoint parent before repository-cleanup-only commits: `69cf0dd52eea93f7e5b9bf7413cde2cb51c2c8b5`.
- R4 checkpoint before PR cleanup: `10642c7a219bb4581b2bb08d990bb12e690d6766`.
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
- Active development branch: **none**.
- Active work pull request: **none**.
- Open pull requests after R5a: **0**.

## R5a result — PR cleanup

R5a changed pull-request state only. No branch was deleted and no product code was changed.

The 32 stale open PRs identified by R4 were closed:

- `#36`, `#37`, `#39`;
- `#42` through `#54`;
- `#56` through `#71`.

Post-cleanup verification returned an empty open-PR list.

The branch inventory remained present after the PR cleanup. In particular, the three refs that must not be removed in R5b remain conceptually protected by this checkpoint:

- `main` — canonical source of truth;
- `feat/kairo-test-interface-v1` — temporary prototype/salvage reservoir only;
- `consolidate/g49-research-durable-stages` — temporary Research design reservoir only.

PR #39 is now closed, but its `feat/kairo-test-interface-v1` branch must remain until later salvage inventory. Closing a PR is not permission to merge or delete that reservoir.

## R4 branch classification still in force

### KEEP — canonical

- `main`.

### KEEP TEMPORARILY — salvage reservoirs only

1. `feat/kairo-test-interface-v1`
   - large divergent experimental reservoir;
   - contains prototype Brain/graph, Gantt/planning, Calendar, Desktop/Tauri, Automations, Finance, Knowledge, Tools, lifecycle/security and related ADR/test work;
   - never merge wholesale;
   - salvage isolated components later from a fresh branch based on current `main` only.

2. `consolidate/g49-research-durable-stages`
   - divergent by three unique Research-stage commits from G48;
   - current `main` already owns the validated Research behavior and passes real Worker `SIGKILL` replay;
   - retain only for isolated design review/salvage, never as an active workspace.

### ABSORBED — R5b candidates

Representative branches already proven to have `ahead=0` versus canonical `main` include:

- `consolidate/g48-ownership`;
- `consolidate/g49-research-replay`;
- `consolidate/g50-baseline`;
- `stabilize/daily-v1`;
- `block3/task-run-artifact-ownership`;
- `block2/research-crash-replay`;
- `block2/research-context-pack`;
- `block3/g51-daily-spine` is merged through PR #73.

The intermediate `block2/*` and `block3/*` branches feeding those absorbed chains are historical implementation steps. R5b must still re-check each ref against live `main` immediately before deletion; branch names alone are not sufficient proof.

### EXACT DUPLICATE SNAPSHOT REFS — R5b candidates

These refs all pointed to the same old snapshot SHA `51977f987a3edd260b4b3ba2adc4794746fb6598` during R4:

- `feat/kairo-test-interface-v1-backup`;
- `feat/kairo-test-interface-v1-draft`;
- `feat/kairo-test-interface-v1-finalreview`;
- `feat/kairo-test-interface-v1-pr`;
- `feat/kairo-test-interface-v1-review`;
- `tmp-noop`.

The retained `feat/kairo-test-interface-v1` was 529 commits ahead of that snapshot, so those duplicate refs have no independent salvage value.

### DEFER TO R5c — divergent/superseded lines

Do not delete divergent V0/OpenClaw/old-architecture/feature branches merely because they look obsolete. R5c will re-check them against both `main` and the retained salvage reservoir before removal. Examples include `architecture/full-platform-foundation`, `tmp-check`, old V0 `feat/*`/`fix/*` lines, and the old `feat/research-command-handoff` lineage.

## Next action

Perform **R5b only — obvious absorbed/duplicate branch cleanup**.

R5b rules:

1. fetch live `main` first;
2. preserve `main`, `feat/kairo-test-interface-v1`, and `consolidate/g49-research-durable-stages` without exception;
3. for an absorbed candidate, compare it with live `main` and delete only if `ahead_by == 0`;
4. delete the six exact duplicate snapshot refs only after confirming they still point to the duplicate snapshot and the retained reservoir still exists;
5. do not delete divergent/superseded branches in R5b — those belong to R5c;
6. verify the remaining branch set and update this checkpoint;
7. stop.

Do **not** start Gantt, Calendar, Brain, Finance/Crypto or any other product slice before the Repository Reset reaches R7.

## Repository reset sequence

- R0 — establish repository truth: **complete**
- R1 — add `AGENTS.md` + `PROJECT_STATE.md`: **complete**
- R2 — resolve/promote PR #73: **complete**
- R3 — synchronize current documentation: **complete**
- R4 — inventory branches and PRs: **complete**
- R5a — close stale open PRs: **complete**
- R5b — remove obvious absorbed/duplicate branches: **next**
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
