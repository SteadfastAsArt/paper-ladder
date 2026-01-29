"""Tests for citation network metrics."""

import pytest

from paper_ladder.analysis.metrics import (
    InfluenceMetrics,
    InfluenceScore,
    rank_papers,
)
from paper_ladder.analysis.network import CitationGraph


class TestInfluenceMetrics:
    """Tests for InfluenceMetrics class."""

    def test_pagerank(self, sample_citation_graph):
        """Test PageRank calculation."""
        scores = InfluenceMetrics.pagerank(sample_citation_graph)

        assert len(scores) == 4
        assert all(0 <= s <= 1 for s in scores.values())
        # Reference paper (paper4) should have high score due to being cited twice
        assert scores["paper4"] > scores["paper2"]

    def test_pagerank_empty_graph(self):
        """Test PageRank on empty graph."""
        graph = CitationGraph()
        scores = InfluenceMetrics.pagerank(graph)

        assert scores == {}

    def test_in_degree_centrality(self, sample_citation_graph):
        """Test in-degree centrality calculation."""
        scores = InfluenceMetrics.in_degree_centrality(sample_citation_graph)

        assert len(scores) == 4
        # paper1 and paper4 are both cited twice
        assert scores["paper1"] == scores["paper4"]
        # paper2 and paper3 are not cited
        assert scores["paper2"] == 0.0
        assert scores["paper3"] == 0.0

    def test_out_degree_centrality(self, sample_citation_graph):
        """Test out-degree centrality calculation."""
        scores = InfluenceMetrics.out_degree_centrality(sample_citation_graph)

        assert len(scores) == 4
        # paper2 cites 2 papers
        assert scores["paper2"] > scores["paper1"]
        # paper4 doesn't cite anyone
        assert scores["paper4"] == 0.0

    def test_betweenness_centrality(self, sample_citation_graph):
        """Test betweenness centrality calculation."""
        scores = InfluenceMetrics.betweenness_centrality(sample_citation_graph)

        assert len(scores) == 4
        assert all(0 <= s <= 1 for s in scores.values())

    def test_citation_burst(self, sample_papers):
        """Test citation burst detection."""
        burst_scores = InfluenceMetrics.citation_burst(
            sample_papers,
            window_years=3,
            current_year=2024,
        )

        assert len(burst_scores) == len(sample_papers)
        # Results should be sorted by burst score descending
        for i in range(len(burst_scores) - 1):
            assert burst_scores[i][1] >= burst_scores[i + 1][1]

    def test_citation_burst_empty(self):
        """Test citation burst on empty list."""
        result = InfluenceMetrics.citation_burst([])
        assert result == []

    def test_h_index_contribution(self, sample_citation_graph):
        """Test h-index contribution calculation."""
        scores = InfluenceMetrics.h_index_contribution(sample_citation_graph)

        assert len(scores) == 4
        # Papers with citations should have non-zero scores
        assert scores["paper1"] > 0
        assert scores["paper4"] > 0


class TestRankPapers:
    """Tests for rank_papers function."""

    def test_rank_by_pagerank(self, sample_citation_graph):
        """Test ranking by PageRank."""
        results = rank_papers(sample_citation_graph, method="pagerank")

        assert len(results) == 4
        assert all(isinstance(r, InfluenceScore) for r in results)
        assert results[0].score >= results[1].score  # Sorted descending

    def test_rank_by_in_degree(self, sample_citation_graph):
        """Test ranking by in-degree."""
        results = rank_papers(sample_citation_graph, method="in_degree")

        assert len(results) == 4
        for r in results:
            assert r.metric == "in_degree"

    def test_rank_by_betweenness(self, sample_citation_graph):
        """Test ranking by betweenness centrality."""
        results = rank_papers(sample_citation_graph, method="betweenness")

        assert len(results) == 4
        for r in results:
            assert r.metric == "betweenness"

    def test_rank_top_k(self, sample_citation_graph):
        """Test ranking with top_k limit."""
        results = rank_papers(sample_citation_graph, method="pagerank", top_k=2)

        assert len(results) == 2

    def test_rank_invalid_method(self, sample_citation_graph):
        """Test ranking with invalid method."""
        with pytest.raises(ValueError, match="Unknown method"):
            rank_papers(sample_citation_graph, method="invalid")

    def test_influence_score_attributes(self, sample_citation_graph):
        """Test InfluenceScore attributes."""
        results = rank_papers(sample_citation_graph, method="pagerank")

        score = results[0]
        assert hasattr(score, "paper_id")
        assert hasattr(score, "title")
        assert hasattr(score, "score")
        assert hasattr(score, "year")
        assert hasattr(score, "doi")
        assert hasattr(score, "metric")
