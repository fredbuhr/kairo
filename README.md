# KAIRO

KAIRO is a self-hosted **Personal AI Operating System**: one coherent interface and domain model for projects, knowledge, tasks, communication, agents, automation, finance, crypto, devices, voice, research, development and personal operations.

KAIRO is not a chatbot wrapper and it is not a fork of another assistant. KAIRO owns the user experience, system-of-record, policy model and integration contracts; specialized open-source engines remain replaceable behind those boundaries.

## Architecture reset — September 2026

The original V0 proved several important properties with an OpenClaw-based runtime and a filesystem/Markdown domain store: durable project capture, explicit epistemic status, background execution, restart recovery, conservative failure behavior and the need for replay-safe autonomous actions.

Those experiments achieved their purpose. The target product is now broader, so the repository is being reset around the full platform architecture from the beginning instead of extending the V0 runtime.

The new foundation deliberately includes the complete dependency graph early so integrations, identity, storage, authorization, eventing, observability, realtime collaboration, model routing and durable execution are designed together rather than retrofitted later.

## KAIRO-owned layers

```text
KAIRO Web / Desktop / Mobile
            |
       KAIRO Core API
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

KAIRO itself owns:

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
- **PydanticAI** — KAIRO agent framework;
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
  web/              KAIRO Cockpit
  desktop/          Tauri Sidecar/Desktop shell
services/
  core/             canonical API, policy and domain
  worker/           Temporal workers + AI execution
  realtime/         Hocuspocus/Yjs collaboration
packages/
  protocol/         stable contracts/types/events
  ui/               KAIRO design system
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

**No specialist engine becomes KAIRO's system of record.** PostgreSQL and KAIRO-owned object storage hold canonical product state. Search indexes, vector indexes, Graphiti, Mem0, realtime documents and third-party tools are projections or adapters that can be rebuilt or replaced.

The only exception is workflow execution state while a workflow is actively owned by Temporal; KAIRO stores its correlation, intent, policy, audit trail and resulting artefacts.

## Security rule

Technical capability is never equivalent to authority. Every external or sensitive action passes through the KAIRO policy/approval boundary. Private wallet keys and raw secrets never enter an LLM context.

See [`docs/security-model.md`](docs/security-model.md).

## Development and operations

Local development keeps its reproducible Keycloak/OpenBao bootstrap in `compose.override.yaml`. Production trust-sensitive behavior is deliberately isolated in `compose.production.yaml`; it does not reuse the development Keycloak fixture or OpenBao dev mode.

Useful validation and recovery commands:

```bash
make config       # validate local development topology
make prod-config  # validate production overlay
make ops-config   # validate production + Restic operations topology
make backup       # quiesced Restic snapshot using the selected environment/overlay
```

Restore is destructive and requires `KAIRO_CONFIRM_RESTORE=YES`. See [`docs/operations.md`](docs/operations.md) before running it.

## Implementation

The implementation plan is organized by large coherent platform blocks rather than dozens of micro-phases. See [`docs/implementation-plan.md`](docs/implementation-plan.md).

Current branch status is tracked in [`docs/status.md`](docs/status.md).
