import asyncio
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from backend.common.errors import ApiError, Code
from backend.ml.compression.tiered_repository import TieredRepository

from .interventions import Intervention
from .report import CounterfactualReport, build_report

router = APIRouter()


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: AwareDatetime
    end: AwareDatetime
    route: str | None = None


class SimulationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: UUID | None = None
    window: Window | None = None
    intervention: Intervention

    @model_validator(mode="after")
    def exactly_one_source(self) -> "SimulationInput":
        if (self.incident_id is None) == (self.window is None):
            raise ValueError("supply incident_id or window, exactly one")
        if self.window and self.window.end <= self.window.start:
            raise ValueError("window end must be after start")
        return self


@router.post("/counterfactual", response_model=CounterfactualReport)
async def counterfactual(body: SimulationInput, request: Request) -> CounterfactualReport:
    async with request.app.state.pool.acquire() as connection:
        window = body.window
        if body.incident_id:
            row = await connection.fetchrow("SELECT * FROM incidents WHERE id=$1", body.incident_id)
            if row is None:
                raise ApiError(Code.NOT_FOUND, "Incident not found", 404)
            window = Window(start=row["start_time"], end=row["updated_at"] + timedelta(seconds=30))
        if window is None:
            raise ApiError(Code.BAD_REQUEST, "Missing simulation window")
        repo = TieredRepository(connection, request.app.state.object_store)
        events = await repo.get_window(window.start, window.end)
        if len(events) > 10_000:
            raise ApiError(Code.TOO_LARGE, "Choose a narrower recorded window")
        events = await repo.get_traces_events(sorted({event["trace_id"] for event in events}))
        if len(events) > 10_000:
            raise ApiError(
                Code.TOO_LARGE, "Complete traces exceed 10,000 events; narrow the window"
            )
        if window.route:
            trace_ids = {
                event["trace_id"]
                for event in events
                if event["attributes"].get("route") == window.route
            }
            events = [event for event in events if event["trace_id"] in trace_ids]
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(build_report, events, body.intervention), timeout=5
        )
    except TimeoutError as error:
        raise ApiError(
            Code.TOO_LARGE, "Simulation exceeded five seconds; choose a smaller window"
        ) from error
