# ADR-044 — Account erasure is a cross-store state machine

Status: accepted

Date: 2026-09-09

## Context

KAIRO now has explicit authenticated subject ownership across most user-world state, but a commercial account lifecycle cannot be reduced to `DELETE FROM projects`.

One user may have material spread across several trust/storage boundaries:

- canonical PostgreSQL state;
- SeaweedFS Asset objects;
- OpenBao connector secret values;
- Mem0 and Graphiti/Neo4j rebuildable projections;
- Keycloak identity state;
- Audit/Outbox evidence and JetStream transport copies;
- encrypted historical backups.

Some stores are canonical, some rebuildable, some external identity/security systems and some intentionally have retention semantics. Claiming “account deleted” after removing only PostgreSQL rows would therefore be false.

The same problem affects export: secret values must not be pulled back through the browser merely because the user requested an export, and shared deployment/control-plane state must not be mixed into a personal bundle.

## Decision

Account lifecycle is an explicit cross-store contract. The current implementation contains **inventory + export manifest + erasure preflight + derived-memory purge + Audit/Outbox evidence retention**. It still does **not** expose destructive full-account deletion.

### Subject-scoped inventory

`GET /v1/account/data-inventory` returns only aggregate facts for the authenticated subject:

- counts for canonical subject-owned/Project-root-owned records;
- tracked SeaweedFS Asset object count and bytes;
- count of canonical memory projection-ledger rows;
- latest canonical conversation-message time and latest completed memory-purge cutoff;
- subject-owned and shared-actor Audit/Outbox evidence counts;
- explicit declarations for data behind derived/shared/external retention boundaries.

The read model intentionally does not return the Keycloak subject identifier, OpenBao provider paths, secret values or deployment MCP endpoint topology.

The inventory follows the canonical ownership rules already defined in ADR-040 through ADR-043 and the evidence ownership rule in ADR-045. It never sends another subject's rows to the browser for client-side filtering.

### Export manifest before export bundle

`GET /v1/account/export/manifest` is versioned as `kairo.account-export-manifest.v1`.

The first implementation is deliberately `manifest_only` and advertises `bundle_export_available=false`. This prevents the UI from implying that a complete portable export exists before every domain has a stable bounded serializer.

The manifest states what a future bundle may contain and what is deliberately excluded. In particular:

- OpenBao secret **values are never exported**;
- Mem0/Graphiti payloads are derived and rebuilt from canonical content rather than treated as authoritative export state;
- shared MCP registry transport details are deployment state, not personal data;
- raw Audit/Outbox evidence is not exported by the current manifest; the retention path minimizes/removes it instead;
- Keycloak credentials/tokens are outside the KAIRO canonical export boundary.

### Erasure preflight

`GET /v1/account/erasure/preflight` reports blockers in two scopes:

- `canonical`: conditions that make even KAIRO canonical deletion unsafe right now;
- `complete`: conditions that prevent KAIRO from truthfully claiming full cross-store erasure.

Canonical blockers include non-terminal Tasks, WorkflowExecutions, approvals, AutomationInvocations and ToolInvocations. Deleting canonical records while an external/durable action is still running could orphan a side effect or destroy the only reconciliation state.

Complete-erasure blockers include, when applicable:

- remaining SecretReferences/credential material requiring explicit revocation;
- stale/not-yet-run Mem0/Graphiti purge relative to the latest canonical message;
- remaining Audit/Outbox evidence requiring the ADR-047 retention action;
- Keycloak identity deletion not yet implemented through KAIRO;
- backup expiry/restore-after-erasure semantics not yet formally verified.

`audit_outbox_retention_required` is now a user-resolvable blocker. It disappears only when the subject-owned Audit/Outbox evidence and shared Audit actor references counted by account lifecycle have been removed/minimized/redacted by the explicit retention action.

The response still advertises `destructive_endpoint_available=false` because evidence retention does not solve Keycloak identity, backup/tombstone, SeaweedFS/canonical deletion ordering or an account freeze. This is intentional product truthfulness, not a missing button.

### Derived-memory purge

`POST /v1/account/derived-memory/purge` creates/reuses a canonical `memory.purge` Task in the owner-scoped KAIRO Memory system Project and executes it through the normal Temporal Worker.

The Task captures a `purge_cutoff_at` equal to the latest canonical conversation-message timestamp at request time. The preflight considers the derived purge current only when:

- no canonical conversation message exists; or
- a completed purge cutoff is at least as new as the latest canonical message **and** the canonical MemoryProjectionRecord ledger has no remaining rows for the subject.

This makes races conservative. A new message after a purge request makes the purge stale even if an external delete happened to catch it; KAIRO asks for another purge rather than overstating deletion.

The Worker boundary is deliberately idempotent/retryable:

- Mem0 deletes by the KAIRO owner scope and verifies it is empty;
- current Graphiti projection deletes every owned `conversation:<id>` group and verifies none remain;
- only after both projector operations report verified success does Core delete the subject's MemoryProjectionRecord ledger rows;
- the ordinary Task completion Artifact remains the durable execution receipt.

KAIRO currently has Graphiti generative entity/fact extraction disabled. Enabling it in the future is forbidden until this purge boundary is widened to remove generated entity/community/edge material for the same owner groups.

`stub` projector mode cannot clear evidence of a real projection. Core marks a subject as requiring real projector cleanup when current projection metadata names a non-stub backend; both Worker and Core then refuse a stub purge.

