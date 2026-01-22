"""Tests for OpenAlex client."""

import pytest

from paper_ladder.clients.openalex import OpenAlexClient


@pytest.fixture
def client():
    """Create OpenAlex client."""
    return OpenAlexClient()


class TestOpenAlexClient:
    """Tests for OpenAlexClient."""

    def test_client_name(self, client):
        """Test client has correct name."""
        assert client.name == "openalex"

    def test_client_base_url(self, client):
        """Test client has correct base URL."""
        assert client.base_url == "https://api.openalex.org"

    def test_reconstruct_abstract(self, client):
        """Test abstract reconstruction from inverted index."""
        inverted_index = {
            "Hello": [0],
            "world": [1],
            "this": [2],
            "is": [3],
            "a": [4],
            "test": [5],
        }
        result = client._reconstruct_abstract(inverted_index)
        assert result == "Hello world this is a test"

    def test_reconstruct_abstract_empty(self, client):
        """Test abstract reconstruction with empty index."""
        assert client._reconstruct_abstract({}) == ""
        assert client._reconstruct_abstract(None) == ""

    def test_parse_work_empty(self, client):
        """Test parsing empty work data."""
        assert client._parse_work({}) is None
        assert client._parse_work(None) is None

    def test_parse_work_minimal(self, client):
        """Test parsing minimal work data."""
        data = {
            "title": "Test Paper",
            "id": "https://openalex.org/W12345",
        }
        paper = client._parse_work(data)
        assert paper is not None
        assert paper.title == "Test Paper"
        assert paper.source == "openalex"

    def test_parse_work_full(self, client):
        """Test parsing full work data."""
        data = {
            "title": "Test Paper Title",
            "doi": "https://doi.org/10.1234/test",
            "publication_year": 2024,
            "cited_by_count": 100,
            "authorships": [
                {"author": {"display_name": "John Doe"}},
                {"author": {"display_name": "Jane Smith"}},
            ],
            "primary_location": {
                "source": {"display_name": "Test Journal"},
                "landing_page_url": "https://example.com/paper",
                "pdf_url": "https://example.com/paper.pdf",
            },
            "open_access": {"is_oa": True, "oa_url": "https://example.com/oa.pdf"},
            "concepts": [
                {"display_name": "Machine Learning"},
                {"display_name": "AI"},
            ],
        }
        paper = client._parse_work(data)
        assert paper is not None
        assert paper.title == "Test Paper Title"
        assert paper.doi == "10.1234/test"
        assert paper.year == 2024
        assert paper.citations_count == 100
        assert paper.authors == ["John Doe", "Jane Smith"]
        assert paper.journal == "Test Journal"
        assert paper.open_access is True
        assert "Machine Learning" in paper.keywords


@pytest.mark.asyncio
class TestOpenAlexClientAsync:
    """Async tests for OpenAlexClient (require network)."""

    @pytest.mark.skip(reason="Requires network access")
    async def test_search(self, client):
        """Test search functionality."""
        papers = await client.search("machine learning", limit=5)
        assert len(papers) > 0
        assert all(p.source == "openalex" for p in papers)

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_paper_by_doi(self, client):
        """Test getting paper by DOI."""
        # Using a known DOI
        paper = await client.get_paper("10.1038/nature14539")
        assert paper is not None
        assert paper.doi == "10.1038/nature14539"
