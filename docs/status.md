# KAIRO implementation status

Last updated: 2026-09-08

## Current phase

**Block 2 — intelligence, memory and safe autonomy.**

Block 1 is complete and its exit conditions are covered by end-to-end CI proofs. The former OpenClaw/filesystem V0 remains useful history, but it is no longer the target runtime. Its lessons are carried into the PostgreSQL/Temporal/NATS architecture rather than maintaining two parallel systems.

Block 2 now has three active pieces rather than only planned contracts: KAIRO-owned policy/approval enforcement, replay-safe and canonically accounted model calls through LiteLLM, and the first canonical conversational command kernel.

## Foundation decisions now active

- PostgreSQL + pgvector is the canonical domain/state store;
- SeaweedFS is canonical object storage;
- Temporal is durable workflow execution;
- NATS JetStream is the event bus, fed by a transactional outbox;
- canonical Conversation/Message/Command records own conversational continuity and routing history;
- KAIRO-owned Capability contracts sit above replaceable specialist engines;
- deterministic high-confidence command routing is the first tier, with semantic routing reserved for a later second tier;
- Neo4j + Graphiti and Mem0 are rebuildable projections;
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

The completion gate contains four independent CI jobs and all four pass together:

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

## Canonical Command Kernel now present

KAIRO has a server-side conversational front door rather than a browser-only command field.

- canonical `Conversation`, `ConversationMessage`, `Command` and `Capability` records;
- versioned capability metadata with input/output schemas, authority level, cost class and runtime;
- `POST /v1/assistant/commands` as the universal command entry point;
- deterministic high-confidence routing for proven intents;
- conservative persistence and refusal for unsupported commands instead of invented intent;
- stable command-to-Task/Workflow correlation;
- a persisted `conversation_id` reused by the web Command Center across requests;
- `GET /v1/capabilities`, Conversation/Message reads and Command inspection;
- a dedicated CI integration job proving PostgreSQL command state and Temporal handoff without public Internet or paid model credentials.

The first registered capability is `news.brief`. The dedicated News HTTP endpoint and the universal command path now call the same transport-independent capability service.

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

Continue Block 2 from this command boundary rather than adding isolated demos: add the PydanticAI semantic routing/agent layer behind the same canonical Command/Capability contracts, then Mem0 and Graphiti projections fed only from canonical KAIRO events, Docling ingestion, MCP tool registry, research/browser/Activepieces adapters and Langfuse trace correlation.

The target Block 2 exit remains: an approved autonomous workflow can research, use tools, create canonical artefacts, survive interruption, respect authority/cost limits and explain what it did.

Production deployment hardening is still a later concern. Block 1 completion does not imply that the current web/runtime exposure is production-ready; TLS, reverse proxy/private-network policy, hardened untrusted execution and verified encrypted off-host recovery remain later hardening work.
