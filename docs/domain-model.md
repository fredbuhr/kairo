# Domain model

KAIRO's mindmap is a view over a domain graph. The graph must support both hierarchical navigation and cross-links between concepts.

## Core entity types

### Project
A durable body of work with its own goals, context, decisions, assets, and workstreams.

Minimum fields:
- `id`
- `name`
- `status`
- `summary`
- `created_at`
- `updated_at`
- `parent_id` (optional)

Suggested statuses:
- inbox
- incubation
- active
- waiting
- paused
- completed
- archived

### Objective
A desired outcome attached to a project or portfolio.

### Workstream
A coherent stream of work inside a project.

### Milestone
A meaningful checkpoint with a target state/date.

### Task
An actionable unit of work.

Important task fields:
- owner: `user | kairo | agent:<id>`
- status: `todo | queued | running | blocked | waiting_user | waiting_external | completed | abandoned | failed`
- deadline (optional)
- budget (optional)
- authority ceiling
- dependencies
- resulting artefacts

### Idea
A proposal that is not yet a decision.

An idea can have:
- status (`captured`, `exploring`, `incubation`, `promoted`, `rejected`)
- rationale
- critic report
- linked research
- review date

### Decision
A choice that has actually been made.

A decision records:
- decision statement;
- date;
- rationale;
- alternatives considered;
- consequences;
- evidence/sources;
- confidence where relevant;
- superseded-by relationship.

### Note
Free-form human-readable knowledge that does not yet require a more specific type.

### Knowledge claim
A claim with epistemic metadata.

Minimum epistemic status:
- `fact`
- `hypothesis`
- `deduction`
- `opinion`
- `unknown`

A claim should support provenance, confidence, last verification date, and source links where applicable.

### Source
A document, URL, dataset, conversation excerpt, or other evidence object.

### Asset
A file such as an image, video, audio item, PDF, CSV, design source, or generated artefact.

### Metric
A time-series or point-in-time measurement associated with a project/entity.

### Automation / Standing order
A repeatable rule that can produce jobs.

### Job
A specific execution instance, possibly autonomous.

### Agent
A runtime worker identity or specialization. An agent is not automatically a domain owner; it acts under task and permission policy.

## Relationships

Relationships are first-class. Examples:

- `PROJECT contains WORKSTREAM`
- `WORKSTREAM targets OBJECTIVE`
- `TASK advances MILESTONE`
- `IDEA belongs_to PROJECT`
- `IDEA related_to IDEA`
- `DECISION resolves IDEA`
- `DECISION supersedes DECISION`
- `KNOWLEDGE_CLAIM supported_by SOURCE`
- `TASK depends_on TASK`
- `JOB executes TASK`
- `JOB produces ASSET`
- `METRIC measures PROJECT`

KAIRO should never force every relationship into a folder hierarchy.

## Mindmap levels

The default visual drill-down should roughly follow:

```text
Portfolio
 -> Domain / Project
   -> Objective / Workstream
     -> Milestone
       -> Task / Idea / Decision / Knowledge / Metric
```

This is a presentation convention, not a storage limitation.

## Markdown representation

Important durable entities should be exportable as Markdown with stable front matter.

Example:

```markdown
---
id: idea_0001
type: idea
project: ztikix
status: incubation
created: 2026-09-07
epistemic_status: hypothesis
confidence: 0.65
---

# Rage Bait reaction

## Idea
Create a ZTIKIX reaction around the concept of rage bait.

## Why
...

## Links
- [[ZTIKIX]]
- [[Social strategy]]
```

The exact schema will evolve; stable IDs and explicit types are the important V0 constraints.

## Invariants

- An **idea is not a decision**.
- A **deduction is not a fact**.
- A task created for KAIRO must carry an authority ceiling before execution.
- Important generated conclusions must retain provenance to the job and sources that produced them.
- Archiving an entity must not silently delete history.
