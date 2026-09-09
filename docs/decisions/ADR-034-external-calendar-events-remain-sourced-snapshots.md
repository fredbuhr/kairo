# ADR-034 — External calendar events remain sourced snapshots

Status: accepted
Date: 2026-09-09

## Context

KAIRO already owns explicit Task planning facts (`planned_start_at`, `planned_end_at`, `due_at`) and projects them into Today, Gantt and Calendar. External calendars such as Google Calendar or Microsoft Outlook are useful context, but importing their events directly into the Task model would blur authority and provenance: an event moved or deleted at the provider could silently mutate KAIRO's own work plan.

KAIRO also needs a connector boundary that does not place OAuth credentials or provider-specific transport logic inside the canonical calendar read model.

## Decision

External calendar data is represented as **provenance-preserving source snapshots** owned by KAIRO, while the external provider remains the authoritative origin of those observations.

### Separate semantics

KAIRO Task planning remains canonical KAIRO work state. An external calendar event is not a Task, Project, Relationship or Gantt instruction merely because it occupies time on the same calendar.

The Calendar workspace may overlay the two kinds of information, but must visually retain their distinction and source identity.

### Source identity

Each `CalendarSource` is scoped to a KAIRO user and binds:

- a stable KAIRO source key;
- a provider identifier;
- an external account/calendar reference;
- a display name;
- source status and synchronization metadata.

A source key cannot later be rebound to another external account. The `(user, provider, external_account_ref)` binding is unique as well.

### Event identity and provenance

Each `ExternalCalendarEvent` stores the source FK plus the provider's `external_id`. The pair is unique. Event rows preserve:

- source/provider identity;
- provider event identity;
- observed title/time/all-day/status/location;
- optional provider URL;
- provider update time when supplied;
- KAIRO observation time;
- connector-provided metadata.

The KAIRO row ID is deterministic for a source/event identity. Replaying a snapshot updates the same observation rather than creating a new semantic event.

### Trusted connector ingestion

Provider/OAuth integrations do not write database rows directly. A trusted connector/adaptor submits normalized snapshots through the internal-token Core boundary.

A full snapshot may remove provider events that are no longer present at the source. That operation affects only external snapshot rows; it never deletes, completes, reschedules or otherwise mutates KAIRO Tasks.

Connector snapshots must use timezone-aware instants and valid intervals. Duplicate external IDs in the same snapshot fail closed.

### Public read boundary

User-facing Calendar reads are owner-scoped in Core and interval-bounded. Cancelled external events are hidden by default but remain source-state concepts rather than KAIRO Task lifecycle states.

### Credentials

OAuth refresh tokens, client secrets and provider credentials are not stored in `CalendarSource` or `ExternalCalendarEvent`. Secret material remains behind the KAIRO secret/connector boundary (for example OpenBao-backed references or a connector-specific credential store).

### Conversion into KAIRO work

A future action such as “create a KAIRO task from this meeting” must be an explicit KAIRO mutation with its own provenance and audit trail. The Calendar projection must never perform that conversion implicitly.

## Consequences

- KAIRO can show external commitments next to its own work plan without losing semantic ownership.
- Provider deletions and reschedules can be replayed safely as source snapshots.
- Google, Microsoft and future providers can share one normalized read contract.
- The actual OAuth/connectors remain replaceable specialist adapters.
- Free/busy and scheduling assistants can later reason over both kinds of time while still knowing which facts KAIRO owns and which facts were observed externally.
