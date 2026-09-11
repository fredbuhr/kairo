# KAIRO operations boundary

## D02 — shared capacity, bounded reads and recovery

The rest of D02 is delivered together in PR #86. `PROJECT_STATE.md` records the exact tested
head; the limits below describe behavior, not measured production throughput. All replicas
must share the same PostgreSQL database, Core settings and compatible Worker revision.

| Control | Default | Behavior |
|---|---|---|
| `KAIRO_WORK_GLOBAL_CONCURRENCY` | 4 | Shared document + memory activities across replicas |
| `KAIRO_WORK_OWNER_CONCURRENCY` | 1 | Shared across all projects of the canonical owner |
| `KAIRO_WORK_MAX_PENDING` / `KAIRO_WORK_OWNER_MAX_PENDING` | 1000 / 100 | Atomic admission backlog; HTTP 429 before creating excess work |
| Work lease | 660 s; renew every 15 s | Expired tokens cannot report canonical results |
| Worker activity slots | 16 | Must exceed global heavy-work concurrency; preserves slots for other activities |
| `OUTBOX_MAX_PENDING` | 10000 | Rejection threshold; producers return 503 when unpublished backlog reaches it |
| `OUTBOX_PAYLOAD_MAX_BYTES` | 65536 | Reject oversized domain-event payloads in their transaction |
| `OUTBOX_RETENTION_DAYS` | 30 | Retain published outbox history; never purge unpublished events |
| `MAINTENANCE_BATCH_SIZE` | 500 | Maximum rows per retention target per 60-second pass |
| `NATS_DOMAIN_MAX_AGE_SECONDS` | 1209600 (14 d) | Finite transport replay window |
| `NATS_DOMAIN_MAX_BYTES` | 268435456 (256 MiB) | Stream size bound; also at most 100000 messages |

The heavy-work admission queue is PostgreSQL state over existing Tasks. A waiting activity
returns immediately and Temporal waits five seconds without occupying an activity slot. After
100 unsuccessful admissions it continues as a new run of the same workflow, preserving the
Task and bounding history growth. FIFO applies to eligible owners whose activities have polled
within 30 seconds. Inactive/expired candidates cannot indefinitely block a different owner.
Model calls keep their separate atomic financial reservations from #85.

Admission precedes document downloads and memory projection. Memory ownership comes from the
canonical conversation, not its shared system Project. Lost completion responses replay a small
cached result. Lease loss cancels and reaps the owned child before releasing the slot. Documents
retain the 540-second activity wall time; memory has a 280-second wall time and 240-second child
limit. Independent child alarms (480 s documents / 270 s memory) also bound lifetime after abrupt
parent death on the Linux Worker. Cold Mem0/embedding startup occurs per child; benchmark it in
D04 before adding a cache/process pool. `infer=False` and no generative Graphiti extraction remain
mandatory. Child isolation is not a complete security sandbox or a guarantee of remote cancellation.

Observability: `/v1/work-capacity` exposes the authenticated owner's active/waiting counts,
oldest waiting timestamp and limits. `/v1/system/work-capacity` requires admin and exposes global
counts. `/v1/system/outbox` adds oldest unpublished timestamp, rejection threshold and retention
limits. HTTP 429 signals admission pressure; 503 signals event-backlog pressure. Alert on growing
oldest age as well as row count. A stuck Task with no valid lease remains diagnosable canonical
state; inspect its Temporal workflow and resume the same identity instead of cloning Tasks.

Outbox publication claims at most 20 rows for 60 seconds in a short transaction. NATS I/O runs
without a SQL transaction/connection; each acknowledgment updates only the matching claim.
Crashes replay the same `Nats-Msg-Id`; consumers must remain idempotent beyond NATS's finite
deduplication window. A full stream rejects new messages (`discard=new`), keeping them unpublished
in PostgreSQL for retry. The outbox rejection threshold is intentionally **not an exact reservation**:
concurrent in-flight producer transactions can overshoot it. It does not authorize unbounded disk
usage; monitor PostgreSQL free space and recover transport before admitting sustained new work.
The message ORM event producer enforces the same threshold.

Cleanup targets only old *published* outbox events and finished heavy-work cache rows whose Tasks
are terminal. It never deletes Tasks, Documents, Assets, conversations, audit receipts, model usage,
reservations or uncertain financial obligations. Canonical/audit retention remains a deliberate data
policy and storage-sizing concern; these records are not disposable transport history.

### Collection protocol

List bodies remain JSON arrays; `limit` defaults to 100, maximum 200. Read `X-Kairo-Next-Cursor`
and send it unchanged as `cursor` to the same collection/filter. The header is exposed through
CORS. An empty header means the end. Ownership and project filters run before SQL LIMIT.
Projects/Tasks/Documents are newest first; document versions use descending generation; messages,
assets, devices, secret references and artifacts use ascending creation; tools retain key order.
Approval requests are newest first. UUID tie-breakers prevent omissions at identical sort keys.

