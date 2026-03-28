"""Configuration management."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


CONFIG_FILENAME = "config.toml"
CONFIG_PATHS = [
    Path.cwd() / CONFIG_FILENAME,
    Path.home() / ".config" / "freshdesk-tui" / CONFIG_FILENAME,
]


class ConfigError(Exception):
    """Raised when Freshdesk credentials cannot be found."""


@dataclass
class Config:
    domain: str
    api_key: str

    @classmethod
    def load(cls, config_paths: list[Path] | None = None) -> Config:
        """Load config from environment variables or TOML files.

        Args:
            config_paths: Override default config file search paths (useful for testing).
        """
        paths = config_paths if config_paths is not None else CONFIG_PATHS

        # Environment variables take precedence
        domain = os.environ.get("FRESHDESK_DOMAIN", "")
        api_key = os.environ.get("FRESHDESK_API_KEY", "")

        if domain and api_key:
            return cls(domain=domain, api_key=api_key)

        # Try config files
        for path in paths:
            if path.exists():
                with open(path, "rb") as f:
                    data = tomllib.load(f)
                fd = data.get("freshdesk", {})
                domain = domain or fd.get("domain", "")
                api_key = api_key or fd.get("api_key", "")
                if domain and api_key:
                    return cls(domain=domain, api_key=api_key)

        raise ConfigError(
            "Freshdesk credentials not found.\n\n"
            "Set environment variables:\n"
            "  export FRESHDESK_DOMAIN=yourcompany.freshdesk.com\n"
            "  export FRESHDESK_API_KEY=your_api_key\n\n"
            f"Or create {paths[0]} with:\n"
            "  [freshdesk]\n"
            '  domain = "yourcompany.freshdesk.com"\n'
            '  api_key = "your_api_key"'
        )
