# ADR-021 — Langfuse is a correlated observability projection

Status: accepted

Date: 2026-09-08

## Context

KAIRO now has multiple model-bearing durable workflows. The canonical model gateway already owns policy authorization, replay safety and PostgreSQL usage accounting, while Langfuse + ClickHouse are declared as the AI observability stack.

Adding traces after tool-bearing agents are implemented would force correlation to be reconstructed from logs. Conversely, allowing an observability backend to sit on the execution authority path would make a tracing outage capable of changing KAIRO behavior.

## Decision

Langfuse is a non-authoritative observability projection fed by LiteLLM's OpenTelemetry callback.

1. **KAIRO creates correlation identity.** Every logical model invocation already has a stable model-call idempotency key. The model gateway now also derives a stable W3C-compatible 32-hex trace ID from the canonical KAIRO correlation UUID, or from task/workflow identity when no UUID correlation is available.
2. **LiteLLM is the telemetry fan-out point.** KAIRO does not add a second Langfuse SDK/provider path inside Worker activities. LiteLLM receives KAIRO trace metadata with the model request and its `langfuse_otel` callback exports the resulting generation span.
3. **Canonical authority stays in Core.** Langfuse never authorizes a model call, grants an approval, decides replay, computes the canonical task budget or inserts the canonical model-usage record. PostgreSQL audit/model-usage records remain authoritative even when Langfuse is unavailable or deleted.
4. **Trace metadata is correlation-only.** It contains stable task/workflow/model-call identifiers, model alias, session ID and tags. It does not duplicate prompt/message content into custom metadata. The normal model request/response may still be visible to self-hosted Langfuse through LiteLLM tracing.
5. **Self-hosting is reproducible.** The KAIRO Compose overlays pass Langfuse headless organization/project/API-key initialization variables to the Langfuse application containers. The same project keys are passed to LiteLLM, so a fresh installation does not require manually creating a project in the Langfuse UI before traces can flow.
6. **No hard service dependency.** LiteLLM does not declare `depends_on: langfuse-web`; the observability service is not an execution prerequisite. Infrastructure monitoring may report missing traces, but KAIRO's canonical execution state does not derive from trace delivery.

## Trace mapping

For each model call:

- `trace_id`: canonical KAIRO correlation UUID rendered as 32 lowercase hex, or a deterministic SHA-256-derived 32-hex fallback;
- `session_id`: workflow execution ID when available, otherwise task ID;
- `generation_name`: `kairo.model.invoke`;
- `tags`: `kairo` plus the model alias;
- custom metadata: task ID, workflow execution ID, model-call key and model alias.

The logical model-call key remains distinct from the trace ID: one trace can contain multiple future model/tool observations while every provider call keeps its own replay/accounting identity.

## Consequences

- model and future tool-bearing workflows can be correlated in Langfuse from day one;
- deleting/rebuilding Langfuse does not remove authoritative KAIRO history;
- observability does not introduce another model/provider client library inside Temporal activities;
- future MCP/tool spans should reuse the same KAIRO trace identity rather than inventing a parallel correlation scheme;
- Langfuse data must be treated as potentially containing model inputs/outputs and protected accordingly.

## Validation

The existing deterministic model-gateway contract now proves that a provider request carries the expected W3C trace metadata while preserving all replay-safe/accounting invariants. Compose validation proves that development and production overlays provide matching headless Langfuse credentials and LiteLLM OTEL endpoint configuration.
