"""Regress completed-result leakage and failure mutation through a different Task."""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from temporalio.exceptions import ApplicationError

from nevolium_worker import tool_runtime as runtime


class ToolTaskBindingContract(unittest.IsolatedAsyncioTestCase):
    def payload(self, task_id: str = "task-a") -> dict:
        return {
            "task_id": task_id, "workflow_execution_id": "execution-a",
            "task_input": {"tool_invocation_id": "invocation-a"},
        }

    async def test_foreign_or_missing_task_cannot_read_completed_result_or_start_tool(self) -> None:
        for status in ("completed", "pending", "running"):
            for caller, owner in (("task-b", "task-a"), ("", ""), ("task-a", "")):
                context = {"task_id": owner, "status": status, "result": {"secret": "owner-a-sentinel"}}
                with (
                    self.subTest(status=status, caller=caller, owner=owner),
                    patch.object(runtime, "_get_context", AsyncMock(return_value=context)),
                    patch.object(runtime, "_start", AsyncMock()) as start,
                    patch.object(runtime, "_complete", AsyncMock()) as complete,
                    patch.object(runtime, "Client") as client,
                ):
                    with self.assertRaises(ApplicationError) as caught:
                        await runtime.perform_tool_invocation(self.payload(caller))
                    self.assertTrue(caught.exception.non_retryable)
                    start.assert_not_awaited()
                    complete.assert_not_awaited()
                    client.assert_not_called()

    async def test_same_task_completed_replay_preserves_result_without_external_call(self) -> None:
        context = {
            "task_id": "task-a", "status": "completed", "tool_key": "fixture.read",
            "result": {"value": "owner-a-sentinel"},
        }
        with (
            patch.object(runtime, "_get_context", AsyncMock(return_value=context)),
            patch.object(runtime, "_start", AsyncMock()) as start,
            patch.object(runtime, "Client") as client,
        ):
            result = await runtime.perform_tool_invocation(self.payload())
            self.assertEqual(result["content"]["result"], context["result"])
            self.assertTrue(result["content"]["replayed"])
            start.assert_not_awaited()
            client.assert_not_called()

    async def test_failure_carries_current_task_and_handles_rejected_binding(self) -> None:
        for applied in (True, False):
            with patch.object(runtime, "_fail", AsyncMock(return_value=applied)) as fail:
                result = await runtime.fail_tool_invocation({**self.payload("task-b"), "error": "denied"})
                fail.assert_awaited_once_with("invocation-a", "task-b", "denied")
                self.assertEqual(result["status"], "failed" if applied else "binding-rejected")
        with patch.object(runtime, "_fail", AsyncMock()) as fail:
            with self.assertRaises(RuntimeError):
                await runtime.fail_tool_invocation(self.payload(""))
            fail.assert_not_awaited()

    async def test_failure_http_contract_is_bound_and_only_conflict_is_suppressed(self) -> None:
        for status in (200, 409, 500):
            def respond(request: httpx.Request) -> httpx.Response:
                self.assertTrue(request.url.path.endswith("/invocation-a/fail"))
                self.assertEqual(json.loads(request.content), {"task_id": "task-b", "error": "x" * 4000})
                return httpx.Response(status, json={})

            client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
            with patch.object(runtime.httpx, "AsyncClient", return_value=client):
                if status == 500:
                    with self.assertRaises(httpx.HTTPStatusError):
                        await runtime._fail("invocation-a", "task-b", "x" * 5000)
                else:
                    self.assertEqual(await runtime._fail("invocation-a", "task-b", "x" * 5000), status == 200)


if __name__ == "__main__":
    unittest.main()
