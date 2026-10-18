from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, grangercausalitytests


@dataclass(frozen=True)
class GrangerResult:
    cause: str
    effect: str
    lag: int | None
    p_forward: float | None
    p_reverse: float | None
    status: str


def _stationary(values: np.ndarray) -> np.ndarray:
    if np.std(values) < 1e-9:
        raise ValueError("constant series")
    if adfuller(values, autolag="AIC", result_object=False)[1] > 0.05:
        values = np.diff(values)
    return values


def _direction(effect: np.ndarray, cause: np.ndarray, max_lag: int) -> tuple[int, float]:
    # statsmodels' second column is the candidate cause of its first column.
    results = grangercausalitytests(np.column_stack((effect, cause)), maxlag=max_lag)
    lag = min(results, key=lambda lag: results[lag][0]["ssr_ftest"][1])
    return lag, min(1, float(results[lag][0]["ssr_ftest"][1]) * max_lag)


def test_edge(
    cause_series: Any,
    effect_series: Any,
    max_lag: int = 5,
    cause: str = "cause",
    effect: str = "effect",
) -> GrangerResult:
    aligned = pd.concat([pd.Series(cause_series), pd.Series(effect_series)], axis=1)
    for column in aligned:
        missing = aligned[column].isna()
        longest = missing.groupby((~missing).cumsum()).sum().max()
        if longest > 3:
            return GrangerResult(cause, effect, None, None, None, "insufficient_data")
    aligned = aligned.interpolate(limit=3, limit_area="inside").dropna()
    if len(aligned) < 60:
        return GrangerResult(cause, effect, None, None, None, "insufficient_data")
    try:
        causes, effects = (
            _stationary(aligned.iloc[:, 0].to_numpy()),
            _stationary(aligned.iloc[:, 1].to_numpy()),
        )
        length = min(len(causes), len(effects))
        causes, effects = causes[-length:], effects[-length:]
        causes = (causes - causes.mean()) / max(causes.std(), 1e-6)
        effects = (effects - effects.mean()) / max(effects.std(), 1e-6)
        lag, forward = _direction(effects, causes, max_lag)
        _, reverse = _direction(causes, effects, max_lag)
    except (ValueError, np.linalg.LinAlgError):
        return GrangerResult(cause, effect, None, None, None, "insufficient_data")
    return GrangerResult(
        cause,
        effect,
        lag,
        forward,
        reverse,
        "supported" if forward < 0.05 and reverse > forward else "not_supported",
    )
