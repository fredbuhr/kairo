#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source scripts/dev/openclaw-env.sh
export OPENCLAW_BIN="${OPENCLAW_BIN:-$ROOT/plugins/openclaw-kairo-tools/node_modules/.bin/openclaw}"

PROOF_ROOT="${KAIRO_DEV_ROOT}/proofs/gate5"
mkdir -p "$PROOF_ROOT"

fail() {
  printf '\nGATE5_FAIL: %s\n' "$*" >&2
  exit 1
}

require_file() {
  [[ -f "$1" ]] || fail "missing file: $1"
}

job_json() {
  local job_id="$1"
  node --input-type=module - "$KAIRO_DATA_DIR" "$job_id" <<'NODE'
import { KairoJobLedger } from "./packages/kairo-core/src/index.js";
const [, , dataDir, jobId] = process.argv;
const ledger = new KairoJobLedger({ dataDir });
const job = await ledger.getJob("ztikix", jobId);
console.log(JSON.stringify(job));
NODE
}

usage_json() {
  local job_id="$1"
  node --input-type=module - "$KAIRO_DATA_DIR" "$job_id" <<'NODE'
import { KairoJobUsageLedger } from "./packages/kairo-core/src/index.js";
const [, , dataDir, jobId] = process.argv;
const ledger = new KairoJobUsageLedger({ dataDir });
const result = await ledger.getUsage("ztikix", jobId);
console.log(JSON.stringify(result));
NODE
}

case "${1:-}" in
  prepare)
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    proof_dir="$PROOF_ROOT/$stamp-prepare"
    mkdir -p "$proof_dir"

    printf 'Building and packing the Gate 5 KAIRO plugin...\n'
    (
      cd plugins/openclaw-kairo-tools
      npm run plugin:pack
    ) | tee "$proof_dir/plugin-pack.log"

    archive="$ROOT/plugins/openclaw-kairo-tools/kairo-openclaw-tools-0.1.0.tgz"
    require_file "$archive"

    printf '\nInstalling packed plugin into the isolated KAIRO runtime...\n'
    "$OPENCLAW_BIN" plugins install "$archive" --force --accept-capabilities \
      | tee "$proof_dir/plugin-install.log"

    printf '\nGATE5_PREPARE_PASS\n'
    printf 'proof_dir=%s\n' "$proof_dir"
    printf 'NEXT: restart the foreground Gateway once, then run: scripts/dev/prove-gate5.sh live\n'
    ;;

  live)
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    proof_dir="$PROOF_ROOT/$stamp-live"
    mkdir -p "$proof_dir"

    printf 'Checking Gateway health...\n'
    "$OPENCLAW_BIN" health > "$proof_dir/health.txt" || fail "Gateway health check failed"

    at_iso="$(node -e 'console.log(new Date(Date.now()+45000).toISOString())')"
    message="Pour ZTIKIX, appelle kairo_background_schedule exactement une fois pour programmer à ${at_iso} un Job A2 nommé 'Gate 5 routing proof'. Utilise requestedBudgetUsd=0.05, allowedTools=['kairo_project_get'], announce=true. Instructions du futur Job : 1) appelle kairo_job_start ; 2) appelle kairo_project_get pour ZTIKIX ; 3) appelle kairo_job_complete avec un résumé factuel très court. N'effectue aucune autre action, aucun accès externe et aucune écriture métier. Retourne le jobId et le scheduler id."

    printf 'Scheduling one bounded routing proof for %s...\n' "$at_iso"
    "$OPENCLAW_BIN" agent \
      --session-key agent:main:kairo-gate5-routing-proof \
      --message "$message" \
      --thinking low \
      --json > "$proof_dir/schedule-agent.json"

    job_id="$(node - "$proof_dir/schedule-agent.json" <<'NODE'
const fs = require("fs");
const text = fs.readFileSync(process.argv[2], "utf8");
const match = text.match(/job_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
if (!match) process.exit(2);
process.stdout.write(match[0]);
NODE
)" || fail "could not extract KAIRO job id from scheduling result"

    job_json "$job_id" > "$proof_dir/job-before.json"
    scheduler_id="$(node - "$proof_dir/job-before.json" <<'NODE'
