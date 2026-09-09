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
- OpenBao: secret-value custody; public KAIRO state stores logical vault handles only.
- Conversation / Message / Command: canonical conversational continuity.
- KAIRO Capability contracts: policy/authority boundary above replaceable engines.
- LiteLLM: model gateway with canonical PostgreSQL budget/usage accounting.
- Mem0 + Graphiti/Neo4j: rebuildable projections, never canonical state.
- Docling: preferred parser into canonical Documents / Versions / Chunks.
- MCP: shared deployment registry + KAIRO-owned user execution ledger/policy.
- Activepieces: replaceable Automation execution adapter behind KAIRO.
- Finance: sourced observations; Rotki is the first read-only provider adapter; signing remains outside the AI/runtime boundary.
- Tauri: bounded Desktop trust boundary around the same Web Cockpit, not a second frontend.

## Block 1 — platform substrate

**Implementation: complete.**

Projects, Tasks, Relationships, WorkflowExecutions, Artifacts, Assets, Devices, SecretReferences, Audit and Outbox state are in place together with deterministic Temporal identity, transactional event delivery, authenticated resources, object digest verification and backup/restore substrate.

Earlier Foundation proofs established the baseline invariants. Current stacked heads still need fresh real-runner validation after issue #38 is resolved.

## Block 2 — intelligence and safe autonomy

### Policy / approvals / accounting

**Implemented.** Authority ceilings, approvals, signed capability tokens, hard Task budgets and canonical model usage accounting are Core-owned. Paid-provider replay ambiguity fails closed.

### Command Kernel / Assistant

**Implemented on the stacked Block 2 head.** `POST /v1/assistant/commands` is the conversational entry point. Deterministic routing is first-tier; durable constrained semantic routing is second-tier. Conversation state remains canonical.

### News / Research / Memory

**Implemented in stacked layers; current heads await real CI.** News Intelligence is operational, Research synthesis/handoff lives on #36/#37, and Mem0/Graphiti remain rebuildable memory projections. Generative Graphiti entity/fact extraction stays deferred until it can use KAIRO's accounted/replay-safe model boundary.

### Documents / Knowledge / MCP

**Implemented.** Asset → Document → Version → Chunk is canonical and provenance-preserving. Knowledge reads only the latest completed generation. MCP registry/policy/schema snapshots, Worker live-contract revalidation and child invocation Tasks are present.

## Block 3 — permanent KAIRO Test Interface v1

**Active implementation: PR #39.**

### Permanent Cockpit / spatial Brain

Implemented:

- stable left navigation, central working surface, contextual right rail and compact Command Dock;
- same shell in Web and Tauri Desktop;
- bounded Home/neighborhood/search Graph projections;
- custom R3F/Three.js mycelium with deterministic Worker layout, instanced nodes, batched filaments and real activity pulses;
- semantic LOD, adaptive quality and reduced motion;
- deterministic natural-language focus/isolate directives;
- KAIRO Brain **3D / Carte 2D / Liste** from the same canonical projection.

### Active specialist workspaces

Implemented inside the same Cockpit:

- Projects lifecycle/hierarchy;
- Tasks / Today / Gantt;
- weekly Calendar plus sourced external-event overlay substrate;
- Knowledge/Documents;
- Agents / Approvals;
- Automations / Activepieces boundary;
- Finance & Crypto / read-only Rotki connector;
- Tools / MCP registry + policy.

Actual Google/Microsoft Calendar adapters, a real provisioned Rotki release and a real Activepieces flow still need provider validation.

### Desktop / Tauri

Implemented first native slice using the same Cockpit:

- runtime/platform/capability introspection;
- clipboard text read/write;
- local notifications with permission requested on use;
- user-selected WebView file input;
- fixed `CmdOrCtrl+Shift+Space` summon shortcut that only restores/shows/focuses KAIRO.

Screenshot, microphone/VAD/wake-word/voice and selected-directory scopes remain unavailable until their bounded contracts exist.

## Authentication and multi-user hardening

### Identity perimeter

Implemented:

- Keycloak Authorization Code + PKCE S256 before React mounts;
- bearer-authenticated Core requests and streamed Graph activity;
- tokens remain in adapter memory rather than LocalStorage/IndexedDB;
- fail-closed public `/v1/*` auth perimeter;
- explicit Web/Tauri CORS origins;
- identity/logout surface in Settings.

### Ownership migrations

Current branch contains:

- `0013_canonical_project_relationship_ownership` — Project/Relationship subject ownership;
- `0014_project_scoped_control_plane_ownership` — Project/subject DB consistency for Automations, FinanceConnectors and optional Finance proposal Project bindings;
- `0015_secret_reference_ownership` — personal SecretReference ownership + same-owner connector bindings;
- `0016_automation_idempotency_scope` — Automation idempotency scoped to one AutomationDefinition;
- `0017_tool_invocation_ownership` — ToolInvocation owner + subject-local idempotency + Task/Project owner trigger;
- `0018_asset_document_ownership` — first-class indexed Asset/Document owners + Project/Asset/Document owner triggers.

ADR-040 through ADR-043 record canonical-world ownership, personal vault semantics, ToolInvocation ownership and first-class Asset/Document ownership.

### Personal vault / OpenBao

Implemented:

- authenticated users manage only their own SecretReferences;
- authenticated clients cannot choose arbitrary OpenBao paths;
- public responses do not expose `provider_path`;
- write-only value provisioning returns key names/version, never values;
- explicit irreversible value destruction is distinct from deleting the logical KAIRO reference;
- reference deletion is refused while connectors still use it, OpenBao still contains values, or OpenBao is unavailable;
- production policy `infrastructure/openbao/policies/kairo-core-user-secrets.hcl` grants only the managed user-secret data/metadata operations required by KAIRO.

