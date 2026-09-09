# ADR-041 — SecretReferences are subject-owned write-only vault handles

Status: accepted

Date: 2026-09-09

## Context

KAIRO needs credentials and private connector configuration for capabilities such as Rotki and
Activepieces. The first implementation kept `SecretReference` rows as a deployment-global registry
and restricted their management to `kairo-admin`. That was acceptable while KAIRO was effectively a
single-user technical prototype, but it is incompatible with the authenticated multi-user boundary
introduced in ADR-040:

- a normal `kairo-user` could not configure their own integrations without an administrator;
- an administrator-facing global list exposed another user's secret metadata;
- simply opening the old API to users would have let a caller choose arbitrary OpenBao paths;
- Automation and Finance records could reference a SecretReference owned by a different subject;
- a globally unique caller-selected Automation idempotency key created an unnecessary cross-tenant
  collision namespace.

Secret values themselves were already kept out of PostgreSQL, but metadata isolation, provisioning
and retention also need an explicit ownership contract.

## Decision

`SecretReference` is part of the authenticated user's KAIRO world.

Each row carries `keycloak_subject`. Public list/get/status/update/delete/provision operations are
scoped to `Principal.subject`; a foreign UUID is returned as 404 rather than disclosing that another
subject owns it.

### Managed OpenBao namespace

In authenticated deployments, clients do **not** supply `provider_path`. KAIRO Core allocates the path
inside a deployment-owned namespace:

`secret/data/kairo/users/<subject-digest>/<reference-id>`

The raw Keycloak subject is not embedded in the path. The digest is only namespace partitioning; Core
authorization remains the access boundary.

Auth-disabled isolated smoke stacks may still provide an explicit deterministic path so controlled
fixtures can pre-provision OpenBao without inventing a second testing API.

### Write-only value provisioning

KAIRO exposes a bounded `PUT /v1/secret-references/{id}/values` operation. The endpoint:

- accepts at most 32 named string fields;
- validates field-name shape;
- limits each value to 16 KiB and the aggregate payload to 64 KiB;
- writes directly to OpenBao KV v2;
- returns only existence, key names and secret version;
- never returns the supplied values;
- records only key names/count/version in audit and domain events.

The web form clears its local value fields after a successful write. There is deliberately no public
API that reads secret values back into the browser. Internal connector adapters may resolve one named
value at execution time through the existing Core-owned OpenBao client.

### Explicit destruction and reference deletion

Removing a PostgreSQL reference and destroying vault material are **two distinct actions**.

`DELETE /v1/secret-references/{id}/values` is the explicit irreversible revocation operation. Core:

- verifies the reference belongs to the authenticated subject;
- reads only status metadata (existence, key names and current version);
- permanently deletes the KV-v2 metadata/all versions through the corresponding OpenBao metadata path;
- records only the previous key names/version/existence in audit and domain events;
- never reads a secret value into the browser, audit, NATS or PostgreSQL.

This operation is allowed even if a connector still references the handle. That is intentional: a user
must be able to revoke credentials immediately. Future executions then fail closed when the provider
value cannot be resolved.

`DELETE /v1/secret-references/{id}` removes only the KAIRO reference record and is stricter. Core
refuses deletion while:

- any AutomationDefinition or FinanceConnector still references the handle; or
- OpenBao still reports values for the path.

If OpenBao is unavailable, Core refuses to delete the reference because it cannot prove the provider
material is absent. This prevents the UI from claiming a credential was removed while leaving orphaned
secret material behind.

The Settings UI exposes these actions separately and requires explicit confirmation for destruction.

### Same-owner connector binding

Database constraints bind both Automation definitions and Finance connectors to a SecretReference
with the same `keycloak_subject`. Public handlers also check the owner before flush so failures are
404/controlled conflicts instead of raw database errors.

This is defense in depth: handler scoping provides correct product behavior, while composite foreign
keys prevent accidental future code from attaching another user's vault handle.

### Automation idempotency

A user-provided idempotency key is scoped to one `AutomationDefinition`, not globally across the
installation. The canonical uniqueness boundary is `(automation_id, idempotency_key)`. Two users may
therefore choose the same human-readable key without learning about or blocking each other.

## Consequences

### Positive

- Ordinary users can configure their own KAIRO integrations without receiving global admin access.
- Secret metadata follows the same subject boundary as Projects, Automations and Finance connectors.
- The browser never needs an OpenBao token and cannot select arbitrary vault paths.
- Secret values remain absent from PostgreSQL, Temporal payloads, NATS domain events and API reads.
- Connector ownership is enforced both in handlers and in PostgreSQL.
- Caller-selected idempotency strings no longer form a cross-tenant namespace.
- Credential revocation is explicit and can occur even before a connector definition is removed.
- Deleting a KAIRO reference cannot silently orphan still-existing vault material.

### Trade-offs

- KAIRO Core still holds a workload credential capable of reaching the managed OpenBao hierarchy;
  production OpenBao policy must constrain that workload to the KAIRO-managed prefix, including the
  minimum KV-v2 data/metadata operations needed for write/status/destruction.
- The first provisioning operation replaces the submitted KV-v2 data set. Partial/merge semantics,
  if needed, require an explicit future contract rather than implicit read-modify-write in the UI.
- Destruction is intentionally irreversible and may make an enabled connector fail until new values
  are provisioned.
- Cross-system PostgreSQL/OpenBao operations cannot be one atomic transaction. The design therefore
  makes provider destruction explicit and requires provider absence before reference deletion rather
  than pretending the two stores can commit atomically.
- Migration 0015 refuses to guess ownership if a legacy SecretReference is already shared by more
  than one authenticated subject; such data must be separated intentionally.

## Rejected alternatives

### Keep SecretReferences global and admin-only

Rejected because KAIRO users need to configure their own connectors and because global metadata does
not satisfy the commercial/multi-user isolation boundary.

### Let clients provide arbitrary OpenBao paths

Rejected because a reference API must not become a path-selection oracle into deployment secrets.

### Return secret values so users can verify them

Rejected. Status is represented by existence, key names and version. Rotation is write-only.

### Silently destroy OpenBao values when deleting the database reference

Rejected because a database delete could fail after the irreversible provider-side action, and because
removing metadata from KAIRO should not disguise a credential-destruction decision. Revocation and
reference deletion are explicit separate operations.

### Store encrypted values in PostgreSQL

Rejected for this boundary. OpenBao already exists specifically to keep secret value custody out of
canonical domain state.
