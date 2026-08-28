from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CARDIOCLAW_",
        extra="ignore",
    )

    environment: Literal["development", "production"] = "development"

    data_dir: Path = Path("~/CardioClaw/data")
    output_dir: Path | None = None
    release_retention: int = Field(default=8, ge=2, le=104)

    ncbi_email: str = ""
    ncbi_api_key: SecretStr | None = None
    ncbi_tool: str = "cardioclaw"
    request_timeout_seconds: float = Field(default=30, ge=5, le=120)

    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-sonnet-4-6"

    openai_api_key: SecretStr | None = None
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_voice: str = "nova"
    openai_tts_instructions: str = (
        "Speak as a calm, precise medical colleague briefing a retired cardiologist. "
        "Use natural prosody, careful pronunciation, and a measured pace. "
        "Read percentages, confidence intervals, study names, and abbreviations distinctly. "
        "Do not sound promotional or theatrical."
    )

    max_nuclear_candidates: int = Field(default=20, ge=5, le=100)
    max_general_candidates: int = Field(default=20, ge=0, le=100)
    max_rss_items_per_feed: int = Field(default=4, ge=0, le=20)
    min_nuclear_findings: int = Field(default=5, ge=0, le=12)
    max_findings: int = Field(default=8, ge=1, le=12)
    min_selection_score: float = Field(default=25, ge=0, le=200)
    full_text_enabled: bool = True
    max_full_text_characters: int = Field(default=45_000, ge=5_000, le=200_000)

    public_base_url: str = "http://127.0.0.1:5000"
    feed_token: SecretStr = SecretStr("development-feed-token")
    show_title: str = "Cardiology Report"
    show_description: str = "A private, automated nuclear cardiology audio briefing."
    show_author: str = "Cardiology Claw"
    cover_filename: str = "cover.png"
    cover_path: Path = Path("./cover.png")
    server_host: str = "127.0.0.1"
    server_port: int = Field(default=5000, ge=1, le=65535)

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    alert_email_to: str = ""
    alert_email_from: str = ""
    alert_email_password: SecretStr | None = None

    @property
    def root_dir(self) -> Path:
        return self.data_dir.expanduser().resolve()

    @property
    def releases_dir(self) -> Path:
        return self.root_dir / "releases"

    @property
    def current_pointer(self) -> Path:
        return self.root_dir / "current.json"

    @property
    def resolved_cover_path(self) -> Path:
        return self.cover_path.expanduser().resolve()

    @property
    def resolved_output_dir(self) -> Path:
        return (self.output_dir or self.root_dir / "legacy_output").expanduser().resolve()

    @property
    def feed_token_value(self) -> str:
        return self.feed_token.get_secret_value()

    @property
    def ncbi_api_key_value(self) -> str | None:
        return self.ncbi_api_key.get_secret_value() if self.ncbi_api_key else None

    @property
    def anthropic_api_key_value(self) -> str | None:
        return self.anthropic_api_key.get_secret_value() if self.anthropic_api_key else None

    @property
    def openai_api_key_value(self) -> str | None:
        return self.openai_api_key.get_secret_value() if self.openai_api_key else None

    @property
    def alert_email_password_value(self) -> str | None:
        return self.alert_email_password.get_secret_value() if self.alert_email_password else None

    @model_validator(mode="after")
    def validate_safety(self) -> Settings:
        base = self.public_base_url.rstrip("/")
        self.public_base_url = base

        if self.environment == "production":
            failures: list[str] = []
            if not base.startswith("https://"):
                failures.append("production public_base_url must use HTTPS")
            if self.feed_token_value in {"", "development-feed-token"}:
                failures.append("production requires a strong private feed token")
            if not self.ncbi_email or "example.com" in self.ncbi_email:
                failures.append("production requires an operational NCBI contact email")
            if self.server_host == "0.0.0.0" and not base.startswith("https://"):
                failures.append("public binding requires an HTTPS reverse proxy")
            if failures:
                raise ValueError("; ".join(failures))
        return self

    def require_generation_credentials(self) -> None:
        missing = []
        if not self.anthropic_api_key_value:
            missing.append("CARDIOCLAW_ANTHROPIC_API_KEY")
        if not self.openai_api_key_value:
            missing.append("CARDIOCLAW_OPENAI_API_KEY")
        if not self.ncbi_email:
            missing.append("CARDIOCLAW_NCBI_EMAIL")
        if missing:
            raise RuntimeError("Missing required configuration: " + ", ".join(missing))

    def prepare_directories(self) -> None:
        self.releases_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_output_dir.mkdir(parents=True, exist_ok=True)

    def ffmpeg_available(self) -> bool:
        return shutil.which("ffmpeg") is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
