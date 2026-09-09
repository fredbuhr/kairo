# KAIRO implementation status

Last updated: 2026-09-10

## Current phase

KAIRO is transitioning from **Block 2 — intelligence, memory and safe autonomy** into the permanent **Block 3 — Cockpit / Test Interface v1**.

The active Block 3 branch is not a disposable frontend prototype. `KairoCockpit` is the product entrypoint and the spatial world plus specialist workspaces are intended to remain the daily-use Test Interface while later capabilities extend the same structure.

Three stacked pull requests remain in order:

1. **PR #36 — durable multi-slot Research synthesis** (`feat/research-synthesis-checkpoints` → `main`);
2. **PR #37 — Research through the Command Kernel** (`feat/research-command-handoff` → PR #36);
3. **PR #39 — KAIRO Test Interface v1** (`feat/kairo-test-interface-v1` → PR #37).

All remain intentionally unmerged while GitHub Actions issue **#38** prevents GitHub-hosted jobs from receiving a runner. A red check with no allocated runner/no executed steps is infrastructure failure, not code validation. Real hosted runs are required before merge.

## Canonical architecture active

- PostgreSQL + pgvector: canonical domain/state store.
- SeaweedFS: canonical object storage.
- Temporal: durable execution/replay.
- NATS JetStream: bounded event transport fed by transactional PostgreSQL Outbox.
- Keycloak: authenticated Web/Desktop identity boundary.
- OpenBao: secret-value custody; KAIRO exposes only logical handles/status metadata.
- Conversation / Message / Command: canonical conversational continuity.
- LiteLLM: model gateway with canonical PostgreSQL budget/usage accounting.
- Mem0 + Graphiti/Neo4j: rebuildable projections, never canonical truth.
- Docling: canonical Document/Version/Chunk parser boundary.
- MCP: shared deployment registry plus subject-owned invocation/execution state.
- Activepieces: replaceable Automation execution adapter behind KAIRO-owned definitions/history.
- Finance: sourced observations; Rotki is the first read-only provider adapter; signing remains outside AI/runtime custody.
- Tauri: bounded Desktop trust boundary around the same Web Cockpit, not a second frontend.

## Product interface implemented

The current Cockpit contains one persistent shell with left navigation, central work surface, contextual right rail and Command Dock. Home and KAIRO Brain consume one canonical graph contract. Brain provides **3D / Carte 2D / Liste** renderers over the same projection.

Operational workspaces currently include:

- Projects lifecycle/hierarchy;
- Tasks / Today / Gantt;
- weekly Calendar plus sourced external-event overlay substrate;
- Knowledge/Documents;
- Agents / Approvals;
- Automations / Activepieces boundary;
- Finance & Crypto / read-only Rotki connector;
- Tools / MCP registry and policy;
- Assistant / News / Research conversation surfaces;
- Settings for identity, Desktop capabilities, personal secrets and account-data lifecycle.

The 3D mycelium uses the custom R3F/Three.js engine with deterministic Worker layout, instanced nodes, batched filaments, canonical activity pulses, semantic LOD, adaptive quality and reduced motion. Later UI work is tuning/extension of this architecture, not a planned rewrite.

## Intelligence and execution

Implemented in stacked code:

- deterministic-first Command Kernel with constrained semantic routing;
- News Intelligence;
- durable Research synthesis/handoff on #36/#37;
- policy authority ceilings, approvals and signed short-lived capability tokens;
- canonical model usage and budget accounting;
- Temporal durable workflows;
- transactional Outbox → JetStream delivery;
- Mem0/Graphiti rebuildable memory projection and owner-scoped purge;
- canonical Document ingestion/retrieval;
- MCP registry/policy/live Worker schema validation;
- Automation invocation with explicit ambiguous-side-effect handling;
- Rotki read-only synchronization.

Generative Graphiti entity/fact extraction remains deliberately disabled until it is both model-accounted/replay-safe and covered by the owner-purge contract.

## Authentication and multi-user hardening

### Identity perimeter

Implemented:

- Keycloak Authorization Code + PKCE S256 before React mounts;
- bearer-authenticated Core/SSE/audio requests;
- token refresh held in adapter memory rather than LocalStorage/IndexedDB;
- fail-closed public `/v1/*` bearer perimeter;
- separate internal-token boundary for `/internal/v1/*` service calls;
- explicit Web/Tauri CORS origins;
- identity/logout surface in Settings.

### Ownership/evidence migrations

Current branch contains:

- `0013_canonical_project_relationship_ownership` — Project/Relationship subject ownership;
- `0014_project_scoped_control_plane_ownership` — Project/subject consistency for Automations, FinanceConnectors and Finance proposal Project bindings;
- `0015_secret_reference_ownership` — personal SecretReference ownership + same-owner connector bindings;
- `0016_automation_idempotency_scope` — Automation idempotency scoped to one definition;
- `0017_tool_invocation_ownership` — ToolInvocation subject ownership/idempotency + Task/Project owner trigger;
- `0018_asset_document_ownership` — first-class Asset/Document owners + Project/Asset/Document owner triggers;
- `0019_audit_outbox_data_subject` — nullable user-world data-subject ownership for Audit/Outbox, distinct from actor identity;
- `0020_outbox_jetstream_receipts` — exact JetStream stream/sequence publication receipts.

