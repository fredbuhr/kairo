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

### Schemas are untrusted contracts

Remote input and output schemas are validated as JSON Schema before catalog state is accepted. Invocation arguments are validated against the currently registered input schema before KAIRO creates a Task.

A remote schema hash is part of the effective authorization contract. If the schema changes during catalog synchronization, KAIRO updates the catalog record but automatically disables the tool. An administrator must review and explicitly re-enable the new contract.

Previously created Tasks keep the schema hash and policy snapshot they were created with. Re-enabling a drifted tool does not upgrade an old pending invocation: Core rejects the stale snapshot and requires a new invocation.

### Stable KAIRO tool keys

A remote MCP tool is addressed inside KAIRO by `<namespace>.<remote_name>`. The remote server and protocol implementation remain replaceable behind that key. Catalog drift is inspectable without changing KAIRO's logical identity.

### Every invocation is canonical

A requested invocation creates a canonical `ToolInvocation` and a normal KAIRO `Task` with capability `tool.invoke`. The Task carries the exact tool key, schema hash, authority level, estimated cost, risk class, retry policy and server key. Temporal therefore reaches the existing KAIRO Core policy gate before the Worker can cross the MCP network boundary.

The invocation ledger owns a stable idempotency key. Reusing a key for a different project, tool or input is rejected.

### Authorization and contract are revalidated at the boundary

The Temporal policy gate decides whether the Task may proceed. Immediately before the external MCP call, the Worker asks Core for the invocation context again. Core verifies that the server and tool are still enabled/available and that the **registered** schema hash, authority, cost, risk and retry policy still match the immutable Task snapshot.

The Worker then opens the MCP session and performs `list_tools()` before `call_tool()`. It requires the remote tool to still exist and computes the live name/input/output schema hash using the same canonical representation as Core. If that live hash differs from the Task's immutable `tool_schema_hash`, execution fails before the side-effect checkpoint.

Fetching the live catalog also loads the MCP SDK's current output contract before `call_tool()`, so structured tool results are checked against the server-advertised output schema instead of being accepted blindly.

Only after both the KAIRO registry/policy snapshot and the live MCP contract agree does the Worker persist `pre_call` and cross the actual tool-call boundary. This prevents an approval obtained under one contract from silently inheriting either a later KAIRO registry change or an unsynchronized remote server schema change.

### Replay policy is explicit

The Worker checkpoints MCP calls with Temporal heartbeats:

1. live catalog refresh and schema comparison happen before the side-effect checkpoint;
2. `pre_call` is persisted immediately before `call_tool()`;
3. `result` is persisted after a complete MCP response is known;
4. `accounted` is persisted after Core has canonically stored the result.

A persisted result may be replayed into Core without calling the remote tool again.

For `no_retry` tools, a retry that sees only `pre_call` raises a non-retryable Temporal application error because the first call may already have performed a side effect. KAIRO does not assume MCP transports or remote servers provide exactly-once execution.

For explicitly `safe_retry` tools, the Worker may repeat a call after an ambiguous attempt.

If the `tool.invoke` workflow terminates because policy is denied or the runtime exhausts retries, the Worker marks the canonical `ToolInvocation` failed before it marks the Task/Workflow failed. The ledger therefore does not remain indefinitely `pending` or `running` after a terminal workflow outcome.

### MCP is transport, not authority

The first production transport is Streamable HTTP via the official MCP Python SDK v2. Core never directly invokes remote MCP servers. External tool servers cannot approve actions, mint policy tokens, change Task authority ceilings, alter budgets or write canonical audit records.

## Consequences

- Agents can use many MCP servers without learning provider-specific permission systems.
- Tool discovery can be broad while execution remains narrow and explicit.
- Both synchronized catalog drift and last-moment live server drift fail closed.
- Structured outputs are evaluated against the contract advertised by the server at execution time.
- Side-effect ambiguity becomes visible instead of being hidden by retries.
- Catalog and runtime adapters can change without invalidating canonical invocation history.
- Autonomous research reuses the same registry and call-specific policy gate rather than inventing another tool abstraction.

## Follow-up

The first bounded autonomous Research capability has now been built on this boundary. Future agents should reuse the same sequence — canonical Task snapshot, Core policy revalidation, live MCP contract refresh, side-effect checkpoint, canonical result — rather than introducing agent-specific tool execution paths.
