# KAIRO implementation status

Last updated: 2026-09-09

## Current phase

KAIRO is transitioning from **Block 2 — intelligence, memory and safe autonomy** into the permanent **Block 3 — Cockpit / Test Interface v1**.

The active Block 3 branch no longer treats the frontend as a disposable dashboard prototype. The shell, spatial world model and operational workspaces being built now are intended to remain the daily-use test interface while later capabilities fill the same structure.

Three stacked pull requests must remain in order:

1. **PR #36 — durable multi-slot Research synthesis** (`feat/research-synthesis-checkpoints` → `main`);
2. **PR #37 — Research through the Command Kernel** (`feat/research-command-handoff` → PR #36);
3. **PR #39 — KAIRO Test Interface v1** (`feat/kairo-test-interface-v1` → PR #37).

All three remain intentionally unmerged while GitHub Actions issue **#38** prevents GitHub-hosted jobs from receiving a runner. A red check with `runner_id=0` / no executed steps is an infrastructure failure, not code validation. Real `ubuntu-latest` runs are still required before merge.

## Canonical architecture active

- PostgreSQL + pgvector is the canonical domain/state store.
- SeaweedFS is canonical object storage.
- Temporal owns durable workflow execution and replay/recovery.
- NATS JetStream is the event bus, fed by a transactional PostgreSQL outbox.
- Keycloak and OpenBao define identity/secrets boundaries.
- canonical Conversation / Message / Command records own conversational continuity.
- KAIRO-owned Capability contracts sit above replaceable specialist engines.
- deterministic routing is first-tier; constrained PydanticAI semantic routing is second-tier.
- LiteLLM is the model gateway; canonical model usage/budget accounting remains in PostgreSQL.
- Langfuse is observability only.
- Mem0 and Graphiti/Neo4j remain rebuildable projections, never canonical state.
- Docling-backed ingestion produces canonical Documents / Versions / Chunks with provenance.
- MCP tools are registered and executed through KAIRO-owned policy/contract boundaries.
- specialist workspaces are views/controls over canonical APIs, not parallel frontend-owned applications.

## Block 1 — platform substrate

**Implementation: complete.**

Canonical Projects, Tasks, Relationships, WorkflowExecutions, Artifacts, Assets, Devices, SecretReferences, Audit and Outbox records are in place together with deterministic Temporal identity, transactional event delivery, authenticated resources, SeaweedFS digest verification, OpenBao secret-reference non-disclosure and Restic backup/restore coverage.

Previously executed Foundation proofs established the substrate invariants. Current heads still need fresh real-runner validation once issue #38 is resolved.

## Block 2 — intelligence and safe autonomy

### Policy, approvals and model accounting

**Implemented.**

KAIRO Core owns approvals, authority ceilings, hard Task budgets, signed capability tokens and canonical model usage accounting. Replay/checkpoint rules fail closed around ambiguous paid-provider outcomes.

### Command Kernel

**Implemented on the stacked Block 2 head.**

`POST /v1/assistant/commands` is the canonical conversational entry point, with deterministic routing first and durable constrained semantic routing second. Conversation/Message/Command state is canonical and routable capability contracts remain KAIRO-owned.

### News Intelligence

**Implemented as `news.brief`.**

SearXNG discovery, transient extraction, sourced synthesis, market-impact mode, optional local Kokoro speech and durable Temporal execution are integrated.

### Memory and temporal context

**Implemented as rebuildable projections.**

Mem0 and Graphiti consume canonical conversational events. Generative Graphiti fact/entity extraction remains deliberately deferred until it can pass through KAIRO's replay-safe/accounted model boundary.

### Canonical documents

**Implemented.**

Asset → Document → DocumentVersion → DocumentChunk is the canonical provenance chain. Ingestion is durable, source hashes are verified and Docling is the preferred parser.

### MCP tool boundary

**Implemented.**

The registry, explicit policy, schema snapshots, Worker live-server revalidation and child tool-invocation Tasks are in place.

### Autonomous Research

**Implemented in stacked layers; final synthesis/handoff awaits real CI validation.**

PR #36 adds replay-safe multi-slot synthesis with canonical MCP evidence citations. PR #37 makes Research a Command capability and projects terminal results/failures back into the canonical Conversation idempotently.

## Block 3 — KAIRO Test Interface v1

**Active implementation: PR #39.**

`docs/interface-v1.md` is the structural interface contract. The goal is one permanent test shell, not successive throwaway frontend generations.

### Product shell

Implemented:

- stable left primary navigation;
- central spatial workspace where the mycelium is the workspace rather than a card;
- collapsible contextual right rail;
- compact always-available KAIRO command dock;
- assistant drawer preserving Command / News / Research;
- universal canonical graph search;
- accessible non-3D graph projection;
- explicit unavailable states for genuinely unimplemented areas.

### Canonical spatial graph

Implemented:

- `GET /v1/graph/home`;
- `GET /v1/graph/neighborhood/{entity_type}/{entity_id}`;
- `GET /v1/graph/search`;
- canonical `relationships` edges + canonical FK-derived structure with distinct provenance;
- presentation-only importance/activity/recency/degree/cluster hints/LOD;
- no Graphiti/Mem0 relationship silently promoted to canonical truth.

### Mycelium product renderer

Implemented as the one engine for Home and KAIRO Brain:

- custom React Three Fiber / Three.js renderer;
- deterministic Web Worker layout;
- instanced nodes;
- batched multi-strand curved filaments;
- sparse organic cluster atmosphere without enclosing category bubbles;
- bounded importance-ranked labels;
- semantic zoom / visual LOD;
- hover/selection neighborhood emphasis;
- branch isolation and type/relation filters;
- per-context pose caches + Worker warm starts for spatial familiarity;
- restrained focus camera transitions;
- reduced-motion support;
- Auto/High/Balanced/Eco quality, including measured frame-budget adaptation.

