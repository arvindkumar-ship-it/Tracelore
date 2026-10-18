import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.common.db import create_pool
from backend.common.settings import get_settings

from .scorer import false_positive_rate
from .traffic.load_generator import run_traffic


async def measure(hours: float, seed: int, rate: float, output: Path) -> dict[str, Any]:
    settings = get_settings()
    start = datetime.now(UTC)
    traffic = await run_traffic(settings.demo_gateway_url, hours * 3600, seed, rate=rate)
    end = datetime.now(UTC)
    await asyncio.sleep(60)
    pool = await create_pool(settings)
    try:
        async with pool.acquire() as connection:
            times = await connection.fetch(
                "SELECT opened_at FROM incidents WHERE opened_at>=$1 AND opened_at<$2", start, end
            )
        result = false_positive_rate(start, end, [row["opened_at"] for row in times])
        result.update(
            {
                "started_at": start.isoformat(),
                "ended_at": end.isoformat(),
                "seed": seed,
                "requests": traffic.requests,
                "http_errors": traffic.errors,
                "passed": result["windows"] >= 24 and result["rate"] < 0.05,
            }
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Measure full one-hour normal windows; short runs cannot pass the 24-hour gate"
    )
    parser.add_argument("--hours", type=float, default=24)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument("--rate", type=float, default=20)
    parser.add_argument("--output", type=Path, default=Path("bench/reports/normal-24h.json"))
    arguments = parser.parse_args()
    if arguments.hours <= 0 or arguments.rate <= 0:
        parser.error("hours and rate must be positive")
    if not asyncio.run(measure(arguments.hours, arguments.seed, arguments.rate, arguments.output))[
        "passed"
    ]:
        raise SystemExit(1)
