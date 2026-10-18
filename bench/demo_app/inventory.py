import asyncio
from typing import Any

from fastapi import HTTPException
from tracelore.canonical import hash_payload
from tracelore.integrations.sql import query_attributes


async def inventory(state: Any, item_id: int) -> dict[str, Any]:
    faults, client = state.faults, state.tracelore
    await faults.before_request({"item_id": item_id})
    key = f"item:{'v2:' if faults.enabled('cache_version') else ''}{item_id}"
    skip = faults.flag in ("cache_miss", "cache_ttl_zero", "cache_db_overload", "skip_cache")
    if faults.enabled("redis_down"):
        with client.span("cache.get", lambda: {"key_hash": hash_payload(key), "hit": False}):
            raise ConnectionError("Injected Redis unavailability")
    if faults.enabled("redis_slow"):
        with client.span("cache.get", lambda: {"key_hash": hash_payload(key), "hit": False}):
            await asyncio.sleep(faults.params.get("delay_ms", 500) / 1000)
    if skip and not faults.enabled("skip_cache"):
        await state.redis.delete(key)
    cached = None if faults.enabled("skip_cache") else await state.redis.get(key)
    if cached is not None:
        return {"item_id": item_id, "stock": int(cached), "cache": "hit"}
    if faults.enabled("db_refused"):
        with client.span("db.query", lambda: query_attributes("select stock from inventory")):
            raise ConnectionError("Injected database connection failure")
    if faults.enabled("small_pool"):
        with client.span("db.query", lambda: query_attributes("select stock from inventory")):
            async with faults.pool_gate:
                await asyncio.sleep(faults.params.get("delay_ms", 300) / 1000)
                row = await _query(state, item_id)
    else:
        row = await _query(state, item_id)
    if row is None:
        raise HTTPException(404, "Item not found")
    if not faults.enabled("cache_ttl_zero"):
        await state.redis.set(key, row["stock"], ex=60)
    return {"item_id": item_id, "stock": row["stock"], "cache": "miss"}


async def _query(state: Any, item_id: int) -> Any:
    fault = state.faults
    if fault.flag == "connection_leak":
        with state.tracelore.span(
            "db.query", lambda: query_attributes("select stock from inventory")
        ):
            return await _database_call(state, item_id)
    return await _database_call(state, item_id)


async def _database_call(state: Any, item_id: int) -> Any:
    fault = state.faults
    if fault.enabled("connection_leak") and len(fault.leases) < 18:
        fault.leases.append(await state.pool.acquire(timeout=2))
    async with state.pool.acquire(timeout=2) as connection:
        if fault.flag in ("slow_query", "shared_db", "cache_db_overload"):
            return await connection.fetchrow(
                "SELECT stock,pg_sleep($1) FROM inventory WHERE item_id=$2",
                fault.params.get("delay_ms", 1000) / 1000,
                item_id,
            )
        if fault.enabled("lock"):
            async with connection.transaction():
                await connection.execute("SELECT pg_advisory_xact_lock(424242)")
                return await connection.fetchrow(
                    "SELECT stock,pg_sleep($1) FROM inventory WHERE item_id=$2",
                    fault.params.get("delay_ms", 1000) / 1000,
                    item_id,
                )
        for _ in range(fault.params.get("queries", 50) if fault.enabled("n_plus_one") else 1):
            row = await connection.fetchrow("SELECT stock FROM inventory WHERE item_id=$1", item_id)
        return row
