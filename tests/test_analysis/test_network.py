"""Tests for citation network analysis."""

import pytest

from paper_ladder.analysis.network import (
    CitationEdge,
    CitationGraph,
    CitationNode,
)
from paper_ladder.models import Paper


class TestCitationNode:
    """Tests for CitationNode."""

    def test_create_node(self):
        """Test creating a citation node."""
        node = CitationNode(
            paper_id="test123",
            doi="10.1234/test",
            title="Test Paper",
            year=2020,
            citations_count=100,
            depth=0,
        )

        assert node.paper_id == "test123"
        assert node.doi == "10.1234/test"
        assert node.title == "Test Paper"
        assert node.year == 2020
        assert node.depth == 0

    def test_from_paper(self, sample_paper):
        """Test creating a node from a Paper object."""
        node = CitationNode.from_paper(sample_paper, depth=1)

        assert node.paper_id == sample_paper.doi
        assert node.title == sample_paper.title
        assert node.year == sample_paper.year
        assert node.depth == 1

    def test_from_paper_no_doi(self, sample_paper_minimal):
        """Test creating a node from a Paper without DOI."""
        node = CitationNode.from_paper(sample_paper_minimal, depth=0)

        assert "title:" in node.paper_id
        assert node.doi is None


class TestCitationEdge:
    """Tests for CitationEdge."""

    def test_create_edge(self):
        """Test creating a citation edge."""
        edge = CitationEdge(citing_id="paper1", cited_id="paper2")

        assert edge.citing_id == "paper1"
        assert edge.cited_id == "paper2"

    def test_edge_equality(self):
        """Test edge equality."""
        edge1 = CitationEdge(citing_id="a", cited_id="b")
        edge2 = CitationEdge(citing_id="a", cited_id="b")
        edge3 = CitationEdge(citing_id="a", cited_id="c")

        assert edge1 == edge2
        assert edge1 != edge3

    def test_edge_hash(self):
        """Test edge hashing."""
        edge1 = CitationEdge(citing_id="a", cited_id="b")
        edge2 = CitationEdge(citing_id="a", cited_id="b")

        assert hash(edge1) == hash(edge2)


class TestCitationGraph:
    """Tests for CitationGraph."""

    def test_create_empty_graph(self):
        """Test creating an empty graph."""
        graph = CitationGraph()

        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_add_node(self):
        """Test adding nodes."""
        graph = CitationGraph()
        node = CitationNode(
            paper_id="paper1",
            doi="10.1234/paper1",
            title="Test Paper",
            year=2020,
            citations_count=10,
            depth=0,
        )

        graph.add_node(node)

        assert "paper1" in graph.nodes
        assert graph.nodes["paper1"].title == "Test Paper"

    def test_add_node_no_duplicate(self):
        """Test that duplicate nodes are not added."""
        graph = CitationGraph()
        node1 = CitationNode(
            paper_id="paper1",
            doi="10.1234/paper1",
            title="Paper 1",
            year=2020,
            citations_count=10,
            depth=0,
        )
        node2 = CitationNode(
            paper_id="paper1",
            doi="10.1234/paper1",
            title="Paper 1 Updated",
            year=2021,
            citations_count=20,
            depth=1,
        )

        graph.add_node(node1)
        graph.add_node(node2)

        assert len(graph.nodes) == 1
        assert graph.nodes["paper1"].title == "Paper 1"  # First node kept

    def test_add_edge(self):
        """Test adding edges."""
        graph = CitationGraph()
        edge = CitationEdge(citing_id="paper2", cited_id="paper1")

        graph.add_edge(edge)

        assert len(graph.edges) == 1
        assert graph.edges[0].citing_id == "paper2"

    def test_get_citing_papers(self, sample_citation_graph):
        """Test getting papers that cite a given paper."""
        citing = sample_citation_graph.get_citing_papers("paper1")

        assert len(citing) == 2
        titles = {n.title for n in citing}
        assert "Citing Paper 1" in titles
        assert "Citing Paper 2" in titles

    def test_get_cited_papers(self, sample_citation_graph):
        """Test getting papers cited by a given paper."""
        cited = sample_citation_graph.get_cited_papers("paper1")

        assert len(cited) == 1
        assert cited[0].title == "Reference Paper"

    def test_get_in_degree(self, sample_citation_graph):
        """Test in-degree calculation."""
        assert sample_citation_graph.get_in_degree("paper1") == 2
        assert sample_citation_graph.get_in_degree("paper4") == 2
        assert sample_citation_graph.get_in_degree("paper2") == 0

    def test_get_out_degree(self, sample_citation_graph):
        """Test out-degree calculation."""
        assert sample_citation_graph.get_out_degree("paper1") == 1
        assert sample_citation_graph.get_out_degree("paper2") == 2
        assert sample_citation_graph.get_out_degree("paper4") == 0

    def test_to_dict(self, sample_citation_graph):
        """Test serialization to dict."""
        data = sample_citation_graph.to_dict()

        assert data["seed_paper_id"] == "paper1"
        assert len(data["nodes"]) == 4
        assert len(data["edges"]) == 4
        assert data["stats"]["node_count"] == 4
        assert data["stats"]["edge_count"] == 4

    def test_from_dict(self, sample_citation_graph):
        """Test deserialization from dict."""
        data = sample_citation_graph.to_dict()
        restored = CitationGraph.from_dict(data)

        assert restored.seed_paper_id == sample_citation_graph.seed_paper_id
        assert len(restored.nodes) == len(sample_citation_graph.nodes)
        assert len(restored.edges) == len(sample_citation_graph.edges)

    def test_to_networkx(self, sample_citation_graph):
        """Test conversion to NetworkX graph."""
        pytest.importorskip("networkx")

        G = sample_citation_graph.to_networkx()

        assert G.number_of_nodes() == 4
        assert G.number_of_edges() == 4
        assert G.has_edge("paper2", "paper1")
