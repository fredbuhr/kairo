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

PostgreSQL enforces the same invariant with `trg_tool_invocation_task_owner`. A ToolInvocation insert or rebind is rejected unless `NEW.task_id → Project.keycloak_subject` equals `NEW.keycloak_subject`. Endpoint checks therefore provide product-level behavior while the database remains the final defense against a future missed constructor/path.

### Research child invocations

Autonomous Research derives the owner from the parent Research Task's Project, scopes its deterministic child-invocation lookup to that subject, and writes the same owner on newly created ToolInvocations.

The internal Research result reader also verifies the child Task's Project owner against the invocation owner before accepting it as Research evidence.

### Shared registry remains separate

This ADR does **not** make `ToolServer` or `ToolDefinition` tenant-owned. They remain deployment/control-plane records under the existing admin policy. A future personal-MCP feature would require an explicit owner/visibility model rather than weakening this separation implicitly.

The normal user-facing `GET /v1/tool-servers` response is a sanitized shared summary: logical identity, namespace, transport kind, policy state and catalog generation are visible, but deployment endpoint URLs and arbitrary server metadata are omitted. Full transport details remain available on admin mutation responses and internal execution context.

The Cockpit follows the same distinction: ordinary users can inspect shared contracts/policy state, while registration and policy mutation controls are shown only to `kairo-admin` (or auth-disabled local development).

## Migration safety

The migration refuses to continue if any existing ToolInvocation cannot derive an owner through Task → Project. It drops the historical global unique constraint on `idempotency_key`, adds subject-local uniqueness, indexes `(keycloak_subject, status, created_at)`, and installs the database Task-owner trigger.

Downgrade may intentionally fail if different subjects have subsequently reused the same idempotency key, because such rows cannot be losslessly collapsed back into the old global namespace.

## Consequences

### Positive

- caller-selected ToolInvocation idempotency no longer couples tenants;
- public invocation reads have an explicit direct owner in addition to Task ownership;
- Worker execution and PostgreSQL both enforce the Task/Project owner binding;
- Research and direct MCP invocation use the same execution-ownership rule;
- ToolServer/ToolDefinition can remain shared without making execution history shared;
- ordinary users no longer receive MCP endpoint topology from the shared registry response or unusable admin mutation controls in the Cockpit.

### Trade-offs

- another ownership column must stay consistent with the canonical Project root;
- every internal ToolInvocation constructor must propagate the derived owner;
- migrations and tests must cover both direct and Research-generated invocation paths;
- a future personal-MCP feature needs a separate ownership/visibility design rather than reusing the shared registry implicitly.

## Validation

`tool_invocation_ownership_contract.py` is a cheap fail-fast source/migration proof: it checks that every current ToolInvocation constructor propagates ownership, the subject-local unique constraint is present and the database owner trigger exists.

The MCP management proof also checks that the ordinary ToolServer list omits `endpoint_url` and `metadata_json` while admin creation still returns the full registered record.

Current-head hosted CI is still blocked before runner assignment by issue #38, so these changes are implemented but not claimed as executed successfully on the current head. A dedicated two-user runtime proof for subject-local ToolInvocation idempotency remains required before this tranche is fully validated.
