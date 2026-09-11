# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**, promoted through PR #73 together with the repository recovery protocol.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- The exact PR head validated before merge was `9af0573d7295d3da10c06477752f07ec4ac51541`.
- All eight workflows on that exact PR head completed successfully: Foundation, Autonomous Research, MCP tool registry, Document ingestion, UI workspace, Multi-user isolation, News ownership, and Baseline reproducibility.
- `AGENTS.md` and this file are now part of the canonical line.
- Rule: always fetch the live `main` head before acting. Recorded SHAs are checkpoints, not permission to ignore newer GitHub state.

## Active work

- Repository Reset is in progress.
- R0 — repository truth: **complete**.
- R1 — recovery protocol: **complete**.
- R2 — validate and promote G51 / PR #73: **complete**.
- Active development branch: **none**.
- Active pull request: **none**.
- The merged branch `block3/g51-daily-spine` may still physically exist until the branch-cleanup gate. It is historical after PR #73 and must not be resumed as an active workspace.

## Next action

Perform **R3 only — synchronize current documentation**.

1. fetch the live `main` head;
2. compare `docs/status.md`, `docs/roadmap.md`, and `docs/component-matrix.md` with the actual canonical implementation;
3. update those documents so they describe the G51 `main` line without stale branch/SHA claims;
4. move no historical files yet unless required to prevent them being mistaken for current truth — broad archive cleanup belongs to R6;
5. make no product-code changes;
6. update this file at the end of R3 with the exact result and next gate.

Do **not** start Gantt, Calendar, Brain, Finance/Crypto or any other product slice before the Repository Reset reaches its clean baseline.

## Lines that are NOT canonical workspaces

### `consolidate/g49-research-durable-stages`

Diverged from canonical `main`. It contains three unique experimental Research-stage commits but is behind the integrated line. Do not resume work there and do not merge it wholesale. Any potentially useful idea must be reviewed and salvaged as an isolated change from current `main`.

### `consolidate/g50-baseline`

Historical consolidation line already represented by the G50 merge into `main`. Do not resume development there.

### `block3/g51-daily-spine`

Merged through PR #73. Treat as historical until R5 removes absorbed branches.

### `feat/kairo-test-interface-v1`

Large experimental reservoir, hundreds of commits diverged from `main`. Keep temporarily for later inventory/salvage only. Never merge wholesale.

### Other Block 2 / Block 3 stacked branches and old PRs

Treat as historical until the repository branch/PR inventory gate classifies them. Do not use them as a starting point merely because they contain a familiar feature name.

## Repository reset sequence

- R0 — establish repository truth: **complete**
- R1 — add `AGENTS.md` + `PROJECT_STATE.md`: **complete**
- R2 — resolve/promote PR #73: **complete**
- R3 — synchronize current documentation (`status`, roadmap, component matrix): **next**
- R4 — inventory all branches and PRs: keep / absorbed / archive / delete
- R5 — close superseded PRs and remove absorbed branches
- R6 — inventory repository files/directories: active / intentional scaffold / historical / duplicate / removable
- R7 — establish a clean tagged baseline with green CI

## Product work after repository reset

The intended next product sequence remains:

1. Gantt + Calendar on the canonical Task planning model;
2. 2D/3D Brain / graph;
3. collaboration and universal search;
4. desktop/voice/presence;
5. specialist Finance/Crypto/Home capabilities behind KAIRO-owned contracts.

This sequencing is subordinate to the live repository state. If GitHub has moved, reconcile this file first instead of creating another branch.
