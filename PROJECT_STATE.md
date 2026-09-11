# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- Clean post-reset CI baseline: `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- Baseline tag: `r7-baseline-2026-09-11` → `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- H1 Memory/Auth handoff: PR #74, merge `3fa1aa5a67628c97ee4367e9a0224cff9086fbf0`.
- H2 Code hygiene: PR #75, merge `31e53b88135ac2db4600bb00a4112bc14d46ba5d`.
- H3a Dependency locks/frozen direct CI: PR #76, merge `ecc3394a648070b16ab4505e07706006999ab945`.
- Canonical main checkpoint before H3b1: `31bc227b9a706842379f0ebfda29268f90c5b292`.
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
   - **H3a — Dependency locks/frozen direct CI: complete and canonical.**
   - **H3b1 — Locked KAIRO container builds: PR #77 open; final PR-head revalidation required.**
   - **H3b2 — External image pinning/debt reduction: not started.**
4. **H4 — Production/auth boundary: not started.**
5. **H5 — Full revalidation + real-engine/production checks + post-audit tag: not started.**

Active development branch: `hardening/h3b1-container-locks`.
Active work pull request: **#77** — `H3b1: build KAIRO containers from canonical locked graphs`.
Last fully green implementation head before PR-overlay correction: `8eaea7eced738e7caad63cd4c8ef1e89fb46f6fa`.
Research-overlay correction technical head: `776d4d9adb570b2f43f7d3e7aa9ab60bac1f1304`.
The final PR head includes this checkpoint update and must be read live from GitHub before merge.

### H1 — Memory/Auth handoff

Canonical merge:

- PR #74 — `H1: fix authenticated memory projection handoff`;
- merge commit: `3fa1aa5a67628c97ee4367e9a0224cff9086fbf0`;
- validated implementation head: `cf04b45d7a10fcc07af16e8e5806f2ddd2d1249f`.

H1 moved Worker-triggered system memory Tasks from the authenticated public user endpoint to an internal-token-protected system-only handoff. The internal route fails closed for non-system Tasks. Authenticated Keycloak + Core + Worker regression coverage proves projections reach `projected` while cross-user reads remain isolated.

`hardening/h1-memory-auth-handoff` is retired and must not be reused.

### H2 — Code hygiene

Canonical merge:

- PR #75 — `H2: remove dead code and add static-quality guardrails`;
- merge commit: `31e53b88135ac2db4600bb00a4112bc14d46ba5d`;
- validated implementation head: `70febab5c06840620557d0fcefd596e20e3f9758`;
- final PR head: `ca2464b70114de4d4d9ad5e91071f8f38982943f`.

H2 removed proven dead code/dependencies/settings, added LF normalization and focused Ruff/Bash static-quality checks, and remained intentionally narrow. Final PR checks were green.

`hardening/h2-code-hygiene` is retired and must not be reused.

### H3a — Dependency locks and frozen direct CI

Canonical merge:

- PR #76 — `H3a: lock dependency graphs and freeze direct CI installs`;
- merge commit: `ecc3394a648070b16ab4505e07706006999ab945`;
- validated implementation head: `6a62b7ac8411543ddd6c4253675f00bae5538b62`;
- final PR head: `215927227baaf051865d9a5b59c65cf2c0f934d0`.

H3a added canonical `pnpm-lock.yaml`, root UV workspace `uv.lock`, `uv.toml` requiring `uv==0.12.13`, frozen/locked direct CI installs and a fail-closed reproducibility contract. Final PR head passed 9/9 workflows, including Foundation and the real Worker SIGKILL Research replay.

No Dockerfile or Compose file changed in H3a. Remaining container/image reproducibility debt was explicitly deferred to H3b.

`hardening/h3a-dependency-locks` is retired and must not be reused.

### H3b1 — Locked KAIRO container builds

H3b1 deliberately solves **KAIRO-owned container dependency/build reproducibility only**. It does not pin the remaining third-party/moving image references; those remain H3b2.

Implementation:

