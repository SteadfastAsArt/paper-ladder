"""arXiv client for Paper-Ladder.

API Documentation: https://info.arxiv.org/help/api/index.html
- User's Manual: https://info.arxiv.org/help/api/user-manual.html
- Query Interface: https://info.arxiv.org/help/api/user-manual.html#query_interface
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING, Any, ClassVar

import feedparser

from paper_ladder.clients.base import BaseClient, sort_papers
from paper_ladder.models import Paper, SortBy
from paper_ladder.utils import clean_html_text

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class ArxivClient(BaseClient):
    """Client for arXiv preprint repository.

    arXiv provides free access to preprints in physics, mathematics,
    computer science, quantitative biology, quantitative finance,
    statistics, electrical engineering, and economics.

    API docs: https://info.arxiv.org/help/api/index.html

    Note: arXiv API has a rate limit of 1 request per 3 seconds.
    """

    name = "arxiv"
    base_url = "http://export.arxiv.org/api"

    # arXiv category mapping for common fields
    CATEGORIES: ClassVar[dict[str, str]] = {
        "cs": "Computer Science",
        "math": "Mathematics",
        "physics": "Physics",
        "q-bio": "Quantitative Biology",
        "q-fin": "Quantitative Finance",
        "stat": "Statistics",
        "eess": "Electrical Engineering and Systems Science",
        "econ": "Economics",
        "astro-ph": "Astrophysics",
        "cond-mat": "Condensed Matter",
        "gr-qc": "General Relativity and Quantum Cosmology",
        "hep-ex": "High Energy Physics - Experiment",
        "hep-lat": "High Energy Physics - Lattice",
        "hep-ph": "High Energy Physics - Phenomenology",
        "hep-th": "High Energy Physics - Theory",
        "math-ph": "Mathematical Physics",
        "nlin": "Nonlinear Sciences",
        "nucl-ex": "Nuclear Experiment",
        "nucl-th": "Nuclear Theory",
        "quant-ph": "Quantum Physics",
    }

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        sort: SortBy | str | None = None,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers on arXiv.

        Args:
            query: Search query string. Supports arXiv query syntax:
                   - all:term - search all fields
                   - ti:term - title
                   - au:term - author
                   - abs:term - abstract
                   - cat:cs.AI - category
            limit: Maximum number of results (max 2000 per request).
            offset: Number of results to skip.
            sort: Sort order - SortBy enum. arXiv supports:
                  - RELEVANCE: relevance ranking
                  - DATE: submittedDate descending (newest first)
                  - DATE_ASC: submittedDate ascending (oldest first)
                  Note: arXiv doesn't support sorting by citation count.
            **kwargs: Additional parameters:
                - category: Filter by arXiv category (e.g., "cs.AI", "physics")
                - year: Filter by year

        Returns:
            List of Paper objects.
        """
        # Build search query
        search_query = self._build_query(query, **kwargs)

        # Determine sort parameters
        sort_by, sort_order = self._get_arxiv_sort(sort)

        params: dict[str, Any] = {
            "search_query": search_query,
            "start": offset,
            "max_results": min(limit, 2000),
        }

        if sort_by:
            params["sortBy"] = sort_by
            params["sortOrder"] = sort_order

        response = await self._get("/query", params=params)
        feed = feedparser.parse(response.text)

        papers = []
        for entry in feed.entries:
            paper = self._parse_entry(entry)
            if paper:
                papers.append(paper)

        # Apply client-side sorting for citations (not supported by API)
        if sort == SortBy.CITATIONS:
            papers = sort_papers(papers, SortBy.CITATIONS)

        return papers

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by arXiv ID.

        Args:
            identifier: arXiv ID (e.g., "2301.07041", "arxiv:2301.07041",
                       "https://arxiv.org/abs/2301.07041").

        Returns:
            Paper object if found, None otherwise.
        """
        # Normalize arXiv ID
        arxiv_id = self._normalize_arxiv_id(identifier)
        if not arxiv_id:
            return None

        params: dict[str, Any] = {
            "id_list": arxiv_id,
            "max_results": 1,
        }

        response = await self._get("/query", params=params)
        feed = feedparser.parse(response.text)

        if feed.entries:
            return self._parse_entry(feed.entries[0])
        return None

    async def get_paper_by_doi(self, doi: str) -> Paper | None:
        """Get a paper by DOI (searches for it).

        Args:
            doi: DOI string.

        Returns:
            Paper object if found, None otherwise.
        """
        # Search for the DOI
        papers = await self.search(f'"{doi}"', limit=1)
        return papers[0] if papers else None

    async def search_by_author(
        self,
        author_name: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers by author name.

        Args:
            author_name: Author name to search for.
            limit: Maximum number of results.
            offset: Number of results to skip.
            **kwargs: Additional parameters (category, year).

        Returns:
            List of papers by the author.
        """
        return await self.search(f"au:{author_name}", limit=limit, offset=offset, **kwargs)

    async def search_by_category(
        self,
        category: str,
        query: str | None = None,
        limit: int = 10,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers in a specific arXiv category.

        Args:
            category: arXiv category (e.g., "cs.AI", "physics.optics").
            query: Optional additional search query.
            limit: Maximum number of results.
            offset: Number of results to skip.
            **kwargs: Additional parameters.

        Returns:
            List of papers in the category.
        """
        search_query = f"cat:{category} AND ({query})" if query else f"cat:{category}"
        return await self.search(search_query, limit=limit, offset=offset, **kwargs)

    async def search_with_cursor(
        self,
        query: str,
        max_results: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[Paper]:
        """Search using offset pagination (arXiv doesn't have cursor).

        Args:
            query: Search query string.
            max_results: Maximum number of results to retrieve.
            **kwargs: Additional parameters.

        Yields:
            Paper objects.
        """
        offset = 0
        batch_size = 200  # arXiv recommends smaller batches
        count = 0

        while True:
            if max_results:
                remaining = max_results - count
                if remaining <= 0:
                    break
                current_limit = min(batch_size, remaining)
            else:
                current_limit = batch_size

            papers = await self.search(query, limit=current_limit, offset=offset, **kwargs)
            if not papers:
                break

            for paper in papers:
                yield paper
                count += 1
                if max_results and count >= max_results:
                    return

            offset += len(papers)
            if len(papers) < current_limit:
                break

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_query(self, query: str, **kwargs: object) -> str:
        """Build arXiv search query with filters.

        Args:
            query: Base search query.
            **kwargs: Filters (category, year).

        Returns:
            Formatted arXiv query string.
        """
        parts = []

        # Add main query - wrap in all: if no field specified
        if not any(f"{field}:" in query for field in ["all", "ti", "au", "abs", "cat", "id"]):
            parts.append(f"all:{query}")
        else:
            parts.append(query)

        # Add category filter
        if kwargs.get("category"):
            parts.append(f"cat:{kwargs['category']}")

        # Combine with AND
        return " AND ".join(parts) if len(parts) > 1 else parts[0]

    def _get_arxiv_sort(self, sort: SortBy | str | None) -> tuple[str | None, str]:
        """Convert SortBy to arXiv sort parameters.

        Args:
            sort: Sort criteria.

        Returns:
            Tuple of (sortBy, sortOrder) for arXiv API.
        """
        if sort is None or sort == SortBy.RELEVANCE:
            return "relevance", "descending"
        elif sort == SortBy.DATE:
            return "submittedDate", "descending"
        elif sort == SortBy.DATE_ASC:
            return "submittedDate", "ascending"
        elif sort == SortBy.CITATIONS:
            # arXiv doesn't support citation sorting - return relevance and sort client-side
            return "relevance", "descending"
        else:
            return "relevance", "descending"

    def _normalize_arxiv_id(self, identifier: str) -> str | None:
        """Normalize an arXiv identifier.

        Args:
            identifier: arXiv ID in various formats.

        Returns:
            Normalized arXiv ID or None if invalid.
        """
        # Remove common prefixes
        identifier = identifier.strip()
        identifier = identifier.replace("arxiv:", "")
        identifier = identifier.replace("arXiv:", "")
        identifier = identifier.replace("https://arxiv.org/abs/", "")
        identifier = identifier.replace("http://arxiv.org/abs/", "")
        identifier = identifier.replace("https://arxiv.org/pdf/", "").replace(".pdf", "")

        # Validate format (new format: YYMM.NNNNN or old format: archive/YYMMNNN)
        new_format = re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", identifier)
        old_format = re.match(r"^[a-z-]+/\d{7}(v\d+)?$", identifier)

        if new_format or old_format:
            return identifier
        return None

    def _parse_entry(self, entry: dict[str, Any]) -> Paper | None:
        """Parse an arXiv feed entry into a Paper.

        Args:
            entry: feedparser entry object.

        Returns:
            Paper object or None if parsing fails.
        """
        title = entry.get("title", "")
        if not title:
            return None

        # Clean title (remove newlines)
        title = clean_html_text(title.replace("\n", " "))

        # Extract arXiv ID
        arxiv_id = None
        entry_id = entry.get("id", "")
        if "arxiv.org/abs/" in entry_id:
            arxiv_id = entry_id.split("/abs/")[-1]
            # Remove version
            if "v" in arxiv_id:
                arxiv_id = arxiv_id.rsplit("v", 1)[0]

        # Extract authors
        authors = []
        for author in entry.get("authors", []):
            name = author.get("name", "")
            if name:
                authors.append(name)

        # Extract abstract
        abstract = entry.get("summary", "")
        if abstract:
            abstract = clean_html_text(abstract.replace("\n", " "))

        # Extract year from published date
        year = None
        published = entry.get("published", "")
        if published:
            with contextlib.suppress(ValueError, IndexError):
                year = int(published[:4])

        # Extract categories
        categories = []
        for tag in entry.get("tags", []):
            term = tag.get("term", "")
            if term:
                categories.append(term)

        # Build URLs
        url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None

        # Extract DOI if available
        doi = None
        for link in entry.get("links", []):
            if link.get("title") == "doi":
                doi_href = link.get("href", "")
                if "doi.org/" in doi_href:
                    doi = doi_href.split("doi.org/")[-1]

        # Primary category as journal substitute
        primary_category = entry.get("arxiv_primary_category", {}).get("term", "")
        journal = f"arXiv:{primary_category}" if primary_category else "arXiv"

        return Paper(
            title=title,
            authors=authors,
            abstract=abstract or None,
            doi=doi,
            year=year,
            journal=journal,
            url=url,
            pdf_url=pdf_url,
            source=self.name,
            source_id=arxiv_id,
            keywords=categories if categories else None,
            raw_data=dict(entry),
        )


# Add to API_LIMITS in base.py - done separately
# "arxiv": {
#     "per_request": 2000,
#     "offset_max": None,  # No hard limit
#     "cursor_support": False,
#     "note": "Rate limit: 1 request per 3 seconds",
# }
