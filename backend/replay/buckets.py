from bisect import bisect_left
from dataclasses import dataclass, field
from math import ceil
from typing import Any

LATENCY_BOUNDS_US = (
    1000,
    1300,
    1700,
    2200,
    2900,
    3800,
    5000,
    6500,
    8500,
    11000,
    14000,
    18000,
    24000,
    31000,
    40000,
    52000,
    68000,
    89000,
    116000,
    151000,
    197000,
    256000,
    333000,
    433000,
    563000,
    732000,
    952000,
    1238000,
    1609000,
    2092000,
    2720000,
    3536000,
    4597000,
    5976000,
    7769000,
    10100000,
    13130000,
    17070000,
    22190000,
    28850000,
    37500000,
    48750000,
    60000000,
    2**63 - 1,
)


@dataclass
class Histogram:
    counts: list[int] = field(default_factory=lambda: [0] * len(LATENCY_BOUNDS_US))

    def add(self, duration_us: int) -> None:
        self.counts[min(bisect_left(LATENCY_BOUNDS_US, duration_us), len(self.counts) - 1)] += 1

    def quantile(self, quantile: float) -> int:
        if not 0 <= quantile <= 1:
            raise ValueError("quantile must be between zero and one")
        target, total = max(1, ceil(sum(self.counts) * quantile)), 0
        for bound, count in zip(LATENCY_BOUNDS_US, self.counts, strict=True):
            total += count
            if total >= target:
                return bound
        return 0

    def to_dict(self) -> dict[str, list[int]]:
        return {"counts": self.counts.copy()}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Histogram":
        counts = list(value["counts"])
        if len(counts) != len(LATENCY_BOUNDS_US) or any(count < 0 for count in counts):
            raise ValueError("invalid histogram")
        return cls(counts)