ADR-040 through ADR-047 record the resulting ownership, secret, execution, evidence and retention boundaries.

### Personal OpenBao boundary

Authenticated users manage only their SecretReferences. Core allocates managed subject-scoped KV-v2 paths; browser reads never expose `provider_path` or secret values. Provisioning is write-only and bounded. Credential destruction is explicit and irreversible, while logical reference deletion is separately guarded.

A production OpenBao policy is committed which grants only the managed user-secret data/metadata operations required by KAIRO. Root/dev tokens remain development-only.

### MCP control plane vs execution state

ToolServer/ToolDefinition remain shared deployment/admin records. Ordinary users receive sanitized registry summaries and do not receive administrative mutation controls. ToolInvocation is explicit user-world execution state, owner-scoped in Core and PostgreSQL and propagated through Research child invocations.

### Assets / Documents

Asset and Document authorization no longer depends on JSON metadata. First-class indexed subject columns are used by REST reads, Knowledge and Graph. PostgreSQL rejects cross-owner Project/Asset/Document bindings, and internal document source resolution validates Document/Asset owner consistency.

### Audit / Outbox and JetStream

Audit/Outbox now distinguish data subject from actor. Shared deployment Audit remains shared even when an administrator acted on it. Graph SSE starts with subject-scoped Outbox queries.

Core stores exact JetStream PubAck stream/sequence receipts and publishes `Nats-Msg-Id = OutboxEvent.id`. Core and Worker independently converge `KAIRO_DOMAIN` to `kairo.domain.>`, max 100,000 messages and finite `NATS_DOMAIN_RETENTION_SECONDS` (7 days default), avoiding startup-order-dependent retention.

## Account lifecycle

ADR-044 defines account erasure as a **cross-store state machine**, not a Project/database cascade.

### Inventory / export / preflight

Implemented:

- `GET /v1/account/data-inventory` — subject-scoped canonical counts, tracked Asset bytes, derived-memory purge freshness and evidence counts;
- `GET /v1/account/export/manifest` — versioned `kairo.account-export-manifest.v1`, deliberately `manifest_only` / `bundle_export_available=false`;
- `GET /v1/account/erasure/preflight` — canonical blockers vs complete-erasure blockers;
- Settings surface that exposes real lifecycle state while full destructive deletion remains disabled.

Secret values are deliberately absent from export. Raw retained Audit/Outbox payloads are not exported by the current manifest.

### Derived-memory purge

`POST /v1/account/derived-memory/purge` creates/reuses a canonical A1 `memory.purge` Task and executes through Temporal/Worker.

Mem0 is deleted by owner scope and verified empty. Current non-generative Graphiti groups are deleted by owned `conversation:<id>` groups and verified empty. `MemoryProjectionRecord` rows are cleared only after projector success. Canonical Conversations/Messages remain untouched. A purge cutoff tied to the latest canonical message makes later messages render the purge stale rather than overstating deletion.

### Audit / Outbox evidence retention

ADR-047 turns the Audit/Outbox blocker into an actual bounded erasure-preparation action:

- `GET /v1/account/evidence/retention` reports subject-only readiness/counts;
- `POST /v1/account/evidence/retention/apply` requires literal confirmation `MINIMIZE_ACCOUNT_EVIDENCE`;
- non-terminal Tasks/Workflows/Approvals/AutomationInvocations/ToolInvocations block the operation;
- unpublished events and malformed JetStream receipts fail closed;
- exact receipted JetStream messages are deleted before their PostgreSQL Outbox rows;
- historical published rows without receipts must age beyond verified max-age + safety grace instead of receiving guessed sequence ids;
- subject-owned Audit is minimized to coarse unowned facts;
- shared administrative Audit preserves shared resource history but removes/redacts the erased actor identity;
- one neutral aggregate receipt remains without a subject identifier/hash;
- processing is bounded to 250 Outbox rows per pass and retry-safe for already-absent transport messages.

Later user activity creates fresh evidence and re-blocks preflight. This is why a final destructive flow still requires an enforced account freeze.

### Keycloak identity management boundary

ADR-048 and `KeycloakIdentityManager` now establish the **provider adapter**, but not the final user-facing deletion flow.

Implemented foundation:

- dedicated confidential `kairo-identity-manager` workload identity;
- `client_credentials`, never the public `kairo-web` client;
- no runtime reuse of bootstrap Keycloak admin credentials;
- exact immutable Keycloak `sub` used as Admin REST user id, not username/email search;
- bounded internal `get_identity`, `disable_identity` and `delete_identity` methods with post-operation verification;
- management secret is Core-only configuration and empty by default in development;
- production compose wiring exists for a separately provisioned least-privilege service account;
- there is deliberately **no APIRouter/public disable/delete endpoint yet**.

Keycloak disable alone is not a KAIRO write freeze because already-issued bearer tokens may remain valid until expiry. A local/durable KAIRO freeze must exist before this provider mutation is wired into account erasure.

### Backup restore-after-erasure guard

