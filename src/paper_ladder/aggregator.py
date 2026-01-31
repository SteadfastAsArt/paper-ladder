"""Multi-source aggregation for Paper-Ladder."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from paper_ladder.clients import CLIENTS, BaseClient
from paper_ladder.config import Config, get_config
from paper_ladder.models import Paper, SearchResult
from paper_ladder.utils import normalize_doi, normalize_title

logger = logging.getLogger(__name__)

# ============================================================================
# Smart Merger
# ============================================================================


class SmartMerger:
    """Intelligently merge paper metadata from multiple sources.

    Different sources have different strengths for different fields.
    This class selects the best value for each field based on source priorities.
    """

    # Source priorities for different fields (higher priority = preferred)
    # Sources not listed will have lowest priority
    FIELD_PRIORITIES: dict[str, list[str]] = {
        # DOI is most authoritative from Crossref
        "doi": ["crossref", "openalex", "semantic_scholar", "pubmed", "wos"],
        # Abstract quality varies - S2 and OpenAlex often have clean abstracts
        "abstract": ["semantic_scholar", "openalex", "pubmed", "crossref", "core"],
        # Citation counts - S2 includes preprints, OpenAlex is comprehensive
        "citations_count": ["semantic_scholar", "openalex", "wos", "elsevier"],
        # Author lists - Crossref is authoritative, OpenAlex disambiguates well
        "authors": ["crossref", "openalex", "semantic_scholar", "pubmed"],
        # Keywords/subjects
        "keywords": ["semantic_scholar", "openalex", "pubmed", "crossref"],
        # PDF URLs - open access sources
        "pdf_url": ["core", "openalex", "semantic_scholar", "doaj", "arxiv", "biorxiv"],
        # Open access status
        "open_access": ["openalex", "doaj", "core", "semantic_scholar"],
        # Journal/venue information
        "journal": ["crossref", "openalex", "pubmed", "semantic_scholar"],
        # Year - most authoritative from Crossref
        "year": ["crossref", "openalex", "pubmed", "semantic_scholar"],
        # Reference count
        "references_count": ["semantic_scholar", "crossref", "openalex"],
    }

    def __init__(self, strategy: str = "best"):
        """Initialize the merger.

        Args:
            strategy: Merge strategy:
                - "best": Select the best value for each field based on priorities
                - "union": Combine values (for list fields like keywords)
        """
        self.strategy = strategy

    def merge_papers(self, papers: list[Paper]) -> Paper:
        """Merge multiple Paper objects into one with the best data.

        Args:
            papers: List of papers from different sources.

        Returns:
            Merged paper with best available data from each source.
        """
        if not papers:
            raise ValueError("No papers to merge")

        if len(papers) == 1:
            return papers[0]

        # Create source -> paper mapping for quick lookup
        source_papers: dict[str, Paper] = {}
        for paper in papers:
            # Handle comma-separated sources (from previous merges)
            sources = paper.source.split(",")
            for source in sources:
                source = source.strip()
                if source not in source_papers:
                    source_papers[source] = paper

        # Select best values for each field
        merged_data: dict[str, Any] = {}

        # Simple string fields
        for field in ["doi", "abstract", "journal", "url"]:
            merged_data[field] = self._select_best_value(field, papers, source_papers)

        # Year (integer)
        merged_data["year"] = self._select_best_value("year", papers, source_papers)

        # Title - use the first non-empty title (they should all be the same)
        merged_data["title"] = next((p.title for p in papers if p.title), papers[0].title)

        # Authors - prefer more complete author lists
        merged_data["authors"] = self._merge_authors(papers, source_papers)

        # PDF URL - try multiple sources
        merged_data["pdf_url"] = self._select_best_value("pdf_url", papers, source_papers)

        # Citation count - prefer higher counts (they're usually more complete)
        merged_data["citations_count"] = self._select_max_value("citations_count", papers)

        # Reference count
        merged_data["references_count"] = self._select_max_value("references_count", papers)

        # Open access - if any source says it's OA, it probably is
        merged_data["open_access"] = any(p.open_access for p in papers if p.open_access is not None)

        # Keywords - union of all keywords
        merged_data["keywords"] = self._merge_keywords(papers)

        # Source - combine all sources
        all_sources = sorted(set(p.source for p in papers))
        merged_data["source"] = ",".join(all_sources)

        # Raw data - store all source data
        merged_data["raw_data"] = {
            "merged_from": [{"source": p.source, "data": p.raw_data} for p in papers]
        }

        return Paper(**merged_data)

    def _select_best_value(
        self,
        field: str,
        papers: list[Paper],
        source_papers: dict[str, Paper],
    ) -> Any:
        """Select the best value for a field based on source priorities.

        Args:
            field: Field name.
            papers: All papers.
            source_papers: Mapping of source to paper.

        Returns:
            Best value for the field.
        """
        priorities = self.FIELD_PRIORITIES.get(field, [])

        # Try sources in priority order
        for source in priorities:
            if source in source_papers:
                value = getattr(source_papers[source], field, None)
                if value:  # Non-empty value
                    return value

        # Fall back to first non-empty value from any source
        for paper in papers:
            value = getattr(paper, field, None)
            if value:
                return value

        return None

    def _select_max_value(self, field: str, papers: list[Paper]) -> int | None:
        """Select the maximum numeric value for a field.

        Args:
            field: Field name.
            papers: All papers.

        Returns:
            Maximum value or None.
        """
        values = [getattr(p, field) for p in papers if getattr(p, field) is not None]
        return max(values) if values else None

    def _merge_authors(
        self,
        papers: list[Paper],
        source_papers: dict[str, Paper],
    ) -> list[str]:
        """Merge author lists, preferring more complete lists.

        Args:
            papers: All papers.
            source_papers: Mapping of source to paper.

        Returns:
            Best author list.
        """
        priorities = self.FIELD_PRIORITIES.get("authors", [])

        # Try sources in priority order, picking the longest list from priority sources
        best_authors: list[str] = []
        best_priority = -1

        for i, source in enumerate(priorities):
            if source in source_papers:
                authors = source_papers[source].authors
                if len(authors) > len(best_authors):
                    best_authors = authors
                    best_priority = i

        # Check remaining sources for longer lists
        for paper in papers:
            if paper.source not in priorities and len(paper.authors) > len(best_authors):
                best_authors = paper.authors

        return best_authors if best_authors else papers[0].authors

    def _merge_keywords(self, papers: list[Paper]) -> list[str]:
        """Merge keywords from all sources, removing duplicates.

        Args:
            papers: All papers.

        Returns:
            Merged unique keywords.
        """
        all_keywords: set[str] = set()

        for paper in papers:
            for keyword in paper.keywords:
                # Normalize keyword for deduplication
                normalized = keyword.strip().lower()
                # Add original casing if not seen before
                if normalized not in {k.lower() for k in all_keywords}:
                    all_keywords.add(keyword.strip())

        # Limit to 20 keywords
        return list(all_keywords)[:20]


class Aggregator:
    """Aggregates search results from multiple sources."""

    def __init__(
        self,
        sources: list[str] | None = None,
        config: Config | None = None,
        merge_strategy: str = "best",
    ):
        """Initialize the aggregator.

        Args:
            sources: List of source names to query. If None, uses config defaults.
            config: Configuration object. If None, loads from default location.
            merge_strategy: Strategy for merging paper metadata:
                - "best": Select best value for each field (default)
                - "union": Combine values where possible
        """
        self.config = config or get_config()
        self.sources = sources or self.config.default_sources
        self._clients: dict[str, BaseClient] = {}
        self.merger = SmartMerger(strategy=merge_strategy)

    def _get_client(self, source: str) -> BaseClient:
        """Get or create a client for the given source.

        Args:
            source: Source name.

        Returns:
            Client instance.
        """
        if source not in self._clients:
            if source not in CLIENTS:
                raise ValueError(f"Unknown source: {source}")
            self._clients[source] = CLIENTS[source](self.config)
        return self._clients[source]

    async def search(
        self,
        query: str,
        limit: int = 10,
        sources: list[str] | None = None,
        deduplicate: bool = True,
        **kwargs: object,
    ) -> SearchResult:
        """Search for papers across multiple sources.

        Args:
            query: Search query string.
            limit: Maximum results per source.
            sources: Sources to query. If None, uses instance sources.
            deduplicate: Whether to deduplicate results.
            **kwargs: Additional source-specific parameters.

        Returns:
            SearchResult with combined papers.
        """
        sources = sources or self.sources
        logger.info(f"[SEARCH] query={query!r} sources={sources} limit={limit}")

        # Create search tasks for each source
        tasks = []
        for source in sources:
            try:
                client = self._get_client(source)
                tasks.append(self._search_source(client, query, limit, **kwargs))
            except ValueError as e:
                logger.warning(f"[SEARCH] Skipping unknown source: {source}")
                continue

        # Run searches concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect papers by source and errors
        source_papers: list[list[Paper]] = []
        errors: dict[str, str] = {}

        for source, result in zip(sources, results):
            if isinstance(result, Exception):
                errors[source] = str(result)
                source_papers.append([])  # Empty list for failed source
                logger.warning(f"[SEARCH] {source} failed: {result}")
            elif isinstance(result, list):
                source_papers.append(result)
                logger.debug(f"[SEARCH] {source} returned {len(result)} papers")
            else:
                source_papers.append([])

        # Interleave results from all sources (round-robin)
        # This ensures fair ranking across sources
        all_papers: list[Paper] = []
        max_len = max((len(papers) for papers in source_papers), default=0)

        for i in range(max_len):
            for papers in source_papers:
                if i < len(papers):
                    all_papers.append(papers[i])

        total_before_dedup = len(all_papers)

        # Deduplicate if requested
        if deduplicate:
            all_papers = self._deduplicate_papers(all_papers)
            logger.debug(
                f"[SEARCH] Deduplicated: {total_before_dedup} -> {len(all_papers)} papers"
            )

        logger.info(
            f"[SEARCH] Complete: {len(all_papers)} papers from {len(sources) - len(errors)}/{len(sources)} sources"
        )

        return SearchResult(
            query=query,
            papers=all_papers,
            total_results=len(all_papers),
            sources_queried=sources,
            errors=errors,
        )

    async def _search_source(
        self,
        client: BaseClient,
        query: str,
        limit: int,
        **kwargs: object,
    ) -> list[Paper]:
        """Search a single source.

        Args:
            client: Client instance.
            query: Search query.
            limit: Maximum results.
            **kwargs: Additional parameters.

        Returns:
            List of papers from this source.
        """
        import time

        start = time.monotonic()
        papers = await client.search(query, limit=limit, **kwargs)
        elapsed = time.monotonic() - start
        logger.info(f"[{client.name}] Found {len(papers)} papers in {elapsed:.2f}s")
        return papers

    async def get_paper(
        self,
        identifier: str,
        sources: list[str] | None = None,
    ) -> Paper | None:
        """Get a paper by identifier from multiple sources.

        Args:
            identifier: DOI or other paper identifier.
            sources: Sources to query. If None, uses instance sources.

        Returns:
            Paper object if found, None otherwise.
        """
        sources = sources or self.sources

        # Try each source until we find the paper
        for source in sources:
            try:
                client = self._get_client(source)
                paper = await client.get_paper(identifier)
                if paper:
                    return paper
            except Exception:
                continue

        return None

    async def get_paper_from_all(
        self,
        identifier: str,
        sources: list[str] | None = None,
    ) -> Paper | None:
        """Get a paper by identifier and merge data from all sources.

        Args:
            identifier: DOI or other paper identifier.
            sources: Sources to query. If None, uses instance sources.

        Returns:
            Merged Paper object if found, None otherwise.
        """
        sources = sources or self.sources

        # Query all sources concurrently
        tasks = []
        for source in sources:
            try:
                client = self._get_client(source)
                tasks.append(client.get_paper(identifier))
            except ValueError:
                continue

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect valid papers
        papers = [r for r in results if isinstance(r, Paper)]

        if not papers:
            return None

        # Merge papers
        return self._merge_papers(papers)

    def _deduplicate_papers(
        self, papers: list[Paper], merge_duplicates: bool = True
    ) -> list[Paper]:
        """Remove duplicate papers based on DOI or title.

        This method uses batch pre-computation for efficiency and optionally
        merges duplicate papers using SmartMerger instead of discarding them.

        Args:
            papers: List of papers to deduplicate.
            merge_duplicates: If True, merge duplicate papers using SmartMerger.
                            If False, keep only the first occurrence.

        Returns:
            Deduplicated list of papers.
        """
        if not papers:
            return []

        # Step 1: Pre-compute all normalized DOIs and titles in batch
        normalized_data: list[tuple[str | None, str]] = [
            (normalize_doi(p.doi) if p.doi else None, normalize_title(p.title))
            for p in papers
        ]

        # Step 2: Group papers by DOI or title for potential merging
        # Using DOI as primary key, title as fallback
        doi_groups: dict[str, list[int]] = {}  # doi -> list of paper indices
        title_groups: dict[str, list[int]] = {}  # title -> list of paper indices

        for idx, (doi, title) in enumerate(normalized_data):
            if doi:
                if doi not in doi_groups:
                    doi_groups[doi] = []
                doi_groups[doi].append(idx)
            else:
                # Only use title grouping if no DOI
                if title not in title_groups:
                    title_groups[title] = []
                title_groups[title].append(idx)

        # Step 3: Process groups - merge or keep first
        unique_papers: list[Paper] = []
        processed_indices: set[int] = set()

        # Process DOI groups first (more reliable identifier)
        for doi, indices in doi_groups.items():
            if indices[0] in processed_indices:
                continue

            if merge_duplicates and len(indices) > 1:
                # Merge all papers with the same DOI
                group_papers = [papers[i] for i in indices]
                merged = self.merger.merge_papers(group_papers)
                unique_papers.append(merged)
            else:
                unique_papers.append(papers[indices[0]])

            processed_indices.update(indices)

        # Process title-only groups (papers without DOI)
        for title, indices in title_groups.items():
            # Filter out already processed indices
            remaining = [i for i in indices if i not in processed_indices]
            if not remaining:
                continue

            if merge_duplicates and len(remaining) > 1:
                group_papers = [papers[i] for i in remaining]
                merged = self.merger.merge_papers(group_papers)
                unique_papers.append(merged)
            else:
                unique_papers.append(papers[remaining[0]])

            processed_indices.update(remaining)

        return unique_papers

    def _merge_papers(self, papers: list[Paper]) -> Paper:
        """Merge multiple Paper objects into one with the best data.

        Uses SmartMerger for intelligent field-level merging based on
        source reliability for each field type.

        Args:
            papers: List of papers to merge.

        Returns:
            Merged paper with best available data.
        """
        return self.merger.merge_papers(papers)

    async def close(self) -> None:
        """Close all client connections."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()

    async def __aenter__(self) -> Aggregator:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()


# Convenience functions


async def search(
    query: str,
    sources: list[str] | None = None,
    limit: int = 10,
    **kwargs: object,
) -> list[Paper]:
    """Search for papers across multiple sources.

    Args:
        query: Search query string.
        sources: Sources to query. If None, uses config defaults.
        limit: Maximum results per source.
        **kwargs: Additional parameters.

    Returns:
        List of deduplicated papers.
    """
    async with Aggregator(sources=sources) as agg:
        result = await agg.search(query, limit=limit, **kwargs)
        return result.papers


async def get_paper(
    identifier: str,
    sources: list[str] | None = None,
) -> Paper | None:
    """Get a paper by identifier.

    Args:
        identifier: DOI or other paper identifier.
        sources: Sources to query. If None, uses config defaults.

    Returns:
        Paper object if found, None otherwise.
    """
    async with Aggregator(sources=sources) as agg:
        return await agg.get_paper(identifier)
