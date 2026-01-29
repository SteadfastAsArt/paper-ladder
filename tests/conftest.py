"""Shared test fixtures for Paper-Ladder tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from paper_ladder.models import Author, Paper


# ============================================================================
# Sample Paper Fixtures
# ============================================================================


@pytest.fixture
def sample_paper() -> Paper:
    """A sample Paper object for testing."""
    return Paper(
        title="Deep Learning",
        authors=["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
        abstract="Deep learning allows computational models that are composed of multiple processing layers to learn representations of data with multiple levels of abstraction.",
        doi="10.1038/nature14539",
        year=2015,
        journal="Nature",
        url="https://www.nature.com/articles/nature14539",
        pdf_url="https://www.nature.com/articles/nature14539.pdf",
        source="openalex",
        citations_count=77000,
        references_count=89,
        open_access=False,
        keywords=["deep learning", "neural networks", "machine learning"],
    )


@pytest.fixture
def sample_paper_minimal() -> Paper:
    """A minimal Paper object with only required fields."""
    return Paper(
        title="Test Paper",
        source="test",
    )


@pytest.fixture
def sample_paper_arxiv() -> Paper:
    """A sample arXiv paper."""
    return Paper(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
        abstract="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
        doi="10.48550/arXiv.1706.03762",
        year=2017,
        url="https://arxiv.org/abs/1706.03762",
        pdf_url="https://arxiv.org/pdf/1706.03762.pdf",
        source="arxiv",
        citations_count=120000,
        open_access=True,
        keywords=["transformers", "attention", "NLP"],
    )


@pytest.fixture
def sample_papers(sample_paper: Paper, sample_paper_arxiv: Paper) -> list[Paper]:
    """A list of sample papers."""
    return [sample_paper, sample_paper_arxiv]


@pytest.fixture
def sample_author() -> Author:
    """A sample Author object."""
    return Author(
        name="Geoffrey Hinton",
        source_id="A123456789",
        source="openalex",
        affiliations=["University of Toronto", "Google"],
        orcid="0000-0001-2345-6789",
        url="https://www.cs.toronto.edu/~hinton/",
        paper_count=350,
        citation_count=500000,
        h_index=180,
    )


# ============================================================================
# Mock HTTP Response Fixtures
# ============================================================================


@pytest.fixture
def mock_httpx_response():
    """Factory for creating mock httpx responses."""

    def _make_response(
        status_code: int = 200,
        json_data: dict[str, Any] | None = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> MagicMock:
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.text = text
        response.content = text.encode() if text else b""
        response.headers = headers or {}
        response.raise_for_status = MagicMock()

        if status_code >= 400:
            from httpx import HTTPStatusError, Request, Response

            mock_request = MagicMock(spec=Request)
            response.raise_for_status.side_effect = HTTPStatusError(
                message=f"HTTP {status_code}",
                request=mock_request,
                response=response,
            )

        return response

    return _make_response


@pytest.fixture
def mock_async_client(mock_httpx_response):
    """Factory for creating mock async HTTP clients."""

    def _make_client(responses: list[dict[str, Any]] | None = None) -> AsyncMock:
        client = AsyncMock()
        client.get = AsyncMock()
        client.post = AsyncMock()
        client.request = AsyncMock()

        if responses:
            mock_responses = [mock_httpx_response(**r) for r in responses]
            client.get.side_effect = mock_responses
            client.post.side_effect = mock_responses
            client.request.side_effect = mock_responses

        return client

    return _make_client


# ============================================================================
# Mock API Response Data
# ============================================================================


MOCK_OPENALEX_WORK = {
    "id": "https://openalex.org/W2100837269",
    "doi": "https://doi.org/10.1038/nature14539",
    "title": "Deep learning",
    "display_name": "Deep learning",
    "publication_year": 2015,
    "publication_date": "2015-05-28",
    "authorships": [
        {"author": {"display_name": "Yann LeCun"}},
        {"author": {"display_name": "Yoshua Bengio"}},
        {"author": {"display_name": "Geoffrey E. Hinton"}},
    ],
    "host_venue": {
        "display_name": "Nature",
    },
    "open_access": {"is_oa": False},
    "cited_by_count": 77000,
    "abstract_inverted_index": {
        "Deep": [0],
        "learning": [1],
        "allows": [2],
    },
}

MOCK_SEMANTIC_SCHOLAR_PAPER = {
    "paperId": "f3c70c7b2f82e3b00e3c0e3a7f24d8e9c7e3c9a3",
    "title": "Deep learning",
    "authors": [
        {"name": "Yann LeCun"},
        {"name": "Yoshua Bengio"},
        {"name": "Geoffrey E. Hinton"},
    ],
    "abstract": "Deep learning allows computational models...",
    "year": 2015,
    "venue": "Nature",
    "externalIds": {"DOI": "10.1038/nature14539"},
    "citationCount": 162000,
    "referenceCount": 89,
    "isOpenAccess": False,
}

MOCK_CROSSREF_WORK = {
    "DOI": "10.1038/nature14539",
    "title": ["Deep learning"],
    "author": [
        {"given": "Yann", "family": "LeCun"},
        {"given": "Yoshua", "family": "Bengio"},
        {"given": "Geoffrey", "family": "Hinton"},
    ],
    "published-print": {"date-parts": [[2015, 5, 28]]},
    "container-title": ["Nature"],
    "is-referenced-by-count": 68500,
    "reference-count": 89,
}

MOCK_DBLP_PUBLICATION = {
    "hit": [
        {
            "info": {
                "title": "Deep Learning.",
                "authors": {
                    "author": [
                        {"text": "Yann LeCun"},
                        {"text": "Yoshua Bengio"},
                        {"text": "Geoffrey E. Hinton"},
                    ]
                },
                "year": "2015",
                "venue": "Nature",
                "doi": "10.1038/nature14539",
                "url": "https://doi.org/10.1038/nature14539",
            }
        }
    ]
}

MOCK_DOAJ_ARTICLE = {
    "id": "12345678",
    "bibjson": {
        "title": "Open Access Research",
        "author": [{"name": "Test Author"}],
        "abstract": "This is an open access paper.",
        "year": "2023",
        "journal": {"title": "Open Access Journal"},
        "identifier": [{"type": "doi", "id": "10.1234/oa.2023.001"}],
        "link": [{"type": "fulltext", "url": "https://example.com/article.pdf"}],
        "keywords": ["open access", "research"],
        "subject": [{"term": "Science"}],
    },
}

MOCK_CORE_WORK = {
    "id": 12345678,
    "title": "Open Access Research Paper",
    "authors": [{"name": "Test Author"}],
    "abstract": "This paper discusses open access...",
    "yearPublished": 2023,
    "doi": "10.1234/core.2023.001",
    "downloadUrl": "https://example.com/paper.pdf",
    "citationCount": 25,
}


@pytest.fixture
def mock_openalex_response() -> dict[str, Any]:
    """Mock OpenAlex API response."""
    return {"meta": {"count": 1}, "results": [MOCK_OPENALEX_WORK]}


@pytest.fixture
def mock_semantic_scholar_response() -> dict[str, Any]:
    """Mock Semantic Scholar API response."""
    return {"total": 1, "data": [MOCK_SEMANTIC_SCHOLAR_PAPER]}


@pytest.fixture
def mock_crossref_response() -> dict[str, Any]:
    """Mock Crossref API response."""
    return {"status": "ok", "message": {"items": [MOCK_CROSSREF_WORK]}}


@pytest.fixture
def mock_dblp_response() -> dict[str, Any]:
    """Mock DBLP API response."""
    return {"result": {"hits": MOCK_DBLP_PUBLICATION}}


@pytest.fixture
def mock_doaj_response() -> dict[str, Any]:
    """Mock DOAJ API response."""
    return {"results": [MOCK_DOAJ_ARTICLE]}


@pytest.fixture
def mock_core_response() -> dict[str, Any]:
    """Mock CORE API response."""
    return {"results": [MOCK_CORE_WORK]}


# ============================================================================
# Test Client Fixtures
# ============================================================================


@pytest.fixture
def mock_base_client():
    """Create a mock BaseClient for testing."""
    from paper_ladder.clients.base import BaseClient

    class MockClient(BaseClient):
        name = "mock"
        base_url = "https://api.mock.example"

        async def search(self, query, limit=10, offset=0, **kwargs):
            return []

        async def get_paper(self, identifier):
            return None

    return MockClient()


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def test_config():
    """Create a test configuration."""
    from paper_ladder.config import Config

    return Config(
        elsevier_api_key="test-elsevier-key",
        serpapi_api_key="test-serpapi-key",
        semantic_scholar_api_key="test-s2-key",
        core_api_key="test-core-key",
        crossref_mailto="test@example.com",
    )


# ============================================================================
# Citation Network Fixtures
# ============================================================================


@pytest.fixture
def sample_citation_graph():
    """Create a sample citation graph for testing."""
    from paper_ladder.analysis.network import CitationEdge, CitationGraph, CitationNode

    graph = CitationGraph(seed_paper_id="paper1")

    # Add nodes
    graph.add_node(
        CitationNode(
            paper_id="paper1",
            doi="10.1234/paper1",
            title="Seed Paper",
            year=2020,
            citations_count=100,
            depth=0,
        )
    )
    graph.add_node(
        CitationNode(
            paper_id="paper2",
            doi="10.1234/paper2",
            title="Citing Paper 1",
            year=2021,
            citations_count=50,
            depth=1,
        )
    )
    graph.add_node(
        CitationNode(
            paper_id="paper3",
            doi="10.1234/paper3",
            title="Citing Paper 2",
            year=2022,
            citations_count=25,
            depth=1,
        )
    )
    graph.add_node(
        CitationNode(
            paper_id="paper4",
            doi="10.1234/paper4",
            title="Reference Paper",
            year=2018,
            citations_count=200,
            depth=1,
        )
    )

    # Add edges
    graph.add_edge(CitationEdge(citing_id="paper2", cited_id="paper1"))
    graph.add_edge(CitationEdge(citing_id="paper3", cited_id="paper1"))
    graph.add_edge(CitationEdge(citing_id="paper1", cited_id="paper4"))
    graph.add_edge(CitationEdge(citing_id="paper2", cited_id="paper4"))

    return graph


# ============================================================================
# Async Test Helpers
# ============================================================================


@pytest.fixture
def anyio_backend():
    """Backend for anyio async tests."""
    return "asyncio"
