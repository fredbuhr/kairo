# Component matrix

The component registry is intentionally broader than the currently implemented product. Presence in `config/components.yaml`, `compose.yaml` or a package manifest does **not** mean the capability is complete.

D02 (#85/#86) adds validated shared admission, bounded SQL/Web pages, recoverable memory batches
and finite transport retention. PostgreSQL and JetStream behavior and controlled child lifecycles
are covered by the exact-head CI recorded in PROJECT_STATE. This does not promote the real
Docling/Mem0/Graphiti engines or the future graphical workspaces to validated product capabilities.

## Maturity legend

- **Validated** — KAIRO integration is exercised by the current canonical CI/product path.
- **Integrated** — KAIRO code/adapters use the component, but the end-user capability or production hardening is not complete.
- **Configured** — dependency/service is wired into manifests or Compose, but no stable KAIRO product workflow is complete.
- **Scaffold** — placeholder contracts/package/application skeleton exists.
- **Declared** — architectural target only on canonical `main`.

The maturity column describes the **KAIRO integration**, not the upstream project's own maturity.

Validation is scenario-specific: controlled text fallback and memory stubs do not prove real
Docling/Mem0/Graphiti execution. D04 supplies that missing evidence. Future delivery lots are
mapped in [implementation-plan](implementation-plan.md); present progress lives in [PROJECT_STATE](../PROJECT_STATE.md).

| Capability | Component | Mode/profile | KAIRO ownership rule | Current maturity |
|---|---|---|---|---|
| Canonical database | PostgreSQL + pgvector | service / core | authoritative domain state; vectors rebuildable | **Validated** |
| Temporal context graph | Graphiti + Neo4j | worker library + service / core | derived projection only | **Integrated** |
| Cache/locks | Valkey | service / core | ephemeral only | **Configured** |
| Event bus | NATS JetStream | service / core | events from transactional outbox | **Validated** |
| Object storage | SeaweedFS | service / core | authoritative binary objects | **Validated** |
| Durable workflows | Temporal | service + SDK / core | in-flight execution authority correlated to KAIRO records | **Validated** |
| Agent framework | PydanticAI | worker library / core | agents act under KAIRO policy | **Validated** |
| Model gateway | LiteLLM | service / core | provider abstraction/routing boundary | **Validated** |
| Local model simple | Ollama | service / core | model provider only | **Configured** |
| Local model edge | llama.cpp | sidecar/host / desktop | model provider only | **Declared** |
| Local model GPU | vLLM | service / `gpu` | model provider only | **Configured** |
| Long-term memory | Mem0 | worker library / core | derived memory projection | **Integrated** |
| Document parsing | Docling | worker library / core | produces canonical document/chunk provenance | **Integrated; deterministic text fallback validated, real engine pending D04** |
| External automation | Activepieces | service / `automation` | delegated engine; KAIRO owns intent/policy/run link | **Configured** |
| Tool protocol | MCP | protocol / core | preferred AI tool boundary | **Validated** |
| Deterministic browser | Playwright | future browser boundary | side effects policy-gated | **Declared; unused direct Worker dependency retired in D03** |
| AI browser | Browser Use | future browser boundary | side effects policy-gated | **Declared; unused direct Worker dependency retired in D03** |
| Dev agent | OpenHands | service / `dev-agent` | KAIRO owns task/approval/diff references | **Configured** |
| Search | SearXNG | service / `search` | sourced search adapter, never canonical truth | **Integrated** |
| Secrets | OpenBao | service / core | secret values never stored in domain DB | **Validated** |
| Identity | Keycloak | service / core | authentication provider; KAIRO owns domain permissions | **Validated** |
| AI observability | Langfuse + ClickHouse | services / `observability` + overlay | tracing/eval projection; not security audit source | **Configured** |
| Notifications | ntfy | service / `notifications` | delivery adapter | **Configured** |
| Realtime docs | Hocuspocus + Yjs | `collaboration-experimental` | realtime state must materialize to canonical state | **Scaffold / configured** |
| Voice realtime | LiveKit | `voice-experimental` | transport only | **Configured** |
| Speech synthesis | Kokoro-FastAPI | service / `voice` | speech synthesis adapter | **Configured** |
| Speech-to-text | whisper.cpp | sidecar/worker / desktop | local transcription engine | **Declared** |
| Voice activity | Silero VAD | sidecar library / desktop | local signal processing | **Declared** |
| Wake word | openWakeWord | sidecar library / desktop | custom KAIRO model preferred | **Declared** |
| Desktop runtime | Tauri | app / desktop | KAIRO-owned local trust boundary | **Scaffold** |
| Workspace shell | Dockview | web library | KAIRO UX/layout surface | **Validated** |
| Data views | TanStack Table/Query | web libraries | KAIRO UX/data access | **Integrated** |
| Drag/drop | dnd-kit | web library | KAIRO UX | **Integrated** |
| Rich text | Lexical | web library | future canonical document/editor surface | **Configured** |
| Whiteboard | Excalidraw | web library target | assets/doc objects linked to domain | **Declared** |
| Calendar UI | Schedule-X | web library | view over normalized calendar state | **Configured** |
| Dashboards | Apache ECharts | web library | view only | **Configured** |
| Maps | MapLibre GL JS | web library | view over place/location state | **Configured** |
| 2D graph | React Flow | web library | view over KAIRO graph | **Configured** |
| 3D graph | React Three Fiber + react-force-graph-3d | web libraries | view over KAIRO graph | **Configured** |
| Gantt | SVAR React Gantt | web library | renderer/editor over canonical Task/Plan data | **Scaffold / configured** |
| Crypto accounting | rotki | service / `finance` | portfolio source/adapter, private network only | **Configured** |
| Exchange APIs | CCXT | integration library / finance | no raw secret exposure to models | **Declared** |
| EVM | viem | web/worker library / finance | prepare/read; signing isolated | **Declared** |
| Trading engine | Hummingbot | service / `finance` | disabled for live authority by default | **Configured** |
| Personal finance | Actual Budget | service / `finance` | external ledger adapter | **Configured** |
| Smart home | Home Assistant | service / `home` | upstream device authority | **Configured** |
| Sandbox | gVisor | host runtime / ops | hardened execution boundary | **Declared** |
| Backup | restic | host job / ops | encrypted recovery layer | **Validated** |
| Private access | Headscale | service / `remote` | private network overlay | **Configured** |
| Deployment UI | Coolify (optional) | host platform | deployment convenience, not KAIRO dependency | **Declared / optional** |

## Important capability notes

### Gantt and Calendar

The current `packages/gantt` package contains only `ScheduledTask` / `PlanVersion` interfaces. SVAR React Gantt and Schedule-X being installed does not make Gantt/Calendar complete. G51 intentionally established canonical Task planning fields first.

### Brain / graph

The current `packages/graph` package contains only canonical graph snapshot interfaces. React Flow, React Three Fiber and react-force-graph-3d are installed but the 2D/3D mycelium Brain is not implemented on canonical `main`.

### Realtime and desktop

Hocuspocus/Yjs, Tauri and voice dependencies represent intended architecture boundaries and scaffolding. They are not yet mature end-user capabilities.

### Specialist engines

Finance, crypto, Home Assistant and OpenHands services can be present in optional profiles while still lacking stabilized KAIRO adapters, ownership rules, policy flows and UX. Optional Compose presence is not considered integration completion.

## Deliberately not foundational

- Open WebUI: useful for model/admin testing, not the KAIRO frontend foundation.
- n8n: avoided as the central automation dependency; Activepieces is the selected automation engine.
- FalkorDB: not selected due licensing concerns; Neo4j Community is the Graphiti backend.
- Kuzu: not selected because the project is archived/deprecated for this use.
- OpenClaw: the V0 proof runtime is removed from the target architecture; its durable-execution lessons are carried forward into Temporal and KAIRO policy contracts.

D03 profiles and refused prototype activations are documented in [deployment](deployment.md).
Validation of deployment controls does not promote the optional engines to real integration evidence.
