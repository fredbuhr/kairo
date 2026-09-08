from decimal import Decimal

from kairo_worker.model_gateway import (
    ChatCompletionResult,
    ModelCheckpointLedger,
    ModelUsage,
)


def result(content: str) -> ChatCompletionResult:
    return ChatCompletionResult(
        content=content,
        usage=ModelUsage(
            provider_model="local/test",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost_usd=Decimal("0.001"),
            cost_reported=True,
            litellm_call_id=None,
        ),
        raw={},
    )


def main() -> None:
    ledger = ModelCheckpointLedger()
    ledger.heartbeat(stage="accounted", idempotency_key="plan-key", result=result("plan"))
    ledger.heartbeat(stage="started", idempotency_key="synth-key")

    snapshot = ledger.snapshot()
    assert snapshot["kind"] == "kairo.model-call-ledger", snapshot
    assert set(snapshot["slots"]) == {"plan-key", "synth-key"}, snapshot
    assert snapshot["slots"]["plan-key"]["result"]["content"] == "plan", snapshot
    assert snapshot["slots"]["synth-key"]["stage"] == "started", snapshot

    restored = ModelCheckpointLedger(snapshot["slots"])
    assert restored.checkpoint("plan-key")["stage"] == "accounted"
    assert restored.checkpoint("plan-key")["result"]["content"] == "plan"
    assert restored.checkpoint("synth-key")["stage"] == "started"

    restored.heartbeat(stage="accounted", idempotency_key="synth-key", result=result("report"))
    second = restored.snapshot()
    assert second["slots"]["plan-key"]["result"]["content"] == "plan", second
    assert second["slots"]["synth-key"]["result"]["content"] == "report", second

    print("PASS: multi-slot model checkpoint ledger preserves plan and synthesis independently")


if __name__ == "__main__":
    main()
