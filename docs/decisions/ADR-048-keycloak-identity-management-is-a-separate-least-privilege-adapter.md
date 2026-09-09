# ADR-048 — Keycloak identity management is a separate least-privilege adapter

Status: accepted

Date: 2026-09-10

## Context

ADR-044 makes complete account erasure a cross-store state machine. After subject ownership, memory purge and Audit/Outbox retention, the external Keycloak identity is still an independent trust boundary.

KAIRO must eventually be able to disable and finally delete one authenticated identity during account erasure, but the ordinary Web/Desktop login client is a public OIDC client and must never receive administrative authority. The Keycloak bootstrap realm administrator is also too broad to become a long-lived KAIRO runtime credential.

There is another important sequencing problem: disabling a Keycloak user does not necessarily invalidate every already-issued access token immediately. Conversely, deleting the identity too early can destroy the user's recovery/authentication path before PostgreSQL, SeaweedFS, OpenBao, derived projections and retained evidence have been reconciled.

## Decision

KAIRO Core owns a dedicated `KeycloakIdentityManager` provider adapter for future account-lifecycle orchestration.

### Separate confidential workload identity

The adapter uses:

- `KEYCLOAK_MANAGEMENT_CLIENT_ID`;
- `KEYCLOAK_MANAGEMENT_CLIENT_SECRET`;
- OIDC `client_credentials` grant.

The management client must be a dedicated confidential service account provisioned with only the realm-management permissions required to inspect, disable and eventually delete users in the KAIRO realm.

The adapter explicitly refuses to reuse `KEYCLOAK_CLIENT_ID`, which is the public Web/Desktop client. Runtime code also does not use `KEYCLOAK_ADMIN` / bootstrap administrator username/password.

The management client secret is Core-only deployment configuration. It is never sent to the browser, Worker, Temporal payloads, Audit, Outbox or user export.

Leaving the management secret empty disables identity-management operations. Development realm import therefore does not silently embed a reusable administrative client secret in source control.

### Exact subject identity

Every lifecycle operation targets the authenticated Keycloak `sub` directly as the Admin REST user id:

`/admin/realms/<configured realm>/users/<subject>`

The adapter does not search by username or email and does not accept a caller-supplied realm or Keycloak origin. After a read it verifies that the returned UserRepresentation `id` is exactly the requested subject.

This prevents username changes, duplicate/ambiguous lookup semantics or user-controlled provider origins from changing the erasure target.

### Bounded provider methods

The adapter currently provides only internal Python methods:

- `get_identity(subject)`;
- `disable_identity(subject)`;
- `delete_identity(subject)`.

Disable and delete verify the resulting provider state. Delete is idempotent for an already-absent identity.

There is deliberately **no public HTTP route** wiring these mutating methods yet.

### Why provider methods exist before a public delete button

A safe full account-erasure flow still needs a durable KAIRO lifecycle ledger and enforced local freeze.

The eventual order must be conceptually:

1. persist a KAIRO account-erasure operation/phase;
2. enforce a local write freeze so already-issued bearer tokens cannot create new user-world state;
3. reconcile/stop active durable work;
4. destroy/purge OpenBao, derived projections, SeaweedFS and canonical state in a replay-safe order;
5. apply the final Audit/Outbox retention pass;
6. persist restore-after-erasure tombstone/backup semantics;
7. delete the Keycloak identity only when recovery no longer depends on that identity.

Keycloak disable may occur earlier than final deletion once the local KAIRO freeze exists, but disable alone is not considered the write freeze because bearer-token lifetime is independent.

### No public self-lockout in this slice

KAIRO does not expose a standalone “disable my Keycloak user” button before the durable lifecycle orchestrator exists. Doing so could strand a user with an unusable identity while the rest of the erasure workflow remains incomplete.

The current Settings full-account delete control therefore stays disabled.

## Validation

`scripts/smoke/keycloak_identity_boundary_contract.py` checks that:

- management configuration is distinct from the public client;
- the adapter uses `client_credentials` and never a password/bootstrap-admin grant;
- target identity is the exact subject path, not username/email search;
- provider disable/delete verify the resulting state;
- the adapter exposes no APIRouter/public deletion endpoint;
- `.env.example` leaves the management secret empty and documents separate provisioning;
- local compose passes the optional management credential only to Core.

This is a provider-boundary source/configuration proof only. A real management-client integration test must be added when a dedicated Keycloak service account is provisioned in CI/deployment.

Current hosted CI is still blocked before runner allocation by issue #38, so even the static proof must not be called current-head validated until a runner executes it.

## Consequences

### Positive

- the public Web/Desktop client never gains Keycloak Admin REST authority;
- the bootstrap administrator does not become a runtime KAIRO credential;
- account lifecycle targets immutable subject identity rather than mutable username/email;
- provider mutation semantics are isolated behind one replaceable/testable adapter;
- KAIRO can add the durable lifecycle state machine later without redesigning identity transport;
- the product avoids exposing a premature self-lockout button.

### Trade-offs

- production deployment needs another confidential workload credential and Keycloak service-account policy;
- local development does not automatically have a working management client merely because Keycloak starts;
- exact token revocation/session invalidation behavior still needs provider-version validation when freeze orchestration is implemented;
- complete account erasure remains blocked until the local freeze/deletion ledger and backup tombstone contract exist.

## Rejected alternatives

### Reuse the public `kairo-web` client

Rejected because a public client cannot safely hold an administrative secret and must not receive realm-management authority.

### Use Keycloak bootstrap admin username/password from Core

Rejected because it grants far broader authority than account lifecycle needs and creates a dangerous long-lived runtime credential.

### Search users by username/email during deletion

Rejected because those attributes are mutable and lookup may be ambiguous; KAIRO already has the exact immutable `sub`.

### Delete Keycloak identity first

Rejected because KAIRO could lose its recovery/reconciliation path while user data still exists elsewhere.

### Expose disable/delete directly as a normal user endpoint now

Rejected because a durable local write freeze and replay-safe cross-store lifecycle ledger are prerequisites.
