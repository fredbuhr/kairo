# ADR-006 — Use a filesystem/Markdown domain store before choosing a database

## Status

Accepted for V0 prototype.

## Context

KAIRO requires durable, human-readable project knowledge and a graph-oriented domain model, but the real access patterns are not yet known. Selecting PostgreSQL, a graph database, a vector database, or a queue before the first domain slice would add infrastructure without evidence that it is needed.

KAIRO also has a strong portability requirement: important project knowledge must remain understandable outside the application.

## Decision

Implement the first KAIRO Core storage adapter as a dependency-free filesystem store:

- stable UUID-based IDs;
- one project directory per project slug;
- Markdown documents with explicit front matter metadata;
- atomic replace/write behavior for individual files;
- runtime-private data directory outside Git;
- a domain API that does not expose filesystem paths to callers.

The initial adapter supports projects, ideas, decisions, tasks, knowledge claims, and sources.

This is a **prototype storage adapter**, not a statement that flat files are the final operational database.

## Consequences

### Positive

- no database service is required for the first vertical slice;
- the stored knowledge is directly inspectable and Obsidian-compatible in spirit;
- tests remain simple and deterministic;
- the domain API can be exercised before database schema decisions;
- migration later can be driven by measured access patterns.

### Limitations

- filesystem scans do not scale to very large collections;
- concurrent multi-writer semantics are intentionally limited;
- rich graph traversal, full-text search, embeddings, job queues, and transactional updates are not solved here;
- runtime-private filesystem backups become important as soon as real data is stored.

## Revisit when

Choose a structured operational database when one or more of these become real constraints:

- concurrent writers;
- graph traversal latency;
- full-text/vector search needs;
- job/approval transactionality;
- analytics and time-series queries;
- multi-user isolation;
- recovery semantics that require transactions.

Any replacement must preserve stable domain IDs and human-readable export.
