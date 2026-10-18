import asyncio
import logging
from pathlib import Path

import asyncpg

from backend.common.settings import get_settings

logger = logging.getLogger(__name__)
MIGRATIONS = Path(__file__).parent / "migrations"


async def migrate(connection: asyncpg.Connection) -> None:
    await connection.execute("SELECT pg_advisory_lock(17031703)")
    try:
        await connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version text PRIMARY KEY, applied_at timestamptz DEFAULT now())"
        )
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if await connection.fetchval(
                "SELECT 1 FROM schema_migrations WHERE version=$1", path.name
            ):
                continue
            async with connection.transaction():
                await connection.execute(path.read_text())
                await connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES($1)", path.name
                )
            logger.info("migration_applied version=%s", path.name)
    finally:
        await connection.execute("SELECT pg_advisory_unlock(17031703)")


async def main() -> None:
    connection = await asyncpg.connect(get_settings().owner_database_url.get_secret_value())
    try:
        await migrate(connection)
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
