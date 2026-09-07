# Architecture

## Goals

KAIRO's architecture must preserve four properties from the start:

1. **Durable autonomy** — approved jobs survive closed clients and server restarts.
2. **Portable memory** — important knowledge remains readable outside the runtime.
3. **Replaceable intelligence** — model providers are adapters, not the identity of KAIRO.
4. **Replaceable execution runtime** — OpenClaw is the current runtime, but KAIRO's domain state must remain separable.

## High-level system

```text
Clients (PWA / mobile browser / desktop browser)
                    |
                    v
              KAIRO Cockpit
                    |
                    v
               KAIRO Core
       +------------+-------------+
       |                          |
       v                          v
OpenClaw adapter/runtime      KAIRO domain store
agents, jobs, tools           graph + Markdown vault
       |                          |
       +------------+-------------+
                    v
               Model Router
              /           \
          OpenAI        Anthropic
          (more providers later)
```

## Boundary decisions

### KAIRO Core

KAIRO Core owns domain logic that must survive any future runtime change:

- projects and portfolio hierarchy;
- ideas, decisions, notes, objectives, milestones, tasks;
- provenance and epistemic status;
- authority policy;
- model-routing policy;
- cost accounting;
- job intent and resulting artefacts;
- API contracts used by the Cockpit and runtime adapters.

KAIRO Core must not expose provider-specific concepts to the rest of the product unless unavoidable.

### OpenClaw

OpenClaw currently provides the execution runtime: agent sessions, tools, sub-agents, scheduled/background execution, channels, and runtime health features.

KAIRO will integrate through supported OpenClaw workspace files, tools/plugins, and runtime APIs before considering any fork.

OpenClaw's documented workspace contract currently includes `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md`, optional `MEMORY.md`, and a one-time `BOOTSTRAP.md`. KAIRO therefore keeps versioned **templates** for these files while the live workspace remains runtime-private.

### Data

KAIRO uses two representations with different purposes:

**Human-readable durable knowledge**
- Markdown files;
- attachments / assets referenced by stable IDs;
- exportable without proprietary tooling.

**Machine-operational state**
- structured database/index for graph relationships, job state, model cost, permissions, and search metadata;
- implementation is deliberately not fixed in V0 beyond requiring a clean repository/service boundary.

V0 should avoid selecting PostgreSQL, a vector database, or a graph database until the first domain use cases prove what is actually needed. SQLite or OpenClaw-owned state may be sufficient for the first prototype, while KAIRO's domain interface remains stable.

## Repository vs runtime state

Version-controlled:

```text
docs/
config/openclaw/workspace-template/
config/policies/
schemas/
future source code
```

Runtime-private and ignored:

```text
runtime/
data/
secrets/
live vault
live USER.md / MEMORY.md
audio captures
OpenClaw state databases
provider credentials
```

The live personal profile is intentionally not committed even though the repository is private. Git history is difficult to erase safely and may later be mirrored or shared for development.

## Model routing

The router evaluates, at minimum:

- whether an LLM is required at all;
- task type;
- complexity;
- context size;
- consequence of error;
- latency requirement;
- provider/model capability;
- estimated cost;
- explicit user quality request;
- later: empirical success rate for this user/task class.

V0 providers:

- OpenAI;
- Anthropic.

Reserved adapters:

- Mistral / other cloud providers;
- local OpenAI-compatible endpoint.

The local adapter remains architecturally possible but is not a V0 deployment requirement.

## Cockpit

The target daily interface is a responsive PWA, not the OpenClaw administration UI.

The Cockpit will eventually expose:

- portfolio graph / mindmap;
- project drill-down;
- Workboard / autonomous jobs;
- approvals;
- conversation;
- voice capture;
- morning brief;
- system health;
- model cost;
- later: social and crypto modules.

The first UI implementation should follow working domain data, not precede it.

## Authentication and exposure

V0 is single-user.

Principles:

- do not expose OpenClaw's administrative surface directly to the public Internet;
- use HTTPS for all user-facing access;
- separate application authentication from provider API credentials;
- use least-privilege tokens for external integrations;
- keep secrets outside Git;
- maintain tested backups before enabling autonomous writes.

Exact VPN / reverse-proxy / identity-provider choices are deployment decisions and are intentionally not fixed yet.

## Observability

Every autonomous execution should eventually produce an audit record containing:

- trigger;
- project / task;
- agent or worker;
- models used;
- provider cost;
- tools/actions used;
- external side effects;
- output artefacts;
- errors/retries;
- approval events.

This is required for trust, debugging, cost control, and future self-diagnosis.

## Evolution rule

Do not add infrastructure because it is fashionable or theoretically scalable.

A new database, queue, workflow engine, SaaS, or framework must solve a demonstrated limitation and be recorded as an architecture decision.
