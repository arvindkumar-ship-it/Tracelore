import asyncio
import hashlib
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from random import Random
from typing import Any

from fastapi import HTTPException


@dataclass
class FaultState:
    service: str = "gateway"
    flag: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    requests: int = 0
    random: Random = field(default_factory=lambda: Random(19))
    leases: list[Any] = field(default_factory=list)
    pool_gate: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(2))

    def enabled(self, flag: str) -> bool:
        return self.flag == flag

    async def reset(self, flag: str, params: dict[str, Any], seed: int, pool: Any) -> None:
        for connection in self.leases:
            await pool.release(connection)
        self.leases.clear()
        self.flag, self.params, self.requests, self.random = flag, params, 0, Random(seed)

    async def before_request(self, payload: dict[str, Any]) -> None:
        self.requests += 1
        at = datetime.now(UTC)
        base = {"inventory": 30, "payments": 22}.get(self.service, 0)
        seasonal = (1 + 0.18 * math.sin(at.hour / 24 * 2 * math.pi)) * (
            0.9 if at.weekday() >= 5 else 1
        )
        if base:
            await asyncio.sleep(max(0, self.random.gauss(base * seasonal, 1)) / 1000)
        if self.flag in ("latency", "tail", "ramp", "payload_slow", "hot_key"):
            delay = self.params.get("delay_ms", 0)
            if self.flag == "tail" and self.random.random() > self.params.get("probability", 0.01):
                delay = 0
            if self.flag == "ramp":
                delay = min(10000, self.requests * self.params.get("per_request_ms", 10))
            if self.flag == "payload_slow" and payload.get("item_id") != 13:
                delay = 0
            await asyncio.sleep(delay / 1000)
        if self.flag == "http_error" and self.random.random() < self.params.get("probability", 1):
            raise HTTPException(int(self.params.get("status", 500)), "Injected HTTP fault")
        if self.flag in ("cpu", "threadpool"):
            jobs = self.params.get("jobs", 1)
            await asyncio.gather(
                *(
                    asyncio.to_thread(_burn, self.params.get("iterations", 10000))
                    for _ in range(jobs)
                )
            )
        if self.flag == "null_key":
            raise KeyError("Injected null inventory key")
        if self.flag == "bad_deploy":
            raise HTTPException(500, "Injected route deployment fault")


def _burn(iterations: int) -> bytes:
    value = b"tracelore-benchmark"
    for _ in range(iterations):
        value = hashlib.sha256(value).digest()
    return value
