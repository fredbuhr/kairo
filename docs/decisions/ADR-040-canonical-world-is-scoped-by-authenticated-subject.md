# ADR-040 — The canonical KAIRO world is scoped by authenticated subject

Status: accepted

Date: 2026-09-09

## Context

Keycloak authentication alone does not provide tenant isolation. A bearer token can prove who the caller is while a query such as `SELECT * FROM projects` can still expose every authenticated user's data.

KAIRO Test Interface v1 compounds that risk because the same canonical world is projected through many surfaces: Projects, Tasks, Today, Gantt, Agents, Approvals, Documents, Assistant conversations, the spatial Graph, search, natural-language focus directives and live activity pulses. Fixing only one REST list endpoint would leave alternate disclosure paths.

KAIRO also creates durable internal work for News, Assistant routing, Documents and Memory. A single shared system Project cannot be used as the ownership root for those user-specific Tasks because it would make their derived workflows visible as one global tenant.

## Decision

The authenticated Keycloak subject is the user-world ownership boundary.

### Project is the canonical root for project-scoped work

`Project.keycloak_subject` is the root owner for:

- Tasks;
- WorkflowExecutions through Task;
- Artifacts through Project/Task;
- project-scoped Documents and Assets;
- specialist work derived from those canonical objects.

Public reads and mutations join or validate this Project root before returning or changing data.

A supplied foreign UUID is treated like an absent UUID and returns `404`. Public APIs must not become cross-tenant existence oracles.

### Explicit polymorphic relationships carry ownership directly

`RelationshipRecord` is polymorphic and cannot infer one safe owner through a fixed foreign key. It therefore stores `keycloak_subject` directly.

Creating a relationship requires both endpoint entities to belong to the authenticated subject. Graph relationship reads also filter by that subject.

### Directly owned canonical entities retain their explicit owner

Some entities have a natural direct owner:

- `Conversation.subject_ref`;
- Document/Asset owner metadata in the current schema;
- Calendar/Finance/Automation source records with their owner subject columns;
- `SecretReference.keycloak_subject` for personal OpenBao handles.

Their public APIs must use those direct bindings and, when they also point at a Project or another owned control-plane object, keep the owner aligned.

`SecretReference` has an additional write-only vault rule described in ADR-041: authenticated clients receive a KAIRO-generated OpenBao path, cannot select arbitrary deployment paths, and never receive secret values back through the public API. AutomationDefinition and FinanceConnector use composite same-owner constraints when binding those references.

### System workspaces are per-user, not globally shared

User-specific capability workspaces such as:

- KAIRO Assistant;
- KAIRO News;
- KAIRO Documents;
- KAIRO Memory;

use deterministic per-subject Project IDs. Historical development/system Project IDs may remain reserved for migrations, but `ensure_system_project` must never seize a row owned by another subject or by `__kairo_system__`.

This gives durable system Tasks the same Project-root ownership semantics as ordinary user work while preserving deterministic replay.

### Every Cockpit projection shares the same boundary

The ownership rule applies to:

- Project/Task lists and detail reads;
- Project hierarchy mutations;
- Task planning and Today;
- Agents and approvals;
- Task budgets;
- Documents and Assets;
- Assistant conversations/messages/commands;
- News and Research public runs;
- SecretReference metadata/status/provisioning;
- Automation and Finance connector configuration;
- Graph Home, neighborhood and search;
- typed natural-language graph directives;
- graph SSE activity and related-entity pulses.

The graph is not permitted to become a side channel around the underlying domain APIs.

### Defense in depth for canonical project/task/control-plane bindings

Core's public `/v1/*` bearer perimeter additionally checks UUID-shaped `/v1/projects/{id}/...` and `/v1/tasks/{id}/...` paths against the authenticated owner. This protects newly introduced subroutes from accidentally bypassing ownership if a handler forgets its local check.

