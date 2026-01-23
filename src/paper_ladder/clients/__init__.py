"""API client adapters for Paper-Ladder."""

from paper_ladder.clients.base import BaseClient
from paper_ladder.clients.crossref import CrossrefClient
from paper_ladder.clients.elsevier import ElsevierClient
from paper_ladder.clients.google_scholar import GoogleScholarClient
from paper_ladder.clients.openalex import OpenAlexClient
from paper_ladder.clients.semantic_scholar import SemanticScholarClient

__all__ = [
    "BaseClient",
    "OpenAlexClient",
    "SemanticScholarClient",
    "ElsevierClient",
    "GoogleScholarClient",
    "CrossrefClient",
    "get_client",
    "CLIENTS",
]

# Registry of available clients
CLIENTS: dict[str, type[BaseClient]] = {
    "openalex": OpenAlexClient,
    "semantic_scholar": SemanticScholarClient,
    "elsevier": ElsevierClient,
    "google_scholar": GoogleScholarClient,
    "crossref": CrossrefClient,
}


def get_client(name: str) -> type[BaseClient]:
    """Get a client class by name.

    Args:
        name: Client name (openalex, semantic_scholar, elsevier, google_scholar).

    Returns:
        Client class.

    Raises:
        ValueError: If client name is not recognized.
    """
    if name not in CLIENTS:
        available = ", ".join(CLIENTS.keys())
        raise ValueError(f"Unknown client: {name}. Available: {available}")
    return CLIENTS[name]
