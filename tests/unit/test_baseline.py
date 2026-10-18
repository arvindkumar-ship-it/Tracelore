from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from backend.ml.anomaly.residuals import to_residual
from backend.ml.baseline.stats_model import Bucket, fit_endpoint, hour_of_week, robust_range

pytestmark = pytest.mark.unit


def test_mad_guard_and_transform():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    buckets = [
        Bucket("svc", "/x", start + timedelta(hours=index), 100, 0, 10, 20, 30)
        for index in range(60)
    ]
    result = fit_endpoint(buckets)
    assert result
    metric = result[0]["p95_ms"]
    assert metric.scale > 0 and metric.low < 20 < metric.high
    assert abs(to_residual(20, metric.expected, metric.scale, "p95_ms")) < 1e-9


def test_warming_up():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    assert fit_endpoint([Bucket("svc", "/x", start, 100, 0, 10, 20, 30)]) == {}


def test_hour_fallback_and_coverage():
    start = datetime(2026, 1, 5, tzinfo=UTC)
    random = np.random.default_rng(19)

    def bucket(index):
        at = start + timedelta(hours=index)
        duration = 30 + 20 * np.sin(at.hour / 24 * 2 * np.pi) + float(random.normal(0, 1))
        return Bucket("svc", "/x", at, 1000, 0, duration, duration * 1.5, duration * 2)

    train = [bucket(index) for index in range(28 * 24)]
    model = fit_endpoint(train)
    heldout = [bucket(index) for index in range(28 * 24, 31 * 24)]
    coverage = sum(
        model[hour_of_week(item.bucket_start)]["p95_ms"].low
        <= item.p95_ms
        <= model[hour_of_week(item.bucket_start)]["p95_ms"].high
        for item in heldout
    ) / len(heldout)
    assert coverage >= 0.95
    assert model[0]["p95_ms"].source == "hour"


def test_error_binomial_floor():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    metric = robust_range(
        [Bucket("s", "/x", start, 10, 1, 1, 2, 3)] * 30, "error_rate", "global", 4
    )
    assert metric.high > 0.3


def test_empty_latency_buckets_do_not_train_a_zero_latency_baseline():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    buckets = [
        Bucket(
            "svc",
            "/sparse",
            start + timedelta(minutes=index),
            1 if index % 4 == 0 else 0,
            0,
            10 if index % 4 == 0 else 0,
            20 if index % 4 == 0 else 0,
            30 if index % 4 == 0 else 0,
        )
        for index in range(1500)
    ]
    model = fit_endpoint(buckets)
    assert model[0]["p95_ms"].expected == pytest.approx(20)
    assert model[0]["count"].high >= 1
