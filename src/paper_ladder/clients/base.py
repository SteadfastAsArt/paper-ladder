"""Abstract base class for API clients."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import httpx

from paper_ladder.config import get_config
from paper_ladder.models import Paper
from paper_ladder.utils import RateLimiter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from paper_ladder.config import Config

logger = logging.getLogger(__name__)

# API limits and capabilities per source
API_LIMITS: dict[str, dict] = {
    "openalex": {
        "per_request": 200,
        "offset_max": 10000,
        "cursor_support": True,
        "note": "Use cursor pagination for >10,000 results",
    },
    "semantic_scholar": {
        "per_request": 100,
        "offset_max": 1000,  # Updated Oct 2024: offset + limit ≤ 1,000
        "cursor_support": False,
        "note": "API limit: offset + limit ≤ 1,000 (reduced from 10,000)",
    },
    "crossref": {
        "per_request": 1000,
        "offset_max": None,  # No hard limit, but cursor recommended
        "cursor_support": True,
        "note": "Cursor expires after 5 minutes",
    },
    "elsevier": {
        "per_request": 200,
        "offset_max": 5000,
        "cursor_support": True,
        "note": "Weekly limit: 20,000 downloads",
    },
    "google_scholar": {
        "per_request": 20,
        "offset_max": None,
        "cursor_support": False,
        "note": "Paid API (~$0.015/request)",
    },
    "pubmed": {
        "per_request": 10000,
        "offset_max": 10000,
        "cursor_support": False,
        "note": "PubMed ESearch limited to first 10,000",
    },
    "wos": {
        "per_request": 100,
        "offset_max": 100000,
        "cursor_support": False,
        "note": "Requires institutional subscription",
    },
}


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
            rate_limit = getattr(self.config.rate_limits, self.name, 10)
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

    # =========================================================================
    # Pagination Support
    # =========================================================================

    @property
    def api_limits(self) -> dict:
        """Get API limits for this client."""
        return API_LIMITS.get(self.name, {})

    @property
    def max_pagination_limit(self) -> int:
        """Get the configured maximum pagination limit for this source."""
        return getattr(self.config.pagination_limits, self.name, 1000)

    def _warn_pagination_limit(self, requested: int, actual_max: int) -> None:
        """Log a warning about pagination limits."""
        limits = self.api_limits
        logger.warning(
            f"[{self.name}] Requested {requested} results, but limited to {actual_max}. "
            f"API limit: {limits.get('note', 'N/A')}"
        )

    async def search_all(
        self,
        query: str,
        max_results: int | None = None,
        **kwargs: object,
    ) -> list[Paper]:
        """Search with automatic pagination up to the configured limit.

        This method handles pagination automatically, using cursor pagination
        when available and falling back to offset pagination otherwise.

        Args:
            query: Search query string.
            max_results: Maximum number of results to retrieve. If None, uses
                        the configured limit for this source.
            **kwargs: Additional parameters passed to search().

        Returns:
            List of Paper objects.
        """
        # Determine effective limit
        config_limit = self.max_pagination_limit
        api_offset_max = self.api_limits.get("offset_max")
        per_request = self.api_limits.get("per_request", 100)

        effective_limit = config_limit if max_results is None else min(max_results, config_limit)

        # Check if we need cursor pagination
        if api_offset_max and effective_limit > api_offset_max:
            if self.api_limits.get("cursor_support") and hasattr(self, "search_with_cursor"):
                logger.info(
                    f"[{self.name}] Requested {effective_limit} results exceeds "
                    f"offset limit ({api_offset_max}). Using cursor pagination."
                )
                papers = []
                async for paper in self.search_with_cursor(
                    query, max_results=effective_limit, **kwargs
                ):
                    papers.append(paper)
                return papers
            else:
                # No cursor support, warn and limit
                self._warn_pagination_limit(effective_limit, api_offset_max)
                effective_limit = api_offset_max

        # Use offset pagination
        papers: list[Paper] = []
        offset = 0

        while len(papers) < effective_limit:
            remaining = effective_limit - len(papers)
            limit = min(per_request, remaining)

            batch = await self.search(query, limit=limit, offset=offset, **kwargs)
            if not batch:
                break

            papers.extend(batch)
            offset += len(batch)

            # If we got fewer results than requested, no more results available
            if len(batch) < limit:
                break

        return papers

    async def search_with_cursor(
        self,
        query: str,
        max_results: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[Paper]:
        """Search using cursor pagination (for sources that support it).

        Override this method in subclasses that support cursor pagination.

        Args:
            query: Search query string.
            max_results: Maximum number of results to retrieve.
            **kwargs: Additional parameters.

        Yields:
            Paper objects.

        Raises:
            NotImplementedError: If cursor pagination is not supported.
        """
        raise NotImplementedError(
            f"{self.name} does not support cursor pagination. Use search() or search_all() instead."
        )
        # Make this an async generator
        yield  # type: ignore[misc]
