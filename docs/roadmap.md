# KAIRO roadmap

The roadmap is aligned with the implementation blocks in [`implementation-plan.md`](implementation-plan.md), but this file reflects the **current sequencing from canonical `main`**.

## Current sequencing — 2026-09-11

The platform/system-of-record foundation is complete, the core Block 2 intelligence/autonomy exit has been reached, and **G51 Daily Spine is integrated in `main`**.

Current work is **Repository Reset**, not new product development.

- R0 — establish repository truth: complete;
- R1 — install `AGENTS.md` + `PROJECT_STATE.md`: complete;
- R2 — validate and promote G51 / PR #73: complete;
- R3 — synchronize canonical status/roadmap/component maturity: complete;
- R4 — inventory branches and PRs: complete;
- R5a/R5b/R5c — close/remove superseded Git refs: complete;
- R6 — inventory files/directories and archive true historical evidence: complete;
- R7 — create a clean tagged baseline with green CI: next.

R6 found no safely removable active implementation files; intentional scaffolds remain explicit and one dated implementation audit was moved to the historical archive. No Gantt, Calendar, Brain, Finance/Crypto, voice or other new product slice should start before R7.

## Foundation

**Status: complete for current development scope.**

PostgreSQL/pgvector, object storage, eventing, identity, secrets, Temporal, canonical migrations, recovery and core service topology are established as the permanent substrate.

Production hardening continues later; “foundation complete” does not mean commercial production-ready.

## System of record

**Status: complete.**

PostgreSQL remains authoritative for domain state. SeaweedFS owns binary objects behind KAIRO references. NATS events are derived from the transactional outbox. Temporal owns in-flight workflow execution rather than replacing canonical business state.

## Intelligence and autonomy

**Status: core exit reached and integrated.**

The canonical line includes LiteLLM routing/accounting, PydanticAI routing/agents, rebuildable memory projections, Docling ingestion, MCP tools, bounded Research, policy/approval/budget boundaries and destructive replay tests.

Later deepening of browser automation, automation engines and specialist agents must reuse the same Task/Artifact/policy/audit ownership contracts rather than inventing parallel control planes.

## Cockpit and planning

**Status: G51 Daily Spine integrated; major Block 3 work remains.**

Already present:

- Cockpit shell and subject-scoped workspace layouts;
- Projects;
- Today;
- Research;
- News;
- Knowledge ingestion/search/inspection;
- canonical Task priority/planning/due fields;
- owner-scoped planning updates;
- timezone-aware Today semantics.

After Repository Reset, continue Block 3 in this order:

1. **Gantt + Calendar** directly on the G51 Task planning model;
2. **2D/3D Brain / graph** on canonical Relationships and derived knowledge context;
3. **collaboration/realtime** with canonical persistence;
4. **universal search** across Projects, Tasks, documents, knowledge and graph surfaces.

Do not treat installed UI dependencies as completed capabilities: the current Gantt and graph packages are still scaffolds.

## Presence and devices

**Status: architecture/scaffolding only.**

Build the Tauri Sidecar, bounded local permissions, notifications, microphone/screen/clipboard/filesystem access, voice orchestration, global summon and private cross-device presence only after Block 3 shares stable canonical state.

## Specialist systems

**Status: declared/configured engines; stable product integrations not complete.**

Integrate OpenHands, Finance/Crypto engines and Home Assistant behind KAIRO-owned domain, policy, approval, secret and audit contracts.

Optional Compose profiles are not considered product completion.

## Production hardening

**Status: continuous; commercial readiness not reached.**

Remaining work includes:

- complete dependency lock/reproducibility policy;
- immutable image/SBOM controls;
- stronger sandboxing;
- controlled upgrades and rollback;
- off-host encrypted backup drills;
- load/performance testing;
- production TLS/network exposure policy;
- observability/alerting maturity;
- complete data lifecycle and erasure behavior.

## Architectural rule

The component registry is intentionally broader than the current implementation. A component may be declared early so dependencies, licensing and ownership boundaries are explicit.

Roadmap sequencing controls **implementation depth**, not whether an eventual dependency is acknowledged. Component maturity is tracked separately in [`component-matrix.md`](component-matrix.md).
