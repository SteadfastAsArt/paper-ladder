"""Free Google Scholar scraper for Paper-Ladder.

This client scrapes Google Scholar directly without requiring SerpAPI.
Use responsibly and respect Google's rate limits to avoid IP blocking.

WARNING: Web scraping may violate Google's Terms of Service.
This is provided for educational and research purposes only.
Consider using the official SerpAPI client for production use.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from paper_ladder.clients.base import BaseClient, sort_papers
from paper_ladder.models import Author, Paper, SortBy
from paper_ladder.utils import clean_html_text, normalize_doi

logger = logging.getLogger(__name__)

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


class GoogleScholarScraperClient(BaseClient):
    """Free Google Scholar scraper client.

    This client scrapes Google Scholar directly without requiring SerpAPI.
    It uses rotating user agents and respects rate limits to avoid blocking.

    WARNING: Web scraping may violate Google's Terms of Service.
    Use responsibly for educational and research purposes only.

    Rate limiting: Default 1 request per 5 seconds to avoid blocking.
    Consider using a proxy for better reliability.
    """

    name = "google_scholar_scraper"
    base_url = "https://scholar.google.com"

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the scraper client."""
        super().__init__(*args, **kwargs)
        self._user_agent_index = 0
        self._request_delay = 5.0  # Seconds between requests
        self._last_request_time = 0.0

    def _get_user_agent(self) -> str:
        """Get a rotating user agent."""
        ua = USER_AGENTS[self._user_agent_index % len(USER_AGENTS)]
        self._user_agent_index += 1
        return ua

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with rotating user agent."""
        return {
            "User-Agent": self._get_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _rate_limited_request(self, url: str, params: dict | None = None) -> httpx.Response:
        """Make a rate-limited request with retry logic.

        Args:
            url: URL to request.
            params: Optional query parameters.

        Returns:
            HTTP response.

        Raises:
            httpx.HTTPStatusError: If request fails.
        """
        # Rate limiting
        import time

        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._request_delay:
            await asyncio.sleep(self._request_delay - elapsed + random.uniform(0.5, 1.5))

        self._last_request_time = time.monotonic()

        # Make request
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(url, params=params, headers=self._get_headers())
            response.raise_for_status()
            return response

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
            limit: Maximum number of results (max 10 per page due to scraping).
            offset: Number of results to skip.
            sort: Sort order. Note: Google Scholar doesn't support sorting
                  in search, so non-relevance sorts are applied client-side.
            **kwargs: Additional parameters:
                - year_low: Start year filter
                - year_high: End year filter
                - year: Single year filter

        Returns:
            List of Paper objects.
        """
        papers: list[Paper] = []
        start = offset

        while len(papers) < limit:
            # Build URL
            params: dict[str, Any] = {
                "q": query,
                "start": start,
                "hl": "en",
            }

            # Add year filters
            if "year_low" in kwargs:
                params["as_ylo"] = kwargs["year_low"]
            if "year_high" in kwargs:
                params["as_yhi"] = kwargs["year_high"]
            if "year" in kwargs:
                params["as_ylo"] = kwargs["year"]
                params["as_yhi"] = kwargs["year"]

            try:
                response = await self._rate_limited_request(
                    f"{self.base_url}/scholar", params=params
                )
                html = response.text

                # Check for CAPTCHA
                if "gs_captcha" in html or "unusual traffic" in html.lower():
                    logger.warning("Google Scholar CAPTCHA detected. Consider using SerpAPI.")
                    break

                # Parse results
                batch = self._parse_search_results(html)
                if not batch:
                    break

                papers.extend(batch)
                start += 10  # Google Scholar shows 10 results per page

                # If we got fewer results, no more available
                if len(batch) < 10:
                    break

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error searching Google Scholar: {e.response.status_code}")
                break
            except Exception as e:
                logger.error(f"Error searching Google Scholar: {e}")
                break

        # Trim to requested limit
        papers = papers[:limit]

        # Apply client-side sorting
        if sort and sort != SortBy.RELEVANCE:
            sort_enum = sort if isinstance(sort, SortBy) else SortBy(sort)
            papers = sort_papers(papers, sort_enum)

        return papers

    async def get_paper(self, identifier: str) -> Paper | None:
        """Get a paper by DOI or title (via search).

        Args:
            identifier: DOI or title to search for.

        Returns:
            Paper object if found, None otherwise.
        """
        papers = await self.search(f'"{identifier}"', limit=1)
        return papers[0] if papers else None

    async def search_author(
        self,
        author_name: str,
        limit: int = 10,
        offset: int = 0,
        **kwargs: object,
    ) -> list[Paper]:
        """Search for papers by a specific author.

        Args:
            author_name: Author name to search for.
            limit: Maximum number of results.
            offset: Number of results to skip.
            **kwargs: Additional filters.

        Returns:
            List of papers by the author.
        """
        return await self.search(f'author:"{author_name}"', limit=limit, offset=offset, **kwargs)

    async def get_author_profile(self, author_id: str) -> Author | None:
        """Get an author profile by Google Scholar author ID.

        Args:
            author_id: Google Scholar author ID.

        Returns:
            Author object if found, None otherwise.
        """
        url = f"{self.base_url}/citations"
        params = {"user": author_id, "hl": "en"}

        try:
            response = await self._rate_limited_request(url, params=params)
            html = response.text

            # Check for CAPTCHA
            if "gs_captcha" in html or "unusual traffic" in html.lower():
                logger.warning("Google Scholar CAPTCHA detected.")
                return None

            return self._parse_author_profile(html, author_id)

        except Exception as e:
            logger.error(f"Error fetching author profile: {e}")
            return None

    # =========================================================================
    # Parsing Methods
    # =========================================================================

    def _parse_search_results(self, html: str) -> list[Paper]:
        """Parse Google Scholar search results HTML.

        Args:
            html: HTML content of search results page.

        Returns:
            List of Paper objects.
        """
        papers: list[Paper] = []
        soup = BeautifulSoup(html, "lxml")

        # Find all search result divs
        results = soup.find_all("div", class_="gs_r gs_or gs_scl")

        for result in results:
            paper = self._parse_result_div(result)
            if paper:
                papers.append(paper)

        return papers

    def _parse_result_div(self, div: Any) -> Paper | None:
        """Parse a single search result div.

        Args:
            div: BeautifulSoup div element.

        Returns:
            Paper object or None.
        """
        # Extract title
        title_elem = div.find("h3", class_="gs_rt")
        if not title_elem:
            return None

        title_link = title_elem.find("a")
        title = clean_html_text(title_link.get_text()) if title_link else clean_html_text(
            title_elem.get_text()
        )
        url = title_link.get("href") if title_link else None

        if not title:
            return None

        # Extract authors and publication info
        authors: list[str] = []
        year = None
        journal = None

        info_elem = div.find("div", class_="gs_a")
        if info_elem:
            info_text = info_elem.get_text()
            # Format: "Author1, Author2 - Journal, Year - Publisher"
            parts = info_text.split(" - ")
            if parts:
                # Parse authors
                author_part = parts[0]
                # Remove ellipsis and clean
                author_part = author_part.replace("…", "").strip()
                authors = [a.strip() for a in author_part.split(",") if a.strip()]

                # Parse journal and year
                if len(parts) >= 2:
                    journal_part = parts[1]
                    # Extract year
                    year_match = re.search(r"\b(19|20)\d{2}\b", journal_part)
                    if year_match:
                        year = int(year_match.group())
                        journal = journal_part.replace(year_match.group(), "").strip(" ,")

        # Extract abstract/snippet
        abstract = None
        snippet_elem = div.find("div", class_="gs_rs")
        if snippet_elem:
            abstract = clean_html_text(snippet_elem.get_text())

        # Extract citation count
        citations_count = None
        cited_by_elem = div.find("a", string=re.compile(r"Cited by \d+"))
        if cited_by_elem:
            cited_text = cited_by_elem.get_text()
            cited_match = re.search(r"Cited by (\d+)", cited_text)
            if cited_match:
                citations_count = int(cited_match.group(1))

        # Extract PDF link
        pdf_url = None
        pdf_elem = div.find("div", class_="gs_or_ggsm")
        if pdf_elem:
            pdf_link = pdf_elem.find("a")
            if pdf_link:
                pdf_url = pdf_link.get("href")

        # Try to extract DOI from URL
        doi = None
        if url and "doi.org/" in url:
            doi = normalize_doi(url)

        # Extract Google Scholar result ID for citations
        result_id = None
        data_cid = div.get("data-cid")
        if data_cid:
            result_id = data_cid

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
            source_id=result_id,
            citations_count=citations_count,
            raw_data={"html": str(div)},
        )

    def _parse_author_profile(self, html: str, author_id: str) -> Author | None:
        """Parse author profile page.

        Args:
            html: HTML content of author profile page.
            author_id: Google Scholar author ID.

        Returns:
            Author object or None.
        """
        soup = BeautifulSoup(html, "lxml")

        # Extract name
        name_elem = soup.find("div", id="gsc_prf_in")
        if not name_elem:
            return None
        name = clean_html_text(name_elem.get_text())

        # Extract affiliation
        affiliations: list[str] = []
        affil_elem = soup.find("div", class_="gsc_prf_il")
        if affil_elem:
            affil_text = clean_html_text(affil_elem.get_text())
            if affil_text:
                affiliations.append(affil_text)

        # Extract citation metrics
        citation_count = None
        h_index = None

        stats_table = soup.find("table", id="gsc_rsb_st")
        if stats_table:
            rows = stats_table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    label = cells[0].get_text().lower()
                    if "citations" in label:
                        with contextlib.suppress(ValueError):
                            citation_count = int(cells[1].get_text().replace(",", ""))
                    elif "h-index" in label:
                        with contextlib.suppress(ValueError):
                            h_index = int(cells[1].get_text())

        # Get profile URL
        profile_url = f"https://scholar.google.com/citations?user={author_id}"

        return Author(
            name=name,
            source_id=author_id,
            source=self.name,
            affiliations=affiliations,
            url=profile_url,
            citation_count=citation_count,
            h_index=h_index,
            raw_data={"author_id": author_id},
        )
