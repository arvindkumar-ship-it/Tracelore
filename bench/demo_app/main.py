import asyncio
import hmac
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from tracelore import Tracelore, TraceloreConfig
from tracelore.canonical import hash_payload
from tracelore.integrations.asyncpg_conn import InstrumentedConnection
from tracelore.integrations.fastapi import TraceloreMiddleware
from tracelore.integrations.httpx_client import TraceloreAsyncTransport
from tracelore.integrations.redis_cache import InstrumentedRedis

from backend.common.settings import get_settings

from .faults import FaultState
from .gateway import checkout
from .inventory import inventory


class FaultInput(BaseModel):
    enabled: bool
    flag: str
    params: dict[str, Any] = Field(default_factory=dict)
    seed: int = 19


@asynccontextmanager
async def lifespan(application: FastAPI) -> Any:
    state = application.state
    settings = state.settings
    state.tracelore.start()

    async def initialize(connection: Any) -> None:
        connection.tracelore = state.tracelore

    state.pool = await asyncpg.create_pool(
        settings.database_url.get_secret_value(),
        min_size=2,
        max_size=20,
        connection_class=InstrumentedConnection,
        init=initialize,
    )
    state.redis = InstrumentedRedis.from_url(settings.redis_url)
    state.redis.tracelore = state.tracelore
    state.http = httpx.AsyncClient(transport=TraceloreAsyncTransport(state.tracelore), timeout=5)
    state.faults = FaultState(service=settings.demo_service)
    try:
        yield
    finally:
        await state.faults.reset("", {}, 19, state.pool)
        await state.http.aclose()
        await state.redis.aclose()
        await state.pool.close()
        await asyncio.to_thread(state.tracelore.shutdown)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=f"Tracelore demo {settings.demo_service}", lifespan=lifespan)
    application.state.settings = settings
    application.state.tracelore = Tracelore(
        TraceloreConfig(
            api_key=settings.demo_ingest_key.get_secret_value(),
            service=settings.demo_service,
            endpoint=settings.ingest_endpoint,
            service_map={"inventory": "inventory", "payments": "payments", "localhost": "payments"},
            skip_routes=("/healthz", "/metrics", "/admin/fault"),
        )
    )
    application.add_middleware(TraceloreMiddleware, client=application.state.tracelore)
    application.post("/admin/fault")(fault)
    application.get("/healthz")(health)
    application.post("/checkout")(checkout_route)
    application.get("/cart")(cart_route)
    application.get("/stock/{item_id}")(stock_route)
    application.post("/pay")(payment_route)
    application.get("/loop")(loop_route)
    return application


async def fault(body: FaultInput, request: Request) -> dict[str, bool]:
    expected = "Bearer " + request.app.state.settings.demo_token.get_secret_value()
    if not hmac.compare_digest(
        request.headers.get("authorization", "").encode(), expected.encode()
    ):
        raise HTTPException(401, "Invalid fault-control token")
    await request.app.state.faults.reset(
        body.flag if body.enabled else "", body.params, body.seed, request.app.state.pool
    )
    return {"enabled": body.enabled}


async def health() -> dict[str, str]:
    return {"status": "ok"}


async def checkout_route(request: Request) -> dict[str, Any]:
    return await checkout(request.app.state, await request.json())


async def cart_route(request: Request) -> dict[str, Any]:
    result = await request.app.state.http.get(
        request.app.state.settings.demo_inventory_url + "/stock/1"
    )
    result.raise_for_status()
    return dict(result.json())


async def stock_route(item_id: int, request: Request) -> dict[str, Any]:
    if request.app.state.faults.enabled("poison") and item_id == 13:
        with request.app.state.tracelore.span(
            "queue.publish", lambda: {"queue": "orders", "message_hash": hash_payload("poison")}
        ):
            raise ValueError("Injected poison message")
    return await inventory(request.app.state, item_id)


async def payment_route(request: Request) -> Any:
    await request.app.state.faults.before_request(await request.json())
    if request.app.state.faults.enabled("bad_json"):
        return Response("invalid-json", media_type="application/json")
    return {"paid": True}


async def loop_route(request: Request) -> dict[str, bool]:
    response = await request.app.state.http.get(
        request.app.state.settings.demo_gateway_url + "/cart"
    )
    return {"loop_completed": response.is_success}


app = create_app()
