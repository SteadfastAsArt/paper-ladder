"""PDF download functionality for Paper-Ladder."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from paper_ladder.models import Paper

logger = logging.getLogger(__name__)

# User agent rotation for web requests
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class PDFDownloader:
    """Download PDFs from various academic sources.

    Supports downloading from:
    - Direct PDF URLs
    - arXiv (arxiv.org)
    - bioRxiv (biorxiv.org)
    - medRxiv (medrxiv.org)
    - PubMed Central (ncbi.nlm.nih.gov/pmc)
    - Unpaywall (api.unpaywall.org) - finds open access versions
    - DOI resolution (doi.org)
    """

    def __init__(
        self,
        output_dir: str | Path = ".",
        timeout: float = 60.0,
        proxy: str | None = None,
        unpaywall_email: str | None = None,
    ):
        """Initialize the downloader.

        Args:
            output_dir: Directory to save downloaded PDFs.
            timeout: Request timeout in seconds.
            proxy: Optional proxy URL.
            unpaywall_email: Email for Unpaywall API (required for Unpaywall lookups).
                            Register at https://unpaywall.org/products/api
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.proxy = proxy
        self.unpaywall_email = unpaywall_email
        self._user_agent_index = 0

    def _get_user_agent(self) -> str:
        """Get a rotating user agent."""
        ua = USER_AGENTS[self._user_agent_index % len(USER_AGENTS)]
        self._user_agent_index += 1
        return ua

    def _get_client(self) -> httpx.AsyncClient:
        """Create an HTTP client with appropriate settings."""
        kwargs: dict = {
            "timeout": self.timeout,
            "headers": {"User-Agent": self._get_user_agent()},
            "follow_redirects": True,
        }
        if self.proxy:
            kwargs["proxy"] = self.proxy
        return httpx.AsyncClient(**kwargs)

    async def download(
        self,
        url: str,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path | None:
        """Download a PDF from a URL.

        Args:
            url: URL to download from.
            filename: Optional filename (without extension). If None, auto-generated.
            overwrite: Whether to overwrite existing files.

        Returns:
            Path to downloaded file, or None if download failed.
        """
        # Resolve URL to direct PDF link
        pdf_url = await self._resolve_pdf_url(url)
        if not pdf_url:
            logger.error(f"Could not resolve PDF URL from: {url}")
            return None

        # Generate filename if not provided
        if not filename:
            filename = self._generate_filename(url, pdf_url)

        output_path = self.output_dir / f"{filename}.pdf"

        # Check if file already exists
        if output_path.exists() and not overwrite:
            logger.info(f"File already exists: {output_path}")
            return output_path

        # Download the PDF
        try:
            async with self._get_client() as client:
                response = await client.get(pdf_url)
                response.raise_for_status()

                # Verify it's a PDF
                content_type = response.headers.get("content-type", "")
                if "pdf" not in content_type.lower() and response.content[:4] != b"%PDF":
                    logger.error(f"Response is not a PDF (content-type: {content_type})")
                    return None

                # Save the file
                output_path.write_bytes(response.content)
                logger.info(f"Downloaded: {output_path}")
                return output_path

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading {pdf_url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error downloading {pdf_url}: {e}")
            return None

    async def download_paper(
        self,
        paper: Paper,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path | None:
        """Download a PDF for a Paper object.

        Tries sources in order:
        1. Direct pdf_url from paper
        2. DOI lookup (includes Unpaywall if configured)
        3. Regular URL

        Args:
            paper: Paper object with pdf_url, doi, or url.
            filename: Optional filename. If None, uses sanitized title.
            overwrite: Whether to overwrite existing files.

        Returns:
            Path to downloaded file, or None if download failed.
        """
        # Try pdf_url first
        if paper.pdf_url:
            result = await self.download(paper.pdf_url, filename, overwrite)
            if result:
                return result

        # Try DOI (includes Unpaywall lookup if email configured)
        if paper.doi:
            result = await self.download_from_doi(paper.doi, filename, overwrite)
            if result:
                return result

        # Try regular URL
        if paper.url:
            result = await self.download(paper.url, filename, overwrite)
            if result:
                return result

        logger.error(f"Could not download PDF for: {paper.title}")
        return None

    async def download_from_doi(
        self,
        doi: str,
        filename: str | None = None,
        overwrite: bool = False,
        try_unpaywall: bool = True,
    ) -> Path | None:
        """Download a PDF by DOI.

        Args:
            doi: DOI string.
            filename: Optional filename.
            overwrite: Whether to overwrite existing files.
            try_unpaywall: Whether to try Unpaywall for open access versions.

        Returns:
            Path to downloaded file, or None if download failed.
        """
        # Normalize DOI
        doi = doi.strip()
        for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
            if doi.lower().startswith(prefix.lower()):
                doi = doi[len(prefix) :]
                break

        # Check for arXiv DOI
        if "arxiv" in doi.lower():
            arxiv_id = self._extract_arxiv_id(doi)
            if arxiv_id:
                return await self.download_from_arxiv(arxiv_id, filename, overwrite)

        # Check for bioRxiv/medRxiv DOI
        if "10.1101" in doi:
            result = await self.download_from_biorxiv_medrxiv(doi, filename, overwrite)
            if result:
                return result

        # Try Unpaywall for open access version
        if try_unpaywall and self.unpaywall_email:
            result = await self.download_from_unpaywall(doi, filename, overwrite)
            if result:
                return result

        # Try to resolve via DOI
        url = f"https://doi.org/{doi}"
        return await self.download(url, filename, overwrite)

    async def download_from_unpaywall(
        self,
        doi: str,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path | None:
        """Download a PDF using Unpaywall to find open access versions.

        Unpaywall is a free service that finds legal open access versions of papers.
        API docs: https://unpaywall.org/products/api

        Args:
            doi: DOI string (without URL prefix).
            filename: Optional filename.
            overwrite: Whether to overwrite existing files.

        Returns:
            Path to downloaded file, or None if no OA version found.
        """
        if not self.unpaywall_email:
            logger.debug("Unpaywall email not configured, skipping Unpaywall lookup")
            return None

        # Normalize DOI
        doi = doi.strip()
        for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
            if doi.lower().startswith(prefix.lower()):
                doi = doi[len(prefix) :]
                break

        api_url = f"https://api.unpaywall.org/v2/{doi}"
        params = {"email": self.unpaywall_email}

        try:
            async with self._get_client() as client:
                response = await client.get(api_url, params=params)

                if response.status_code == 404:
                    logger.debug(f"DOI not found in Unpaywall: {doi}")
                    return None

                response.raise_for_status()
                data = response.json()

                # Check if open access
                if not data.get("is_oa"):
                    logger.debug(f"No open access version found for: {doi}")
                    return None

                # Try best OA location first
                best_location = data.get("best_oa_location", {})
                pdf_url = best_location.get("url_for_pdf")

                if not pdf_url:
                    # Try other OA locations
                    for location in data.get("oa_locations", []):
                        pdf_url = location.get("url_for_pdf")
                        if pdf_url:
                            break

                if not pdf_url:
                    # Fall back to landing page URL
                    pdf_url = best_location.get("url")
                    if pdf_url:
                        logger.info(f"No direct PDF URL, trying landing page: {pdf_url}")

                if pdf_url:
                    logger.info(f"Found OA version via Unpaywall: {pdf_url}")
                    return await self.download(pdf_url, filename, overwrite)

                logger.debug(f"No PDF URL in Unpaywall response for: {doi}")
                return None

        except httpx.HTTPStatusError as e:
            logger.debug(f"Unpaywall API error for {doi}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.debug(f"Error querying Unpaywall for {doi}: {e}")
            return None

    async def download_from_arxiv(
        self,
        arxiv_id: str,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path | None:
        """Download a PDF from arXiv.

        Args:
            arxiv_id: arXiv ID (e.g., "2301.07041").
            filename: Optional filename.
            overwrite: Whether to overwrite existing files.

        Returns:
            Path to downloaded file, or None if download failed.
        """
        # Normalize arXiv ID
        arxiv_id = self._extract_arxiv_id(arxiv_id) or arxiv_id
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        return await self.download(pdf_url, filename or f"arxiv_{arxiv_id}", overwrite)

    async def download_from_biorxiv_medrxiv(
        self,
        doi: str,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path | None:
        """Download a PDF from bioRxiv or medRxiv.

        Args:
            doi: DOI (e.g., "10.1101/2024.01.01.123456").
            filename: Optional filename.
            overwrite: Whether to overwrite existing files.

        Returns:
            Path to downloaded file, or None if download failed.
        """
        # Try bioRxiv first
        pdf_url = f"https://www.biorxiv.org/content/{doi}.full.pdf"
        result = await self.download(pdf_url, filename, overwrite)
        if result:
            return result

        # Try medRxiv
        pdf_url = f"https://www.medrxiv.org/content/{doi}.full.pdf"
        return await self.download(pdf_url, filename, overwrite)

    async def download_from_pmc(
        self,
        pmc_id: str,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path | None:
        """Download a PDF from PubMed Central.

        Args:
            pmc_id: PMC ID (e.g., "PMC1234567" or "1234567").
            filename: Optional filename.
            overwrite: Whether to overwrite existing files.

        Returns:
            Path to downloaded file, or None if download failed.
        """
        # Normalize PMC ID
        if not pmc_id.upper().startswith("PMC"):
            pmc_id = f"PMC{pmc_id}"

        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/"
        return await self.download(pdf_url, filename or pmc_id.lower(), overwrite)

    async def _resolve_pdf_url(self, url: str) -> str | None:
        """Resolve a URL to a direct PDF link.

        Args:
            url: URL to resolve.

        Returns:
            Direct PDF URL or None if not resolvable.
        """
        # Already a PDF URL
        if url.lower().endswith(".pdf"):
            return url

        # arXiv abstract page
        if "arxiv.org/abs/" in url:
            arxiv_id = url.split("/abs/")[-1].split("v")[0]
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        # arXiv PDF page (without .pdf extension)
        if "arxiv.org/pdf/" in url and not url.endswith(".pdf"):
            return url + ".pdf"

        # bioRxiv/medRxiv
        if "biorxiv.org/content/" in url or "medrxiv.org/content/" in url:
            if not url.endswith(".pdf"):
                return url.rstrip("/") + ".full.pdf"
            return url

        # PubMed Central
        if "ncbi.nlm.nih.gov/pmc/articles/" in url:
            if not url.endswith("/pdf/"):
                return url.rstrip("/") + "/pdf/"
            return url

        # DOI URL - try to follow redirect and find PDF
        if "doi.org/" in url:
            try:
                async with self._get_client() as client:
                    response = await client.head(url)
                    final_url = str(response.url)

                    # Check if redirected to a known source
                    if "arxiv.org" in final_url:
                        return await self._resolve_pdf_url(final_url)
                    if "biorxiv.org" in final_url or "medrxiv.org" in final_url:
                        return await self._resolve_pdf_url(final_url)
                    if "pmc/articles" in final_url:
                        return await self._resolve_pdf_url(final_url)

                    # Return the resolved URL
                    return final_url

            except Exception:
                pass

        # Return original URL as fallback
        return url

    def _extract_arxiv_id(self, text: str) -> str | None:
        """Extract arXiv ID from a string.

        Args:
            text: String that may contain an arXiv ID.

        Returns:
            arXiv ID or None.
        """
        # New format: YYMM.NNNNN
        new_format = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", text)
        if new_format:
            return new_format.group(1)

        # Old format: archive/YYMMNNN
        old_format = re.search(r"([a-z-]+/\d{7})(v\d+)?", text)
        if old_format:
            return old_format.group(1)

        return None

    def _generate_filename(self, original_url: str, pdf_url: str) -> str:
        """Generate a filename from URLs.

        Args:
            original_url: Original URL.
            pdf_url: Resolved PDF URL.

        Returns:
            Safe filename (without extension).
        """
        # Try to extract meaningful ID
        for url in [pdf_url, original_url]:
            # arXiv ID
            arxiv_id = self._extract_arxiv_id(url)
            if arxiv_id:
                return f"arxiv_{arxiv_id.replace('/', '_')}"

            # DOI
            if "10.1101" in url:  # bioRxiv/medRxiv
                match = re.search(r"10\.1101/[\d.]+", url)
                if match:
                    return f"preprint_{match.group().replace('/', '_').replace('.', '_')}"

            # PMC ID
            pmc_match = re.search(r"PMC\d+", url, re.IGNORECASE)
            if pmc_match:
                return pmc_match.group().lower()

        # Fallback: use URL hash
        import hashlib

        url_hash = hashlib.md5(original_url.encode()).hexdigest()[:12]
        return f"paper_{url_hash}"


async def download_pdf(
    url: str,
    output_dir: str | Path = ".",
    filename: str | None = None,
    overwrite: bool = False,
    timeout: float = 60.0,
    proxy: str | None = None,
    unpaywall_email: str | None = None,
) -> Path | None:
    """Convenience function to download a single PDF.

    Args:
        url: URL to download from.
        output_dir: Directory to save the PDF.
        filename: Optional filename (without extension).
        overwrite: Whether to overwrite existing files.
        timeout: Request timeout in seconds.
        proxy: Optional proxy URL.
        unpaywall_email: Email for Unpaywall API lookups.

    Returns:
        Path to downloaded file, or None if download failed.
    """
    downloader = PDFDownloader(output_dir, timeout, proxy, unpaywall_email)
    return await downloader.download(url, filename, overwrite)


async def download_papers(
    papers: list[Paper],
    output_dir: str | Path = ".",
    overwrite: bool = False,
    timeout: float = 60.0,
    proxy: str | None = None,
    unpaywall_email: str | None = None,
    max_concurrent: int = 5,
) -> dict[str, Path | None]:
    """Download PDFs for multiple papers with parallel downloads.

    Args:
        papers: List of Paper objects.
        output_dir: Directory to save PDFs.
        overwrite: Whether to overwrite existing files.
        timeout: Request timeout in seconds.
        proxy: Optional proxy URL.
        unpaywall_email: Email for Unpaywall API lookups (finds open access versions).
        max_concurrent: Maximum number of concurrent downloads (default: 5).

    Returns:
        Dictionary mapping paper titles to downloaded file paths (or None if failed).
    """
    import asyncio

    downloader = PDFDownloader(output_dir, timeout, proxy, unpaywall_email)
    semaphore = asyncio.Semaphore(max_concurrent)

    async def download_one(paper: Paper) -> tuple[str, Path | None]:
        """Download a single paper with semaphore control."""
        async with semaphore:
            # Generate safe filename from title
            safe_title = re.sub(r"[^\w\s-]", "", paper.title or "untitled")
            safe_title = re.sub(r"\s+", "_", safe_title)[:100]

            try:
                path = await downloader.download_paper(paper, safe_title, overwrite)
                return (paper.title or "untitled", path)
            except Exception as e:
                logger.error(f"Error downloading '{paper.title}': {e}")
                return (paper.title or "untitled", None)

    # Run all downloads concurrently
    tasks = [download_one(paper) for paper in papers]
    results_list = await asyncio.gather(*tasks, return_exceptions=False)

    return dict(results_list)
