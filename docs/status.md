# KAIRO implementation status

Last updated: 2026-09-08

## Current phase

**Block 2 — intelligence, memory and safe autonomy.**

Block 1 is complete and its exit conditions are covered by end-to-end CI proofs. The former OpenClaw/filesystem V0 remains useful history, but it is no longer the target runtime. Its lessons are carried into the PostgreSQL/Temporal/NATS architecture rather than maintaining two parallel systems.

Block 2 now has five active pieces rather than only planned contracts: KAIRO-owned policy/approval enforcement, replay-safe and canonically accounted model calls through LiteLLM, the canonical conversational command kernel, a durable PydanticAI semantic-routing tier constrained to registered KAIRO capabilities, and rebuildable Mem0 + Graphiti/Neo4j projections driven from canonical conversation events.

## Foundation decisions now active

- PostgreSQL + pgvector is the canonical domain/state store;
- SeaweedFS is canonical object storage;
- Temporal is durable workflow execution;
- NATS JetStream is the event bus, fed by a transactional outbox;
- canonical Conversation/Message/Command records own conversational continuity and routing history;
- KAIRO-owned Capability contracts sit above replaceable specialist engines;
- deterministic high-confidence command routing is the first tier;
- PydanticAI provides a second-tier semantic route proposal only when deterministic routing has no match;
- semantic PydanticAI provider access goes through the same replay-safe/accounted LiteLLM Worker gateway as other model calls;
- Neo4j + Graphiti and Mem0 are rebuildable projections, never canonical state;
- Mem0 uses an isolated PostgreSQL `mem0` database rather than writing vector tables into KAIRO's canonical schema;
- LiteLLM is the model-provider gateway;
- PydanticAI is the agent framework;
- Keycloak and OpenBao are identity/secrets boundaries;
- Hocuspocus/Yjs provides realtime collaboration without becoming the domain store;
- Activepieces and MCP provide external tool/automation integration;
- specialist engines are declared in the component registry from the beginning.

## Block 1 complete

The permanent platform substrate now includes:

- Alembic migrations for canonical projects, tasks, relationships, workflow executions, artifacts, assets, devices, secret references, audit and outbox records;
- Core-owned domain mutations through PostgreSQL;
- transactional outbox relay from PostgreSQL to NATS JetStream;
- deterministic Temporal Workflow IDs and conservative `start_unknown` handling for ambiguous starts;
- Worker mutations returning through internal KAIRO Core endpoints rather than writing canonical state directly;
- idempotent task completion with one canonical artifact per workflow execution;
- separate Temporal workflow and activity modules so network libraries are not imported into the workflow sandbox;
- different heartbeat budgets for short foundation work and longer intelligence work;
- Keycloak JWT validation through JWKS/RS256 with the signed `sub` as the canonical device owner;
- authenticated device registration and KAIRO-owned current-identity contract;
- OpenBao secret references/status that expose metadata and key names without returning secret values;
- authenticated SeaweedFS asset upload/download/delete with digest verification;
- separate substrate readiness and trust-boundary health endpoints;
- development-only Keycloak/OpenBao bootstrap isolated from the production trust-boundary overlay;
- Restic backup/restore commands for the four durable Block 1 stores: PostgreSQL, NATS, SeaweedFS and OpenBao.

## Block 1 proof status

The completion gate contains independent CI jobs that continue to pass together:

1. `validate` — development, production and operations Compose topologies; TypeScript/Python builds; deterministic capability/model/news contracts;
2. `block1-integration` — create canonical entities, start a durable Temporal workflow, hard-stop the Worker, restart it, resume execution, finish exactly once and drain the transactional outbox;
3. `resource-integration` — reject unauthenticated access, obtain a real Keycloak token, bind resources to the signed subject, prove OpenBao non-disclosure and perform a SeaweedFS asset round-trip;
4. `backup-restore-integration` — seed independent markers in PostgreSQL, NATS, SeaweedFS and OpenBao, create and verify a Restic snapshot, delete the live markers, destructively restore all four volumes and prove every marker returns.

This closes the Block 1 exit requirement: KAIRO can create/read canonical entities, publish domain events, store assets, survive service interruption and restore its durable substrate from backup.

## Block 2 safe-autonomy kernel already present

- KAIRO Core owns approval requests and policy authorization;
- authority ceilings and hard task budgets are checked before guarded activities;
- approved actions receive short-lived signed policy capability tokens;
- Temporal workflows can suspend for approval and resume after a decision;
- LiteLLM model calls are authorized and recorded in the canonical PostgreSQL usage ledger;
- model usage records support stable idempotency keys;
- paid model calls keep replay checkpoints through Temporal heartbeats and refuse blind provider replay when the prior outcome is ambiguous;
- retries can replay known results or repeat only the idempotent accounting handoff rather than silently double-spending.

## Canonical Command Kernel and semantic routing

