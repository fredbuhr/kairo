# ADR-033 — The 2D mind map is a canonical graph projection, not a second knowledge model

Status: accepted
Date: 2026-09-09

## Context

KAIRO Brain needs a dense 3D mycelium for spatial exploration and a simpler 2D mind-map representation for planning, explanation and day-to-day navigation. A 2D renderer can easily become a competing graph model if it stores its own nodes, invented parent/child relations or persistent drag positions as domain truth.

That would violate the existing graph boundary: KAIRO Core owns the canonical entities and relationships, while presentation engines consume bounded graph projections.

## Decision

The 2D mind map consumes the exact same `KairoGraphProjection` contract as the 3D mycelium and accessible list view.

### Canonical content

Every visible entity comes from a canonical graph node. Every visible semantic connection comes from a canonical graph edge whose provenance remains either:

- `canonical_relationship`; or
- `canonical_fk`.

The 2D view must not silently promote Graphiti/Mem0 facts, local UI grouping or inferred similarity into canonical connections.

### Presentation-only layout tree

A deterministic radial layout derives a temporary spanning tree from the current bounded projection so branches can be placed legibly around a root. The tree parent, branch angle, radial depth and node coordinates are **presentation metadata only**.

The renderer continues to draw all canonical edges, including edges that are not part of the temporary layout tree. Therefore a layout parent must never be interpreted as a KAIRO domain relationship.

The root is selected deterministically:

1. the canonical focused entity when the projection has one;
2. otherwise the most relevant node using existing presentation scores and canonical relationship degree.

### Interaction state

Dragging cards in 2D changes only local viewport state. It does not mutate Projects, Tasks, Relationships, Graphiti, Mem0 or any other canonical/derived knowledge store.

Single selection is shared with the surrounding KAIRO Brain context rail. Double-clicking an entity asks the existing canonical neighborhood endpoint to focus that entity; it does not fabricate a local expansion.

### Shared filtering

Entity/relation filters and explicit branch isolation are applied to the shared graph projection before either renderer receives it. The 3D, 2D and list views therefore represent the same filtered canonical world.

## Consequences

- KAIRO Brain can switch between 3D, 2D mind map and accessible list without synchronization code or duplicate state.
- User-arranged 2D positions remain safe presentation preferences and can later be persisted separately if desired without changing domain truth.
- A future collaborative mind-map editing feature must introduce explicit KAIRO-owned mutation contracts before any new relationship becomes canonical.
- Renderer replacement remains possible because the 2D layout algorithm is a pure projection helper in `@kairo/graph`, not a domain service.
