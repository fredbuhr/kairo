# KAIRO roadmap

The roadmap is intentionally aligned with the large implementation blocks in [`implementation-plan.md`](implementation-plan.md).

## Foundation

Reset the repository around the complete permanent platform architecture and component dependency graph. Remove the OpenClaw/filesystem proof implementation from the target branch while retaining its lessons in architecture contracts and Git history.

## System of record

Bring up PostgreSQL/pgvector, object storage, eventing, identity, secrets, Temporal and backups as one coherent substrate. Establish migrations, outbox events, health and recovery before higher-level modules depend on them.

## Intelligence and autonomy

Add LiteLLM routing/cost control, PydanticAI agents, Mem0, Graphiti, Docling, MCP, browser/research tools, Activepieces and approval-gated Temporal workflows.

## Cockpit and planning

Build the customizable KAIRO interface, universal project/knowledge views, realtime documents, 2D/3D mindmap, Gantt/scheduling, calendar, dashboards, maps and universal search.

## Presence and devices

Build the Tauri Sidecar, voice plane, local permissions, cross-device presence, notifications and private remote connectivity.

## Specialist systems

Integrate OpenHands, crypto/finance engines and Home Assistant behind the same KAIRO domain/policy/audit contracts.

## Production hardening

Harden sandboxing, backups, observability, upgrades, self-maintenance proposals, recovery, resource control and data lifecycle.

The component registry is complete from the beginning; roadmap sequencing controls **implementation depth**, not whether a dependency is acknowledged.
