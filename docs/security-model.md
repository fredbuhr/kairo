# KAIRO security and authority model

KAIRO is designed to observe, reason and eventually act across sensitive personal systems. Capability therefore remains separate from authority at every layer.

## Authority levels

### A0 — Read / observe
Approved integrations may be read without per-action confirmation.

Examples: read project data, inspect system health, search public information, read market data, inspect analytics.

### A1 — Internal KAIRO write
May change KAIRO-owned reversible state.

Examples: create notes, update task status, add graph relationships, write research reports.

### A2 — Prepare an external action
May construct and validate an action but cannot cause the external side effect.

Examples: draft an email, prepare a deployment plan, build an unsigned transaction, simulate a trade.

### A3 — Narrow standing external authority
May execute only a precisely pre-authorized, reversible/low-consequence standing order with scope, destination, limits and audit.

Examples: send KAIRO notifications, perform known-safe refreshes, publish content that was separately approved and scheduled.

### A4 — Sensitive external action
Requires explicit approval at execution time unless a future dedicated policy narrows the case safely.

Examples: consequential communication, production infrastructure changes, authentication changes, public publication that was not pre-approved.

### A5 — Critical / irreversible / financial
Strong explicit confirmation is required by default.

Examples: wallet signing, live exchange trades, transfers, destructive deletion without recoverable backup, legal commitments.

Live autonomous finance remains disabled until a separate security review/ADR explicitly defines bounded standing authority.

## Effective permission

A request may use only the intersection of:

1. user's global policy;
2. actor/agent policy;
3. project/workspace policy;
4. device capability grants;
5. integration OAuth/API scope;
6. workflow/task authority ceiling;
7. environment restrictions;
8. current approval evidence.

Default is deny.

## Policy decision before execution

Every side-effecting Temporal activity must receive a KAIRO policy decision or a verifiable approval token/capability scoped to that exact activity. A NATS event, model output or tool availability is never sufficient authorization.

## Secrets

OpenBao is the source for service/integration secret material.

Rules:

- Git contains templates only;
- PostgreSQL stores opaque secret references, not secret values;
- LLM prompts receive the minimum derived information required for reasoning;
- tools that require secrets obtain them inside the execution boundary, not through the model context;
- credentials are separated by environment/integration and rotated independently;
- audit logs redact secret values.

## Crypto signing boundary

KAIRO can read portfolio data, analyze risk, prepare and simulate transactions, and request approval.

Private keys/seed phrases must never be accessible to PydanticAI, LiteLLM, Mem0, Graphiti, Langfuse, chat history or ordinary application logs.

Preferred execution flow:

```text
Agent analysis
 -> TransactionProposal
 -> deterministic validation/simulation
 -> KAIRO policy decision
 -> explicit user approval
 -> isolated signer / hardware wallet / user wallet
 -> broadcast adapter
 -> immutable audit record
```

The signer exposes a narrow signing API or user interaction, not raw key export.

## Local-device boundary

The Tauri Sidecar is a separate trust boundary. Server authorization does not automatically grant microphone, clipboard, screenshot, filesystem or shell access on a registered device.

Local capability grants are explicit, revocable and auditable.

## Browser/code execution

Untrusted or agent-generated code should run in isolated containers. Production deployment should use gVisor or an equivalent strengthened sandbox where supported.

Browser sessions use dedicated profiles/credentials and least privilege. Playwright deterministic flows are preferred over free-form AI browsing for sensitive actions.

## Identity

Keycloak provides authentication/SSO. KAIRO remains single-user initially but uses proper subject/device identities from the beginning so later multi-user/team scenarios do not require replacing the authorization model.

## Audit

Security/autonomy events record:

- actor and device;
- request/trigger;
- domain entity/workflow correlation;
- policy decision and authority level;
- tools/integrations invoked;
- model/provider/cost where relevant;
- external destination/side effect;
- approval evidence;
- idempotency key;
- result/error/retry;
- artefacts produced.

Langfuse traces AI behavior, but the KAIRO audit log remains the security source of truth.

## Backup and recovery

restic performs encrypted off-host backups of canonical databases/config/object data according to a tested restore procedure. Backups must be verified before enabling higher authority levels.

## Self-modification

KAIRO may diagnose itself and prepare code/config changes. It may not silently alter core policy, authentication, secrets, production infrastructure or deploy unreviewed code. Self-change flows require a diff, tests, backup/rollback plan and approval.
