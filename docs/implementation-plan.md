# KAIRO implementation plan

The plan uses large coherent blocks. Each block should finish with an end-to-end usable capability, but the architecture and component registry are present from the beginning.

## Block 0 — Full-platform foundation

**Purpose:** replace the V0 proof architecture with the permanent platform boundaries.

Deliverables:

- monorepo structure for Web, Desktop, Core, Worker and Realtime;
- complete component registry and integrated Compose topology;
- PostgreSQL/pgvector, Neo4j, Valkey, NATS, SeaweedFS, Temporal, LiteLLM, Activepieces, OpenBao, Keycloak, SearXNG, Ollama, Langfuse/ClickHouse, ntfy and LiveKit represented from day one;
- specialist profiles for finance, home, development agent, GPU inference and remote access;
- canonical domain/data-ownership/security contracts;
- CI that validates TypeScript/Python manifests, Compose syntax and service smoke tests as implementation lands;
- removal of OpenClaw-specific runtime/plugin/filesystem proof code.

**Exit:** repository topology and infrastructure contracts are internally consistent; no new feature is allowed to bypass them.

## Block 1 — Platform substrate and system of record

**Status: complete — 2026-09-08.**

**Purpose:** make the foundation actually boot as one system.

Deliverables:

- database migrations and canonical entity tables;
- transactional outbox + NATS publication;
- SeaweedFS object API and asset references;
- Keycloak identity + device registration;
- OpenBao secret references;
- Temporal namespaces/workers and durable workflow correlation;
- health/readiness endpoints across KAIRO services;
- backup/restore with restic;
- local development bootstrap and production configuration separation.

**Exit:** KAIRO can create/read canonical entities, publish domain events, store assets, survive service restarts and restore from backup.

The exit is enforced by four CI gates: general build/topology validation, Temporal/outbox crash recovery, authenticated Keycloak/OpenBao/SeaweedFS resource integration, and a destructive Restic restore drill covering PostgreSQL, NATS, SeaweedFS and OpenBao.

## Block 2 — Intelligence, memory and safe autonomy

**Status: active.**

**Purpose:** make KAIRO reason and work durably without coupling intelligence to one provider/runtime.

Deliverables:

- LiteLLM logical model aliases, routing policy, token/cost accounting and hard budgets;
- PydanticAI agent/skill framework;
- Mem0 memory projection;
- Graphiti/Neo4j temporal context projection;
- Docling ingestion pipeline;
- MCP tool registry;
- approval requests and policy tokens in Temporal activities;
- SearXNG research path;
- Playwright deterministic browser activities and Browser Use only where AI navigation is needed;
- Activepieces adapter for external automations;
- Langfuse trace correlation with KAIRO audit IDs.

**Exit:** an approved autonomous workflow can research, use tools, create canonical artefacts, survive interruption, respect authority/cost limits and explain what it did.

## Block 3 — KAIRO Cockpit, graph and planning workspace

**Purpose:** deliver the daily interface instead of exposing specialist tools.

Deliverables:

- Dockview-based customizable workspace and KAIRO design system;
- Command Center/chat, Today, Projects, Knowledge, Agents, Approvals and Activity surfaces;
- Lexical documents and Excalidraw whiteboards;
- 2D React Flow mindmap and realtime 3D graph view backed by the same canonical graph;
- Yjs/Hocuspocus realtime collaboration and cross-device synchronization;
- KAIRO scheduling engine + SVAR Gantt renderer with simple manipulation, dependencies, critical path and AI-assisted replanning;
- Schedule-X calendar, ECharts dashboards and MapLibre place/map views;
- universal search across canonical records, documents, embeddings and graph context.

**Exit:** KAIRO is usable every day through one customizable Cockpit, including mindmap 3D and Gantt.

## Block 4 — Sidecar, voice and personal operations

**Purpose:** turn the server product into a persistent Jarvis-like assistant across devices.

Deliverables:

- Tauri desktop/Sidecar with explicit local capability grants;
- global summon shortcut, microphone, clipboard, screenshot and selected-filesystem access;
- local wake word/VAD/transcription using openWakeWord, Silero VAD and whisper.cpp;
- LiveKit low-latency realtime voice sessions;
- ntfy notification delivery and unified attention inbox;
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
- Actual Budget integration and normalized personal finance summaries;
- Home Assistant adapter for devices/scenes/automations;
- cross-domain dashboards and alerts linking financial/home/dev state to projects and attention items.

**Exit:** KAIRO can manage and reason across these systems while every side effect still passes through one policy/audit model.

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
