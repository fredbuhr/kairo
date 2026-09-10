# KAIRO status

Last updated: 2026-09-11

## Current phase

KAIRO is now in **Block 3 — Cockpit, daily planning and graph workspace**.

Block 1 (platform substrate/system of record) is complete. The core exit criterion for Block 2 (intelligence, memory and safe autonomy) has been reached and the G48–G50 consolidation line was promoted to `main` through PR #72. The resulting `main` merge commit `f524ed7c8e8a71fa3de882f4d294c224cb8d207f` passed all eight workflows triggered after merge, including real Research `SIGKILL` replay, destructive Restic restore and multi-user ownership isolation.

G51 is the first coherent product slice after that consolidation. It establishes a **Daily Spine** so Projects, Today and the future Gantt/Calendar use the same canonical Task planning state rather than separate UI-specific JSON.

## Last fully validated baseline

The current production-development baseline on `main` is:

`f524ed7c8e8a71fa3de882f4d294c224cb8d207f`

That merge commit completed all eight triggered push workflows successfully:

- Baseline reproducibility validation;
- Foundation validation;
- Autonomous research validation;
- MCP tool registry validation;
- Document ingestion validation;
- UI workspace validation;
- Multi-user isolation validation;
- News ownership validation.

The G51 feature branch `block3/g51-daily-spine` has also passed all seven workflows triggered by its final functional SHA before documentation synchronization, including the actual two-Keycloak-user Daily Spine integration proof.

## What is materially implemented

### Platform and canonical state

- PostgreSQL + pgvector are the authoritative system of record.
- SeaweedFS stores object/blob state behind KAIRO-owned references.
- NATS JetStream publishes canonical domain events/outbox state.
- Temporal is the durable execution substrate.
- Keycloak provides authenticated user identity.
- OpenBao provides secret-reference boundaries.
- backup/restore, readiness and recovery smoke tests exist and are exercised in CI.
- canonical migrations now run through `0012_task_planning` on G51.

### Command, policy and safe autonomy

- canonical Conversation/Command/Task/Artifact execution contracts exist;
- policy authorization, approval requests and budgets are represented in canonical state;
- LiteLLM-facing model calls are routed through KAIRO's model gateway with usage/idempotency accounting;
- replay-critical model call checkpoints are persisted through bounded Temporal heartbeats;
- ToolInvocation is canonical, owner-scoped and replay-aware;
- detailed internal diagnostics are not exposed as ordinary user-world surfaces.

### Memory and knowledge

- rebuildable derived-memory projection contracts exist;
- Mem0/Graphiti/Neo4j remain derived context engines rather than the source of truth;
- document ingestion, canonical document/chunk provenance and Knowledge inspection/search surfaces are present;
- Research Context Packs can combine canonical document context and owner-scoped derived memory without making those projections authoritative.

### Research and tools

- canonical MCP server/tool registry and policy metadata exist;
- first-party Web MCP is read-only at its current boundary;
- autonomous Research includes bounded planning, tool use and grounded synthesis;
- Research results are owner-scoped canonical Artifacts;
- the real hard-kill replay smoke verifies that already-accounted model/tool work is not silently duplicated after Worker death.

### Web/Cockpit surface

The validated line contains meaningful product surfaces rather than only architecture scaffolding:

- Cockpit shell and persisted owner-scoped workspace layouts;
- Command Center panel;
- Today workspace;
- Projects workspace;
- Research workspace;
- News workspace;
- Knowledge workspace, ingestion, inspection and search helpers;
- authenticated API/session helpers and Project selection state.

These are usable Block 3 foundations, not the final Cockpit.

## G48 — multi-user boundary hardening

G48 introduced a coherent ownership pass instead of isolated route patches:

- canonical subject ownership for polymorphic Relationships;
- owner-scoped ToolInvocations and owner-local idempotency;
- database-level consistency between ToolInvocation Task ownership and Project ownership;
- stronger approval/budget and diagnostic boundaries;
- Research propagation of ToolInvocation ownership;
- a real two-user Keycloak isolation workflow.

This removed a class of cross-user risks before additional product modules were added.

## G49 — durable Research replay

G49 fixed the last known Block 2 destructive-recovery failure.

The failure was not ordinary Research correctness: normal Research contracts and integration were already green. The failing invariant was a Worker `SIGKILL` after canonical MCP completion. The planner provider call could be repeated because the SDK heartbeat containing the replay-critical accounted checkpoint could remain coalesced in process memory too long.

