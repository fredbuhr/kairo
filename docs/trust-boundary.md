# KAIRO trust boundary

This document is normative for code that handles identity, devices, secret references and binary assets.

## Identity

Keycloak is the authentication provider. KAIRO Core owns authorization semantics.

For trusted resource APIs, Core validates a Bearer access token using the configured Keycloak JWKS endpoint and verifies:

- RS256 signature;
- expiration and issued-at claims;
- configured issuer;
- subject (`sub`);
- authorized party (`azp`) when present;
- KAIRO realm roles.

The client never supplies the canonical user subject for a device. `DeviceRegistration.keycloak_subject` is derived from the validated JWT `sub` claim.

Development uses the reproducible `kairo` realm imported from `infrastructure/keycloak/kairo-realm.json`. Those credentials are local-development fixtures only and must not exist in production.

## Roles

- `kairo-user`: personal resources such as the caller's registered devices and assets.
- `kairo-admin`: global trust configuration such as secret-reference metadata.

A later Policy Engine may impose stricter decisions, but it may not weaken authentication established here.

## Secrets

PostgreSQL stores only `SecretReference` metadata:

- name;
- OpenBao provider path;
- purpose.

Secret values live in OpenBao. Public KAIRO endpoints MUST NOT accept, return, log, audit, publish, trace, embed or otherwise persist secret values.

`GET /v1/secret-references/{id}/status` may report only whether a secret exists, the names of fields present, and version metadata. It must never return field values.

Internal adapters may use `OpenBaoClient.read_secret_value()` for a single requested field. Callers are responsible for keeping the returned value out of PostgreSQL, NATS, Temporal payloads/history, Langfuse, Mem0, Graphiti and LLM contexts unless a future explicit security design permits a narrowly scoped use.

Production must replace the development root token with a least-privilege workload identity/token.

## Assets

Binary content is authoritative in SeaweedFS; PostgreSQL stores canonical asset metadata and integrity hashes.

The first asset API:

- requires a validated `kairo-user` identity;
- limits upload size;
- computes SHA-256 before metadata commit;
- writes the object to the SeaweedFS Filer;
- stores only the generated object path, metadata and hash in PostgreSQL;
- records the owner subject in metadata until a richer sharing/ACL model lands;
- deletes the just-written object when the metadata transaction cannot be committed;
- preserves PostgreSQL metadata when SeaweedFS deletion fails, so a failed remote side effect is not silently represented as completed.

## Readiness

`/health/ready` proves the durable execution substrate needed by normal KAIRO work.

`/health/trust` separately proves that the sensitive resource boundary is usable:

- Keycloak JWKS available;
- OpenBao active/healthy standby;
- SeaweedFS Filer reachable.

This separation permits non-sensitive durable workflows to remain available during a temporary identity/secrets outage while sensitive APIs fail closed.

## Required acceptance proof

`scripts/smoke/resources.py` must prove, against real services:

1. a sensitive endpoint rejects an unauthenticated request;
2. a real Keycloak access token is accepted;
3. a device subject is derived from the signed token and duplicate registration is rejected;
4. an OpenBao KV value can be referenced while its value never appears in KAIRO API responses;
5. an authenticated file can be uploaded, hashed, read back byte-for-byte and deleted through KAIRO Core.
