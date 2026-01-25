"""OpenAlex API client for Paper-Ladder.

API Documentation: https://docs.openalex.org/
- Works: https://docs.openalex.org/api-entities/works
- Authors: https://docs.openalex.org/api-entities/authors
- Sources: https://docs.openalex.org/api-entities/sources
- Institutions: https://docs.openalex.org/api-entities/institutions
- Concepts: https://docs.openalex.org/api-entities/concepts
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from paper_ladder.clients.base import BaseClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import httpx
from paper_ladder.models import Author, Institution, Paper, SortBy
from paper_ladder.utils import clean_html_text, normalize_doi


class OpenAlexClient(BaseClient):
    """Client for the OpenAlex API.

    OpenAlex is a free, open catalog of the world's scholarly works.
    Rate limit: 100k credits/day with free API key, 100 credits/day without.

    API docs: https://docs.openalex.org/
    """

    name = "openalex"
    base_url = "https://api.openalex.org"

    async def _get(self, url: str, **kwargs: object) -> httpx.Response:
        """Make a rate-limited GET request with API key."""
        # Add API key to params if configured
        if self.config.openalex_api_key:
            params = kwargs.get("params", {})
            if isinstance(params, dict):
                params["api_key"] = self.config.openalex_api_key
                kwargs["params"] = params
        return await self._request("GET", url, **kwargs)

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
            limit: Maximum number of results (max 200 per page).
            offset: Number of results to skip.
            sort: Sort order - SortBy enum (RELEVANCE, CITATIONS, DATE, DATE_ASC)
                  or raw API value (cited_by_count, publication_date, relevance_score).
            **kwargs: Additional filters:
                - year: Publication year (int or range like "2020-2023")
                - open_access: Filter for open access papers (bool)
                - type: Work type (article, book, etc.)
                - institution: Filter by institution ID
                - author: Filter by author ID
                - cited_by_count: Minimum citation count

        Returns:
            List of Paper objects.
        """
        params: dict[str, Any] = {
            "search": query,
            "per_page": min(limit, 200),
            "page": (offset // max(limit, 1)) + 1,
        }

        # Build filter string
        filters = self._build_filters(kwargs)
        if filters:
            params["filter"] = ",".join(filters)

        # Add sorting (convert unified sort to API-specific)
        api_sort, _ = self._get_sort_param(sort)
        if api_sort:
            params["sort"] = api_sort

        response = await self._get("/works", params=params)
        data = response.json()

        papers = []
        for result in data.get("results", []):
            paper = self._parse_work(result)
            if paper:
                papers.append(paper)

        return papers

    async def search_with_cursor(
        self,
        query: str,
        max_results: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[Paper]:
        """Search for papers using cursor pagination.

        This method allows retrieving more than 10,000 results by using
        cursor-based pagination instead of offset pagination.

        Args:
            query: Search query string.
            max_results: Maximum number of results to retrieve. None for unlimited.
            **kwargs: Additional filters (same as search()).

        Yields:
            Paper objects.
        """
        cursor = "*"
        count = 0
        per_page = 200  # OpenAlex max per request

        while cursor:
            params: dict[str, Any] = {
                "search": query,
                "per_page": per_page,
                "cursor": cursor,
            }

            # Build filter string
            filters = self._build_filters(kwargs)
            if filters:
                params["filter"] = ",".join(filters)

            # Add sorting
            if "sort" in kwargs:
                params["sort"] = kwargs["sort"]

            response = await self._get("/works", params=params)
            data = response.json()

            for result in data.get("results", []):
                paper = self._parse_work(result)
                if paper:
                    yield paper
                    count += 1
                    if max_results and count >= max_results:
                        return

            # Get next cursor
            cursor = data.get("meta", {}).get("next_cursor")

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by DOI or OpenAlex ID.

        Args:
            identifier: DOI (with or without prefix) or OpenAlex ID (W123456789).

        Returns:
            Paper object if found, None otherwise.
        """
        # Normalize DOI if provided
        normalized = normalize_doi(identifier)
        if normalized:
            identifier = f"https://doi.org/{normalized}"

        try:
            response = await self._get(f"/works/{identifier}")
            data = response.json()
            return self._parse_work(data)
        except Exception:
            return None

    async def get_paper_citations(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers that cite the given paper.

        Args:
            paper_id: OpenAlex work ID (W...) or DOI.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of citing papers.
        """
        # If it's a DOI, we need to get the OpenAlex ID first
        if not paper_id.startswith("W") and not paper_id.startswith("https://openalex.org"):
            paper = await self.get_paper(paper_id)
            if not paper or not paper.raw_data:
                return []
            paper_id = paper.raw_data.get("id", "")

        params: dict[str, Any] = {
            "filter": f"cites:{paper_id}",
            "per_page": min(limit, 200),
            "page": (offset // max(limit, 1)) + 1,
        }

        response = await self._get("/works", params=params)
        data = response.json()

        papers = []
        for result in data.get("results", []):
            paper = self._parse_work(result)
            if paper:
                papers.append(paper)

        return papers

    async def get_paper_references(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers referenced by the given paper.

        Args:
            paper_id: OpenAlex work ID or DOI.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of referenced papers.
        """
        # First get the paper to get its referenced_works
        paper = await self.get_paper(paper_id)
        if not paper or not paper.raw_data:
            return []

        referenced_works = paper.raw_data.get("referenced_works", [])
        if not referenced_works:
            return []

        # Batch fetch the referenced works
        # OpenAlex supports OR filters
        work_ids = referenced_works[offset : offset + limit]
        if not work_ids:
            return []

        filter_str = "|".join(work_ids)
        params: dict[str, Any] = {
            "filter": f"openalex_id:{filter_str}",
            "per_page": min(len(work_ids), 200),
        }

        response = await self._get("/works", params=params)
        data = response.json()

        papers = []
        for result in data.get("results", []):
            paper = self._parse_work(result)
            if paper:
                papers.append(paper)

        return papers

    # =========================================================================
    # Authors
    # =========================================================================

    async def search_authors(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Author]:
        """Search for authors.

        Args:
            query: Search query for author names.
            limit: Maximum number of results.
            offset: Number of results to skip.
            **kwargs: Additional filters:
                - institution: Filter by institution ID
                - has_orcid: Filter for authors with ORCID (bool)

        Returns:
            List of Author objects.
        """
        params: dict[str, Any] = {
            "search": query,
            "per_page": min(limit, 200),
            "page": (offset // max(limit, 1)) + 1,
        }

        filters = []
        if kwargs.get("institution"):
            filters.append(f"last_known_institution.id:{kwargs['institution']}")
        if kwargs.get("has_orcid"):
            filters.append("has_orcid:true")

        if filters:
            params["filter"] = ",".join(filters)

        response = await self._get("/authors", params=params)
        data = response.json()

        authors = []
        for result in data.get("results", []):
            author = self._parse_author(result)
            if author:
                authors.append(author)

        return authors

    async def get_author(self, identifier: str) -> Author | None:
        """Get an author by OpenAlex ID or ORCID.

        Args:
            identifier: OpenAlex author ID (A123456789) or ORCID.

        Returns:
            Author object if found, None otherwise.
        """
        # Check if it's an ORCID
        if identifier.startswith("0000-") or "orcid.org" in identifier:
            identifier = identifier.replace("https://orcid.org/", "")
            identifier = f"https://orcid.org/{identifier}"

        try:
            response = await self._get(f"/authors/{identifier}")
            data = response.json()
            return self._parse_author(data)
        except Exception:
            return None

    async def get_author_papers(
        self,
        author_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers by an author.

        Args:
            author_id: OpenAlex author ID.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of papers by the author.
        """
        params: dict[str, Any] = {
            "filter": f"author.id:{author_id}",
            "per_page": min(limit, 200),
            "page": (offset // max(limit, 1)) + 1,
            "sort": "cited_by_count:desc",
        }

        response = await self._get("/works", params=params)
        data = response.json()

        papers = []
        for result in data.get("results", []):
            paper = self._parse_work(result)
            if paper:
                papers.append(paper)

        return papers

    # =========================================================================
    # Institutions
    # =========================================================================

    async def search_institutions(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Institution]:
        """Search for institutions.

        Args:
            query: Search query for institution names.
            limit: Maximum number of results.
            offset: Number of results to skip.
            **kwargs: Additional filters:
                - country: Filter by country code (e.g., "US", "GB")
                - type: Institution type (education, company, etc.)

        Returns:
            List of Institution objects.
        """
        params: dict[str, Any] = {
            "search": query,
            "per_page": min(limit, 200),
            "page": (offset // max(limit, 1)) + 1,
        }

        filters = []
        if kwargs.get("country"):
            filters.append(f"country_code:{kwargs['country']}")
        if kwargs.get("type"):
            filters.append(f"type:{kwargs['type']}")

        if filters:
            params["filter"] = ",".join(filters)

        response = await self._get("/institutions", params=params)
        data = response.json()

        institutions = []
        for result in data.get("results", []):
            inst = self._parse_institution(result)
            if inst:
                institutions.append(inst)

        return institutions

    async def get_institution(self, identifier: str) -> Institution | None:
        """Get an institution by OpenAlex ID or ROR.

        Args:
            identifier: OpenAlex institution ID (I123456789) or ROR.

        Returns:
            Institution object if found, None otherwise.
        """
        try:
            response = await self._get(f"/institutions/{identifier}")
            data = response.json()
            return self._parse_institution(data)
        except Exception:
            return None

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_filters(self, kwargs: dict[str, Any]) -> list[str]:
        """Build filter list from kwargs."""
        filters = []

        if "year" in kwargs:
            year = kwargs["year"]
            if isinstance(year, str) and "-" in year:
                filters.append(f"publication_year:{year}")
            else:
                filters.append(f"publication_year:{year}")

        if kwargs.get("open_access"):
            filters.append("is_oa:true")

        if "type" in kwargs:
            filters.append(f"type:{kwargs['type']}")

        if "institution" in kwargs:
            filters.append(f"institutions.id:{kwargs['institution']}")

        if "author" in kwargs:
            filters.append(f"author.id:{kwargs['author']}")

        if "cited_by_count" in kwargs:
            filters.append(f"cited_by_count:>{kwargs['cited_by_count']}")

        return filters

    def _parse_work(self, data: dict[str, Any]) -> Paper | None:
        """Parse an OpenAlex work object into a Paper."""
        if not data:
            return None

        title = data.get("title", "")
        if not title:
            return None

        # Extract authors
        authors = []
        for authorship in data.get("authorships", []):
            author = authorship.get("author", {})
            name = author.get("display_name")
            if name:
                authors.append(name)

        # Extract abstract (OpenAlex uses inverted index)
        abstract = None
        abstract_index = data.get("abstract_inverted_index")
        if abstract_index:
            abstract = self._reconstruct_abstract(abstract_index)

        # Extract DOI
        doi = normalize_doi(data.get("doi"))

        # Extract year
        year = data.get("publication_year")

        # Extract journal/venue
        journal = None
        primary_location = data.get("primary_location", {})
        if primary_location:
            source = primary_location.get("source", {})
            if source:
                journal = source.get("display_name")

        # Extract URLs
        url = data.get("id")  # OpenAlex URL
        pdf_url = None

        # Try to get PDF URL from open access location
        oa_url = data.get("open_access", {}).get("oa_url")
        if oa_url and oa_url.lower().endswith(".pdf"):
            pdf_url = oa_url
        elif primary_location:
            pdf_url = primary_location.get("pdf_url")

        # Get landing page URL
        if primary_location.get("landing_page_url"):
            url = primary_location["landing_page_url"]

        return Paper(
            title=clean_html_text(title),
            authors=authors,
            abstract=clean_html_text(abstract) if abstract else None,
            doi=doi,
            year=year,
            journal=journal,
            url=url,
            pdf_url=pdf_url,
            source=self.name,
            raw_data=data,
            citations_count=data.get("cited_by_count"),
            references_count=len(data.get("referenced_works", [])),
            open_access=data.get("open_access", {}).get("is_oa"),
            keywords=[
                c.get("display_name", "")
                for c in data.get("concepts", [])[:5]
                if c.get("display_name")
            ],
        )

    def _parse_author(self, data: dict[str, Any]) -> Author | None:
        """Parse an OpenAlex author object into an Author."""
        if not data:
            return None

        name = data.get("display_name", "")
        if not name:
            return None

        # Extract affiliations
        affiliations = []
        last_inst = data.get("last_known_institution", {})
        if last_inst:
            inst_name = last_inst.get("display_name")
            if inst_name:
                affiliations.append(inst_name)

        # Get ORCID
        orcid = None
        ids = data.get("ids", {})
        if ids.get("orcid"):
            orcid = ids["orcid"].replace("https://orcid.org/", "")

        return Author(
            name=name,
            source_id=data.get("id"),
            source=self.name,
            affiliations=affiliations,
            orcid=orcid,
            url=data.get("id"),
            paper_count=data.get("works_count"),
            citation_count=data.get("cited_by_count"),
            h_index=data.get("summary_stats", {}).get("h_index"),
            raw_data=data,
        )

    def _parse_institution(self, data: dict[str, Any]) -> Institution | None:
        """Parse an OpenAlex institution object into an Institution."""
        if not data:
            return None

        name = data.get("display_name", "")
        if not name:
            return None

        return Institution(
            name=name,
            source_id=data.get("id"),
            source=self.name,
            country=data.get("country_code"),
            type=data.get("type"),
            url=data.get("homepage_url"),
            paper_count=data.get("works_count"),
            citation_count=data.get("cited_by_count"),
            raw_data=data,
        )

    def _reconstruct_abstract(self, inverted_index: dict[str, list[int]]) -> str:
        """Reconstruct abstract text from OpenAlex inverted index format."""
        if not inverted_index:
            return ""

        # Find the maximum position to determine array size
        max_pos = 0
        for positions in inverted_index.values():
            if positions:
                max_pos = max(max_pos, max(positions))

        # Build the abstract word by word
        words = [""] * (max_pos + 1)
        for word, positions in inverted_index.items():
            for pos in positions:
                words[pos] = word

        return " ".join(words)
