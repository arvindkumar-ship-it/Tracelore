from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: SecretStr = SecretStr("postgresql://tracelore_app@localhost:5432/tracelore")
    owner_database_url: SecretStr = SecretStr(
        "postgresql://tracelore_owner@localhost:5432/tracelore"
    )
    redis_url: str = "redis://localhost:6379/0"
    kafka_broker: str = "localhost:19092"
    tracelore_secret: SecretStr = Field(min_length=32)
    ingest_max_batch: int = Field(default=1000, ge=1, le=1000)
    ingest_rate_limit: int = Field(default=50_000, ge=1)
    late_grace_seconds: int = Field(default=30, ge=0)
    snapshot_every_events: int = Field(default=5000, ge=1)
    hot_retention_days: int = Field(default=7, ge=1)
    warm_retention_days: int = Field(default=30, ge=1)
    llm_model: str = "openai/gpt-4o-mini"
    openai_api_key: SecretStr = SecretStr("")
    llm_enabled: bool = False
    rag_enabled: bool = False
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "tracelore"
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    dashboard_origin: str = "http://localhost:3000"
    baseline_k: float = Field(default=4, ge=1)
    model_dir: Path = Path("models")
    sequence_mode: Literal["ngram", "dual"] = "ngram"
    archive_dir: Path = Path("artifacts/archive")
    lossy_sampling_enabled: bool = False
    enable_tiering: bool = False
    rca_weights: tuple[float, float, float, float] = (0.40, 0.25, 0.20, 0.15)
    max_body_bytes: int = 5 * 1024 * 1024
    demo_token: SecretStr = SecretStr("")
    demo_service: str = "gateway"
    demo_ingest_key: SecretStr = SecretStr("")
    ingest_endpoint: str = "http://localhost:8001/ingest"
    demo_gateway_url: str = "http://localhost:8010"
    demo_inventory_url: str = "http://localhost:8011"
    demo_payments_url: str = "http://localhost:8012"

    @model_validator(mode="after")
    def check_retention(self) -> "Settings":
        if self.warm_retention_days < self.hot_retention_days:
            raise ValueError("warm retention must be at least hot retention")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # Required fields are supplied by environment sources.
