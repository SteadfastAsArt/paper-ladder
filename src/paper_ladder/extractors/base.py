"""Abstract base class for content extractors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from paper_ladder.config import Config, get_config
from paper_ladder.models import ExtractedContent


class BaseExtractor(ABC):
    """Abstract base class for content extractors."""

    name: str = "base"
    supported_extensions: list[str] = []

    def __init__(self, config: Config | None = None):
        """Initialize the extractor.

        Args:
            config: Configuration object. If None, loads from default location.
        """
        self.config = config or get_config()

    @abstractmethod
    async def extract(
        self,
        source: str | Path,
        **kwargs: object,
    ) -> ExtractedContent:
        """Extract content from a source.

        Args:
            source: URL or file path to extract from.
            **kwargs: Additional extractor-specific parameters.

        Returns:
            ExtractedContent with markdown, metadata, figures, and tables.
        """
        ...

    @abstractmethod
    def can_handle(self, source: str | Path) -> bool:
        """Check if this extractor can handle the given source.

        Args:
            source: URL or file path to check.

        Returns:
            True if this extractor can handle the source.
        """
        ...

    def _get_extension(self, source: str | Path) -> str:
        """Get the file extension from a source.

        Args:
            source: URL or file path.

        Returns:
            Lowercase file extension without dot, or empty string.
        """
        source_str = str(source).lower()
        # Handle URLs with query parameters
        source_str = source_str.split("?")[0]
        if "." in source_str:
            return source_str.rsplit(".", 1)[-1]
        return ""
