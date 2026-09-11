#!/usr/bin/env python3
"""D02 shared PostgreSQL proof: admission, bounded pages, rebuild and relay recovery.

Synthetic identity/transport fixtures; no paid providers. Run after canonical migrations
only in the disposable kairo_admission_test database.
"""
import asyncio
from datetime import UTC, datetime, timedelta
import uuid
from time import perf_counter

import httpx
from sqlalchemy import delete, func, select, update

from kairo_core.auth import Principal, require_kairo_user
from kairo_core.command_models import Conversation, ConversationMessage
from kairo_core.config import settings
from kairo_core.db import SessionFactory, engine
from kairo_core.document_models import Document, DocumentVersion
from kairo_core.main import app
from kairo_core.memory_models import MemoryProjectionRecord
from kairo_core.models import Asset, OutboxEvent, Project, Task, WorkflowExecution
from kairo_core.outbox import OutboxRelay, prune_technical_history
from kairo_core.pagination import encode_cursor
from kairo_core.work_capacity import WorkAdmission

OWNER = "d02-data-owner"
FOREIGN = "d02-data-foreign"
INTERNAL = {"X-Kairo-Internal-Token": settings.kairo_internal_token}


async def post(client, path, payload, expected=200):
    for _ in range(100):
        response = await client.post(path, json=payload, headers=INTERNAL)
        if response.status_code == 429 and response.json().get("detail") == "work_admission_busy":
            await asyncio.sleep(0.01)
            continue
        assert response.status_code == expected, (path, response.status_code, response.text)
        return response.json()
    raise AssertionError("Admission lock did not become available")


async def seed():
    now = datetime.now(UTC)
    async with SessionFactory() as session:
        owned, foreign = Project(name="D02 owned", owner_subject=OWNER), Project(name="D02 foreign", owner_subject=FOREIGN)
        conversation = Conversation(subject_ref=OWNER)
        other_conversation = Conversation(subject_ref=FOREIGN)
        session.add_all([owned, foreign, conversation, other_conversation])
        await session.flush()
        messages = [ConversationMessage(conversation_id=conversation.id, role="user", content=f"D02 message {i}") for i in range(123)]
        messages += [ConversationMessage(conversation_id=other_conversation.id, role="user", content="Other owner")]
        session.add_all(messages)
        for i in range(1000):
            project = owned if i < 600 else foreign
            bucket = i % 6
            task = Task(project_id=project.id, title=f"D02 task {i}", priority=i % 5,
                        status="completed" if bucket == 4 else "running" if bucket == 1 else "todo",
                        created_at=now, completed_at=now if bucket == 4 else None,
                        due_at=now - timedelta(days=2) if bucket == 0 else now if bucket == 2 else None,
                        planned_start_at=now if bucket == 3 else None)
            session.add(task)
        documents = []
        for i in range(250):
            project = owned if i < 123 else foreign
            owner = OWNER if i < 123 else FOREIGN
            asset = Asset(project_id=project.id, bucket="d02-fixture", object_key=str(uuid.uuid4()), metadata_json={"owner_subject": owner})
            session.add(asset)
            await session.flush()
            document = Document(asset_id=asset.id, project_id=project.id, title=f"Document {i}", metadata_json={"owner_subject": owner})
            session.add(document)
            documents.append(document)
        await session.flush()
        versions = [DocumentVersion(document_id=documents[0].id, generation=i + 1) for i in range(123)]
        foreign_version = DocumentVersion(document_id=documents[-1].id, generation=1)
        session.add_all([*versions, foreign_version])
        await session.commit()
        return str(owned.id), [str(message.id) for message in messages], str(documents[0].id), str(foreign.id), str(foreign_version.id)


async def all_pages(client, path, size, expected):
    cursor, seen = None, set()
    while True:
        separator = "&" if "?" in path else "?"
        response = await client.get(f"{path}{separator}limit={size}" + (f"&cursor={cursor}" if cursor else ""))
        assert response.status_code == 200, response.text
        page = response.json()
        assert len(page) <= size
        identities = {row["id"] for row in page}
        assert not (seen & identities), "A page repeated IDs at an equal timestamp"
        seen |= identities
        cursor = response.headers.get("X-Kairo-Next-Cursor")
        if not cursor:
            break
    assert len(seen) == expected, (path, len(seen), expected)


