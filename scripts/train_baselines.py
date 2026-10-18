import asyncio
import logging
from datetime import UTC, datetime

from backend.common.db import create_pool
from backend.common.settings import get_settings
from backend.ml.anomaly.training import train_sequences
from backend.ml.baseline.aggregate import backfill
from backend.ml.baseline.store import train


async def main() -> None:
    settings = get_settings()
    pool = await create_pool(settings)
    try:
        async with pool.acquire() as connection:
            bounds = await connection.fetchrow(
                "SELECT min(ended_at) AS start,max(ended_at) AS finish FROM events"
            )
            if bounds is None or bounds["start"] is None:
                raise ValueError("ingest history before training")
            await backfill(connection, bounds["start"], bounds["finish"])
            await train(connection, datetime.now(UTC), settings.baseline_k)
            await train_sequences(connection, datetime.now(UTC))
    finally:
        await pool.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
