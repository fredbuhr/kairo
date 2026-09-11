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
- Canonical main checkpoint before H3b2a: `e8351c3d33f21d2e6b6244af284b47c6a66285e6`.
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
   - **H3b2 — External image pinning/debt reduction: in progress through bounded sub-gates.**
     - **H3b2a — KAIRO Node build-base digest pins: implementation validated; PR/merge next.**
     - **Remaining H3b2 image debt: not started.**
4. **H4 — Production/auth boundary: not started.**
5. **H5 — Full revalidation + real-engine/production checks + post-audit tag: not started.**

Active development branch: `hardening/h3b2a-node-image-pins`.
Active work pull request: **none yet**.
H3b2a validated technical head: `538af6072bee2239187339a0bf66bda8c29fa916`.

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

H3b1 solves **KAIRO-owned container dependency/build reproducibility only**. Core, Worker, Realtime and Web consume canonical locked dependency graphs; Reproducibility CI builds all four images; the Research crash overlay follows the same Worker build contract. Final PR-head validation passed 8/8 workflows, including Foundation and the real Worker SIGKILL Research replay.

`hardening/h3b1-container-locks` is retired after merge and must not be reused. The connector does not expose branch-ref deletion, so the inert remote ref may remain.

### H3b2a — KAIRO Node build-base digest pins

H3b2a is deliberately limited to the two KAIRO-owned Node build-base references. No Compose service image is changed in this sub-gate.

Implementation on validated technical head `538af6072bee2239187339a0bf66bda8c29fa916`:

1. `apps/web/Dockerfile` pins `node:22-alpine` to `sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32`.
2. `services/realtime/Dockerfile` pins the same `node:22-alpine` image to the same digest.
3. That exact Node digest was already observed and successfully used by the final H3b1 Reproducibility build, so H3b2a does not change the intended Node tag/version line.
4. `config/reproducibility-baseline.json` advances to version 4, records both Node Dockerfiles as validated digest pins, and reduces known unpinned-image debt from **31 to 29** references.
5. `scripts/smoke/reproducibility_contract.py` keeps the same fail-closed behavior; only its success message is generalized from the H3b1-specific wording to the current reproducibility baseline.

Technical diff versus canonical pre-H3b2a `main` is exactly four files before this checkpoint:

- `apps/web/Dockerfile`;
- `services/realtime/Dockerfile`;
- `config/reproducibility-baseline.json`;
- `scripts/smoke/reproducibility_contract.py`.

Validation on exact technical head `538af607...`: **8/8 push workflows success**:

- Baseline reproducibility validation — run `34587219896` — success, including real KAIRO container builds using the digest-pinned Node base;
- Foundation validation — run `34587219893` — success;
- Autonomous Research validation — run `34587219916` — success, including the real Worker SIGKILL replay proof;
- MCP tool registry validation — run `34587219921` — success;
- Multi-user isolation validation — run `34587219888` — success;
- Document ingestion validation — run `34587219886` — success;
- UI workspace validation — run `34587219917` — success;
- Code quality validation — run `34587219906` — success.

News ownership is path-filtered and was not triggered by this H3b2a file set.

H3b2a is not canonical until its PR is merged. Do not pin any additional image on this branch.

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

Finish **H3b2a only — KAIRO Node build-base digest pins**:

1. confirm the final diff remains the four H3b2a technical files plus this checkpoint file only;
2. open a PR from `hardening/h3b2a-node-image-pins` to live `main`;
3. require all final PR-head checks to be green;
4. merge H3b2a;
5. update canonical `PROJECT_STATE.md` with the PR/merge result and mark H3b2a complete;
6. retire the H3b2a branch;
7. stop before the next H3b2 image-pin batch.

After H3b2a is canonical, continue H3b2 only through another small branch fresh from live `main`, prioritizing a coherent, verifiable subset of the remaining **29** unpinned/moving image references. Do not begin H4 until H3b2 is explicitly complete.

Do not begin Gantt, Calendar, Brain, Finance/Crypto, voice or other product work until H5 is complete.