PostgreSQL also carries same-owner constraints for project-scoped Automation/Finance configuration and personal SecretReference bindings. These database invariants do not replace endpoint-level SQL scoping; they are final guards against future handler regressions.

### Internal execution remains a separate trust boundary

`/internal/v1/*` routes remain authenticated by the KAIRO internal token and may operate on a durable Task/Workflow/connector identity across subjects. They do not accept a browser bearer token as a substitute and must validate their canonical binding before an external side effect.

### Shared control-plane records are not user-world records

Some registries are intentionally deployment/control-plane state rather than personal world data, for example capability contracts and centrally managed MCP ToolServer/ToolDefinition metadata. Their authorization model may remain administrative/global when explicitly documented. They must not be silently mixed into a user's canonical graph as if they were owned personal entities.

## Migration

Migration `0013_canonical_project_relationship_ownership` adds non-null ownership columns and indexes to canonical Projects and explicit Relationships.

Migration `0014_project_scoped_control_plane_ownership` adds database-level same-owner Project constraints for AutomationDefinition and FinanceConnector and a guard for nullable Finance transaction-proposal Project bindings.

Migration `0015_secret_reference_ownership` assigns SecretReferences to a subject and adds same-owner Automation/Finance secret bindings. It refuses migration if a legacy SecretReference is already shared by multiple authenticated subjects rather than guessing which tenant should own it.

Migration `0016_automation_idempotency_scope` scopes caller-selected Automation invocation idempotency to one AutomationDefinition instead of creating a deployment-global user-controlled namespace.

Historical rows are assigned to the isolated development subject where ownership can be determined safely, with known migration/system workspaces reserved as `__kairo_system__`. New authenticated user data is never attached to those shared system rows.

## Validation

Two real Keycloak identities are required in the development realm for isolation proofs.

`multi_user_ownership.py` proves isolation for Projects, Tasks, Planning/Today, Agents, Approvals/Budgets, Relationships and Graph search/navigation.

`multi_user_conversation_ownership.py` proves isolation for Assistant conversations/commands, News results, Memory projection inspection, Research project binding and the generic Task run subroute.

`multi_user_secret_ownership.py` proves personal SecretReference list/read/write isolation, write-only OpenBao provisioning, foreign Project/Secret rejection for Automations and Finance connectors, and per-Automation idempotency scope across two tenants.

These tests intentionally use one Core, one PostgreSQL database and — for the secret proof — one OpenBao instance. Passing only single-user tests is insufficient evidence for this ADR.

## Consequences

### Positive

- An authenticated user sees one KAIRO world rather than a globally shared database.
- Mycelium nodes, labels and activity pulses cannot reveal another user's project/task identity through the Graph API.
- Personal connector metadata and vault handles are no longer deployment-global user-visible state.
- System capability work can still use deterministic Temporal/Task identities without sharing a Project owner.
- Foreign UUID probing does not reveal whether an entity exists on covered user-world APIs.
- Future specialist workspaces have a clear ownership rule to follow.

### Trade-offs

- More queries join Project or filter direct owner columns to enforce ownership.
- Legacy local fixtures may require per-user system-workspace migration on first mutation/reingestion.
- Shared/team Projects are not implemented by this ADR; they require an explicit membership/ACL model rather than weakening subject ownership.
- Administrative deployment-control-plane access remains a distinct concern from user-world ownership.
- Ownership still requires endpoint-by-endpoint review as new modules appear; database constraints are defense in depth, not a substitute for that review.

## Rejected alternatives

### Authentication without query scoping

Rejected because it protects the door but not the data once the caller is inside.

### Frontend filtering

Rejected because the browser must never receive another user's canonical data in the first place.

### One global KAIRO Assistant/News/Documents/Memory Project

Rejected because all user-specific durable Tasks would inherit one shared Project owner.

### Returning 403 for known foreign objects

Rejected for ordinary user-world APIs because it confirms object existence. Foreign and absent user objects both return 404.
