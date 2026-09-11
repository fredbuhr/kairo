# ADR-012 — PostgreSQL is Nevolium's canonical operational store

**Status:** Accepted

## Decision

PostgreSQL is the canonical store for Nevolium domain and operational state. pgvector is used for colocated rebuildable embeddings. SeaweedFS stores canonical binary objects.

Graphiti/Neo4j, Mem0, Yjs and search/vector indexes are projections or specialized runtime state, not independent product sources of truth.

## Rationale

A unified relational source with transactions, constraints and outbox support provides a stable backbone for project/task/permission/audit/finance relationships while allowing specialized projections without data ownership ambiguity.
