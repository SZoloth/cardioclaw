from pathlib import Path

import pytest
from pydantic import ValidationError

from cardioclaw.config import Settings


def test_production_rejects_insecure_feed_configuration() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(
            _env_file=None,
            environment="production",
            public_base_url="http://cardio.example.test",
            feed_token="development-feed-token",
            ncbi_email="operator@example.com",
        )


def test_production_accepts_https_private_feed() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        public_base_url="https://cardio.example.test/",
        feed_token="a" * 48,
        ncbi_email="operator@cardio.test",
        server_host="0.0.0.0",
    )

    assert settings.public_base_url == "https://cardio.example.test"
    assert settings.feed_token_value == "a" * 48


def test_generation_credentials_are_explicit() -> None:
    with pytest.raises(RuntimeError, match="CARDIOCLAW_ANTHROPIC_API_KEY"):
        Settings(_env_file=None).require_generation_credentials()

    settings = Settings(
        _env_file=None,
        anthropic_api_key="anthropic-test",
        openai_api_key="openai-test",
        ncbi_email="operator@cardio.test",
    )
    settings.require_generation_credentials()


def test_paths_and_directories_are_derived_from_data_dir(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)
    settings.prepare_directories()

    assert settings.root_dir == tmp_path.resolve()
    assert settings.releases_dir.is_dir()
    assert settings.resolved_output_dir.is_dir()
    assert settings.current_pointer == tmp_path.resolve() / "current.json"


def test_ffmpeg_availability_uses_path_lookup(monkeypatch) -> None:
    monkeypatch.setattr("cardioclaw.config.shutil.which", lambda name: "/usr/bin/ffmpeg")
    assert Settings(_env_file=None).ffmpeg_available() is True

    monkeypatch.setattr("cardioclaw.config.shutil.which", lambda name: None)
    assert Settings(_env_file=None).ffmpeg_available() is False
