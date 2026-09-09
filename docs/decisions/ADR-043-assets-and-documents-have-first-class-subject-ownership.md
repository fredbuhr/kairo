# ADR-043 — Assets and Documents have first-class subject ownership

Status: accepted

Date: 2026-09-09

## Context

The first KAIRO document pipeline stored `owner_subject` inside `Asset.metadata_json` and
`Document.metadata_json`. Public handlers checked that tag, and Knowledge search already filtered it
inside PostgreSQL. That was workable for a single-user prototype, but it is a weak commercial tenant
boundary:

- ownership is hidden inside mutable JSON rather than represented in the schema;
- list handlers can accidentally load installation-wide rows and filter them later in Python;
- owner queries have no ordinary typed/indexed column;
- Project/Asset/Document consistency cannot be defended cleanly at the database boundary;
- Graph/entity ownership must understand an implementation detail of arbitrary metadata.

## Decision

Migration `0018_asset_document_ownership` adds non-null `keycloak_subject` columns to both `Asset` and
`Document` and makes those columns the canonical ownership boundary.

### Backfill

Existing rows are backfilled in this order:

1. historical `metadata_json.owner_subject` when present;
2. the attached Project owner when no metadata owner exists;
3. the isolated `development-user` subject as a final legacy fallback.

The historical JSON tag may remain as inert legacy metadata, but new code does not rely on it for
authorization.

### Asset boundary

New Assets always receive `Principal.subject` directly. Public list reads filter
`Asset.keycloak_subject` in SQL before rows are materialized. Detail/content/delete routes compare the
same first-class owner.

An Asset may remain unscoped (`project_id = NULL`). If a Project is attached, the database trigger
`trg_asset_project_owner` requires `Asset.keycloak_subject == Project.keycloak_subject` on new inserts
or rebindings. Project deletion may still set the nullable Asset project to NULL.

### Document boundary

New Documents receive `Principal.subject` and may only be created from an Asset owned by that same
subject. Public list/detail/version paths use `Document.keycloak_subject`; Knowledge search uses the
same column.

`trg_document_owner_bindings` requires future Document inserts/rebindings to agree with both the
Project owner and source Asset owner. Historical development Documents that still point at a reserved
migration-owned system Project are not rewritten merely to satisfy the new trigger; the existing
reingest compatibility path rehomes an explicitly owned legacy Document when it is touched.

Internal document source resolution also verifies the source Asset and Document owners still agree
before returning the source location to the Worker.

### Graph ownership

`entity_belongs_to_subject(...)` now checks the explicit Asset/Document columns rather than interpreting
metadata. This keeps Home/Brain relationship validation aligned with the canonical ownership schema.

## Validation

`scripts/smoke/asset_document_ownership_contract.py` checks the migration, first-class model fields,
constructors and SQL-scoped read paths without needing the integration stack.

`scripts/smoke/multi_user_asset_document_ownership.py` uses two real Keycloak users with one
Core/PostgreSQL/SeaweedFS instance and verifies:

- foreign Project Asset attachment returns 404;
- Asset lists/details/content do not cross subjects;
- a foreign Asset cannot become another user's Document source;
- Document lists/details/version routes do not cross subjects.

Both proofs are part of the dedicated Ownership workflow. Current hosted CI is still blocked before
runner assignment by issue #38, so this is implemented but not yet current-head validated.

## Consequences

### Positive

- tenant ownership is typed, indexed and queryable without JSON conventions;
- list operations scale with one user's world rather than the installation-wide table;
- PostgreSQL can reject future cross-owner Project/Asset/Document bindings;
- Knowledge and Graph share the same ownership fact as the REST APIs;
- JSON metadata can return to its intended role: descriptive/provenance metadata rather than access control.

### Trade-offs

- legacy metadata remains during migration compatibility and can no longer be treated as authoritative;
- historical system-project mismatches are tolerated until touched so migration does not silently seize or reassign old user data;
- Asset/Document account-deletion lifecycle still needs a cross-store policy covering PostgreSQL and SeaweedFS object deletion.

## Rejected alternatives

### Keep owner_subject only in JSONB

Rejected because commercial tenant ownership should not depend on an untyped metadata convention.

### Derive all ownership only through Project

Rejected because Assets may be intentionally unscoped and because a direct owner is useful before or
without Project attachment.

### Rewrite every historical Document to a new Project during migration

Rejected because migration should not guess user intent or silently seize reserved migration-owned
system workspaces. Existing compatibility code can rehome an explicitly owned Document when it is
actually used.
