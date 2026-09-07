# ADR-005 — Separate KAIRO Cockpit from OpenClaw admin UI

- **Status:** Accepted
- **Date:** 2026-09-07

## Decision

Build a dedicated responsive KAIRO PWA for daily use instead of deeply customizing the OpenClaw administrative interface.

Use OpenClaw's UI as an administration/diagnostic fallback only.

## Rationale

KAIRO needs a portfolio mindmap, voice capture, approvals, morning brief, project drill-down, cost visibility, and mobile-first interaction. These are product requirements, not generic runtime-administration requirements.

Separating the Cockpit also keeps OpenClaw replaceable.

## Consequences

- additional frontend work;
- much better control over UX and identity;
- cleaner runtime/product separation.
