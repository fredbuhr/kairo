#!/usr/bin/env python3
"""Real PostgreSQL transactions through Core ASGI; identity fixtures, no provider calls.

Run only in the isolated kairo_admission_test database after alembic upgrade head.
The existing authenticated and SIGKILL suites remain separate mandatory gates.
"""
import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import uuid

import httpx
from sqlalchemy import delete, func, select, update

from kairo_core.auth import Principal, require_kairo_user
from kairo_core.autonomy_models import ModelReservation, ModelUsageRecord
from kairo_core.config import settings
from kairo_core.db import SessionFactory, engine
from kairo_core.main import app
from kairo_core.models import Project, Task

OWNER_A = "admission-owner-a"
OWNER_B = "admission-owner-b"
INTERNAL = {"X-Kairo-Internal-Token": settings.kairo_internal_token}


async def seed(owner: str = OWNER_A, budget: str = "1") -> str:
    async with SessionFactory() as session:
        project = Project(name="Admission proof", owner_subject=owner)
        session.add(project)
        await session.flush()
        task = Task(project_id=project.id, title="Admission proof", budget_usd=Decimal(budget))
        session.add(task)
        await session.commit()
        return str(task.id)


async def reset() -> None:
    async with SessionFactory() as session:
        await session.execute(delete(Project).where(Project.owner_subject.in_((OWNER_A, OWNER_B))))
        await session.commit()


async def request(client, path, payload, expected=200):
    for _ in range(100):
        response = await client.post(path, json=payload, headers=INTERNAL)
        if response.status_code == 429 and response.json().get("detail") == "model_admission_busy":
            assert response.headers["Retry-After"] == "1"
            await asyncio.sleep(0.01)
            continue
        assert response.status_code == expected, (response.status_code, response.text, expected)
        return response.json()
    raise AssertionError("Admission transaction did not release its lock")


async def reserve(client, task, key, amount="0.6", expected=200):
    return await request(client, "/internal/v1/policy/authorize", {
        "task_id": task, "idempotency_key": key, "action": "model.invoke",
        "resource_type": "model_alias", "resource_id": "smart", "authority_level": 1,
        "estimated_cost_usd": amount,
    }, expected)


async def start(client, task, key, expected=200):
    return await request(client, "/internal/v1/model-reservations/start", {
        "task_id": task, "idempotency_key": key,
    }, expected)


async def account(client, task, key, cost="0.25", reported=True, expected=200):
    return await request(client, "/internal/v1/model-usage", {
        "task_id": task, "idempotency_key": key, "model_alias": "smart", "provider": "fixture",
        "correlation_id": str(uuid.uuid5(uuid.NAMESPACE_URL, key)), "cost_usd": cost,
        "metadata": {"cost_reported": reported},
    }, expected)


async def expire(key):
    async with SessionFactory() as session:
        await session.execute(update(ModelReservation).where(ModelReservation.idempotency_key == key).values(
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        ))
        await session.commit()


