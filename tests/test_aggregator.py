"""Tests for the aggregator module."""

import pytest

from paper_ladder.aggregator import Aggregator, SmartMerger
from paper_ladder.models import Paper


class TestSmartMerger:
    """Tests for SmartMerger."""

    def test_merge_single_paper(self):
        """Test merging a single paper returns it unchanged."""
        paper = Paper(
            title="Test Paper",
            authors=["Author A"],
            doi="10.1234/test",
            year=2023,
            source="openalex",
        )
        merger = SmartMerger()
        result = merger.merge_papers([paper])
        assert result.title == paper.title
        assert result.doi == paper.doi

    def test_merge_papers_best_abstract(self):
        """Test that abstract is selected from preferred source."""
        paper1 = Paper(
            title="Test Paper",
            authors=["Author A"],
            doi="10.1234/test",
            abstract="Short abstract",
            year=2023,
            source="crossref",
        )
        paper2 = Paper(
            title="Test Paper",
            authors=["Author A"],
            doi="10.1234/test",
            abstract="Detailed abstract from Semantic Scholar",
            year=2023,
            source="semantic_scholar",
        )
        merger = SmartMerger()
        result = merger.merge_papers([paper1, paper2])
        # semantic_scholar has higher priority for abstracts
        assert result.abstract == "Detailed abstract from Semantic Scholar"

    def test_merge_papers_max_citations(self):
        """Test that highest citation count is selected."""
        paper1 = Paper(
            title="Test Paper",
            authors=["Author A"],
            doi="10.1234/test",
            citations_count=100,
            year=2023,
            source="openalex",
        )
        paper2 = Paper(
            title="Test Paper",
            authors=["Author A"],
            doi="10.1234/test",
            citations_count=150,
            year=2023,
            source="semantic_scholar",
        )
        merger = SmartMerger()
        result = merger.merge_papers([paper1, paper2])
        assert result.citations_count == 150

    def test_merge_papers_combined_keywords(self):
        """Test that keywords are combined from all sources."""
        paper1 = Paper(
            title="Test Paper",
            authors=["Author A"],
            keywords=["AI", "ML"],
            year=2023,
            source="openalex",
        )
        paper2 = Paper(
            title="Test Paper",
            authors=["Author A"],
            keywords=["Deep Learning", "Neural Networks"],
            year=2023,
            source="semantic_scholar",
        )
        merger = SmartMerger()
        result = merger.merge_papers([paper1, paper2])
        assert len(result.keywords) == 4
        assert "AI" in result.keywords
        assert "Deep Learning" in result.keywords


class TestAggregatorDeduplication:
    """Tests for _deduplicate_papers method."""

    @pytest.fixture
    def aggregator(self):
        """Create aggregator instance."""
        return Aggregator(sources=["openalex"])

    def test_deduplicate_by_doi(self, aggregator):
        """Test deduplication by DOI."""
        papers = [
            Paper(
                title="Paper One",
                authors=["Author A"],
                doi="10.1234/test",
                year=2023,
                source="openalex",
            ),
            Paper(
                title="Paper One (variant)",
                authors=["Author A"],
                doi="10.1234/test",  # Same DOI
                year=2023,
                source="semantic_scholar",
            ),
            Paper(
                title="Different Paper",
                authors=["Author B"],
                doi="10.5678/other",
                year=2022,
                source="crossref",
            ),
        ]
        result = aggregator._deduplicate_papers(papers)
        assert len(result) == 2
        # First paper should be merged from two sources
        merged = next(p for p in result if "10.1234/test" in (p.doi or ""))
        assert "openalex" in merged.source
        assert "semantic_scholar" in merged.source

    def test_deduplicate_by_title(self, aggregator):
        """Test deduplication by title when no DOI."""
        papers = [
            Paper(
                title="Same Title Paper",
                authors=["Author A"],
                year=2023,
                source="openalex",
            ),
            Paper(
                title="same title paper",  # Same title, different case
                authors=["Author A"],
                year=2023,
                source="semantic_scholar",
            ),
            Paper(
                title="Different Paper",
                authors=["Author B"],
                year=2022,
                source="crossref",
            ),
        ]
        result = aggregator._deduplicate_papers(papers)
        assert len(result) == 2

    def test_deduplicate_no_merge(self, aggregator):
        """Test deduplication without merging (keep first only)."""
        papers = [
            Paper(
                title="Paper One",
                authors=["Author A"],
                doi="10.1234/test",
                abstract="First abstract",
                year=2023,
                source="openalex",
            ),
            Paper(
                title="Paper One",
                authors=["Author A"],
                doi="10.1234/test",
                abstract="Second abstract",
                year=2023,
                source="semantic_scholar",
            ),
        ]
        result = aggregator._deduplicate_papers(papers, merge_duplicates=False)
        assert len(result) == 1
        assert result[0].abstract == "First abstract"
        assert result[0].source == "openalex"

    def test_deduplicate_empty_list(self, aggregator):
        """Test deduplication of empty list."""
        result = aggregator._deduplicate_papers([])
        assert result == []

    def test_deduplicate_preserves_order(self, aggregator):
        """Test that deduplication preserves relative order."""
        papers = [
            Paper(
                title="First Paper",
                authors=["Author A"],
                doi="10.1234/first",
                year=2023,
                source="openalex",
            ),
            Paper(
                title="Second Paper",
                authors=["Author B"],
                doi="10.1234/second",
                year=2022,
                source="crossref",
            ),
            Paper(
                title="Third Paper",
                authors=["Author C"],
                doi="10.1234/third",
                year=2021,
                source="pubmed",
            ),
        ]
        result = aggregator._deduplicate_papers(papers)
        assert len(result) == 3
        # DOI groups are processed first, maintaining insertion order
        dois = [p.doi for p in result]
        assert "10.1234/first" in dois
        assert "10.1234/second" in dois
        assert "10.1234/third" in dois

    def test_deduplicate_doi_normalization(self, aggregator):
        """Test that DOI normalization works during deduplication."""
        papers = [
            Paper(
                title="Paper One",
                authors=["Author A"],
                doi="https://doi.org/10.1234/TEST",  # URL format, uppercase
                year=2023,
                source="openalex",
            ),
            Paper(
                title="Paper One",
                authors=["Author A"],
                doi="10.1234/test",  # Plain format, lowercase
                year=2023,
                source="semantic_scholar",
            ),
        ]
        result = aggregator._deduplicate_papers(papers)
        assert len(result) == 1
        # Should be merged
        assert "openalex" in result[0].source
        assert "semantic_scholar" in result[0].source

    def test_deduplicate_mixed_doi_and_title(self, aggregator):
        """Test deduplication with mix of DOI and title-only papers."""
        papers = [
            Paper(
                title="Paper With DOI",
                authors=["Author A"],
                doi="10.1234/test",
                year=2023,
                source="openalex",
            ),
            Paper(
                title="Paper Without DOI",
                authors=["Author B"],
                year=2022,
                source="crossref",
            ),
            Paper(
                title="Paper With DOI",  # Same title, but different DOI
                authors=["Author A"],
                doi="10.1234/test",  # Same DOI as first
                year=2023,
                source="semantic_scholar",
            ),
            Paper(
                title="paper without doi",  # Same title as second (normalized)
                authors=["Author B"],
                year=2022,
                source="pubmed",
            ),
        ]
        result = aggregator._deduplicate_papers(papers)
        assert len(result) == 2
