from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FORGE_", env_file=".env", extra="ignore")

    environment: Literal["local", "test", "production"] = "local"
    database_url: SecretStr
    database_timeout_seconds: float = Field(default=3, gt=0, le=60)

    approval_reviewer_token: SecretStr | None = Field(default=None, min_length=32)
    approval_reviewer_id: UUID | None = None

    execution_mode: Literal["queued", "inline"] = "queued"
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    worker_poll_seconds: float = Field(default=1, gt=0, le=30)
    model_max_attempts: int = Field(default=3, ge=1, le=5)
    retry_base_seconds: float = Field(default=1, gt=0, le=30)

    model_backend: Literal["gemini", "fake"] = "gemini"
    gemini_api_key: SecretStr | None = None
    model_timeout_seconds: float = Field(default=60, gt=0, le=300)
    model_max_output_tokens: int = Field(default=1024, ge=1, le=8192)

    @field_validator("approval_reviewer_token", "approval_reviewer_id", mode="before")
    @classmethod
    def empty_reviewer_setting(cls, value):
        return None if value == "" else value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername == "postgresql+asyncpg" and bool(url.database)
        except Exception:
            valid = False
        if not valid:
            raise ValueError("Database URL must use postgresql+asyncpg and name a database")
        return value
