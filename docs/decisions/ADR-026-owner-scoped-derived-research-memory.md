# ADR-026 — Research reads derived memory only through Core-owned identity scope

Status: Accepted for the derived-memory context slice.

Date: 2026-09-10

## Context

KAIRO already projects canonical `ConversationMessage` records into Mem0 and Graphiti. Those stores are rebuildable and non-authoritative. Autonomous Research now needs relevant personal context, but letting a Worker infer a user scope from arbitrary model input or enumerate every graph group would create a privacy boundary outside Core.

Mem0 projections can use one user scope (`subject:<keycloak-subject>`). Current Graphiti projections are grouped per canonical Conversation (`conversation:<conversation-id>`), so Graphiti access must be constrained to conversations that Core says belong to the requester.

## Decision

A Research Task carries the authenticated `requester_subject`. Core derives a read-only memory scope from canonical state and exposes only:

- the exact Mem0 user id `subject:<requester-subject>`;
- at most 100 Graphiti group ids derived from Conversations whose `subject_ref` exactly matches that requester.

The Worker cannot widen this scope. It queries Mem0 with the exact `filters={"user_id": ...}` contract of the pinned Mem0 version and queries Graphiti only within the supplied group ids.

Results are normalized behind KAIRO context records with stable `M*` and `G*` ids, bounded excerpts and links back to canonical message/conversation ids when available. Engine-specific payloads do not escape this adapter.

Mem0 and Graphiti are queried independently. A failure in either derived store is reported as `unavailable` but does not fail the other store or become a Research authority decision.

## Consequences

- derived personal context cannot cross a canonical Conversation ownership boundary;
- legacy unowned Conversations are excluded rather than implicitly claimed;
- Mem0 and Graphiti remain replaceable projections rather than sources of truth;
- Research can later combine canonical Documents and derived memory without knowing engine APIs;
- Graphiti context is currently limited to the 100 most recently updated owned Conversations; a future owner-level graph projection may remove that bounded compatibility layer;
- this slice only provides retrieval. It does not yet put derived memory into model prompts; that remains A6c.
