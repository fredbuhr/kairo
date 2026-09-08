# Component matrix

The component list is declared early to make dependencies and ownership explicit. Inclusion here does not mean every process must run on every laptop continuously.

| Capability | Component | Mode | KAIRO ownership rule |
|---|---|---|---|
| Canonical database | PostgreSQL + pgvector | service | authoritative domain state; vectors rebuildable |
| Temporal context graph | Graphiti + Neo4j | worker library + service | derived projection only |
| Cache/locks | Valkey | service | ephemeral only |
| Event bus | NATS JetStream | service | events from transactional outbox |
| Object storage | SeaweedFS | service | authoritative binary objects |
| Durable workflows | Temporal | service + SDK | runtime execution authority, correlated to KAIRO records |
| Agent framework | PydanticAI | worker library | agents act under KAIRO policy |
| Model gateway | LiteLLM | service | provider abstraction/routing boundary |
| Local model simple | Ollama | service | model provider only |
| Local model edge | llama.cpp | sidecar/host | model provider only |
| Local model GPU | vLLM | `gpu` profile | model provider only |
| Long-term memory | Mem0 | worker library | derived memory projection |
| Document parsing | Docling | worker library | produces canonical sources/assets |
| External automation | Activepieces | service | engine state delegated; KAIRO owns intent/policy/run link |
| Tool protocol | MCP | protocol | preferred AI tool boundary |
| Deterministic browser | Playwright | worker/sandbox | side effects policy-gated |
| AI browser | Browser Use | worker/sandbox | side effects policy-gated |
| Dev agent | OpenHands | `dev-agent` profile | KAIRO owns task/approval/diff references |
| Search | SearXNG | service | results become sourced research records |
| Secrets | OpenBao | service | secret values never stored in domain DB |
| Identity | Keycloak | service | authentication provider; KAIRO owns domain permissions |
| AI observability | Langfuse + ClickHouse | services | tracing/eval; not security audit source |
| Notifications | ntfy | service | delivery adapter |
| Realtime docs | Hocuspocus + Yjs | KAIRO service/library | realtime state materialized to canonical state |
| Voice realtime | LiveKit | service | transport only |
| Speech-to-text | whisper.cpp | sidecar/worker | local transcription engine |
| Voice activity | Silero VAD | sidecar library | local signal processing |
| Wake word | openWakeWord | sidecar library | custom KAIRO model preferred |
| Desktop runtime | Tauri | app | KAIRO-owned Sidecar trust boundary |
| Workspace shell | Dockview + shadcn/ui | web libraries | KAIRO UX |
| Data views | TanStack Table/Query | web libraries | KAIRO UX |
| Drag/drop | dnd-kit | web library | KAIRO UX |
| Rich text | Lexical | web library | canonical document model/snapshots |
| Whiteboard | Excalidraw | web library | assets/doc objects linked to domain |
| Calendar UI | Schedule-X | web library | view over normalized calendar state |
| Dashboards | Apache ECharts | web library | view only |
| Maps | MapLibre GL JS | web library | view over place/location state |
| 2D graph | React Flow | web library | view over KAIRO graph |
| 3D graph | React Three Fiber + react-force-graph-3d | web libraries | view over KAIRO graph |
| Gantt | SVAR React Gantt | web library | renderer/editor over KAIRO Plan/Task data |
| Crypto accounting | rotki | `finance` profile | portfolio source/adapter, private network only |
| Exchange APIs | CCXT | integration library | no raw secret exposure to models |
| EVM | viem | web/worker library | prepare/read; signing isolated |
| Trading engine | Hummingbot | `finance` profile | disabled for live authority by default |
| Personal finance | Actual Budget | `finance` profile | external ledger adapter |
| Smart home | Home Assistant | `home` profile | upstream device authority |
| Sandbox | gVisor | host runtime | hardened execution boundary |
| Backup | restic | `ops`/host | encrypted off-host backup |
| Private access | Headscale | `remote` profile | private network overlay |
| Deployment UI | Coolify (optional) | host platform | deployment convenience, not KAIRO dependency |

## Deliberately not foundational

- Open WebUI: useful for model/admin testing, not the KAIRO frontend foundation.
- n8n: avoided as the central automation dependency; Activepieces is the selected automation engine.
- FalkorDB: not selected due licensing concerns; Neo4j Community is the Graphiti backend.
- Kuzu: not selected because the project is archived/deprecated for this use.
- OpenClaw: the V0 proof runtime is removed from the target architecture; its durable-execution lessons are carried forward into Temporal and KAIRO policy contracts.