const job = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
if (!job.scheduler_id) process.exit(2);
process.stdout.write(job.scheduler_id);
NODE
)" || fail "scheduled KAIRO job has no scheduler_id"

    printf 'KAIRO job: %s\nOpenClaw scheduler: %s\n' "$job_id" "$scheduler_id"
    "$OPENCLAW_BIN" cron get "$scheduler_id" > "$proof_dir/cron-job.json"

    printf 'Waiting for the scheduled KAIRO Job to settle...\n'
    deadline=$((SECONDS + 180))
    status=""
    while (( SECONDS < deadline )); do
      job_json "$job_id" > "$proof_dir/job-current.json"
      status="$(node - "$proof_dir/job-current.json" <<'NODE'
const job = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
process.stdout.write(String(job.status || ""));
NODE
)"
      case "$status" in
        completed|failed|cancelled) break ;;
      esac
      sleep 2
    done

    [[ "$status" == "completed" ]] || fail "expected proof Job to complete; final status=${status:-unknown}"
    cp "$proof_dir/job-current.json" "$proof_dir/job-final.json"

    printf 'Waiting for authoritative routing accounting...\n'
    routing_complete="false"
    deadline=$((SECONDS + 60))
    while (( SECONDS < deadline )); do
      usage_json "$job_id" > "$proof_dir/usage-current.json"
      routing_complete="$(node - "$proof_dir/usage-current.json" <<'NODE'
const result = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
process.stdout.write(String(result?.summary?.routing_complete === true));
NODE
)"
      [[ "$routing_complete" == "true" ]] && break
      sleep 2
    done

    cp "$proof_dir/usage-current.json" "$proof_dir/usage-final.json"
    "$OPENCLAW_BIN" cron runs "$scheduler_id" --json > "$proof_dir/cron-runs.json" || true

    [[ "$routing_complete" == "true" ]] || fail "routing accounting remained incomplete; inspect $proof_dir/usage-final.json"

    node - "$proof_dir/usage-final.json" <<'NODE'
const fs = require("fs");
const result = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const summary = result?.summary;
if (summary?.schema_version !== 3) throw new Error(`expected job-usage schema 3, got ${summary?.schema_version}`);
if (!Array.isArray(summary.routing) || summary.routing.length !== 1) {
  throw new Error(`expected exactly one routing summary, got ${JSON.stringify(summary?.routing)}`);
}
const route = summary.routing[0];
if (route.complete !== true) throw new Error("routing summary is not authoritative/complete");
if (!route.requested_ref) throw new Error("requested_ref missing");
if (!route.resolved_ref) throw new Error("resolved_ref missing");
if (!Array.isArray(route.harness_ids) || !route.harness_ids.includes("codex")) {
  throw new Error(`Codex harness not recorded: ${JSON.stringify(route.harness_ids)}`);
}
if (!route.classification || route.classification === "unknown") {
  throw new Error(`routing classification is not deterministic: ${route.classification}`);
}
if (!route.reason_code || !route.reason) throw new Error("routing reason code/text missing");
console.log(
  `routing_ok classification=${route.classification} reason_code=${route.reason_code} requested=${route.requested_ref} resolved=${route.resolved_ref} harness=codex`,
);
NODE

    printf '\nGATE5_LIVE_PASS\n'
    printf 'job_id=%s\n' "$job_id"
    printf 'scheduler_id=%s\n' "$scheduler_id"
    printf 'proof_dir=%s\n' "$proof_dir"
    ;;

  *)
    cat >&2 <<'EOF'
Usage:
  scripts/dev/prove-gate5.sh prepare
  scripts/dev/prove-gate5.sh live

prepare: pack/install the Gate 5 branch plugin.
         Restart the foreground Gateway once after it passes.
live:    run one bounded Cron routing/accounting proof after that restart.
EOF
    exit 2
    ;;
esac
