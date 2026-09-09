# ADR-027 — KAIRO spatial graph is a KAIRO-owned canonical read model

Status: accepted for KAIRO Test Interface v1.

## Context

KAIRO's interface direction makes the mycelium a functional representation of the user's digital world rather than a decorative graph.

The repository already has canonical domain entities and a canonical `relationships` table in PostgreSQL. It also has Graphiti/Neo4j and Mem0, but both are explicitly rebuildable projections. The frontend package `@kairo/graph` previously contained only minimal node/edge interfaces and no KAIRO-owned projection API.

Binding the visual product directly to Neo4j, Graphiti, a force-graph library or a renderer-specific data model would violate KAIRO's replaceability rules and would make it easy for inferred/decorative relationships to become indistinguishable from canonical product state.

## Decision

KAIRO Core owns a spatial graph **read model** over canonical state.

The first API exposes Home, entity-neighborhood and graph-search projections. It returns:

- canonical entity identity and labels;
- explicit canonical `RelationshipRecord` edges;
- canonical structural/foreign-key edges where the relationship is already authoritative in PostgreSQL;
- display-only projection signals such as importance, activity, recency, relationship count, cluster hint and level-of-detail;
- edge provenance and a human-inspectable explanation.

The projection is bounded. The client never requests the complete account graph merely because a 3D renderer can technically accept it.

`@kairo/graph` is the stable TypeScript contract between KAIRO Core, layout logic and renderers. Layout pose/velocity and viewport interaction state are kept separate from canonical entity identity.

Home and KAIRO Brain must use the same graph contract and spatial engine.

## Provenance rule

Visible relationships must declare provenance.

Initial accepted provenance:

- `canonical_relationship` — a canonical `relationships` row;
- `canonical_fk` — an authoritative structural relation already encoded by a canonical foreign key.

Future semantic relationships from Graphiti or other intelligence systems may be displayed only after they have an explicit derived provenance class and the UI can distinguish them from canonical edges. They must not silently enter the canonical graph.

## KAIRO anchor

The central KAIRO symbol is a system/UI anchor, not a fabricated domain record. It may be rendered without being returned as a user-data node by the graph API.

## Consequences

Positive:

- the visual interface cannot accidentally promote a specialist graph engine to system-of-record;
- 2D, 3D, search and future mobile/accessibility views share one data contract;
- renderer/layout technology can change without rewriting KAIRO domain semantics;
- relationship explanations and provenance are available from the beginning;
- large graphs can be server-bounded and context-sensitive.

Costs:

- KAIRO Core must maintain entity resolvers and projection heuristics;
- projection ranking/LOD requires tuning as more entity types appear;
- new canonical entity types must register a graph representation before they become fully spatially visible.

## Non-decision

This ADR does not choose the final force-layout algorithm, shader implementation or WebGL/WebGPU backend. Those are renderer concerns behind `@kairo/graph`.

It also does not make current projection scores canonical fields. Importance/activity/LOD are read-model values and may evolve without data migrations.
