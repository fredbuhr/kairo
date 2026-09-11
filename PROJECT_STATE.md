# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- Last fully revalidated product/checkpoint parent before repository-cleanup-only commits: `69cf0dd52eea93f7e5b9bf7413cde2cb51c2c8b5`.
- R5b completion checkpoint before R5c classification: `bc72c7043ac1c0ba6ae62fb8f62d2aa7aed728a5`.
- R5c classification checkpoint before deletion: `0fa7a39dc873d9c84f1ae71bf4241e1ca76b4c33`.
- The seven workflows triggered on the R2 checkpoint passed, including Foundation and real Research Worker `SIGKILL` replay. News ownership passed on the exact validated PR #73 head where all eight workflows were green.
- `AGENTS.md` and this file are part of the canonical line.
- Rule: always fetch live `main` before acting. Recorded SHAs are checkpoints, not permission to ignore newer GitHub state.

## Repository Reset status

- R0 — repository truth: **complete**.
- R1 — recovery protocol: **complete**.
- R2 — validate and promote G51 / PR #73: **complete**.
- R3 — synchronize canonical documentation: **complete**.
- R4 — branch and PR inventory: **complete**.
- R5a — close stale open PRs: **complete**.
- R5b — obvious absorbed/duplicate branch cleanup: **complete**.
- R5c — superseded divergent branch cleanup: **complete**.
- Active development branch: **none**.
- Active work pull request: **none**.
- Open pull requests: **0**.

## R5c result — branch cleanup complete

R5c was completed against live GitHub state and independently verified afterwards.

### Verified mutation

- Branches before R5c deletion: **49**.
- Branches deleted in R5c: **46**.
- Branches remaining after R5c: **3**.
- Product code changed by R5c: **none**.

### Final branch set

Exactly these three branches remain on GitHub:

1. `main`
   - canonical integrated source of truth;
   - tip immediately before this checkpoint update: `0fa7a39dc873d9c84f1ae71bf4241e1ca76b4c33`.

2. `feat/kairo-test-interface-v1`
   - temporary broad prototype/salvage reservoir only;
   - verified tip: `ed12d503aa500a6e7700e9ac82d823e0e815f33d`;
   - contains prototype Brain/graph, Gantt/planning, Calendar, Desktop/Tauri, Automations, Finance, Knowledge, Tools, lifecycle/security and related ADR/test work;
   - never merge wholesale;
   - later salvage must copy isolated components into a fresh branch based on current `main`.

3. `consolidate/g49-research-durable-stages`
   - temporary focused Research design reservoir only;
   - verified tip: `57a1a217f466c56446d84d863f4b9b09855e4c4e`;
   - preserves the alternative durable Research-stage activity design;
   - current `main` already owns validated Research behavior and real Worker `SIGKILL` replay;
   - retain only for isolated design review, never resume as an active development branch.

No other branch remains after R5c.

## R5c classification summary

The 46 removed branches fell into these historical/superseded groups:

- divergent Block 2 alternatives for Context Pack, Web MCP and crash/replay proofs whose useful behavior is represented in current `main`;
- legacy V0/OpenClaw proof/runtime branches replaced by the permanent Temporal/PostgreSQL architecture;
- predecessor platform/capability branches for Command Kernel, model gateway/accounting, Documents/Docling, MCP, memory, Projects/Tasks and Research;
- old architecture reset and temporary/fix branches with no independent salvage value.

Two non-canonical refs were deliberately retained because they still have explicit independent salvage value: the broad prototype reservoir and the focused alternative Research design reservoir above.

## Next action

Perform **R6 only — repository file/directory inventory and cleanup planning**.

R6 must classify current `main` files/directories as:

- active canonical implementation;
- intentional scaffold;
- historical evidence/archive;
- duplicate/stale;
- removable.

R6 must use the repository itself as source of truth and must not begin product feature work. In particular, do not start Gantt, Calendar, Brain, Finance/Crypto or any other product slice before R7 is complete.

## Repository reset sequence

- R0 — establish repository truth: **complete**
- R1 — add `AGENTS.md` + `PROJECT_STATE.md`: **complete**
- R2 — resolve/promote PR #73: **complete**
- R3 — synchronize current documentation: **complete**
- R4 — inventory branches and PRs: **complete**
- R5a — close stale open PRs: **complete**
- R5b — remove obvious absorbed/duplicate branches: **complete**
- R5c — remove remaining superseded divergent branches after re-check: **complete**
- R6 — inventory repository files/directories: **next**
- R7 — establish a clean tagged baseline with green CI

## Product work after repository reset

The intended next product sequence remains:

1. Gantt + Calendar on the canonical G51 Task planning model;
2. 2D/3D Brain / graph;
3. collaboration and universal search;
4. desktop/voice/presence;
5. specialist Finance/Crypto/Home capabilities behind KAIRO-owned contracts.

If GitHub state moves, reconcile this file before creating or resuming any development branch.
