# KAIRO status

Last updated: 2026-09-11

## Current phase

KAIRO is in **Repository Reset / baseline hardening**.

The canonical product line has reached **G51 — Daily Spine**. Git-ref cleanup (R4–R5c) is complete and the repository file/directory inventory (R6) is complete. There is currently **no active development branch and no active pull request**. The only remaining reset gate is R7: establish a clean tagged baseline with green CI before product work resumes.

## Canonical baseline

`main` is the only integrated source of truth.

R5c completion checkpoint before the R6 documentation/archive cleanup:

`b715f2952bad0976dadbe33cb6191e0402698e9c`

The last fully revalidated product checkpoint remains:

`69cf0dd52eea93f7e5b9bf7413cde2cb51c2c8b5`

The G51 merge commit is:

`f1dbb6e6ae1a4d419bc35a924639be713263fb77`

The exact PR #73 head validated before merge was `9af0573d7295d3da10c06477752f07ec4ac51541`. All eight workflows associated with that exact head passed: Foundation, Autonomous Research, MCP tool registry, Document ingestion, UI workspace, Multi-user isolation, News ownership and Baseline reproducibility.

After the R2 checkpoint commit, the seven workflows triggered on the new `main` checkpoint also passed, including Foundation and the real Autonomous Research Worker `SIGKILL` replay. News ownership was not retriggered by that documentation-only checkpoint; its most recent validation remains the green PR #73 head.

Recorded SHAs are checkpoints only. Every new work session must fetch the live `main` head before acting.

## What is materially implemented and validated

### Platform and canonical state

- PostgreSQL + pgvector are the authoritative domain system of record.
- SeaweedFS stores binary/object state behind KAIRO-owned references.
- NATS JetStream carries transactional-outbox-derived domain events.
- Temporal is the durable execution authority for in-flight workflows.
- Keycloak provides authenticated identity; KAIRO owns domain authorization.
- OpenBao provides the secret-reference boundary used by Core.
- Restic backup/restore and destructive recovery are exercised in CI.
- Canonical migrations currently run through `0012_task_planning`.

### Command, policy and safe autonomy

- canonical Conversation, Command, Task, WorkflowExecution and Artifact contracts exist;
- policy authorization, approvals and hard budgets are represented in canonical state;
- LiteLLM-facing model calls use KAIRO model-gateway accounting/idempotency contracts;
- PydanticAI semantic routing and bounded autonomous research are integrated;
- ToolInvocation is canonical, subject-owned and replay-aware;
- public ownership boundaries fail closed and the real two-Keycloak-user isolation workflow is green.

### Memory, documents and knowledge

- derived memory is rebuildable and non-authoritative;
- Mem0 and Graphiti/Neo4j are treated as context/projection engines rather than canonical state;
- Docling-backed document ingestion, versioning, chunks and provenance are implemented;
- Knowledge ingestion, inspection and search surfaces exist in the Web workspace;
- Research Context Packs can consume canonical document context plus owner-scoped derived memory.

### Research and tools

- canonical MCP server/tool registry and policy metadata exist;
- first-party Web MCP is read-only at its validated boundary;
- autonomous Research performs bounded planning, tool use and grounded synthesis;
- Research results are owner-scoped canonical Artifacts;
- the destructive Research smoke kills the real Worker and proves replay does not silently duplicate already-accounted external work.

### Cockpit and everyday planning

The canonical Web line contains working product foundations rather than only architecture declarations:

- Cockpit shell with persisted subject-scoped workspace layouts;
- Command Center;
- Projects workspace;
- Today workspace;
- Research workspace;
- News workspace;
- Knowledge ingestion/search/inspection workspace;
- authenticated Web session/API helpers and project selection state.

G51 adds the shared planning model used by Today and future scheduling surfaces:

- `Task.priority` from 0 to 4;
- `planned_start_at`;
- `planned_end_at`;
- `due_at`;
- owner-scoped `PATCH /v1/tasks/{task_id}` planning updates;
- workflow-managed status protection once Temporal owns execution;
- timezone-aware `GET /v1/today` with correct local-day/DST semantics.

## Consolidation milestones represented in `main`

### G48 — multi-user boundary hardening

G48 introduced coherent subject ownership for Relationships and ToolInvocations, owner-local idempotency, stronger approval/budget boundaries, safer diagnostics and the real two-user Keycloak isolation proof.

