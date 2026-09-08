import asyncio
import html
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from temporalio import activity
from trafilatura import extract

from .config import settings

_MARKET_TERMS: dict[str, int] = {
    "fed": 18,
    "ecb": 18,
    "bce": 18,
    "central bank": 18,
    "banque centrale": 18,
    "interest rate": 16,
    "taux d'intérêt": 16,
    "inflation": 14,
    "recession": 16,
    "récession": 16,
    "gdp": 12,
    "pib": 12,
    "jobs": 10,
    "emploi": 10,
    "tariff": 14,
    "droits de douane": 14,
    "sanction": 14,
    "war": 18,
    "guerre": 18,
    "oil": 12,
    "pétrole": 12,
    "gas": 10,
    "gaz": 10,
    "earnings": 12,
    "résultats": 12,
    "bankruptcy": 18,
    "faillite": 18,
    "default": 18,
    "défaut": 18,
    "merger": 10,
    "acquisition": 10,
    "regulation": 10,
    "régulation": 10,
    "crypto": 8,
    "hack": 12,
}


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def _clean_text(value: Any, limit: int = 1200) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _canonical_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))
    except Exception:
        return value


def _domain(value: str) -> str:
    try:
        return urlsplit(value).netloc.removeprefix("www.")
    except Exception:
        return ""


def _market_score(source: dict[str, Any]) -> int:
    haystack = f"{source.get('title', '')} {source.get('snippet', '')}".lower()
    return min(100, sum(weight for term, weight in _MARKET_TERMS.items() if term in haystack))


def _impact_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


async def _search_searxng(
    *, query: str, language: str, time_range: str, max_sources: int, mode: str
) -> list[dict[str, Any]]:
    search_query = query
    if mode == "market_impact":
        search_query = (
            f"{query} marchés bourse actions économie banques centrales taux inflation "
            "entreprises géopolitique énergie"
        )

    params = {
        "q": search_query,
        "categories": "news",
        "language": language,
        "time_range": time_range,
        "format": "json",
        "safesearch": 1,
    }
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        response = await client.get(f"{settings.searxng_url.rstrip('/')}/search", params=params)
        response.raise_for_status()
        payload = response.json()

        raw_results = payload.get("results") or []
        if not raw_results:
            params["categories"] = "general"
            response = await client.get(f"{settings.searxng_url.rstrip('/')}/search", params=params)
            response.raise_for_status()
            raw_results = response.json().get("results") or []

    sources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for raw in raw_results:
        url = _canonical_url(str(raw.get("url") or ""))
        title = _clean_text(raw.get("title"), 320)
        if not url or not title:
            continue
        title_key = re.sub(r"\W+", " ", title.lower()).strip()
        if url in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(title_key)
        engines = raw.get("engines") or ([raw.get("engine")] if raw.get("engine") else [])
        source = {
            "title": title,
            "url": url,
            "domain": _domain(url),
            "snippet": _clean_text(raw.get("content"), 900),
            "published_at": raw.get("publishedDate") or raw.get("published_date"),
            "engines": [str(item) for item in engines if item],
        }
        source["market_score"] = _market_score(source)
        sources.append(source)
        if len(sources) >= max_sources * 2:
            break

    if mode == "market_impact":
        sources.sort(key=lambda item: item["market_score"], reverse=True)

    sources = sources[:max_sources]
    for index, source in enumerate(sources, start=1):
        source["id"] = f"S{index}"
    return sources


