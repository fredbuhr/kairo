# ADR-011 — Declare the full platform foundation early

**Status:** Accepted

## Decision

KAIRO will declare the complete selected platform dependency graph at the architecture/foundation stage rather than adding foundational infrastructure only when individual feature experiments fail.

Components may use deployment profiles, but their data ownership, security and adapter boundaries are designed now.

## Rationale

KAIRO's target scope crosses AI, realtime collaboration, projects, planning, finance, devices and external actions. Retrofitting identity, durable workflows, eventing, secrets or canonical data ownership after these modules are built would create more complexity than selecting the boundaries early.

## Consequence

The foundation is broader than the original V0, but later feature work has fewer hidden migrations and specialist engines remain replaceable.