async def main():
    assert settings.database_url.endswith("/kairo_admission_test"), "Requires disposable test DB"
    settings.kairo_model_global_concurrency = 3
    settings.kairo_model_owner_concurrency = 2
    settings.kairo_model_global_daily_budget_usd = Decimal("50")
    settings.kairo_model_owner_daily_budget_usd = Decimal("10")
    app.dependency_overrides[require_kairo_user] = lambda: Principal(
        subject=OWNER_A, username=None, email=None, roles=frozenset(), claims={}
    )
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://core") as client:
            await reset()
            task = await seed()
            # Two independent requests/SQL transactions race on the previously unsafe 0.6+0.6 case.
            decisions = await asyncio.gather(reserve(client, task, "race-a"), reserve(client, task, "race-b"))
            assert sorted(d["allowed"] for d in decisions) == [False, True], decisions
            assert [d["reason"] for d in decisions if not d["allowed"]] == ["hard_budget_exceeded"]
            key = "race-a" if decisions[0]["allowed"] else "race-b"
            assert (await reserve(client, task, key))["allowed"]  # lost reserve response
            async with SessionFactory() as session:
                assert await session.scalar(select(func.count()).select_from(ModelReservation)) == 1
            # Concurrent dispatch claims: only one caller ever gets permission to send the request.
            async def claim():
                for _ in range(100):
                    r = await client.post("/internal/v1/model-reservations/start", headers=INTERNAL,
                                          json={"task_id": task, "idempotency_key": key})
                    if r.status_code == 429:
                        await asyncio.sleep(0.01)
                        continue
                    return r.status_code
                raise AssertionError("claim remained busy")
            assert sorted(await asyncio.gather(claim(), claim())) == [200, 409]
            assert not (await reserve(client, task, key))["allowed"]  # heartbeat may be entirely lost
            budgets = await asyncio.gather(account(client, task, key), account(client, task, key))
            assert all(Decimal(b["spent_usd"]) == Decimal("0.25") for b in budgets)
            assert Decimal(budgets[-1]["reserved_usd"]) == 0
            async with SessionFactory() as session:
                assert await session.scalar(select(func.count()).select_from(ModelUsageRecord)) == 1
            await account(client, task, key, cost="0.30", expected=409)
            assert (await reserve(client, task, "after-settle"))["allowed"]
            print("PASS concurrent budget reservation, one-shot dispatch, idempotent settlement")

            # One owner cannot obtain more slots by multiplying projects. Another can still run.
            await reset()
            a1, a2, a3 = [await seed(budget="10") for _ in range(3)]
            b1, b2 = [await seed(OWNER_B, "10") for _ in range(2)]
            assert (await reserve(client, a1, "owner-a1"))["allowed"]
            assert (await reserve(client, a2, "owner-a2"))["allowed"]
            assert (await reserve(client, a3, "owner-a3", expected=429))["detail"] == "model_owner_capacity_exhausted"
            assert (await reserve(client, b1, "owner-b1"))["allowed"]
            assert (await reserve(client, b2, "owner-b2", expected=429))["detail"] == "model_global_capacity_exhausted"
            summary = (await client.get("/v1/model-admission")).json()
            assert summary["active_calls"] == 2, summary
            assert (await client.get(f"/v1/tasks/{b1}/budget")).status_code == 404
            await start(client, b1, "owner-a1", expected=404)
            await reserve(client, b1, "owner-a1", expected=409)
            print("PASS global/owner slots across projects and owner-scoped visibility")

            # Daily monetary admission is atomic across different tasks, not just a task lock.
            await reset()
            settings.kairo_model_owner_daily_budget_usd = Decimal("1")
            a1, a2 = await seed(budget="10"), await seed(budget="10")
            decisions = await asyncio.gather(reserve(client, a1, "money-a1"), reserve(client, a2, "money-a2"))
            assert sorted(d["allowed"] for d in decisions) == [False, True]
            assert any(d["reason"] == "model_owner_daily_budget_exceeded" for d in decisions)
            settings.kairo_model_owner_daily_budget_usd = Decimal("10")
            settings.kairo_model_global_daily_budget_usd = Decimal("1")
            b1 = await seed(OWNER_B, "10")
            assert (await reserve(client, b1, "money-global"))["reason"] == "model_global_daily_budget_exceeded"
            settings.kairo_model_global_daily_budget_usd = Decimal("50")
            print("PASS owner/global money admission under concurrent transactions")

            await reset()
            task = await seed()
            assert (await reserve(client, task, "never-started"))["allowed"]
            await expire("never-started")
            assert (await reserve(client, task, "interrupted"))["allowed"]
            await start(client, task, "never-started", expected=409)
            await start(client, task, "interrupted")
            await expire("interrupted")
            state = (await client.get(f"/v1/tasks/{task}/budget")).json()
            assert state["uncertain_calls"] == 1 and Decimal(state["uncertain_usd"]) == Decimal("0.6"), state
            assert (await reserve(client, task, "unsafe-reuse"))["reason"] == "hard_budget_exceeded"
            assert not (await reserve(client, task, "interrupted"))["allowed"]
            state = await account(client, task, "interrupted", cost="0.1")
            assert state["uncertain_calls"] == 0
            assert (await reserve(client, task, "safe-new-call"))["allowed"]
            await start(client, task, "safe-new-call")
            state = await account(client, task, "safe-new-call", cost="0", reported=False)
            assert state["uncertain_calls"] == 1
            state = await account(client, task, "safe-new-call", cost="0.2", reported=True)
            assert state["uncertain_calls"] == 0 and Decimal(state["spent_usd"]) == Decimal("0.3")
            # A real cost above the estimate is recorded and surfaced, never discarded to fake a ceiling.
            assert (await reserve(client, task, "overrun", amount="0.1"))["allowed"]
            await start(client, task, "overrun")
            state = await account(client, task, "overrun", cost="1")
            assert state["over_budget"] and Decimal(state["spent_usd"]) == Decimal("1.3")
            assert (await reserve(client, task, "after-overrun", amount="0.01"))["reason"] == "hard_budget_exceeded"
            print("PASS expiry, unknown liability, late reconciliation and visible overrun")

            await reset()
            task = await seed()
            assert (await reserve(client, task, "zero", amount="0"))["reason"] == "paid_model_requires_positive_estimate"
            await reserve(client, task, "fine", amount="0.0000001")
            async with SessionFactory() as session:
                assert (await session.get(ModelReservation, "fine")).amount_usd == Decimal("0.000001")
            # Outstanding uncertainty cannot evade daily caps by waiting for midnight.
            await start(client, task, "fine")
            async with SessionFactory() as session:
                await session.execute(update(ModelReservation).where(ModelReservation.idempotency_key == "fine").values(
                    created_at=datetime.now(UTC) - timedelta(days=2),
                    expires_at=datetime.now(UTC) - timedelta(days=1),
                ))
                await session.commit()
            assert Decimal((await client.get("/v1/model-admission")).json()["daily_exposure_usd"]) == Decimal("0.000001")
            # Internal boundary and invalid values are exercised through the actual router.
            assert (await client.post("/internal/v1/model-reservations/start", json={"task_id": task, "idempotency_key": "fine"})).status_code in {401, 403}
            print("PASS rounding, cross-day liabilities and internal-token boundary")
    finally:
        app.dependency_overrides.clear()
        await reset()
        await engine.dispose()
    print("MODEL ADMISSION POSTGRESQL CONTRACT PASSED")


if __name__ == "__main__":
    asyncio.run(main())
