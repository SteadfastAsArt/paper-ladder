"""Content extractors for Paper-Ladder."""

from paper_ladder.extractors.base import BaseExtractor
from paper_ladder.extractors.html_extractor import HTMLExtractor
from paper_ladder.extractors.pdf_extractor import PDFExtractor

__all__ = [
    "BaseExtractor",
    "PDFExtractor",
    "HTMLExtractor",
    "get_extractor",
    "EXTRACTORS",
]

# Registry of available extractors
EXTRACTORS: dict[str, type[BaseExtractor]] = {
    "pdf": PDFExtractor,
    "html": HTMLExtractor,
}


def get_extractor(source: str) -> BaseExtractor:
    """Get an appropriate extractor for the given source.

    Args:
        source: URL or file path.

    Returns:
        Extractor instance that can handle the source.

    Raises:
        ValueError: If no extractor can handle the source.
    """
    for extractor_class in EXTRACTORS.values():
        extractor = extractor_class()
        if extractor.can_handle(source):
            return extractor

    raise ValueError(f"No extractor found for: {source}")
