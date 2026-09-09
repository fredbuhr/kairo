# ADR-036 — Finance snapshots are sourced; signing stays isolated

**Status:** Accepted

## Context

KAIRO needs a useful Finance & Crypto workspace without becoming a wallet custodian, an exchange database or a second authoritative ledger.

Existing specialist engines such as Rotki, exchanges, wallets and future banking connectors may observe balances and positions, but their internal schemas and credentials must remain replaceable implementation details. At the same time, an AI/agent compromise or prompt injection must never expose wallet private keys or seed phrases or gain direct transaction-signing authority.

ADR-015 already requires financial signing isolation. This ADR defines the canonical read/proposal boundary that feeds the Cockpit while preserving that invariant.

## Decision

### Sourced portfolio observations

KAIRO Core owns normalized, provenance-preserving Finance records:

- `FinanceSource` identifies the provider and external account source for one KAIRO user;
- `FinanceAccount` identifies an observed wallet, exchange or other account under that source;
- `FinancePosition` is the latest normalized account/asset observation with quantity and optional valuation/cost/P&L fields.

External adapters feed these records only through a trusted normalized snapshot boundary. Source/account identity is stable across replay and a source key cannot silently be rebound to another provider account.

These records are observations, not custody and not a transaction ledger. A full source snapshot may remove observations that disappeared upstream; this never creates, signs or submits a financial transaction.

### No secrets in financial facts

Finance snapshot/proposal JSON is not a secret store. Private keys, seed phrases, mnemonics, provider API credentials and access/refresh tokens are rejected from normalized metadata/simulation fields.

Public wallet addresses may be stored because they are provenance/identity facts, not signing authority.

Provider credentials, where needed by future connectors, remain behind KAIRO's secret/reference boundary and never become FinanceSource/Account/Position facts.

### Unsigned transaction proposals only

KAIRO may create an unsigned `FinanceTransactionProposal` for an asset that is present in the latest observed source-account snapshot. A proposal is a durable draft containing intent/simulation context; it is not a signed transaction and does not imply that the observed quantity is current enough to authorize spending.

The first Cockpit slice exposes `crypto_transfer` drafts only. It intentionally exposes no sign/send/broadcast endpoint.

### Signing boundary

Any future transaction signing must occur after KAIRO policy/approval checks through an isolated signer, hardware wallet or explicit user-wallet interaction. LLM/agent processes never receive the private key or seed phrase.

The public proposal contract therefore states:

- `signing_required = true`;
- `signing_boundary = external_isolated_signer`.

## Consequences

- Rotki/exchange/wallet adapters remain replaceable and cannot silently become canonical state.
- The Finance Cockpit can aggregate useful portfolio context without fabricating balances when no connector is present.
- Snapshot staleness is visible as provenance/observation time rather than hidden behind an invented “available balance”.
- AI can analyze and prepare financial intent without becoming a custody boundary.
- Future signing work must extend ADR-015/ADR-036 rather than adding wallet secrets or direct agent signing to the current Finance API.
