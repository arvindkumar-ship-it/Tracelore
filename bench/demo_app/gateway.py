import asyncio
from typing import Any

import httpx
from tracelore.canonical import hash_payload


async def checkout(state: Any, payload: dict[str, Any]) -> dict[str, Any]:
    faults = state.faults
    await faults.before_request(payload)
    if faults.enabled("large_payload"):
        await asyncio.to_thread(hash_payload, b"x" * faults.params.get("bytes", 1000000))
    item = payload.get("item_id", 1)
    if faults.enabled("wrong_order"):
        await _payment(state, payload)
    response = await state.http.get(state.settings.demo_inventory_url + f"/stock/{item}")
    response.raise_for_status()
    if not faults.enabled("skip_payment"):
        attempts = (
            faults.params.get("attempts", 5)
            if faults.flag in ("retry_storm", "no_breaker")
            else 2
            if faults.enabled("duplicate_payment")
            else 1
        )
        failure = None
        for _ in range(attempts):
            try:
                await _payment(state, payload)
            except (httpx.TransportError, httpx.HTTPStatusError) as error:
                failure = error
                if faults.flag not in ("retry_storm", "no_breaker"):
                    raise
        if failure is not None:
            raise failure
    if faults.enabled("queue_backlog"):
        for _ in range(faults.params.get("messages", 25)):
            with state.tracelore.span(
                "queue.publish",
                lambda: {"queue": "orders", "message_hash": hash_payload(str(item))},
            ):
                await state.redis.lpush("orders", str(item))
    if faults.enabled("dependency_loop"):
        await state.http.get(state.settings.demo_inventory_url + "/loop")
    return {"status": "accepted", "item_id": item}


async def _payment(state: Any, payload: dict[str, Any]) -> None:
    timeout = (
        state.faults.params.get("timeout_ms", 1) / 1000 if state.faults.enabled("timeout") else 5
    )
    response = await state.http.post(
        state.settings.demo_payments_url + "/pay",
        json={"amount": payload.get("amount", 100)},
        timeout=timeout,
    )
    response.raise_for_status()
    response.json()
