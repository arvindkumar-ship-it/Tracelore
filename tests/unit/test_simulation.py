from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from tracelore.chain import HashChain
from tracelore.config import TraceloreConfig
from tracelore.event import build_event

from backend.ml.counterfactual.interventions import LatencyScale, TimeoutChange
from backend.ml.counterfactual.report import build_report
from backend.ml.counterfactual.timing import union_length

pytestmark = pytest.mark.unit


def trace(server=True):
    trace_id, root, client, callee = str(uuid4()), str(uuid4()), str(uuid4()), str(uuid4())
    config = TraceloreConfig(api_key="test", service="gateway", instance_id="simulation")
    chain = HashChain(config.stream_id)
    start = datetime(2026, 1, 1, tzinfo=UTC)

    def event(kind, attributes, span, parent, duration, status, offset=0):
        return chain.seal(
            build_event(
                config,
                kind,
                attributes,
                trace_id,
                span,
                parent,
                start + timedelta(milliseconds=offset),
                duration,
                status,
            )
        )

    events = [
        event(
            "http.client",
            {
                "method": "POST",
                "host": "payments",
                "downstream_service": "payments",
                "status_code": None,
                "timeout_ms": 1000,
            },
            client,
            root,
            1000,
            "error",
            10,
        ),
        event(
            "http.request",
            {"method": "POST", "route": "/checkout", "status_code": 500},
            root,
            None,
            1020,
            "error",
        ),
    ]
    if server:
        events.append(
            event(
                "http.request",
                {"method": "POST", "route": "/pay", "status_code": 200},
                callee,
                client,
                2000,
                "ok",
                15,
            )
        )
    return events


@pytest.mark.parametrize(
    ("intervals", "expected"),
    [([], 0), ([(0, 10), (5, 15)], 15), ([(0, 5), (5, 10)], 10), ([(0, 20), (5, 10)], 20)],
)
def test_union(intervals, expected):
    assert union_length(intervals) == expected


def test_timeout_server_evidence():
    report = build_report(
        trace(), TimeoutChange(caller="gateway", callee="payments", new_timeout_ms=2500)
    )
    assert report.original["error_rate"] == 1
    assert report.counterfactual["error_rate"] == 0
    assert report.unsimulatable_count == 0
    assert report.counterfactual["p95_ms"] == pytest.approx(2020)


def test_missing_server_unsimulatable():
    report = build_report(
        trace(False), TimeoutChange(caller="gateway", callee="payments", new_timeout_ms=2500)
    )
    assert report.unsimulatable_count == 1 and report.unsimulatable_percent == 100
    assert report.counterfactual["error_rate"] == 1


def test_simulation_determinism():
    events = trace()
    intervention = LatencyScale(node="svc:gateway", factor=0.5)
    assert (
        build_report(events, intervention).result_digest
        == build_report(list(reversed(events)), intervention).result_digest
    )
    assert build_report(events, intervention).mode == "simulated"
