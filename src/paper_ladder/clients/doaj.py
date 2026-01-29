"""DOAJ (Directory of Open Access Journals) API client for Paper-Ladder.

API Documentation: https://doaj.org/api/docs
- Articles API: https://doaj.org/api/v3/search/articles
- Journals API: https://doaj.org/api/v3/search/journals

DOAJ is a community-curated directory of open access journals with 20,000+ journals.
No API key required. All content is open access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from paper_ladder.clients.base import BaseClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
from paper_ladder.models import Paper, SortBy


class DOAJClient(BaseClient):
    """Client for the DOAJ API.

    DOAJ (Directory of Open Access Journals) provides free access to metadata
    for open access journals and articles. All indexed content is open access.

    API docs: https://doaj.org/api/docs
    """

    name = "doaj"
    base_url = "https://doaj.org/api"

    # =========================================================================
    # Articles (Papers)
    # =========================================================================

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        sort: SortBy | str | None = None,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for articles matching the query.

        Args:
            query: Search query string (Elasticsearch query syntax).
            limit: Maximum number of results (max 100 per page).
            offset: Number of results to skip (page * limit).
            sort: Sort order - SortBy enum or raw field name.
            **kwargs: Additional filters:
                - year: Publication year (int)
                - journal: Journal title (str)
                - subject: Subject classification (str)
                - language: Article language code (str)

        Returns:
            List of Paper objects.
        """
        # Build query with filters
        search_parts = [query]

        if "year" in kwargs:
            search_parts.append(f"bibjson.year:{kwargs['year']}")
        if "journal" in kwargs:
            search_parts.append(f'bibjson.journal.title:"{kwargs["journal"]}"')
        if "subject" in kwargs:
            search_parts.append(f'index.classification:"{kwargs["subject"]}"')
        if "language" in kwargs:
            search_parts.append(f"index.language:{kwargs['language']}")

        full_query = " AND ".join(f"({p})" for p in search_parts)

        params: dict[str, Any] = {
            "page": (offset // max(limit, 1)) + 1,
            "pageSize": min(limit, 100),
        }

        # Add sorting
        api_sort, _ = self._get_sort_param(sort)
        if api_sort:
            if sort == SortBy.CITATIONS:
                # DOAJ doesn't have citation counts, skip
                pass
            elif sort == SortBy.DATE:
                params["sort"] = "created_date:desc"
            elif sort == SortBy.DATE_ASC:
                params["sort"] = "created_date:asc"

        response = await self._get(f"/v3/search/articles/{full_query}", params=params)
        data = response.json()

        papers = []
        for item in data.get("results", []):
            paper = self._parse_article(item)
            if paper:
                papers.append(paper)

        return papers

    async def search_with_cursor(
        self,
        query: str,
        max_results: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[Paper]:
        """Search with pagination using page numbers.

        Args:
            query: Search query string.
            max_results: Maximum number of results to retrieve.
            **kwargs: Additional filters (same as search()).

        Yields:
            Paper objects.
        """
        offset = 0
        batch_size = 100  # DOAJ max page size
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
        """Get an article by DOI or DOAJ ID.

        Args:
            identifier: DOI or DOAJ article ID.

        Returns:
            Paper object if found, None otherwise.
        """
        # Normalize DOI
        if identifier.startswith("10.") or "doi.org" in identifier:
            doi = identifier.replace("https://doi.org/", "").replace("http://doi.org/", "")
            papers = await self.search(f"bibjson.identifier.id:{doi}", limit=1)
            return papers[0] if papers else None

        # Try DOAJ ID
        try:
            response = await self._get(f"/v3/articles/{identifier}")
            data = response.json()
            return self._parse_article(data)
        except Exception:
            pass

        # Try as search query
        papers = await self.search(identifier, limit=1)
        return papers[0] if papers else None

    # =========================================================================
    # Journals
    # =========================================================================

    async def search_journals(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs: object,
    ) -> list[dict[str, Any]]:
        """Search for journals.

        Args:
            query: Search query string.
            limit: Maximum number of results.
            offset: Number of results to skip.
            **kwargs: Additional filters:
                - subject: Subject classification (str)
                - language: Journal language code (str)
                - publisher: Publisher name (str)

        Returns:
            List of journal metadata dicts.
        """
        # Build query with filters
        search_parts = [query]

        if "subject" in kwargs:
            search_parts.append(f'index.classification:"{kwargs["subject"]}"')
        if "language" in kwargs:
            search_parts.append(f"index.language:{kwargs['language']}")
        if "publisher" in kwargs:
            search_parts.append(f'bibjson.publisher.name:"{kwargs["publisher"]}"')

        full_query = " AND ".join(f"({p})" for p in search_parts)

        params: dict[str, Any] = {
            "page": (offset // max(limit, 1)) + 1,
            "pageSize": min(limit, 100),
        }

        response = await self._get(f"/v3/search/journals/{full_query}", params=params)
        data = response.json()

        journals = []
        for item in data.get("results", []):
            journal = self._parse_journal(item)
            if journal:
                journals.append(journal)

        return journals

    async def get_journal(self, identifier: str) -> dict[str, Any] | None:
        """Get journal by ISSN or DOAJ ID.

        Args:
            identifier: ISSN or DOAJ journal ID.

        Returns:
            Journal metadata dict if found, None otherwise.
        """
        # Try DOAJ ID first
        try:
            response = await self._get(f"/v3/journals/{identifier}")
            data = response.json()
            return self._parse_journal(data)
        except Exception:
            pass

        # Search by ISSN
        papers = await self.search_journals(f"bibjson.eissn:{identifier} OR bibjson.pissn:{identifier}", limit=1)
        return papers[0] if papers else None

    async def get_journal_articles(
        self,
        journal_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get articles from a specific journal.

        Args:
            journal_id: DOAJ journal ID or ISSN.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of Paper objects.
        """
        return await self.search(
            f"bibjson.journal.title:* AND index.issn:{journal_id}",
            limit=limit,
            offset=offset,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_article(self, data: dict[str, Any]) -> Paper | None:
        """Parse a DOAJ article object into a Paper."""
        if not data:
            return None

        bibjson = data.get("bibjson", {})
        if not bibjson:
            return None

        # Extract title
        title = bibjson.get("title")
        if not title:
            return None

        # Extract authors
        authors = []
        for author in bibjson.get("author", []):
            name = author.get("name")
            if name:
                authors.append(name)

        # Extract abstract
        abstract = bibjson.get("abstract")

        # Extract DOI
        doi = None
        for identifier in bibjson.get("identifier", []):
            if identifier.get("type") == "doi":
                doi = identifier.get("id")
                break

        # Extract year
        year = None
        year_str = bibjson.get("year")
        if year_str:
            try:
                year = int(year_str)
            except ValueError:
                pass

        # Extract journal
        journal_info = bibjson.get("journal", {})
        journal = journal_info.get("title")

        # Extract URLs
        url = None
        pdf_url = None
        for link in bibjson.get("link", []):
            link_type = link.get("type", "").lower()
            link_url = link.get("url")
            if link_type == "fulltext" and link_url:
                if link_url.lower().endswith(".pdf"):
                    pdf_url = link_url
                else:
                    url = link_url

        # DOAJ ID as fallback URL
        doaj_id = data.get("id")
        if not url and doaj_id:
            url = f"https://doaj.org/article/{doaj_id}"

        # Extract keywords
        keywords = bibjson.get("keywords", [])

        # Extract subjects
        subjects = []
        for subject in bibjson.get("subject", []):
            term = subject.get("term")
            if term:
                subjects.append(term)

        all_keywords = keywords + subjects

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
            citations_count=None,  # DOAJ doesn't provide citation counts
            references_count=None,
            open_access=True,  # All DOAJ content is open access
            keywords=all_keywords[:10] if all_keywords else [],
        )

    def _parse_journal(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Parse a DOAJ journal object into a metadata dict."""
        if not data:
            return None

        bibjson = data.get("bibjson", {})
        if not bibjson:
            return None

        # Extract basic info
        title = bibjson.get("title")
        if not title:
            return None

        # Extract ISSNs
        eissn = bibjson.get("eissn")
        pissn = bibjson.get("pissn")

        # Extract publisher
        publisher = bibjson.get("publisher", {}).get("name")

        # Extract subjects
        subjects = []
        for subject in bibjson.get("subject", []):
            term = subject.get("term")
            if term:
                subjects.append(term)

        # Extract APC info
        apc = bibjson.get("apc", {})
        has_apc = apc.get("has_apc", False)

        # Extract license
        licenses = []
        for lic in bibjson.get("license", []):
            lic_type = lic.get("type")
            if lic_type:
                licenses.append(lic_type)

        return {
            "id": data.get("id"),
            "title": title,
            "eissn": eissn,
            "pissn": pissn,
            "publisher": publisher,
            "subjects": subjects,
            "has_apc": has_apc,
            "licenses": licenses,
            "url": bibjson.get("ref", {}).get("journal"),
            "source": self.name,
            "raw_data": data,
        }
