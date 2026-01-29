"""API client adapters for Paper-Ladder."""

from paper_ladder.clients.arxiv import ArxivClient
from paper_ladder.clients.base import BaseClient
from paper_ladder.clients.biorxiv import BiorxivClient
from paper_ladder.clients.core import COREClient
from paper_ladder.clients.crossref import CrossrefClient
from paper_ladder.clients.dblp import DBLPClient
from paper_ladder.clients.doaj import DOAJClient
from paper_ladder.clients.elsevier import ElsevierClient
from paper_ladder.clients.google_scholar import GoogleScholarClient
from paper_ladder.clients.google_scholar_scraper import GoogleScholarScraperClient
from paper_ladder.clients.medrxiv import MedrxivClient
from paper_ladder.clients.openalex import OpenAlexClient
from paper_ladder.clients.pubmed import PubMedClient
from paper_ladder.clients.semantic_scholar import SemanticScholarClient
from paper_ladder.clients.wos import WebOfScienceClient

__all__ = [
    "CLIENTS",
    "ArxivClient",
    "BaseClient",
    "BiorxivClient",
    "COREClient",
    "CrossrefClient",
    "DBLPClient",
    "DOAJClient",
    "ElsevierClient",
    "GoogleScholarClient",
    "GoogleScholarScraperClient",
    "MedrxivClient",
    "OpenAlexClient",
    "PubMedClient",
    "SemanticScholarClient",
    "WebOfScienceClient",
    "get_client",
]

# Registry of available clients
CLIENTS: dict[str, type[BaseClient]] = {
    "arxiv": ArxivClient,
    "biorxiv": BiorxivClient,
    "core": COREClient,
    "crossref": CrossrefClient,
    "dblp": DBLPClient,
    "doaj": DOAJClient,
    "elsevier": ElsevierClient,
    "google_scholar": GoogleScholarClient,
    "google_scholar_scraper": GoogleScholarScraperClient,
    "medrxiv": MedrxivClient,
    "openalex": OpenAlexClient,
    "pubmed": PubMedClient,
    "semantic_scholar": SemanticScholarClient,
    "wos": WebOfScienceClient,
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