### MCP control-plane vs user execution

Implemented distinction:

- ToolServer/ToolDefinition remain shared deployment/admin control-plane records;
- ordinary ToolServer listings omit endpoint URLs/arbitrary deployment metadata;
- ordinary users inspect contracts/policy state but do not receive admin mutation controls;
- ToolInvocation is user-world execution state with explicit subject ownership;
- direct and Research-generated ToolInvocations preserve Task→Project ownership;
- PostgreSQL rejects a ToolInvocation bound to a foreign Task;
- caller idempotency is subject-local rather than installation-global.

### Assets / Documents

Implemented first-class ownership:

- Asset and Document authorization no longer depends on `metadata_json.owner_subject`;
- list/detail/content/delete/search paths filter first-class subject columns;
- Knowledge and Graph consume the same owner fact;
- PostgreSQL triggers reject future cross-owner Project/Asset/Document bindings;
- internal document source resolution verifies Document/Asset owner consistency before returning a Worker source.

### Deployment diagnostics

Installation-wide diagnostics are admin-only:

- `/v1/system/components`;
- `/v1/system/architecture`;
- `/v1/system/outbox`.

Normal users receive 403; `kairo-admin` retains access. Health/readiness remain orchestrator probes.

## Account data lifecycle

ADR-044 defines account erasure as a **cross-store state machine**, not a Project/database cascade.

Implemented first slice:

- `GET /v1/account/data-inventory` — subject-scoped aggregate canonical counts, tracked Asset object count/bytes, projection-ledger count and explicit retention boundaries;
- `GET /v1/account/export/manifest` — versioned `kairo.account-export-manifest.v1`, currently truthful `manifest_only` with `bundle_export_available=false`;
- `GET /v1/account/erasure/preflight` — canonical blockers vs complete-erasure blockers;
- Settings surface showing the same inventory/preflight and allowing local JSON manifest download;
- no destructive account endpoint is advertised while complete cross-store erasure cannot be guaranteed.

Canonical deletion is blocked while Tasks, Workflows, Approvals, AutomationInvocations or ToolInvocations remain active.

Complete erasure is still blocked by some combination of:

- remaining personal SecretReferences/credential material;
- missing subject-wide Mem0/Graphiti purge adapter;
- audit/outbox retention not yet fully subject-addressable;
- Keycloak identity deletion contract not yet implemented through KAIRO;
- backup expiry/restore-after-erasure semantics not yet formally verified.

Secret values are deliberately excluded from export; export must never become a secret-readback path.

## Validation code committed

The dedicated Ownership workflow now compiles/schedules proof code for:

- canonical Project/Task/Graph two-user isolation;
- Assistant/News/Memory/Research two-user isolation;
- Asset/Document two-user isolation;
- SecretReference/Automation/Finance connector ownership + credential-retention lifecycle;
- ToolInvocation source/migration invariants + two-user idempotency/read isolation;
- least-privilege OpenBao policy;
- admin-only deployment diagnostics;
- account inventory/export/preflight two-user isolation.

Graph Interface, Desktop, Research, MCP, Document, Automation and Finance validation suites remain committed as well.

These proofs are **implemented but not claimed as passed on the current head** because GitHub still does not assign a runner under issue #38.

## Major work still remaining

### Before treating the test baseline as validated

1. Resolve GitHub Actions runner allocation issue #38.
2. Execute #36 → #37 → #39 in order on real runners.
3. Fix only real executed failures and rerun until green.
4. Finish the remaining cross-store lifecycle/retention contracts and freeze this stack as one coherent Test Interface baseline.

### Account lifecycle / commercial multi-user

- subject-wide idempotent Mem0/Graphiti purge with evidence;
- formal audit/outbox subject indexing, retention/redaction or justified bounded retention;
- Keycloak account deletion/disable contract;
- verified backup expiry and restore-after-erasure semantics;
- full portable canonical export bundle beyond the current manifest;
- eventual replay-safe destructive deletion ledger spanning PostgreSQL, SeaweedFS and OpenBao.

### Provider work

- Google/Microsoft Calendar OAuth, polling and free/busy adapters;
- validate Rotki against a real provisioned release/version;
- validate an actual Activepieces flow;
- add exchange/wallet Finance adapters only where useful.

### Desktop / presence

- authenticated runtime/server configuration hardening;
- screenshot/capture;
- microphone/VAD/transcription/voice + visible recording state;
- selected-directory/watched-folder access with bounded scopes.

### Brain / collaboration / Developer

- audited canonical relationship/domain editing and richer collaboration;
- browser/computer-use specialist capabilities;
- production-grade isolation for untrusted code/actions.

### Finance signing / production operations

- isolated signer / hardware-wallet / explicit wallet handoff; still no agent private-key custody or generic sign/send/broadcast path;
- TLS/reverse proxy/private-network policy;
- production workload identities rather than development tokens;
- verified encrypted off-host recovery and provider-specific rate-limit/retry/credential lifecycle.

## Current implementation order

1. **Finish cross-store lifecycle/retention boundaries without changing the Cockpit architecture.**
2. **Restore real CI execution and validate the entire stacked baseline.**
3. **Freeze Test Interface v1 as the coherent daily-use test baseline.**
4. Connect real Calendar / Rotki / Activepieces providers.
5. Continue Tauri with screenshot → microphone/voice as separate permissioned capabilities.
6. Add isolated signing and Developer/computer-use only behind explicit policy/audit boundaries.

The Block 3 goal is one stable KAIRO environment in which every visible object, relationship, activity pulse, external observation and specialist workspace remains traceable to KAIRO-owned canonical state, provenance, identity, retention and policy boundaries.
