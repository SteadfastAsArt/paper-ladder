"""CORE API client for Paper-Ladder.

API Documentation: https://core.ac.uk/documentation
- API v3: https://api.core.ac.uk/v3
- Search: https://api.core.ac.uk/v3/search/works

CORE aggregates open access research papers from repositories worldwide.
Contains 150M+ open access publications.
Free API key required (register at https://core.ac.uk/register).
Rate limit: 10,000 requests/day.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from paper_ladder.clients.base import BaseClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
from paper_ladder.models import Paper, SortBy


class COREClient(BaseClient):
    """Client for the CORE API.

    CORE is the world's largest aggregator of open access research papers,
    harvesting from repositories and journals worldwide.

    API docs: https://core.ac.uk/documentation
    """

    name = "core"
    base_url = "https://api.core.ac.uk/v3"

    @property
    def api_key(self) -> str | None:
        """Get the CORE API key from config."""
        return self.config.core_api_key

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with API key."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # =========================================================================
    # Works (Papers)
    # =========================================================================

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        sort: SortBy | str | None = None,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers matching the query.

        Args:
            query: Search query string.
            limit: Maximum number of results (max 100 per page).
            offset: Number of results to skip.
            sort: Sort order - SortBy enum or raw field name.
            **kwargs: Additional filters:
                - year: Publication year (int)
                - from_year: Start year for date range
                - until_year: End year for date range
                - has_fulltext: Filter for papers with full text (bool)
                - repository: Filter by repository ID (int)

        Returns:
            List of Paper objects.
        """
        # Build search body
        body: dict[str, Any] = {
            "q": query,
            "limit": min(limit, 100),
            "offset": offset,
        }

        # Add filters
        filters = []
        if "year" in kwargs:
            filters.append(f"yearPublished:{kwargs['year']}")
        if "from_year" in kwargs:
            filters.append(f"yearPublished>={kwargs['from_year']}")
        if "until_year" in kwargs:
            filters.append(f"yearPublished<={kwargs['until_year']}")
        if kwargs.get("has_fulltext"):
            filters.append("fullTextLink:*")
        if "repository" in kwargs:
            filters.append(f"repositories.id:{kwargs['repository']}")

        if filters:
            body["q"] = f"({query}) AND {' AND '.join(filters)}"

        # Add sorting
        api_sort, _ = self._get_sort_param(sort)
        if api_sort:
            if sort == SortBy.DATE:
                body["sort"] = [{"yearPublished": "desc"}]
            elif sort == SortBy.DATE_ASC:
                body["sort"] = [{"yearPublished": "asc"}]
            elif sort == SortBy.CITATIONS:
                body["sort"] = [{"citationCount": "desc"}]

        response = await self._post(
            "/search/works",
            json=body,
            headers=self._get_headers(),
        )
        data = response.json()

        papers = []
        for item in data.get("results", []):
            paper = self._parse_work(item)
            if paper:
                papers.append(paper)

        return papers

    async def search_with_cursor(
        self,
        query: str,
        max_results: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[Paper]:
        """Search with pagination using offset.

        Args:
            query: Search query string.
            max_results: Maximum number of results to retrieve.
            **kwargs: Additional filters (same as search()).

        Yields:
            Paper objects.
        """
        offset = 0
        batch_size = 100  # CORE max page size
        count = 0

        while True:
            papers = await self.search(query, limit=batch_size, offset=offset, **kwargs)
            if not papers:
                break

            for paper in papers:
                yield paper
                count += 1
                if max_results and count >= max_results:
                    return

            offset += len(papers)
            if len(papers) < batch_size:
                break

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by CORE ID, DOI, or other identifier.

        Args:
            identifier: CORE ID, DOI, or OAI identifier.

        Returns:
            Paper object if found, None otherwise.
        """
        # Check if it's a DOI
        if identifier.startswith("10.") or "doi.org" in identifier:
            doi = identifier.replace("https://doi.org/", "").replace("http://doi.org/", "")
            papers = await self.search(f"doi:{doi}", limit=1)
            return papers[0] if papers else None

        # Try CORE ID
        try:
            response = await self._get(
                f"/works/{identifier}",
                headers=self._get_headers(),
            )
            data = response.json()
            return self._parse_work(data)
        except Exception:
            pass

        # Try as search
        papers = await self.search(identifier, limit=1)
        return papers[0] if papers else None

    async def get_paper_fulltext(self, paper_id: str) -> str | None:
        """Get the full text of a paper if available.

        Args:
            paper_id: CORE paper ID.

        Returns:
            Full text content as string, or None if not available.
        """
        try:
            response = await self._get(
                f"/works/{paper_id}",
                params={"fulltext": "true"},
                headers=self._get_headers(),
            )
            data = response.json()
            return data.get("fullText")
        except Exception:
            return None

    # =========================================================================
    # Data Providers (Repositories)
    # =========================================================================

    async def search_repositories(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs: object,
    ) -> list[dict[str, Any]]:
        """Search for data providers (repositories).

        Args:
            query: Search query string.
            limit: Maximum number of results.
            offset: Number of results to skip.
            **kwargs: Additional filters (unused).

        Returns:
            List of repository metadata dicts.
        """
        body: dict[str, Any] = {
            "q": query,
            "limit": min(limit, 100),
            "offset": offset,
        }

        response = await self._post(
            "/search/data-providers",
            json=body,
            headers=self._get_headers(),
        )
        data = response.json()

        return data.get("results", [])

    async def get_repository(self, repo_id: int) -> dict[str, Any] | None:
        """Get a data provider by ID.

        Args:
            repo_id: CORE data provider ID.

        Returns:
            Repository metadata dict if found, None otherwise.
        """
        try:
            response = await self._get(
                f"/data-providers/{repo_id}",
                headers=self._get_headers(),
            )
            return response.json()
        except Exception:
            return None

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_work(self, data: dict[str, Any]) -> Paper | None:
        """Parse a CORE work object into a Paper."""
        if not data:
            return None

        # Extract title
        title = data.get("title")
        if not title:
            return None

        # Extract authors
        authors = []
        for author in data.get("authors", []):
            if isinstance(author, dict):
                name = author.get("name")
                if name:
                    authors.append(name)
            elif isinstance(author, str):
                authors.append(author)

        # Extract abstract
        abstract = data.get("abstract")

        # Extract DOI
        doi = data.get("doi")
        if doi:
            # Clean DOI format
            doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")

        # Extract year
        year = data.get("yearPublished")

        # Extract journal/publisher
        journal = None
        publisher = data.get("publisher")
        if publisher:
            journal = publisher

        # Check for journal in other fields
        journals = data.get("journals", [])
        if journals and isinstance(journals[0], dict):
            journal = journals[0].get("title") or journal

        # Extract URLs
        url = None
        pdf_url = None

        # Try download URL first
        download_url = data.get("downloadUrl")
        if download_url:
            if download_url.lower().endswith(".pdf"):
                pdf_url = download_url
            else:
                url = download_url

        # Try source full text URLs
        source_fulltext = data.get("sourceFulltextUrls", [])
        if source_fulltext:
            for u in source_fulltext:
                if u and u.lower().endswith(".pdf"):
                    pdf_url = pdf_url or u
                else:
                    url = url or u

        # Try full text URL
        fulltext_url = data.get("fullTextLink")
        if fulltext_url and not pdf_url:
            if fulltext_url.lower().endswith(".pdf"):
                pdf_url = fulltext_url
            else:
                url = url or fulltext_url

        # OAI identifier as fallback
        oai = data.get("oai")
        if not url and oai:
            url = f"https://core.ac.uk/display/{data.get('id', oai)}"

        # Extract citation count
        citations_count = data.get("citationCount")

        # Determine open access status (CORE only indexes OA content)
        open_access = True

        # Extract subjects/keywords
        subjects = data.get("subjects", [])

        # Extract language
        language = data.get("language", {})
        if isinstance(language, dict):
            language = language.get("name")

        keywords = subjects[:10] if subjects else []

        return Paper(
            title=title,
            authors=authors,
            abstract=abstract,
            doi=doi,
            year=year,
            journal=journal,
            url=url,
            pdf_url=pdf_url,
            source=self.name,
            raw_data=data,
            citations_count=citations_count,
            references_count=None,
            open_access=open_access,
            keywords=keywords,
        )
