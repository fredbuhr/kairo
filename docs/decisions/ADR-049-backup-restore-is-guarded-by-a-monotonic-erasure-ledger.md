# ADR-049 — Backup restore is guarded by a monotonic erasure ledger

Status: accepted

Date: 2026-09-10

## Context

KAIRO's disaster-recovery snapshot contains PostgreSQL, NATS JetStream, SeaweedFS and OpenBao durable volumes. PostgreSQL also contains the Keycloak database in the current deployment topology.

That is correct for disaster recovery, but creates a privacy hazard once full account erasure exists: restoring a snapshot from before an erasure can resurrect canonical rows, objects, transport events, secrets or identity state which the live installation had already removed.

An erasure marker stored only inside the same Restic snapshot is not sufficient because restoring an older snapshot would roll the marker backward together with the data it is supposed to protect.

KAIRO does not yet have the final destructive account-erasure state machine or a verified post-restore tombstone reconciler. Restore must therefore fail closed rather than silently resurrecting erased data.

## Decision

KAIRO introduces a **monotonic erasure-ledger boundary outside the rollback-able state snapshot**.

### External ledger location

`scripts/ops/restore.sh` reads `KAIRO_ERASURE_LEDGER_PATH` from the process environment or compose environment file. Local development falls back to:

`.kairo-erasure-ledger/tombstones.jsonl`

The local directory is ignored by Git. A production deployment must mount/provide the ledger independently of the Restic state repository.

The ledger is deliberately **not** included in `scripts/ops/backup.sh`, whose Restic snapshot remains limited to the durable application volumes. This separation is a correctness property: the erasure ledger must not roll backward when application state does.

### Current fail-closed restore behavior

Before Restic staging or any volume mutation, restore checks the external ledger.

- when `KAIRO_ENV=production`, a missing ledger file refuses restore;
- when the ledger exists and is non-empty in any environment, restore refuses;
- the refusal happens before `restic restore`, service shutdown or `volume-restore` can modify durable state.

This is intentionally restrictive. Current KAIRO has no verified tombstone reconciliation step capable of safely restoring an old snapshot and then removing every resurrected subject across PostgreSQL, SeaweedFS, OpenBao, NATS, Keycloak and derived projections before services reopen.

A non-empty ledger therefore means: **do not restore this historical application snapshot with the current tooling.**

### Why environment detection uses `KAIRO_ENV`

The guard derives production status from `KAIRO_ENV` in the selected environment file (or an explicit process environment override), not from the overlay filename. Deployment filenames are conventions; the declared runtime environment is the product contract.

### Future tombstone format

This ADR does not yet standardize the final tombstone payload because the destructive account lifecycle does not exist.

The future format must satisfy all of the following:

- be append-only/monotonic from the perspective of restore protection;
- permit the restore reconciler to identify data that must not be resurrected;
- avoid turning the ledger into a plaintext export of Keycloak subjects;
- avoid reusing a simple unsalted hash that remains trivially linkable to a known subject;
- be encrypted and replicated independently from the rollback-able KAIRO state backup;
- survive restoration or replacement of the application database.

A keyed identifier or other operator-held mapping may be appropriate, but it must be decided together with the final erasure state machine rather than introduced casually.

### Future restore reconciliation

A later restore flow may relax the current blanket refusal only after it can prove this sequence:

1. materialize historical application state while normal user traffic remains unavailable;
2. read the external monotonic tombstone ledger;
3. remove every resurrected subject's canonical rows, objects, OpenBao values, NATS transport copies, Keycloak identity and derived projections using replay-safe deletion semantics;
4. apply Audit/Outbox minimization/retention policy;
5. verify no tombstoned subject remains addressable;
6. only then start Web/API/Worker services.

Until this sequence has an integration proof, a non-empty ledger remains a hard restore blocker.

### Relationship to backup retention

The ledger guard prevents an operator from accidentally resurrecting erased data with current tooling. It does not by itself erase historical encrypted backup bytes.

Production still needs a documented Restic retention/forget/prune policy and a maximum backup lifetime. Complete account-erasure claims must distinguish:

- live-system erasure;
- inability to restore an erased subject because tombstones are monotonic;
- eventual expiry/destruction of old encrypted backup media.

The account-erasure preflight therefore remains blocked on backup policy even after this guard exists.

## Validation

`scripts/smoke/restore_erasure_guard_contract.py` checks that:

- the ledger is ignored from Git application state;
- production detection is based on `KAIRO_ENV` rather than overlay filename;
- production refuses a missing external ledger;
- any non-empty ledger refuses restore;
- both checks appear before Restic materialization and `volume-restore` in the script;
- the normal backup command does not include `.kairo-erasure-ledger` or `KAIRO_ERASURE_LEDGER_PATH`;
- account lifecycle documentation continues to report backup/tombstone semantics as incomplete rather than claiming complete erasure.

Current GitHub-hosted CI is still blocked before runner allocation by issue #38. The guard and proof are implemented but are not claimed as executed/validated on the current head.

## Consequences

### Positive

- restoring an old state snapshot cannot silently roll back the erasure protection ledger;
- production fails closed when the independent erasure ledger is unavailable;
- erased-data resurrection risk becomes an explicit restore gate rather than an undocumented operator responsibility;
- future reconciliation can be added without changing the Restic snapshot boundary;
- KAIRO remains truthful that encrypted backup expiry is not yet solved merely because restore is guarded.

### Trade-offs

- once real tombstones exist, current restore tooling becomes unavailable until a verified reconciler is implemented;
- operators must protect another small but critical monotonic data store;
- disaster recovery and privacy deletion are now explicitly coupled operationally;
- no final tombstone serialization or cryptographic identifier is defined yet.

## Rejected alternatives

### Store tombstones only in PostgreSQL

Rejected because the same historical PostgreSQL snapshot would roll them backward.

### Include the erasure ledger in the same Restic backup

Rejected because restoring an old backup would restore an old ledger and defeat the monotonic guarantee.

### Restore first and clean erased users after services start

Rejected because resurrected data could become queryable or trigger background workflows before cleanup completes.

### Use a plaintext list of Keycloak subjects immediately

Rejected because the ledger would itself become a sensitive long-lived user identifier registry before its final access/encryption design exists.

### Claim backups are erased because restore is blocked

Rejected. A restore guard prevents resurrection; it is not physical encrypted-backup expiry or destruction.
