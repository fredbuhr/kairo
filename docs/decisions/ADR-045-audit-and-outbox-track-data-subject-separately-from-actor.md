# ADR-045 — Audit and Outbox track data subject separately from actor

Status: accepted

Date: 2026-09-09

## Context

KAIRO needs Audit and Outbox records for provenance, security, durable event delivery and replayable integration. Those streams are not ordinary user-domain tables:

- an Audit row has an **actor** who performed an action;
- the resource being audited may belong to a different authenticated user or may be shared deployment control-plane state;
- an Outbox event describes an aggregate which may be user-world state or shared/system state;
- account erasure needs to address evidence tied to one user's world without pretending all installation-wide audit traffic belongs to that user.

The original schema had `AuditRecord.actor_type/actor_id` and `OutboxEvent.aggregate_type/aggregate_id` but no explicit data-subject owner. Account lifecycle would therefore have needed to parse arbitrary payload/resource conventions repeatedly, and Graph SSE still had to load installation-wide Outbox rows before entity-level ownership filtering.

## Decision

Migration `0019_audit_outbox_data_subject` adds nullable indexed `keycloak_subject` fields to `audit_records` and `outbox_events`.

The field means **owner/data subject of the user-world resource**, not actor identity.

### Shared control-plane rows remain unowned

Deployment-scoped records such as ToolServer, ToolDefinition, capability metadata and system diagnostics remain `keycloak_subject = NULL` even when an authenticated administrator is the actor.

This distinction is intentional. Deleting an administrator's personal KAIRO world must not silently delete the installation's shared MCP policy history merely because that administrator changed it.

The administrator identity may still appear as `AuditRecord.actor_id`; account lifecycle counts those shared audit actor references separately because they require a retention/redaction decision rather than user-world cascade semantics.

### Central canonical owner resolver

`event_ownership.resolve_data_subject(...)` resolves the owner from canonical tables for known user-world resources:

- Project / Task / WorkflowExecution / Artifact;
- Relationship / Asset / Device / SecretReference;
- Conversation / ConversationMessage / Command;
- Approval / ModelUsage;
- Document / Version / Chunk;
- Calendar sources/events;
- Automation definitions/invocations;
- Finance source/account/position/proposal/connector;
- ToolInvocation.

`enqueue_domain_event(...)` and `append_audit(...)` call this resolver automatically unless an explicit owner was already supplied.

The resolver does not trust request payload fields as authority when canonical ownership can be queried.

### Direct transactional conversation event

ConversationMessage uses a synchronous SQLAlchemy `after_insert` listener so its memory-projection Outbox event is inserted in the same database transaction as the message. That path intentionally bypasses the async event helper.

The listener therefore resolves `Conversation.subject_ref` directly with the same database connection and writes it into `OutboxEvent.keycloak_subject` before inserting the event.

### Historical backfill

Migration 0019 builds a canonical owner map from existing tables and backfills Audit/Outbox rows whose resource/aggregate UUID can be resolved safely.

Shared/non-UUID/system records remain NULL rather than being guessed from an actor or arbitrary JSON payload.

### Graph activity uses ownership at the first query boundary

`GET /v1/graph/activity/stream` now queries only Outbox rows where `keycloak_subject == Principal.subject`.

`Last-Event-ID` cursor lookup uses the same owner predicate so a foreign event UUID cannot influence another user's stream cursor.

Entity-level graph ownership validation remains after this SQL filter as defense in depth. The Outbox owner and the actual graph entity must both agree.

### Account lifecycle inventory

`GET /v1/account/data-inventory` now reports a separate evidence section:

- subject-owned Audit rows;
- shared Audit rows that still reference the user as actor;
- subject-owned Outbox rows;
- unpublished subject-owned Outbox rows.

This is evidence inventory, not part of the canonical domain-row total.

`GET /v1/account/erasure/preflight` no longer claims Audit/Outbox are unaddressable. Instead it reports `audit_outbox_retention_policy_not_applied`: the rows can now be addressed by subject, but the final commercial delete/redact/retain behavior is deliberately not implemented yet.

## Retention rule still outstanding

Subject addressability does **not** itself authorize deletion.

Before KAIRO can claim complete account erasure, a separate retention policy/action must define at least:

- what happens to subject-owned Audit evidence;
- whether published Outbox rows are deleted, minimized or retained for a bounded period;
- how shared administrative Audit rows pseudonymize/redact `actor_id` when the actor's account is erased;
- whether any legally/financially required evidence has a distinct retention class;
- how restored backups reapply an erasure/tombstone so deleted personal data is not resurrected.

Until then, the account-erasure preflight remains blocked and `retention_action_available=false`.

## Validation

`scripts/smoke/evidence_subject_contract.py` is a fail-fast source/migration proof. It checks:

- schema fields/indexes;
- the central owner resolver and shared-control-plane classification;
- automatic Audit/Outbox owner resolution;
- the direct ConversationMessage listener owner binding;
- migration 0019 backfill structure;
- subject-first Graph SSE and Last-Event-ID queries;
- account lifecycle evidence accounting and the truthful retention blocker.

`scripts/smoke/multi_user_account_lifecycle.py` verifies at runtime that creating one Project and one Task for user A increments only A's subject-owned Audit/Outbox evidence counts while user B remains unchanged.

Both proofs are scheduled in the dedicated Ownership workflow. Current GitHub-hosted CI remains blocked before runner assignment by issue #38, so this contract is implemented but not yet current-head validated.

## Consequences

### Positive

- Audit actor identity and user-world data ownership are no longer conflated;
- account lifecycle can address evidence by subject without parsing arbitrary JSON;
- shared deployment policy history stays shared;
- live Graph activity begins with a subject-scoped SQL query instead of an installation-wide scan;
- foreign Outbox cursor IDs cannot influence another user's SSE stream;
- historical resolvable evidence gains ownership without guessing ambiguous records.

### Trade-offs

- the owner resolver adds one canonical ownership query when event/audit callers do not already supply the owner;
- nullable ownership remains necessary for shared/system evidence;
- shared Audit actor references still require a later redaction/retention action;
- adding new user-world aggregate types requires adding them to the central resolver and regression proof.

## Rejected alternatives

### Treat Audit actor_id as the data owner

Rejected because an administrator can act on shared control-plane state and workers/systems can act on user-owned resources.

### Infer ownership only during account deletion

Rejected because late parsing of arbitrary resource/payload conventions is fragile, slow and easy to omit.

### Mark every authenticated admin action as that admin's erasable data

Rejected because it would allow personal account deletion to erase shared installation control-plane history.

### Delete all Audit/Outbox evidence immediately once it is addressable

Rejected because retention is a separate policy decision and may include security, legal, financial or restore-consistency constraints.
