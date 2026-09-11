"""Real subprocess lifecycle and bounded document-activity regressions; no model downloads."""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError
from temporalio.exceptions import ApplicationError

from nevolium_worker import document_ingestion as runtime
from nevolium_worker.config import Settings
from nevolium_worker.document_parser import parse_document


class DocumentExecutionContract(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "source.txt"
        self.path.write_text("Document proof.\n\nCanonical second paragraph.")
        self.settings = Settings(nevolium_document_parse_timeout_seconds=5)
        self.enterContext(patch.object(runtime, "settings", self.settings))
        self.enterContext(patch.object(runtime, "_document_slots", asyncio.Semaphore(1)))
        self.children: list[asyncio.subprocess.Process] = []
        self.real_spawn = asyncio.create_subprocess_exec

    async def asyncTearDown(self) -> None:
        # Test assertion failures must not leave their controlled slow fixtures running either.
        for child in self.children:
            if child.returncode is None:
                child.kill()
            await child.wait()

    async def wait_file(self, path: Path) -> None:
        async with asyncio.timeout(5):
            while not path.exists():
                await asyncio.sleep(0.01)

    async def slow_spawn(self, *args, **kwargs):
        source, result = args[3], args[4]
        script = """
import json, os, sys, time
from pathlib import Path
root = Path(sys.argv[1]).parent
(root / 'ready').write_text(str(os.getpid()))
while not (root / 'release').exists():
    time.sleep(0.01)
Path(sys.argv[2]).write_text(json.dumps({'parser': 'controlled-slow-fixture', 'parser_version': None,
    'metadata': {}, 'chunks': [{'text': 'proof', 'metadata': {}}]}))
"""
        child = await self.real_spawn(sys.executable, "-c", script, source, result, **kwargs)
        self.children.append(child)
        return child

    async def test_real_fallback_subprocess_preserves_document_contract(self) -> None:
        result = await runtime._run_parser(self.path, "text/plain")
        self.assertEqual(result["parser"], "text-fallback")
        self.assertEqual(result["chunks"][0]["text"], self.path.read_text())

    async def test_slow_parser_leaves_async_loop_available(self) -> None:
        with patch.object(runtime.asyncio, "create_subprocess_exec", self.slow_spawn):
            work = asyncio.create_task(runtime._run_parser(self.path, "text/plain"))
            await self.wait_file(self.path.parent / "ready")
            light_completed = asyncio.Event()

            async def light_activity():
                light_completed.set()

            await asyncio.wait_for(light_activity(), timeout=1)
            self.assertTrue(light_completed.is_set())
            self.assertFalse(work.done())
            (self.path.parent / "release").touch()
            result = await work
            self.assertEqual(result["parser"], "controlled-slow-fixture")
            self.assertIsNotNone(self.children[0].returncode)

    async def test_timeout_terminates_and_reaps_real_child(self) -> None:
        self.settings.nevolium_document_parse_timeout_seconds = 0.25
        with patch.object(runtime.asyncio, "create_subprocess_exec", self.slow_spawn):
            with self.assertRaises(ApplicationError) as caught:
                await runtime._run_parser(self.path, "text/plain")
        self.assertTrue(caught.exception.non_retryable)
        self.assertIn("time limit", str(caught.exception))
        self.assertIsNotNone(self.children[0].returncode)
        with self.assertRaises(ProcessLookupError):
            os.kill(self.children[0].pid, 0)

    async def test_cancellation_during_spawn_does_not_orphan_child(self) -> None:
        spawned = asyncio.Event()
        deliver_handle = asyncio.Event()

        async def delayed_spawn(*args, **kwargs):
            child = await self.slow_spawn(*args, **kwargs)
            spawned.set()
            await deliver_handle.wait()
            return child

        with patch.object(runtime.asyncio, "create_subprocess_exec", delayed_spawn):
            work = asyncio.create_task(runtime._run_parser(self.path, "text/plain"))
            await asyncio.wait_for(spawned.wait(), timeout=5)
            work.cancel()
            deliver_handle.set()
            with self.assertRaises(asyncio.CancelledError):
                await work
        self.assertIsNotNone(self.children[0].returncode)

    async def test_activity_cancellation_cleans_directory_heartbeat_and_slot(self) -> None:
        downloaded = asyncio.Event()
        paths = []

        async def download(_source, path):
            path.write_text("proof")
            paths.append(path)
            downloaded.set()
            return hashlib.sha256(b"proof").hexdigest(), 5

        with (
            patch.object(runtime, "_fetch_source", AsyncMock(return_value={"filename": "owned.txt"})),
            patch.object(runtime, "_download_source", download),
            patch.object(runtime.asyncio, "create_subprocess_exec", self.slow_spawn),
            patch.object(runtime, "_report_complete", AsyncMock()) as report,
        ):
            work = asyncio.create_task(runtime._perform_document_ingestion(
                {"task_input": {"document_version_id": "fixture"}}
            ))
            await asyncio.wait_for(downloaded.wait(), timeout=5)
            await self.wait_file(paths[0].parent / "ready")
            work.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await work
            self.assertFalse(paths[0].parent.exists())
            self.assertFalse(runtime._document_slots.locked())
            report.assert_not_awaited()
        self.assertFalse(any(t.get_name() == "document-ingestion-heartbeat" for t in asyncio.all_tasks()))

    async def test_capacity_is_bounded_and_waiting_cancellation_does_not_take_a_slot(self) -> None:
        first_started, release = asyncio.Event(), asyncio.Event()
        active = peak = 0
        calls = []

        async def ingest(version_id):
            nonlocal active, peak
            calls.append(version_id)
            active += 1
            peak = max(peak, active)
            first_started.set()
            try:
                await release.wait()
                return {"id": version_id}
            finally:
                active -= 1

        with patch.object(runtime, "_ingest", ingest):
            tasks = [asyncio.create_task(runtime._perform_document_ingestion(
                {"task_input": {"document_version_id": str(i)}}
            )) for i in range(3)]
            await asyncio.wait_for(first_started.wait(), timeout=5)
            tasks[1].cancel()
            with self.assertRaises(asyncio.CancelledError):
                await tasks[1]
            self.assertEqual(calls, ["0"])
            release.set()
            self.assertEqual(await tasks[0], {"id": "0"})
            self.assertEqual(await tasks[2], {"id": "2"})
        self.assertEqual(peak, 1)
        self.assertFalse(runtime._document_slots.locked())

    async def test_source_bound_covers_missing_length_and_canonical_digest(self) -> None:
        class Chunks(httpx.AsyncByteStream):
            async def __aiter__(self):
                for _ in range(4):
                    yield b"x" * 65536

        for mode in ("declared-large", "stream-large", "bad-digest", "valid"):
            self.settings.nevolium_document_max_source_bytes = 100000

            def respond(_request):
                if mode == "declared-large":
                    return httpx.Response(200, headers={"content-length": "100001"}, content=b"")
                if mode == "stream-large":
                    return httpx.Response(200, stream=Chunks())
                return httpx.Response(200, content=b"proof")

            client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
            source = {"download_url": "https://source.invalid/owned", "source_sha256":
                      "0" * 64 if mode == "bad-digest" else hashlib.sha256(b"proof").hexdigest()}
            with self.subTest(mode=mode), patch.object(runtime.httpx, "AsyncClient", return_value=client):
                if mode == "valid":
                    digest, size = await runtime._download_source(source, self.path)
                    self.assertEqual((digest, size), (source["source_sha256"], 5))
                else:
                    with self.assertRaises(ApplicationError) as caught:
                        await runtime._download_source(source, self.path)
                    self.assertTrue(caught.exception.non_retryable)
                    self.assertLessEqual(self.path.stat().st_size, 100000)

    async def test_parser_text_empty_and_unsupported_inputs_fail_closed(self) -> None:
        for content, media_type, max_chars in (("abcdef", "text/plain", 5), (" ", "text/plain", 10), ("pdf", "application/pdf", 10)):
            self.path.write_text(content)
            with self.subTest(content=content), patch("importlib.util.find_spec", return_value=None):
                with self.assertRaises(ValueError):
                    parse_document(self.path, media_type, max_chars)

    async def test_parser_does_not_receive_service_credentials(self) -> None:
        real = self.real_spawn

        async def inspect_spawn(*args, **kwargs):
            self.assertNotIn("NEVOLIUM_INTERNAL_TOKEN", kwargs["env"])
            self.assertNotIn("DATABASE_URL", kwargs["env"])
            return await real(*args, **kwargs)

        with (
            patch.dict(os.environ, {"NEVOLIUM_INTERNAL_TOKEN": "fixture-secret", "DATABASE_URL": "fixture-db"}),
            patch.object(runtime.asyncio, "create_subprocess_exec", inspect_spawn),
        ):
            await runtime._run_parser(self.path, "text/plain")

    async def test_invalid_worker_limits_rejected_at_startup(self) -> None:
        for values in ({"nevolium_document_max_concurrent": 0}, {"nevolium_document_max_concurrent": 16},
                       {"nevolium_worker_max_concurrent_workflow_tasks": 1},
                       {"nevolium_document_parse_timeout_seconds": 600}, {"nevolium_document_max_source_bytes": 0}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                Settings(**values)


if __name__ == "__main__":
    unittest.main()
