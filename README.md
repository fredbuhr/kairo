# Nevolium

Nevolium is a self-hosted **Personal AI Operating System**: one coherent interface and domain model for projects, knowledge, tasks, communication, agents, automation, finance, crypto, devices, voice, research, development and personal operations.

Nevolium is not a chatbot wrapper and it is not a fork of another assistant. Nevolium owns the user experience, system-of-record, policy model and integration contracts; specialized open-source engines remain replaceable behind those boundaries.

## Current delivery line — September 2026

Repository Reset R0–R7 is complete; G51 planning foundations, H1–H3 and the H4 Task-dispatch
isolation repair are integrated. D01–D03 (#84–#87) complete the assigned H4 controls; D04/H5 real-engine and operations evidence precedes new product features.
The current Web cockpit exists; the complete Mycelium 3D, editable mindmaps and Gantt are planned,
not delivered merely by installing their rendering libraries.

Start with [PROJECT_STATE.md](PROJECT_STATE.md) for live recovery, the
[detailed D01–D22 plan](docs/implementation-plan.md) for delivery scope, and the
[development/recovery protocol](docs/development-workflow.md) when changing conversations.
See the [deployment and profiles guide](docs/deployment.md) for minimal startup, SQL identities,
production checks, model assets and upgrades. Optional engines no longer start as a mandatory bundle.

## Architecture history

The original V0 proved several important properties with an OpenClaw-based runtime and a filesystem/Markdown domain store: durable project capture, explicit epistemic status, background execution, restart recovery, conservative failure behavior and the need for replay-safe autonomous actions.

Those experiments achieved their purpose. The repository reset established the permanent platform architecture instead of extending the V0 runtime.

The component registry records the wider target architecture. Runtime activation and implementation
follow proven needs and the delivery plan; configured components do not all need to run by default.

## Nevolium-owned layers

```text
Nevolium Web / Desktop / Mobile
            |
       Nevolium Core API
            |
   +--------+---------+
   |                  |
Policy + Domain    Intelligence
   |                  |
   +--------+---------+
            |
      Durable Workflows
            |
     Integration Adapters
            |
 Open-source engines / APIs
```

Nevolium itself owns:

- the Cockpit and design system;
- the canonical domain model and graph semantics;
- identity, permissions, approval and authority policy;
- durable audit and provenance;
- the relationship between projects, people, tasks, documents, conversations, agents, assets, finances and devices;
- orchestration rules and stable adapter contracts;
- the desktop Sidecar and local-device permission boundary.

## Platform foundation

The target foundation includes, from the start:

- **PostgreSQL + pgvector** — authoritative operational/domain state and semantic indexes;
- **Neo4j + Graphiti** — derived temporal knowledge graph;
- **Valkey** — cache, locks and ephemeral coordination;
- **NATS JetStream** — event bus;
- **SeaweedFS** — S3-compatible object storage;
- **Temporal** — durable workflows and crash-safe execution;
- **LiteLLM** — provider/model gateway and routing boundary;
- **PydanticAI** — Nevolium agent framework;
- **Mem0** — derived long-term conversational memory;
- **Docling** — document ingestion;
- **Activepieces** — external automation/connectors;
- **MCP** — common tool/plugin contract;
- **Browser Use + Playwright** — web action and deterministic browser automation;
- **OpenHands** — software-development agents;
- **Ollama / llama.cpp / vLLM** — local inference tiers;
- **Hocuspocus + Yjs** — realtime collaborative state;
- **OpenBao** — secrets;
- **Keycloak** — identity/SSO boundary;
- **Langfuse + ClickHouse** — AI observability and evaluation;
- **SearXNG** — private web metasearch;
- **ntfy** — self-hosted notifications;
- **LiveKit + local voice components** — realtime voice plane;
- **rotki + CCXT + viem + optional Hummingbot** — crypto portfolio and execution boundary;
- **Actual Budget** — personal finance adapter;
- **Home Assistant** — home/device integration boundary;
- **restic, gVisor, Headscale** — backup, sandboxing and private remote access.

Frontend engines include Dockview, shadcn/ui, TanStack, Lexical, Excalidraw, Schedule-X, Apache ECharts, MapLibre, React Flow, React Three Fiber, 3D force graph rendering, SVAR React Gantt and Yjs.

See [`docs/component-matrix.md`](docs/component-matrix.md) for ownership and deployment mode.

## Repository shape

```text
apps/
  web/              Nevolium Cockpit
  desktop/          Tauri Sidecar/Desktop shell
services/
  core/             canonical API, policy and domain
  worker/           Temporal workers + AI execution
  realtime/         Hocuspocus/Yjs collaboration
packages/
  protocol/         stable contracts/types/events
  ui/               Nevolium design system
  graph/            2D/3D graph views
  gantt/            scheduling/Gantt UX
config/
  components.yaml   complete component registry
infrastructure/
  postgres/
  keycloak/
  litellm/
  openbao/
  livekit/
  ...
compose.yaml                 integrated development topology
compose.override.yaml        local-only bootstrap/development behavior
compose.production.yaml      production trust-boundary overlay
compose.ops.yaml             backup/restore operations overlay
.env.production.example      production configuration template without secrets
```

## Architectural rule

**No specialist engine becomes Nevolium's system of record.** PostgreSQL and Nevolium-owned object storage hold canonical product state. Search indexes, vector indexes, Graphiti, Mem0, realtime documents and third-party tools are projections or adapters that can be rebuilt or replaced.

The only exception is workflow execution state while a workflow is actively owned by Temporal; Nevolium stores its correlation, intent, policy, audit trail and resulting artefacts.

## Security rule

Technical capability is never equivalent to authority. Every external or sensitive action passes through the Nevolium policy/approval boundary. Private wallet keys and raw secrets never enter an LLM context.

See [`docs/security-model.md`](docs/security-model.md).

## Development and operations

Local development keeps its reproducible Keycloak/OpenBao bootstrap in `compose.override.yaml`. Production trust-sensitive behavior is deliberately isolated in `compose.production.yaml`; it does not reuse the development Keycloak fixture or OpenBao dev mode.

Useful validation and recovery commands:

```bash
make config       # validate local development topology
make prod-template # check template syntax only
make prod-config  # check the real private .env.production (placeholders are rejected)
make ops-config   # validate production + Restic operations topology
make backup       # quiesced Restic snapshot using the selected environment/overlay
```

Restore is destructive and requires `NEVOLIUM_CONFIRM_RESTORE=YES`. See [`docs/operations.md`](docs/operations.md) before running it.

## Implementation

The implementation plan uses bounded D01–D22 deliveries with prerequisites, observable exits and
recovery criteria. See [`docs/implementation-plan.md`](docs/implementation-plan.md).

Active branch/PR and next action: [`PROJECT_STATE.md`](PROJECT_STATE.md).
Implemented capabilities and limitations: [`docs/status.md`](docs/status.md).
