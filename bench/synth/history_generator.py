import argparse
import asyncio
import math
import random
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from tracelore.canonical import hash_payload
from tracelore.chain import HashChain
from tracelore.config import TraceloreConfig
from tracelore.event import build_event


class HistoryGenerator:
    def __init__(self, seed: int) -> None:
        self.random = random.Random(seed)
        self.configs = {
            service: TraceloreConfig(
                api_key="synthetic", service=service, instance_id=f"history-{seed}"
            )
            for service in ("gateway", "inventory", "payments")
        }
        self.chains = {
            service: HashChain(config.stream_id) for service, config in self.configs.items()
        }

    def uuid(self) -> str:
        return str(UUID(int=self.random.getrandbits(128), version=4))

    def trace(self, at: datetime, checkout: bool = True) -> list[dict[str, Any]]:
        trace_id, root, inventory_client, inventory_server = (self.uuid() for _ in range(4))
        daily = 1 + 0.18 * math.sin(at.hour / 24 * 2 * math.pi)
        weekly = 0.9 if at.weekday() >= 5 else 1
        latency = max(1, self.random.gauss(30 * daily * weekly, 2))
        events = [
            self._event(
                "inventory",
                "http.request",
                {"method": "GET", "route": "/stock/{item_id}", "status_code": 200},
                trace_id,
                inventory_server,
                inventory_client,
                at + timedelta(milliseconds=2),
                latency,
            ),
            self._event(
                "gateway",
                "http.client",
                {
                    "method": "GET",
                    "host": "inventory",
                    "downstream_service": "inventory",
                    "status_code": 200,
                    "timeout_ms": 5000,
                },
                trace_id,
                inventory_client,
                root,
                at,
                latency + 5,
            ),
        ]
        events.extend(
            self._inventory_events(
                trace_id, inventory_server, at + timedelta(milliseconds=3), latency
            )
        )
        total = latency + 8
        if checkout:
            payment_client, payment_server = self.uuid(), self.uuid()
            payment_duration = max(1, self.random.gauss(22 * daily, 1))
            payment_at = at + timedelta(milliseconds=total)
            events.extend(
                [
                    self._event(
                        "payments",
                        "http.request",
                        {"method": "POST", "route": "/pay", "status_code": 200},
                        trace_id,
                        payment_server,
                        payment_client,
                        payment_at + timedelta(milliseconds=1),
                        payment_duration,
                    ),
                    self._event(
                        "gateway",
                        "http.client",
                        {
                            "method": "POST",
                            "host": "payments",
                            "downstream_service": "payments",
                            "status_code": 200,
                            "timeout_ms": 5000,
                        },
                        trace_id,
                        payment_client,
                        root,
                        payment_at,
                        payment_duration + 3,
                    ),
                ]
            )
            total += payment_duration + 5
        events.append(
            self._event(
                "gateway",
                "http.request",
                {
                    "method": "POST" if checkout else "GET",
                    "route": "/checkout" if checkout else "/cart",
                    "status_code": 200,
                },
                trace_id,
                root,
                None,
                at,
                total,
            )
        )
        return [
            self.chains[event["service"]].seal(event)
            for event in sorted(events, key=lambda event: event["ended_at"])
        ]

    def _inventory_events(
        self, trace_id: str, parent: str, at: datetime, latency: float
    ) -> list[dict[str, Any]]:
        hit = self.random.random() < 0.75
        events = [
            self._event(
                "inventory",
                "cache.get",
                {"key_hash": hash_payload("item:1"), "hit": hit},
                trace_id,
                self.uuid(),
                parent,
                at,
                min(latency / 3, 2),
            )
        ]
        if not hit:
            events.extend(
                [
                    self._event(
                        "inventory",
                        "db.query",
                        {
                            "operation": "select",
                            "db_table": "inventory",
                            "query_hash": hash_payload(
                                "select stock from inventory where item_id=?"
                            ),
                            "rows": 1,
                        },
                        trace_id,
                        self.uuid(),
                        parent,
                        at + timedelta(milliseconds=3),
                        latency / 2,
                    ),
                    self._event(
                        "inventory",
                        "cache.set",
                        {"key_hash": hash_payload("item:1")},
                        trace_id,
                        self.uuid(),
                        parent,
                        at + timedelta(milliseconds=latency * 0.8),
                        1,
                    ),
                ]
            )
        return events

    def _event(
        self,
        service: str,
        kind: str,
        attributes: dict[str, Any],
        trace_id: str,
        span: str,
        parent: str | None,
        at: datetime,
        duration: float,
    ) -> dict[str, Any]:
        return build_event(
            self.configs[service],
            kind,
            attributes,
            trace_id,
            span,
            parent,
            at,
            duration,
            "ok",
            event_id=self.uuid(),
        )


def generate(start: datetime, days: int, seed: int, traces_per_minute: int = 1) -> Any:
    generator = HistoryGenerator(seed)
    for minute in range(days * 1440):
        at = start + timedelta(minutes=minute)
        for index in range(traces_per_minute):
            yield from generator.trace(
                at + timedelta(seconds=index * 60 / traces_per_minute), checkout=minute % 4 != 0
            )


async def send_history(endpoint: str, key: str, events: Any) -> int:
    from itertools import islice

    iterator = iter(events)
    count = 0
    async with httpx.AsyncClient(timeout=30, trust_env=False) as http:
        while batch := list(islice(iterator, 1000)):
            response = await http.post(
                endpoint,
                json={"batch_id": str(UUID(int=count + 1, version=4)), "events": batch},
                headers={"x-api-key": key},
            )
            response.raise_for_status()
            result = response.json()
            if result["rejected"]:
                raise ValueError(f"history rejected: {result['rejected'][:3]}")
            count += result["accepted"]
    return count


async def main() -> None:
    import logging

    from backend.common.settings import get_settings

    parser = argparse.ArgumentParser(description="Generate seeded, sealed seasonal SDK history")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument("--traces-per-minute", type=int, default=1)
    parser.add_argument("--end", type=datetime.fromisoformat)
    args = parser.parse_args()
    settings = get_settings()
    end = args.end or datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    count = await send_history(
        settings.ingest_endpoint,
        settings.demo_ingest_key.get_secret_value(),
        generate(end - timedelta(days=args.days), args.days, args.seed, args.traces_per_minute),
    )
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).info("history_ingested count=%s", count)


if __name__ == "__main__":
    asyncio.run(main())
