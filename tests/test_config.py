"""Tests for freshdesk_tui.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from freshdesk_tui.config import Config, ConfigError


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure Freshdesk env vars are unset unless explicitly set in a test."""
    monkeypatch.delenv("FRESHDESK_DOMAIN", raising=False)
    monkeypatch.delenv("FRESHDESK_API_KEY", raising=False)


class TestConfigFromEnv:
    def test_loads_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("FRESHDESK_DOMAIN", "test.freshdesk.com")
        monkeypatch.setenv("FRESHDESK_API_KEY", "secret123")

        config = Config.load()

        assert config.domain == "test.freshdesk.com"
        assert config.api_key == "secret123"

    def test_env_vars_take_precedence_over_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FRESHDESK_DOMAIN", "env.freshdesk.com")
        monkeypatch.setenv("FRESHDESK_API_KEY", "env_key")

        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[freshdesk]\ndomain = "file.freshdesk.com"\napi_key = "file_key"\n'
        )

        config = Config.load(config_paths=[config_file])

        assert config.domain == "env.freshdesk.com"
        assert config.api_key == "env_key"


class TestConfigFromFile:
    def test_loads_from_toml_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[freshdesk]\ndomain = "acme.freshdesk.com"\napi_key = "toml_key"\n'
        )

        config = Config.load(config_paths=[config_file])

        assert config.domain == "acme.freshdesk.com"
        assert config.api_key == "toml_key"

    def test_tries_multiple_paths(self, tmp_path):
        missing = tmp_path / "nonexistent.toml"
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[freshdesk]\ndomain = "second.freshdesk.com"\napi_key = "key2"\n'
        )

        config = Config.load(config_paths=[missing, config_file])

        assert config.domain == "second.freshdesk.com"

    def test_partial_env_completed_by_file(self, monkeypatch, tmp_path):
        """If only domain is in env, api_key can come from file."""
        monkeypatch.setenv("FRESHDESK_DOMAIN", "env.freshdesk.com")

        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[freshdesk]\napi_key = "file_key"\n'
        )

        config = Config.load(config_paths=[config_file])

        assert config.domain == "env.freshdesk.com"
        assert config.api_key == "file_key"


class TestConfigMissing:
    def test_raises_config_error_when_no_credentials(self):
        config = Path("/nonexistent/path/config.toml")
        with pytest.raises(ConfigError, match="Freshdesk credentials not found"):
            Config.load(config_paths=[config])

    def test_raises_when_file_has_incomplete_config(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[freshdesk]\ndomain = "only-domain.freshdesk.com"\n')

        with pytest.raises(ConfigError):
            Config.load(config_paths=[config_file])
