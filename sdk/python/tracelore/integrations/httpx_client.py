from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import cast
from uuid import uuid4

import httpx

from ..client import Tracelore
from ..context import TRACE_HEADER, current_ids, header_value


class _ObservedStream(httpx.AsyncByteStream):
    def __init__(self, stream: httpx.AsyncByteStream, finish: Callable[[bool], None]) -> None:
        self.stream, self.finish = stream, finish

    async def __aiter__(self) -> AsyncIterator[bytes]:
        try:
            async for chunk in self.stream:
                yield chunk
        except BaseException:
            self.finish(True)
            raise
        else:
            self.finish(False)

    async def aclose(self) -> None:
        try:
            await self.stream.aclose()
        finally:
            self.finish(False)


class TraceloreAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(
        self, client: Tracelore, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.client = client
        self.transport = transport or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        trace_id, parent = current_ids()
        trace_id, span_id = trace_id or str(uuid4()), str(uuid4())
        request.headers[TRACE_HEADER] = header_value(trace_id, span_id)
        started_at, started = datetime.now(UTC), perf_counter()
        status_code = None
        recorded = False

        def finish(failed: bool) -> None:
            nonlocal recorded
            if recorded:
                return
            recorded = True
            self._record(
                request, trace_id, span_id, parent, started_at, started, status_code, failed
            )

        try:
            response = await self.transport.handle_async_request(request)
            status_code = response.status_code
        except BaseException:
            finish(True)
            raise
        response.stream = _ObservedStream(cast(httpx.AsyncByteStream, response.stream), finish)
        return response

    def _record(
        self,
        request: httpx.Request,
        trace_id: str,
        span_id: str,
        parent: str | None,
        started_at: datetime,
        started: float,
        status_code: int | None,
        failed: bool,
    ) -> None:
        host = request.url.host
        timeout = request.extensions.get("timeout", {}).get("read")
        self.client.record(
            "http.client",
            {
                "method": request.method,
                "host": host,
                "status_code": status_code,
                "downstream_service": self.client.config.service_map.get(host, host),
                "timeout_ms": None if timeout is None else round(timeout * 1000),
            },
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
            status="error" if failed or status_code is None or status_code >= 500 else "ok",
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent,
        )

    async def aclose(self) -> None:
        await self.transport.aclose()
