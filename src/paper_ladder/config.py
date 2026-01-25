"""Configuration loader for Paper-Ladder."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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


class PaginationLimits(BaseModel):
    """Maximum results per source for auto-pagination.

    These limits control how many results search_all() will retrieve.
    For sources with cursor support, higher limits are possible.
    """

    openalex: int = 10000  # Cursor pagination allows unlimited, but default limit
    semantic_scholar: int = 1000  # API hard limit (offset + limit ≤ 1,000)
    crossref: int = 10000  # Cursor pagination allows unlimited
    elsevier: int = 5000  # Cursor pagination can bypass 5,000 offset limit
    google_scholar: int = 100  # Paid API, limit to control costs
    pubmed: int = 10000  # ESearch hard limit
    wos: int = 10000  # Based on subscription tier


class Config(BaseModel):
    """Main configuration model."""

    # API Keys
    elsevier_api_key: str | None = None
    serpapi_api_key: str | None = None
    semantic_scholar_api_key: str | None = None
    pubmed_api_key: str | None = None  # Optional, for higher rate limits (10 req/s vs 3 req/s)
    wos_api_key: str | None = None  # Required for Web of Science API
    openalex_api_key: str | None = None  # Free API key for 100k credits/day

    # Crossref polite pool email (highly recommended for better rate limits)
    crossref_mailto: str | None = None

    # Proxy settings
    proxy: ProxyConfig | None = None

    # Default sources
    default_sources: list[str] = Field(default_factory=lambda: ["openalex", "semantic_scholar"])

    # Request settings
    request_timeout: int = 30
    max_retries: int = 3

    # Rate limiting
    rate_limits: RateLimits = Field(default_factory=RateLimits)

    # Pagination limits (max results per source for search_all)
    pagination_limits: PaginationLimits = Field(default_factory=PaginationLimits)

    # Enable auto-pagination in search_all()
    auto_pagination: bool = True

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


def find_config_file() -> Path | None:
    """Find configuration file by searching multiple locations.

    Search order (first found wins):
    1. PAPER_LADDER_CONFIG environment variable
    2. Current working directory: ./config.yaml
    3. User home directory: ~/.paper-ladder/config.yaml

    Returns:
        Path to config file if found, None otherwise.
    """
    # 1. Environment variable
    env_path = os.environ.get("PAPER_LADDER_CONFIG")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists():
            return path
        logger.warning(f"PAPER_LADDER_CONFIG path does not exist: {env_path}")

    # 2. Current working directory
    cwd_config = Path("config.yaml")
    if cwd_config.exists():
        return cwd_config.resolve()

    # 3. User home directory
    home_config = Path.home() / ".paper-ladder" / "config.yaml"
    if home_config.exists():
        return home_config

    return None


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, searches for config.yaml
                    in multiple locations (see find_config_file).

    Returns:
        Config object with loaded settings.
    """
    global _config

    config_path = Path(config_path).expanduser() if config_path is not None else find_config_file()

    if config_path is not None and config_path.exists():
        logger.debug(f"Loading configuration from: {config_path}")
        with open(config_path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        _config = Config(**data)
    else:
        logger.debug("No configuration file found, using defaults")
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