G49 therefore:

- bounds Temporal heartbeat throttling for the KAIRO Worker to one second;
- makes successful `tool.invoke` Tasks return the canonical Artifact-shaped result expected by the generic Task execution workflow;
- preserves the single canonical ToolInvocation during replay;
- makes the backup/restore smoke wait for the durable PostgreSQL TCP server rather than the entrypoint's transient initialization socket server.

## G50 — baseline consolidation

G50 established the single trustworthy baseline used by later Block 3 work:

- Core and Worker `uv` build image pinned to the exact digest observed in validated CI;
- explicit reproducibility debt baseline and CI guard;
- status/roadmap/implementation-plan synchronized with the actual repository;
- Block 2 core exit recorded without claiming production readiness;
- consolidation promoted to `main` through one reviewed PR instead of merging the broad experimental spatial branch wholesale.

JavaScript/Python dependency lockfiles and several third-party immutable image digests remain explicit reproducibility debt. They are tracked rather than hidden or fabricated.

## G51 — Daily Spine

G51 establishes one canonical planning contract for everyday work.

### Canonical Task planning

`Task` now carries:

- `priority` (0–4);
- `planned_start_at`;
- `planned_end_at`;
- `due_at`.

The database enforces priority range and valid planning windows, and public Task creation requires timezone-aware timestamps.

### Owner-scoped Task updates

`PATCH /v1/tasks/{task_id}` can update title, description, priority and planning metadata. Manual status transitions are intentionally limited to `todo` / `completed`.

Once a Task has a Temporal `WorkflowExecution`, its status becomes execution-owned and a user cannot forge completion through the planning endpoint. Planning metadata can still be adjusted without rewriting the workflow state machine.

### Timezone-aware Today

`GET /v1/today?day=YYYY-MM-DD&timezone=<IANA zone>` builds an owner-scoped daily view using local calendar boundaries rather than assuming every day is 24 hours.

Tasks are grouped into:

- overdue;
- in progress;
- due today;
- planned today;
- completed today;
- unscheduled backlog.

The contract explicitly tests a DST transition day to preserve correct local-day semantics.

### Today Cockpit panel

The Web Cockpit now exposes a dockable Today workspace that can:

- browse a local day;
- see project context and timing;
- change priority;
- quickly plan one hour from the backlog;
- complete or reopen manual Tasks;
- show Workflow-managed Tasks as Temporal-controlled rather than offering a false manual status button.

### Security proof

The existing two-Keycloak-user integration test now also proves that:

- one user cannot patch another user's planning state;
- `/v1/today` never leaks another user's Task;
- manual completion appears in the correct owner's `completed_today` bucket;
- once a Task is submitted to Temporal, manual completion is rejected.

## What is not ready yet

### Gantt and graph/Brain

`packages/gantt` and `packages/graph` are still scaffolds on the validated line. The mature simple Gantt and realtime 2D/3D Brain/mycelium experience required by the product vision are **not complete**.

G51 deliberately adds the canonical dates/priority first so the Gantt does not invent a second planning model.

### Desktop/Sidecar and voice

The stabilized `apps/desktop` is still skeletal. Global summon, microphone, screenshot, clipboard, selected-filesystem access, wake word, realtime voice and local computer-use permissions are Block 4 work.

### Finance, crypto, home and development agent

The permanent architecture recognizes these specialist systems and Compose profiles exist for several engines, but the stabilized KAIRO domain adapters and user workflows are not complete. They remain Block 5 work.

### Production hardening

KAIRO is not yet a production/commercial release. Remaining work includes stronger sandboxing, full immutable dependency/SBOM policy, controlled upgrades, off-host encrypted backup drills, load/performance testing, production exposure/TLS/network policy and the complete data lifecycle.

## Branch discipline

`main` is now the validated source of truth after the G48–G50 consolidation. New Block 3 work should branch from the last validated `main` commit and return through small coherent PRs.

Large experimental work, especially the broad draft spatial-interface branch, remains a reservoir of ideas/code and must not be merged wholesale over this baseline.

## Next implementation block

After G51 promotion, continue Block 3 in this order:

1. **Gantt + Calendar** on the canonical Task planning fields established by G51;
2. 2D/3D Brain/graph on canonical Relationships and knowledge context;
3. collaboration/realtime and universal search across those surfaces.

Do not start Block 4/5 specialist expansion until these Block 3 foundations share the same ownership, Task, Artifact and workflow model.
