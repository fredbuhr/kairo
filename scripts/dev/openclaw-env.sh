#!/usr/bin/env bash
set -euo pipefail

# Source this file from the KAIRO repository root:
#   source scripts/dev/openclaw-env.sh
#
# It keeps the KAIRO/OpenClaw development runtime outside the Git repository so
# live memory, credentials, session databases, and provider auth cannot be
# committed accidentally.

export KAIRO_DEV_ROOT="${KAIRO_DEV_ROOT:-$HOME/.kairo-dev}"
export OPENCLAW_HOME="${OPENCLAW_HOME:-$KAIRO_DEV_ROOT/openclaw-home}"
export OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-$KAIRO_DEV_ROOT/openclaw-state}"
export OPENCLAW_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-$KAIRO_DEV_ROOT/openclaw.json}"
export OPENCLAW_WORKSPACE_DIR="${OPENCLAW_WORKSPACE_DIR:-$KAIRO_DEV_ROOT/workspace}"
export KAIRO_DATA_DIR="${KAIRO_DATA_DIR:-$KAIRO_DEV_ROOT/kairo-data}"

mkdir -p \
  "$OPENCLAW_HOME" \
  "$OPENCLAW_STATE_DIR" \
  "$OPENCLAW_WORKSPACE_DIR" \
  "$KAIRO_DATA_DIR"

printf 'KAIRO development runtime\n'
printf '  KAIRO_DEV_ROOT=%s\n' "$KAIRO_DEV_ROOT"
printf '  OPENCLAW_STATE_DIR=%s\n' "$OPENCLAW_STATE_DIR"
printf '  OPENCLAW_CONFIG_PATH=%s\n' "$OPENCLAW_CONFIG_PATH"
printf '  OPENCLAW_WORKSPACE_DIR=%s\n' "$OPENCLAW_WORKSPACE_DIR"
printf '  KAIRO_DATA_DIR=%s\n' "$KAIRO_DATA_DIR"
printf '\nProvider credentials are intentionally not set by this script.\n'
