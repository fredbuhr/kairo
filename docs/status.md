# KAIRO implementation status

Last updated: 2026-09-09

## Current phase

KAIRO is transitioning from **Block 2 — intelligence, memory and safe autonomy** into the permanent **Block 3 — Cockpit / Test Interface v1**.

The active Block 3 branch does not treat the frontend as a disposable dashboard prototype. `KairoCockpit` is the product entrypoint and the current spatial world model plus specialist workspaces are intended to remain the daily-use test interface while later capabilities extend the same structure.

Three stacked pull requests must remain in order:

1. **PR #36 — durable multi-slot Research synthesis** (`feat/research-synthesis-checkpoints` → `main`);
2. **PR #37 — Research through the Command Kernel** (`feat/research-command-handoff` → PR #36);
3. **PR #39 — KAIRO Test Interface v1** (`feat/kairo-test-interface-v1` → PR #37).

All three remain intentionally unmerged while GitHub Actions issue **#38** prevents GitHub-hosted jobs from receiving a runner. A red check with `runner_id=0` / no executed steps is an infrastructure failure, not code validation. Real hosted runs are required before merge.

## Canonical architecture active

- PostgreSQL + pgvector: canonical domain/state store.
- SeaweedFS: canonical object storage.
- Temporal: durable workflow execution/replay.
- NATS JetStream: event bus fed by a transactional PostgreSQL outbox.
- Keycloak: authenticated Web/Desktop identity boundary.
- OpenBao: secret-value custody; public KAIRO state stores vault handles only.
- Conversation / Message / Command: canonical conversational continuity.
- KAIRO Capability contracts: policy/authority boundary above replaceable engines.
- deterministic routing first; constrained PydanticAI semantic routing second.
- LiteLLM: model gateway with canonical PostgreSQL budget/usage accounting.
- Mem0 + Graphiti/Neo4j: rebuildable projections, never canonical state.
- Docling: preferred parser into canonical Documents / Versions / Chunks.
- MCP: shared deployment registry + KAIRO-owned user execution ledger/policy.
- Activepieces: replaceable Automation execution adapter behind KAIRO.
- Finance: sourced observations; Rotki is the first read-only provider adapter; signing remains outside the AI/runtime boundary.
- Tauri: bounded Desktop trust boundary around the same Web Cockpit, not a second frontend.

## Block 1 — platform substrate

**Implementation: complete.**

Canonical Projects, Tasks, Relationships, WorkflowExecutions, Artifacts, Assets, Devices, SecretReferences, Audit and Outbox state are in place together with deterministic Temporal identity, transactional event delivery, authenticated resources, object digest verification and backup/restore substrate.

Earlier Foundation proofs established the baseline invariants. Current stacked heads still need fresh real-runner validation after issue #38 is resolved.

## Block 2 — intelligence and safe autonomy

### Policy / approvals / accounting

**Implemented.** Authority ceilings, approvals, signed capability tokens, hard Task budgets and canonical model usage accounting are Core-owned. Paid-provider replay ambiguity fails closed.

### Command Kernel / Assistant

**Implemented on the stacked Block 2 head.** `POST /v1/assistant/commands` is the conversational entry point. Deterministic routing is first-tier; durable constrained semantic routing is second-tier. Conversation state remains canonical.

### News Intelligence

**Implemented.** SearXNG discovery, transient extraction, sourced synthesis, market-impact mode, optional local speech and durable execution are integrated.

### Memory / temporal context

**Implemented as rebuildable projections.** Mem0 and Graphiti consume canonical events. Generative Graphiti fact/entity extraction remains deferred until it can use the accounted/replay-safe model boundary.

### Documents / Knowledge

**Implemented.** Asset → Document → DocumentVersion → DocumentChunk is canonical, durable and provenance-preserving. Knowledge retrieval uses the latest completed document generation.

### MCP / Autonomous Research

**Implemented in stacked layers; current heads await real CI.** MCP registry/policy/schema snapshots, Worker live-contract revalidation and child invocation Tasks are present. PR #36 adds replay-safe Research synthesis/evidence citations; #37 routes Research through Command and projects terminal results/failures back into Conversation.

## Block 3 — permanent KAIRO Test Interface v1

**Active implementation: PR #39.**

### Permanent Cockpit

Implemented:

- stable left navigation;
- central spatial/specialist working surface;
- contextual right rail;
- compact Command Dock and Assistant drawer;
- universal graph search;
- same shell in Web and Tauri Desktop;
- specialist workspaces as views/controls over canonical APIs or sourced projections, not frontend-owned mini-apps.

Active workspaces: **Projects, Knowledge, KAIRO Brain, Tasks/Gantt, Calendar, Agents, Automations, Finance & Crypto, Tools**.

