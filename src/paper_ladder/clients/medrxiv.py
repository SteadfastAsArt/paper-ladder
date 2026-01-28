"""medRxiv client for Paper-Ladder.

API Documentation: https://api.biorxiv.org/
medRxiv shares the same API as bioRxiv with a different server parameter.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from paper_ladder.clients.base import BaseClient, sort_papers
from paper_ladder.models import Paper, SortBy
from paper_ladder.utils import clean_html_text

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class MedrxivClient(BaseClient):
    """Client for medRxiv preprint server.

    medRxiv is a preprint repository for health sciences research.
    The API is shared with bioRxiv but uses a different server parameter.

    API docs: https://api.biorxiv.org/

    Note: medRxiv API returns batches of 100 results.
    """

    name = "medrxiv"
    base_url = "https://api.biorxiv.org"

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        sort: SortBy | str | None = None,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers on medRxiv.

        Note: medRxiv API doesn't support full-text search directly.
        This method fetches recent preprints and filters by query.

        Args:
            query: Search query (searches title and abstract locally).
            limit: Maximum number of results.
            offset: Number of results to skip.
            sort: Sort order - SortBy enum.
            **kwargs: Additional parameters:
                - from_date: Start date (YYYY-MM-DD)
                - to_date: End date (YYYY-MM-DD)
                - days: Number of days to look back (default 30)

        Returns:
            List of Paper objects matching the query.
        """
        # Determine date range
        from_date = kwargs.get("from_date")
        to_date = kwargs.get("to_date")
        days = kwargs.get("days", 30)

        if not from_date or not to_date:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=int(days))  # type: ignore[arg-type]
            from_date = start_date.strftime("%Y-%m-%d")
            to_date = end_date.strftime("%Y-%m-%d")

        # Fetch papers and filter by query
        papers = await self._fetch_by_date_range(
            str(from_date), str(to_date), query=query.lower(), max_results=limit + offset
        )

        # Apply offset
        papers = papers[offset : offset + limit]

        # Apply sorting
        if sort:
            sort_enum = sort if isinstance(sort, SortBy) else SortBy(sort)
            papers = sort_papers(papers, sort_enum)

        return papers

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by DOI.

        Args:
            identifier: medRxiv DOI (e.g., "10.1101/2024.01.01.24300001").

        Returns:
            Paper object if found, None otherwise.
        """
        # Normalize DOI
        doi = identifier.strip()
        if doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "")
        if doi.startswith("http://doi.org/"):
            doi = doi.replace("http://doi.org/", "")

        # Use the details endpoint with DOI
        try:
            response = await self._get(f"/details/medrxiv/{doi}")
            data = response.json()

            collection = data.get("collection", [])
            if collection:
                return self._parse_entry(collection[0])
        except Exception:
            pass

        return None

    async def search_by_date(
        self,
        from_date: str,
        to_date: str,
        limit: int = 100,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers by date range.

        Args:
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            limit: Maximum number of results.
            offset: Number of results to skip.
            **kwargs: Additional parameters.

        Returns:
            List of papers in the date range.
        """
        papers = await self._fetch_by_date_range(from_date, to_date, max_results=limit + offset)
        return papers[offset : offset + limit]

    async def get_recent_papers(
        self,
        days: int = 7,
        limit: int = 100,
        **kwargs: object,
    ) -> list[Paper]:
        """Get recent papers from the last N days.

        Args:
            days: Number of days to look back.
            limit: Maximum number of results.
            **kwargs: Additional parameters.

        Returns:
            List of recent papers.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        return await self.search_by_date(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            limit=limit,
            **kwargs,
        )

    async def search_by_category(
        self,
        category: str,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 100,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers by medRxiv category.

        Args:
            category: medRxiv category (e.g., "infectious diseases", "epidemiology").
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).
            limit: Maximum number of results.
            **kwargs: Additional parameters.

        Returns:
            List of papers in the category.
        """
        # Set default date range
        if not from_date or not to_date:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            from_date = start_date.strftime("%Y-%m-%d")
            to_date = end_date.strftime("%Y-%m-%d")

        papers = await self._fetch_by_date_range(from_date, to_date, max_results=limit * 5)

        # Filter by category
        filtered = [p for p in papers if self._matches_category(p, category)]
        return filtered[:limit]

    async def search_with_cursor(
        self,
        query: str,
        max_results: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[Paper]:
        """Search using cursor pagination.

        Args:
            query: Search query string.
            max_results: Maximum number of results to retrieve.
            **kwargs: Additional parameters.

        Yields:
            Paper objects.
        """
        from_date = kwargs.get("from_date")
        to_date = kwargs.get("to_date")
        days = kwargs.get("days", 365)  # Default to 1 year for cursor search

        if not from_date or not to_date:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=int(days))  # type: ignore[arg-type]
            from_date = start_date.strftime("%Y-%m-%d")
            to_date = end_date.strftime("%Y-%m-%d")

        cursor = 0
        count = 0
        query_lower = query.lower()

        while True:
            # medRxiv returns 100 results per page
            url = f"/details/medrxiv/{from_date}/{to_date}/{cursor}"
            try:
                response = await self._get(url)
                data = response.json()
            except Exception:
                break

            collection = data.get("collection", [])
            if not collection:
                break

            for entry in collection:
                paper = self._parse_entry(entry)
                if paper and self._matches_query(paper, query_lower):
                    yield paper
                    count += 1
                    if max_results and count >= max_results:
                        return

            # Move to next page
            cursor += len(collection)

            # Check if there are more results
            total = data.get("messages", [{}])[0].get("total", 0)
            if cursor >= total:
                break

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _fetch_by_date_range(
        self,
        from_date: str,
        to_date: str,
        query: str | None = None,
        max_results: int = 1000,
    ) -> list[Paper]:
        """Fetch papers in a date range.

        Args:
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            query: Optional query to filter results.
            max_results: Maximum number of results.

        Returns:
            List of papers.
        """
        papers: list[Paper] = []
        cursor = 0

        while len(papers) < max_results:
            url = f"/details/medrxiv/{from_date}/{to_date}/{cursor}"
            try:
                response = await self._get(url)
                data = response.json()
            except Exception:
                break

            collection = data.get("collection", [])
            if not collection:
                break

            for entry in collection:
                paper = self._parse_entry(entry)
                if paper and (query is None or self._matches_query(paper, query)):
                    papers.append(paper)
                    if len(papers) >= max_results:
                        break

            cursor += len(collection)

            # Check if there are more results
            messages = data.get("messages", [{}])
            total = messages[0].get("total", 0) if messages else 0
            if cursor >= total:
                break

        return papers

    def _matches_query(self, paper: Paper, query: str) -> bool:
        """Check if a paper matches the search query.

        Args:
            paper: Paper to check.
            query: Lowercase query string.

        Returns:
            True if paper matches query.
        """
        if not query:
            return True

        # Search in title
        if paper.title and query in paper.title.lower():
            return True

        # Search in abstract
        if paper.abstract and query in paper.abstract.lower():
            return True

        # Search in authors
        return any(query in author.lower() for author in paper.authors)

    def _matches_category(self, paper: Paper, category: str) -> bool:
        """Check if a paper is in the specified category.

        Args:
            paper: Paper to check.
            category: Category to match.

        Returns:
            True if paper is in category.
        """
        category_lower = category.lower()
        raw_data = paper.raw_data or {}
        paper_category = raw_data.get("category", "").lower()
        return category_lower in paper_category

    def _parse_entry(self, entry: dict[str, Any]) -> Paper | None:
        """Parse a medRxiv API entry into a Paper.

        Args:
            entry: API response entry.

        Returns:
            Paper object or None if parsing fails.
        """
        title = entry.get("title", "")
        if not title:
            return None

        title = clean_html_text(title)

        # Extract DOI
        doi = entry.get("doi", "")

        # Extract authors (usually comma-separated string)
        authors_str = entry.get("authors", "")
        if isinstance(authors_str, str):
            # Split by semicolon or comma
            if ";" in authors_str:
                authors = [a.strip() for a in authors_str.split(";") if a.strip()]
            else:
                authors = [a.strip() for a in authors_str.split(",") if a.strip()]
        else:
            authors = []

        # Extract abstract
        abstract = entry.get("abstract", "")
        if abstract:
            abstract = clean_html_text(abstract)

        # Extract year from date
        year = None
        date_str = entry.get("date", "")
        if date_str:
            with contextlib.suppress(ValueError, IndexError):
                year = int(date_str[:4])

        # Build URLs
        url = f"https://www.medrxiv.org/content/{doi}" if doi else None
        pdf_url = f"https://www.medrxiv.org/content/{doi}.full.pdf" if doi else None

        # Category as journal
        category = entry.get("category", "")
        journal = f"medRxiv - {category}" if category else "medRxiv"

        return Paper(
            title=title,
            authors=authors,
            abstract=abstract or None,
            doi=doi or None,
            year=year,
            journal=journal,
            url=url,
            pdf_url=pdf_url,
            source=self.name,
            source_id=doi,
            raw_data=entry,
        )
