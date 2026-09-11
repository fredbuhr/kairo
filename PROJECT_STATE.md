# KAIRO — current project state

Last checkpoint review: 2026-09-11 (Europe/Paris)

## Canonical integrated line

- Canonical branch: `main`.
- Last integrated product milestone: **G51 Daily Spine**.
- G51 merge commit: `f1dbb6e6ae1a4d419bc35a924639be713263fb77`.
- Clean post-reset CI baseline: `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- Baseline tag: `r7-baseline-2026-09-11` → `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- First post-audit hardening merge: **H1 Memory/Auth handoff**, PR #74, merge commit `3fa1aa5a67628c97ee4367e9a0224cff9086fbf0`.
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

The post-reset audit found one production-path bug plus bounded code-hygiene, reproducibility and production-boundary debt. Product feature work remains paused until H5 is complete.

Hardening sequence:

1. **H1 — Memory/Auth handoff: complete.** Authenticated Worker startup of system-owned memory projection Tasks now uses a dedicated internal-token path and is covered by an authenticated regression proof.
2. **H2 — Code hygiene: next.** Remove dead News implementation/bootstrap/dependencies proven unused, add `.gitattributes`, and enable focused lint/static checks without broad refactoring.
3. **H3 — Reproducibility.** Introduce lockfiles/frozen installs and reduce critical moving Docker tags/digests while keeping the reproducibility contract truthful.
4. **H4 — Production/auth boundary.** Production Web serving/public URLs, stricter JWT audience/client validation, Web MCP bootstrap path, and explicit profiles for unfinished/exposed services.
5. **H5 — Full revalidation.** Run the canonical suite plus targeted real-engine/production checks, synchronize docs, and create a new post-audit hardening tag.

Active development branch: **none**.
Active work pull request: **none**.
Next implementation gate: **H2 only**.

### H1 — Memory/Auth handoff

Canonical merge:

- PR: `#74` — `H1: fix authenticated memory projection handoff`.
- merge commit: `3fa1aa5a67628c97ee4367e9a0224cff9086fbf0`.
- validated implementation head: `cf04b45d7a10fcc07af16e8e5806f2ddd2d1249f`.
- final PR head: `ad7ed78dac30669c2a8b9c179a407381fb38e947`.

Changes:

- `services/core/src/kairo_core/workflows.py` adds internal-token-protected `/internal/v1/tasks/{task_id}/run`, restricted to Tasks with `owner_type == "system"`;
- `services/worker/src/kairo_worker/memory_events.py` uses that internal route with `X-Kairo-Internal-Token` instead of the authenticated public user Task-run endpoint;
- `.github/workflows/multi-user-isolation.yml` starts the Worker while Keycloak remains enabled and uses deterministic memory projector mode;
- `scripts/smoke/multi_user_isolation.py` now requires authenticated Worker-driven Mem0/Graphiti projections to reach `projected` and still proves cross-user 404 isolation.

Validation evidence:

- Multi-user isolation run `34578505066` on the exact H1 implementation head: **success**; Keycloak, Core and Worker were active and the new authenticated memory projection assertion passed.
- Foundation run `34578505040` on the exact H1 implementation head: **all eight jobs success**, including compile/build, existing memory projection, authenticated resources, policy, command, crash/outbox and backup/restore proofs.
- PR #74 checks on final head `ad7ed78...`: Reproducibility, UI, Documents, MCP, Multi-user, Autonomous Research and Foundation all completed successfully; Foundation run `34578930269` finished **success**.

The branch `hardening/h1-memory-auth-handoff` is **retired after merge**. The current connector does not expose branch-ref deletion, so do not reuse it. H2 must be created fresh from live `main`.

## Canonical branch policy

Canonical truth is `main`. Two non-canonical salvage reservoirs remain intentionally available:

1. `feat/kairo-test-interface-v1` — broad prototype/salvage reservoir; never merge wholesale.
2. `consolidate/g49-research-durable-stages` — focused Research design reservoir; never resume as active development.

A merged hardening branch may temporarily remain as an inert remote ref when the available connector cannot delete refs. It is not an active development branch and must never be resumed.

For every next gate:

1. fetch live `main`;
2. create exactly one fresh implementation branch;
3. keep the gate small and targeted;
4. validate it;
5. merge it;
6. retire/delete the branch;
7. update this file;
8. stop before the following gate.

## R6 inventory summary

At the R6 checkpoint the repository contained **234 tracked files**:

- **215 active canonical implementation/configuration/documentation files**;
- **18 intentional scaffold files** across Desktop, Realtime, Gantt, Graph, Protocol and shared UI;
- **1 historical audit file** archived at `docs/archive/audit-2026-09-08.md`;
- **0 duplicate/stale files remaining after R6 cleanup**;
- **0 tracked files proven safely removable at that checkpoint**.

Intentional scaffolds do not imply product completion. In particular `packages/gantt`, `packages/graph`, `services/realtime` and `apps/desktop` remain future boundaries rather than mature capabilities.

## R7 validation summary

The exact baseline `6cf3647a609bbd8463cb734e87eb4088572bc037` passed all seven push workflows:

1. Baseline reproducibility validation — run `34573983621` — success.
2. UI workspace validation — run `34573983736` — success.
3. MCP tool registry validation — run `34573983615` — success.
4. Multi-user isolation validation — run `34573983654` — success.
5. Document ingestion validation — run `34573983738` — success.
6. Foundation validation — run `34573983693` — success.
7. Autonomous research validation — run `34573983651` — success.

Key validated invariants include canonical ownership boundaries, Temporal crash/replay behavior, real Worker SIGKILL Research replay, command/model accounting, memory projections, MCP, Documents, backup/restore, Today/G51 planning and reproducibility-debt drift protection.

`News ownership validation` is path-filtered. Its validated G51 code head remained unchanged through the R7 baseline except for documentation-only commits, so its successful proof carries forward for the same product code.

## Next action

Perform **H2 only — Code hygiene** from a fresh branch created from live `main`.

H2 should remain bounded to proven cleanup/static-quality work:

- remove the dead legacy News summary/activity path while retaining shared News helpers used by `news_activity.py`;
- remove `scripts/bootstrap.sh` only after re-confirming it has no live consumer;
- remove Python dependencies/settings only when usage search proves them unused;
- add `.gitattributes` to force LF for shell/source/config files used from Windows;
- add a focused Python lint/static check to CI (prefer Ruff) and resolve only findings introduced/exposed by that selected ruleset;
- avoid refactoring large Research/Temporal functions solely for style;
- stop after H2 merge/checkpoint before beginning H3.

Do not begin Gantt, Calendar, Brain, Finance/Crypto, voice or other product work until H5 is complete.