async def _enrich_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Read accessible article bodies transiently for better analysis.

    The extracted body is held only in activity memory and removed before the KAIRO Artifact is
    persisted. Paywalls, JavaScript-only pages and robots/network failures simply fall back to the
    SearXNG snippet.
    """

    semaphore = asyncio.Semaphore(4)
    headers = {
        "User-Agent": "KAIRO-News/0.2 (+local personal research assistant)",
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=True, headers=headers
    ) as client:

        async def enrich(source: dict[str, Any]) -> dict[str, Any]:
            enriched = dict(source)
            enriched["content_available"] = False
            try:
                async with semaphore:
                    response = await client.get(source["url"])
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "html" not in content_type or len(response.content) > 2_500_000:
                    return enriched
                extracted = await asyncio.to_thread(
                    extract,
                    response.text,
                    url=str(response.url),
                    include_comments=False,
                    include_tables=False,
                )
                article_text = _clean_text(extracted, 5000)
                if article_text:
                    enriched["analysis_text"] = article_text
                    enriched["content_available"] = True
            except Exception:
                pass
            return enriched

        enriched_head = await asyncio.gather(*(enrich(source) for source in sources[:6]))

    tail = [dict(source, content_available=False) for source in sources[6:]]
    return [*enriched_head, *tail]


def _public_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in source.items() if key != "analysis_text"}
        for source in sources
    ]


def _fallback_brief(
    *, query: str, mode: str, language: str, sources: list[dict[str, Any]]
) -> dict[str, Any]:
    if not sources:
        return {
            "headline": f"Aucune source récente trouvée — {query}",
            "summary": "KAIRO n'a trouvé aucune source récente exploitable pour cette requête.",
            "spoken_summary": "Je n'ai trouvé aucune source récente exploitable pour cette requête.",
            "market_impact": None,
        }

    lines = []
    spoken = []
    for source in sources[:6]:
        snippet = source["snippet"] or "Article récent détecté par le moteur de recherche."
        lines.append(f"- [{source['id']}] {source['title']} — {snippet}")
        spoken.append(f"{source['title']}. {snippet}")

    market_impact: dict[str, Any] | None = None
    if mode == "market_impact":
        score = max(int(source["market_score"]) for source in sources)
        market_impact = {
            "score": score,
            "level": _impact_level(score),
            "direction": "uncertain",
            "rationale": "Score heuristique basé sur les thèmes macroéconomiques, géopolitiques et entreprises présents dans les sources.",
            "affected_sectors": [],
            "affected_assets": [],
        }

    return {
        "headline": f"Briefing KAIRO — {query}",
        "summary": "\n".join(lines),
        "spoken_summary": " ".join(spoken)[:6000],
        "market_impact": market_impact,
    }


def _parse_json_object(value: str) -> dict[str, Any] | None:
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
    return None


async def _summarize_with_litellm(
    *, query: str, mode: str, language: str, sources: list[dict[str, Any]]
) -> dict[str, Any] | None:
    compact_sources = [
        {
            "id": source["id"],
            "title": source["title"],
            "domain": source["domain"],
            "published_at": source["published_at"],
            "text": str(source.get("analysis_text") or source["snippet"])[:3000],
            "market_score_hint": source["market_score"],
        }
        for source in sources
    ]
    system_prompt = (
        "You are KAIRO News Intelligence. Use only the supplied sources. Never invent facts. "
        "Distinguish reported facts from analysis. Cite sources inline with [S1], [S2], etc. "
        "Return valid JSON only with keys headline, summary, spoken_summary, market_impact. "
        "summary must be concise but informative and suitable for reading in a dashboard. "
        "spoken_summary must be natural speech without URLs or markdown. "
        "market_impact must be null unless mode is market_impact; then return an object with "
        "score (0-100), level (low|medium|high|critical), direction "
        "(positive|negative|mixed|uncertain), rationale, affected_sectors, affected_assets."
    )
    user_payload = {
        "query": query,
        "mode": mode,
        "language": language,
        "sources": compact_sources,
    }
    headers = {"Content-Type": "application/json"}
    if settings.litellm_master_key:
        headers["Authorization"] = f"Bearer {settings.litellm_master_key}"
    request = {
        "model": settings.kairo_news_model,
        "temperature": 0.15,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            f"{settings.litellm_url.rstrip('/')}/v1/chat/completions",
            headers=headers,
            json=request,
        )
        response.raise_for_status()
        data = response.json()
    content = data["choices"][0]["message"]["content"]
    return _parse_json_object(str(content))


@activity.defn
async def begin_execution(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_id = payload["workflow_id"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url}/internal/v1/executions/{workflow_id}/start",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


@activity.defn
async def perform_foundation_work(payload: dict[str, Any]) -> dict[str, Any]:
    """Replay-safe Block 1 activity used to exercise crash/restart semantics."""
    task_input = payload.get("task_input") or {}
    delay = max(0.0, min(float(task_input.get("delay_seconds", 0)), 30.0))
    elapsed = 0.0
    while elapsed < delay:
        step = min(1.0, delay - elapsed)
        await asyncio.sleep(step)
        elapsed += step
        activity.heartbeat({"elapsed_seconds": elapsed})

    return {
        "kind": "foundation-result",
        "title": f"Result — {payload['task_title']}",
        "content": {
            "task_id": payload["task_id"],
            "message": "Durable Temporal workflow completed through the KAIRO Core boundary.",
            "input": task_input,
        },
    }


@activity.defn
async def perform_news_brief(payload: dict[str, Any]) -> dict[str, Any]:
    task_input = payload.get("task_input") or {}
    query = _clean_text(task_input.get("query"), 500)
    if not query:
        raise ValueError("news.brief requires a non-empty query")
    mode = str(task_input.get("mode") or "general")
    language = str(task_input.get("language") or "fr")
    time_range = str(task_input.get("time_range") or "day")
    max_sources = max(3, min(int(task_input.get("max_sources") or 10), 20))
    location = _clean_text(task_input.get("location"), 160)
    if location and location.lower() not in query.lower():
        query = f"{query} {location}"

    activity.heartbeat({"stage": "search"})
    sources = await _search_searxng(
        query=query,
        language=language,
        time_range=time_range,
        max_sources=max_sources,
        mode=mode,
    )

    activity.heartbeat({"stage": "article-enrichment", "sources": len(sources)})
    analysis_sources = await _enrich_sources(sources) if sources else []
    public_sources = _public_sources(analysis_sources)

    activity.heartbeat(
        {
            "stage": "summarize",
            "sources": len(public_sources),
            "full_text_sources": sum(
                1 for source in public_sources if source.get("content_available") is True
            ),
        }
    )
    brief = _fallback_brief(query=query, mode=mode, language=language, sources=public_sources)
    if analysis_sources:
        try:
            model_brief = await _summarize_with_litellm(
                query=query, mode=mode, language=language, sources=analysis_sources
            )
            if model_brief:
                brief.update({key: value for key, value in model_brief.items() if value is not None})
        except Exception as exc:
            brief["model_warning"] = f"LiteLLM summary unavailable; deterministic fallback used: {exc}"

    return {
        "kind": "news-brief",
        "title": _clean_text(brief.get("headline"), 320) or f"Briefing — {query}",
        "content": {
            "query": query,
            "mode": mode,
            "language": language,
            "time_range": time_range,
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": str(brief.get("summary") or ""),
            "spoken_summary": str(brief.get("spoken_summary") or brief.get("summary") or ""),
            "market_impact": brief.get("market_impact"),
            "sources": public_sources,
            "model_warning": brief.get("model_warning"),
        },
    }


@activity.defn
async def complete_execution(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_id = payload["workflow_id"]
    result = payload["result"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url}/internal/v1/executions/{workflow_id}/complete",
            headers=_headers(),
            json=result,
        )
        response.raise_for_status()
        return response.json()


@activity.defn
async def fail_execution(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_id = payload["workflow_id"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url}/internal/v1/executions/{workflow_id}/fail",
            headers=_headers(),
            json={"error": payload["error"]},
        )
        response.raise_for_status()
        return response.json()
