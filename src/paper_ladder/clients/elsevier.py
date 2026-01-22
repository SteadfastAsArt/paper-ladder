"""Elsevier API client for Paper-Ladder (Scopus/ScienceDirect).

API Documentation: https://dev.elsevier.com/documentation/
- Scopus Search: https://dev.elsevier.com/documentation/SCOPUSSearchAPI.wadl
- Scopus Abstract: https://dev.elsevier.com/documentation/AbstractRetrievalAPI.wadl
- Author Search: https://dev.elsevier.com/documentation/AuthorSearchAPI.wadl
- Author Retrieval: https://dev.elsevier.com/documentation/AuthorRetrievalAPI.wadl
- Affiliation Search: https://dev.elsevier.com/documentation/AffiliationSearchAPI.wadl
- Affiliation Retrieval: https://dev.elsevier.com/documentation/AffiliationRetrievalAPI.wadl
- Citation Overview: https://dev.elsevier.com/documentation/AbstractCitationAPI.wadl
"""

from __future__ import annotations

from typing import Any

from paper_ladder.clients.base import BaseClient
from paper_ladder.models import Author, Institution, Paper
from paper_ladder.utils import clean_html_text, normalize_doi


class ElsevierClient(BaseClient):
    """Client for the Elsevier APIs (Scopus and ScienceDirect).

    Requires an API key from https://dev.elsevier.com/
    Rate limits vary by subscription tier.

    API docs: https://dev.elsevier.com/documentation/
    """

    name = "elsevier"
    base_url = "https://api.elsevier.com"

    @property
    def api_key(self) -> str | None:
        """Get the Elsevier API key from config."""
        return self.config.elsevier_api_key

    def _get_headers(self) -> dict[str, str]:
        """Get headers with API key."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-ELS-APIKey"] = self.api_key
        return headers

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers in Scopus.

        Args:
            query: Search query string.
            limit: Maximum number of results (max 25 per page).
            offset: Number of results to skip.
            **kwargs: Additional parameters (year, subject_area, etc.).

        Returns:
            List of Paper objects.

        Raises:
            ValueError: If API key is not configured.
        """
        if not self.api_key:
            raise ValueError(
                "Elsevier API key required. Set 'elsevier_api_key' in config.yaml"
            )

        params: dict[str, Any] = {
            "query": query,
            "count": min(limit, 25),
            "start": offset,
        }

        # Add optional filters
        if "year" in kwargs:
            params["date"] = kwargs["year"]
        if "subject_area" in kwargs:
            params["subj"] = kwargs["subject_area"]

        response = await self._get(
            "/content/search/scopus",
            params=params,
            headers=self._get_headers(),
        )
        data = response.json()

        papers = []
        search_results = data.get("search-results", {})
        for entry in search_results.get("entry", []):
            paper = self._parse_scopus_entry(entry)
            if paper:
                papers.append(paper)

        return papers

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by DOI or Scopus ID.

        Args:
            identifier: DOI or Scopus ID.

        Returns:
            Paper object if found, None otherwise.

        Raises:
            ValueError: If API key is not configured.
        """
        if not self.api_key:
            raise ValueError(
                "Elsevier API key required. Set 'elsevier_api_key' in config.yaml"
            )

        # Determine identifier type
        normalized_doi = normalize_doi(identifier)
        if normalized_doi:
            endpoint = f"/content/abstract/doi/{normalized_doi}"
        else:
            endpoint = f"/content/abstract/scopus_id/{identifier}"

        try:
            response = await self._get(
                endpoint,
                headers=self._get_headers(),
            )
            data = response.json()

            # Parse the abstract retrieval response
            result = data.get("abstracts-retrieval-response", {})
            if result:
                return self._parse_abstract_response(result)
            return None
        except Exception:
            return None

    async def get_article_fulltext(self, doi: str) -> str | None:
        """Get full text of an article from ScienceDirect (if available).

        Args:
            doi: DOI of the article.

        Returns:
            Article full text or None if not available.

        Raises:
            ValueError: If API key is not configured.
        """
        if not self.api_key:
            raise ValueError(
                "Elsevier API key required. Set 'elsevier_api_key' in config.yaml"
            )

        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return None

        try:
            headers = self._get_headers()
            headers["Accept"] = "text/plain"

            response = await self._get(
                f"/content/article/doi/{normalized_doi}",
                headers=headers,
            )
            return response.text
        except Exception:
            return None

    async def get_paper_citations(
        self,
        scopus_id: str,
        limit: int = 25,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers that cite the given paper.

        Args:
            scopus_id: Scopus ID of the paper.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of citing papers.
        """
        if not self.api_key:
            raise ValueError(
                "Elsevier API key required. Set 'elsevier_api_key' in config.yaml"
            )

        params: dict[str, Any] = {
            "query": f"refeid({scopus_id})",
            "count": min(limit, 25),
            "start": offset,
        }

        response = await self._get(
            "/content/search/scopus",
            params=params,
            headers=self._get_headers(),
        )
        data = response.json()

        papers = []
        search_results = data.get("search-results", {})
        for entry in search_results.get("entry", []):
            paper = self._parse_scopus_entry(entry)
            if paper:
                papers.append(paper)

        return papers

    # =========================================================================
    # Authors
    # =========================================================================

    async def search_authors(
        self,
        query: str,
        limit: int = 25,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Author]:
        """Search for authors in Scopus.

        Args:
            query: Search query (e.g., author name, ORCID).
            limit: Maximum number of results (max 25).
            offset: Number of results to skip.
            **kwargs: Additional filters:
                - affiliation: Filter by affiliation name
                - subject_area: Filter by subject area

        Returns:
            List of Author objects.
        """
        if not self.api_key:
            raise ValueError(
                "Elsevier API key required. Set 'elsevier_api_key' in config.yaml"
            )

        # Build Scopus author search query
        search_query = f"AUTHLAST({query})"
        if kwargs.get("affiliation"):
            search_query += f" AND AFFIL({kwargs['affiliation']})"
        if kwargs.get("subject_area"):
            search_query += f" AND SUBJAREA({kwargs['subject_area']})"

        params: dict[str, Any] = {
            "query": search_query,
            "count": min(limit, 25),
            "start": offset,
        }

        response = await self._get(
            "/content/search/author",
            params=params,
            headers=self._get_headers(),
        )
        data = response.json()

        authors = []
        search_results = data.get("search-results", {})
        for entry in search_results.get("entry", []):
            author = self._parse_author_entry(entry)
            if author:
                authors.append(author)

        return authors

    async def get_author(self, author_id: str) -> Author | None:
        """Get an author by Scopus author ID.

        Args:
            author_id: Scopus author ID.

        Returns:
            Author object if found, None otherwise.
        """
        if not self.api_key:
            raise ValueError(
                "Elsevier API key required. Set 'elsevier_api_key' in config.yaml"
            )

        try:
            response = await self._get(
                f"/content/author/author_id/{author_id}",
                headers=self._get_headers(),
            )
            data = response.json()
            result = data.get("author-retrieval-response", [])
            if result and len(result) > 0:
                return self._parse_author_detail(result[0])
            return None
        except Exception:
            return None

    async def get_author_papers(
        self,
        author_id: str,
        limit: int = 25,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers by an author.

        Args:
            author_id: Scopus author ID.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of papers by the author.
        """
        if not self.api_key:
            raise ValueError(
                "Elsevier API key required. Set 'elsevier_api_key' in config.yaml"
            )

        params: dict[str, Any] = {
            "query": f"AU-ID({author_id})",
            "count": min(limit, 25),
            "start": offset,
            "sort": "-citedby-count",
        }

        response = await self._get(
            "/content/search/scopus",
            params=params,
            headers=self._get_headers(),
        )
        data = response.json()

        papers = []
        search_results = data.get("search-results", {})
        for entry in search_results.get("entry", []):
            paper = self._parse_scopus_entry(entry)
            if paper:
                papers.append(paper)

        return papers

    # =========================================================================
    # Affiliations (Institutions)
    # =========================================================================

    async def search_institutions(
        self,
        query: str,
        limit: int = 25,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Institution]:
        """Search for institutions/affiliations in Scopus.

        Args:
            query: Search query (affiliation name).
            limit: Maximum number of results (max 25).
            offset: Number of results to skip.
            **kwargs: Additional filters:
                - country: Filter by country

        Returns:
            List of Institution objects.
        """
        if not self.api_key:
            raise ValueError(
                "Elsevier API key required. Set 'elsevier_api_key' in config.yaml"
            )

        search_query = f"AFFIL({query})"
        if kwargs.get("country"):
            search_query += f" AND AFFILCOUNTRY({kwargs['country']})"

        params: dict[str, Any] = {
            "query": search_query,
            "count": min(limit, 25),
            "start": offset,
        }

        response = await self._get(
            "/content/search/affiliation",
            params=params,
            headers=self._get_headers(),
        )
        data = response.json()

        institutions = []
        search_results = data.get("search-results", {})
        for entry in search_results.get("entry", []):
            inst = self._parse_affiliation_entry(entry)
            if inst:
                institutions.append(inst)

        return institutions

    async def get_institution(self, affiliation_id: str) -> Institution | None:
        """Get an institution by Scopus affiliation ID.

        Args:
            affiliation_id: Scopus affiliation ID.

        Returns:
            Institution object if found, None otherwise.
        """
        if not self.api_key:
            raise ValueError(
                "Elsevier API key required. Set 'elsevier_api_key' in config.yaml"
            )

        try:
            response = await self._get(
                f"/content/affiliation/affiliation_id/{affiliation_id}",
                headers=self._get_headers(),
            )
            data = response.json()
            result = data.get("affiliation-retrieval-response", {})
            if result:
                return self._parse_affiliation_detail(result)
            return None
        except Exception:
            return None

    # =========================================================================
    # Helper Methods - Papers
    # =========================================================================

    def _parse_scopus_entry(self, data: dict[str, Any]) -> Paper | None:
        """Parse a Scopus search result entry into a Paper.

        Args:
            data: Scopus entry JSON object.

        Returns:
            Paper object or None if parsing fails.
        """
        if not data:
            return None

        title = data.get("dc:title", "")
        if not title:
            return None

        # Extract authors (Scopus returns as comma-separated string)
        authors_str = data.get("dc:creator", "")
        authors = [a.strip() for a in authors_str.split(",") if a.strip()]

        # Extract DOI
        doi = normalize_doi(data.get("prism:doi"))

        # Extract year from cover date
        cover_date = data.get("prism:coverDate", "")
        year = None
        if cover_date and len(cover_date) >= 4:
            try:
                year = int(cover_date[:4])
            except ValueError:
                pass

        # Extract URLs
        url = None
        pdf_url = None
        for link in data.get("link", []):
            if link.get("@ref") == "scopus":
                url = link.get("@href")
            elif link.get("@ref") == "full-text":
                pdf_url = link.get("@href")

        return Paper(
            title=clean_html_text(title),
            authors=authors,
            abstract=clean_html_text(data.get("dc:description", "")) or None,
            doi=doi,
            year=year,
            journal=data.get("prism:publicationName"),
            url=url,
            pdf_url=pdf_url,
            source=self.name,
            raw_data=data,
            citations_count=int(data.get("citedby-count", 0)) or None,
            open_access=data.get("openaccess") == "1",
        )

    def _parse_abstract_response(self, data: dict[str, Any]) -> Paper | None:
        """Parse a Scopus abstract retrieval response into a Paper.

        Args:
            data: Scopus abstract response JSON object.

        Returns:
            Paper object or None if parsing fails.
        """
        if not data:
            return None

        coredata = data.get("coredata", {})
        title = coredata.get("dc:title", "")
        if not title:
            return None

        # Extract authors
        authors = []
        author_data = data.get("authors", {}).get("author", [])
        if isinstance(author_data, list):
            for author in author_data:
                name = author.get("ce:indexed-name")
                if not name:
                    name = author.get("preferred-name", {}).get("ce:indexed-name")
                if name:
                    authors.append(name)
        elif isinstance(author_data, dict):
            name = author_data.get("ce:indexed-name")
            if name:
                authors.append(name)

        # Extract DOI
        doi = normalize_doi(coredata.get("prism:doi"))

        # Extract year
        cover_date = coredata.get("prism:coverDate", "")
        year = None
        if cover_date and len(cover_date) >= 4:
            try:
                year = int(cover_date[:4])
            except ValueError:
                pass

        return Paper(
            title=clean_html_text(title),
            authors=authors,
            abstract=clean_html_text(coredata.get("dc:description", "")) or None,
            doi=doi,
            year=year,
            journal=coredata.get("prism:publicationName"),
            url=coredata.get("link", [{}])[0].get("@href") if coredata.get("link") else None,
            pdf_url=None,
            source=self.name,
            raw_data=data,
            citations_count=int(coredata.get("citedby-count", 0)) or None,
        )

    # =========================================================================
    # Helper Methods - Authors
    # =========================================================================

    def _parse_author_entry(self, data: dict[str, Any]) -> Author | None:
        """Parse a Scopus author search entry into an Author.

        Args:
            data: Scopus author entry JSON object.

        Returns:
            Author object or None if parsing fails.
        """
        if not data:
            return None

        # Get preferred name
        preferred_name = data.get("preferred-name", {})
        name = preferred_name.get("surname", "")
        given_name = preferred_name.get("given-name", "")
        if given_name:
            name = f"{given_name} {name}"

        if not name:
            return None

        # Extract affiliations
        affiliations = []
        affil = data.get("affiliation-current", {})
        if isinstance(affil, dict):
            affil_name = affil.get("affiliation-name")
            if affil_name:
                affiliations.append(affil_name)
        elif isinstance(affil, list):
            for a in affil:
                affil_name = a.get("affiliation-name")
                if affil_name:
                    affiliations.append(affil_name)

        # Extract ORCID
        orcid = data.get("orcid")

        # Extract URL
        url = None
        for link in data.get("link", []):
            if link.get("@ref") == "self":
                url = link.get("@href")
                break

        return Author(
            name=name.strip(),
            source_id=data.get("dc:identifier", "").replace("AUTHOR_ID:", ""),
            source=self.name,
            affiliations=affiliations,
            orcid=orcid,
            url=url,
            paper_count=int(data.get("document-count", 0)) or None,
            citation_count=None,  # Not available in search results
            h_index=None,  # Not available in search results
            raw_data=data,
        )

    def _parse_author_detail(self, data: dict[str, Any]) -> Author | None:
        """Parse a Scopus author retrieval response into an Author.

        Args:
            data: Scopus author detail JSON object.

        Returns:
            Author object or None if parsing fails.
        """
        if not data:
            return None

        # Get name from coredata
        coredata = data.get("coredata", {})
        preferred_name = data.get("author-profile", {}).get("preferred-name", {})

        name = preferred_name.get("indexed-name", "")
        if not name:
            name = coredata.get("dc:identifier", "")

        if not name:
            return None

        # Extract affiliations
        affiliations = []
        affil_history = (
            data.get("author-profile", {})
            .get("affiliation-history", {})
            .get("affiliation", [])
        )
        if isinstance(affil_history, dict):
            affil_history = [affil_history]
        for affil in affil_history[:3]:  # Take first 3
            ip_doc = affil.get("ip-doc", {})
            affil_name = ip_doc.get("afdispname")
            if affil_name:
                affiliations.append(affil_name)

        # h-index not directly available in author retrieval response
        h_index = None

        return Author(
            name=name.strip(),
            source_id=coredata.get("dc:identifier", "").replace("AUTHOR_ID:", ""),
            source=self.name,
            affiliations=affiliations,
            orcid=coredata.get("orcid"),
            url=coredata.get("link", [{}])[0].get("@href")
            if coredata.get("link")
            else None,
            paper_count=int(coredata.get("document-count", 0)) or None,
            citation_count=int(coredata.get("cited-by-count", 0)) or None,
            h_index=h_index,
            raw_data=data,
        )

    # =========================================================================
    # Helper Methods - Affiliations
    # =========================================================================

    def _parse_affiliation_entry(self, data: dict[str, Any]) -> Institution | None:
        """Parse a Scopus affiliation search entry into an Institution.

        Args:
            data: Scopus affiliation entry JSON object.

        Returns:
            Institution object or None if parsing fails.
        """
        if not data:
            return None

        name = data.get("affiliation-name", "")
        if not name:
            return None

        # Extract URL
        url = None
        for link in data.get("link", []):
            if link.get("@ref") == "self":
                url = link.get("@href")
                break

        return Institution(
            name=name,
            source_id=data.get("dc:identifier", "").replace("AFFILIATION_ID:", ""),
            source=self.name,
            country=data.get("country"),
            type=None,  # Not directly available in search
            url=url,
            paper_count=int(data.get("document-count", 0)) or None,
            citation_count=None,
            raw_data=data,
        )

    def _parse_affiliation_detail(self, data: dict[str, Any]) -> Institution | None:
        """Parse a Scopus affiliation retrieval response into an Institution.

        Args:
            data: Scopus affiliation detail JSON object.

        Returns:
            Institution object or None if parsing fails.
        """
        if not data:
            return None

        coredata = data.get("coredata", {})
        name = data.get("affiliation-name", "")
        if not name:
            name = coredata.get("dc:identifier", "")

        if not name:
            return None

        # Determine institution type from name patterns
        inst_type = None
        name_lower = name.lower()
        if "university" in name_lower or "college" in name_lower:
            inst_type = "education"
        elif "hospital" in name_lower or "medical" in name_lower:
            inst_type = "healthcare"
        elif "institute" in name_lower or "laboratory" in name_lower:
            inst_type = "research"

        return Institution(
            name=name,
            source_id=coredata.get("dc:identifier", "").replace("AFFILIATION_ID:", ""),
            source=self.name,
            country=data.get("country"),
            type=inst_type,
            url=data.get("org-URL"),
            paper_count=int(coredata.get("document-count", 0)) or None,
            citation_count=None,
            raw_data=data,
        )
