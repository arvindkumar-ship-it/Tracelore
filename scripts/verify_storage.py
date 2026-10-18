import argparse
import asyncio
from datetime import datetime

from backend.common.db import create_pool
from backend.common.settings import get_settings
from backend.ledger.verify import verify_stream
from backend.ml.compression.object_store import ObjectStore
from backend.ml.compression.tiered_repository import TieredRepository
from backend.replay.engine import replay_until
from backend.replay.snapshots import Snapshots


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--until", type=datetime.fromisoformat, required=True)
    args = parser.parse_args()
    if args.until.tzinfo is None:
        parser.error("include a UTC offset or Z")
    settings = get_settings()
    pool = await create_pool(settings)
    try:
        async with pool.acquire() as connection:
            streams = await connection.fetch("SELECT DISTINCT stream_id FROM events")
            for row in streams:
                findings = await verify_stream(connection, row["stream_id"])
                if any(finding.kind == "break" for finding in findings):
                    raise ValueError("hash-chain break")
            repo = TieredRepository(connection, ObjectStore(settings))
            zero = await replay_until(repo, None, args.until)
            cached = await replay_until(repo, Snapshots(connection), args.until)
            if zero.digest() != cached.digest():
                raise ValueError("replay digest mismatch")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