ADR-027 defines canonical graph provenance. ADR-028 defines stable/batched spatial rendering.

### Live graph activity

Implemented:

- sanitized `GET /v1/graph/activity/stream` SSE from canonical Outbox rows;
- coalesced graph invalidation in the browser;
- short-lived active entity keys drive bounded instanced pulses;
- pulses therefore represent real KAIRO activity rather than random decorative traffic.

### Natural-language spatial navigation

Implemented deterministically/read-only:

- `POST /v1/graph/directives/resolve`;
- `focus_entity` and `isolate_entity`;
- typed entity hints;
- ambiguity falls back to search;
- non-navigation language continues through the normal Command Kernel;
- models never receive direct Three.js authority.

### Projects workspace

**Active.**

- canonical project list/create;
- parent-project selection;
- real human-work Task counts;
- direct navigation to the same Project node in KAIRO Brain;
- project creation invalidates both operational and graph read models.

### Tasks / Today workspace

**Active.**

Migration `0008_task_planning_fields` adds canonical Task:

- `priority`;
- `planned_start_at`;
- `planned_end_at`;
- `due_at`.

`PATCH /v1/tasks/{task_id}/planning` validates timezone-aware intervals, audits mutations, emits `task.updated` and keeps lifecycle timestamps coherent.

`GET /v1/today` deterministically projects human work into mutually exclusive groups:

1. overdue;
2. due today;
3. planned today;
4. explicit high priority.

No LLM/frontend heuristic invents urgency. The Tasks workspace supports Today, all-task filtering, completion/reopen/start and explicit planning edits.

ADR-030 records this planning contract.

### Gantt

**Active inside Tasks.**

`@kairo/gantt` projects the same canonical Task planning fields into renderer-independent timeline geometry. The UI offers 14/30/90 day ranges, project filtering, interval bars, due-only milestones, deadline markers and unscheduled work. No separate Gantt plan database is introduced.

### Calendar

**Active.**

The Calendar workspace projects the same Task planning intervals into a weekly 06:00–22:00 view, with due-only deadlines, project filtering and direct graph navigation. External calendars are not yet integrated; when they are, they must retain explicit source/provenance rather than replacing KAIRO planning facts.

### Knowledge workspace

**Active.**

- canonical document library;
- file import through Asset → Document → Version → Chunks;
- version/chunk inspection;
- durable reingestion from the immutable source Asset;
- direct navigation to the same Document node in KAIRO Brain;
- `GET /v1/knowledge/search` searches only the newest completed owned Document generation;
- SQL ownership scoping and exact Document/Version/Chunk provenance.

The Knowledge smoke proof explicitly verifies that text from a superseded generation is no longer returned as current knowledge.

### Agents / approvals workspace

**Active.**

Capability-backed durable execution Tasks are intentionally excluded from the human Tasks/Today/Gantt surfaces and projected instead through `GET /v1/operations/agents`.

Agents now shows:

- capability / execution identity;
- Task and WorkflowExecution status;
- project context;
- authority level;
- canonical model spend and budget where available;
- pending approval counts;
- safe execution metadata;
- workflow errors;
- direct navigation to Task / Workflow nodes.

The right-side Agents rail exposes real pending ApprovalRequest rows and uses existing canonical approve/deny endpoints. ADR-031 records the human-work vs capability-execution workspace boundary.

### Shared specialist-workspace contract

ADR-029 records that Projects, Tasks/Today/Gantt, Calendar, Knowledge and Agents are alternate views/controls over canonical KAIRO state. Frontend state remains interaction state only.

## Dedicated Block 3 validation coverage

The Graph Interface workflow now typechecks/builds the graph, Gantt and web packages, compiles Core/migrations and contains integration proofs for:

- canonical spatial graph + provenance + live activity;
- canonical Knowledge + latest-completed-generation retrieval;
- explicit Task planning + timezone-aware Today;
- Agents capability-execution / human-work separation + approval surfacing.

These tests are committed but **not yet considered passed on the latest head** because issue #38 still prevents GitHub from assigning hosted runners.

## Major work still remaining

- richer Project editing/status/lifecycle operations;
- external Calendar integration with provenance/free-busy boundaries;
- fuller 2D mind map / deep KAIRO Brain tooling;
- Automations operational workspace / Activepieces integration;
- broader MCP Tools management UX;
- Tauri desktop capability bridge (files/clipboard/capture/notifications/microphone) reusing the same web UI;
- Voice interaction;
- Finance / Crypto portfolio, analysis and signing-isolation UX;
- Developer / browser/computer-use specialist capabilities;
- production hardening: auth propagation in the web client, multi-user ownership coverage for every domain endpoint, TLS/reverse proxy/private-network policy, untrusted execution isolation and verified encrypted off-host recovery.

## Next implementation milestone

1. Resolve GitHub Actions runner issue #38 and execute #36 → #37 → #39 on real runners before merge.
2. Continue filling Test Interface v1 without introducing a second frontend.
3. Extend Calendar with explicit external-source provenance/connectors.
4. Build Automations and Tools operational views from existing canonical registries/policy boundaries.
5. Then move into Desktop/Voice and specialist Finance/Crypto/Developer capability surfaces.

The Block 3 goal is not "a pretty graph". It is one stable KAIRO environment in which every visible object, relationship, activity pulse and specialist workspace stays traceable to KAIRO-owned canonical state and policy boundaries.
