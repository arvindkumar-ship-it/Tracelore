import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


class ConfigError(ValueError):
    """SDK configuration cannot identify or authenticate its stream."""


@dataclass(frozen=True)
class TraceloreConfig:
    api_key: str
    service: str
    endpoint: str = "http://localhost:8001/ingest"
    instance_id: str = field(default_factory=lambda: str(uuid4()))
    batch_size: int = 50
    flush_interval_ms: int = 100
    max_buffer: int = 10_000
    spool_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "tracelore-spool")
    spool_max_mb: float = 100
    enabled: bool = True
    service_map: dict[str, str] = field(default_factory=dict)
    skip_routes: tuple[str, ...] = ("/health", "/healthz", "/metrics")

    def __post_init__(self) -> None:
        if not self.service or not self.api_key:
            raise ConfigError("service and api_key must be set")
        if min(self.batch_size, self.flush_interval_ms, self.max_buffer) < 1:
            raise ConfigError("batch, interval and buffer limits must be positive")
        if self.spool_max_mb <= 0:
            raise ConfigError("spool_max_mb must be positive")

    @property
    def stream_id(self) -> str:
        return f"{self.service}:{self.instance_id}"


def load_config(**overrides: Any) -> TraceloreConfig:
    values: dict[str, Any] = {}
    for key in ("api_key", "service", "endpoint", "instance_id"):
        if value := os.getenv(f"TRACELORE_{key.upper()}"):
            values[key] = value
    for key in ("batch_size", "flush_interval_ms", "max_buffer", "spool_max_mb"):
        if value := os.getenv(f"TRACELORE_{key.upper()}"):
            values[key] = float(value) if key == "spool_max_mb" else int(value)
    if value := os.getenv("TRACELORE_SPOOL_DIR"):
        values["spool_dir"] = Path(value)
    values["enabled"] = os.getenv("TRACELORE_ENABLED", "true").lower() != "false"
    return TraceloreConfig(**(values | overrides))
