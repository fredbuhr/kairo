# KAIRO implementation status

Last updated: 2026-09-09

## Current phase

KAIRO is transitioning from **Block 2 — intelligence, memory and safe autonomy** into the permanent **Block 3 — Cockpit / Test Interface v1**.

The canonical substrate is already in place. The current work is no longer a dashboard prototype: the active Block 3 branch builds the product shell and spatial world model that is intended to remain the daily-use test interface while later work fills Projects, Knowledge, Tasks, Calendar, Agents, Finance and other specialist areas.

Three stacked pull requests must remain in order:

1. **PR #36 — durable multi-slot Research synthesis** (`feat/research-synthesis-checkpoints` → `main`);
2. **PR #37 — Research through the Command Kernel** (`feat/research-command-handoff` → PR #36);
3. **PR #39 — KAIRO Test Interface v1** (`feat/kairo-test-interface-v1` → PR #37).

All three are intentionally unmerged while GitHub Actions issue **#38** prevents GitHub-hosted jobs from receiving a runner. A red check with `runner_id=0` / no executed steps is an infrastructure failure, not a substitute for validation. The stacked PRs must receive real `ubuntu-latest` runs before merge.

## Canonical architecture active

- PostgreSQL + pgvector is the canonical domain/state store.
- SeaweedFS is canonical object storage.
- Temporal owns durable workflow execution and replay/recovery.
- NATS JetStream is the event bus, fed by a transactional PostgreSQL outbox.
- Keycloak and OpenBao define identity/secrets boundaries.
- canonical Conversation / Message / Command records own conversational continuity.
- KAIRO-owned Capability contracts sit above replaceable specialist engines.
- deterministic routing is the first command-routing tier; constrained PydanticAI semantic routing is second tier.
- LiteLLM is the model gateway; canonical model usage/budget accounting remains in PostgreSQL.
- Langfuse is observability only and is correlated from KAIRO execution identity.
- Mem0 and Graphiti/Neo4j are rebuildable projections, never canonical state.
- Docling-backed document ingestion produces canonical Documents / Versions / Chunks with provenance.
- MCP tools are registered and executed through KAIRO-owned policy/contract boundaries.
- specialist engines remain replaceable behind KAIRO adapters.

## Block 1 — platform substrate

**Implementation: complete.**

The permanent substrate includes canonical Projects, Tasks, Relationships, WorkflowExecutions, Artifacts, Assets, Devices, SecretReferences, Audit and Outbox records; deterministic Temporal workflow identity; internal Worker → Core mutation handoff; transactional event delivery; authenticated resource ownership; SeaweedFS digest verification; OpenBao secret-reference non-disclosure; and Restic backup/restore coverage for PostgreSQL, NATS, SeaweedFS and OpenBao.

The repository contains independent Foundation integration proofs for interruption/restart, resources/trust boundaries and backup/restore. They previously established the Block 1 invariants. Current GitHub-hosted reruns are blocked before execution by issue #38, so no new head should be treated as validated until runners resume.

## Block 2 — intelligence and safe autonomy

### Policy, approvals and model accounting

**Implemented.**

- KAIRO Core owns approval requests and policy authorization.
- authority ceilings and hard Task budgets gate guarded activities.
- approved actions receive short-lived signed capability tokens.
- Temporal workflows can wait for and resume after approvals.
- LiteLLM calls are canonically accounted in PostgreSQL.
- stable idempotency/checkpoint rules prevent blind paid-provider replay after ambiguous outcomes.

### Command Kernel

**Implemented on the current stacked Block 2 head.**

- canonical Conversation, ConversationMessage, Command and Capability records;
- `POST /v1/assistant/commands` as the universal conversational entry point;
- deterministic high-confidence routing first;
- durable PydanticAI semantic proposal only when deterministic routing has no match;
- semantic model access through the same KAIRO model gateway/accounting boundary;
- fail-closed capability/schema/confidence validation;
- deterministic final Task identities for replay-safe handoff;
- persistent conversation read model and Command inspection.

### News Intelligence

**Implemented and integrated as `news.brief`.**

- SearXNG discovery;
- transient Trafilatura extraction with internal-network blocking;
- LiteLLM synthesis with deterministic fallback;
- sourced canonical Artifact output;
- market-impact mode;
- optional local Kokoro speech synthesis;
- durable Task/Temporal execution.

### Memory and temporal context

**Implemented as rebuildable projections.**

- canonical ConversationMessage rows emit projection events transactionally;
- Mem0 uses its own disposable PostgreSQL database and non-generative local embeddings in the current slice;
- Graphiti writes canonical messages as temporal episodes in Neo4j;
- Graphiti generative entity/fact extraction remains deliberately deferred until it can use KAIRO's replay-safe/accounted model boundary;
- projection generation/rebuild logic prevents stale deliveries from rolling state backwards.

### Canonical documents

**Implemented.**

- Asset remains the immutable source object;
- Document is the stable KAIRO identity;
- DocumentVersion preserves generations;
- DocumentChunk preserves deterministic content/ordinal provenance;
- `document.ingest` runs durably through Temporal;
- source SHA-256 is verified before parsing;
- Docling is the preferred parser, with deterministic text fallback for substrate/CI installations.

### MCP tool boundary

