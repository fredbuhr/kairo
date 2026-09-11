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
- H3b1 Locked KAIRO container builds: PR #77, merge `e43e192938ce412f534eb68e989e7408289be3be`.
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
   - **H3b1 — Locked KAIRO container builds: complete and canonical.**
   - **H3b2 — External image pinning/debt reduction: next; not started.**
4. **H4 — Production/auth boundary: not started.**
5. **H5 — Full revalidation + real-engine/production checks + post-audit tag: not started.**

Active development branch: **none**.
Active work pull request: **none**.
Next implementation gate: **H3b2 only — External image pinning/debt reduction**.

### H1 — Memory/Auth handoff

Canonical merge:

- PR #74 — `H1: fix authenticated memory projection handoff`;
- merge commit: `3fa1aa5a67628c97ee4367e9a0224cff9086fbf0`;
- validated implementation head: `cf04b45d7a10fcc07af16e8e5806f2ddd2d1249f`.

H1 moved Worker-triggered system memory Tasks from the authenticated public user endpoint to an internal-token-protected system-only handoff. Authenticated Keycloak + Core + Worker regression coverage proves projections reach `projected` while cross-user reads remain isolated.

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

`hardening/h3a-dependency-locks` is retired and must not be reused.

### H3b1 — Locked KAIRO container builds

Canonical merge:

- PR #77 — `H3b1: build KAIRO containers from canonical locked graphs`;
- merge commit: `e43e192938ce412f534eb68e989e7408289be3be`;
- final validated PR head: `ac5835f0071412236dc6797c0c7911fbcf317164`.

H3b1 solves **KAIRO-owned container dependency/build reproducibility only**. It does not pin the remaining third-party/moving image references; those remain H3b2.

Canonical H3b1 changes:

1. Root `.dockerignore` bounds repository-root Docker build contexts.
2. Core, Worker, Realtime and Web Compose builds use repository-root contexts with explicit Dockerfile paths so canonical root lockfiles are visible.
3. Core and Worker consume the root UV workspace with `uv sync --locked`.
4. Core and Worker retain the historically validated Python runtime image digest while `uv`/`uvx` are overlaid from `ghcr.io/astral-sh/uv:0.12.13` pinned to digest `sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6`, matching `uv.toml`.
5. Web and Realtime consume root `pnpm-lock.yaml` with `--frozen-lockfile`.
6. Realtime explicitly receives root `tsconfig.base.json`, required by its existing TypeScript config inheritance.
7. Reproducibility baseline/contract now requires locked/frozen KAIRO container installs and records zero known unlocked KAIRO container installs.
8. Reproducibility CI builds all four KAIRO images from canonical locked graphs.
9. `compose.research-crash.yaml` uses the same root-context Worker build contract for its fake Research services, preserving the real SIGKILL replay proof.

The final H3b1 PR diff contains exactly ten technical files plus this checkpoint file:

- `.dockerignore` — added;
- `.github/workflows/reproducibility.yml`;
- `apps/web/Dockerfile`;
- `compose.research-crash.yaml`;
- `compose.yaml`;
- `config/reproducibility-baseline.json`;
- `scripts/smoke/reproducibility_contract.py`;
- `services/core/Dockerfile`;
- `services/realtime/Dockerfile`;
- `services/worker/Dockerfile`;
- `PROJECT_STATE.md` — checkpoint evidence only.

Validation failures were resolved rather than hidden:

1. Reproducibility run `34585085624` exposed the historical Python image's `uv 0.9.30` mismatch with canonical `uv==0.12.13`.
2. Reproducibility run `34585359120` exposed PATH precedence when the new uv binary was copied to `/bin`; the canonical overlay now targets `/usr/local/bin`.
3. Reproducibility run `34585537868` exposed Realtime's missing inherited root `tsconfig.base.json` in its image context.
4. PR run `34585997643` exposed the Research crash overlay's stale isolated Worker context; `compose.research-crash.yaml` was aligned to the root-context Worker build.

Final PR-head validation on exact head `ac5835f...`: **8/8 workflows success**:

- Baseline reproducibility validation — run `34586337983` — success, including real builds of Core, Worker, Realtime and Web from canonical locked graphs;
- Foundation validation — run `34586338184` — success;
- Autonomous Research validation — run `34586338026` — success, including the real Worker SIGKILL replay proof;
- MCP tool registry validation — run `34586337969` — success;
- Multi-user isolation validation — run `34586338112` — success;
- Document ingestion validation — run `34586338088` — success;
- UI workspace validation — run `34586337997` — success;
- Code quality validation — run `34586337922` — success.

News ownership was path-filtered and was not triggered by this H3b1 file set.

`hardening/h3b1-container-locks` is retired after merge and must not be reused. The connector does not expose branch-ref deletion, so the inert remote ref may remain.

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

Perform **H3b2 only — External image pinning/debt reduction** from a fresh branch created from live `main`.

H3b2 should remain bounded to image-reference reproducibility already tracked by `config/reproducibility-baseline.json`:

- inventory the remaining unpinned/moving third-party image references;
- prioritize critical runtime/infrastructure images and replace moving tags with immutable digests where verifiable;
- update the reproducibility baseline only alongside concrete debt reduction;
- preserve service versions and runtime behavior unless a pin requires an explicitly validated compatibility adjustment;
- do not mix H4 production/auth-boundary work;
- stop after H3b2 merge/checkpoint before beginning H4.

Do not begin Gantt, Calendar, Brain, Finance/Crypto, voice or other product work until H5 is complete.
