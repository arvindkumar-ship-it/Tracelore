import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

from backend.common.db import create_pool
from backend.common.settings import get_settings
from backend.ml.baseline.export_onnx import export_model
from backend.ml.baseline.paths import endpoint_model_dir
from backend.ml.baseline.store import NORMAL_BUCKETS
from backend.ml.baseline.train import train_forecaster


def longest_clean_series(rows: list[Any]) -> np.ndarray:
    blocks: list[list[Any]] = [[]]
    for row in rows:
        if blocks[-1] and row["bucket_start"] - blocks[-1][-1]["bucket_start"] != timedelta(
            minutes=1
        ):
            blocks.append([])
        blocks[-1].append(row)
    selected = max(blocks, key=len)
    if len(selected) < 7500:
        raise ValueError(
            "need at least 7,500 consecutive clean one-minute buckets for a time-based split"
        )
    return np.array(
        [
            [
                row["count"],
                row["errors"] / max(row["count"], 1),
                row["p50_ms"],
                row["p95_ms"],
                row["p99_ms"],
            ]
            for row in selected
        ],
        dtype=np.float32,
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", required=True)
    parser.add_argument("--route", required=True)
    args = parser.parse_args()
    settings = get_settings()
    pool = await create_pool(settings)
    try:
        at = datetime.now(UTC)
        async with pool.acquire() as connection:
            rows = await connection.fetch(NORMAL_BUCKETS, at - timedelta(days=28), at)
        rows = [
            row for row in rows if row["service"] == args.service and row["route"] == args.route
        ]
        values = longest_clean_series(rows)
        await asyncio.to_thread(
            train_forecaster,
            values,
            endpoint_model_dir(settings.model_dir, args.service, args.route),
        )
        await asyncio.to_thread(
            export_model, endpoint_model_dir(settings.model_dir, args.service, args.route)
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
