from __future__ import annotations

import asyncio

from nevolium_worker.research_memory_context import (
    MAX_DERIVED_CONTEXT_EXCERPT_CHARS,
    collect_derived_memory_context,
)


async def main() -> None:
    observed = {"mem0": None, "graphiti": None}

    def fake_mem0(query: str, user_id: str, limit: int):
        observed["mem0"] = (query, user_id, limit)
        return [
            {
                "id": "mem-1",
                "memory": "The user prefers canonical Nevolium state over derived stores.",
                "score": 0.91,
                "metadata": {
                    "nevolium_message_id": "00000000-0000-0000-0000-000000000001",
                    "nevolium_conversation_id": "00000000-0000-0000-0000-000000000010",
                },
            }
        ]

    async def fake_graphiti(query: str, group_ids: list[str], limit: int):
        observed["graphiti"] = (query, list(group_ids), limit)
        return [
            {
                "uuid": "00000000-0000-0000-0000-000000000002",
                "group_id": "conversation:00000000-0000-0000-0000-000000000020",
                "content": "user: Nevolium research should retain durable provenance.",
                "score": 2,
            }
        ]

    result = await collect_derived_memory_context(
        query="Nevolium canonical durable provenance",
        mem0_user_id="subject:user-a",
        graphiti_group_ids=["conversation:00000000-0000-0000-0000-000000000020"],
        limit_per_source=4,
        mem0_search=fake_mem0,
        graphiti_search=fake_graphiti,
    )
    assert observed["mem0"] == ("Nevolium canonical durable provenance", "subject:user-a", 4), observed
    assert observed["graphiti"] == (
        "Nevolium canonical durable provenance",
        ["conversation:00000000-0000-0000-0000-000000000020"],
        4,
    ), observed
    assert result["authoritative"] is False and result["derived"] is True, result
    assert result["sources"]["mem0"] == {"status": "ok", "count": 1}, result
    assert result["sources"]["graphiti"] == {"status": "ok", "count": 1}, result
    assert {item["context_id"] for item in result["items"]} == {"M1", "G1"}, result
    mem0 = next(item for item in result["items"] if item["source"] == "mem0")
    graphiti = next(item for item in result["items"] if item["source"] == "graphiti")
    assert mem0["canonical_conversation_id"].endswith("0010"), mem0
    assert graphiti["canonical_conversation_id"].endswith("0020"), graphiti
    assert graphiti["canonical_message_id"].endswith("0002"), graphiti

    def failing_mem0(_query: str, _user_id: str, _limit: int):
        raise RuntimeError("mem0 fixture unavailable")

    degraded = await collect_derived_memory_context(
        query="Nevolium canonical durable provenance",
        mem0_user_id="subject:user-a",
        graphiti_group_ids=["conversation:00000000-0000-0000-0000-000000000020"],
        mem0_search=failing_mem0,
        graphiti_search=fake_graphiti,
    )
    assert degraded["sources"]["mem0"]["status"] == "unavailable", degraded
    assert degraded["sources"]["graphiti"]["status"] == "ok", degraded
    assert any(item["source"] == "graphiti" for item in degraded["items"]), degraded

    long_memory = "x" * (MAX_DERIVED_CONTEXT_EXCERPT_CHARS + 500)

    def long_mem0(_query: str, _user_id: str, _limit: int):
        return [{"id": "mem-long", "memory": long_memory, "score": 0.5, "metadata": {}}]

    bounded = await collect_derived_memory_context(
        query="long memory",
        mem0_user_id="subject:user-a",
        graphiti_group_ids=[],
        mem0_search=long_mem0,
        graphiti_search=fake_graphiti,
    )
    assert len(bounded["items"][0]["excerpt"]) <= MAX_DERIVED_CONTEXT_EXCERPT_CHARS
    assert bounded["items"][0]["excerpt"].endswith("…")
    assert bounded["sources"]["graphiti"]["status"] == "skipped", bounded

    print(
        "PASS: derived Research memory uses the exact Core-provided owner scopes, normalizes Mem0/Graphiti "
        "provenance, bounds excerpts and degrades independently when one projector is unavailable"
    )


if __name__ == "__main__":
    asyncio.run(main())
