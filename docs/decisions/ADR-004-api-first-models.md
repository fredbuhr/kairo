# ADR-004 — API-first model strategy

- **Status:** Accepted
- **Date:** 2026-09-07

## Decision

Start with external AI APIs only.

Initial providers:
- OpenAI;
- Anthropic.

A local OpenAI-compatible provider remains a reserved future adapter but is not a V0 deployment requirement.

KAIRO will route tasks by capability, risk, and cost, and should avoid LLM calls entirely when deterministic code is sufficient.

## Rationale

This keeps V0 simpler, cheaper to host, faster to iterate, and easier to benchmark while preserving future local-inference optionality.

## Revisit when

Measured API cost, privacy requirements, latency, availability, or local-model quality justify running inference on owned hardware/server resources.
