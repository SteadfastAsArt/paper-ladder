"""Utility functions for Paper-Ladder."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar
from urllib.parse import urlparse

T = TypeVar("T")


def normalize_doi(doi: str | None) -> str | None:
    """Normalize a DOI string.

    Args:
        doi: DOI string in various formats.

    Returns:
        Normalized DOI (lowercase, without URL prefix) or None.
    """
    if not doi:
        return None

    doi = doi.strip().lower()

    # Remove common URL prefixes
    prefixes = [
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ]
    for prefix in prefixes:
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
            break

    return doi if doi else None


def normalize_title(title: str) -> str:
    """Normalize a paper title for comparison.

    Args:
        title: Paper title.

    Returns:
        Normalized title (lowercase, stripped of extra whitespace).
    """
    title = title.lower().strip()
    title = re.sub(r"\s+", " ", title)
    return title


def extract_year_from_date(date_str: str | None) -> int | None:
    """Extract year from a date string.

    Args:
        date_str: Date string in various formats (YYYY, YYYY-MM-DD, etc.).

    Returns:
        Year as integer or None.
    """
    if not date_str:
        return None

    # Try to find a 4-digit year
    match = re.search(r"\b(19|20)\d{2}\b", date_str)
    if match:
        return int(match.group())
    return None


def is_valid_url(url: str | None) -> bool:
    """Check if a string is a valid URL.

    Args:
        url: URL string to validate.

    Returns:
        True if valid URL, False otherwise.
    """
    if not url:
        return False
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def is_pdf_url(url: str | None) -> bool:
    """Check if a URL likely points to a PDF.

    Args:
        url: URL to check.

    Returns:
        True if URL appears to be a PDF link.
    """
    if not url:
        return False
    url_lower = url.lower()
    return url_lower.endswith(".pdf") or "/pdf/" in url_lower


class RateLimiter:
    """Simple rate limiter for API requests."""

    def __init__(self, requests_per_second: float, name: str = ""):
        """Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second.
            name: Name for logging (e.g., client name).
        """
        self.min_interval = 1.0 / requests_per_second
        self.requests_per_second = requests_per_second
        self.last_request_time = 0.0
        self.name = name
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger(__name__)

    async def acquire(self) -> None:
        """Wait until a request can be made."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                if wait_time > 0.1:  # Only log if waiting more than 100ms
                    self._logger.debug(
                        f"[{self.name}] Rate limit: waiting {wait_time:.2f}s"
                    )
                await asyncio.sleep(wait_time)
            self.last_request_time = time.monotonic()


def retry_async(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying async functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries in seconds.
        backoff: Multiplier for delay after each retry.
        exceptions: Tuple of exception types to catch and retry.

    Returns:
        Decorated function.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        break

            raise last_exception  # type: ignore

        return wrapper  # type: ignore

    return decorator


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to a maximum length.

    Args:
        text: Text to truncate.
        max_length: Maximum length including suffix.
        suffix: Suffix to append if truncated.

    Returns:
        Truncated text.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def clean_html_text(text: str | None) -> str:
    """Clean text that may contain HTML entities or tags.

    Args:
        text: Text to clean.

    Returns:
        Cleaned text.
    """
    if not text:
        return ""

    import html

    # Decode HTML entities
    text = html.unescape(text)
    # Remove any remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text
