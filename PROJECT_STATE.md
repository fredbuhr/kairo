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
- H3b2a KAIRO Node build-base digest pins: PR #78, merge `f51ac9c0b00c46b046bb24b751540d204763bcbc`.
- H3b2b Core Compose service digest pins: PR #79, merge `f510043eb69b63919c6d012208f9b64b2bb63749`.
- H3b2c Temporal Compose digest pins: PR #80, merge `082a296650d77ebbe247bb3d5360b15e621c2596`.
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
     - **H3b2a — KAIRO Node build-base digest pins: complete and canonical.**
     - **H3b2b — Core Compose service digest pins: complete and canonical.**
     - **H3b2c — Temporal Compose digest pins: complete and canonical.**
     - **Remaining H3b2 image debt: 23 references.**
4. **H4 — Production/auth boundary: not started.**
5. **H5 — Full revalidation + real-engine/production checks + post-audit tag: not started.**

Active development branch: **none**.
Active work pull request: **none**.
Next implementation gate: **H3b2 only — next small, coherent image-pin batch from the remaining 23 references**.

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

Canonical merge:

- PR #78 — `H3b2a: pin KAIRO Node build images by digest`;
- merge commit: `f51ac9c0b00c46b046bb24b751540d204763bcbc`;
- validated technical head: `538af6072bee2239187339a0bf66bda8c29fa916`;
- final validated PR head: `93ad537c29d2862d210f977ab8344ef9b0c6fcd7`.

H3b2a is deliberately limited to the two KAIRO-owned Node build-base references. No Compose service image changed in this sub-gate.

Canonical H3b2a changes:

1. `apps/web/Dockerfile` pins `node:22-alpine` to `sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32`.
2. `services/realtime/Dockerfile` pins the same `node:22-alpine` image to the same digest.
3. The digest was already observed and successfully used by the final H3b1 Reproducibility build, so the intended Node tag/version line did not change.
4. `config/reproducibility-baseline.json` advances to version 4, records both Node Dockerfiles as validated digest pins, and reduces known unpinned-image debt from **31 to 29** references.
5. `scripts/smoke/reproducibility_contract.py` keeps the same fail-closed behavior; only its success message is generalized beyond H3b1.

Final PR diff contained exactly four H3b2a technical files plus this checkpoint file:

- `apps/web/Dockerfile`;
- `services/realtime/Dockerfile`;
- `config/reproducibility-baseline.json`;
- `scripts/smoke/reproducibility_contract.py`;
- `PROJECT_STATE.md` — checkpoint evidence only.

Technical-head validation on `538af607...`: **8/8 push workflows success**.

Final PR-head validation on exact head `93ad537c...`: **8/8 workflows success**:

- Baseline reproducibility validation — run `34587827514` — success, including real KAIRO container builds using the digest-pinned Node base;
- Foundation validation — run `34587827426` — success;
- Autonomous Research validation — run `34587827470` — success, including the real Worker SIGKILL replay proof;
- MCP tool registry validation — run `34587827453` — success;
- Multi-user isolation validation — run `34587827466` — success;
- Document ingestion validation — run `34587827429` — success;
- UI workspace validation — run `34587827443` — success;
- Code quality validation — run `34587827448` — success.

News ownership was path-filtered and was not triggered by this H3b2a file set.

`hardening/h3b2a-node-image-pins` is retired after merge and must not be reused. The inert remote ref may remain.

### H3b2b — Core Compose service digest pins

Canonical merge:

- PR #79 — `H3b2b: pin core service images by digest`;
- merge commit: `f510043eb69b63919c6d012208f9b64b2bb63749`;
- validated technical head: `b3d6fe1a54907699f5f15aa8243620d3cc112e7a`;
- final validated PR head: `e6170558584cf231de228ff0f11b591dfe86b509`.

H3b2b is deliberately limited to three heavily shared core Compose services. No service tag/version changed.

Canonical H3b2b changes:

1. `postgres` keeps `pgvector/pgvector:0.8.6-pg17` and pins it to `sha256:cf134a767f474095eeba57e0117be8e568e011a63f33fbf252f14c9b760f8e6f`.
2. `valkey` keeps `valkey/valkey:8.1.10-alpine` and pins it to `sha256:d2e18f3410b6f616de1417f570fa55261af2898b9c5b2cfb6781ce2373ea43d1`.
3. `nats` keeps `nats:2.14.5-alpine` and pins it to `sha256:d4ac35882ac65aff236cd65b9d3fa4d24332c681e1a85f94eedccd3cdd65b1da`.
4. `config/reproducibility-baseline.json` advances to version 5, records these exact Compose digest pins, and reduces known unpinned-image debt from **29 to 26** references.
5. `scripts/smoke/reproducibility_contract.py` now fail-closes on drift of the validated Compose digest set, including replacement of one immutable digest by another without an explicit baseline update.

Final PR diff contained exactly three H3b2b technical files plus this checkpoint file:

- `compose.yaml`;
- `config/reproducibility-baseline.json`;
- `scripts/smoke/reproducibility_contract.py`;
- `PROJECT_STATE.md` — checkpoint evidence only.

Technical-head validation on exact head `b3d6fe1a54907699f5f15aa8243620d3cc112e7a`: **8/8 push workflows success**.

Final PR-head validation on exact head `e6170558584cf231de228ff0f11b591dfe86b509`: **8/8 pull-request workflows success**:

