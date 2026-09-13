#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${NEVOLIUM_COMPOSE_ENV_FILE:-.env}"
OVERLAY="${NEVOLIUM_COMPOSE_OVERLAY:-compose.override.yaml}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Create it from the appropriate environment template first." >&2
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

mkdir -p .nevolium-backup-staging "${RESTIC_LOCAL_PATH:-./backups/restic}"

QUIESCE_SERVICES=(
  nevolium-web
  nevolium-realtime
  nevolium-worker
  nevolium-core
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

resume_services() {
  if ((${#STOPPED_SERVICES[@]} > 0)); then
    compose up -d "${STOPPED_SERVICES[@]}"
  fi
}

trap resume_services EXIT INT TERM

if ((${#STOPPED_SERVICES[@]} > 0)); then
  echo "Quiescing Nevolium durable-state writers: ${STOPPED_SERVICES[*]}"
  compose stop -t 30 "${STOPPED_SERVICES[@]}"
fi

if ! ops run --rm restic snapshots >/dev/null 2>&1; then
  echo "Initializing Restic repository..."
  ops run --rm restic init
fi

echo "Creating consistent Restic snapshot of PostgreSQL, NATS, SeaweedFS and OpenBao volumes..."
ops run --rm restic backup \
  /data/postgres \
  /data/nats \
  /data/seaweed \
  /data/openbao \
  --tag nevolium \
  --tag block1

ops run --rm restic check

resume_services
trap - EXIT INT TERM

echo "Nevolium backup completed and previously running services were resumed."
