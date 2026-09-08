# ADR-019 — Rebuildable memory and temporal-context projections

**Status:** accepted — 2026-09-08

## Context

KAIRO needs useful long-lived memory and temporal context, but Mem0 and Graphiti/Neo4j must not become alternate systems of record. The permanent data-ownership rule is that canonical user/domain state belongs to KAIRO Core in PostgreSQL; specialist intelligence stores are replaceable accelerators and views.

A projection system also has to survive at-least-once event delivery, Worker restarts and deliberate destruction/rebuild of derived stores. Re-running a completed Temporal Task under the same Task/Workflow identity is not sufficient for a true rebuild.

## Decision

Canonical `ConversationMessage` insertion emits `conversation.message.created` through the same PostgreSQL transaction/outbox boundary as other domain events. The event carries stable references only; it does not duplicate message content into JetStream. The Worker fetches the canonical source from Core before projecting it.

Each source message has two tracked projectors in canonical PostgreSQL:

- `mem0` for searchable vector memory;
- `graphiti` for temporal episodic context in Neo4j.

Core owns a projection generation. Generation `N` maps to a deterministic `memory.project` Task and Temporal Workflow. A rebuild advances the generation, resets only projection tracking and republishes the canonical source reference. Old/stale generation deliveries are ignored and cannot roll the current generation backwards.

Mem0 is configured as a raw projection with `infer=False`. It embeds the canonical message locally and stores it in an isolated PostgreSQL `mem0` database with pgvector. It is deliberately given an unreachable LLM endpoint so an accidental direct generative call fails closed. No Mem0-owned model call is permitted to bypass KAIRO's model gateway.

Graphiti is used at its low-level Neo4j episode boundary for this first slice: the canonical message UUID is the episode UUID and the canonical timestamp is the temporal validity timestamp. Entity/fact extraction is not enabled yet because Graphiti's high-level ingestion path performs model calls. Future generative graph extraction must be implemented through KAIRO's replay-safe/accounted `model_gateway` rather than through a Graphiti-owned provider client.

The CI integration uses deterministic stub projectors when intelligence extras are absent. This proves event delivery, deterministic Task handoff, projection generations, idempotency and canonical-data immutability without public network or model dependencies.

## Consequences

- PostgreSQL KAIRO tables remain the only source needed to rebuild conversation memory.
- The entire Mem0 database and Neo4j graph may be deleted without losing canonical conversation data.
- Rebuilds create new durable execution identities without duplicating canonical source records.
- At-least-once JetStream delivery is safe because Core owns deterministic Tasks and unique source/projector projection rows.
- Projection status and failures are inspectable in Core even when a specialist store is unavailable.
- The first memory slice is intentionally less semantically rich than LLM-extracted memory; safety, rebuildability and provider accounting are established before adding extraction.
