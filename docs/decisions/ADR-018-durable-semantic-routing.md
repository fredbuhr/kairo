# ADR-018 — Semantic command routing is a durable proposal-only capability

## Status

Accepted.

## Context

The deterministic Nevolium command router is intentionally conservative. This is desirable for known intents, but natural language often expresses a proven capability without using a stable keyword. For example, “Que s'est-il passé à Paris ce matin ?” is clearly a request for current local information but does not necessarily contain `news`, `actualités` or another deterministic trigger.

A semantic model can improve usability, but placing an LLM directly inside Nevolium Core would create three unacceptable bypasses:

- model calls could escape the canonical usage/budget ledger;
- provider retries could bypass Temporal replay-safety checkpoints;
- a model could be mistaken for an authority boundary and invent or directly invoke tools.

## Decision

Semantic routing is implemented as the internal Nevolium capability `assistant.route.semantic`.

### Deterministic routing remains the first tier

Known high-confidence commands continue to route without a model call. Semantic routing is used only when the deterministic router returns no route.

### Semantic routing is durable

An ambiguous command creates a canonical Task with a deterministic ID and a Temporal WorkflowExecution. The Task has its own authority ceiling and hard USD budget. Worker interruption therefore does not turn semantic routing into a best-effort HTTP request.

### PydanticAI does not own provider access

PydanticAI validates a typed `SemanticRouteProposal`, but its `FunctionModel` delegates the one permitted model turn to Nevolium's existing Worker `model_gateway`.

That gateway remains responsible for:

- Core policy authorization before provider access;
- canonical model-usage accounting;
- LiteLLM provider abstraction;
- deterministic model-call idempotency keys;
- Temporal heartbeat replay checkpoints;
- fail-closed handling of an ambiguous provider outcome.

PydanticAI therefore sits above the Nevolium model boundary rather than creating a second provider boundary.

### The model can only propose

Core sends only capabilities explicitly marked `routable=true` to the semantic router. The model returns one of those stable keys or `unsupported`.

Core then independently verifies:

- the canonical user message does not explicitly forbid execution;
- the key still exists and is routable;
- confidence meets the configured floor;
- parameters validate against the registered capability input schema;
- a concrete Nevolium adapter exists.

Only after those checks does Core launch the final capability. A provider response cannot invent an MCP tool, HTTP endpoint, specialist engine or hidden action.
An explicit classification-only or no-execution instruction remains auditable but makes the command
terminal as `semantic.execution-veto`, even if the model proposes a valid capability with high confidence.

### One logical model turn for V1

The semantic PydanticAI agent uses zero automatic output retries. If the first provider response fails structured validation, Nevolium records an unsupported proposal rather than silently spending a second model call.

Multi-turn structured repair may be enabled later only after the model gateway can checkpoint multiple named model-call slots inside one durable Activity.

### Final capability handoff is replay-safe

For semantic commands, the final capability Task ID is derived deterministically from `command_id + capability_key + contract_version`. If the semantic Activity loses the Core response after the final Task was created, replay returns the existing Task/Workflow rather than creating another side effect.

## Consequences

- Natural phrasing becomes usable without weakening deterministic routes.
- Cheap/local models can classify routine requests while paid models remain replaceable LiteLLM fallbacks.
- Every semantic model call is budgeted and accounted like other Nevolium model usage.
- Model output remains untrusted proposal data until Core validation.
- Semantic routing survives Worker interruption without duplicating the final capability Task.
- The same architecture can later route to Projects, Calendar, Research, Finance and Home capabilities as those contracts become real.
