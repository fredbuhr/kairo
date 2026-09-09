# ADR-046 — Domain-event transport retention is bounded and receipted

Status: accepted

Date: 2026-09-09

## Context

KAIRO's transactional PostgreSQL Outbox and NATS JetStream solve different problems:

- PostgreSQL Outbox is the canonical delivery/reconciliation ledger;
- JetStream is transport/replay state for asynchronous consumers.

The first implementation published `kairo.domain.>` events into a persistent JetStream stream with a message-count cap but no explicit `max_age`, and the Outbox stored only `published_at`. That created two account-lifecycle gaps:

1. a published user-world event could remain in NATS without a time-bounded retention guarantee;
2. KAIRO could not map one published Outbox row back to the exact JetStream stream sequence for future privacy/retention reconciliation.

Deleting the PostgreSQL Outbox row alone would therefore not prove that the transport copy disappeared.

## Decision

KAIRO makes the domain-event transport both **time-bounded** and **receipted**.

### Bounded domain stream

`KAIRO_DOMAIN` retains `kairo.domain.>` events for a configurable maximum age:

`NATS_DOMAIN_RETENTION_SECONDS`

The development/default value is 604800 seconds (7 days).

Both Core's Outbox relay and the Worker memory-event consumer reconcile the shared domain stream before using it. New streams are created with KAIRO's declared subject, message-count bound and `max_age`; already-existing streams are updated when those fields drift. This deliberately avoids making retention correctness depend on whether Core or Worker starts first.

This stream is transport state, not canonical history. Production deployments may shorten the horizon, but increasing it to effectively indefinite retention requires revisiting the account-retention contract.

### Outbox publication receipts

Migration `0020_outbox_jetstream_receipts` adds nullable:

- `OutboxEvent.jetstream_stream`;
- `OutboxEvent.jetstream_sequence`.

After a successful `JetStreamContext.publish(...)`, Core records the returned `PubAck.stream` and `PubAck.seq` in the same database transaction that marks the event published.

The `(jetstream_stream, jetstream_sequence)` pair is unique when present. It is transport identity only and does not replace the canonical Outbox UUID.

### Publish replay de-duplication

Core publishes the canonical Outbox UUID as the `Nats-Msg-Id` header while preserving KAIRO event-type and correlation headers used for diagnostics.

This closes the most common dual-write ambiguity: if NATS accepted the message but Core lost the PostgreSQL commit, the immediate Outbox retry asks JetStream to de-duplicate the same logical publish instead of intentionally creating another transport copy.

JetStream de-duplication is still a server-side bounded window, not a substitute for the PostgreSQL Outbox. The canonical replay identity remains `OutboxEvent.id`.

### Historical published rows

Migration 0020 does **not** guess JetStream sequences for rows published before receipt persistence existed.

Those historical rows may have `published_at` but no stream/sequence. ADR-047 handles them conservatively: a historical unreceipted row may be removed from PostgreSQL only after its publication timestamp is older than the configured domain max-age plus a safety grace, and only while Core can verify the live stream remains bounded no more loosely than the declared contract. If the stream no longer exists, the transport copy is necessarily absent.

KAIRO never fabricates historical sequence identity.

### Account evidence retention consumes the receipt boundary

ADR-047 implements the retention operation prepared by this ADR.

For a subject-owned Outbox row with an exact receipt, Core:

1. verifies the live domain-stream subject/retention contract;
2. deletes the exact JetStream `(stream, sequence)` message;
3. treats an already-absent message as an idempotent success;
4. only then deletes the corresponding PostgreSQL Outbox row.

The operation is batched and retry-safe across the cross-store boundary. If JetStream deletion succeeded but the PostgreSQL transaction did not commit, a retry observes the message as absent and safely continues.

The full account destructive endpoint remains disabled because evidence retention is only one stage of the ADR-044 cross-store state machine. Keycloak identity and backup/restore-after-erasure boundaries remain independent release gates.

## Validation

`scripts/smoke/outbox_jetstream_retention_contract.py` checks without infrastructure that:

- Outbox has stream/sequence receipt fields and uniqueness;
- migration 0020 exists and documents the historical limitation;
- the relay captures the PubAck, uses `Nats-Msg-Id`, preserves diagnostic headers and persists `PubAck.stream/seq` before marking publication complete;
- Core and Worker share the 7-day default retention setting;
- `.env.example` exposes the retention control;
- both Core and Worker set max-age/message-count bounds on new streams and reconcile existing streams with `update_stream`.

`scripts/smoke/evidence_retention_contract.py` checks that ADR-047 consumes these receipts before PostgreSQL Outbox deletion and uses the bounded expiry fallback only for historical unreceipted rows.

The proofs are scheduled in the Ownership workflow. Current GitHub-hosted CI remains blocked before runner assignment by issue #38, so they are implemented but not yet current-head validated.

## Consequences

### Positive

- NATS transport copies no longer have intentionally indefinite retention;
- newly published user-world events have an exact JetStream receipt for later erasure/reconciliation;
- Outbox publish replay has a stable de-duplication identity;
- stream configuration converges independently of Core/Worker startup order and older persistent NATS volumes;
- account evidence retention can delete mapped new events exactly and treat historical unmapped events conservatively.

### Trade-offs

- domain-stream configuration logic currently exists in Core and Worker; a future dedicated messaging-control component could centralize the policy while retaining startup-order independence;
- each successful publish persists two additional receipt fields;
- historical published rows cannot be retroactively mapped safely and may delay erasure until bounded expiry;
- bounded max-age can remove events a consumer failed to process for longer than the retention horizon, so consumer health/lag must be operationally monitored;
- JetStream logical deletion does not itself prove physical media or backup erasure.

## Rejected alternatives

### Keep JetStream indefinitely and delete only PostgreSQL evidence

Rejected because complete erasure cannot ignore a durable transport copy.

### Infer JetStream sequence from Outbox order

Rejected because retries, other publishers and historical delivery timing make ordering inference unsafe.

### Treat `published_at` as immediate deletion proof

Rejected because publication time does not identify a specific message. ADR-047 uses it only after the bounded max-age horizon plus safety grace has elapsed.

### Use only NATS de-duplication and remove the PostgreSQL Outbox

Rejected because JetStream's duplicate window is bounded and does not replace transactional domain-state-to-event reconciliation.
