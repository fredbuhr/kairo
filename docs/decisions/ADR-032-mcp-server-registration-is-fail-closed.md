# ADR-032 — MCP server registration is fail-closed

Status: accepted
Date: 2026-09-09

## Context

The KAIRO Tools workspace must let an administrator connect and inspect MCP servers without turning discovery into authorization. A newly typed endpoint URL is untrusted configuration: merely registering it must not grant network authority to tools, and discovering a remote tool must not make that tool executable.

## Decision

KAIRO separates three states:

1. **registered server** — endpoint metadata exists in the canonical ToolServer registry;
2. **enabled server** — KAIRO policy permits that server to participate in tool execution;
3. **enabled tool** — a specific available ToolDefinition is explicitly authorized with its own risk/authority/retry policy.

`POST /v1/tool-servers` creates a canonical ToolServer but always sets `enabled=false`, regardless of the client request. Registration validates a stable KAIRO key and requires an absolute HTTP(S) endpoint. It records audit/domain events but performs no network synchronization as a side effect.

`PATCH /v1/tool-servers/{server_key}/policy` is an explicit administrator decision. Disabling a server disables every currently enabled tool on that server. Re-enabling the server does **not** silently re-enable those tools; each tool remains denied until its own policy says otherwise.

Catalog synchronization stays a separate explicit action. Tools that disappear from the live catalog become unavailable. Worker execution continues to revalidate the live MCP contract immediately before execution, so the Cockpit never becomes the final authority for remote schema trust.

## Consequences

- The Tools workspace can register real MCP endpoints without making them executable.
- A compromised/stale remote server cannot gain authority merely by appearing in a synced catalog.
- Server disable is a strong kill switch; server re-enable is intentionally not an authority restore switch.
- UI state remains a projection of canonical ToolServer/ToolDefinition policy.
- Secret values remain outside ToolServer metadata; auth modes may reference KAIRO secret machinery but credentials are never stored in the frontend registration form.