- Baseline reproducibility validation — run `34589403058` — success, including baseline-drift proof and locked KAIRO container builds;
- Foundation validation — run `34589403074` — success, including Compose topology and integration checks;
- Autonomous Research validation — run `34589403065` — success, including the real Worker SIGKILL replay proof;
- MCP tool registry validation — run `34589403040` — success;
- Multi-user isolation validation — run `34589403060` — success;
- Document ingestion validation — run `34589403047` — success;
- UI workspace validation — run `34589403041` — success;
- Code quality validation — run `34589403070` — success.

The same exact final head also triggered the eight push-event mirrors; all **16/16** workflow executions completed successfully with no failure, cancellation or timeout.

`hardening/h3b2b-core-service-image-pins` is retired after merge and must not be reused. The inert remote ref may remain.

### H3b2c — Temporal Compose digest pins

Canonical merge:

- PR #80 — `H3b2c: pin Temporal images by digest`;
- merge commit: `082a296650d77ebbe247bb3d5360b15e621c2596`;
- base `main` at branch creation: `8a85918ab8fed681093a32ba1b2e1d4242050433`;
- validated technical head: `d5514db9fa4baf4e22a0f5f594843d5df956ce5e`;
- final validated PR head: `f0edad27bf7a2ebbc7f905bec8c1cdf52943f33e`.

H3b2c is deliberately limited to the Temporal Compose image family already configured by `.env.example`. No Temporal tag/version changed.

Canonical H3b2c changes:

1. `temporalio/server:${TEMPORAL_VERSION}` keeps `TEMPORAL_VERSION=1.31.2` and is pinned to `sha256:b5ecdb8282bededae2a10c36e8d862e27d0bc2d247fc73c5416025997ab4a1da`.
2. `temporalio/admin-tools:${TEMPORAL_ADMINTOOLS_VERSION}` keeps `TEMPORAL_ADMINTOOLS_VERSION=1.31.2` and both Compose uses are pinned to `sha256:dbc5fcd6ee8f0f4d808bf765af9a87dea9d8a283abfdcfbd2fc148496ba66107`.
3. `temporalio/ui:${TEMPORAL_UI_VERSION}` keeps `TEMPORAL_UI_VERSION=2.53.0` and is pinned to `sha256:810eba47f77a89b0e64e2e751478ca585d037bbd90c0951a2974a92a6c5adeb9`.
4. `config/reproducibility-baseline.json` advances to version 6, records the three exact Temporal Compose digest tuples, and reduces known unpinned-image debt from **26 to 23** references.
5. No reproducibility-contract code change was needed: H3b2b already made validated Compose digest pins fail closed on removal or immutable-digest substitution without an explicit baseline update.

Final PR diff contained exactly two H3b2c technical files plus this checkpoint file:

- `compose.yaml`;
- `config/reproducibility-baseline.json`;
- `PROJECT_STATE.md` — checkpoint evidence only.

Technical-head validation on exact head `d5514db9fa4baf4e22a0f5f594843d5df956ce5e`: **8/8 push workflows success**:

- Foundation validation — run `34590782585` — success;
- Code quality validation — run `34590782612` — success;
- MCP tool registry validation — run `34590782671` — success;
- Multi-user isolation validation — run `34590782745` — success;
- Document ingestion validation — run `34590782589` — success;
- UI workspace validation — run `34590782748` — success;
- Autonomous Research validation — run `34590782588` — success;
- Baseline reproducibility validation — run `34590782677` — success.

Final PR-head validation on exact head `f0edad27bf7a2ebbc7f905bec8c1cdf52943f33e`: **8/8 pull-request workflows success**:

- Baseline reproducibility validation — run `34591124988` — success;
- Foundation validation — run `34591124977` — success;
- Autonomous Research validation — run `34591125071` — success, including the real Worker SIGKILL replay proof;
- MCP tool registry validation — run `34591124990` — success;
- Multi-user isolation validation — run `34591125001` — success;
- Document ingestion validation — run `34591124975` — success;
- UI workspace validation — run `34591125050` — success;
- Code quality validation — run `34591125013` — success.

The same exact final head also triggered eight push-event mirrors. The final check found exactly eight push runs, all completed, with no failure, cancellation, timeout, action-required, startup-failure, neutral, skipped, stale or pending conclusion; therefore all **16/16** final-head workflow executions were successful.

`hardening/h3b2c-temporal-image-pins` is retired after merge and must not be reused. The inert remote ref may remain.

H3b2 is **not complete**: 23 unpinned/moving image references remain recorded in the reproducibility baseline. Do not begin H4 yet.

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

Continue **H3b2 only — External image pinning/debt reduction** through another small branch created fresh from live `main`.

The next H3b2 sub-gate should:

- select one coherent, verifiable subset from the remaining **23** unpinned/moving image references;
- preserve service versions and runtime behavior while replacing moving references with immutable digests where verifiable;
- update the reproducibility baseline only alongside concrete debt reduction;
- remain narrow enough for targeted runtime/CI validation;
- not mix H4 production/auth-boundary work or product features;
- stop and checkpoint after that sub-gate before selecting another batch.

Do not begin H4 until H3b2 is explicitly complete.

Do not begin Gantt, Calendar, Brain, Finance/Crypto, voice or other product work until H5 is complete.
