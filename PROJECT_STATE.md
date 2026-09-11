# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- Last fully revalidated product/checkpoint parent before repository-cleanup-only commits: `69cf0dd52eea93f7e5b9bf7413cde2cb51c2c8b5`.
- R5b completion checkpoint before R5c classification: `bc72c7043ac1c0ba6ae62fb8f62d2aa7aed728a5`.
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
- R5c — superseded divergent branch cleanup: **classification complete; deletion mutation pending**.
- Active development branch: **none**.
- Active work pull request: **none**.
- Open pull requests: **0**.

## R5c starting state

R5c started from the independently verified post-R5b GitHub state:

- total branches: **49**;
- canonical branch: **1** (`main`);
- non-canonical branches reviewed: **48**;
- product-code delta between the local full-history comparison checkpoint (`dfaa9ace...`) and live `main` at R5b completion was documentation-only (`PROJECT_STATE.md`), so R5c branch/code comparisons remain valid for product behavior.

## R5c retention decision

After comparing actual commit ancestry, unique commits/files, current `main`, and the retained prototype reservoir, only two non-canonical refs have explicit independent salvage value.

### KEEP TEMPORARILY — prototype reservoir

- `feat/kairo-test-interface-v1`
  - tip at R5c classification: `ed12d503aa500a6e7700e9ac82d823e0e815f33d`;
  - large divergent experimental reservoir covering Brain/graph, Gantt/planning, Calendar, Desktop/Tauri, Automations, Finance, Knowledge, Tools, lifecycle/security and related ADR/test work;
  - never merge wholesale;
  - later salvage must copy isolated components into a fresh branch based on current `main`.

### KEEP TEMPORARILY — focused Research design reservoir

- `consolidate/g49-research-durable-stages`
  - tip at R5c classification: `57a1a217f466c56446d84d863f4b9b09855e4c4e`;
  - three unique commits versus canonical G48 lineage;
  - preserves the alternative durable Research-stage activity design (`research_stages.py` plus Worker registration/workflow changes);
  - current `main` already owns validated Research behavior and real Worker `SIGKILL` replay;
  - retain only for later isolated design review, never resume as an active development branch.

## R5c deletion decision — 46 refs

The other **46** non-canonical branches have no independent branch-level salvage value and are approved for deletion. Their histories are historical evidence only; none should be resumed as an implementation workspace.

### A. Already contained by canonical/prototype history — 4 refs

- `feat/canonical-document-ingestion` — strict ancestor of `main`;
- `fix/embedded-usage-correlation` — strict ancestor of `main`;
- `feat/research-synthesis-checkpoints` — fully preserved inside `feat/kairo-test-interface-v1`;
- `feat/research-command-handoff` — fully preserved inside `feat/kairo-test-interface-v1`.

### B. Divergent Block 2 alternatives now superseded by current `main` — 6 refs

- `block2/context-pack-documents`;
- `block2/research-crash-recovery`;
- `block2/research-crash-replay-proof`;
- `block2/research-e2e-proof`;
- `block2/web-mcp-bootstrap`;
- `block2/web-mcp-search`.

These refs contain old alternative implementations/proofs, but their useful capabilities are represented by the current canonical line through the current Research Context Pack (`research_context.py` / `research_context_pack.py`), first-party Web MCP (`web_mcp.py`, `web_mcp_bootstrap.py`, `compose.web-mcp.yaml`, ADR-025), ADR-027 Context Pack semantics, and the canonical real Worker `SIGKILL` replay proof. The old filenames such as `web_mcp_server.py`, `first_party_tools.py` and the older crash fixtures are not the active contracts.

### C. Legacy V0 / OpenClaw proof lineage — 18 refs

