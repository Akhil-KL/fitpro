"""Application configuration. All secrets come from environment variables."""

import json
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        enable_decoding=False,
    )

    app_name: str = "Fitness Logger"
    environment: Literal["development", "test", "production"] = "development"

    # PostgreSQL in every real deployment. SQLite is accepted for quick local runs and tests.
    database_url: str = "postgresql+psycopg://fitpro:fitpro@localhost:5432/fitpro"
    auto_create_tables: bool = False  # dev convenience only; production uses Alembic

    # --- Authentication ---------------------------------------------------
    # "local": email/password handled by pwdlib (Argon2) + signed JWTs (no hand-rolled crypto).
    # "supabase": Supabase Auth issues the JWT; the backend only validates it.
    auth_mode: Literal["local", "supabase"] = "local"
    jwt_secret: str = Field(default="change-me-in-production-please-32+chars", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24
    password_reset_minutes: int = 30
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None  # Supabase project JWT secret (HS256)
    supabase_jwt_audience: str = "authenticated"
    supabase_service_key: str | None = None  # used for Storage uploads
    supabase_storage_bucket: str = "workout-plans"

    # --- AI ------------------------------------------------------------------
    ai_provider: Literal["rules", "openai", "gemini"] = "rules"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    ai_timeout_seconds: float = 20.0
    chat_context_messages: int = 8

    # --- Storage -------------------------------------------------------------
    storage_backend: Literal["local", "supabase"] = "local"
    local_storage_dir: str = "./storage"
    max_upload_mb: int = 5

    # --- HTTP ----------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:3000"]
    chat_rate_limit_per_minute: int = 30
    frontend_url: str = "http://localhost:3000"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            value = v.strip()
            if value.startswith("["):
                return json.loads(value)
            return [o.strip() for o in value.split(",") if o.strip()]
        return v

    @property
    def ai_enabled(self) -> bool:
        return (
            (self.ai_provider == "openai" and bool(self.openai_api_key))
            or (self.ai_provider == "gemini" and bool(self.gemini_api_key))
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
