"""Google Scholar client via SerpAPI for Paper-Ladder.

API Documentation: https://serpapi.com/google-scholar-api
- Organic Results: https://serpapi.com/google-scholar-organic-results
- Author Profiles: https://serpapi.com/google-scholar-profiles
- Author Profile: https://serpapi.com/google-scholar-author-api
- Cite Results: https://serpapi.com/google-scholar-cite-api
"""

from __future__ import annotations

from typing import Any

from paper_ladder.clients.base import BaseClient, sort_papers
from paper_ladder.models import Author, Paper, SortBy
from paper_ladder.utils import clean_html_text, is_pdf_url, normalize_doi


class GoogleScholarClient(BaseClient):
    """Client for Google Scholar via SerpAPI.

    Requires a SerpAPI key from https://serpapi.com/
    Cost: ~$0.015 per search.

    API docs: https://serpapi.com/google-scholar-api
    """

    name = "google_scholar"
    base_url = "https://serpapi.com"

    @property
    def api_key(self) -> str | None:
        """Get the SerpAPI key from config."""
        return self.config.serpapi_api_key

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        sort: SortBy | str | None = None,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers on Google Scholar.

        Args:
            query: Search query string.
            limit: Maximum number of results (max 20 per page).
            offset: Number of results to skip.
            sort: Sort order - SortBy enum (RELEVANCE, CITATIONS, DATE, DATE_ASC).
                  Note: Google Scholar search API doesn't support sorting,
                  so non-relevance sorts are applied client-side.
            **kwargs: Additional parameters (year_low, year_high, etc.).

        Returns:
            List of Paper objects.

        Raises:
            ValueError: If API key is not configured.
        """
        if not self.api_key:
            raise ValueError(
                "SerpAPI key required for Google Scholar. Set 'serpapi_api_key' in config.yaml"
            )

        params: dict[str, Any] = {
            "engine": "google_scholar",
            "q": query,
            "num": min(limit, 20),
            "start": offset,
            "api_key": self.api_key,
        }

        # Add year filters
        if "year_low" in kwargs:
            params["as_ylo"] = kwargs["year_low"]
        if "year_high" in kwargs:
            params["as_yhi"] = kwargs["year_high"]
        if "year" in kwargs:
            params["as_ylo"] = kwargs["year"]
            params["as_yhi"] = kwargs["year"]

        response = await self._get("/search", params=params)
        data = response.json()

        papers = []
        for result in data.get("organic_results", []):
            paper = self._parse_result(result)
            if paper:
                papers.append(paper)

        # Apply client-side sorting (Google Scholar API doesn't support sorting)
        if sort and sort != SortBy.RELEVANCE:
            sort_enum = sort if isinstance(sort, SortBy) else SortBy(sort)
            papers = sort_papers(papers, sort_enum)

        return papers

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by searching for its DOI or title.

        Note: Google Scholar doesn't have a direct lookup API,
        so this performs a search with the identifier.

        Args:
            identifier: DOI or title to search for.

        Returns:
            Paper object if found, None otherwise.
        """
        if not self.api_key:
            raise ValueError(
                "SerpAPI key required for Google Scholar. Set 'serpapi_api_key' in config.yaml"
            )

        # Search for the identifier
        papers = await self.search(identifier, limit=1)
        return papers[0] if papers else None

    async def get_cite_info(self, result_id: str) -> dict[str, Any] | None:
        """Get citation information for a paper.

        Args:
            result_id: Google Scholar result ID.

        Returns:
            Citation information dict or None.
        """
        if not self.api_key:
            return None

        params: dict[str, Any] = {
            "engine": "google_scholar_cite",
            "q": result_id,
            "api_key": self.api_key,
        }

        try:
            response = await self._get("/search", params=params)
            return response.json()
        except Exception:
            return None

    async def get_paper_citations(
        self,
        cites_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers that cite the given paper.

        Args:
            cites_id: Google Scholar citation ID (from inline_links.cited_by.cites_id).
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of citing papers.
        """
        if not self.api_key:
            raise ValueError(
                "SerpAPI key required for Google Scholar. Set 'serpapi_api_key' in config.yaml"
            )

        params: dict[str, Any] = {
            "engine": "google_scholar",
            "cites": cites_id,
            "num": min(limit, 20),
            "start": offset,
            "api_key": self.api_key,
        }

        response = await self._get("/search", params=params)
        data = response.json()

        papers = []
        for result in data.get("organic_results", []):
            paper = self._parse_result(result)
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
        """Search for author profiles on Google Scholar.

        Args:
            query: Search query (author name).
            limit: Maximum number of results (max 10).
            offset: Number of results to skip (multiples of 10).
            **kwargs: Additional filters:
                - affiliation: Filter by affiliation (institution name)

        Returns:
            List of Author objects.
        """
        if not self.api_key:
            raise ValueError(
                "SerpAPI key required for Google Scholar. Set 'serpapi_api_key' in config.yaml"
            )

        # Build mauthors parameter for filtering
        mauthors = query
        if kwargs.get("affiliation"):
            mauthors = f"{query} label:{kwargs['affiliation']}"

        params: dict[str, Any] = {
            "engine": "google_scholar_profiles",
            "mauthors": mauthors,
            "api_key": self.api_key,
        }

        # Pagination for profiles is by "after_author" token, not offset
        # For simplicity, we just get one page

        response = await self._get("/search", params=params)
        data = response.json()

        authors = []
        for result in data.get("profiles", []):
            author = self._parse_author_profile(result)
            if author:
                authors.append(author)
                if len(authors) >= limit:
                    break

        return authors

    async def get_author(self, author_id: str) -> Author | None:
        """Get an author profile by Google Scholar author ID.

        Args:
            author_id: Google Scholar author ID.

        Returns:
            Author object if found, None otherwise.
        """
        if not self.api_key:
            raise ValueError(
                "SerpAPI key required for Google Scholar. Set 'serpapi_api_key' in config.yaml"
            )

        params: dict[str, Any] = {
            "engine": "google_scholar_author",
            "author_id": author_id,
            "api_key": self.api_key,
        }

        try:
            response = await self._get("/search", params=params)
            data = response.json()
            return self._parse_author_detail(data)
        except Exception:
            return None

    async def get_author_papers(
        self,
        author_id: str,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "cited",
    ) -> list[Paper]:
        """Get papers by an author.

        Args:
            author_id: Google Scholar author ID.
            limit: Maximum number of results (max 100).
            offset: Number of results to skip.
            sort_by: Sort order - "cited" (most cited) or "pubdate" (most recent).

        Returns:
            List of papers by the author.
        """
        if not self.api_key:
            raise ValueError(
                "SerpAPI key required for Google Scholar. Set 'serpapi_api_key' in config.yaml"
            )

        params: dict[str, Any] = {
            "engine": "google_scholar_author",
            "author_id": author_id,
            "num": min(limit, 100),
            "start": offset,
            "sort": "cited" if sort_by == "cited" else "pubdate",
            "api_key": self.api_key,
        }

        response = await self._get("/search", params=params)
        data = response.json()

        papers = []
        for article in data.get("articles", []):
            paper = self._parse_author_article(article)
            if paper:
                papers.append(paper)

        return papers

    # =========================================================================
    # Helper Methods - Papers
    # =========================================================================

    def _parse_result(self, data: dict[str, Any]) -> Paper | None:
        """Parse a Google Scholar search result into a Paper.

        Args:
            data: Google Scholar result JSON object.

        Returns:
            Paper object or None if parsing fails.
        """
        if not data:
            return None

        title = data.get("title", "")
        if not title:
            return None

        # Extract authors from publication info
        authors = []
        pub_info = data.get("publication_info", {})
        author_str = pub_info.get("authors", [])

        if isinstance(author_str, list):
            for author in author_str:
                name = author.get("name")
                if name:
                    authors.append(name)
        elif isinstance(author_str, str):
            authors = [a.strip() for a in author_str.split(",") if a.strip()]

        # Try to extract year from summary
        year = None
        summary = pub_info.get("summary", "")
        if summary:
            # Year is usually in format "Author1, Author2 - Journal, Year"
            parts = summary.split(" - ")
            if len(parts) >= 2:
                year_part = parts[-1]
                for word in year_part.replace(",", " ").split():
                    if word.isdigit() and 1900 <= int(word) <= 2100:
                        year = int(word)
                        break

        # Extract DOI if available (often not in Google Scholar results)
        doi = None
        inline_links = data.get("inline_links", {})
        # Sometimes DOI is in the link
        link = data.get("link", "")
        if "doi.org/" in link:
            doi = normalize_doi(link)

        # Extract URLs
        url = data.get("link")
        pdf_url = None

        # Check resources for PDF
        resources = data.get("resources", [])
        for resource in resources:
            resource_link = resource.get("link", "")
            if is_pdf_url(resource_link) or resource.get("file_format") == "PDF":
                pdf_url = resource_link
                break

        # Extract journal from summary
        journal = None
        if summary:
            parts = summary.split(" - ")
            if len(parts) >= 2:
                journal_part = parts[-1].split(",")[0].strip()
                if journal_part and not journal_part.isdigit():
                    journal = journal_part

        return Paper(
            title=clean_html_text(title),
            authors=authors,
            abstract=clean_html_text(data.get("snippet", "")) or None,
            doi=doi,
            year=year,
            journal=journal,
            url=url,
            pdf_url=pdf_url,
            source=self.name,
            raw_data=data,
            citations_count=inline_links.get("cited_by", {}).get("total"),
        )

    def _parse_author_article(self, data: dict[str, Any]) -> Paper | None:
        """Parse a Google Scholar author article into a Paper.

        Args:
            data: Author article JSON object.

        Returns:
            Paper object or None if parsing fails.
        """
        if not data:
            return None

        title = data.get("title", "")
        if not title:
            return None

        # Extract authors
        authors_str = data.get("authors", "")
        authors = [a.strip() for a in authors_str.split(",") if a.strip()]

        # Extract year
        year = data.get("year")
        if year and isinstance(year, str):
            try:
                year = int(year)
            except ValueError:
                year = None

        return Paper(
            title=clean_html_text(title),
            authors=authors,
            abstract=None,  # Not available in author articles
            doi=None,
            year=year,
            journal=None,
            url=data.get("link"),
            pdf_url=None,
            source=self.name,
            raw_data=data,
            citations_count=data.get("cited_by", {}).get("value"),
        )

    # =========================================================================
    # Helper Methods - Authors
    # =========================================================================

    def _parse_author_profile(self, data: dict[str, Any]) -> Author | None:
        """Parse a Google Scholar author profile search result into an Author.

        Args:
            data: Profile search result JSON object.

        Returns:
            Author object or None if parsing fails.
        """
        if not data:
            return None

        name = data.get("name", "")
        if not name:
            return None

        # Extract affiliations
        affiliations = []
        affil = data.get("affiliations")
        if affil:
            affiliations.append(affil)

        return Author(
            name=name,
            source_id=data.get("author_id"),
            source=self.name,
            affiliations=affiliations,
            orcid=None,  # Not available in Google Scholar
            url=data.get("link"),
            paper_count=None,  # Not in profile search
            citation_count=data.get("cited_by"),
            h_index=None,  # Not in profile search
            raw_data=data,
        )

    def _parse_author_detail(self, data: dict[str, Any]) -> Author | None:
        """Parse a Google Scholar author detail response into an Author.

        Args:
            data: Author detail JSON object.

        Returns:
            Author object or None if parsing fails.
        """
        if not data:
            return None

        author_data = data.get("author", {})
        name = author_data.get("name", "")
        if not name:
            return None

        # Extract affiliations
        affiliations = []
        affil = author_data.get("affiliations")
        if affil:
            affiliations.append(affil)

        # Extract h-index and other metrics from cited_by
        cited_by = data.get("cited_by", {})
        h_index = None
        citation_count = None

        # Look for h-index in the table
        table = cited_by.get("table", [])
        for row in table:
            if row.get("h_index"):
                h_index = row.get("h_index", {}).get("all")

        # Get total citations from graph data
        graph = cited_by.get("graph", [])
        citation_count = graph[-1].get("citations") if graph else None

        return Author(
            name=name,
            source_id=data.get("search_parameters", {}).get("author_id"),
            source=self.name,
            affiliations=affiliations,
            orcid=None,  # Not available in Google Scholar
            url=author_data.get("link"),
            paper_count=None,  # Would need to count articles
            citation_count=citation_count,
            h_index=h_index,
            raw_data=data,
        )
