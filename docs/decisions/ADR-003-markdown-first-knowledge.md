# ADR-003 — Markdown-first durable knowledge

- **Status:** Accepted
- **Date:** 2026-09-07

## Decision

Store important user-facing knowledge in human-readable Markdown with stable IDs/front matter, while allowing structured indexes/databases for operational state and fast queries.

Do not make the live personal vault part of the source repository.

## Rationale

KAIRO's knowledge must remain understandable, exportable, and usable even if the runtime, UI, or database technology changes.

## Consequences

- easier export/backup and optional Obsidian compatibility;
- some relationships/search data require a parallel structured index;
- synchronization between representations must be explicit and testable.
