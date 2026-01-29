"""Abstract base class for API clients."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import httpx

from paper_ladder.config import get_config
from paper_ladder.models import Paper, SortBy
from paper_ladder.retry import RetryConfig, RetryHandler
from paper_ladder.utils import RateLimiter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from paper_ladder.config import Config

logger = logging.getLogger(__name__)

# API limits and capabilities per source
API_LIMITS: dict[str, dict] = {
    "arxiv": {
        "per_request": 2000,
        "offset_max": None,  # No hard limit
        "cursor_support": False,
        "note": "Rate limit: 1 request per 3 seconds",
    },
    "biorxiv": {
        "per_request": 100,
        "offset_max": None,  # No hard limit
        "cursor_support": True,
        "note": "Returns 100 results per page, paginate with cursor",
    },
    "core": {
        "per_request": 100,
        "offset_max": None,  # No hard limit
        "cursor_support": True,
        "note": "10,000 requests/day, free API key required",
    },
    "crossref": {
        "per_request": 1000,
        "offset_max": None,  # No hard limit, but cursor recommended
        "cursor_support": True,
        "note": "Cursor expires after 5 minutes",
    },
    "dblp": {
        "per_request": 1000,
        "offset_max": None,  # No hard limit
        "cursor_support": True,
        "note": "1 request per second recommended",
    },
    "doaj": {
        "per_request": 100,
        "offset_max": None,  # No hard limit
        "cursor_support": True,
        "note": "All content is open access",
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
    "google_scholar_scraper": {
        "per_request": 10,
        "offset_max": None,
        "cursor_support": False,
        "note": "Free scraping, 1 req/5s rate limit, may trigger CAPTCHA",
    },
    "medrxiv": {
        "per_request": 100,
        "offset_max": None,  # No hard limit
        "cursor_support": True,
        "note": "Returns 100 results per page, paginate with cursor",
    },
    "openalex": {
        "per_request": 200,
        "offset_max": 10000,
        "cursor_support": True,
        "note": "Use cursor pagination for >10,000 results",
    },
    "pubmed": {
        "per_request": 10000,
        "offset_max": 10000,
        "cursor_support": False,
        "note": "PubMed ESearch limited to first 10,000",
    },
    "semantic_scholar": {
        "per_request": 100,
        "offset_max": 1000,  # Updated Oct 2024: offset + limit ≤ 1,000
        "cursor_support": False,
        "note": "API limit: offset + limit ≤ 1,000 (reduced from 10,000)",
    },
    "wos": {
        "per_request": 100,
        "offset_max": 100000,
        "cursor_support": False,
        "note": "Requires institutional subscription",
    },
}

# Mapping from standard SortBy to API-specific sort parameters
# None means the sort option is not supported by that API
SORT_MAPPING: dict[str, dict[str, str | None]] = {
    "arxiv": {
        "relevance": "relevance",
        "citations": "_client_sort",  # arXiv doesn't have citation data
        "date": "submittedDate",
        "date_asc": "submittedDate",  # With sortOrder=ascending
    },
    "biorxiv": {
        # bioRxiv API doesn't support sorting - we do client-side sort
        "relevance": None,
        "citations": "_client_sort",
        "date": "_client_sort",
        "date_asc": "_client_sort",
    },
    "core": {
        "relevance": None,  # Default
        "citations": "citationCount",
        "date": "yearPublished",
        "date_asc": "yearPublished",  # Direction in sort object
    },
    "crossref": {
        "relevance": "relevance",
        "citations": "is-referenced-by-count",
        "date": "published",
        "date_asc": "published",  # With order=asc
    },
    "dblp": {
        # DBLP doesn't support server-side sorting
        "relevance": None,
        "citations": "_client_sort",  # DBLP doesn't have citation data
        "date": "_client_sort",
        "date_asc": "_client_sort",
    },
    "doaj": {
        "relevance": None,  # Default
        "citations": "_client_sort",  # DOAJ doesn't have citation data
        "date": "created_date",
        "date_asc": "created_date",  # With direction param
    },
    "elsevier": {
        "relevance": None,  # Default
        "citations": "-citedby-count",
        "date": "-coverDate",
        "date_asc": "+coverDate",
    },
    "google_scholar": {
        # Google Scholar only supports sorting in get_author_papers
        "relevance": None,
        "citations": None,  # Not supported in search()
        "date": None,
        "date_asc": None,
    },
    "google_scholar_scraper": {
        # Free scraper doesn't support sorting - use client-side sort
        "relevance": None,
        "citations": "_client_sort",
        "date": "_client_sort",
        "date_asc": "_client_sort",
    },
    "medrxiv": {
        # medRxiv API doesn't support sorting - we do client-side sort
        "relevance": None,
        "citations": "_client_sort",
        "date": "_client_sort",
        "date_asc": "_client_sort",
    },
    "openalex": {
        "relevance": "relevance_score",
        "citations": "cited_by_count:desc",
        "date": "publication_date:desc",
        "date_asc": "publication_date:asc",
    },
    "pubmed": {
        "relevance": "relevance",
        "citations": None,  # PubMed doesn't have citation sort
        "date": "pub_date",
        "date_asc": "pub_date",  # PubMed only has date, not direction
    },
    "semantic_scholar": {
        # Semantic Scholar API doesn't support sorting - we do client-side sort
        "relevance": None,
        "citations": "_client_sort",  # Special marker for client-side sorting
        "date": "_client_sort",
        "date_asc": "_client_sort",
    },
    "wos": {
        "relevance": "RS+D",
        "citations": "TC+D",
        "date": "PY+D",
        "date_asc": "PY+A",
    },
}


def sort_papers(papers: list[Paper], sort_by: SortBy) -> list[Paper]:
    """Sort papers client-side when API doesn't support sorting.

    Args:
        papers: List of papers to sort.
        sort_by: Sort criteria.

    Returns:
        Sorted list of papers.
    """
    if sort_by == SortBy.CITATIONS:
        return sorted(papers, key=lambda p: p.citations_count or 0, reverse=True)
    elif sort_by == SortBy.DATE:
        return sorted(papers, key=lambda p: p.year or 0, reverse=True)
    elif sort_by == SortBy.DATE_ASC:
        return sorted(papers, key=lambda p: p.year or 0, reverse=False)
    else:
        return papers  # relevance - keep original order


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
        self._retry_handler: RetryHandler | None = None

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

    @property
    def retry_handler(self) -> RetryHandler:
        """Get or create the retry handler."""
        if self._retry_handler is None:
            retry_settings = self.config.retry
            self._retry_handler = RetryHandler(
                RetryConfig(
                    max_retries=retry_settings.max_retries,
                    base_delay=retry_settings.base_delay,
                    max_delay=retry_settings.max_delay,
                    exponential_base=retry_settings.exponential_base,
                    jitter=retry_settings.jitter,
                )
            )
        return self._retry_handler

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
        """Make a rate-limited HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: URL path (relative to base_url).
            **kwargs: Additional arguments for httpx.

        Returns:
            HTTP response.

        Raises:
            httpx.HTTPStatusError: If the request fails after all retries.
        """

        async def do_request() -> httpx.Response:
            await self.rate_limiter.acquire()
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        return await self.retry_handler.execute(do_request)

    async def _get(self, url: str, **kwargs: object) -> httpx.Response:
        """Make a rate-limited GET request."""
        return await self._request("GET", url, **kwargs)

    async def _post(self, url: str, **kwargs: object) -> httpx.Response:
        """Make a rate-limited POST request."""
        return await self._request("POST", url, **kwargs)

    # =========================================================================
    # Sorting Support
    # =========================================================================

    def _get_sort_param(self, sort: SortBy | str | None) -> tuple[str | None, bool]:
        """Convert standard SortBy to API-specific sort parameter.

        Args:
            sort: SortBy enum, string value, or None.

        Returns:
            Tuple of (api_sort_param, needs_client_sort).
            - api_sort_param: The API-specific sort parameter, or None if not supported.
            - needs_client_sort: True if client-side sorting is needed.
        """
        if sort is None:
            return None, False

        # Convert to standard key
        if isinstance(sort, SortBy):
            sort_key = sort.value
        else:
            # Check if it's a SortBy value or a raw API-specific value
            try:
                sort_key = SortBy(sort).value
            except ValueError:
                # It's a raw API-specific value, pass through
                return str(sort), False

        # Look up in mapping
        source_mapping = SORT_MAPPING.get(self.name, {})
        api_param = source_mapping.get(sort_key)

        if api_param == "_client_sort":
            return None, True
        elif api_param is None:
            if sort_key != "relevance":
                logger.warning(f"[{self.name}] Sort by '{sort_key}' not supported, using relevance")
            return None, False
        else:
            return api_param, False

    def _apply_client_sort(self, papers: list[Paper], sort: SortBy | str | None) -> list[Paper]:
        """Apply client-side sorting if needed.

        Args:
            papers: List of papers.
            sort: Sort criteria.

        Returns:
            Sorted list of papers.
        """
        if sort is None:
            return papers

        # Convert to SortBy if possible
        if isinstance(sort, str):
            try:
                sort = SortBy(sort)
            except ValueError:
                return papers  # Raw API param, already sorted by API

        return sort_papers(papers, sort)

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
