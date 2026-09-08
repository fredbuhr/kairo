# KAIRO implementation status

Last updated: 2026-09-08

## Current phase

**Architecture reset / full-platform foundation.**

The prior OpenClaw/filesystem V0 proved useful runtime properties but is no longer the target implementation. Its code and ADRs remain recoverable through Git history; target-architecture files remove that dependency rather than carrying parallel runtimes indefinitely.

## Proven by the previous V0

The earlier implementation demonstrated:

- stable project/idea/task/knowledge identifiers;
- explicit epistemic status and provenance concepts;
- background execution with no active client;
- survival of queued work across controlled runtime restarts;
- conservative handling of interrupted `running` work;
- the danger of replaying an activity whose result is unknown;
- the need for idempotency, hard budget enforcement, explicit approvals and authoritative user-visible work state.

Those lessons remain requirements in the new architecture and motivate Temporal, the policy boundary and explicit audit/idempotency contracts.

## Removed from the target architecture

- OpenClaw runtime/plugin/workspace templates;
- OpenClaw Cron scheduling adapter;
- OpenClaw-specific CI;
- filesystem/Markdown store as canonical operational state;
- V0 job ledger implementation tied to that runtime;
- V0 proof scripts/runbooks and superseded ADR set.

Markdown remains an export/import format for user-readable knowledge, not the primary operational database.

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

## Work now in progress on `architecture/full-platform-foundation`

1. replace legacy repository topology with the permanent monorepo structure;
2. add complete component registry and Compose topology;
3. add minimal Core/Worker/Realtime/Web service skeletons;
4. add CI/static validation for the new foundation;
5. open the architecture reset for review before merging to `main`.

## Next major milestone

Boot the complete foundation, run migrations, create the first canonical Project/Task/Relationship through `kairo-core`, publish its domain event through NATS, and execute a Temporal workflow that safely writes a resulting artefact back through the Core policy boundary.
