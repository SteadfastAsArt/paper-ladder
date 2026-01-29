"""Citation network analysis for Paper-Ladder.

This module provides tools for building and analyzing citation networks
from academic papers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from paper_ladder.clients.base import BaseClient
    from paper_ladder.models import Paper

logger = logging.getLogger(__name__)


@dataclass
class CitationNode:
    """A node in the citation network representing a paper."""

    paper_id: str
    doi: str | None
    title: str
    year: int | None
    citations_count: int | None
    depth: int  # Distance from the seed paper (0 = seed)
    source: str | None = None

    @classmethod
    def from_paper(cls, paper: Paper, depth: int = 0) -> CitationNode:
        """Create a CitationNode from a Paper object.

        Args:
            paper: Paper object.
            depth: Distance from seed paper.

        Returns:
            CitationNode instance.
        """
        # Use DOI as primary ID if available, otherwise use title hash
        paper_id = paper.doi or f"title:{hash(paper.title.lower())}"

        return cls(
            paper_id=paper_id,
            doi=paper.doi,
            title=paper.title,
            year=paper.year,
            citations_count=paper.citations_count,
            depth=depth,
            source=paper.source,
        )


@dataclass
class CitationEdge:
    """An edge in the citation network representing a citation relationship."""

    citing_id: str  # ID of the paper doing the citing
    cited_id: str  # ID of the paper being cited

    def __hash__(self) -> int:
        return hash((self.citing_id, self.cited_id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CitationEdge):
            return False
        return self.citing_id == other.citing_id and self.cited_id == other.cited_id


@dataclass
class CitationGraph:
    """A citation network graph."""

    nodes: dict[str, CitationNode] = field(default_factory=dict)
    edges: list[CitationEdge] = field(default_factory=list)
    seed_paper_id: str = ""

    def add_node(self, node: CitationNode) -> None:
        """Add a node to the graph.

        Args:
            node: CitationNode to add.
        """
        if node.paper_id not in self.nodes:
            self.nodes[node.paper_id] = node

    def add_edge(self, edge: CitationEdge) -> None:
        """Add an edge to the graph.

        Args:
            edge: CitationEdge to add.
        """
        if edge not in self.edges:
            self.edges.append(edge)

    def get_citing_papers(self, paper_id: str) -> list[CitationNode]:
        """Get papers that cite the given paper.

        Args:
            paper_id: ID of the paper.

        Returns:
            List of CitationNodes that cite this paper.
        """
        citing_ids = {e.citing_id for e in self.edges if e.cited_id == paper_id}
        return [self.nodes[pid] for pid in citing_ids if pid in self.nodes]

    def get_cited_papers(self, paper_id: str) -> list[CitationNode]:
        """Get papers cited by the given paper.

        Args:
            paper_id: ID of the paper.

        Returns:
            List of CitationNodes cited by this paper.
        """
        cited_ids = {e.cited_id for e in self.edges if e.citing_id == paper_id}
        return [self.nodes[pid] for pid in cited_ids if pid in self.nodes]

    def get_in_degree(self, paper_id: str) -> int:
        """Get the number of papers citing this paper (in-degree).

        Args:
            paper_id: ID of the paper.

        Returns:
            In-degree count.
        """
        return sum(1 for e in self.edges if e.cited_id == paper_id)

    def get_out_degree(self, paper_id: str) -> int:
        """Get the number of papers cited by this paper (out-degree).

        Args:
            paper_id: ID of the paper.

        Returns:
            Out-degree count.
        """
        return sum(1 for e in self.edges if e.citing_id == paper_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph to a dictionary.

        Returns:
            Dictionary representation of the graph.
        """
        return {
            "seed_paper_id": self.seed_paper_id,
            "nodes": [
                {
                    "paper_id": n.paper_id,
                    "doi": n.doi,
                    "title": n.title,
                    "year": n.year,
                    "citations_count": n.citations_count,
                    "depth": n.depth,
                    "source": n.source,
                }
                for n in self.nodes.values()
            ],
            "edges": [{"citing_id": e.citing_id, "cited_id": e.cited_id} for e in self.edges],
            "stats": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CitationGraph:
        """Deserialize a graph from a dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            CitationGraph instance.
        """
        graph = cls(seed_paper_id=data.get("seed_paper_id", ""))

        for node_data in data.get("nodes", []):
            node = CitationNode(
                paper_id=node_data["paper_id"],
                doi=node_data.get("doi"),
                title=node_data["title"],
                year=node_data.get("year"),
                citations_count=node_data.get("citations_count"),
                depth=node_data.get("depth", 0),
                source=node_data.get("source"),
            )
            graph.add_node(node)

        for edge_data in data.get("edges", []):
            edge = CitationEdge(
                citing_id=edge_data["citing_id"],
                cited_id=edge_data["cited_id"],
            )
            graph.add_edge(edge)

        return graph

    def to_networkx(self) -> Any:
        """Convert to a NetworkX DiGraph (requires networkx).

        Returns:
            NetworkX DiGraph object.

        Raises:
            ImportError: If networkx is not installed.
        """
        try:
            import networkx as nx
        except ImportError:
            raise ImportError("networkx is required for to_networkx(). Install with: pip install networkx")

        G = nx.DiGraph()

        # Add nodes with attributes
        for node in self.nodes.values():
            G.add_node(
                node.paper_id,
                doi=node.doi,
                title=node.title,
                year=node.year,
                citations_count=node.citations_count,
                depth=node.depth,
                source=node.source,
            )

        # Add edges
        for edge in self.edges:
            G.add_edge(edge.citing_id, edge.cited_id)

        return G


class CitationNetworkBuilder:
    """Builds citation networks from seed papers."""

    def __init__(
        self,
        client: BaseClient,
        max_depth: int = 2,
        max_papers_per_level: int = 50,
        direction: Literal["citations", "references", "both"] = "both",
    ):
        """Initialize the builder.

        Args:
            client: API client that supports get_paper_citations and get_paper_references.
            max_depth: Maximum depth of citation traversal (1 = direct citations only).
            max_papers_per_level: Maximum papers to retrieve at each level.
            direction: Which direction to traverse:
                - "citations": Only papers that cite the seed (cited by)
                - "references": Only papers the seed cites (references)
                - "both": Both directions
        """
        self.client = client
        self.max_depth = max_depth
        self.max_papers_per_level = max_papers_per_level
        self.direction = direction

    async def build_graph(self, seed_paper: Paper | str) -> CitationGraph:
        """Build a citation graph from a seed paper.

        Args:
            seed_paper: Paper object or identifier (DOI).

        Returns:
            CitationGraph with the citation network.
        """
        # Get the seed paper if identifier provided
        if isinstance(seed_paper, str):
            paper = await self.client.get_paper(seed_paper)
            if not paper:
                raise ValueError(f"Could not find paper: {seed_paper}")
            seed_paper = paper

        # Initialize graph
        seed_node = CitationNode.from_paper(seed_paper, depth=0)
        graph = CitationGraph(seed_paper_id=seed_node.paper_id)
        graph.add_node(seed_node)

        # Track papers to process at each level
        current_level = [seed_paper]
        current_depth = 0

        while current_level and current_depth < self.max_depth:
            current_depth += 1
            next_level: list[Paper] = []

            for paper in current_level:
                paper_id = paper.doi or f"title:{hash(paper.title.lower())}"

                # Get citations (papers that cite this paper)
                if self.direction in ("citations", "both"):
                    try:
                        if hasattr(self.client, "get_paper_citations"):
                            citations = await self.client.get_paper_citations(
                                paper.doi or paper.title,
                                limit=self.max_papers_per_level,
                            )
                            for citing_paper in citations:
                                citing_node = CitationNode.from_paper(citing_paper, depth=current_depth)
                                graph.add_node(citing_node)
                                graph.add_edge(CitationEdge(citing_id=citing_node.paper_id, cited_id=paper_id))
                                next_level.append(citing_paper)
                    except Exception as e:
                        logger.warning(f"Failed to get citations for {paper_id}: {e}")

                # Get references (papers this paper cites)
                if self.direction in ("references", "both"):
                    try:
                        if hasattr(self.client, "get_paper_references"):
                            references = await self.client.get_paper_references(
                                paper.doi or paper.title,
                                limit=self.max_papers_per_level,
                            )
                            for ref_paper in references:
                                ref_node = CitationNode.from_paper(ref_paper, depth=current_depth)
                                graph.add_node(ref_node)
                                graph.add_edge(CitationEdge(citing_id=paper_id, cited_id=ref_node.paper_id))
                                next_level.append(ref_paper)
                    except Exception as e:
                        logger.warning(f"Failed to get references for {paper_id}: {e}")

            # Limit next level to avoid explosion
            current_level = next_level[: self.max_papers_per_level * 2]

            logger.info(f"Depth {current_depth}: Added {len(next_level)} papers, graph has {len(graph.nodes)} nodes")

        return graph

    async def find_influential_papers(
        self,
        graph: CitationGraph,
        method: Literal["pagerank", "in_degree", "betweenness"] = "pagerank",
        top_k: int = 10,
    ) -> list[tuple[CitationNode, float]]:
        """Find the most influential papers in the citation network.

        Args:
            graph: Citation graph to analyze.
            method: Ranking method:
                - "pagerank": PageRank algorithm (requires networkx)
                - "in_degree": Number of citations within the network
                - "betweenness": Betweenness centrality (requires networkx)
            top_k: Number of top papers to return.

        Returns:
            List of (CitationNode, score) tuples, sorted by score descending.
        """
        if method == "in_degree":
            # Simple in-degree ranking
            scores = {pid: graph.get_in_degree(pid) for pid in graph.nodes}
        else:
            # Use networkx for advanced metrics
            try:
                import networkx as nx
            except ImportError:
                raise ImportError(f"networkx is required for method='{method}'. Install with: pip install networkx")

            G = graph.to_networkx()

            if method == "pagerank":
                scores = nx.pagerank(G)
            elif method == "betweenness":
                scores = nx.betweenness_centrality(G)
            else:
                raise ValueError(f"Unknown method: {method}")

        # Sort by score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return [(graph.nodes[pid], score) for pid, score in ranked if pid in graph.nodes]


async def build_citation_network(
    seed: Paper | str,
    client: BaseClient,
    max_depth: int = 2,
    max_papers_per_level: int = 50,
    direction: Literal["citations", "references", "both"] = "both",
) -> CitationGraph:
    """Convenience function to build a citation network.

    Args:
        seed: Seed paper or identifier.
        client: API client.
        max_depth: Maximum traversal depth.
        max_papers_per_level: Max papers per level.
        direction: Traversal direction.

    Returns:
        CitationGraph with the citation network.
    """
    builder = CitationNetworkBuilder(
        client=client,
        max_depth=max_depth,
        max_papers_per_level=max_papers_per_level,
        direction=direction,
    )
    return await builder.build_graph(seed)
