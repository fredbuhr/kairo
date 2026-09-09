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

env_file_value() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 || true)"
  printf '%s' "${line#*=}"
}

KAIRO_ENV_VALUE="${KAIRO_ENV:-$(env_file_value KAIRO_ENV)}"
KAIRO_ENV_VALUE="${KAIRO_ENV_VALUE:-development}"

# The erasure ledger is deliberately outside the Restic state snapshot. Restoring an older snapshot
# must never roll this guard backward with the data it protects. Production therefore requires the
# external ledger file to be mounted/present before any destructive restore is allowed.
ERASURE_LEDGER_PATH="${KAIRO_ERASURE_LEDGER_PATH:-$(env_file_value KAIRO_ERASURE_LEDGER_PATH)}"
ERASURE_LEDGER_PATH="${ERASURE_LEDGER_PATH:-.kairo-erasure-ledger/tombstones.jsonl}"
if [[ "$KAIRO_ENV_VALUE" == "production" && ! -f "$ERASURE_LEDGER_PATH" ]]; then
  echo "Production restore refused: external erasure ledger is unavailable at $ERASURE_LEDGER_PATH." >&2
  echo "Mount the monotonic erasure ledger before restoring any historical KAIRO state." >&2
  exit 4
fi
if [[ -s "$ERASURE_LEDGER_PATH" ]]; then
  echo "Restore refused: the external erasure ledger contains account tombstones." >&2
  echo "Current KAIRO has no verified post-restore tombstone reconciler yet; restoring this snapshot could resurrect erased user data." >&2
  echo "Services and volumes were not modified." >&2
  exit 4
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

clean_restore_staging() {
  ops run --rm --entrypoint /bin/sh volume-restore -ec 'rm -rf /staging/restore'
}

mkdir -p .kairo-backup-staging "${RESTIC_LOCAL_PATH:-./backups/restic}"
clean_restore_staging
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
clean_restore_staging

echo "KAIRO restore completed from snapshot '$SNAPSHOT'."
echo "Production OpenBao may require operator unseal before /health/trust becomes ready."
