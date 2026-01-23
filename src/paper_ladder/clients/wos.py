"""Web of Science API client for Paper-Ladder.

API Documentation: https://developer.clarivate.com/apis/wos
- API Expanded: https://developer.clarivate.com/apis/wos
- API Starter: https://developer.clarivate.com/apis/wos-starter
- Swagger UI: https://api.clarivate.com/swagger-ui/

Note: This client uses the WoS Expanded API which requires institutional subscription.
For free access (limited features), use the Starter API endpoints.
"""

from __future__ import annotations

from typing import Any

from paper_ladder.clients.base import BaseClient
from paper_ladder.models import Author, Paper
from paper_ladder.utils import clean_html_text, normalize_doi


class WebOfScienceClient(BaseClient):
    """Client for the Web of Science API.

    Web of Science is a comprehensive citation index covering science,
    social science, arts, and humanities.

    Rate limit: 2 requests/second, 200 requests/day (may vary by subscription).

    API docs: https://developer.clarivate.com/apis/wos
    """

    name = "wos"
    base_url = "https://api.clarivate.com/api/wos"

    @property
    def api_key(self) -> str | None:
        """Get the Web of Science API key from config."""
        return self.config.wos_api_key

    def _get_headers(self) -> dict[str, str]:
        """Get headers with API key."""
        headers = {
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-ApiKey"] = self.api_key
        return headers

    # =========================================================================
    # Papers (Works)
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
            query: Search query string (supports WoS advanced search syntax).
            limit: Maximum number of results (max 100 per request).
            offset: Number of results to skip (max 100000).
            **kwargs: Additional filters:
                - year: Publication year (int)
                - from_year: Start year for date range
                - until_year: End year for date range
                - database: Database to search (WOS, BCI, CCC, DRCI, etc.)
                - edition: Collection edition (SCI, SSCI, AHCI, ISTP, etc.)
                - doc_type: Document type (Article, Review, etc.)
                - sort: Sort order ("relevance", "date", "cited")

        Returns:
            List of Paper objects.
        """
        if not self.api_key:
            raise ValueError("Web of Science API key is required")

        # Build the search query with filters
        search_query = self._build_query(query, kwargs)

        params: dict[str, Any] = {
            "databaseId": kwargs.get("database", "WOS"),
            "usrQuery": search_query,
            "count": min(limit, 100),
            "firstRecord": offset + 1,  # WoS uses 1-based indexing
        }

        # Handle edition filter
        if "edition" in kwargs:
            params["edition"] = kwargs["edition"]

        # Handle sorting
        sort = kwargs.get("sort")
        if sort == "date":
            params["sortField"] = "PY+D"  # Publication year descending
        elif sort == "cited":
            params["sortField"] = "TC+D"  # Times cited descending
        else:
            params["sortField"] = "RS+D"  # Relevance descending

        try:
            response = await self._get(
                "/query",
                params=params,
                headers=self._get_headers(),
            )
            data = response.json()

            papers = []
            records = data.get("Data", {}).get("Records", {}).get("records", {})
            if records and "REC" in records:
                for record in records["REC"]:
                    paper = self._parse_record(record)
                    if paper:
                        papers.append(paper)

            return papers
        except Exception:
            return []

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by DOI or WoS UID.

        Args:
            identifier: DOI (with or without prefix) or WoS UID (WOS:...).

        Returns:
            Paper object if found, None otherwise.
        """
        if not self.api_key:
            raise ValueError("Web of Science API key is required")

        # Check if it's a DOI or WoS UID
        normalized_doi = normalize_doi(identifier)
        if normalized_doi:
            # Search by DOI
            query = f"DO={normalized_doi}"
        elif identifier.startswith("WOS:"):
            # Search by WoS UID
            query = f"UT={identifier}"
        else:
            # Assume it's a WoS UID without prefix
            query = f"UT=WOS:{identifier}"

        try:
            papers = await self.search(query, limit=1)
            return papers[0] if papers else None
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
            paper_id: WoS UID (WOS:...) or DOI.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of citing papers.
        """
        if not self.api_key:
            raise ValueError("Web of Science API key is required")

        # First get the paper to get its WoS UID
        paper = await self.get_paper(paper_id)
        if not paper or not paper.raw_data.get("uid"):
            return []

        uid = paper.raw_data["uid"]

        try:
            params: dict[str, Any] = {
                "databaseId": "WOS",
                "uniqueId": uid,
                "count": min(limit, 100),
                "firstRecord": offset + 1,
            }

            response = await self._get(
                "/citing",
                params=params,
                headers=self._get_headers(),
            )
            data = response.json()

            papers = []
            records = data.get("Data", {}).get("Records", {}).get("records", {})
            if records and "REC" in records:
                for record in records["REC"]:
                    citing_paper = self._parse_record(record)
                    if citing_paper:
                        papers.append(citing_paper)

            return papers
        except Exception:
            return []

    async def get_paper_references(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers referenced by the given paper.

        Args:
            paper_id: WoS UID (WOS:...) or DOI.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of referenced papers.
        """
        if not self.api_key:
            raise ValueError("Web of Science API key is required")

        # First get the paper to get its WoS UID
        paper = await self.get_paper(paper_id)
        if not paper or not paper.raw_data.get("uid"):
            return []

        uid = paper.raw_data["uid"]

        try:
            params: dict[str, Any] = {
                "databaseId": "WOS",
                "uniqueId": uid,
                "count": min(limit, 100),
                "firstRecord": offset + 1,
            }

            response = await self._get(
                "/references",
                params=params,
                headers=self._get_headers(),
            )
            data = response.json()

            papers = []
            # References endpoint returns a different structure
            references = data.get("Data", [])
            for ref in references[offset : offset + limit]:
                paper = self._parse_reference(ref)
                if paper:
                    papers.append(paper)

            return papers
        except Exception:
            return []

    async def get_related_papers(
        self,
        paper_id: str,
        limit: int = 20,
    ) -> list[Paper]:
        """Get papers related to the given paper.

        Uses WoS related records feature.

        Args:
            paper_id: WoS UID (WOS:...) or DOI.
            limit: Maximum number of results.

        Returns:
            List of related papers.
        """
        if not self.api_key:
            raise ValueError("Web of Science API key is required")

        paper = await self.get_paper(paper_id)
        if not paper or not paper.raw_data.get("uid"):
            return []

        uid = paper.raw_data["uid"]

        try:
            params: dict[str, Any] = {
                "databaseId": "WOS",
                "uniqueId": uid,
                "count": min(limit, 100),
                "firstRecord": 1,
            }

            response = await self._get(
                "/related",
                params=params,
                headers=self._get_headers(),
            )
            data = response.json()

            papers = []
            records = data.get("Data", {}).get("Records", {}).get("records", {})
            if records and "REC" in records:
                for record in records["REC"]:
                    related_paper = self._parse_record(record)
                    if related_paper:
                        papers.append(related_paper)

            return papers
        except Exception:
            return []

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

        Note: WoS doesn't have a dedicated author search in the standard API.
        This searches for papers by the author and extracts author info.

        Args:
            query: Author name to search for.
            limit: Maximum number of authors to return.
            offset: Number of results to skip.
            **kwargs: Additional filters:
                - organization: Filter by organization/affiliation

        Returns:
            List of Author objects.
        """
        # Build author search query
        search_query = f"AU={query}"
        if kwargs.get("organization"):
            search_query += f" AND OG={kwargs['organization']}"

        try:
            papers = await self.search(search_query, limit=limit * 3, offset=offset)

            # Extract unique authors
            authors_dict: dict[str, Author] = {}
            for paper in papers:
                for author_info in paper.raw_data.get("authors_full", []):
                    name = author_info.get("name", "")
                    if name and name.lower().find(query.lower()) >= 0:
                        if name not in authors_dict:
                            authors_dict[name] = Author(
                                name=name,
                                source_id=author_info.get("dais_id"),
                                source=self.name,
                                affiliations=author_info.get("affiliations", []),
                                orcid=author_info.get("orcid"),
                                raw_data=author_info,
                            )

            return list(authors_dict.values())[:limit]
        except Exception:
            return []

    async def get_author_papers(
        self,
        author_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers by an author.

        Args:
            author_name: Author name to search for.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of papers by the author.
        """
        return await self.search(f"AU={author_name}", limit=limit, offset=offset)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_query(self, query: str, kwargs: dict[str, Any]) -> str:
        """Build WoS advanced search query with filters."""
        # If query doesn't contain field tags, treat as topic search
        if "=" not in query:
            query = f"TS={query}"

        parts = [query]

        # Year filters
        if "year" in kwargs:
            parts.append(f"PY={kwargs['year']}")
        elif "from_year" in kwargs or "until_year" in kwargs:
            from_year = kwargs.get("from_year", "1900")
            until_year = kwargs.get("until_year", "2100")
            parts.append(f"PY={from_year}-{until_year}")

        # Document type filter
        if "doc_type" in kwargs:
            parts.append(f"DT={kwargs['doc_type']}")

        return " AND ".join(parts)

    def _parse_record(self, record: dict[str, Any]) -> Paper | None:
        """Parse a WoS record into a Paper object."""
        if not record:
            return None

        # Get UID
        uid = record.get("UID", "")

        # Get static data
        static_data = record.get("static_data", {})
        summary = static_data.get("summary", {})
        fullrecord = static_data.get("fullrecord_metadata", {})

        # Title
        titles = summary.get("titles", {}).get("title", [])
        title = ""
        for t in titles:
            if t.get("type") == "item":
                title = t.get("content", "")
                break
        if not title:
            return None

        # Authors
        authors = []
        authors_full = []
        names = summary.get("names", {}).get("name", [])
        for name_entry in names:
            if name_entry.get("role") == "author":
                full_name = name_entry.get("full_name", "")
                if full_name:
                    authors.append(full_name)
                    author_info = {
                        "name": full_name,
                        "dais_id": name_entry.get("dais_id"),
                        "orcid": name_entry.get("orcid_id"),
                        "affiliations": [],
                    }
                    # Get affiliations
                    addr_no = name_entry.get("addr_no")
                    if addr_no:
                        addresses = fullrecord.get("addresses", {}).get("address_name", [])
                        for addr in addresses:
                            addr_spec = addr.get("address_spec", {})
                            if str(addr_spec.get("addr_no")) == str(addr_no):
                                org = addr_spec.get("full_address", "")
                                if org:
                                    author_info["affiliations"].append(org)
                    authors_full.append(author_info)

        # Abstract
        abstract = None
        abstracts = fullrecord.get("abstracts", {}).get("abstract", {})
        if abstracts:
            abstract_text = abstracts.get("abstract_text", {})
            if isinstance(abstract_text, dict):
                abstract = abstract_text.get("p", "")
            elif isinstance(abstract_text, list):
                parts = [p.get("p", "") if isinstance(p, dict) else str(p) for p in abstract_text]
                abstract = " ".join(parts)
            elif isinstance(abstract_text, str):
                abstract = abstract_text

        # DOI
        doi = None
        dynamic_data = static_data.get("dynamic_data", {})
        cluster_related = dynamic_data.get("cluster_related", {})
        identifiers = cluster_related.get("identifiers", {}).get("identifier", [])
        if not identifiers:
            identifiers = summary.get("other_id", [])
        for id_entry in identifiers:
            if isinstance(id_entry, dict) and id_entry.get("type") == "doi":
                doi = normalize_doi(id_entry.get("value"))
                break

        # Year
        year = None
        pub_info = summary.get("pub_info", {})
        year_str = pub_info.get("pubyear")
        if year_str:
            try:
                year = int(year_str)
            except ValueError:
                pass

        # Journal
        journal = None
        publishers = summary.get("publishers", {}).get("publisher", {})
        if publishers:
            names_data = publishers.get("names", {}).get("name", {})
            if isinstance(names_data, dict):
                journal = names_data.get("full_name")
            elif isinstance(names_data, list) and names_data:
                journal = names_data[0].get("full_name")

        # Citation count
        citations_count = None
        rec_dynamic = record.get("dynamic_data", {})
        citation_related = rec_dynamic.get("citation_related", {})
        tc_list = citation_related.get("tc_list", {})
        citation_data = tc_list.get("silo_tc", {})
        if citation_data:
            if isinstance(citation_data, dict):
                citations_count = citation_data.get("local_count")
            elif isinstance(citation_data, list) and citation_data:
                citations_count = citation_data[0].get("local_count")
        if citations_count is not None:
            try:
                citations_count = int(citations_count)
            except (ValueError, TypeError):
                citations_count = None

        # Keywords
        keywords = []
        kw_data = fullrecord.get("keywords", {}).get("keyword", [])
        for kw in kw_data:
            if isinstance(kw, str):
                keywords.append(kw)
            elif isinstance(kw, dict):
                keywords.append(kw.get("content", ""))

        # URL
        url = f"https://www.webofscience.com/wos/woscc/full-record/{uid}" if uid else None

        # Open access
        fullrecord_meta = static_data.get("fullrecord_metadata", {})
        fund_ack = fullrecord_meta.get("fund_ack", {})
        oa_data = fund_ack.get("fund_text", {})
        open_access = bool(oa_data)

        return Paper(
            title=clean_html_text(title),
            authors=authors,
            abstract=clean_html_text(abstract) if abstract else None,
            doi=doi,
            year=year,
            journal=journal,
            url=url,
            pdf_url=None,  # WoS doesn't provide direct PDF links
            source=self.name,
            raw_data={
                "uid": uid,
                "authors_full": authors_full,
            },
            citations_count=citations_count,
            open_access=open_access,
            keywords=keywords[:10],
        )

    def _parse_reference(self, ref: dict[str, Any]) -> Paper | None:
        """Parse a WoS reference into a Paper object."""
        if not ref:
            return None

        # References have limited data
        title = ref.get("citedTitle", "")
        if not title:
            return None

        authors = []
        cited_author = ref.get("citedAuthor", "")
        if cited_author:
            authors = [a.strip() for a in cited_author.split(";")]

        year = None
        year_str = ref.get("year")
        if year_str:
            try:
                year = int(year_str)
            except ValueError:
                pass

        doi = normalize_doi(ref.get("doi"))
        journal = ref.get("citedWork", "")

        return Paper(
            title=clean_html_text(title),
            authors=authors,
            doi=doi,
            year=year,
            journal=journal,
            source=self.name,
            raw_data=ref,
        )
