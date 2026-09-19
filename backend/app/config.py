"""Application configuration.

All deployment-sensitive values are read from the environment (or ``.env``).
Development gets an ephemeral key so a checked-out repository never contains
an authentication secret.  Production refuses to start with the development
credentials.
"""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("["):
            try:
                import json
                parsed = json.loads(value)
                return _list(parsed)
            except (ValueError, TypeError):
                pass
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value).strip()]


class Settings(BaseSettings):
    app_name: str = Field(
        default="GuardAIN",
        validation_alias=AliasChoices("GUARDAIN_APP_NAME", "APP_NAME", "GAURDAIN_APP_NAME"),
    )
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    api_v1_prefix: str = "/v1"
    log_level: str = "INFO"
    cors_origins: list[str] = [
        "http://127.0.0.1:3000", "http://localhost:3000",
        "http://127.0.0.1:3001", "http://localhost:3001",
        "http://127.0.0.1:8080", "http://localhost:8080",
    ]
    allow_credentials: bool = True
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl_seconds: int = 300
    redis_request_ttl_seconds: int = 60
    database_url: str = "sqlite:///./guardain.db"
    model_version: str = "heuristic-fallback-v1"
    deep_analysis_enabled: bool = True
    verify_timeout_ms: int = 5000
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    rate_limit_per_minute: int = 100
    rate_limit_window_seconds: int = 60
    onnx_model_path: str = "backend/models/guardain_muril.onnx"
    onnx_tokenizer_path: str = "backend/models/guardain_tokenizer"
    onnx_execution_providers: list[str] = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    gnn_feature_dim: int = 32
    gnn_hops: int = 3
    pii_scrub_enabled: bool = True
    pii_hash_enabled: bool = True
    dataset_output_dir: str = "./data"
    model_retrain_buffer: str = "./data/false_positive_buffer.parquet"
    admin_username: str = Field(
        default="admin",
        validation_alias=AliasChoices("GUARDAIN_ADMIN_USERNAME", "ADMIN_USERNAME"),
    )
    admin_password: str = Field(
        default="admin@26",
        validation_alias=AliasChoices("GUARDAIN_ADMIN_PASSWORD", "ADMIN_PASSWORD"),
    )
    admin_password_hash: str = ""
    max_incidents: int = 500
    max_telemetry_events: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False,
        extra="ignore", validate_default=True, enable_decoding=False,
    )

    @field_validator("cors_origins", "onnx_execution_providers", mode="before")
    @classmethod
    def parse_lists(cls, value: Any) -> list[str]:
        return _list(value)

    @field_validator("dataset_output_dir", "model_retrain_buffer", mode="before")
    @classmethod
    def normalize_paths(cls, value: Any) -> str:
        return str(Path(value or "./data"))

    @model_validator(mode="after")
    def apply_secure_defaults(self) -> "Settings":
        # A random per-process development key prevents accidental reuse.
        if not self.jwt_secret_key:
            self.jwt_secret_key = secrets.token_urlsafe(48)
        if not self.admin_password:
            self.admin_password = secrets.token_urlsafe(24)
        if not self.admin_password_hash:
            try:
                import bcrypt
                self.admin_password_hash = bcrypt.hashpw(
                    self.admin_password.encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8")
            except ImportError as exc:
                raise RuntimeError("bcrypt is required for administrator authentication") from exc
        if self.environment.lower() in {"production", "prod"}:
            if len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")
            if len(self.admin_password) < 12:
                raise ValueError("GUARDAIN_ADMIN_PASSWORD must be at least 12 characters in production")
            if self.admin_password == "guardain-local-admin":
                raise ValueError("The development administrator password is not allowed in production")
        return self


settings = Settings()
