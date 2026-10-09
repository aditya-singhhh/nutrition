"""Application settings. All secrets come from environment variables - never hard-code."""
from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HC_", extra="ignore")

    env: str = "dev"  # dev | test | staging | prod
    database_url: str = "sqlite:///./healthcompanion.db"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 14  # 14 days: mobile app has no refresh flow yet (add refresh tokens before real users)
    seed_on_startup: bool = True
    rate_limit: bool = True
    # Hosted demo without migrations: create tables and load reference data on boot. Remove once Alembic exists.
    auto_create_tables: bool = False
    log_level: str = "INFO"

    # Provider selection (AI Gateway). Business logic never imports a vendor SDK directly.
    llm_provider: str = "mock"  # mock | anthropic
    vision_provider: str = "null"  # null | mock | gemini (auto-enabled when HC_GEMINI_API_KEY is set)
    ocr_provider: str = "null"  # null | mock | gemini (auto-enabled when HC_GEMINI_API_KEY is set)
    # Comma-separated emails allowed to review products (no role editing through the API).
    admin_emails: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    # Look unknown barcodes up in Open Food Facts (public, crowd-sourced, unverified) and cache them.
    off_lookup: bool = True
    llm_model: str = ""  # required when llm_provider != mock
    llm_api_key: str = ""

    consent_version: str = "2026-10-v1"
    max_upload_bytes: int = 8 * 1024 * 1024

    @field_validator("database_url")
    @classmethod
    def _driver(cls, v: str) -> str:
        # Hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg driver named.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    def resolved_jwt_secret(self) -> str:
        if self.jwt_secret:
            return self.jwt_secret
        if self.env in ("staging", "prod"):
            raise RuntimeError("HC_JWT_SECRET must be set in staging/prod")
        return _dev_secret()


@lru_cache
def _dev_secret() -> str:
    logger.warning("HC_JWT_SECRET not set; using an ephemeral dev secret (tokens die on restart)")
    return secrets.token_urlsafe(32)


@lru_cache
def get_settings() -> Settings:
    return Settings()
