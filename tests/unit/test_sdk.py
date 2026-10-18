import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from tracelore import Tracelore, TraceloreConfig
from tracelore.buffer import EventBuffer
from tracelore.canonical import canonical_json, compute_event_hash, hash_payload
from tracelore.chain import HashChain
from tracelore.context import current_ids, parse_header, span_scope
from tracelore.integrations.fastapi import TraceloreMiddleware
from tracelore.integrations.sql import normalize_sql
from tracelore.spool import Spool
from tracelore.transport import SendResult, Transport

pytestmark = pytest.mark.unit


def test_canonical():
    assert canonical_json({"b": 1, "a": {"z": "हिन्दी"}}) == canonical_json(
        {"a": {"z": "हिन्दी"}, "b": 1}
    )
    with pytest.raises(ValueError):
        canonical_json({"value": float("nan")})
    assert hash_payload(None) == hash_payload(b"")


def test_chain_threads(event_factory):
    chain = HashChain("gateway:threads")
    events = [event_factory() for _ in range(1000)]
    with ThreadPoolExecutor(8) as executor:
        sealed = sorted(executor.map(chain.seal, events), key=lambda event: event["sequence"])
    assert [event["sequence"] for event in sealed] == list(range(1, 1001))
    assert all(
        event["prev_event_hash"] == previous["event_hash"]
        for previous, event in zip(sealed, sealed[1:], strict=False)
    )
    assert all(compute_event_hash(event) == event["event_hash"] for event in sealed)


def test_context_reset():
    trace, span = str(uuid4()), str(uuid4())
    with span_scope(trace, span):
        assert current_ids() == (trace, span)
        assert parse_header(f"{trace}:{span}") == (trace, span)
    assert current_ids() == (None, None)
    assert parse_header("invalid") is None


def test_buffer(event_factory):
    buffer = EventBuffer(1)
    assert buffer.put(event_factory())
    assert not buffer.put(event_factory())
    assert buffer.dropped == 1
    assert len(buffer.drain(20, 0)) == 1


def test_spool_truncated_and_commit(tmp_path, event_factory):
    spool = Spool(tmp_path, 1)
    event = event_factory()
    spool.append([event])
    path = next(tmp_path.glob("*.jsonl"))
    with path.open("ab") as file:
        file.write(b"{truncated")
    batches = list(spool.iter_batches(10))
    assert [item for _, events in batches for item in events] == [event]
    spool.commit(batches[0][0])
    assert not list(tmp_path.glob("spool-*"))


def test_spool_cap(tmp_path, event_factory):
    spool = Spool(tmp_path, 0.0001)
    spool.append([event_factory()])
    assert spool.dropped == 1


def test_transport(tmp_path, event_factory):
    config = TraceloreConfig(api_key="test", service="test", spool_dir=tmp_path)
    transport = Transport(
        config,
        http=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500))),
    )
    assert transport.send([event_factory()], str(uuid4())) == SendResult.RETRYABLE
    transport.close()


def test_partial_rejection(tmp_path, event_factory):
    event = event_factory()
    config = TraceloreConfig(api_key="test", service="test", spool_dir=tmp_path)
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "accepted": 0,
                    "duplicates": 0,
                    "rejected": [{"event_id": event["event_id"], "code": "HASH_MISMATCH"}],
                },
            )
        )
    )
    transport = Transport(config, http=http)
    assert transport.send([event], str(uuid4())) is SendResult.OK
    assert len(list(transport.dead_letters.glob("*.jsonl"))) == 1
    transport.close()


def test_sql_scrub():
    normalized = normalize_sql(
        "SELECT * FROM users WHERE email='secret@example.com' AND id IN (1,2,3) -- PII"
    )
    assert "secret" not in normalized
    assert "PII" not in normalized
    assert "1" not in normalized
    assert normalize_sql("select $$secret$$, 42") == "select ?, ?"


async def test_middleware_concurrency(tmp_path):
    app = FastAPI()
    client = Tracelore(
        TraceloreConfig(api_key="test", service="test", max_buffer=1000, spool_dir=tmp_path)
    )
    app.add_middleware(TraceloreMiddleware, client=client)

    @app.get("/orders/{order_id}")
    async def read(order_id: int):
        await asyncio.sleep(0)
        return {"id": order_id}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as http:
        await asyncio.gather(*(http.get(f"/orders/{index}") for index in range(100)))
    events = client.buffer.drain(1000, 0)
    assert len({event["trace_id"] for event in events}) == 100
    assert all(event["attributes"]["route"] == "/orders/{order_id}" for event in events)
    assert all(event["parent_span_id"] is None for event in events)
    client.shutdown()


async def test_httpx_stream_error_and_trace_header(tmp_path):
    from tracelore.integrations.httpx_client import TraceloreAsyncTransport

    client = Tracelore(TraceloreConfig(api_key="test", service="gateway", spool_dir=tmp_path))
    seen = []

    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"partial"
            raise httpx.ReadError("injected stream failure")

    def handle(request):
        seen.append(request.headers.get("x-tracelore-trace"))
        return httpx.Response(200, stream=BrokenStream())

    transport = TraceloreAsyncTransport(client, httpx.MockTransport(handle))
    try:
        async with httpx.AsyncClient(transport=transport) as http:
            with pytest.raises(httpx.ReadError):
                await http.get("http://payments/pay")
        events = client.buffer.drain(100, 0)
        assert len(events) == 1 and events[0]["status"] == "error"
        assert seen[0].split(":")[1] == events[0]["span_id"]
    finally:
        client.shutdown()
