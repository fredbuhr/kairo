#!/bin/sh
# Based on Temporal's maintained samples-server PostgreSQL setup contract.
set -eu

: "${POSTGRES_SEEDS:?POSTGRES_SEEDS is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"

PORT="${DB_PORT:-5432}"
echo "Waiting for PostgreSQL at ${POSTGRES_SEEDS}:${PORT}..."
until nc -z -w 2 "${POSTGRES_SEEDS}" "${PORT}"; do sleep 1; done

create_and_upgrade() {
  DB_NAME="$1"
  SCHEMA_PATH="$2"
  temporal-sql-tool --plugin postgres12 --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${PORT}" --db "${DB_NAME}" create || true
  temporal-sql-tool --plugin postgres12 --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${PORT}" --db "${DB_NAME}" setup-schema -v 0.0 || true
  temporal-sql-tool --plugin postgres12 --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${PORT}" --db "${DB_NAME}" update-schema -d "${SCHEMA_PATH}"
}

create_and_upgrade temporal /etc/temporal/schema/postgresql/v12/temporal/versioned
create_and_upgrade temporal_visibility /etc/temporal/schema/postgresql/v12/visibility/versioned

echo "Temporal PostgreSQL schemas are ready."
