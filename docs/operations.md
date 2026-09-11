# KAIRO operations boundary

## D02 — model admission and estimated money exposure

First D02 tranche; implementation validation is recorded in PROJECT_STATE, not implied here.
PostgreSQL owns reservations for the canonical model gateway, shared by all Core/Worker replicas. A short transaction advisory
lock serializes admission and accounting; contention and exhausted capacity return HTTP 429
with `Retry-After: 1`. No lock or DB connection is retained during a provider request.

| Setting | Default | Meaning |
|---|---|---|
| `KAIRO_MODEL_GLOBAL_CONCURRENCY` | 8 | Reserved/started model calls across replicas |
| `KAIRO_MODEL_OWNER_CONCURRENCY` | 2 | Model calls across all projects of one canonical owner |
| `KAIRO_MODEL_GLOBAL_DAILY_BUDGET_USD` | 50 | UTC-day known spend plus all outstanding estimates |
| `KAIRO_MODEL_OWNER_DAILY_BUDGET_USD` | 10 | Same exposure per project owner |
| `KAIRO_MODEL_MAX_OUTPUT_TOKENS` | 4096 | Non-streaming completion output bound passed to LiteLLM |
| `KAIRO_NEWS_MODEL_ESTIMATED_COST_USD` | 0.01 | Explicit News estimate when its task has no override |
| `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | 5 / 5 | Maximum ten connections per Core process by default |
| `DATABASE_POOL_TIMEOUT` | 10 seconds | Pool checkout timeout |

These are configurable initial limits, not measured throughput or a purchase authorization.
The task budget is still authoritative. Admission counts spent + reserved + uncertain amounts;
estimates round upward to six decimal places. Paid aliases `smart`/`alternative` require a
positive estimate. `local-fast` permits zero. Provider prices are not inferred from the alias:
**an estimate and output-token limit do not guarantee a strict dollar ceiling**. Actual cost
above the estimate is recorded, audited (`estimate_exceeded`) and blocks subsequent admission
if a budget is exceeded. `/v1/tasks/{id}/budget` exposes reserved/uncertain amounts, uncertain
call count and `over_budget`; `/v1/model-admission` exposes only the requesting owner's usage.

Lifecycle:

- Policy authorization requires the deterministic model-call key and creates a reservation for
  60 seconds. Repeating this reservation is safe and does not extend its lifetime.
- `/internal/v1/model-reservations/start` consumes that reservation exactly once and grants a
  300-second execution lease. A concurrent/lost start response is never blindly replayed.
- The Worker then checkpoints and sends one request, with a 120-second absolute deadline.
  LiteLLM router and SDK retries are configured to zero; real provider/proxy behavior remains
  a D04 measurement. Lease expiration cannot prove remote cancellation.
- A never-started expiry frees both money and capacity and can be re-admitted under the same key.
  A started expiry frees capacity but retains uncertain financial exposure across UTC midnight.
  Expired states are materialized on the next admission; read queries already respect expiry.
- Known results replay the canonical accounting handoff. Settlement and ledger insertion share
  a transaction and stable key. No reported price retains the unresolved estimate and is visible.
  A later trusted `model-usage` handoff with `cost_reported: true` reconciles an unknown record,
  audited in place; changed known costs are rejected. Never fabricate a zero cost to clear a block.

Recovery/upgrade: drain and stop old Workers before applying migration `0013_model_reservations`,
then upgrade Core and Workers together. Legacy accounting without a reservation remains accepted
for pre-D02 checkpoint recovery; old Workers cannot acquire fresh model authorization without a
stable key. Do not delete reservations/unknown costs to make a retry succeed. Recover verified
usage from the provider and reconcile with the same task/execution/key/alias; a missing provider
result still fails closed. A rollback to 0012 drops the reservation table and is only safe before
new dispatches, or after archiving/reconciling every liability and stopping all Workers.

Validation: `scripts/smoke/model_admission_contract.py` uses actual independent PostgreSQL
transactions and Core ASGI routes with explicit identity fixtures (no provider). CI applies real
migrations and exercises rollback/reapply on a disposable DB. Authenticated isolation and real
Research SIGKILL tests remain required. D02 still owes document/non-model admission, pagination,
projection batches, outbox/retention and capacity measurement. Memory SDKs/embeddings outside
this gateway are not covered by these model slots. One short global lock is a simple
correctness boundary; measure contention before replacing it with a more complex design.

References: [PostgreSQL advisory locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS),
[LiteLLM configuration](https://docs.litellm.ai/docs/proxy/configs).

## D01 — Worker and document processing limits

Temporal's existing queue is retained with explicit per-Worker slots. Document capacity is acquired
before download; conversion/chunking run in a short-lived child receiving model/cache paths but no
Core/DB/API credentials. No new service or broker is introduced.

| Setting | Default | Meaning |
|---|---|---|
| `KAIRO_WORKER_MAX_CONCURRENT_ACTIVITIES` | 16 | All concurrent activities per Worker |
| `KAIRO_WORKER_MAX_CONCURRENT_WORKFLOW_TASKS` | 8 | Workflow-task concurrency; minimum 2 with the current cache |
| `KAIRO_DOCUMENT_MAX_CONCURRENT` | 1 | Download/parse/report concurrency; below activity limit |
| `KAIRO_DOCUMENT_MAX_SOURCE_BYTES` | 26214400 | 25 MiB cap, enforced during streaming without requiring Content-Length |
| `KAIRO_DOCUMENT_MAX_TEXT_CHARS` | 1000000 | Parsed text limit before chunking |
| `KAIRO_DOCUMENT_PARSE_TIMEOUT_SECONDS` | 180 | Child wall-time; configurable up to 420 seconds |
| `KAIRO_WORKER_CPUS` | 2.0 | CPU ceiling per Worker container |
| `KAIRO_WORKER_MEMORY_LIMIT` | 4g | Memory ceiling per Worker container |
| `KAIRO_WORKER_PIDS_LIMIT` | 256 | PID/thread ceiling per Worker container |

These initial safety settings are not measured capacity guarantees. D04 must measure real
Docling/model memory and cold starts on the chosen hardware. Total usage multiplies with replicas.
Compose passes these settings through and uses `init: true` to reap descendants. Core's upload
`ASSET_MAX_BYTES` is independent; keep it consistent with the intended ingestion limit.

The activity has a 540-second local deadline, including capacity wait, inside the existing
600-second Temporal deadline. Heartbeats continue every five seconds. Cancellation/timeout kills
and reaps the parser group before deleting temporary files and releasing capacity. The output file
is bounded before reading. Empty/oversize/unsupported input fails without repeated retries;
transient parser failures retain the existing bounded retry policy. Generation/chunk provenance is preserved.

Each child owns its converter; caching models/converters across conversions remains a measured
future optimization. Waiting documents still occupy bounded Worker activity slots: **per-user
fairness and interactive priority during a document flood are not provided by D01**. D02 owns
global/owner admission. Other AI libraries and service budgets remain to be hardened; this is
not a complete production sandbox. Reverting restores the blocking parser but requires no data migration.

`uv run --locked --project services/worker python scripts/smoke/document_execution_contract.py`
tests actual controlled subprocesses and the text fallback, without model downloads. The existing
Documents integration exercises real Core/Temporal/Worker ingestion/reingestion. D04 supplies the
real Docling/PDF and memory/model proof. References:
[Python subprocess lifecycle](https://docs.python.org/3.12/library/asyncio-subprocess.html),
[Temporal Worker concurrency](https://python.temporal.io/temporalio.worker.Worker.html).

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
