import asyncio

from tracelore.canonical import hash_payload

from backend.common.db import create_pool
from backend.common.settings import get_settings


async def main() -> None:
    settings = get_settings()
    key = settings.demo_ingest_key.get_secret_value()
    if not key:
        raise ValueError("DEMO_INGEST_KEY is required for first-run registration")
    pool = await create_pool(settings, owner=True)
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                (
                    "INSERT INTO api_keys(key_hash,name) VALUES($1,'Local demo services') ON "
                    "CONFLICT DO NOTHING"
                ),
                hash_payload(key),
            )
    finally:
        await pool.close()
    from scripts.create_topics import main as create_topics

    await create_topics()


if __name__ == "__main__":
    asyncio.run(main())
