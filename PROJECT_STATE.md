# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**, promoted through PR #73 together with the repository recovery protocol.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- Last fully revalidated product/checkpoint parent before R3 documentation: `69cf0dd52eea93f7e5b9bf7413cde2cb51c2c8b5`.
- R3 documentation head and live `main` verified before R4: `fd3586f8e3c6e8b86967f453323b27fb0a59dfe9`.
- The seven workflows triggered on the R2 checkpoint passed, including Foundation and real Research Worker `SIGKILL` replay. News ownership passed on the exact validated PR #73 head where all eight workflows were green.
- `AGENTS.md` and this file are part of the canonical line.
- Rule: always fetch the live `main` head before acting. Recorded SHAs are checkpoints, not permission to ignore newer GitHub state.

## Repository Reset status

- R0 — repository truth: **complete**.
- R1 — recovery protocol: **complete**.
- R2 — validate and promote G51 / PR #73: **complete**.
- R3 — synchronize canonical documentation: **complete**.
- R4 — branch and PR inventory: **complete**.
- Active development branch: **none**.
- Active work pull request: **none**.
- There are still stale open PRs and historical branches; they are cleanup inventory, not active work.

## R4 inventory result

R4 was classification-only. No branch was deleted and no PR was closed.

### Counts

- Branches found: **88** total.
- Open PRs found: **32** (`#36`, `#37`, `#39`, `#42`–`#54`, `#56`–`#71`).
- Canonical branches to keep permanently now: **1** (`main`).
- Non-canonical branches to keep temporarily for salvage: **2**.
- Remaining branches are cleanup candidates, subject to the R5 safety checks before deletion.

### KEEP — canonical

- `main` — the only integrated source of truth.

### KEEP TEMPORARILY — salvage reservoirs only

1. `feat/kairo-test-interface-v1`
   - large divergent experimental reservoir;
   - contains prototype Brain/graph, Gantt/planning, Calendar, Desktop/Tauri, Automations, Finance, Knowledge, Tools, lifecycle/security and related ADR/test work;
   - never merge wholesale;
   - salvage isolated components later from a fresh `main` branch only.

2. `consolidate/g49-research-durable-stages`
   - divergent by only three unique commits from G48;
   - contains the alternative durable Research-stage activity design (`research_stages.py` plus Worker registration/workflow changes);
   - current `main` already passes real Research `SIGKILL` replay through the integrated G49 solution;
   - keep only long enough to preserve/review any useful design lesson, never resume or merge wholesale.

### ABSORBED — deletion candidates

Representative comparisons prove the important consolidated/stabilized lines are already ancestors of `main`:

- `consolidate/g48-ownership`: `ahead=0`, behind current main;
- `consolidate/g49-research-replay`: `ahead=0`, behind current main;
- `consolidate/g50-baseline`: `ahead=0`, behind current main;
- `stabilize/daily-v1`: `ahead=0`, behind current main;
- `block3/task-run-artifact-ownership`: `ahead=0`, behind current main;
- `block2/research-crash-replay`: `ahead=0`, behind current main;
- `block2/research-context-pack`: `ahead=0`, behind current main;
- `block3/g51-daily-spine`: merged through PR #73.

The intermediate `block2/*`, `block3/*` and permanent-platform feature branches that feed those validated chains are historical implementation steps and should not be resumed. R5 will re-check a ref before deleting it rather than relying only on its name.

### SUPERSEDED / DUPLICATE — deletion candidates

- old V0/OpenClaw `bootstrap/*`, `docs/*`, old `feat/*`, `fix/*` and `tmp-*` lines are superseded by the permanent architecture introduced through PR #21 and later canonical work;
- `architecture/full-platform-foundation` is an old divergent architecture-reset implementation, superseded by the evolved architecture now on `main`;
- `tmp-check` only carries obsolete OpenClaw runtime/package material;
- `feat/kairo-test-interface-v1-backup`, `-draft`, `-finalreview`, `-pr`, `-review` and `tmp-noop` all point to the same old snapshot SHA `51977f987a3edd260b4b3ba2adc4794746fb6598`;
- the current `feat/kairo-test-interface-v1` is 529 commits ahead of that shared snapshot, so those snapshot refs add no separate salvage value.

### Open PR classification

All **32 open PRs are close candidates**; none is current work.

- PRs `#42`–`#54` and `#56`–`#71`: stacked implementation slices whose resulting capability chain is already represented in current `main`; representative branch tips are strict ancestors of `main`.
- PRs `#36` and `#37`: old divergent Research implementation line. Their functionality is superseded on `main`, and the old chain is also an ancestor of the retained `feat/kairo-test-interface-v1` reservoir; close them rather than keep separate active lines.
- PR `#39`: close the PR because it must never merge wholesale, but keep its current `feat/kairo-test-interface-v1` branch temporarily as the explicit prototype/salvage reservoir.
- Closed/merged PRs remain untouched as historical evidence. PR #72 and PR #73 are important consolidation/promotion records.

## Next action

Perform **R5a only — close stale open PRs**.

R5 is deliberately split into smaller mutation gates:

1. **R5a — PR cleanup only**
   - re-fetch live `main` and the open-PR list;
   - close the 32 stale open PRs;
   - do not delete any branch;
   - verify no open PR remains and update this checkpoint;
   - stop.

2. **R5b — obvious absorbed/duplicate branch cleanup**
   - delete only branches proven strict ancestors of `main` plus exact duplicate snapshot refs;
   - preserve `main`, `feat/kairo-test-interface-v1`, and `consolidate/g49-research-durable-stages`;
   - stop and verify.

3. **R5c — superseded divergent branch cleanup**
   - re-check remaining V0/OpenClaw/old architecture/feature refs against `main` and the retained salvage reservoir;
   - delete only after proving they add no independent salvage value;
   - stop and verify the final branch set.

Do **not** start Gantt, Calendar, Brain, Finance/Crypto or any other product slice before the Repository Reset reaches R7.

## Lines that are NOT canonical workspaces

### `feat/kairo-test-interface-v1`

Temporary salvage reservoir only. Hundreds of commits diverged from `main`. Never merge wholesale and never treat it as the active KAIRO line.

### `consolidate/g49-research-durable-stages`

Temporary design reservoir only. Three unique experimental Research-stage commits, but current `main` owns the validated product behavior. Never resume it as active development.

### Everything else outside `main`

Historical until R5 cleanup. Do not use any old branch as a starting point simply because a previous conversation or PR mentioned it.

## Repository reset sequence

- R0 — establish repository truth: **complete**
- R1 — add `AGENTS.md` + `PROJECT_STATE.md`: **complete**
- R2 — resolve/promote PR #73: **complete**
- R3 — synchronize current documentation: **complete**
- R4 — inventory branches and PRs: **complete**
- R5a — close stale open PRs: **next**
- R5b — remove obvious absorbed/duplicate branches
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

This sequencing is subordinate to the live repository state. If GitHub has moved, reconcile this file first instead of creating another branch.
