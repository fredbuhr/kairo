# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- Last fully revalidated product/checkpoint parent before repository-cleanup-only commits: `69cf0dd52eea93f7e5b9bf7413cde2cb51c2c8b5`.
- R5b pre-deletion checkpoint: `dfaa9ace5bb8a8bc849fed655f72744092c0d593`.
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
- R5b — obvious absorbed/duplicate branch cleanup: **complete**.
- Active development branch: **none**.
- Active work pull request: **none**.
- Open pull requests: **0**.

## R5b result — branch cleanup complete

R5b was completed against live GitHub state after an independent post-delete verification.

### Verified mutation

- Branches before R5b deletion: **88**.
- Branches deleted: **39**.
- Branches remaining: **49**.
- Strict ancestors of `main` deleted: **33**.
- Exact duplicate snapshot refs deleted: **6**.
- Product code changed by R5b: **none**.

### Protected refs verified after deletion

These three refs remain present at the expected SHAs:

- `main` — `dfaa9ace5bb8a8bc849fed655f72744092c0d593` before this checkpoint update;
- `feat/kairo-test-interface-v1` — `ed12d503aa500a6e7700e9ac82d823e0e815f33d`;
- `consolidate/g49-research-durable-stages` — `57a1a217f466c56446d84d863f4b9b09855e4c4e`.

`feat/kairo-test-interface-v1` remains a temporary prototype/salvage reservoir only. It must never be merged wholesale.

`consolidate/g49-research-durable-stages` remains a temporary Research design reservoir only. Current `main` owns the validated Research behavior.

### Deleted in R5b

#### Absorbed Block 2 refs — 10

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

#### Absorbed Block 3 refs — 19

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

#### Absorbed consolidation/stabilization refs — 4

- `consolidate/g48-ownership`
- `consolidate/g49-research-replay`
- `consolidate/g50-baseline`
- `stabilize/daily-v1`

#### Exact duplicate snapshot refs — 6

All six pointed to snapshot `51977f987a3edd260b4b3ba2adc4794746fb6598` immediately before deletion:

- `feat/kairo-test-interface-v1-backup`
- `feat/kairo-test-interface-v1-draft`
- `feat/kairo-test-interface-v1-finalreview`
- `feat/kairo-test-interface-v1-pr`
- `feat/kairo-test-interface-v1-review`
- `tmp-noop`

## R5c input — remaining divergent/historical refs

R5c begins from **49 branches total**, including `main` and the two explicit salvage reservoirs.

The six divergent Block 2 refs discovered during R5b must be reviewed rather than deleted by name:

- `block2/context-pack-documents` — previously observed as divergent with 28 commits ahead;
- `block2/research-crash-recovery` — previously observed as divergent with 4 commits ahead;
- `block2/research-crash-replay-proof` — previously observed as divergent with 25 commits ahead;
- `block2/research-e2e-proof` — previously observed as divergent with 19 commits ahead;
- `block2/web-mcp-bootstrap` — previously observed as divergent with 14 commits ahead;
- `block2/web-mcp-search` — previously observed as divergent with 5 commits ahead.

Other remaining refs include old V0/OpenClaw, architecture-reset, early Block 1/2, job-ledger, command-router, document-ingestion, model-gateway, MCP, memory, project/task and Research lines. R5c must compare each remaining non-protected branch against live `main` and, where relevant, against `feat/kairo-test-interface-v1` before deletion.

## Next action

Perform **R5c only — superseded divergent branch cleanup**.

R5c rules:

1. fetch live `main` and the full 49-branch inventory first;
2. preserve `main`, `feat/kairo-test-interface-v1`, and `consolidate/g49-research-durable-stages` while evaluating salvage value;
3. classify each remaining non-canonical branch by actual unique commits/files, not by branch name;
4. verify whether unique material is already represented in `main` or preserved inside the retained prototype reservoir;
5. delete only branches proven to have no independent salvage value;
6. stop and verify the final branch set before R6;
7. update this checkpoint with the resulting canonical/salvage branch inventory.

Do **not** start R6, Gantt, Calendar, Brain, Finance/Crypto or any other product slice during R5c.

## Repository reset sequence

- R0 — establish repository truth: **complete**
- R1 — add `AGENTS.md` + `PROJECT_STATE.md`: **complete**
- R2 — resolve/promote PR #73: **complete**
- R3 — synchronize current documentation: **complete**
- R4 — inventory branches and PRs: **complete**
- R5a — close stale open PRs: **complete**
- R5b — remove obvious absorbed/duplicate branches: **complete**
- R5c — remove remaining superseded divergent branches after re-check: **next**
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
