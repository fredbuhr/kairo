# ADR-017 — Canonical conversational command kernel routes to KAIRO capabilities

## Status

Accepted.

## Context

KAIRO is intended to feel like one personal operating system rather than a collection of unrelated tools. A user should be able to type, speak or later automate a natural command such as:

- “Quelles sont les nouvelles du jour sur la ville de Paris ?”
- “Quelles sont les nouvelles qui risquent d'impacter la bourse ?”
- “Lis-moi les nouvelles qui risquent d'impacter les marchés aujourd'hui.”

The front door must remain stable while specialist engines, model providers and transports remain replaceable. Conversational convenience must never create a shadow execution path that bypasses canonical state, Temporal durability, policy, approval, model accounting, audit or outbox delivery.

## Decision

KAIRO owns a canonical command kernel with four first-class records:

1. `Conversation` stores continuity across commands and future channels.
2. `ConversationMessage` stores the user-visible input stream.
3. `Command` stores routing status, confidence, normalized parameters, correlation and the eventual Task/Workflow linkage.
4. `Capability` stores the stable KAIRO-owned contract that callers route to.

### Commands route to capabilities, not tools

The router emits stable identifiers such as `news.brief`. The capability implementation creates the same canonical Task and durable Temporal workflow used by the dedicated News workspace. The assistant does not call SearXNG, LiteLLM, Kokoro or another specialist engine directly.

### Deterministic high-confidence routing comes first

Known, unambiguous intents are routed by deterministic rules. This path is fast, offline-testable and does not spend a model call merely to recognize a capability KAIRO already knows.

The first implementation recognizes general news, local news, market-impact questions, day/week/month hints and spoken-output requests.

### Ambiguous commands fail conservatively

If no deterministic capability matches, KAIRO persists the Conversation, Message and unsupported Command, then returns a refusal to route. It does not invent an intent or silently choose an unrelated action.

A later PydanticAI/LiteLLM semantic router may act as a second tier, but it must produce the same canonical Command record and capability contract before execution.

### Capability metadata is inspectable and versioned

Each capability declares at least:

- stable key and version;
- input and output schemas;
- authority requirement;
- cost class;
- runtime;
- metadata about durability and specialist dependencies.

The code-owned registry is synchronized into PostgreSQL so the stable contract is both executable and inspectable.

### Transport surfaces are thin adapters

Dedicated HTTP endpoints, the universal web command bar, future voice input, device clients and future automations all call the same transport-independent capability service.

### Durability and authority do not change with phrasing

Natural-language invocation grants no additional authority. The resulting Task inherits the same KAIRO Core policy/approval/model-accounting boundaries as a direct capability invocation.

## Consequences

- KAIRO gets a Jarvis-like front door without turning every request into an opaque LLM decision.
- Conversation continuity becomes canonical server-side state rather than browser-local UI state.
- New capabilities can register behind one command surface without redesigning the UI.
- Tool providers and specialist engines remain replaceable behind KAIRO capability adapters.
- Unsupported intents are auditable instead of silently guessed.
- The command-to-task linkage provides the future bridge for Activity, approvals, notifications, memory projections and cross-device continuity.
