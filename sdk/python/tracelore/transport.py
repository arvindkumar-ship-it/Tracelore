import gzip
import logging
from enum import Enum
from pathlib import Path
from time import time_ns
from typing import Any

import httpx

from .canonical import canonical_json
from .config import TraceloreConfig

logger = logging.getLogger(__name__)


class SendResult(Enum):
    OK = "ok"
    RETRYABLE = "retryable"
    REJECTED = "rejected"


class Transport:
    def __init__(self, config: TraceloreConfig, *, http: httpx.Client | None = None) -> None:
        self.config = config
        self.http = http or httpx.Client(timeout=2, trust_env=False)
        self.dead_letters = config.spool_dir / config.service / "rejected"

    def send(
        self, events: list[dict[str, Any]], batch_id: str, sdk_stats: dict[str, int] | None = None
    ) -> SendResult:
        body = canonical_json({"batch_id": batch_id, "events": events, "sdk_stats": sdk_stats})
        try:
            response = self.http.post(
                self.config.endpoint,
                content=gzip.compress(body),
                headers={
                    "x-api-key": self.config.api_key,
                    "content-type": "application/json",
                    "content-encoding": "gzip",
                },
            )
        except httpx.TransportError:
            return SendResult.RETRYABLE
        if response.status_code == 429 or response.status_code >= 500:
            return SendResult.RETRYABLE
        if response.is_success:
            rejected = response.json().get("rejected", [])
            rejected_ids = {item["event_id"] for item in rejected}
            self.reject([event for event in events if event["event_id"] in rejected_ids])
            return SendResult.OK
        self.reject(events)
        return SendResult.REJECTED

    def reject(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        self.dead_letters.mkdir(parents=True, exist_ok=True, mode=0o700)
        path: Path = self.dead_letters / f"rejected-{time_ns()}.jsonl"
        path.write_bytes(b"".join(canonical_json(event) + b"\n" for event in events))
        logger.error("events_rejected count=%s file=%s", len(events), path.name)

    def close(self) -> None:
        self.http.close()
