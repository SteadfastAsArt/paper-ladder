"""Semantic Scholar API client for Paper-Ladder.

API Documentation: https://api.semanticscholar.org/api-docs/
- Paper Search: https://api.semanticscholar.org/api-docs/#tag/Paper-Data/operation/get_graph_paper_relevance_search
- Author Search: https://api.semanticscholar.org/api-docs/#tag/Author-Data/operation/get_graph_get_author_search
- Batch Endpoints: https://api.semanticscholar.org/api-docs/#tag/Paper-Data/operation/post_graph_get_papers
- Recommendations: https://api.semanticscholar.org/api-docs/#tag/Recommendations-API
"""

from __future__ import annotations

from typing import Any

from paper_ladder.clients.base import BaseClient
from paper_ladder.models import Author, Paper
from paper_ladder.utils import clean_html_text, normalize_doi


class SemanticScholarClient(BaseClient):
    """Client for the Semantic Scholar API.

    Semantic Scholar is a free AI-powered research tool by Allen AI.
    Rate limit: 100 requests/5 minutes unauthenticated, 1 req/sec with API key.

    API docs: https://api.semanticscholar.org/
    """

    name = "semantic_scholar"
    base_url = "https://api.semanticscholar.org/graph/v1"

    @property
    def api_key(self) -> str | None:
        """Get the Semantic Scholar API key from config."""
        return self.config.semantic_scholar_api_key

    def _get_headers(self) -> dict[str, str]:
        """Get headers with API key if configured."""
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    # Fields to request from the API
    PAPER_FIELDS = [
        "paperId",
        "externalIds",
        "title",
        "abstract",
        "year",
        "venue",
        "authors",
        "citationCount",
        "referenceCount",
        "isOpenAccess",
        "openAccessPdf",
        "url",
        "fieldsOfStudy",
    ]

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
            limit: Maximum number of results (max 100).
            offset: Number of results to skip (max 9999).
            **kwargs: Additional parameters (year, fields_of_study, etc.).

        Returns:
            List of Paper objects.
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": min(limit, 100),
            "offset": min(offset, 9999),
            "fields": ",".join(self.PAPER_FIELDS),
        }

        # Add optional filters
        if "year" in kwargs:
            params["year"] = kwargs["year"]
        if "fields_of_study" in kwargs:
            params["fieldsOfStudy"] = kwargs["fields_of_study"]
        if kwargs.get("open_access"):
            params["openAccessPdf"] = ""

        response = await self._get("/paper/search", params=params, headers=self._get_headers())
        data = response.json()

        papers = []
        for result in data.get("data", []):
            paper = self._parse_paper(result)
            if paper:
                papers.append(paper)

        return papers

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by Semantic Scholar ID, DOI, or other identifier.

        Args:
            identifier: Paper ID. Can be:
                - Semantic Scholar paper ID
                - DOI (prefix with "DOI:")
                - arXiv ID (prefix with "ARXIV:")
                - Corpus ID (prefix with "CorpusId:")

        Returns:
            Paper object if found, None otherwise.
        """
        # If it looks like a DOI, add prefix
        normalized = normalize_doi(identifier)
        if normalized and "/" in normalized:
            identifier = f"DOI:{normalized}"

        try:
            params = {"fields": ",".join(self.PAPER_FIELDS)}
            response = await self._get(
                f"/paper/{identifier}", params=params, headers=self._get_headers()
            )
            data = response.json()
            return self._parse_paper(data)
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
            paper_id: Semantic Scholar paper ID or DOI.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of citing Paper objects.
        """
        normalized = normalize_doi(paper_id)
        if normalized and "/" in normalized:
            paper_id = f"DOI:{normalized}"

        params: dict[str, Any] = {
            "fields": ",".join(self.PAPER_FIELDS),
            "limit": min(limit, 1000),
            "offset": offset,
        }

        response = await self._get(
            f"/paper/{paper_id}/citations", params=params, headers=self._get_headers()
        )
        data = response.json()

        papers = []
        for item in data.get("data", []):
            citing_paper = item.get("citingPaper", {})
            paper = self._parse_paper(citing_paper)
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
            paper_id: Semantic Scholar paper ID or DOI.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of referenced Paper objects.
        """
        normalized = normalize_doi(paper_id)
        if normalized and "/" in normalized:
            paper_id = f"DOI:{normalized}"

        params: dict[str, Any] = {
            "fields": ",".join(self.PAPER_FIELDS),
            "limit": min(limit, 1000),
            "offset": offset,
        }

        response = await self._get(
            f"/paper/{paper_id}/references", params=params, headers=self._get_headers()
        )
        data = response.json()

        papers = []
        for item in data.get("data", []):
            cited_paper = item.get("citedPaper", {})
            paper = self._parse_paper(cited_paper)
            if paper:
                papers.append(paper)

        return papers

    # =========================================================================
    # Authors
    # =========================================================================

    AUTHOR_FIELDS = [
        "authorId",
        "name",
        "affiliations",
        "homepage",
        "paperCount",
        "citationCount",
        "hIndex",
        "externalIds",
    ]

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
            limit: Maximum number of results (max 1000).
            offset: Number of results to skip.
            **kwargs: Additional parameters (not currently used).

        Returns:
            List of Author objects.
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": min(limit, 1000),
            "offset": offset,
            "fields": ",".join(self.AUTHOR_FIELDS),
        }

        response = await self._get("/author/search", params=params, headers=self._get_headers())
        data = response.json()

        authors = []
        for result in data.get("data", []):
            author = self._parse_author(result)
            if author:
                authors.append(author)

        return authors

    async def get_author(self, author_id: str) -> Author | None:
        """Get an author by Semantic Scholar ID.

        Args:
            author_id: Semantic Scholar author ID.

        Returns:
            Author object if found, None otherwise.
        """
        try:
            params = {"fields": ",".join(self.AUTHOR_FIELDS)}
            response = await self._get(
                f"/author/{author_id}", params=params, headers=self._get_headers()
            )
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
            author_id: Semantic Scholar author ID.
            limit: Maximum number of results (max 1000).
            offset: Number of results to skip.

        Returns:
            List of papers by the author.
        """
        params: dict[str, Any] = {
            "fields": ",".join(self.PAPER_FIELDS),
            "limit": min(limit, 1000),
            "offset": offset,
        }

        response = await self._get(
            f"/author/{author_id}/papers", params=params, headers=self._get_headers()
        )
        data = response.json()

        papers = []
        for item in data.get("data", []):
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)

        return papers

    # =========================================================================
    # Batch Operations
    # =========================================================================

    async def get_papers_batch(self, paper_ids: list[str]) -> list[Paper]:
        """Get multiple papers by their IDs in a single request.

        Args:
            paper_ids: List of paper IDs (Semantic Scholar IDs, DOIs, arXiv IDs).
                      Max 500 IDs per request.

        Returns:
            List of Paper objects.
        """
        if not paper_ids:
            return []

        # Normalize DOIs
        normalized_ids = []
        for pid in paper_ids[:500]:  # Max 500
            normalized = normalize_doi(pid)
            if normalized and "/" in normalized:
                normalized_ids.append(f"DOI:{normalized}")
            else:
                normalized_ids.append(pid)

        params = {"fields": ",".join(self.PAPER_FIELDS)}
        response = await self._post(
            "/paper/batch",
            params=params,
            json={"ids": normalized_ids},
            headers=self._get_headers(),
        )
        data = response.json()

        papers = []
        for item in data if isinstance(data, list) else []:
            if item:  # Can be null for not found papers
                paper = self._parse_paper(item)
                if paper:
                    papers.append(paper)

        return papers

    async def get_authors_batch(self, author_ids: list[str]) -> list[Author]:
        """Get multiple authors by their IDs in a single request.

        Args:
            author_ids: List of Semantic Scholar author IDs. Max 1000 IDs.

        Returns:
            List of Author objects.
        """
        if not author_ids:
            return []

        params = {"fields": ",".join(self.AUTHOR_FIELDS)}
        response = await self._post(
            "/author/batch",
            params=params,
            json={"ids": author_ids[:1000]},
            headers=self._get_headers(),
        )
        data = response.json()

        authors = []
        for item in data if isinstance(data, list) else []:
            if item:
                author = self._parse_author(item)
                if author:
                    authors.append(author)

        return authors

    # =========================================================================
    # Recommendations
    # =========================================================================

    async def get_recommendations(
        self,
        paper_id: str,
        limit: int = 10,
        pool_from: str = "recent",
    ) -> list[Paper]:
        """Get paper recommendations based on a seed paper.

        Args:
            paper_id: Seed paper ID (Semantic Scholar ID or DOI).
            limit: Maximum number of recommendations (max 500).
            pool_from: Recommendation pool - "recent" or "all-cs".

        Returns:
            List of recommended papers.
        """
        normalized = normalize_doi(paper_id)
        if normalized and "/" in normalized:
            paper_id = f"DOI:{normalized}"

        # Recommendations use a different base URL
        rec_url = "https://api.semanticscholar.org/recommendations/v1"
        params: dict[str, Any] = {
            "fields": ",".join(self.PAPER_FIELDS),
            "limit": min(limit, 500),
            "from": pool_from,
        }

        # Need to make direct request since base_url is different
        import httpx

        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            response = await client.get(
                f"{rec_url}/papers/forpaper/{paper_id}",
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

        papers = []
        for item in data.get("recommendedPapers", []):
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)

        return papers

    async def get_recommendations_from_list(
        self,
        positive_paper_ids: list[str],
        negative_paper_ids: list[str] | None = None,
        limit: int = 10,
    ) -> list[Paper]:
        """Get paper recommendations based on a list of positive/negative examples.

        Args:
            positive_paper_ids: Papers similar to what you want (max 100).
            negative_paper_ids: Papers you want to avoid (max 100).
            limit: Maximum number of recommendations (max 500).

        Returns:
            List of recommended papers.
        """
        if not positive_paper_ids:
            return []

        # Normalize DOIs
        positive_ids = []
        for pid in positive_paper_ids[:100]:
            normalized = normalize_doi(pid)
            if normalized and "/" in normalized:
                positive_ids.append(f"DOI:{normalized}")
            else:
                positive_ids.append(pid)

        negative_ids = []
        if negative_paper_ids:
            for pid in negative_paper_ids[:100]:
                normalized = normalize_doi(pid)
                if normalized and "/" in normalized:
                    negative_ids.append(f"DOI:{normalized}")
                else:
                    negative_ids.append(pid)

        rec_url = "https://api.semanticscholar.org/recommendations/v1"
        params: dict[str, Any] = {
            "fields": ",".join(self.PAPER_FIELDS),
            "limit": min(limit, 500),
        }

        body: dict[str, Any] = {"positivePaperIds": positive_ids}
        if negative_ids:
            body["negativePaperIds"] = negative_ids

        import httpx

        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            response = await client.post(
                f"{rec_url}/papers/",
                params=params,
                json=body,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

        papers = []
        for item in data.get("recommendedPapers", []):
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)

        return papers

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_paper(self, data: dict[str, Any]) -> Paper | None:
        """Parse a Semantic Scholar paper object into a Paper.

        Args:
            data: Semantic Scholar paper JSON object.

        Returns:
            Paper object or None if parsing fails.
        """
        if not data:
            return None

        title = data.get("title", "")
        if not title:
            return None

        # Extract authors
        authors = [a.get("name", "") for a in data.get("authors", []) if a.get("name")]

        # Extract DOI from external IDs
        external_ids = data.get("externalIds", {}) or {}
        doi = normalize_doi(external_ids.get("DOI"))

        # Extract URLs
        url = data.get("url")
        pdf_url = None
        open_access_pdf = data.get("openAccessPdf")
        if open_access_pdf and isinstance(open_access_pdf, dict):
            pdf_url = open_access_pdf.get("url")

        # Extract keywords from fields of study
        fields = data.get("fieldsOfStudy") or []
        keywords = fields if isinstance(fields, list) else []

        return Paper(
            title=clean_html_text(title),
            authors=authors,
            abstract=clean_html_text(data.get("abstract", "")) or None,
            doi=doi,
            year=data.get("year"),
            journal=data.get("venue") or None,
            url=url,
            pdf_url=pdf_url,
            source=self.name,
            raw_data=data,
            citations_count=data.get("citationCount"),
            references_count=data.get("referenceCount"),
            open_access=data.get("isOpenAccess"),
            keywords=keywords,
        )

    def _parse_author(self, data: dict[str, Any]) -> Author | None:
        """Parse a Semantic Scholar author object into an Author.

        Args:
            data: Semantic Scholar author JSON object.

        Returns:
            Author object or None if parsing fails.
        """
        if not data:
            return None

        name = data.get("name", "")
        if not name:
            return None

        # Extract ORCID from external IDs
        external_ids = data.get("externalIds", {}) or {}
        orcid = external_ids.get("ORCID")

        # Extract affiliations
        affiliations = data.get("affiliations") or []

        return Author(
            name=name,
            source_id=data.get("authorId"),
            source=self.name,
            affiliations=affiliations,
            orcid=orcid,
            url=data.get("homepage"),
            paper_count=data.get("paperCount"),
            citation_count=data.get("citationCount"),
            h_index=data.get("hIndex"),
            raw_data=data,
        )
