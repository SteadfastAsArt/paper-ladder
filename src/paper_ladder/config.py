"""Configuration loader for Paper-Ladder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    http: str | None = None
    https: str | None = None


class RateLimits(BaseModel):
    """Rate limits per source (requests per second)."""

    openalex: float = 10
    semantic_scholar: float = 10
    elsevier: float = 5
    google_scholar: float = 1
    crossref: float = 50  # Polite pool allows higher rates
    pubmed: float = 3  # 3 req/s without key, 10 req/s with key
    wos: float = 2  # 2 req/s per Clarivate guidelines


class Config(BaseModel):
    """Main configuration model."""

    # API Keys
    elsevier_api_key: str | None = None
    serpapi_api_key: str | None = None
    semantic_scholar_api_key: str | None = None
    pubmed_api_key: str | None = None  # Optional, for higher rate limits (10 req/s vs 3 req/s)
    wos_api_key: str | None = None  # Required for Web of Science API
    openalex_api_key: str | None = None  # Free API key for 100k credits/day

    # Proxy settings
    proxy: ProxyConfig | None = None

    # Default sources
    default_sources: list[str] = Field(default_factory=lambda: ["openalex", "semantic_scholar"])

    # Request settings
    request_timeout: int = 30
    max_retries: int = 3

    # Rate limiting
    rate_limits: RateLimits = Field(default_factory=RateLimits)

    # Output settings
    output_dir: str = "./output"

    def get_proxy_dict(self) -> dict[str, str] | None:
        """Get proxy configuration as a dict for httpx."""
        if not self.proxy:
            return None
        proxies = {}
        if self.proxy.http:
            proxies["http://"] = self.proxy.http
        if self.proxy.https:
            proxies["https://"] = self.proxy.https
        return proxies if proxies else None

    def get_proxy_url(self) -> str | None:
        """Get proxy URL for httpx (prefers https, falls back to http)."""
        if not self.proxy:
            return None
        return self.proxy.https or self.proxy.http


_config: Config | None = None


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, looks for config.yaml
                    in current directory.

    Returns:
        Config object with loaded settings.
    """
    global _config

    if config_path is None:
        config_path = Path("config.yaml")
    else:
        config_path = Path(config_path)

    if config_path.exists():
        with open(config_path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        _config = Config(**data)
    else:
        _config = Config()

    return _config


def get_config() -> Config:
    """Get the current configuration, loading if necessary."""
    global _config
    if _config is None:
        return load_config()
    return _config


def reset_config() -> None:
    """Reset the cached configuration."""
    global _config
    _config = None
