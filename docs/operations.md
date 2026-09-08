# KAIRO operations boundary

This document defines how the Block 1 substrate is run, backed up and restored without mixing local-development conveniences with production trust assumptions.

## Development

Development uses the default Compose pair:

```bash
cp .env.example .env
make config
make up
```

`compose.override.yaml` deliberately enables development-only behavior such as Keycloak realm import and OpenBao dev mode. The imported `kairo-dev` account and the OpenBao dev root token must never be reused outside a local or disposable integration environment.

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
- KAIRO Core receives an explicit OpenBao workload token and production Keycloak issuer/JWKS configuration.

The repository intentionally does not contain production credentials or a pre-created production user. On first deployment, initialize/unseal OpenBao, provision a least-privilege KAIRO workload token, and configure the production Keycloak realm/client through the operator boundary. Block 6 will add the final TLS/reverse-proxy/private-network deployment hardening; the Block 1 overlay exists to prevent development bootstrap behavior from silently becoming production behavior.

## Restic backup set

The durable Block 1 recovery set is:

- `postgres_data` — canonical KAIRO state plus Temporal/Keycloak and other PostgreSQL-backed service databases;
- `nats_data` — JetStream state so already-published outbox events are not lost during a full disaster restore;
- `seaweed_data` — canonical asset/object bytes;
- `openbao_data` — persistent OpenBao state in production.

Neo4j, Valkey and other explicitly rebuildable projections/caches are not part of the Block 1 canonical recovery set.

The operations overlay pins Restic `0.19.1` and gives it read-only access to the durable volumes. The backup script quiesces only services that can write those volumes, snapshots the four stores, runs `restic check`, and then resumes only services that were running before the backup.

For a local restore drill:

```bash
# Set RESTIC_PASSWORD in .env first.
make backup
```

For production/off-host backups, point `RESTIC_REPOSITORY` and the corresponding backend credentials in `.env.production` to the chosen encrypted remote repository. `RESTIC_LOCAL_PATH` remains useful for local drills but is not an off-host disaster-recovery strategy.

## Restore

Restore is intentionally destructive and requires an explicit guard:

```bash
KAIRO_CONFIRM_RESTORE=YES make restore SNAPSHOT=latest
```

For production:

```bash
KAIRO_COMPOSE_ENV_FILE=.env.production \
KAIRO_COMPOSE_OVERLAY=compose.production.yaml \
KAIRO_CONFIRM_RESTORE=YES \
bash scripts/ops/restore.sh latest
```

The restore procedure first materializes the snapshot into staging, verifies all required volume payloads exist, stops durable-state users, replaces the four target volumes and restarts the services that were previously running. If the destructive copy fails, affected services remain stopped for operator inspection rather than starting against a partial restore. Root-owned Restic staging data is cleaned through the isolated ops helper rather than by weakening host permissions.

A production OpenBao process restored from persistent storage may still require operator unseal before `/health/trust` becomes ready.

## CI recovery proof

`backup-restore-integration` performs a destructive recovery drill on disposable volumes. It seeds independent markers in PostgreSQL, NATS, SeaweedFS and OpenBao, snapshots all four stores, removes the live markers, restores the snapshot, and verifies that every marker returns. This prevents backup code that merely creates archives from being mistaken for a working recovery path.
