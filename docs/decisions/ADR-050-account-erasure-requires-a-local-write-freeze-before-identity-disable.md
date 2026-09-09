# ADR-050 — Account erasure requires a local write freeze before identity disable

Status: accepted

Date: 2026-09-10

## Context

ADR-048 introduces a dedicated Keycloak identity-management provider adapter, but disabling a Keycloak user is not an instantaneous KAIRO write barrier. Access tokens already issued before provider disable may remain cryptographically valid until expiration, and KAIRO Core must not assume that provider state has revoked every bearer already present on Web/Desktop clients.

The account-erasure path therefore needs a canonical local barrier which can reject new user-originated mutations immediately while allowing already-started internal durable work to reconcile to a terminal state.

Without this boundary, the following race is possible:

1. KAIRO cleans derived memory/evidence for the account;
2. Keycloak is disabled;
3. an already-issued bearer creates another Project/Conversation/Asset before token expiry;
4. the destructive cleanup proceeds from a stale inventory and overstates erasure.

## Decision

KAIRO introduces `AccountWriteFreeze`, persisted in PostgreSQL by migration `0021_account_write_freeze`.

**Row existence for a Keycloak subject means public user-originated mutations are frozen.**

### Enforcement point

The fail-closed public `/v1/*` authentication perimeter checks the freeze after authenticating the subject and before dispatching a mutating request.

For a frozen subject:

- `GET` and `HEAD` remain available so the user can inspect inventory/preflight/export/read models;
- ordinary `POST`, `PUT`, `PATCH` and `DELETE` return HTTP `423 Locked` with stable code `account_write_frozen`;
- `/internal/v1/*` is outside the public bearer perimeter and keeps the internal-token trust boundary so already-running Worker/connector work can complete or fail canonically.

The freeze is therefore enforced against already-issued browser/Desktop bearer tokens without pretending to be a Temporal cancellation mechanism.

### Small erasure-preparation allow-list

A frozen user may still call only a bounded list of lifecycle writes:

- create/read/cancel the reversible write freeze itself;
- apply the ADR-047 Audit/Outbox evidence-retention stage;
- request the ADR-044 derived-memory purge.

Future destructive orchestration should use dedicated internal durable operations rather than continually broadening this public allow-list.

### Reversible current slice

The current public freeze is deliberately reversible because full destructive account erasure does not exist yet.

`POST /v1/account/erasure/write-freeze` requires literal confirmation `FREEZE_ACCOUNT_WRITES`. Replaying freeze returns the same operation identity.

`POST /v1/account/erasure/write-freeze/cancel` requires literal confirmation `UNFREEZE_ACCOUNT_WRITES` and removes the local barrier.

Both transitions are audited and emitted as subject-owned domain events. Cancelling a freeze can therefore create fresh account evidence, which is expected: a later erasure attempt must run its final evidence-retention pass only after the account is frozen for good by the eventual durable state machine.

### Separation from Keycloak provider mutation

The freeze route does **not** call `KeycloakIdentityManager.disable_identity()`.

Local freeze and provider identity state solve different problems:

- local KAIRO freeze rejects mutations from already-issued tokens;
- Keycloak disable prevents new authentication/session issuance at the provider boundary;
- Keycloak final deletion removes external identity only at a late durable erasure phase.

The eventual erasure orchestrator must persist its phase first, enforce local freeze, then use the Keycloak adapter. It must not delete Keycloak identity before KAIRO no longer needs the user bearer for recovery/cancellation semantics.

### Subject isolation

`account_write_freezes.keycloak_subject` is the primary key. A freeze for user A has no effect on user B. The API never accepts another subject as input; it always derives the target from `Principal.subject`.

### Why this is not yet full erasure

This slice adds a reliable write barrier, not the destructive state machine itself. Complete erasure still needs:

- durable account-erasure operation phases that become non-cancellable after irreversible work begins;
- internal/replay-safe cleanup of SecretReferences/OpenBao, SeaweedFS Assets, canonical PostgreSQL records and projections;
- final Audit/Outbox retention after the last possible personal write;
- Keycloak disable/session handling/final deletion through ADR-048;
- monotonic tombstone emission and restore reconciliation through ADR-049;
- backup expiry/forget/prune policy.

The full delete button remains unavailable.

## Validation

`scripts/smoke/account_write_freeze_contract.py` verifies the migration/model, typed confirmation, global public mutation barrier, explicit lifecycle allow-list and separation from Keycloak mutation.

`scripts/smoke/multi_user_account_write_freeze.py` uses two real Keycloak identities against one Core/PostgreSQL instance and verifies that:

- A can create state before freeze;
- A freezes using the existing bearer and receives a stable operation id;
- replay returns the same freeze operation;
- A can continue read-only access;
- A's ordinary Project mutation returns 423 with `account_write_frozen`;
- B remains unfrozen and can still mutate its own world;
- A can cancel the reversible current freeze and mutate again.

These proofs are committed to the Ownership workflow but are not claimed as passed while GitHub Actions issue #38 prevents a runner from executing them.

## Consequences

### Positive

- already-issued bearer tokens cannot race the final cleanup merely because Keycloak was disabled moments earlier;
- write freeze is subject-local and enforced before endpoint-specific mutation code;
- normal reads remain available during preparation;
- already-started internal durable work can still reconcile;
- Keycloak provider authority stays separate from the local data-plane guard;
- the eventual destructive orchestrator has a concrete freeze primitive instead of relying on token lifetime assumptions.

### Trade-offs

- every public mutating request performs one small subject freeze lookup;
- current freeze remains reversible and is therefore not by itself a final erasure commitment;
- lifecycle preparation actions can themselves create final Audit/Outbox evidence that must be reconciled later;
- long-running internal Workflows are not cancelled by freeze and must still reach terminal state before destructive deletion.

## Rejected alternatives

### Rely only on Keycloak `enabled=false`

Rejected because already-issued tokens may remain valid until expiry.

### Reject all requests including reads

Rejected because the user should still be able to inspect/export/preflight their data while preparing deletion.

### Block internal Worker traffic

Rejected because it could strand in-flight durable actions in non-terminal states and destroy the reconciliation path required before deletion.

### Expose a generic bypass header for frozen writes

Rejected because a browser-controlled escape hatch would defeat the freeze. Only explicit route-level lifecycle exceptions exist.

### Automatically delete the Keycloak identity when freeze is requested

Rejected because the current freeze is reversible and full cross-store destructive orchestration is not yet implemented.
