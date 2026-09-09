# ADR-025 — Routing contracts cannot grant execution authority

Status: Accepted

Date: 2026-09-09

## Context

KAIRO's Command Kernel can route a conversational request deterministically or ask PydanticAI to propose one registered capability. A routable capability often needs more execution state than the user or router should be allowed to choose.

Autonomous Research makes the distinction concrete. The HTTP execution API accepts a project, an optional tool allow-list, a model alias and a model budget, but exposing those fields in the semantic routing schema would invite the model to manufacture authority-bearing values that belong to Core policy.

A capability registry therefore needs to distinguish **intent parameters** from **execution parameters** rather than reusing every transport-specific request model as a routing contract.

## Decision

Routable capabilities expose the smallest schema required to express user intent.

For `research.autonomous`, the Command Kernel routing contract is `ResearchCommandInput`:

- `query`
- `max_tool_calls`, bounded to 1–8

It does not expose:

- `project_id`
- `allowed_tool_keys`
- `model_alias`
- `estimated_model_cost_usd`
- authority levels, policy scopes, approval state or tool risk classification

When Core accepts a Research route, it constructs the actual `ResearchRunCreate` itself. The first conversational adapter injects:

- the canonical KAIRO Assistant workspace;
- the Core-selected `local-fast` model alias;
- a Core-owned $0.02 Research model budget;
- an empty explicit tool allow-list, which means the Research runtime may see only the tools that the canonical registry independently classifies as enabled, available, read-only and A1.

The final Research Task has a deterministic ID derived from the Command ID and capability key. Retrying semantic route application therefore reuses the same canonical Task and WorkflowExecution rather than creating another research run.

Command `parameters_json` stores only the validated routing contract. Core-injected execution fields live on the final Task and must never be represented as though they came from the user or semantic model.

Explicit, high-confidence phrases such as "Fais une recherche approfondie..." may route directly to Research without paying for semantic capability routing. Specialist News routing retains priority when a request explicitly asks for current news or market-impact news.

## Consequences

- PydanticAI chooses intent, not project/model/budget/tool authority.
- Capability schemas shown to the semantic router stay small and easier to validate.
- HTTP APIs can remain richer than conversational routing contracts without widening model authority.
- Deterministic and semantic routing share the same final Research adapter and replay semantics.
- The Web Command Center can treat capability identity as the dispatch key and poll the corresponding public read model rather than assuming every accepted Task is a News brief.

## General rule

Future routable capabilities must define a dedicated intent contract whenever their execution API contains fields related to identity, workspace placement, credentials, model selection, budgets, tool permissions, side effects or approvals. Core is responsible for deriving or authorizing those values after route acceptance.
