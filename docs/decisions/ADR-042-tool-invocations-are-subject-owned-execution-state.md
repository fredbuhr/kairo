# ADR-042 — Tool invocations are subject-owned execution state

Status: accepted

Date: 2026-09-09

## Context

KAIRO's MCP registry intentionally distinguishes two kinds of state:

- `ToolServer` / `ToolDefinition` describe deployment-managed capabilities and policy;
- `ToolInvocation` records an actual user's requested execution and is bound to a canonical Task → Project.

The first MCP implementation made `ToolInvocation.idempotency_key` globally unique. That was safe in a single-user prototype but is the wrong boundary for authenticated multi-user KAIRO: a caller-controlled request identity must not create an installation-wide collision namespace or reveal that another subject has already used the same string.

Research also creates child ToolInvocations internally, so fixing only the public `/v1/tool-invocations` route would leave a second construction path without explicit owner state.

## Decision

`ToolInvocation` is **user-world execution state**, even when its `ToolDefinition` is shared control-plane state.

Migration `0017_tool_invocation_ownership` adds `ToolInvocation.keycloak_subject`, backfilled from the canonical `Task → Project.keycloak_subject` ownership chain.

The canonical idempotency uniqueness boundary becomes:

`(keycloak_subject, idempotency_key)`

This means two authenticated subjects may use the same human- or client-selected idempotency string independently, while replay by the same subject still resolves to the same invocation when the Tool, Project and input binding also match.

### Public invocation creation

`POST /v1/tool-invocations`:

1. requires an owned Project;
2. resolves idempotency only inside `Principal.subject`;
3. writes `ToolInvocation.keycloak_subject = Principal.subject`;
4. continues to validate the shared ToolDefinition/ToolServer policy and input schema;
5. never treats another subject's matching idempotency key as the caller's existing invocation.

`GET /v1/tool-invocations/{id}` requires both the invocation owner and its Task → Project chain to belong to the authenticated subject. Foreign and absent invocation IDs both return 404.

### Internal execution binding

Worker-facing invocation routes keep the separate internal-token trust boundary, but `_load_invocation_binding` verifies that the invocation owner still equals the Project owner reached through its Task. A stale/corrupt cross-owner binding fails closed before execution.

### Research child invocations

Autonomous Research derives the owner from the parent Research Task's Project, scopes its deterministic child-invocation lookup to that subject, and writes the same owner on newly created ToolInvocations.

The internal Research result reader also verifies the child Task's Project owner against the invocation owner before accepting it as Research evidence.

### Shared registry remains separate

This ADR does **not** make `ToolServer` or `ToolDefinition` tenant-owned. They remain deployment/control-plane records under the existing admin policy. A future personal-MCP feature would require an explicit owner/visibility model rather than weakening this separation implicitly.

## Migration safety

The migration refuses to continue if any existing ToolInvocation cannot derive an owner through Task → Project. It drops the historical global unique constraint on `idempotency_key`, adds subject-local uniqueness, and indexes `(keycloak_subject, status, created_at)` for owner-scoped operational reads.

Downgrade may intentionally fail if different subjects have subsequently reused the same idempotency key, because such rows cannot be losslessly collapsed back into the old global namespace.

## Consequences

### Positive

- caller-selected ToolInvocation idempotency no longer couples tenants;
- public invocation reads have an explicit direct owner in addition to Task ownership;
- internal Worker execution gains a defense-in-depth owner-binding check;
- Research and direct MCP invocation use the same execution-ownership rule;
- ToolServer/ToolDefinition can remain shared without making execution history shared.

### Trade-offs

- another ownership column must stay consistent with the canonical Project root;
- every internal ToolInvocation constructor must propagate the derived owner;
- migrations and tests must cover both direct and Research-generated invocation paths.

## Validation

Current-head CI is still blocked before runner assignment by issue #38. Migration/model/Core changes are therefore implemented but not yet claimed as executed successfully on the current head.

A dedicated two-user runtime proof for subject-local ToolInvocation idempotency remains required before this hardening tranche is considered fully validated.
