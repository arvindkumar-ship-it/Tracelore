from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import expm1, log1p, sqrt
from statistics import median
from typing import Literal

import numpy as np

from .contracts import METRICS, MetricRange

MIN_SAMPLES = 20
MAD_SCALE = 1.4826
EPSILON = 1e-6


@dataclass(frozen=True)
class Bucket:
    service: str
    route: str
    bucket_start: datetime
    count: int
    errors: int
    p50_ms: float
    p95_ms: float
    p99_ms: float

    def metric(self, name: str) -> float:
        if name == "error_rate":
            return self.errors / max(self.count, 1)
        return float(getattr(self, name))


def transform(value: float, metric: str) -> float:
    return value if metric == "error_rate" else log1p(max(0, value))


def inverse(value: float, metric: str) -> float:
    return max(0, min(1, value)) if metric == "error_rate" else max(0, expm1(value))


def hour_of_week(at: datetime) -> int:
    at = at.astimezone(UTC)
    return at.weekday() * 24 + at.hour


def robust_range(
    buckets: list[Bucket], metric: str, source: Literal["slot", "hour", "global"], multiplier: float
) -> MetricRange:
    values = [transform(bucket.metric(metric), metric) for bucket in buckets]
    center = median(values)
    scale = max(
        MAD_SCALE * median(abs(value - center) for value in values), 0.05 * abs(center), EPSILON
    )
    if metric == "count":
        mean_count = sum(bucket.count for bucket in buckets) / len(buckets)
        scale = max(scale, sqrt(mean_count) / (mean_count + 1))
    low, high = center - multiplier * scale, center + multiplier * scale
    if metric == "error_rate":
        mean_count = sum(bucket.count for bucket in buckets) / len(buckets)
        high = max(
            float(np.quantile(values, 0.99)),
            center + 3 * sqrt(center * (1 - center) / max(mean_count, 1)),
            center + multiplier * scale,
        )
    return MetricRange(
        low=inverse(low, metric),
        expected=inverse(center, metric),
        high=inverse(high, metric),
        scale=scale,
        n=len(values),
        source=source,
    )


def fit_endpoint(buckets: list[Bucket], multiplier: float = 4) -> dict[int, dict[str, MetricRange]]:
    if not buckets or max(bucket.bucket_start for bucket in buckets) - min(
        bucket.bucket_start for bucket in buckets
    ) < timedelta(hours=24):
        return {}
    fitted: dict[int, dict[str, MetricRange]] = {slot: {} for slot in range(168)}
    for metric in METRICS:
        eligible = (
            [bucket for bucket in buckets if bucket.count > 0]
            if metric.startswith("p")
            else buckets
        )
        if not eligible:
            return {}
        for slot in range(168):
            selected, source = _select(eligible, slot)
            fitted[slot][metric] = robust_range(selected, metric, source, multiplier)
    return fitted


def _select(
    buckets: list[Bucket], slot: int
) -> tuple[list[Bucket], Literal["slot", "hour", "global"]]:
    selected = [bucket for bucket in buckets if hour_of_week(bucket.bucket_start) == slot]
    if len(selected) >= MIN_SAMPLES:
        return selected, "slot"
    selected = [
        bucket for bucket in buckets if bucket.bucket_start.astimezone(UTC).hour == slot % 24
    ]
    return (selected, "hour") if len(selected) >= MIN_SAMPLES else (buckets, "global")
