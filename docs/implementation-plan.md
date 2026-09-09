# KAIRO implementation plan

The plan uses large coherent blocks. Each block should finish with an end-to-end usable capability, while platform boundaries and specialist-engine contracts remain stable from the beginning.

A key implementation rule now applies to Block 3: **KAIRO Test Interface v1 is the product interface, not a disposable frontend prototype.** Later work may tune rendering, density and interactions, but must fill and extend the same shell instead of replacing it.

## Block 0 — Full-platform foundation

**Status: complete.**

**Purpose:** replace the V0 proof architecture with permanent platform boundaries.

Deliverables:

- monorepo structure for Web, Desktop, Core, Worker and Realtime;
- component registry and integrated Compose topology;
- PostgreSQL/pgvector, Neo4j, Valkey, NATS, SeaweedFS, Temporal, LiteLLM, Activepieces, OpenBao, Keycloak, SearXNG, Ollama, Langfuse/ClickHouse, ntfy and LiveKit represented architecturally;
- specialist profiles for finance, home, development agent, GPU inference and remote access;
- canonical domain/data-ownership/security contracts;
- CI structure for TypeScript/Python/build/topology/integration proofs;
- removal of the former OpenClaw filesystem/runtime proof as the target architecture.

**Exit:** repository topology and trust/data boundaries are internally consistent; features are not allowed to bypass them.

## Block 1 — Platform substrate and system of record

**Status: complete — 2026-09-08.**

**Purpose:** make the foundation boot and recover as one system.

Deliverables:

- database migrations and canonical entity tables;
- transactional outbox + NATS publication;
- SeaweedFS object API and asset references;
- Keycloak identity + device registration;
- OpenBao secret references;
- Temporal namespaces/workers and durable workflow correlation;
- readiness/trust-boundary endpoints;
- Restic backup/restore;
- local development bootstrap and production configuration separation.

**Exit:** KAIRO can create/read canonical entities, publish domain events, store assets, survive service interruption and restore its durable substrate from backup.

The repository contains separate Foundation gates for build/topology, Temporal/outbox crash recovery, authenticated resource boundaries and destructive backup/restore. New heads remain subject to those gates once GitHub-hosted runner allocation issue #38 is resolved.

## Block 2 — Intelligence, memory and safe autonomy

**Status: implementation substantially complete; stacked PR #36/#37 await real CI execution before merge.**

**Purpose:** make KAIRO reason and work durably without coupling intelligence to one model/provider/runtime.

Implemented slices:

- LiteLLM logical aliases, replay-safe model calls, canonical token/cost accounting and hard budgets;
- PydanticAI semantic routing and bounded agent planning behind KAIRO-owned authority;
- Mem0 rebuildable memory projection;
- Graphiti/Neo4j temporal context projection;
- Docling canonical document ingestion/version/chunk provenance;
- KAIRO MCP tool registry and deny-by-default typed execution boundary;
- approval requests and policy tokens in Temporal activities;
- SearXNG + News Intelligence;
- Langfuse correlation with canonical KAIRO execution identity;
- first bounded autonomous Research agent with MCP child Tasks.

PR #36 adds:

- multi-slot replay-safe model checkpoints;
- live MCP server contract revalidation immediately before execution;
- evidence-backed Research synthesis whose factual findings cite canonical ToolInvocation IDs.

PR #37 adds:

- `research.autonomous` as a real Command Kernel capability;
- Core-owned routing authority injection (project/model/budget/tool eligibility cannot be smuggled through model/user routing fields);
- final News/Research results and safe failures projected idempotently back into canonical Conversation history.

Remaining Block 2 integration work after the stacked merge:

- deterministic Playwright browser activities and Browser Use only where semantic navigation is actually required;
- Activepieces operational adapter beyond registry/topology presence;
- deeper retrieval over documents/memory/Graphiti as agent context while preserving those stores as non-canonical projections.

**Exit:** an approved autonomous workflow can research, use tools, create canonical artefacts, survive interruption, respect authority/cost limits and explain what it did.

## Block 3 — KAIRO Test Interface v1, graph and planning workspace

**Status: active — draft PR #39 stacked on PR #37.**

**Purpose:** deliver the permanent daily KAIRO environment instead of exposing specialist tools or a temporary dashboard.

### 3A — Stable KAIRO shell and canonical world projection

This is the first Block 3 implementation slice and is intentionally substantial enough to become the interface used for testing rather than being thrown away later.

Deliverables:

- stable primary navigation;
- central spatial workspace;
- contextual right rail;
- compact Command Dock + expandable assistant conversation surface;
- KAIRO design language based on the approved organic cyan/mint identity;
- Graph Read Model owned by Core:
  - `/v1/graph/home`;
  - `/v1/graph/neighborhood/{entity_type}/{entity_id}`;
  - `/v1/graph/search`;
