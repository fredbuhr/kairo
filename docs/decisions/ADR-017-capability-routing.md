# ADR-017 — One conversational command surface routes to KAIRO capabilities

## Status

Accepted.

## Context

KAIRO is intended to feel like one personal operating system rather than a collection of unrelated tools. A user should be able to type or eventually say a natural command such as:

- “Quelles sont les nouvelles du jour sur la ville de Paris ?”
- “Quelles sont les nouvelles qui risquent d'impacter la bourse ?”
- “Lis-moi les nouvelles qui risquent d'impacter les marchés aujourd'hui.”

The command surface must remain stable while specialist engines and implementation details remain replaceable. It must also avoid creating shadow execution paths that bypass canonical state, policy, audit or Temporal durability.

## Decision

KAIRO exposes a transport-independent capability router behind `/v1/assistant/commands`.

1. **Commands route to capabilities, not tools**
   - The router returns a KAIRO-owned capability identifier such as `news.brief`.
   - The capability service creates the same canonical Task and durable workflow used by its dedicated workspace/API.
   - The assistant surface never calls SearXNG, LiteLLM, Kokoro or another specialist engine directly.

2. **Deterministic high-confidence routing comes first**
   - Known, unambiguous intents are routed using deterministic rules.
   - This path is fast, offline-testable and does not spend a model call merely to recognize a capability KAIRO already knows.
   - News routing currently recognizes general news, local news, market-impact news, time-range hints and requests for spoken output.

3. **Conservative failure is preferred to invented intent**
   - If no deterministic capability matches, the router returns an unsupported-command response rather than guessing and taking an unrelated action.
   - A later PydanticAI/LiteLLM semantic router may handle genuinely ambiguous commands, but only after policy and capability contracts are in place.

4. **Transport surfaces are thin adapters**
   - Dedicated HTTP endpoints, the universal command bar, future voice input and future automations all call the same internal capability service.
   - Capability logic is not implemented inside HTTP endpoint functions.

5. **Routing output is inspectable**
   - The response includes capability, confidence and normalized parameters before/alongside the durable execution identifiers.
   - The UI can therefore show which KAIRO capability handled the request.

6. **Durability and authority do not change with phrasing**
   - Natural-language commands inherit the same PostgreSQL canonical state, Temporal execution, NATS outbox, audit and future policy gates as direct workspace actions.
   - Conversational convenience never grants additional authority.

## Consequences

- KAIRO gets a Jarvis-like front door without turning every request into an opaque LLM decision.
- New capabilities can register behind the command surface without redesigning the UI.
- Semantic/agentic routing can be added later as a second tier while deterministic routes remain stable regression-tested contracts.
- The first implementation intentionally supports only proven News Intelligence intents; unsupported requests remain explicit until their corresponding KAIRO capability exists.
