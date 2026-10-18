import io
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.special import gammaln, logsumexp

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BocpdOutput:
    short_mass: float
    map_run_length: int
    step_index: int


class BOCPD:
    def __init__(
        self,
        hazard: float = 1 / 250,
        prior: tuple[float, float, float, float] = (0, 1, 1, 1),
        max_run: int = 500,
        k_short: int = 5,
    ) -> None:
        if not 0 < hazard < 1 or max_run <= k_short or min(prior[1:]) <= 0:
            raise ValueError("invalid change-point prior")
        self.hazard, self.prior, self.max_run, self.k_short = hazard, prior, max_run, k_short
        self.step_index = 0
        self.run_probs = np.array([1.0])
        self.mu, self.kappa, self.alpha, self.beta = (np.array([value]) for value in prior)

    def _log_predictive(self, value: float) -> Any:
        degrees = 2 * self.alpha
        scale_squared = self.beta * (self.kappa + 1) / (self.alpha * self.kappa)
        return (
            gammaln((degrees + 1) / 2)
            - gammaln(degrees / 2)
            - 0.5 * np.log(degrees * np.pi * scale_squared)
            - (degrees + 1) / 2 * np.log1p((value - self.mu) ** 2 / (degrees * scale_squared))
        )

    def update(self, value: float) -> BocpdOutput:
        if not np.isfinite(value):
            raise ValueError("change-point input must be finite")
        joint = np.log(np.maximum(self.run_probs, np.finfo(float).tiny)) + self._log_predictive(
            value
        )
        log_probs = np.r_[logsumexp(joint) + np.log(self.hazard), joint + np.log1p(-self.hazard)]
        self.run_probs = np.exp(log_probs - logsumexp(log_probs))
        self._update_parameters(value)
        if not np.isfinite(self.run_probs).all():
            logger.warning("bocpd_numerical_reset step=%s", self.step_index)
            self.run_probs = np.array([1.0])
            self.mu, self.kappa, self.alpha, self.beta = (np.array([value]) for value in self.prior)
        if len(self.run_probs) > self.max_run:
            self.run_probs[self.max_run - 1] += self.run_probs[self.max_run :].sum()
            self.run_probs = self.run_probs[: self.max_run]
            self.mu, self.kappa, self.alpha, self.beta = (
                value[: self.max_run] for value in (self.mu, self.kappa, self.alpha, self.beta)
            )
        self.step_index += 1
        return BocpdOutput(
            float(self.run_probs[: self.k_short + 1].sum()),
            int(np.argmax(self.run_probs, axis=None)),
            self.step_index,
        )

    def _update_parameters(self, value: float) -> None:
        self.beta = np.r_[
            self.prior[3], self.beta + self.kappa * (value - self.mu) ** 2 / (2 * (self.kappa + 1))
        ]
        self.mu = np.r_[self.prior[0], (self.kappa * self.mu + value) / (self.kappa + 1)]
        self.kappa = np.r_[self.prior[1], self.kappa + 1]
        self.alpha = np.r_[self.prior[2], self.alpha + 0.5]

    def to_bytes(self) -> bytes:
        buffer = io.BytesIO()
        np.savez(
            buffer,
            run_probs=self.run_probs,
            mu=self.mu,
            kappa=self.kappa,
            alpha=self.alpha,
            beta=self.beta,
            prior=np.asarray(self.prior),
            config=np.array([self.hazard, self.max_run, self.k_short, self.step_index]),
        )
        return buffer.getvalue()

    @classmethod
    def from_bytes(cls, data: bytes) -> "BOCPD":
        with np.load(io.BytesIO(data), allow_pickle=False) as arrays:
            hazard, max_run, k_short, step = arrays["config"]
            model = cls(float(hazard), tuple(arrays["prior"]), int(max_run), int(k_short))
            model.step_index = int(step)
            for field in ("run_probs", "mu", "kappa", "alpha", "beta"):
                setattr(model, field, arrays[field].copy())
        return model
