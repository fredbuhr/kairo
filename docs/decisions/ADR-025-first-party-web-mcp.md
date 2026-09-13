# ADR-025 — First-party Web research crosses the canonical MCP boundary

Status: Accepted for the first Web research tool slice.

Date: 2026-09-10

## Context

`research.autonomous` can now plan bounded read-only tool calls, execute each call as a canonical `tool.invoke` child Task and produce a grounded synthesis. It still needs useful real tools. Nevolium already runs SearXNG and already has an SSRF-safe public-page reader for News Intelligence.

Calling those helpers directly from the research agent would create a privileged special case outside the MCP registry, invocation ledger and live policy revalidation that Block 2 has established for tools.

## Decision

Nevolium exposes a small first-party Streamable HTTP MCP server containing exactly two tools:

- `web.search` — search recent public sources through SearXNG;
- `web.fetch` — retrieve one SSRF-validated public HTML page and return a bounded main-text excerpt.

The MCP server is an adapter, not an authority source. It cannot create Tasks, grant permissions, change budgets or write audit state. `research.autonomous` discovers and invokes these tools through the same canonical `ToolServer`, `ToolDefinition` and `ToolInvocation` boundary as any external MCP server.

### Discovery remains separate from permission

The bootstrap reads the live MCP catalog and synchronizes it through Core. It refuses unexpected tool names or a tool that is not declared read-only. Synchronization still creates/discovers tools disabled by default. A separate explicit policy update in the bootstrap enables only the expected `web.search` and `web.fetch` keys as A1/read/safe-retry tools.

When Nevolium authentication is enabled, the public registry/policy operations require an explicit admin bearer token. Internal catalog synchronization continues to use Nevolium's internal service token.

### Public-page retrieval is bounded

`web.fetch` reuses Nevolium's existing URL and redirect validation so localhost, private addresses and other non-global destinations are rejected before requests are issued.

The canonical ToolInvocation result never stores an unrestricted extracted article body. The tool returns only a bounded excerpt: 3,500 characters by default and at most 5,000 characters, plus the canonical/final URL and truncation metadata. Research may use that excerpt as evidence while retaining canonical provenance without turning Nevolium into an article archive.

### Internal transport is explicit

The first deployment is only on the private Nevolium Compose network. The MCP Streamable HTTP server binds inside the container and uses an explicit Host allowlist for `nevolium-web-mcp` and local development hosts. No host port is published by the Web MCP overlay.

## Consequences

- Research receives real Web capabilities without a privileged bypass around the canonical tool boundary.
- Existing MCP replay, schema-drift, policy and audit guarantees apply unchanged.
- SearXNG and the public-page reader remain replaceable implementation details behind stable Nevolium tool keys.
- Web evidence is inspectable and bounded before it becomes canonical ToolInvocation data.
- Broader browser navigation, authenticated sites and mutating Web actions remain separate higher-authority capabilities; they are not part of this slice.
