from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class TimeoutChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["timeout"] = "timeout"
    caller: str = Field(min_length=1, max_length=100)
    callee: str = Field(min_length=1, max_length=100)
    new_timeout_ms: int = Field(gt=0, le=300_000)


class CacheHitRate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["cache_hit_rate"] = "cache_hit_rate"
    service: str = Field(min_length=1, max_length=100)
    route: str = Field(min_length=1, max_length=500)
    target_hit_rate: float = Field(ge=0, le=1)


class LatencyScale(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["latency_scale"] = "latency_scale"
    node: str = Field(min_length=1, max_length=200)
    factor: float = Field(ge=0.05, le=5)


Intervention = Annotated[TimeoutChange | CacheHitRate | LatencyScale, Field(discriminator="type")]
