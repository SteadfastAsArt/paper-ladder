"""Retry mechanism with exponential backoff for Paper-Ladder."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

import httpx

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = logging.getLogger(__name__)

# Type variable for the return type of the decorated function
T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1  # +/- 10% jitter

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Args:
            attempt: The current attempt number (0-indexed).

        Returns:
            Delay in seconds before the next retry.
        """
        # Exponential backoff: base_delay * (exponential_base ^ attempt)
        delay = self.base_delay * (self.exponential_base**attempt)

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter if enabled
        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


# Status codes that should trigger a retry
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset(
    {
        429,  # Too Many Requests (rate limited)
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
        520,  # Cloudflare: Unknown Error
        521,  # Cloudflare: Web Server Is Down
        522,  # Cloudflare: Connection Timed Out
        523,  # Cloudflare: Origin Is Unreachable
        524,  # Cloudflare: A Timeout Occurred
    }
)

# Exception types that should trigger a retry
RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.NetworkError,
)


def is_retryable_error(error: Exception) -> bool:
    """Check if an error should trigger a retry.

    Args:
        error: The exception that occurred.

    Returns:
        True if the error should trigger a retry.
    """
    # Check for retryable exceptions
    if isinstance(error, RETRYABLE_EXCEPTIONS):
        return True

    # Check for HTTP status errors with retryable status codes
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in RETRYABLE_STATUS_CODES

    return False


def get_retry_after(error: Exception) -> float | None:
    """Extract Retry-After header value from an HTTP error.

    Args:
        error: The exception that occurred.

    Returns:
        Retry-After value in seconds, or None if not present.
    """
    if not isinstance(error, httpx.HTTPStatusError):
        return None

    retry_after = error.response.headers.get("Retry-After")
    if retry_after is None:
        return None

    try:
        # Try to parse as integer (seconds)
        return float(retry_after)
    except ValueError:
        # Could be a date string, but we'll ignore that for simplicity
        return None


async def retry_async(
    func: Callable[..., Awaitable[T]],
    config: RetryConfig | None = None,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Execute an async function with retry logic.

    Args:
        func: The async function to execute.
        config: Retry configuration. Uses defaults if None.
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.

    Returns:
        The result of the function.

    Raises:
        The last exception if all retries are exhausted.
    """
    config = config or RetryConfig()
    last_error: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except Exception as e:
            last_error = e

            # Check if we should retry
            if not is_retryable_error(e):
                raise

            # Check if we've exhausted retries
            if attempt >= config.max_retries:
                logger.warning(
                    f"All {config.max_retries} retries exhausted for {func.__name__}"
                )
                raise

            # Calculate delay
            delay = config.calculate_delay(attempt)

            # Check for Retry-After header
            retry_after = get_retry_after(e)
            if retry_after is not None:
                delay = max(delay, retry_after)
                delay = min(delay, config.max_delay)  # Still cap at max_delay

            # Log the retry
            error_info = str(e)
            if isinstance(e, httpx.HTTPStatusError):
                error_info = f"HTTP {e.response.status_code}"

            logger.info(
                f"Retry {attempt + 1}/{config.max_retries} for {func.__name__} "
                f"after {error_info}, waiting {delay:.2f}s"
            )

            await asyncio.sleep(delay)

    # This should never be reached, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Retry loop completed without result or error")


def with_retry(config: RetryConfig | None = None) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to add retry logic to an async function.

    Args:
        config: Retry configuration. Uses defaults if None.

    Returns:
        Decorator function.

    Example:
        @with_retry(RetryConfig(max_retries=5))
        async def fetch_data():
            ...
    """
    config = config or RetryConfig()

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await retry_async(func, config, *args, **kwargs)

        return wrapper

    return decorator


class RetryHandler:
    """A reusable retry handler for HTTP requests.

    This class can be used by clients to add retry logic to their requests.
    """

    def __init__(self, config: RetryConfig | None = None):
        """Initialize the retry handler.

        Args:
            config: Retry configuration.
        """
        self.config = config or RetryConfig()

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a function with retry logic.

        Args:
            func: The async function to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            The function result.
        """
        return await retry_async(func, self.config, *args, **kwargs)
