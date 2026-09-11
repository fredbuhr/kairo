# KAIRO platform architecture

This document combines implemented boundaries and target responsibilities. Current maturity is
in [component-matrix](component-matrix.md), current delivery in [status](status.md), and planned
work in [implementation-plan](implementation-plan.md). In particular, realtime persistence,
Desktop/voice, general browser automation and specialist adapters described below remain targets.
The component registry is not a requirement to start every service; D03 assigns optional profiles and isolated production networks; see [deployment](deployment.md).

## Architectural objective

KAIRO is built as a modular personal AI operating system with a **KAIRO-owned shell, domain model, policy boundary and API**, backed by replaceable open-source engines.

The architecture intentionally declares the full dependency graph now. This is not a requirement to expose or actively use every feature immediately; it is a requirement that identity, storage, eventing, security and integration boundaries are correct before feature modules grow around accidental assumptions.

## Runtime topology

```text
Web / Desktop / future mobile
          |
          v
+-------------------------+
|       KAIRO Core        |
| API · Domain · Policy   |
+---+---------+---------+-+
    |         |         |
    |         |         +------> Realtime (Yjs/Hocuspocus)
    |         |
    |         +----------------> PostgreSQL / pgvector
    |                            SeaweedFS
    |                            Neo4j/Graphiti projection
    |
    +--------------------------> Temporal
                                  |
                                  v
                           KAIRO Worker
                    PydanticAI · tools · agents
                                  |
             +--------------------+--------------------+
             |                    |                    |
          LiteLLM              MCP/Apps           Browser/Code
       cloud + local          Activepieces       Playwright/OpenHands
             |
       Ollama/vLLM/etc.

Cross-cutting: NATS · Valkey · OpenBao · Keycloak · Langfuse · ntfy
```

## KAIRO-owned application services

### `kairo-core`
The canonical API and policy boundary. It owns:

- domain mutations;
- authorization and authority evaluation;
- approval requests;
- audit correlation;
- integration registry;
- durable user-visible job/workflow records;
- projection/outbox events;
- API contracts used by every client.

`kairo-core` does **not** run arbitrary agent loops or browser/code execution inside the API process.

### `kairo-worker`
Runs Temporal workers and AI activities:

- PydanticAI agents;
- model requests through LiteLLM;
- Mem0 and Graphiti projection work;
- Docling ingestion;
- browser and MCP activities;
- deterministic scheduled jobs;
- integration calls that have already passed policy checks.

### `kairo-realtime`
Target Hocuspocus/Yjs collaboration plane for documents, mindmaps, Gantt interaction and live
multi-device presence. Canonical authentication/persistence are not implemented yet. D12 must
materialize durable state into KAIRO records; Yjs must not become the domain system of record.

### Shared planning and visual state

G51 supplies Task planning dates/priority. D06 adds scheduling semantics to those canonical Tasks;
the Gantt, calendar, Today and lists are views over the same identities. D07–D09 add editable
knowledge/relationships and 2D/3D projections. Per-user viewport positions, camera and grouping
preferences are separate from domain relations and permissions. A visual rearrangement must not
silently reschedule work or grant access. Derived Graphiti suggestions retain provenance and do
not overwrite user-authored facts/decisions without an explicit accepted mutation.

### `kairo-web`
The customizable Cockpit. Dockable workspaces and shared KAIRO view models prevent each feature from becoming a disconnected app.

### `kairo-desktop`
Tauri desktop shell and Sidecar. It owns local permission prompts and device-level capabilities: global hotkey, microphone, clipboard, screenshots, selected filesystem access, local notifications and approved app/system commands.

## Data planes

### Canonical relational state — PostgreSQL
Authoritative for users, projects, work, people, conversations, agents, policies, approvals, audit, finance metadata, integration configuration references and graph relationships that affect product behavior.

`pgvector` stores embeddings as a rebuildable index beside canonical records.

### Canonical binary/object state — SeaweedFS
Authoritative for attachments, imported source files, generated artefacts, audio retained by policy, screenshots, exports and backup objects.

### Derived temporal context graph — Graphiti + Neo4j
Graphiti maintains temporal semantic relationships and retrieval context. It is a projection from canonical/ingested events and can be rebuilt. Neo4j is selected as the open-source graph backend because Graphiti currently supports it directly and Kuzu is deprecated/archived.

### Derived conversational memory — Mem0
Mem0 holds user/agent memory optimized for retrieval. Memory items retain KAIRO source IDs/provenance whenever possible. Canonical facts and decisions must not exist only inside Mem0.

### Realtime collaborative state — Yjs
Optimizes concurrent editing and presence. Durable snapshots and domain mutations flow back into KAIRO-owned storage.

