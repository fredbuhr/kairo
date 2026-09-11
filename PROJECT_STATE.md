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
   - **H3b — Container reproducibility/image pinning: next; not started.**
4. **H4 — Production/auth boundary: not started.**
5. **H5 — Full revalidation + real-engine/production checks + post-audit tag: not started.**

Active development branch: **none**.
Active work pull request: **none**.
Next implementation gate: **H3b only — Container reproducibility/image pinning**.

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

H2 removed the proven dead News implementation, obsolete bootstrap script, unused direct `boto3` dependencies and unused settings; added LF normalization plus focused Ruff/Bash static-quality checks. Final PR checks were green. A transient memory smoke timing race was confirmed by an unchanged-head rerun rather than hidden by a product-code change.

`hardening/h2-code-hygiene` is retired and must not be reused.

### H3a — Dependency locks and frozen direct CI

Canonical merge:

- PR #76 — `H3a: lock dependency graphs and freeze direct CI installs`;
- merge commit: `ecc3394a648070b16ab4505e07706006999ab945`;
- validated implementation head: `6a62b7ac8411543ddd6c4253675f00bae5538b62`;
- final PR head: `215927227baaf051865d9a5b59c65cf2c0f934d0`.

Canonical H3a changes:

1. Added root `pnpm-lock.yaml` for the JS/TS workspace.
2. Added root `uv.lock` for the existing UV workspace (`services/core` + `services/worker`).
3. Added `uv.toml` with `required-version = "==0.12.13"`; root `package.json` already pins `pnpm@10.15.1`.
4. Reproducibility CI now proves `pnpm install --frozen-lockfile`, `uv lock --check`, required lockfile presence and toolchain-pin stability.
5. Direct non-container CI paths in Foundation, UI, Research, MCP and News use locked UV execution.
6. The reproducibility baseline/contract now fails closed if lockfiles/toolchain pins drift.
7. Remaining Docker-context unlocked installs and unpinned/moving image references remain explicitly recorded debt for H3b.

No Dockerfile or Compose file changed in H3a.

Validation on exact implementation head `6a62b7ac...`: **9/9 workflows success**:

- Reproducibility `34583114892`;
- UI `34583114854`;
- News ownership `34583114840`;
- Foundation `34583114819`;
- Autonomous Research `34583114839`, including real Worker SIGKILL replay;
- MCP `34583114862`;
- Multi-user isolation `34583114913`;
- Documents `34583114942`;
- Code quality `34583114843`.

Final PR head `21592722...` also passed **9/9 pull-request workflows**. Important final runs include Foundation `34583611695` and Autonomous Research `34583611700`, both success; the latter retained the real Worker SIGKILL replay proof.

The temporary branch-only workflow used to bootstrap the initial lockfiles was deleted before the validated implementation head and never entered the PR diff.

A non-fatal pnpm peer warning remains for `@react-three/fiber` versus React 19.3. Frozen install, typecheck and Web build pass; treat it as ecosystem warning unless it becomes a concrete incompatibility.

`hardening/h3a-dependency-locks` is retired after merge and must not be reused. The connector does not expose branch-ref deletion, so the inert remote ref may remain.

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

Perform **H3b only — Container reproducibility/image pinning** from a fresh branch created from live `main`.

H3b should remain bounded to container reproducibility:

- make Core/Worker/Web/Realtime container installs consume locked dependency graphs rather than resolving freely inside isolated Docker contexts;
- adjust build contexts/Dockerfiles only as much as required to expose canonical lockfiles safely;
- reduce moving/unpinned image references, prioritizing critical runtime/infrastructure images;
- update the reproducibility baseline only alongside concrete debt reduction;
- do not mix H4 production serving, public URLs, JWT/Web-MCP auth-boundary work or product features;
- stop after H3b merge/checkpoint before beginning H4.

Do not begin Gantt, Calendar, Brain, Finance/Crypto, voice or other product work until H5 is complete.
