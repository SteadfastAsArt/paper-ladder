"""Abstract base class for API clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import httpx

from paper_ladder.config import get_config
from paper_ladder.models import Paper
from paper_ladder.utils import RateLimiter

if TYPE_CHECKING:
    from paper_ladder.config import Config


class BaseClient(ABC):
    """Abstract base class for academic API clients."""

    name: str = "base"
    base_url: str = ""

    def __init__(self, config: Config | None = None):
        """Initialize the client.

        Args:
            config: Configuration object. If None, loads from default location.
        """
        self.config = config or get_config()
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter: RateLimiter | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            kwargs: dict[str, object] = {
                "base_url": self.base_url,
                "timeout": self.config.request_timeout,
            }
            proxy = self.config.get_proxy_url()
            if proxy:
                kwargs["proxy"] = proxy
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    @property
    def rate_limiter(self) -> RateLimiter:
        """Get or create the rate limiter."""
        if self._rate_limiter is None:
            rate_limit = getattr(
                self.config.rate_limits, self.name, 10
            )
            self._rate_limiter = RateLimiter(rate_limit)
        return self._rate_limiter

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> BaseClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers matching the query.

        Args:
            query: Search query string.
            limit: Maximum number of results to return.
            offset: Number of results to skip.
            **kwargs: Additional source-specific parameters.

        Returns:
            List of Paper objects.
        """
        ...

    @abstractmethod
    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a single paper by identifier (DOI, ID, etc.).

        Args:
            identifier: Paper identifier (DOI, source-specific ID, etc.).

        Returns:
            Paper object if found, None otherwise.
        """
        ...

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        """Make a rate-limited HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: URL path (relative to base_url).
            **kwargs: Additional arguments for httpx.

        Returns:
            HTTP response.
        """
        await self.rate_limiter.acquire()
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    async def _get(self, url: str, **kwargs: object) -> httpx.Response:
        """Make a rate-limited GET request."""
        return await self._request("GET", url, **kwargs)

    async def _post(self, url: str, **kwargs: object) -> httpx.Response:
        """Make a rate-limited POST request."""
        return await self._request("POST", url, **kwargs)
