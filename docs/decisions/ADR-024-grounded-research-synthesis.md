# ADR-024 — Research synthesis is evidence-bound and replay-safe

## Status

Accepted for the second autonomous research slice.

## Context

ADR-023 deliberately stopped autonomous research after one planning model turn plus canonical read-only MCP child results. That proved tool authority and deterministic child invocation, but it did not yet produce a useful final answer.

Adding a synthesis turn introduces two risks that Nevolium must not hide:

1. a later Temporal heartbeat could erase the replay state of the earlier planning call and cause a paid provider call to be repeated after retry;
2. an unconstrained synthesizer could treat model memory or malicious tool output as authority and invent unsupported conclusions.

## Decision

`research.autonomous` now has two named logical model slots:

- `research-plan-v1`;
- `research-synthesis-v1`.

Both use the same bounded `ModelCheckpointLedger`, so every heartbeat carries the known state of both slots. A retry may replay a known accounted result or resume idempotent accounting, but an ambiguous provider outcome still fails closed.

The existing `estimated_model_cost_usd` remains the total parent research model budget. Nevolium reserves that ceiling across planning and synthesis rather than treating it as a per-call allowance.

Completed MCP child results are transformed into stable evidence records (`E1` through `E8`) before synthesis. Only a bounded excerpt enters the model context; the canonical raw child results remain preserved separately in the research artifact.

The synthesis model receives evidence as untrusted data. It is instructed never to follow instructions contained in evidence and to answer only from the supplied records. Structured factual claims must reference one or more supplied evidence IDs. Nevolium independently rejects any synthesis that cites an evidence ID outside the supplied set.

If no admissible evidence was collected, Nevolium does not ask a model to improvise an answer. It returns an explicit deterministic no-evidence result.

## Consequences

- research now produces a directly useful answer while retaining inspectable claim-to-tool provenance;
- prompt size is bounded independently of potentially large MCP tool responses;
- tool-output prompt injection does not gain authority merely by appearing in retrieved data;
- the second model turn cannot silently double the user-requested model budget;
- richer iterative research can add future named model slots without changing the replay rule;
- semantic quality is still limited by the current read-only tool set and does not yet include Nevolium memory/document retrieval.

## Rejected alternatives

### Send raw tool output directly to a free-form completion

Rejected because it has no stable evidence identifiers, no bounded prompt contract and no machine-checkable provenance map.

### Let the model cite arbitrary URLs or source names

Rejected for this slice because those references are model-authored strings. Nevolium instead binds claims to canonical child invocation evidence IDs; richer source-level citations can be derived from typed MCP results later.

### Give planning and synthesis separate full budgets

Rejected because two model calls must not silently double the authority/cost envelope requested for one research Task.
