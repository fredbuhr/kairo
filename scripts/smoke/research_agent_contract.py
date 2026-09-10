import asyncio
import json
from decimal import Decimal

from pydantic_ai import UnexpectedModelBehavior

from kairo_worker.model_gateway import MODEL_CHECKPOINT_KIND, MODEL_CHECKPOINT_VERSION, ModelCheckpointLedger
from kairo_worker.research_agent import (
    build_research_evidence,
    plan_research,
    research_progress_snapshot,
    split_research_model_budget,
    synthesize_research,
)


TOOLS = [
    {
        "key": "web.search",
        "title": "Search web",
        "description": "Search public sources without side effects.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    }
]

TOOL_RESULTS = [
    {
        "slot": 0,
        "tool_key": "web.search",
        "input": {"query": "KAIRO architecture"},
        "rationale": "Find public evidence.",
        "invocation_id": "00000000-0000-0000-0000-000000000010",
        "result": {
            "items": [
                {
                    "title": "KAIRO architecture",
                    "snippet": "KAIRO keeps canonical state in its own platform boundary.",
                }
            ]
        },
    }
]


async def main() -> None:
    async def valid_completion(_messages):
        return json.dumps(
            {
                "calls": [
                    {
                        "tool_key": "web.search",
                        "input": {"query": "KAIRO architecture"},
                        "rationale": "Find public evidence.",
                    }
                ],
                "rationale": "One read-only search is sufficient.",
            }
        )

    plan = await plan_research(
        query="Research KAIRO architecture",
        tools=TOOLS,
        max_tool_calls=1,
        completion=valid_completion,
    )
    assert len(plan.calls) == 1, plan
    assert plan.calls[0].tool_key == "web.search", plan

    async def invented_completion(_messages):
        return json.dumps(
            {
                "calls": [
                    {
                        "tool_key": "payments.send",
                        "input": {"amount": 100},
                        "rationale": "Invent a side-effecting tool.",
                    }
                ],
                "rationale": "Invalid proposal used to prove fail-closed behavior.",
            }
        )

    try:
        await plan_research(
            query="Do something unsafe",
            tools=TOOLS,
            max_tool_calls=1,
            completion=invented_completion,
        )
    except UnexpectedModelBehavior:
        pass
    else:
        raise AssertionError("Planner accepted a tool outside the Core-provided catalog")

    evidence = build_research_evidence(TOOL_RESULTS)
    assert len(evidence) == 1, evidence
    assert evidence[0]["evidence_id"] == "E1", evidence
    assert evidence[0]["invocation_id"] == TOOL_RESULTS[0]["invocation_id"], evidence
    assert "canonical state" in evidence[0]["result_excerpt"], evidence

    synthesis_prompts = []

    async def grounded_completion(messages):
        synthesis_prompts.append(messages)
        return json.dumps(
            {
                "answer": "The supplied evidence says KAIRO keeps canonical state inside its own platform boundary.",
                "claims": [
                    {
                        "text": "KAIRO keeps canonical state inside its own platform boundary.",
                        "evidence_ids": ["E1"],
                        "confidence": "high",
                    }
                ],
                "uncertainties": ["The single evidence record is insufficient for broader architecture claims."],
            }
        )

    synthesis = await synthesize_research(
        query="What does the evidence say about KAIRO architecture?",
        evidence=evidence,
        completion=grounded_completion,
    )
    assert synthesis.claims[0].evidence_ids == ["E1"], synthesis
    assert len(synthesis_prompts) == 1, synthesis_prompts
    rendered_prompt = json.dumps(synthesis_prompts[0], ensure_ascii=False)
    assert "E1" in rendered_prompt and "canonical state" in rendered_prompt, rendered_prompt

    async def invented_evidence_completion(_messages):
        return json.dumps(
            {
                "answer": "Invented claim.",
                "claims": [
                    {
                        "text": "Invented claim.",
                        "evidence_ids": ["E999"],
                        "confidence": "high",
                    }
                ],
                "uncertainties": [],
            }
        )

    try:
        await synthesize_research(
            query="Invent something",
            evidence=evidence,
            completion=invented_evidence_completion,
        )
    except UnexpectedModelBehavior:
        pass
    else:
        raise AssertionError("Synthesizer accepted an evidence id outside the supplied evidence set")

    async def uncited_answer_completion(_messages):
        return json.dumps(
            {
                "answer": "This answer asserts a fact without binding it to evidence.",
                "claims": [],
                "uncertainties": [],
            }
        )

    try:
        await synthesize_research(
            query="Answer without citations",
            evidence=evidence,
            completion=uncited_answer_completion,
        )
    except UnexpectedModelBehavior:
        pass
    else:
        raise AssertionError("Synthesizer accepted an answer without evidence-bound claims")

    planner_budget, synthesis_budget = split_research_model_budget(Decimal("0.01"))
    assert planner_budget == Decimal("0.005"), planner_budget
    assert synthesis_budget == Decimal("0.005"), synthesis_budget
    assert planner_budget + synthesis_budget == Decimal("0.01")

    # Research phase heartbeats must not overwrite the replay-critical model checkpoint bundle.
    planner_key = "00000000-0000-0000-0000-000000000099"
    ledger = ModelCheckpointLedger()
    ledger.record(
        {
            "kind": MODEL_CHECKPOINT_KIND,
            "version": MODEL_CHECKPOINT_VERSION,
            "stage": "accounted",
            "idempotency_key": planner_key,
            "result": {
                "content": "fixture research plan",
                "usage": {
                    "provider_model": "fixture/local-fast",
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "cost_usd": "0",
                    "cost_reported": True,
                    "litellm_call_id": planner_key,
                },
            },
        }
    )
    heartbeat = research_progress_snapshot(
        ledger,
        phase="tool-wait",
        planned_tool_calls=2,
        active_slot=1,
        completed_tool_slots=[0, 0],
    )
    assert heartbeat["research_progress"] == {
        "phase": "tool-wait",
        "completed_tool_slots": [0],
        "planned_tool_calls": 2,
        "active_slot": 1,
    }, heartbeat
    restored = ModelCheckpointLedger.from_heartbeat_details([heartbeat])
    restored_planner = restored.checkpoint_for(planner_key)
    assert restored_planner is not None and restored_planner["stage"] == "accounted", restored_planner
    assert restored_planner["result"]["content"] == "fixture research plan", restored_planner

    print(
        "PASS: research planning and synthesis stay evidence-bound, budgets remain bounded and "
        "progress heartbeats preserve replay-critical model checkpoints"
    )


if __name__ == "__main__":
    asyncio.run(main())
