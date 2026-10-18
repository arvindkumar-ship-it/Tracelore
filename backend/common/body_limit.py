import zlib
from typing import Any

from fastapi.responses import JSONResponse

from .errors import envelope


class BodyLimit:
    def __init__(self, app: Any, max_bytes: int) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        inflater = (
            zlib.decompressobj(16 + zlib.MAX_WBITS)
            if headers.get(b"content-encoding") == b"gzip"
            else None
        )
        chunks, total, wire_bytes = [], 0, 0
        try:
            more = True
            while more:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                data = message.get("body", b"")
                wire_bytes += len(data)
                if wire_bytes > self.max_bytes:
                    raise OverflowError
                data = inflater.decompress(data, self.max_bytes - total + 1) if inflater else data
                total += len(data)
                if total > self.max_bytes or (inflater and inflater.unconsumed_tail):
                    raise OverflowError
                chunks.append(data)
                more = message.get("more_body", False)
            if inflater and (not inflater.eof or inflater.unused_data):
                raise ValueError("Incomplete gzip body")
        except (OverflowError, ValueError, zlib.error) as error:
            status = 413 if isinstance(error, OverflowError) else 400
            response = JSONResponse(
                envelope(
                    "TOO_LARGE" if status == 413 else "BAD_REQUEST",
                    "Body exceeds limit or has invalid encoding",
                ),
                status,
            )
            await response(scope, receive, send)
            return
        await self._forward(scope, receive, send, b"".join(chunks))

    async def _forward(self, scope: Any, receive: Any, send: Any, body: bytes) -> None:
        delivered = False

        async def replay() -> Any:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        scope = dict(scope)
        scope["headers"] = [
            (key, value)
            for key, value in scope["headers"]
            if key not in (b"content-encoding", b"content-length")
        ]
        await self.app(scope, replay, send)