**Implemented.**

- KAIRO-owned MCP registry and explicit enablement;
- typed input/output contract metadata;
- deny-by-default policy boundary;
- Worker live-server contract revalidation before execution on the PR #36 head;
- autonomous tool calls become separate canonical child Tasks / invocations.

### Autonomous Research

**Implemented in two layers; final synthesis/handoff awaits CI validation before merge.**

Already on `main`, the first bounded Research agent plans against the Core-supplied read-only tool catalog while Core remains authoritative over every tool execution.

PR #36 adds multi-slot replay-safe model checkpoints and evidence-backed synthesis whose factual findings must cite canonical MCP invocation IDs.

PR #37 makes `research.autonomous` a real Command capability and projects final results/failures back into the canonical Conversation idempotently. These changes are code-complete but must not merge until GitHub runners execute their validation suites.

## Block 3 — KAIRO Test Interface v1

**Active implementation: PR #39.**

The old `App.tsx` technical dashboard/grid is being replaced once, not iterated through multiple disposable frontends. `docs/interface-v1.md` is the structural interface contract.

### Product shell

Implemented on the Block 3 branch:

- stable left primary navigation;
- central spatial workspace where the mycelium is the workspace rather than a card;
- collapsible contextual right rail;
- compact always-available KAIRO command dock;
- contextual assistant drawer preserving working Command / News / Research behavior;
- universal canonical graph search;
- accessible non-3D graph projection;
- explicit unavailable states for future workspaces instead of fake sample data.

### Canonical spatial graph

Implemented on the Block 3 branch:

- `GET /v1/graph/home`;
- `GET /v1/graph/neighborhood/{entity_type}/{entity_id}`;
- `GET /v1/graph/search`;
- canonical `relationships` rows exposed as `canonical_relationship` edges;
- canonical foreign-key structure exposed as `canonical_fk` edges;
- presentation-only importance, activity, recency, degree, cluster hints and LOD;
- no Graphiti/Mem0 relationship is silently promoted to canonical visual truth.

### Mycelium product renderer

Implemented as the single engine for Home and KAIRO Brain:

- custom React Three Fiber / Three.js renderer;
- deterministic Web Worker layout;
- instanced node rendering;
- batched multi-strand curved filaments;
- project/context gravity wells without type-based pseudo-clusters;
- bounded importance-ranked spatial labels;
- semantic zoom / visual LOD;
- hover/selection neighborhood emphasis;
- explicit branch isolation and type/relation filters;
- stable per-context pose caches and Worker warm starts so refresh/navigation preserves spatial familiarity;
- restrained focus camera transitions;
- reduced-motion support;
- Auto/High/Balanced/Eco quality framework, including measured frame-budget adaptation for Auto.

ADR-027 defines the canonical graph boundary. ADR-028 defines the stable/batched spatial-rendering rules.

### Live graph activity

Implemented on the Block 3 branch:

- sanitized `GET /v1/graph/activity/stream` SSE derived from canonical Outbox rows;
- no raw domain-event payload is exposed through the graph stream;
- browser subscription coalesces graph query invalidation;
- short-lived active entity keys drive bounded instanced pulses;
- semantic pulses therefore correspond to real recent KAIRO activity rather than random decorative traffic.

### Natural-language spatial navigation

Implemented deterministically/read-only:

- `POST /v1/graph/directives/resolve`;
- `focus_entity` and `isolate_entity` directives;
- unambiguous canonical resolution only;
- ambiguous targets fall back to search rather than arbitrary selection;
- typed target phrases such as `Ouvre le projet …` / `Montre-moi la tâche …` narrow resolution;
- non-navigation text continues to the normal Command Kernel;
- models never receive direct Three.js authority.

## What is not yet complete

The stable shell exists, but specialist/product workspaces still need to be filled with real capabilities rather than placeholders. Major remaining areas include:

- Projects workspace beyond the canonical graph representation;
- Tasks / Today prioritization workspace;
- Calendar and external calendar integration;
- Knowledge workspace and deeper document retrieval UX;
- full 2D mind map / deeper KAIRO Brain tooling;
- simple but capable Gantt workspace;
- Agents and Automations operational views;
- Tauri desktop capability bridge (microphone/files/clipboard/capture/notifications) reusing the same web UI;
- Voice interaction;
- Finance / Crypto portfolio, analysis and signing-isolation UX;
- Developer / browser/computer-use specialist capabilities;
- Activepieces operational integration and broader connectors;
- production hardening (TLS/reverse proxy/private-network policy, untrusted execution isolation, verified encrypted off-host recovery).

## Next implementation milestone

1. Resolve GitHub Actions runner allocation issue #38 and execute the stacked #36 → #37 → #39 validation chain on real runners.
2. While the infrastructure blocker remains external, continue completing Test Interface v1 without creating a second frontend.
3. Fill the stable Cockpit in coherent feature slices, beginning with Projects / Tasks / Knowledge and then Calendar / Gantt / Agents.
4. Reuse the same graph model and shell for all specialist workspaces rather than creating parallel applications.

The Block 3 goal is not "a pretty graph". It is a stable KAIRO environment in which every visible object, relationship, activity pulse and specialist workspace remains traceable to KAIRO-owned canonical state and policy boundaries.