1. Added root `.dockerignore` so root build contexts remain bounded and exclude Git metadata, local environments, dependency caches/build output and backup staging.
2. Switched the four KAIRO Compose builds (`kairo-core`, `kairo-worker`, `kairo-realtime`, `kairo-web`) from isolated service/app contexts to the repository root, with explicit Dockerfile paths.
3. Core and Worker now consume the canonical root UV workspace via `uv sync --locked` instead of `uv pip install --system`, preserving the existing Core/Worker package split and Worker extras behavior.
4. Core and Worker retain the historically validated Python runtime image digest, while `uv`/`uvx` are overlaid from `ghcr.io/astral-sh/uv:0.12.13` pinned to digest `sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6`, matching canonical `uv.toml`.
5. Web and Realtime now consume root `pnpm-lock.yaml` and install with `--frozen-lockfile`.
6. Realtime additionally copies root `tsconfig.base.json`, required by its existing `../../tsconfig.base.json` inheritance before container-local TypeScript compilation.
7. `config/reproducibility-baseline.json` advances to version 3: known unlocked container-install debt is now empty, and the four KAIRO Dockerfiles are required to contain their locked/frozen install modes.
8. `scripts/smoke/reproducibility_contract.py` now fails closed if KAIRO container installs stop using the required frozen/locked modes.
9. Reproducibility CI actually builds all four KAIRO images from canonical lockfiles, with Worker extras disabled only for this deterministic build proof.
10. `compose.research-crash.yaml` aligns its two fake Research services with the new root-context Worker build contract so the real Worker SIGKILL replay continues to build the same canonical Worker image definition.

Current technical diff versus canonical pre-H3b1 `main` is exactly ten files before this checkpoint:

- `.dockerignore` — added;
- `.github/workflows/reproducibility.yml`;
- `apps/web/Dockerfile`;
- `compose.research-crash.yaml`;
- `compose.yaml`;
- `config/reproducibility-baseline.json`;
- `scripts/smoke/reproducibility_contract.py`;
- `services/core/Dockerfile`;
- `services/realtime/Dockerfile`;
- `services/worker/Dockerfile`.

Validation discoveries were resolved inside H3b1 rather than hidden:

1. Reproducibility run `34585085624` on head `df792094...` proved the old pinned Python runtime contained `uv 0.9.30`, incompatible with canonical `uv==0.12.13`.
2. Reproducibility run `34585359120` on head `3db57091...` proved copying the new binary to `/bin` did not override the older `/usr/local/bin/uv`; the overlay destination was corrected to `/usr/local/bin`.
3. Reproducibility run `34585537868` on head `90545f32...` proved Core, Worker and Web locked builds succeeded, while Realtime failed only because its inherited root `tsconfig.base.json` was absent from the image context; the required config is now copied explicitly.
4. Final PR run `34585997643` exposed a remaining old build context in `compose.research-crash.yaml`: the crash topology tried to build the updated Worker Dockerfile from `./services/worker`, so root `uv.toml`, lockfiles and workspace paths were unavailable. The overlay is now aligned to root context with explicit `services/worker/Dockerfile`; the Research contract and Core integration jobs in that same failed run were already green.

Validation on exact pre-PR implementation head `8eaea7ec...`: **8/8 push workflows success**:

- Baseline reproducibility validation — run `34585734035` — success, including real builds of Core, Worker, Realtime and Web from canonical locked graphs;
- Foundation validation — run `34585734054` — success;
- Autonomous Research validation — run `34585734078` — success;
- MCP tool registry validation — run `34585734103` — success;
- Multi-user isolation validation — run `34585734081` — success;
- Document ingestion validation — run `34585734034` — success;
- UI workspace validation — run `34585734111` — success;
- Code quality validation — run `34585734100` — success.

PR #77 final-head validation must be completely green after the Research overlay correction before merge. News ownership is path-filtered and is not expected for this file set.

H3b1 is not canonical until PR #77 is merged. Do not begin H3b2 on this branch.

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

Finish **H3b1 only — Locked KAIRO container builds**:

1. read the live PR #77 head after this checkpoint update;
2. require all final PR-head workflows to be green, especially Autonomous Research with the real Worker SIGKILL replay;
3. confirm the final diff remains the ten H3b1 technical files plus this checkpoint file only;
4. merge PR #77 with expected-head protection;
5. update canonical `PROJECT_STATE.md` with the PR/merge result and mark H3b1 complete;
6. retire the H3b1 branch;
7. stop before H3b2.

After H3b1 is canonical, **H3b2 — External image pinning/debt reduction** is next. H3b2 must be created fresh from live `main` and should reduce moving/unpinned third-party image references without mixing H4 production/auth-boundary work.

Do not begin Gantt, Calendar, Brain, Finance/Crypto, voice or other product work until H5 is complete.
