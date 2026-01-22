"""Paper-Ladder: Academic paper search and content extraction library."""

from paper_ladder.aggregator import Aggregator, get_paper, search
from paper_ladder.config import Config, get_config, load_config
from paper_ladder.extractors import get_extractor
from paper_ladder.models import Author, ExtractedContent, Paper, SearchResult

__version__ = "0.1.0"

__all__ = [
    # Core functions
    "search",
    "get_paper",
    "get_extractor",
    # Classes
    "Aggregator",
    "Config",
    "Paper",
    "Author",
    "ExtractedContent",
    "SearchResult",
    # Config
    "get_config",
    "load_config",
    # Version
    "__version__",
]