KAIRO has a server-side conversational front door rather than a browser-only command field.

- canonical `Conversation`, `ConversationMessage`, `Command` and `Capability` records;
- versioned capability metadata with input/output schemas, authority level, cost class and runtime;
- `POST /v1/assistant/commands` as the universal command entry point;
- deterministic high-confidence routing for proven intents without a model call;
- ambiguous commands create a canonical `assistant.route.semantic` Task instead of being guessed synchronously;
- PydanticAI validates a typed route proposal but has no direct provider/tool authority;
- `FunctionModel` delegates the single semantic model turn to the existing KAIRO `model_gateway`;
- semantic routing defaults to the `local-fast` LiteLLM alias and carries its own hard Task budget;
- Core sends only capabilities explicitly marked `routable=true` and independently re-validates the returned key, confidence and input schema;
- malformed/low-confidence/invented routes become `unsupported` rather than side effects;
- semantic final Task IDs are deterministic so retries reuse an existing capability invocation;
- stable Command → routing Task → final Task/Workflow correlation;
- a persisted `conversation_id` reused by the web Command Center across requests;
- the Web Command Center follows asynchronous semantic routing before attaching to the final capability Task;
- `GET /v1/capabilities`, Conversation/Message reads and Command inspection.

The first user-routable capability remains `news.brief`. `assistant.route.semantic` is internal and cannot itself be proposed by the model.

## Rebuildable memory and temporal context

Conversation memory now starts from the same canonical `ConversationMessage` rows used by the Command Kernel rather than from a specialist memory database.

- inserting a canonical message writes a `conversation.message.created` outbox record in the same PostgreSQL transaction;
- the event contains stable message/conversation references but not a duplicate copy of message text;
- a durable JetStream Worker consumer turns the event into a deterministic `memory.project` Task;
- Core tracks one `mem0` and one `graphiti` projection row per canonical message/source version;
- Mem0 stores raw message memory with `infer=False` and local FastEmbed embeddings, so this slice does not introduce a hidden generative provider call;
- Mem0 vector tables live in a separate PostgreSQL `mem0` database that can be destroyed independently of canonical KAIRO state;
- Graphiti writes the canonical message as a temporal `EpisodicNode` in Neo4j using the message UUID as its stable episode UUID;
- Graphiti entity/fact extraction is deliberately deferred until its model calls can be routed through KAIRO's replay-safe/accounted model gateway;
- projection generation numbers make a real rebuild possible after a previous Temporal Task has completed;
- stale generation events/reports are ignored rather than rolling a rebuilt projection backwards;
- `POST /internal/v1/memory/rebuild` reconstructs selected or all conversation-message projections from canonical Core data;
- `GET /v1/memory/projections/conversation-messages/{message_id}` exposes projection state without making Mem0/Neo4j authoritative;
- CI uses deterministic projectors when intelligence extras are absent and proves initial projection, generation-2 rebuild, stale-delivery rejection and unchanged canonical message data.

ADR-019 records the rule that Mem0/Graphiti are disposable views and that future generative extraction must remain behind KAIRO's model/accounting boundary.

## News Intelligence already present

News Intelligence is a first-class KAIRO capability (`news.brief`) rather than a separate application.

- SearXNG discovers current news and general web sources through a private metasearch service;
- Trafilatura transiently extracts main article text from accessible public pages for better summarization without persisting full copyrighted article bodies;
- enrichment blocks localhost, private/non-global IP destinations and redirects toward internal services;
- LiteLLM creates sourced text/spoken briefings and is replaceable by provider/model alias;
- deterministic fallback summaries remain available when the model gateway is unavailable;
- `market_impact` mode combines a deterministic relevance signal with model synthesis while keeping sources and uncertainty visible;
- each request is a canonical Task in the `KAIRO News` workspace;
- each completed briefing is an Artifact with source metadata and provenance;
- Kokoro-FastAPI provides local French speech synthesis under the optional `voice` Compose profile;
- the web application has a News Intelligence workspace with local/general/market modes, source list, progress state and audio playback;
- CI has a deterministic News Intelligence contract proof that does not depend on the public internet or paid model credentials.

## Next major milestone

After the rebuildable-memory slice is green, continue Block 2 with Docling ingestion and canonical document/chunk provenance, then Langfuse correlation, the MCP tool registry and the first tool-bearing research workflow. Semantic retrieval over Mem0/Graphiti can then be connected to agent context without changing their status as disposable projections.

The target Block 2 exit remains: an approved autonomous workflow can research, use tools, create canonical artefacts, survive interruption, respect authority/cost limits and explain what it did.

Production deployment hardening is still a later concern. Block 1 completion does not imply that the current web/runtime exposure is production-ready; TLS, reverse proxy/private-network policy, hardened untrusted execution and verified encrypted off-host recovery remain later hardening work.
