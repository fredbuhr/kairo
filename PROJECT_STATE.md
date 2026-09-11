# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- Clean post-reset CI baseline: `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- Baseline tag: `r7-baseline-2026-09-11` → `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- H1 Memory/Auth handoff is canonical via PR #74, merge `3fa1aa5a67628c97ee4367e9a0224cff9086fbf0`.
- Canonical main checkpoint before H2: `6e8b838b787678bcf5254bb9ef2c20a05f23ca2d`.
- `AGENTS.md` and this file define repository recovery/resume discipline.
- Rule: always fetch live `main` before acting. GitHub wins over chat memory or recorded checkpoint SHAs.

## Repository Reset status

- R0–R7: **complete**.
- Repository Reset: **complete**.

## Post-R7 audit hardening

Product feature work remains paused until H5 is complete.

1. **H1 — Memory/Auth handoff: complete and canonical.**
2. **H2 — Code hygiene: implementation validated; PR/merge next.**
3. **H3 — Reproducibility: not started.**
4. **H4 — Production/auth boundary: not started.**
5. **H5 — Full revalidation + real-engine/production checks + post-audit tag: not started.**

Active development branch: `hardening/h2-code-hygiene`.
Active work pull request: **none yet**.
H2 validated implementation head: `70febab5c06840620557d0fcefd596e20e3f9758`.

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

H2 is deliberately limited to proven cleanup and static-quality guardrails. No broad refactor and no H3 reproducibility work is included.

Implementation changes on exact code head `70febab5c06840620557d0fcefd596e20e3f9758`:

1. `.gitattributes` added to keep shell/source/config files on LF across Windows/Linux checkouts.
2. `.github/workflows/code-quality.yml` added with:
   - Ruff `F,E9` correctness/dead-import checks on Core, Worker and smoke scripts;
   - `bash -n` parsing for all tracked shell scripts under `scripts/`.
3. `scripts/bootstrap.sh` removed after usage search proved it had no live consumer; the Makefile already owns bootstrap/config setup.
4. `services/worker/src/kairo_worker/activities.py` removed the obsolete duplicate News summarizer/activity while retaining shared search/enrichment/fallback helpers used by `news_activity.py`.
5. Unused direct `boto3` dependencies removed from Core and Worker after repository-wide usage search found no imports/consumers.
6. Four unused Core settings removed after usage search proved they were read nowhere: `seaweed_s3_endpoint`, `litellm_url`, `keycloak_url`, `keycloak_realm`.

H2 implementation diff versus canonical pre-H2 `main` is exactly seven files:

- `.gitattributes` — added;
- `.github/workflows/code-quality.yml` — added;
- `scripts/bootstrap.sh` — deleted;
- `services/core/pyproject.toml` — unused dependency removed;
- `services/core/src/kairo_core/config.py` — unused settings removed;
- `services/worker/pyproject.toml` — unused dependency removed;
- `services/worker/src/kairo_worker/activities.py` — dead legacy News implementation removed.

Validation on exact H2 implementation head `70febab5...` — **8/8 workflows success**:

1. Code quality validation — run `34580077358` — success.
2. Baseline reproducibility validation — run `34580077234` — success.
3. UI workspace validation — run `34580077298` — success.
4. MCP tool registry validation — run `34580077235` — success.
5. Document ingestion validation — run `34580077277` — success.
6. Multi-user isolation validation — run `34580077266` — success.
7. Foundation validation — run `34580077301` — success.
8. Autonomous research validation — run `34580077260` — success, including the real Worker SIGKILL replay proof.

Local/static pre-push checks also passed: Python compile/AST parsing, workflow YAML parsing, `git diff --check`, and an import-usage scan.

H2 is not canonical until its PR is merged. Do not start H3 on this branch.

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

Finish **H2 only**:

1. open a PR from `hardening/h2-code-hygiene` to live `main`;
2. verify the PR diff remains the seven H2 files plus this checkpoint file only;
3. require PR checks to be green on the final checkpoint head;
4. merge H2;
5. update canonical `PROJECT_STATE.md` with the PR/merge result and mark H2 complete;
6. retire/delete the H2 branch;
7. stop before H3.

After H2 is canonical, **H3 — Reproducibility** is next. Do not begin Gantt, Calendar, Brain, Finance/Crypto, voice or other product work until H5 is complete.
