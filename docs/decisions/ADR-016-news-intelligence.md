# ADR-016 — News Intelligence is a sourced Nevolium capability

## Status

Accepted.

## Context

Nevolium must answer requests such as:

- “Quelles sont les nouvelles du jour sur la ville de Paris ?”
- “Quelles nouvelles risquent d'impacter la bourse aujourd'hui ?”
- “Lis-moi le briefing.”

The capability must work from the same Nevolium data model and durable execution substrate as other tasks. It must not create a parallel source of truth or couple the product to a single news provider.

## Decision

News Intelligence is implemented as a Nevolium task capability named `news.brief`.

1. **Discovery — SearXNG**
   - Nevolium Worker queries the private SearXNG instance.
   - News/general search results are normalized and deduplicated.
   - Nevolium keeps source metadata, links and short search-result extracts rather than mirroring full newspaper articles.

2. **Transient article enrichment — Trafilatura**
   - For a bounded set of accessible sources, the Worker may fetch the public article page and extract its main text with Trafilatura.
   - Extracted article text exists only in activity memory and can be supplied to the summarization model; it is removed before the Nevolium Artifact is persisted.
   - Paywalls, JavaScript-only pages, oversized pages and extraction failures fall back to the search-result extract.
   - Article enrichment accepts only public HTTP(S) destinations. Localhost, private/non-global IP addresses and redirects toward internal destinations are rejected before the request, preventing search results from becoming an SSRF path into Nevolium services.

3. **Analysis — Nevolium Worker + LiteLLM**
   - The Worker supplies only retrieved source material to the summarization model.
   - Summaries must cite source identifiers such as `[S1]` and must not invent facts absent from the supplied material.
   - If LiteLLM is unavailable, Nevolium produces a deterministic source digest instead of losing the briefing.

4. **Market-impact mode**
   - A deterministic keyword signal provides an initial relevance score.
   - The model may synthesize likely market impact, direction, sectors and assets from the supplied sources.
   - This output is analytical context, not an instruction to trade. Sources and uncertainty remain visible.

5. **Canonical persistence — PostgreSQL**
   - A request is a normal Nevolium `Task` in the system workspace `Nevolium News`.
   - The completed result is a normal `Artifact` with kind `news-brief`.
   - Source URLs, source metadata, generated summary, spoken summary and market-impact metadata live inside the artifact content.
   - Task and artifact lifecycle events use the existing transactional outbox and NATS event path.

6. **Durability — Temporal**
   - News collection and synthesis run inside the existing durable task workflow.
   - Network activities remain outside Temporal workflow sandbox code.
   - News activities use a longer heartbeat budget than short foundation activities because model calls can take materially longer.

7. **Speech — Kokoro-FastAPI**
   - Audio is synthesized locally and on demand from the persisted `spoken_summary`.
   - Kokoro-FastAPI runs under the optional Compose `voice` profile.
   - MP3 output is streamed to the client; it is not duplicated into canonical state unless a later product requirement explicitly asks to retain audio.

8. **Interface**
   - The web client exposes query, analysis mode and output mode.
   - The result shows the briefing, market-impact metadata when requested, and the retained source list.
   - Audio playback calls the Nevolium Core audio endpoint; the browser never talks to the TTS engine directly.

## Consequences

- News providers, model providers, extraction engines and TTS engines remain replaceable behind Nevolium-owned contracts.
- A news request inherits Nevolium's audit, durability, eventing and future scheduling/notification capabilities.
- Nevolium can later add source subscriptions, watchlists, embeddings, entity extraction and alerting without replacing the first implementation.
- Full-text article persistence, paywall bypassing and republishing are explicitly outside this capability.
