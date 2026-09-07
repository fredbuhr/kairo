# V0 core implementation notes

## First vertical slice

The first implementation is deliberately narrower than the complete domain model. `@kairo/core` now provides a filesystem-backed domain API for the records needed to prove durable capture:

- `createProject`
- `captureIdea`
- `recordDecision`
- `createTask`
- `captureKnowledgeClaim`
- `captureSource`
- retrieval helpers for each type

Important invariants are enforced in code:

- ideas and decisions are separate entity types;
- knowledge claims require `fact | hypothesis | deduction | opinion | unknown`;
- task authority is constrained to `A0` through `A5`;
- unknown projects fail explicitly instead of silently creating data in an unintended scope;
- IDs are stable UUID-based identifiers rather than filenames or titles;
- project nesting is represented with stable parent IDs plus a readable parent slug.

## Why JavaScript first

The V0 core is plain ESM JavaScript on Node and uses only built-in modules. This avoids choosing a build system before the domain contracts are stable. OpenClaw's tool-plugin SDK is TypeScript-oriented and requires a modern Node runtime; the OpenClaw adapter may therefore use TypeScript later without forcing the portable KAIRO domain core to depend on it.

## What this does not solve yet

- semantic/full-text search;
- cross-link graph indexes;
- model routing;
- autonomous job persistence;
- approvals;
- Cockpit API;
- voice;
- social/crypto integrations;
- multi-writer concurrency.

Those remain separate milestones rather than hidden complexity inside the first store.
