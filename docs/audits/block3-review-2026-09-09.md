# KAIRO Block 3 implementation review — 2026-09-09

Status: implementation audit of the active stacked Test Interface v1 branch (`feat/kairo-test-interface-v1`, PR #39).

This review distinguishes **implemented in code** from **executed and validated on the current head**. GitHub Actions issue #38 is still preventing hosted jobs from receiving runners. A red workflow with no assigned runner / no executed steps is therefore not evidence that the code failed its tests, but it is also not evidence that the code passed. No stacked PR should merge until real runs execute #36 → #37 → #39 in order.

## Executive state

KAIRO is no longer primarily a backend prototype. The active branch contains the intended daily-use Test Interface architecture and most of the first operational Cockpit: spatial Home/Brain, Projects, Knowledge, Tasks/Today/Gantt, Calendar, Agents/Approvals, Automations, Tools, Finance/Crypto, the Assistant surface and an initial Tauri desktop boundary.

The dominant Block 3 risk is now **trust-boundary completion rather than missing UI**. Authentication existed before every user-world/read-model/control-plane path had explicit tenant semantics, so the current tranche is deliberately closing ownership, idempotency, disclosure and secret-retention gaps before adding more large specialist modules.

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

## Ownership and control-plane hardening added during this review

### Canonical root ownership

Migration `0013_canonical_project_relationship_ownership` adds `Project.keycloak_subject` and `RelationshipRecord.keycloak_subject`.

Current endpoint/read-model changes enforce the authenticated subject across Project/Task planning, Agents/Approvals, Documents/Assets, Assistant/News/Research/Memory and Graph Home/neighborhood/search/directives/SSE. Foreign and absent user-world UUIDs intentionally collapse to the same 404 behavior on covered public APIs.

### Per-user system workspaces

Assistant, News, Documents and Memory use stable per-subject system Projects. `ensure_system_project` refuses to seize historical migration-owned `__kairo_system__` rows.

### Database-level consistency for project-scoped control-plane records

Migration `0014_project_scoped_control_plane_ownership` adds database ownership invariants for AutomationDefinition and FinanceConnector `(project_id, keycloak_subject)` bindings plus the nullable Finance transaction-proposal Project invariant.

The public Finance proposal handler is now also owner-scoped: an optional `project_id` must pass `require_owned_project(...)` before the draft is created. The API therefore returns the intended 404 for a foreign Project rather than depending on PostgreSQL as the final product-level guard.

### Personal secret vault handles, disclosure and retention

Migration `0015_secret_reference_ownership` and ADR-041 establish subject-owned SecretReferences, generated KAIRO-managed OpenBao paths, bounded write-only provisioning, same-owner Automation/Finance connector bindings and normal-user management of personal connector credentials without global admin rights.

The public `SecretReferenceRead` contract no longer exposes `provider_path`. Browser surfaces receive the logical handle (`id`, name, purpose, timestamps) and status metadata only; the managed OpenBao namespace stays inside Core. Finance/Automation selectors use the logical name/purpose rather than vault topology.

The retention boundary is explicit:

- `DELETE /v1/secret-references/{id}/values` is the deliberate irreversible KV-v2 destruction action;
- it removes OpenBao metadata/all versions and records only previous key names/version/existence;
- another subject receives 404 and cannot revoke the credential;
- credential destruction is allowed even while a connector references the handle so a user can revoke access immediately;
- deleting the PostgreSQL SecretReference is refused while Automation/Finance records still use it;
- deleting the PostgreSQL SecretReference is also refused while OpenBao still reports values;
- if OpenBao is unavailable, Core refuses metadata deletion because it cannot prove provider material is absent.

The permanent Settings `Connexions & secrets` surface exposes value destruction and reference deletion as separate confirmed actions. It never offers secret-value readback.

The two-user SecretReference proof now checks vault-path non-disclosure and includes a dedicated unused credential lifecycle: provision → foreign-destruction refusal → reference-delete refusal while populated → explicit value destruction → empty status → reference deletion.

### Automation idempotency tenant boundary

Migration `0016_automation_idempotency_scope` changes Automation invocation uniqueness from a deployment-global caller-controlled `idempotency_key` to `(automation_id, idempotency_key)`.

### ToolInvocation execution ownership

Migration `0017_tool_invocation_ownership` and ADR-042 establish that ToolServer/ToolDefinition are shared control-plane state while ToolInvocation is user-world execution state:

- `ToolInvocation.keycloak_subject` is backfilled from Task → Project;
- migration fails closed if an owner cannot be derived;
- idempotency uniqueness is `(keycloak_subject, idempotency_key)`, not global;
- a PostgreSQL trigger rejects ToolInvocation ↔ Task bindings whose Project owner differs;
- public creation/replay/detail reads are owner scoped;
- Worker execution verifies ToolInvocation owner == Task Project owner;
- Research child ToolInvocations derive/preserve the parent Research Project owner;
- Research evidence lookup rejects stale/cross-owner child bindings.

Two complementary proofs are committed:

- `tool_invocation_ownership_contract.py` checks current constructors, migration uniqueness and DB trigger statically;
- `multi_user_tool_invocation_ownership.py` creates one shared read-only MCP contract and verifies two real Keycloak subjects can reuse the same caller idempotency key without collision, same-subject replay remains stable, changed-input rebinding fails and foreign invocation IDs return 404.

These are proof **implementations**; current hosted CI has not executed them yet because of issue #38.

### MCP shared control-plane disclosure

ToolServer/ToolDefinition remain intentionally deployment-global/admin-managed, but ordinary users no longer receive the full deployment transport record from `GET /v1/tool-servers`. The user-facing response is a sanitized summary containing logical identity, namespace, transport kind, enabled state and catalog generation while omitting `endpoint_url` and arbitrary `metadata_json`.

The MCP management smoke proof checks that split explicitly: admin creation returns the full record, while the shared registry list omits endpoint/metadata details.

The Tools Cockpit follows the same boundary. Ordinary `kairo-user` sessions may inspect shared contracts and current authorization state but are no longer shown server-registration or policy-mutation controls that would only fail with 403. Auth-disabled development and `kairo-admin` sessions retain management controls.

### Deployment diagnostics are admin-only

The route review found installation-wide diagnostics that were authenticated but still visible to every `kairo-user`:

- `/v1/system/components`;
- `/v1/system/architecture`;
- `/v1/system/outbox`.

They now require `kairo-admin` explicitly. `control_plane_visibility.py` uses the two development identities to require admin 200 / normal-user 403 on all three. Health/readiness remain orchestrator probes.

### Two-user validation fixtures

The local Keycloak realm contains two deterministic development identities:

- `kairo-dev` (user/admin);
- `kairo-alt` (user only).

The dedicated Ownership workflow now compiles and schedules runtime proofs for canonical Project/Task/Graph isolation, Assistant/News/Memory/Research isolation, SecretReference/Automation/Finance connector isolation+retention, ToolInvocation two-user idempotency/read isolation and deployment-diagnostic visibility. It also runs the ToolInvocation source/migration contract before starting the integration stack.

## Implemented but not yet proven on the current head

All of the following have proof/build code committed, but current hosted CI has not actually executed them because of issue #38:

- current Foundation substrate and ownership changes;
- migrations `0013`–`0017`;
- Graph Interface build/integration jobs;
- all current two-user ownership proofs;
- explicit OpenBao value destruction/reference-retention proof;
- admin-only deployment diagnostics proof;
- ToolInvocation source/migration and two-user runtime proofs;
- sanitized MCP shared registry response;
- Desktop Rust/Tauri build;
- current Research synthesis/handoff stack;
- current MCP / Document / Automation / Finance controlled integration proofs.

The correct status is therefore **implemented, awaiting real-runner validation**, not “working in production”.

## Known incomplete or intentionally unavailable areas

### CI / mergeability evidence

- GitHub-hosted jobs are still failing before runner assignment under issue #38;
- the stacked #36 → #37 → #39 chain remains unmerged;
- current-head implementation must not be called validated until jobs actually execute.

### Final ownership / data-lifecycle audit

The broad user-world ownership paths, personal connector secrets/retention, shared MCP disclosure, deployment diagnostics and caller-controlled idempotency namespaces are now covered. The final commercial multi-user audit is narrower:

- finish route-by-route classification of every remaining public object as subject-owned, Project-root-owned or intentionally shared control-plane state;
- keep handler-level 404 behavior aligned with database constraints for future Project-bound routes;
- confirm the production OpenBao workload policy grants only the KAIRO-managed data/metadata operations required by provisioning/status/destruction;
- define account export/deletion retention across PostgreSQL, SeaweedFS, OpenBao and rebuildable projections rather than treating per-secret deletion as the whole user-data lifecycle.

Centrally managed MCP ToolServer/ToolDefinition records remain intentionally deployment-global/admin-controlled; they must remain shared control-plane state unless a future personal-MCP ownership model is explicitly introduced.

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

- close the remaining route/data-lifecycle audit and add regression proofs;
- TLS/reverse proxy and private-network policy;
- least-privilege production OpenBao workload policy;
- untrusted execution isolation;
- real workload identities rather than development tokens;
- verified encrypted off-host recovery;
- provider-specific rate-limit/retry/credential lifecycle handling;
- real current-head CI evidence on supported OS/runtime combinations.

## Current implementation order

1. Finish the remaining route/data-lifecycle audit without changing the Cockpit architecture.
2. Obtain real GitHub-hosted CI execution and fix only actual executed failures.
3. Validate the current Test Interface stack as one coherent baseline before adding another large module.
4. Connect real external providers to boundaries that already exist: Calendar, Rotki and Activepieces.
5. Continue Tauri with screenshot → microphone/voice as individually bounded native capabilities.
6. Add isolated signing handoff and Developer/computer-use capabilities only behind explicit policy/audit boundaries.

## Merge rule

PR #39 remains draft. The ownership and UI work must not be described as production-validated or merged simply because implementation is extensive. Real executed CI for the stacked chain remains the release gate.