### Canonical graph / 3D Mycelium / 2D Brain

Implemented:

- bounded Home/neighborhood/search projections;
- explicit Relationships + FK-derived structural edges with distinct provenance;
- custom R3F/Three.js mycelium;
- deterministic Worker layout and spatial continuity;
- instanced nodes, batched curved filaments, organic cluster atmosphere;
- real Outbox-derived activity pulses;
- semantic LOD, adaptive quality, reduced motion;
- hover/selection/focus/isolation/type+relation filters;
- deterministic natural-language `focus_entity` / `isolate_entity` directives;
- 3D / Carte 2D / Liste accessible from the same `KairoGraphProjection`.

ADR-027/028/033 define graph provenance, stable spatial rendering and presentation-only 2D layout state.

### Projects / Tasks / Today / Gantt / Calendar

Implemented:

- Project lifecycle/hierarchy editing with cycle refusal;
- canonical Task priority/start/end/due planning facts;
- deterministic Today ordering: overdue → due today → planned today → high priority;
- capability execution Tasks excluded from human planning;
- Gantt and weekly Calendar projected from the same Task facts;
- owner-scoped external Calendar source/event snapshot substrate with provider provenance.

Actual Google/Microsoft OAuth/polling/free-busy adapters remain to be connected.

### Agents / Approvals

Implemented. Capability-backed Tasks/WorkflowExecutions are projected separately from human work with authority, budget/spend, failures and pending ApprovalRequest controls.

### Automations / Activepieces

Implemented KAIRO-owned AutomationDefinition/AutomationInvocation state. Definitions are owner/Project scoped and created disabled. Activepieces remains an execution adapter behind a SecretReference. The webhook side-effect boundary uses one Temporal attempt; uncertain outcomes become `outcome_ambiguous` instead of blind replay. Controlled full-stack proof code crosses Core → Temporal → Worker → OpenBao → webhook fixture. A real provisioned Activepieces flow still needs provider validation.

### Finance & Crypto / Rotki

Implemented sourced FinanceSource/Account/Position read model, unsigned transaction proposals and a concrete read-only Rotki connector. Rotki credentials stay behind OpenBao and never enter browser or Temporal payloads. Controlled full-stack provider-fixture proof code covers normalization, stable identities, credential non-disclosure and last-good-snapshot preservation. A real Rotki release still needs provider validation.

There is intentionally no sign/send/broadcast API. Future signing must remain behind explicit user/policy approval and an isolated signer/wallet/hardware-wallet boundary.

### Desktop / Tauri

Implemented first native slice using the same Cockpit:

- runtime/platform/capability introspection;
- clipboard text read/write;
- local notifications with permission requested on use;
- user-selected WebView file input;
- fixed `CmdOrCtrl+Shift+Space` summon shortcut that only restores/shows/focuses KAIRO.

Screenshot, microphone/VAD/wake-word/voice, selected-directory scopes and configurable native shortcut registration remain unavailable until their bounded contracts exist.

## Authentication and multi-user hardening

### Identity perimeter

Implemented:

- Keycloak Authorization Code + PKCE S256 before React mounts;
- bearer-authenticated Core requests;
- tokens remain in adapter memory rather than LocalStorage/IndexedDB;
- bearer-authenticated streamed Graph activity;
- fail-closed public `/v1/*` auth perimeter;
- explicit Web/Tauri CORS origins;
- identity/logout surface in Settings.

### Ownership migrations

Current branch contains:

- `0013_canonical_project_relationship_ownership` — Project/Relationship subject ownership;
- `0014_project_scoped_control_plane_ownership` — Project/subject DB consistency for Automations, FinanceConnectors and optional Finance proposal Project bindings;
- `0015_secret_reference_ownership` — personal SecretReference ownership + same-owner connector bindings;
- `0016_automation_idempotency_scope` — Automation idempotency scoped to one AutomationDefinition;
- `0017_tool_invocation_ownership` — ToolInvocation owner + subject-local idempotency + Task/Project owner trigger.

ADR-040/041/042 record canonical-world ownership, personal vault semantics and ToolInvocation ownership.

### Personal vault / SecretReference

Implemented:

- authenticated users manage only their own SecretReferences;
- authenticated clients cannot choose arbitrary OpenBao paths;
- Core allocates a subject-scoped managed KV-v2 path;
- public SecretReference responses expose only logical handle metadata and **do not expose `provider_path`**;
- write-only value provisioning returns key names/version, never values;
- explicit irreversible `DELETE /v1/secret-references/{id}/values` destroys KV-v2 versions/metadata;
- another subject receives 404 for reads/writes/destruction;
- KAIRO reference deletion is refused while Automations/Finance connectors still use it or OpenBao still contains values;
- if OpenBao is unavailable, KAIRO refuses metadata deletion rather than pretending the vault is empty;
- Settings exposes provisioning, explicit destruction and reference deletion as separate actions.

