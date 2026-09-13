"""Cancellation-safe ownership of a bounded process group."""
import asyncio
import os
import signal


async def run_owned_process(*command: str, environment: dict[str, str], timeout: float) -> int:
    spawning = asyncio.create_task(asyncio.create_subprocess_exec(
        *command, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL, env=environment, start_new_session=os.name == "posix",
    ))
    process = None
    try:
        process = await asyncio.shield(spawning)
        async with asyncio.timeout(timeout):
            await process.wait()
    finally:
        if process is None:
            process = await spawning
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            elif process.returncode is None:
                process.kill()
        except ProcessLookupError:
            pass
        await process.wait()
    return process.returncode
