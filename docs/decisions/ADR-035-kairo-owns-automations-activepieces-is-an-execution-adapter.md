# ADR-035 — KAIRO owns Automations; Activepieces is a replaceable execution adapter

Status: accepted
Date: 2026-09-09

## Context

KAIRO needs a practical automation surface without becoming dependent on a second product's domain model, credentials, retry semantics or paid administration API. Activepieces is already present in the KAIRO stack and is useful as a specialist flow engine, but KAIRO must remain authoritative for user-visible automation identity, policy, execution history, approval, audit and failure semantics.

Webhook-triggered flows also cross a potentially irreversible external side-effect boundary. A normal durable-workflow retry policy is unsafe once an HTTP POST may have reached Activepieces but KAIRO has not received the response.

## Decision

KAIRO introduces canonical `AutomationDefinition` and `AutomationInvocation` records in PostgreSQL. Activepieces is integrated through a narrow `activepieces_webhook` execution adapter rather than exposed as a second authoritative application.

### KAIRO-owned definition

An AutomationDefinition owns:

- KAIRO user and Project scope;
- stable KAIRO key/name/description;
- enabled/disabled policy;
- authority level;
- execution engine identifier;
- timeout;
- a SecretReference to the webhook path;
- non-secret metadata.

New automations are always disabled. Creating or discovering an external flow never grants execution authority.

### Secret boundary and fixed origin

The Activepieces webhook path is stored as a secret value referenced through OpenBao. The Automation row stores only the SecretReference id and the name of the secret field.

The secret value is interpreted as a **path only**. KAIRO Core prepends the configured internal Activepieces origin. Arbitrary absolute URLs, alternate schemes and protocol-relative paths are rejected so an automation definition cannot turn the Worker into a generic SSRF client.

The Worker does not receive a broad OpenBao token. It receives the resolved internal endpoint only from the internal-token Core context endpoint after Core revalidates that the automation is still enabled.

### Canonical invocation

Every run creates a canonical capability Task and AutomationInvocation before execution. The Task passes through the existing KAIRO policy/approval boundary and receives normal WorkflowExecution identity.

The AutomationInvocation records:

- stable idempotency key;
- canonical Task and WorkflowExecution binding;
- input object;
- status and timestamps;
- HTTP response status when known;
- sanitized result metadata;
- failure text;
- whether the external outcome is ambiguous.

The external response body is not persisted by default. KAIRO records content type, byte count and SHA-256 so operational evidence exists without importing arbitrary third-party response content into canonical state.

### No automatic replay after the webhook boundary

`automation.invoke` uses a Temporal activity with one attempt only.

Before the webhook call, failures are deterministic/pre-call failures and may safely terminate without ambiguity. Once the Worker begins the external POST, a transport error or lost response can mean that the remote flow ran successfully even though KAIRO cannot prove the result. KAIRO therefore records `outcome_ambiguous=true` instead of automatically replaying the webhook.

A user or future reconciliation policy may explicitly create a new invocation after inspecting the situation. That decision is never hidden inside an automatic retry.

### Activepieces remains replaceable

KAIRO's public API and UI talk to AutomationDefinition / AutomationInvocation, not directly to Activepieces flow objects. Another specialist engine can later implement the same KAIRO execution boundary without migrating KAIRO's project/task/audit model.

Flow authoring may still happen in Activepieces while KAIRO's own authoring UX is incomplete. That does not make the Activepieces flow catalog canonical KAIRO state.

## Consequences

- Automations appear as first-class KAIRO objects without duplicating project/task state.
- Activepieces can be self-hosted and replaced without changing the Cockpit contract.
- external side effects are protected from blind Temporal replay.
- webhook credentials do not appear in frontend data or Automation rows.
- enabling an automation validates its secret binding; changing that binding while enabled is also validated fail-closed.
- richer trigger scheduling, flow discovery and reconciliation can be added later behind the same KAIRO-owned boundary.
