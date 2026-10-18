import asyncio
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter

import httpx


@dataclass(frozen=True)
class TrafficResult:
    requests: int
    errors: int
    started_at: str
    ended_at: str
    latencies_ms: list[float]


async def run_traffic(
    url: str,
    duration: float,
    seed: int,
    concurrency: int = 20,
    rate: float = 20,
    profile: str = "normal",
) -> TrafficResult:
    randomizer = random.Random(seed)
    rate *= {"marketing": 2, "weekend": 0.65, "batch": 1.25}.get(profile, 1)
    deadline = perf_counter() + duration
    counters = {"requests": 0, "errors": 0}
    latencies = []
    started_at = datetime.now(UTC).isoformat()
    async with httpx.AsyncClient(timeout=12, trust_env=False) as http:

        async def worker(index: int) -> None:
            local = random.Random(randomizer.getrandbits(64))
            due = perf_counter() + index / max(rate, 1)
            while perf_counter() < deadline:
                await asyncio.sleep(max(0, due - perf_counter()))
                started = perf_counter()
                await _request(http, url, local, counters, profile)
                latencies.append((perf_counter() - started) * 1000)
                hour = datetime.now(UTC).hour
                seasonality = 1 + 0.2 * math.sin(hour / 24 * 2 * math.pi)
                due = max(due + concurrency / max(rate * seasonality, 1), perf_counter())

        await asyncio.gather(*(worker(index) for index in range(concurrency)))
    return TrafficResult(
        counters["requests"],
        counters["errors"],
        started_at,
        datetime.now(UTC).isoformat(),
        latencies,
    )


async def _request(
    http: httpx.AsyncClient,
    url: str,
    randomizer: random.Random,
    counters: dict[str, int],
    profile: str,
) -> None:
    try:
        if profile == "health_flood":
            response = await http.get(url + "/healthz")
        elif profile == "batch" or randomizer.random() < 0.25:
            response = await http.get(url + "/cart")
        else:
            response = await http.post(
                url + "/checkout",
                json={
                    "item_id": 13 if randomizer.random() < 0.2 else randomizer.randint(1, 10),
                    "amount": 100,
                },
            )
        counters["errors"] += int(response.is_error)
    except httpx.TransportError:
        counters["errors"] += 1
    counters["requests"] += 1
