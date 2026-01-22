"""Multi-source aggregation for Paper-Ladder."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from paper_ladder.clients import CLIENTS, BaseClient
from paper_ladder.config import Config, get_config
from paper_ladder.models import Paper, SearchResult
from paper_ladder.utils import normalize_doi, normalize_title

if TYPE_CHECKING:
    pass


class Aggregator:
    """Aggregates search results from multiple sources."""

    def __init__(
        self,
        sources: list[str] | None = None,
        config: Config | None = None,
    ):
        """Initialize the aggregator.

        Args:
            sources: List of source names to query. If None, uses config defaults.
            config: Configuration object. If None, loads from default location.
        """
        self.config = config or get_config()
        self.sources = sources or self.config.default_sources
        self._clients: dict[str, BaseClient] = {}

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

        # Create search tasks for each source
        tasks = []
        for source in sources:
            try:
                client = self._get_client(source)
                tasks.append(self._search_source(client, query, limit, **kwargs))
            except ValueError:
                continue

        # Run searches concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect papers and errors
        all_papers: list[Paper] = []
        errors: dict[str, str] = {}

        for source, result in zip(sources, results):
            if isinstance(result, Exception):
                errors[source] = str(result)
            elif isinstance(result, list):
                all_papers.extend(result)

        # Deduplicate if requested
        if deduplicate:
            all_papers = self._deduplicate_papers(all_papers)

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
        return await client.search(query, limit=limit, **kwargs)

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

    def _deduplicate_papers(self, papers: list[Paper]) -> list[Paper]:
        """Remove duplicate papers based on DOI or title.

        Args:
            papers: List of papers to deduplicate.

        Returns:
            Deduplicated list of papers.
        """
        seen_dois: set[str] = set()
        seen_titles: set[str] = set()
        unique_papers: list[Paper] = []

        for paper in papers:
            # Check DOI
            if paper.doi:
                doi = normalize_doi(paper.doi)
                if doi and doi in seen_dois:
                    continue
                if doi:
                    seen_dois.add(doi)

            # Check title
            title = normalize_title(paper.title)
            if title in seen_titles:
                continue
            seen_titles.add(title)

            unique_papers.append(paper)

        return unique_papers

    def _merge_papers(self, papers: list[Paper]) -> Paper:
        """Merge multiple Paper objects into one with the best data.

        Args:
            papers: List of papers to merge.

        Returns:
            Merged paper with best available data.
        """
        if not papers:
            raise ValueError("No papers to merge")

        if len(papers) == 1:
            return papers[0]

        # Start with the first paper as base
        base = papers[0]

        # Collect best values from all papers
        best_abstract = base.abstract
        best_authors = base.authors
        best_pdf_url = base.pdf_url
        best_citations = base.citations_count
        all_keywords: set[str] = set(base.keywords)
        sources: list[str] = [base.source]

        for paper in papers[1:]:
            sources.append(paper.source)

            # Prefer longer abstract
            if paper.abstract and (
                not best_abstract or len(paper.abstract) > len(best_abstract)
            ):
                best_abstract = paper.abstract

            # Prefer more authors
            if len(paper.authors) > len(best_authors):
                best_authors = paper.authors

            # Get PDF URL if missing
            if not best_pdf_url and paper.pdf_url:
                best_pdf_url = paper.pdf_url

            # Get higher citation count
            if paper.citations_count and (
                not best_citations or paper.citations_count > best_citations
            ):
                best_citations = paper.citations_count

            # Merge keywords
            all_keywords.update(paper.keywords)

        # Create merged paper
        return Paper(
            title=base.title,
            authors=best_authors,
            abstract=best_abstract,
            doi=base.doi,
            year=base.year,
            journal=base.journal,
            url=base.url,
            pdf_url=best_pdf_url,
            source=",".join(sources),
            raw_data={"merged_from": [p.raw_data for p in papers]},
            citations_count=best_citations,
            references_count=base.references_count,
            open_access=any(p.open_access for p in papers if p.open_access is not None),
            keywords=list(all_keywords),
        )

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
