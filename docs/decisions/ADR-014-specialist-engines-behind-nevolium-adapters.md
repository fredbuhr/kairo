# ADR-014 — Specialist engines remain behind Nevolium adapters

**Status:** Accepted

## Decision

Nevolium will not fork a large assistant/admin product as its foundation. The Cockpit and domain model remain Nevolium-owned. Open-source engines are integrated through stable adapters/protocols.

## Examples

- LiteLLM for model routing;
- Activepieces for external automation;
- Graphiti/Mem0 for derived context/memory;
- OpenHands for development agents;
- rotki for crypto accounting;
- Home Assistant for device integrations.

Replacing one engine must not require rewriting canonical Nevolium entities.
