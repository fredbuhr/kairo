# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`
- Verified `main` head before R1: `f524ed7c8e8a71fa3de882f4d294c224cb8d207f`
- Integrated milestone: validated consolidation through G50 via PR #72
- Rule: always fetch the live `main` head before acting; the SHA above is a checkpoint, not permission to ignore newer GitHub state.

## Active work

- Repository Reset is in progress.
- Current reset gate: **R1 — install recovery protocol**.
- Active development branch: `block3/g51-daily-spine`
- Active pull request: **#73 — Block 3: establish canonical Daily Spine with Today**
- Last verified functional G51 head before R1 metadata commits: `90951161a8cdd8f0194148aa6bc498bc0d018671`
- PR #73 is based directly on current `main`, was 12 commits ahead / 0 behind at R0, and was mergeable.
- The eight workflows associated with that verified functional head were green: Foundation, Autonomous Research, MCP, Documents, UI, Multi-user isolation, News ownership, and Baseline reproducibility.

R1 adds only repository-recovery metadata. The live PR head will therefore advance beyond the functional SHA above; always query PR #73 before editing or merging.

## Next action

After R1 is complete, perform **R2 only**:

1. re-fetch `main` and PR #73;
2. confirm PR #73 is still based on canonical `main` and remains mergeable;
3. review the small R1 metadata addition separately from the already-validated G51 functional changes;
4. run/inspect any CI triggered by R1;
5. merge PR #73 only if the resulting head is green and coherent;
6. update this file immediately after merge so `main` becomes the recorded G51 baseline.

Do not start Gantt/Calendar before R2 is resolved.

## Lines that are NOT canonical workspaces

### `consolidate/g49-research-durable-stages`

Diverged from current `main`. It contains three unique experimental Research-stage commits but is behind the canonical line. Do not resume work there and do not merge it wholesale. Any potentially useful idea must be reviewed and salvaged as an isolated change from current `main`.

### `consolidate/g50-baseline`

Historical consolidation line already represented by the G50 merge into `main`. Do not resume development there.

### `feat/kairo-test-interface-v1`

Large experimental reservoir, hundreds of commits diverged from `main`. Keep temporarily for later inventory/salvage only. Never merge wholesale.

### Other Block 2 / Block 3 stacked branches and old PRs

Treat as historical until the repository branch/PR inventory gate classifies them. Do not use them as a starting point merely because they contain a familiar feature name.

## Repository reset sequence

- R0 — establish repository truth: **complete**
- R1 — add `AGENTS.md` + `PROJECT_STATE.md`: **current gate**
- R2 — resolve/promote PR #73 if still valid
- R3 — synchronize current documentation (`status`, roadmap, component matrix)
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
