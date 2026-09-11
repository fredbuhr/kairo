# ADR-015 — Financial signing is isolated from AI execution

**Status:** Accepted

## Decision

LLM/agent processes may read portfolio data and prepare/simulate transaction proposals, but they do not receive wallet private keys or seed phrases.

Signing occurs through an isolated signer/hardware wallet/user-wallet interaction after Nevolium policy and approval checks.

## Consequence

Crypto can be deeply integrated into Nevolium without turning a prompt-injection or agent compromise into direct custody compromise.
