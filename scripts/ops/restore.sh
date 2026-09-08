#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${KAIRO_COMPOSE_ENV_FILE:-.env}"
OVERLAY="${KAIRO_COMPOSE_OVERLAY:-compose.override.yaml}"
SNAPSHOT="${1:-latest}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Create it from the appropriate environment template first." >&2
  exit 2
fi

if [[ "${KAIRO_CONFIRM_RESTORE:-}" != "YES" ]]; then
  echo "Restore is destructive. Re-run with KAIRO_CONFIRM_RESTORE=YES after verifying the target environment." >&2
  exit 2
fi

COMPOSE_ARGS=(--env-file "$ENV_FILE" -f compose.yaml)
if [[ -n "$OVERLAY" ]]; then
  COMPOSE_ARGS+=(-f "$OVERLAY")
fi
OPS_ARGS=("${COMPOSE_ARGS[@]}" -f compose.ops.yaml)

compose() {
  docker compose "${COMPOSE_ARGS[@]}" "$@"
}

ops() {
  docker compose "${OPS_ARGS[@]}" --profile ops "$@"
}

mkdir -p .kairo-backup-staging "${RESTIC_LOCAL_PATH:-./backups/restic}"
rm -rf .kairo-backup-staging/restore
mkdir -p .kairo-backup-staging/restore

echo "Materializing Restic snapshot '$SNAPSHOT' into restore staging..."
ops run --rm restic restore "$SNAPSHOT" \
  --target /staging/restore \
  --include /data/postgres \
  --include /data/nats \
  --include /data/seaweed \
  --include /data/openbao

for volume in postgres nats seaweed openbao; do
  if [[ ! -d ".kairo-backup-staging/restore/data/$volume" ]]; then
    echo "Snapshot is missing required volume payload: /data/$volume" >&2
    exit 3
  fi
done

QUIESCE_SERVICES=(
  kairo-web
  kairo-realtime
  kairo-worker
  kairo-core
  temporal-ui
  keycloak
  temporal
  activepieces
  langfuse-web
  langfuse-worker
  litellm
  openbao
  seaweedfs
  nats
  postgres
)

mapfile -t RUNNING_SERVICES < <(compose ps --services --status running)
STOPPED_SERVICES=()
for candidate in "${QUIESCE_SERVICES[@]}"; do
  for running in "${RUNNING_SERVICES[@]}"; do
    if [[ "$candidate" == "$running" ]]; then
      STOPPED_SERVICES+=("$candidate")
      break
    fi
  done
done

if ((${#STOPPED_SERVICES[@]} > 0)); then
  echo "Stopping durable-state users before destructive restore: ${STOPPED_SERVICES[*]}"
  compose stop -t 30 "${STOPPED_SERVICES[@]}"
fi

RESTORE_APPLIED=false
restore_failure_guard() {
  if [[ "$RESTORE_APPLIED" != "true" ]]; then
    echo "Restore did not complete; affected services remain stopped for inspection." >&2
  fi
}
trap restore_failure_guard EXIT INT TERM

ops run --rm volume-restore
RESTORE_APPLIED=true

if ((${#STOPPED_SERVICES[@]} > 0)); then
  compose up -d "${STOPPED_SERVICES[@]}"
fi

trap - EXIT INT TERM
rm -rf .kairo-backup-staging/restore

echo "KAIRO restore completed from snapshot '$SNAPSHOT'."
echo "Production OpenBao may require operator unseal before /health/trust becomes ready."
