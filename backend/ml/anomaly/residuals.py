from backend.ml.baseline.stats_model import transform


def to_residual(value: float, expected: float, scale: float, metric: str = "error_rate") -> float:
    return (transform(value, metric) - transform(expected, metric)) / max(scale, 1e-6)
