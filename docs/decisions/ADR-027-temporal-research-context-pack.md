# ADR-027 — Research Context Pack is bounded, owner-scoped and snapshotted before model work

Status: Accepted for the Block 2 Context Pack slice.

Date: 2026-09-10

## Context

Autonomous Research can now use canonical document chunks, rebuildable Mem0/Graphiti projections and policy-bound MCP tools. Reading those stores directly inside the replay-sensitive Research activity would make retries nondeterministic: personal context may legitimately change between the original attempt and a retry after a Worker crash.

Large context payloads also do not belong in Temporal heartbeats, whose purpose in Nevolium is to preserve compact progress and replay-critical model-call checkpoints.

## Decision

Research context preparation is a separate read-only Temporal activity, `prepare_research_context_pack`, executed after policy authorization and before the main `perform_autonomous_research` activity.

The preparation activity reads only the Core-owned requester scope established by ADR-026, gathers canonical document context and best-effort derived memory, then returns one bounded Context Pack. Temporal records that successful activity result in workflow history. Retries of the main Research activity therefore receive the same context snapshot instead of re-reading mutable stores.

The Context Pack contains at most:

- 6 canonical document chunks;
- 6 derived memory records;
- 12 records total;
- 20,000 characters of evidence excerpts total.

Canonical document records have `D*` evidence ids and `authority=canonical`. Mem0/Graphiti records have `M*`/`G*` ids and `authority=derived`. Duplicate derived projections that map to the same canonical message are collapsed to the highest-ranked representation. MCP results retain their existing `E*` ids and policy-bound tool provenance.

All Context Pack contents are treated as untrusted data by both planner and synthesizer. Context may help the planner avoid redundant tool calls, but it cannot grant tool authority or modify schemas. The synthesizer may cite only supplied `D*`, `M*`, `G*` or `E*` identifiers, and Core/Worker validation still rejects invented evidence ids.

If no MCP tool is available, Nevolium skips the planning model call. Context-only synthesis may use the full Research model budget and the resulting Artifact does not claim that a planner model was invoked.

The final Artifact stores the bounded context evidence needed for claim provenance plus a sanitized Context Pack source summary. Backend exception messages from Mem0/Neo4j are not part of the public Research result contract.

Public Research result reads require the exact authenticated `requester_subject` captured when the Research Task was created. Missing and foreign ownership share the same not-found surface.

## Consequences

- a Worker crash cannot silently change personal evidence between planning and synthesis retries;
- Context Pack size is explicitly bounded independently of the size of source stores;
- canonical documents, derived memory and MCP evidence share one inspectable claim-evidence contract without sharing authority;
- derived-store outages degrade context quality but do not become authorization failures;
- context-only questions can be answered without unnecessary Web calls;
- larger retrieval, semantic reranking and owner-level Graphiti projections remain replaceable future improvements behind the same Nevolium Context Pack boundary.
