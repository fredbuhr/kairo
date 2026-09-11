from __future__ import annotations

import asyncio
import importlib.util
import os
import json
from pathlib import Path
import sys
import tempfile
import threading
from datetime import datetime
from typing import Any

import httpx
from temporalio import activity

from .config import settings
from .owned_process import run_owned_process
from .work_capacity import current_work_lease, run_admitted

MEM0_COLLECTION = "kairo_mem0_memory_v1"
MEM0_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MEM0_EMBEDDING_DIMS = 384

_mem0_lock = threading.Lock()
_mem0_instance: Any | None = None


def _headers() -> dict[str, str]:
    return {"X-Kairo-Internal-Token": settings.kairo_internal_token}


def memory_projector_mode() -> str:
    requested = settings.kairo_memory_projector_mode.strip().lower()
    if requested not in {"auto", "real", "stub"}:
        raise RuntimeError("KAIRO_MEMORY_PROJECTOR_MODE must be one of: auto, real, stub")
    if requested != "auto":
        return requested
    available = all(
        importlib.util.find_spec(module) is not None for module in ("mem0", "graphiti_core")
    )
    return "real" if available else "stub"


def _postgres_connection_string() -> str:
    explicit = settings.mem0_database_url.strip()
    value = explicit or f"{settings.database_url.rsplit('/', 1)[0]}/mem0"
    if value.startswith("postgresql+asyncpg://"):
        return "postgresql://" + value.removeprefix("postgresql+asyncpg://")
    if value.startswith("postgresql+psycopg://"):
        return "postgresql://" + value.removeprefix("postgresql+psycopg://")
    return value


def _memory_scope(source: dict[str, Any]) -> str:
    subject_ref = str(source.get("subject_ref") or "").strip()
    if subject_ref and not any(char.isspace() for char in subject_ref):
        return f"subject:{subject_ref}"
    return f"conversation:{source['conversation_id']}"


def _get_mem0_instance() -> Any:
    global _mem0_instance
    with _mem0_lock:
        if _mem0_instance is not None:
            return _mem0_instance

        # Mem0 is only a projection engine here. `infer=False` is mandatory below and this
        # unreachable endpoint makes any accidental direct LLM path fail closed.
        os.environ.setdefault("MEM0_TELEMETRY", "false")
        from mem0 import Memory

        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "api_key": "kairo-direct-llm-disabled",
                    "model": "gpt-5-mini",
                    "openai_base_url": "http://127.0.0.1:9/v1",
                },
            },
            "embedder": {
                "provider": "fastembed",
                "config": {
                    "model": MEM0_EMBEDDING_MODEL,
                    "embedding_dims": MEM0_EMBEDDING_DIMS,
                },
            },
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "collection_name": MEM0_COLLECTION,
                    "embedding_model_dims": MEM0_EMBEDDING_DIMS,
                    "connection_string": _postgres_connection_string(),
                    "hnsw": True,
                    "diskann": False,
                },
            },
        }
        _mem0_instance = Memory.from_config(config)
        return _mem0_instance


def _mem0_project_sync(source: dict[str, Any]) -> dict[str, Any]:
    memory = _get_mem0_instance()
    message_id = str(source["message_id"])
    scope = _memory_scope(source)

    existing = memory.get_all(
        filters={"user_id": scope, "kairo_message_id": message_id},
        top_k=10,
    )
    existing_results = existing.get("results") if isinstance(existing, dict) else []
    if existing_results:
        projection_key = str(existing_results[0]["id"])
        return {
            "projector": "mem0",
            "status": "projected",
            "projection_key": projection_key,
            "metadata": {
                "backend": "mem0-pgvector",
                "scope": scope,
                "infer": False,
                "embedding_model": MEM0_EMBEDDING_MODEL,
                "embedding_dims": MEM0_EMBEDDING_DIMS,
                "database": "derived-mem0",
                "reused": True,
            },
        }

    result = memory.add(
        [{"role": str(source["role"]), "content": str(source["content"])}],
        user_id=scope,
        metadata={
            "kairo_message_id": message_id,
            "kairo_conversation_id": str(source["conversation_id"]),
            "kairo_source_version": int(source["source_version"]),
            "kairo_created_at": str(source["created_at"]),
        },
        infer=False,
    )
    results = result.get("results") if isinstance(result, dict) else None
    if not results:
        raise RuntimeError("Mem0 raw projection returned no memory")
    projection_key = str(results[0]["id"])
    return {
        "projector": "mem0",
        "status": "projected",
        "projection_key": projection_key,
        "metadata": {
            "backend": "mem0-pgvector",
            "scope": scope,
            "infer": False,
            "embedding_model": MEM0_EMBEDDING_MODEL,
            "embedding_dims": MEM0_EMBEDDING_DIMS,
            "database": "derived-mem0",
            "reused": False,
        },
    }


