# ADR-022 — MCP tool registry and invocation authority

Status: Accepted

Date: 2026-09-09

## Context

KAIRO needs a large and replaceable tool surface without allowing external MCP servers, model-generated tool names or remote annotations to become an authority boundary. Tools may be read-only, mutating or destructive, and a Worker crash can make the outcome of a remote side effect ambiguous.

The existing Block 2 boundary already makes PostgreSQL canonical, Temporal durable, and KAIRO Core authoritative for policy, approvals and budgets. MCP must fit inside that boundary rather than create a parallel agent runtime with its own permissions.

## Decision

KAIRO owns a canonical PostgreSQL registry composed of `ToolServer`, `ToolDefinition` and `ToolInvocation` records.

### Discovery is not permission

Catalog synchronization may import remote MCP names, schemas and annotations, but newly discovered tools are always `enabled=false`.

Remote annotations are treated only as conservative hints for initial classification:

- `readOnlyHint=true` defaults to `risk_class=read`, authority A1 and `safe_retry`;
- `destructiveHint=true` defaults to `risk_class=destructive`, authority A3 and `no_retry`;
- unknown or ordinary tools default to `risk_class=write`, authority A2 and `no_retry` unless an idempotency hint justifies `safe_retry`.

Only KAIRO policy state can enable a tool or change its authority/retry classification.

### Stable KAIRO tool keys

A remote MCP tool is addressed inside KAIRO by `<namespace>.<remote_name>`. The remote server and protocol implementation remain replaceable behind that key. The registry stores the remote schema hash so catalog drift is visible without changing KAIRO's logical identity.

### Every invocation is canonical

A requested invocation creates a canonical `ToolInvocation` and a normal KAIRO `Task` with capability `tool.invoke`. The Task carries the exact tool key, authority level, estimated cost and policy scope. Temporal therefore reaches the existing KAIRO Core policy gate before the Worker can cross the MCP network boundary.

The invocation ledger owns a stable idempotency key. Reusing a key for a different tool or input is rejected.

### Replay policy is explicit

The Worker checkpoints MCP calls with Temporal heartbeats:

1. `pre_call` immediately before crossing the network boundary;
2. `result` after a complete MCP response is known;
3. `accounted` after Core has canonically persisted the result.

A persisted result may be replayed into Core without calling the remote tool again.

For `no_retry` tools, a retry that sees only `pre_call` fails closed because the first call may already have performed a side effect. KAIRO does not assume MCP transports or remote servers provide exactly-once execution.

For explicitly `safe_retry` tools, the Worker may repeat a call after an ambiguous attempt.

### MCP is transport, not authority

The first production transport is Streamable HTTP via the official MCP Python SDK v2. Core never directly invokes remote MCP servers. External tool servers cannot approve actions, mint policy tokens, change Task authority ceilings, alter budgets or write canonical audit records.

## Consequences

- Agents can eventually use many MCP servers without learning provider-specific permission systems.
- Tool discovery can be broad while execution remains narrow and explicit.
- Side-effect ambiguity becomes visible instead of being hidden by retries.
- Catalog and runtime adapters can change without invalidating canonical invocation history.
- Future autonomous research workflows can reuse the same registry and call-specific policy gate rather than invent another tool abstraction.

## Follow-up

The next slice should build the first autonomous research capability on top of this registry. It should use PydanticAI only for planning/proposals, schedule model calls through the replay-safe model gateway, and execute each selected tool through this MCP boundary with per-call policy checks.
