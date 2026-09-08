# KAIRO vision

## Product definition

KAIRO is a self-hosted Personal AI Operating System that gives one user a persistent, inspectable and increasingly autonomous intelligence layer across their work and personal systems.

The product should feel like one coherent application even though it delegates specialized capabilities to multiple open-source engines.

## Core promise

KAIRO should be able to answer and act on questions that cross application boundaries, for example:

- What is blocking ZTIKIX right now?
- Re-plan the launch after this dependency slipped by a week.
- Show this project's knowledge structure as a 3D map and turn these nodes into tasks.
- Prepare a research brief, attach the evidence, create the resulting decisions and update the Gantt.
- Summarize my crypto exposure and prepare a transaction proposal without exposing a signing key to an LLM.
- Work on this repository, run tests, produce a diff and ask for approval before deployment.
- Tell me what needs my attention today across projects, messages, calendar, finances and autonomous jobs.

## Product spaces

The Cockpit is expected to converge on these integrated spaces:

- Command Center / chat / voice;
- Today / brief / attention queue;
- Projects and portfolio;
- tasks, Kanban, milestones and simple-but-powerful Gantt;
- Knowledge, notes, documents and universal search;
- 2D mindmap, realtime 3D mindmap and knowledge graph;
- Calendar and time planning;
- People / contacts / relationship context;
- Inbox / notifications / approvals;
- Research;
- Automations;
- Agents and skills;
- Computer / browser / local-device actions;
- Developer workspace;
- Crypto;
- personal finance;
- home and devices;
- analytics and dashboards;
- maps and places;
- model/cost control;
- permissions, audit, backups and system health.

## Product principles

### One product, replaceable engines
The user sees KAIRO, not a collection of embedded admin UIs. Specialist engines sit behind KAIRO-owned adapters.

### Complete dependency graph early
Core infrastructure is selected and represented from the beginning so data ownership, security boundaries, identity, events and service dependencies are explicit before feature work expands.

### Canonical state stays under KAIRO control
Projects, tasks, people, approvals, audit records, agent intents, financial proposals and product relationships cannot be trapped inside a workflow engine, chat history or third-party service.

### Derived systems are rebuildable
Embeddings, memory indexes, knowledge graphs, caches and search indexes are projections. Losing one must not destroy canonical KAIRO state.

### Autonomy is durable
Approved work survives closed clients, process restarts and transient failures. Temporal is the durable execution substrate; KAIRO policy remains authoritative over what that work may do.

### Authority is explicit
External side effects and sensitive actions are gated by policy and approvals. Crypto signing is isolated from AI execution.

### Intelligence is model-agnostic
Cloud and local models are providers, not KAIRO's identity or memory. LiteLLM provides a stable routing boundary.

### No-LLM first
Deterministic code should solve deterministic problems. When an LLM is needed, KAIRO selects the least-cost model that meets quality, latency and risk requirements.

### Epistemic honesty
Facts, hypotheses, deductions, opinions and unknowns remain distinguishable with provenance and verification dates.

### Inspectability
Every autonomous action can be traced to its trigger, policy, tool usage, model usage, cost, approvals and resulting artefacts.

### Portable interaction
Web, desktop and later mobile clients use stable KAIRO APIs. A local Sidecar exposes device capabilities without making the server omnipotent over the user's machine.

## Non-goals

KAIRO should not:

- rebuild generic databases, workflow engines, vector search, browser automation or home automation from scratch;
- expose another project's admin UI as the primary user experience;
- let agents bypass approval policy because a tool happens to be reachable;
- store wallet seeds/private keys in prompts, chat logs, memory systems or source control;
- couple canonical state to a single AI provider or agent framework;
- silently self-update core policy or production code.
