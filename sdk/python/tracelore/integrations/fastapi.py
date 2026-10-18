from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from ..client import Tracelore
from ..context import TRACE_HEADER, parse_header, span_scope


class TraceloreMiddleware:
    def __init__(self, app: Any, client: Tracelore) -> None:
        self.app = app
        self.client = client

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["path"] in self.client.config.skip_routes:
            await self.app(scope, receive, send)
            return
        header = dict(scope.get("headers", [])).get(TRACE_HEADER.encode(), b"").decode("latin1")
        incoming = parse_header(header)
        trace_id, parent = incoming if incoming else (str(uuid4()), None)
        span_id = str(uuid4())
        status_code = 500
        failed = False
        started_at, started = datetime.now(UTC), perf_counter()

        async def capture(message: Any) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            with span_scope(trace_id, span_id):
                await self.app(scope, receive, capture)
        except BaseException as error:
            failed = True
            self.client.record_error(error, trace_id, span_id)
            raise
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            self.client.record(
                "http.request",
                {"method": scope["method"], "route": route, "status_code": status_code},
                started_at=started_at,
                duration_ms=(perf_counter() - started) * 1000,
                status="error" if failed or status_code >= 500 else "ok",
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent,
            )
