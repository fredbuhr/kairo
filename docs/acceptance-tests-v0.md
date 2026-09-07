# V0 acceptance tests

KAIRO V0 is complete only when it demonstrates durable knowledge, durable autonomous work, epistemic honesty, and cross-device continuity. A polished interface is not sufficient.

## AT-01 — Durable idea capture

**Given** a project exists (for example ZTIKIX)

**When** the user says or types:

> Kairo, record this as an idea for ZTIKIX: ...

**Then** KAIRO must:

- create a stable idea ID;
- store it under the correct project;
- preserve the original meaning;
- mark it as an `idea`, not a decision;
- retain creation timestamp and provenance;
- expose a human-readable Markdown representation;
- retrieve it in a later session.

## AT-02 — Epistemic status

**When** the user expresses uncertainty (for example, "I think X may be true")

**Then** KAIRO must not persist X as a confirmed fact.

The stored representation must distinguish hypothesis/deduction/opinion from fact.

## AT-03 — Critic mode

**When** the user invokes Critic mode on an idea

**Then** the result must explicitly cover:

- assumptions;
- evidence for/against;
- failure modes;
- opportunity cost;
- simpler alternatives;
- missing information;
- falsification conditions;
- recommendation and confidence.

The critic report must link back to the original idea rather than overwrite it.

## AT-04 — Autonomous overnight job

**Given** the user creates a research task with a deadline, cost ceiling, and A1/A2 authority only

**When** all browser/phone clients are closed

**Then** the server must be able to:

- start/continue the job;
- survive at least one controlled runtime restart or recover safely;
- perform only authorized actions;
- produce a durable report with sources/provenance;
- record models/tools/cost used;
- mark the job completed or failed with an explanation;
- surface the outcome on the next client connection / morning brief.

This is the key non-gadget acceptance test.

## AT-05 — Permission boundary

**Given** an autonomous job has maximum authority A2

**When** it determines that publishing externally would be useful

**Then** it may prepare the publication but must not publish it.

It must create an approval request instead.

## AT-06 — "I don't know"

**When** KAIRO cannot answer from reliable available information

**Then** it must explicitly state the limitation rather than invent a fact.

Where useful it may propose a research action, but the uncertainty must remain visible.

## AT-07 — Model routing

For each LLM-backed execution, KAIRO must record:

- provider;
- model;
- token/usage metadata where available;
- estimated or reported cost;
- task classification / routing reason.

A deterministic task that does not need an LLM should not make an LLM call.

## AT-08 — Multi-project isolation

**Given** two active projects have different brand rules/context

**When** KAIRO works on one project

**Then** it must not silently import the other project's rules, decisions, or assets unless an explicit relationship exists.

## AT-09 — Portfolio drill-down

The domain API must support retrieving a hierarchy from portfolio level down to project/workstream/milestone/task/idea/decision/knowledge entities, plus cross-links.

A graphical mindmap is not required to pass V0; the data model and navigation contract are.

## AT-10 — Human-readable export

Important durable knowledge must remain exportable/readable without KAIRO through Markdown and ordinary referenced files.

The user must not need a proprietary database viewer to understand their project decisions and notes.

## AT-11 — Health visibility

KAIRO must provide a minimal health report covering at least:

- core/runtime reachable;
- job runner state;
- storage availability;
- last successful backup (once backups are implemented);
- AI provider connectivity state without exposing secrets;
- failed jobs.

## AT-12 — Cross-device state

A change created from one supported browser/device must be visible from another after synchronization with the server without manually copying local files.

## V0 exit criterion

The following scenario must work end-to-end:

> From a phone, capture an idea for a project, ask KAIRO to critique it and research comparable approaches overnight within a fixed budget, close the phone, then open KAIRO from a computer the next morning and find the original idea, the critic report, sourced overnight research, job history, cost, and recommendation linked in the project graph.

If this scenario does not work reliably, V0 is not complete regardless of UI quality.
