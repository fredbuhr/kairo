# KAIRO implementation status

Last updated: 2026-09-08

## Current phase

**Block 1 — canonical system of record and durable execution.**

The architecture reset is complete enough to run real integration proofs. The active implementation branch is `feat/block1-system-of-record`.

The prior OpenClaw/filesystem V0 remains useful history, but it is no longer the target runtime. Its lessons are carried into the PostgreSQL/Temporal/NATS architecture rather than maintaining two parallel systems.

## Foundation decisions now active

- PostgreSQL + pgvector is the canonical domain/state store;
- SeaweedFS is canonical object storage;
- Temporal is durable workflow execution;
- NATS JetStream is the event bus, fed by a transactional outbox;
- Neo4j + Graphiti and Mem0 are rebuildable projections;
- LiteLLM is the model-provider gateway;
- PydanticAI is the agent framework;
- Keycloak and OpenBao are identity/secrets boundaries;
- Hocuspocus/Yjs provides realtime collaboration without becoming the domain store;
- Activepieces and MCP provide external tool/automation integration;
- specialist engines are declared in the component registry from the beginning.

## Block 1 implemented

- Alembic migrations for canonical projects, tasks, relationships, workflow executions, artifacts, assets, devices, secret references, audit and outbox records;
- Core-owned domain mutations through PostgreSQL;
- transactional outbox relay from PostgreSQL to NATS JetStream;
- deterministic Temporal Workflow IDs and conservative `start_unknown` handling for ambiguous starts;
- Worker mutations return through internal KAIRO Core endpoints rather than writing canonical state directly;
- idempotent task completion with one canonical artifact per workflow execution;
- separate Temporal workflow and activity modules so network libraries are not imported into the workflow sandbox;
- different heartbeat budgets for short foundation work and longer intelligence work.

## Block 1 proof status

The real integration job has successfully demonstrated:

1. boot PostgreSQL, NATS, SeaweedFS, Temporal, KAIRO Core and KAIRO Worker;
2. create a canonical Project, Task and Relationship;
3. start a durable task workflow;
4. hard-stop the Worker while the activity is running;
5. keep canonical task state as `running` while the Worker is down;
6. restart the Worker and resume through Temporal;
7. complete with exactly one canonical Artifact;
8. reject a second run of the completed task;
9. drain the transactional outbox with the relay still connected.

This closes the failure that previously came from importing `httpx` through the Temporal workflow sandbox.

## News Intelligence added

News Intelligence is now a first-class KAIRO capability (`news.brief`) rather than a separate application.

- SearXNG discovers current news and general web sources through a private metasearch service;
- Trafilatura transiently extracts main article text from accessible public pages for better summarization without persisting full copyrighted article bodies;
- enrichment blocks localhost, private/non-global IP destinations and redirects toward internal services;
- LiteLLM creates sourced text/spoken briefings and is replaceable by provider/model alias;
- deterministic fallback summaries remain available when the model gateway is unavailable;
- `market_impact` mode combines a deterministic relevance signal with model synthesis while keeping sources and uncertainty visible;
- each request is a canonical Task in the `KAIRO News` workspace;
- each completed briefing is an Artifact with source metadata and provenance;
- Kokoro-FastAPI provides local French speech synthesis under the optional `voice` Compose profile;
- the web application now has a working News Intelligence workspace with local/general/market modes, source list, progress state and audio playback;
- CI has a deterministic News Intelligence contract proof that does not depend on the public internet or paid model credentials.

## Next major milestone

Finish hardening Block 1 around concurrency, authorization/policy and recovery edge cases, then connect the realtime/event layer and conversational command routing so capabilities such as `news.brief` can be invoked naturally from KAIRO's general assistant surface as well as their dedicated workspaces.
