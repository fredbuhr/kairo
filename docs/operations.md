# KAIRO operations boundary

This document defines how the current substrate is run, backed up and restored without mixing local-development conveniences with production trust assumptions.

## Development

Development uses the default Compose pair:

```bash
cp .env.example .env
make config
make up
```

`compose.override.yaml` deliberately enables development-only behavior such as Keycloak realm import and OpenBao dev mode. The imported `kairo-dev` account and the OpenBao dev root token must never be reused outside a local or disposable integration environment.

The optional `KEYCLOAK_MANAGEMENT_CLIENT_SECRET` is empty by default. Local realm import does **not** embed a reusable administrative service-account secret merely to make future account deletion convenient.

## Production configuration boundary

Production is represented by `compose.production.yaml` and `.env.production.example`.

Validate it with:

```bash
make prod-config
make ops-config
```

A production invocation uses explicit files so Docker Compose does not automatically load the development override:

```bash
cp .env.production.example .env.production
# Replace every CHANGE_ME value before starting anything.
docker compose --env-file .env.production \
  -f compose.yaml \
  -f compose.production.yaml \
  up -d
```

The production overlay changes the trust-sensitive behavior:

- OpenBao uses persistent file storage instead of `-dev` mode and explicitly erases inherited `BAO_DEV_*` values;
- Keycloak uses `start` instead of `start-dev` and does not import the development realm fixture;
- KAIRO Core always has authentication enabled;
- KAIRO Core receives an explicit least-privilege OpenBao workload token;
- Keycloak issuer/JWKS remain explicit production settings;
- the optional Keycloak account-lifecycle adapter receives a **dedicated** confidential management client id/secret, never the public Web/Desktop client or bootstrap admin password;
- JetStream domain retention is explicitly bounded by `NATS_DOMAIN_RETENTION_SECONDS`.

The repository intentionally does not contain production credentials or a pre-created production user. On first deployment, initialize/unseal OpenBao, provision a least-privilege KAIRO workload token, and configure the production Keycloak realm/client through the operator boundary.

If account lifecycle management is enabled, provision `kairo-identity-manager` separately with only the Keycloak realm-management user permissions required by ADR-048. Its secret belongs only in deployment secret configuration; it must not be exposed to Web/Desktop or Worker services.

## Restic backup set

The durable recovery set is:

- `postgres_data` — canonical KAIRO state plus Temporal/Keycloak and other PostgreSQL-backed service databases;
- `nats_data` — JetStream state so already-published outbox events are not lost during a full disaster restore;
- `seaweed_data` — canonical asset/object bytes;
- `openbao_data` — persistent OpenBao state in production.

Neo4j, Valkey and other explicitly rebuildable projections/caches are not part of the canonical recovery set.

The operations overlay gives Restic read-only access to the durable volumes. The backup script quiesces services that can write those volumes, snapshots the four stores, runs `restic check`, and then resumes only services that were running before the backup.

The **erasure tombstone ledger is deliberately not part of this Restic snapshot**. It protects against restore-after-erasure rollback and therefore must not be rolled backward with application state.

For a local backup drill:

```bash
# Set RESTIC_PASSWORD in .env first.
make backup
```

For production/off-host backups, point `RESTIC_REPOSITORY` and the corresponding backend credentials to an encrypted remote repository. `RESTIC_LOCAL_PATH` remains useful for local drills but is not an off-host disaster-recovery strategy.

## Restore

Restore is intentionally destructive and requires explicit confirmation:

```bash
KAIRO_CONFIRM_RESTORE=YES make restore SNAPSHOT=latest
```

For production:

```bash
KAIRO_COMPOSE_ENV_FILE=.env.production \
KAIRO_COMPOSE_OVERLAY=compose.production.yaml \
KAIRO_ERASURE_LEDGER_PATH=/secure-independent-store/kairo/tombstones.jsonl \
KAIRO_CONFIRM_RESTORE=YES \
bash scripts/ops/restore.sh latest
```

`KAIRO_ERASURE_LEDGER_PATH` must refer to a small monotonic ledger persisted independently from the Restic application-state repository. The final encrypted/replicated tombstone implementation is not complete yet, so current restore tooling is intentionally fail-closed:

- `KAIRO_ENV=production` plus a missing ledger file refuses restore;
- any non-empty ledger refuses restore in every environment;
- both checks happen **before** Restic materialization, service shutdown or volume replacement.

This means an operator cannot accidentally restore an old snapshot once erasure tombstones exist and silently resurrect deleted user data. Current KAIRO does not yet have the post-restore reconciler required to safely relax that refusal. ADR-049 records this boundary.

When the ledger is available and empty, the restore procedure materializes the snapshot into staging, verifies all required volume payloads exist, stops durable-state users, replaces the four target volumes and restarts the services that were previously running. If the destructive copy fails, affected services remain stopped for inspection rather than starting against a partial restore.

A production OpenBao process restored from persistent storage may still require operator unseal before `/health/trust` becomes ready.

## What the restore guard does not claim

The erasure ledger guard prevents **resurrection through current restore tooling**. It does not physically erase historical encrypted Restic snapshots.

Production still requires an explicit backup retention/forget/prune schedule and a verified maximum lifetime. A later complete-account-erasure claim must cover both:

- monotonic tombstones that prevent an erased account from becoming live again after restore;
- eventual expiration/destruction of historical encrypted backup material according to the declared retention policy.

Until both are implemented and tested, account erasure preflight continues to report the backup boundary as incomplete.

## CI recovery proof

`backup-restore-integration` performs a destructive recovery drill on disposable volumes. It seeds independent markers in PostgreSQL, NATS, SeaweedFS and OpenBao, snapshots all four stores, removes the live markers, restores the snapshot, and verifies that every marker returns.

The ownership/lifecycle suite additionally contains `restore_erasure_guard_contract.py`, which checks that the monotonic erasure guard cannot be rolled backward with the Restic backup set. Current GitHub-hosted CI remains blocked by issue #38, so new current-head proofs must not be described as passed until a runner actually executes them.
