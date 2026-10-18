from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import AwareDatetime

from backend.api.contracts import SpanColumns, SpanDictionary, StateView, TraceView
from backend.common.errors import ApiError, Code
from backend.common.time import microseconds
from backend.ml.compression.tiered_repository import TieredRepository

from .engine import replay_trace, replay_until, state_at_event
from .reducers import ReplayError
from .snapshots import SNAPSHOT_LOCK, Snapshots

router = APIRouter()


@router.get("/replay/state", response_model=StateView)
async def state(request: Request, at: AwareDatetime) -> StateView:
    async with request.app.state.pool.acquire() as connection, connection.transaction():
        await connection.execute("LOCK TABLE events IN ACCESS SHARE MODE")
        await connection.execute("SELECT pg_advisory_xact_lock_shared($1)", SNAPSHOT_LOCK)
        repo = TieredRepository(connection, request.app.state.object_store)
        observed = await replay_until(repo, Snapshots(connection), at)
    return StateView(digest=observed.digest(), state=observed.summary())


@router.get("/replay/trace/{trace_id}", response_model=TraceView)
async def trace(trace_id: UUID, request: Request) -> TraceView:
    async with request.app.state.pool.acquire() as connection:
        result = await replay_trace(
            TieredRepository(connection, request.app.state.object_store), str(trace_id)
        )
    if not result.events:
        raise ApiError(Code.NOT_FOUND, "Trace not found", 404)
    services = sorted({event["service"] for event in result.events})
    types = sorted({event["type"] for event in result.events})
    service_indices, type_indices = (
        {value: index for index, value in enumerate(services)},
        {value: index for index, value in enumerate(types)},
    )
    spans = SpanColumns(
        id=[],
        event_id=[],
        parent=[],
        start_us=[],
        dur_us=[],
        service_idx=[],
        type_idx=[],
        status=[],
    )
    for event in result.events:
        spans.id.append(event["span_id"])
        spans.event_id.append(event["event_id"])
        spans.parent.append(event["parent_span_id"])
        spans.start_us.append(microseconds(event["timestamp"]))
        spans.dur_us.append(round(event["duration_ms"] * 1000))
        spans.service_idx.append(service_indices[event["service"]])
        spans.type_idx.append(type_indices[event["type"]])
        spans.status.append(event["status"])
    return TraceView(
        trace_id=trace_id,
        dict=SpanDictionary(services=services, types=types),
        spans=spans,
        digest=result.final_state.digest(),
    )


@router.get("/replay/trace/{trace_id}/state", response_model=StateView)
async def trace_state(trace_id: UUID, event_id: UUID, request: Request) -> StateView:
    try:
        async with request.app.state.pool.acquire() as connection:
            observed = await state_at_event(
                TieredRepository(connection, request.app.state.object_store),
                str(trace_id),
                str(event_id),
            )
    except ReplayError as error:
        raise ApiError(Code.NOT_FOUND, str(error), 404) from error
    return StateView(digest=observed.digest(), state=observed.summary())
