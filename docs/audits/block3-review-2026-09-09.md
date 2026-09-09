# KAIRO Block 3 implementation review — 2026-09-09

Status: implementation audit of the active stacked Test Interface v1 branch (`feat/kairo-test-interface-v1`, PR #39).

This review distinguishes **implemented in code** from **executed and validated on the current head**. GitHub Actions issue #38 is still preventing hosted jobs from receiving runners. A red workflow with no assigned runner / no executed steps is therefore not evidence that the code failed its tests, but it is also not evidence that the code passed. No stacked PR should merge until real runs execute #36 → #37 → #39 in order.

## Executive state

KAIRO is no longer primarily a backend prototype. The active branch contains the intended daily-use Test Interface architecture and most of the first operational Cockpit: spatial Home/Brain, Projects, Knowledge, Tasks/Today/Gantt, Calendar, Agents/Approvals, Automations, Tools, Finance/Crypto, the Assistant surface and an initial Tauri desktop boundary.

The dominant risk discovered by the Block 3 review has been **trust-boundary completion rather than missing UI**. Authentication existed, but user-world data, control-plane bindings and connector metadata still had several paths that could remain global or depend only on database fallback constraints. The current hardening tranche therefore prioritizes authenticated subject ownership before adding more large specialist modules.

Migrations 0013–0016 plus ADR-040/041 now define Project/Relationship ownership, project-scoped control-plane consistency, personal SecretReference ownership and per-Automation idempotency scope.

## Implemented in code

### Permanent Cockpit / UI architecture

- one `KairoCockpit` product entrypoint;
- one stable left navigation / central work surface / contextual rail / Command Dock structure;
- Home and KAIRO Brain share one canonical graph contract;
- 3D mycelium, 2D mind map and accessible list are renderers of the same projection;
- no separate Desktop frontend: Tauri reuses the same Web Cockpit;
- specialist workspaces consume canonical APIs or explicit sourced read models rather than maintaining parallel frontend domain state.

### Spatial graph

- bounded Home and neighborhood read models;
- canonical explicit Relationships and FK-derived structural edges with distinct provenance;
- search and deterministic natural-language focus/isolate directives;
- custom React Three Fiber / Three.js mycelium;
- deterministic Worker layout and pose continuity;
- instanced nodes, batched filaments, activity pulses, semantic LOD, adaptive quality and reduced motion;
- 2D mind-map projection using the same `KairoGraphProjection`;
- live SSE activity derived from canonical Outbox events.

### Human work / operational Cockpit

- Projects lifecycle and parent-cycle validation;
- Tasks with explicit priority/start/end/due planning facts;
- deterministic Today projection;
- Gantt from the same Task planning fields;
- weekly Calendar from KAIRO Task planning plus sourced external-event snapshots;
- Documents/Knowledge with Asset → Document → Version → Chunk provenance and latest-generation retrieval;
- capability Task separation in Agents;
- real ApprovalRequest review controls;
- MCP ToolServer/ToolDefinition policy workspace;
- KAIRO-owned Automation definitions/invocations with Activepieces as a replaceable webhook adapter;
- sourced Finance portfolio/read model, unsigned transaction proposals and a first read-only Rotki connector.

### Durable intelligence / execution

- deterministic-first Command Kernel;
- constrained semantic routing through PydanticAI;
- News Intelligence;
- durable autonomous Research and the stacked synthesis/handoff work in #36/#37;
- Mem0/Graphiti rebuildable memory projections;
- LiteLLM model gateway and canonical usage/budget accounting;
- Temporal durable execution and transactional-outbox/NATS event delivery.

### Desktop

- real Tauri v2 shell over the same Web application;
- bounded IPC capability introspection;
- clipboard read/write;
- local notifications with permission requested on use;
- fixed `CmdOrCtrl+Shift+Space` summon shortcut implemented in Rust;
- no generic shell execution, unrestricted filesystem permission or frontend shortcut-registration authority.

### Authentication

- Keycloak public-client Authorization Code + PKCE S256 initialization before React mounts;
- bearer-authenticated Core requests through one shared client path;
- token refresh kept in adapter memory rather than LocalStorage/IndexedDB;
- bearer-authenticated streamed fetch for Graph SSE;
- bearer-protected News audio fetched to a local object URL;
- fail-closed Core `/v1/*` authentication perimeter;
- explicit CORS origins for Web/Tauri;
- identity and logout controls in Settings.

## Ownership hardening added during this review

### Canonical root ownership

Migration `0013_canonical_project_relationship_ownership` adds `Project.keycloak_subject` and `RelationshipRecord.keycloak_subject`.

Current endpoint/read-model changes enforce the authenticated subject across:

- Project create/list/update/hierarchy;
- Task create/list/detail/run-path guard;
- Task planning and Today;
- Agents read model;
- Approval create/list/decision and Task budget reads;
- Asset upload into Project scopes;
- explicit Relationship creation;
- Graph Home/neighborhood/search;
- graph UI directives;
- Graph live activity SSE;
- Assistant Conversation/Message/Command reads and continuation;
- News tasks/results/audio;
- Research public runs and semantic-router owner preservation;
- public Memory projection inspection;
- Document creation/reingestion and owner-scoped Documents system workspace.

Foreign and absent user-world UUIDs intentionally collapse to the same 404 behavior on covered public APIs.

### Per-user system workspaces

Assistant, News, Documents and Memory no longer need a globally shared user-data Project. `ensure_system_project` creates stable per-subject system Projects and refuses to seize historical migration-owned `__kairo_system__` rows.

### Database-level consistency for project-scoped control-plane records

Migration `0014_project_scoped_control_plane_ownership` adds database ownership invariants for AutomationDefinition and FinanceConnector `(project_id, keycloak_subject)` bindings and a trigger for nullable Finance transaction-proposal Project bindings.

This prevents an endpoint bug from persisting a user-owned control-plane row attached to another user's Project even while the handler-level audit continues.

### Personal secret vault handles

A second concrete gap found during this review was `SecretReference`: the old API was global/admin-only. That prevented ordinary users from safely configuring their own Rotki/Activepieces integrations and would have exposed cross-user secret metadata if it were simply opened to `kairo-user`.

Migration `0015_secret_reference_ownership` and ADR-041 now establish:

- `SecretReference.keycloak_subject`;
- owner-scoped list/get/status/update/delete/provision routes;
- generated authenticated OpenBao paths under a KAIRO-managed subject namespace rather than caller-supplied paths;
- a bounded write-only value provisioning API whose response/audit/events expose key names/version, never secret values;
- same-owner composite SecretReference bindings for AutomationDefinition and FinanceConnector;
- normal `kairo-user` configuration of their own Automation/Finance connectors without granting global admin control.

The permanent Settings panel now includes a personal secret-vault surface. Secret values are held only in the form while being written and are cleared after successful provisioning.

### Automation idempotency tenant boundary

Migration `0016_automation_idempotency_scope` changes Automation invocation uniqueness from a deployment-global caller-controlled `idempotency_key` to `(automation_id, idempotency_key)`. The public invocation query uses the same scope.

This removes an unnecessary cross-tenant collision/oracle surface while preserving replay/idempotency semantics for one AutomationDefinition.

### Two-user validation fixtures

The local Keycloak realm contains two deterministic development identities:

- `kairo-dev` (user/admin);
- `kairo-alt` (user only).

Committed proofs use both identities against the same services:

- `scripts/smoke/multi_user_ownership.py` — Projects, Tasks, Planning/Today, Agents, Approvals/Budgets, Relationships and Graph isolation;
- `scripts/smoke/multi_user_conversation_ownership.py` — Task run guard, Assistant conversations/commands, News, Memory and Research project isolation;
- `scripts/smoke/multi_user_secret_ownership.py` — SecretReference list/read/write isolation, write-only OpenBao provisioning, Automation/Finance foreign binding rejection and per-Automation idempotency scope.

`Ownership isolation validation` now starts one Core/PostgreSQL/OpenBao/Keycloak stack and schedules all three proofs.

## Implemented but not yet proven on the current head

All of the following have proof/build code committed, but current hosted CI has not actually executed them because of issue #38:

- current Foundation substrate and ownership changes;
- migrations 0013–0016;
- Graph Interface build/integration jobs;
- all three two-user isolation proofs;
- personal OpenBao provisioning boundary;
- Desktop Rust/Tauri build;
- current Research synthesis/handoff stack;
- current MCP / Document / Automation / Finance controlled integration proofs.

The correct status is therefore **implemented, awaiting real-runner validation**, not “working in production”.

## Known incomplete or intentionally unavailable areas

### CI / mergeability evidence

- GitHub-hosted jobs are still failing before runner assignment under issue #38;
- the stacked #36 → #37 → #39 chain remains unmerged;
- current-head implementation must not be called validated until jobs actually execute.

### Ownership audit still open

The broadest ownership surfaces are now covered, but commercial multi-user readiness still requires a final endpoint/control-plane audit. One known example is the optional `FinanceTransactionProposal.project_id` handler path: PostgreSQL already prevents a persisted cross-owner binding through migration 0014, but the public handler still needs the same ideal owner-scoped 404 check rather than relying on the database as the last guard. Similar new/less-used control-plane routes must be reviewed before declaring the tenant audit closed.

Centrally managed MCP ToolServer/ToolDefinition records remain intentionally deployment-global/admin-controlled; that is valid only while they are treated as shared control-plane state rather than personal world entities.

### Provider integrations

- Google/Microsoft Calendar OAuth, polling and free/busy adapters are not yet implemented against the normalized Calendar snapshot boundary.
- Rotki has a controlled API-contract fixture and full KAIRO path, but still needs validation against a separately provisioned real Rotki release/version.
- Exchange/wallet Finance adapters beyond Rotki are not implemented.
- Activepieces is validated through a controlled webhook-contract fixture; a separately provisioned actual Activepieces flow remains to validate.

### Desktop / voice

- screenshot/capture bridge is not enabled;
- microphone/VAD/wake-word/transcription is not enabled;
- voice interaction and visible recording state are not complete;
- selected-directory/watched-folder access is not enabled;
- user-configurable native shortcut registration is intentionally not exposed yet.

### Finance signing

- transaction proposals are unsigned drafts only;
- isolated signer / hardware-wallet / explicit wallet handoff UX is not implemented;
- there is intentionally no agent-accessible sign/send/broadcast API.

### Brain/domain editing

- Brain exploration/filtering/focus is implemented;
- richer explicit relationship/domain editing and collaborative authoring still need audited canonical mutations rather than presentation-only graph moves.

### Developer / computer use

- browser/computer-use specialist capabilities are not yet part of the operational Cockpit;
- untrusted code/action execution isolation is not production-hardened.

### Memory semantics

- Mem0/Graphiti projections exist;
- generative Graphiti entity/fact extraction remains deliberately deferred until it can use KAIRO's accounted/replay-safe model boundary.

### Production operations

Still required before commercial multi-user deployment:

- close the remaining ownership audit and add regression proofs for newly covered endpoints;
- TLS/reverse proxy and private-network policy;
- least-privilege production OpenBao workload policy for the managed KAIRO user-secret prefix;
- untrusted execution isolation;
- real workload identities rather than development tokens;
- verified encrypted off-host recovery;
- provider-specific rate-limit/retry/credential lifecycle handling;
- real current-head CI evidence on supported OS/runtime combinations.

## Current implementation order

1. Finish the remaining ownership/control-plane audit without changing the Cockpit architecture.
2. Obtain real GitHub-hosted CI execution and fix only actual executed failures.
3. Validate the current Test Interface stack as one coherent baseline before adding another large module.
4. Connect real external providers to boundaries that already exist: Calendar, Rotki and Activepieces.
5. Continue Tauri with screenshot → microphone/voice as individually bounded native capabilities.
6. Add isolated signing handoff and Developer/computer-use capabilities only behind explicit policy/audit boundaries.

## Merge rule

PR #39 remains draft. The ownership and UI work must not be described as production-validated or merged simply because implementation is extensive. Real executed CI for the stacked chain remains the release gate.
