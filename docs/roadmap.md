# Roadmap

The roadmap is intentionally capability-first. A visually impressive cockpit is not a milestone unless the underlying capability is real.

## V0 — Foundations

### Phase 0A — Architecture and policy

- define product vision;
- define KAIRO/OpenClaw boundary;
- define domain graph;
- define authority levels;
- define OpenClaw workspace templates;
- define V0 acceptance tests;
- keep live user data out of source control.

**Exit:** architecture review accepted.

### Phase 0B — Runtime bootstrap

- install a pinned OpenClaw release in a development environment;
- create a KAIRO runtime workspace from templates;
- configure OpenAI + Anthropic via environment/runtime secrets;
- establish basic health checks;
- establish local/dev backup procedure.

**Exit:** KAIRO can hold a conversation through the runtime with its own identity/policy and no secrets in Git.

### Phase 0C — Durable domain capture

Implement the smallest KAIRO Core surface for:

- project;
- idea;
- decision;
- task;
- knowledge claim/source;
- stable IDs and Markdown export.

Expose the first OpenClaw integration tools, beginning with idea capture/search.

**Exit:** Acceptance tests AT-01 and AT-02 pass.

### Phase 0D — Critic and provenance

- Critic mode;
- source/provenance links;
- recommendation + confidence recording;
- prevent generated critique from overwriting original material.

**Exit:** AT-03 and AT-06 pass.

### Phase 0E — Durable autonomous jobs

- task/job contract;
- background scheduling;
- budget/authority ceilings;
- artefact persistence;
- morning-brief data surface;
- failure/retry visibility.

**Exit:** AT-04, AT-05, AT-07 pass.

### Phase 0F — Portfolio navigation

- hierarchical + cross-linked project graph API;
- minimal web interface for project drill-down;
- cross-device server state.

**Exit:** AT-08, AT-09, AT-10, AT-12 pass.

### Phase 0G — Health and backup

- minimal KAIRO health endpoint;
- OpenClaw/runtime diagnostic integration;
- tested backup/restore of KAIRO data;
- update-available reporting without unattended core updates.

**Exit:** AT-11 passes and the full V0 exit scenario is repeatable.

## V1 — Daily-use KAIRO

Only after V0 proves useful:

- responsive KAIRO Cockpit PWA;
- portfolio mindmap visualization;
- mobile voice capture and transcription;
- approval inbox;
- Morning Brief UI;
- cost dashboard;
- stronger Focus Guardian / portfolio-limit behavior;
- production deployment on a European VPS.

## V1.x — Project integrations

Add only integrations with a concrete workflow and API support:

- social content planning/publishing;
- CoinMarketCap / market-data intelligence;
- email/calendar if useful;
- project-specific ZTIKIX skills and analytics;
- additional model provider such as Mistral if it materially improves cost/privacy/quality.

## V2 — Re-evaluate local inference

Do not deploy a local LLM merely because it is possible.

Revisit when measured API spend, privacy requirements, hardware economics, or local-model quality justify it. The existing model-provider adapter must allow addition without redesigning KAIRO Core.

## Backlog principles

Before promoting a feature from backlog, answer:

1. Which user problem does it solve?
2. Does an existing KAIRO/OpenClaw capability already solve it?
3. Is it required for the current acceptance test?
4. Does it add a new service or maintenance burden?
5. Can it wait until usage data proves the need?

If the answers do not justify implementation, keep it in incubation.
