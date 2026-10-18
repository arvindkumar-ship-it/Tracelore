from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from tracelore.chain import HashChain
from tracelore.config import TraceloreConfig
from tracelore.event import build_event


@pytest.fixture
def event_factory():
    config = TraceloreConfig(api_key="test-key", service="gateway", instance_id=str(uuid4()))
    chain = HashChain(config.stream_id)
    start = datetime(2026, 1, 1, tzinfo=UTC)

    def build(event_type="http.request", attributes=None, **overrides: Any):
        attributes = attributes or {"method": "GET", "route": "/orders/{id}", "status_code": 200}
        arguments = (
            dict(
                trace_id=str(uuid4()),
                span_id=str(uuid4()),
                parent_span_id=None,
                started_at=start + timedelta(seconds=chain._sequence),
                duration_ms=10.0,
                status="ok",
            )
            | overrides
        )
        return chain.seal(build_event(config, event_type, attributes, **arguments))

    return build
