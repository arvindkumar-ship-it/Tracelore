import json
from typing import Any

import asyncpg

from .settings import Settings


async def initialize_connection(connection: asyncpg.Connection) -> None:
    await connection.execute("SET TIME ZONE 'UTC'")
    await connection.set_type_codec(
        "jsonb",
        schema="pg_catalog",
        format="binary",
        encoder=lambda value: b"\x01" + json.dumps(value).encode(),
        decoder=lambda value: json.loads(value[1:]),
    )


async def create_pool(settings: Settings, *, owner: bool = False) -> Any:
    url = settings.owner_database_url if owner else settings.database_url
    return await asyncpg.create_pool(
        url.get_secret_value(),
        min_size=4,
        max_size=20,
        init=initialize_connection,
        command_timeout=60,
    )