async def _graphiti_project(source: dict[str, Any]) -> dict[str, Any]:
    from graphiti_core.driver.neo4j_driver import Neo4jDriver
    from graphiti_core.nodes import EpisodeType, EpisodicNode

    created_at = datetime.fromisoformat(str(source["created_at"]).replace("Z", "+00:00"))
    message_id = str(source["message_id"])
    driver = Neo4jDriver(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    try:
        episode = EpisodicNode(
            uuid=message_id,
            name=f"KAIRO {source['role']} message {message_id}",
            group_id=f"conversation:{source['conversation_id']}",
            source=EpisodeType.message,
            source_description=(
                "KAIRO canonical conversation_message "
                f"{message_id}; source_version={source['source_version']}"
            ),
            content=f"{source['role']}: {source['content']}",
            created_at=created_at,
            valid_at=created_at,
        )
        await driver.episode_node_ops.save(driver, episode)
    finally:
        await driver.close()

    return {
        "projector": "graphiti",
        "status": "projected",
        "projection_key": message_id,
        "metadata": {
            "backend": "graphiti-neo4j",
            "group_id": f"conversation:{source['conversation_id']}",
            "episode_type": "message",
            "generative_extraction": False,
        },
    }


def _stub_projection(projector: str, source: dict[str, Any]) -> dict[str, Any]:
    message_id = str(source["message_id"])
    return {
        "projector": projector,
        "status": "projected",
        "projection_key": f"stub:{projector}:{message_id}",
        "metadata": {
            "backend": "deterministic-stub",
            "source_id": message_id,
            "generative_extraction": False,
        },
    }


async def _fetch_source(message_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/memory/"
            f"sources/conversation-messages/{message_id}",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def _report(message_id: str, generation: int, reports: list[dict[str, Any]]) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{settings.kairo_core_url.rstrip('/')}/internal/v1/memory/"
            f"projections/conversation-messages/{message_id}/report",
            headers=_headers(),
            json={"generation": generation, "projectors": reports, "work_lease_token": current_work_lease.get()},
        )
        response.raise_for_status()


async def _project_source(source: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    reports = []
    for projector in ("mem0", "graphiti"):
        try:
            if mode == "stub":
                report = _stub_projection(projector, source)
            elif projector == "mem0":
                # Synchronous inference lives only in the owned child process.
                report = _mem0_project_sync(source)
            else:
                report = await _graphiti_project(source)
        except Exception as exc:
            report = {
                "projector": projector, "status": "failed", "projection_key": None,
                "metadata": {"backend": mode, "generative_extraction": False},
                "error": f"Projection failed ({type(exc).__name__})",
            }
        reports.append(report)
    return reports


async def _run_projection(source: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="kairo-memory-") as directory:
        path, output = Path(directory) / "source.json", Path(directory) / "result.json"
        encoded = json.dumps(source, default=str)
        if len(encoded.encode()) > 262144:
            raise RuntimeError("Memory source exceeds bounded projection input")
        path.write_text(encoded, encoding="utf-8")
        allowed = {"HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "PATH", "PYTHONPATH", "HOME", "LANG", "LC_ALL", "HF_HOME", "HF_HUB_CACHE",
                   "FASTEMBED_CACHE_PATH", "DATABASE_URL", "MEM0_DATABASE_URL", "NEO4J_URI",
                   "NEO4J_USER", "NEO4J_PASSWORD"}
        environment = {key: value for key, value in os.environ.items() if key in allowed}
        environment.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                            "TMPDIR": directory})
        returncode = await run_owned_process(
            sys.executable, "-m", "kairo_worker.memory_projection", str(path), str(output), mode,
            environment=environment, timeout=240,
        )
        if returncode != 0 or not output.is_file() or output.stat().st_size > 65536:
            raise RuntimeError("Memory projector failed or exceeded bounded result")
        reports = json.loads(output.read_text(encoding="utf-8"))
        if not isinstance(reports, list) or len(reports) != 2:
            raise RuntimeError("Memory projector returned invalid reports")
        return reports


async def _keep_alive(message_id: str) -> None:
    while True:
        if activity.in_activity():
            activity.heartbeat({"kind": "kairo.memory-projection", "source_id": message_id})
        await asyncio.sleep(5)


@activity.defn
async def perform_memory_projection(payload: dict[str, Any]) -> dict[str, Any]:
    return await run_admitted(payload, lambda: _perform_memory_projection(payload))


async def _perform_memory_projection(payload: dict[str, Any]) -> dict[str, Any]:
    task_input = payload.get("task_input") or {}
    message_id = str(task_input.get("source_id") or "")
    if not message_id:
        raise RuntimeError("memory.project requires source_id")
    generation = int(task_input.get("projection_generation") or 1)
    heartbeat = asyncio.create_task(_keep_alive(message_id))
    try:
        async with asyncio.timeout(280):  # Below the five-minute Temporal deadline.
            source = await _fetch_source(message_id)
            mode = memory_projector_mode()
            reports = await _run_projection(source, mode)
            await _report(message_id, generation, reports)
            if any(item["status"] == "failed" for item in reports):
                raise RuntimeError("Memory projection failed; see canonical projector status")
            return {
                "kind": "memory-projection", "title": f"Memory projection — {message_id}",
                "content": {
                    "source_type": "conversation_message", "source_id": message_id,
                    "source_version": int(source["source_version"]), "projection_generation": generation,
                    "projector_mode": mode,
                    "projectors": [{key: item[key] for key in ("projector", "projection_key", "metadata")}
                                   for item in reports],
                },
            }
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)


def main() -> None:
    import signal
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.alarm(270)
    source_path, result_path, mode = sys.argv[1:]
    source = json.loads(Path(source_path).read_text(encoding="utf-8"))
    reports = asyncio.run(_project_source(source, mode))
    Path(result_path).write_text(json.dumps(reports), encoding="utf-8")


if __name__ == "__main__":
    main()
