"""DBLP API client for Paper-Ladder.

API Documentation: https://dblp.org/faq/How+to+use+the+dblp+search+API.html
- Search API: https://dblp.org/search/publ/api
- Author API: https://dblp.org/search/author/api
- Publication info: https://dblp.org/rec/{key}.xml

DBLP is a free computer science bibliography with 6M+ publications.
No API key required. Rate limit: 1 request per second recommended.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from paper_ladder.clients.base import BaseClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
from paper_ladder.models import Author, Paper, SortBy


class DBLPClient(BaseClient):
    """Client for the DBLP computer science bibliography.

    DBLP provides free access to bibliographic metadata for computer science
    publications including journals, conferences, and preprints.

    API docs: https://dblp.org/faq/How+to+use+the+dblp+search+API.html
    """

    name = "dblp"
    base_url = "https://dblp.org"

    # =========================================================================
    # Publications (Papers)
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
            limit: Maximum number of results (max 1000 per page).
            offset: Number of results to skip (first result is 0).
            sort: Sort order (DBLP doesn't support sorting, client-side only).
            **kwargs: Additional filters:
                - year: Publication year (int)
                - venue: Conference/journal venue (str)
                - type: Publication type (article, inproceedings, book, etc.)

        Returns:
            List of Paper objects.
        """
        params: dict[str, Any] = {
            "q": query,
            "format": "json",
            "h": min(limit, 1000),
            "f": offset,
        }

        # Add filters to query
        filters = []
        if "year" in kwargs:
            filters.append(f"year:{kwargs['year']}")
        if "venue" in kwargs:
            filters.append(f"venue:{kwargs['venue']}")
        if "type" in kwargs:
            filters.append(f"type:{kwargs['type']}")

        if filters:
            params["q"] = f"{query} {' '.join(filters)}"

        response = await self._get("/search/publ/api", params=params)
        data = response.json()

        papers = []
        result = data.get("result", {})
        hits = result.get("hits", {})

        for hit in hits.get("hit", []):
            info = hit.get("info", {})
            paper = self._parse_publication(info)
            if paper:
                papers.append(paper)

        # Apply client-side sorting if needed
        _, needs_client_sort = self._get_sort_param(sort)
        if needs_client_sort and sort:
            papers = self._apply_client_sort(papers, sort)

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
        batch_size = 1000
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
        """Get a paper by DBLP key or DOI.

        Args:
            identifier: DBLP key (e.g., "journals/nature/LeCunBH15") or DOI.

        Returns:
            Paper object if found, None otherwise.
        """
        # Check if it's a DOI
        if identifier.startswith("10.") or "doi.org" in identifier:
            # Search by DOI
            papers = await self.search(f"doi:{identifier}", limit=1)
            return papers[0] if papers else None

        # Try DBLP key
        try:
            response = await self._get(f"/rec/{identifier}.xml", params={"format": "json"})
            data = response.json()
            result = data.get("result", {})
            hits = result.get("hits", {})
            hit_list = hits.get("hit", [])

            if hit_list:
                info = hit_list[0].get("info", {})
                return self._parse_publication(info)
        except Exception:
            pass

        # Try as a search query
        papers = await self.search(identifier, limit=1)
        return papers[0] if papers else None

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
            query: Author name or partial name.
            limit: Maximum number of results.
            offset: Number of results to skip.
            **kwargs: Additional parameters (unused).

        Returns:
            List of Author objects.
        """
        params: dict[str, Any] = {
            "q": query,
            "format": "json",
            "h": min(limit, 1000),
            "f": offset,
        }

        response = await self._get("/search/author/api", params=params)
        data = response.json()

        authors = []
        result = data.get("result", {})
        hits = result.get("hits", {})

        for hit in hits.get("hit", []):
            info = hit.get("info", {})
            author = self._parse_author(info)
            if author:
                authors.append(author)

        return authors

    async def get_author_papers(
        self,
        pid: str,
        limit: int = 100,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Paper]:
        """Get papers by an author using their DBLP PID.

        Args:
            pid: DBLP person identifier (e.g., "h/GeoffreyEHinton").
            limit: Maximum number of results.
            offset: Number of results to skip.
            **kwargs: Additional parameters (unused).

        Returns:
            List of Paper objects.
        """
        # DBLP uses a person-based URL for listing publications
        try:
            response = await self._get(f"/pid/{pid}.xml", params={"format": "json"})
            data = response.json()

            papers = []
            result = data.get("result", {})
            hits = result.get("hits", {})

            for hit in hits.get("hit", []):
                info = hit.get("info", {})
                paper = self._parse_publication(info)
                if paper:
                    papers.append(paper)

            # Apply pagination
            return papers[offset : offset + limit]

        except Exception:
            # Fallback: search by author name
            author_parts = pid.split("/")
            if author_parts:
                author_name = author_parts[-1].replace("-", " ")
                return await self.search(f"author:{author_name}", limit=limit, offset=offset)
            return []

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_publication(self, data: dict[str, Any]) -> Paper | None:
        """Parse a DBLP publication info dict into a Paper."""
        if not data:
            return None

        # Extract title
        title = data.get("title")
        if not title:
            return None

        # Clean title (remove trailing period if present)
        if title.endswith("."):
            title = title[:-1]

        # Extract authors
        authors = []
        author_data = data.get("authors", {})
        if isinstance(author_data, dict):
            author_list = author_data.get("author", [])
            if isinstance(author_list, list):
                for author in author_list:
                    if isinstance(author, dict):
                        authors.append(author.get("text", ""))
                    elif isinstance(author, str):
                        authors.append(author)
            elif isinstance(author_list, dict):
                authors.append(author_list.get("text", ""))
            elif isinstance(author_list, str):
                authors.append(author_list)

        # Extract year
        year = None
        year_str = data.get("year")
        if year_str:
            try:
                year = int(year_str)
            except ValueError:
                pass

        # Extract DOI
        doi = data.get("doi")
        if doi:
            # Clean DOI format
            doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")

        # Extract venue (journal/conference)
        venue = data.get("venue")

        # Extract URL
        url = data.get("url") or data.get("ee")

        # Determine PDF URL
        pdf_url = None
        ee = data.get("ee")
        if ee:
            if isinstance(ee, list):
                for link in ee:
                    if isinstance(link, str) and link.lower().endswith(".pdf"):
                        pdf_url = link
                        break
                if not pdf_url:
                    url = ee[0] if ee else None
            elif isinstance(ee, str):
                if ee.lower().endswith(".pdf"):
                    pdf_url = ee
                else:
                    url = ee

        # Extract publication type
        pub_type = data.get("type")

        # Extract DBLP key
        dblp_key = data.get("key")

        return Paper(
            title=title,
            authors=authors,
            abstract=None,  # DBLP doesn't provide abstracts
            doi=doi,
            year=year,
            journal=venue,
            url=url,
            pdf_url=pdf_url,
            source=self.name,
            raw_data=data,
            citations_count=None,  # DBLP doesn't provide citation counts
            references_count=None,
            open_access=None,
            keywords=[pub_type] if pub_type else [],
        )

    def _parse_author(self, data: dict[str, Any]) -> Author | None:
        """Parse a DBLP author info dict into an Author."""
        if not data:
            return None

        # Extract name
        name = data.get("author")
        if not name:
            return None

        # Extract PID (person identifier)
        pid = data.get("url", "").replace("https://dblp.org/pid/", "")

        # Extract affiliations
        affiliations = []
        notes = data.get("notes", {})
        if isinstance(notes, dict):
            note_list = notes.get("note", [])
            if isinstance(note_list, list):
                for note in note_list:
                    if isinstance(note, dict) and note.get("@type") == "affiliation":
                        affiliations.append(note.get("text", ""))
            elif isinstance(note_list, dict) and note_list.get("@type") == "affiliation":
                affiliations.append(note_list.get("text", ""))

        return Author(
            name=name,
            source_id=pid,
            source=self.name,
            affiliations=affiliations,
            orcid=None,
            url=data.get("url"),
            paper_count=None,
            citation_count=None,
            h_index=None,
            raw_data=data,
        )
