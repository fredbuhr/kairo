"""Regression tests for the observed projection-report / Task-completion interleaving.

These exercise the smoke's synchronization only. Foundation's Docker integration proves the
real ORM, outbox, JetStream, Core and Temporal path separately.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import memory_projection as smoke


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.now += delay


class TaskCompletionWaitContract(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        for name in ("monotonic", "sleep"):
            patcher = patch.object(smoke.time, name, getattr(self.clock, name))
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_report_can_be_projected_while_task_is_still_running(self) -> None:
        completed = {"id": "memory-g1", "status": "completed", "input": {"generation": 1}}
        with patch.object(smoke, "json_request", side_effect=[
            (200, {"id": "memory-g1", "status": "running"}),
            (200, completed),
        ]) as request:
            self.assertEqual(smoke.wait_for_task_completion("memory-g1"), completed)
            self.assertEqual(request.call_count, 2)
        self.assertEqual(self.clock.now, 0.5)

    def test_completed_task_returns_without_a_sleep(self) -> None:
        with patch.object(smoke, "json_request", return_value=(200, {"status": "completed"})):
            smoke.wait_for_task_completion("memory-g2")
        self.assertEqual(self.clock.now, 0.0)

    def test_failed_task_stops_immediately_with_identity_and_state(self) -> None:
        with patch.object(smoke, "json_request", return_value=(200, {"status": "failed"})) as request:
            with self.assertRaisesRegex(AssertionError, "memory-g2.*failed"):
                smoke.wait_for_task_completion("memory-g2")
            self.assertEqual(request.call_count, 1)
        self.assertEqual(self.clock.now, 0.0)

    def test_stuck_task_has_bounded_wait_and_request_timeouts(self) -> None:
        with patch.object(smoke, "json_request", return_value=(200, {"status": "running"})) as request:
            with self.assertRaisesRegex(TimeoutError, "memory-g2.*1.0s.*running"):
                smoke.wait_for_task_completion("memory-g2", timeout=1.0)
            self.assertEqual([call.kwargs["timeout"] for call in request.call_args_list], [1.0, 0.5])
        self.assertEqual(self.clock.now, 1.0)


if __name__ == "__main__":
    unittest.main()
