# ADR-047 — Account evidence retention minimizes Audit and clears Outbox transport

Status: accepted

Date: 2026-09-10

## Context

ADR-044 defined account erasure as a cross-store state machine. ADR-045 made Audit/Outbox evidence addressable by data subject without confusing resource ownership with the actor who performed an action. ADR-046 bounded the shared JetStream domain stream and added exact stream/sequence receipts for newly published Outbox rows.

Those changes made an erasure action possible, but did not decide what the action should actually do.

Audit and Outbox have different purposes:

- Outbox is a delivery/reconciliation ledger for domain events and is not intended to be permanent personal history;
- Audit is security/provenance evidence and may remain useful after personal content is removed;
- shared deployment Audit can legitimately describe an administrator changing global MCP/control-plane state even when that administrator later erases their personal KAIRO world.

Deleting both tables blindly would destroy useful deployment evidence. Retaining them unchanged would retain personal payloads and identifiers after a user requests erasure.

## Decision

KAIRO introduces an explicit **account evidence retention** primitive under `/v1/account/evidence/retention`.

It is an erasure-preparation operation, not account deletion and not a general-purpose audit-cleaning button.

### Readiness

The read model reports:

- subject-owned Audit row count;
- shared Audit rows that still identify the user as actor;
- subject-owned Outbox count;
- unpublished Outbox count;
- exact JetStream-receipted published rows;
- historical published rows without a receipt;
- malformed partial receipts;
- the latest time after which all historical unreceipted messages are covered by the configured max-age plus a safety grace.

Evidence retention is refused while canonical work may still be changing or reconciling:

- non-terminal Tasks;
- non-terminal WorkflowExecutions;
- pending ApprovalRequests;
- non-terminal AutomationInvocations;
- non-terminal ToolInvocations.

It is also refused while subject-owned Outbox events are unpublished or a receipt is structurally incomplete.

### Outbox transport first

PostgreSQL Outbox rows are never removed before their JetStream copy is accounted for.

For rows with an exact `jetstream_stream` + `jetstream_sequence` receipt:

1. Core verifies the domain stream still has the declared `kairo.domain.>` subject and a finite max-age no longer than `NATS_DOMAIN_RETENTION_SECONDS`;
2. Core deletes the exact JetStream sequence;
3. a message already absent is treated as successful idempotent reconciliation;
4. only after transport reconciliation does Core delete the corresponding PostgreSQL Outbox row.

If the whole domain stream no longer exists, its transport copies are necessarily absent and the PostgreSQL rows may be removed.

Historical published Outbox rows created before ADR-046 have no exact receipt. KAIRO does not guess their sequence. Such a row can be removed only after its publication time is older than the configured domain max-age plus a fixed safety grace, while the current stream contract is verified. This deliberately trades immediate erasure for truthful evidence when exact historical transport identity is unavailable.

The operation processes a bounded batch and can be repeated. External message deletion is idempotent, so a process failure after JetStream deletion but before the PostgreSQL commit is safe to retry.

### Audit minimization

Audit is minimized only after no subject-owned Outbox rows remain.

Subject-owned Audit rows keep only coarse non-personal security/provenance facts such as:

- action;
- resource type;
- authority level;
- timestamp.

KAIRO removes the direct user-world link by:

- clearing `keycloak_subject`;
- clearing `actor_id`;
- replacing `resource_id` with a generic erased marker;
- replacing the correlation id so minimized rows do not remain linkable as one subject history;
- clearing idempotency keys;
- clearing request payloads;
- replacing result payloads with a generic retention marker.

The goal is to retain an aggregate operational fact, not a pseudonymous copy of the user's history.

### Shared administrative Audit

A shared control-plane Audit row is not deleted merely because the erased user was its actor. Its shared resource history remains deployment state.

KAIRO instead:

- clears the matching user `actor_id`;
- clears the idempotency key;
- replaces occurrences of the subject identifier in structured request/result values;
- preserves the shared resource identity and action.

This keeps shared control-plane history without keeping the erased account as the attributed actor.

### Neutral destructive receipt

After a final batch completes, KAIRO writes one deployment-neutral Audit receipt describing only aggregate counts for the retention operation. It has no `keycloak_subject`, no user actor id and no source subject hash.

KAIRO intentionally does **not** persist a stable hash/HMAC of the erased Keycloak subject in this receipt, because that would create a new durable pseudonymous account identifier merely to prove that an identifier was removed.

### Later activity makes evidence dirty again

This primitive does not freeze the account. If a user performs new work after retention, normal KAIRO mutations create fresh Audit/Outbox evidence and the account-erasure preflight becomes blocked again.

A later full destructive account state machine may add an account freeze before invoking this primitive. Until then, the final preflight remains the release truth.

### Relationship to complete account erasure

After evidence retention completes, the `audit_outbox_retention_required` blocker disappears when the subject-owned/readable evidence counts are zero.

Complete account erasure still remains unavailable until the independent Keycloak identity and backup/restore contracts are implemented and validated. The destructive account endpoint therefore remains disabled.

## Validation

Two proof layers accompany this decision:

- `evidence_retention_contract.py` checks the explicit confirmation contract, active-work refusal, bounded batching, exact JetStream receipt deletion, historical max-age fallback, Audit minimization and neutral receipt rules without requiring infrastructure;
- `multi_user_evidence_retention.py` uses two real Keycloak users against one PostgreSQL/NATS/Core stack and verifies that applying retention to one subject removes/minimizes only that subject's evidence while the other subject's evidence remains intact.

The runtime proof waits for Core's Outbox relay to publish the fixture event before requesting retention, so it exercises the real PubAck stream/sequence path rather than bypassing transport reconciliation.

Current GitHub-hosted CI is still blocked before runner allocation by issue #38. These proofs are committed but are not claimed as executed or passed on the current head.

## Consequences

### Positive

- Outbox transport copies are reconciled before canonical delivery rows disappear;
- exact new JetStream receipts permit immediate targeted deletion;
- historical unreceipted events remain conservative instead of using guessed sequences;
- Audit can retain coarse deployment/security facts without keeping a personal history;
- shared control-plane Audit survives while erased actors are de-identified;
- the operation is bounded and idempotent enough to retry after cross-store failures;
- account preflight can now clear the Audit/Outbox blocker truthfully.

### Trade-offs

- historical pre-ADR-046 transport copies may delay erasure until the max-age horizon has elapsed;
- NATS logical message deletion is not a claim about lower-level storage media or backup destruction;
- evidence retention before an account freeze can become stale after later user activity;
- legal or regulated retention classes are not inferred by this generic product policy and would require explicit future policy extensions.

## Rejected alternatives

### Delete all Audit rows

Rejected because coarse security/provenance facts and shared control-plane history can remain operationally useful after personal data is removed.

### Keep subject-owned Audit unchanged for a fixed period

Rejected as the default erasure action because it retains direct subject/resource identifiers and arbitrary request/result payloads.

### Hash the subject and keep the full history pseudonymously

Rejected because a stable hash would preserve linkability across the user's retained history and create another durable account identifier.

### Delete PostgreSQL Outbox first and trust JetStream expiry later

Rejected because it destroys the only exact transport reconciliation receipt for newer events.

### Guess historical JetStream sequence numbers

Rejected because event ordering, retries and other publishers make sequence inference unsafe.
