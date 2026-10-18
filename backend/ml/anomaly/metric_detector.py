from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean
from uuid import NAMESPACE_URL, uuid5

from backend.ml.baseline.contracts import MetricRange

from .bocpd import BOCPD
from .contracts import Signal
from .residuals import to_residual

BUCKET_SECONDS = 5
COOLDOWN_SECONDS = 600


@dataclass
class MetricStream:
    model: BOCPD = field(default_factory=BOCPD)
    consecutive: int = 0
    residuals: list[float] = field(default_factory=list)
    last_alarm: datetime | None = None
    last_seen: datetime | None = None

    def observe(
        self,
        service: str,
        route: str,
        metric: str,
        value: float,
        baseline: MetricRange,
        at: datetime,
    ) -> Signal | None:
        self.last_seen = at
        residual = to_residual(value, baseline.expected, baseline.scale, metric)
        output = self.model.update(residual)
        self.residuals = (self.residuals + [residual])[-600:]
        # The initial prior assigns all mass to short runs; it is not a change.
        self.consecutive = (
            self.consecutive + 1 if output.short_mass > 0.7 and output.step_index > 20 else 0
        )
        if self.consecutive < 2 or (
            self.last_alarm and at - self.last_alarm < timedelta(seconds=COOLDOWN_SECONDS)
        ):
            return None
        self.last_alarm = at
        post = self.residuals[-max(1, min(output.map_run_length, len(self.residuals))) :]
        return Signal(
            id=str(uuid5(NAMESPACE_URL, f"{service}:{route}:{metric}:{at.isoformat()}")),
            kind="metric",
            service=service,
            route=route,
            detected_at=at,
            estimated_start=at - timedelta(seconds=output.map_run_length * BUCKET_SECONDS),
            metric=metric,
            direction="up" if mean(post) >= 0 else "down",
            confidence=output.short_mass,
            magnitude=mean(abs(value) for value in post),
            baseline_high=baseline.high,
        )
