#!/bin/sh
set -eu

ADDRESS="${TEMPORAL_ADDRESS:-temporal:7233}"
NAMESPACE="${DEFAULT_NAMESPACE:-default}"
RETENTION="${DEFAULT_NAMESPACE_RETENTION:-24h}"

echo "Waiting for Temporal at ${ADDRESS}..."
until temporal operator cluster health --address "${ADDRESS}" >/dev/null 2>&1; do sleep 2; done

if temporal operator namespace describe --address "${ADDRESS}" --namespace "${NAMESPACE}" >/dev/null 2>&1; then
  echo "Temporal namespace ${NAMESPACE} already exists."
else
  temporal operator namespace create --address "${ADDRESS}" --namespace "${NAMESPACE}" --retention "${RETENTION}"
  echo "Created Temporal namespace ${NAMESPACE}."
fi
