# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- Last fully revalidated product checkpoint before Repository Reset: `69cf0dd52eea93f7e5b9bf7413cde2cb51c2c8b5`.
- Clean post-reset CI baseline: `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- Baseline tag: `r7-baseline-2026-09-11` → `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- `AGENTS.md` and this file define repository recovery/resume discipline.
- Rule: always fetch live `main` before acting. GitHub wins over chat memory or recorded checkpoint SHAs.

## Repository Reset status

- R0 — repository truth: **complete**.
- R1 — recovery protocol: **complete**.
- R2 — validate/promote G51: **complete**.
- R3 — synchronize canonical documentation: **complete**.
- R4 — branch/PR inventory: **complete**.
- R5a — stale PR cleanup: **complete**.
- R5b — absorbed/duplicate branch cleanup: **complete**.
- R5c — superseded divergent branch cleanup: **complete**.
- R6 — repository file/directory inventory: **complete**.
- R7 — clean tagged baseline with green CI: **complete**.
- **Repository Reset R0–R7: complete.**
- Active development branch: **none**.
- Active work pull request: **none**.
- Open pull requests: **0**.

## Final branch set after Repository Reset

Exactly three branches remain:

1. `main` — only canonical integrated source of truth.
2. `feat/kairo-test-interface-v1` — temporary broad prototype/salvage reservoir; never merge wholesale.
3. `consolidate/g49-research-durable-stages` — temporary focused Research design reservoir; never resume as active development.

Any new product gate must branch fresh from live `main`. Do not resume either salvage branch as an implementation workspace.

## R6 inventory result

R6 inventoried the current `main` working tree before product work. The repository contained **234 tracked files** at the R6 checkpoint.

### Active canonical implementation/configuration/documentation — 215 files

This includes:

- all `.github/workflows/*` validation workflows;
- all `apps/web/*` Cockpit/Today/Projects/Research/News/Knowledge/auth/API code;
- all `services/core/*` canonical state, ownership, policy, planning, Research, MCP, memory, document and UI-layout code plus migrations through `0012_task_planning`;
- all `services/worker/*` durable execution, model gateway, memory/document projections, Research, Web MCP and semantic routing code;
- all `scripts/smoke/*` proofs — every current smoke script is referenced by a CI workflow;
- backup/restore/bootstrap scripts and every current Compose overlay, each of which has an active workflow/runbook/Makefile consumer;
- `config/*`, `infrastructure/*`, root manifests/configuration and the current architecture/security/operations/roadmap/status/decision documentation.

No active implementation file was proven safe to delete in R6.

### Intentional scaffolds — 18 files

These files are deliberately retained because they encode future KAIRO boundaries without claiming product completion:

- `apps/desktop/*` — 2 files; Tauri/Sidecar skeleton.
- `services/realtime/*` — 4 files; Hocuspocus/Yjs service scaffold without mature canonical collaboration persistence.
- `packages/gantt/*` — 3 files; planning interfaces only.
- `packages/graph/*` — 3 files; graph snapshot interfaces only.
- `packages/protocol/*` — 3 files; shared protocol/authority/event contract scaffold, not yet consumed by current apps.
- `packages/ui/*` — 3 files; shared KAIRO space/design-system scaffold, not yet consumed by the current Web app.

Installed but currently unused Web dependencies for Gantt, Calendar, Brain, realtime, rich text, maps and dashboards remain intentional configured dependencies because `config/components.yaml` and `docs/component-matrix.md` explicitly track them as Configured/Scaffold/Declared rather than completed features.

### Historical evidence — 1 file

- `docs/audit-2026-09-08.md` was a dated implementation snapshot whose current-state assertions became obsolete after G48–G51. It is retained as evidence at `docs/archive/audit-2026-09-08.md`.

### Duplicate/stale after R6 cleanup — 0 files

`docs/status.md`, `docs/roadmap.md` and the Block 2/3 status lines in `docs/implementation-plan.md` were stale about Repository Reset progress; R6 refreshed them rather than deleting them because they are authoritative/current planning documents.

### Removable — 0 files

R6 found no tracked file whose removal was justified without either deleting active validation/implementation or prematurely removing an intentional architecture scaffold.

## R7 validation evidence

The exact clean R6 checkpoint `6cf3647a609bbd8463cb734e87eb4088572bc037` triggered **7 push workflows**, and all 7 completed successfully:

1. **Baseline reproducibility validation** — run `34573983621` — success.
2. **UI workspace validation** — run `34573983736` — success.
3. **MCP tool registry validation** — run `34573983615` — success.
4. **Multi-user isolation validation** — run `34573983654` — success.
5. **Document ingestion validation** — run `34573983738` — success.
6. **Foundation validation** — run `34573983693` — success.
7. **Autonomous research validation** — run `34573983651` — success.

Key validated invariants on that exact SHA include:

- Compose/dev/production/ops topology validation;
- TypeScript typechecks and Web/Realtime builds;
- Python compile/import validation;
- deterministic and semantic command routing;
- Assistant conversation ownership;
- LiteLLM accounting contract;
- News Intelligence contract;
- Block 1 crash recovery and outbox delivery;
- autonomy policy/approval/budget enforcement;
- authenticated resource and multi-user ownership boundaries;
- memory projection replay;
- destructive backup/restore proof;
- MCP registry and MCP SDK contract;
- canonical document ingestion/versioned re-ingestion;
- workspace layout, Project/Task ownership and G51 Daily Spine/Today contracts;
- Research Context Pack, grounded synthesis, Web MCP, canonical result ownership and **real Worker SIGKILL replay invariants**;
- reproducibility baseline drift protection.

### News ownership carry-forward

`News ownership validation` is intentionally path-filtered and therefore did not run on the documentation-only R6 checkpoint. Its last validated G51 head `9af0573d7295d3da10c06477752f07ec4ac51541` passed News ownership in run `34544882488`.

A direct compare from `9af0573d...` to the R6 baseline `6cf3647a...` changes only six documentation paths (`PROJECT_STATE.md`, `docs/component-matrix.md`, `docs/implementation-plan.md`, `docs/roadmap.md`, `docs/status.md`, and the audit move). No News/auth/model/schema/contract implementation file changed, so the News ownership proof applies to the same product code.

## R7 tag result

The baseline tag was created and independently verified on GitHub:

- tag: `r7-baseline-2026-09-11`;
- type: lightweight Git tag;
- target: `6cf3647a609bbd8463cb734e87eb4088572bc037`;
- meaning: first clean post-Repository-Reset code baseline with the required CI evidence green.

The tag intentionally targets the exact CI-validated R6 code checkpoint. Subsequent `main` commits that only record R7 governance/checkpoint state are not part of the tagged code baseline.

## Next action

Repository Reset is complete. Product work may resume, but the small-gate discipline remains mandatory:

1. fetch live `main`;
2. create exactly one fresh implementation branch for the next product gate;
3. do not resume or wholesale-merge either salvage reservoir;
4. keep the gate small, validate it, merge it, delete/retire the branch, then start the next gate from updated `main`.

The intended first post-reset product sequence remains:

1. **Gantt + Calendar** on the canonical G51 Task planning model;
2. **2D/3D Brain / graph**;
3. collaboration/realtime and universal search;
4. Desktop/voice/presence;
5. specialist Finance/Crypto/Home capabilities behind KAIRO-owned contracts.
