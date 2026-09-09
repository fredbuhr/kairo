# ADR-037 — Rotki is a read-only Finance connector

Status: Accepted

## Context

KAIRO needs a concrete first Finance adapter capable of turning a real portfolio engine into the sourced Finance read model without giving the assistant, browser UI or durable workflow history custody of financial credentials or signing material.

Rotki is already part of the optional self-hosted Finance stack. Its API can expose blockchain balances and account observations, but Rotki must remain a replaceable provider rather than becoming KAIRO's canonical financial database.

## Decision

Rotki is integrated as a **read-only Finance connector** behind KAIRO Core.

KAIRO owns a canonical `FinanceConnector` record containing provider identity, Project scope, policy state, a stable Finance source key and a `SecretReference`. The connector is created disabled and must be explicitly enabled.

Rotki credentials remain in OpenBao. PostgreSQL stores only the SecretReference and the names of the required secret fields. The frontend never receives credential values. The Temporal Task payload and general Worker process receive only connector/task/workflow identifiers; KAIRO Core resolves the credential immediately before accessing Rotki.

The Rotki origin is deployment-owned through `ROTKI_URL`. A user-controlled connector record or secret cannot redirect Core to an arbitrary origin.

A synchronization request creates a normal KAIRO capability Task with `finance.sync.rotki`, authority A1 and zero model budget. Temporal owns durable execution. Because this operation only reads external portfolio state and writes a sourced KAIRO snapshot, retrying a failed synchronization is safe.

Core authenticates to Rotki, optionally requests a fresh blockchain-balance calculation, waits for Rotki's async task, normalizes the returned balances and passes them through the existing Finance snapshot ingestion boundary.

Normalized observations preserve:

- stable Finance source identity;
- stable account identity;
- stable position identity;
- provider and network provenance;
- Decimal quantity/value semantics;
- public wallet addresses where Rotki exposes them.

The adapter does not invent asset tickers when Rotki supplies a richer identifier. Extended public keys are not persisted in the first adapter slice because they are high-value privacy data even though they are not signing secrets.

Rotki does **not** provide signing authority to KAIRO. Transaction proposals remain unsigned KAIRO drafts governed by ADR-015 and ADR-036. There is no Rotki sign/send/broadcast path in this connector.

## Failure behavior

If credentials are missing/invalid, Rotki rejects the request, or the provider contract cannot be normalized, the synchronization Task fails and the connector records an error. The last successfully ingested Finance snapshot is retained rather than destroyed by a failed refresh.

Changing a connector's SecretReference or credential-field binding while it is enabled causes Core to revalidate the new OpenBao binding before accepting the mutation.

## Validation

The controlled full-stack Finance proof crosses:

`Core → Temporal → Worker → Core → OpenBao → Rotki API fixture → Finance snapshot`

It verifies fail-closed connector creation, successful synchronization, absence of credentials from the Finance read model, stable source/account/position identity across a changed external observation, and preservation of the last good snapshot after a credential failure.

A controlled fixture proves KAIRO's adapter contract. A separately provisioned real Rotki instance remains the final provider-integration validation before this adapter is considered production-validated against a specific Rotki release.

## Consequences

KAIRO can now expose a concrete self-hosted Finance connector without making Rotki authoritative, without leaking credentials into browser/Temporal state and without weakening the isolated-signing boundary. Additional exchange/wallet connectors should target the same normalized Finance snapshot contract rather than introduce provider-specific portfolio state into the Cockpit.
