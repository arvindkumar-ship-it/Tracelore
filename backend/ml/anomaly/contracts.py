from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Signal(BaseModel):
    id: str
    kind: Literal["metric", "sequence"]
    service: str
    route: str
    detected_at: datetime
    estimated_start: datetime
    confidence: float = Field(ge=0, le=1)
    magnitude: float = 0
    incident_grade: bool = True
    model_votes: list[str] = Field(default_factory=lambda: ["ngram"])
    event_id: str | None = None
    trace_id: str | None = None
    metric: str | None = None
    direction: Literal["up", "down"] = "up"
    surprise: float | None = None
    anomaly_kind: Literal["unexpected", "missing_end"] | None = None
    baseline_high: float | None = None
