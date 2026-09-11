# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**, promoted through PR #73 together with the repository recovery protocol.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- Last fully revalidated product/checkpoint parent before R3 documentation: `69cf0dd52eea93f7e5b9bf7413cde2cb51c2c8b5`.
- The seven workflows triggered on that R2 checkpoint passed, including Foundation and real Research Worker `SIGKILL` replay.
- News ownership was not retriggered by the R2 documentation-only checkpoint; it passed on the exact validated PR #73 head `9af0573d7295d3da10c06477752f07ec4ac51541`, where all eight workflows were green.
- `AGENTS.md` and this file are part of the canonical line.
- Rule: always fetch the live `main` head before acting. Recorded SHAs are checkpoints, not permission to ignore newer GitHub state.

## Active work

- Repository Reset is in progress.
- R0 — repository truth: **complete**.
- R1 — recovery protocol: **complete**.
- R2 — validate and promote G51 / PR #73: **complete**.
- R3 — synchronize canonical documentation: **complete in the current documentation commit**.
- Active development branch: **none**.
- Active pull request: **none**.
- No product code was changed in R3.

R3 synchronized exactly these current-truth documents:

- `docs/status.md` — G51/main baseline, validation state, implemented vs not-ready capabilities and Repository Reset status;
- `docs/roadmap.md` — Repository Reset first, then post-R7 Block 3 sequencing;
- `docs/component-matrix.md` — explicit maturity states so declared/configured dependencies are not confused with validated KAIRO capabilities.

## Next action

Perform **R4 only — inventory all branches and pull requests**.

R4 is read-only classification work:

1. fetch the live `main` head first;
2. enumerate branches and open/closed PRs relevant to the current repository;
3. classify each meaningful branch/PR as `keep`, `absorbed`, `archive/salvage`, or `delete/close candidate`;
4. compare divergent branches against `main` before classifying unique work;
5. pay special attention to `feat/kairo-test-interface-v1` as a code reservoir and to old consolidation/review/backup branches;
6. make **no branch deletions, PR closures or product-code changes** in R4;
7. record the inventory/result here before ending the gate.

Do **not** start Gantt, Calendar, Brain, Finance/Crypto or any other product slice before the Repository Reset reaches R7.

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

Treat as historical until R4 classifies them. Do not use them as a starting point merely because they contain a familiar feature name.

## Repository reset sequence

- R0 — establish repository truth: **complete**
- R1 — add `AGENTS.md` + `PROJECT_STATE.md`: **complete**
- R2 — resolve/promote PR #73: **complete**
- R3 — synchronize current documentation: **complete**
- R4 — inventory all branches and PRs: **next**
- R5 — close superseded PRs and remove absorbed branches
- R6 — inventory repository files/directories: active / intentional scaffold / historical / duplicate / removable
- R7 — establish a clean tagged baseline with green CI

## Product work after repository reset

The intended next product sequence remains:

1. Gantt + Calendar on the canonical G51 Task planning model;
2. 2D/3D Brain / graph;
3. collaboration and universal search;
4. desktop/voice/presence;
5. specialist Finance/Crypto/Home capabilities behind KAIRO-owned contracts.

This sequencing is subordinate to the live repository state. If GitHub has moved, reconcile this file first instead of creating another branch.
