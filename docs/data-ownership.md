# Data ownership and projection rules

This document prevents the platform from becoming a collection of mutually inconsistent sources of truth.

| Data class | Authoritative store | Derived/secondary systems |
|---|---|---|
| Domain entities and relationships | PostgreSQL | pgvector, Graphiti/Neo4j, search indexes |
| Security policy / approvals / audit | PostgreSQL | Langfuse correlation, analytics |
| Binary files / artefacts | SeaweedFS | local caches, generated previews |
| In-flight workflow execution | Temporal | Nevolium workflow-run projection in PostgreSQL |
| Conversational memory | canonical conversation/events in PostgreSQL/object store | Mem0 |
| Temporal semantic context | canonical events/sources | Graphiti + Neo4j |
| Collaborative edit session | Yjs while active | durable snapshots/domain records |
| External automation execution | Activepieces for engine-internal runtime | Nevolium automation/run correlation |
| LLM traces | Nevolium usage/audit summaries + provider records | Langfuse detailed traces |
| Model/provider configuration | Nevolium config + OpenBao secret refs | LiteLLM runtime config |
| Crypto signing material | isolated wallet/hardware signer | never copied into Nevolium AI stores |
| Home device state | Home Assistant | normalized Nevolium entity references/events |
| Budget ledger | Actual Budget/source institutions | normalized Nevolium summaries/links |
| Crypto portfolio accounting | rotki/exchanges/chains | normalized Nevolium holdings/alerts |

## Projection rule

A derived system must be rebuildable from authoritative Nevolium state or its upstream authoritative external system. If it cannot be rebuilt, it is not merely a projection and requires an explicit ADR before adoption.

## Deletion rule

Deleting a projection must not delete canonical records. Deleting canonical user data propagates tombstones/removal jobs to derived stores subject to legal/audit retention rules.
