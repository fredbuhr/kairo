# ADR-023 — Autonomous research is orchestration, not authority

## Status

Accepted for the first autonomous research slice.

## Context

KAIRO now has a canonical MCP tool registry, explicit enablement, authority classification, Temporal policy gates and replay-safe tool invocations. The next requirement is to let an agent choose useful tools without turning model output into an authority source.

A naive agent loop that connects PydanticAI directly to MCP would bypass the controls already established by KAIRO. It would also make retries dangerous because a model/tool loop could repeat remote side effects after Worker failure.

## Decision

`research.autonomous` is a durable parent Task with authority level 1. PydanticAI receives only the subset of the registry that Core currently considers eligible for autonomous research:

- server enabled;
- tool available and explicitly enabled;
- `risk_class=read`;
- `authority_level=1`;
- optional user allow-list satisfied.

The model produces a proposal only. Core independently validates the proposed tool key and its JSON Schema input.

Every accepted proposal becomes a normal canonical `ToolInvocation` plus a deterministic child `tool.invoke` Task. The child Task runs through the existing Temporal policy gate and the MCP runtime revalidates the live registry/policy snapshot immediately before the network call.

The deterministic child identity is derived from `(research parent task, tool slot, tool key)`. Replaying the parent activity therefore reattaches to the same child invocation instead of creating a second remote call.

The v1 planner has one accounted model-call slot. The initial result intentionally contains the plan and canonical child tool results without a second model synthesis turn. This keeps replay semantics explicit while the multi-slot model checkpoint abstraction is still being designed.

## Consequences

- A model cannot grant itself access to write or destructive tools.
- Disabling a tool after planning but before execution is respected by the child runtime.
- Research retries do not create duplicate tool invocations for the same logical slot.
- Tool provenance remains inspectable because raw child invocation results are preserved in the parent artifact.
- Rich synthesis, iterative replanning and mixed-authority agents require later ADRs and additional replay-safe model-call slots.

## Rejected alternatives

### Give PydanticAI direct MCP tools

Rejected because MCP transport metadata is not an authority boundary and direct execution would bypass KAIRO's canonical Task, policy and audit model.

### Allow all enabled tools and rely on approval prompts

Rejected for the first autonomous slice. Autonomous research is intentionally read-only/A1; higher authority operations belong to explicit specialist workflows.

### Let the model synthesize and call tools in an unconstrained loop

Rejected until KAIRO has first-class durable multi-turn/multi-slot model checkpoints. Hidden model retries or repeated tool calls are unacceptable for a replayable personal agent.
