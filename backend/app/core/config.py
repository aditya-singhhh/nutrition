"""Application settings. All secrets come from environment variables - never hard-code."""
from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HC_", extra="ignore")

    env: str = "dev"  # dev | test | staging | prod
    database_url: str = "sqlite:///./healthcompanion.db"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    seed_on_startup: bool = True
    log_level: str = "INFO"

    # Provider selection (AI Gateway). Business logic never imports a vendor SDK directly.
    llm_provider: str = "mock"  # mock | anthropic
    vision_provider: str = "null"  # null | mock
    ocr_provider: str = "null"  # null | mock
    llm_model: str = ""  # required when llm_provider != mock
    llm_api_key: str = ""

    consent_version: str = "2026-10-v1"
    max_upload_bytes: int = 8 * 1024 * 1024

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