The user-facing Settings action explicitly states that canonical Conversations/Messages are preserved. Purging derived memory is therefore reversible in the architectural sense: canonical state can later re-seed Mem0/Graphiti through the existing rebuild pipeline.

### Audit / Outbox evidence retention

ADR-045 gives user-world Audit/Outbox rows a data-subject identity distinct from actor identity. ADR-046 bounds JetStream retention and records exact publication receipts. ADR-047 now implements the cross-store evidence-retention primitive.

`GET /v1/account/evidence/retention` exposes only aggregate readiness/count facts for the authenticated subject. `POST /v1/account/evidence/retention/apply` requires explicit typed confirmation.

The operation is ordered:

1. active/reconciling work must be terminal;
2. subject Outbox must have no unpublished or malformed receipt rows;
3. exact JetStream receipt messages are deleted, or historical unreceipted messages must have aged beyond verified max-age plus safety grace;
4. only then are reconciled PostgreSQL Outbox rows removed;
5. after the subject Outbox is empty, subject Audit rows are minimized and shared administrative actor references are redacted;
6. one deployment-neutral aggregate receipt is retained without a subject identifier/hash.

It is batched and retryable. It does not freeze the account. Any later KAIRO activity creates fresh evidence and the preflight becomes blocked again. A future destructive state machine must therefore freeze/disable the identity before its final retention pass.

### SeaweedFS

Asset ownership is first-class after ADR-043, so object inventory is deterministic. A future destructive state machine must remove each tracked SeaweedFS object and only then remove/commit canonical metadata according to a replay-safe deletion ledger. A plain database cascade is insufficient.

### OpenBao

ADR-041 remains authoritative: values are write-only to the browser and destruction is a separate explicit action. Account erasure may orchestrate those existing destruction primitives later, but must never first read secret values into canonical state.

### Keycloak and backups

Keycloak identity and historical backups remain independent blockers.

A complete destructive flow needs an identity freeze/disable/delete contract so new authenticated writes cannot race the final cross-store cleanup. Backup semantics must guarantee that restoring a snapshot cannot resurrect an erased subject without reapplying a durable erasure tombstone/ledger.

Until these contracts exist and are validated, `complete_erasure_ready` cannot truthfully become true solely because canonical rows, secrets, projections and current evidence have been cleaned.

## Validation

`scripts/smoke/multi_user_account_lifecycle.py` uses two real Keycloak identities against one Core/PostgreSQL instance. It verifies that:

- creating Project/Task state for user A changes only A's inventory;
- user B's inventory remains unchanged;
- A's active-work erasure blocker changes without affecting B;
- export manifests mirror only their own inventory;
- the public lifecycle payload does not expose the username/subject or `provider_path`;
- Audit/Outbox retention is advertised as an explicit user-resolvable blocker rather than an unimplemented policy;
- no destructive full-account endpoint is advertised while other cross-store contracts remain incomplete.

`scripts/smoke/evidence_retention_contract.py` checks the static retention invariants introduced by ADR-047.

`scripts/smoke/memory_projection.py` extends the durable projection/rebuild proof with a `memory.purge` execution in deterministic stub mode. It verifies that projection ledger rows disappear, `purge_current` becomes true and the canonical Conversation/Message is unchanged through the public read model.

`scripts/smoke/memory_purge_provider_contract.py` imports the pinned Mem0/Graphiti APIs and fails fast if the required subject/group delete and verification signatures drift.

These proofs are committed to the relevant workflows. Current GitHub-hosted CI still fails before runner allocation under issue #38, so the contracts are implemented but not yet current-head validated.

## Consequences

### Positive

- KAIRO no longer conflates account deletion with deleting one SQL root row;
- the product can show users what data it currently knows it holds without leaking another tenant;
- future export has a stable versioned contract instead of ad hoc table dumps;
- secret values remain outside export/readback paths;
- Mem0/Graphiti have an explicit durable owner-scoped purge path without deleting canonical conversation history;
- Audit/Outbox now have an explicit transport-first retention action rather than only addressability;
- destructive account deletion remains blocked until the remaining identity/storage/recovery boundaries are real.

### Trade-offs

- there is intentionally no one-click account erasure yet;
- complete export remains a later bundle/streaming implementation;
- the inventory performs multiple owner-scoped count queries and should eventually be optimized/cached for very large accounts;
- the Graphiti purge contract is valid only while generative extraction remains disabled;
- evidence retention may need to be repeated if new activity occurs before a future account freeze;
- Keycloak identity lifecycle and backup/tombstone semantics still need explicit contracts.

## Rejected alternatives

### Cascade-delete all Projects

Rejected because Conversations, Secrets, Devices, external sourced records, SeaweedFS objects, projections and identity state do not all reduce to the Project root.

### Delete PostgreSQL first and clean external stores later

Rejected because failure after the canonical delete would destroy the reconciliation ledger and could leave orphaned data with no trustworthy retry path.

### Clear the memory ledger without deleting Mem0/Graphiti

Rejected because the ledger is deletion evidence/reconciliation state, not the derived data itself. Core deletes it only after projector deletion has been verified.

### Allow stub purge after prior real projection

Rejected because runtime configuration must not weaken retention guarantees.

### Export everything including OpenBao values

Rejected because a portability request must not turn KAIRO into a secret-exfiltration/readback API.

### Claim complete erasure after evidence cleanup alone

Rejected because Keycloak identity, SeaweedFS/canonical destruction ordering and restore-after-erasure semantics are independent parts of the real lifecycle.
