from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

METRICS = ("count", "error_rate", "p50_ms", "p95_ms", "p99_ms")


class MetricRange(BaseModel):
    low: float
    expected: float
    high: float
    scale: float = Field(gt=0)
    n: int
    source: Literal["slot", "hour", "global"]


class BaselineRange(BaseModel):
    service: str
    route: str
    at: datetime
    status: Literal["ready", "warming_up"]
    model: Literal["stats", "forecaster"] = "stats"
    version: int = 0
    metrics: dict[str, MetricRange] = Field(default_factory=dict)
