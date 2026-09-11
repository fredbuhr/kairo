# ADR-020 — Canonical document ingestion and Docling boundary

Status: accepted

## Context

Nevolium needs documents to support knowledge retrieval, project context and later agent research. A parser such as Docling is useful, but parser output must not become the system of record: parser versions, chunking strategies and extraction engines will change over time.

## Decision

Nevolium separates document identity, object storage and parser execution.

- SeaweedFS `Asset` remains the canonical uploaded binary and retains its SHA-256 digest.
- PostgreSQL `Document` is the stable semantic identity bound to one source Asset.
- Each parse creates an immutable-generation `DocumentVersion` with parser/version/source digest/provenance.
- PostgreSQL `DocumentChunk` rows are canonical ingestion results for that version and carry deterministic ordinal identity plus a content digest.
- `document.ingest` is a normal Nevolium Task executed through Temporal and the existing policy boundary at authority A1 with zero model budget.
- Docling runs only in the Worker. Core never imports Docling and does not depend on its internal schemas.
- Parsing introduces no model call. When Docling is absent, CI and minimal installations may use a deterministic fallback only for explicitly textual media types; binary formats fail closed rather than pretending to have been parsed.
- Re-ingestion creates a new generation. It does not mutate or erase previous document versions.
- Completion is idempotent for a version: Core replaces that version's chunk set using deterministic chunk IDs and independently verifies the source SHA-256.
- Assets without a user project are assigned to the canonical `Nevolium Documents` system workspace so every ingestion Task still has a valid project boundary.

## Consequences

Parser upgrades can be tested by creating a new generation and comparing outputs. Retrieval can later select a version explicitly or use the latest completed generation without losing provenance. Embeddings, Mem0, Graphiti and future vector/search indexes may project from canonical chunks, but they remain disposable and rebuildable.

Generative enrichment, summarization or entity extraction is deliberately outside this ADR. Any such later stage must pass through Nevolium's replay-safe model gateway, policy and usage accounting instead of being invoked directly by Docling or a projection engine.
