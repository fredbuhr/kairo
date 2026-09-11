"""Acquire briefly or return to a Temporal timer; never wait in an activity slot."""
import asyncio
import contextvars
import logging

import httpx
from temporalio import activity

from .config import settings

logger = logging.getLogger(__name__)
current_work_lease = contextvars.ContextVar("work_lease", default=None)


async def _call(action: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{settings.nevolium_core_url.rstrip('/')}/internal/v1/work-capacity/{action}",
            headers={"X-Nevolium-Internal-Token": settings.nevolium_internal_token}, json=payload,
        )
        if action == "acquire" and response.status_code == 429:
            return {"admitted": False}
        response.raise_for_status()
        return response.json()


async def _renew(lease: dict) -> None:
    while True:
        await asyncio.sleep(15)
        await _call("renew", lease)


async def run_admitted(payload: dict, operation):
    info = activity.info()
    holder = f"{info.workflow_run_id}:{info.activity_id}:{info.attempt}"
    admission = await _call("acquire", {"task_id": payload["task_id"], "holder": holder})
    if admission.get("completed_result"):
        return admission["completed_result"]
    if not admission.get("admitted"):
        return {"waiting_for_capacity": True}
    lease = {"task_id": payload["task_id"], "lease_token": admission["lease_token"]}
    context_token = current_work_lease.set(admission["lease_token"])
    work = asyncio.create_task(operation())
    renewal = asyncio.create_task(_renew(lease))
    result = None
    try:
        done, _ = await asyncio.wait({work, renewal}, return_when=asyncio.FIRST_COMPLETED)
        if renewal in done:
            await renewal  # Failed renewal cancels/reaps work before giving the slot back.
        result = await work
        await _call("release", {**lease, "completed": True, "result": result})
        return result
    finally:
        work.cancel()
        renewal.cancel()
        await asyncio.gather(work, renewal, return_exceptions=True)
        current_work_lease.reset(context_token)
        if result is None:
            try:
                await asyncio.shield(_call("release", lease))
            except Exception:
                logger.warning("Work lease will expire after interrupted cleanup", exc_info=True)
