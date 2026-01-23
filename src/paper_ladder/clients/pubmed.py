"""PubMed API client for Paper-Ladder.

API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25497/
- E-utilities Overview: https://www.ncbi.nlm.nih.gov/books/NBK25500/
- ESearch: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ESearch
- EFetch: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.EFetch
- ESummary: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ESummary
- ELink: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ELink
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from paper_ladder.clients.base import BaseClient
from paper_ladder.models import Author, Paper
from paper_ladder.utils import clean_html_text, extract_year_from_date, normalize_doi


class PubMedClient(BaseClient):
    """Client for the PubMed E-utilities API.

    PubMed is a free database of biomedical literature from MEDLINE,
    life science journals, and online books.

    Rate limit: 3 requests/second without API key, 10 requests/second with key.

    API docs: https://www.ncbi.nlm.nih.gov/books/NBK25497/
    """

    name = "pubmed"
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    @property
    def api_key(self) -> str | None:
        """Get the PubMed/NCBI API key from config."""
        return self.config.pubmed_api_key

    def _get_base_params(self) -> dict[str, Any]:
        """Get base parameters for all requests."""
        params: dict[str, Any] = {
            "db": "pubmed",
            "retmode": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key
        return params

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
            query: Search query string (supports PubMed query syntax).
            limit: Maximum number of results (max 10000 per request).
            offset: Number of results to skip.
            **kwargs: Additional filters:
                - year: Publication year (int)
                - from_year: Start year for date range
                - until_year: End year for date range
                - author: Author name to filter by
                - journal: Journal name to filter by
                - mesh: MeSH term to filter by
                - article_type: Article type (e.g., "review", "clinical trial")
                - sort: Sort order ("relevance", "pub_date", "author")

        Returns:
            List of Paper objects.
        """
        # Build the search query with filters
        search_query = self._build_query(query, kwargs)

        # Step 1: ESearch to get PMIDs
        search_params = self._get_base_params()
        search_params.update(
            {
                "term": search_query,
                "retmax": min(limit, 10000),
                "retstart": offset,
                "usehistory": "n",
            }
        )

        # Handle sorting
        sort = kwargs.get("sort")
        if sort == "pub_date":
            search_params["sort"] = "pub_date"
        elif sort == "author":
            search_params["sort"] = "author"
        # Default is relevance

        response = await self._get("/esearch.fcgi", params=search_params)
        search_data = response.json()

        esearch_result = search_data.get("esearchresult", {})
        pmids = esearch_result.get("idlist", [])

        if not pmids:
            return []

        # Step 2: EFetch to get full records
        return await self._fetch_papers(pmids)

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by PMID or DOI.

        Args:
            identifier: PMID (e.g., "12345678") or DOI.

        Returns:
            Paper object if found, None otherwise.
        """
        # Check if it's a DOI (DOIs start with "10.")
        normalized_doi = normalize_doi(identifier)
        if normalized_doi and normalized_doi.startswith("10."):
            # Search by DOI
            search_params = self._get_base_params()
            search_params["term"] = f"{normalized_doi}[doi]"
            search_params["retmax"] = 1

            try:
                response = await self._get("/esearch.fcgi", params=search_params)
                search_data = response.json()
                pmids = search_data.get("esearchresult", {}).get("idlist", [])
                if not pmids:
                    return None
                identifier = pmids[0]
            except Exception:
                return None

        # Fetch by PMID
        try:
            papers = await self._fetch_papers([identifier])
            return papers[0] if papers else None
        except Exception:
            return None

    async def get_paper_references(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers referenced by the given paper.

        Note: PubMed only has reference data for some PMC articles.

        Args:
            paper_id: PMID.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of referenced papers.
        """
        # Use ELink to get references
        link_params = self._get_base_params()
        link_params.update(
            {
                "id": paper_id,
                "linkname": "pubmed_pubmed_refs",
                "retmode": "json",
            }
        )

        try:
            response = await self._get("/elink.fcgi", params=link_params)
            link_data = response.json()

            # Extract linked PMIDs
            pmids = []
            linksets = link_data.get("linksets", [])
            for linkset in linksets:
                linksetdbs = linkset.get("linksetdbs", [])
                for linksetdb in linksetdbs:
                    if linksetdb.get("linkname") == "pubmed_pubmed_refs":
                        links = linksetdb.get("links", [])
                        pmids.extend(str(link) for link in links)

            if not pmids:
                return []

            # Apply pagination
            pmids = pmids[offset : offset + limit]
            return await self._fetch_papers(pmids)
        except Exception:
            return []

    async def get_paper_citations(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Get papers that cite the given paper.

        Note: PubMed citation data comes from PMC and may be incomplete.

        Args:
            paper_id: PMID.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of citing papers.
        """
        # Use ELink to get citing papers (citedin)
        link_params = self._get_base_params()
        link_params.update(
            {
                "id": paper_id,
                "linkname": "pubmed_pubmed_citedin",
                "retmode": "json",
            }
        )

        try:
            response = await self._get("/elink.fcgi", params=link_params)
            link_data = response.json()

            # Extract linked PMIDs
            pmids = []
            linksets = link_data.get("linksets", [])
            for linkset in linksets:
                linksetdbs = linkset.get("linksetdbs", [])
                for linksetdb in linksetdbs:
                    if linksetdb.get("linkname") == "pubmed_pubmed_citedin":
                        links = linksetdb.get("links", [])
                        pmids.extend(str(link) for link in links)

            if not pmids:
                return []

            # Apply pagination
            pmids = pmids[offset : offset + limit]
            return await self._fetch_papers(pmids)
        except Exception:
            return []

    async def get_related_papers(
        self,
        paper_id: str,
        limit: int = 20,
    ) -> list[Paper]:
        """Get papers related to the given paper.

        Uses PubMed's related articles algorithm.

        Args:
            paper_id: PMID.
            limit: Maximum number of results.

        Returns:
            List of related papers.
        """
        link_params = self._get_base_params()
        link_params.update(
            {
                "id": paper_id,
                "linkname": "pubmed_pubmed",
                "retmode": "json",
            }
        )

        try:
            response = await self._get("/elink.fcgi", params=link_params)
            link_data = response.json()

            pmids = []
            linksets = link_data.get("linksets", [])
            for linkset in linksets:
                linksetdbs = linkset.get("linksetdbs", [])
                for linksetdb in linksetdbs:
                    if linksetdb.get("linkname") == "pubmed_pubmed":
                        links = linksetdb.get("links", [])
                        pmids.extend(str(link) for link in links[:limit])

            if not pmids:
                return []

            return await self._fetch_papers(pmids)
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

        Note: PubMed doesn't have a dedicated author database.
        This searches for papers by the author and extracts author info.

        Args:
            query: Author name to search for.
            limit: Maximum number of authors to return.
            offset: Number of results to skip.
            **kwargs: Additional filters:
                - affiliation: Filter by affiliation

        Returns:
            List of Author objects.
        """
        # Build author search query
        search_query = f"{query}[Author]"
        if kwargs.get("affiliation"):
            search_query += f" AND {kwargs['affiliation']}[Affiliation]"

        search_params = self._get_base_params()
        search_params.update(
            {
                "term": search_query,
                "retmax": min(limit * 5, 100),  # Get more papers to find authors
                "retstart": offset,
            }
        )

        try:
            response = await self._get("/esearch.fcgi", params=search_params)
            search_data = response.json()
            pmids = search_data.get("esearchresult", {}).get("idlist", [])

            if not pmids:
                return []

            # Fetch papers and extract unique authors
            papers = await self._fetch_papers(pmids)
            authors_dict: dict[str, Author] = {}

            for paper in papers:
                for author_info in paper.raw_data.get("authors_full", []):
                    name = author_info.get("name", "")
                    if name and name.lower().find(query.lower()) >= 0:
                        if name not in authors_dict:
                            authors_dict[name] = Author(
                                name=name,
                                source_id=None,
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
        return await self.search(f"{author_name}[Author]", limit=limit, offset=offset)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_query(self, query: str, kwargs: dict[str, Any]) -> str:
        """Build PubMed query with filters."""
        parts = [query]

        # Year filters
        if "year" in kwargs:
            parts.append(f"{kwargs['year']}[pdat]")
        elif "from_year" in kwargs or "until_year" in kwargs:
            from_year = kwargs.get("from_year", "1900")
            until_year = kwargs.get("until_year", "3000")
            parts.append(f"{from_year}:{until_year}[pdat]")

        # Author filter
        if "author" in kwargs:
            parts.append(f"{kwargs['author']}[Author]")

        # Journal filter
        if "journal" in kwargs:
            parts.append(f"{kwargs['journal']}[Journal]")

        # MeSH term filter
        if "mesh" in kwargs:
            parts.append(f"{kwargs['mesh']}[MeSH Terms]")

        # Article type filter
        if "article_type" in kwargs:
            parts.append(f"{kwargs['article_type']}[Publication Type]")

        return " AND ".join(parts)

    async def _fetch_papers(self, pmids: list[str]) -> list[Paper]:
        """Fetch full paper records by PMIDs.

        Args:
            pmids: List of PubMed IDs.

        Returns:
            List of Paper objects.
        """
        if not pmids:
            return []

        # Use EFetch to get full XML records
        fetch_params: dict[str, Any] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "xml",
            "retmode": "xml",
        }
        if self.api_key:
            fetch_params["api_key"] = self.api_key

        response = await self._get("/efetch.fcgi", params=fetch_params)
        xml_content = response.text

        return self._parse_pubmed_xml(xml_content)

    def _parse_pubmed_xml(self, xml_content: str) -> list[Paper]:
        """Parse PubMed XML response into Paper objects."""
        papers = []

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return []

        for article in root.findall(".//PubmedArticle"):
            paper = self._parse_article(article)
            if paper:
                papers.append(paper)

        return papers

    def _parse_article(self, article: ET.Element) -> Paper | None:
        """Parse a single PubmedArticle XML element."""
        medline = article.find("MedlineCitation")
        if medline is None:
            return None

        article_elem = medline.find("Article")
        if article_elem is None:
            return None

        # Title
        title_elem = article_elem.find("ArticleTitle")
        title = self._get_text(title_elem)
        if not title:
            return None

        # PMID
        pmid_elem = medline.find("PMID")
        pmid = self._get_text(pmid_elem)

        # Authors
        authors = []
        authors_full = []
        author_list = article_elem.find("AuthorList")
        if author_list is not None:
            for author_elem in author_list.findall("Author"):
                author_info = self._parse_author_elem(author_elem)
                if author_info:
                    authors.append(author_info["name"])
                    authors_full.append(author_info)

        # Abstract
        abstract = None
        abstract_elem = article_elem.find("Abstract")
        if abstract_elem is not None:
            abstract_parts = []
            for text_elem in abstract_elem.findall("AbstractText"):
                label = text_elem.get("Label", "")
                text = self._get_text(text_elem)
                if text:
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
            abstract = " ".join(abstract_parts)

        # DOI
        doi = None
        pubmed_data = article.find("PubmedData")
        if pubmed_data is not None:
            article_ids = pubmed_data.find("ArticleIdList")
            if article_ids is not None:
                for id_elem in article_ids.findall("ArticleId"):
                    if id_elem.get("IdType") == "doi":
                        doi = normalize_doi(self._get_text(id_elem))
                        break

        # Year
        year = None
        pub_date = article_elem.find(".//PubDate")
        if pub_date is not None:
            year_elem = pub_date.find("Year")
            if year_elem is not None:
                year = int(self._get_text(year_elem) or "0") or None
            else:
                # Try MedlineDate
                medline_date = pub_date.find("MedlineDate")
                if medline_date is not None:
                    year = extract_year_from_date(self._get_text(medline_date))

        # Journal
        journal = None
        journal_elem = article_elem.find("Journal")
        if journal_elem is not None:
            journal_title = journal_elem.find("Title")
            if journal_title is not None:
                journal = self._get_text(journal_title)
            else:
                iso_abbrev = journal_elem.find("ISOAbbreviation")
                if iso_abbrev is not None:
                    journal = self._get_text(iso_abbrev)

        # Keywords (MeSH terms)
        keywords = []
        mesh_list = medline.find("MeshHeadingList")
        if mesh_list is not None:
            for mesh in mesh_list.findall("MeshHeading"):
                descriptor = mesh.find("DescriptorName")
                if descriptor is not None:
                    keywords.append(self._get_text(descriptor))

        # URL
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None

        # PDF URL (PMC if available)
        pdf_url = None
        pmc_id = None
        if pubmed_data is not None:
            article_ids = pubmed_data.find("ArticleIdList")
            if article_ids is not None:
                for id_elem in article_ids.findall("ArticleId"):
                    if id_elem.get("IdType") == "pmc":
                        pmc_id = self._get_text(id_elem)
                        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/"
                        break

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
            raw_data={
                "pmid": pmid,
                "pmc_id": pmc_id,
                "authors_full": authors_full,
                "mesh_terms": keywords,
            },
            open_access=pmc_id is not None,
            keywords=keywords[:10],
        )

    def _parse_author_elem(self, author_elem: ET.Element) -> dict[str, Any] | None:
        """Parse an Author XML element."""
        # Handle collective name
        collective = author_elem.find("CollectiveName")
        if collective is not None:
            return {"name": self._get_text(collective)}

        last_name = author_elem.find("LastName")
        fore_name = author_elem.find("ForeName")
        initials = author_elem.find("Initials")

        if last_name is None:
            return None

        # Build name
        name_parts = []
        if fore_name is not None:
            name_parts.append(self._get_text(fore_name))
        elif initials is not None:
            name_parts.append(self._get_text(initials))
        name_parts.append(self._get_text(last_name))

        name = " ".join(filter(None, name_parts))
        if not name:
            return None

        # Affiliations
        affiliations = []
        for aff in author_elem.findall("AffiliationInfo/Affiliation"):
            aff_text = self._get_text(aff)
            if aff_text:
                affiliations.append(aff_text)

        # ORCID
        orcid = None
        for identifier in author_elem.findall("Identifier"):
            if identifier.get("Source") == "ORCID":
                orcid = self._get_text(identifier)
                if orcid:
                    orcid = orcid.replace("https://orcid.org/", "")

        return {
            "name": name,
            "affiliations": affiliations,
            "orcid": orcid,
        }

    def _get_text(self, elem: ET.Element | None) -> str:
        """Get text content from an XML element."""
        if elem is None:
            return ""
        # Handle mixed content (text with child elements)
        text_parts = []
        if elem.text:
            text_parts.append(elem.text)
        for child in elem:
            if child.text:
                text_parts.append(child.text)
            if child.tail:
                text_parts.append(child.tail)
        return "".join(text_parts).strip()
