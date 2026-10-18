from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from tracelore.canonical import canonical_json, sha256_hex
from tracelore.event import format_timestamp

from backend.ledger.records import OrderKey

from .buckets import Histogram
from .keys import pair_key, split_key

CACHE_KEY_LIMIT = 100_000


@dataclass
class EndpointStats:
    count: int = 0
    errors: int = 0
    total_duration_us: int = 0
    histogram: Histogram = field(default_factory=Histogram)


@dataclass
class EdgeStats:
    count: int = 0
    errors: int = 0
    total_duration_us: int = 0


@dataclass
class CacheState:
    hits: int = 0
    misses: int = 0
    present_keys: dict[str, None] = field(default_factory=dict)

    def mark_present(self, key_hash: str) -> None:
        self.present_keys[key_hash] = None
        if len(self.present_keys) > CACHE_KEY_LIMIT:
            del self.present_keys[next(iter(self.present_keys))]


@dataclass
class SystemState:
    endpoints: dict[tuple[str, str], EndpointStats] = field(default_factory=dict)
    edges: dict[tuple[str, str], EdgeStats] = field(default_factory=dict)
    db_tables: dict[str, dict[str, int]] = field(default_factory=dict)
    cache: CacheState = field(default_factory=CacheState)
    queues: dict[str, int] = field(default_factory=dict)
    errors_by_type: dict[str, int] = field(default_factory=dict)
    last_key: OrderKey | None = None
    event_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoints": {
                pair_key(key): asdict(value) for key, value in sorted(self.endpoints.items())
            },
            "edges": {pair_key(key): asdict(value) for key, value in sorted(self.edges.items())},
            "db_tables": dict(sorted(self.db_tables.items())),
            "cache": {
                "hits": self.cache.hits,
                "misses": self.cache.misses,
                "present_keys": list(self.cache.present_keys),
            },
            "queues": dict(sorted(self.queues.items())),
            "errors_by_type": dict(sorted(self.errors_by_type.items())),
            "last_key": [format_timestamp(self.last_key[0]), *self.last_key[1:]]
            if self.last_key
            else None,
            "event_count": self.event_count,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SystemState":
        state = cls()
        for key, stats in value["endpoints"].items():
            service, route = split_key(key)
            state.endpoints[(service, route)] = EndpointStats(
                stats["count"],
                stats["errors"],
                stats["total_duration_us"],
                Histogram.from_dict(stats["histogram"]),
            )
        state.edges = {split_key(key): EdgeStats(**stats) for key, stats in value["edges"].items()}
        state.db_tables = value["db_tables"]
        state.cache = CacheState(
            value["cache"]["hits"],
            value["cache"]["misses"],
            dict.fromkeys(value["cache"]["present_keys"]),
        )
        state.queues, state.errors_by_type = value["queues"], value["errors_by_type"]
        if key := value["last_key"]:
            state.last_key = (datetime.fromisoformat(key[0]), key[1], key[2])
        state.event_count = value["event_count"]
        return state

    def summary(self) -> dict[str, Any]:
        value = self.to_dict()
        value["cache"] = {
            "hits": self.cache.hits,
            "misses": self.cache.misses,
            "present_key_count": len(self.cache.present_keys),
            "hit_ratio": self.cache.hits / max(self.cache.hits + self.cache.misses, 1),
        }
        for key in ("endpoints", "edges"):
            value[key] = dict(
                sorted(value[key].items(), key=lambda item: (-item[1]["count"], item[0]))[:100]
            )
        value["db_tables"] = dict(list(value["db_tables"].items())[:100])
        return value

    def digest(self) -> str:
        return sha256_hex(canonical_json(self.to_dict()))

    def copy(self) -> "SystemState":
        return deepcopy(self)