`/v1/today` returns at most 20 items per mutually exclusive bucket (maximum 100), plus
`next_cursors`. Continue with the same day/timezone and `bucket` + its `cursor`; only that bucket
is returned. These are live pages, not immutable snapshots: editing sort keys may move a Task;
refresh after edits. Projects, Research, Knowledge and Today provide explicit next-page controls;
selection-by-ID routes keep older selected Projects/DocumentVersions accessible. Search results
can open their exact Document/Version without scanning earlier pages. Counts in the interface
refer to displayed rows. Capabilities are a fixed registry; knowledge/context and chunk endpoints
retain their existing bounded queries.

### Rebuild and interruption procedure

1. Stop/drain old Workers and stop Core before migration `0014_capacity_and_data`; take the normal
   backup. Apply migrations, start matching Core and Workers with the same limits, then restore
   ingress. Do not mix pre-D02 Workers that lack lease reporting. A downgrade to 0013 drops active
   leases/cache; only do it with all Workers stopped and no active heavy work. Never downgrade to
   0012 to erase financial obligations.
2. For a stopped Worker, restart the matching revision and let Temporal retry the existing workflow.
   Another attempt waits until release/expiry. Inspect pending age, lease, Task and projection status.
   Terminal memory timeouts mark unfinished projection rows failed; successful/newer generations
   remain intact. Do not manually clear live leases while their process may still be running.
3. For NATS outage/full stream, restore connectivity/capacity and observe outbox drain. Do not purge
   unpublished rows. Stream configuration is reconciled on Core connection; one durable memory
   event consumer hands off Tasks, while all Workers may execute admitted Tasks. Admission rejection
   NAKs for five seconds; unacknowledged delivery and local buffers are bounded. Existing durable
   consumer limits are reconciled explicitly on startup; binding alone does not upgrade them.
   Core reuses its reconnecting NATS client and reconciles stream limits after reconnection.
4. After an outage beyond the 14-day replay window, rebuild derived memory from canonical messages.
   Set `KAIRO_OPERATIONS_TOKEN` in the environment (development: use the development internal token); do not put it in shell history or the checkpoint.
   Run `python scripts/ops/rebuild_memory.py --core http://127.0.0.1:8000 --checkpoint /safe/path/memory-rebuild.json`.
   Use `--message-id UUID` for a selected recovery (at most 200 IDs) or `--limit 40` on a new run.
   On interruption rerun the same Core/checkpoint command without selection/limit overrides.
5. The CLI saves request identity before network dispatch, then advances atomically after each page.
   Core takes at most 100 messages per page and records a durable audit receipt in the same transaction
   as generation changes/events. Retrying the identical page returns that receipt without creating
   another generation. Continue with the returned cursor and fixed `through` watermark. New messages
   after the watermark are handled by normal events or a later rebuild. A completed checkpoint does
   nothing on replay; deliberately use a new checkpoint to request a new rebuild.
6. `queued` means handoff, not completed embeddings. Observe Task/projector terminal states and run
   the memory smoke. A 429/503 leaves the page recoverable; diagnose persistent pressure rather than
   multiplying request IDs. Audit receipts preserve historical replay and are not automatically pruned.

Validation combines the PostgreSQL capacity/data contract (1000 synthetic Tasks, multiple owners,
page ties, per-bucket traversal, lease expiry, idempotent rebuild and retention), real controlled
child-process tests, the existing authenticated Core/Temporal integrations and Research SIGKILL.
Real model/Docling/embedding load, hardware throughput and backup recovery off-host remain D04;
D03 deployment controls are documented in [deployment](deployment.md); its exact-head validation is in PROJECT_STATE.

References: [nats.py stream and consumer configuration](https://nats-io.github.io/nats.py/modules.html),
[NATS stream limits](https://docs.nats.io/learn/jetstream/your-first-stream).

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
Research SIGKILL tests remain required. The shared-capacity section above covers document/memory
admission, pagination, rebuild and technical retention. Real capacity measurement remains D04.
Memory SDKs/embeddings are covered by heavy-work slots, separately from model money reservations. One short global lock is a simple
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
future optimization. D01 alone provided only local document slots; D02 now adds global/owner
admission and durable waiting before work. The local parser guard remains in place. Other AI libraries and service budgets remain to be hardened; this is
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

D03 replaces the earlier bootstrap-only production instructions. Follow the complete
[deployment procedure](deployment.md): effective configuration check, separate SQL provisioning
and migration, identity/secrets, networks, model inventory and explicit profiles. Do not run the
development override, noauth overlay or a blanket `up` before preparing those prerequisites.
`make prod-template` checks template syntax; `make prod-config` checks the real private environment.
Runtime Core/Worker enforce their own production guards as well. D04 retains the actual private
installation, real-engine, capacity and encrypted off-host restore proof.

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
