# Security and authority model

KAIRO is expected to act autonomously, so authority must be explicit before capability expands.

## Authority levels

### A0 — Read / observe
Allowed without confirmation when the integration itself is approved.

Examples:
- read project data;
- search the web;
- inspect system health;
- read supported market data;
- inspect analytics.

### A1 — Internal write
May modify KAIRO-owned internal state.

Examples:
- create notes;
- classify an idea;
- update task status;
- write research reports;
- update the project graph.

### A2 — Prepare external action
May prepare but not execute an external side effect.

Examples:
- draft an email;
- draft a social post;
- prepare a server change plan;
- prepare a transaction proposal.

### A3 — Pre-authorized external action
May execute only within a narrowly pre-approved standing order.

Examples:
- publish an already approved item at its scheduled time;
- send a routine notification to the user;
- perform a known-safe integration refresh.

A3 actions require auditable scope, destination, and rollback/mitigation where possible.

### A4 — Sensitive external action
Requires explicit user confirmation at execution time unless a future policy states otherwise.

Examples:
- send a consequential email;
- make a public statement not previously approved;
- modify production infrastructure;
- change authentication or permissions;
- install/update core software.

### A5 — Critical / irreversible / financial
Always requires strong explicit confirmation in V0/V1.

Examples:
- financial transactions;
- wallet signing;
- destructive deletion without recoverable backup;
- irreversible account actions;
- legal/contractual commitments.

## Default-deny rule

A tool's technical availability does not imply permission to use it.

A job must not exceed the lowest of:

1. the user's global authority policy;
2. the integration's granted scope;
3. the task-specific authority ceiling;
4. the agent's configured policy.

## Autonomous-job contract

Every autonomous job should carry:

- purpose;
- project/task ID;
- allowed tools;
- authority ceiling;
- optional API budget;
- optional deadline;
- expected artefact/result;
- failure behavior;
- notification/approval behavior.

## Secrets

Never commit live secrets to Git, even in a private repository.

Keep outside source control:

- API keys;
- OAuth refresh/access tokens;
- passwords;
- private keys;
- wallet secrets;
- production `.env` files;
- OpenClaw state databases;
- live personal memory/profile data.

Use least-privilege credentials and separate credentials by integration/environment where practical.

## Personal data

The live `USER.md`, `MEMORY.md`, daily memory, private vault, and raw voice captures are runtime data.

Version-control only **templates and schemas**. Do not commit the user's live personal profile simply because the repository is private.

## Voice data

Default desired policy for future voice capture:

1. record only after explicit user action / approved wake mechanism;
2. upload over encrypted transport;
3. transcribe;
4. confirm persistence target when ambiguity matters;
5. delete raw audio after successful transcription unless retention is explicitly requested.

## Self-diagnosis vs self-modification

KAIRO may inspect its own health, identify likely problems, and recommend changes.

It must not silently:

- update its own core runtime;
- change authority policy;
- rotate authentication configuration;
- rewrite foundational identity/policy files;
- deploy unreviewed code to production.

Any future self-change workflow must produce a diff/plan, backup state, test results, and a user approval point.

## Updates

Core updates should follow:

```text
update available
 -> inspect changelog / compatibility
 -> backup verified
 -> test in non-production or controlled upgrade
 -> user approval where required
 -> apply
 -> health checks
 -> rollback if needed
```

## External publication

Drafting and publishing are separate capabilities.

A content-generation agent may have A2 but not A3/A4. Social publishing should use platform-specific scopes and an approval queue.

## Crypto

V0/V1 crypto capability is analytical only:

- market data;
- watchlists;
- thesis tracking;
- alerts;
- critique;
- scenario analysis.

Autonomous trading, wallet signing, or custody are explicitly out of scope.

## Auditability

Sensitive and autonomous operations should record:

- actor/agent;
- request/trigger;
- timestamp;
- permission level;
- tools invoked;
- external destination;
- model/provider where relevant;
- cost;
- result;
- approval record;
- failure/retry information.
