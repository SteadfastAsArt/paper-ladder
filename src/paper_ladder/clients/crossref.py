"""Crossref API client for Paper-Ladder.

API Documentation: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- Works: https://api.crossref.org/works
- Rate Limits: Use polite pool with mailto parameter for better performance
- Filters: https://api.crossref.org/swagger-ui/index.html
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from paper_ladder.clients.base import BaseClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
from paper_ladder.config import get_config
from paper_ladder.models import Paper
from paper_ladder.utils import clean_html_text, normalize_doi


class CrossrefClient(BaseClient):
    """Client for the Crossref API.

    Crossref is a DOI registration agency with metadata for over 150 million records.
    No authentication required. Use polite pool (mailto parameter) for better rate limits.

    API docs: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
    """

    name = "crossref"
    base_url = "https://api.crossref.org"

    # Polite pool email - can be overridden via config
    DEFAULT_MAILTO = "paper-ladder@example.com"

    # =========================================================================
    # Works (Papers)
    # =========================================================================

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers matching the query.

        Args:
            query: Search query string.
            limit: Maximum number of results (max 1000 per page).
            offset: Number of results to skip.
            **kwargs: Additional filters:
                - year: Publication year (int)
                - from_year: Start year for date range
                - until_year: End year for date range
                - type: Work type (journal-article, book-chapter, etc.)
                - has_abstract: Filter for works with abstracts (bool)
                - has_references: Filter for works with references (bool)
                - has_orcid: Filter for works with ORCID (bool)
                - issn: Filter by journal ISSN
                - sort: Sort field (relevance, published, deposited, indexed,
                    is-referenced-by-count)
                - order: Sort order (asc, desc)

        Returns:
            List of Paper objects.
        """
        params: dict[str, Any] = {
            "query": query,
            "rows": min(limit, 1000),
            "offset": offset,
            "mailto": self._get_mailto(),
        }

        # Build filter string
        filters = self._build_filters(kwargs)
        if filters:
            params["filter"] = ",".join(filters)

        # Add sorting
        if "sort" in kwargs:
            params["sort"] = kwargs["sort"]
            params["order"] = kwargs.get("order", "desc")

        response = await self._get("/works", params=params)
        data = response.json()

        papers = []
        message = data.get("message", {})
        for item in message.get("items", []):
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
        """Search for papers using cursor pagination.

        This method allows retrieving large result sets efficiently using
        cursor-based pagination. Note that cursors expire after 5 minutes.

        Args:
            query: Search query string.
            max_results: Maximum number of results to retrieve. None for unlimited.
            **kwargs: Additional filters (same as search()).

        Yields:
            Paper objects.
        """
        cursor = "*"
        count = 0
        rows = 1000  # Crossref max per request

        while cursor:
            params: dict[str, Any] = {
                "query": query,
                "rows": rows,
                "cursor": cursor,
                "mailto": self._get_mailto(),
            }

            # Build filter string
            filters = self._build_filters(kwargs)
            if filters:
                params["filter"] = ",".join(filters)

            # Add sorting
            if "sort" in kwargs:
                params["sort"] = kwargs["sort"]
                params["order"] = kwargs.get("order", "desc")

            response = await self._get("/works", params=params)
            data = response.json()
            message = data.get("message", {})
            items = message.get("items", [])

            for item in items:
                paper = self._parse_work(item)
                if paper:
                    yield paper
                    count += 1
                    if max_results and count >= max_results:
                        return

            # Check if there are more results
            if len(items) < rows:
                break

            # Get next cursor
            cursor = message.get("next-cursor")

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by DOI.

        Args:
            identifier: DOI (with or without prefix/URL).

        Returns:
            Paper object if found, None otherwise.
        """
        # Normalize DOI
        doi = normalize_doi(identifier)
        if not doi:
            return None

        try:
            params = {"mailto": self._get_mailto()}
            response = await self._get(f"/works/{doi}", params=params)
            data = response.json()
            message = data.get("message", {})
            return self._parse_work(message)
        except Exception:
            return None

    async def get_paper_references(
        self,
        doi: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers referenced by the given paper.

        Args:
            doi: DOI of the paper.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of referenced papers.
        """
        # First get the paper to extract reference DOIs
        paper = await self.get_paper(doi)
        if not paper or not paper.raw_data:
            return []

        references = paper.raw_data.get("reference", [])
        if not references:
            return []

        # Extract DOIs from references
        ref_dois = []
        for ref in references:
            ref_doi = ref.get("DOI")
            if ref_doi:
                ref_dois.append(ref_doi)

        if not ref_dois:
            return []

        # Fetch referenced papers (paginate)
        ref_dois = ref_dois[offset : offset + limit]
        papers = []

        for ref_doi in ref_dois:
            ref_paper = await self.get_paper(ref_doi)
            if ref_paper:
                papers.append(ref_paper)

        return papers

    async def get_journal(self, issn: str) -> dict[str, Any] | None:
        """Get journal metadata by ISSN.

        Args:
            issn: Journal ISSN.

        Returns:
            Journal metadata dict if found, None otherwise.
        """
        try:
            params = {"mailto": self._get_mailto()}
            response = await self._get(f"/journals/{issn}", params=params)
            data = response.json()
            return data.get("message")
        except Exception:
            return None

    async def get_journal_works(
        self,
        issn: str,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get works published in a journal.

        Args:
            issn: Journal ISSN.
            query: Optional search query to filter works.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of papers from the journal.
        """
        params: dict[str, Any] = {
            "rows": min(limit, 1000),
            "offset": offset,
            "mailto": self._get_mailto(),
        }

        if query:
            params["query"] = query

        try:
            response = await self._get(f"/journals/{issn}/works", params=params)
            data = response.json()

            papers = []
            message = data.get("message", {})
            for item in message.get("items", []):
                paper = self._parse_work(item)
                if paper:
                    papers.append(paper)

            return papers
        except Exception:
            return []

    async def get_funder(self, funder_id: str) -> dict[str, Any] | None:
        """Get funder metadata by ID.

        Args:
            funder_id: Funder DOI or ID.

        Returns:
            Funder metadata dict if found, None otherwise.
        """
        try:
            params = {"mailto": self._get_mailto()}
            response = await self._get(f"/funders/{funder_id}", params=params)
            data = response.json()
            return data.get("message")
        except Exception:
            return None

    async def get_funder_works(
        self,
        funder_id: str,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get works funded by a funder.

        Args:
            funder_id: Funder DOI or ID.
            query: Optional search query to filter works.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of funded papers.
        """
        params: dict[str, Any] = {
            "rows": min(limit, 1000),
            "offset": offset,
            "mailto": self._get_mailto(),
        }

        if query:
            params["query"] = query

        try:
            response = await self._get(f"/funders/{funder_id}/works", params=params)
            data = response.json()

            papers = []
            message = data.get("message", {})
            for item in message.get("items", []):
                paper = self._parse_work(item)
                if paper:
                    papers.append(paper)

            return papers
        except Exception:
            return []

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_mailto(self) -> str:
        """Get the mailto address for polite pool."""
        config = get_config()
        if config.crossref_mailto:
            return config.crossref_mailto
        return self.DEFAULT_MAILTO

    def _build_filters(self, kwargs: dict[str, Any]) -> list[str]:
        """Build filter list from kwargs."""
        filters = []

        # Year filters
        if "year" in kwargs:
            year = kwargs["year"]
            filters.append(f"from-pub-date:{year}")
            filters.append(f"until-pub-date:{year}")
        else:
            if "from_year" in kwargs:
                filters.append(f"from-pub-date:{kwargs['from_year']}")
            if "until_year" in kwargs:
                filters.append(f"until-pub-date:{kwargs['until_year']}")

        # Work type filter
        if "type" in kwargs:
            filters.append(f"type:{kwargs['type']}")

        # Content filters
        if kwargs.get("has_abstract"):
            filters.append("has-abstract:true")

        if kwargs.get("has_references"):
            filters.append("has-references:true")

        if kwargs.get("has_orcid"):
            filters.append("has-orcid:true")

        # Journal filter
        if "issn" in kwargs:
            filters.append(f"issn:{kwargs['issn']}")

        # Funder filter
        if "funder" in kwargs:
            filters.append(f"funder:{kwargs['funder']}")

        # Open access filter
        if kwargs.get("open_access"):
            filters.append("has-license:true")

        return filters

    def _parse_work(self, data: dict[str, Any]) -> Paper | None:
        """Parse a Crossref work object into a Paper."""
        if not data:
            return None

        # Extract title
        titles = data.get("title", [])
        title = titles[0] if titles else None
        if not title:
            return None

        # Extract authors
        authors = []
        for author in data.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            if family:
                name = f"{given} {family}".strip() if given else family
                authors.append(name)

        # Extract abstract
        abstract = data.get("abstract")
        if abstract:
            # Crossref abstracts may contain JATS XML tags
            abstract = clean_html_text(abstract)

        # Extract DOI
        doi = normalize_doi(data.get("DOI"))

        # Extract year from various date fields
        year = None
        for date_field in ["published-print", "published-online", "published", "created"]:
            date_parts = data.get(date_field, {}).get("date-parts", [[]])
            if date_parts and date_parts[0]:
                year = date_parts[0][0]
                break

        if not year:
            # Try issued date
            issued = data.get("issued", {}).get("date-parts", [[]])
            if issued and issued[0]:
                year = issued[0][0]

        # Extract journal/container
        journal = None
        container_titles = data.get("container-title", [])
        if container_titles:
            journal = container_titles[0]

        # Extract URLs
        url = data.get("URL")
        pdf_url = None

        # Try to find PDF URL in links
        for link in data.get("link", []):
            content_type = link.get("content-type", "")
            if "pdf" in content_type.lower():
                pdf_url = link.get("URL")
                break

        # Check resource link
        if not pdf_url:
            resource = data.get("resource", {})
            primary = resource.get("primary", {})
            resource_url = primary.get("URL", "")
            if resource_url and resource_url.lower().endswith(".pdf"):
                pdf_url = resource_url

        # Extract citation count
        citations_count = data.get("is-referenced-by-count")

        # Extract reference count
        references_count = data.get("reference-count") or data.get("references-count")

        # Determine open access status
        open_access = None
        licenses = data.get("license", [])
        if licenses:
            # Check if any license is open
            for lic in licenses:
                lic_url = lic.get("URL", "").lower()
                if "creativecommons" in lic_url or "open" in lic_url:
                    open_access = True
                    break

        # Extract keywords/subjects
        keywords = data.get("subject", [])

        return Paper(
            title=clean_html_text(title),
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
            references_count=references_count,
            open_access=open_access,
            keywords=keywords[:10] if keywords else [],
        )
