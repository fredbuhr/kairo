#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export NEVOLIUM_COMPOSE_ENV_FILE="${NEVOLIUM_COMPOSE_ENV_FILE:-.env}"
export NEVOLIUM_COMPOSE_OVERLAY="${NEVOLIUM_COMPOSE_OVERLAY:-compose.override.yaml}"
export NEVOLIUM_CONFIRM_RESTORE=YES

OPS_COMPOSE=(docker compose --env-file "$NEVOLIUM_COMPOSE_ENV_FILE" -f compose.yaml)
if [[ -n "$NEVOLIUM_COMPOSE_OVERLAY" ]]; then
  OPS_COMPOSE+=(-f "$NEVOLIUM_COMPOSE_OVERLAY")
fi
OPS_COMPOSE+=(-f compose.ops.yaml --profile ops)

wait_for_postgres() {
  for _ in $(seq 1 60); do
    # The official Postgres entrypoint briefly starts an init-only server on the
    # Unix socket and then shuts it down before the real server starts. Probe TCP
    # loopback so the smoke cannot mistake that transient bootstrap server for
    # the durable instance that backup/restore must exercise.
    if docker compose exec -T postgres sh -ec 'pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null'; then
      return 0
    fi
    sleep 1
  done
  echo "PostgreSQL did not become ready" >&2
  return 1
}

openbao_volume_command() {
  "${OPS_COMPOSE[@]}" run --rm --entrypoint sh volume-restore -ec "$1"
}

mkdir -p backups/restic .nevolium-backup-staging
"${OPS_COMPOSE[@]}" run --rm ops-cleanup

docker compose up -d postgres nats seaweedfs
wait_for_postgres

docker compose exec -T postgres sh -ec '
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<"SQL"
DROP TABLE IF EXISTS nevolium_backup_probe;
CREATE TABLE nevolium_backup_probe (value text NOT NULL);
INSERT INTO nevolium_backup_probe(value) VALUES ($$canonical-postgres-proof$$);
SQL
'
docker compose exec -T nats sh -ec 'printf "%s\n" "canonical-nats-proof" > /data/nevolium-backup-probe'
docker compose exec -T seaweedfs sh -ec 'printf "%s\n" "canonical-seaweed-proof" > /data/nevolium-backup-probe'
openbao_volume_command 'printf "%s\n" "canonical-openbao-proof" > /restore/openbao/nevolium-backup-probe'

bash scripts/ops/backup.sh

wait_for_postgres
docker compose exec -T postgres sh -ec 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP TABLE nevolium_backup_probe"'
docker compose exec -T nats rm -f /data/nevolium-backup-probe
docker compose exec -T seaweedfs rm -f /data/nevolium-backup-probe
openbao_volume_command 'rm -f /restore/openbao/nevolium-backup-probe'

bash scripts/ops/restore.sh latest
wait_for_postgres

POSTGRES_PROOF="$(docker compose exec -T postgres sh -ec 'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT value FROM nevolium_backup_probe"' | tr -d '\r')"
NATS_PROOF="$(docker compose exec -T nats cat /data/nevolium-backup-probe | tr -d '\r\n')"
SEAWEED_PROOF="$(docker compose exec -T seaweedfs cat /data/nevolium-backup-probe | tr -d '\r\n')"
OPENBAO_PROOF="$(openbao_volume_command 'cat /restore/openbao/nevolium-backup-probe' | tr -d '\r\n')"

[[ "$POSTGRES_PROOF" == "canonical-postgres-proof" ]]
[[ "$NATS_PROOF" == "canonical-nats-proof" ]]
[[ "$SEAWEED_PROOF" == "canonical-seaweed-proof" ]]
[[ "$OPENBAO_PROOF" == "canonical-openbao-proof" ]]

echo "BACKUP/RESTORE SMOKE PASSED: PostgreSQL, NATS, SeaweedFS and OpenBao durable state survived a destructive restore drill."
