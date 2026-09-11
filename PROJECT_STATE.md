# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- Clean post-reset CI baseline: `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- Baseline tag: `r7-baseline-2026-09-11` → `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- H1 Memory/Auth handoff is canonical via PR #74, merge `3fa1aa5a67628c97ee4367e9a0224cff9086fbf0`.
- H2 Code hygiene is canonical via PR #75, merge `31e53b88135ac2db4600bb00a4112bc14d46ba5d`.
- Canonical main checkpoint before H3a: `9d2ff654552efd27461b0b395ae4305b5ce550eb`.
- `AGENTS.md` and this file define repository recovery/resume discipline.
- Rule: always fetch live `main` before acting. GitHub wins over chat memory or recorded checkpoint SHAs.

## Repository Reset status

- R0–R7: **complete**.
- Repository Reset: **complete**.

## Post-R7 audit hardening

Product feature work remains paused until H5 is complete.

1. **H1 — Memory/Auth handoff: complete and canonical.**
2. **H2 — Code hygiene: complete and canonical.**
3. **H3 — Reproducibility: split into bounded sub-gates.**
   - **H3a — Dependency locks/frozen direct CI: implementation validated; PR/merge next.**
   - **H3b — Container reproducibility/image pinning: not started.**
4. **H4 — Production/auth boundary: not started.**
5. **H5 — Full revalidation + real-engine/production checks + post-audit tag: not started.**

Active development branch: `hardening/h3a-dependency-locks`.
Active work pull request: **none yet**.
H3a validated implementation head: `6a62b7ac8411543ddd6c4253675f00bae5538b62`.

### H1 — Memory/Auth handoff

Canonical merge:

- PR #74 — `H1: fix authenticated memory projection handoff`;
- merge commit: `3fa1aa5a67628c97ee4367e9a0224cff9086fbf0`;
- validated implementation head: `cf04b45d7a10fcc07af16e8e5806f2ddd2d1249f`.

H1 moved Worker-triggered system memory Tasks from the authenticated public user endpoint to an internal-token-protected system-only handoff. The internal route fails closed for non-system Tasks. An authenticated Keycloak + Core + Worker regression proof now requires Mem0/Graphiti projection state to reach `projected` while cross-user reads remain isolated.

Key evidence:

- Multi-user isolation run `34578505066`: success on exact H1 code head;
- Foundation run `34578505040`: all eight jobs success;
- PR #74 final checks: green, including Foundation run `34578930269`.

`hardening/h1-memory-auth-handoff` is retired and must not be reused.

### H2 — Code hygiene

Canonical merge:

- PR #75 — `H2: remove dead code and add static-quality guardrails`;
- merge commit: `31e53b88135ac2db4600bb00a4112bc14d46ba5d`;
- validated implementation head: `70febab5c06840620557d0fcefd596e20e3f9758`;
- final PR head: `ca2464b70114de4d4d9ad5e91071f8f38982943f`.

H2 removed the proven dead News implementation, obsolete bootstrap script, unused direct `boto3` dependencies and unused settings; added LF normalization plus focused Ruff/Bash static-quality checks. H2 did not contain broad refactoring or reproducibility work.

Validation on exact H2 implementation head `70febab5...`: **8/8 workflows success**. Final PR-head validation also finished green. Foundation run `34580502091` initially exposed a timing race in `memory-projection-integration`; a targeted rerun on the unchanged PR head passed, confirming the transient smoke timing issue without product-code changes.

`hardening/h2-code-hygiene` is retired after merge and must not be reused.

### H3a — Dependency locks and frozen direct CI

H3a deliberately solves dependency-graph reproducibility only. It does **not** restructure Docker build contexts or pin the remaining moving image references; those are H3b.

Implementation on exact validated head `6a62b7ac8411543ddd6c4253675f00bae5538b62`:

1. Added canonical root `pnpm-lock.yaml` for the JS/TS workspace.
2. Added canonical root `uv.lock` for the existing root UV workspace (`services/core` + `services/worker`).
3. Added `uv.toml` with `required-version = "==0.12.13"`; pnpm was already pinned by root `package.json` to `pnpm@10.15.1`.
4. Reproducibility CI now proves:
   - `pnpm install --frozen-lockfile` succeeds;
   - `uv lock --check` succeeds;
   - both canonical lockfiles are present;
   - the pnpm and UV toolchain pins have not drifted.
