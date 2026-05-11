"""Application settings loaded from environment variables (.env supported)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for the IKUSA prototype.

    Loaded from environment variables; .env in the current working dir is
    picked up automatically. Defaults are aligned with the docker-compose
    services (mobsf on 8000, ollama on 11434).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mobsf_url: str = "http://localhost:8000"
    mobsf_api_key: str = "replace_with_actual_mobsf_key"

    llm_provider: str = "ollama"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    scan_storage: Path = Field(default=Path("/tmp/ikusa-scans"))
    api_keys_path: Path = Field(default=Path("data/api_keys.yaml"))


def get_settings() -> Settings:
    """Return validated settings and ensure storage dir exists."""
    settings = Settings()
    settings.scan_storage.mkdir(parents=True, exist_ok=True)
    return settings
