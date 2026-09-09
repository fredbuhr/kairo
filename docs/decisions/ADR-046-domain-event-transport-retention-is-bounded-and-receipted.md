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

The Worker memory-event consumer is currently the component that ensures the shared domain stream exists. It now also reconciles an already-existing stream so `subjects`, `max_msgs` and `max_age` converge on KAIRO's declared configuration rather than silently preserving an old unbounded stream.

This stream is transport state, not canonical history. Production deployments may shorten the horizon, but increasing it to effectively indefinite retention requires revisiting the account-retention contract.

### Outbox publication receipts

Migration `0020_outbox_jetstream_receipts` adds nullable:

- `OutboxEvent.jetstream_stream`;
- `OutboxEvent.jetstream_sequence`.

After a successful `JetStreamContext.publish(...)`, Core records the returned `PubAck.stream` and `PubAck.seq` in the same database transaction that marks the event published.

The `(jetstream_stream, jetstream_sequence)` pair is unique when present. It is transport identity only and does not replace the canonical Outbox UUID.

### Publish replay de-duplication

Core publishes the canonical Outbox UUID as the `Nats-Msg-Id` header.

This closes the most common dual-write ambiguity: if NATS accepted the message but Core lost the PostgreSQL commit, the immediate Outbox retry asks JetStream to de-duplicate the same logical publish instead of intentionally creating another transport copy.

JetStream de-duplication is still a server-side bounded window, not a substitute for the PostgreSQL Outbox. The canonical replay identity remains `OutboxEvent.id`.

### Historical published rows

Migration 0020 does **not** guess JetStream sequences for rows published before receipt persistence existed.

Those historical rows may have `published_at` but no stream/sequence. They require either:

- natural expiry under the bounded stream retention horizon; or
- an operator/migration-specific reconciliation procedure if immediate deletion is mandatory.

KAIRO must surface such unmapped evidence rather than pretending it can surgically delete a sequence it never recorded.

### Future erasure action

ADR-045 already makes user-world Outbox rows subject-addressable. This ADR adds the transport identity needed for the next retention action:

1. require no unpublished subject-owned events;
2. delete/purge mapped JetStream sequences or wait for verified max-age expiry;
3. only then minimize/remove PostgreSQL Outbox payloads according to the final retention policy;
4. preserve shared/system evidence separately.

The actual delete/redact/retain action is intentionally not introduced merely by adding the receipt columns. `AccountErasurePreflight.destructive_endpoint_available` remains false until the full evidence-retention operation is replay-safe and validated.

## Validation

`scripts/smoke/outbox_jetstream_retention_contract.py` checks without infrastructure that:

- Outbox has stream/sequence receipt fields and uniqueness;
- migration 0020 exists and documents the historical limitation;
- the relay uses `Nats-Msg-Id` and persists `PubAck.stream/seq` before marking publication complete;
- Core and Worker share the 7-day default retention setting;
- `.env.example` exposes the retention control;
- the Worker sets max-age on new streams and reconciles existing streams with `update_stream`.

The proof is scheduled in the Ownership workflow. Current GitHub-hosted CI remains blocked before runner assignment by issue #38, so this is implemented but not yet current-head validated.

## Consequences

### Positive

- NATS transport copies no longer have intentionally indefinite retention;
- newly published user-world events have an exact JetStream receipt for later erasure/reconciliation;
- Outbox publish replay has a stable de-duplication identity;
- stream configuration converges even when an older persistent NATS volume already exists;
- account-erasure logic can distinguish mapped new events from historical unmapped events.

### Trade-offs

- the Worker currently owns domain-stream configuration because it owns the durable consumer bootstrap; a future dedicated messaging-control service could centralize this;
- each successful publish persists two additional receipt fields;
- historical published rows cannot be retroactively mapped safely;
- bounded max-age can remove events a consumer failed to process for longer than the retention horizon, so consumer health/lag must be operationally monitored;
- exact immediate erasure still requires a later JetStream sequence-deletion/reconciliation action.

## Rejected alternatives

### Keep JetStream indefinitely and delete only PostgreSQL evidence

Rejected because complete erasure cannot ignore a durable transport copy.

### Infer JetStream sequence from Outbox order

Rejected because retries, other publishers and historical delivery timing make ordering inference unsafe.

### Treat `published_at` as proof the NATS copy has expired

Rejected because publication time alone does not identify the message or prove stream retention configuration.

### Use only NATS de-duplication and remove the PostgreSQL Outbox

Rejected because JetStream's duplicate window is bounded and does not replace transactional domain-state-to-event reconciliation.
