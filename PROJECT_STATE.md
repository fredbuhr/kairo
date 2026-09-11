# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- Clean post-reset CI baseline: `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- Baseline tag: `r7-baseline-2026-09-11` → `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- H1 Memory/Auth handoff is canonical via PR #74, merge `3fa1aa5a67628c97ee4367e9a0224cff9086fbf0`.
- H2 Code hygiene is canonical via PR #75, merge `31e53b88135ac2db4600bb00a4112bc14d46ba5d`.
- `AGENTS.md` and this file define repository recovery/resume discipline.
- Rule: always fetch live `main` before acting. GitHub wins over chat memory or recorded checkpoint SHAs.

## Repository Reset status

- R0–R7: **complete**.
- Repository Reset: **complete**.

## Post-R7 audit hardening

Product feature work remains paused until H5 is complete.

1. **H1 — Memory/Auth handoff: complete and canonical.**
2. **H2 — Code hygiene: complete and canonical.**
3. **H3 — Reproducibility: next; not started.**
4. **H4 — Production/auth boundary: not started.**
5. **H5 — Full revalidation + real-engine/production checks + post-audit tag: not started.**

Active development branch: **none**.
Active work pull request: **none**.
Next implementation gate: **H3 only — Reproducibility**.

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

H2 remained deliberately limited to proven cleanup and static-quality guardrails. No broad refactor and no H3 reproducibility work was included.

Canonical H2 changes:

1. `.gitattributes` keeps shell/source/config files on LF across Windows/Linux checkouts.
2. `.github/workflows/code-quality.yml` adds:
   - Ruff `F,E9` correctness/dead-import checks on Core, Worker and smoke scripts;
   - `bash -n` parsing for all tracked shell scripts under `scripts/`.
3. `scripts/bootstrap.sh` was removed after usage search proved it had no live consumer; the Makefile already owns bootstrap/config setup.
4. `services/worker/src/kairo_worker/activities.py` removed the obsolete duplicate News summarizer/activity while retaining shared search/enrichment/fallback helpers used by `news_activity.py`.
5. Unused direct `boto3` dependencies were removed from Core and Worker after repository-wide usage search found no imports/consumers.
6. Four unused Core settings were removed after usage search proved they were read nowhere: `seaweed_s3_endpoint`, `litellm_url`, `keycloak_url`, `keycloak_realm`.

H2 implementation diff versus canonical pre-H2 `main` was exactly seven implementation/config files plus this checkpoint file:

- `.gitattributes` — added;
- `.github/workflows/code-quality.yml` — added;
- `scripts/bootstrap.sh` — deleted;
- `services/core/pyproject.toml` — unused dependency removed;
- `services/core/src/kairo_core/config.py` — unused settings removed;
- `services/worker/pyproject.toml` — unused dependency removed;
- `services/worker/src/kairo_worker/activities.py` — dead legacy News implementation removed;
- `PROJECT_STATE.md` — gate/checkpoint evidence only.

Validation on exact H2 implementation head `70febab5...` — **8/8 workflows success**:

1. Code quality validation — run `34580077358` — success.
2. Baseline reproducibility validation — run `34580077234` — success.
3. UI workspace validation — run `34580077298` — success.
4. MCP tool registry validation — run `34580077235` — success.
5. Document ingestion validation — run `34580077277` — success.
6. Multi-user isolation validation — run `34580077266` — success.
7. Foundation validation — run `34580077301` — success.
8. Autonomous research validation — run `34580077260` — success, including the real Worker SIGKILL replay proof.

Final PR-head validation on `ca2464b...` also finished green across all eight workflows. Foundation run `34580502091` initially exposed a timing race in `memory-projection-integration`: the smoke read a projection Task while it was still `running`, immediately before the Worker completed it. A targeted rerun of that same job on the unchanged PR head passed; the workflow run then concluded **success**. No product/code change was made to mask the transient failure.

Local/static pre-push checks also passed: Python compile/AST parsing, workflow YAML parsing, `git diff --check`, and an import-usage scan.

`hardening/h2-code-hygiene` is retired after merge and must not be reused. The connector does not expose branch-ref deletion, so the inert remote ref may remain.

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

Perform **H3 only — Reproducibility** from a fresh branch created from live `main`.

H3 should remain bounded to reproducibility work already identified by the post-R7 audit:

- introduce lockfiles/frozen dependency installs where appropriate;
- reduce critical moving Docker tags/digests while keeping the reproducibility contract truthful;
- preserve the existing reproducibility-debt drift guard or update it only alongside concrete debt reduction;
- avoid production/auth-boundary work reserved for H4;
- stop after H3 merge/checkpoint before beginning H4.

Do not begin Gantt, Calendar, Brain, Finance/Crypto, voice or other product work until H5 is complete.