5. Direct non-container CI paths in Foundation, UI, Research, MCP and News now use `uv run --locked` and/or `uv lock --check` rather than allowing implicit dependency resolution.
6. Foundation now installs JS dependencies with `--frozen-lockfile`.
7. `config/reproducibility-baseline.json` was advanced to version 2: dependency lockfiles/toolchains are required, while the remaining container/image debt is still explicitly tracked for H3b.
8. `scripts/smoke/reproducibility_contract.py` now fails closed when required lockfiles/toolchain pins are absent or drift.

A temporary branch-only bootstrap workflow was used to generate the initial lockfiles because the assistant runtime has no package-registry network access. That workflow was deleted before the validated head and is absent from the H3a diff.

Final H3a implementation diff versus canonical pre-H3a `main` contains exactly 11 implementation/configuration files before this checkpoint:

- `.github/workflows/autonomous-research.yml`;
- `.github/workflows/foundation.yml`;
- `.github/workflows/mcp-tools.yml`;
- `.github/workflows/news-ownership.yml`;
- `.github/workflows/reproducibility.yml`;
- `.github/workflows/ui-workspace.yml`;
- `config/reproducibility-baseline.json`;
- `pnpm-lock.yaml` — added;
- `scripts/smoke/reproducibility_contract.py`;
- `uv.lock` — added;
- `uv.toml` — added.

No Dockerfile or Compose file changed in H3a.

Validation on exact H3a implementation head `6a62b7ac...`: **9/9 workflows success**:

1. Baseline reproducibility validation — run `34583114892` — success.
2. UI workspace validation — run `34583114854` — success.
3. News ownership validation — run `34583114840` — success.
4. Foundation validation — run `34583114819` — success; its validate job proved frozen pnpm install, UV lock check, builds, typechecks and locked direct smokes.
5. Autonomous research validation — run `34583114839` — success, including the real Worker SIGKILL replay proof.
6. MCP tool registry validation — run `34583114862` — success.
7. Multi-user isolation validation — run `34583114913` — success.
8. Document ingestion validation — run `34583114942` — success.
9. Code quality validation — run `34583114843` — success.

The lock generation emitted one non-fatal pnpm peer warning (`@react-three/fiber` versus React 19.3). Frozen install, typecheck and Web build all passed on the generated lock; this is recorded as an ecosystem warning rather than broadened into H3a scope.

H3a is not canonical until its PR is merged. Do not begin H3b on this branch.

## Canonical branch policy

Canonical truth is `main`. Two non-canonical salvage reservoirs remain intentionally available:

1. `feat/kairo-test-interface-v1` — broad prototype/salvage reservoir; never merge wholesale.
2. `consolidate/g49-research-durable-stages` — focused Research design reservoir; never resume as active development.

Retired hardening branches may remain as inert refs when the connector cannot delete refs. They are not development branches and must never be resumed.

For every gate: branch fresh from live `main`, keep scope small, validate, merge, retire, update this file, then stop.

## R6/R7 baseline summary

R6 classified the repository into active canonical files, intentional scaffolds and historical evidence; no product rewrite was justified. Intentional scaffolds include Desktop, Realtime, Gantt, Graph, Protocol and shared UI.

The exact R7 baseline `6cf3647a...` passed the canonical workflow suite, including ownership boundaries, Temporal crash/replay behavior, real Worker SIGKILL Research replay, command/model accounting, memory projections, MCP, Documents, backup/restore, Today/G51 planning and reproducibility-debt drift protection.

## Next action

Finish **H3a only — Dependency locks/frozen direct CI**:

1. verify the final PR diff remains the 11 H3a files plus this checkpoint file only;
2. open a PR from `hardening/h3a-dependency-locks` to live `main`;
3. require all final PR-head checks to be green;
4. merge H3a;
5. update canonical `PROJECT_STATE.md` with the PR/merge result and mark H3a complete;
6. retire/delete the H3a branch;
7. stop before H3b.

After H3a is canonical, **H3b — Container reproducibility/image pinning** is next. H3b must be created fresh from live `main` and should address isolated Docker build contexts, locked container installs, and reduction of moving/unpinned image references without mixing H4 production/auth work.

Do not begin Gantt, Calendar, Brain, Finance/Crypto, voice or other product work until H5 is complete.