- canonical relationship provenance (`canonical_relationship` / `canonical_fk`);
- sanitized canonical activity stream for live graph refresh/activity;
- deterministic typed UI focus/isolation directives for natural-language spatial navigation;
- one `@kairo/graph` engine shared by Home and KAIRO Brain;
- custom R3F/Three.js rendering rather than a generic graph component as the product renderer;
- Worker-based deterministic/warm-started layout;
- instanced nodes, batched curved filaments and instanced canonical activity pulses;
- semantic zoom / LOD;
- stable context pose caches;
- bounded labels;
- hover/selection emphasis, Explore, Back, recenter, branch isolation and filters;
- accessible non-3D projection;
- reduced-motion and adaptive Auto/High/Balanced/Eco quality.

Architectural contracts:

- `docs/interface-v1.md` — stable product/interface boundary;
- ADR-027 — canonical spatial graph projection/provenance;
- ADR-028 — stable/batched spatial rendering.

**Exit for 3A:** the old technical grid/dashboard is no longer needed as a parallel frontend; real KAIRO data can be navigated through the same shell and engine that later workspaces will extend.

### 3B — Fill the stable Cockpit with real workspaces

The shell does not change. Specialist views fill it.

Deliverables, grouped into coherent slices rather than micro-features:

- **Projects + Tasks + Today**
  - real project/task CRUD and focus/navigation;
  - priorities/attention derived from canonical state;
  - project context rail and activity;
- **Knowledge**
  - document/library workspace;
  - canonical document ingest/search/retrieval UX;
  - knowledge relationships projected into the same graph world;
- **Calendar + planning**
  - Schedule-X calendar;
  - KAIRO scheduling layer;
  - simple SVAR Gantt manipulation, dependencies and AI-assisted replanning;
- **KAIRO Brain / mind mapping**
  - deeper filters/path/neighborhood tooling;
  - 2D React Flow projection and richer 3D inspection using the same canonical graph contract;
- **Agents + Automations + Approvals + Activity**
  - running/queued/waiting agent state;
  - automation execution/history;
  - policy/approval surface;
  - unified activity/attention presentation;
- **Documents / notes / whiteboards**
  - Lexical/Yjs documents;
  - Excalidraw where free-form visual work is useful;
  - Hocuspocus realtime collaboration without becoming canonical domain storage;
- **Analytics / Maps / specialist panels**
  - ECharts and MapLibre only where a concrete workspace requires them;
  - Dockview may be used inside dense specialist workspaces, but does not define Home or the global shell.

Universal search progressively expands from canonical graph records to document chunks/embeddings/derived context without changing the global search interaction.

**Block 3 exit:** KAIRO is usable every day through the same Cockpit for projects, tasks, knowledge, calendar/planning, agents/approvals/activity, mindmap/Brain and Gantt.

## Block 4 — Sidecar, voice and personal operations

**Purpose:** turn the server product into a persistent Jarvis-like assistant across devices while reusing the exact same web interface.

Deliverables:

- Tauri desktop shell embedding KAIRO Web rather than implementing a second UI;
- explicit local capability bridge for microphone, clipboard, screenshot, capture and selected filesystem access;
- local wake word/VAD/transcription using openWakeWord, Silero VAD and whisper.cpp;
- LiveKit low-latency realtime voice sessions;
- ntfy notifications and unified attention delivery;
- calendar/contact/email/message adapters through MCP/Activepieces/native connectors where appropriate;
- Headscale private device network for remote access.

**Exit:** KAIRO can be summoned, listen/speak through approved paths, act on a registered device and continue work server-side when clients disconnect.

## Block 5 — Specialist systems: developer, finance, crypto and home

**Purpose:** connect high-value personal systems without compromising KAIRO's unified model.

Deliverables:

- OpenHands development-agent adapter with sandboxed repositories, diff/test/approval workflow;
- rotki portfolio/accounting ingestion;
- CCXT exchange read/trade proposal adapters;
- viem EVM read/simulation/proposal support with isolated signing boundary;
- optional Hummingbot paper/strategy engine, with live authority disabled until separate security approval;
- Actual Budget integration and normalized finance summaries;
- Home Assistant adapter for devices/scenes/automations;
- cross-domain views and alerts linking financial/home/dev state to projects and Attention.

**Exit:** KAIRO can reason and operate across these systems while every side effect still passes through one policy/audit model.

## Block 6 — Hardening, self-maintenance and production operations

**Purpose:** make KAIRO trustworthy enough to run persistently.

Deliverables:

- gVisor or equivalent hardened execution for untrusted agent/code workloads;
- production TLS/private-network exposure model;
- resource quotas and per-agent/tool rate limits;
- disaster-recovery drills and verified encrypted off-host backups;
- version pinning, dependency/SBOM scanning and controlled upgrades;
- self-diagnosis, proposed self-changes, automated tests and approval-gated deployment/rollback;
- load/performance testing of graph, realtime, Temporal and model paths;
- full audit/export/delete lifecycle for user data.

**Exit:** production KAIRO can run continuously, fail safely, recover, explain its actions and evolve without silently rewriting its own trust boundaries.

## Current sequencing constraint

GitHub Actions issue #38 is an external validation blocker, not permission to weaken the gates. Development may continue on the stacked feature branches, but merge order remains:

`#36 → #37 → #39 → subsequent Block 3 workspace slices`

Each merge must be based on real executed validation, not runner-allocation failures.
