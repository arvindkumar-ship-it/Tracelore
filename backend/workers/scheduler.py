import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any

from backend.common.metrics import JOB_FAILURES, JOB_SECONDS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    name: str
    interval_seconds: float
    run: Callable[[Any], Awaitable[Any]]


async def run_locked(pool: Any, job: Job) -> bool:
    async with pool.acquire() as connection:
        acquired = await connection.fetchval("SELECT pg_try_advisory_lock(hashtext($1))", job.name)
        if not acquired:
            return False
        try:
            with JOB_SECONDS.labels(job.name).time():
                await job.run(connection)
            return True
        finally:
            await connection.execute("SELECT pg_advisory_unlock(hashtext($1))", job.name)


class Scheduler:
    def __init__(self, pool: Any, jobs: list[Job]) -> None:
        self.pool, self.jobs = pool, jobs
        self.stop = asyncio.Event()

    async def run(self) -> None:
        tasks = [asyncio.create_task(self._loop(job), name=job.name) for job in self.jobs]
        await self.stop.wait()
        await asyncio.gather(*tasks)

    async def _loop(self, job: Job) -> None:
        while not self.stop.is_set():
            started = monotonic()
            try:
                await run_locked(self.pool, job)
            except Exception:
                JOB_FAILURES.labels(job.name).inc()
                logger.exception("worker_job_failed job=%s", job.name)
            delay = max(0.1, job.interval_seconds - (monotonic() - started))
            try:
                await asyncio.wait_for(self.stop.wait(), delay)
            except TimeoutError:
                continue
