# KAIRO implementation status

Last updated: 2026-09-07

This document describes what exists in code today. It is intentionally stricter than the long-term roadmap.

## Implemented and versioned

### Product / architecture

- vision, non-goals, and portability principles;
- OpenClaw selected as V0 execution runtime without forking it;
- KAIRO Core remains runtime/provider independent;
- human-readable Markdown-first durable knowledge;
- authority model A0-A5;
- explicit epistemic states;
- V0 acceptance tests and staged roadmap.

### KAIRO Core

Durable project-scoped domain state currently includes:

- Projects and parent relationships;
- Ideas;
- Decisions;
- Tasks with owner/authority/budget fields;
- KnowledgeClaims with epistemic status/confidence/source IDs;
- Sources;
- KAIRO Jobs with lifecycle state and scheduler linkage.

Storage is a filesystem/Markdown V0 adapter with stable IDs and atomic writes. No database has been selected yet.

### OpenClaw adapter

The validated `kairo-tools` plugin exposes tools for:

- project create/list/get;
- idea capture/list/get;
- source capture/get;
- knowledge-claim capture/get;
- job list/get/start/complete/fail;
- bounded future background scheduling.

Background scheduling:

- uses OpenClaw Cron-backed `scheduleSessionTurn`;
- creates a durable KAIRO Job before external scheduling;
- links the OpenClaw scheduler handle to the KAIRO Job;
- records scheduler failure durably;
- limits V0 background authority to A0-A2;
- instructs the future turn to use explicit Job lifecycle calls;
- supports an advisory requested model budget but does not hard-enforce it yet.

### Automated validation

GitHub Actions currently validates:

- KAIRO Core tests on Node 22;
- OpenClaw plugin TypeScript build;
- generated plugin metadata consistency;
- adapter/core integration tests;
- OpenClaw plugin validation against the pinned development release.

## Not yet proven live

The code path is tested/validated, but no persistent local/VPS Gateway has yet demonstrated the full user scenario with real model calls.

The next mandatory proof is:

1. load the real KAIRO plugin into an isolated OpenClaw Gateway;
2. capture/retrieve an idea across sessions;
3. schedule a KAIRO background job;
4. close the client while leaving the Gateway running;
5. confirm the future turn wakes and updates durable Job/source/knowledge state;
6. repeat around a controlled Gateway restart.

See `docs/runbooks/dev-openclaw-runtime.md`.

## Explicitly unfinished

- hard model budget enforcement;
- actual token/provider/model cost accounting;
- stale queued/running Job reconciliation after crashes;
- model router (OpenAI/Anthropic choice);
- Critic mode implementation;
- full portfolio graph API;
- Cockpit/PWA and mindmap visualization;
- voice input;
- production VPS deployment/auth/HTTPS/backups;
- social publishing;
- CoinMarketCap/crypto module;
- optional local inference.

## Current engineering rule

Do not implement the Cockpit or add more infrastructure before the live runtime proof reveals what is actually missing.

The next failure should drive the next piece of code.
