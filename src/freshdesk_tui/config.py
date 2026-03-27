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


@dataclass
class Config:
    domain: str
    api_key: str

    @classmethod
    def load(cls) -> Config:
        # Environment variables take precedence
        domain = os.environ.get("FRESHDESK_DOMAIN", "")
        api_key = os.environ.get("FRESHDESK_API_KEY", "")

        if domain and api_key:
            return cls(domain=domain, api_key=api_key)

        # Try config files
        for path in CONFIG_PATHS:
            if path.exists():
                with open(path, "rb") as f:
                    data = tomllib.load(f)
                fd = data.get("freshdesk", {})
                domain = domain or fd.get("domain", "")
                api_key = api_key or fd.get("api_key", "")
                if domain and api_key:
                    return cls(domain=domain, api_key=api_key)

        print(
            "Error: Freshdesk credentials not found.\n\n"
            "Set environment variables:\n"
            "  export FRESHDESK_DOMAIN=yourcompany.freshdesk.com\n"
            "  export FRESHDESK_API_KEY=your_api_key\n\n"
            f"Or create {CONFIG_PATHS[0]} with:\n"
            "  [freshdesk]\n"
            '  domain = "yourcompany.freshdesk.com"\n'
            '  api_key = "your_api_key"\n',
            file=sys.stderr,
        )
        sys.exit(1)
