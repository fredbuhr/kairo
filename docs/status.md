# KAIRO implementation status

Last updated: 2026-09-09

## Current phase

KAIRO is transitioning from **Block 2 — intelligence, memory and safe autonomy** into the permanent **Block 3 — Cockpit / Test Interface v1**.

The active Block 3 branch no longer treats the frontend as a disposable dashboard prototype. `KairoCockpit` is now the actual product entrypoint and the spatial world model plus specialist workspaces are intended to remain the daily-use test interface while later capabilities fill the same structure.

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
- Automation definitions/invocations are KAIRO-owned while Activepieces remains a replaceable execution adapter.
- Finance portfolio data is an explicit sourced observation model; Rotki is the first concrete read-only connector and signing authority remains outside the AI/runtime boundary.
- specialist workspaces are views/controls over canonical APIs or explicit sourced read models, not parallel frontend-owned applications.

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

### Permanent Cockpit shell

Implemented:

- `App.tsx` mounts `KairoCockpit` as the actual product entrypoint;
- `LiveGraphBridge` is mounted once at the application root rather than duplicated;
- stable left primary navigation;
- central spatial/specialist working surface;
- collapsible contextual right rail;
- compact always-available KAIRO command dock;
- assistant drawer preserving Command / News / Research;
- universal canonical graph search;
- explicit unavailable states for genuinely unimplemented areas;
- all active workspace styles are wired from the same app entrypoint.

The active primary workspaces are now Projects, Knowledge, KAIRO Brain, Tasks/Gantt, Calendar, Agents, Automations, Finance & Crypto and Tools.

### Canonical graph

Implemented:

- `GET /v1/graph/home`;
- `GET /v1/graph/neighborhood/{entity_type}/{entity_id}`;
- `GET /v1/graph/search`;
- canonical `relationships` edges + canonical FK-derived structure with distinct provenance;
- presentation-only importance/activity/recency/degree/cluster hints/LOD;
- no Graphiti/Mem0 relationship silently promoted to canonical truth.

### 3D Mycelium

Implemented as the spatial engine for Home and KAIRO Brain:

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

### 2D KAIRO Brain mind map

**Active.**

KAIRO Brain can switch between **3D**, **Carte 2D** and **Liste** without creating another graph model.

`@kairo/graph` contains a pure deterministic radial mind-map projection that consumes the same `KairoGraphProjection` as the 3D renderer. The layout builds a temporary spanning tree only for positioning while still drawing all canonical graph edges with their original provenance.

The 2D workspace provides deterministic focus/root selection, stable radial branch placement, provenance-distinguishable edges, shared selection/context, canonical neighborhood focus, presentation-only drag state, shared filters/branch isolation and MiniMap/zoom/pan with accessible list fallback.

ADR-033 records that tree parents, radial depth and dragged coordinates are presentation state only.

### Live graph activity

Implemented:

- sanitized `GET /v1/graph/activity/stream` SSE from canonical Outbox rows;
- coalesced graph invalidation in the browser;
- short-lived active entity keys drive bounded instanced pulses;
- pulses represent real KAIRO activity rather than random decorative traffic.

### Natural-language spatial navigation

Implemented deterministically/read-only:

- `POST /v1/graph/directives/resolve`;
- `focus_entity` and `isolate_entity`;
- typed entity hints;
- ambiguity falls back to search;
- non-navigation language continues through the normal Command Kernel;
- models never receive direct Three.js/React Flow authority.

### Projects workspace

**Active with lifecycle editing.**

- canonical list/create;
- rename and summary mutation;
- active / paused / archived status mutation;
- parent-project reassignment;
- Core hierarchy-cycle refusal;
- real human-work Task counts;
- archived projects recede from the Home graph candidate set;
- direct navigation to the same Project node in KAIRO Brain;
- workspace/graph query invalidation after mutation.

### Tasks / Today workspace

**Active.**

Migration `0008_task_planning_fields` adds canonical Task priority, planned start/end and due date. `PATCH /v1/tasks/{task_id}/planning` validates timezone-aware intervals, audits mutations, emits `task.updated` and keeps lifecycle timestamps coherent.

`GET /v1/today` deterministically projects human work into mutually exclusive groups: overdue → due today → planned today → explicit high priority. No LLM/frontend heuristic invents urgency. Capability execution Tasks are excluded from human planning and fail closed on the human planning mutation endpoint.

### Gantt

**Active inside Tasks.**

`@kairo/gantt` projects the same canonical Task planning fields into renderer-independent timeline geometry. The UI offers 14/30/90 day ranges, project filtering, interval bars, due-only milestones, deadline markers and unscheduled work. No separate Gantt plan database is introduced.

ADR-030 records the Task planning/Today/Gantt contract.

### Calendar — KAIRO planning

**Active.**

The Calendar workspace projects the same Task planning intervals into a weekly 06:00–22:00 view, with due-only deadlines, project filtering and direct graph navigation.

### Calendar — external sourced snapshots

**Canonical substrate and UI projection implemented; provider OAuth adapters are still to be connected.**

