"""Real owned processes and lease orchestration; no model downloads or paid calls."""
import asyncio
from datetime import UTC, datetime
import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from nevolium_worker import memory_projection, work_capacity
from nevolium_worker.config import Settings
from nevolium_worker.owned_process import run_owned_process
from nevolium_worker.workflows import TaskExecutionWorkflow


class HeavyWorkExecutionContract(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(patch.object(work_capacity.activity, "info", return_value=SimpleNamespace(
            workflow_run_id="run", activity_id="activity", attempt=1)))

    async def test_denied_work_returns_to_timer_without_starting_operation(self):
        operation = AsyncMock()
        with patch.object(work_capacity, "_call", AsyncMock(return_value={"admitted": False})):
            result = await asyncio.wait_for(work_capacity.run_admitted({"task_id": "task"}, operation), 1)
        self.assertEqual(result, {"waiting_for_capacity": True})
        operation.assert_not_awaited()

    async def test_completed_result_replays_without_projector(self):
        operation, result = AsyncMock(), {"kind": "completed", "content": {"proof": True}}
        with patch.object(work_capacity, "_call", AsyncMock(return_value={"completed_result": result})):
            self.assertEqual(await work_capacity.run_admitted({"task_id": "task"}, operation), result)
        operation.assert_not_awaited()

    async def test_failed_renewal_kills_and_reaps_before_releasing_lease(self):
        real_spawn = asyncio.create_subprocess_exec
        spawned, children, released = asyncio.Event(), [], []
        async def spawn(*args, **kwargs):
            child = await real_spawn(*args, **kwargs)
            children.append(child)
            spawned.set()
            return child
        async def call(action, payload):
            if action == "acquire":
                return {"admitted": True, "lease_token": "fixture-lease"}
            if action == "release":
                self.assertFalse(payload.get("completed", False))
                self.assertIsNotNone(children[0].returncode)
                with self.assertRaises(ProcessLookupError):
                    os.kill(children[0].pid, 0)
                released.append(True)
                return {"released": True}
            raise AssertionError(action)
        async def lose_lease(_lease):
            await spawned.wait()
            raise RuntimeError("controlled lease loss")
        async def operation():
            self.assertEqual(work_capacity.current_work_lease.get(), "fixture-lease")
            await run_owned_process(sys.executable, "-c", "import time; time.sleep(60)", environment={}, timeout=60)
        try:
            with patch.object(asyncio, "create_subprocess_exec", spawn), patch.object(work_capacity, "_call", call), patch.object(work_capacity, "_renew", lose_lease):
                with self.assertRaisesRegex(RuntimeError, "controlled lease loss"):
                    await asyncio.wait_for(work_capacity.run_admitted({"task_id": "task"}, operation), 5)
            self.assertEqual(released, [True])
            self.assertIsNone(work_capacity.current_work_lease.get())
        finally:
            for child in children:
                if child.returncode is None:
                    child.kill()
                await child.wait()

    async def test_memory_uses_real_child_and_withholds_core_and_provider_secrets(self):
        real_spawn, environments = asyncio.create_subprocess_exec, []
        async def spawn(*args, **kwargs):
            environments.append(kwargs["env"])
            return await real_spawn(*args, **kwargs)
        source = {"message_id": "fixture", "conversation_id": "conversation", "subject_ref": "owner",
                  "content": "Canonical source", "role": "user", "source_version": 1,
                  "created_at": datetime.now(UTC).isoformat()}
        with patch.dict(os.environ, {"NEVOLIUM_INTERNAL_TOKEN": "fixture-secret", "OPENAI_API_KEY": "fixture-key"}), patch.object(asyncio, "create_subprocess_exec", spawn):
            reports = await asyncio.wait_for(memory_projection._run_projection(source, "stub"), 15)
        self.assertEqual([r["projector"] for r in reports], ["mem0", "graphiti"])
        self.assertTrue(all(r["metadata"]["backend"] == "deterministic-stub" for r in reports))
        self.assertNotIn("NEVOLIUM_INTERNAL_TOKEN", environments[0])
        self.assertNotIn("OPENAI_API_KEY", environments[0])

    async def test_waiting_work_uses_durable_timer_and_bounded_history(self):
        # Temporal orchestration fixture complements the real Temporal memory/document CI suites.
        from nevolium_worker import workflows
        timer = AsyncMock()
        execute = AsyncMock(side_effect=[{"waiting_for_capacity": True}, {"kind": "done"}])
        with patch.object(workflows.workflow, "execute_activity", execute), patch.object(workflows.workflow, "sleep", timer):
            result = await TaskExecutionWorkflow()._heavy_work("fixture", {}, {}, 5)
        self.assertEqual(result, {"kind": "done"})
        timer.assert_awaited_once_with(5)
        class Continued(BaseException):
            pass
        with patch.object(workflows.workflow, "execute_activity", AsyncMock(return_value={"waiting_for_capacity": True})), patch.object(workflows.workflow, "sleep", AsyncMock()), patch.object(workflows.workflow, "continue_as_new", side_effect=Continued) as continuation:
            with self.assertRaises(Continued):
                await TaskExecutionWorkflow()._heavy_work("fixture", {}, {"task_id": "retained"}, 5)
            continuation.assert_called_once_with({"task_id": "retained"})

    def test_configuration_reserves_slots_for_other_activities(self):
        with self.assertRaises(ValidationError):
            Settings(nevolium_work_global_concurrency=4, nevolium_worker_max_concurrent_activities=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
