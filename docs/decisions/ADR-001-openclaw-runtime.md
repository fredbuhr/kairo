# ADR-001 — Use OpenClaw as the initial agent runtime

- **Status:** Accepted
- **Date:** 2026-09-07

## Context

KAIRO needs persistent agent sessions, tools, background work, workspace bootstrap files, and runtime diagnostics. Rebuilding all of that from scratch would delay validation of the actual product value.

## Decision

Use OpenClaw as the initial execution/runtime layer for V0.

KAIRO-specific domain logic and durable user state remain outside the OpenClaw core boundary wherever practical.

## Consequences

### Positive
- faster path to durable agents/jobs;
- existing workspace contract (`AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md`, optional `MEMORY.md`);
- ability to use supported tools/plugins before modifying upstream code;
- easier experimentation with multiple providers.

### Negative
- KAIRO inherits some runtime constraints and upgrade risk;
- a future runtime migration may require an adapter rewrite.

## Revisit when

A critical KAIRO capability cannot be implemented through supported OpenClaw APIs/plugins/workspace contracts without invasive patches.
