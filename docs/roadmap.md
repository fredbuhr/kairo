# KAIRO roadmap

The roadmap is intentionally aligned with the large implementation blocks in [`implementation-plan.md`](implementation-plan.md).

## Current sequencing — 2026-09-11

The platform/system-of-record block is complete and the core intelligence/autonomy exit has been reached on the validated G49 baseline. Current work is a short consolidation gate before deeper Cockpit/planning work: reproducibility debt is being made explicit, documentation is being synchronized with the code, and the validated line will be promoted before new specialist surface is added.

## Foundation

Reset the repository around the complete permanent platform architecture and component dependency graph. Remove the OpenClaw/filesystem proof implementation from the target branch while retaining its lessons in architecture contracts and Git history.

## System of record

**Status: complete.**

Bring up PostgreSQL/pgvector, object storage, eventing, identity, secrets, Temporal and backups as one coherent substrate. Establish migrations, outbox events, health and recovery before higher-level modules depend on them.

## Intelligence and autonomy

**Status: core exit reached; consolidation in progress.**

Add LiteLLM routing/cost control, PydanticAI agents, rebuildable memory/context projections, Docling ingestion, MCP tools, research, policy/approval boundaries and durable Temporal replay semantics. General browser automation and Activepieces-specific workflows can deepen later when required by concrete product slices, but must use the same canonical policy/Task/Artifact/audit boundaries.

## Cockpit and planning

**Status: early foundation present; next major product block.**

Build the customizable KAIRO interface, universal project/knowledge views, realtime documents, 2D/3D mindmap, Gantt/scheduling, calendar, dashboards, maps and universal search.

The implementation order after consolidation is: Projects/Tasks/Today first, then Gantt/calendar planning, then the 2D/3D Brain/graph, followed by collaboration and universal search.

## Presence and devices

Build the Tauri Sidecar, voice plane, local permissions, cross-device presence, notifications and private remote connectivity.

## Specialist systems

Integrate OpenHands, crypto/finance engines and Home Assistant behind the same KAIRO domain/policy/audit contracts.

## Production hardening

Harden sandboxing, backups, observability, upgrades, immutable dependency/SBOM policy, self-maintenance proposals, recovery, resource control and data lifecycle.

The component registry is complete from the beginning; roadmap sequencing controls **implementation depth**, not whether a dependency is acknowledged.
