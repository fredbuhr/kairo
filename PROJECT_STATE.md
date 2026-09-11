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

## Post-R7 audit hardening

A post-reset audit found one production-path bug plus bounded cleanup/reproducibility/production-boundary debt. Product feature work is paused until the hardening sequence is complete.

Hardening sequence:

1. **H1 — Memory/Auth handoff**: fix authenticated Worker startup of system-owned memory projection Tasks; prove the path with Keycloak enabled. **Implementation validated; merge next.**
2. **H2 — Code hygiene**: remove dead News implementation/bootstrap/dependencies proven unused, add `.gitattributes`, and add focused lint/static checks without broad refactoring.
3. **H3 — Reproducibility**: introduce lockfiles/frozen installs and reduce critical moving Docker tags/digests while keeping the reproducibility contract truthful.
4. **H4 — Production/auth boundary**: production Web serving/public URLs, stricter JWT audience/client validation, Web MCP bootstrap path, and explicit profiles for unfinished/exposed services.
5. **H5 — Full revalidation**: run the canonical suite plus targeted real-engine/production checks, synchronize docs, and create a new post-audit hardening tag.

Current active development branch: `hardening/h1-memory-auth-handoff`.
Active work pull request: **none yet**.
Open pull requests before H1 PR: **0**.

### H1 evidence

H1 implementation code head: `cf04b45d7a10fcc07af16e8e5806f2ddd2d1249f`.

H1 changes exactly four implementation/validation files before this checkpoint update:

- `services/core/src/kairo_core/workflows.py` — adds internal-token-protected `/internal/v1/tasks/{task_id}/run`, restricted to `owner_type == "system"` Tasks;
- `services/worker/src/kairo_worker/memory_events.py` — memory consumer uses the internal system-Task handoff with `X-Kairo-Internal-Token` instead of the authenticated public user endpoint;
- `.github/workflows/multi-user-isolation.yml` — starts the Worker with Keycloak enabled and deterministic memory projector mode;
- `scripts/smoke/multi_user_isolation.py` — requires authenticated Worker-driven Mem0/Graphiti projections to reach `projected` while preserving cross-user 404 isolation.

Targeted authenticated proof:

- **Multi-user isolation validation** run `34578505066` — success on exact H1 code head; Keycloak, Core and Worker were active and the new authenticated memory projection assertion passed.
- **Foundation validation** run `34578505040` — all eight jobs reported success on the exact H1 code head, including the existing memory-projection integration, authenticated resource boundary, policy, command, backup/restore and compile/build checks.
- Reproducibility and UI workflow checks on the same code head also completed successfully; no failing workflow was observed in the H1 suite.

H1 is not canonical until merged to `main`. Do not start H2 on this branch. After H1 merge, retire/delete this branch and start H2 fresh from updated `main`.

## Final branch set after Repository Reset

Before H1, exactly three repository-reset branches remained:

1. `main` — only canonical integrated source of truth.
2. `feat/kairo-test-interface-v1` — temporary broad prototype/salvage reservoir; never merge wholesale.
3. `consolidate/g49-research-durable-stages` — temporary focused Research design reservoir; never resume as active development.

H1 temporarily adds one normal implementation branch, as allowed by the governance rule. Any subsequent gate must branch fresh from the updated `main` after the preceding gate is merged and retired.

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

Finish **H1 only**:

1. open a PR from `hardening/h1-memory-auth-handoff` to live `main`;
2. verify the PR diff remains limited to H1 plus this checkpoint file;
3. merge H1 only after the required checks are green;
4. update `PROJECT_STATE.md` on canonical `main` to record the merge;
5. retire/delete the H1 branch;
6. stop before H2.

After H1 is canonical, the next gate is **H2 — code hygiene**. Product features such as Gantt/Calendar remain paused through H5.
