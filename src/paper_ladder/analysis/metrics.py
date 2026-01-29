"""Influence metrics for citation network analysis.

This module provides various metrics for analyzing paper influence
within citation networks.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paper_ladder.analysis.network import CitationGraph
    from paper_ladder.models import Paper


@dataclass
class InfluenceScore:
    """Influence score with paper information."""

    paper_id: str
    title: str
    score: float
    year: int | None = None
    doi: str | None = None
    metric: str = "unknown"


class InfluenceMetrics:
    """Static methods for calculating paper influence metrics."""

    @staticmethod
    def pagerank(
        graph: CitationGraph,
        damping: float = 0.85,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> dict[str, float]:
        """Calculate PageRank scores for papers in the citation network.

        PageRank measures the "importance" of papers based on the citation
        structure, where citations from highly-cited papers count more.

        Args:
            graph: Citation graph to analyze.
            damping: Damping factor (typically 0.85).
            max_iterations: Maximum iterations for convergence.
            tolerance: Convergence tolerance.

        Returns:
            Dictionary mapping paper IDs to PageRank scores.
        """
        nodes = list(graph.nodes.keys())
        n = len(nodes)

        if n == 0:
            return {}

        # Initialize scores uniformly
        scores = dict.fromkeys(nodes, 1.0 / n)

        # Build adjacency lists
        in_links: dict[str, list[str]] = defaultdict(list)  # papers that cite this paper
        out_degree: dict[str, int] = defaultdict(int)  # number of papers this paper cites

        for edge in graph.edges:
            in_links[edge.cited_id].append(edge.citing_id)
            out_degree[edge.citing_id] += 1

        # Iterate until convergence
        for _ in range(max_iterations):
            new_scores = {}
            diff = 0.0

            for node in nodes:
                # Sum of (score / out_degree) from all papers citing this one
                rank_sum = 0.0
                for citing_node in in_links[node]:
                    if out_degree[citing_node] > 0:
                        rank_sum += scores[citing_node] / out_degree[citing_node]

                # PageRank formula
                new_score = (1 - damping) / n + damping * rank_sum
                new_scores[node] = new_score
                diff += abs(new_score - scores[node])

            scores = new_scores

            if diff < tolerance:
                break

        return scores

    @staticmethod
    def in_degree_centrality(graph: CitationGraph) -> dict[str, float]:
        """Calculate in-degree centrality (normalized citation count within network).

        Args:
            graph: Citation graph to analyze.

        Returns:
            Dictionary mapping paper IDs to normalized in-degree scores.
        """
        n = len(graph.nodes)
        if n <= 1:
            return dict.fromkeys(graph.nodes, 0.0)

        scores = {}
        for paper_id in graph.nodes:
            in_degree = graph.get_in_degree(paper_id)
            # Normalize by maximum possible in-degree
            scores[paper_id] = in_degree / (n - 1)

        return scores

    @staticmethod
    def out_degree_centrality(graph: CitationGraph) -> dict[str, float]:
        """Calculate out-degree centrality (normalized reference count within network).

        Args:
            graph: Citation graph to analyze.

        Returns:
            Dictionary mapping paper IDs to normalized out-degree scores.
        """
        n = len(graph.nodes)
        if n <= 1:
            return dict.fromkeys(graph.nodes, 0.0)

        scores = {}
        for paper_id in graph.nodes:
            out_degree = graph.get_out_degree(paper_id)
            # Normalize by maximum possible out-degree
            scores[paper_id] = out_degree / (n - 1)

        return scores

    @staticmethod
    def betweenness_centrality(graph: CitationGraph) -> dict[str, float]:
        """Calculate betweenness centrality.

        Betweenness centrality measures how often a paper lies on the shortest
        path between other papers. High betweenness indicates a "bridge" paper
        connecting different research areas.

        Args:
            graph: Citation graph to analyze.

        Returns:
            Dictionary mapping paper IDs to betweenness centrality scores.
        """
        nodes = list(graph.nodes.keys())
        n = len(nodes)

        if n <= 2:
            return dict.fromkeys(nodes, 0.0)

        # Build adjacency list (directed)
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in graph.edges:
            adj[edge.citing_id].append(edge.cited_id)

        betweenness = dict.fromkeys(nodes, 0.0)

        # For each node, compute shortest paths
        for s in nodes:
            # BFS from source
            stack: list[str] = []
            pred: dict[str, list[str]] = {node: [] for node in nodes}
            sigma: dict[str, int] = dict.fromkeys(nodes, 0)
            sigma[s] = 1
            dist: dict[str, int] = dict.fromkeys(nodes, -1)
            dist[s] = 0

            queue = [s]
            while queue:
                v = queue.pop(0)
                stack.append(v)

                for w in adj[v]:
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        queue.append(w)

                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        pred[w].append(v)

            # Accumulate
            delta = dict.fromkeys(nodes, 0.0)
            while stack:
                w = stack.pop()
                for v in pred[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])

                if w != s:
                    betweenness[w] += delta[w]

        # Normalize
        scale = 1.0 / ((n - 1) * (n - 2)) if n > 2 else 1.0
        for node in nodes:
            betweenness[node] *= scale

        return betweenness

    @staticmethod
    def citation_burst(
        papers: list[Paper],
        window_years: int = 3,
        current_year: int | None = None,
    ) -> list[tuple[Paper, float]]:
        """Identify papers with citation bursts.

        A citation burst indicates rapid growth in citations over a recent time window,
        suggesting emerging importance or trending research.

        Args:
            papers: List of papers to analyze.
            window_years: Time window for measuring burst.
            current_year: Reference year (defaults to max year in papers).

        Returns:
            List of (Paper, burst_score) tuples, sorted by score descending.
        """
        if not papers:
            return []

        # Determine current year
        if current_year is None:
            years = [p.year for p in papers if p.year]
            current_year = max(years) if years else 2024

        burst_scores = []

        for paper in papers:
            if not paper.year or not paper.citations_count:
                burst_scores.append((paper, 0.0))
                continue

            paper_age = current_year - paper.year

            if paper_age <= 0:
                # Very recent paper - use raw citations
                burst_scores.append((paper, float(paper.citations_count)))
            elif paper_age <= window_years:
                # Within window - calculate citation velocity
                # Citations per year, weighted by recency
                velocity = paper.citations_count / paper_age
                recency_weight = 1.0 + (window_years - paper_age) / window_years
                burst_scores.append((paper, velocity * recency_weight))
            else:
                # Older paper - lower burst score
                velocity = paper.citations_count / paper_age
                decay = window_years / paper_age  # Decay factor
                burst_scores.append((paper, velocity * decay))

        # Sort by burst score descending
        burst_scores.sort(key=lambda x: x[1], reverse=True)

        return burst_scores

    @staticmethod
    def h_index_contribution(graph: CitationGraph) -> dict[str, float]:
        """Calculate each paper's contribution to the h-index of the network.

        Papers that would be included in an h-index calculation get higher scores.

        Args:
            graph: Citation graph to analyze.

        Returns:
            Dictionary mapping paper IDs to h-index contribution scores.
        """
        # Get citation counts (in-degree) for each paper
        citation_counts = [(pid, graph.get_in_degree(pid)) for pid in graph.nodes]

        # Sort by citation count descending
        citation_counts.sort(key=lambda x: x[1], reverse=True)

        # Calculate h-index of the network
        h_index = 0
        for i, (pid, count) in enumerate(citation_counts, 1):
            if count >= i:
                h_index = i
            else:
                break

        # Papers contributing to h-index get score of 1.0
        # Others get fractional score based on how close they are
        scores = {}
        for i, (pid, count) in enumerate(citation_counts, 1):
            if i <= h_index:
                scores[pid] = 1.0
            elif count > 0:
                # Partial contribution based on citation count relative to h-index
                scores[pid] = min(count / (h_index + 1), 0.9)
            else:
                scores[pid] = 0.0

        return scores


def rank_papers(
    graph: CitationGraph,
    method: str = "pagerank",
    top_k: int | None = None,
) -> list[InfluenceScore]:
    """Rank papers by influence using the specified method.

    Args:
        graph: Citation graph to analyze.
        method: Ranking method:
            - "pagerank": PageRank algorithm
            - "in_degree": Citation count within network
            - "out_degree": Reference count within network
            - "betweenness": Betweenness centrality
            - "h_contribution": H-index contribution
        top_k: Number of top papers to return (None for all).

    Returns:
        List of InfluenceScore objects, sorted by score descending.
    """
    if method == "pagerank":
        scores = InfluenceMetrics.pagerank(graph)
    elif method == "in_degree":
        scores = InfluenceMetrics.in_degree_centrality(graph)
    elif method == "out_degree":
        scores = InfluenceMetrics.out_degree_centrality(graph)
    elif method == "betweenness":
        scores = InfluenceMetrics.betweenness_centrality(graph)
    elif method == "h_contribution":
        scores = InfluenceMetrics.h_index_contribution(graph)
    else:
        raise ValueError(f"Unknown method: {method}")

    # Convert to InfluenceScore objects
    results = []
    for paper_id, score in scores.items():
        node = graph.nodes.get(paper_id)
        if node:
            results.append(
                InfluenceScore(
                    paper_id=paper_id,
                    title=node.title,
                    score=score,
                    year=node.year,
                    doi=node.doi,
                    metric=method,
                )
            )

    # Sort by score descending
    results.sort(key=lambda x: x.score, reverse=True)

    if top_k:
        results = results[:top_k]

    return results
