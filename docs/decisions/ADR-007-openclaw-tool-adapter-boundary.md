# ADR-007 — Keep OpenClaw behind a KAIRO tool adapter

## Status

Accepted for V0.

## Context

KAIRO currently uses OpenClaw as its agent/runtime layer, while KAIRO Core owns durable project knowledge and domain invariants. The first useful vertical slice requires OpenClaw to create and retrieve KAIRO entities.

Allowing a model or OpenClaw agent to write Markdown files directly would bypass KAIRO's validation, project isolation, provenance, stable IDs, and future storage adapters. Embedding OpenClaw-specific types inside KAIRO Core would create the opposite problem: the core would become difficult to reuse if the runtime changes.

OpenClaw provides a supported tool-plugin API (`defineToolPlugin`) with static discovery metadata and explicit runtime configuration.

## Decision

Expose KAIRO capabilities to OpenClaw through a dedicated plugin package.

The boundary is:

```text
OpenClaw / model
    -> kairo_* tool contract
        -> @kairo/core
            -> KAIRO storage adapter
```

For V0:

- tool names are stable, lowercase KAIRO-prefixed API names;
- runtime storage location is plugin configuration, never model input;
- plugin tools call KAIRO Core rather than manipulating files directly;
- read/list tools should return compact data where possible to reduce model context;
- tools that retrieve one entity may return its human-readable body;
- durable external side effects beyond KAIRO-internal A1 writes are not added to this plugin yet;
- OpenClaw is pinned in development/CI so upstream SDK changes are detected explicitly.

## Consequences

### Positive

- OpenClaw can be upgraded or replaced without migrating the KAIRO domain model.
- Domain rules are enforced consistently for UI, agents, scripts, and future APIs.
- The model does not control filesystem paths.
- Tool contracts become an auditable seam for permissions and telemetry.
- The adapter can stay small and tested against real OpenClaw plugin contracts.

### Negative

- There is an additional adapter package to maintain.
- Some OpenClaw context (for example session provenance) may require explicit adapter work rather than being available automatically.
- Local development needs both OpenClaw SDK dependencies and KAIRO Core.

## Revisit when

- KAIRO Core becomes a network service and the plugin should call a local authenticated API instead of importing the package;
- a required runtime capability cannot be represented safely through supported OpenClaw plugin APIs;
- OpenClaw is replaced as the execution runtime.