### G49 — replay and execution repair

The G49 line ultimately promoted to `main` fixed the destructive Research replay failure by bounding Temporal heartbeat throttling, repaired the generic `tool.invoke` Task result so it matches the canonical Artifact contract, and corrected backup/restore PostgreSQL readiness detection. The alternative later `consolidate/g49-research-durable-stages` branch is **not** canonical and must not be treated as the implementation in `main`.

### G50 — reproducibility baseline

G50 pinned the Core/Worker uv build image to the observed validated digest, added an explicit reproducibility-debt baseline and CI guard, synchronized consolidation documentation and promoted the G48–G50 line to `main` without merging the broad experimental spatial branch wholesale.

Known reproducibility debt remains explicit rather than hidden: JavaScript/Python dependency lockfiles are not yet complete, and several optional or external service images still use floating tags.

### G51 — Daily Spine

G51 establishes one canonical Task planning contract for Projects, Today and future Gantt/Calendar work. Its owner-scoped update rules, timezone-aware Today endpoint, Web Today panel and two-user security proof are integrated in `main`.

## What is not ready yet

### Gantt and Calendar

`packages/gantt` currently contains only planning data interfaces; the mature Gantt renderer/editor is not implemented. SVAR React Gantt and Schedule-X are installed dependencies, not evidence of a completed product capability.

Calendar normalization/adapters and a complete Calendar workspace are also not yet part of the stabilized line.

### Brain / graph

`packages/graph` currently contains only graph snapshot interfaces on canonical `main`. React Flow, React Three Fiber and react-force-graph-3d are installed, but the realtime 2D/3D mycelium Brain experience remains future Block 3 work.

### Realtime collaboration

The Hocuspocus/Yjs realtime service exists as scaffolding/configuration, but canonical collaborative persistence and a mature multi-user document workflow are not production-ready.

### Desktop, presence and voice

`apps/desktop` is still skeletal. Tauri native permissions, global summon, screen/clipboard/filesystem access, microphone/wake word, LiveKit voice orchestration and local computer-use controls remain later work. Voice services being declared or present in Compose does not mean the end-user voice plane is complete.

### Finance, crypto, home and development agent

Rotki, Actual Budget, Hummingbot, Home Assistant, OpenHands and related libraries/profiles are architecture targets or optional engines. The stabilized KAIRO-owned adapters, policy flows and user workspaces are not complete on `main`.

### Production/commercial readiness

KAIRO is not yet production/commercial-ready. Remaining work includes stronger sandboxing, complete immutable dependency/SBOM policy, controlled upgrades, off-host encrypted backup drills, load/performance testing, production TLS/network exposure policy and full data lifecycle/erasure hardening.

## Repository reset status

- R0 — establish repository truth: **complete**
- R1 — install recovery protocol: **complete**
- R2 — validate/promote G51: **complete**
- R3 — synchronize canonical documentation: **complete**
- R4 — inventory branches and pull requests: **complete**
- R5a/R5b/R5c — close/remove superseded Git refs: **complete**
- R6 — inventory files/directories and archive true historical evidence: **complete**
- R7 — establish a clean tagged, green baseline: **next**

R6 found no active implementation file that could be safely removed. All current smoke scripts are referenced by CI workflows, the Web/Core/Worker code is active canonical implementation, and the Desktop/Realtime/Gantt/Graph/shared-package skeletons are intentional scaffolds. The dated 2026-09-08 implementation audit is historical evidence and is archived under `docs/archive/`.

## Branch discipline

`main` is the only canonical integrated line. Exactly two non-canonical branches remain temporarily for salvage: `feat/kairo-test-interface-v1` (broad prototype reservoir) and `consolidate/g49-research-durable-stages` (focused Research design reservoir). Neither may be merged wholesale or resumed as the active line.

## Next action

The next gate is **R7 — clean tagged baseline with green CI**. No product feature work should start before R7 is complete.

After R7, the intended product sequence is:

1. Gantt + Calendar on the canonical G51 Task planning fields;
2. 2D/3D Brain/graph on canonical Relationships and knowledge context;
3. collaboration/realtime and universal search;
4. desktop/voice/presence;
5. specialist Finance/Crypto/Home capabilities behind KAIRO-owned contracts.
