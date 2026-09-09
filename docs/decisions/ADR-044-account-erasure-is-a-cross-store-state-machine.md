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
- shared audit/outbox evidence;
- encrypted historical backups.

Some of those stores are canonical, some are rebuildable, some are external identity/security systems and some intentionally have shared retention semantics. Claiming “account deleted” after removing only PostgreSQL rows would therefore be false.

The same problem affects export: secret values must not be pulled back through the browser merely because the user requested an export, and shared deployment/control-plane state must not be mixed into a personal bundle.

## Decision

Account lifecycle is implemented as an explicit cross-store contract. The first slice is **inventory + export manifest + erasure preflight**, not destructive deletion.

### Subject-scoped inventory

`GET /v1/account/data-inventory` returns only aggregate facts for the authenticated subject:

- counts for canonical subject-owned/Project-root-owned records;
- tracked SeaweedFS Asset object count and bytes;
- count of canonical memory projection-ledger rows;
- explicit declarations for data that sits behind derived/shared/external retention boundaries.

The read model intentionally does not return the Keycloak subject identifier, OpenBao provider paths, secret values or deployment MCP endpoint topology.

The inventory follows the canonical ownership rules already defined in ADR-040 through ADR-043. It never scans another subject's rows and filters them in the browser.

### Export manifest before export bundle

`GET /v1/account/export/manifest` is versioned as `kairo.account-export-manifest.v1`.

The first implementation is deliberately `manifest_only` and advertises `bundle_export_available=false`. This prevents the UI from implying that a complete portable export exists before every domain has a stable bounded serializer.

The manifest states what a future bundle may contain and what is deliberately excluded. In particular:

- OpenBao secret **values are never exported**;
- Mem0/Graphiti payloads are derived and should be rebuilt from canonical content rather than treated as authoritative export state;
- shared MCP registry transport details are deployment state, not personal data;
- shared audit/outbox streams require their own retention/redaction policy;
- Keycloak credentials/tokens are outside the KAIRO canonical export boundary.

### Erasure preflight

`GET /v1/account/erasure/preflight` reports blockers in two scopes:

- `canonical`: conditions that make even KAIRO canonical deletion unsafe right now;
- `complete`: conditions that prevent KAIRO from truthfully claiming full cross-store erasure.

Canonical blockers currently include non-terminal Tasks, WorkflowExecutions, approvals, AutomationInvocations and ToolInvocations. Deleting canonical records while an external/durable action is still running could orphan a side effect or destroy the only reconciliation state.

Complete-erasure blockers currently include:

- remaining SecretReferences/credential material requiring explicit revocation;
- subject-wide Mem0/Graphiti purge not yet implemented;
- audit/outbox retention not yet fully subject-addressable;
- Keycloak identity deletion not yet implemented through KAIRO;
- backup expiry/restore-after-erasure semantics not yet formally verified.

The response always advertises `destructive_endpoint_available=false` until those boundaries are implemented and validated. This is intentional product truthfulness, not a missing button.

### SeaweedFS

Asset ownership is first-class after ADR-043, so object inventory is deterministic. A future destructive state machine must remove each tracked SeaweedFS object and only then remove/commit canonical metadata according to a replay-safe deletion ledger. A plain database cascade is insufficient.

### OpenBao

ADR-041 remains authoritative: values are write-only to the browser and destruction is a separate explicit action. Account erasure may orchestrate those existing destruction primitives later, but must never first read secret values into canonical state.

### Derived projections

Mem0 and Graphiti remain rebuildable. Complete erasure requires projector-specific subject purge adapters with idempotent evidence. Until those exist, the preflight remains blocked even if PostgreSQL canonical rows could otherwise be removed.

### Audit, outbox and backups

Audit/outbox and backup policy are not silently treated as ordinary user tables. Commercial retention requirements may require bounded retention, pseudonymization or delayed expiry instead of immediate destructive deletion. That policy must be explicit before `complete_erasure_ready` can ever become true.

## Validation

`scripts/smoke/multi_user_account_lifecycle.py` uses two real Keycloak identities against one Core/PostgreSQL instance. It verifies that:

- creating Project/Task state for user A changes only A's inventory;
- user B's inventory remains unchanged;
- A's active-work erasure blocker changes without affecting B;
- export manifests mirror only their own inventory;
- the public lifecycle payload does not expose the username/subject or `provider_path`;
- no destructive endpoint is advertised and complete erasure remains blocked while cross-store contracts are incomplete.

The proof is committed to the dedicated Ownership workflow. Current GitHub-hosted CI still fails before runner allocation under issue #38, so the contract is implemented but not yet current-head validated.

## Consequences

### Positive

- KAIRO no longer conflates account deletion with deleting one SQL root row;
- the product can show users what data it currently knows it holds without leaking another tenant;
- future export has a stable versioned contract instead of ad hoc table dumps;
- secret values remain outside export/readback paths;
- destructive deletion cannot be exposed before durable/external work and projection retention are safe;
- backup/audit/identity retention gaps are visible instead of hidden.

### Trade-offs

- there is intentionally no one-click account erasure yet;
- complete export remains a later bundle/streaming implementation;
- the inventory performs multiple owner-scoped count queries and should eventually be optimized/cached for very large accounts;
- audit/outbox/backups need an explicit commercial retention policy before full erasure can be claimed.

## Rejected alternatives

### Cascade-delete all Projects

Rejected because Conversations, Secrets, Devices, external sourced records, SeaweedFS objects, projections and identity state do not all reduce to the Project root.

### Delete PostgreSQL first and clean external stores later

Rejected because failure after the canonical delete would destroy the reconciliation ledger and could leave orphaned data with no trustworthy retry path.

### Export everything including OpenBao values

Rejected because a portability request must not turn KAIRO into a secret-exfiltration/readback API.

### Claim complete erasure while backups/projections remain

Rejected because the user-facing state must describe the real retention boundary rather than a convenient database state.