async def main():
    assert settings.database_url.endswith("/kairo_admission_test"), "Requires disposable test DB"
    settings.kairo_auth_enabled = True
    settings.kairo_work_global_concurrency = 2
    settings.kairo_work_owner_concurrency = 1
    app.dependency_overrides[require_kairo_user] = lambda: Principal(
        subject=OWNER, username=None, email=None, roles=frozenset(), claims={})
    project_id, messages, document_id, foreign_project, foreign_version = await seed()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://core") as client:
            for size in (1, 10, 100):
                await all_pages(client, "/v1/documents", size, 123)
            await all_pages(client, f"/v1/tasks?project_id={project_id}", 100, 600)
            await all_pages(client, "/v1/assets", 40, 123)
            await all_pages(client, f"/v1/documents/{document_id}/versions", 40, 123)
            assert (await client.get(f"/v1/projects/{foreign_project}")).status_code == 404
            assert (await client.get(f"/v1/document-versions/{foreign_version}")).status_code == 404
            for path in ("/v1/tasks?limit=1000", "/v1/documents?cursor=not-a-cursor", "/v1/today?limit=1000"):
                assert (await client.get(path)).status_code == 422, path
            for identity in (123, {}, []):
                cursor = encode_cursor(["created_at", True, datetime.now(UTC).isoformat(), identity])
                assert (await client.get(f"/v1/tasks?cursor={cursor}")).status_code == 422
            view = (await client.get("/v1/today?timezone=UTC&limit=10")).json()
            for bucket in ("overdue", "in_progress", "due_today", "planned", "completed_today", "backlog"):
                seen = {row["task"]["id"] for row in view[bucket]}
                assert len(seen) == 10, (bucket, view)
                cursor = view["next_cursors"][bucket]
                while cursor:
                    page = (await client.get(f"/v1/today?timezone=UTC&limit=17&bucket={bucket}&cursor={cursor}")).json()
                    ids = {row["task"]["id"] for row in page[bucket]}
                    assert len(ids) <= 17 and not (seen & ids)
                    seen |= ids
                    cursor = page["next_cursors"].get(bucket)
                assert len(seen) == 100, (bucket, len(seen))
            print("PASS 1000-row fixture: SQL owner filtering, equal-key cursor ties, every Today bucket")

            tasks = []
            for message in [messages[0], messages[1], messages[-1]]:
                ensured = await post(client, f"/internal/v1/memory/projections/conversation-messages/{message}/ensure", {})
                tasks.append(ensured["task_id"])
            async def acquire(task, holder="worker-one"):
                return await post(client, "/internal/v1/work-capacity/acquire", {"task_id": task, "holder": holder})
            first, second, foreign = await asyncio.gather(*(acquire(task) for task in tasks))
            assert sum(item["admitted"] for item in (first, second, foreign)) == 2
            assert first["admitted"] != second["admitted"] and foreign["admitted"]
            active_index = 0 if first["admitted"] else 1
            active, waiting = tasks[active_index], tasks[1 - active_index]
            lease = {"task_id": active, "lease_token": (first if active_index == 0 else second)["lease_token"]}
            assert not (await acquire(active, "replacement"))["admitted"]
            for burst in (1, 10, 100, 1000):
                start = perf_counter()
                slots = asyncio.Semaphore(20)
                async def poll(index):
                    async with slots:
                        # A replacement cannot start while either owner's lease remains active.
                        response = await acquire(tasks[index % 3], f"burst-{burst}-{index}")
                        assert not response["admitted"]
                await asyncio.gather(*(poll(i) for i in range(burst)))
                async with SessionFactory() as session:
                    assert await session.scalar(select(func.count()).select_from(WorkAdmission).where(WorkAdmission.status == "active")) == 2
                print(f"PASS saturation: {burst} requests / concurrency 20 / {perf_counter() - start:.3f}s / active=2")
            await post(client, "/internal/v1/work-capacity/renew", lease)
            assert (await client.get("/v1/work-capacity")).json()["active"] == 1
            async with SessionFactory() as session:
                await session.execute(update(WorkAdmission).where(WorkAdmission.task_id == uuid.UUID(active)).values(
                    lease_until=datetime.now(UTC) - timedelta(seconds=1)))
                await session.commit()
            replacement = await acquire(waiting)
            assert replacement["admitted"]
            await post(client, "/internal/v1/work-capacity/renew", lease, expected=409)
            await post(client, "/internal/v1/work-capacity/release", {**lease, "completed": True, "result": {"kind": "stale"}}, expected=409)
            result = {"kind": "fixture-completed", "content": {"task_id": waiting}}
            complete = {"task_id": waiting, "lease_token": replacement["lease_token"], "completed": True, "result": result}
            await post(client, "/internal/v1/work-capacity/release", complete)
            await post(client, "/internal/v1/work-capacity/release", complete)
            assert (await acquire(waiting, "lost-response-retry"))["completed_result"] == result
            settings.kairo_work_owner_max_pending = 1
            await post(client, f"/internal/v1/memory/projections/conversation-messages/{messages[2]}/ensure", {}, expected=429)
            settings.kairo_work_owner_max_pending = 100
            print("PASS global/owner concurrency, transactional backlog, expiry fencing and completed replay")
            workflow_id = f"d02-failure-{active}"
            async with SessionFactory() as session:
                session.add(WorkflowExecution(task_id=uuid.UUID(active), workflow_id=workflow_id,
                                             status="running", correlation_id=uuid.uuid4()))
                await session.commit()
            await post(client, f"/internal/v1/executions/{workflow_id}/fail", {"error": "controlled projector timeout"})
            async with SessionFactory() as session:
                assert (await session.get(WorkAdmission, uuid.UUID(active))).status == "finished"
                rows = list((await session.execute(select(MemoryProjectionRecord).where(MemoryProjectionRecord.task_id == uuid.UUID(active)))).scalars())
                assert rows and all(row.status == "failed" for row in rows)
            assert (await client.post("/internal/v1/work-capacity/acquire", json={"task_id": active, "holder": "untrusted"})).status_code in {401, 403}
            print("PASS failed child propagates terminal projection status and internal token remains mandatory")

            request = {"request_id": str(uuid.uuid4()), "message_ids": messages[:-1], "limit": 40}
            first_page = await post(client, "/internal/v1/memory/rebuild", request)
            assert await post(client, "/internal/v1/memory/rebuild", request) == first_page
            seen, page = set(), first_page
            while True:
                seen.update(row["message_id"] for row in page["messages"])
                assert page["queued"] <= 40
                if page["complete"]:
                    break
                request = {**request, "cursor": page["next_cursor"], "through": page["through"]}
                page = await post(client, "/internal/v1/memory/rebuild", request)
                assert await post(client, "/internal/v1/memory/rebuild", request) == page
            assert len(seen) == 123
            async with SessionFactory() as session:
                rows = list((await session.execute(select(MemoryProjectionRecord).where(
                    MemoryProjectionRecord.source_id == uuid.UUID(messages[0])))).scalars())
                assert all(row.generation == 2 for row in rows), "Retried page duplicated generations"
            print("PASS bounded rebuild, stable watermark and durable page receipts")

            # Restrict relay fixture to three events and prove its SQL claims outlive the connection.
            async with SessionFactory() as session:
                await session.execute(delete(OutboxEvent))
                events = [OutboxEvent(subject="kairo.domain.fixture", event_type="fixture", aggregate_type="fixture",
                          aggregate_id=uuid.uuid4(), correlation_id=uuid.uuid4(), payload={"fixture": i}) for i in range(3)]
                session.add_all(events)
                await session.commit()
            relay = OutboxRelay()
            token, batch = await relay._claim_batch()
            assert len(batch) == 3
            assert not (await OutboxRelay()._claim_batch())[1]
            async with SessionFactory() as session:
                await session.execute(update(OutboxEvent).values(claim_until=datetime.now(UTC) - timedelta(seconds=1)))
                await session.commit()
            delivered = []
            class Transport:
                async def publish(self, subject, payload, *, headers, timeout):
                    # An unrelated SQL transaction can lock the row during transport I/O.
                    async with SessionFactory() as session, session.begin():
                        row = await session.scalar(select(OutboxEvent).where(
                            OutboxEvent.id == uuid.UUID(headers["Nats-Msg-Id"])).with_for_update(nowait=True))
                        assert row.claim_token != token
                    delivered.append(headers["Nats-Msg-Id"])
            relay._js = Transport()
            assert await relay._publish_batch() == 3
            assert set(delivered) == {str(event["id"]) for event in batch}
            async with SessionFactory() as session:
                await session.execute(update(OutboxEvent).values(published_at=datetime.now(UTC) - timedelta(days=60)))
                await session.execute(update(OutboxEvent).where(OutboxEvent.id == batch[0]["id"]).values(published_at=None))
                await session.commit()
            settings.maintenance_batch_size = 1
            assert (await prune_technical_history())["published_events"] == 1
            assert (await prune_technical_history())["published_events"] == 1
            assert (await prune_technical_history())["published_events"] == 0
            async with SessionFactory() as session:
                assert await session.get(OutboxEvent, batch[0]["id"]) is not None
                assert await session.scalar(select(func.count()).select_from(Document)) == 250
            print("PASS relay crash claims, network without SQL locks, bounded retention preserving canonical/unpublished data")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
    print("D02 CAPACITY AND DATA POSTGRESQL CONTRACT PASSED")


if __name__ == "__main__":
    asyncio.run(main())
