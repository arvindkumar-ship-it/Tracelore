from typing import Literal

from fastapi import APIRouter, Request
from pydantic import AwareDatetime, BaseModel

from .contracts import BaselineRange

router = APIRouter()


class PredictInput(BaseModel):
    service: str
    route: str
    at: AwareDatetime
    model: Literal["stats", "forecaster"] = "stats"


@router.post("/predict/baseline", response_model=BaselineRange)
async def predict_baseline(body: PredictInput, request: Request) -> BaselineRange:
    if body.model == "forecaster":
        from .inference import predict_forecaster

        async with request.app.state.pool.acquire() as connection:
            return await predict_forecaster(connection, body, request.app.state.settings.model_dir)
    from .cache import predict_cached

    async with request.app.state.pool.acquire() as connection:
        return await predict_cached(
            connection, request.app.state.redis, body.service, body.route, body.at
        )