ADR-049 introduces a monotonic erasure-ledger boundary outside the rollback-able Restic application-state snapshot.

Implemented current guard:

- `.kairo-erasure-ledger/` is excluded from Git/application state;
- `restore.sh` derives production from `KAIRO_ENV`, not an overlay filename convention;
- production restore refuses a missing external erasure ledger;
- any non-empty erasure ledger refuses restore before Restic materialization or durable volume mutation;
- normal Restic backup remains limited to PostgreSQL/NATS/SeaweedFS/OpenBao and intentionally does not back up the erasure ledger;
- `docs/operations.md` documents separate encrypted/replicated production storage for the future ledger.

This **prevents accidental resurrection through current restore tooling**. It does not yet implement tombstone creation/reconciliation and it does not physically destroy old encrypted Restic snapshots. Backup expiry/prune and restore reconciliation remain complete-erasure blockers.

## Desktop / Tauri

Implemented first native slice using the same Cockpit:

- runtime/platform/capability introspection;
- clipboard text read/write;
- local notifications requested on use;
- explicit WebView file input;
- fixed `CmdOrCtrl+Shift+Space` summon shortcut that only restores/shows/focuses KAIRO.

Screenshot, microphone/VAD/wake-word/voice and selected-directory scopes remain unavailable until their bounded contracts exist.

## Validation code committed

The Ownership/Foundation suites now compile/schedule contracts/proofs covering:

- Project/Task/Graph two-user isolation;
- Assistant/News/Memory/Research isolation;
- Asset/Document two-user isolation;
- SecretReference/Automation/Finance ownership and credential lifecycle;
- ToolInvocation ownership/idempotency;
- least-privilege OpenBao policy;
- admin-only deployment diagnostics;
- Audit/Outbox data-subject ownership;
- bounded JetStream max-age + PubAck receipts;
- internal Worker Task-start trust boundary;
- account inventory/export/preflight isolation;
- Audit/Outbox evidence-retention source/behavior contract;
- Keycloak identity-management boundary contract;
- restore-after-erasure guard contract;
- pinned Mem0/Graphiti purge-provider compatibility and durable projection/purge lifecycle.

Graph, Desktop, Research, MCP, Document, Automation and Finance suites remain committed too.

A two-user **destructive** evidence-retention runtime proof could not be committed in the earlier tooling session because the repository write was blocked by the surrounding safety control. Do not treat that runtime proof as existing. The retention implementation currently has a static behavior/source contract plus the existing two-user lifecycle/readiness coverage.

None of the current-head proof/build code is claimed as passed because issue #38 still prevents GitHub-hosted runner execution.

## Major work still remaining

### Release gate for Test Interface v1

1. Resolve GitHub Actions runner allocation issue #38.
2. Execute #36 → #37 → #39 on real runners.
3. Fix only actual executed failures and rerun until green.
4. Freeze the stack as one coherent daily-use Test Interface baseline.

### Account lifecycle / commercial multi-user

- durable local account freeze that blocks stale bearer-token writes while allowing the erasure orchestrator to proceed;
- replay-safe account-erasure operation/deletion ledger;
- provision and provider-validate the dedicated Keycloak management service account;
- final Keycloak disable/session/delete sequencing;
- final PostgreSQL + SeaweedFS + OpenBao + projection destructive ordering;
- monotonic erasure tombstone creation and verified post-restore reconciliation;
- documented/verified backup retention, forget/prune and maximum lifetime;
- full portable canonical export bundle beyond the manifest.

### Provider work

- Google/Microsoft Calendar OAuth/polling/free-busy adapters;
- validation against a real provisioned Rotki release;
- validation against a real Activepieces flow;
- additional exchange/wallet adapters only where useful.

### Desktop / presence

- authenticated runtime/server configuration hardening;
- screenshot/capture;
- microphone/VAD/transcription/voice + visible recording state;
- selected-directory/watched-folder access with explicit scopes.

### Brain / collaboration / Developer

- audited canonical relationship/domain editing and richer collaboration;
- browser/computer-use specialist capabilities;
- production-grade isolation for untrusted code/actions.

### Finance signing / production operations

- isolated signer/hardware-wallet/explicit wallet handoff; still no agent private-key custody or generic sign/send/broadcast path;
- TLS/reverse proxy/private-network policy;
- production workload identities rather than development tokens;
- verified encrypted off-host recovery and provider-specific rate-limit/retry/credential lifecycle.

## Current implementation order

1. **Implement the durable local account-freeze/erasure ledger boundary without exposing premature full deletion.**
2. **Define tombstone emission + post-restore reconciliation/backup retention semantics.**
3. **Restore real CI execution and validate the entire stacked baseline.**
4. Freeze Test Interface v1, then connect real external providers.
5. Continue Tauri with screenshot → microphone/voice as separate permissioned capabilities.
6. Add isolated signing and Developer/computer-use only behind explicit policy/audit boundaries.

The Block 3 goal remains one stable KAIRO environment in which every visible object, relationship, activity pulse, external observation and specialist workspace is traceable to KAIRO-owned canonical state, provenance, identity, retention and policy boundaries.