- `bootstrap/kairo-foundations`;
- `chore/core-ci`;
- `docs/record-at04-live-proof`;
- `docs/record-sigkill-recovery-proof`;
- `docs/runtime-proof-runbook`;
- `feat/background-turns`;
- `feat/gate3-autonomy-contract`;
- `feat/gate5-routing-accounting`;
- `feat/job-ledger`;
- `feat/job-model-usage-accounting`;
- `feat/job-step-checkpoints`;
- `feat/openclaw-job-step-checkpoints`;
- `feat/openclaw-kairo-tools`;
- `feat/reconcile-queued-kairo-jobs`;
- `feat/v0-core-storage`;
- `fix/gateway-cron-background-jobs`;
- `fix/openclaw-plugin-packaging`;
- `tmp-check`.

This lineage belongs to the superseded OpenClaw/filesystem V0. Current `main` explicitly records that OpenClaw was a proof runtime and is removed from the target architecture; its durable-execution lessons were reimplemented behind Temporal, PostgreSQL canonical state, policy and accounting contracts. Old OpenClaw plugin/runtime/package files are historical only.

### D. Superseded platform/capability implementation lines — 18 refs

- `architecture/full-platform-foundation`;
- `feat/autonomous-research-agent`;
- `feat/autonomous-research-v1`;
- `feat/block1-completion-and-intelligence-foundation`;
- `feat/block1-system-of-record`;
- `feat/block1-trust-boundary`;
- `feat/block2-agents-memory`;
- `feat/block2-model-call-replay-safety`;
- `feat/block2-model-transaction-safety`;
- `feat/block2-safe-autonomy-model-gateway`;
- `feat/command-kernel-v1`;
- `feat/conversational-command-router`;
- `feat/docling-document-ingestion`;
- `feat/langfuse-correlation`;
- `feat/mcp-tool-registry`;
- `feat/projects-tasks-workspace`;
- `feat/rebuildable-memory-projections`;
- `feat/semantic-capability-router`.

These are predecessor implementations of capabilities now owned by the canonical platform. Current `main` contains the evolved auth/Keycloak/OpenBao boundary, model gateway/accounting, Command Kernel/routing, Docling Documents, MCP registry/tools, memory projections, autonomous Research, and canonical Projects/Tasks workspace. `feat/projects-tasks-workspace` has unique historical UI/API files, but current `main` has the canonical `ProjectsWorkspace.tsx`, owner-scoped Project/Task access and G51 Task planning/Today model; the older workspace branch is not an independent product line.

## R5c expected post-delete branch set

After deleting the 46 approved refs, GitHub should contain exactly **3 branches**:

1. `main` — the only canonical integrated source of truth;
2. `feat/kairo-test-interface-v1` — temporary broad prototype/salvage reservoir;
3. `consolidate/g49-research-durable-stages` — temporary focused Research design reservoir.

No other branch should remain after R5c.

## R5c mutation guard

R5c is **not complete yet** until the 46 approved refs are actually deleted on GitHub and the 3-branch postcondition is independently verified.

Before deletion:

1. re-fetch live GitHub branch state;
2. require exactly 49 branches;
3. require `main`, `feat/kairo-test-interface-v1`, and `consolidate/g49-research-durable-stages` to remain on the expected SHAs for this checkpoint;
4. require every deletion candidate to remain on its classified SHA;
5. delete exactly the 46 refs listed above;
6. verify exactly 3 branches remain;
7. verify the three protected refs still exist and did not move unexpectedly;
8. update this file to mark R5c complete;
9. stop before R6.

## Next action

Perform **the R5c deletion mutation only**. Do not begin R6 until the remote deletion is independently verified.

## Repository reset sequence

- R0 — establish repository truth: **complete**
- R1 — add `AGENTS.md` + `PROJECT_STATE.md`: **complete**
- R2 — resolve/promote PR #73: **complete**
- R3 — synchronize current documentation: **complete**
- R4 — inventory branches and PRs: **complete**
- R5a — close stale open PRs: **complete**
- R5b — remove obvious absorbed/duplicate branches: **complete**
- R5c — remove remaining superseded divergent branches after re-check: **classification complete, deletion pending**
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