### MCP control-plane vs user execution

Implemented distinction:

- ToolServer/ToolDefinition remain shared deployment/admin control-plane records;
- normal `GET /v1/tool-servers` is sanitized and omits endpoint URLs/arbitrary server metadata;
- ordinary `kairo-user` sessions can inspect shared tool contracts/policy state but do not receive server/policy mutation controls in the Cockpit;
- `kairo-admin` (and auth-disabled local development) retains registration/policy controls;
- ToolInvocation is user-world execution state with explicit subject ownership;
- direct and Research-generated ToolInvocations preserve the Task→Project owner;
- PostgreSQL rejects a ToolInvocation bound to a Task owned by another subject;
- caller idempotency is subject-local rather than installation-global.

### Deployment diagnostics

Installation-wide diagnostics are now explicit admin surfaces:

- `/v1/system/components`;
- `/v1/system/architecture`;
- `/v1/system/outbox`.

Normal users receive 403; `kairo-admin` retains access. Health/readiness remain orchestrator probes.

### Ownership validation code committed

The dedicated Ownership workflow now compiles/runs proof code for:

- canonical Project/Task/Graph two-user isolation;
- Assistant/News/Memory/Research two-user isolation;
- SecretReference/Automation/Finance connector ownership + credential-retention lifecycle;
- ToolInvocation source/migration invariants;
- **ToolInvocation two-user runtime idempotency/read isolation** using one shared logical MCP contract;
- admin-only deployment diagnostics.

The MCP management proof also checks that ordinary shared server listings omit endpoint/metadata topology.

These proofs are **committed but not claimed as passed on the current head** because GitHub still does not assign a runner under issue #38.

## What is implemented but not yet current-head validated

Because of issue #38, the following status is “implemented, awaiting actual execution”, not “production working”:

- migrations 0013–0017 and current ownership changes;
- current Foundation/Graph/Desktop validation suites;
- all new two-user/control-plane proofs;
- current Research #36/#37 stack;
- current MCP/Document/Automation/Finance controlled integration proofs;
- current Web + Rust/Tauri build on the latest branch head.

## Major work still remaining

### Before treating the test baseline as validated

1. Resolve GitHub Actions runner allocation issue #38.
2. Execute #36 → #37 → #39 in order on real runners.
3. Fix only real executed failures and rerun until green.
4. Complete the final route/data-lifecycle audit and freeze this stack as one coherent Test Interface baseline.

### Provider work

- Google/Microsoft Calendar OAuth, polling and free/busy adapters;
- validate Rotki adapter against a provisioned real release/version;
- validate an actual Activepieces flow;
- add exchange/wallet Finance adapters only where useful.

### Desktop / presence

- authenticated runtime/server configuration hardening;
- screenshot/capture;
- microphone/VAD/transcription/voice + visible recording state;
- selected-directory/watched-folder access with bounded scopes.

### Brain / collaboration

- audited canonical relationship/domain editing;
- richer collaborative authoring on top of canonical mutations rather than presentation-only graph moves.

### Finance signing

- explicit isolated signer / hardware-wallet / user-wallet handoff UX;
- still no agent-accessible private-key custody or generic sign/send/broadcast path.

### Developer / computer use

- browser/computer-use specialist capabilities;
- production-grade isolation for untrusted code/actions.

### Production operations / commercial multi-user

- finish route-by-route ownership/control-plane classification;
- define full account export/deletion lifecycle across PostgreSQL, SeaweedFS, OpenBao and rebuildable projections;
- least-privilege production OpenBao policy for only the managed KAIRO user-secret data/metadata paths/actions;
- TLS/reverse proxy/private-network policy;
- real workload identities instead of development tokens;
- untrusted execution isolation;
- verified encrypted off-host recovery;
- provider-specific rate limits/retries/credential lifecycle;
- current-head validation on supported OS/runtime combinations.

## Current implementation order

1. **Finish the narrow remaining route/data-lifecycle audit.**
2. **Restore real CI execution and validate the entire stacked baseline.**
3. **Freeze Test Interface v1 as the coherent daily-use test baseline; do not replace its UI architecture.**
4. Connect real Calendar / Rotki / Activepieces providers to the already-defined boundaries.
5. Continue Tauri with screenshot → microphone/voice as separate permissioned capabilities.
6. Add isolated signing and Developer/computer-use only behind explicit policy/audit boundaries.

The Block 3 goal is not “a pretty graph”. It is one stable KAIRO environment in which every visible object, relationship, activity pulse, external observation and specialist workspace remains traceable to KAIRO-owned canonical state, provenance, identity and policy boundaries.
