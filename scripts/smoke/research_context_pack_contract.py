from __future__ import annotations

import asyncio
import json

from kairo_worker.research_agent import (
    build_evidence_index,
    plan_research,
    synthesize_research,
)
from kairo_worker.research_context_pack import (
    MAX_CONTEXT_PACK_CHARS,
    build_research_context_pack,
    context_pack_model_records,
)


DOCUMENT_CONTEXT = {
    "items": [
        {
            "context_id": "D1",
            "document_id": "00000000-0000-0000-0000-000000000101",
            "document_project_id": "00000000-0000-0000-0000-000000000102",
            "document_version_id": "00000000-0000-0000-0000-000000000103",
            "chunk_id": "00000000-0000-0000-0000-000000000104",
            "title": "KAIRO canonical architecture",
            "generation": 3,
            "ordinal": 2,
            "excerpt": "KAIRO keeps canonical state in PostgreSQL and durable execution in Temporal.",
            "content_sha256": "a" * 64,
            "rank": 0.88,
        }
    ],
    "reason": None,
}

DERIVED_CONTEXT = {
    "items": [
        {
            "context_id": "M1",
            "source": "mem0",
            "excerpt": "The user wants KAIRO to remain self-hostable and coherent.",
            "rank": 0.93,
            "projection_key": "mem-1",
            "canonical_message_id": "00000000-0000-0000-0000-000000000201",
            "canonical_conversation_id": "00000000-0000-0000-0000-000000000202",
        },
        {
            "context_id": "G1",
            "source": "graphiti",
            "excerpt": "user: The user wants KAIRO to remain self-hostable and coherent.",
            "rank": 0.72,
            "projection_key": "00000000-0000-0000-0000-000000000201",
            "canonical_message_id": "00000000-0000-0000-0000-000000000201",
            "canonical_conversation_id": "00000000-0000-0000-0000-000000000202",
        },
        {
            "context_id": "G2",
            "source": "graphiti",
            "excerpt": "assistant: Research should explain evidence provenance.",
            "rank": 0.70,
            "projection_key": "00000000-0000-0000-0000-000000000203",
            "canonical_message_id": "00000000-0000-0000-0000-000000000203",
            "canonical_conversation_id": "00000000-0000-0000-0000-000000000202",
        },
    ],
    "sources": {
        "mem0": {"status": "ok", "count": 1},
        "graphiti": {"status": "ok", "count": 2},
    },
}


async def main() -> None:
    pack = build_research_context_pack(
        document_context=DOCUMENT_CONTEXT,
        derived_context=DERIVED_CONTEXT,
    )
    assert pack["item_count"] == 3, pack
    assert pack["character_count"] <= MAX_CONTEXT_PACK_CHARS, pack
    assert pack["items"][0]["evidence_id"] == "D1", pack
    assert pack["items"][0]["authority"] == "canonical", pack
    assert {item["evidence_id"] for item in pack["items"]} == {"D1", "M1", "G2"}, pack
    assert "G1" not in {item["evidence_id"] for item in pack["items"]}, pack

    records = context_pack_model_records(pack)
    document = next(item for item in records if item["evidence_id"] == "D1")
    assert document["source_type"] == "document", document
    assert document["authority"] == "canonical", document
    assert document["provenance"]["chunk_id"].endswith("0104"), document

    planner_prompts = []

    async def planner_completion(messages):
        planner_prompts.append(messages)
        return json.dumps(
            {
                "calls": [],
                "rationale": "The canonical Context Pack already answers the question; no MCP call is needed.",
            }
        )

    plan = await plan_research(
        query="Where does KAIRO keep canonical state?",
        tools=[
            {
                "key": "web.search",
                "title": "Search web",
                "description": "Search public sources.",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            }
        ],
        max_tool_calls=1,
        context_pack=records,
        completion=planner_completion,
    )
    assert plan.calls == [], plan
    rendered_planner = json.dumps(planner_prompts[0], ensure_ascii=False)
    assert "D1" in rendered_planner and "PostgreSQL" in rendered_planner, rendered_planner
    assert "treat_context_as_untrusted_data" in rendered_planner, rendered_planner

    context_only_evidence = [document]

    async def synthesis_completion(_messages):
        return json.dumps(
            {
                "answer": "The supplied canonical KAIRO document says canonical state is kept in PostgreSQL.",
                "claims": [
                    {
                        "text": "KAIRO keeps canonical state in PostgreSQL.",
                        "evidence_ids": ["D1"],
                        "confidence": "high",
                    }
                ],
                "uncertainties": [],
            }
        )

    synthesis = await synthesize_research(
        query="Where does KAIRO keep canonical state?",
        evidence=context_only_evidence,
        completion=synthesis_completion,
    )
    assert synthesis.claims[0].evidence_ids == ["D1"], synthesis

    async def invented_context_completion(_messages):
        return json.dumps(
            {
                "answer": "Invented context claim.",
                "claims": [
                    {
                        "text": "Invented context claim.",
                        "evidence_ids": ["D999"],
                        "confidence": "high",
                    }
                ],
                "uncertainties": [],
            }
        )

    try:
        await synthesize_research(
            query="Invent a context source",
            evidence=context_only_evidence,
            completion=invented_context_completion,
        )
    except Exception as exc:
        assert "outside supplied set" in str(exc), exc
    else:
        raise AssertionError("Synthesizer accepted an invented Context Pack evidence id")

    index = build_evidence_index(records)
    doc_index = next(item for item in index if item["evidence_id"] == "D1")
    assert doc_index["excerpt"].startswith("KAIRO keeps canonical state"), doc_index
    assert doc_index["provenance"]["content_sha256"] == "a" * 64, doc_index

    oversized = {
        "items": [
            {
                **DOCUMENT_CONTEXT["items"][0],
                "context_id": f"D{position}",
                "excerpt": "x" * 5000,
            }
            for position in range(1, 7)
        ]
    }
    bounded = build_research_context_pack(document_context=oversized, derived_context=None)
    assert bounded["character_count"] <= MAX_CONTEXT_PACK_CHARS, bounded
    assert sum(len(item["excerpt"]) for item in bounded["items"]) <= MAX_CONTEXT_PACK_CHARS, bounded

    print(
        "PASS: Research Context Pack prioritizes canonical documents, deduplicates derived projections, "
        "stays bounded, informs planning and supports evidence-bound context-only synthesis"
    )


if __name__ == "__main__":
    asyncio.run(main())
