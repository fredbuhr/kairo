# KAIRO Block 3 implementation review — 2026-09-09

Status: implementation audit of the active stacked Test Interface v1 branch (`feat/kairo-test-interface-v1`, PR #39).

This review distinguishes **implemented in code** from **executed and validated on the current head**. GitHub Actions issue #38 is still preventing hosted jobs from receiving runners. A red workflow with no assigned runner / no executed steps is therefore not evidence that the code failed its tests, but it is also not evidence that the code passed. No stacked PR should merge until real runs execute #36 → #37 → #39 in order.

## Executive state

KAIRO is no longer primarily a backend prototype. The active branch contains the intended daily-use Test Interface architecture and most of the first operational Cockpit: spatial Home/Brain, Projects, Knowledge, Tasks/Today/Gantt, Calendar, Agents/Approvals, Automations, Tools, Finance/Crypto, the Assistant surface and an initial Tauri desktop boundary.

The dominant Block 3 risk is now **trust-boundary completion rather than missing UI**. Authentication existed before every user-world/read-model/control-plane path had explicit tenant semantics, so the current tranche is deliberately closing ownership, idempotency and connector-boundary gaps before adding more large specialist modules.

Migrations `0013`–`0017` plus ADR-040/041/042 now cover Project/Relationship ownership, project-scoped control-plane consistency, personal SecretReference ownership, Automation idempotency scope and ToolInvocation execution ownership.

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

Current endpoint/read-model changes enforce the authenticated subject across Project/Task planning, Agents/Approvals, Documents/Assets, Assistant/News/Research/Memory and Graph Home/neighborhood/search/directives/SSE. Foreign and absent user-world UUIDs intentionally collapse to the same 404 behavior on covered public APIs.

### Per-user system workspaces

Assistant, News, Documents and Memory use stable per-subject system Projects. `ensure_system_project` refuses to seize historical migration-owned `__kairo_system__` rows.

### Database-level consistency for project-scoped control-plane records

Migration `0014_project_scoped_control_plane_ownership` adds database ownership invariants for AutomationDefinition and FinanceConnector `(project_id, keycloak_subject)` bindings plus the nullable Finance transaction-proposal Project invariant.

The corresponding public Finance proposal handler is now also owner-scoped: an optional `project_id` must pass `require_owned_project(...)` before the draft is created. The API therefore returns the intended 404 for a foreign Project rather than depending on PostgreSQL as the final product-level guard.

### Personal secret vault handles

Migration `0015_secret_reference_ownership` and ADR-041 establish subject-owned SecretReferences, generated KAIRO-managed OpenBao paths, bounded write-only provisioning, same-owner Automation/Finance connector bindings and normal-user management of personal connector credentials without global admin rights.

The permanent Settings panel includes the personal `Connexions & secrets` surface. Secret values are held only while being submitted and are cleared after successful provisioning.

### Automation idempotency tenant boundary

Migration `0016_automation_idempotency_scope` changes Automation invocation uniqueness from a deployment-global caller-controlled `idempotency_key` to `(automation_id, idempotency_key)`.

### ToolInvocation execution ownership

A further audit pass found the same class of problem in MCP invocation history: ToolServer/ToolDefinition are intentionally shared control-plane records, but a ToolInvocation is user-world execution state tied to a Task → Project.

Migration `0017_tool_invocation_ownership` and ADR-042 now establish:

- `ToolInvocation.keycloak_subject` backfilled from Task → Project;
- fail-closed migration if an existing invocation has no derivable owner;
- subject-local `(keycloak_subject, idempotency_key)` uniqueness instead of a deployment-global caller namespace;
- owner-scoped public creation/replay lookup and detail reads;
- an internal Worker binding check requiring ToolInvocation owner == Task Project owner;
- Research child ToolInvocations deriving and preserving the parent Research Project owner;
- Research result inspection rejecting stale/cross-owner child invocation bindings.

A lightweight static contract proof, `scripts/smoke/tool_invocation_ownership_contract.py`, checks all current ToolInvocation constructors and the migration/model idempotency contract. A true two-user runtime proof for the shared-tool/same-idempotency scenario is still required once the hosted CI environment is executable.

### MCP admin UX boundary

The Tools workspace now respects the existing backend distinction between shared MCP control-plane policy and ordinary use. A normal `kairo-user` can inspect shared available contracts but is no longer presented with server registration or policy mutation controls that would only fail with an admin 403. Auth-disabled local development retains management controls.

The backend still returns the full ToolServer representation on the current shared registry read, including transport endpoint metadata. Whether ordinary users need that deployment-level detail remains an explicit control-plane disclosure item in the final audit; the Cockpit no longer displays the endpoint to non-admin usage paths.

### Two-user validation fixtures

The local Keycloak realm contains two deterministic development identities:

- `kairo-dev` (user/admin);
- `kairo-alt` (user only).

Committed runtime proofs use both identities against the same services for canonical Project/Task/Graph isolation, Assistant/News/Memory/Research isolation, and SecretReference/Automation/Finance connector isolation. The Ownership workflow also runs the ToolInvocation static ownership contract before starting the integration stack.

## Implemented but not yet proven on the current head

All of the following have proof/build code committed, but current hosted CI has not actually executed them because of issue #38:

- current Foundation substrate and ownership changes;
- migrations `0013`–`0017`;
- Graph Interface build/integration jobs;
- existing two-user isolation proofs;
- ToolInvocation static ownership contract on a hosted runner and a future two-user runtime ToolInvocation proof;
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

### Ownership/control-plane audit still open

The broad user-world ownership paths and two concrete idempotency namespaces are now covered, but commercial multi-user readiness still requires a final route-by-route classification:

- confirm every public object is either subject-owned, Project-root-owned or explicitly shared control-plane state;
- review shared operational endpoints such as global outbox/component status for the minimum information a normal user should receive;
- decide whether `/v1/tool-servers` should expose full deployment transport metadata to normal users or return a sanitized server summary;
- add a real two-user ToolInvocation idempotency/read-isolation proof;
- keep handler-level 404 behavior aligned with database constraints for every newly added Project-bound route.

Centrally managed MCP ToolServer/ToolDefinition records remain intentionally deployment-global/admin-controlled; that is valid only while they remain shared control-plane state rather than personal graph entities.

### Provider integrations

- Google/Microsoft Calendar OAuth, polling and free/busy adapters are not yet implemented against the normalized Calendar snapshot boundary;
- Rotki has a controlled API-contract fixture and full KAIRO path, but still needs validation against a separately provisioned real Rotki release/version;
- Exchange/wallet Finance adapters beyond Rotki are not implemented;
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

- close the remaining ownership/control-plane disclosure audit and add regression proofs;
- TLS/reverse proxy and private-network policy;
- least-privilege production OpenBao workload policy for the managed KAIRO user-secret prefix;
- untrusted execution isolation;
- real workload identities rather than development tokens;
- verified encrypted off-host recovery;
- provider-specific rate-limit/retry/credential lifecycle handling;
- real current-head CI evidence on supported OS/runtime combinations.

## Current implementation order

1. Finish the remaining ownership/control-plane disclosure audit without changing the Cockpit architecture.
2. Obtain real GitHub-hosted CI execution and fix only actual executed failures.
3. Validate the current Test Interface stack as one coherent baseline before adding another large module.
4. Connect real external providers to boundaries that already exist: Calendar, Rotki and Activepieces.
5. Continue Tauri with screenshot → microphone/voice as individually bounded native capabilities.
6. Add isolated signing handoff and Developer/computer-use capabilities only behind explicit policy/audit boundaries.

## Merge rule

PR #39 remains draft. The ownership and UI work must not be described as production-validated or merged simply because implementation is extensive. Real executed CI for the stacked chain remains the release gate.