Migration `0009_external_calendar_snapshots` adds owner-scoped `CalendarSource` and provenance-preserving `ExternalCalendarEvent` rows. Core exposes owner/interval-scoped reads and a trusted normalized snapshot ingestion boundary.

The boundary requires timezone-aware intervals, rejects duplicate identities, prevents account rebinding, updates stable provider identities on replay, permits full-snapshot deletion and never mutates KAIRO Tasks as a side effect. OAuth secrets never live in source/event snapshot rows.

The Calendar UI overlays external events distinctly from KAIRO planning and preserves source/provider/sync provenance.

ADR-034 records this boundary. Actual Google/Microsoft credential exchange and polling adapters remain a later connector layer.

### Knowledge workspace

**Active.**

- canonical document library;
- file import through Asset → Document → Version → Chunks;
- version/chunk inspection;
- durable reingestion from the immutable source Asset;
- direct navigation to the same Document node in KAIRO Brain;
- newest-completed-generation-only Knowledge retrieval;
- SQL ownership scoping and exact Document/Version/Chunk provenance.

The Knowledge smoke proof explicitly verifies that text from a superseded generation is no longer returned as current knowledge.

### Agents / approvals workspace

**Active.**

Capability-backed durable execution Tasks are intentionally excluded from human Tasks/Today/Gantt and projected through `GET /v1/operations/agents`.

Agents shows capability/execution identity, Task and Workflow status, project context, authority level, canonical model spend/budget, pending approvals, safe execution metadata and errors. Real pending ApprovalRequest rows are approved/denied through existing canonical endpoints.

ADR-031 records the human-work vs capability-execution boundary.

### Tools / MCP workspace

**Active and aligned with the real Core contract.**

The workspace uses canonical `ToolServer` / `ToolDefinition` fields and supports real server registration, fail-closed creation, explicit server enable/disable, per-tool allow/deny policy, availability/risk/authority/retry/cost/schema inspection and truthful empty-catalog state.

Catalog synchronization remains an internal trusted gateway boundary. Worker live-contract validation remains the execution-time authority boundary.

ADR-032 records fail-closed MCP server registration.

### Automations / Activepieces

**Active KAIRO-owned workspace and execution boundary.**

Migration `0010_automation_registry` adds:

- owner/Project-scoped `AutomationDefinition` records created disabled;
- canonical `AutomationInvocation` rows tied one-to-one to capability Tasks;
- response status/evidence, terminal error and explicit `outcome_ambiguous` state.

Core exposes real list/create/update/run/history APIs. The Cockpit lists definitions, policy state and runs and links each run back to its canonical Task.

Activepieces remains behind KAIRO rather than becoming a second application shell:

- webhook configuration is represented by a SecretReference;
- OpenBao holds only the webhook path;
- Core prepends the fixed internal Activepieces origin and rejects arbitrary absolute/protocol-relative destinations;
- enabling an automation validates the current secret binding;
- each run creates a canonical `automation.invoke` capability Task/WorkflowExecution and passes through the shared policy/approval boundary;
- the Worker revalidates Core context immediately before the external call;
- the webhook activity deliberately has one Temporal attempt;
- if the request may have crossed the external side-effect boundary but no response is known, KAIRO records `outcome_ambiguous=true` and does not blindly replay it;
- downstream response bodies are not copied into canonical state by default; status/content-type/size/SHA-256 evidence is retained instead.

A dedicated controlled full-stack proof now crosses **Core → Temporal → Worker → OpenBao → webhook transport** and verifies both successful execution and an accepted-but-response-lost ambiguous outcome, including idempotent non-replay. The fixture models the Activepieces webhook contract; provisioning/executing an actual Activepieces flow remains a separate adapter integration proof.

ADR-035 records this boundary.

### Finance & Crypto

**Active sourced portfolio, unsigned transaction drafts and concrete read-only Rotki connector.**

Migrations `0011_finance_portfolio_snapshots` and `0012_finance_connectors` add:

- owner-scoped `FinanceSource` provider bindings;
- deterministic sourced `FinanceAccount` observations;
- latest `FinancePosition` observations with Decimal quantity/valuation/cost/P&L;
- unsigned `FinanceTransactionProposal` drafts;
- Project/owner-scoped `FinanceConnector` definitions created disabled.

Core exposes the normalized Finance read model plus a concrete Rotki adapter. Rotki credentials are referenced through OpenBao; PostgreSQL stores only a `SecretReference` and required secret-field names. The Worker receives connector/task/workflow identifiers only and calls back into Core, so Rotki username/password values do not enter the Temporal payload/history or browser client.

The deployment owns `ROTKI_URL`; user metadata/secrets cannot redirect the connector to an arbitrary HTTP origin. A synchronization request creates/reuses a durable A1 `finance.sync.rotki` capability Task, and Core authenticates to Rotki, optionally refreshes blockchain balances, waits for Rotki's async task, normalizes sourced accounts/assets/liabilities, and ingests them through the existing Finance snapshot boundary.

