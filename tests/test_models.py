"""Tests for data models."""


from paper_ladder.models import ExtractedContent, Paper, SearchResult


class TestPaper:
    """Tests for Paper model."""

    def test_paper_creation(self):
        """Test basic paper creation."""
        paper = Paper(
            title="Test Paper",
            source="test",
        )
        assert paper.title == "Test Paper"
        assert paper.source == "test"
        assert paper.authors == []
        assert paper.abstract is None

    def test_paper_with_all_fields(self):
        """Test paper with all fields."""
        paper = Paper(
            title="Full Paper",
            authors=["Author 1", "Author 2"],
            abstract="Test abstract",
            doi="10.1234/test",
            year=2024,
            journal="Test Journal",
            url="https://example.com",
            pdf_url="https://example.com/paper.pdf",
            source="test",
            raw_data={"key": "value"},
            citations_count=100,
            open_access=True,
            keywords=["test", "paper"],
        )
        assert paper.title == "Full Paper"
        assert len(paper.authors) == 2
        assert paper.doi == "10.1234/test"
        assert paper.year == 2024
        assert paper.citations_count == 100

    def test_paper_equality_by_doi(self):
        """Test paper equality based on DOI."""
        paper1 = Paper(title="Paper 1", doi="10.1234/test", source="a")
        paper2 = Paper(title="Paper 2", doi="10.1234/TEST", source="b")
        assert paper1 == paper2

    def test_paper_equality_by_title(self):
        """Test paper equality based on title."""
        paper1 = Paper(title="Test Paper", source="a")
        paper2 = Paper(title="TEST PAPER", source="b")
        assert paper1 == paper2

    def test_paper_hash_by_doi(self):
        """Test paper hashing based on DOI."""
        paper1 = Paper(title="Paper 1", doi="10.1234/test", source="a")
        paper2 = Paper(title="Paper 2", doi="10.1234/TEST", source="b")
        assert hash(paper1) == hash(paper2)

    def test_paper_hash_by_title(self):
        """Test paper hashing based on title."""
        paper1 = Paper(title="Test Paper", source="a")
        paper2 = Paper(title="TEST PAPER", source="b")
        assert hash(paper1) == hash(paper2)


class TestExtractedContent:
    """Tests for ExtractedContent model."""

    def test_extracted_content_creation(self):
        """Test basic ExtractedContent creation."""
        content = ExtractedContent(markdown="# Test")
        assert content.markdown == "# Test"
        assert content.metadata == {}
        assert content.figures == []
        assert content.tables == []

    def test_extracted_content_full(self):
        """Test ExtractedContent with all fields."""
        content = ExtractedContent(
            markdown="# Test\nContent here",
            metadata={"title": "Test"},
            figures=["fig1.png", "fig2.png"],
            tables=["<table></table>"],
            source_url="https://example.com",
            source_type="pdf",
        )
        assert len(content.figures) == 2
        assert len(content.tables) == 1
        assert content.source_type == "pdf"


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_search_result_creation(self):
        """Test basic SearchResult creation."""
        result = SearchResult(query="test")
        assert result.query == "test"
        assert result.papers == []
        assert result.errors == {}

    def test_search_result_with_papers(self):
        """Test SearchResult with papers."""
        papers = [
            Paper(title="Paper 1", source="a"),
            Paper(title="Paper 2", source="b"),
        ]
        result = SearchResult(
            query="test",
            papers=papers,
            total_results=2,
            sources_queried=["a", "b"],
        )
        assert len(result.papers) == 2
        assert result.total_results == 2
        assert "a" in result.sources_queried
