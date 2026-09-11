# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- Last fully revalidated product checkpoint: `69cf0dd52eea93f7e5b9bf7413cde2cb51c2c8b5`.
- R5c completion checkpoint before R6: `b715f2952bad0976dadbe33cb6191e0402698e9c`.
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
- R7 — clean tagged baseline with green CI: **next**.
- Active development branch: **none**.
- Active work pull request: **none**.
- Open pull requests: **0**.

## Final branch set after R5

Exactly three branches remain:

1. `main` — only canonical integrated source of truth.
2. `feat/kairo-test-interface-v1` — temporary broad prototype/salvage reservoir; never merge wholesale.
3. `consolidate/g49-research-durable-stages` — temporary focused Research design reservoir; never resume as active development.

## R6 inventory result

R6 inventoried the current `main` working tree before any product work. The repository contains **234 tracked files**.

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
- `packages/protocol/*` — 3 files; shared protocol/authority/event contract scaffold, not yet consumed by the current apps.
- `packages/ui/*` — 3 files; shared KAIRO space/design-system scaffold, not yet consumed by the current Web app.

Installed but currently unused Web dependencies for Gantt, Calendar, Brain, realtime, rich text, maps and dashboards remain intentional configured dependencies because `config/components.yaml` and `docs/component-matrix.md` explicitly track them as Configured/Scaffold/Declared rather than completed features.

### Historical evidence — 1 file

- `docs/audit-2026-09-08.md` was a dated implementation snapshot whose current-state assertions became obsolete after G48–G51. It is retained as evidence but moved to `docs/archive/audit-2026-09-08.md`.

### Duplicate/stale after R6 cleanup — 0 files

`docs/status.md`, `docs/roadmap.md` and the Block 2/3 status lines in `docs/implementation-plan.md` were stale about Repository Reset progress; R6 refreshes them rather than deleting them because they are authoritative/current planning documents.

### Removable — 0 files

R6 found no tracked file whose removal is justified without either deleting active validation/implementation or prematurely removing an intentional architecture scaffold.

## Important R6 findings

- All current Web source modules are referenced by the application graph; `vite-env.d.ts` is the expected declaration-only exception.
- Every file in `scripts/smoke/` is referenced by a current GitHub Actions workflow.
- `compose.research-crash.yaml`, `compose.test-noauth.yaml`, `compose.web-mcp.yaml`, `compose.ops.yaml`, `compose.override.yaml` and `compose.production.yaml` all have current workflow/Makefile/runbook/script consumers.
- `packages/gantt` and `packages/graph` remain scaffolds; installed renderers do not imply product completion.
- `services/realtime` and `apps/desktop` remain explicit scaffolds, not mature capabilities.
- The component registry intentionally includes future/optional engines; presence in Compose/manifests is not evidence that the corresponding capability is complete.

## Next action

Perform **R7 only — establish a clean tagged baseline with green CI**.

R7 should:

1. fetch live `main`;
2. run/inspect the full canonical validation suite on the R6 checkpoint;
3. resolve only reproducibility/CI issues required for a truthful green baseline;
4. create a clean baseline tag only after required CI is green;
5. update this checkpoint with the tag and validation evidence;
6. stop before beginning Gantt/Calendar or any other product slice.

Do **not** start Gantt, Calendar, Brain, Finance/Crypto, voice or other product work until R7 is complete.

## Product work after Repository Reset

1. Gantt + Calendar on the canonical G51 Task planning model.
2. 2D/3D Brain / graph.
3. Collaboration/realtime and universal search.
4. Desktop/voice/presence.
5. Specialist Finance/Crypto/Home capabilities behind KAIRO-owned contracts.
