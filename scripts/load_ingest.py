import argparse
import asyncio
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
import numpy as np
from tracelore.canonical import canonical_json
from tracelore.chain import HashChain
from tracelore.config import TraceloreConfig
from tracelore.event import build_event

from backend.common.settings import get_settings


async def run(seconds: int, events_per_second: int, output: Path) -> dict:
    settings = get_settings()
    config = TraceloreConfig(
        api_key=settings.demo_ingest_key.get_secret_value(), service="load-ingest"
    )
    chain = HashChain(config.stream_id)
    semaphore = asyncio.Semaphore(16)
    latencies = []
    results = []
    started = perf_counter()
    tasks = []
    batches = seconds * events_per_second // 1000
    async with httpx.AsyncClient(timeout=30, trust_env=False) as http:
        for index in range(batches):
            await asyncio.sleep(max(0, started + index * 1000 / events_per_second - perf_counter()))
            events = [
                chain.seal(
                    build_event(
                        config,
                        "http.request",
                        {"method": "GET", "route": "/load", "status_code": 200},
                        str(uuid4()),
                        str(uuid4()),
                        None,
                        datetime.now(UTC),
                        1,
                        "ok",
                    )
                )
                for _ in range(1000)
            ]
            tasks.append(
                asyncio.create_task(
                    _send(
                        http,
                        semaphore,
                        settings.ingest_endpoint,
                        config.api_key,
                        events,
                        latencies,
                        results,
                    )
                )
            )
        await asyncio.gather(*tasks)
    elapsed = perf_counter() - started
    report = {
        "offered": batches * 1000,
        "accepted": sum(result["accepted"] for result in results),
        "duplicates": sum(result["duplicates"] for result in results),
        "rejected": sum(len(result["rejected"]) for result in results),
        "elapsed_seconds": elapsed,
        "accepted_per_second": sum(result["accepted"] for result in results) / elapsed,
        "p99_batch_ms": float(np.quantile(latencies, 0.99)) * 1000,
        "stream_id": config.stream_id,
    }
    report["passed"] = (
        report["accepted"] == report["offered"]
        and report["accepted_per_second"] >= events_per_second * 0.99
        and report["p99_batch_ms"] < 300
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    return report


async def _send(
    http: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    endpoint: str,
    key: str,
    events: list[dict[str, Any]],
    latencies: list[float],
    results: list[dict[str, Any]],
) -> None:
    async with semaphore:
        started = perf_counter()
        response = await http.post(
            endpoint,
            content=gzip.compress(canonical_json({"batch_id": str(uuid4()), "events": events})),
            headers={
                "x-api-key": key,
                "content-encoding": "gzip",
                "content-type": "application/json",
            },
        )
        response.raise_for_status()
        latencies.append(perf_counter() - started)
        results.append(response.json())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--events-per-second", type=int, default=10000)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/ingest.json"))
    arguments = parser.parse_args()
    result = asyncio.run(run(arguments.seconds, arguments.events_per_second, arguments.output))
    if not result["passed"]:
        raise SystemExit(1)
