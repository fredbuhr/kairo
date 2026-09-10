# KAIRO status

Last updated: 2026-09-11

## Current phase

KAIRO is at the **consolidation boundary between Block 2 and Block 3**.

Block 1 (platform substrate/system of record) is complete. The **core exit criterion for Block 2 (intelligence, memory and safe autonomy) has been reached**: KAIRO can run an approved research workflow, route model calls through the gateway, use an MCP tool, persist canonical results, preserve ownership boundaries, resume after a real Worker SIGKILL without duplicating external work, and account for provenance/cost through canonical records.

The current work is deliberately not adding product surface. G50 is consolidating the validated baseline, documenting remaining reproducibility debt and preparing one trustworthy branch for promotion before deeper Block 3 work resumes.

## Last fully validated baseline

The G49 baseline is commit `5df3f8872a899c886a588c9232053e5402260a98` on `consolidate/g49-research-replay`.

On that exact SHA, all six workflows triggered by the G49 change completed successfully:

- Foundation validation;
- Autonomous research validation;
- MCP tool registry validation;
- Document ingestion validation;
- UI workspace validation;
- Multi-user isolation validation.

The important destructive proofs are green on the same baseline:

- Restic backup/restore survives a destructive restore drill for PostgreSQL, NATS, SeaweedFS and OpenBao;
- a real KAIRO Worker `SIGKILL` during Research resumes from Temporal state with exactly one planner provider call, one remote MCP call, one synthesis provider call and one final Research Artifact;
- two authenticated Keycloak users are isolated across owner-scoped Projects/Tasks, Relationships, approvals/budgets, ToolInvocations/idempotency and memory access.

## What is materially implemented

### Platform and canonical state

- PostgreSQL + pgvector are the authoritative system of record.
- SeaweedFS stores object/blob state behind KAIRO-owned references.
- NATS JetStream publishes canonical domain events/outbox state.
- Temporal is the durable execution substrate.
- Keycloak provides authenticated user identity.
- OpenBao provides secret-reference boundaries.
- backup/restore, readiness and recovery smoke tests exist and are exercised in CI.
- canonical migrations currently run through `0011_tool_invocation_ownership`.

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

The stabilization line already contains meaningful product surfaces rather than only architecture scaffolding:

- Cockpit shell and persisted owner-scoped workspace layouts;
- Command Center panel;
- Projects workspace;
- Research workspace;
- News workspace;
- Knowledge workspace, ingestion, inspection and search helpers;
- authenticated API/session helpers and Project selection state.

These surfaces are an early usable Block 3 foundation, not the final Cockpit.

## G48 — multi-user boundary hardening

G48 introduced a coherent ownership pass instead of isolated route patches:

- canonical subject ownership for polymorphic Relationships;
- owner-scoped ToolInvocations and owner-local idempotency;
- database-level consistency between ToolInvocation Task ownership and Project ownership;
- stronger approval/budget and diagnostic boundaries;
- Research propagation of ToolInvocation ownership;
- a real two-user Keycloak isolation workflow.

This removed a class of cross-user risks before additional product modules are added.

## G49 — durable Research replay

G49 fixed the last known Block 2 destructive-recovery failure.

The failure was not ordinary Research correctness: normal Research contracts and integration were already green. The failing invariant was a Worker `SIGKILL` after canonical MCP completion. The planner provider call could be repeated because the SDK heartbeat containing the replay-critical accounted checkpoint could remain coalesced in process memory too long.

G49 therefore:

- bounds Temporal heartbeat throttling for the KAIRO Worker to one second;
- makes successful `tool.invoke` Tasks return the canonical Artifact-shaped result expected by the generic Task execution workflow;
- preserves the single canonical ToolInvocation during replay;
- makes the backup/restore smoke wait for the durable PostgreSQL TCP server rather than the entrypoint's transient initialization socket server.

The resulting G49 SHA is all-green for the triggered validation set.

## G50 — baseline consolidation (current)

G50 is intentionally infrastructure/documentation work, not feature expansion.

Current objectives:

1. pin build inputs when an immutable digest was actually observed in the validated G49 CI;
2. record all remaining image/install/lockfile reproducibility debt explicitly rather than pretending it is solved;
3. fail CI if new reproducibility debt appears silently;
4. update status/roadmap/implementation-plan documents so they describe the repository that actually exists;
5. validate the consolidation SHA before proposing promotion to `main`.

The Core and Worker `uv` build image is now pinned to the exact digest observed in the validated G49 build. JavaScript/Python dependency lockfiles are still a known gap and must be generated by the real package resolvers, not fabricated manually. Several third-party Compose images also still use mutable tags; G50 tracks this as explicit debt so it can only change deliberately.

## What is not ready yet

### Gantt and graph/Brain

`packages/gantt` and `packages/graph` are still scaffolds on the stabilized line. The mature simple Gantt and realtime 2D/3D Brain/mycelium experience required by the product vision are **not complete**.

### Desktop/Sidecar and voice

The stabilized `apps/desktop` is still skeletal. Global summon, microphone, screenshot, clipboard, selected filesystem access, wake word, realtime voice and local computer-use permissions are Block 4 work.

### Finance, crypto, home and development agent

The permanent architecture recognizes these specialist systems and Compose profiles exist for several engines, but the stabilized KAIRO domain adapters and user workflows are not complete. They remain Block 5 work.

### Production hardening

KAIRO is not yet a production/commercial release. Remaining work includes stronger sandboxing, full immutable dependency/SBOM policy, controlled upgrades, off-host encrypted backup drills, load/performance testing, production exposure/TLS/network policy and the complete data lifecycle.

## Branch discipline

The repository has accumulated stacked and experimental branches. The validated consolidation line should be treated as the source of truth. Large experimental work, especially the broad draft spatial-interface branch, is a reservoir of ideas/code and must not be merged wholesale over the validated baseline.

After G50 is green, consolidation should happen through one reviewed promotion path to `main`; obsolete or superseded branches can then be archived/closed separately rather than mixed into feature development.

## Next implementation block

After baseline promotion, resume Block 3 in coherent product slices:

1. Projects / Tasks / Today as the daily operational spine;
2. simple but capable Gantt + calendar planning on the same canonical Task model;
3. 2D/3D Brain/graph on the same canonical relationships and knowledge context;
4. collaboration/realtime and universal search across those surfaces.

Do not start Block 4/5 specialist expansion until these Block 3 foundations share one ownership, Task, Artifact and workflow model.
