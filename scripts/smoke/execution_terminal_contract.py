"""Offline regression checks for new failure timestamps and replay preservation."""
from datetime import UTC, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import uuid

from nevolium_core import workflows
from nevolium_core.schemas import InternalFailRequest


class ExecutionTerminalContract(unittest.IsolatedAsyncioTestCase):
    def fixture(self, status="running", finished=None):
        task = SimpleNamespace(id=uuid.uuid4(), status=status, completed_at=finished,
                               input={}, authority_ceiling=1)
        execution = SimpleNamespace(id=uuid.uuid4(), task_id=task.id, status=status,
                                    completed_at=finished, last_error=None,
                                    correlation_id=uuid.uuid4())
        session = AsyncMock()
        session.scalar.return_value = execution
        session.get.return_value = task
        return task, execution, session

    async def fail(self, session, error="fixture failure"):
        with (
            patch.object(workflows, "enqueue_domain_event", AsyncMock()) as events,
            patch.object(workflows, "append_audit", AsyncMock()) as audit,
            patch.object(workflows, "_propagate_semantic_route_failure", AsyncMock()),
            patch.object(workflows, "_propagate_document_ingestion_failure", AsyncMock()),
        ):
            result = await workflows.internal_fail_execution(
                "fixture-workflow", InternalFailRequest(error=error), session,
            )
            return result, events.await_count, audit.await_count

    async def test_new_failure_stamps_task_and_execution_once(self):
        task, execution, session = self.fixture()
        before = datetime.now(UTC)
        result, events, audits = await self.fail(session)
        self.assertEqual(result, {"status": "failed"})
        self.assertEqual(task.status, "failed")
        self.assertEqual(task.completed_at, execution.completed_at)
        self.assertLessEqual(before, execution.completed_at)
        self.assertLessEqual(execution.completed_at, datetime.now(UTC))
        self.assertEqual((events, audits), (1, 1))
        first = execution.completed_at
        _, events, audits = await self.fail(session, "different retry error")
        self.assertEqual(execution.completed_at, first)
        self.assertEqual(task.completed_at, first)
        self.assertEqual(execution.last_error, "fixture failure")
        self.assertEqual((events, audits), (0, 0))

    async def test_completed_execution_is_not_changed(self):
        first = datetime(2026, 1, 1, tzinfo=UTC)
        task, execution, session = self.fixture("completed", first)
        result, events, audits = await self.fail(session)
        self.assertEqual(result, {"status": "completed"})
        self.assertEqual(task.status, "completed")
        self.assertEqual(execution.completed_at, first)
        self.assertEqual(task.completed_at, first)
        self.assertEqual((events, audits), (0, 0))
        session.commit.assert_not_awaited()

    async def test_legacy_failure_without_timestamp_is_not_backfilled(self):
        task, execution, session = self.fixture("failed")
        _, events, audits = await self.fail(session)
        self.assertIsNone(execution.completed_at)
        self.assertIsNone(task.completed_at)
        self.assertEqual((events, audits), (0, 0))

    async def test_existing_terminal_dates_are_preserved(self):
        first = datetime(2026, 1, 1, tzinfo=UTC)
        task, execution, session = self.fixture(finished=first)
        await self.fail(session)
        self.assertEqual(execution.completed_at, first)
        self.assertEqual(task.completed_at, first)


if __name__ == "__main__":
    unittest.main()