The Rotki normalizer handles the current blockchain-balance forms including address balance sheets and UTXO standalone/xpub observations. It preserves Decimal values and provider identifiers rather than inventing tickers. Extended public key material is deliberately not persisted in the first adapter slice.

The Finance Cockpit now has a connector-management panel for real `FinanceConnector` records: list, fail-closed create, explicit enable/disable, sync, last sync/error state, SecretReference selection and credential-field binding. Credential values themselves are never exposed to the browser.

The snapshot boundary prevents source-account rebinding, preserves deterministic account/position identity across replay, supports full-source replacement and rejects credential/private-key/seed-like metadata fields. Public addresses are allowed because they are provenance, not signing authority.

A transfer draft must refer to an asset currently present in the selected sourced account observation and keeps the observed-position identity/time in its simulation metadata. KAIRO deliberately does **not** interpret that stale-able observation as current spend authority.

There is no sign/send/broadcast API. Proposal responses state `signing_required=true` and `signing_boundary=external_isolated_signer`. Private keys and seed phrases never enter the AI/agent process. Future signing must remain behind policy/approval plus an isolated signer, hardware wallet or explicit user-wallet interaction.

A controlled full-stack Rotki proof now crosses **Core → Temporal → Worker → Core → OpenBao → Rotki API fixture → canonical Finance snapshot**. It checks disabled-by-default creation, credential non-disclosure, successful refresh, stable source/account/position identity as external values change, and preservation of the last good snapshot after a credential failure. A separately provisioned real Rotki release still requires provider-integration validation before production deployment.

ADR-015 defines signing isolation; ADR-036 defines sourced Finance/signing separation; ADR-037 defines the concrete read-only Rotki connector boundary.

### Shared specialist-workspace contract

ADR-029 records that Projects, Tasks/Today/Gantt, Calendar, Knowledge, Agents, Tools, Automations and Finance are alternate views/controls over KAIRO state or explicit sourced projections. Frontend state remains interaction state only.

## Dedicated Block 3 validation coverage

The Graph Interface workflow now typechecks/builds graph, Gantt and web packages, builds both Core and Worker Python packages, compiles Core/migrations/Worker/smoke sources and contains integration proofs for:

- canonical graph + provenance + live activity + deterministic spatial directives;
- Knowledge latest-completed-generation retrieval;
- explicit Task planning + timezone-aware Today;
- Agents capability-execution / human-work separation + approval surfacing;
- Project lifecycle + hierarchy-cycle refusal + archived Home behavior;
- fail-closed MCP server registration/policy;
- external Calendar source/event identity, replay, deletion, rebinding refusal and timezone validation;
- canonical Automation registry fail-closed creation/enablement behavior;
- controlled full-stack Automation Core/Temporal/Worker/OpenBao/webhook success + ambiguous-outcome non-replay;
- sourced Finance source/account/position replay, full replacement, secret-field rejection, proposal provenance and external signing isolation;
- controlled full-stack Rotki Core/Temporal/Worker/OpenBao/provider synchronization, credential non-disclosure, identity stability and last-good-snapshot preservation.

Because isolated Cockpit proofs intentionally do not start Keycloak, `compose.graph-ci.yaml` disables user auth **only for that CI stack**. Production explicitly forces KAIRO authentication on.

These proofs are committed but **not yet considered passed on the latest head** because issue #38 still prevents GitHub from assigning hosted runners.

## Major work still remaining

- real Google/Microsoft Calendar connector authentication/polling/free-busy adapters feeding the normalized snapshot boundary;
- validate the concrete Rotki adapter against a separately provisioned real Rotki release and then add exchange/wallet Finance adapters where useful;
- an actual provisioned Activepieces-flow integration proof in addition to the controlled webhook-contract proof;
- deeper editable/collaborative Brain functionality where explicit graph/domain mutations are required;
- Tauri desktop capability bridge (files/clipboard/capture/notifications/microphone) reusing the same web UI;
- Voice interaction;
- isolated Finance signing handoff UX when a concrete wallet/hardware signer target is selected;
- Developer / browser/computer-use specialist capabilities;
- production hardening: auth propagation in the web client, multi-user ownership coverage for every domain endpoint, TLS/reverse proxy/private-network policy, untrusted execution isolation and verified encrypted off-host recovery.

## Next implementation milestone

1. Resolve GitHub Actions runner issue #38 and execute #36 → #37 → #39 on real runners before merge.
2. Keep filling Test Interface v1 without introducing a second frontend.
3. Validate/adapt the concrete connector boundaries against real providers: Google/Microsoft Calendar, a provisioned Rotki release and a provisioned Activepieces flow.
4. Continue Desktop/Voice integration while preserving the same Cockpit and canonical Core contracts.
5. Then deepen Developer/computer-use capabilities and isolated transaction-signing handoff without granting agents private-key custody.

The Block 3 goal is not “a pretty graph”. It is one stable KAIRO environment in which every visible object, relationship, activity pulse, external observation and specialist workspace stays traceable to KAIRO-owned canonical state, provenance and policy boundaries.
