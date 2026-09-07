# Product vision

## Purpose

KAIRO exists to reduce cognitive load across a multi-project life without flattening everything into a generic task manager.

The system should help the user move from:

- ideas scattered across chats, notes, files, and memory;
- projects that compete for attention without a common portfolio view;
- repeated context rebuilding;
- AI assistants that only work while a conversation is open;
- model-specific silos;

toward:

- a persistent graph of projects, concepts, goals, decisions, tasks, notes, evidence, and relationships;
- an assistant that can capture spoken thoughts and turn them into durable structure;
- approved autonomous work that continues while the user is offline;
- an inspectable, human-readable memory;
- deliberate contradiction and critique instead of automatic agreement;
- model routing based on cost, task fit, and risk rather than brand loyalty.

## Primary user needs

KAIRO must eventually support all of the following, while V0 focuses on the foundations that make them possible.

### 1. Multi-level portfolio map

The user needs a visual map that can move from macro to micro:

```text
Portfolio
  -> Project
    -> Objective / Workstream
      -> Milestone
        -> Task / Idea / Decision / Knowledge
```

The map is a **view over KAIRO's domain graph**, not an independent drawing that must be maintained separately.

A node may belong to more than one context. For example, a note can be linked to both `ZTIKIX` and `Social strategy`, and a research source can support several decisions.

### 2. Voice capture

From a phone or computer, the user should be able to speak naturally:

- "note this idea for ZTIKIX";
- "remind me to revisit this after the prototype";
- "research this tonight and summarize it tomorrow";
- "criticize this idea".

KAIRO must transcribe, classify, preserve the original meaning, and ask only when ambiguity changes the resulting action.

### 3. Durable, readable memory

Important knowledge must be readable by a human without KAIRO.

KAIRO therefore uses Markdown as the portable representation for durable notes, decisions, research, and project summaries while allowing structured indexes/databases for machine use.

The memory model must distinguish at least:

- fact;
- hypothesis;
- deduction;
- opinion;
- idea;
- decision;
- unknown / insufficient evidence.

Provenance and confidence matter. A tentative remark must never silently become a confirmed decision.

### 4. Autonomous background work

KAIRO is not successful if it stops when the browser closes.

Approved work must be able to continue server-side, with:

- durable jobs;
- deadlines;
- owner (`user`, `kairo`, or an agent);
- budget limits;
- authority limits;
- status and failure history;
- resulting artefacts;
- a morning brief / notification surface.

### 5. Critic mode and constructive resistance

KAIRO should not optimize for agreement.

Normal mode should already surface important contradictions. Explicit `Critic` mode should actively examine:

1. the actual claim or proposal;
2. assumptions required for it to work;
3. evidence for and against;
4. failure modes;
5. opportunity cost;
6. simpler alternatives;
7. missing information;
8. what would falsify the thesis;
9. a recommendation and confidence level.

Encouragement should be evidence-based (progress, completed milestones, consistency), not generic praise.

### 6. Multi-project operation

KAIRO must handle several active projects simultaneously without mixing their identities, brand rules, decisions, or knowledge.

Initial known use cases include projects such as ZTIKIX and other creative/business/software initiatives. Project-specific agents or skills may be introduced when they have a clear operational purpose.

### 7. Social publishing

Later phases must support preparing, scheduling, approving, publishing, and analysing content across supported social platforms.

The architecture must keep publication permissions separate from drafting permissions. A research or writing agent must not automatically gain authority to publish externally.

### 8. Crypto intelligence

Later phases should support market-data ingestion (including CoinMarketCap where appropriate), watchlists, thesis tracking, alerts, and structured critique of investment theses.

V0 explicitly excludes autonomous trading and wallet signing.

### 9. Self-diagnosis

KAIRO should be able to inspect its own operational health and explain:

- service failures;
- expired connectors;
- failed jobs;
- storage / memory pressure;
- backup failures;
- excessive model costs;
- available updates;
- degraded capabilities.

Self-diagnosis is not permission for uncontrolled self-modification.

### 10. Cross-device continuity

The same server-side state must be available from desktop and mobile clients regardless of OS. The target client is a responsive PWA, with voice capture optimized for mobile.

## Non-goals for V0

V0 will **not** attempt to provide:

- autonomous crypto trading;
- broad unsupervised account control;
- a local LLM in production;
- every social-network integration;
- home automation;
- a finished sci-fi HUD;
- a fully autonomous self-updating system;
- a general-purpose multi-user SaaS product.

These can be revisited only after the core architecture proves useful in daily operation.

## Definition of value

A feature belongs in KAIRO only if it does at least one of the following:

- reduces cognitive load;
- saves meaningful time;
- preserves valuable context;
- improves decision quality;
- enables safe autonomous work;
- gives the user a capability they did not already have.

A feature that merely makes KAIRO look more impressive is not sufficient justification for implementation.
