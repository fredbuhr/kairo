# ADR-002 — Do not fork OpenClaw in V0

- **Status:** Accepted
- **Date:** 2026-09-07

## Context

A fork would give maximum control but would immediately create an upstream merge and maintenance burden while KAIRO's actual extension needs are still unknown.

## Decision

Do not fork OpenClaw in V0.

Integrate through supported workspace files, plugins/tools, and runtime APIs. Pin the OpenClaw version used by KAIRO and upgrade deliberately.

## Consequences

### Positive
- lower maintenance burden;
- easier upstream updates;
- forces clean KAIRO/OpenClaw boundaries.

### Negative
- some deep customizations may be unavailable initially.

## Revisit when

A required capability is impossible through stable/supported extension points and the business value clearly outweighs long-term fork maintenance.
