"""Tests for retry mechanism."""

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from paper_ladder.retry import (
    RetryConfig,
    RetryHandler,
    is_retryable_error,
    retry_async,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_calculate_delay_exponential(self):
        """Test exponential delay calculation."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)

        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0

    def test_calculate_delay_max_cap(self):
        """Test delay is capped at max_delay."""
        config = RetryConfig(base_delay=10.0, max_delay=30.0, jitter=False)

        assert config.calculate_delay(0) == 10.0
        assert config.calculate_delay(1) == 20.0
        assert config.calculate_delay(2) == 30.0  # Capped
        assert config.calculate_delay(3) == 30.0  # Still capped

    def test_calculate_delay_with_jitter(self):
        """Test delay with jitter is variable."""
        config = RetryConfig(base_delay=1.0, jitter=True, jitter_factor=0.1)

        delays = [config.calculate_delay(0) for _ in range(10)]
        # Should have some variation
        assert len(set(delays)) > 1


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_retryable_status_codes(self):
        """Test retryable HTTP status codes."""
        from unittest.mock import MagicMock

        for status_code in [429, 500, 502, 503, 504]:
            response = MagicMock()
            response.status_code = status_code

            error = httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=response,
            )

            assert is_retryable_error(error) is True

    def test_non_retryable_status_codes(self):
        """Test non-retryable HTTP status codes."""
        from unittest.mock import MagicMock

        for status_code in [400, 401, 403, 404]:
            response = MagicMock()
            response.status_code = status_code

            error = httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=response,
            )

            assert is_retryable_error(error) is False

    def test_retryable_exceptions(self):
        """Test retryable exception types."""
        assert is_retryable_error(httpx.ConnectTimeout("timeout")) is True
        assert is_retryable_error(httpx.ReadTimeout("timeout")) is True
        assert is_retryable_error(httpx.ConnectError("error")) is True

    def test_non_retryable_exceptions(self):
        """Test non-retryable exception types."""
        assert is_retryable_error(ValueError("error")) is False
        assert is_retryable_error(RuntimeError("error")) is False


class TestRetryAsync:
    """Tests for retry_async function."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        """Test successful call on first try."""
        mock_func = AsyncMock(return_value="success")

        result = await retry_async(mock_func, RetryConfig(max_retries=3))

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        """Test successful call after retries."""
        mock_func = AsyncMock(
            side_effect=[
                httpx.ConnectError("error1"),
                httpx.ConnectError("error2"),
                "success",
            ]
        )
        config = RetryConfig(max_retries=3, base_delay=0.01)

        result = await retry_async(mock_func, config)

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries(self):
        """Test exception raised after all retries exhausted."""
        mock_func = AsyncMock(side_effect=httpx.ConnectError("persistent error"))
        config = RetryConfig(max_retries=2, base_delay=0.01)

        with pytest.raises(httpx.ConnectError):
            await retry_async(mock_func, config)

        assert mock_func.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_non_retryable_error_not_retried(self):
        """Test non-retryable errors are not retried."""
        mock_func = AsyncMock(side_effect=ValueError("not retryable"))
        config = RetryConfig(max_retries=3, base_delay=0.01)

        with pytest.raises(ValueError):
            await retry_async(mock_func, config)

        assert mock_func.call_count == 1


class TestRetryHandler:
    """Tests for RetryHandler class."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful execution."""
        handler = RetryHandler(RetryConfig(max_retries=3))
        mock_func = AsyncMock(return_value="result")

        result = await handler.execute(mock_func)

        assert result == "result"

    @pytest.mark.asyncio
    async def test_execute_with_args(self):
        """Test execution with arguments."""
        handler = RetryHandler(RetryConfig(max_retries=3))

        async def add(a, b):
            return a + b

        result = await handler.execute(add, 1, 2)

        assert result == 3

    @pytest.mark.asyncio
    async def test_execute_with_kwargs(self):
        """Test execution with keyword arguments."""
        handler = RetryHandler(RetryConfig(max_retries=3))

        async def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = await handler.execute(greet, "World", greeting="Hi")

        assert result == "Hi, World!"