### Workflow state — Temporal
Temporal is authoritative for in-flight workflow execution semantics. KAIRO remains authoritative for intent, authority, approval, cost budget, user-visible status and resulting domain artefacts.

## Shared execution capacity and bounded reads

D02 uses PostgreSQL WorkAdmission rows and Temporal timers over existing Tasks. Heavy document
and memory activities share global/owner quotas; memory derives its owner from the canonical
conversation. Leases fence canonical reports; owned subprocesses terminate before their capacity
is released. Model money reservations remain a separate ledger that retains uncertain obligations.
No extra broker or queue service is introduced. Core and Workers must run compatible revisions.

Collection APIs apply ownership before keyset LIMIT and expose continuation cursors. Today queries
each mutually exclusive bucket separately. Web consumers request further pages explicitly and
resolve selected records by identity. Bounded memory rebuild pages carry a fixed watermark and
transactional audit receipts, allowing recovery after a lost response without double generation.
Outbox claims are short SQL transactions; network publication holds no database connection.
Published transport history has finite retention; canonical records and financial obligations are
preserved. Limits, observability, upgrade and replay procedures are in `docs/operations.md`.

## Eventing

KAIRO uses a transactional outbox in PostgreSQL and publishes committed domain events to NATS JetStream.

Rules:

1. domain writes and outbox records commit together;
2. consumers are idempotent;
3. projections may be rebuilt from canonical data/events;
4. an event is not permission to perform an external action;
5. external actions require a policy decision tied to a workflow/activity.

## Durable execution

Temporal replaces the V0 scheduler/job-recovery mechanism.

Every significant autonomous workflow carries:

- intent and originating entity IDs;
- actor/agent ID;
- allowed capabilities;
- authority ceiling;
- budget/cost ceiling;
- idempotency keys for side effects;
- approval checkpoints where required;
- expected result/artefact contract;
- retry/timeout policy;
- audit correlation ID.

## Model plane

All general model traffic uses LiteLLM as the provider boundary. The worker asks KAIRO routing policy for a task class/quality/risk budget, then calls a logical model alias rather than provider-specific names.

Local tiers:

- Ollama for simple local deployment;
- llama.cpp for edge/desktop-native inference where useful;
- vLLM for dedicated GPU serving.

Provider-specific capabilities remain available through adapters when needed, but they cannot leak into the canonical domain schema.

## Automation and tools

### MCP
Primary capability protocol for AI-callable tools and integrations.

### Activepieces
External SaaS/webhook automation and connector engine. Its flow state belongs to Activepieces; KAIRO stores the automation identity, policy, trigger relationship and user-visible execution linkage.

### Browser
Playwright is preferred for deterministic browser tasks; Browser Use is used when AI-driven navigation is genuinely needed.

### Software development
OpenHands is a specialized development engine invoked behind a KAIRO adapter and sandbox boundary. KAIRO owns repository intent, permissions, task state, approvals and produced diffs/artifacts.

## Identity and secrets

- Keycloak is the identity/SSO provider boundary.
- OpenBao holds service and integration secrets.
- applications receive scoped short-lived credentials where possible.
- database rows store secret references, never raw secrets.
- the local Sidecar has its own device registration and permission grants.

## Observability

Langfuse records AI traces/evaluations; OpenTelemetry-compatible service telemetry is the long-term transport for application metrics/traces. KAIRO's own audit log is separate and authoritative for security/user accountability.

## Deployment profiles

The repository defines every selected component immediately, but specialized engines can be activated with Compose profiles when their security or hardware footprint justifies isolation:

- `finance`: rotki, Actual Budget, optional Hummingbot;
- `home`: Home Assistant;
- `dev-agent`: OpenHands;
- `gpu`: vLLM;
- `remote`: Headscale;
- `ops`: backup/maintenance jobs.

This keeps dependencies explicit without forcing every development laptop to run every heavyweight process continuously.

## Replaceability rule

Every engine has a KAIRO adapter or protocol boundary. Replacing Mem0, Graphiti, Activepieces, LiteLLM, the Gantt renderer or a model provider must not require rewriting the canonical domain model.


## D03 deployment boundaries

[ADR-028](decisions/ADR-028-production-boundaries-and-optional-topology.md) defines production settings,
JWT claims, separate SQL identities/migration and operator rebuild authority. The static Web has no
canonical network access. Worker/MCP public HTML connects validated IPs with origin Host/SNI, bounded
streaming and no ambient proxy. Resource ceilings and shutdown do not constitute a hostile-code sandbox.
The model-byte inventory is separate from container pins and from D04 real-engine compatibility evidence.
