# KAIRO

KAIRO is a self-hosted personal AI operating system and autonomous assistant.

It is being designed as a persistent layer between one user and their projects, ideas, tasks, knowledge, services, and AI providers. KAIRO is not intended to be a chatbot with a futuristic skin: it must preserve context over time, work while the user is offline, expose its reasoning limits, and turn conversations into durable, inspectable work.

## Status

**Phase:** V0 runtime proof / durable autonomy.

The first live vertical slice is working in an isolated local runtime: a real model call through OpenClaw can invoke KAIRO tools, create/retrieve a project, capture a tentative idea, and persist human-readable Markdown through KAIRO Core. The next gate is the corrected server-side background wake path, followed by controlled-restart recovery.

No production deployment exists yet. KAIRO is still deliberately capability-first: prove durable autonomous behavior and its safety/audit boundaries before adding the full Cockpit or production infrastructure.

See [`docs/status.md`](docs/status.md) for the current acceptance-test assessment and observed live-runtime results.

## Product principles

- **One product, few dependencies.** Prefer built-in capabilities and small libraries over a permanent collection of SaaS tools.
- **User-owned state.** Identity, project structure, memory, decisions, tasks, and audit history live under KAIRO's control.
- **Human-readable memory.** Important knowledge must remain exportable and understandable as Markdown, even if KAIRO also maintains structured indexes.
- **Autonomy over chat.** Closing the browser must not stop approved work.
- **Model-agnostic intelligence.** OpenAI and Anthropic are inference providers, not the identity or memory of KAIRO.
- **Least-cost routing.** Use no LLM when deterministic code is sufficient; otherwise use the least expensive model that meets the task's quality and risk requirements.
- **Epistemic honesty.** KAIRO distinguishes facts, hypotheses, deductions, opinions, and unknowns.
- **Constructive contradiction.** KAIRO does not flatter by default and includes an explicit critic mode.
- **Explicit authority.** External, irreversible, financial, or sensitive actions require appropriate permission.
- **Portable by design.** The UI, agent runtime, model providers, and storage implementation must remain replaceable behind stable KAIRO boundaries.

## Initial architecture

```text
PC / phone / tablet
        |
        v
+------------------+
|   KAIRO Cockpit  |  responsive PWA
+--------+---------+
         |
         v
+------------------+
|    KAIRO Core    |  domain logic and policy
+--+-----------+---+
   |           |
   |           +-------------------+
   v                               v
OpenClaw runtime              KAIRO data
agents / jobs / tools         Markdown + structured state
   |                               |
   +---------------+---------------+
                   v
              Model Router
              /          \
          OpenAI       Anthropic
             (optional local provider later)
```

OpenClaw is currently selected as the execution runtime, but KAIRO's domain model and durable data must not depend on an OpenClaw fork.

## Repository boundaries

This repository contains **source code, architecture, templates, and versioned policy**.

It must **not** contain runtime-private data such as:

- API keys or credentials;
- the live personal `USER.md` profile;
- the live knowledge vault;
- OpenClaw runtime state or session databases;
- private audio captures;
- social-network tokens;
- backups.

Those will live in encrypted/controlled runtime storage and be mounted into the application when deployed.

## Documents

- [`docs/vision.md`](docs/vision.md) — product vision and requirements
- [`docs/architecture.md`](docs/architecture.md) — current system boundaries
- [`docs/domain-model.md`](docs/domain-model.md) — conceptual model behind the project graph / mindmap
- [`docs/security-model.md`](docs/security-model.md) — authority, safety, secrets, and self-maintenance rules
- [`docs/acceptance-tests-v0.md`](docs/acceptance-tests-v0.md) — what V0 must prove
- [`docs/roadmap.md`](docs/roadmap.md) — staged implementation plan
- [`docs/status.md`](docs/status.md) — implemented/live-proven/pending capability status
- [`docs/decisions/`](docs/decisions/) — architecture decision records

## OpenClaw workspace templates

Versioned KAIRO defaults for OpenClaw live under [`config/openclaw/workspace-template/`](config/openclaw/workspace-template/).

The actual runtime workspace is created outside the Git repository. Personal memory and the live user profile are runtime data, not source code.

## Near-term milestone

The first software milestone has now been demonstrated live:

> From a KAIRO conversation, create a durable, structured idea inside a project and retrieve it later with its provenance/epistemic status intact.

The current milestone is the one that separates KAIRO from a chat UI:

> Schedule an approved internal/research task, close every client, let the server finish the job, and surface a durable outcome when the user reconnects.

After normal closed-client wake succeeds, the same path must be tested across a controlled Gateway restart before autonomous-job recovery can be considered adequate.

See the V0 acceptance tests for the complete definition of success.
