# KAIRO Block 3 implementation review — 2026-09-10

Status: implementation audit of the active stacked Test Interface v1 branch (`feat/kairo-test-interface-v1`, PR #39).

This review distinguishes **implemented in code** from **executed and validated on the current head**. GitHub Actions issue #38 is still preventing hosted jobs from receiving runners. A red workflow with no assigned runner / no executed steps is therefore not evidence that the code failed its tests, but it is also not evidence that the code passed. No stacked PR should merge until real runs execute #36 → #37 → #39 in order.

## Executive state

KAIRO is no longer primarily a backend prototype. The active branch contains the intended daily-use Test Interface architecture and most of the first operational Cockpit: spatial Home/Brain, Projects, Knowledge, Tasks/Today/Gantt, Calendar, Agents/Approvals, Automations, Tools, Finance/Crypto, Assistant and a bounded Tauri desktop boundary.

The dominant Block 3 risk is **trust-boundary and lifecycle completion rather than missing UI**. The current hardening work has therefore frozen large feature expansion while ownership, secret custody, execution idempotency, evidence retention and account-erasure truthfulness are made explicit.

Migrations `0013`–`0020` plus ADR-040 through ADR-047 now cover canonical user ownership, project-scoped control-plane consistency, personal SecretReferences, Automation/ToolInvocation idempotency, Asset/Document first-class ownership, Audit/Outbox data-subject addressing, bounded JetStream receipts and the first real cross-store account-evidence retention action.

## Implemented in code

### Permanent Cockpit / UI architecture

- one `KairoCockpit` product entrypoint;
- stable left navigation / central work surface / contextual rail / Command Dock;
- Home and Brain share one canonical graph contract;
- 3D mycelium, 2D mind map and accessible list are renderers of the same projection;
- Tauri reuses the same Web Cockpit rather than introducing a second frontend;
- specialist workspaces consume canonical APIs or sourced read models rather than parallel frontend domain state.

### Spatial graph

- bounded Home/neighborhood/search projections;
- canonical explicit Relationships and FK-derived structural edges with distinct provenance;
- deterministic natural-language focus/isolate directives;
- custom R3F/Three.js mycelium with deterministic Worker layout, instanced nodes, batched filaments, activity pulses, semantic LOD, adaptive quality and reduced motion;
- 2D mind-map projection from the same `KairoGraphProjection`;
- live SSE activity scoped first by subject-owned canonical Outbox events.

### Operational Cockpit

- Projects lifecycle/hierarchy and parent-cycle refusal;
- Tasks with explicit priority/start/end/due facts;
- deterministic Today and Gantt from the same Task facts;
- weekly Calendar plus provenance-preserving external-event snapshot substrate;
- Documents/Knowledge with Asset → Document → Version → Chunk provenance;
- capability execution Tasks separated into Agents;
- real ApprovalRequest controls;
- shared MCP ToolServer/ToolDefinition policy plus subject-owned ToolInvocation execution state;
- KAIRO-owned Automation definitions/invocations with Activepieces behind a replaceable webhook adapter;
- sourced Finance read model, unsigned transaction proposals and first read-only Rotki connector.

### Durable intelligence / execution

- deterministic-first Command Kernel and constrained semantic routing;
- News Intelligence;
- stacked durable autonomous Research synthesis/handoff in #36/#37;
- Mem0/Graphiti rebuildable memory projections;
- LiteLLM gateway with canonical budget/usage accounting;
- Temporal durable execution;
- transactional PostgreSQL Outbox → bounded NATS JetStream delivery.

### Desktop

- Tauri v2 shell over the same Web application;
- bounded IPC capability introspection;
- clipboard read/write;
- local notifications requested on use;
- fixed `CmdOrCtrl+Shift+Space` summon shortcut;
- no generic shell execution, unrestricted filesystem permission or frontend shortcut-registration authority.

### Authentication

- Keycloak Authorization Code + PKCE S256 before React mounts;
- bearer-authenticated Core/SSE/audio requests;
- token refresh stays in adapter memory rather than LocalStorage/IndexedDB;
- fail-closed Core `/v1/*` bearer perimeter;
- separate internal-token boundary for `/internal/v1/*` service calls;
- explicit Web/Tauri CORS origins;
- identity/logout controls in Settings.

## Ownership and lifecycle hardening completed in this review

### Canonical world

Migration 0013 and ADR-040 make `Project.keycloak_subject` the primary root for Project-scoped work and give polymorphic Relationships an explicit subject. User-specific Assistant/News/Documents/Memory workspaces use deterministic per-subject system Projects. Foreign and absent user-world UUIDs collapse to the same 404 behavior on covered public APIs.

Migration 0014 adds database consistency for Project-bound Automation, Finance connector and optional Finance proposal bindings. Public Finance proposal creation now also calls `require_owned_project(...)` rather than depending on a database violation for a foreign Project.

### Personal secret vault

Migration 0015 and ADR-041 make SecretReference a subject-owned logical vault handle. Authenticated clients cannot choose arbitrary OpenBao paths and public reads do not expose `provider_path`.

Value provisioning is bounded and write-only. Irreversible OpenBao value destruction is separate from deleting the PostgreSQL reference. Reference deletion is refused while a connector uses it, values remain, or OpenBao is unavailable. The committed production OpenBao policy grants only KAIRO-managed user-secret data/metadata operations.

### Caller-controlled idempotency

Migration 0016 scopes Automation idempotency to one AutomationDefinition.

Migration 0017 and ADR-042 make ToolInvocation user-world execution state, scope its idempotency by subject and add a database Task/Project-owner invariant. Research-generated child invocations propagate the same owner.

### Assets and Documents

Migration 0018 and ADR-043 promote historical JSON owner tags into first-class indexed `keycloak_subject` fields on Asset and Document. Public reads, Knowledge and Graph now consume those typed owner facts. PostgreSQL triggers reject future cross-owner Project/Asset/Document bindings.

### Audit / Outbox data-subject addressing

Migration 0019 and ADR-045 introduce nullable `keycloak_subject` on Audit/Outbox as **owner of the user-world resource**, not actor identity. Shared deployment/control-plane evidence remains unowned even when an administrator was the actor.

`event_ownership.resolve_data_subject(...)` centralizes ownership resolution. Graph SSE queries subject-owned Outbox rows before applying entity-level defense-in-depth ownership validation.

### JetStream bounded transport / receipts

Migration 0020 and ADR-046 add exact `jetstream_stream` / `jetstream_sequence` receipts. Core stores PubAck identity before marking Outbox publication complete and publishes with `Nats-Msg-Id = OutboxEvent.id`.

Core and Worker independently converge `KAIRO_DOMAIN` on `kairo.domain.>`, max 100,000 messages and finite configurable max-age (7 days default), avoiding startup-order dependence.

### Internal Task start boundary

A review caught the Worker memory projector calling the authenticated public Task start route without a user bearer. Core now exposes an internal-token-protected Task start route that reuses the exact same deterministic start implementation. The Worker uses only that internal route. `internal_task_start_contract.py` prevents regression to the public service-call path.

### Account data lifecycle

ADR-044 establishes an explicit cross-store state machine rather than a Project/database cascade.

Current account lifecycle includes:

- subject-scoped data inventory;
- versioned export manifest (`manifest_only`);
- erasure preflight with canonical vs complete blockers;
- durable Mem0/Graphiti purge that preserves canonical Conversations;
- Settings presentation of real lifecycle state rather than a fake delete button.

### Audit / Outbox evidence retention

ADR-047 and `account_evidence.py` now implement the first destructive cross-store erasure-preparation stage.

`GET /v1/account/evidence/retention` reports readiness and only subject-level aggregate counts. `POST /v1/account/evidence/retention/apply` requires the literal confirmation `MINIMIZE_ACCOUNT_EVIDENCE` and refuses to run while Tasks, Workflows, Approvals, AutomationInvocations or ToolInvocations are non-terminal.

The action also refuses unpublished Outbox or partial stream/sequence receipts.

For receipted events, exact JetStream messages are deleted before their PostgreSQL Outbox rows. An already-absent JetStream sequence is an idempotent success. Historical published rows without a receipt are never assigned a guessed sequence: they must age past the verified domain max-age plus a safety grace before their PostgreSQL delivery evidence can be removed.

After subject Outbox is empty, subject-owned Audit rows are minimized to coarse unowned operational facts and shared administrative Audit rows have the erased user's actor attribution/redactable structured values removed. A final deployment-neutral aggregate receipt contains no subject id/hash.

The operation is bounded to 250 Outbox rows per pass. It does not freeze an active account: later activity creates fresh evidence and makes erasure preflight dirty again. A future full account state machine must freeze/disable identity before the final pass.

The Settings lifecycle surface now exposes this operation independently from derived-memory purge and full account deletion.

## Validation code committed, but not current-head validated

The current branch contains proof/build code for:

- Project/Task/Graph two-user isolation;
- Assistant/News/Memory/Research isolation;
- Asset/Document two-user isolation;
- SecretReference/Automation/Finance ownership and credential lifecycle;
- ToolInvocation ownership/idempotency;
- admin-only deployment diagnostics;
- least-privilege OpenBao policy;
- Audit/Outbox data-subject ownership;
- bounded JetStream stream configuration and publication receipts;
- internal Worker Task-start trust boundary;
- account inventory/export/preflight isolation;
- account evidence-retention static contract;
- pinned Mem0/Graphiti purge-provider API contract;
- durable memory projection/rebuild/purge lifecycle;
- Graph, Desktop, Research, MCP, Document, Automation and Finance integration/build suites.

One intended additional two-user **destructive evidence-retention runtime proof** was not added during this tooling session because the repository write was blocked by the surrounding tool safety control. It must not be listed as existing validation. The existing two-user account-lifecycle proof verifies subject isolation and the retention blocker/readiness contract, while the destructive retention path currently has the static source/behavior proof only.

None of these current-head suites may be called passed: GitHub Actions issue #38 still prevents hosted jobs from receiving a runner.

## Known incomplete or intentionally unavailable areas

### CI / mergeability evidence

- GitHub-hosted jobs still fail before runner assignment under issue #38;
- #36 → #37 → #39 remain unmerged;
- PR #39 remains draft until actual jobs execute and real failures are fixed.

### Account identity / destructive lifecycle

The Audit/Outbox policy is no longer merely outstanding; an explicit retention action exists. The remaining account-erasure gap is now concentrated in:

- Keycloak account freeze/disable/delete semantics;
- replay-safe final cross-store deletion ledger for PostgreSQL + SeaweedFS + OpenBao + projections + identity;
- an account freeze before the final cleanup so writes cannot recreate evidence mid-erasure;
- backup expiry and restore-after-erasure tombstone semantics;
- full portable canonical export beyond the manifest.

### Provider integrations

- Google/Microsoft Calendar OAuth, polling and free/busy adapters are not yet implemented;
- Rotki needs validation against a separately provisioned real release/version;
- additional exchange/wallet Finance adapters are not implemented;
- Activepieces still needs validation against a separately provisioned real flow.

### Desktop / voice

- screenshot/capture bridge is not enabled;
- microphone/VAD/wake-word/transcription/voice is not complete;
- selected-directory/watched-folder access is not enabled;
- user-configurable native shortcut registration remains intentionally unavailable.

### Finance signing

- transaction proposals are unsigned drafts only;
- isolated signer / hardware-wallet / explicit wallet handoff UX is not implemented;
- there is intentionally no agent-accessible sign/send/broadcast API.

### Brain/domain editing and collaboration

Exploration/filtering/focus are implemented. Rich explicit relationship/domain editing and collaborative authoring still require audited canonical mutations rather than presentation-only graph movement.

### Developer / computer use

Browser/computer-use specialist capabilities are not yet operational in the Cockpit and untrusted code/action execution isolation is not production-hardened.

### Memory semantics

Mem0/Graphiti projections exist. Generative Graphiti entity/fact extraction remains deferred until it can use the accounted/replay-safe model boundary **and** the resulting generated material is covered by the account purge contract.

### Production operations

Still required before commercial multi-user deployment:

- Keycloak account lifecycle and backup/tombstone contract;
- TLS/reverse proxy/private-network policy;
- production workload identities rather than development tokens;
- verified encrypted off-host recovery;
- provider-specific rate-limit/retry/credential lifecycle handling;
- untrusted execution isolation;
- real current-head CI evidence on supported OS/runtime combinations.

## Current implementation order

1. Define the Keycloak account freeze/disable/delete boundary and backup restore-after-erasure/tombstone semantics without changing the Cockpit architecture.
2. Obtain real GitHub-hosted CI execution and fix only actual executed failures.
3. Validate/freeze the current Test Interface stack as one coherent baseline before adding another large module.
4. Connect real Calendar / Rotki / Activepieces providers.
5. Continue Tauri with screenshot → microphone/voice as individually permissioned capabilities.
6. Add isolated signing and Developer/computer-use only behind explicit policy/audit boundaries.

## Merge rule

PR #39 remains draft. Extensive implementation is not production validation. Real executed CI for #36 → #37 → #39 remains the release gate.
