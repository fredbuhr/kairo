# ADR-028 — Stable, batched spatial rendering

Status: accepted for KAIRO Test Interface v1.

## Context

KAIRO Home and KAIRO Brain are intended to become a familiar spatial environment rather than a graph that re-randomizes on every refresh. The renderer must also remain responsive when a contextual projection contains tens or hundreds of visible entities and relationships.

A naive Three.js implementation creates one mesh/tube/material per node and edge. That scales poorly in draw calls and makes future visual refinement expensive. Likewise, recalculating a force layout from a cold deterministic seed on every query refresh causes technically deterministic but perceptually disruptive movement.

## Decision

KAIRO's product mycelium uses one renderer and one graph contract, with the following rules:

1. **Nodes are instanced.** Visible canonical entities share instanced geometry/material paths. Selection, focus, activity and dimming are expressed through per-instance transforms/colors rather than one mesh hierarchy per entity.
2. **Filaments are batched.** Visible canonical relationships are sampled as multiple subtle curved strands in shared line geometries. A small bounded number of activity effects may use separate/instanced geometry, but the base graph must not require one draw call per edge.
3. **Activity pulses are event-driven.** Pulses receive short-lived entity keys from the sanitized canonical activity stream. They are not random ambient traffic. Decorative breathing may remain, but semantic activity animation must trace real KAIRO events.
4. **Clusters are visual gravity wells, not category menus.** Shared clustering is driven by canonical/contextual cluster hints (primarily project scope) and real relationship springs. Unscoped entities receive private deterministic wells; KAIRO must not group all Tasks, all Conversations, etc. merely by type.
5. **Spatial layout is warm-started.** The client caches stable poses per projection context. Query refreshes reuse the previous positions, and the Worker receives those poses as its initial state so new data settles locally instead of rebuilding the world from scratch.
6. **Focused contexts preserve continuity.** When entering an entity neighborhood for the first time, known positions are translated around the focused entity before local relaxation. Returning to a previously visited Home/focus context restores that context's cached layout.
7. **Semantic zoom remains data-aware.** Camera distance changes the LOD band; focus, selection, direct neighbors and recently active entities may be forced visible even when their normal LOD would hide them.
8. **Labels are bounded.** Only a small importance-ranked subset receives spatial labels. Hover/selection and the accessible list remain the detailed inspection mechanisms.
9. **Reduced motion is first-class.** Ambient emergence/breathing and camera transitions are disabled or collapsed when reduced motion is requested; essential navigation remains available without relying on animation.

## Consequences

- The 3D scene stays visually organic without requiring fake entities or decorative edges.
- Draw-call growth is substantially slower than entity/relationship count growth.
- A graph refresh should feel like the existing world adapting, not a new graph being generated.
- Home and KAIRO Brain can share the same engine while using different projection depth/limits.
- The renderer can later migrate individual layers to custom shaders/WebGPU without changing the canonical graph API or product shell.

## Non-goals

This ADR does not make arbitrary graph sizes renderable. KAIRO Core must still return bounded contextual projections and the client must still apply LOD/filtering. PostgreSQL remains canonical; the spatial cache is presentation state only and may be discarded/rebuilt at any time.
